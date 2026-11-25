"""Runtime: one manager per config entry, one controller per cover."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from functools import partial
import logging
import random
import time as monotonic_time
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION as COVER_ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    condition as ha_condition,
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
    script as ha_script,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import (
    CONF_COVER_ENTITY,
    CONF_PROFILE,
    CONF_SETTINGS,
    COVER_SWITCHES,
    DECISION_HISTORY,
    DOMAIN,
    EVENT_DRIVE,
    EVENT_MANUAL,
    EVENT_RAIN_WINDOW,
    FORECAST_SECONDS,
    GLOBAL_SWITCHES,
    SIGNAL_COVER_UPDATE,
    SIGNAL_GLOBAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORE_SAVE_DELAY,
    SUBENTRY_COVER,
    SUBENTRY_PROFILE,
    SWITCH_ADVENT,
    SWITCH_AUTOMATIC,
    SWITCH_COMFORT,
    SWITCH_EVENING,
    SWITCH_HARDWARE_LOCK,
    SWITCH_MORNING,
    SWITCH_PARTY,
    SWITCH_PAUSE,
    SWITCH_SELF_DEFENSE,
    SWITCH_SHADING,
    SWITCH_WEEKEND_TIMES,
    TICK_SECONDS,
)
from .engine.arbiter import (
    BLOCK_AT_TARGET,
    BLOCK_LOCKOUT,
    REASON_HEAT,
    REASON_MANUAL,
    REASON_RAIN_WINDOW,
    REASON_SERVICE,
    REASON_SHADING,
    REASON_WIGGLE,
    REASON_WINDOW_RETURN,
    TEMPORARY_REASONS,
    TRIGGER_APPLY_TARGET,
    TRIGGER_EXTERNAL,
    TRIGGER_FORCE,
    TRIGGER_OVERRIDE_END,
    TRIGGER_PRIVACY,
    TRIGGER_PROTECTION,
    TRIGGER_RELEASE,
    TRIGGER_RESIDENTS,
    TRIGGER_RESUME,
    TRIGGER_SCHEDULE_DOWN,
    TRIGGER_SCHEDULE_UP,
    TRIGGER_SHADING,
    TRIGGER_SHADING_END,
    TRIGGER_WINDOW,
    TRIGGER_WINDOW_CLOSED,
    Decision,
    Situation,
    build_wishes,
    decide,
)
from .engine.calendar import calendar_windows
from .engine.daynight import (
    DOWN,
    PRIVACY_DOWN,
    UP,
    DayMarks,
    condition_held,
    in_dynamic_window,
    is_day as daynight_is_day,
    light_condition,
    privacy_by_brightness,
    privacy_phase,
    privacy_times,
)
from .engine.override import manual_counts_as_scheduled, override_until
from .engine.protection import (
    FROST,
    PROTECTIONS,
    RAIN,
    RAIN_WINDOW,
    WIND,
    Protection,
    above,
    as_value,
    at_least,
    below,
    frost_effect,
    step as protection_step,
)
from .engine.residents import (
    SLEEPING,
    Source,
    parse_map,
    presence_allows,
    self_defense_due,
    status as residents_status,
)
from .engine.resolve import ResolvedConfig, resolve
from .engine.schedule import DaySchedule, day_schedule, default_workday, next_events
from .engine.settings import (
    FROST_OFF,
    KIND_CLOSE,
    KIND_OPEN,
    KIND_SHADING,
    KIND_VENTILATE,
    LOCKOUT_HARD,
    MODE_RESIDENTS,
    PRESENCE_OFF,
    RES_ABSENT,
    RES_AWOKEN,
    RES_HOME,
    RESET_NEXT_SCHEDULE,
    RETURN_PREVIOUS,
    TILT_AFTER,
    TILT_FIRST,
    WINDOW_CLOSED,
    WINDOW_OPEN,
    WINDOW_TILTED,
    WINDOWS_CALENDAR,
)
from .engine.shading import (
    OUT as SHADING_OUT,
    SHADED,
    Configured,
    Inputs,
    average,
    combine as shading_combine,
    conditions as shading_conditions,
    heat_active,
    in_time_window,
    step as shading_step,
    sun_left,
)
from .engine.special import advent_active, trigger_position, wiggle_target
from .engine.sun import Location, SunCalculator
from .engine.tilt import shading_tilt, tilt_for
from .engine.window import lockout_active, window_position, window_state

_LOGGER = logging.getLogger(__name__)

_UNUSABLE = (None, STATE_UNAVAILABLE, STATE_UNKNOWN)
STARTUP_GRACE = 30  # seconds after start without manual detection


def _never(*_args: Any, **_kwargs: Any) -> bool:
    """Condition that never holds (invalid configuration)."""
    return False


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def protection_raw(
    cfg: Mapping[str, Any],
    kind: str,
    rain: float | bool | None,
    wind: float | None,
    temp: float | None,
    active: bool,
) -> bool | None:
    """Raw state (threshold + hysteresis) of one protection; None = keep."""
    if kind == RAIN:
        return above(rain, cfg["rain_threshold"], cfg["rain_hysteresis"], active)
    if kind == RAIN_WINDOW:
        threshold = cfg["rain_window_threshold"]
        if threshold is None:
            threshold = cfg["rain_threshold"]
        return above(rain, threshold, cfg["rain_hysteresis"], active)
    if kind == WIND:
        return at_least(wind, cfg["wind_threshold"], cfg["wind_hysteresis"], active)
    return below(temp, cfg["frost_temp"], cfg["frost_hysteresis"], active)


def protection_delays(cfg: Mapping[str, Any], kind: str) -> tuple[int, int]:
    """Waits (minutes) before a protection starts and ends."""
    if kind == RAIN:
        return cfg["rain_delay_start"], cfg["rain_delay_end"]
    if kind == RAIN_WINDOW:
        # Water does not wait
        return 0, cfg["rain_delay_end"]
    if kind == WIND:
        return cfg["wind_delay_start"], cfg["wind_delay_end"]
    return 0, 0


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


def _state_value(hass: HomeAssistant, entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNUSABLE:
        return None
    return state.state


def _number(hass: HomeAssistant, entity_id: str | None) -> float | None:
    value = _state_value(hass, entity_id)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class AscManager:
    """Everything that belongs to the one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {"global": {}, "covers": {}}
        self.switches: dict[str, bool] = dict(GLOBAL_SWITCHES)
        self.controllers: dict[str, CoverController] = {}
        self.sun = self._make_sun()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._unsub_residents: CALLBACK_TYPE | None = None
        self.central_device_id: str | None = None
        # Last usable state of every resident source ("last known counts")
        self.resident_sources: dict[str, Source] = {}
        # Weather forecast per entity: (monotonic time of fetch, max temperature today)
        self.forecasts: dict[str, tuple[float, float | None]] = {}
        self._forecast_pending: set[str] = set()
        # Rain / wind / frost of the global sensors (central device)
        self.global_protect: dict[str, Protection] = {k: Protection() for k in PROTECTIONS}

    # --- configuration ----------------------------------------------------

    @property
    def global_settings(self) -> Mapping[str, Any]:
        """Settings of the main entry."""
        return self.entry.options.get(CONF_SETTINGS, {})

    def profile_settings(self, profile_id: str | None) -> Mapping[str, Any] | None:
        """Settings of a profile subentry."""
        if not profile_id:
            return None
        sub = self.entry.subentries.get(profile_id)
        if sub is None or sub.subentry_type != SUBENTRY_PROFILE:
            return None
        return sub.data.get(CONF_SETTINGS, {})

    def resolve_cover(self, subentry_id: str) -> ResolvedConfig:
        """Resolve the settings of one cover subentry."""
        sub = self.entry.subentries[subentry_id]
        return resolve(
            self.global_settings,
            self.profile_settings(sub.data.get(CONF_PROFILE)),
            sub.data.get(CONF_SETTINGS, {}),
        )

    @property
    def global_cfg(self) -> ResolvedConfig:
        """Resolved global settings (with defaults)."""
        return resolve(self.global_settings)

    def resident_source(self, entity_id: str) -> Source | None:
        """State of a resident source; the last known one while unavailable."""
        state = self.hass.states.get(entity_id)
        if state is not None and state.state not in _UNUSABLE:
            source = Source(entity_id, state.state, state.last_changed)
            self.resident_sources[entity_id] = source
            return source
        return self.resident_sources.get(entity_id)

    def residents(self, entities, cfg, now: datetime) -> str | None:
        """Combined status of resident source entities."""
        sources = [s for s in (self.resident_source(e) for e in entities) if s is not None]
        return residents_status(
            sources, parse_map(cfg["residents_map"]), now, cfg["residents_gone_hours"]
        )

    def house_status(self, now: datetime | None = None) -> str | None:
        """House status from the global sources (sensor of the central device)."""
        cfg = self.global_cfg
        return self.residents(cfg["residents_house"], cfg, now or dt_util.utcnow())

    def _subscribe_residents(self) -> None:
        if self._unsub_residents:
            self._unsub_residents()
            self._unsub_residents = None
        entities = list(self.global_cfg["residents_house"])
        if entities:
            self._unsub_residents = async_track_state_change_event(
                self.hass, entities, self._on_global_residents
            )

    @callback
    def _on_global_residents(self, _event: Event) -> None:
        async_dispatcher_send(self.hass, SIGNAL_GLOBAL_UPDATE)

    def forecast(self, entity_id: str) -> float | None:
        """Forecast maximum temperature of today (refreshed in the background)."""
        entry = self.forecasts.get(entity_id)
        if entry is None or monotonic_time.monotonic() - entry[0] > FORECAST_SECONDS:
            self._refresh_forecast(entity_id)
        return entry[1] if entry else None

    def _refresh_forecast(self, entity_id: str) -> None:
        if entity_id in self._forecast_pending:
            return
        self._forecast_pending.add(entity_id)
        self.entry.async_create_background_task(
            self.hass, self._async_fetch_forecast(entity_id), f"{DOMAIN} forecast {entity_id}"
        )

    async def _async_fetch_forecast(self, entity_id: str) -> None:
        value: float | None = None
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {ATTR_ENTITY_ID: entity_id, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            forecasts = (response or {}).get(entity_id, {}).get("forecast", [])
            today = dt_util.now(self.tz).date()
            for item in forecasts:
                when = dt_util.parse_datetime(str(item.get("datetime", "")))
                if when is None or dt_util.as_local(when).date() == today:
                    value = item.get("temperature")
                    break
            if value is None and forecasts:
                value = forecasts[0].get("temperature")
            value = float(value) if value is not None else None
        except Exception as err:  # noqa: BLE001 - weather may be unavailable
            _LOGGER.warning("Forecast of %s not readable: %s", entity_id, err)
        finally:
            self._forecast_pending.discard(entity_id)
        self.forecasts[entity_id] = (monotonic_time.monotonic(), value)

    def structure(self) -> set[str]:
        """Return the subentry ids; a change needs a reload."""
        return set(self.entry.subentries)

    def _make_sun(self) -> SunCalculator:
        cfg = self.hass.config
        return SunCalculator(
            Location(cfg.latitude, cfg.longitude, cfg.elevation, dt_util.get_default_time_zone())
        )

    @property
    def tz(self):
        """Local time zone."""
        return dt_util.get_default_time_zone()

    # --- life cycle ---------------------------------------------------------

    async def async_start(self) -> None:
        """Load state and start all controllers."""
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, self.entry.entry_id)},
            name="AutoShuttersControl",
            manufacturer="AutoShuttersControl for HA",
            model="AutoShuttersControl",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self.central_device_id = device.id
        stored = await self.store.async_load()
        if stored:
            self.data = stored
        self.data.setdefault("global", {})
        self.data.setdefault("covers", {})
        for key, value in self.data["global"].get("switches", {}).items():
            if key in self.switches:
                self.switches[key] = bool(value)

        for sub_id, sub in self.entry.subentries.items():
            if sub.subentry_type != SUBENTRY_COVER:
                continue
            state = self.data["covers"].setdefault(sub_id, {})
            controller = CoverController(
                self, sub_id, sub.data[CONF_COVER_ENTITY], sub.title, state
            )
            self.controllers[sub_id] = controller
        # Forget state of removed covers
        for sub_id in list(self.data["covers"]):
            if sub_id not in self.controllers:
                self.data["covers"].pop(sub_id)

        for controller in self.controllers.values():
            await controller.async_compile()
            controller.async_start()
        self._subscribe_residents()
        self.global_protection(dt_util.utcnow())

        self._unsubs.append(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=5)
        )
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._core_config))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=TICK_SECONDS))
        )

    @callback
    def _tick(self, now: datetime) -> None:
        self.global_protection(now)
        for controller in self.controllers.values():
            controller.tick()

    @callback
    def global_protection(self, now: datetime) -> None:
        cfg = self.global_cfg
        changed = False
        rain = as_value(_state_value(self.hass, cfg["rain_sensor"]))
        wind = _number(self.hass, cfg["wind_sensor"])
        temp = _number(self.hass, cfg["outdoor_temperature_sensor"])
        for kind in (RAIN, WIND, FROST):
            old = self.global_protect[kind]
            raw = protection_raw(cfg, kind, rain, wind, temp, old.active)
            new = protection_step(old, raw, now, *protection_delays(cfg, kind))
            if new.active != old.active:
                changed = True
            self.global_protect[kind] = new
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_GLOBAL_UPDATE)

    @callback
    def release_deferred(self, controllers=None) -> None:
        """Advent: do the deferred evening drives now."""
        for controller in controllers or self.controllers.values():
            controller.release_advent()

    async def async_stop(self) -> None:
        """Stop everything and save."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_residents:
            self._unsub_residents()
            self._unsub_residents = None
        for controller in self.controllers.values():
            controller.async_stop()
        await self.store.async_save(self.data)

    @callback
    def async_reconfigure(self) -> None:
        """Settings changed without new or removed subentries."""
        for controller in self.controllers.values():
            sub = self.entry.subentries[controller.subentry_id]
            controller.name = sub.title
            controller.async_reconfigure(sub.data[CONF_COVER_ENTITY])
            self.entry.async_create_background_task(
                self.hass, controller.async_compile(), f"{DOMAIN} compile {controller.cover_entity}"
            )
        self._subscribe_residents()
        async_dispatcher_send(self.hass, SIGNAL_GLOBAL_UPDATE)

    @callback
    def _midnight(self, _now: datetime) -> None:
        self.recalculate()

    @callback
    def _core_config(self, _event: Event) -> None:
        self.sun = self._make_sun()
        self.recalculate()

    @callback
    def recalculate(self) -> None:
        """Recalculate all schedules."""
        for controller in self.controllers.values():
            controller.recalculate()

    @callback
    def save(self) -> None:
        """Save the state later."""
        self.data["global"]["switches"] = dict(self.switches)
        self.store.async_delay_save(lambda: self.data, STORE_SAVE_DELAY)

    # --- global switches ------------------------------------------------------

    @callback
    def set_switch(self, key: str, value: bool) -> None:
        """Change a global switch."""
        old = self.switches[key]
        self.switches[key] = value
        self.save()
        async_dispatcher_send(self.hass, SIGNAL_GLOBAL_UPDATE)
        if key in (SWITCH_WEEKEND_TIMES, SWITCH_MORNING, SWITCH_EVENING):
            self.recalculate()
        if key == SWITCH_COMFORT and old != value:
            for controller in self.controllers.values():
                if controller.window_state not in (None, WINDOW_CLOSED):
                    controller.evaluate(TRIGGER_WINDOW)
        if key in (SWITCH_SHADING, SWITCH_SELF_DEFENSE) and old != value:
            for controller in self.controllers.values():
                controller.tick()
        if key == SWITCH_HARDWARE_LOCK and old != value:
            for controller in self.controllers.values():
                controller.apply_hardware_lock()
        if key in (SWITCH_PARTY, SWITCH_ADVENT) and old and not value:
            # Deferred drives are calculated again
            for controller in self.controllers.values():
                controller.evaluate(TRIGGER_RESUME)
        if key == SWITCH_PAUSE and old and not value:
            for controller in self.controllers.values():
                controller.evaluate(TRIGGER_RESUME)
        for controller in self.controllers.values():
            controller.notify()


class CoverController:
    """Controls one cover."""

    def __init__(
        self,
        manager: AscManager,
        subentry_id: str,
        cover_entity: str,
        name: str,
        state: dict[str, Any],
    ) -> None:
        self.manager = manager
        self.hass = manager.hass
        self.subentry_id = subentry_id
        self.cover_entity = cover_entity
        self.name = name
        self.state = state
        state.setdefault("switches", dict(COVER_SWITCHES))
        for key, value in COVER_SWITCHES.items():
            state["switches"].setdefault(key, value)
        self.cfg: ResolvedConfig = manager.resolve_cover(subentry_id)
        self.next_up: datetime | None = None
        self.next_down: datetime | None = None
        self.next_privacy: datetime | None = None
        self.last_decision: Decision | None = None
        self.decisions: deque[dict[str, Any]] = deque(maxlen=DECISION_HISTORY)
        self._own_contexts: deque[str] = deque(maxlen=20)
        self._active_drive: tuple[int, float] | None = None
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._unsub_up: CALLBACK_TYPE | None = None
        self._unsub_down: CALLBACK_TYPE | None = None
        self._unsub_override: CALLBACK_TYPE | None = None
        self._unsub_delay: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        # Manual drives are only detected some time after Home Assistant started,
        # because many covers report their restored state again during startup.
        self._detect_from: float | None = None
        self.window_state: str | None = None
        self._unsub_window_delay: CALLBACK_TYPE | None = None
        self._unsub_privacy: CALLBACK_TYPE | None = None
        self._light_since: dict[str, datetime | None] = {UP: None, DOWN: None}
        self._calendar: dict[date, dict[str, tuple]] = {}
        self._calendar_task: Any = None
        self._res_key: tuple | None = None
        self._brightness: deque[tuple[datetime, float]] = deque(maxlen=120)
        self._tilt_wait: tuple[int, int, Context] | None = None
        self._unsub_tilt: CALLBACK_TYPE | None = None
        self._unsub_position: CALLBACK_TYPE | None = None
        self._unsub_wiggle: CALLBACK_TYPE | None = None
        # Last usable state of force / pause / trigger entities
        self._last_states: dict[str, str] = {}
        self._force: str | None = None
        self._trigger_pos: int | None = None
        self._frost_effect: tuple[bool, bool] = (False, False)
        self._rain_window_notified = False
        self._conditions: dict[str, list[Any]] = {}
        self._actions: dict[str, Any] = {}

    # --- life cycle ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Subscribe and schedule."""
        self._subscribe()
        self._restore_override()
        self.window_state = self._read_window()
        self.recalculate()
        self._res_key = self._residents_key(dt_util.utcnow())
        self._force = self.force_kind()
        self._trigger_pos = self.trigger_pos()
        self._protection_tick(dt_util.utcnow(), evaluate=False)
        self._unsub_started = async_at_started(self.hass, self._on_started)

    @callback
    def async_stop(self) -> None:
        """Cancel everything."""
        self._unsubscribe()
        for name in (
            "_unsub_up",
            "_unsub_down",
            "_unsub_override",
            "_unsub_delay",
            "_unsub_started",
            "_unsub_window_delay",
            "_unsub_privacy",
            "_unsub_tilt",
            "_unsub_position",
            "_unsub_wiggle",
        ):
            unsub = getattr(self, name)
            if unsub:
                unsub()
                setattr(self, name, None)

    @callback
    def async_reconfigure(self, cover_entity: str) -> None:
        """Settings changed."""
        self.cover_entity = cover_entity
        self.cfg = self.manager.resolve_cover(self.subentry_id)
        self._unsubscribe()
        self._subscribe()
        self._check_cover_exists(None)
        self._calendar.clear()
        self.window_state = self._read_window()
        self.recalculate()
        self._res_key = self._residents_key(dt_util.utcnow())
        self._force = self.force_kind()
        self._trigger_pos = self.trigger_pos()
        self.apply_hardware_lock()

    def _subscribe(self) -> None:
        self._unsub_listeners.append(
            async_track_state_change_event(self.hass, [self.cover_entity], self._on_cover_change)
        )
        sensors = [
            e for e in (self.cfg["workday_sensor"], self.cfg["workday_tomorrow_sensor"]) if e
        ]
        if sensors:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, sensors, self._on_workday_change)
            )
        if self.cfg["position_entity"]:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self.cfg["position_entity"]], self._on_position_entity_change
                )
            )
        windows = [
            e
            for e in (
                self.cfg["window_open_sensor"],
                self.cfg["window_tilted_sensor"],
                self.cfg["window_state_sensor"],
            )
            if e
        ]
        if windows:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, windows, self._on_window_change)
            )
        light = [e for e in (self.cfg["brightness_sensor"], self.cfg["elevation_sensor"]) if e]
        if light:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, light, self._on_light_change)
            )
        residents = [*self.cfg["residents_house"], *self.cfg["residents_room"]]
        if residents:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, residents, self._on_residents_change)
            )
        special = [
            e
            for e in (
                self.cfg["force_close"],
                self.cfg["force_open"],
                self.cfg["force_ventilate"],
                self.cfg["force_shading"],
                self.cfg["pause_entity"],
                self.cfg["trigger_entity"],
            )
            if e
        ]
        if special:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, special, self._on_special_change)
            )
        weather = [
            e
            for e in (
                self.cfg["rain_sensor"],
                self.cfg["wind_sensor"],
                self.cfg["outdoor_temperature_sensor"],
            )
            if e
        ]
        if weather:
            self._unsub_listeners.append(
                async_track_state_change_event(self.hass, weather, self._on_weather_change)
            )
        if self.cfg["shading_alt_entity"]:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self.cfg["shading_alt_entity"]], self._on_shading_alt_change
                )
            )
        if self.cfg["calendar"] and self.cfg["time_source"] == WINDOWS_CALENDAR:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self.cfg["calendar"]], self._on_calendar_change
                )
            )

    def _unsubscribe(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    @callback
    def _on_started(self, hass: HomeAssistant) -> None:
        self._unsub_started = None
        self._detect_from = monotonic_time.monotonic() + STARTUP_GRACE
        self._check_cover_exists(hass)

    @callback
    def _check_cover_exists(self, _hass: HomeAssistant | None) -> None:
        issue_id = f"cover_missing_{self.subentry_id}"
        if self.hass.states.get(self.cover_entity) is None:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="cover_missing",
                translation_placeholders={"name": self.name, "entity_id": self.cover_entity},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # --- helpers ------------------------------------------------------------

    @property
    def switches(self) -> dict[str, bool]:
        """Per cover switches."""
        return self.state["switches"]

    @callback
    def notify(self) -> None:
        """Tell the entities to update."""
        async_dispatcher_send(self.hass, SIGNAL_COVER_UPDATE.format(self.subentry_id))

    def _save(self) -> None:
        self.manager.save()

    @property
    def tz(self):
        """Local time zone."""
        return self.manager.tz

    def is_workday(self, day: date) -> bool:
        """Workday from the sensors, otherwise Monday to Friday."""
        today = dt_util.now(self.tz).date()
        entity = None
        if day == today:
            entity = self.cfg["workday_sensor"]
        elif day == today + timedelta(days=1):
            entity = self.cfg["workday_tomorrow_sensor"]
        if entity:
            state = self.hass.states.get(entity)
            if state is not None and state.state in (STATE_ON, STATE_OFF):
                return state.state == STATE_ON
        return default_workday(day)

    def schedule_for(self, day: date) -> DaySchedule:
        """Schedule of a day."""
        return day_schedule(
            self.cfg,
            day,
            self.manager.sun,
            self.tz,
            self.is_workday,
            self.manager.switches[SWITCH_WEEKEND_TIMES],
            self._windows,
        )

    def marks_for(self, day: date) -> DayMarks:
        """What already happened on a day (dynamic drives, privacy by brightness)."""
        marks = self.state.get("marks")
        if not marks or marks.get("date") != day.isoformat():
            return DayMarks()
        return DayMarks(
            up=_parse(marks.get("up")),
            down=_parse(marks.get("down")),
            privacy_down=_parse(marks.get("privacy_down")),
        )

    def _set_mark(self, now: datetime, key: str) -> None:
        today = now.astimezone(self.tz).date().isoformat()
        marks = self.state.get("marks")
        if not marks or marks.get("date") != today:
            marks = {"date": today}
        marks[key] = _iso(now)
        self.state["marks"] = marks
        self._save()

    def is_day(self, now: datetime | None = None) -> bool:
        """True between morning and evening drive."""
        now = now or dt_util.now(self.tz)
        day = now.astimezone(self.tz).date()
        return daynight_is_day(self.schedule_for(day), self.marks_for(day), now)

    def privacy_phase(self, now: datetime | None = None) -> str | None:
        """Current privacy phase or None."""
        now = now or dt_util.now(self.tz)
        day = now.astimezone(self.tz).date()
        return privacy_phase(self.cfg, self.schedule_for(day), self.marks_for(day), now)

    # --- calendar -------------------------------------------------------------

    def _windows(self, day: date) -> dict[str, tuple] | None:
        if self.cfg["time_source"] != WINDOWS_CALENDAR or not self.cfg["calendar"]:
            return None
        return self._calendar.get(day)

    def _refresh_calendar(self) -> None:
        if self.cfg["time_source"] != WINDOWS_CALENDAR or not self.cfg["calendar"]:
            return
        if self._calendar_task is not None and not self._calendar_task.done():
            return
        self._calendar_task = self.hass.async_create_background_task(
            self._async_fetch_calendar(), f"{DOMAIN} calendar {self.cover_entity}"
        )

    async def _async_fetch_calendar(self) -> None:
        entity = self.cfg["calendar"]
        today = dt_util.now(self.tz).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=self.tz)
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    ATTR_ENTITY_ID: entity,
                    "start_date_time": start.isoformat(),
                    "end_date_time": (start + timedelta(days=3)).isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - calendar may be unavailable
            _LOGGER.warning("%s: calendar %s not readable: %s", self.cover_entity, entity, err)
            return
        events = (response or {}).get(entity, {}).get("events", [])
        windows = calendar_windows(
            events,
            self.cfg["calendar_open_title"],
            self.cfg["calendar_close_title"],
            self.tz,
        )
        if windows != self._calendar:
            self._calendar = windows
            self.recalculate(fetch=False)

    @callback
    def _on_calendar_change(self, _event: Event) -> None:
        self._refresh_calendar()

    @property
    def cover_state(self) -> State | None:
        """State of the cover entity."""
        return self.hass.states.get(self.cover_entity)

    def current_position(self) -> float | None:
        """Position 0 (closed) .. 100 (open), from the cover or a sensor."""
        value: Any = None
        if self.cfg["position_entity"]:
            state = self.hass.states.get(self.cfg["position_entity"])
            if state is not None and state.state not in _UNUSABLE:
                value = state.state
        else:
            state = self.cover_state
            if state is None or state.state in _UNUSABLE:
                return None
            value = state.attributes.get(ATTR_CURRENT_POSITION)
            if value is None:
                if state.state == CoverState.OPEN:
                    value = 100
                elif state.state == CoverState.CLOSED:
                    value = 0
        try:
            position = float(value)
        except (TypeError, ValueError):
            return None
        return 100 - position if self.cfg["invert"] else position

    @property
    def available(self) -> bool:
        """Cover can be driven."""
        state = self.cover_state
        return state is not None and state.state not in _UNUSABLE

    @property
    def moving(self) -> bool:
        """Motor is running."""
        state = self.cover_state
        return state is not None and state.state in (CoverState.OPENING, CoverState.CLOSING)

    # --- override -----------------------------------------------------------

    @property
    def override(self) -> dict[str, Any] | None:
        """Active manual override or None."""
        return self.state.get("override")

    @property
    def override_active(self) -> bool:
        """True while a manual override is active."""
        return self.override is not None

    @property
    def override_until(self) -> datetime | None:
        """End of the manual override."""
        return _parse(self.override["until"]) if self.override else None

    def _restore_override(self) -> None:
        if not self.override:
            return
        until = self.override_until
        if until is not None and until <= dt_util.utcnow():
            self.state["override"] = None
            self._save()
            return
        self._schedule_override_end(until)

    def _schedule_override_end(self, until: datetime | None) -> None:
        if self._unsub_override:
            self._unsub_override()
            self._unsub_override = None
        if until is not None:
            self._unsub_override = async_track_point_in_time(
                self.hass, self._on_override_end, until
            )

    @callback
    def _on_override_end(self, _now: datetime) -> None:
        self._unsub_override = None
        self.clear_override()

    @callback
    def set_override(self, now: datetime) -> None:
        """A manual drive was detected."""
        until = override_until(self.cfg, now, self.tz)
        self.state["override"] = {"since": _iso(now), "until": _iso(until)}
        self._schedule_override_end(until)
        position = self.current_position()
        kind = manual_counts_as_scheduled(
            self.cfg, self.schedule_for(now.astimezone(self.tz).date()), now, position
        )
        if kind:
            self._mark_done(now, kind)
        self.state["last"] = {
            "reason": REASON_MANUAL,
            "trigger": None,
            "position": position,
            "time": _iso(now),
        }
        self._save()
        self.hass.bus.async_fire(
            EVENT_MANUAL,
            {"entity_id": self.cover_entity, "name": self.name, "position": position},
        )
        self.run_action("manual", {"position": position})
        self.notify()

    @callback
    def clear_override(self, *, apply: bool | None = None) -> None:
        """End the manual override (timer, schedule, service or button)."""
        if self._unsub_override:
            self._unsub_override()
            self._unsub_override = None
        if self.state.get("override") is None:
            return
        self.state["override"] = None
        self._save()
        self.notify()
        self.run_action("override_end", {})
        if apply if apply is not None else self.cfg["override_return"]:
            self.evaluate(TRIGGER_OVERRIDE_END)

    def _mark_done(self, now: datetime, kind: str) -> None:
        today = now.astimezone(self.tz).date().isoformat()
        done = self.state.get("done")
        if not done or done.get("date") != today:
            done = {"date": today, "kinds": []}
        if kind not in done["kinds"]:
            done["kinds"].append(kind)
        self.state["done"] = done

    def done_today(self, now: datetime) -> frozenset[str]:
        """Drive kinds already done by hand today."""
        done = self.state.get("done")
        if not done or done.get("date") != now.astimezone(self.tz).date().isoformat():
            return frozenset()
        return frozenset(done.get("kinds", ()))

    # --- schedule -----------------------------------------------------------

    def _next_events(self, now: datetime) -> tuple[datetime, datetime]:
        return next_events(
            self.cfg,
            now,
            self.manager.sun,
            self.tz,
            self.is_workday,
            self.manager.switches[SWITCH_WEEKEND_TIMES],
            self._windows,
        )

    @callback
    def recalculate(self, *, fetch: bool = True) -> None:
        """Compute the next morning and evening drive and set timers."""
        if fetch:
            self._refresh_calendar()
        now = dt_util.now(self.tz)
        today = now.astimezone(self.tz).date()
        sched = self.schedule_for(today)
        marks = self.marks_for(today)
        self.next_up, self.next_down = self._next_events(now)
        # A dynamic drive that already happened today: the next one is tomorrow
        if marks.up is not None and self.next_up == sched.up:
            self.next_up = self._next_events(sched.up)[0]
        if marks.down is not None and self.next_down == sched.down:
            self.next_down = self._next_events(sched.down)[1]
        for unsub in (self._unsub_up, self._unsub_down, self._unsub_privacy):
            if unsub:
                unsub()
        self._unsub_up = async_track_point_in_time(self.hass, self._on_up, self.next_up)
        self._unsub_down = async_track_point_in_time(self.hass, self._on_down, self.next_down)
        self._unsub_privacy = None
        self.next_privacy = self._next_privacy(now)
        if self.next_privacy is not None:
            self._unsub_privacy = async_track_point_in_time(
                self.hass, self._on_privacy, self.next_privacy
            )
        self.notify()

    def _next_privacy(self, now: datetime) -> datetime | None:
        today = now.astimezone(self.tz).date()
        for offset in (0, 1):
            day = today + timedelta(days=offset)
            times = privacy_times(self.cfg, self.schedule_for(day), self.marks_for(day))
            upcoming = sorted(t for t in times.values() if t > now)
            if upcoming:
                return upcoming[0]
        return None

    @callback
    def _on_privacy(self, _now: datetime) -> None:
        self._unsub_privacy = None
        self.evaluate(TRIGGER_PRIVACY, delayed=True)
        self.recalculate(fetch=False)

    @callback
    def _on_up(self, now: datetime) -> None:
        self._unsub_up = None
        if self.marks_for(now.astimezone(self.tz).date()).up is not None:
            # Already opened earlier by brightness / sun elevation
            self.recalculate(fetch=False)
            return
        self._schedule_event(TRIGGER_SCHEDULE_UP)

    @callback
    def _on_down(self, now: datetime) -> None:
        self._unsub_down = None
        if self.marks_for(now.astimezone(self.tz).date()).down is not None:
            self.recalculate(fetch=False)
            return
        self._schedule_event(TRIGGER_SCHEDULE_DOWN)

    # --- brightness, sun elevation, privacy by brightness ---------------------

    def _number(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _UNUSABLE:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    @callback
    def _on_light_change(self, _event: Event) -> None:
        self.tick()

    @callback
    def tick(self) -> None:
        """Check the dynamic modes and the privacy by brightness."""
        now = dt_util.now(self.tz)
        self._protection_tick(now)
        self._check_residents(now)
        self._shading_tick(now)
        today = now.astimezone(self.tz).date()
        sched = self.schedule_for(today)
        marks = self.marks_for(today)
        brightness = self._number(self.cfg["brightness_sensor"])
        for direction, mark, trigger in (
            (UP, marks.up, TRIGGER_SCHEDULE_UP),
            (DOWN, marks.down, TRIGGER_SCHEDULE_DOWN),
        ):
            if mark is not None or not in_dynamic_window(sched, direction, now):
                self._light_since[direction] = None
                continue
            residents_mode = self.cfg[f"{direction}_mode"] == MODE_RESIDENTS
            if residents_mode:
                resident = self.resident_status(now)
                met = resident in ((RES_AWOKEN, RES_HOME) if direction == UP else SLEEPING)
            else:
                met = light_condition(
                    self.cfg,
                    direction,
                    brightness,
                    self.manager.sun.elevation(now),
                    self._number(self.cfg["elevation_sensor"]),
                )
            if not met:
                self._light_since[direction] = None
                continue
            if self._light_since[direction] is None:
                self._light_since[direction] = now
            duration = 0 if residents_mode else self.cfg["brightness_duration"]
            if condition_held(self._light_since[direction], now, duration):
                self._light_since[direction] = None
                self._set_mark(now, direction)
                self._schedule_event(trigger)
                return
        if privacy_by_brightness(self.cfg, sched, marks, now, brightness):
            self._set_mark(now, PRIVACY_DOWN)
            self.evaluate(TRIGGER_PRIVACY, delayed=True)
            self.recalculate(fetch=False)

    # --- rain, wind, frost ------------------------------------------------------

    def protection(self, kind: str) -> bool:
        """Protection active (after hysteresis and waits)."""
        return bool(((self.state.get("protect") or {}).get(kind) or {}).get("active"))

    def protections(self) -> dict[str, bool]:
        """Which protections act on this cover now."""
        cfg = self.cfg
        rain_window = (
            cfg["rain_window"]
            and self.protection(RAIN_WINDOW)
            and self.window_state in cfg["rain_window_states"]
        )
        return {
            RAIN: bool(cfg["rain_protection"] and self.protection(RAIN)),
            RAIN_WINDOW: bool(rain_window),
            WIND: bool(cfg["wind_protection"] and self.protection(WIND)),
            FROST: cfg["frost_mode"] != FROST_OFF and self.protection(FROST),
        }

    def _frost_now(self, now: datetime) -> tuple[bool, bool]:
        local = now.astimezone(self.tz).time().replace(tzinfo=None)
        return frost_effect(self.cfg, self.protections()[FROST], local)

    @callback
    def _protection_tick(self, now: datetime, *, evaluate: bool = True) -> None:
        cfg = self.cfg
        stored = self.state.setdefault("protect", {})
        before = self.protections()
        rain = as_value(_state_value(self.hass, cfg["rain_sensor"]))
        wind = _number(self.hass, cfg["wind_sensor"])
        temp = _number(self.hass, cfg["outdoor_temperature_sensor"])
        changed = False
        for kind in PROTECTIONS:
            data = stored.get(kind) or {}
            old = Protection(bool(data.get("active")), _parse(data.get("pending")))
            raw = protection_raw(cfg, kind, rain, wind, temp, old.active)
            new = protection_step(old, raw, now, *protection_delays(cfg, kind))
            if new != old:
                stored[kind] = {"active": new.active, "pending": _iso(new.pending_since)}
                changed = True
        if changed:
            self._save()
            self.notify()
        after = self.protections()
        frost = self._frost_now(now)
        frost_changed = frost != self._frost_effect
        self._frost_effect = frost
        if evaluate and (after != before or frost_changed):
            self.evaluate(TRIGGER_PROTECTION)

    @callback
    def _on_weather_change(self, _event: Event) -> None:
        now = dt_util.now(self.tz)
        self.manager.global_protection(now)
        self._protection_tick(now)

    # --- force, pause entity, external trigger ---------------------------------

    def _entity_state(self, entity_id: str | None) -> str | None:
        """State of an entity; the last known one while unavailable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is not None and state.state not in _UNUSABLE:
            self._last_states[entity_id] = state.state
            return state.state
        return self._last_states.get(entity_id)

    def force_kind(self) -> str | None:
        """Active force function (close, open, ventilate, shading) or None."""
        for name in ("close", "open", "ventilate", "shading"):
            if self._entity_state(self.cfg[f"force_{name}"]) == STATE_ON:
                return name
        return None

    @property
    def pause_entity_on(self) -> bool:
        """Pause by the entity of this cover."""
        return self._entity_state(self.cfg["pause_entity"]) == STATE_ON

    def trigger_pos(self) -> int | None:
        """Position of the external trigger, None if not active."""
        return trigger_position(self.cfg, self._entity_state(self.cfg["trigger_entity"]))

    @callback
    def _on_special_change(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")
        if entity_id == self.cfg["pause_entity"]:
            self.notify()
            was_on = old_state is not None and old_state.state == STATE_ON
            if was_on and new_state is not None and new_state.state == STATE_OFF:
                self.evaluate(TRIGGER_RESUME)
            return
        force = self.force_kind()
        if force != self._force:
            ended = force is None
            self._force = force
            self.notify()
            if not ended or self.cfg["force_return"]:
                self.evaluate(TRIGGER_FORCE)
            return
        position = self.trigger_pos()
        if position != self._trigger_pos:
            ended = position is None
            self._trigger_pos = position
            self.notify()
            if not ended or self.cfg["trigger_return"]:
                self.evaluate(TRIGGER_EXTERNAL)

    # --- party, advent ------------------------------------------------------------

    def advent_now(self, now: datetime | None = None) -> bool:
        """Advent defers the closing of this cover now."""
        if not (self.manager.switches[SWITCH_ADVENT] and self.cfg["advent"]):
            return False
        day = (now or dt_util.now(self.tz)).astimezone(self.tz).date()
        if self.state.get("advent_released") == day.isoformat():
            return False
        return advent_active(self.cfg, day)

    @callback
    def release_advent(self) -> None:
        """Do the closing deferred by advent now (for today)."""
        today = dt_util.now(self.tz).date().isoformat()
        self.state["advent_released"] = today
        self._save()
        self.evaluate(TRIGGER_RELEASE)

    # --- wiggle, hardware lock --------------------------------------------------

    @callback
    def wiggle(self) -> bool:
        """Move a little and back (function check)."""
        current = self.current_position()
        if current is None or not self.available or self._unsub_wiggle:
            return False
        self._drive(wiggle_target(self.cfg, current), REASON_WIGGLE, None)
        self._unsub_wiggle = async_call_later(
            self.hass,
            self.cfg["wiggle_wait"],
            partial(self._wiggle_back, int(round(current))),
        )
        return True

    @callback
    def _wiggle_back(self, position: int, _now: datetime) -> None:
        self._unsub_wiggle = None
        self._drive(position, REASON_WIGGLE, None)

    @callback
    def apply_hardware_lock(self) -> None:
        """Hard lock-out: lock the actuator while the door is open."""
        entity = self.cfg["lockout_entity"]
        if not entity or self.cfg["lockout"] != LOCKOUT_HARD:
            return
        want = self.manager.switches[SWITCH_HARDWARE_LOCK] and lockout_active(
            self.cfg, self.window_state
        )
        if self.state.get("hardware_lock", False) == want:
            return
        self.state["hardware_lock"] = want
        self._save()
        domain = entity.split(".", 1)[0]
        if domain == "lock":
            service = "lock" if want else "unlock"
        else:
            service = "turn_on" if want else "turn_off"
        self.hass.async_create_task(
            self.hass.services.async_call(
                domain, service, {ATTR_ENTITY_ID: entity}, blocking=False
            ),
            f"{DOMAIN} hardware lock {entity}",
        )

    # --- extra conditions and actions -------------------------------------------

    async def async_compile(self) -> None:
        """Prepare the extra conditions and actions of this cover."""
        conditions: dict[str, list[Any]] = {}
        actions: dict[str, Any] = {}
        for name in ("all", "open", "close", "ventilate", "shading"):
            config = self.cfg[f"condition_{name}"]
            if not config:
                continue
            try:
                validated = await ha_condition.async_validate_conditions_config(
                    self.hass, cv.CONDITIONS_SCHEMA(list(config))
                )
                conditions[name] = [
                    await ha_condition.async_from_config(self.hass, c) for c in validated
                ]
            except (HomeAssistantError, vol.Invalid) as err:
                _LOGGER.warning("%s: extra condition %s invalid: %s", self.name, name, err)
                conditions[name] = [_never]
        for name in ("drive", "manual", "override_end", "rain_window"):
            config = self.cfg[f"action_{name}"]
            if not config:
                continue
            try:
                validated = await ha_script.async_validate_actions_config(
                    self.hass, cv.SCRIPT_SCHEMA(list(config))
                )
            except (HomeAssistantError, vol.Invalid) as err:
                _LOGGER.warning("%s: extra action %s invalid: %s", self.name, name, err)
                continue
            actions[name] = ha_script.Script(
                self.hass,
                validated,
                f"ASC {self.name} {name}",
                DOMAIN,
                script_mode=ha_script.SCRIPT_MODE_PARALLEL,
                max_runs=10,
            )
        self._conditions = conditions
        self._actions = actions

    def condition_ok(self, name: str, variables: dict[str, Any]) -> bool:
        """Extra condition of a drive kind (True if not set)."""
        checks = self._conditions.get(name)
        if not checks:
            return True
        try:
            return all(bool(check(self.hass, variables)) for check in checks)
        except HomeAssistantError as err:
            _LOGGER.debug("%s: condition %s failed: %s", self.name, name, err)
            return False

    def run_action(
        self, name: str, variables: dict[str, Any], context: Context | None = None
    ) -> None:
        """Run an extra action in the background."""
        action = self._actions.get(name)
        if action is None:
            return
        variables = {"cover": self.cover_entity, "name": self.name, **variables}
        self.hass.async_create_task(
            action.async_run(variables, context=context), f"{DOMAIN} action {name}"
        )

    # --- residents and self defense -------------------------------------------

    def house_status(self, now: datetime | None = None) -> str | None:
        """House status from the (inherited) house sources."""
        return self.manager.residents(
            self.cfg["residents_house"], self.cfg, now or dt_util.utcnow()
        )

    def room_status(self, now: datetime | None = None) -> str | None:
        """Room status from the room sources of this cover."""
        if not self.cfg["residents_room"]:
            return None
        return self.manager.residents(self.cfg["residents_room"], self.cfg, now or dt_util.utcnow())

    def resident_status(self, now: datetime | None = None) -> str | None:
        """Status for this cover: the room if it has sources, otherwise the house."""
        if self.cfg["residents_room"]:
            return self.room_status(now)
        return self.house_status(now)

    def self_defense_active(self, now: datetime | None = None) -> bool:
        """Close because nobody is at home (with an open window, or always)."""
        if not self.manager.switches[SWITCH_SELF_DEFENSE]:
            return False
        now = now or dt_util.utcnow()
        absent_since = _parse(self.state.get("absent_since"))
        if not self_defense_due(self.cfg, self.house_status(now), absent_since, now):
            return False
        return self.cfg["self_defense_all"] or self.window_state in (WINDOW_OPEN, WINDOW_TILTED)

    def _residents_key(self, now: datetime) -> tuple:
        house = self.house_status(now)
        return (
            self.resident_status(now) in SLEEPING,
            self.self_defense_active(now),
            presence_allows(self.cfg["presence_up"], house),
            presence_allows(self.cfg["presence_down"], house),
        )

    @callback
    def _check_residents(self, now: datetime) -> None:
        """React to a change of sleep, self defense or presence modes."""
        house = self.house_status(now)
        if house == RES_ABSENT:
            if not self.state.get("absent_since"):
                self.state["absent_since"] = _iso(now)
                self._save()
        elif self.state.pop("absent_since", None):
            self._save()
        key = self._residents_key(now)
        old = self._res_key
        self._res_key = key
        if old is None or key == old:
            return
        self.notify()
        woke = old[0] and not key[0]
        if woke and not self.cfg["wake_open"] and key[1] == old[1]:
            return
        self.evaluate(TRIGGER_RESIDENTS)

    @callback
    def _on_residents_change(self, _event: Event) -> None:
        self.tick()
        self.notify()

    # --- shading ----------------------------------------------------------------

    @property
    def shading_state(self) -> str:
        """State of the shading state machine."""
        return (self.state.get("shading") or {}).get("state", SHADING_OUT)

    def heat_latched(self, now: datetime | None = None) -> bool:
        """Heat protection started today (kept until the evening)."""
        now = now or dt_util.utcnow()
        return self.state.get("heat") == now.astimezone(self.tz).date().isoformat()

    def shaded(self, now: datetime | None = None) -> tuple[bool, bool]:
        """(shaded by the sun conditions, heat protection) for the arbiter."""
        return self.shading_state in SHADED, self.heat_latched(now)

    def _is_on(self, entity_id: str | None) -> bool | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _UNUSABLE:
            return None
        return state.state == STATE_ON

    def shading_inputs(self, now: datetime, *, sample: bool = False) -> tuple[Inputs, Configured]:
        """Measured values of the shading conditions."""
        cfg = self.cfg
        bright_entity = cfg["shading_brightness_sensor"] or cfg["brightness_sensor"]
        brightness = self._number(bright_entity)
        if brightness is not None:
            if sample:
                self._brightness.append((now, brightness))
            if self._brightness:
                brightness = average(list(self._brightness), now, cfg["shading_brightness_average"])
        weather_entity = cfg["weather_entity"]
        forecast = None
        if cfg["forecast_sensor"]:
            forecast = self._number(cfg["forecast_sensor"])
        elif weather_entity and cfg["shading_forecast_min"] is not None:
            forecast = self.manager.forecast(weather_entity)
        weather = None
        if weather_entity:
            state = self.hass.states.get(weather_entity)
            if state is not None and state.state not in _UNUSABLE:
                weather = state.state
        inputs = Inputs(
            azimuth=self.manager.sun.azimuth(now),
            elevation=self.manager.sun.elevation(now),
            brightness=brightness,
            temp_out=self._number(cfg["outdoor_temperature_sensor"]),
            temp_in=self._number(cfg["indoor_temperature_sensor"]),
            forecast=forecast,
            weather=weather,
            sensor=self._is_on(cfg["shading_sensor"]),
        )
        configured = Configured(
            brightness=bool(bright_entity),
            temp_out=bool(cfg["outdoor_temperature_sensor"]),
            temp_in=bool(cfg["indoor_temperature_sensor"]),
            forecast=bool(cfg["forecast_sensor"] or weather_entity),
            weather=bool(weather_entity),
            sensor=bool(cfg["shading_sensor"]),
        )
        return inputs, configured

    @callback
    def _shading_tick(self, now: datetime) -> None:
        cfg = self.cfg
        old = self.shading_state
        if (
            cfg["shading_mode"] == PRESENCE_OFF
            and cfg["heat_protection_temp"] is None
            and old == SHADING_OUT
        ):
            return
        inputs, configured = self.shading_inputs(now, sample=True)
        switch_on = self.manager.switches[SWITCH_SHADING]
        day = self.is_day(now)
        local = now.astimezone(self.tz)
        allowed = (
            switch_on
            and cfg["shading_mode"] != PRESENCE_OFF
            and presence_allows(cfg["shading_mode"], self.house_status(now))
            and in_time_window(cfg, local.time().replace(tzinfo=None))
            and day
        )
        start_ok = shading_combine(cfg, shading_conditions(cfg, inputs, configured, False))
        still = shading_conditions(cfg, inputs, configured, True)
        stored = self.state.get("shading") or {}
        since = _parse(stored.get("since"))
        new, new_since = shading_step(
            cfg,
            old,
            since,
            now,
            start_ok=start_ok,
            still_ok=shading_combine(cfg, still),
            left=sun_left(still),
            allowed=allowed,
        )
        if new != old or new_since != since:
            self.state["shading"] = {"state": new, "since": _iso(new_since)}
            self._save()
            self.notify()
        heat_allowed = switch_on and day
        latched = self.heat_latched(now)
        heat = heat_allowed and heat_active(cfg, inputs.temp_out, latched)
        if heat and not latched:
            self.state["heat"] = local.date().isoformat()
            self._save()
        before = old in SHADED or (latched and heat_allowed)
        after = new in SHADED or heat
        if after and not before:
            self.evaluate(TRIGGER_SHADING)
        elif before and not after:
            self.evaluate(TRIGGER_SHADING_END)
        elif after and shading_tilt(cfg, inputs.elevation) != self.state.get("shading_tilt"):
            # Next slat step by sun elevation
            self.evaluate(TRIGGER_SHADING)

    @callback
    def _on_shading_alt_change(self, _event: Event) -> None:
        if any(self.shaded()):
            self.evaluate(TRIGGER_SHADING)

    # --- slats ------------------------------------------------------------------

    @property
    def tilt_entity(self) -> str:
        """Entity that moves the slats."""
        return self.cfg["tilt_entity"] or self.cover_entity

    def tilt_supported(self) -> bool:
        """The slat entity can be set to a tilt position."""
        state = self.hass.states.get(self.tilt_entity)
        if state is None or state.state in _UNUSABLE:
            return False
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        return bool(features & CoverEntityFeature.SET_TILT_POSITION)

    def current_tilt(self) -> float | None:
        """Tilt position of the slats."""
        state = self.hass.states.get(self.tilt_entity)
        if state is None:
            return None
        value = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def tilt_for_reason(self, reason: str | None) -> int | None:
        """Tilt for a drive reason, None if no tilt is configured or supported."""
        tilt = tilt_for(self.cfg, reason, self.manager.sun.elevation(dt_util.utcnow()))
        if tilt is None or not self.tilt_supported():
            return None
        return tilt

    def _cancel_tilt(self) -> None:
        self._tilt_wait = None
        for name in ("_unsub_tilt", "_unsub_position"):
            unsub = getattr(self, name)
            if unsub:
                unsub()
                setattr(self, name, None)

    def _call_tilt(self, tilt: int, context: Context) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_TILT_POSITION,
                {ATTR_ENTITY_ID: self.tilt_entity, ATTR_TILT_POSITION: tilt},
                blocking=False,
                context=context,
            ),
            f"{DOMAIN} tilt {self.tilt_entity}",
        )

    @callback
    def _send_tilt(self, tilt: int, context: Context, _now: datetime | None = None) -> None:
        """Set the slats (optionally closed first)."""
        self._unsub_tilt = None
        self._tilt_wait = None
        current = self.current_tilt()
        if (
            self.cfg["tilt_close_first"]
            and tilt != 0
            and (current is None or current > self.cfg["tilt_tolerance"])
        ):
            self._call_tilt(0, context)
            self._unsub_tilt = async_call_later(
                self.hass,
                max(self.cfg["tilt_delay"], 1),
                partial(self._send_tilt_direct, tilt, context),
            )
            return
        self._call_tilt(tilt, context)

    @callback
    def _send_tilt_direct(self, tilt: int, context: Context, _now: datetime | None = None) -> None:
        self._unsub_tilt = None
        self._call_tilt(tilt, context)

    @callback
    def _check_tilt_wait(self) -> None:
        """Mode "standstill": set the slats once the cover reached its position."""
        if self._tilt_wait is None or self.moving:
            return
        position, tilt, context = self._tilt_wait
        current = self.current_position()
        if current is not None and abs(current - position) > self.cfg["tolerance"]:
            return
        self._tilt_wait = None
        if self._unsub_tilt:
            self._unsub_tilt()
        self._unsub_tilt = async_call_later(
            self.hass, self.cfg["tilt_delay"], partial(self._send_tilt, tilt, context)
        )

    def _tilt_only(self, tilt: int, reason: str | None) -> None:
        """Position reached, only the slats differ."""
        current = self.current_tilt()
        if current is not None and abs(current - tilt) <= self.cfg["tilt_tolerance"]:
            return
        self._cancel_tilt()
        context = Context()
        self._own_contexts.append(context.id)
        self._active_drive = (int(self.current_position() or 0), monotonic_time.monotonic())
        if reason in (REASON_SHADING, REASON_HEAT):
            self.state["shading_tilt"] = tilt
        self._send_tilt(tilt, context)
        _LOGGER.debug("%s: slats to %s (%s)", self.cover_entity, tilt, reason)

    def _schedule_event(self, trigger: str) -> None:
        self.evaluate(trigger, delayed=True)
        if self.override_active and self.cfg["override_reset"] == RESET_NEXT_SCHEDULE:
            self.clear_override(apply=False)
        self.recalculate(fetch=False)

    # --- decisions ----------------------------------------------------------

    def situation(self, trigger: str, now: datetime) -> Situation:
        """Collect the inputs of the arbiter."""
        variables = {"cover": self.cover_entity, "trigger": trigger}
        frost = self._frost_now(now)
        return Situation(
            trigger=trigger,
            automatic=self.manager.switches[SWITCH_AUTOMATIC] and self.switches[SWITCH_AUTOMATIC],
            paused=self.manager.switches[SWITCH_PAUSE]
            or self.switches[SWITCH_PAUSE]
            or self.pause_entity_on,
            available=self.available,
            moving=self.moving and not self._own_drive_running(),
            current_position=self.current_position(),
            override_active=self.override_active,
            done_today=self.done_today(now),
            lockout=lockout_active(self.cfg, self.window_state),
            lockout_hard=self.cfg["lockout"] == LOCKOUT_HARD,
            frost_block=frost[0],
            frost_soft=frost[1],
            party=self.manager.switches[SWITCH_PARTY] and self.cfg["party"],
            advent=self.advent_now(now),
            condition_all=self.condition_ok("all", variables),
            blocked_kinds=frozenset(
                kind
                for kind, name in (
                    (KIND_OPEN, "open"),
                    (KIND_CLOSE, "close"),
                    (KIND_VENTILATE, "ventilate"),
                    (KIND_SHADING, "shading"),
                )
                if not self.condition_ok(name, variables)
            ),
            after_temporary=(self.state.get("last") or {}).get("reason") in TEMPORARY_REASONS,
        )

    def target(self, trigger: str = TRIGGER_APPLY_TARGET) -> Decision:
        """Decide without driving (target state)."""
        now = dt_util.now(self.tz)
        situation = self.situation(trigger, now)
        house = self.house_status(now)
        shaded, heat = self.shaded(now)
        wishes = build_wishes(
            self.cfg,
            trigger=trigger,
            is_day=self.is_day(now),
            privacy_phase=self.privacy_phase(now),
            window=window_position(
                self.cfg, self.window_state, self.manager.switches[SWITCH_COMFORT]
            ),
            current=situation.current_position,
            morning_enabled=self.manager.switches[SWITCH_MORNING]
            and presence_allows(self.cfg["presence_up"], house),
            evening_enabled=self.manager.switches[SWITCH_EVENING]
            and presence_allows(self.cfg["presence_down"], house),
            sleeping=self.resident_status(now) in SLEEPING,
            self_defense=self.self_defense_active(now),
            shaded=shaded and self.manager.switches[SWITCH_SHADING],
            heat=heat and self.manager.switches[SWITCH_SHADING],
            shading_alt=bool(self._is_on(self.cfg["shading_alt_entity"])),
            force=self.force_kind(),
            lockout=situation.lockout,
            trigger_pos=self.trigger_pos(),
            **{k: v for k, v in self.protections().items() if k != FROST},
        )
        return decide(self.cfg, situation, wishes)

    @callback
    def evaluate(self, trigger: str, *, delayed: bool = False) -> Decision:
        """Ask the arbiter and drive if it says so."""
        decision = self.target(trigger)
        self._record(decision)
        if decision.reason == REASON_RAIN_WINDOW:
            if not self._rain_window_notified:
                self._rain_window_notified = True
                data = {
                    "entity_id": self.cover_entity,
                    "name": self.name,
                    "window": self.window_state,
                    "position": decision.position,
                    "driven": decision.drive,
                    "blocked_by": decision.blocked_by,
                }
                self.hass.bus.async_fire(EVENT_RAIN_WINDOW, data)
                self.run_action("rain_window", data)
        else:
            self._rain_window_notified = False
        if decision.blocked_by == BLOCK_LOCKOUT:
            # Drive again when the door is closed
            self.state["lockout_deferred"] = True
        if not decision.drive:
            _LOGGER.debug("%s: %s not driven (%s)", self.cover_entity, trigger, decision.blocked_by)
            if decision.blocked_by == BLOCK_AT_TARGET:
                tilt = self.tilt_for_reason(decision.reason)
                if tilt is not None:
                    self._tilt_only(tilt, decision.reason)
            self.notify()
            return decision
        delay = 0.0
        if delayed:
            delay = self.cfg["delay_fixed"] + random.uniform(0, self.cfg["delay_random"])
        if delay > 0:
            self._cancel_delay()
            self._unsub_delay = async_track_point_in_time(
                self.hass,
                partial(self._delayed, trigger),
                dt_util.utcnow() + timedelta(seconds=delay),
            )
            self.notify()
            return decision
        self._drive(decision.position, decision.reason, trigger, decision.source)  # type: ignore[arg-type]
        return decision

    def _cancel_delay(self) -> None:
        if self._unsub_delay:
            self._unsub_delay()
            self._unsub_delay = None

    @callback
    def _delayed(self, trigger: str, _now: datetime) -> None:
        self._unsub_delay = None
        # Check again: something may have changed while waiting
        self.evaluate(trigger, delayed=False)

    def _record(self, decision: Decision) -> None:
        self.last_decision = decision
        entry = decision.as_dict()
        entry["time"] = dt_util.utcnow().isoformat()
        entry["position_now"] = self.current_position()
        entry["override"] = self.override_active
        self.decisions.append(entry)

    # --- driving ------------------------------------------------------------

    def _own_drive_running(self) -> bool:
        if self._active_drive is None:
            return False
        return monotonic_time.monotonic() - self._active_drive[1] < self.cfg["drive_time"]

    @callback
    def _drive(
        self, position: int, reason: str, trigger: str | None, source: str | None = None
    ) -> None:
        """Send the drive command."""
        state = self.cover_state
        if state is None:
            return
        if source == "rain_window":
            # Back to the target when the window is closed
            self.state["window_drive"] = {"previous": None}
        elif source == "window" and not self.state.get("window_drive"):
            # Remember where the cover was, for "back to the previous position"
            self.state["window_drive"] = {"previous": self.current_position()}
        elif source != "window" and trigger != TRIGGER_WINDOW_CLOSED and reason != REASON_WIGGLE:
            self.state.pop("window_drive", None)
        context = Context()
        self._own_contexts.append(context.id)
        self._active_drive = (position, monotonic_time.monotonic())
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        raw = 100 - position if self.cfg["invert"] else position
        if features & CoverEntityFeature.SET_POSITION:
            service = SERVICE_SET_COVER_POSITION
            data: dict[str, Any] = {ATTR_ENTITY_ID: self.cover_entity, COVER_ATTR_POSITION: raw}
        else:
            current = self.current_position()
            opening = position > (current if current is not None else 50)
            service = SERVICE_OPEN_COVER if opening else SERVICE_CLOSE_COVER
            data = {ATTR_ENTITY_ID: self.cover_entity}
        self._cancel_tilt()
        tilt = self.tilt_for_reason(reason) if reason != REASON_SERVICE else None
        if reason in (REASON_SHADING, REASON_HEAT):
            self.state["shading_tilt"] = tilt
        mode = self.cfg["tilt_mode"]
        if tilt is not None and mode == TILT_FIRST:
            # Slats first, then the position (e.g. Z-Wave)
            self._send_tilt(tilt, context)
            self._unsub_position = async_call_later(
                self.hass,
                max(self.cfg["tilt_delay"], 1),
                partial(self._send_position, service, data, context),
            )
        else:
            self._send_position(service, data, context)
            if tilt is not None and mode == TILT_AFTER:
                self._unsub_tilt = async_call_later(
                    self.hass, self.cfg["tilt_delay"], partial(self._send_tilt, tilt, context)
                )
            elif tilt is not None:
                # Wait until the cover stands still at its position (with a time limit)
                self._tilt_wait = (position, tilt, context)
                self._unsub_tilt = async_call_later(
                    self.hass, self.cfg["tilt_timeout"], partial(self._send_tilt, tilt, context)
                )
        now = dt_util.utcnow()
        self.state["last"] = {
            "reason": reason,
            "trigger": trigger,
            "position": position,
            "tilt": tilt,
            "time": _iso(now),
        }
        self._save()
        self.hass.bus.async_fire(
            EVENT_DRIVE,
            {
                "entity_id": self.cover_entity,
                "name": self.name,
                "position": position,
                "reason": reason,
                "trigger": trigger,
            },
            context=context,
        )
        _LOGGER.debug("%s: drive to %s (%s, %s)", self.cover_entity, position, reason, trigger)
        self.run_action(
            "drive",
            {"position": position, "tilt": tilt, "reason": reason, "trigger": trigger},
            context,
        )
        self.notify()

    @callback
    def _send_position(
        self, service: str, data: dict[str, Any], context: Context, _now: datetime | None = None
    ) -> None:
        self._unsub_position = None
        self.hass.async_create_task(
            self.hass.services.async_call(
                COVER_DOMAIN, service, data, blocking=False, context=context
            ),
            f"{DOMAIN} drive {self.cover_entity}",
        )

    @callback
    def drive_to(self, position: int, *, respect_rules: bool) -> bool:
        """Drive from the service; with rules, automatic/pause/availability count."""
        if respect_rules:
            sit = self.situation(REASON_SERVICE, dt_util.now(self.tz))
            if not (sit.automatic and not sit.paused and sit.available):
                return False
        self._drive(position, REASON_SERVICE, None)
        return True

    # --- cover state --------------------------------------------------------

    @callback
    def _on_cover_change(self, event: Event) -> None:
        new: State | None = event.data.get("new_state")
        old: State | None = event.data.get("old_state")
        if new is None or old is None:
            return
        if new.state in _UNUSABLE or old.state in _UNUSABLE:
            return
        if self._tilt_wait is not None:
            self._check_tilt_wait()
        if not self.cfg["position_entity"]:
            if (
                new.state == old.state
                and new.attributes.get(ATTR_CURRENT_POSITION)
                == old.attributes.get(ATTR_CURRENT_POSITION)
                and new.attributes.get(ATTR_CURRENT_TILT_POSITION)
                == old.attributes.get(ATTR_CURRENT_TILT_POSITION)
            ):
                return
        self._check_manual(new.context)

    @callback
    def _on_position_entity_change(self, event: Event) -> None:
        new: State | None = event.data.get("new_state")
        old: State | None = event.data.get("old_state")
        if new is None or old is None or new.state in _UNUSABLE or old.state in _UNUSABLE:
            return
        if new.state == old.state:
            return
        self._check_manual(new.context)

    def _check_manual(self, context: Context) -> None:
        """Decide if a change came from us or from someone else."""
        if self._detect_from is None or monotonic_time.monotonic() < self._detect_from:
            if context.user_id is None:
                return
        if context.id in self._own_contexts or (
            context.parent_id is not None and context.parent_id in self._own_contexts
        ):
            return
        if self._own_drive_running() and context.user_id is None:
            # Position reports of our own drive after the context expired
            return
        self.set_override(dt_util.now(self.tz))

    @callback
    def _on_workday_change(self, _event: Event) -> None:
        self.recalculate()

    # --- window contacts ------------------------------------------------------

    def _read_window(self) -> str | None:
        def value(key: str) -> str | None:
            entity = self.cfg[key]
            if not entity:
                return None
            state = self.hass.states.get(entity)
            if state is None or state.state in _UNUSABLE:
                return None
            return state.state

        return window_state(
            self.cfg,
            value("window_open_sensor"),
            value("window_tilted_sensor"),
            value("window_state_sensor"),
        )

    @callback
    def _on_window_change(self, _event: Event) -> None:
        new = self._read_window()
        if new is None:
            # Contact unavailable: keep the last known state
            return
        if self._unsub_window_delay:
            self._unsub_window_delay()
            self._unsub_window_delay = None
        if new == self.window_state:
            return
        delay = (
            self.cfg["window_close_delay"]
            if new == WINDOW_CLOSED
            else self.cfg["window_open_delay"]
        )
        if delay:
            self._unsub_window_delay = async_call_later(self.hass, delay, self._window_settled)
        else:
            self._window_settled(None)

    @callback
    def _window_settled(self, _now: datetime | None) -> None:
        self._unsub_window_delay = None
        self._window_changed()
        # Self defense depends on the window
        self._check_residents(dt_util.utcnow())

    def _window_changed(self) -> None:
        new = self._read_window()
        old = self.window_state
        if new is None or new == old:
            return
        self.window_state = new
        self.apply_hardware_lock()
        self.notify()
        if new != WINDOW_CLOSED:
            self.evaluate(TRIGGER_WINDOW)
            return
        window_drive = self.state.pop("window_drive", None)
        deferred = self.state.pop("lockout_deferred", False)
        self._save()
        if not window_drive and not deferred:
            return
        previous = (window_drive or {}).get("previous")
        if (
            window_drive
            and self.cfg["window_close_return"] == RETURN_PREVIOUS
            and previous is not None
        ):
            sit = self.situation(TRIGGER_WINDOW_CLOSED, dt_util.now(self.tz))
            if sit.automatic and not sit.paused and sit.available:
                self._drive(int(previous), REASON_WINDOW_RETURN, TRIGGER_WINDOW_CLOSED)
            return
        self.evaluate(TRIGGER_WINDOW_CLOSED)

    # --- diagnostics --------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        """Everything about this cover."""
        return {
            "name": self.name,
            "cover_entity": self.cover_entity,
            "next_up": _iso(self.next_up),
            "next_down": _iso(self.next_down),
            "next_privacy": _iso(self.next_privacy),
            "window": self.window_state,
            "privacy_phase": self.privacy_phase(),
            "house_status": self.house_status(),
            "resident_status": self.resident_status(),
            "self_defense": self.self_defense_active(),
            "shading_state": self.shading_state,
            "heat_protection": self.heat_latched(),
            "tilt": self.current_tilt(),
            "is_day": self.is_day(),
            "position": self.current_position(),
            "state": self.state,
            "effective_config": self.cfg.as_dict(),
            "decisions": list(self.decisions),
        }


def get_manager(hass: HomeAssistant) -> AscManager | None:
    """Return the manager of the (single) config entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None
    return entries[0].runtime_data

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
    ATTR_POSITION as COVER_ATTR_POSITION,
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
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Context, Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
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

from .const import (
    CONF_COVER_ENTITY,
    CONF_PROFILE,
    CONF_SETTINGS,
    COVER_SWITCHES,
    DECISION_HISTORY,
    DOMAIN,
    EVENT_DRIVE,
    EVENT_MANUAL,
    GLOBAL_SWITCHES,
    SIGNAL_COVER_UPDATE,
    SIGNAL_GLOBAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORE_SAVE_DELAY,
    SUBENTRY_COVER,
    SUBENTRY_PROFILE,
    SWITCH_AUTOMATIC,
    SWITCH_COMFORT,
    SWITCH_EVENING,
    SWITCH_MORNING,
    SWITCH_PAUSE,
    SWITCH_WEEKEND_TIMES,
    TICK_SECONDS,
)
from .engine.arbiter import (
    BLOCK_LOCKOUT,
    REASON_MANUAL,
    REASON_SERVICE,
    REASON_WINDOW_RETURN,
    TRIGGER_APPLY_TARGET,
    TRIGGER_OVERRIDE_END,
    TRIGGER_PRIVACY,
    TRIGGER_RESUME,
    TRIGGER_SCHEDULE_DOWN,
    TRIGGER_SCHEDULE_UP,
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
from .engine.resolve import ResolvedConfig, resolve
from .engine.schedule import DaySchedule, day_schedule, default_workday, next_events
from .engine.settings import RESET_NEXT_SCHEDULE, RETURN_PREVIOUS, WINDOW_CLOSED, WINDOWS_CALENDAR
from .engine.sun import Location, SunCalculator
from .engine.window import lockout_active, window_position, window_state

_LOGGER = logging.getLogger(__name__)

_UNUSABLE = (None, STATE_UNAVAILABLE, STATE_UNKNOWN)
STARTUP_GRACE = 30  # seconds after start without manual detection


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


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
        self.central_device_id: str | None = None

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
            controller.async_start()

        self._unsubs.append(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=5)
        )
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, self._core_config))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=TICK_SECONDS))
        )

    @callback
    def _tick(self, now: datetime) -> None:
        for controller in self.controllers.values():
            controller.tick()

    async def async_stop(self) -> None:
        """Stop everything and save."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
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

    # --- life cycle ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Subscribe and schedule."""
        self._subscribe()
        self._restore_override()
        self.window_state = self._read_window()
        self.recalculate()
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
            if condition_held(self._light_since[direction], now, self.cfg["brightness_duration"]):
                self._light_since[direction] = None
                self._set_mark(now, direction)
                self._schedule_event(trigger)
                return
        if privacy_by_brightness(self.cfg, sched, marks, now, brightness):
            self._set_mark(now, PRIVACY_DOWN)
            self.evaluate(TRIGGER_PRIVACY, delayed=True)
            self.recalculate(fetch=False)

    def _schedule_event(self, trigger: str) -> None:
        self.evaluate(trigger, delayed=True)
        if self.override_active and self.cfg["override_reset"] == RESET_NEXT_SCHEDULE:
            self.clear_override(apply=False)
        self.recalculate(fetch=False)

    # --- decisions ----------------------------------------------------------

    def situation(self, trigger: str, now: datetime) -> Situation:
        """Collect the inputs of the arbiter."""
        return Situation(
            trigger=trigger,
            automatic=self.manager.switches[SWITCH_AUTOMATIC] and self.switches[SWITCH_AUTOMATIC],
            paused=self.manager.switches[SWITCH_PAUSE] or self.switches[SWITCH_PAUSE],
            available=self.available,
            moving=self.moving and not self._own_drive_running(),
            current_position=self.current_position(),
            override_active=self.override_active,
            done_today=self.done_today(now),
            lockout=lockout_active(self.cfg, self.window_state),
        )

    def target(self, trigger: str = TRIGGER_APPLY_TARGET) -> Decision:
        """Decide without driving (target state)."""
        now = dt_util.now(self.tz)
        situation = self.situation(trigger, now)
        wishes = build_wishes(
            self.cfg,
            trigger=trigger,
            is_day=self.is_day(now),
            privacy_phase=self.privacy_phase(now),
            window=window_position(
                self.cfg, self.window_state, self.manager.switches[SWITCH_COMFORT]
            ),
            current=situation.current_position,
            morning_enabled=self.manager.switches[SWITCH_MORNING],
            evening_enabled=self.manager.switches[SWITCH_EVENING],
        )
        return decide(self.cfg, situation, wishes)

    @callback
    def evaluate(self, trigger: str, *, delayed: bool = False) -> Decision:
        """Ask the arbiter and drive if it says so."""
        decision = self.target(trigger)
        self._record(decision)
        if decision.blocked_by == BLOCK_LOCKOUT:
            # Drive again when the door is closed
            self.state["lockout_deferred"] = True
        if not decision.drive:
            _LOGGER.debug("%s: %s not driven (%s)", self.cover_entity, trigger, decision.blocked_by)
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
        if source == "window" and not self.state.get("window_drive"):
            # Remember where the cover was, for "back to the previous position"
            self.state["window_drive"] = {"previous": self.current_position()}
        elif source != "window" and trigger != TRIGGER_WINDOW_CLOSED:
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
        self.hass.async_create_task(
            self.hass.services.async_call(
                COVER_DOMAIN, service, data, blocking=False, context=context
            ),
            f"{DOMAIN} drive {self.cover_entity}",
        )
        now = dt_util.utcnow()
        self.state["last"] = {
            "reason": reason,
            "trigger": trigger,
            "position": position,
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
        self.notify()

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
        if not self.cfg["position_entity"]:
            if new.state == old.state and new.attributes.get(
                ATTR_CURRENT_POSITION
            ) == old.attributes.get(ATTR_CURRENT_POSITION):
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
        new = self._read_window()
        old = self.window_state
        if new is None or new == old:
            return
        self.window_state = new
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

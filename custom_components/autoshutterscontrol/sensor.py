"""Sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import DEGREE, PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from . import AscConfigEntry
from .engine.arbiter import (
    BLOCKS,
    REASON_COMFORT,
    REASON_DAY_OPEN,
    REASON_FORCE,
    REASON_HEAT,
    REASON_HOT_DAY,
    REASON_MANUAL,
    REASON_NIGHT_CLOSE,
    REASON_PRIVACY_DOWN,
    REASON_PRIVACY_UP,
    REASON_RAIN,
    REASON_RAIN_RETURN,
    REASON_RAIN_WINDOW,
    REASON_SELF_DEFENSE,
    REASON_SERVICE,
    REASON_SHADING,
    REASON_SLEEP,
    REASON_TRIGGER,
    REASON_VENTILATE,
    REASON_WIGGLE,
    REASON_WIND,
    REASON_WINDOW_RETURN,
)
from .engine.settings import DRIVE_KINDS, RESIDENT_STATES, WINDOW_CLOSED, WINDOW_OPEN, WINDOW_TILTED
from .engine.shading import SHADING_STATES
from .entity import AscCoverEntity, AscGlobalEntity
from .runtime import AscManager, CoverController

REASONS = [
    REASON_DAY_OPEN,
    REASON_NIGHT_CLOSE,
    REASON_VENTILATE,
    REASON_COMFORT,
    REASON_PRIVACY_UP,
    REASON_PRIVACY_DOWN,
    REASON_RAIN_RETURN,
    REASON_WINDOW_RETURN,
    REASON_SLEEP,
    REASON_SELF_DEFENSE,
    REASON_SHADING,
    REASON_HEAT,
    REASON_HOT_DAY,
    REASON_RAIN_WINDOW,
    REASON_RAIN,
    REASON_WIND,
    REASON_FORCE,
    REASON_TRIGGER,
    REASON_WIGGLE,
    REASON_SERVICE,
    REASON_MANUAL,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    manager = entry.runtime_data
    async_add_entities(
        [
            HouseStatusSensor(manager),
            SunSensor(manager, "sun_azimuth"),
            SunSensor(manager, "sun_elevation"),
            ForecastSensor(manager),
        ]
    )
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            [
                NextDriveSensor(controller, "next_up"),
                NextDriveSensor(controller, "next_down"),
                NextDriveSensor(controller, "next_privacy"),
                WindowSensor(controller),
                ResidentsSensor(controller),
                ShadingSensor(controller),
                LastReasonSensor(controller),
                TargetSensor(controller),
                BlockedBySensor(controller),
                SimulatedSensor(controller),
            ],
            config_subentry_id=controller.subentry_id,
        )


class NextDriveSensor(AscCoverEntity, SensorEntity):
    """Time of the next morning or evening drive."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: CoverController, key: str) -> None:
        super().__init__(controller, key)
        self._key = key

    @property
    def native_value(self) -> datetime | None:
        return getattr(self.controller, self._key)


class LastReasonSensor(AscCoverEntity, SensorEntity):
    """Reason of the last drive."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = REASONS

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "last_reason")

    @property
    def native_value(self) -> str | None:
        last = self.controller.state.get("last") or {}
        reason = last.get("reason")
        return reason if reason in REASONS else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self.controller.state.get("last") or {}
        return {
            "position": last.get("position"),
            "time": last.get("time"),
            "trigger": last.get("trigger"),
        }


class BlockedBySensor(AscCoverEntity, SensorEntity):
    """Why the last decision did not drive (empty after a drive)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = list(BLOCKS)

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "blocked_by")

    @property
    def native_value(self) -> str | None:
        last = self.controller.last_decision
        if last is None or last.drive:
            return None
        return last.blocked_by

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self.controller.last_decision
        return {"reason": last.reason, "trigger": last.trigger} if last else {}


class TargetSensor(AscCoverEntity, SensorEntity):
    """Target state of the cover (also when nothing is driven)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(DRIVE_KINDS)
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({"effective_config"})

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "target")

    @property
    def native_value(self) -> str | None:
        return self.controller.target().kind

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        decision = self.controller.target()
        last = self.controller.last_decision
        return {
            "target_position": decision.position,
            "reason": decision.reason,
            "blocked_by": decision.blocked_by,
            "profile": self.controller.profile_name,
            "last_decision": last.as_dict() if last else None,
            "evaluated": dt_util.utcnow().isoformat(),
            "effective_config": self.controller.cfg.as_dict(),
        }


class WindowSensor(AscCoverEntity, SensorEntity):
    """Window state as seen by AutoShuttersControl (after the delays)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [WINDOW_CLOSED, WINDOW_TILTED, WINDOW_OPEN]

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "window_state")

    @property
    def native_value(self) -> str | None:
        return self.controller.window_state


class HouseStatusSensor(AscGlobalEntity, SensorEntity):
    """House status from the global resident sources."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(RESIDENT_STATES)

    def __init__(self, manager: AscManager) -> None:
        super().__init__(manager, "house_status")

    @property
    def native_value(self) -> str | None:
        return self.manager.house_status()


class ResidentsSensor(AscCoverEntity, SensorEntity):
    """Residents status that counts for this cover (room, otherwise house)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(RESIDENT_STATES)

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "residents")

    @property
    def native_value(self) -> str | None:
        return self.controller.resident_status()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "house": self.controller.house_status(),
            "room": self.controller.room_status(),
        }


class ShadingSensor(AscCoverEntity, SensorEntity):
    """State of the shading state machine and the inputs."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SHADING_STATES)

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "shading_state")

    @property
    def native_value(self) -> str | None:
        return self.controller.shading_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        inputs, _configured = self.controller.shading_inputs(now)
        stored = self.controller.state.get("shading") or {}
        return {
            "since": stored.get("since"),
            "heat_protection": self.controller.heat_latched(now),
            "hot_day": self.controller.hot_day(),
            "azimuth": round(inputs.azimuth, 1) if inputs.azimuth is not None else None,
            "elevation": round(inputs.elevation, 1) if inputs.elevation is not None else None,
            "brightness": inputs.brightness,
            "temp_out": inputs.temp_out,
            "temp_in": inputs.temp_in,
            "forecast": inputs.forecast,
            "weather": inputs.weather,
        }


class SunSensor(AscGlobalEntity, SensorEntity):
    """Sun azimuth or elevation (as used for shading and the slats)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = DEGREE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, manager: AscManager, key: str) -> None:
        super().__init__(manager, key)
        self._key = key

    async def async_added_to_hass(self) -> None:
        """Update every minute."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._minute, timedelta(minutes=1))
        )

    @callback
    def _minute(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        now = dt_util.utcnow()
        sun = self.manager.sun
        value = sun.azimuth(now) if self._key == "sun_azimuth" else sun.elevation(now)
        return round(value, 1)


class ForecastSensor(AscGlobalEntity, SensorEntity):
    """Forecast maximum temperature of today (global forecast sensor or weather)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, manager: AscManager) -> None:
        super().__init__(manager, "forecast_max_temperature")

    async def async_added_to_hass(self) -> None:
        """Update every ten minutes (the forecast is fetched in the background)."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._refresh, timedelta(minutes=10))
        )

    @callback
    def _refresh(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        return self.manager.forecast_today(self.manager.global_cfg)[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"condition": self.manager.forecast_today(self.manager.global_cfg)[1]}


class SimulatedSensor(AscCoverEntity, SensorEntity):
    """Position of the last drive in simulation mode (nothing was driven)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "simulated_drive")

    @property
    def native_value(self) -> int | None:
        return (self.controller.state.get("simulated") or {}).get("position")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        simulated = self.controller.state.get("simulated") or {}
        return {k: simulated.get(k) for k in ("reason", "trigger", "tilt", "time")}

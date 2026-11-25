"""Sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AscConfigEntry
from .engine.arbiter import (
    REASON_COMFORT,
    REASON_DAY_OPEN,
    REASON_FORCE,
    REASON_HEAT,
    REASON_MANUAL,
    REASON_NIGHT_CLOSE,
    REASON_PRIVACY_DOWN,
    REASON_PRIVACY_UP,
    REASON_RAIN,
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
    REASON_WINDOW_RETURN,
    REASON_SLEEP,
    REASON_SELF_DEFENSE,
    REASON_SHADING,
    REASON_HEAT,
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
    async_add_entities([HouseStatusSensor(entry.runtime_data)])
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
            "azimuth": round(inputs.azimuth, 1) if inputs.azimuth is not None else None,
            "elevation": round(inputs.elevation, 1) if inputs.elevation is not None else None,
            "brightness": inputs.brightness,
            "temp_out": inputs.temp_out,
            "temp_in": inputs.temp_in,
            "forecast": inputs.forecast,
            "weather": inputs.weather,
        }

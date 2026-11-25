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
from .engine.arbiter import REASON_DAY_OPEN, REASON_MANUAL, REASON_NIGHT_CLOSE, REASON_SERVICE
from .engine.settings import DRIVE_KINDS
from .entity import AscCoverEntity
from .runtime import CoverController

REASONS = [REASON_DAY_OPEN, REASON_NIGHT_CLOSE, REASON_SERVICE, REASON_MANUAL]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            [
                NextDriveSensor(controller, "next_up"),
                NextDriveSensor(controller, "next_down"),
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

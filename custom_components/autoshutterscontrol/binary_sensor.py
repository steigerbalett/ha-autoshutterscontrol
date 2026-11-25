"""Binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AscConfigEntry
from .engine.daynight import PRIVACY_DOWN, PRIVACY_UP, effective_down, effective_up, privacy_times
from .entity import AscCoverEntity
from .runtime import CoverController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            [
                DayBinarySensor(controller),
                OverrideBinarySensor(controller),
                SelfDefenseBinarySensor(controller),
            ],
            config_subentry_id=controller.subentry_id,
        )


class DayBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On between the morning and the evening drive."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "is_day")

    @property
    def is_on(self) -> bool:
        return self.controller.is_day()

    @property
    def extra_state_attributes(self) -> dict:
        today = dt_util.now(self.controller.tz).date()
        sched = self.controller.schedule_for(today)
        marks = self.controller.marks_for(today)
        privacy = privacy_times(self.controller.cfg, sched, marks)
        return {
            "up_today": effective_up(sched, marks).isoformat(),
            "down_today": effective_down(sched, marks).isoformat(),
            "up_workday": sched.up_workday,
            "down_workday": sched.down_workday,
            "up_dynamic": sched.up_dynamic,
            "down_dynamic": sched.down_dynamic,
            "privacy_up_today": privacy[PRIVACY_UP].isoformat() if PRIVACY_UP in privacy else None,
            "privacy_down_today": (
                privacy[PRIVACY_DOWN].isoformat() if PRIVACY_DOWN in privacy else None
            ),
        }


class OverrideBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On while a manual override is active."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "manual_override")

    @property
    def is_on(self) -> bool:
        return self.controller.override_active

    @property
    def extra_state_attributes(self) -> dict:
        override = self.controller.override or {}
        return {"since": override.get("since"), "until": override.get("until")}


class SelfDefenseBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On while self defense keeps the cover closed."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "self_defense")

    @property
    def is_on(self) -> bool:
        return self.controller.self_defense_active()

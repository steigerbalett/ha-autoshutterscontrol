"""Buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AscConfigEntry
from .engine.arbiter import TRIGGER_APPLY_TARGET
from .entity import AscCoverEntity, AscGlobalEntity
from .runtime import AscManager, CoverController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    manager = entry.runtime_data
    async_add_entities(
        [
            GlobalButton(manager, "global_recalculate"),
            GlobalButton(manager, "global_apply_target"),
            GlobalButton(manager, "global_wiggle"),
            GlobalButton(manager, "global_release_deferred"),
        ]
    )
    for controller in manager.controllers.values():
        async_add_entities(
            [
                CoverButton(controller, "apply_target"),
                CoverButton(controller, "clear_override"),
                CoverButton(controller, "wiggle"),
            ],
            config_subentry_id=controller.subentry_id,
        )


class GlobalButton(AscGlobalEntity, ButtonEntity):
    """Button of the central device."""

    def __init__(self, manager: AscManager, key: str) -> None:
        super().__init__(manager, key)
        self._key = key

    async def async_press(self) -> None:
        if self._key == "global_recalculate":
            self.manager.recalculate()
            return
        if self._key == "global_release_deferred":
            self.manager.release_deferred()
            return
        if self._key == "global_wiggle":
            for controller in self.manager.controllers.values():
                controller.wiggle()
            return
        for controller in self.manager.controllers.values():
            controller.evaluate(TRIGGER_APPLY_TARGET)


class CoverButton(AscCoverEntity, ButtonEntity):
    """Button of one cover."""

    def __init__(self, controller: CoverController, key: str) -> None:
        super().__init__(controller, key)
        self._key = key

    async def async_press(self) -> None:
        if self._key == "apply_target":
            self.controller.evaluate(TRIGGER_APPLY_TARGET)
        elif self._key == "wiggle":
            self.controller.wiggle()
        else:
            self.controller.clear_override()

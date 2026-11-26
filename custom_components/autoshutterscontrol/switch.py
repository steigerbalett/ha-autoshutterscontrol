"""Switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AscConfigEntry
from .const import COVER_SWITCHES, GLOBAL_SWITCHES, SWITCH_GUEST, SWITCH_PAUSE
from .engine.arbiter import TRIGGER_RESUME
from .entity import AscCoverEntity, AscGlobalEntity
from .runtime import AscManager, CoverController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    manager = entry.runtime_data
    async_add_entities(GlobalSwitch(manager, key) for key in GLOBAL_SWITCHES)
    for controller in manager.controllers.values():
        async_add_entities(
            (CoverSwitch(controller, key) for key in COVER_SWITCHES),
            config_subentry_id=controller.subentry_id,
        )


class GlobalSwitch(AscGlobalEntity, SwitchEntity):
    """Global switch of the central device."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: AscManager, key: str) -> None:
        super().__init__(manager, f"global_{key}")
        self._key = key

    @property
    def is_on(self) -> bool:
        return self.manager.switches[self._key]

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.manager.set_switch(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.manager.set_switch(self._key, False)


class CoverSwitch(AscCoverEntity, SwitchEntity):
    """Switch of one cover."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: CoverController, key: str) -> None:
        super().__init__(controller, f"cover_{key}")
        self._key = key

    @property
    def is_on(self) -> bool:
        return self.controller.switches[self._key]

    def _set(self, value: bool) -> None:
        old = self.controller.switches[self._key]
        self.controller.switches[self._key] = value
        self.controller.manager.save()
        self.controller.notify()
        if self._key == SWITCH_PAUSE and old and not value:
            self.controller.evaluate(TRIGGER_RESUME)
        if self._key == SWITCH_GUEST:
            self.controller.guest_changed()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(False)

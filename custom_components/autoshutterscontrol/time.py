"""Times (per cover settings)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AscConfigEntry
from .engine.settings import LEVEL_COVER, Setting, settings_for, to_storage
from .entity import AscCoverEntity
from .runtime import CoverController
from .services import write_cover_setting


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time entities."""
    settings = [s for s in settings_for(LEVEL_COVER) if s.entity == "time"]
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            (SettingTime(controller, s) for s in settings),
            config_subentry_id=controller.subentry_id,
        )


class SettingTime(AscCoverEntity, TimeEntity):
    """Time for one cover setting; shows the effective value."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, controller: CoverController, setting: Setting) -> None:
        super().__init__(controller, setting.key)
        self._setting = setting

    @property
    def native_value(self) -> time | None:
        return self.controller.cfg[self._setting.key]

    @property
    def extra_state_attributes(self) -> dict:
        return {"source": self.controller.cfg.source(self._setting.key)}

    async def async_set_value(self, value: time) -> None:
        write_cover_setting(
            self.hass,
            self.controller.manager,
            self.controller.subentry_id,
            self._setting.key,
            to_storage(self._setting, value),
        )

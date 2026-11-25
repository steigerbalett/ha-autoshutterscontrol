"""Selects (per cover settings with "inherit")."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AscConfigEntry
from .const import CONF_SETTINGS, INHERIT
from .engine.settings import LEVEL_COVER, Setting, settings_for
from .entity import AscCoverEntity
from .runtime import CoverController
from .services import write_cover_setting


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    settings = [s for s in settings_for(LEVEL_COVER) if s.entity == "select"]
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            (SettingSelect(controller, s) for s in settings),
            config_subentry_id=controller.subentry_id,
        )


class SettingSelect(AscCoverEntity, SelectEntity):
    """Select for one cover setting; "inherit" removes the cover value."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: CoverController, setting: Setting) -> None:
        super().__init__(controller, setting.key)
        self._setting = setting
        self._attr_options = [INHERIT, *setting.options]

    @property
    def current_option(self) -> str:
        sub = self.controller.manager.entry.subentries[self.controller.subentry_id]
        value = sub.data.get(CONF_SETTINGS, {}).get(self._setting.key)
        return value if value in self._setting.options else INHERIT

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "effective": self.controller.cfg[self._setting.key],
            "source": self.controller.cfg.source(self._setting.key),
        }

    async def async_select_option(self, option: str) -> None:
        write_cover_setting(
            self.hass,
            self.controller.manager,
            self.controller.subentry_id,
            self._setting.key,
            None if option == INHERIT else option,
        )

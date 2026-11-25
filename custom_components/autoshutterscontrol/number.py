"""Numbers (per cover settings)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up numbers."""
    settings = [s for s in settings_for(LEVEL_COVER) if s.entity == "number"]
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            (SettingNumber(controller, s) for s in settings),
            config_subentry_id=controller.subentry_id,
        )


class SettingNumber(AscCoverEntity, NumberEntity):
    """Number for one cover setting; shows the effective value."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX

    def __init__(self, controller: CoverController, setting: Setting) -> None:
        super().__init__(controller, setting.key)
        self._setting = setting
        self._attr_native_min_value = setting.minimum or 0
        self._attr_native_max_value = setting.maximum or 100
        self._attr_native_step = setting.step
        self._attr_native_unit_of_measurement = setting.unit

    @property
    def native_value(self) -> float | None:
        return self.controller.cfg[self._setting.key]

    @property
    def extra_state_attributes(self) -> dict:
        return {"source": self.controller.cfg.source(self._setting.key)}

    async def async_set_native_value(self, value: float) -> None:
        write_cover_setting(
            self.hass,
            self.controller.manager,
            self.controller.subentry_id,
            self._setting.key,
            to_storage(self._setting, value),
        )

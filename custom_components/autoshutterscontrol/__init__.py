"""AutoShuttersControl for HA."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .runtime import AscManager
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AscConfigEntry = ConfigEntry[AscManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services once."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AscConfigEntry) -> bool:
    """Set up from a config entry."""
    manager = AscManager(hass, entry)
    await manager.async_start()
    entry.runtime_data = manager
    structure = manager.structure()

    async def _updated(hass: HomeAssistant, entry: AscConfigEntry) -> None:
        if entry.runtime_data.structure() != structure:
            # Covers or profiles were added or removed: entities change
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        entry.runtime_data.async_reconfigure()

    entry.async_on_unload(entry.add_update_listener(_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AscConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded

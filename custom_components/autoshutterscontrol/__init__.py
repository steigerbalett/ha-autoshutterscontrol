"""AutoShuttersControl for HA."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .entity import cover_device
from .panel import async_remove_panel, async_setup_websocket, async_update_panel
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
    async_setup_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AscConfigEntry) -> bool:
    """Set up from a config entry."""
    manager = AscManager(hass, entry)
    await manager.async_start()
    entry.runtime_data = manager
    structure = manager.structure()
    devices = _cover_devices(hass, manager)

    async def _updated(hass: HomeAssistant, entry: AscConfigEntry) -> None:
        if (
            entry.runtime_data.structure() != structure
            or _cover_devices(hass, entry.runtime_data) != devices
        ):
            # Covers or profiles were added or removed: entities change
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        entry.runtime_data.async_reconfigure()
        await async_update_panel(hass, entry.runtime_data.global_cfg["panel"])

    entry.async_on_unload(entry.add_update_listener(_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_empty_cover_devices(hass, manager)
    await async_update_panel(hass, manager.global_cfg["panel"])
    return True


def _cover_devices(hass: HomeAssistant, manager: AscManager) -> dict[str, str | None]:
    """Device of the real cover per cover subentry (None: own ASC device)."""
    out = {}
    for sub_id, sub in manager.entry.subentries.items():
        if sub.subentry_type == "cover":
            device = cover_device(hass, sub.data["cover_entity"])
            out[sub_id] = device.id if device else None
    return out


@callback
def _remove_empty_cover_devices(hass: HomeAssistant, manager: AscManager) -> None:
    """Own ASC devices of covers whose entities moved to the device of the cover."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    for sub_id in manager.controllers:
        device = dev_reg.async_get_device_by_identifier((DOMAIN, sub_id), manager.entry.entry_id)
        if device is not None and not er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        ):
            dev_reg.async_remove_device(device.id)


async def async_unload_entry(hass: HomeAssistant, entry: AscConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_remove_panel(hass)
        await entry.runtime_data.async_stop()
    return unloaded

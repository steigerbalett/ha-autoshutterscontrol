"""Base entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_COVER_UPDATE, SIGNAL_GLOBAL_UPDATE
from .runtime import AscManager, CoverController


def global_device(manager: AscManager) -> DeviceInfo:
    """Central device."""
    return DeviceInfo(
        identifiers={(DOMAIN, manager.entry.entry_id)},
        name="AutoShuttersControl",
        manufacturer="AutoShuttersControl for HA",
        model="AutoShuttersControl",
        entry_type=DeviceEntryType.SERVICE,
    )


class AscGlobalEntity(Entity):
    """Entity of the central device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: AscManager, key: str) -> None:
        self.manager = manager
        self._attr_translation_key = key
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = global_device(manager)

    async def async_added_to_hass(self) -> None:
        """Follow global changes."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_GLOBAL_UPDATE, self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()


def cover_device(hass: HomeAssistant, cover_entity: str) -> dr.DeviceEntry | None:
    """Device of the real cover; the entities of the cover are shown there."""
    device = async_entity_id_to_device(hass, cover_entity)
    return device if isinstance(device, dr.DeviceEntry) else None


class AscCoverEntity(Entity):
    """Entity of one cover: on the device of the real cover, else on an own device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: CoverController, key: str) -> None:
        self.controller = controller
        self._attr_translation_key = key
        self._attr_unique_id = f"{controller.subentry_id}_{key}"
        device = cover_device(controller.hass, controller.cover_entity)
        if device is not None:
            # Like the helpers of Home Assistant: link to the device of the cover
            self.device_entry = device
            return
        info = DeviceInfo(
            identifiers={(DOMAIN, controller.subentry_id)},
            name=f"ASC {controller.name}",
            manufacturer="AutoShuttersControl for HA",
            model="Cover",
            entry_type=DeviceEntryType.SERVICE,
            via_device_id=controller.manager.central_device_id,
        )
        self._attr_device_info = info

    async def async_added_to_hass(self) -> None:
        """Follow cover changes."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_COVER_UPDATE.format(self.controller.subentry_id), self._updated
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_GLOBAL_UPDATE, self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()

"""Services of AutoShuttersControl for HA."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_DURATION,
    ATTR_MODE,
    ATTR_NAMED_POSITION,
    ATTR_OPTION,
    ATTR_POSITION,
    ATTR_RESPECT_RULES,
    ATTR_TARGET_PROFILE,
    ATTR_VALUE,
    CONF_PROFILE,
    CONF_SETTINGS,
    DOMAIN,
    NAMED_POSITIONS,
    SERVICE_APPLY_TARGET,
    SERVICE_CLEAR_OVERRIDE,
    SERVICE_DRIVE,
    SERVICE_RECALCULATE,
    SERVICE_RELEASE_DEFERRED,
    SERVICE_SET_LOCK,
    SERVICE_SET_OPTION,
    SERVICE_WIGGLE,
    SUBENTRY_PROFILE,
)
from .engine.arbiter import TRIGGER_APPLY_TARGET
from .engine.settings import BY_KEY, LEVEL_COVER, LEVEL_PROFILE, LOCK_MODES, to_storage

if TYPE_CHECKING:
    from .runtime import AscManager, CoverController

TARGET_SCHEMA = {
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_TARGET_PROFILE): cv.string,
}

DRIVE_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Exclusive(ATTR_POSITION, "position"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Exclusive(ATTR_NAMED_POSITION, "position"): vol.In(NAMED_POSITIONS),
        vol.Optional(ATTR_RESPECT_RULES, default=True): cv.boolean,
    }
)
TARGET_ONLY_SCHEMA = vol.Schema(TARGET_SCHEMA)
SET_LOCK_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required(ATTR_MODE): vol.In(LOCK_MODES),
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(min=0, max=10080)),
    }
)
SET_OPTION_SCHEMA = vol.Schema(
    {
        **TARGET_SCHEMA,
        vol.Required(ATTR_OPTION): vol.In(list(BY_KEY)),
        vol.Optional(ATTR_VALUE): vol.Any(None, str, int, float, bool, list),
    }
)


def _manager(hass: HomeAssistant) -> AscManager:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    return entries[0].runtime_data


def _profile_id(manager: AscManager, value: str) -> str:
    for sub_id, sub in manager.entry.subentries.items():
        if sub.subentry_type == SUBENTRY_PROFILE and value in (sub_id, sub.title):
            return sub_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_profile",
        translation_placeholders={"profile": value},
    )


def _targets(manager: AscManager, call: ServiceCall) -> list[CoverController]:
    controllers = list(manager.controllers.values())
    entity_ids = call.data.get(ATTR_ENTITY_ID)
    if entity_ids:
        controllers = [c for c in controllers if c.cover_entity in entity_ids]
        missing = set(entity_ids) - {c.cover_entity for c in controllers}
        if missing:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_cover",
                translation_placeholders={"entity_id": ", ".join(sorted(missing))},
            )
    if profile := call.data.get(ATTR_TARGET_PROFILE):
        profile_id = _profile_id(manager, profile)
        controllers = [
            c
            for c in controllers
            if manager.entry.subentries[c.subentry_id].data.get(CONF_PROFILE) == profile_id
        ]
    return controllers


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services."""

    async def drive(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            if ATTR_POSITION in call.data:
                position = call.data[ATTR_POSITION]
            elif ATTR_NAMED_POSITION in call.data:
                position = controller.cfg[f"pos_{call.data[ATTR_NAMED_POSITION]}"]
                if position is None:
                    position = controller.cfg["pos_closed"]
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="no_position"
                )
            controller.drive_to(int(position), respect_rules=call.data[ATTR_RESPECT_RULES])

    async def recalculate(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            controller.recalculate()

    async def apply_target(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            controller.evaluate(TRIGGER_APPLY_TARGET)

    async def clear_override(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            controller.clear_override()

    async def wiggle(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            controller.wiggle()

    async def set_lock(call: ServiceCall) -> None:
        manager = _manager(hass)
        for controller in _targets(manager, call):
            controller.set_lock(call.data[ATTR_MODE], call.data.get(ATTR_DURATION))

    async def release_deferred(call: ServiceCall) -> None:
        manager = _manager(hass)
        manager.release_deferred(_targets(manager, call))

    async def set_option(call: ServiceCall) -> None:
        manager = _manager(hass)
        setting = BY_KEY[call.data[ATTR_OPTION]]
        value: Any = call.data.get(ATTR_VALUE)
        try:
            stored = to_storage(setting, value) if value not in (None, "") else None
        except (TypeError, ValueError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"option": setting.key},
            ) from err
        if setting.options and stored is not None:
            values = stored if isinstance(stored, list) else [stored]
            if any(v not in setting.options for v in values):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_value",
                    translation_placeholders={"option": setting.key},
                )
        entry = manager.entry
        if ATTR_ENTITY_ID not in call.data and ATTR_TARGET_PROFILE in call.data:
            if LEVEL_PROFILE not in setting.levels:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="wrong_level",
                    translation_placeholders={"option": setting.key},
                )
            sub = entry.subentries[_profile_id(manager, call.data[ATTR_TARGET_PROFILE])]
            _write(hass, entry, sub, setting.key, stored)
            return
        if ATTR_ENTITY_ID not in call.data:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_target")
        if LEVEL_COVER not in setting.levels:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="wrong_level",
                translation_placeholders={"option": setting.key},
            )
        for controller in _targets(manager, call):
            _write(hass, entry, entry.subentries[controller.subentry_id], setting.key, stored)

    hass.services.async_register(DOMAIN, SERVICE_DRIVE, drive, schema=DRIVE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RECALCULATE, recalculate, schema=TARGET_ONLY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_TARGET, apply_target, schema=TARGET_ONLY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_OVERRIDE, clear_override, schema=TARGET_ONLY_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_SET_OPTION, set_option, schema=SET_OPTION_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_WIGGLE, wiggle, schema=TARGET_ONLY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_LOCK, set_lock, schema=SET_LOCK_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_RELEASE_DEFERRED, release_deferred, schema=TARGET_ONLY_SCHEMA
    )


def _write(hass: HomeAssistant, entry, subentry, key: str, value: Any) -> None:
    settings = dict(subentry.data.get(CONF_SETTINGS, {}))
    if value is None:
        settings.pop(key, None)
    else:
        settings[key] = value
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, CONF_SETTINGS: settings}
    )


def write_cover_setting(
    hass: HomeAssistant, manager: AscManager, subentry_id: str, key: str, value: Any
) -> None:
    """Write one cover setting (used by the config entities)."""
    entry = manager.entry
    _write(hass, entry, entry.subentries[subentry_id], key, value)

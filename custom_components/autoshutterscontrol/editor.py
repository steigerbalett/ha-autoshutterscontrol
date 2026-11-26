"""Edit covers in the sidebar page: list, change several at once, add, duplicate, delete.

The values stay in the subentries, exactly as the dialog stores them. Only
administrators may change anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import time
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .const import (
    CONF_COVER_ENTITY,
    CONF_PROFILE,
    CONF_SETTINGS,
    DOMAIN,
    SUBENTRY_COVER,
    SUBENTRY_PROFILE,
)
from .engine.resolve import inherited_value
from .engine.settings import (
    ACTION,
    BOOL,
    BY_KEY,
    CONDITION,
    COVER_ONLY,
    ENTITIES,
    ENTITY,
    FLOAT,
    INT,
    LEVEL_COVER,
    MULTI,
    SELECT,
    TEXT,
    TIME,
    Setting,
    parse_time,
    sections_for,
    settings_for,
    to_storage,
)

WS_DATA = f"{DOMAIN}/editor/data"
WS_UPDATE = f"{DOMAIN}/editor/update"
WS_ADD = f"{DOMAIN}/editor/add"
WS_DUPLICATE = f"{DOMAIN}/editor/duplicate"
WS_DELETE = f"{DOMAIN}/editor/delete"

# Conditions and actions are edited in the dialog only
_SKIP = (CONDITION, ACTION)


@callback
def async_setup_editor(hass: HomeAssistant) -> None:
    """Register the websocket commands of the editor."""
    for command in (ws_data, ws_update, ws_add, ws_duplicate, ws_delete):
        websocket_api.async_register_command(hass, command)


def editable() -> list[Setting]:
    """Settings of a cover that the page can edit."""
    return [s for s in settings_for(LEVEL_COVER) if s.kind not in _SKIP]


def _json(value: Any) -> Any:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, tuple):
        return list(value)
    return value


def check_value(setting: Setting, value: Any) -> Any:
    """Check one value from the page and return it as it is stored."""
    kind = setting.kind
    if kind in _SKIP:
        raise vol.Invalid(f"{setting.key} can only be changed in the dialog")
    if kind == BOOL:
        if not isinstance(value, bool):
            raise vol.Invalid(f"{setting.key}: true or false")
        return value
    if kind in (INT, FLOAT):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise vol.Invalid(f"{setting.key}: a number")
        if setting.minimum is not None and value < setting.minimum:
            raise vol.Invalid(f"{setting.key}: at least {setting.minimum:g}")
        if setting.maximum is not None and value > setting.maximum:
            raise vol.Invalid(f"{setting.key}: at most {setting.maximum:g}")
        return to_storage(setting, value)
    if kind == TIME:
        try:
            return to_storage(setting, parse_time(str(value)))
        except (ValueError, TypeError) as err:
            raise vol.Invalid(f"{setting.key}: a time HH:MM") from err
    if kind == SELECT:
        if value not in setting.options:
            raise vol.Invalid(f"{setting.key}: one of {', '.join(setting.options)}")
        return value
    if kind == MULTI:
        if not isinstance(value, list) or any(v not in setting.options for v in value):
            raise vol.Invalid(f"{setting.key}: a list of {', '.join(setting.options)}")
        return list(value)
    if kind == ENTITY:
        _check_entity(setting, value)
        return value
    if kind == ENTITIES:
        if not isinstance(value, list):
            raise vol.Invalid(f"{setting.key}: a list of entities")
        for item in value:
            _check_entity(setting, item)
        return list(value)
    if kind == TEXT:
        if not isinstance(value, str):
            raise vol.Invalid(f"{setting.key}: a text")
        return value
    raise vol.Invalid(f"{setting.key}: unknown kind")


def _check_entity(setting: Setting, value: Any) -> None:
    if not isinstance(value, str) or "." not in value:
        raise vol.Invalid(f"{setting.key}: an entity id")
    if setting.domains and value.split(".", 1)[0] not in setting.domains:
        raise vol.Invalid(f"{setting.key}: an entity of {', '.join(setting.domains)}")


def apply_changes(
    current: Mapping[str, Any], set_values: Mapping[str, Any], clear: list[str]
) -> dict[str, Any]:
    """New stored settings: only the changed fields, everything else stays."""
    allowed = {s.key for s in editable()}
    result = dict(current)
    for key in clear:
        if key not in allowed:
            raise vol.Invalid(f"unknown setting {key}")
        result.pop(key, None)
    for key, value in set_values.items():
        if key not in allowed:
            raise vol.Invalid(f"unknown setting {key}")
        if value is None:
            result.pop(key, None)
        else:
            result[key] = check_value(BY_KEY[key], value)
    return result


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0] if entries else None


def _profiles(entry: ConfigEntry) -> dict[str, ConfigSubentry]:
    return {k: s for k, s in entry.subentries.items() if s.subentry_type == SUBENTRY_PROFILE}


def _covers(entry: ConfigEntry) -> dict[str, ConfigSubentry]:
    return {k: s for k, s in entry.subentries.items() if s.subentry_type == SUBENTRY_COVER}


def editor_data(entry: ConfigEntry) -> dict[str, Any]:
    """Everything the page needs."""
    global_settings = entry.options.get(CONF_SETTINGS, {})
    profiles = _profiles(entry)
    fields = []
    for s in editable():
        fields.append(
            {
                "key": s.key,
                "kind": s.kind,
                "section": s.section,
                "options": list(s.options),
                "min": s.minimum,
                "max": s.maximum,
                "step": s.step,
                "unit": s.unit,
                "domains": list(s.domains),
                "default": _json(s.default),
            }
        )
    covers = []
    for sub_id, sub in sorted(_covers(entry).items(), key=lambda item: item[1].title.lower()):
        profile_id = sub.data.get(CONF_PROFILE)
        profile = profiles.get(profile_id) if profile_id else None
        profile_settings = profile.data.get(CONF_SETTINGS, {}) if profile else None
        inherited = {}
        for s in editable():
            value, source = inherited_value(s.key, LEVEL_COVER, global_settings, profile_settings)
            inherited[s.key] = [_json(value), source]
        covers.append(
            {
                "subentry_id": sub_id,
                "title": sub.title,
                "cover_entity": sub.data.get(CONF_COVER_ENTITY),
                "profile": profile_id,
                "settings": dict(sub.data.get(CONF_SETTINGS, {})),
                "inherited": inherited,
            }
        )
    return {
        "sections": [
            sec for sec in sections_for(LEVEL_COVER) if any(s.section == sec for s in editable())
        ],
        "fields": fields,
        "profiles": [
            {"id": k, "title": p.title}
            for k, p in sorted(profiles.items(), key=lambda item: item[1].title.lower())
        ],
        "covers": covers,
    }


def _not_loaded(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_error(msg["id"], "not_loaded", "AutoShuttersControl is not loaded")


@websocket_api.websocket_command({vol.Required("type"): WS_DATA})
@callback
def ws_data(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Fields, profiles and covers with their own and inherited values."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg)
        return
    data = editor_data(entry)
    data["admin"] = bool(connection.user and connection.user.is_admin)
    connection.send_result(msg["id"], data)


def _cover_ids(
    entry: ConfigEntry, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> list[str] | None:
    covers = _covers(entry)
    unknown = [i for i in msg["subentry_ids"] if i not in covers]
    if unknown:
        connection.send_error(msg["id"], "not_found", f"Unknown cover {', '.join(unknown)}")
        return None
    return list(msg["subentry_ids"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_UPDATE,
        vol.Required("subentry_ids"): [str],
        vol.Optional("set", default={}): {str: vol.Any(None, bool, int, float, str, [str])},
        vol.Optional("clear", default=[]): [str],
        # Profile: missing = unchanged, None = no profile
        vol.Optional("profile"): vol.Any(None, str),
        vol.Optional("title"): str,
    }
)
@websocket_api.require_admin
@callback
def ws_update(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Apply the changed fields to every selected cover."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg)
        return
    ids = _cover_ids(entry, connection, msg)
    if ids is None:
        return
    if "profile" in msg and msg["profile"] is not None and msg["profile"] not in _profiles(entry):
        connection.send_error(msg["id"], "not_found", "Unknown profile")
        return
    if "title" in msg and (len(ids) != 1 or not msg["title"].strip()):
        connection.send_error(msg["id"], "invalid_format", "A name needs exactly one cover")
        return
    new: dict[str, dict[str, Any]] = {}
    try:
        for sub_id in ids:
            sub = entry.subentries[sub_id]
            data = dict(sub.data)
            data[CONF_SETTINGS] = apply_changes(
                sub.data.get(CONF_SETTINGS, {}), msg["set"], msg["clear"]
            )
            if "profile" in msg:
                data[CONF_PROFILE] = msg["profile"]
            new[sub_id] = data
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    changed = 0
    for sub_id, data in new.items():
        sub = entry.subentries[sub_id]
        kwargs: dict[str, Any] = {"data": data}
        if "title" in msg:
            kwargs["title"] = msg["title"].strip()
        if hass.config_entries.async_update_subentry(entry, sub, **kwargs):
            changed += 1
    connection.send_result(msg["id"], {"changed": changed})


def _configured(entry: ConfigEntry) -> set[str]:
    return {s.data.get(CONF_COVER_ENTITY) for s in _covers(entry).values()}


def _title(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    return state.name if state else entity_id


def _check_new(
    hass: HomeAssistant,
    entry: ConfigEntry,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> list[str] | None:
    entities = list(dict.fromkeys(msg["cover_entities"]))
    taken = _configured(entry)
    bad = [e for e in entities if not e.startswith("cover.") or e in taken]
    if bad or not entities:
        connection.send_error(
            msg["id"], "invalid_format", f"Not a new cover: {', '.join(bad) or '–'}"
        )
        return None
    return entities


def _add(
    hass: HomeAssistant, entry: ConfigEntry, entity_id: str, profile: str | None, settings: dict
) -> str:
    sub = ConfigSubentry(
        data={CONF_COVER_ENTITY: entity_id, CONF_PROFILE: profile, CONF_SETTINGS: settings},
        subentry_type=SUBENTRY_COVER,
        title=_title(hass, entity_id),
        unique_id=entity_id,
    )
    hass.config_entries.async_add_subentry(entry, sub)
    return sub.subentry_id


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_ADD,
        vol.Required("cover_entities"): [str],
        vol.Optional("profile"): vol.Any(None, str),
    }
)
@websocket_api.require_admin
@callback
def ws_add(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add covers (as *Add covers* on the entry)."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg)
        return
    entities = _check_new(hass, entry, connection, msg)
    if entities is None:
        return
    profile = msg.get("profile")
    if profile is not None and profile not in _profiles(entry):
        connection.send_error(msg["id"], "not_found", "Unknown profile")
        return
    ids = [_add(hass, entry, e, profile, {}) for e in entities]
    connection.send_result(msg["id"], {"subentry_ids": ids})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_DUPLICATE,
        vol.Required("subentry_id"): str,
        vol.Required("cover_entities"): [str],
    }
)
@websocket_api.require_admin
@callback
def ws_duplicate(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """New covers with the profile and the own values of an existing one."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg)
        return
    source = _covers(entry).get(msg["subentry_id"])
    if source is None:
        connection.send_error(msg["id"], "not_found", "Unknown cover")
        return
    entities = _check_new(hass, entry, connection, msg)
    if entities is None:
        return
    # Devices of this one window (contacts, room sensors) do not fit the new cover
    settings = {
        k: v
        for k, v in source.data.get(CONF_SETTINGS, {}).items()
        if not (
            k in BY_KEY and BY_KEY[k].levels == COVER_ONLY and BY_KEY[k].kind in (ENTITY, ENTITIES)
        )
    }
    profile = source.data.get(CONF_PROFILE)
    ids = [_add(hass, entry, e, profile, dict(settings)) for e in entities]
    connection.send_result(msg["id"], {"subentry_ids": ids})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_DELETE, vol.Required("subentry_ids"): [str]}
)
@websocket_api.require_admin
@callback
def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove covers from AutoShuttersControl (the cover itself stays)."""
    entry = _entry(hass)
    if entry is None:
        _not_loaded(connection, msg)
        return
    ids = _cover_ids(entry, connection, msg)
    if ids is None:
        return
    for sub_id in ids:
        hass.config_entries.async_remove_subentry(entry, sub_id)
    connection.send_result(msg["id"], {"removed": len(ids)})

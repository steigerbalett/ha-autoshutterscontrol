"""Diagnostics: effective settings and the last decisions of every cover."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import AscConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AscConfigEntry
) -> dict[str, Any]:
    """Return diagnostics."""
    manager = entry.runtime_data
    return {
        "global_settings": dict(manager.global_settings),
        "switches": dict(manager.switches),
        "subentries": [sub.as_dict() for sub in entry.subentries.values()],
        "covers": {sub_id: c.diagnostics() for sub_id, c in manager.controllers.items()},
    }

"""Test helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.autoshutterscontrol.const import DOMAIN

TZ_NAME = "Europe/Berlin"
TZ = ZoneInfo(TZ_NAME)
COVER = "cover.living_room"
COVER2 = "cover.kitchen"


def local(*args: int) -> datetime:
    """Local datetime."""
    return datetime(*args, tzinfo=TZ)


async def setup_hass(hass: HomeAssistant) -> None:
    """Location and time zone of Brilon."""
    await hass.config.async_set_time_zone(TZ_NAME)
    hass.config.latitude = 51.35
    hass.config.longitude = 8.57
    hass.config.elevation = 450


def set_cover(
    hass: HomeAssistant,
    entity_id: str = COVER,
    position: int = 0,
    state: str | None = None,
    context=None,
) -> None:
    """Set the state of a fake cover."""
    if state is None:
        state = "closed" if position == 0 else "open"
    hass.states.async_set(
        entity_id,
        state,
        {
            "current_position": position,
            "supported_features": 15,
            "friendly_name": entity_id.split(".")[1],
        },
        context=context,
    )


def cover_subentry(
    entity_id: str = COVER,
    settings: dict[str, Any] | None = None,
    profile: str | None = None,
    sub_id: str = "sub_cover",
) -> dict[str, Any]:
    """Subentry data of a cover."""
    return {
        "data": {"cover_entity": entity_id, "profile": profile, "settings": settings or {}},
        "subentry_id": sub_id,
        "subentry_type": "cover",
        "title": entity_id.split(".")[1],
        "unique_id": entity_id,
    }


def profile_subentry(
    name: str, settings: dict[str, Any], sub_id: str = "sub_profile"
) -> dict[str, Any]:
    """Subentry data of a profile."""
    return {
        "data": {"settings": settings},
        "subentry_id": sub_id,
        "subentry_type": "profile",
        "title": name,
        "unique_id": None,
    }


async def setup_entry(
    hass: HomeAssistant,
    global_settings: dict[str, Any] | None = None,
    subentries: list[dict[str, Any]] | None = None,
) -> MockConfigEntry:
    """Create and load the main entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AutoShuttersControl",
        data={},
        options={"settings": global_settings or {}},
        subentries_data=subentries if subentries is not None else [cover_subentry()],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def mock_cover_services(hass: HomeAssistant) -> list:
    """Record set_cover_position calls."""
    return async_mock_service(hass, "cover", "set_cover_position")

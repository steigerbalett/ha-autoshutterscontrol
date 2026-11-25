"""Alternative profile while an entity shows a value (concept 6.7, CCA instance_active)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.autoshutterscontrol.const import DOMAIN

from .helpers import (
    cover_subentry,
    local,
    mock_cover_services,
    profile_subentry,
    set_cover,
    setup_entry,
    setup_hass,
)

WINTER = "input_boolean.winter"


def subentries(**extra):
    cover = cover_subentry(profile="p_summer")
    cover["data"].update({"profile_alt": "p_winter", "profile_switch_entity": WINTER, **extra})
    return [
        profile_subentry("Summer", {"pos_open": 100}, sub_id="p_summer"),
        profile_subentry("Winter", {"pos_open": 60}, sub_id="p_winter"),
        cover,
    ]


def target(hass: HomeAssistant):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "sub_cover_target")
    return hass.states.get(entity_id)


async def test_switch_profile_by_entity(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    hass.states.async_set(WINTER, "off")
    calls = mock_cover_services(hass)
    await setup_entry(hass, {"up_mode": "time", "down_mode": "time"}, subentries())
    assert target(hass).attributes["profile"] == "Summer"
    hass.states.async_set(WINTER, "on")
    await hass.async_block_till_done()
    assert target(hass).attributes["profile"] == "Winter"
    assert calls[-1].data["position"] == 60
    set_cover(hass, position=60, context=calls[-1].context)
    # Unavailable: the last state counts
    hass.states.async_set(WINTER, "unavailable")
    await hass.async_block_till_done()
    assert target(hass).attributes["profile"] == "Winter"
    hass.states.async_set(WINTER, "off")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_switch_value(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    hass.states.async_set(WINTER, "Sommer")
    mock_cover_services(hass)
    await setup_entry(
        hass, {"up_mode": "time", "down_mode": "time"}, subentries(profile_switch_value="winter")
    )
    assert target(hass).attributes["profile"] == "Summer"
    hass.states.async_set(WINTER, "Winter")
    await hass.async_block_till_done()
    assert target(hass).attributes["profile"] == "Winter"


async def test_base_page_stores_switch(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    entry = await setup_entry(
        hass,
        {},
        [
            profile_subentry("Summer", {}, sub_id="p_summer"),
            profile_subentry("Winter", {}, sub_id="p_winter"),
            cover_subentry(profile="p_summer"),
        ],
    )
    result = await entry.start_subentry_reconfigure_flow(hass, "sub_cover")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "base"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Living room",
            "profile": "p_summer",
            "profile_alt": "p_winter",
            "profile_switch_entity": WINTER,
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    data = entry.subentries["sub_cover"].data
    assert data["profile_alt"] == "p_winter"
    assert data["profile_switch_entity"] == WINTER
    assert data["profile_switch_value"] is None

"""Config flow, options flow and subentry flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.autoshutterscontrol.const import DOMAIN

from .helpers import (
    COVER,
    COVER2,
    cover_subentry,
    profile_subentry,
    set_cover,
    setup_entry,
    setup_hass,
)


async def test_user_flow_single_instance(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"workday_sensor": "binary_sensor.workday"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {"settings": {"workday_sensor": "binary_sensor.workday"}}
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    entry = await setup_entry(hass, {"pos_open": 90})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "schedule"}
    )
    assert result["type"] is FlowResultType.FORM
    # defaults are prefilled
    schema = {str(k): k for k in result["data_schema"].schema}
    assert schema["up_mode"].description["suggested_value"] == "astro"
    user_input = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description
    }
    user_input["up_mode"] = "time"
    user_input["time_up_early_workday"] = "06:30:00"
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"keys": ["pos_open"]}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    settings = entry.options["settings"]
    assert settings["up_mode"] == "time"
    assert settings["time_up_early_workday"] == "06:30:00"
    assert "pos_open" not in settings
    await hass.async_block_till_done()
    manager = entry.runtime_data
    assert manager.controllers["sub_cover"].cfg["up_mode"] == "time"


async def test_add_covers_with_profile(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    set_cover(hass, COVER2)
    set_cover(hass, "cover.bath")
    entry = await setup_entry(hass, {}, [profile_subentry("South", {}), cover_subentry()])
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "cover"), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    # covers that are set up already cannot be chosen
    selector = next(v for k, v in result["data_schema"].schema.items() if str(k) == "cover_entity")
    assert selector.config["exclude_entities"] == [COVER]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"cover_entity": [COVER2, "cover.bath"], "profile": "sub_profile"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    covers = [s for s in entry.subentries.values() if s.subentry_type == "cover"]
    assert {c.data["cover_entity"] for c in covers} == {COVER, COVER2, "cover.bath"}
    assert all(
        c.data["profile"] == "sub_profile" for c in covers if c.data["cover_entity"] != COVER
    )
    # reloaded with the new covers
    assert len(entry.runtime_data.controllers) == 3


async def test_reconfigure_cover(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    entry = await setup_entry(
        hass,
        {"pos_open": 90},
        [profile_subentry("South", {"pos_open": 80}), cover_subentry(settings={"tolerance": 5})],
    )
    result = await entry.start_subentry_reconfigure_flow(hass, "sub_cover")
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "positions"}
    )
    assert result["type"] is FlowResultType.FORM
    # without profile the global value is inherited
    assert result["description_placeholders"]["inh_pos_open"] == "90 %"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"pos_open": 75, "tolerance": 5, "invert": "on"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "base"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Living", "profile": "sub_profile"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "positions"}
    )
    assert result["description_placeholders"]["inh_pos_open"] == "80 %"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"pos_open": 75, "invert": "inherit"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reset"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"keys": ["pos_open"]}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "override"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"override_blocks": ["none"], "override_reset": "inherit", "override_return": "off"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    sub = entry.subentries["sub_cover"]
    assert sub.title == "Living"
    assert sub.data["profile"] == "sub_profile"
    assert sub.data["settings"] == {"override_blocks": [], "override_return": False}
    await hass.async_block_till_done()
    cfg = entry.runtime_data.controllers["sub_cover"].cfg
    assert cfg["pos_open"] == 80
    assert cfg["override_blocks"] == ()


async def test_add_profile(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    entry = await setup_entry(hass, {})
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "profile"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "base"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bedrooms"}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "schedule"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"up_mode": "time", "time_up_early_workday": "07:15:00", "down_tomorrow_workday": "on"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    profiles = [s for s in entry.subentries.values() if s.subentry_type == "profile"]
    assert profiles[0].title == "Bedrooms"
    assert profiles[0].data["settings"] == {
        "up_mode": "time",
        "time_up_early_workday": "07:15:00",
        "down_tomorrow_workday": True,
    }


async def test_stage3_pages(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass)
    entry = await setup_entry(hass, {"residents_house": ["person.anna"]})
    # Global residents and shading pages
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert {"residents", "shading", "tilt"} <= set(result["menu_options"])
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "residents"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"residents_house": ["person.anna", "person.ben"], "self_defense_mode": "absent"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "shading"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"shading_mode": "always", "shading_must": ["azimuth", "elevation"], "shading_any": []},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    settings = entry.options["settings"]
    assert settings["residents_house"] == ["person.anna", "person.ben"]
    assert settings["shading_must"] == ["azimuth", "elevation"]
    await hass.async_block_till_done()
    # Cover: room sources and own slat entity, inherited house sources shown
    result = await entry.start_subentry_reconfigure_flow(hass, "sub_cover")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "residents"}
    )
    placeholders = result["description_placeholders"]
    assert placeholders["inh_residents_house"] == "person.anna, person.ben"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"residents_room": ["binary_sensor.bed"], "residents_house": []}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "tilt"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"tilt_entity": "cover.slats", "tilt_shading": 40}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert entry.subentries["sub_cover"].data["settings"] == {
        "residents_room": ["binary_sensor.bed"],
        "tilt_entity": "cover.slats",
        "tilt_shading": 40,
    }
    await hass.async_block_till_done()
    cfg = entry.runtime_data.controllers["sub_cover"].cfg
    assert cfg["residents_house"] == ("person.anna", "person.ben")

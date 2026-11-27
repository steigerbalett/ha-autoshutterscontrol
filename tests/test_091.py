"""0.9.1: import of one shutter from FHEM, update of existing covers, overview."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.autoshutterscontrol.engine import fhem

from .helpers import COVER, cover_subentry, mock_cover_services, set_cover, setup_entry, setup_hass

# Output of "list -r EG_Wohnzimmer" in FHEM (name differs from the cover)
LIST_ONE = """define EG_Wohnzimmer dummy
attr EG_Wohnzimmer room Wohnzimmer
attr EG_Wohnzimmer ASC_Closed_Pos 15
attr EG_Wohnzimmer ASC_Open_Pos 100
attr EG_Wohnzimmer ASC_WindowRec Fenster_WZ
attr EG_Wohnzimmer ASC_Down {sunset()}
setstate EG_Wohnzimmer 100
setstate EG_Wohnzimmer 2026-11-20 10:00:00 ASC_Time_DriveUp 08:00
"""

LIST_TWO = (
    LIST_ONE
    + """define OG_Bad dummy
attr OG_Bad ASC 1
attr OG_Bad ASC_Closed_Pos 30
"""
)


def test_convert_loose_takes_shutter_without_asc_attribute() -> None:
    assert fhem.convert(LIST_ONE).shutters == {}
    result = fhem.convert(LIST_ONE, loose=True)
    assert list(result.shutters) == ["EG_Wohnzimmer"]
    values = result.shutters["EG_Wohnzimmer"]
    assert values["pos_closed"] == 15
    assert fhem.references_in(values) == ["Fenster_WZ"]
    assert "EG_Wohnzimmer: ASC_Down (Perl)" in result.not_transferred


async def _open_import(hass: HomeAssistant, entry):
    result = await entry.start_subentry_reconfigure_flow(hass, "sub_cover")
    assert "fhem_import" in result["menu_options"]
    assert result["menu_options"][-1] == "save"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "fhem_import"}
    )


async def test_cover_import_one_shutter(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    hass.config.language = "de"
    set_cover(hass, position=100)
    mock_cover_services(hass)
    hass.states.async_set("binary_sensor.fenster_wz", "off", {"friendly_name": "Fenster WZ"})
    entry = await setup_entry(hass, {}, [cover_subentry(settings={"pos_sleep": 20})])
    result = await _open_import(hass, entry)
    assert result["step_id"] == "fhem_import"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"fhem_cfg": "attr x room y"}
    )
    assert result["errors"] == {"fhem_cfg": "fhem_nothing_found"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"fhem_cfg": LIST_ONE}
    )
    assert result["step_id"] == "fhem_entities"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested == {"Fenster_WZ": "binary_sensor.fenster_wz"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"Fenster_WZ": "binary_sensor.fenster_wz"}
    )
    assert result["step_id"] == "fhem_done"
    placeholders = result["description_placeholders"]
    assert placeholders["shutter"] == "EG_Wohnzimmer"
    # pos_open 100 is the default and stays inherited
    assert placeholders["count"] == "2"
    assert "15" in placeholders["values"]
    assert placeholders["not_transferred"] == "ASC_Down (Perl)"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {
        "pos_sleep": 20,
        "pos_closed": 15,
        "window_state_sensor": "binary_sensor.fenster_wz",
    }


async def test_cover_import_pick_and_replace(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(
        hass, {}, [cover_subentry(settings={"pos_sleep": 20, "pos_closed": 5})]
    )
    result = await _open_import(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"fhem_cfg": LIST_TWO}
    )
    assert result["step_id"] == "fhem_pick"
    assert result["description_placeholders"]["count"] == "2"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"shutter": "OG_Bad"}
    )
    assert result["step_id"] == "fhem_done"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"replace": True}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {"pos_closed": 30}


async def test_cover_import_value_equal_to_inherited_inherits(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(hass, {}, [cover_subentry(settings={"pos_open": 80})])
    result = await _open_import(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"fhem_cfg": "attr R ASC_Open_Pos 100"}
    )
    assert result["step_id"] == "fhem_done"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "save"}
    )
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {}


async def test_profile_has_no_import(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    entry = await setup_entry(hass, {}, [])
    flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "profile"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(flow["flow_id"], {"name": "Süd"})
    assert "fhem_import" not in result["menu_options"]


GLOBAL_CFG = """define ASC_Dev AutoShuttersControl
attr Rollo_Living_Room ASC 2
attr Rollo_Living_Room ASC_Closed_Pos 10
"""


async def _global_import(hass: HomeAssistant, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fhem_import"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"fhem_cfg": GLOBAL_CFG}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Rollo_Living_Room": COVER}
    )
    assert result["step_id"] == "fhem_done"
    return result


async def test_global_import_updates_existing_cover(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(hass, {}, [cover_subentry(settings={"pos_sleep": 20})])
    result = await _global_import(hass, entry)
    assert "update_existing" in {str(k) for k in result["data_schema"].schema}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"update_existing": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {"pos_sleep": 20, "pos_closed": 10}


async def test_global_import_keeps_existing_cover(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(hass, {}, [cover_subentry(settings={"pos_sleep": 20})])
    result = await _global_import(hass, entry)
    await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {"pos_sleep": 20}


async def test_summary_is_a_list_per_cover(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    hass.config.language = "de"
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(hass, {"panel": True})
    placeholders = entry.runtime_data.summary_markdown()
    assert placeholders["covers"].startswith("**living_room**\n- Position: 100 %")
    assert "| " not in placeholders["covers"]
    assert placeholders["panel"] == (
        "Übersicht in der Seitenleiste: an · [Große Übersicht öffnen](/autoshutterscontrol)"
    )

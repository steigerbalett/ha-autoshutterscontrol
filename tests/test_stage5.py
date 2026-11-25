"""Integration tests of stage 5: catching up, plausibility check, logbook, diagnostics,
import from FHEM."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID, EVENT_LOGBOOK_ENTRY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.autoshutterscontrol.const import DOMAIN, STORAGE_KEY
from custom_components.autoshutterscontrol.diagnostics import async_get_config_entry_diagnostics

from .helpers import (
    COVER,
    cover_subentry,
    local,
    mock_cover_services,
    set_cover,
    setup_entry,
    setup_hass,
)

TIME_MODE = {"up_mode": "time", "down_mode": "time"}


def eid(hass: HomeAssistant, platform: str, key: str, sub: str = "sub_cover") -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{sub}_{key}")
    assert entity_id, key
    return entity_id


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


def alive(hass_storage, when) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"global": {"alive": when.isoformat()}, "covers": {}},
    }


@pytest.fixture
async def evening(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 25 November 2026, 18:00, cover still open."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 18, 0))
    set_cover(hass, position=100)
    return mock_cover_services(hass)


async def test_catch_up_missed_evening(hass: HomeAssistant, evening, freezer, hass_storage) -> None:
    calls = evening
    alive(hass_storage, local(2026, 11, 25, 15, 0))  # down before the evening drive
    await setup_entry(hass, TIME_MODE)
    assert calls == []
    await tick(hass, freezer, local(2026, 11, 25, 18, 0, 50))
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "night_close"


async def test_no_catch_up_without_missed_drive(
    hass: HomeAssistant, evening, freezer, hass_storage
) -> None:
    calls = evening
    alive(hass_storage, local(2026, 11, 25, 17, 55))  # it was already night
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 11, 25, 18, 0, 50))
    assert calls == []


async def test_catch_up_always(hass: HomeAssistant, evening, freezer, hass_storage) -> None:
    calls = evening
    alive(hass_storage, local(2026, 11, 25, 17, 55))
    await setup_entry(hass, {**TIME_MODE, "recovery": "always"})
    await tick(hass, freezer, local(2026, 11, 25, 18, 0, 50))
    assert calls[-1].data["position"] == 0


async def test_catch_up_off(hass: HomeAssistant, evening, freezer, hass_storage) -> None:
    calls = evening
    alive(hass_storage, local(2026, 11, 25, 15, 0))
    await setup_entry(hass, {**TIME_MODE, "recovery": "off"})
    await tick(hass, freezer, local(2026, 11, 25, 18, 0, 50))
    assert calls == []


async def test_catch_up_when_cover_is_back(hass: HomeAssistant, evening, freezer) -> None:
    calls = evening
    freezer.move_to(local(2026, 11, 25, 15, 0))
    await setup_entry(hass, TIME_MODE)
    hass.states.async_set(COVER, "unavailable")
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    assert hass.states.get(eid(hass, "sensor", "blocked_by")).state == "unavailable"
    set_cover(hass, position=100)
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0


async def test_logbook_entries(hass: HomeAssistant, evening, freezer) -> None:
    calls = evening
    entries = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)
    freezer.move_to(local(2026, 11, 25, 15, 0))
    await setup_entry(hass, TIME_MODE)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: eid(hass, "switch", "cover_pause")},
        blocking=True,
    )
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    assert entries[-1].data["entity_id"] == COVER
    assert entries[-1].data["message"] == "did not drive (Evening closing): Pause"
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: eid(hass, "switch", "cover_pause")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0
    assert entries[-1].data["message"] == "drove to 0 % (Evening closing)"
    assert hass.states.get(eid(hass, "sensor", "blocked_by")).state == "unknown"


async def test_logbook_off(hass: HomeAssistant, evening, freezer) -> None:
    entries = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)
    freezer.move_to(local(2026, 11, 25, 15, 0))
    await setup_entry(hass, {**TIME_MODE, "logbook": False})
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert entries == []


async def test_plausibility_issues(hass: HomeAssistant, evening) -> None:
    entry = await setup_entry(
        hass,
        {**TIME_MODE, "rain_protection": True},
        [cover_subentry(settings={"window_open_sensor": "binary_sensor.gone"})],
    )
    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, "check_missing_rain_sub_cover")
    assert issue is not None
    assert issue.translation_placeholders["name"] == "living_room"
    missing = registry.async_get_issue(DOMAIN, "check_entity_missing_sub_cover")
    assert missing.translation_placeholders["entities"] == "binary_sensor.gone"
    # Fixed in the options: the issue disappears after the reload
    hass.config_entries.async_update_entry(
        entry, options={"settings": {**TIME_MODE, "rain_sensor": "binary_sensor.rain"}}
    )
    hass.states.async_set("binary_sensor.rain", "off")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, "check_missing_rain_sub_cover") is None


async def test_diagnostics_have_inputs(hass: HomeAssistant, evening, freezer) -> None:
    freezer.move_to(local(2026, 11, 25, 15, 0))
    entry = await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    diag = await async_get_config_entry_diagnostics(hass, entry)
    decision = diag["covers"]["sub_cover"]["decisions"][-1]
    assert decision["reason"] == "night_close"
    assert decision["inputs"]["situation"]["trigger"] == "schedule_down"
    assert decision["inputs"]["wishes"][0]["source"] == "schedule"


FHEM_CFG = """define ASC_Dev AutoShuttersControl
attr ASC_Dev ASC_tempSensor Aussen:temperature
attr ASC_Dev ASC_freezeTemp 3
attr Rollo_Living_Room ASC 2
attr Rollo_Living_Room ASC_Closed_Pos 10
attr Rollo_Living_Room ASC_Antifreeze soft
attr Rollo_Living_Room ASC_Down {sunset()}
attr Rollo_Kitchen ASC 1
attr Rollo_Kitchen ASC_Closed_Pos 20
"""


async def test_fhem_import(hass: HomeAssistant, evening) -> None:
    set_cover(hass, "cover.kitchen", position=100)
    hass.states.async_set("sensor.aussen", "5", {"friendly_name": "Außen"})
    entry = await setup_entry(hass, TIME_MODE, [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "fhem_import" in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fhem_import"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"fhem_cfg": "nothing here"}
    )
    assert result["errors"] == {"fhem_cfg": "fhem_nothing_found"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"fhem_cfg": FHEM_CFG}
    )
    assert result["step_id"] == "fhem_covers"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested == {"Rollo_Living_Room": COVER, "Rollo_Kitchen": "cover.kitchen"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Rollo_Living_Room": COVER, "Rollo_Kitchen": "cover.kitchen"}
    )
    assert result["step_id"] == "fhem_entities"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Aussen": "sensor.aussen"}
    )
    assert result["step_id"] == "fhem_done"
    assert (
        "Rollo_Living_Room: ASC_Down (Perl)"
        in result["description_placeholders"]["not_transferred"]
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    settings = entry.options["settings"]
    assert settings["outdoor_temperature_sensor"] == "sensor.aussen"
    assert settings["frost_temp"] == 3.0
    covers = {
        sub.data["cover_entity"]: sub.data["settings"]
        for sub in entry.subentries.values()
        if sub.subentry_type == "cover"
    }
    assert covers == {
        COVER: {"pos_closed": 10, "frost_mode": "soft"},
        "cover.kitchen": {"pos_closed": 20},
    }
    _ = timedelta

"""Integration tests: schedule, manual override, switches, services, storage."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.autoshutterscontrol.const import DOMAIN

from .helpers import (
    COVER,
    COVER2,
    cover_subentry,
    local,
    mock_cover_services,
    profile_subentry,
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


@pytest.fixture
async def base(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 04:00, cover closed."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 4, 0))
    set_cover(hass, position=0)
    return mock_cover_services(hass)


async def test_entities_and_next_times(hass: HomeAssistant, base) -> None:
    await setup_entry(hass, TIME_MODE)
    up = hass.states.get(eid(hass, "sensor", "next_up")).state
    down = hass.states.get(eid(hass, "sensor", "next_down")).state
    assert up == "2026-11-25T04:00:00+00:00"
    assert down == "2026-11-25T15:00:00+00:00"
    assert hass.states.get(eid(hass, "binary_sensor", "is_day")).state == "off"
    assert hass.states.get(eid(hass, "sensor", "target")).state == "close"
    # central device
    ent = er.async_get(hass)
    entry_ids = [e for e in ent.entities.values() if e.platform == DOMAIN]
    assert any(e.unique_id.endswith("_global_automatic") for e in entry_ids)
    # cover device hangs below the central device
    dev = dr.async_get(hass)
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    central = dev.async_get_device_by_identifier((DOMAIN, entry_id), entry_id)
    cover_dev = dev.async_get_device_by_identifier((DOMAIN, "sub_cover"), entry_id)
    assert cover_dev.via_device_id == central.id
    # config entities disabled by default
    time_entity = ent.async_get(eid(hass, "time", "time_up_early_workday"))
    assert time_entity.disabled_by is not None


async def test_morning_and_evening_drive(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert len(calls) == 1
    assert calls[0].data == {ATTR_ENTITY_ID: COVER, "position": 100}
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "day_open"
    assert hass.states.get(eid(hass, "binary_sensor", "is_day")).state == "on"

    # The cover reports with our context: no manual override
    set_cover(hass, position=100, context=calls[0].context)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"

    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert len(calls) == 2
    assert calls[1].data["position"] == 0
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "night_close"
    # next morning is Thursday 05:00
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-26T04:00:00+00:00"


async def test_astro_mode_uses_sunrise(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, {})
    up = hass.states.get(eid(hass, "sensor", "next_up")).state
    # Sunrise in Brilon on 25 Nov is around 07:5x local time
    assert up.startswith("2026-11-25T06:5")
    await tick(hass, freezer, local(2026, 11, 25, 8, 0))
    assert len(calls) == 1


async def test_weekend_and_workday_sensor(hass: HomeAssistant, base) -> None:
    hass.states.async_set("binary_sensor.workday", "off")
    await setup_entry(hass, {**TIME_MODE, "workday_sensor": "binary_sensor.workday"})
    # today is no workday -> 08:00 local
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-25T07:00:00+00:00"
    hass.states.async_set("binary_sensor.workday", "on")
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-25T04:00:00+00:00"


async def test_global_weekend_switch(hass: HomeAssistant, base, freezer) -> None:
    freezer.move_to(local(2026, 11, 28, 4, 0))  # Saturday
    await setup_entry(hass, TIME_MODE)
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-28T07:00:00+00:00"
    switch = er.async_get(hass).async_get_entity_id(
        "switch",
        DOMAIN,
        f"{hass.config_entries.async_entries(DOMAIN)[0].entry_id}_global_weekend_times",
    )
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: switch}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-28T04:00:00+00:00"


async def test_profile_inheritance(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(
        hass,
        {**TIME_MODE, "pos_open": 90},
        [
            profile_subentry("South", {"pos_open": 70, "time_up_early_workday": "06:00:00"}),
            cover_subentry(profile="sub_profile", settings={"pos_open": 60}),
        ],
    )
    target = hass.states.get(eid(hass, "sensor", "target"))
    assert target.attributes["effective_config"]["pos_open"] == {"value": 60, "source": "cover"}
    assert target.attributes["effective_config"]["time_up_early_workday"]["source"] == "profile"
    assert target.attributes["effective_config"]["up_mode"]["source"] == "global"
    await tick(hass, freezer, local(2026, 11, 25, 6, 0, 1))
    assert calls[-1].data["position"] == 60


async def test_manual_override(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, {**TIME_MODE, "override_blocks": ["open"]})
    # Someone opens by hand (new context, no own drive)
    set_cover(hass, position=50, context=Context(user_id="abc"))
    await hass.async_block_till_done()
    override = hass.states.get(eid(hass, "binary_sensor", "manual_override"))
    assert override.state == "on"
    assert override.attributes["until"] is not None
    # Scheduled opening is blocked by the override
    await tick(hass, freezer, local(2026, 11, 25, 4, 10))
    # still active after 10 minutes, ends after 20
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "on"
    await tick(hass, freezer, local(2026, 11, 25, 4, 21))
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"
    assert not calls


async def test_override_blocks_schedule(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(
        hass, {**TIME_MODE, "override_blocks": ["open"], "override_reset": "next_schedule"}
    )
    set_cover(hass, position=30, context=Context())
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert not calls
    target = hass.states.get(eid(hass, "sensor", "target"))
    assert target.attributes["last_decision"]["blocked_by"] == "manual_override"
    # next_schedule: the override ended with the scheduled drive
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"


async def test_override_return(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    freezer.move_to(local(2026, 11, 25, 10, 0))
    set_cover(hass, position=100)
    await setup_entry(hass, {**TIME_MODE, "override_return": True, "override_minutes": 5})
    set_cover(hass, position=0, context=Context())
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 10, 6))
    assert len(calls) == 1
    assert calls[0].data["position"] == 100


async def test_manual_counts_as_morning(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    # astro with window: earliest 05:00, sunrise ~07:5x
    await setup_entry(hass, {})
    freezer.move_to(local(2026, 11, 25, 6, 0))
    set_cover(hass, position=100, context=Context())
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 8, 31))
    assert not calls
    assert hass.states.get(eid(hass, "sensor", "target")).attributes["last_decision"][
        "blocked_by"
    ] in (
        "done_by_manual",
        "at_target",
    )


async def test_own_drive_reports_after_context_expired(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert len(calls) == 1
    # The device reports later with a fresh context (as many integrations do)
    set_cover(hass, position=40, state="opening", context=Context())
    set_cover(hass, position=100, context=Context())
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"


async def test_delay(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, {**TIME_MODE, "delay_fixed": 30})
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert not calls
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 32))
    assert len(calls) == 1


async def test_pause_and_resume(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, TIME_MODE)
    pause = eid(hass, "switch", "cover_pause")
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: pause}, blocking=True)
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert not calls
    assert (
        hass.states.get(eid(hass, "sensor", "target")).attributes["last_decision"]["blocked_by"]
        == "paused"
    )
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: pause}, blocking=True)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["position"] == 100


async def test_automatic_off(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    await setup_entry(hass, TIME_MODE)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: eid(hass, "switch", "cover_automatic")},
        blocking=True,
    )
    await tick(hass, freezer, local(2026, 11, 25, 5, 0, 1))
    assert not calls


async def test_services(hass: HomeAssistant, base, freezer) -> None:
    calls = base
    set_cover(hass, COVER2, position=0)
    entry = await setup_entry(
        hass,
        TIME_MODE,
        [cover_subentry(), cover_subentry(COVER2, sub_id="sub_cover2")],
    )
    await hass.services.async_call(
        DOMAIN, "drive", {"entity_id": [COVER], "named_position": "open"}, blocking=True
    )
    assert [c.data for c in calls] == [{ATTR_ENTITY_ID: COVER, "position": 100}]

    await hass.services.async_call(DOMAIN, "drive", {"position": 40}, blocking=True)
    assert len(calls) == 3

    # apply_target at night: already closed -> nothing
    await hass.services.async_call(DOMAIN, "apply_target", {"entity_id": [COVER2]}, blocking=True)
    assert len(calls) == 3

    await hass.services.async_call(
        DOMAIN,
        "set_option",
        {"entity_id": [COVER2], "option": "up_mode", "value": "astro"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover2"].data["settings"] == {"up_mode": "astro"}
    select = eid(hass, "select", "up_mode", "sub_cover2")
    assert hass.states.get(select).state == "astro"
    await hass.services.async_call(
        "select", "select_option", {ATTR_ENTITY_ID: select, "option": "inherit"}, blocking=True
    )
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover2"].data["settings"] == {}

    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "drive", {"entity_id": ["cover.none"], "position": 1}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_option",
            {"option": "up_mode", "value": "x", "entity_id": [COVER]},
            blocking=True,
        )


async def test_number_entity_writes_cover_setting(hass: HomeAssistant, base) -> None:
    entry = await setup_entry(hass, TIME_MODE)
    ent = er.async_get(hass)
    number = eid(hass, "number", "pos_open")
    ent.async_update_entity(number, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: number, "value": 80}, blocking=True
    )
    await hass.async_block_till_done()
    assert entry.subentries["sub_cover"].data["settings"] == {"pos_open": 80}
    assert hass.states.get(number).state == "80"


async def test_state_survives_reload(hass: HomeAssistant, base) -> None:
    entry = await setup_entry(hass, TIME_MODE)
    set_cover(hass, position=50, context=Context())
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "on"


async def test_missing_cover_repair(hass: HomeAssistant, base) -> None:
    await setup_entry(hass, TIME_MODE, [cover_subentry("cover.gone")])
    assert ir.async_get(hass).async_get_issue(DOMAIN, "cover_missing_sub_cover")


async def test_unload(hass: HomeAssistant, base) -> None:
    entry = await setup_entry(hass, TIME_MODE)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics(hass: HomeAssistant, base) -> None:
    from custom_components.autoshutterscontrol.diagnostics import async_get_config_entry_diagnostics

    entry = await setup_entry(hass, TIME_MODE)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["covers"]["sub_cover"]["effective_config"]["up_mode"]["value"] == "time"


async def test_startup_grace(hass: HomeAssistant, base, freezer) -> None:
    """Reports right after the start are no manual drives, a user's drive is."""
    await setup_entry(hass, TIME_MODE)
    set_cover(hass, position=40, context=Context())
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"
    set_cover(hass, position=60, context=Context(user_id="abc"))
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "on"
    await hass.services.async_call(DOMAIN, "clear_override", {"entity_id": [COVER]}, blocking=True)
    freezer.tick(31)
    set_cover(hass, position=20, context=Context())
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "on"

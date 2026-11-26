"""Integration tests of 0.9.0: drive check, horizon, depth of the sun, glare, temperature
limits, winter, away heat limits, holiday shift, lock, wind only open or closed."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.autoshutterscontrol.const import DOMAIN
from custom_components.autoshutterscontrol.engine.shading import depth_position
from custom_components.autoshutterscontrol.engine.tilt import window_azimuth

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
LUX = "sensor.lux"
TEMP = "sensor.outdoor"
WIND = "sensor.wind"
PERSON = "person.anna"


def eid(hass: HomeAssistant, platform: str, key: str, sub: str = "sub_cover") -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{sub}_{key}")
    assert entity_id, key
    return entity_id


def global_eid(hass: HomeAssistant, platform: str, key: str) -> str:
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
    assert entity_id, key
    return entity_id


def controller(hass: HomeAssistant):
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data.controllers["sub_cover"]


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def minutes(hass, freezer, start, count: int) -> None:
    for i in range(count):
        await tick(hass, freezer, start + timedelta(minutes=i, seconds=1))


def follow(hass: HomeAssistant, calls: list, position: int) -> None:
    set_cover(hass, position=position, context=calls[-1].context)


def reason(hass: HomeAssistant) -> str:
    return hass.states.get(eid(hass, "sensor", "last_reason")).state


@pytest.fixture
async def noon(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 17 June 2026, 12:00, cover open."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 6, 17, 12, 0))
    set_cover(hass, position=100)
    return mock_cover_services(hass)


# --- 1 drive check ----------------------------------------------------------------


async def test_drive_check_retry_and_stuck(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    assert len(calls) == 1
    # The cover did not move: after the drive time the command is sent again
    await tick(hass, freezer, local(2026, 6, 17, 16, 1, 15))
    assert len(calls) == 2
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}
    assert hass.states.get(eid(hass, "binary_sensor", "stuck")).state == "off"
    # Still not there: stuck, with a repair issue
    await tick(hass, freezer, local(2026, 6, 17, 16, 2, 30))
    assert len(calls) == 2
    stuck = hass.states.get(eid(hass, "binary_sensor", "stuck"))
    assert stuck.state == "on"
    assert stuck.attributes["target"] == 0
    assert ir.async_get(hass).async_get_issue(DOMAIN, "stuck_sub_cover") is not None
    # The next drive that arrives clears it
    await hass.services.async_call(
        DOMAIN, "drive", {ATTR_ENTITY_ID: [COVER], "position": 50}, blocking=True
    )
    follow(hass, calls, 50)
    await tick(hass, freezer, local(2026, 6, 17, 16, 4, 0))
    assert hass.states.get(eid(hass, "binary_sensor", "stuck")).state == "off"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "stuck_sub_cover") is None


async def test_drive_check_arrived(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    follow(hass, calls, 0)
    await tick(hass, freezer, local(2026, 6, 17, 16, 1, 15))
    await tick(hass, freezer, local(2026, 6, 17, 16, 2, 30))
    assert len(calls) == 1
    assert hass.states.get(eid(hass, "binary_sensor", "stuck")).state == "off"


async def test_drive_check_off(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, {**TIME_MODE, "drive_check": False})
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    await tick(hass, freezer, local(2026, 6, 17, 16, 1, 15))
    assert len(calls) == 1


async def test_drive_check_manual_cancels(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    await tick(hass, freezer, local(2026, 6, 17, 16, 1, 5))
    set_cover(hass, position=40)  # wall switch
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 6, 17, 16, 1, 15))
    await tick(hass, freezer, local(2026, 6, 17, 16, 2, 30))
    assert len(calls) == 1


# --- 2 horizon --------------------------------------------------------------------

SUN_WEST = {
    **TIME_MODE,
    "time_down_early_workday": "22:00:00",
    "shading_mode": "always",
    "shading_azimuth_start": 200,
    "shading_azimuth_end": 320,
    "shading_elevation_min": 5,
    "shading_delay_start": 0,
    "shading_delay_end": 0,
}


async def test_sun_left_button(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 6, 17, 18, 0))
    await setup_entry(hass, SUN_WEST)
    await tick(hass, freezer, local(2026, 6, 17, 18, 1, 1))
    assert calls[-1].data["position"] == 30
    follow(hass, calls, 30)
    ctrl = controller(hass)
    assert ctrl.shading_state == "in"
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: eid(hass, "button", "sun_left")}, blocking=True
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    horizon = entry.subentries["sub_cover"].data["settings"]["horizon"]
    azimuth, elevation = (float(v) for v in horizon.split(":"))
    assert 250 < azimuth < 300
    assert 10 < elevation < 40
    await tick(hass, freezer, local(2026, 6, 17, 18, 1, 5))
    await tick(hass, freezer, local(2026, 6, 17, 18, 2, 1))
    # The sun is behind the horizon now: shading ends, the cover goes up
    assert ctrl.shading_state == "out"
    assert calls[-1].data["position"] == 100
    # A second press near the same direction replaces the point
    await tick(hass, freezer, local(2026, 6, 17, 18, 10, 1))
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: eid(hass, "button", "sun_left")}, blocking=True
    )
    await hass.async_block_till_done()
    assert "," not in entry.subentries["sub_cover"].data["settings"]["horizon"]


async def test_horizon_invalid_issue(hass: HomeAssistant, noon) -> None:
    await setup_entry(hass, SUN_WEST, [cover_subentry(settings={"horizon": "west:20"})])
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "check_horizon_invalid_sub_cover") is not None


# --- 3 depth of the sun ---------------------------------------------------------------


async def test_shading_by_depth(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 6, 17, 17, 0))
    geometry = {"window_sill": 90, "window_height": 130, "sun_depth": 2.0}
    await setup_entry(hass, SUN_WEST, [cover_subentry(settings=geometry)])
    await tick(hass, freezer, local(2026, 6, 17, 17, 1, 1))
    ctrl = controller(hass)
    sun = ctrl.manager.sun
    now = local(2026, 6, 17, 17, 1, 1)
    expected = depth_position(
        ctrl.cfg, sun.elevation(now), sun.azimuth(now), window_azimuth(ctrl.cfg)
    )
    assert expected is not None and expected > 30
    assert ctrl.depth == expected
    assert calls[-1].data["position"] == expected
    assert reason(hass) == "shading"
    follow(hass, calls, expected)
    # Lower sun later: deeper into the room, the cover goes further down
    await minutes(hass, freezer, local(2026, 6, 17, 19, 0), 3)
    assert calls[-1].data["position"] < expected


# --- 4 glare protection -------------------------------------------------------------

GLARE = {
    **TIME_MODE,
    "shading_brightness_sensor": LUX,
    "shading_azimuth_start": 90,
    "shading_azimuth_end": 270,
    "glare": True,
}


async def test_glare_protection(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(LUX, "60000")
    await setup_entry(hass, GLARE)
    await minutes(hass, freezer, local(2026, 6, 17, 12, 1), 4)
    assert calls == []
    await minutes(hass, freezer, local(2026, 6, 17, 12, 5), 2)
    assert calls[-1].data["position"] == 40
    assert reason(hass) == "glare"
    assert hass.states.get(eid(hass, "binary_sensor", "glare")).state == "on"
    follow(hass, calls, 40)
    # Still bright above the end threshold: stays
    hass.states.async_set(LUX, "40000")
    await minutes(hass, freezer, local(2026, 6, 17, 12, 10), 25)
    assert len(calls) == 1
    hass.states.async_set(LUX, "20000")
    await minutes(hass, freezer, local(2026, 6, 17, 12, 40), 22)
    assert calls[-1].data["position"] == 100
    assert hass.states.get(eid(hass, "binary_sensor", "glare")).state == "off"


async def test_glare_not_while_away(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(LUX, "60000")
    hass.states.async_set(PERSON, "not_home")
    await setup_entry(hass, {**GLARE, "residents_house": [PERSON]})
    await minutes(hass, freezer, local(2026, 6, 17, 12, 1), 8)
    assert calls == []


# --- 5 temperature limits and winter -------------------------------------------------


async def test_temperature_limits(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(TEMP, "25")
    await setup_entry(
        hass, {**TIME_MODE, "outdoor_temperature_sensor": TEMP, "close_above_temp": 30}
    )
    hass.states.async_set(TEMP, "31")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "temp_high"
    follow(hass, calls, 0)
    hass.states.async_set(TEMP, "29.5")
    await hass.async_block_till_done()
    assert len(calls) == 1
    hass.states.async_set(TEMP, "28.5")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_close_below(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(TEMP, "-12")
    await setup_entry(
        hass, {**TIME_MODE, "outdoor_temperature_sensor": TEMP, "close_below_temp": -10}
    )
    await tick(hass, freezer, local(2026, 6, 17, 12, 1, 1))
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "temp_low"


async def test_winter_sensor(hass: HomeAssistant, noon, freezer) -> None:
    hass.states.async_set(TEMP, "5")
    await setup_entry(hass, {**TIME_MODE, "outdoor_temperature_sensor": TEMP})
    winter = hass.states.get(global_eid(hass, "binary_sensor", "winter"))
    assert winter.state == "on"
    assert winter.attributes["mean_24h"] == 5.0
    # Warm for a day: the mean rises above 12 + 1 °C
    hass.states.async_set(TEMP, "20")
    start = local(2026, 6, 17, 12, 0)
    for hour in range(1, 26):
        await tick(hass, freezer, start + timedelta(hours=hour))
    winter = hass.states.get(global_eid(hass, "binary_sensor", "winter"))
    assert winter.state == "off"
    assert winter.attributes["mean_24h"] > 19


# --- 6 nobody at home: lower heat limits ---------------------------------------------


async def test_away_lowers_heat_limit(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(TEMP, "23")
    hass.states.async_set(PERSON, "home")
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "outdoor_temperature_sensor": TEMP,
            "heat_protection_temp": 25,
            "away_heat_offset": 3,
            "residents_house": [PERSON],
        },
    )
    await tick(hass, freezer, local(2026, 6, 17, 12, 1, 1))
    assert calls == []
    hass.states.async_set(PERSON, "not_home")
    await tick(hass, freezer, local(2026, 6, 17, 12, 2, 1))
    assert calls[-1].data["position"] == 30
    assert reason(hass) == "heat"


# --- 7 holiday ---------------------------------------------------------------------------


async def test_holiday_shift(hass: HomeAssistant, noon, freezer) -> None:
    await setup_entry(hass, TIME_MODE)
    ctrl = controller(hass)
    normal = ctrl.next_down
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: global_eid(hass, "switch", "global_holiday")},
        blocking=True,
    )
    await hass.async_block_till_done()
    shifted = ctrl.next_down
    shift = ctrl.manager.holiday_shift("sub_cover", 30, "down", normal.date())
    assert shifted == normal + timedelta(minutes=shift)
    assert abs(shifted - normal) <= timedelta(minutes=30)
    # The same after a recalculation
    ctrl.recalculate()
    assert ctrl.next_down == shifted


# --- 8 lock -------------------------------------------------------------------------------


async def test_lock_with_duration(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await hass.services.async_call(
        DOMAIN,
        "set_lock",
        {ATTR_ENTITY_ID: [COVER], "mode": "closed", "duration": 30},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "lock"
    assert hass.states.get(eid(hass, "select", "lock")).state == "closed"
    follow(hass, calls, 0)
    await tick(hass, freezer, local(2026, 6, 17, 12, 30, 5))
    assert calls[-1].data["position"] == 100
    assert hass.states.get(eid(hass, "select", "lock")).state == "none"


async def test_lock_hold_blocks_evening(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: eid(hass, "select", "lock"), "option": "hold"},
        blocking=True,
    )
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    assert calls == []
    assert hass.states.get(eid(hass, "sensor", "blocked_by")).state == "locked"
    # A manual drive ends the lock
    set_cover(hass, position=60)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "select", "lock")).state == "none"


# --- 9 wind: only fully open or fully closed -------------------------------------------


async def test_wind_nearest_end(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(WIND, "10")
    set_cover(hass, position=70)
    await setup_entry(
        hass,
        {**TIME_MODE, "wind_sensor": WIND, "wind_mode": "nearest"},
        [cover_subentry(settings={"wind_protection": True})],
    )
    hass.states.async_set(WIND, "80")
    await hass.async_block_till_done()
    # The schedule wants 100 %: the nearest end is open
    assert calls[-1].data["position"] == 100
    assert reason(hass) == "wind"
    follow(hass, calls, 100)
    await tick(hass, freezer, local(2026, 6, 17, 12, 2, 1))
    # Moved by hand in between: back to an end
    set_cover(hass, position=60)
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100
    assert len(calls) == 2


async def test_wind_always_closed(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(WIND, "10")
    await setup_entry(
        hass,
        {**TIME_MODE, "wind_sensor": WIND, "wind_mode": "closed", "pos_wind": 50},
        [cover_subentry(settings={"wind_protection": True})],
    )
    hass.states.async_set(WIND, "80")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0

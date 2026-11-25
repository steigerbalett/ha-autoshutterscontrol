"""Integration tests of stage 3: residents, self defense, shading, slats, forecast."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.autoshutterscontrol.const import DOMAIN

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
PERSON = "person.anna"
BED = "binary_sensor.bed"
WINDOW = "binary_sensor.window"
LUX = "sensor.lux"
TEMP = "sensor.outdoor"


def eid(hass: HomeAssistant, platform: str, key: str, sub: str = "sub_cover") -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{sub}_{key}")
    assert entity_id, key
    return entity_id


def global_eid(hass: HomeAssistant, platform: str, key: str) -> str:
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
    assert entity_id, key
    return entity_id


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def minutes(hass, freezer, start, count: int) -> None:
    for i in range(count):
        await tick(hass, freezer, start + timedelta(minutes=i, seconds=1))


def follow(hass: HomeAssistant, calls: list, position: int, **kw) -> None:
    set_cover(hass, position=position, context=calls[-1].context, **kw)


async def switch(hass: HomeAssistant, key: str, on: bool = True) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {ATTR_ENTITY_ID: global_eid(hass, "switch", key)},
        blocking=True,
    )
    await hass.async_block_till_done()


def state(hass, entity_id, value, **attrs) -> None:
    hass.states.async_set(entity_id, value, attrs)


@pytest.fixture
async def noon(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 17 June 2026, 12:00, cover open, Anna at home."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 6, 17, 12, 0))
    set_cover(hass, position=100)
    state(hass, PERSON, "home")
    state(hass, BED, "off")
    state(hass, WINDOW, "off")
    return mock_cover_services(hass)


async def test_sleep_closes_and_wake_opens(hass: HomeAssistant, noon) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "residents_house": [PERSON], "pos_sleep": 10},
        [cover_subentry(settings={"residents_room": [BED]})],
    )
    assert hass.states.get(global_eid(hass, "sensor", "house_status")).state == "home"
    assert hass.states.get(eid(hass, "sensor", "residents")).state == "awoken"
    state(hass, BED, "on")
    await hass.async_block_till_done()
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 10}
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "sleep"
    follow(hass, calls, 10)
    state(hass, BED, "off")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"


async def test_wake_open_off(hass: HomeAssistant, noon) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "wake_open": False},
        [cover_subentry(settings={"residents_room": [BED]})],
    )
    state(hass, BED, "on")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0
    follow(hass, calls, 0)
    state(hass, BED, "off")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_morning_waits_while_asleep(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 6, 17, 4, 0))
    set_cover(hass, position=0)
    state(hass, BED, "on")
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"residents_room": [BED]})])
    await tick(hass, freezer, local(2026, 6, 17, 5, 0, 1))
    assert calls == []
    state(hass, BED, "off")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_residents_mode_up(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 6, 17, 4, 0))
    set_cover(hass, position=0)
    state(hass, BED, "on")
    await setup_entry(
        hass,
        {"up_mode": "residents", "down_mode": "time", "sleep_close": False},
        [cover_subentry(settings={"residents_room": [BED]})],
    )
    await minutes(hass, freezer, local(2026, 6, 17, 5, 0), 3)
    assert calls == []
    await tick(hass, freezer, local(2026, 6, 17, 6, 10))
    state(hass, BED, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 6, 17, 6, 11, 1))
    assert calls[-1].data["position"] == 100
    assert hass.states.get(eid(hass, "sensor", "next_up")).state.startswith("2026-06-18")


async def test_presence_up_only_when_home(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 6, 17, 4, 0))
    set_cover(hass, position=0)
    state(hass, PERSON, "not_home")
    await setup_entry(hass, {**TIME_MODE, "residents_house": [PERSON], "presence_up": "home"})
    assert hass.states.get(global_eid(hass, "sensor", "house_status")).state == "absent"
    await tick(hass, freezer, local(2026, 6, 17, 5, 0, 1))
    assert calls == []
    # Coming home by day: the morning drive is now allowed
    state(hass, PERSON, "home")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_self_defense_with_open_window(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "residents_house": [PERSON], "self_defense_mode": "absent"},
        [cover_subentry(settings={"window_open_sensor": WINDOW, "lockout": "soft"})],
    )
    await switch(hass, "global_self_defense")
    state(hass, WINDOW, "on")
    await hass.async_block_till_done()
    assert calls == []  # open window by day: nothing to ventilate
    state(hass, PERSON, "not_home")
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 6, 17, 12, 3))
    assert calls == []
    await tick(hass, freezer, local(2026, 6, 17, 12, 5, 30))
    assert calls[-1].data["position"] == 0
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "self_defense"
    assert hass.states.get(eid(hass, "binary_sensor", "self_defense")).state == "on"
    follow(hass, calls, 0)
    # Back home: target again
    state(hass, PERSON, "home")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_self_defense_needs_switch(hass: HomeAssistant, noon) -> None:
    calls = noon
    state(hass, WINDOW, "on")
    await setup_entry(
        hass,
        {**TIME_MODE, "residents_house": [PERSON], "self_defense_all": True},
    )
    state(
        hass,
        PERSON,
        "not_home",
    )
    state(hass, "alarm_control_panel.house", "armed_away")
    await hass.async_block_till_done()
    assert calls == []


async def test_self_defense_gone_all_covers(hass: HomeAssistant, noon) -> None:
    calls = noon
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "residents_house": ["alarm_control_panel.house"],
            "self_defense_all": True,
        },
    )
    await switch(hass, "global_self_defense")
    state(hass, "alarm_control_panel.house", "armed_away")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0


SHADING = {
    **TIME_MODE,
    "shading_mode": "always",
    "brightness_sensor": LUX,
    "outdoor_temperature_sensor": TEMP,
}


async def test_shading_start_and_end(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    state(hass, LUX, "50000")
    state(hass, TEMP, "25")
    await setup_entry(hass, SHADING)
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 1))
    assert hass.states.get(eid(hass, "sensor", "shading_state")).state == "in_reserved"
    assert calls == []
    await minutes(hass, freezer, local(2026, 6, 17, 13, 1), 10)
    assert hass.states.get(eid(hass, "sensor", "shading_state")).state == "in"
    assert calls[-1].data["position"] == 30
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "shading"
    follow(hass, calls, 30)
    # Clouds below the end threshold: end after 20 minutes
    await tick(hass, freezer, local(2026, 6, 17, 13, 30))
    state(hass, LUX, "5000")
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "sensor", "shading_state")).state == "out_reserved"
    await minutes(hass, freezer, local(2026, 6, 17, 13, 31), 18)
    assert calls[-1].data["position"] == 30
    await tick(hass, freezer, local(2026, 6, 17, 13, 50, 30))
    assert hass.states.get(eid(hass, "sensor", "shading_state")).state == "out"
    assert calls[-1].data["position"] == 100


async def test_shading_not_when_cold_or_switch_off(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    state(hass, LUX, "50000")
    state(hass, TEMP, "10")
    await setup_entry(hass, {**SHADING, "shading_delay_start": 0})
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 1))
    assert calls == []
    state(hass, TEMP, "25")
    await switch(hass, "global_shading", False)
    await tick(hass, freezer, local(2026, 6, 17, 13, 1, 1))
    assert calls == []
    await switch(hass, "global_shading", True)
    await tick(hass, freezer, local(2026, 6, 17, 13, 2, 1))
    assert calls[-1].data["position"] == 30


async def test_shading_end_leaves_manual_position(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    state(hass, LUX, "50000")
    state(hass, TEMP, "25")
    await setup_entry(
        hass, {**SHADING, "shading_delay_start": 0, "shading_delay_end": 0, "override_minutes": 1}
    )
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 1))
    assert calls[-1].data["position"] == 30
    follow(hass, calls, 30)
    await tick(hass, freezer, local(2026, 6, 17, 13, 3))
    from homeassistant.core import Context

    set_cover(hass, position=60, context=Context(user_id="x"))
    await tick(hass, freezer, local(2026, 6, 17, 13, 10))
    state(hass, LUX, "1000")
    await tick(hass, freezer, local(2026, 6, 17, 13, 11, 1))
    assert len(calls) == 1


async def test_heat_protection(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    state(hass, TEMP, "30")
    await setup_entry(
        hass, {**TIME_MODE, "outdoor_temperature_sensor": TEMP, "heat_protection_temp": 28}
    )
    await tick(hass, freezer, local(2026, 6, 17, 12, 1, 1))
    assert calls[-1].data["position"] == 30
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "heat"
    follow(hass, calls, 30)
    state(hass, TEMP, "20")
    await minutes(hass, freezer, local(2026, 6, 17, 12, 2), 5)
    assert len(calls) == 1
    # Evening drive as usual
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 1))
    assert calls[-1].data["position"] == 0


async def test_slats_after_standstill(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    tilt_calls = async_mock_service(hass, "cover", "set_cover_tilt_position")
    set_cover(hass, position=100)
    hass.states.async_set(
        COVER,
        "open",
        {"current_position": 100, "current_tilt_position": 100, "supported_features": 255},
    )
    state(hass, LUX, "50000")
    state(hass, TEMP, "25")
    await setup_entry(
        hass,
        {**SHADING, "shading_delay_start": 0, "tilt_shading": 40, "tilt_delay": 2},
    )
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 1))
    assert calls[-1].data["position"] == 30
    assert tilt_calls == []
    hass.states.async_set(
        COVER,
        "closing",
        {"current_position": 60, "current_tilt_position": 100, "supported_features": 255},
        context=calls[-1].context,
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        COVER,
        "open",
        {"current_position": 30, "current_tilt_position": 100, "supported_features": 255},
        context=calls[-1].context,
    )
    await hass.async_block_till_done()
    assert tilt_calls == []
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 4))
    assert tilt_calls[-1].data == {ATTR_ENTITY_ID: COVER, "tilt_position": 40}
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"


async def test_slat_steps_by_elevation(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    tilt_calls = async_mock_service(hass, "cover", "set_cover_tilt_position")
    hass.states.async_set(
        COVER,
        "open",
        {"current_position": 30, "current_tilt_position": 50, "supported_features": 255},
    )
    state(hass, LUX, "50000")
    state(hass, TEMP, "25")
    await setup_entry(
        hass,
        {
            **SHADING,
            "shading_delay_start": 0,
            "tilt_mode": "after",
            "tilt_delay": 0,
            "tilt_shading_steps": "20:70, 55:20",
        },
    )
    await tick(hass, freezer, local(2026, 6, 17, 12, 1, 1))
    # Already at the shading position: only the slats (elevation about 58° -> 20)
    assert calls == []
    assert tilt_calls[-1].data["tilt_position"] == 20
    # Afternoon: the sun is lower, next step
    hass.states.async_set(
        COVER,
        "open",
        {"current_position": 30, "current_tilt_position": 20, "supported_features": 255},
        context=tilt_calls[-1].context,
    )
    await tick(hass, freezer, local(2026, 6, 17, 15, 30, 1))
    assert tilt_calls[-1].data["tilt_position"] == 70


async def test_forecast_from_weather(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    asked: list[ServiceCall] = []

    async def get_forecasts(call: ServiceCall):
        asked.append(call)
        return {
            "weather.home": {
                "forecast": [
                    {"datetime": "2026-06-17T10:00:00+00:00", "temperature": 27.0},
                    {"datetime": "2026-06-18T10:00:00+00:00", "temperature": 15.0},
                ]
            }
        }

    hass.services.async_register(
        "weather", "get_forecasts", get_forecasts, supports_response=SupportsResponse.ONLY
    )
    state(hass, "weather.home", "sunny")
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "shading_mode": "always",
            "weather_entity": "weather.home",
            "shading_forecast_min": 24,
            "shading_delay_start": 0,
        },
    )
    await tick(hass, freezer, local(2026, 6, 17, 13, 0, 1))
    assert asked
    await tick(hass, freezer, local(2026, 6, 17, 13, 1, 1))
    assert calls[-1].data["position"] == 30
    attrs = hass.states.get(eid(hass, "sensor", "shading_state")).attributes
    assert attrs["forecast"] == 27.0
    assert attrs["weather"] == "sunny"

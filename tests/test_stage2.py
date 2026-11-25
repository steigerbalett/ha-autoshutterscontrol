"""Integration tests of stage 2: window, brightness, sun elevation, privacy, calendar."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

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
CONTACT = "binary_sensor.window"
TILTED = "binary_sensor.window_tilted"
LUX = "sensor.lux"


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
    """Fire the time every minute (the 60 s check)."""
    for i in range(count):
        await tick(hass, freezer, start + timedelta(minutes=i, seconds=1))


def follow(hass: HomeAssistant, calls: list, position: int) -> None:
    """The fake cover reaches the position of our last drive."""
    set_cover(hass, position=position, context=calls[-1].context)


@pytest.fixture
async def night(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 04:00, cover closed, window closed."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 4, 0))
    set_cover(hass, position=0)
    hass.states.async_set(CONTACT, "off")
    hass.states.async_set(TILTED, "off")
    return mock_cover_services(hass)


def window_cover(**settings):
    return cover_subentry(
        settings={"window_open_sensor": CONTACT, "window_tilted_sensor": TILTED, **settings}
    )


async def test_tilted_at_night_ventilates_and_closes_again(hass: HomeAssistant, night) -> None:
    calls = night
    await setup_entry(hass, TIME_MODE, [window_cover()])
    assert hass.states.get(eid(hass, "sensor", "window_state")).state == "closed"
    hass.states.async_set(TILTED, "on")
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "sensor", "window_state")).state == "tilted"
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 50}
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "ventilate"
    follow(hass, calls, 50)
    await hass.async_block_till_done()
    hass.states.async_set(TILTED, "off")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[-1].data["position"] == 0
    # No manual override from our own drives
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"


async def test_window_return_to_previous(hass: HomeAssistant, night) -> None:
    calls = night
    set_cover(hass, position=20)
    await setup_entry(hass, TIME_MODE, [window_cover(window_close_return="previous")])
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 50
    follow(hass, calls, 50)
    hass.states.async_set(CONTACT, "off")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 20
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "window_return"


async def test_ventilate_only_up(hass: HomeAssistant, night) -> None:
    calls = night
    set_cover(hass, position=80)
    await setup_entry(hass, TIME_MODE, [window_cover()])
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()
    assert calls == []


async def test_comfort_switch(hass: HomeAssistant, night) -> None:
    calls = night
    await setup_entry(hass, TIME_MODE, [window_cover()])
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 50
    follow(hass, calls, 50)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: global_eid(hass, "switch", "global_comfort")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 70
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "comfort"


async def test_window_open_delay(hass: HomeAssistant, night, freezer) -> None:
    calls = night
    await setup_entry(hass, TIME_MODE, [window_cover(window_open_delay=30)])
    hass.states.async_set(TILTED, "on")
    await hass.async_block_till_done()
    assert calls == []
    # Closed again within the delay: nothing happens
    await tick(hass, freezer, local(2026, 11, 25, 4, 0, 10))
    hass.states.async_set(TILTED, "off")
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 4, 1))
    assert calls == []
    hass.states.async_set(TILTED, "on")
    await hass.async_block_till_done()
    await tick(hass, freezer, local(2026, 11, 25, 4, 1, 31))
    assert calls[-1].data["position"] == 50


async def test_lockout_blocks_evening_until_door_closed(
    hass: HomeAssistant, night, freezer
) -> None:
    calls = night
    set_cover(hass, position=100)
    await setup_entry(hass, TIME_MODE, [window_cover(lockout="soft", ventilate_enabled=False)])
    await tick(hass, freezer, local(2026, 11, 25, 15, 0))
    hass.states.async_set(CONTACT, "on")
    await hass.async_block_till_done()
    assert calls == []
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    hass.states.async_set(CONTACT, "off")
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 0
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "night_close"


async def test_brightness_opens_after_duration(hass: HomeAssistant, night, freezer) -> None:
    calls = night
    hass.states.async_set(LUX, "10")
    await setup_entry(
        hass,
        {"up_mode": "brightness", "down_mode": "time", "brightness_sensor": LUX},
    )
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-25T07:30:00+00:00"
    await tick(hass, freezer, local(2026, 11, 25, 5, 10))
    hass.states.async_set(LUX, "1000")
    await hass.async_block_till_done()
    await minutes(hass, freezer, local(2026, 11, 25, 5, 11), 1)
    assert calls == []
    await minutes(hass, freezer, local(2026, 11, 25, 5, 12), 1)
    assert calls[-1].data["position"] == 100
    assert hass.states.get(eid(hass, "binary_sensor", "is_day")).state == "on"
    # The deadline is not driven again, the next morning is tomorrow
    assert hass.states.get(eid(hass, "sensor", "next_up")).state.startswith("2026-11-26")
    follow(hass, calls, 100)
    await tick(hass, freezer, local(2026, 11, 25, 8, 30, 1))
    assert len(calls) == 1


async def test_brightness_dark_before_early_time_waits(hass: HomeAssistant, night, freezer) -> None:
    calls = night
    hass.states.async_set(LUX, "1000")
    await setup_entry(
        hass,
        {"up_mode": "brightness", "down_mode": "time", "brightness_sensor": LUX},
    )
    await minutes(hass, freezer, local(2026, 11, 25, 4, 50), 5)
    assert calls == []
    await minutes(hass, freezer, local(2026, 11, 25, 5, 0), 4)
    assert calls[-1].data["position"] == 100


async def test_sun_elevation_closes(hass: HomeAssistant, night, freezer) -> None:
    calls = night
    set_cover(hass, position=100)
    await setup_entry(hass, {"up_mode": "time", "down_mode": "elevation"})
    await minutes(hass, freezer, local(2026, 11, 25, 16, 0), 60)
    assert len(calls) == 1
    assert calls[0].data["position"] == 0
    last = hass.states.get(eid(hass, "sensor", "last_reason")).state
    assert last == "night_close"
    assert hass.states.get(eid(hass, "binary_sensor", "is_day")).state == "off"


async def test_privacy_before_evening(hass: HomeAssistant, night, freezer) -> None:
    calls = night
    set_cover(hass, position=100)
    await setup_entry(hass, {**TIME_MODE, "privacy_down_minutes": 20})
    await tick(hass, freezer, local(2026, 11, 25, 12, 0))
    assert hass.states.get(eid(hass, "sensor", "next_privacy")).state == (
        "2026-11-25T14:40:00+00:00"
    )
    await tick(hass, freezer, local(2026, 11, 25, 15, 40, 1))
    assert calls[-1].data["position"] == 50
    assert hass.states.get(eid(hass, "sensor", "last_reason")).state == "privacy_down"
    follow(hass, calls, 50)
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls[-1].data["position"] == 0


async def test_calendar_window(hass: HomeAssistant, night) -> None:
    calls_cal: list[ServiceCall] = []

    async def get_events(call: ServiceCall):
        calls_cal.append(call)
        return {
            "calendar.shutters": {
                "events": [
                    {
                        "start": "2026-11-25T06:30:00+01:00",
                        "end": "2026-11-25T07:00:00+01:00",
                        "summary": "Open shutters",
                    },
                    {"start": "2026-11-25", "end": "2026-11-26", "summary": "close"},
                    {
                        "start": "2026-11-25T18:15:00+01:00",
                        "end": "2026-11-25T19:00:00+01:00",
                        "summary": "CLOSE",
                    },
                ]
            }
        }

    hass.services.async_register(
        "calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set("calendar.shutters", "off")
    await setup_entry(
        hass, {**TIME_MODE, "time_source": "calendar", "calendar": "calendar.shutters"}
    )
    await hass.async_block_till_done()
    assert calls_cal
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-25T05:30:00+00:00"
    assert hass.states.get(eid(hass, "sensor", "next_down")).state == "2026-11-25T17:15:00+00:00"


async def test_calendar_unavailable_falls_back_to_times(hass: HomeAssistant, night) -> None:
    await setup_entry(
        hass, {**TIME_MODE, "time_source": "calendar", "calendar": "calendar.missing"}
    )
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "sensor", "next_up")).state == "2026-11-25T04:00:00+00:00"

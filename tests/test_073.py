"""Integration tests of 0.7.3: simulation, staggered drives, quiet hours, hot day,
morning time from an entity, diagnostic sensors."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.autoshutterscontrol.const import DOMAIN

from .helpers import (
    COVER,
    COVER2,
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


def global_eid(hass: HomeAssistant, platform: str, key: str) -> str:
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
    assert entity_id, key
    return entity_id


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def turn_on(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()


def state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_simulation_drives_nothing(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    calls = mock_cover_services(hass)
    events = async_capture_events(hass, "autoshutterscontrol_drive")
    await setup_entry(hass, TIME_MODE)
    await turn_on(hass, global_eid(hass, "switch", "global_simulation"))
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    assert state(hass, eid(hass, "sensor", "simulated_drive")) == "0"
    attrs = hass.states.get(eid(hass, "sensor", "simulated_drive")).attributes
    assert attrs["reason"] == "night_close"
    assert events[-1].data["simulation"] is True
    # The last real drive is untouched
    assert state(hass, eid(hass, "sensor", "last_reason")) == "unknown"


async def test_simulation_per_cover(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    set_cover(hass, COVER2, position=100)
    calls = mock_cover_services(hass)
    await setup_entry(
        hass, TIME_MODE, [cover_subentry(), cover_subentry(COVER2, sub_id="sub_cover2")]
    )
    await turn_on(hass, eid(hass, "switch", "cover_simulation"))
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert [c.data[ATTR_ENTITY_ID] for c in calls] == [COVER2]


async def test_staggered_drives(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    set_cover(hass, COVER2, position=100)
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {**TIME_MODE, "drive_stagger": 10},
        [cover_subentry(), cover_subentry(COVER2, sub_id="sub_cover2")],
    )
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert len(calls) == 1
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 5))
    assert len(calls) == 1
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 12))
    assert len(calls) == 2
    assert {c.data[ATTR_ENTITY_ID] for c in calls} == {COVER, COVER2}


async def test_quiet_hours(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 22, 0))
    set_cover(hass, position=0)
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "time_up_early_workday": "07:00:00",
            "quiet_start": "21:30:00",
            "quiet_end": "07:30:00",
        },
    )
    assert state(hass, eid(hass, "binary_sensor", "quiet")) == "on"
    await tick(hass, freezer, local(2026, 11, 26, 6, 59))
    await tick(hass, freezer, local(2026, 11, 26, 7, 0, 1))
    assert calls == []
    assert state(hass, eid(hass, "sensor", "blocked_by")) == "quiet"
    # End of the quiet hours: to the target
    await tick(hass, freezer, local(2026, 11, 26, 7, 30, 30))
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 100}


async def test_quiet_hours_from_entity(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    hass.states.async_set("input_datetime.quiet_from", "15:00:00", {"has_time": True})
    hass.states.async_set("input_datetime.quiet_to", "17:00:00", {"has_time": True})
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "quiet_start_entity": "input_datetime.quiet_from",
            "quiet_end_entity": "input_datetime.quiet_to",
        },
    )
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    await tick(hass, freezer, local(2026, 11, 25, 17, 0, 30))
    assert calls[-1].data["position"] == 0


async def _summer(hass: HomeAssistant, freezer, settings: dict) -> list:
    await setup_hass(hass)
    freezer.move_to(local(2026, 6, 24, 4, 0))
    set_cover(hass, position=0)
    hass.states.async_set("sensor.forecast", "31")
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "time_up_early_workday": "07:00:00",
            "time_down_early_workday": "21:30:00",
            "forecast_sensor": "sensor.forecast",
            "pos_shading": 30,
            **settings,
        },
    )
    return calls


async def test_hot_day_morning_to_shading(hass: HomeAssistant, freezer) -> None:
    calls = await _summer(hass, freezer, {"hot_day": True})
    # At night nothing happens (the flat cools down)
    await tick(hass, freezer, local(2026, 6, 24, 5, 0))
    assert calls == []
    await tick(hass, freezer, local(2026, 6, 24, 7, 0, 1))
    assert calls[-1].data["position"] == 30
    assert state(hass, eid(hass, "sensor", "last_reason")) == "hot_day"
    assert state(hass, eid(hass, "binary_sensor", "hot_day")) == "on"
    set_cover(hass, position=30, context=calls[-1].context)
    await hass.async_block_till_done()
    # The sun has passed the south window: open
    for hour in range(8, 20):
        await tick(hass, freezer, local(2026, 6, 24, hour, 0))
    assert calls[-1].data["position"] == 100
    assert state(hass, eid(hass, "binary_sensor", "hot_day")) == "off"


async def test_hot_day_off_by_default(hass: HomeAssistant, freezer) -> None:
    calls = await _summer(hass, freezer, {})
    await tick(hass, freezer, local(2026, 6, 24, 7, 0, 1))
    assert calls[-1].data["position"] == 100


async def test_hot_day_not_when_cool(hass: HomeAssistant, freezer) -> None:
    calls = await _summer(hass, freezer, {"hot_day": True, "hot_day_temp": 32})
    await tick(hass, freezer, local(2026, 6, 24, 7, 0, 1))
    assert calls[-1].data["position"] == 100


async def test_morning_time_from_entity(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 22, 0))
    set_cover(hass, position=0)
    alarm = "sensor.phone_next_alarm"
    hass.states.async_set(alarm, "2026-11-26T05:45:00+00:00", {"device_class": "timestamp"})
    calls = mock_cover_services(hass)
    await setup_entry(hass, {"up_mode": "entity", "up_time_entity": alarm, "down_mode": "time"})
    assert state(hass, eid(hass, "sensor", "next_up")) == "2026-11-26T05:45:00+00:00"
    # A new alarm time is taken at once
    hass.states.async_set(alarm, "2026-11-26T06:00:00+00:00", {"device_class": "timestamp"})
    await hass.async_block_till_done()
    assert state(hass, eid(hass, "sensor", "next_up")) == "2026-11-26T06:00:00+00:00"
    await tick(hass, freezer, local(2026, 11, 26, 6, 59, 0))
    await tick(hass, freezer, local(2026, 11, 26, 7, 0, 1))
    assert calls[-1].data["position"] == 100
    # The phone shows the alarm of tomorrow: today is done
    hass.states.async_set(alarm, "2026-11-27T06:00:00+00:00", {"device_class": "timestamp"})
    await hass.async_block_till_done()
    assert state(hass, eid(hass, "sensor", "next_up")) == "2026-11-27T06:00:00+00:00"
    assert state(hass, eid(hass, "binary_sensor", "is_day")) == "on"
    await tick(hass, freezer, local(2026, 11, 26, 8, 30, 1))
    assert len(calls) == 1


async def test_diagnostic_sensors(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 6, 24, 13, 0))
    set_cover(hass, position=100)
    hass.states.async_set("sensor.forecast", "31")
    hass.states.async_set("weather.home", "sunny")
    mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            "forecast_sensor": "sensor.forecast",
            "weather_entity": "weather.home",
            "hot_day_temp": 30,
        },
    )
    assert 150 < float(state(hass, global_eid(hass, "sensor", "sun_azimuth"))) < 200
    assert 50 < float(state(hass, global_eid(hass, "sensor", "sun_elevation"))) < 65
    assert state(hass, global_eid(hass, "sensor", "forecast_max_temperature")) == "31.0"
    assert state(hass, global_eid(hass, "binary_sensor", "sunny")) == "on"
    assert state(hass, global_eid(hass, "binary_sensor", "hot")) == "on"
    hass.states.async_set("weather.home", "rainy")
    await tick(hass, freezer, local(2026, 6, 24, 13, 1, 1))
    assert state(hass, global_eid(hass, "binary_sensor", "sunny")) == "off"
    # Hot follows the forecast of the day, not the weather now
    assert state(hass, global_eid(hass, "binary_sensor", "hot")) == "on"
    hass.states.async_set("sensor.forecast", "28")
    await tick(hass, freezer, local(2026, 6, 24, 13, 12))
    assert state(hass, global_eid(hass, "binary_sensor", "hot")) == "off"


async def test_guest_blocks_morning(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 22, 0))
    set_cover(hass, position=0)
    set_cover(hass, COVER2, position=0)
    hass.states.async_set("device_tracker.guest_phone", "home")
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {**TIME_MODE, "time_up_early_workday": "07:00:00"},
        [
            cover_subentry(settings={"guest_entities": ["device_tracker.guest_phone"]}),
            cover_subentry(COVER2, sub_id="sub_cover2"),
        ],
    )
    assert state(hass, eid(hass, "binary_sensor", "guest")) == "on"
    await tick(hass, freezer, local(2026, 11, 26, 6, 59))
    await tick(hass, freezer, local(2026, 11, 26, 7, 0, 1))
    # Only the cover without a guest opens
    assert [c.data[ATTR_ENTITY_ID] for c in calls] == [COVER2]
    # The guest leaves: the morning opening is caught up
    hass.states.async_set("device_tracker.guest_phone", "not_home")
    await hass.async_block_till_done()
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 100}


async def test_guest_switch(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 22, 0))
    set_cover(hass, position=0)
    calls = mock_cover_services(hass)
    await setup_entry(hass, {**TIME_MODE, "time_up_early_workday": "07:00:00"})
    await turn_on(hass, eid(hass, "switch", "cover_guest"))
    await tick(hass, freezer, local(2026, 11, 26, 6, 59))
    await tick(hass, freezer, local(2026, 11, 26, 7, 0, 1))
    assert calls == []
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: eid(hass, "switch", "cover_guest")}, blocking=True
    )
    await hass.async_block_till_done()
    assert calls[-1].data["position"] == 100


async def test_guest_no_morning_and_evening(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    calls = mock_cover_services(hass)
    await setup_entry(hass, {**TIME_MODE, "guest_mode": "no_morning_evening"})
    await turn_on(hass, eid(hass, "switch", "cover_guest"))
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []


async def test_guest_only_manual(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    hass.states.async_set("binary_sensor.rain", "off")
    hass.states.async_set("sensor.wind", "5")
    calls = mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "guest_mode": "manual_only",
            "wind_sensor": "sensor.wind",
            "wind_protection": True,
            "pos_wind": 100,
        },
    )
    await turn_on(hass, eid(hass, "switch", "cover_guest"))
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    assert state(hass, eid(hass, "sensor", "blocked_by")) == "guest"


async def test_entities_on_the_cover_device(hass: HomeAssistant, freezer) -> None:
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    other = MockConfigEntry(domain="shelly")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("shelly", "abc")}, name="Rollladen WZ"
    )
    er.async_get(hass).async_get_or_create(
        "cover", "shelly", "abc-cover", suggested_object_id="living_room", device_id=device.id
    )
    set_cover(hass, position=100)
    mock_cover_services(hass)
    await setup_entry(
        hass, TIME_MODE, [cover_subentry(), cover_subentry(COVER2, sub_id="sub_cover2")]
    )
    registry = er.async_get(hass)
    entry = registry.async_get(eid(hass, "sensor", "next_up"))
    assert entry.device_id == device.id
    # No own device for this cover, the other one (without device) keeps its ASC device
    devices = dr.async_get(hass)
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    assert devices.async_get_device_by_identifier((DOMAIN, "sub_cover"), entry_id) is None
    assert devices.async_get_device_by_identifier((DOMAIN, "sub_cover2"), entry_id) is not None

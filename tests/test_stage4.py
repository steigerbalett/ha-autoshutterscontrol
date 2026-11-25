"""Integration tests of stage 4: rain, wind, frost, force, pause, party, advent, trigger,
wiggle, hardware lock, extra conditions and actions."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

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
RAIN = "binary_sensor.rain"
WIND = "sensor.wind"
TEMP = "sensor.outdoor"
WINDOW = "binary_sensor.window"
FORCE = "input_boolean.force_close"
PAUSE = "input_boolean.pause_cover"
TRIGGER = "input_select.mode"
LOCK = "lock.actuator"


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


def follow(hass: HomeAssistant, calls: list, position: int) -> None:
    set_cover(hass, position=position, context=calls[-1].context)


async def switch(hass: HomeAssistant, key: str, on: bool = True) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {ATTR_ENTITY_ID: global_eid(hass, "switch", key)},
        blocking=True,
    )
    await hass.async_block_till_done()


async def press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()


async def put(hass: HomeAssistant, entity_id: str, value: str) -> None:
    hass.states.async_set(entity_id, value)
    await hass.async_block_till_done()


def reason(hass: HomeAssistant) -> str:
    return hass.states.get(eid(hass, "sensor", "last_reason")).state


@pytest.fixture
async def noon(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 25 November 2026, 12:00, cover open, dry, window closed."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    for entity_id, value in ((RAIN, "off"), (WIND, "5"), (TEMP, "10"), (WINDOW, "off")):
        hass.states.async_set(entity_id, value)
    return mock_cover_services(hass)


async def test_water_protection_with_open_window(hass: HomeAssistant, noon) -> None:
    calls = noon
    events = async_capture_events(hass, "autoshutterscontrol_rain_window")
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain_window": 10},
        [cover_subentry(settings={"window_open_sensor": WINDOW, "ventilate_enabled": False})],
    )
    await put(hass, RAIN, "on")
    assert calls == []  # window closed: nothing to do
    await put(hass, WINDOW, "on")
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 10}
    assert reason(hass) == "rain_window"
    assert len(events) == 1
    assert events[0].data["window"] == "open"
    assert hass.states.get(eid(hass, "binary_sensor", "protection_rain_window")).state == "on"
    follow(hass, calls, 10)
    # Window closed: back to the target
    await put(hass, WINDOW, "off")
    assert calls[-1].data["position"] == 100
    assert len(events) == 1


async def test_water_protection_with_lockout(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain_window": 0, "pos_ventilate": 40},
        [cover_subentry(settings={"window_open_sensor": WINDOW, "lockout": "soft"})],
    )
    await put(hass, WINDOW, "on")
    assert calls == []
    await put(hass, RAIN, "on")
    assert calls[-1].data["position"] == 40
    assert reason(hass) == "rain_window"


async def test_rain_protection_with_delay(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain": 30},
        [cover_subentry(settings={"rain_protection": True, "rain_delay_end": 5})],
    )
    await put(hass, RAIN, "on")
    assert calls[-1].data["position"] == 30
    assert reason(hass) == "rain"
    assert hass.states.get(global_eid(hass, "binary_sensor", "global_rain")).state == "on"
    follow(hass, calls, 30)
    await put(hass, RAIN, "off")
    assert len(calls) == 1
    await tick(hass, freezer, local(2026, 11, 25, 12, 3, 1))
    assert len(calls) == 1
    await tick(hass, freezer, local(2026, 11, 25, 12, 5, 1))
    assert calls[-1].data["position"] == 100


async def test_rain_protection_beats_manual(hass: HomeAssistant, noon) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain": 30},
        [cover_subentry(settings={"rain_protection": True})],
    )
    set_cover(hass, position=60)
    await hass.async_block_till_done()
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "on"
    await put(hass, RAIN, "on")
    assert calls[-1].data["position"] == 30


async def test_wind_hysteresis(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "wind_sensor": WIND, "pos_wind": 100},
        [cover_subentry(settings={"wind_protection": True, "wind_delay_end": 0})],
    )
    set_cover(hass, position=50, context=None)
    await hass.services.async_call(
        DOMAIN, "drive", {ATTR_ENTITY_ID: COVER, "position": 20}, blocking=True
    )
    follow(hass, calls, 20)
    await put(hass, WIND, "55")
    assert calls[-1].data["position"] == 100
    assert reason(hass) == "wind"
    follow(hass, calls, 100)
    count = len(calls)
    await put(hass, WIND, "35")  # above 50 - 20: still wind
    assert hass.states.get(eid(hass, "binary_sensor", "protection_wind")).state == "on"
    await put(hass, WIND, "25")
    assert hass.states.get(eid(hass, "binary_sensor", "protection_wind")).state == "off"
    assert len(calls) >= count


async def test_frost_hard_blocks_evening(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, {**TIME_MODE, "frost_mode": "hard", "outdoor_temperature_sensor": TEMP})
    await put(hass, TEMP, "-3")
    assert hass.states.get(eid(hass, "binary_sensor", "protection_frost")).state == "on"
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    target = hass.states.get(eid(hass, "sensor", "target"))
    assert target.attributes["blocked_by"] == "frost"


async def test_frost_soft_position(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass,
        {
            **TIME_MODE,
            "frost_mode": "soft",
            "pos_frost": 15,
            "outdoor_temperature_sensor": TEMP,
        },
    )
    await put(hass, TEMP, "-3")
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls[-1].data["position"] == 15
    assert reason(hass) == "night_close"


async def test_force_close_and_return(hass: HomeAssistant, noon) -> None:
    calls = noon
    hass.states.async_set(FORCE, "off")
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"force_close": FORCE})])
    set_cover(hass, position=70)
    await hass.async_block_till_done()
    await put(hass, FORCE, "on")
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "force"
    assert hass.states.get(eid(hass, "binary_sensor", "force")).state == "on"
    follow(hass, calls, 0)
    await put(hass, FORCE, "off")
    assert calls[-1].data["position"] == 100
    follow(hass, calls, 100)
    # Pause and Automatic off do not stop a force function
    await switch(hass, "global_pause")
    await put(hass, FORCE, "on")
    assert calls[-1].data["position"] == 0


async def test_pause_entity(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(PAUSE, "on")
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"pause_entity": PAUSE})])
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    await put(hass, PAUSE, "off")
    assert calls[-1].data["position"] == 0


async def test_party_defers_until_off(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await switch(hass, "global_party")
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    await switch(hass, "global_party", False)
    assert calls[-1].data["position"] == 0


async def test_party_not_for_this_cover(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"party": False})])
    await switch(hass, "global_party")
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls[-1].data["position"] == 0


async def test_advent_defers_closing(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    freezer.move_to(local(2026, 12, 2, 12, 0))
    await setup_entry(hass, TIME_MODE)
    await switch(hass, "global_advent")
    await tick(hass, freezer, local(2026, 12, 2, 16, 0, 1))
    assert calls == []
    await press(hass, global_eid(hass, "button", "global_release_deferred"))
    assert calls[-1].data["position"] == 0


async def test_advent_not_before_first_sunday(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, TIME_MODE)
    await switch(hass, "global_advent")
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls[-1].data["position"] == 0


async def test_external_trigger(hass: HomeAssistant, noon) -> None:
    calls = noon
    hass.states.async_set(TRIGGER, "normal")
    await setup_entry(
        hass,
        TIME_MODE,
        [
            cover_subentry(
                settings={
                    "trigger_entity": TRIGGER,
                    "trigger_value": "kino",
                    "trigger_position": 0,
                    "trigger_value2": "lesen",
                    "trigger_position2": 60,
                }
            )
        ],
    )
    await put(hass, TRIGGER, "Kino")
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "trigger"
    follow(hass, calls, 0)
    await put(hass, TRIGGER, "lesen")
    assert calls[-1].data["position"] == 60
    follow(hass, calls, 60)
    await put(hass, TRIGGER, "normal")
    assert calls[-1].data["position"] == 100


async def test_wiggle(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    set_cover(hass, position=80)
    await setup_entry(hass, {**TIME_MODE, "wiggle_wait": 3})
    await press(hass, eid(hass, "button", "wiggle"))
    assert calls[-1].data["position"] == 75
    follow(hass, calls, 75)
    await tick(hass, freezer, local(2026, 11, 25, 12, 0, 4))
    assert calls[-1].data["position"] == 80
    follow(hass, calls, 80)
    assert hass.states.get(eid(hass, "binary_sensor", "manual_override")).state == "off"
    await hass.services.async_call(DOMAIN, "wiggle", {}, blocking=True)
    assert calls[-1].data["position"] == 75


async def test_hardware_lock(hass: HomeAssistant, noon) -> None:
    lock_on = async_mock_service(hass, "lock", "lock")
    lock_off = async_mock_service(hass, "lock", "unlock")
    await setup_entry(
        hass,
        TIME_MODE,
        [
            cover_subentry(
                settings={"window_open_sensor": WINDOW, "lockout": "hard", "lockout_entity": LOCK}
            )
        ],
    )
    await put(hass, WINDOW, "on")
    assert [c.data[ATTR_ENTITY_ID] for c in lock_on] == [LOCK]
    await put(hass, WINDOW, "off")
    assert [c.data[ATTR_ENTITY_ID] for c in lock_off] == [LOCK]


async def test_hardware_lock_switch_off(hass: HomeAssistant, noon) -> None:
    lock_on = async_mock_service(hass, "lock", "lock")
    await setup_entry(
        hass,
        TIME_MODE,
        [
            cover_subentry(
                settings={"window_open_sensor": WINDOW, "lockout": "hard", "lockout_entity": LOCK}
            )
        ],
    )
    entity = global_eid(hass, "switch", "global_hardware_lock")
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: entity}, blocking=True)
    await hass.async_block_till_done()
    await put(hass, WINDOW, "on")
    assert [c.data[ATTR_ENTITY_ID] for c in lock_on if c.data[ATTR_ENTITY_ID] == LOCK] == []


async def test_hard_lockout_waits_for_rain(hass: HomeAssistant, noon) -> None:
    calls = noon
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain": 0},
        [
            cover_subentry(
                settings={
                    "window_open_sensor": WINDOW,
                    "lockout": "hard",
                    "rain_protection": True,
                    "rain_window": False,
                    "ventilate_enabled": False,
                }
            )
        ],
    )
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    assert calls == []
    await put(hass, WINDOW, "off")
    assert calls[-1].data["position"] == 0


async def test_extra_condition_blocks_closing(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set("input_boolean.allow", "off")
    condition = [{"condition": "state", "entity_id": "input_boolean.allow", "state": "on"}]
    await setup_entry(hass, {**TIME_MODE, "condition_close": condition})
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    # The drive is skipped; applying the target catches up
    hass.states.async_set("input_boolean.allow", "on")
    await press(hass, eid(hass, "button", "apply_target"))
    assert calls[-1].data["position"] == 0


async def test_extra_actions(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    seen = async_mock_service(hass, "test", "action")
    action = [
        {
            "action": "test.action",
            "data": {
                "cover": "{{ cover }}",
                "position": "{{ position }}",
                "reason": "{{ reason }}",
            },
        }
    ]
    manual = [{"action": "test.action", "data": {"manual": "{{ position }}"}}]
    await setup_entry(hass, {**TIME_MODE, "action_drive": action, "action_manual": manual})
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls[-1].data["position"] == 0
    assert seen[-1].data == {"cover": COVER, "position": 0, "reason": "night_close"}
    follow(hass, calls, 0)
    await tick(hass, freezer, local(2026, 11, 25, 16, 5))
    set_cover(hass, position=40)
    await hass.async_block_till_done()
    assert seen[-1].data == {"manual": 40}


async def test_invalid_condition_never_drives(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, {**TIME_MODE, "condition_all": [{"condition": "nonsense"}]})
    await tick(hass, freezer, local(2026, 11, 25, 16, 0, 1))
    assert calls == []
    # Protections are not affected
    _ = timedelta


async def test_back_after_trigger_ignores_direction_rules(hass: HomeAssistant, noon) -> None:
    calls = noon
    hass.states.async_set(TRIGGER, "normal")
    set_cover(hass, position=80)
    await setup_entry(
        hass,
        {**TIME_MODE, "pos_open": 80, "open_never_down": True},
        [
            cover_subentry(
                settings={
                    "trigger_entity": TRIGGER,
                    "trigger_value": "hell",
                    "trigger_position": 100,
                }
            )
        ],
    )
    await put(hass, TRIGGER, "hell")
    assert calls[-1].data["position"] == 100
    follow(hass, calls, 100)
    await put(hass, TRIGGER, "normal")
    assert calls[-1].data["position"] == 80


# --- water protection: back after the rain ---------------------------------

RAIN_RETURN_COVER = {"window_open_sensor": WINDOW, "ventilate_enabled": False}


async def _rain(hass: HomeAssistant, calls: list, settings: dict | None = None) -> None:
    await setup_entry(
        hass,
        {**TIME_MODE, "rain_sensor": RAIN, "pos_rain_window": 0, **(settings or {})},
        [cover_subentry(settings=RAIN_RETURN_COVER)],
    )


async def _dry(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when) -> None:
    await put(hass, RAIN, "off")
    # Default wait after the rain: 15 minutes
    await tick(hass, freezer, when + timedelta(minutes=16))


async def test_back_to_manual_position(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await _rain(hass, calls)
    set_cover(hass, position=40)  # by hand
    await hass.async_block_till_done()
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    assert calls[-1].data["position"] == 0
    follow(hass, calls, 0)
    await _dry(hass, freezer, local(2026, 11, 25, 12, 0))
    assert calls[-1].data["position"] == 40
    assert reason(hass) == "rain_return"


async def test_back_when_window_closed(hass: HomeAssistant, noon) -> None:
    calls = noon
    await _rain(hass, calls)
    set_cover(hass, position=60)
    await hass.async_block_till_done()
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    follow(hass, calls, 0)
    await put(hass, WINDOW, "off")
    assert calls[-1].data["position"] == 60
    assert reason(hass) == "rain_return"


async def test_target_when_evening_came(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await _rain(
        hass, calls, {"time_down_early_workday": "13:00", "time_down_late_workday": "13:00"}
    )
    set_cover(hass, position=40)
    await hass.async_block_till_done()
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    follow(hass, calls, 0)
    await tick(hass, freezer, local(2026, 11, 25, 13, 30))
    count = len(calls)
    # Dry in the evening: the evening target (closed) applies, not the old 40 %
    await _dry(hass, freezer, local(2026, 11, 25, 13, 30))
    assert all(c.data.get("position") != 40 for c in calls[count:])
    assert reason(hass) != "rain_return"


async def test_manual_drive_during_rain_wins(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await _rain(hass, calls)
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    assert calls[-1].data["position"] == 0
    follow(hass, calls, 0)
    set_cover(hass, position=30, context=Context(user_id="user"))  # by hand while it rains
    await hass.async_block_till_done()
    count = len(calls)
    await _dry(hass, freezer, local(2026, 11, 25, 12, 0))
    # Not back to the position before the rain: the manual drive counts as something new,
    # so the current target applies (the override does not block opening by default)
    assert [c.data.get("position") for c in calls[count:]] == [100]
    assert reason(hass) == "day_open"


async def test_setting_target(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await _rain(hass, calls, {"rain_window_return": "target"})
    set_cover(hass, position=40)
    await hass.async_block_till_done()
    await put(hass, WINDOW, "on")
    await put(hass, RAIN, "on")
    follow(hass, calls, 0)
    await _dry(hass, freezer, local(2026, 11, 25, 12, 0))
    assert calls[-1].data["position"] == 100
    assert reason(hass) == "day_open"

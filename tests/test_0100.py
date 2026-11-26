"""0.10.0: window contact without state, command gap, known positions, group covers,
emergency input, window presets, close by entity, night stage, golden hour, summer,
advent position, awnings."""

from __future__ import annotations

from datetime import date, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest

from custom_components.autoshutterscontrol.const import DOMAIN
from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_ADVENT,
    BLOCK_SUMMER,
    REASON_ADVENT,
    Situation,
    Wish,
    awning_wishes,
    decide,
    emergency_wish,
)
from custom_components.autoshutterscontrol.engine.resolve import SOURCE_PRESET, resolve
from custom_components.autoshutterscontrol.engine.settings import KIND_CLOSE
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator

from .helpers import (
    COVER,
    COVER2,
    TZ,
    cover_subentry,
    local,
    mock_cover_services,
    profile_subentry,
    set_cover,
    setup_entry,
    setup_hass,
)
from .test_090 import controller, eid, global_eid, reason, tick

TIME_MODE = {"up_mode": "time", "down_mode": "time"}
WINDOW = "binary_sensor.window"
SMOKE = "binary_sensor.smoke"
LIGHT = "light.living"


@pytest.fixture
async def noon(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Wednesday 17 June 2026, 12:00, cover open."""
    await setup_hass(hass)
    freezer.move_to(local(2026, 6, 17, 12, 0))
    set_cover(hass, position=100)
    return mock_cover_services(hass)


# --- 5: window contact without a state ---------------------------------------------


async def test_unavailable_contact_holds_lockout_and_reports(
    hass: HomeAssistant, noon, freezer
) -> None:
    calls = noon
    hass.states.async_set(WINDOW, "unavailable")
    await setup_entry(
        hass,
        TIME_MODE,
        [cover_subentry(settings={"window_open_sensor": WINDOW, "lockout": "soft"})],
    )
    await tick(hass, freezer, local(2026, 6, 17, 12, 3))
    issue_id = "contact_sub_cover"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 5))
    assert calls == []
    assert controller(hass).last_decision.blocked_by == "lockout"
    # The contact is back and closed: the deferred drive follows, the issue is gone
    hass.states.async_set(WINDOW, "off")
    await hass.async_block_till_done()
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_unavailable_contact_without_lockout_drives(
    hass: HomeAssistant, noon, freezer
) -> None:
    calls = noon
    hass.states.async_set(WINDOW, "unavailable")
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"window_open_sensor": WINDOW})])
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 5))
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}


# --- 1: minimum gap between commands ------------------------------------------------


async def test_command_gap(hass: HomeAssistant, noon, monkeypatch) -> None:
    calls = noon
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("custom_components.autoshutterscontrol.runtime.asyncio.sleep", fake_sleep)
    set_cover(hass, COVER2, position=100)
    entry = await setup_entry(
        hass,
        {**TIME_MODE, "command_gap": 0.2},
        [cover_subentry(), cover_subentry(COVER2, sub_id="sub_cover2")],
    )
    manager = entry.runtime_data
    for c in manager.controllers.values():
        c.drive_to(30, respect_rules=False)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == 2
    assert {c.data[ATTR_ENTITY_ID] for c in calls} == {COVER, COVER2}
    assert calls[1].context.id != calls[0].context.id
    gaps = [w for w in waits if w > 0]
    assert len(gaps) == 1 and abs(gaps[0] - 0.2) < 0.01  # the second one waited for the gap


# --- 2: manual drive to a known position --------------------------------------------


async def test_manual_to_known_position_keeps_automatic(hass: HomeAssistant, noon) -> None:
    await setup_entry(hass, {**TIME_MODE, "manual_known": True})
    ctrl = controller(hass)
    set_cover(hass, position=50, state="closing", context=Context(user_id="u"))
    await hass.async_block_till_done()
    set_cover(hass, position=0, context=Context(user_id="u"))
    await hass.async_block_till_done()
    assert not ctrl.override_active
    assert ctrl.state["last"]["reason"] == "manual"


async def test_manual_to_other_position_overrides(hass: HomeAssistant, noon) -> None:
    await setup_entry(hass, {**TIME_MODE, "manual_known": True})
    set_cover(hass, position=55, context=Context(user_id="u"))
    await hass.async_block_till_done()
    assert controller(hass).override_active


# --- 3: group covers ------------------------------------------------------------------


async def test_group_covers(hass: HomeAssistant, noon) -> None:
    calls = noon
    set_cover(hass, COVER2, position=50)
    hass.states.async_set(WINDOW, "on")
    await setup_entry(
        hass,
        TIME_MODE,
        [
            profile_subentry("Süd", {}),
            cover_subentry(
                settings={"window_open_sensor": WINDOW, "lockout": "soft"},
                profile="sub_profile",
            ),
            cover_subentry(COVER2, sub_id="sub_cover2"),
        ],
    )
    everything = global_eid(hass, "cover", "group_all")
    south = global_eid(hass, "cover", "group_sub_profile")
    state = hass.states.get(everything)
    assert state.attributes["current_position"] == 75
    assert sorted(state.attributes[ATTR_ENTITY_ID]) == [COVER2, COVER]
    assert hass.states.get(south).attributes[ATTR_ENTITY_ID] == [COVER]
    # (the cover services are mocked in the tests: call the group entity directly)
    group = hass.data["entity_components"]["cover"].get_entity(everything)
    await group.async_set_cover_position(position=20)
    await hass.async_block_till_done()
    # The door of the living room is open: only the kitchen moves
    assert [c.data for c in calls] == [{ATTR_ENTITY_ID: COVER2, "position": 20}]


# --- 4: emergency input -----------------------------------------------------------------


async def test_emergency_latched_until_reset(hass: HomeAssistant, noon) -> None:
    calls = noon
    set_cover(hass, position=0)
    hass.states.async_set(SMOKE, "off")
    hass.states.async_set(WINDOW, "on")
    await setup_entry(
        hass,
        {**TIME_MODE, "emergency_entities": [SMOKE], "pos_emergency": 100},
        [cover_subentry(settings={"window_open_sensor": WINDOW, "lockout": "hard"})],
    )
    # Automatic off does not stop the emergency
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: eid(hass, "switch", "cover_automatic")},
        blocking=True,
    )
    hass.states.async_set(SMOKE, "on")
    await hass.async_block_till_done()
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 100}
    assert reason(hass) == "emergency"
    sensor = global_eid(hass, "binary_sensor", "emergency")
    assert hass.states.get(sensor).state == "on"
    hass.states.async_set(SMOKE, "off")
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "on"
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: global_eid(hass, "button", "global_clear_emergency")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == "off"


def test_emergency_wish() -> None:
    cfg = {"pos_emergency": 100}
    wish = emergency_wish(cfg, True)
    assert wish.priority == 0 and wish.bypass_rules and wish.position == 100
    assert emergency_wish(cfg, True, awning=True).position == 0
    assert emergency_wish(cfg, False) is None


# --- 6: window presets -------------------------------------------------------------------


def test_window_preset_terrace_door() -> None:
    cfg = resolve({"pos_open": 90}, None, {"window_preset": "terrace_door"})
    assert cfg["lockout"] == "soft"
    assert cfg["pos_ventilate"] == 90
    assert cfg.source("lockout") == SOURCE_PRESET
    # A value set on the cover wins over the preset
    cfg = resolve({}, None, {"window_preset": "terrace_door", "lockout": "hard"})
    assert cfg["lockout"] == "hard"
    # A preset of a profile does not win over a value of the cover
    cfg = resolve({}, {"window_preset": "protection_only"}, {"ventilate_enabled": True})
    assert cfg["ventilate_enabled"] is True
    assert cfg["lockout"] == "soft"


# --- 7: close by entity, night stage ---------------------------------------------------------


async def test_close_by_entity(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    hass.states.async_set(LIGHT, "off")
    await setup_entry(hass, {**TIME_MODE, "close_entity": LIGHT, "close_entity_from": "15:00:00"})
    hass.states.async_set(LIGHT, "on")
    await hass.async_block_till_done()
    assert calls == []  # before 15:00
    hass.states.async_set(LIGHT, "off")
    await tick(hass, freezer, local(2026, 6, 17, 15, 10))
    hass.states.async_set(LIGHT, "on")
    await hass.async_block_till_done()
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}
    assert not controller(hass).is_day()


async def test_night_stage(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(
        hass, {**TIME_MODE, "pos_closed": 30, "pos_night": 0, "night_time": "22:00:00"}
    )
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 5))
    assert calls[-1].data["position"] == 30
    set_cover(hass, position=30, context=calls[-1].context)
    await tick(hass, freezer, local(2026, 6, 17, 22, 1))
    assert calls[-1].data["position"] == 0
    assert reason(hass) == "night"


# --- 8: golden hour ---------------------------------------------------------------------------


def test_golden_hour() -> None:
    sun = SunCalculator(Location(51.35, 8.57, 450, TZ))
    day = date(2026, 6, 17)
    golden = sun.morning(day, "golden")
    assert sun.morning(day, "real") < golden
    assert 5.0 < sun.elevation(golden) < 6.5
    assert sun.evening(day, "golden") < sun.evening(day, "real")


# --- 9: summer, advent position ------------------------------------------------------------------


def _cfg(**values):
    base = {
        "tolerance": 2,
        "override_blocks": (),
        "open_never_down": True,
        "close_never_up": True,
        "pos_advent": None,
        "pos_frost": None,
        "ventilate_only_up": True,
        "shading_only_down": True,
        "shading_end_open": True,
        "quiet_window": True,
    }
    return {**base, **values}


def test_summer_blocks_evening_close_only() -> None:
    situation = Situation(trigger="schedule_down", current_position=100, summer=True)
    close = Wish(14, "schedule", KIND_CLOSE, 0, "night_close")
    assert decide(_cfg(), situation, [close]).blocked_by == BLOCK_SUMMER
    sleep = Wish(11, "residents", KIND_CLOSE, 0, "sleep")
    assert decide(_cfg(), situation, [sleep]).drive


def test_advent_position() -> None:
    situation = Situation(trigger="schedule_down", current_position=100, advent=True)
    close = Wish(14, "schedule", KIND_CLOSE, 0, "night_close")
    assert decide(_cfg(), situation, [close]).blocked_by == BLOCK_ADVENT
    decision = decide(_cfg(pos_advent=40), situation, [close])
    assert decision.drive and decision.position == 40 and decision.reason == REASON_ADVENT


async def test_summer_no_close(hass: HomeAssistant, noon, freezer) -> None:
    calls = noon
    await setup_entry(hass, {**TIME_MODE, "summer_no_close": True})
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 5))
    assert calls == []
    assert controller(hass).last_decision.blocked_by == BLOCK_SUMMER


# --- 10: awnings ---------------------------------------------------------------------------------


def test_awning_wishes() -> None:
    cfg = {"pos_awning": 80, "pos_emergency": 100}
    wishes = awning_wishes(cfg, is_day=True, shaded=True)
    best = min(wishes, key=lambda w: w.priority)
    assert best.position == 80 and best.reason == "awning_out"
    best = min(awning_wishes(cfg, is_day=True, shaded=True, wind=True), key=lambda w: w.priority)
    assert best.position == 0 and best.reason == "wind"
    best = min(awning_wishes(cfg, is_day=False, shaded=True), key=lambda w: w.priority)
    assert best.position == 0 and best.reason == "awning_in"


async def test_awning_retracts_at_night_and_is_no_group_member(
    hass: HomeAssistant, noon, freezer
) -> None:
    calls = noon
    set_cover(hass, position=60)
    await setup_entry(hass, TIME_MODE, [cover_subentry(settings={"cover_type": "awning"})])
    assert hass.states.get(global_eid(hass, "cover", "group_all")).state == "unavailable"
    await tick(hass, freezer, local(2026, 6, 17, 16, 0, 5))
    assert calls[-1].data == {ATTR_ENTITY_ID: COVER, "position": 0}
    assert reason(hass) == "awning_in"
    _ = timedelta

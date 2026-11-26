"""Engine tests of 0.9.0: horizon, depth of the sun, glare, lock, temperature limits,
wind only open or closed, holiday shift."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.autoshutterscontrol.engine import horizon
from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_LOCK,
    REASON_GLARE,
    REASON_LOCK,
    REASON_SHADING,
    REASON_TEMP_HIGH,
    REASON_WIND,
    TRIGGER_APPLY_TARGET,
    TRIGGER_SHADING,
    Situation,
    build_wishes,
    decide,
    shading_wish,
    wind_position,
)
from custom_components.autoshutterscontrol.engine.checks import check
from custom_components.autoshutterscontrol.engine.resolve import resolve
from custom_components.autoshutterscontrol.engine.schedule import day_schedule
from custom_components.autoshutterscontrol.engine.settings import BY_KEY, to_storage
from custom_components.autoshutterscontrol.engine.shading import (
    Configured,
    Inputs,
    conditions,
    depth_position,
)
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator

TZ = ZoneInfo("Europe/Berlin")
SUN = SunCalculator(Location(51.35, 8.57, 450, TZ))


def cfg(**values):
    """Settings on the cover level (also the ones only a cover has)."""
    return resolve({}, None, {k: to_storage(BY_KEY[k], v) for k, v in values.items()})


# --- horizon ----------------------------------------------------------------------


def test_horizon_parse_and_format() -> None:
    points = horizon.parse("230:25, 200:18;250:10")
    assert points == [(200.0, 18.0), (230.0, 25.0), (250.0, 10.0)]
    assert horizon.fmt(points) == "200:18, 230:25, 250:10"
    assert horizon.parse("") == []
    with pytest.raises(ValueError):
        horizon.parse("west:20")
    with pytest.raises(ValueError):
        horizon.parse("400:20")
    assert not horizon.valid("200")
    assert horizon.safe_parse("x") == []


def test_horizon_interpolation() -> None:
    points = [(200.0, 10.0), (220.0, 30.0)]
    assert horizon.at(points, 210) == pytest.approx(20)
    assert horizon.at(points, 190) == 10  # held 15 degrees beyond
    assert horizon.at(points, 234) == 30
    assert horizon.at(points, 180) is None
    assert horizon.at(points, 240) is None
    assert horizon.hidden(points, 210, 20)
    assert not horizon.hidden(points, 210, 20.5)
    assert not horizon.hidden([], 210, 0)


def test_horizon_add_replaces_close_point() -> None:
    points = horizon.add([(200.0, 10.0), (230.0, 20.0)], 201.6, 14.23)
    assert points == [(202.0, 14.3), (230.0, 20.0)]
    points = horizon.add(points, 260.2, 5.0)
    assert len(points) == 3


def test_horizon_hides_the_sun_for_shading() -> None:
    c = cfg(shading_azimuth_start=180, shading_azimuth_end=300, shading_elevation_min=10)
    inputs = Inputs(azimuth=240, elevation=20, hidden=True)
    assert conditions(c, inputs, Configured(), False)["elevation"] is False
    inputs = Inputs(azimuth=240, elevation=20)
    assert conditions(c, inputs, Configured(), False)["elevation"] is True


def test_horizon_check() -> None:
    assert ("horizon_invalid", {"value": "x"}) in check(cfg(horizon="x"))
    assert not any(code == "horizon_invalid" for code, _ in check(cfg(horizon="200:10")))


# --- depth of the sun ---------------------------------------------------------------


def test_depth_position() -> None:
    c = cfg(window_sill=90, window_height=130, sun_depth=2.0)
    # Sun straight in front of the window
    assert depth_position(c, 25, 180, 180) == 0
    assert depth_position(c, 40, 180, 180) == 50
    assert depth_position(c, 55, 180, 180) == 100
    # Sun from the side: the profile angle is steeper, more can stay open
    assert depth_position(c, 30, 240, 180) > depth_position(c, 30, 180, 180)
    # Sun behind the facade or below the horizon
    assert depth_position(c, 30, 0, 180) is None
    assert depth_position(c, -1, 180, 180) is None
    assert depth_position(cfg(), 40, 180, 180) is None


def test_depth_check() -> None:
    assert ("depth_incomplete", {}) in check(cfg(window_sill=90))
    assert not any(code == "depth_incomplete" for code, _ in check(cfg(sun_depth=2.0)))


def test_shading_wish_depth_and_glare() -> None:
    c = cfg(pos_shading=30, pos_glare=40)
    wish = shading_wish(c, True, depth=60)
    assert (wish.position, wish.reason) == (60, REASON_SHADING)
    # Never below the fixed position
    assert shading_wish(c, True, depth=10).position == 30
    # Glare alone, and the lower one wins
    assert (shading_wish(c, False, glare=True).position, REASON_GLARE) == (40, REASON_GLARE)
    wish = shading_wish(c, True, glare=True)
    assert (wish.position, wish.reason) == (30, REASON_SHADING)
    wish = shading_wish(cfg(pos_shading=50, pos_glare=40), True, glare=True)
    assert (wish.position, wish.reason) == (40, REASON_GLARE)


def test_shading_follows_the_sun_up() -> None:
    c = cfg(shading_only_down=True)
    wishes = build_wishes(c, trigger=TRIGGER_SHADING, is_day=True, shaded=True, depth=70)
    # The cover is where the last shading drive put it: up is allowed
    sit = Situation(trigger=TRIGGER_SHADING, current_position=50, shading_from=50)
    assert decide(c, sit, wishes).drive
    # Moved lower by hand: shading does not open it
    sit = Situation(trigger=TRIGGER_SHADING, current_position=20, shading_from=50)
    assert not decide(c, sit, wishes).drive


# --- lock, temperature limits, wind ------------------------------------------------


def test_lock_open_closed_hold() -> None:
    c = cfg()
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=False, lock="open")
    decision = decide(c, Situation(trigger=TRIGGER_APPLY_TARGET, current_position=0), wishes)
    assert (decision.position, decision.reason) == (100, REASON_LOCK)
    # Wind still wins over a lock
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=False, lock="open", wind=True)
    decision = decide(c, Situation(trigger=TRIGGER_APPLY_TARGET, current_position=50), wishes)
    assert decision.reason == REASON_WIND
    # Hold: the schedule does not drive, wind does
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=False)
    sit = Situation(trigger=TRIGGER_APPLY_TARGET, current_position=100, lock_hold=True)
    assert decide(c, sit, wishes).blocked_by == BLOCK_LOCK
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=False, wind=True)
    assert decide(c, sit, wishes).drive


def test_temperature_limit_wish() -> None:
    c = cfg()
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=True, temp_limit="high")
    decision = decide(c, Situation(trigger=TRIGGER_APPLY_TARGET, current_position=100), wishes)
    assert (decision.position, decision.reason) == (0, REASON_TEMP_HIGH)
    # An open window still ventilates
    wishes = build_wishes(
        c,
        trigger=TRIGGER_APPLY_TARGET,
        is_day=True,
        temp_limit="high",
        window=(50, "ventilate"),
    )
    decision = decide(c, Situation(trigger=TRIGGER_APPLY_TARGET, current_position=100), wishes)
    assert decision.position == 50


def test_temp_limits_check() -> None:
    found = dict(check(cfg(close_above_temp=10, close_below_temp=12)))
    assert "temp_limits_order" in found
    assert "missing_temperature" in found


@pytest.mark.parametrize(
    ("mode", "wanted", "expected"),
    [
        ("position", 100, 0),
        ("nearest", 80, 100),
        ("nearest", 20, 0),
        ("nearest", None, 0),
        ("open", 0, 100),
        ("closed", 100, 0),
    ],
)
def test_wind_position(mode, wanted, expected) -> None:
    assert wind_position(cfg(wind_mode=mode, pos_wind=0), wanted) == expected


def test_wind_nearest_uses_the_schedule() -> None:
    c = cfg(wind_mode="nearest")
    day = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=True, wind=True)
    night = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=False, wind=True)
    assert day[0].position == 100
    assert night[0].position == 0


# --- holiday -------------------------------------------------------------------------


def test_day_schedule_shift() -> None:
    c = cfg(up_mode="time", down_mode="time")
    day = date(2026, 6, 17)
    normal = day_schedule(c, day, SUN, TZ, lambda d: True)
    shifted = day_schedule(
        c, day, SUN, TZ, lambda d: True, shift=lambda direction, d: -20 if direction == "up" else 25
    )
    assert (shifted.up - normal.up).total_seconds() == -20 * 60
    assert (shifted.down - normal.down).total_seconds() == 25 * 60
    assert shifted.up_early <= shifted.up <= shifted.up_late
    assert isinstance(shifted.up, datetime)


def test_manual_override_wins_over_temperature_limit() -> None:
    c = cfg()
    wishes = build_wishes(c, trigger=TRIGGER_APPLY_TARGET, is_day=True, temp_limit="high")
    sit = Situation(trigger=TRIGGER_APPLY_TARGET, current_position=100, override_active=True)
    assert decide(c, sit, wishes).blocked_by == "manual_override"

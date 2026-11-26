"""Engine tests of 0.7.3: hot day, quiet hours, slat angle, time from an entity."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.autoshutterscontrol.engine import fhem
from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_QUIET,
    REASON_HOT_DAY,
    REASON_SHADING,
    TRIGGER_SCHEDULE_UP,
    TRIGGER_WINDOW,
    Situation,
    build_wishes,
    decide,
)
from custom_components.autoshutterscontrol.engine.checks import check
from custom_components.autoshutterscontrol.engine.hotday import is_hot, sun_on_window
from custom_components.autoshutterscontrol.engine.period import in_quiet
from custom_components.autoshutterscontrol.engine.resolve import resolve
from custom_components.autoshutterscontrol.engine.schedule import day_schedule
from custom_components.autoshutterscontrol.engine.settings import BY_KEY, to_storage
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator
from custom_components.autoshutterscontrol.engine.tilt import (
    auto_tilt,
    shading_tilt,
    slat_angle,
    tilt_for,
    window_azimuth,
)

TZ = ZoneInfo("Europe/Berlin")
SUN = SunCalculator(Location(51.35, 8.57, 450, TZ))


def cfg(**values):
    return resolve({k: to_storage(BY_KEY[k], v) for k, v in values.items()})


# --- hot day -----------------------------------------------------------------


def test_hot_day_is_off_by_default() -> None:
    assert not is_hot(cfg(), 35, "sunny")


@pytest.mark.parametrize(
    ("forecast", "condition", "sunny", "expected"),
    [
        (30, "sunny", True, True),
        (25.5, "sunny", True, False),
        (None, "sunny", True, False),
        (30, "rainy", True, False),
        (30, "rainy", False, True),
        (30, None, True, True),  # no condition known: temperature decides
    ],
)
def test_is_hot(forecast, condition, sunny, expected) -> None:
    c = cfg(hot_day=True, hot_day_temp=26, hot_day_sunny=sunny)
    assert is_hot(c, forecast, condition) is expected


def test_sun_on_window() -> None:
    c = cfg(shading_azimuth_start=105, shading_azimuth_end=255, shading_elevation_min=25)
    day = date(2026, 6, 24)
    morning = datetime.combine(day, time(7, 0), tzinfo=TZ)
    evening = datetime.combine(day, time(21, 0), tzinfo=TZ)
    assert sun_on_window(c, SUN, morning, evening)
    # Late in the day the sun has passed the south window
    late = datetime.combine(day, time(19, 30), tzinfo=TZ)
    assert not sun_on_window(c, SUN, late, evening)
    # A west window still gets the sun in the evening
    west = cfg(shading_azimuth_start=200, shading_azimuth_end=320, shading_elevation_min=5)
    assert sun_on_window(west, SUN, late, evening)


def test_hot_day_wish_only_by_day() -> None:
    c = cfg(pos_shading=30)
    day = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=True, hot_day=True)
    assert (day[0].reason, day[0].position) == (REASON_HOT_DAY, 30)
    night = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=False, hot_day=True)
    assert night[0].reason == "night_close"
    # Real shading wins as reason
    both = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=True, shaded=True, hot_day=True)
    assert both[0].reason == REASON_SHADING


def test_hot_day_morning_goes_straight_to_shading() -> None:
    c = cfg(pos_shading=30, shading_only_down=True)
    wishes = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=True, hot_day=True)
    decision = decide(c, Situation(TRIGGER_SCHEDULE_UP, current_position=0), wishes)
    assert decision.drive and decision.position == 30 and decision.reason == REASON_HOT_DAY


# --- quiet hours -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "now", "expected"),
    [
        (time(22, 0), time(7, 0), time(23, 0), True),
        (time(22, 0), time(7, 0), time(6, 59), True),
        (time(22, 0), time(7, 0), time(7, 0), False),
        (time(13, 0), time(15, 0), time(14, 0), True),
        (time(13, 0), time(15, 0), time(12, 0), False),
        (None, time(7, 0), time(3, 0), False),
        (time(7, 0), time(7, 0), time(7, 0), False),
    ],
)
def test_in_quiet(start, end, now, expected) -> None:
    assert in_quiet(start, end, now) is expected


def test_quiet_blocks_all_but_protection() -> None:
    c = cfg()
    situation = Situation(TRIGGER_SCHEDULE_UP, current_position=0, quiet=True)
    wishes = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=True)
    assert decide(c, situation, wishes).blocked_by == BLOCK_QUIET
    open_cover = Situation(TRIGGER_SCHEDULE_UP, current_position=100, quiet=True)
    wishes = build_wishes(c, trigger=TRIGGER_SCHEDULE_UP, is_day=True, wind=True)
    decision = decide(c, open_cover, wishes)
    assert decision.drive and decision.reason == "wind"
    # Ventilation stays allowed (setting)
    window = Situation(TRIGGER_WINDOW, current_position=0, quiet=True)
    wishes = build_wishes(
        c, trigger=TRIGGER_WINDOW, is_day=False, window=(50, "ventilate"), current=0
    )
    assert decide(c, window, wishes).drive
    strict = cfg(quiet_window=False)
    assert decide(strict, window, wishes).blocked_by == BLOCK_QUIET


def test_quiet_incomplete_check() -> None:
    codes = [code for code, _ in check(cfg(quiet_start=time(22, 0)))]
    assert "quiet_incomplete" in codes
    codes = [code for code, _ in check(cfg(quiet_start=time(22, 0), quiet_end=time(6, 0)))]
    assert "quiet_incomplete" not in codes


# --- slat angle ----------------------------------------------------------------


def test_window_azimuth() -> None:
    assert window_azimuth(cfg()) == 180
    assert window_azimuth(cfg(shading_azimuth_start=300, shading_azimuth_end=60)) == 0
    assert window_azimuth(cfg(window_azimuth=200)) == 200


def test_slat_angle() -> None:
    # Low sun straight in front: nearly closed (arcsin 0.9 = 64.2 degrees)
    assert slat_angle(0.9, 0.01, 180, 180) == pytest.approx(64.15, abs=0.1)
    # High sun: horizontal is enough
    assert slat_angle(0.9, 80, 180, 180) == 0
    # Sun behind the facade or below the horizon
    assert slat_angle(0.9, 30, 0, 180) == 0
    assert slat_angle(0.9, -2, 180, 180) == 0
    # Sun from the side: the profile angle is steeper, less closing
    assert slat_angle(0.9, 30, 240, 180) < slat_angle(0.9, 30, 180, 180)
    # Wide spaced slats can never block the low sun completely
    assert slat_angle(1.5, 5, 180, 180) == 90


def test_auto_tilt() -> None:
    c = cfg(tilt_auto=True, tilt_shading=50, tilt_horizontal=100, tilt_vertical=0)
    assert auto_tilt(c, 0.01, 180) == 30  # 100 - 64.2 / 90 * 100 = 28.7 -> 30
    assert auto_tilt(c, 80, 180) == 100
    assert shading_tilt(c, 80, 180) == 100
    assert tilt_for(c, REASON_HOT_DAY, 0.01, azimuth=180) == 30
    # Without the sun position the fixed slats when shading apply
    assert shading_tilt(c, 30) == 50
    inverted = cfg(tilt_auto=True, tilt_horizontal=0, tilt_vertical=100)
    assert auto_tilt(inverted, 0.01, 180) == 70


# --- morning and evening from an entity ------------------------------------------


def test_time_from_entity() -> None:
    c = cfg(
        up_mode="entity",
        down_mode="entity",
        time_up_early_workday=time(5, 0),
        time_up_late_workday=time(8, 30),
        time_down_early_workday=time(16, 0),
        time_down_late_workday=time(22, 0),
        offset_up=10,
    )
    day = date(2026, 11, 25)
    times = {
        "up": datetime(2026, 11, 25, 6, 15, tzinfo=TZ),
        "down": datetime(2026, 11, 25, 23, 0, tzinfo=TZ),
    }
    sched = day_schedule(c, day, SUN, TZ, lambda _d: True, entity_time=lambda d, _day: times[d])
    assert sched.up == datetime(2026, 11, 25, 6, 25, tzinfo=TZ)  # with the offset
    assert sched.down == datetime(2026, 11, 25, 22, 0, tzinfo=TZ)  # latest time
    # No usable value: latest morning time, earliest evening time
    sched = day_schedule(c, day, SUN, TZ, lambda _d: True, entity_time=lambda _d, _day: None)
    assert sched.up == datetime(2026, 11, 25, 8, 30, tzinfo=TZ)
    assert sched.down == datetime(2026, 11, 25, 16, 0, tzinfo=TZ)


def test_missing_time_entity_check() -> None:
    codes = [code for code, _ in check(cfg(up_mode="entity"))]
    assert "missing_time_entity" in codes
    codes = [code for code, _ in check(cfg(up_mode="entity", up_time_entity="sensor.alarm"))]
    assert "missing_time_entity" not in codes


def test_fhem_drive_delay_is_staggered() -> None:
    imp = fhem.convert(
        "define ASC_Dev AutoShuttersControl\nattr ASC_Dev ASC_shuttersDriveDelay 5\n"
    )
    assert imp.global_settings.get("drive_stagger") == 5

"""Table tests of stage 2: brightness, sun elevation, privacy, window, calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_DIRECTION,
    BLOCK_LOCKOUT,
    BLOCK_NO_WISH,
    TRIGGER_APPLY_TARGET,
    TRIGGER_SCHEDULE_DOWN,
    TRIGGER_WINDOW,
    Situation,
    build_wishes,
    decide,
)
from custom_components.autoshutterscontrol.engine.calendar import calendar_windows
from custom_components.autoshutterscontrol.engine.daynight import (
    DOWN,
    PRIVACY_DOWN,
    PRIVACY_UP,
    UP,
    DayMarks,
    condition_held,
    elevation_threshold,
    in_dynamic_window,
    is_day,
    light_condition,
    privacy_by_brightness,
    privacy_phase,
)
from custom_components.autoshutterscontrol.engine.resolve import resolve
from custom_components.autoshutterscontrol.engine.schedule import day_schedule, default_workday
from custom_components.autoshutterscontrol.engine.settings import BY_KEY, to_storage
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator
from custom_components.autoshutterscontrol.engine.window import (
    lockout_active,
    window_position,
    window_state,
)

TZ = ZoneInfo("Europe/Berlin")
SUN = SunCalculator(Location(51.35, 8.57, 450, TZ))
DAY = date(2026, 11, 25)


def cfg(**kw):
    return resolve({k: to_storage(BY_KEY[k], v) for k, v in kw.items()})


def at(h, m=0):
    return datetime(2026, 11, 25, h, m, tzinfo=TZ)


# --- brightness and sun elevation -------------------------------------------


@pytest.mark.parametrize(
    ("settings", "direction", "brightness", "elevation", "expected"),
    [
        ({"up_mode": "brightness"}, UP, 600, None, True),
        ({"up_mode": "brightness"}, UP, 400, None, False),
        ({"up_mode": "brightness"}, UP, None, 10, False),
        ({"down_mode": "brightness"}, DOWN, 250, None, True),
        ({"down_mode": "brightness"}, DOWN, 350, None, False),
        ({"up_mode": "elevation"}, UP, None, 3.5, True),
        ({"up_mode": "elevation"}, UP, None, 2.0, False),
        ({"down_mode": "elevation"}, DOWN, None, 0.5, True),
        ({"up_mode": "brightness_elevation"}, UP, 100, 5, True),  # OR
        ({"up_mode": "brightness_elevation", "light_logic": "and"}, UP, 100, 5, False),
        ({"up_mode": "brightness_elevation", "light_logic": "and"}, UP, 900, 5, True),
        ({"up_mode": "brightness_elevation"}, UP, None, 5, True),  # OR without sensor
        ({"up_mode": "astro"}, UP, 900, 5, False),  # not a dynamic mode
    ],
)
def test_light_condition(settings, direction, brightness, elevation, expected):
    assert light_condition(cfg(**settings), direction, brightness, elevation) is expected


@pytest.mark.parametrize(
    ("source", "sensor", "expected"),
    [("fixed", 7, 3.0), ("sensor", 7, 7), ("hybrid", 7, 10.0), ("sensor", None, 3.0)],
)
def test_elevation_threshold(source, sensor, expected):
    assert elevation_threshold(cfg(elevation_source=source), UP, sensor) == expected


def test_condition_held():
    assert not condition_held(None, at(7), 2)
    assert not condition_held(at(7), at(7, 1), 2)
    assert condition_held(at(7), at(7, 2), 2)
    assert condition_held(at(7), at(7), 0)


def test_dynamic_schedule_uses_late_time_as_deadline():
    c = cfg(up_mode="brightness", down_mode="elevation")
    s = day_schedule(c, DAY, SUN, TZ, default_workday)
    assert s.up == at(8, 30) and s.up_dynamic
    assert s.down == at(22, 0) and s.down_dynamic
    assert in_dynamic_window(s, UP, at(6))
    assert not in_dynamic_window(s, UP, at(4))
    assert not in_dynamic_window(s, UP, at(8, 30))
    # opened early by brightness
    marks = DayMarks(up=at(7, 10))
    assert is_day(s, marks, at(7, 15))
    assert not is_day(s, DayMarks(), at(7, 15))


def test_calendar_windows_override_times():
    c = cfg(up_mode="time", down_mode="time")
    s = day_schedule(
        c, DAY, SUN, TZ, default_workday, windows=lambda d: {"up": (time(6, 45), time(7, 30))}
    )
    assert s.up == at(6, 45)
    assert s.down == at(16, 0)


# --- privacy ----------------------------------------------------------------


def test_privacy_phases():
    c = cfg(up_mode="time", down_mode="time", privacy_up_minutes=30, privacy_down_minutes=20)
    s = day_schedule(c, DAY, SUN, TZ, default_workday)
    m = DayMarks()
    assert privacy_phase(c, s, m, at(4, 29)) is None
    assert privacy_phase(c, s, m, at(4, 30)) == PRIVACY_UP
    assert privacy_phase(c, s, m, at(5, 0)) is None
    assert privacy_phase(c, s, m, at(15, 40)) == PRIVACY_DOWN
    assert privacy_phase(c, s, m, at(16, 0)) is None
    assert privacy_phase(cfg(), s, m, at(15, 50)) is None


def test_privacy_by_brightness():
    c = cfg(down_mode="time", time_down_early_workday="16:00", privacy_brightness=200)
    c2 = cfg(down_mode="time", time_down_early_workday="16:00")
    s = day_schedule(c, DAY, SUN, TZ, default_workday)
    # in time mode the evening drive is at the early time: no window
    assert not privacy_by_brightness(c, s, DayMarks(), at(15, 59), 100)
    c = cfg(down_mode="astro", privacy_brightness=200)
    s = day_schedule(c, DAY, SUN, TZ, default_workday)
    assert privacy_by_brightness(c, s, DayMarks(), at(16, 5), 150)
    assert not privacy_by_brightness(c, s, DayMarks(), at(16, 5), 250)
    assert not privacy_by_brightness(c, s, DayMarks(privacy_down=at(16)), at(16, 5), 150)
    assert not privacy_by_brightness(c2, s, DayMarks(), at(16, 5), 150)
    m = DayMarks(privacy_down=at(16, 5))
    assert privacy_phase(c, s, m, at(16, 10)) == PRIVACY_DOWN


# --- window -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("open_c", "tilted_c", "three", "expected"),
    [
        (None, None, None, None),
        ("on", None, None, "open"),
        ("off", None, None, "closed"),
        ("off", "on", None, "tilted"),
        ("on", "on", None, "open"),
        (None, None, "Tilted", "tilted"),
        (None, None, "open", "open"),
        (None, None, "closed", "closed"),
    ],
)
def test_window_state(open_c, tilted_c, three, expected):
    assert window_state(cfg(), open_c, tilted_c, three) == expected


def test_window_state_own_texts():
    c = cfg(window_value_open="offen", window_value_tilted="gekippt")
    assert window_state(c, None, None, "gekippt") == "tilted"
    assert window_state(c, None, None, "offen") == "open"


def test_window_position_and_lockout():
    c = cfg()
    assert window_position(c, "tilted", False) == (50, "ventilate")
    assert window_position(c, "open", False) == (50, "ventilate")
    assert window_position(c, "open", True) == (70, "comfort")
    assert window_position(c, "closed", True) is None
    assert window_position(cfg(ventilate_enabled=False), "open", True) is None
    assert not lockout_active(c, "open")
    assert lockout_active(cfg(lockout="soft"), "open")
    assert not lockout_active(cfg(lockout="soft"), "tilted")
    assert lockout_active(cfg(lockout="hard", lockout_tilted=True), "tilted")


def _decide(c, trigger, current, is_day, window=None, privacy=None, lockout=False):
    wishes = build_wishes(
        c, trigger=trigger, is_day=is_day, privacy_phase=privacy, window=window, current=current
    )
    return decide(c, Situation(trigger, current_position=current, lockout=lockout), wishes)


def test_window_at_night_ventilates_instead_of_closing():
    c = cfg()
    d = _decide(c, TRIGGER_SCHEDULE_DOWN, 100, False, window=(50, "ventilate"))
    assert d.drive and d.position == 50 and d.reason == "ventilate"
    # window tilted while closed: up to ventilation
    d = _decide(c, TRIGGER_WINDOW, 0, False, window=(50, "ventilate"))
    assert d.drive and d.position == 50


def test_window_by_day_does_not_open_fully():
    c = cfg()
    d = _decide(c, TRIGGER_WINDOW, 100, True, window=(50, "ventilate"))
    assert not d.drive and d.blocked_by == BLOCK_NO_WISH
    # cover lowered by hand below the ventilation position
    d = _decide(c, TRIGGER_WINDOW, 20, True, window=(50, "ventilate"))
    assert d.drive and d.position == 50
    # target of the day stays "open"
    d = _decide(c, TRIGGER_APPLY_TARGET, 20, True, window=(50, "ventilate"))
    assert d.position == 100


def test_ventilate_only_up():
    c = cfg(pos_closed=0)
    # comfort cover at 70, window goes to tilted (ventilation 50): no lowering
    d = _decide(c, TRIGGER_WINDOW, 70, False, window=(50, "ventilate"))
    assert not d.drive and d.blocked_by == BLOCK_DIRECTION
    c = cfg(ventilate_only_up=False)
    d = _decide(c, TRIGGER_WINDOW, 70, False, window=(50, "ventilate"))
    assert d.drive and d.position == 50


def test_lockout_blocks_closing():
    c = cfg(lockout="soft", ventilate_enabled=False)
    d = _decide(c, TRIGGER_SCHEDULE_DOWN, 100, False, lockout=True)
    assert not d.drive and d.blocked_by == BLOCK_LOCKOUT
    d = _decide(c, TRIGGER_SCHEDULE_DOWN, None, False, lockout=True)
    assert d.blocked_by == BLOCK_LOCKOUT
    # opening is fine
    d = _decide(c, TRIGGER_APPLY_TARGET, 0, True, lockout=True)
    assert d.drive


def test_privacy_wishes():
    c = cfg(pos_privacy=40)
    d = _decide(c, TRIGGER_APPLY_TARGET, 100, True, privacy=PRIVACY_DOWN)
    assert d.drive and d.position == 40 and d.reason == "privacy_down"
    d = _decide(c, TRIGGER_APPLY_TARGET, 0, False, privacy=PRIVACY_UP)
    assert d.drive and d.position == 40 and d.reason == "privacy_up"
    c = cfg(pos_privacy=40, pos_privacy_up=20)
    d = _decide(c, TRIGGER_APPLY_TARGET, 0, False, privacy=PRIVACY_UP)
    assert d.position == 20
    # privacy down never drives up
    d = _decide(c, TRIGGER_APPLY_TARGET, 10, True, privacy=PRIVACY_DOWN)
    assert not d.drive and d.blocked_by == BLOCK_DIRECTION


# --- calendar ---------------------------------------------------------------


def test_calendar_windows():
    events = [
        {
            "summary": "Rollladen OPEN",
            "start": "2026-11-25T06:30:00+01:00",
            "end": "2026-11-25T07:15:00+01:00",
        },
        {
            "summary": "close",
            "start": "2026-11-25T17:00:00+01:00",
            "end": "2026-11-25T18:00:00+01:00",
        },
        {
            "summary": "open late",
            "start": "2026-11-25T09:00:00+01:00",
            "end": "2026-11-25T10:00:00+01:00",
        },
        {"summary": "holiday", "start": "2026-11-26", "end": "2026-11-27"},
        {"summary": "open", "start": "2026-11-26", "end": "2026-11-27"},
        {
            "summary": "Open",
            "start": "2026-11-26T08:00:00+01:00",
            "end": "2026-11-26T09:00:00+01:00",
        },
    ]
    windows = calendar_windows(events, "open", "close", TZ)
    assert windows[DAY] == {"up": (time(6, 30), time(7, 15)), "down": (time(17), time(18))}
    assert windows[DAY + timedelta(days=1)] == {"up": (time(8), time(9))}

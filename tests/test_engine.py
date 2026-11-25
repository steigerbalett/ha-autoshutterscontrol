"""Table tests of the pure logic (no Home Assistant needed)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_AT_TARGET,
    BLOCK_AUTOMATIC_OFF,
    BLOCK_DIRECTION,
    BLOCK_DONE_BY_MANUAL,
    BLOCK_MOVING,
    BLOCK_NO_WISH,
    BLOCK_OVERRIDE,
    BLOCK_PAUSED,
    BLOCK_UNAVAILABLE,
    PRIO_FORCE,
    PRIO_SHADING,
    REASON_DAY_OPEN,
    REASON_NIGHT_CLOSE,
    TRIGGER_APPLY_TARGET,
    TRIGGER_SCHEDULE_UP,
    Situation,
    Wish,
    decide,
    schedule_wish,
)
from custom_components.autoshutterscontrol.engine.override import (
    manual_counts_as_scheduled,
    override_until,
)
from custom_components.autoshutterscontrol.engine.resolve import inherited_value, resolve
from custom_components.autoshutterscontrol.engine.schedule import (
    day_schedule,
    default_workday,
    next_events,
)
from custom_components.autoshutterscontrol.engine.settings import (
    BY_KEY,
    SETTINGS,
    from_storage,
    parse_time,
    to_storage,
)
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator

TZ = ZoneInfo("Europe/Berlin")
SUN = SunCalculator(Location(51.35, 8.57, 450, TZ))  # Brilon


def cfg(**kw):
    return resolve({k: to_storage(BY_KEY[k], v) for k, v in kw.items()})


# --- settings and inheritance -------------------------------------------


def test_every_setting_has_valid_default():
    for s in SETTINGS:
        if s.options and s.default is not None:
            values = s.default if isinstance(s.default, tuple) else (s.default,)
            assert set(values) <= set(s.options), s.key
        if s.minimum is not None and isinstance(s.default, (int, float)):
            assert s.minimum <= s.default <= s.maximum, s.key


def test_storage_roundtrip():
    s = BY_KEY["time_up_early_workday"]
    assert to_storage(s, time(6, 15)) == "06:15:00"
    assert from_storage(s, "06:15") == time(6, 15)
    assert parse_time("7:05:09") == time(7, 5, 9)
    assert from_storage(BY_KEY["override_blocks"], ["open"]) == ("open",)


@pytest.mark.parametrize(
    ("glob", "prof", "cover", "value", "source"),
    [
        ({}, {}, {}, "astro", "default"),
        ({"up_mode": "time"}, {}, {}, "time", "global"),
        ({"up_mode": "time"}, {"up_mode": "astro"}, {}, "astro", "profile"),
        ({"up_mode": "time"}, {"up_mode": "astro"}, {"up_mode": "time"}, "time", "cover"),
        ({"up_mode": "time"}, None, {"up_mode": None}, "time", "global"),
        ({"up_mode": "time"}, {"up_mode": ""}, {}, "time", "global"),
    ],
)
def test_resolve_levels(glob, prof, cover, value, source):
    resolved = resolve(glob, prof, cover)
    assert resolved["up_mode"] == value
    assert resolved.source("up_mode") == source


def test_resolve_cover_only_setting_ignores_global():
    resolved = resolve({"invert": True}, {"invert": True}, {})
    assert resolved["invert"] is False
    assert resolve({}, {}, {"invert": True})["invert"] is True


def test_resolve_empty_list_is_a_value():
    resolved = resolve({"override_blocks": ["open"]}, None, {"override_blocks": []})
    assert resolved["override_blocks"] == ()
    assert resolved.source("override_blocks") == "cover"


def test_inherited_value():
    assert inherited_value("pos_open", "cover", {"pos_open": 90}, {"pos_open": 80}) == (
        80,
        "profile",
    )
    assert inherited_value("pos_open", "cover", {"pos_open": 90}, None) == (90, "global")
    assert inherited_value("pos_open", "profile", {}, None) == (100, "default")


def test_as_dict_is_json_friendly():
    data = cfg().as_dict()
    assert data["time_up_early_workday"] == {"value": "05:00:00", "source": "default"}
    assert data["override_blocks"]["value"] == ["ventilate", "shading"]


# --- sun ------------------------------------------------------------------


def test_twilight_order():
    day = date(2026, 3, 20)
    times = [SUN.morning(day, t) for t in ("astronomical", "nautical", "civil", "real")]
    assert times == sorted(times)
    evening = [SUN.evening(day, t) for t in ("real", "civil", "nautical")]
    assert evening == sorted(evening)


def test_horizon_between_real_and_noon():
    day = date(2026, 3, 20)
    assert (
        SUN.morning(day, "real") < SUN.morning(day, "horizon", 5) < SUN.evening(day, "horizon", 5)
    )


def test_polar_returns_none():
    north = SunCalculator(Location(78.2, 15.6, 0, ZoneInfo("Arctic/Longyearbyen")))
    assert north.morning(date(2026, 12, 21), "real") is None
    # astronomical twilight does not happen in midsummer at 54° N either
    assert (
        SunCalculator(Location(54.3, 10.1, 0, TZ)).morning(date(2026, 6, 21), "astronomical")
        is None
    )


# --- schedule -------------------------------------------------------------

WORKDAY = date(2026, 11, 25)  # Wednesday
FRIDAY = date(2026, 11, 27)
SATURDAY = date(2026, 11, 28)


def test_default_workday():
    assert default_workday(WORKDAY)
    assert not default_workday(SATURDAY)


def test_time_mode_uses_early_times():
    c = cfg(up_mode="time", down_mode="time")
    s = day_schedule(c, WORKDAY, SUN, TZ, default_workday)
    assert s.up == datetime(2026, 11, 25, 5, 0, tzinfo=TZ)
    assert s.down == datetime(2026, 11, 25, 16, 0, tzinfo=TZ)
    s = day_schedule(c, SATURDAY, SUN, TZ, default_workday)
    assert s.up == datetime(2026, 11, 28, 8, 0, tzinfo=TZ)
    assert not s.up_workday


@pytest.mark.parametrize(
    ("day", "early", "late", "expected"),
    [
        # November: sunrise in Brilon ~07:50 -> between 05:00 and 08:30
        (WORKDAY, "05:00", "08:30", None),
        # late limit
        (WORKDAY, "05:00", "07:00", time(7, 0)),
        # early limit
        (WORKDAY, "08:15", "09:00", time(8, 15)),
    ],
)
def test_astro_mode_clamped(day, early, late, expected):
    c = cfg(time_up_early_workday=early, time_up_late_workday=late)
    s = day_schedule(c, day, SUN, TZ, default_workday)
    if expected is None:
        assert s.up == SUN.morning(day, "real").astimezone(TZ)
    else:
        assert s.up.timetz().replace(tzinfo=None) == expected


def test_astro_offset():
    base = day_schedule(cfg(), WORKDAY, SUN, TZ, default_workday)
    shifted = day_schedule(cfg(offset_up=15, offset_down=-20), WORKDAY, SUN, TZ, default_workday)
    assert shifted.up - base.up == timedelta(minutes=15)
    assert base.down - shifted.down == timedelta(minutes=20)


def test_down_by_tomorrow():
    c = cfg(
        down_mode="time",
        time_down_early_workday="18:00",
        time_down_early_free="21:00",
        down_tomorrow_workday=True,
    )
    assert day_schedule(c, FRIDAY, SUN, TZ, default_workday).down.hour == 21
    c = cfg(down_mode="time", time_down_early_workday="18:00", time_down_early_free="21:00")
    assert day_schedule(c, FRIDAY, SUN, TZ, default_workday).down.hour == 18


def test_weekend_times_off():
    c = cfg(up_mode="time")
    s = day_schedule(c, SATURDAY, SUN, TZ, default_workday, weekend_times=False)
    assert s.up.hour == 5
    assert s.up_workday


def test_workday_function_is_used():
    c = cfg(up_mode="time")
    s = day_schedule(c, WORKDAY, SUN, TZ, lambda d: False)
    assert s.up.hour == 8


def test_misconfigured_down_before_up():
    c = cfg(
        up_mode="time",
        down_mode="time",
        time_up_early_workday="17:00",
        time_down_early_workday="16:00",
    )
    s = day_schedule(c, WORKDAY, SUN, TZ, default_workday)
    assert s.down > s.up


def test_is_day():
    s = day_schedule(cfg(up_mode="time", down_mode="time"), WORKDAY, SUN, TZ, default_workday)
    assert not s.is_day(datetime(2026, 11, 25, 4, 59, tzinfo=TZ))
    assert s.is_day(datetime(2026, 11, 25, 5, 0, tzinfo=TZ))
    assert not s.is_day(datetime(2026, 11, 25, 16, 0, tzinfo=TZ))


def test_next_events():
    c = cfg(up_mode="time", down_mode="time")
    up, down = next_events(c, datetime(2026, 11, 25, 12, 0, tzinfo=TZ), SUN, TZ, default_workday)
    assert up == datetime(2026, 11, 26, 5, 0, tzinfo=TZ)
    assert down == datetime(2026, 11, 25, 16, 0, tzinfo=TZ)
    up, down = next_events(c, datetime(2026, 11, 27, 17, 0, tzinfo=TZ), SUN, TZ, default_workday)
    assert up == datetime(2026, 11, 28, 8, 0, tzinfo=TZ)


def test_dst_change():
    c = cfg(up_mode="time")
    s = day_schedule(c, date(2026, 3, 29), SUN, TZ, default_workday)  # Sunday, DST starts
    assert s.up == datetime(2026, 3, 29, 8, 0, tzinfo=TZ)
    assert s.up.utcoffset() == timedelta(hours=2)


# --- arbiter --------------------------------------------------------------

C = cfg()


@pytest.mark.parametrize(
    ("situation", "is_day", "drive", "position", "block"),
    [
        (Situation(TRIGGER_SCHEDULE_UP, current_position=0), True, True, 100, None),
        (Situation(TRIGGER_SCHEDULE_UP, current_position=0), False, False, 0, BLOCK_AT_TARGET),
        (Situation(TRIGGER_APPLY_TARGET, current_position=100), False, True, 0, None),
        (Situation(TRIGGER_SCHEDULE_UP, current_position=99), True, False, 100, BLOCK_AT_TARGET),
        (
            Situation(TRIGGER_SCHEDULE_UP, automatic=False, current_position=0),
            True,
            False,
            100,
            BLOCK_AUTOMATIC_OFF,
        ),
        (
            Situation(TRIGGER_SCHEDULE_UP, paused=True, current_position=0),
            True,
            False,
            100,
            BLOCK_PAUSED,
        ),
        (Situation(TRIGGER_SCHEDULE_UP, available=False), True, False, 100, BLOCK_UNAVAILABLE),
        (
            Situation(TRIGGER_SCHEDULE_UP, moving=True, current_position=0),
            True,
            False,
            100,
            BLOCK_MOVING,
        ),
        (Situation(TRIGGER_SCHEDULE_UP, current_position=None), True, True, 100, None),
        (
            Situation(TRIGGER_SCHEDULE_UP, current_position=0, done_today=frozenset({"open"})),
            True,
            False,
            100,
            BLOCK_DONE_BY_MANUAL,
        ),
        (
            Situation(TRIGGER_APPLY_TARGET, current_position=0, done_today=frozenset({"open"})),
            True,
            True,
            100,
            None,
        ),
        # default override blocks ventilation and shading only
        (
            Situation(TRIGGER_SCHEDULE_UP, current_position=0, override_active=True),
            True,
            True,
            100,
            None,
        ),
    ],
)
def test_decide_schedule(situation, is_day, drive, position, block):
    d = decide(C, situation, [schedule_wish(C, is_day)])
    assert d.drive is drive
    assert d.position == position
    assert d.blocked_by == block
    assert d.reason == (REASON_DAY_OPEN if is_day else REASON_NIGHT_CLOSE)


def test_override_blocks_open():
    c = cfg(override_blocks=["open", "close"])
    d = decide(
        c,
        Situation(TRIGGER_SCHEDULE_UP, current_position=0, override_active=True),
        [schedule_wish(c, True)],
    )
    assert d.blocked_by == BLOCK_OVERRIDE
    assert not d.drive


@pytest.mark.parametrize(
    ("is_day", "current", "rule", "drive"),
    [
        (True, 100, {}, False),  # at target
        (False, 50, {}, True),
        # closed position 30: cover at 10 would have to drive up
        (False, 10, {"pos_closed": 30}, False),
        (False, 10, {"pos_closed": 30, "close_never_up": False}, True),
        # open position 70: cover at 90 would have to drive down
        (True, 90, {"pos_open": 70}, False),
        (True, 90, {"pos_open": 70, "open_never_down": False}, True),
    ],
)
def test_direction_rules(is_day, current, rule, drive):
    c = cfg(**rule)
    d = decide(
        c, Situation(TRIGGER_APPLY_TARGET, current_position=current), [schedule_wish(c, is_day)]
    )
    assert d.drive is drive
    if not drive and abs(current - d.position) > c["tolerance"]:
        assert d.blocked_by == BLOCK_DIRECTION


def test_morning_and_evening_switches():
    assert schedule_wish(C, True, morning_enabled=False) is None
    assert schedule_wish(C, False, evening_enabled=False) is None
    d = decide(C, Situation(TRIGGER_SCHEDULE_UP, current_position=0), [None])
    assert d.blocked_by == BLOCK_NO_WISH


def test_higher_priority_wins_and_bypasses_rules():
    force = Wish(PRIO_FORCE, "force", "close", 0, "force_close", bypass_rules=True)
    shade = Wish(PRIO_SHADING, "shading", "shading", 30, "shading_in")
    c = cfg(override_blocks=["close", "shading"])
    sit = Situation(TRIGGER_APPLY_TARGET, current_position=100, override_active=True)
    d = decide(c, sit, [schedule_wish(c, True), shade, force])
    assert d.drive and d.position == 0 and d.source == "force"
    d = decide(c, sit, [schedule_wish(c, True), shade])
    assert d.blocked_by == BLOCK_OVERRIDE and d.source == "shading"


# --- override -------------------------------------------------------------

NOW = datetime(2026, 11, 25, 10, 0, tzinfo=TZ)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({}, NOW + timedelta(minutes=20)),
        ({"override_minutes": 90}, NOW + timedelta(minutes=90)),
        (
            {"override_reset": "time", "override_reset_time": "12:00"},
            datetime(2026, 11, 25, 12, 0, tzinfo=TZ),
        ),
        (
            {"override_reset": "time", "override_reset_time": "03:00"},
            datetime(2026, 11, 26, 3, 0, tzinfo=TZ),
        ),
        ({"override_reset": "next_schedule"}, None),
        ({"override_reset": "manual"}, None),
    ],
)
def test_override_until(settings, expected):
    assert override_until(cfg(**settings), NOW, TZ) == expected


def test_manual_counts_as_scheduled():
    # astro mode with a window between the early time and the sunrise
    c = cfg(time_up_early_workday="06:00", time_up_late_workday="09:00")
    s = day_schedule(c, WORKDAY, SUN, TZ, default_workday)
    before = s.up - timedelta(minutes=30)
    assert manual_counts_as_scheduled(c, s, before, 100) == "open"
    assert manual_counts_as_scheduled(c, s, before, 50) is None
    assert manual_counts_as_scheduled(c, s, s.up + timedelta(minutes=1), 100) is None
    assert (
        manual_counts_as_scheduled(
            cfg(
                time_up_early_workday="06:00",
                time_up_late_workday="09:00",
                manual_counts_open=False,
            ),
            s,
            before,
            100,
        )
        is None
    )
    evening = s.down - timedelta(minutes=10)
    assert manual_counts_as_scheduled(c, s, evening, 0) == "close"
    assert manual_counts_as_scheduled(c, s, evening, None) is None

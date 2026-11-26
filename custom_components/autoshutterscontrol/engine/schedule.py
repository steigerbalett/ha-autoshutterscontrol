"""Morning and evening times of one cover.

Modes: time, sun (astro), time of an entity (e.g. the next alarm of a phone,
clamped to the early and late time), and the dynamic modes brightness / sun elevation,
where the drive happens as soon as the condition is met between the early and
the late time; the late time is the deadline. The early/late window comes from
the configured times or from calendar events.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

from .settings import DYNAMIC_MODES, MODE_ASTRO, MODE_ENTITY
from .sun import SunCalculator

# Returns True if the given day is a workday
WorkdayFunc = Callable[[date], bool]
# Returns calendar windows of a day: {"up": (start, end), "down": (start, end)}
WindowsFunc = Callable[[date], Mapping[str, tuple[time, time]]]
# Returns the time an entity gives for a direction ("up"/"down") on a day
EntityTimeFunc = Callable[[str, date], datetime | None]
# Returns the shift in minutes of a direction on a day (holiday)
ShiftFunc = Callable[[str, date], int]


@dataclass(frozen=True)
class DaySchedule:
    """Times of one day.

    ``up``/``down`` are the planned drive times; in a dynamic mode they are the
    deadlines (late time) and the drive may happen earlier.
    """

    day: date
    up: datetime
    down: datetime
    up_workday: bool
    down_workday: bool
    up_early: datetime
    up_late: datetime
    down_early: datetime
    down_late: datetime
    up_dynamic: bool = False
    down_dynamic: bool = False

    def is_day(self, now: datetime) -> bool:
        """Return True between the planned morning and evening drive."""
        return self.up <= now < self.down


def _at(day: date, value: time, tz: tzinfo) -> datetime:
    return datetime.combine(day, value, tzinfo=tz)


def _clamp(value: datetime, early: datetime, late: datetime) -> datetime:
    return min(max(value, early), late)


def default_workday(day: date) -> bool:
    """Fallback without workday sensor: Monday to Friday."""
    return day.weekday() < 5


def _window(
    cfg: Mapping[str, Any],
    direction: str,
    day: date,
    workday: bool,
    tz: tzinfo,
    windows: Mapping[str, tuple[time, time]] | None,
) -> tuple[datetime, datetime]:
    if windows and direction in windows:
        start, end = windows[direction]
    else:
        suffix = "workday" if workday else "free"
        start = cfg[f"time_{direction}_early_{suffix}"]
        end = cfg[f"time_{direction}_late_{suffix}"]
    early = _at(day, start, tz)
    late = _at(day, end, tz)
    return early, max(early, late)


def _drive_time(
    cfg: Mapping[str, Any],
    direction: str,
    day: date,
    early: datetime,
    late: datetime,
    sun: SunCalculator,
    tz: tzinfo,
    entity_time: EntityTimeFunc | None = None,
) -> datetime:
    mode = cfg[f"{direction}_mode"]
    if mode in DYNAMIC_MODES:
        return late
    if mode == MODE_ENTITY:
        event = entity_time(direction, day) if entity_time else None
    elif mode != MODE_ASTRO:
        return early
    elif direction == "up":
        event = sun.morning(day, cfg["twilight_up"], cfg["horizon_up"])
    else:
        event = sun.evening(day, cfg["twilight_down"], cfg["horizon_down"])
    if event is None:
        # No sun event (polar night / midnight sun) or no usable entity time
        return late if direction == "up" else early
    event = event.astimezone(tz) + timedelta(minutes=cfg[f"offset_{direction}"])
    return _clamp(event, early, late)


def up_time(cfg, day, workday, sun, tz, windows=None, entity_time=None) -> datetime:
    """Return the morning drive time (deadline in a dynamic mode)."""
    early, late = _window(cfg, "up", day, workday, tz, windows)
    return _drive_time(cfg, "up", day, early, late, sun, tz, entity_time)


def down_time(cfg, day, workday, sun, tz, windows=None, entity_time=None) -> datetime:
    """Return the evening drive time (deadline in a dynamic mode)."""
    early, late = _window(cfg, "down", day, workday, tz, windows)
    return _drive_time(cfg, "down", day, early, late, sun, tz, entity_time)


def day_schedule(
    cfg: Mapping[str, Any],
    day: date,
    sun: SunCalculator,
    tz: tzinfo,
    is_workday: WorkdayFunc,
    weekend_times: bool = True,
    windows: WindowsFunc | None = None,
    entity_time: EntityTimeFunc | None = None,
    shift: ShiftFunc | None = None,
) -> DaySchedule:
    """Return the schedule of one day.

    ``weekend_times`` off means every day uses the workday times.
    ``down_tomorrow_workday`` chooses the evening time by tomorrow's day type.
    """
    if weekend_times:
        up_wd = is_workday(day)
        down_wd = is_workday(day + timedelta(days=1)) if cfg["down_tomorrow_workday"] else up_wd
    else:
        up_wd = down_wd = True
    win = windows(day) if windows else None
    up_early, up_late = _window(cfg, "up", day, up_wd, tz, win)
    down_early, down_late = _window(cfg, "down", day, down_wd, tz, win)
    up = _drive_time(cfg, "up", day, up_early, up_late, sun, tz, entity_time)
    down = _drive_time(cfg, "down", day, down_early, down_late, sun, tz, entity_time)
    if shift is not None:
        # Holiday: after the limits, so the shift may leave the early/late window
        up += timedelta(minutes=shift("up", day))
        down += timedelta(minutes=shift("down", day))
        up_late = max(up_late, up)
        down_late = max(down_late, down)
        up_early = min(up_early, up)
        down_early = min(down_early, down)
    if down <= up:
        # Misconfiguration (evening before morning): keep the order
        down = up + timedelta(minutes=1)
    return DaySchedule(
        day,
        up,
        down,
        up_wd,
        down_wd,
        up_early,
        up_late,
        down_early,
        down_late,
        cfg["up_mode"] in DYNAMIC_MODES,
        cfg["down_mode"] in DYNAMIC_MODES,
    )


def next_events(
    cfg: Mapping[str, Any],
    now: datetime,
    sun: SunCalculator,
    tz: tzinfo,
    is_workday: WorkdayFunc,
    weekend_times: bool = True,
    windows: WindowsFunc | None = None,
    entity_time: EntityTimeFunc | None = None,
    shift: ShiftFunc | None = None,
) -> tuple[datetime, datetime]:
    """Return the next morning and the next evening drive after ``now``."""
    today = now.astimezone(tz).date()
    next_up: datetime | None = None
    next_down: datetime | None = None
    for offset in range(0, 3):
        sched = day_schedule(
            cfg,
            today + timedelta(days=offset),
            sun,
            tz,
            is_workday,
            weekend_times,
            windows,
            entity_time,
            shift,
        )
        if next_up is None and sched.up > now:
            next_up = sched.up
        if next_down is None and sched.down > now:
            next_down = sched.down
        if next_up and next_down:
            break
    assert next_up is not None and next_down is not None
    return next_up, next_down

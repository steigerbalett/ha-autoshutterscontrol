"""Morning and evening times of one cover (time or sun, workday or free day)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

from .settings import MODE_ASTRO
from .sun import SunCalculator

# Returns True if the given day is a workday
WorkdayFunc = Callable[[date], bool]


@dataclass(frozen=True)
class DaySchedule:
    """Times of one day."""

    day: date
    up: datetime
    down: datetime
    up_workday: bool
    down_workday: bool

    def is_day(self, now: datetime) -> bool:
        """Return True between the morning and the evening drive."""
        return self.up <= now < self.down


def _at(day: date, value: time, tz: tzinfo) -> datetime:
    return datetime.combine(day, value, tzinfo=tz)


def _clamp(value: datetime, early: datetime, late: datetime) -> datetime:
    if late < early:
        late = early
    return min(max(value, early), late)


def default_workday(day: date) -> bool:
    """Fallback without workday sensor: Monday to Friday."""
    return day.weekday() < 5


def up_time(
    cfg: Mapping[str, Any],
    day: date,
    workday: bool,
    sun: SunCalculator,
    tz: tzinfo,
) -> datetime:
    """Return the morning drive time of a day.

    time mode: the early time (as in ASC).
    astro mode: sun event plus offset, kept between early and late.
    """
    suffix = "workday" if workday else "free"
    early = _at(day, cfg[f"time_up_early_{suffix}"], tz)
    late = _at(day, cfg[f"time_up_late_{suffix}"], tz)
    if cfg["up_mode"] != MODE_ASTRO:
        return early
    event = sun.morning(day, cfg["twilight_up"], cfg["horizon_up"])
    if event is None:
        # No sunrise (polar night or midnight sun): use the late limit
        return late if late >= early else early
    event = event.astimezone(tz) + timedelta(minutes=cfg["offset_up"])
    return _clamp(event, early, late)


def down_time(
    cfg: Mapping[str, Any],
    day: date,
    workday: bool,
    sun: SunCalculator,
    tz: tzinfo,
) -> datetime:
    """Return the evening drive time of a day.

    time mode: the early time (as in ASC).
    astro mode: sun event plus offset, kept between early and late.
    """
    suffix = "workday" if workday else "free"
    early = _at(day, cfg[f"time_down_early_{suffix}"], tz)
    late = _at(day, cfg[f"time_down_late_{suffix}"], tz)
    if cfg["down_mode"] != MODE_ASTRO:
        return early
    event = sun.evening(day, cfg["twilight_down"], cfg["horizon_down"])
    if event is None:
        return early
    event = event.astimezone(tz) + timedelta(minutes=cfg["offset_down"])
    return _clamp(event, early, late)


def day_schedule(
    cfg: Mapping[str, Any],
    day: date,
    sun: SunCalculator,
    tz: tzinfo,
    is_workday: WorkdayFunc,
    weekend_times: bool = True,
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
    up = up_time(cfg, day, up_wd, sun, tz)
    down = down_time(cfg, day, down_wd, sun, tz)
    if down <= up:
        # Misconfiguration (evening before morning): keep the order
        down = up + timedelta(minutes=1)
    return DaySchedule(day, up, down, up_wd, down_wd)


def next_events(
    cfg: Mapping[str, Any],
    now: datetime,
    sun: SunCalculator,
    tz: tzinfo,
    is_workday: WorkdayFunc,
    weekend_times: bool = True,
) -> tuple[datetime, datetime]:
    """Return the next morning and the next evening drive after ``now``."""
    today = now.astimezone(tz).date()
    next_up: datetime | None = None
    next_down: datetime | None = None
    for offset in range(0, 3):
        sched = day_schedule(
            cfg, today + timedelta(days=offset), sun, tz, is_workday, weekend_times
        )
        if next_up is None and sched.up > now:
            next_up = sched.up
        if next_down is None and sched.down > now:
            next_down = sched.down
        if next_up and next_down:
            break
    assert next_up is not None and next_down is not None
    return next_up, next_down

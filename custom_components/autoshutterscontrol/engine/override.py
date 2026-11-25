"""Manual override: when it ends and what counts as a finished scheduled drive."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, tzinfo
from typing import Any

from .schedule import DaySchedule
from .settings import KIND_CLOSE, KIND_OPEN, RESET_MINUTES, RESET_TIME


def override_until(cfg: Mapping[str, Any], since: datetime, tz: tzinfo) -> datetime | None:
    """Return when an override that started at ``since`` ends.

    None means it does not end by time: either at the next scheduled drive
    (``next_schedule``) or only by hand (``manual``).
    """
    mode = cfg["override_reset"]
    if mode == RESET_MINUTES:
        return since + timedelta(minutes=cfg["override_minutes"])
    if mode == RESET_TIME:
        local = since.astimezone(tz)
        end = datetime.combine(local.date(), cfg["override_reset_time"], tzinfo=tz)
        if end <= local:
            end = datetime.combine(
                local.date() + timedelta(days=1), cfg["override_reset_time"], tzinfo=tz
            )
        return end
    return None


def manual_counts_as_scheduled(
    cfg: Mapping[str, Any],
    sched: DaySchedule,
    now: datetime,
    position: float | None,
) -> str | None:
    """Return the drive kind a manual drive replaces, if any.

    A manual drive to the open position between the early morning time and
    the scheduled morning drive counts as that morning drive (and likewise in
    the evening), so the cover is not driven again.
    """
    if position is None:
        return None
    tol = cfg["tolerance"]
    early_up = sched.up_early
    early_down = sched.down_early
    if (
        cfg["manual_counts_open"]
        and early_up <= now < sched.up
        and position >= cfg["pos_open"] - tol
    ):
        return KIND_OPEN
    if (
        cfg["manual_counts_close"]
        and early_down <= now < sched.down
        and position <= cfg["pos_closed"] + tol
    ):
        return KIND_CLOSE
    return None

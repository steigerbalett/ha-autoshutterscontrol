"""Day and night of one cover, dynamic modes (brightness, sun elevation), privacy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .schedule import DaySchedule
from .settings import (
    ELEVATION_HYBRID,
    ELEVATION_SENSOR,
    LOGIC_AND,
    MODE_BRIGHTNESS,
    MODE_BRIGHTNESS_ELEVATION,
    MODE_ELEVATION,
)

UP = "up"
DOWN = "down"

PRIVACY_UP = "privacy_up"
PRIVACY_DOWN = "privacy_down"


@dataclass(frozen=True)
class DayMarks:
    """What already happened today (dynamic drives, privacy by brightness)."""

    up: datetime | None = None
    down: datetime | None = None
    privacy_down: datetime | None = None


def elevation_threshold(
    cfg: Mapping[str, Any], direction: str, sensor_value: float | None
) -> float:
    """Threshold for the sun elevation: fixed, from a sensor, or sensor + fixed offset."""
    fixed = cfg[f"elevation_{direction}"]
    source = cfg["elevation_source"]
    if sensor_value is None:
        return fixed
    if source == ELEVATION_SENSOR:
        return sensor_value
    if source == ELEVATION_HYBRID:
        return sensor_value + fixed
    return fixed


def light_condition(
    cfg: Mapping[str, Any],
    direction: str,
    brightness: float | None,
    elevation: float | None,
    elevation_sensor: float | None = None,
) -> bool:
    """Is it bright (UP) or dark (DOWN) enough for the dynamic mode of a direction?

    A missing value counts as "not met"; with OR the other value decides alone.
    """
    mode = cfg[f"{direction}_mode"]
    results: list[bool] = []
    if mode in (MODE_BRIGHTNESS, MODE_BRIGHTNESS_ELEVATION):
        if brightness is None:
            results.append(False)
        elif direction == UP:
            results.append(brightness >= cfg["brightness_up"])
        else:
            results.append(brightness <= cfg["brightness_down"])
    if mode in (MODE_ELEVATION, MODE_BRIGHTNESS_ELEVATION):
        if elevation is None:
            results.append(False)
        else:
            threshold = elevation_threshold(cfg, direction, elevation_sensor)
            results.append(elevation >= threshold if direction == UP else elevation <= threshold)
    if not results:
        return False
    if mode == MODE_BRIGHTNESS_ELEVATION and cfg["light_logic"] == LOGIC_AND:
        return all(results)
    return any(results)


def condition_held(since: datetime | None, now: datetime, minutes: int) -> bool:
    """True if a condition has been met for ``minutes``."""
    return since is not None and now - since >= timedelta(minutes=minutes)


def in_dynamic_window(sched: DaySchedule, direction: str, now: datetime) -> bool:
    """True between the early and the late time of a dynamic direction."""
    if direction == UP:
        return sched.up_dynamic and sched.up_early <= now < sched.up
    return sched.down_dynamic and sched.down_early <= now < sched.down


def effective_up(sched: DaySchedule, marks: DayMarks) -> datetime:
    """Morning drive time, earlier if a dynamic condition was met."""
    if marks.up is not None and marks.up < sched.up:
        return marks.up
    return sched.up


def effective_down(sched: DaySchedule, marks: DayMarks) -> datetime:
    """Evening drive time, earlier if a dynamic condition was met."""
    if marks.down is not None and marks.down < sched.down:
        return marks.down
    return sched.down


def is_day(sched: DaySchedule, marks: DayMarks, now: datetime) -> bool:
    """True between the (effective) morning and evening drive."""
    return effective_up(sched, marks) <= now < effective_down(sched, marks)


def privacy_times(
    cfg: Mapping[str, Any], sched: DaySchedule, marks: DayMarks
) -> dict[str, datetime]:
    """Start of the privacy phases of a day (only the configured ones)."""
    out: dict[str, datetime] = {}
    up = effective_up(sched, marks)
    down = effective_down(sched, marks)
    if cfg["privacy_up_minutes"]:
        out[PRIVACY_UP] = up - timedelta(minutes=cfg["privacy_up_minutes"])
    starts = []
    if cfg["privacy_down_minutes"]:
        starts.append(down - timedelta(minutes=cfg["privacy_down_minutes"]))
    if marks.privacy_down is not None and marks.privacy_down < down:
        starts.append(marks.privacy_down)
    if starts:
        out[PRIVACY_DOWN] = min(starts)
    return out


def privacy_phase(
    cfg: Mapping[str, Any], sched: DaySchedule, marks: DayMarks, now: datetime
) -> str | None:
    """PRIVACY_UP before the morning drive, PRIVACY_DOWN before the evening drive, else None."""
    times = privacy_times(cfg, sched, marks)
    if PRIVACY_UP in times and times[PRIVACY_UP] <= now < effective_up(sched, marks):
        return PRIVACY_UP
    if PRIVACY_DOWN in times and times[PRIVACY_DOWN] <= now < effective_down(sched, marks):
        return PRIVACY_DOWN
    return None


def privacy_by_brightness(
    cfg: Mapping[str, Any],
    sched: DaySchedule,
    marks: DayMarks,
    now: datetime,
    brightness: float | None,
) -> bool:
    """True if the evening privacy should start now because it got dark enough."""
    threshold = cfg["privacy_brightness"]
    if threshold is None or brightness is None or marks.privacy_down is not None:
        return False
    return sched.down_early <= now < effective_down(sched, marks) and brightness <= threshold

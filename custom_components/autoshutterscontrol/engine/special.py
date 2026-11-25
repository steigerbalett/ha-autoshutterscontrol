"""Advent, external trigger, wiggle."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from .period import in_period, parse_day
from .settings import ADVENT_CANDLEMAS, ADVENT_DATE


def first_advent(year: int) -> date:
    """First Sunday of Advent (fourth Sunday before Christmas)."""
    christmas = date(year, 12, 25)
    # Sunday before Christmas (or Christmas Eve's Sunday)
    days_back = (christmas.weekday() + 1) % 7 or 7
    fourth = christmas - timedelta(days=days_back)
    return fourth - timedelta(weeks=3)


def advent_start(cfg: Mapping[str, Any], year: int) -> tuple[int, int]:
    """(month, day) Advent starts in a year: first Sunday of Advent or a fixed day."""
    if cfg.get("advent_start") == ADVENT_DATE:
        fixed = parse_day(cfg.get("advent_start_date"))
        if fixed is not None:
            return fixed
    first = first_advent(year)
    return first.month, first.day


def advent_end(cfg: Mapping[str, Any]) -> tuple[int, int]:
    """(month, day) Advent ends: 6 January, 2 February or a fixed day."""
    if cfg["advent_end"] == ADVENT_DATE:
        fixed = parse_day(cfg.get("advent_end_date"))
        if fixed is not None:
            return fixed
    if cfg["advent_end"] == ADVENT_CANDLEMAS:
        return 2, 2
    return 1, 6


def advent_active(cfg: Mapping[str, Any], day: date) -> bool:
    """From the start (first Sunday of Advent or a day) until the end, across the new year.

    The first Sunday of Advent is taken from the year in which the period starts.
    """
    end = advent_end(cfg)
    start = advent_start(cfg, day.year)
    if start > end and (day.month, day.day) <= end:
        # Across the new year: these days belong to the period that started last year
        start = advent_start(cfg, day.year - 1)
    return in_period(day, start, end)


def trigger_position(cfg: Mapping[str, Any], state: str | None) -> int | None:
    """Position for the state of the external trigger entity (two active values)."""
    if state is None or not cfg["trigger_entity"]:
        return None
    value = str(state).strip().lower()
    for key, pos_key in (
        ("trigger_value", "trigger_position"),
        ("trigger_value2", "trigger_position2"),
    ):
        wanted = cfg[key]
        if wanted is not None and cfg[pos_key] is not None and value == str(wanted).strip().lower():
            return cfg[pos_key]
    return None


def wiggle_target(cfg: Mapping[str, Any], current: float) -> int:
    """Position for a short wiggle: down by the value, up near the bottom."""
    step = cfg["wiggle_value"]
    if current - step >= 0:
        return int(round(current - step))
    return int(round(min(100, current + step)))

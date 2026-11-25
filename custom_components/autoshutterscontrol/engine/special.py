"""Advent, external trigger, wiggle."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from .settings import ADVENT_CANDLEMAS


def first_advent(year: int) -> date:
    """First Sunday of Advent (fourth Sunday before Christmas)."""
    christmas = date(year, 12, 25)
    # Sunday before Christmas (or Christmas Eve's Sunday)
    days_back = (christmas.weekday() + 1) % 7 or 7
    fourth = christmas - timedelta(days=days_back)
    return fourth - timedelta(weeks=3)


def advent_active(cfg: Mapping[str, Any], day: date) -> bool:
    """From the first Sunday of Advent until 6 January (or 2 February)."""
    end = date(day.year, 2, 2) if cfg["advent_end"] == ADVENT_CANDLEMAS else date(day.year, 1, 6)
    if day <= end:
        return True
    return day >= first_advent(day.year)


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

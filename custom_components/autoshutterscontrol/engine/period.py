"""Periods of the year (day and month, e.g. 1.11. to 31.3.) and of the day."""

from __future__ import annotations

from datetime import date, time
import re

_DAY = re.compile(r"^\s*(\d{1,2})\s*[./-]\s*(\d{1,2})\s*\.?\s*$")
_DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def parse_day(text: str | None) -> tuple[int, int] | None:
    """Return (month, day) for "DD.MM." (also "D.M", "DD-MM", "DD/MM"), else None."""
    if not text:
        return None
    match = _DAY.match(str(text))
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12 or not 1 <= day <= _DAYS_IN_MONTH[month - 1]:
        return None
    return month, day


def valid_day(text: str | None) -> bool:
    """True for an empty value or a valid day."""
    return not text or parse_day(text) is not None


def in_period(day: date, start: tuple[int, int], end: tuple[int, int]) -> bool:
    """True if the day lies in the period, both ends included; it may span the new year."""
    today = (day.month, day.day)
    if start <= end:
        return start <= today <= end
    return today >= start or today <= end


def in_quiet(start: time | None, end: time | None, now: time) -> bool:
    """True between start and end (end not included); the range may span midnight."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end

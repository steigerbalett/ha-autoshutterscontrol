"""Calendar events as morning and evening windows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, tzinfo
from typing import Any


def _parse(value: Any, tz: tzinfo) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if dt.tzinfo is None:
        # All-day events come as dates: not usable as a window
        return None
    return dt.astimezone(tz)


def calendar_windows(
    events: Iterable[Mapping[str, Any]],
    open_title: str,
    close_title: str,
    tz: tzinfo,
) -> dict[date, dict[str, tuple[time, time]]]:
    """Map days to {"up": (start, end), "down": (start, end)}.

    An event whose summary contains ``open_title`` (case-insensitive) is the
    window for the morning drive, ``close_title`` for the evening drive. The
    first matching event of a day wins; all-day events are ignored.
    """
    out: dict[date, dict[str, tuple[time, time]]] = {}
    for event in events:
        summary = str(event.get("summary", "")).lower()
        if open_title and open_title.lower() in summary:
            direction = "up"
        elif close_title and close_title.lower() in summary:
            direction = "down"
        else:
            continue
        start = _parse(event.get("start"), tz)
        end = _parse(event.get("end"), tz)
        if start is None or end is None:
            continue
        if end.date() != start.date():
            end = datetime.combine(start.date(), time(23, 59, 59), tzinfo=tz)
        out.setdefault(start.date(), {}).setdefault(
            direction, (start.time().replace(tzinfo=None), end.time().replace(tzinfo=None))
        )
    return out

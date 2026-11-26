"""Horizon of a window: where buildings and trees hide the sun.

A point is "direction:elevation" in degrees, e.g. ``220:18.5``. Between two
points the horizon is interpolated; beyond the outermost points it holds for
15 degrees, outside of that only the shading elevation range applies. The sun
is hidden while its elevation is at or below the horizon in its direction.
"""

from __future__ import annotations

import math

HOLD = 15.0  # degrees beyond the outermost points
REPLACE = 3.0  # a new point within this many degrees replaces an older one


def parse(text: str | None) -> list[tuple[float, float]]:
    """Points sorted by direction; raises ValueError on a broken entry."""
    points: list[tuple[float, float]] = []
    if not text:
        return points
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(part)
        azimuth, elevation = (float(v) for v in part.split(":", 1))
        if not (0 <= azimuth <= 360 and -10 <= elevation <= 90):
            raise ValueError(part)
        points.append((azimuth, elevation))
    return sorted(points)


def valid(text: str | None) -> bool:
    """The text can be read."""
    try:
        parse(text)
    except ValueError:
        return False
    return True


def safe_parse(text: str | None) -> list[tuple[float, float]]:
    """Points, or none if the text is broken (reported as a repair issue)."""
    try:
        return parse(text)
    except ValueError:
        return []


def fmt(points: list[tuple[float, float]]) -> str:
    """Text of the points."""
    return ", ".join(f"{a:g}:{e:g}" for a, e in sorted(points))


def add(
    points: list[tuple[float, float]], azimuth: float, elevation: float
) -> list[tuple[float, float]]:
    """Add a point (direction to whole degrees, elevation rounded up to 0.1 degrees)."""
    azimuth = round(azimuth) % 360
    elevation = math.ceil(elevation * 10) / 10
    kept = [p for p in points if abs(p[0] - azimuth) > REPLACE]
    return sorted([*kept, (float(azimuth), elevation)])


def at(points: list[tuple[float, float]], azimuth: float) -> float | None:
    """Horizon elevation in a direction (None = no horizon there)."""
    if not points:
        return None
    first, last = points[0], points[-1]
    if azimuth < first[0]:
        return first[1] if first[0] - azimuth <= HOLD else None
    if azimuth > last[0]:
        return last[1] if azimuth - last[0] <= HOLD else None
    for (a1, e1), (a2, e2) in zip(points, points[1:], strict=False):
        if a1 <= azimuth <= a2:
            if a2 == a1:
                return max(e1, e2)
            return e1 + (e2 - e1) * (azimuth - a1) / (a2 - a1)
    return last[1]


def hidden(points: list[tuple[float, float]], azimuth: float, elevation: float) -> bool:
    """The sun is behind the horizon."""
    horizon = at(points, azimuth)
    return horizon is not None and elevation <= horizon

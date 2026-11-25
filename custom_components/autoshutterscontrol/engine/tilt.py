"""Slats: tilt position per drive reason, shading steps by sun elevation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Reason of a drive -> tilt setting (suffix after "tilt_")
_BY_REASON = {
    "day_open": "open",
    "night_close": "closed",
    "ventilate": "ventilate",
    "comfort": "comfort",
    "privacy_up": "privacy",
    "privacy_down": "privacy",
    "sleep": "sleep",
    "self_defense": "closed",
    "shading": "shading",
    "heat": "shading",
}

# Named positions of the drive action -> tilt setting
_BY_NAME = {
    "open": "open",
    "closed": "closed",
    "sleep": "sleep",
    "ventilate": "ventilate",
    "comfort": "comfort",
    "shading": "shading",
    "privacy": "privacy",
}


def parse_steps(text: str | None) -> list[tuple[float, int]]:
    """Parse "elevation:tilt, ..." (up to 4 steps), sorted by elevation."""
    steps: list[tuple[float, int]] = []
    if not text:
        return steps
    for part in str(text).replace(";", ",").split(","):
        if ":" not in part:
            continue
        elevation, tilt = part.split(":", 1)
        try:
            steps.append((float(elevation), max(0, min(100, int(float(tilt))))))
        except ValueError:
            continue
    return sorted(steps)[:4]


def shading_tilt(cfg: Mapping[str, Any], elevation: float | None) -> int | None:
    """Tilt while shading: the step of the highest elevation reached, else tilt_shading."""
    steps = parse_steps(cfg["tilt_shading_steps"])
    tilt = cfg["tilt_shading"]
    if elevation is None:
        return tilt
    for step_elevation, step_tilt in steps:
        if elevation >= step_elevation:
            tilt = step_tilt
    return tilt


def tilt_for(
    cfg: Mapping[str, Any],
    reason: str | None,
    elevation: float | None = None,
    named: str | None = None,
) -> int | None:
    """Tilt position for a drive, None = leave the slats alone."""
    key = _BY_NAME.get(named) if named else _BY_REASON.get(reason or "")
    if key is None:
        return None
    if key == "shading":
        return shading_tilt(cfg, elevation)
    value = cfg[f"tilt_{key}"]
    if value is None and key == "sleep":
        value = cfg["tilt_closed"]
    return value

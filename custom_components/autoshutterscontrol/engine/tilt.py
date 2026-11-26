"""Slats: tilt position per drive reason, shading steps or angle from the sun."""

from __future__ import annotations

from collections.abc import Mapping
import math
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
    "hot_day": "shading",
    "glare": "shading",
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


def window_azimuth(cfg: Mapping[str, Any]) -> float:
    """Direction the window faces: set, else the middle of the shading azimuth range."""
    if cfg["window_azimuth"] is not None:
        return float(cfg["window_azimuth"]) % 360
    start, end = cfg["shading_azimuth_start"], cfg["shading_azimuth_end"]
    if end < start:
        end += 360
    return ((start + end) / 2) % 360


def slat_angle(ratio: float, elevation: float, azimuth: float, window: float) -> float:
    """Slat angle from horizontal (0..90 degrees) that just keeps the direct sun out.

    ``ratio`` is slat distance / slat width. The profile angle a of the sun
    (elevation projected on the plane perpendicular to the window) gives
    b = arcsin(ratio * cos a) - a. Sun behind the facade or below the
    horizon: 0 (horizontal).
    """
    gamma = (azimuth - window + 180) % 360 - 180
    if elevation <= 0 or abs(gamma) >= 90:
        return 0.0
    alpha = math.atan(math.tan(math.radians(elevation)) / math.cos(math.radians(gamma)))
    x = ratio * math.cos(alpha)
    if x >= 1:
        return 90.0
    beta = math.degrees(math.asin(x) - alpha)
    return max(0.0, min(90.0, beta))


def auto_tilt(cfg: Mapping[str, Any], elevation: float | None, azimuth: float | None) -> int | None:
    """Tilt position from the slat angle, in steps of 5 %."""
    if elevation is None or azimuth is None:
        return None
    beta = slat_angle(cfg["tilt_slat_ratio"], elevation, azimuth, window_azimuth(cfg))
    horizontal, vertical = cfg["tilt_horizontal"], cfg["tilt_vertical"]
    value = horizontal + (vertical - horizontal) * beta / 90
    value = round(value / 5) * 5
    return int(max(min(horizontal, vertical), min(max(horizontal, vertical), value)))


def shading_tilt(
    cfg: Mapping[str, Any], elevation: float | None, azimuth: float | None = None
) -> int | None:
    """Tilt while shading.

    Automatic: from the sun and the slat geometry. Otherwise the step of the
    highest elevation reached, else tilt_shading.
    """
    if cfg["tilt_auto"]:
        tilt = auto_tilt(cfg, elevation, azimuth)
        if tilt is not None:
            return tilt
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
    azimuth: float | None = None,
) -> int | None:
    """Tilt position for a drive, None = leave the slats alone."""
    key = _BY_NAME.get(named) if named else _BY_REASON.get(reason or "")
    if key is None:
        return None
    if key == "shading":
        return shading_tilt(cfg, elevation, azimuth)
    value = cfg[f"tilt_{key}"]
    if value is None and key == "sleep":
        value = cfg["tilt_closed"]
    return value

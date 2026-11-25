"""Rain, wind and frost: thresholds with hysteresis and waits in both directions.

A sensor that is unavailable keeps the last state (no drive on "unknown").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from .settings import FROST_AM, FROST_HARD, FROST_PM, FROST_SOFT

RAIN = "rain"
RAIN_WINDOW = "rain_window"
WIND = "wind"
FROST = "frost"
PROTECTIONS = (RAIN, RAIN_WINDOW, WIND, FROST)

_ON = ("on", "true", "rain", "raining", "wet")
_OFF = ("off", "false", "dry", "clear")


def as_value(raw: str | None) -> float | bool | None:
    """Sensor state as number, as on/off, or None if unusable."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in _ON:
        return True
    if text in _OFF:
        return False
    try:
        return float(text)
    except ValueError:
        return None


def above(
    value: float | bool | None, threshold: float, hysteresis: float, active: bool
) -> bool | None:
    """Value above the threshold; ends only below threshold - hysteresis. None = keep."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if active:
        return value > threshold - hysteresis
    return value > threshold


def at_least(value: float | None, threshold: float, hysteresis: float, active: bool) -> bool | None:
    """Value reaches the threshold (wind); ends only below threshold - hysteresis."""
    if value is None or isinstance(value, bool):
        return None
    if active:
        return value >= threshold - hysteresis
    return value >= threshold


def below(value: float | None, threshold: float, hysteresis: float, active: bool) -> bool | None:
    """Value at or below the threshold (frost); ends only above threshold + hysteresis."""
    if value is None or isinstance(value, bool):
        return None
    if active:
        return value <= threshold + hysteresis
    return value <= threshold


@dataclass(frozen=True)
class Protection:
    """State of one protection."""

    active: bool = False
    pending_since: datetime | None = None


def step(
    state: Protection,
    raw: bool | None,
    now: datetime,
    delay_start: int,
    delay_end: int,
) -> Protection:
    """Apply the waits (minutes) before a change is taken over."""
    if raw is None or raw == state.active:
        return Protection(state.active, None)
    since = state.pending_since or now
    delay = timedelta(minutes=delay_start if raw else delay_end)
    if now - since >= delay:
        return Protection(raw, None)
    return Protection(state.active, since)


def frost_effect(cfg: Mapping[str, Any], frost: bool, local_time: time) -> tuple[bool, bool]:
    """(block drives, soft: closed -> frost position) for the frost mode."""
    if not frost:
        return False, False
    mode = cfg["frost_mode"]
    if mode == FROST_HARD:
        return True, False
    if mode == FROST_AM:
        return local_time < time(12, 0), False
    if mode == FROST_PM:
        return local_time >= time(12, 0), False
    if mode == FROST_SOFT:
        return False, cfg["pos_frost"] is not None
    return False, False

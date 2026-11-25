"""Shading: conditions with hysteresis, start/end lists, state machine, heat protection.

State machine (as in ASC): out -> in_reserved -> in -> out_reserved -> out.
The cover is shaded in the states "in" and "out_reserved".

Conditions are only used when they are configured (sensor set, threshold
set). Start: all of the "must" list and, if the "any" list has configured
conditions, at least one of them. While shading, the same lists are checked
with the end thresholds (hysteresis); a configured sensor that is unavailable
then keeps its last result instead of ending the shading.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from .settings import (
    COND_AZIMUTH,
    COND_BRIGHTNESS,
    COND_ELEVATION,
    COND_FORECAST,
    COND_SENSOR,
    COND_TEMP_IN,
    COND_TEMP_OUT,
    COND_WEATHER,
)

OUT = "out"
IN_RESERVED = "in_reserved"
IN = "in"
OUT_RESERVED = "out_reserved"
SHADING_STATES = (OUT, IN_RESERVED, IN, OUT_RESERVED)
SHADED = frozenset({IN, OUT_RESERVED})

SUN_CONDITIONS = frozenset({COND_AZIMUTH, COND_ELEVATION})


@dataclass(frozen=True)
class Inputs:
    """Measured values for the shading conditions (None = unavailable)."""

    azimuth: float | None = None
    elevation: float | None = None
    brightness: float | None = None
    temp_out: float | None = None
    temp_in: float | None = None
    forecast: float | None = None
    weather: str | None = None
    sensor: bool | None = None


@dataclass(frozen=True)
class Configured:
    """Which conditions have a source."""

    brightness: bool = False
    temp_out: bool = False
    temp_in: bool = False
    forecast: bool = False
    weather: bool = False
    sensor: bool = False


def in_azimuth(azimuth: float, start: float, end: float) -> bool:
    """Azimuth between start and end (clockwise, also across north)."""
    if start <= end:
        return start <= azimuth <= end
    return azimuth >= start or azimuth <= end


def _threshold(value: float | None, minimum: float, hysteresis: float, active: bool) -> bool | None:
    if value is None:
        return None
    return value >= (minimum - hysteresis if active else minimum)


def conditions(
    cfg: Mapping[str, Any], inputs: Inputs, configured: Configured, active: bool
) -> dict[str, bool | None]:
    """Result per condition; None = not configured. ``active`` uses the end thresholds."""
    out: dict[str, bool | None] = {}
    if inputs.azimuth is None:
        out[COND_AZIMUTH] = False
    else:
        out[COND_AZIMUTH] = in_azimuth(
            inputs.azimuth, cfg["shading_azimuth_start"], cfg["shading_azimuth_end"]
        )
    if inputs.elevation is None:
        out[COND_ELEVATION] = False
    else:
        out[COND_ELEVATION] = (
            cfg["shading_elevation_min"] <= inputs.elevation <= cfg["shading_elevation_max"]
        )
    hyst = cfg["shading_temp_hysteresis"]
    out[COND_BRIGHTNESS] = None
    if configured.brightness:
        if inputs.brightness is None:
            out[COND_BRIGHTNESS] = None if active else False
        else:
            limit = cfg["shading_brightness_end"] if active else cfg["shading_brightness_start"]
            out[COND_BRIGHTNESS] = inputs.brightness >= limit
    for key, value, enabled, minimum in (
        (COND_TEMP_OUT, inputs.temp_out, configured.temp_out, cfg["shading_temp_out_min"]),
        (COND_TEMP_IN, inputs.temp_in, configured.temp_in, cfg["shading_temp_in_min"]),
        (COND_FORECAST, inputs.forecast, configured.forecast, cfg["shading_forecast_min"]),
    ):
        if not enabled or minimum is None:
            out[key] = None
            continue
        result = _threshold(value, minimum, hyst, active)
        out[key] = (None if active else False) if result is None else result
    out[COND_WEATHER] = None
    if configured.weather and cfg["shading_weather_conditions"]:
        if inputs.weather is None:
            out[COND_WEATHER] = None if active else False
        else:
            out[COND_WEATHER] = inputs.weather in cfg["shading_weather_conditions"]
    out[COND_SENSOR] = None
    if configured.sensor:
        if inputs.sensor is None:
            out[COND_SENSOR] = None if active else False
        else:
            out[COND_SENSOR] = inputs.sensor
    return out


def combine(cfg: Mapping[str, Any], results: Mapping[str, bool | None]) -> bool:
    """Start/still condition from the must and the any list."""
    must = set(cfg["shading_must"])
    if not all(results[c] for c in must if results.get(c) is not None):
        return False
    anys = [results[c] for c in cfg["shading_any"] if c not in must and results.get(c) is not None]
    return not anys or any(anys)


def sun_left(results: Mapping[str, bool | None]) -> bool:
    """The sun is no longer in the area of the window."""
    return results.get(COND_AZIMUTH) is False or results.get(COND_ELEVATION) is False


def in_time_window(cfg: Mapping[str, Any], now_time: time) -> bool:
    """Shading only between the configured times (ASC_Shading_BetweenTheTime)."""
    start = cfg["shading_time_start"]
    end = cfg["shading_time_end"]
    if start is None and end is None:
        return True
    start = start or time(0, 0)
    end = end or time(23, 59, 59)
    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def step(
    cfg: Mapping[str, Any],
    state: str,
    since: datetime | None,
    now: datetime,
    *,
    start_ok: bool,
    still_ok: bool,
    left: bool,
    allowed: bool = True,
) -> tuple[str, datetime | None]:
    """Next state of the state machine."""
    if not allowed:
        return OUT, None
    delay_start = timedelta(minutes=cfg["shading_delay_start"])
    delay_end = timedelta(minutes=cfg["shading_delay_end"])
    end_now = left and cfg["shading_end_sun_leaves"]
    if state == OUT:
        if not start_ok:
            return OUT, since
        if not delay_start:
            return IN, now
        return IN_RESERVED, now
    if state == IN_RESERVED:
        if not start_ok:
            return OUT, now
        if since is None or now - since >= delay_start:
            return IN, now
        return IN_RESERVED, since
    if state == IN:
        if still_ok:
            return IN, since
        if end_now or not delay_end:
            return OUT, now
        return OUT_RESERVED, now
    # OUT_RESERVED
    if still_ok:
        return IN, now
    if end_now or since is None or now - since >= delay_end:
        return OUT, now
    return OUT_RESERVED, since


def heat_active(cfg: Mapping[str, Any], temp_out: float | None, latched: bool) -> bool:
    """Heat protection: shade from a temperature on, kept until the evening."""
    limit = cfg["heat_protection_temp"]
    if limit is None:
        return False
    if latched:
        return True
    return temp_out is not None and temp_out >= limit


def average(samples: list[tuple[datetime, float]], now: datetime, minutes: int) -> float | None:
    """Mean of the samples of the last ``minutes`` (0 = the newest sample)."""
    if not samples:
        return None
    if minutes <= 0:
        return samples[-1][1]
    start = now - timedelta(minutes=minutes)
    values = [v for t, v in samples if t >= start]
    if not values:
        return samples[-1][1]
    return sum(values) / len(values)

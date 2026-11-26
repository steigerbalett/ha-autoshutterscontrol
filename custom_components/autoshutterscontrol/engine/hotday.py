"""Hot day: the morning drive goes straight to the shading position.

On a day with a hot (and sunny) forecast the cover does not open completely
in the morning when the sun will still shine on the window today. Nothing
happens at night: the flat may cool down as much as possible.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from .horizon import hidden
from .shading import in_azimuth
from .sun import SunCalculator

STEP = timedelta(minutes=10)


def is_hot(cfg: Mapping[str, Any], forecast: float | None, condition: str | None) -> bool:
    """Forecast maximum of today at or above the limit (and a sunny forecast)."""
    if not cfg["hot_day"] or forecast is None or forecast < cfg["hot_day_temp"]:
        return False
    return not (
        cfg["hot_day_sunny"]
        and condition is not None
        and condition not in cfg["shading_weather_conditions"]
    )


def sun_on_window(
    cfg: Mapping[str, Any],
    sun: SunCalculator,
    start: datetime,
    end: datetime,
    horizon: list[tuple[float, float]] | None = None,
) -> bool:
    """Does the sun shine on the window (azimuth and elevation range, horizon) between start and end?"""
    when = start
    while when <= end:
        elevation = sun.elevation(when)
        azimuth = sun.azimuth(when)
        if (
            cfg["shading_elevation_min"] <= elevation <= cfg["shading_elevation_max"]
            and in_azimuth(azimuth, cfg["shading_azimuth_start"], cfg["shading_azimuth_end"])
            and not hidden(horizon or [], azimuth, elevation)
        ):
            return True
        when += STEP
    return False

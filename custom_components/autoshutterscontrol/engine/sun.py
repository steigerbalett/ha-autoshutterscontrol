"""Sun times with the twilight types of ASC (REAL, CIVIL, NAUTIC, ASTRONOMIC, HORIZON).

Uses ``astral`` directly; no Home Assistant imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from astral import Observer
from astral.sun import SunDirection, dawn, dusk, elevation, sunrise, sunset, time_at_elevation

from .settings import (
    TWILIGHT_ASTRONOMICAL,
    TWILIGHT_CIVIL,
    TWILIGHT_HORIZON,
    TWILIGHT_NAUTICAL,
    TWILIGHT_REAL,
)

_DEPRESSION = {
    TWILIGHT_CIVIL: 6.0,
    TWILIGHT_NAUTICAL: 12.0,
    TWILIGHT_ASTRONOMICAL: 18.0,
}


@dataclass(frozen=True)
class Location:
    """Observer location."""

    latitude: float
    longitude: float
    elevation: float
    timezone: tzinfo


class SunCalculator:
    """Calculate morning and evening sun events."""

    def __init__(self, location: Location) -> None:
        self.location = location
        self._observer = Observer(location.latitude, location.longitude, location.elevation)

    def morning(self, day: date, twilight: str, horizon: float = 0.0) -> datetime | None:
        """Return the morning event, or None if it does not happen on that day."""
        tz = self.location.timezone
        try:
            if twilight == TWILIGHT_REAL:
                return sunrise(self._observer, day, tzinfo=tz)
            if twilight == TWILIGHT_HORIZON:
                return time_at_elevation(
                    self._observer, horizon, day, SunDirection.RISING, tzinfo=tz
                )
            return dawn(self._observer, day, depression=_DEPRESSION[twilight], tzinfo=tz)
        except ValueError:
            return None

    def evening(self, day: date, twilight: str, horizon: float = 0.0) -> datetime | None:
        """Return the evening event, or None if it does not happen on that day."""
        tz = self.location.timezone
        try:
            if twilight == TWILIGHT_REAL:
                return sunset(self._observer, day, tzinfo=tz)
            if twilight == TWILIGHT_HORIZON:
                return time_at_elevation(
                    self._observer, horizon, day, SunDirection.SETTING, tzinfo=tz
                )
            return dusk(self._observer, day, depression=_DEPRESSION[twilight], tzinfo=tz)
        except ValueError:
            return None

    def elevation(self, when: datetime) -> float:
        """Sun elevation in degrees at a moment."""
        return float(elevation(self._observer, when))

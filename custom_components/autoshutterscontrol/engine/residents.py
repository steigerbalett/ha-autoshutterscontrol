"""Residents: house and room status from several sources, presence modes, self defense.

Every source entity is mapped to one of the ASC states. Several sources are
combined by the ASC priority asleep > gotosleep > awoken > home > absent > gone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .settings import (
    PRESENCE_ABSENT,
    PRESENCE_ALWAYS,
    PRESENCE_HOME,
    RES_ABSENT,
    RES_ASLEEP,
    RES_AWOKEN,
    RES_GONE,
    RES_GOTOSLEEP,
    RES_HOME,
    RESIDENT_STATES,
    SELF_DEFENSE_ABSENT,
    SELF_DEFENSE_GONE,
)

SLEEPING = frozenset({RES_ASLEEP, RES_GOTOSLEEP})
PRESENT = frozenset({RES_ASLEEP, RES_GOTOSLEEP, RES_AWOKEN, RES_HOME})
AWAY = frozenset({RES_ABSENT, RES_GONE})

_ALARM = {
    "armed_away": RES_GONE,
    "armed_vacation": RES_GONE,
    "armed_night": RES_ASLEEP,
    "armed_home": RES_HOME,
    "armed_custom_bypass": RES_HOME,
    "disarmed": RES_HOME,
}


@dataclass(frozen=True)
class Source:
    """State of one source entity."""

    entity_id: str
    state: str
    last_changed: datetime | None = None


def parse_map(text: str | None) -> dict[str, str]:
    """Parse "value:state, value:state" (own mapping of source values)."""
    out: dict[str, str] = {}
    if not text:
        return out
    for part in str(text).replace(";", ",").split(","):
        if ":" not in part:
            continue
        value, state = part.rsplit(":", 1)
        value = value.strip().lower()
        state = state.strip().lower()
        if value and state in RESIDENT_STATES:
            out[value] = state
    return out


def map_source(
    source: Source,
    own_map: Mapping[str, str],
    now: datetime,
    gone_hours: int,
) -> str | None:
    """ASC state of one source, or None if it says nothing."""
    domain = source.entity_id.split(".", 1)[0]
    value = str(source.state).strip().lower()
    if value in own_map:
        return own_map[value]
    if value in RESIDENT_STATES:
        return value
    if domain in ("person", "device_tracker"):
        if value == "home":
            return RES_HOME
        if (
            gone_hours
            and source.last_changed is not None
            and now - source.last_changed >= timedelta(hours=gone_hours)
        ):
            return RES_GONE
        return RES_ABSENT
    if domain == "zone":
        try:
            return RES_HOME if float(value) >= 1 else RES_ABSENT
        except ValueError:
            return None
    if domain in ("binary_sensor", "input_boolean"):
        # Bed or sleep sensor
        if value == "on":
            return RES_ASLEEP
        if value == "off":
            return RES_AWOKEN
        return None
    if domain == "alarm_control_panel":
        return _ALARM.get(value)
    return None


def combine(states: Iterable[str | None]) -> str | None:
    """Combine several states by ASC priority."""
    present = [s for s in states if s is not None]
    if not present:
        return None
    return min(present, key=RESIDENT_STATES.index)


def status(
    sources: Iterable[Source], own_map: Mapping[str, str], now: datetime, gone_hours: int
) -> str | None:
    """Status of a group of sources (house or room)."""
    return combine(map_source(s, own_map, now, gone_hours) for s in sources)


def presence_allows(mode: str, house: str | None) -> bool:
    """ASC_Mode_Up / _Down / Shading_Mode: always, home, absent, off."""
    if mode == PRESENCE_ALWAYS:
        return True
    if house is None:
        # No sources configured: only "off" blocks
        return mode in (PRESENCE_HOME, PRESENCE_ABSENT)
    if mode == PRESENCE_HOME:
        return house in PRESENT
    if mode == PRESENCE_ABSENT:
        return house in AWAY
    return False


def self_defense_due(
    cfg: Mapping[str, Any],
    house: str | None,
    absent_since: datetime | None,
    now: datetime,
) -> bool:
    """Is the house empty long enough for self defense?"""
    mode = cfg["self_defense_mode"]
    if house == RES_GONE and mode in (SELF_DEFENSE_GONE, SELF_DEFENSE_ABSENT):
        return True
    if house == RES_ABSENT and mode == SELF_DEFENSE_ABSENT:
        return absent_since is not None and now - absent_since >= timedelta(
            minutes=cfg["self_defense_delay"]
        )
    return False

"""The arbiter: every function reports a wish, the arbiter picks one drive.

Priorities follow section 5 of the concept. Stage 1 knows the blocks of
priority 0, the manual override (8) and the schedule (14); later stages add
their wishes with the priorities below.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .settings import KIND_CLOSE, KIND_OPEN

# Priorities (lower wins)
PRIO_FORCE = 1
PRIO_RAIN_WINDOW = 2
PRIO_WIND_RAIN = 3
PRIO_FROST = 4
PRIO_SELF_DEFENSE = 5
PRIO_PARTY = 6
PRIO_LOCKOUT = 7
PRIO_OVERRIDE = 8
PRIO_TRIGGER = 9
PRIO_WINDOW = 10
PRIO_RESIDENTS = 11
PRIO_SHADING = 12
PRIO_PRIVACY = 13
PRIO_SCHEDULE = 14

# Triggers (why the arbiter is asked)
TRIGGER_SCHEDULE_UP = "schedule_up"
TRIGGER_SCHEDULE_DOWN = "schedule_down"
TRIGGER_APPLY_TARGET = "apply_target"
TRIGGER_OVERRIDE_END = "override_end"
TRIGGER_RESUME = "resume"
SCHEDULE_TRIGGERS = frozenset({TRIGGER_SCHEDULE_UP, TRIGGER_SCHEDULE_DOWN})

# Reasons of a wish (stored as keys, translated only for display)
REASON_DAY_OPEN = "day_open"
REASON_NIGHT_CLOSE = "night_close"
REASON_SERVICE = "service"
REASON_MANUAL = "manual"

# Why nothing was driven
BLOCK_AUTOMATIC_OFF = "automatic_off"
BLOCK_PAUSED = "paused"
BLOCK_UNAVAILABLE = "unavailable"
BLOCK_MOVING = "moving"
BLOCK_NO_WISH = "no_wish"
BLOCK_OVERRIDE = "manual_override"
BLOCK_DONE_BY_MANUAL = "done_by_manual"
BLOCK_DIRECTION = "direction"
BLOCK_AT_TARGET = "at_target"


@dataclass(frozen=True)
class Wish:
    """What one function would like the cover to do."""

    priority: int
    source: str
    kind: str
    position: int
    reason: str
    bypass_rules: bool = False


@dataclass(frozen=True)
class Situation:
    """State of the cover and the switches at decision time."""

    trigger: str
    automatic: bool = True
    paused: bool = False
    available: bool = True
    moving: bool = False
    current_position: float | None = None
    override_active: bool = False
    done_today: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Decision:
    """Result of the arbiter."""

    trigger: str
    drive: bool
    kind: str | None = None
    position: int | None = None
    reason: str | None = None
    source: str | None = None
    blocked_by: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict for diagnostics and events."""
        return {
            "trigger": self.trigger,
            "drive": self.drive,
            "kind": self.kind,
            "position": self.position,
            "reason": self.reason,
            "source": self.source,
            "blocked_by": self.blocked_by,
        }


def schedule_wish(
    cfg: Mapping[str, Any],
    is_day: bool,
    *,
    morning_enabled: bool = True,
    evening_enabled: bool = True,
) -> Wish | None:
    """Wish of the schedule: open by day, closed by night."""
    if is_day:
        if not morning_enabled:
            return None
        return Wish(PRIO_SCHEDULE, "schedule", KIND_OPEN, cfg["pos_open"], REASON_DAY_OPEN)
    if not evening_enabled:
        return None
    return Wish(PRIO_SCHEDULE, "schedule", KIND_CLOSE, cfg["pos_closed"], REASON_NIGHT_CLOSE)


def _blocked(situation: Situation, wish: Wish | None, block: str) -> Decision:
    return Decision(
        trigger=situation.trigger,
        drive=False,
        kind=wish.kind if wish else None,
        position=wish.position if wish else None,
        reason=wish.reason if wish else None,
        source=wish.source if wish else None,
        blocked_by=block,
    )


def decide(cfg: Mapping[str, Any], situation: Situation, wishes: Iterable[Wish | None]) -> Decision:
    """Pick the drive for a situation.

    The target (kind, position, reason) is reported even when nothing is
    driven, so the cover always knows its target state.
    """
    candidates = sorted((w for w in wishes if w is not None), key=lambda w: w.priority)
    wish = candidates[0] if candidates else None

    # Priority 0: nothing moves, the target is still tracked
    if not situation.automatic:
        return _blocked(situation, wish, BLOCK_AUTOMATIC_OFF)
    if situation.paused:
        return _blocked(situation, wish, BLOCK_PAUSED)
    if not situation.available:
        return _blocked(situation, wish, BLOCK_UNAVAILABLE)
    if situation.moving:
        return _blocked(situation, wish, BLOCK_MOVING)
    if wish is None:
        return _blocked(situation, None, BLOCK_NO_WISH)

    if not wish.bypass_rules:
        if (
            situation.override_active
            and wish.priority > PRIO_OVERRIDE
            and wish.kind in cfg["override_blocks"]
        ):
            return _blocked(situation, wish, BLOCK_OVERRIDE)
        if (
            situation.trigger in SCHEDULE_TRIGGERS
            and wish.source == "schedule"
            and wish.kind in situation.done_today
        ):
            return _blocked(situation, wish, BLOCK_DONE_BY_MANUAL)

    current = situation.current_position
    tol = cfg["tolerance"]
    if current is not None:
        if abs(current - wish.position) <= tol:
            return _blocked(situation, wish, BLOCK_AT_TARGET)
        if not wish.bypass_rules:
            if wish.kind == KIND_OPEN and cfg["open_never_down"] and current > wish.position:
                return _blocked(situation, wish, BLOCK_DIRECTION)
            if wish.kind == KIND_CLOSE and cfg["close_never_up"] and current < wish.position:
                return _blocked(situation, wish, BLOCK_DIRECTION)

    return Decision(
        trigger=situation.trigger,
        drive=True,
        kind=wish.kind,
        position=wish.position,
        reason=wish.reason,
        source=wish.source,
    )

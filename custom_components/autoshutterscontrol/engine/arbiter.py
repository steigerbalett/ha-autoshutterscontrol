"""The arbiter: every function reports a wish, the arbiter picks one drive.

Priorities follow section 5 of the concept (lower wins): blocks of priority 0
(automatic, pause, extra condition, availability), force (1), rain with an
open window (2), wind and rain (3), frost (4), self defense (5), party and
advent (6), lock-out (7), manual override (8), external trigger (9), window
(10), residents (11), shading (12), privacy (13) and schedule (14).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from .settings import KIND_CLOSE, KIND_OPEN, KIND_SHADING, KIND_TRIGGER, KIND_VENTILATE

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
TRIGGER_WINDOW = "window"
TRIGGER_WINDOW_CLOSED = "window_closed"
TRIGGER_PRIVACY = "privacy"
TRIGGER_RESIDENTS = "residents"
TRIGGER_SHADING = "shading"
TRIGGER_SHADING_END = "shading_end"
TRIGGER_PROTECTION = "protection"
TRIGGER_FORCE = "force"
TRIGGER_EXTERNAL = "external"
TRIGGER_RELEASE = "release"
TRIGGER_RECOVERY = "recovery"
TRIGGER_PROFILE = "profile"
SCHEDULE_TRIGGERS = frozenset({TRIGGER_SCHEDULE_UP, TRIGGER_SCHEDULE_DOWN, TRIGGER_RECOVERY})

# Reasons of a wish (stored as keys, translated only for display)
REASON_DAY_OPEN = "day_open"
REASON_NIGHT_CLOSE = "night_close"
REASON_SERVICE = "service"
REASON_MANUAL = "manual"
REASON_VENTILATE = "ventilate"
REASON_COMFORT = "comfort"
REASON_PRIVACY_UP = "privacy_up"
REASON_PRIVACY_DOWN = "privacy_down"
REASON_WINDOW_RETURN = "window_return"
REASON_SLEEP = "sleep"
REASON_SELF_DEFENSE = "self_defense"
REASON_SHADING = "shading"
REASON_HEAT = "heat"
REASON_FORCE = "force"
REASON_RAIN = "rain"
REASON_RAIN_WINDOW = "rain_window"
REASON_WIND = "wind"
REASON_TRIGGER = "trigger"
REASON_WIGGLE = "wiggle"
# Drives that are undone when their cause ends
TEMPORARY_REASONS = frozenset(
    {REASON_FORCE, REASON_RAIN, REASON_RAIN_WINDOW, REASON_WIND, REASON_TRIGGER, REASON_WIGGLE}
)

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
BLOCK_LOCKOUT = "lockout"
BLOCK_NOT_SHADED = "not_shaded"
BLOCK_FROST = "frost"
BLOCK_PARTY = "party"
BLOCK_ADVENT = "advent"
BLOCK_CONDITION = "condition"
# Blocks that mean "deliberately not driven" (logbook)
LOGGED_BLOCKS = frozenset(
    {
        BLOCK_AUTOMATIC_OFF,
        BLOCK_PAUSED,
        BLOCK_UNAVAILABLE,
        BLOCK_OVERRIDE,
        BLOCK_DONE_BY_MANUAL,
        BLOCK_DIRECTION,
        BLOCK_LOCKOUT,
        BLOCK_NOT_SHADED,
        BLOCK_FROST,
        BLOCK_PARTY,
        BLOCK_ADVENT,
        BLOCK_CONDITION,
    }
)
BLOCKS = (
    BLOCK_AUTOMATIC_OFF,
    BLOCK_PAUSED,
    BLOCK_UNAVAILABLE,
    BLOCK_MOVING,
    BLOCK_NO_WISH,
    BLOCK_OVERRIDE,
    BLOCK_DONE_BY_MANUAL,
    BLOCK_DIRECTION,
    BLOCK_AT_TARGET,
    BLOCK_LOCKOUT,
    BLOCK_NOT_SHADED,
    BLOCK_FROST,
    BLOCK_PARTY,
    BLOCK_ADVENT,
    BLOCK_CONDITION,
)


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
    lockout: bool = False
    lockout_hard: bool = False
    done_today: frozenset[str] = field(default_factory=frozenset)
    frost_block: bool = False
    frost_soft: bool = False
    party: bool = False
    advent: bool = False
    condition_all: bool = True
    # Drive kinds whose extra condition is false
    blocked_kinds: frozenset[str] = field(default_factory=frozenset)
    # The last drive was temporary (force, rain, wind, trigger, wiggle): going back
    # to the target is not limited by the direction rules
    after_temporary: bool = False


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


def privacy_wish(
    cfg: Mapping[str, Any],
    phase: str | None,
    *,
    morning_enabled: bool = True,
    evening_enabled: bool = True,
) -> Wish | None:
    """Privacy before the morning drive (partly open) or before the evening drive."""
    if phase == REASON_PRIVACY_UP and morning_enabled:
        position = cfg["pos_privacy_up"]
        if position is None:
            position = cfg["pos_privacy"]
        return Wish(PRIO_PRIVACY, "privacy", KIND_OPEN, position, REASON_PRIVACY_UP)
    if phase == REASON_PRIVACY_DOWN and evening_enabled:
        return Wish(PRIO_PRIVACY, "privacy", KIND_CLOSE, cfg["pos_privacy"], REASON_PRIVACY_DOWN)
    return None


def window_wish(
    window: tuple[int, str] | None,
    base: Wish | None,
    current: float | None,
    trigger: str,
) -> Wish | None:
    """Ventilation/comfort for an open or tilted window.

    Wanted when the target of the lower priorities is below the ventilation
    position, or when the window was just opened and the cover is below it.
    """
    if window is None:
        return None
    position, reason = window
    below_target = base is not None and base.position < position
    below_now = trigger == TRIGGER_WINDOW and current is not None and current < position
    if not (below_target or below_now):
        return None
    return Wish(PRIO_WINDOW, "window", KIND_VENTILATE, position, reason)


def sleep_position(cfg: Mapping[str, Any]) -> int:
    """Position while residents sleep (sleep position, else closed)."""
    position = cfg["pos_sleep"]
    return cfg["pos_closed"] if position is None else position


def residents_wish(cfg: Mapping[str, Any], sleeping: bool) -> Wish | None:
    """Residents asleep: close (to the sleep position)."""
    if not sleeping or not cfg["sleep_close"]:
        return None
    return Wish(PRIO_RESIDENTS, "residents", KIND_CLOSE, sleep_position(cfg), REASON_SLEEP)


def self_defense_wish(cfg: Mapping[str, Any], active: bool) -> Wish | None:
    """Nobody at home: close."""
    if not active:
        return None
    return Wish(
        PRIO_SELF_DEFENSE, "self_defense", KIND_CLOSE, cfg["pos_closed"], REASON_SELF_DEFENSE
    )


def shading_position(cfg: Mapping[str, Any], alternative: bool) -> int:
    """Shading position, the alternative one while its entity is on."""
    if alternative and cfg["pos_shading_alt"] is not None:
        return cfg["pos_shading_alt"]
    return cfg["pos_shading"]


def shading_wish(
    cfg: Mapping[str, Any], shaded: bool, heat: bool = False, alternative: bool = False
) -> Wish | None:
    """Shading (sun conditions met, or heat protection)."""
    if not (shaded or heat):
        return None
    reason = REASON_SHADING if shaded else REASON_HEAT
    return Wish(PRIO_SHADING, "shading", KIND_SHADING, shading_position(cfg, alternative), reason)


_FORCE = {
    "close": (KIND_CLOSE, "pos_closed"),
    "open": (KIND_OPEN, "pos_open"),
    "ventilate": (KIND_VENTILATE, "pos_ventilate"),
    "shading": (KIND_SHADING, "pos_shading"),
}


def force_wish(cfg: Mapping[str, Any], force: str | None) -> Wish | None:
    """Force entity on: drive without any further check."""
    if force not in _FORCE:
        return None
    kind, key = _FORCE[force]
    return Wish(PRIO_FORCE, "force", kind, cfg[key], REASON_FORCE, bypass_rules=True)


def rain_window_wish(cfg: Mapping[str, Any], active: bool, lockout: bool) -> Wish | None:
    """Rain with an open or tilted window: close (water protection).

    With lock-out protection the cover only goes down to the ventilation
    position, unless water protection is set to win over the lock-out.
    """
    if not active:
        return None
    position = cfg["pos_rain_window"]
    if lockout and not cfg["rain_window_over_lockout"]:
        position = max(position, cfg["pos_ventilate"])
    return Wish(PRIO_RAIN_WINDOW, "rain_window", KIND_CLOSE, position, REASON_RAIN_WINDOW)


def weather_wishes(cfg: Mapping[str, Any], wind: bool, rain: bool) -> list[Wish]:
    """Wind and rain protection position."""
    out = []
    if wind:
        out.append(Wish(PRIO_WIND_RAIN, "wind", KIND_CLOSE, cfg["pos_wind"], REASON_WIND))
    if rain:
        out.append(Wish(PRIO_WIND_RAIN, "rain", KIND_CLOSE, cfg["pos_rain"], REASON_RAIN))
    return out


def trigger_wish(position: int | None) -> Wish | None:
    """External trigger active: its position."""
    if position is None:
        return None
    return Wish(PRIO_TRIGGER, "trigger", KIND_TRIGGER, position, REASON_TRIGGER)


def build_wishes(
    cfg: Mapping[str, Any],
    *,
    trigger: str,
    is_day: bool,
    privacy_phase: str | None = None,
    window: tuple[int, str] | None = None,
    current: float | None = None,
    morning_enabled: bool = True,
    evening_enabled: bool = True,
    sleeping: bool = False,
    self_defense: bool = False,
    shaded: bool = False,
    heat: bool = False,
    shading_alt: bool = False,
    force: str | None = None,
    rain_window: bool = False,
    wind: bool = False,
    rain: bool = False,
    lockout: bool = False,
    trigger_pos: int | None = None,
) -> list[Wish]:
    """All wishes, from force down to the schedule.

    ``morning_enabled``/``evening_enabled`` include the presence modes.
    """
    defense = self_defense_wish(cfg, self_defense)
    sched = schedule_wish(
        cfg,
        is_day,
        morning_enabled=morning_enabled and not (sleeping and not cfg["sleep_allow_open"]),
        evening_enabled=evening_enabled,
    )
    priv = privacy_wish(
        cfg, privacy_phase, morning_enabled=morning_enabled, evening_enabled=evening_enabled
    )
    res = residents_wish(cfg, sleeping)
    shade = None
    if is_day and (not sleeping or cfg["sleep_allow_shading"]):
        shade = shading_wish(cfg, shaded, heat, shading_alt)
    base = res or shade or priv or sched
    win = None
    if not sleeping or cfg["sleep_allow_ventilate"]:
        win = window_wish(window, base, current, trigger)
    top = [
        force_wish(cfg, force),
        rain_window_wish(cfg, rain_window, lockout),
        *weather_wishes(cfg, wind, rain),
        defense,
        trigger_wish(trigger_pos),
    ]
    return [w for w in (*top, win, res, shade, priv, sched) if w is not None]


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
    if (
        wish is not None
        and situation.frost_soft
        and not wish.bypass_rules
        and wish.priority > PRIO_FROST
        and wish.kind == KIND_CLOSE
        and cfg["pos_frost"] is not None
        and wish.position < cfg["pos_frost"]
    ):
        # Soft frost protection: do not close completely
        wish = replace(wish, position=cfg["pos_frost"])

    # Priority 0: nothing moves, the target is still tracked (force functions do)
    forced = wish is not None and wish.priority == PRIO_FORCE
    if not situation.automatic and not forced:
        return _blocked(situation, wish, BLOCK_AUTOMATIC_OFF)
    if situation.paused and not forced:
        return _blocked(situation, wish, BLOCK_PAUSED)
    if not situation.available:
        return _blocked(situation, wish, BLOCK_UNAVAILABLE)
    if situation.moving:
        return _blocked(situation, wish, BLOCK_MOVING)
    if wish is None:
        return _blocked(situation, None, BLOCK_NO_WISH)
    # Force and the protections ignore extra conditions and direction limits
    protective = wish.priority <= PRIO_SELF_DEFENSE
    if (
        not wish.bypass_rules
        and not protective
        and (not situation.condition_all or wish.kind in situation.blocked_kinds)
    ):
        return _blocked(situation, wish, BLOCK_CONDITION)

    if situation.trigger == TRIGGER_WINDOW and wish.source not in ("window", "rain_window"):
        # Opening a window only ever starts a ventilation drive
        return _blocked(situation, wish, BLOCK_NO_WISH)
    if situation.trigger == TRIGGER_SHADING and wish.source != "shading":
        # The start of shading only ever starts a shading drive
        return _blocked(situation, wish, BLOCK_NO_WISH)

    if not wish.bypass_rules:
        if situation.frost_block and wish.priority > PRIO_FROST:
            return _blocked(situation, wish, BLOCK_FROST)
        if situation.party and wish.priority > PRIO_PARTY:
            return _blocked(situation, wish, BLOCK_PARTY)
        if situation.advent and wish.kind == KIND_CLOSE and wish.priority > PRIO_PARTY:
            return _blocked(situation, wish, BLOCK_ADVENT)
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
    if situation.trigger == TRIGGER_SHADING_END and not wish.bypass_rules:
        if not cfg["shading_end_open"]:
            return _blocked(situation, wish, BLOCK_NO_WISH)
        shading_positions = [
            p for p in (cfg["pos_shading"], cfg["pos_shading_alt"]) if p is not None
        ]
        if current is not None and not any(abs(current - p) <= tol for p in shading_positions):
            # Moved away from the shading position (by hand, window ...): leave it
            return _blocked(situation, wish, BLOCK_NOT_SHADED)
    if (
        situation.lockout
        and not wish.bypass_rules
        and wish.source != "rain_window"
        and (situation.lockout_hard or wish.priority > PRIO_LOCKOUT)
    ):
        if (current is None and wish.kind == KIND_CLOSE) or (
            current is not None and wish.position < current - tol
        ):
            return _blocked(situation, wish, BLOCK_LOCKOUT)
    if current is not None:
        if abs(current - wish.position) <= tol:
            return _blocked(situation, wish, BLOCK_AT_TARGET)
        if (
            not wish.bypass_rules
            and not protective
            and not situation.after_temporary
            # A profile switch moves to the new target in any direction
            and situation.trigger != TRIGGER_PROFILE
        ):
            if (
                wish.kind == KIND_VENTILATE
                and situation.trigger == TRIGGER_WINDOW
                and cfg["ventilate_only_up"]
                and current > wish.position
            ):
                return _blocked(situation, wish, BLOCK_DIRECTION)
            if wish.kind == KIND_OPEN and cfg["open_never_down"] and current > wish.position:
                return _blocked(situation, wish, BLOCK_DIRECTION)
            if wish.kind == KIND_CLOSE and cfg["close_never_up"] and current < wish.position:
                return _blocked(situation, wish, BLOCK_DIRECTION)
            if (
                wish.kind == KIND_SHADING
                and cfg["shading_only_down"]
                and current < wish.position
                # The morning opening (or catching it up) goes to the shading position
                and situation.trigger not in (TRIGGER_SCHEDULE_UP, TRIGGER_RECOVERY)
            ):
                return _blocked(situation, wish, BLOCK_DIRECTION)

    return Decision(
        trigger=situation.trigger,
        drive=True,
        kind=wish.kind,
        position=wish.position,
        reason=wish.reason,
        source=wish.source,
    )

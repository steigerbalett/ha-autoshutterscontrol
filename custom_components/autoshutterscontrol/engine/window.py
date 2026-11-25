"""Window contacts: state, ventilation, comfort, lock-out protection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .settings import LOCKOUT_OFF, WINDOW_CLOSED, WINDOW_OPEN, WINDOW_TILTED

_OFF_STATES = ("off", "closed", "false", "0")


def window_state(
    cfg: Mapping[str, Any],
    open_contact: str | None,
    tilted_contact: str | None,
    three_state: str | None,
) -> str | None:
    """Combine the contacts: open wins over tilted. None = no usable contact."""
    states: list[str] = []
    if three_state is not None:
        value = three_state.strip().lower()
        if value == str(cfg["window_value_open"]).strip().lower():
            states.append(WINDOW_OPEN)
        elif value == str(cfg["window_value_tilted"]).strip().lower():
            states.append(WINDOW_TILTED)
        else:
            states.append(WINDOW_CLOSED)
    if open_contact is not None:
        states.append(WINDOW_OPEN if open_contact == "on" else WINDOW_CLOSED)
    if tilted_contact is not None:
        states.append(WINDOW_TILTED if tilted_contact == "on" else WINDOW_CLOSED)
    if not states:
        return None
    if WINDOW_OPEN in states:
        return WINDOW_OPEN
    if WINDOW_TILTED in states:
        return WINDOW_TILTED
    return WINDOW_CLOSED


def window_position(
    cfg: Mapping[str, Any], state: str | None, comfort: bool
) -> tuple[int, str] | None:
    """Position and reason for an open or tilted window, or None."""
    if state not in (WINDOW_OPEN, WINDOW_TILTED) or not cfg["ventilate_enabled"]:
        return None
    if state == WINDOW_OPEN and comfort:
        return cfg["pos_comfort"], "comfort"
    return cfg["pos_ventilate"], "ventilate"


def lockout_active(cfg: Mapping[str, Any], state: str | None) -> bool:
    """True if the cover must not close because the door/window is open."""
    if cfg["lockout"] == LOCKOUT_OFF:
        return False
    if state == WINDOW_OPEN:
        return True
    return state == WINDOW_TILTED and cfg["lockout_tilted"]

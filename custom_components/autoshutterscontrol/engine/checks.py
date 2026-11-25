"""Plausibility check of the effective settings of a cover (shown as repair issues).

Every finding is a code with placeholders; the texts are in the language files
(``issues.check_<code>``). Only configuration mistakes are reported, not states.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import time
from typing import Any

from .period import parse_day
from .settings import (
    ADVENT_DATE,
    FROST_OFF,
    LOCKOUT_OFF,
    MODE_BRIGHTNESS,
    MODE_BRIGHTNESS_ELEVATION,
    MODE_RESIDENTS,
    WINDOWS_CALENDAR,
)

MIDNIGHT = time(0, 0)


def _fmt(value: Any) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def check(cfg: Mapping[str, Any]) -> list[tuple[str, dict[str, str]]]:
    """Findings (code, placeholders), sorted by code."""
    found: dict[str, dict[str, str]] = {}

    def add(code: str, **values: Any) -> None:
        found.setdefault(code, {k: _fmt(v) for k, v in values.items()})

    # Times: earliest before latest, 0:00 is not a latest time
    for day in ("workday", "free"):
        for way in ("up", "down"):
            early = cfg[f"time_{way}_early_{day}"]
            late = cfg[f"time_{way}_late_{day}"]
            if early is None or late is None:
                continue
            if late == MIDNIGHT and way == "down":
                add("midnight", setting=f"time_{way}_late_{day}")
            elif early > late:
                add("time_order", early=early, late=late, setting=f"time_{way}_early_{day}")

    # Thresholds in the right order
    modes = (cfg["up_mode"], cfg["down_mode"])
    uses_light = any(m in (MODE_BRIGHTNESS, MODE_BRIGHTNESS_ELEVATION) for m in modes)
    if uses_light and cfg["brightness_down"] > cfg["brightness_up"]:
        add("brightness_order", up=cfg["brightness_up"], down=cfg["brightness_down"])
    if cfg["shading_brightness_end"] > cfg["shading_brightness_start"]:
        add(
            "shading_brightness_order",
            start=cfg["shading_brightness_start"],
            end=cfg["shading_brightness_end"],
        )
    if cfg["shading_elevation_min"] >= cfg["shading_elevation_max"]:
        add(
            "elevation_order",
            minimum=cfg["shading_elevation_min"],
            maximum=cfg["shading_elevation_max"],
        )
    if cfg["wind_hysteresis"] >= cfg["wind_threshold"]:
        add("wind_hysteresis", threshold=cfg["wind_threshold"], hysteresis=cfg["wind_hysteresis"])
    if cfg["pos_open"] == cfg["pos_closed"]:
        add("positions_equal", position=cfg["pos_open"])

    # Advent with an own day: the day must be valid
    if cfg["advent"]:
        for mode, day in (("advent_start", "advent_start_date"), ("advent_end", "advent_end_date")):
            if cfg[mode] == ADVENT_DATE and parse_day(cfg[day]) is None:
                add("advent_date", setting=day)

    # Functions without the sensor they need
    def needs(code: str, enabled: bool, *sources: str) -> None:
        if enabled and not any(cfg[s] for s in sources):
            add(code, setting=sources[0])

    needs("missing_brightness", uses_light, "brightness_sensor")
    needs("missing_calendar", cfg["time_source"] == WINDOWS_CALENDAR, "calendar")
    needs("missing_rain", cfg["rain_protection"], "rain_sensor")
    needs("missing_wind", cfg["wind_protection"], "wind_sensor")
    needs("missing_temperature", cfg["frost_mode"] != FROST_OFF, "outdoor_temperature_sensor")
    needs(
        "missing_temperature",
        cfg["heat_protection_temp"] is not None,
        "outdoor_temperature_sensor",
    )
    needs(
        "missing_window",
        cfg["lockout"] != LOCKOUT_OFF,
        "window_open_sensor",
        "window_tilted_sensor",
        "window_state_sensor",
    )
    needs(
        "missing_residents",
        MODE_RESIDENTS in modes,
        "residents_house",
        "residents_room",
    )
    needs(
        "missing_trigger_position",
        bool(cfg["trigger_entity"]),
        "trigger_position",
        "trigger_position2",
    )
    return sorted(found.items())

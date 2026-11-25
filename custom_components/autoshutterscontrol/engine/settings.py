"""Registry of all settings.

Every setting exists once here. The config flow forms, the inheritance
(global -> profile -> cover), the config entities and the diagnostics are all
built from this list. Settings with a ``stage`` higher than ``ACTIVE_STAGE``
are already part of the data model but not shown in the user interface yet.

This module has no Home Assistant imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any

ACTIVE_STAGE = 2

LEVEL_GLOBAL = "global"
LEVEL_PROFILE = "profile"
LEVEL_COVER = "cover"
ALL_LEVELS = frozenset({LEVEL_GLOBAL, LEVEL_PROFILE, LEVEL_COVER})
COVER_ONLY = frozenset({LEVEL_COVER})

# Kinds
BOOL = "bool"
INT = "int"
FLOAT = "float"
TIME = "time"
SELECT = "select"
MULTI = "multi"
ENTITY = "entity"
TEXT = "text"

# Sections (one options page each)
SEC_SCHEDULE = "schedule"
SEC_SENSORS = "sensors"
SEC_POSITIONS = "positions"
SEC_DRIVE = "drive"
SEC_OVERRIDE = "override"
SEC_LIGHT = "light"
SEC_WINDOW = "window"
SEC_PRIVACY = "privacy"
SECTIONS = (
    SEC_SCHEDULE,
    SEC_LIGHT,
    SEC_SENSORS,
    SEC_POSITIONS,
    SEC_WINDOW,
    SEC_PRIVACY,
    SEC_DRIVE,
    SEC_OVERRIDE,
)

# Option values
MODE_TIME = "time"
MODE_ASTRO = "astro"
MODE_BRIGHTNESS = "brightness"
MODE_ELEVATION = "elevation"
MODE_BRIGHTNESS_ELEVATION = "brightness_elevation"
UP_DOWN_MODES = (MODE_TIME, MODE_ASTRO, MODE_BRIGHTNESS, MODE_ELEVATION, MODE_BRIGHTNESS_ELEVATION)
# Modes where the drive happens when a condition is met (between early and late)
DYNAMIC_MODES = frozenset({MODE_BRIGHTNESS, MODE_ELEVATION, MODE_BRIGHTNESS_ELEVATION})

LOGIC_AND = "and"
LOGIC_OR = "or"
LOGICS = (LOGIC_AND, LOGIC_OR)

ELEVATION_FIXED = "fixed"
ELEVATION_SENSOR = "sensor"
ELEVATION_HYBRID = "hybrid"
ELEVATION_SOURCES = (ELEVATION_FIXED, ELEVATION_SENSOR, ELEVATION_HYBRID)

WINDOWS_TIMES = "times"
WINDOWS_CALENDAR = "calendar"
WINDOW_SOURCES = (WINDOWS_TIMES, WINDOWS_CALENDAR)

WINDOW_CLOSED = "closed"
WINDOW_TILTED = "tilted"
WINDOW_OPEN = "open"

RETURN_TARGET = "target"
RETURN_PREVIOUS = "previous"
WINDOW_RETURNS = (RETURN_TARGET, RETURN_PREVIOUS)

LOCKOUT_OFF = "off"
LOCKOUT_SOFT = "soft"
LOCKOUT_HARD = "hard"
LOCKOUTS = (LOCKOUT_OFF, LOCKOUT_SOFT, LOCKOUT_HARD)

TWILIGHT_REAL = "real"
TWILIGHT_CIVIL = "civil"
TWILIGHT_NAUTICAL = "nautical"
TWILIGHT_ASTRONOMICAL = "astronomical"
TWILIGHT_HORIZON = "horizon"
TWILIGHTS = (
    TWILIGHT_REAL,
    TWILIGHT_CIVIL,
    TWILIGHT_NAUTICAL,
    TWILIGHT_ASTRONOMICAL,
    TWILIGHT_HORIZON,
)

KIND_OPEN = "open"
KIND_CLOSE = "close"
KIND_VENTILATE = "ventilate"
KIND_SHADING = "shading"
DRIVE_KINDS = (KIND_OPEN, KIND_CLOSE, KIND_VENTILATE, KIND_SHADING)

RESET_MINUTES = "minutes"
RESET_TIME = "time"
RESET_NEXT_SCHEDULE = "next_schedule"
RESET_MANUAL = "manual"
RESET_MODES = (RESET_MINUTES, RESET_TIME, RESET_NEXT_SCHEDULE, RESET_MANUAL)


@dataclass(frozen=True)
class Setting:
    """One setting."""

    key: str
    kind: str
    default: Any
    section: str
    stage: int = 1
    levels: frozenset[str] = ALL_LEVELS
    options: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float = 1
    unit: str | None = None
    domains: tuple[str, ...] = ()
    device_class: str | None = None
    # Config entity created per cover ("number", "time" or "select")
    entity: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def active(self) -> bool:
        """Return True if the setting is shown in this version."""
        return self.stage <= ACTIVE_STAGE


def _pos(key: str, default: int | None, stage: int, entity: bool = False) -> Setting:
    return Setting(
        key,
        INT,
        default,
        SEC_POSITIONS,
        stage=stage,
        minimum=0,
        maximum=100,
        unit="%",
        entity="number" if entity else None,
    )


SETTINGS: tuple[Setting, ...] = (
    # --- schedule -------------------------------------------------------
    Setting("up_mode", SELECT, MODE_ASTRO, SEC_SCHEDULE, options=UP_DOWN_MODES, entity="select"),
    Setting("down_mode", SELECT, MODE_ASTRO, SEC_SCHEDULE, options=UP_DOWN_MODES, entity="select"),
    Setting("twilight_up", SELECT, TWILIGHT_REAL, SEC_SCHEDULE, options=TWILIGHTS),
    Setting("twilight_down", SELECT, TWILIGHT_REAL, SEC_SCHEDULE, options=TWILIGHTS),
    Setting("horizon_up", FLOAT, 0.0, SEC_SCHEDULE, minimum=-18, maximum=18, step=0.5, unit="°"),
    Setting("horizon_down", FLOAT, 0.0, SEC_SCHEDULE, minimum=-18, maximum=18, step=0.5, unit="°"),
    Setting("offset_up", INT, 0, SEC_SCHEDULE, minimum=-240, maximum=240, unit="min"),
    Setting("offset_down", INT, 0, SEC_SCHEDULE, minimum=-240, maximum=240, unit="min"),
    Setting("time_up_early_workday", TIME, time(5, 0), SEC_SCHEDULE, entity="time"),
    Setting("time_up_late_workday", TIME, time(8, 30), SEC_SCHEDULE, entity="time"),
    Setting("time_up_early_free", TIME, time(8, 0), SEC_SCHEDULE, entity="time"),
    Setting("time_up_late_free", TIME, time(9, 30), SEC_SCHEDULE, entity="time"),
    Setting("time_down_early_workday", TIME, time(16, 0), SEC_SCHEDULE, entity="time"),
    Setting("time_down_late_workday", TIME, time(22, 0), SEC_SCHEDULE, entity="time"),
    Setting("time_down_early_free", TIME, time(16, 0), SEC_SCHEDULE, entity="time"),
    Setting("time_down_late_free", TIME, time(22, 0), SEC_SCHEDULE, entity="time"),
    Setting("down_tomorrow_workday", BOOL, False, SEC_SCHEDULE),
    Setting("time_source", SELECT, WINDOWS_TIMES, SEC_SCHEDULE, stage=2, options=WINDOW_SOURCES),
    Setting("calendar_open_title", TEXT, "open", SEC_SCHEDULE, stage=2),
    Setting("calendar_close_title", TEXT, "close", SEC_SCHEDULE, stage=2),
    # --- brightness and sun elevation (modes brightness/elevation) ----------
    Setting("light_logic", SELECT, LOGIC_OR, SEC_LIGHT, stage=2, options=LOGICS),
    Setting("brightness_up", INT, 500, SEC_LIGHT, stage=2, minimum=0, maximum=200000, unit="lx"),
    Setting("brightness_down", INT, 300, SEC_LIGHT, stage=2, minimum=0, maximum=200000, unit="lx"),
    Setting("brightness_duration", INT, 2, SEC_LIGHT, stage=2, minimum=0, maximum=120, unit="min"),
    Setting(
        "elevation_source", SELECT, ELEVATION_FIXED, SEC_LIGHT, stage=2, options=ELEVATION_SOURCES
    ),
    Setting(
        "elevation_up", FLOAT, 3.0, SEC_LIGHT, stage=2, minimum=-18, maximum=60, step=0.5, unit="°"
    ),
    Setting(
        "elevation_down",
        FLOAT,
        1.0,
        SEC_LIGHT,
        stage=2,
        minimum=-18,
        maximum=60,
        step=0.5,
        unit="°",
    ),
    Setting(
        "elevation_sensor",
        ENTITY,
        None,
        SEC_LIGHT,
        stage=2,
        domains=("sensor", "input_number", "number"),
    ),
    # --- sensors --------------------------------------------------------
    Setting("workday_sensor", ENTITY, None, SEC_SENSORS, domains=("binary_sensor",)),
    Setting("workday_tomorrow_sensor", ENTITY, None, SEC_SENSORS, domains=("binary_sensor",)),
    Setting("calendar", ENTITY, None, SEC_SENSORS, stage=2, domains=("calendar",)),
    Setting("brightness_sensor", ENTITY, None, SEC_SENSORS, stage=2, domains=("sensor",)),
    Setting("residents_home", ENTITY, None, SEC_SENSORS, stage=3),
    Setting("rain_sensor", ENTITY, None, SEC_SENSORS, stage=4, domains=("sensor", "binary_sensor")),
    Setting("wind_sensor", ENTITY, None, SEC_SENSORS, stage=4, domains=("sensor",)),
    Setting("outdoor_temperature_sensor", ENTITY, None, SEC_SENSORS, stage=3, domains=("sensor",)),
    Setting("indoor_temperature_sensor", ENTITY, None, SEC_SENSORS, stage=3, domains=("sensor",)),
    Setting("weather_entity", ENTITY, None, SEC_SENSORS, stage=3, domains=("weather",)),
    # --- positions ------------------------------------------------------
    _pos("pos_open", 100, 1, entity=True),
    _pos("pos_closed", 0, 1, entity=True),
    _pos("pos_sleep", None, 3),
    _pos("pos_ventilate", 50, 2),
    _pos("pos_comfort", 70, 2),
    _pos("pos_shading", 30, 3),
    _pos("pos_shading_alt", None, 3),
    _pos("pos_privacy", 50, 2),
    _pos("pos_privacy_up", None, 2),
    _pos("pos_frost", None, 4),
    _pos("pos_wind", 0, 4),
    _pos("pos_rain", 0, 4),
    _pos("pos_rain_window", 0, 4),
    Setting("tolerance", INT, 2, SEC_POSITIONS, minimum=0, maximum=20, unit="%"),
    Setting("invert", BOOL, False, SEC_POSITIONS, levels=COVER_ONLY),
    Setting(
        "position_entity",
        ENTITY,
        None,
        SEC_POSITIONS,
        levels=COVER_ONLY,
        domains=("sensor", "number", "input_number"),
    ),
    # --- window contacts ------------------------------------------------
    Setting(
        "window_open_sensor",
        ENTITY,
        None,
        SEC_WINDOW,
        stage=2,
        levels=COVER_ONLY,
        domains=("binary_sensor",),
    ),
    Setting(
        "window_tilted_sensor",
        ENTITY,
        None,
        SEC_WINDOW,
        stage=2,
        levels=COVER_ONLY,
        domains=("binary_sensor",),
    ),
    Setting(
        "window_state_sensor",
        ENTITY,
        None,
        SEC_WINDOW,
        stage=2,
        levels=COVER_ONLY,
        domains=("sensor", "input_select", "select"),
    ),
    Setting("window_value_open", TEXT, "open", SEC_WINDOW, stage=2),
    Setting("window_value_tilted", TEXT, "tilted", SEC_WINDOW, stage=2),
    Setting("ventilate_enabled", BOOL, True, SEC_WINDOW, stage=2),
    Setting("ventilate_only_up", BOOL, True, SEC_WINDOW, stage=2),
    Setting("window_open_delay", INT, 0, SEC_WINDOW, stage=2, minimum=0, maximum=600, unit="s"),
    Setting("window_close_delay", INT, 0, SEC_WINDOW, stage=2, minimum=0, maximum=600, unit="s"),
    Setting(
        "window_close_return", SELECT, RETURN_TARGET, SEC_WINDOW, stage=2, options=WINDOW_RETURNS
    ),
    Setting("lockout", SELECT, LOCKOUT_OFF, SEC_WINDOW, stage=2, options=LOCKOUTS),
    Setting("lockout_tilted", BOOL, False, SEC_WINDOW, stage=2),
    # --- privacy ----------------------------------------------------------
    Setting("privacy_up_minutes", INT, 0, SEC_PRIVACY, stage=2, minimum=0, maximum=240, unit="min"),
    Setting(
        "privacy_down_minutes", INT, 0, SEC_PRIVACY, stage=2, minimum=0, maximum=240, unit="min"
    ),
    Setting(
        "privacy_brightness", INT, None, SEC_PRIVACY, stage=2, minimum=0, maximum=200000, unit="lx"
    ),
    # --- drive behaviour ------------------------------------------------
    Setting("delay_fixed", INT, 0, SEC_DRIVE, minimum=0, maximum=3600, unit="s"),
    Setting("delay_random", INT, 0, SEC_DRIVE, minimum=0, maximum=3600, unit="s"),
    Setting("drive_time", INT, 60, SEC_DRIVE, minimum=5, maximum=600, unit="s"),
    Setting("open_never_down", BOOL, True, SEC_DRIVE),
    Setting("close_never_up", BOOL, True, SEC_DRIVE),
    # --- manual override ------------------------------------------------
    Setting(
        "override_blocks",
        MULTI,
        (KIND_VENTILATE, KIND_SHADING),
        SEC_OVERRIDE,
        options=DRIVE_KINDS,
    ),
    Setting("override_reset", SELECT, RESET_MINUTES, SEC_OVERRIDE, options=RESET_MODES),
    Setting("override_minutes", INT, 20, SEC_OVERRIDE, minimum=1, maximum=1440, unit="min"),
    Setting("override_reset_time", TIME, time(3, 0), SEC_OVERRIDE),
    Setting("override_return", BOOL, False, SEC_OVERRIDE),
    Setting("manual_counts_open", BOOL, True, SEC_OVERRIDE),
    Setting("manual_counts_close", BOOL, True, SEC_OVERRIDE),
)

BY_KEY: dict[str, Setting] = {s.key: s for s in SETTINGS}


def settings_for(
    level: str, section: str | None = None, *, only_active: bool = True
) -> list[Setting]:
    """Return the settings that can be set on a level (optionally one section)."""
    return [
        s
        for s in SETTINGS
        if level in s.levels
        and (section is None or s.section == section)
        and (s.active or not only_active)
    ]


def sections_for(level: str) -> list[str]:
    """Return the sections that have at least one active setting on a level."""
    return [sec for sec in SECTIONS if settings_for(level, sec)]


# --- serialisation ---------------------------------------------------------


def to_storage(setting: Setting, value: Any) -> Any:
    """Convert a python value into what is stored in config entries (JSON)."""
    if value is None:
        return None
    if setting.kind == TIME:
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        return parse_time(value).strftime("%H:%M:%S")
    if setting.kind == MULTI:
        return list(value)
    if setting.kind == INT:
        return int(value)
    if setting.kind == FLOAT:
        return float(value)
    if setting.kind == BOOL:
        return bool(value)
    return value


def from_storage(setting: Setting, value: Any) -> Any:
    """Convert a stored value into its python value."""
    if value is None:
        return None
    if setting.kind == TIME:
        return value if isinstance(value, time) else parse_time(value)
    if setting.kind == MULTI:
        return tuple(value)
    if setting.kind == INT:
        return int(value)
    if setting.kind == FLOAT:
        return float(value)
    return value


def parse_time(value: str) -> time:
    """Parse HH:MM or HH:MM:SS."""
    parts = [int(p) for p in str(value).split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])

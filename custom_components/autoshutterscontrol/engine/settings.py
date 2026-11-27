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

ACTIVE_STAGE = 5

LEVEL_GLOBAL = "global"
LEVEL_PROFILE = "profile"
LEVEL_COVER = "cover"
ALL_LEVELS = frozenset({LEVEL_GLOBAL, LEVEL_PROFILE, LEVEL_COVER})
COVER_ONLY = frozenset({LEVEL_COVER})
GLOBAL_ONLY = frozenset({LEVEL_GLOBAL})

# Kinds
BOOL = "bool"
INT = "int"
FLOAT = "float"
TIME = "time"
SELECT = "select"
MULTI = "multi"
ENTITY = "entity"
TEXT = "text"
ENTITIES = "entities"
CONDITION = "condition"
ACTION = "action"

# Sections (one options page each)
SEC_SCHEDULE = "schedule"
SEC_SENSORS = "sensors"
SEC_POSITIONS = "positions"
SEC_DRIVE = "drive"
SEC_OVERRIDE = "override"
SEC_LIGHT = "light"
SEC_WINDOW = "window"
SEC_PRIVACY = "privacy"
SEC_RESIDENTS = "residents"
SEC_SHADING = "shading"
SEC_TILT = "tilt"
SEC_PROTECTION = "protection"
SEC_SPECIAL = "special"
SEC_EXTRA = "extra"
# Shown on the overview page of the options only (not one of SECTIONS)
SEC_SUMMARY = "summary"
SECTIONS = (
    SEC_SCHEDULE,
    SEC_LIGHT,
    SEC_SENSORS,
    SEC_RESIDENTS,
    SEC_POSITIONS,
    SEC_WINDOW,
    SEC_SHADING,
    SEC_TILT,
    SEC_PRIVACY,
    SEC_PROTECTION,
    SEC_SPECIAL,
    SEC_DRIVE,
    SEC_OVERRIDE,
    SEC_EXTRA,
)

# Option values
MODE_TIME = "time"
MODE_ASTRO = "astro"
MODE_BRIGHTNESS = "brightness"
MODE_ELEVATION = "elevation"
MODE_BRIGHTNESS_ELEVATION = "brightness_elevation"
MODE_RESIDENTS = "residents"
MODE_ENTITY = "entity"
UP_DOWN_MODES = (
    MODE_TIME,
    MODE_ASTRO,
    MODE_BRIGHTNESS,
    MODE_ELEVATION,
    MODE_BRIGHTNESS_ELEVATION,
    MODE_RESIDENTS,
    MODE_ENTITY,
)
# Entities that can give a time (input_datetime, time entity, timestamp sensor)
TIME_DOMAINS = ("input_datetime", "time", "sensor")
# Modes where the drive happens when a condition is met (between early and late)
DYNAMIC_MODES = frozenset(
    {MODE_BRIGHTNESS, MODE_ELEVATION, MODE_BRIGHTNESS_ELEVATION, MODE_RESIDENTS}
)

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
TWILIGHT_GOLDEN = "golden"
TWILIGHT_BLUE = "blue"
TWILIGHTS = (
    TWILIGHT_REAL,
    TWILIGHT_CIVIL,
    TWILIGHT_NAUTICAL,
    TWILIGHT_ASTRONOMICAL,
    TWILIGHT_HORIZON,
    TWILIGHT_GOLDEN,
    TWILIGHT_BLUE,
)

KIND_OPEN = "open"
KIND_CLOSE = "close"
KIND_VENTILATE = "ventilate"
KIND_SHADING = "shading"
KIND_TRIGGER = "trigger"
DRIVE_KINDS = (KIND_OPEN, KIND_CLOSE, KIND_VENTILATE, KIND_SHADING, KIND_TRIGGER)

FROST_OFF = "off"
FROST_SOFT = "soft"
FROST_AM = "am"
FROST_PM = "pm"
FROST_HARD = "hard"
FROST_MODES = (FROST_OFF, FROST_SOFT, FROST_AM, FROST_PM, FROST_HARD)

ADVENT_FIRST_SUNDAY = "first_advent"
ADVENT_DATE = "date"
# Sunday before the first Sunday of Advent (Totensonntag)
ADVENT_DEAD_SUNDAY = "dead_sunday"
ADVENT_STARTS = (ADVENT_FIRST_SUNDAY, ADVENT_DEAD_SUNDAY, ADVENT_DATE)
ADVENT_EPIPHANY = "epiphany"
ADVENT_CANDLEMAS = "candlemas"
ADVENT_ENDS = (ADVENT_EPIPHANY, ADVENT_CANDLEMAS, ADVENT_DATE)

# Residents (ASC states, highest priority first)
RES_ASLEEP = "asleep"
RES_GOTOSLEEP = "gotosleep"
RES_AWOKEN = "awoken"
RES_HOME = "home"
RES_ABSENT = "absent"
RES_GONE = "gone"
RESIDENT_STATES = (RES_ASLEEP, RES_GOTOSLEEP, RES_AWOKEN, RES_HOME, RES_ABSENT, RES_GONE)
RESIDENT_DOMAINS = (
    "person",
    "device_tracker",
    "zone",
    "binary_sensor",
    "input_boolean",
    "input_select",
    "select",
    "sensor",
    "alarm_control_panel",
)

# Drive only when residents are ... (ASC_Mode_Up / _Down / ASC_Shading_Mode)
PRESENCE_ALWAYS = "always"
PRESENCE_HOME = "home"
PRESENCE_ABSENT = "absent"
PRESENCE_OFF = "off"
PRESENCE_MODES = (PRESENCE_ALWAYS, PRESENCE_HOME, PRESENCE_ABSENT, PRESENCE_OFF)

SELF_DEFENSE_OFF = "off"
SELF_DEFENSE_ABSENT = "absent"
SELF_DEFENSE_GONE = "gone"
SELF_DEFENSE_MODES = (SELF_DEFENSE_OFF, SELF_DEFENSE_ABSENT, SELF_DEFENSE_GONE)

# A guest in the room
GUEST_NO_MORNING = "no_morning"
GUEST_NO_SCHEDULE = "no_morning_evening"
GUEST_MANUAL = "manual_only"
GUEST_MODES = (GUEST_NO_MORNING, GUEST_NO_SCHEDULE, GUEST_MANUAL)

# Catching up after a restart or a failure
RECOVERY_OFF = "off"
RECOVERY_FAILURE = "failure"
RECOVERY_ALWAYS = "always"
RECOVERY_MODES = (RECOVERY_OFF, RECOVERY_FAILURE, RECOVERY_ALWAYS)

# Shading conditions
COND_AZIMUTH = "azimuth"
COND_ELEVATION = "elevation"
COND_BRIGHTNESS = "brightness"
COND_TEMP_OUT = "temp_out"
COND_TEMP_IN = "temp_in"
COND_FORECAST = "forecast"
COND_WEATHER = "weather"
COND_SENSOR = "sensor"
SHADING_CONDITIONS = (
    COND_AZIMUTH,
    COND_ELEVATION,
    COND_BRIGHTNESS,
    COND_TEMP_OUT,
    COND_TEMP_IN,
    COND_FORECAST,
    COND_WEATHER,
    COND_SENSOR,
)
WEATHER_CONDITIONS = (
    "clear-night",
    "cloudy",
    "exceptional",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "partlycloudy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "sunny",
    "windy",
    "windy-variant",
)

TILT_AFTER = "after"
TILT_STANDSTILL = "standstill"
TILT_FIRST = "first"
TILT_MODES = (TILT_AFTER, TILT_STANDSTILL, TILT_FIRST)

RESET_MINUTES = "minutes"
RESET_TIME = "time"
RESET_NEXT_SCHEDULE = "next_schedule"
RESET_MANUAL = "manual"
RESET_MODES = (RESET_MINUTES, RESET_TIME, RESET_NEXT_SCHEDULE, RESET_MANUAL)

# Wind protection: a fixed position, or only fully open / fully closed
WIND_POSITION = "position"
WIND_NEAREST = "nearest"
WIND_OPEN = "open"
WIND_CLOSED = "closed"
WIND_MODES = (WIND_POSITION, WIND_NEAREST, WIND_OPEN, WIND_CLOSED)

# Lock of a cover (action or select)
LOCK_NONE = "none"
LOCK_HOLD = "hold"
LOCK_OPEN = "open"
LOCK_CLOSED = "closed"
LOCK_MODES = (LOCK_NONE, LOCK_HOLD, LOCK_OPEN, LOCK_CLOSED)

# Presets for doors and windows (set several window fields at once)
PRESET_CUSTOM = "custom"
PRESET_TERRACE = "terrace_door"
PRESET_VENT = "vent_window"
PRESET_PROTECT = "protection_only"
WINDOW_PRESETS = (PRESET_CUSTOM, PRESET_TERRACE, PRESET_VENT, PRESET_PROTECT)
# Value "=pos_open": the value of that setting
PRESET_VALUES: dict[str, dict[str, Any]] = {
    PRESET_TERRACE: {
        "ventilate_enabled": True,
        "ventilate_only_up": True,
        "pos_ventilate": "=pos_open",
        "lockout": LOCKOUT_SOFT,
        "lockout_tilted": True,
        "window_close_return": RETURN_TARGET,
    },
    PRESET_VENT: {
        "ventilate_enabled": True,
        "ventilate_only_up": True,
        "lockout": LOCKOUT_OFF,
        "window_close_return": RETURN_TARGET,
    },
    PRESET_PROTECT: {
        "ventilate_enabled": False,
        "lockout": LOCKOUT_SOFT,
        "lockout_tilted": True,
    },
}

# Type of the cover
TYPE_SHUTTER = "shutter"
TYPE_AWNING = "awning"
COVER_TYPES = (TYPE_SHUTTER, TYPE_AWNING)

PROFILE_AND_COVER = frozenset({LEVEL_PROFILE, LEVEL_COVER})


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
    Setting("up_time_entity", ENTITY, None, SEC_SCHEDULE, domains=TIME_DOMAINS),
    Setting("down_time_entity", ENTITY, None, SEC_SCHEDULE, domains=TIME_DOMAINS),
    Setting(
        "close_entity",
        ENTITY,
        None,
        SEC_SCHEDULE,
        stage=5,
        domains=("binary_sensor", "input_boolean", "switch", "light"),
    ),
    Setting("close_entity_from", TIME, None, SEC_SCHEDULE, stage=5),
    Setting("night_time", TIME, None, SEC_SCHEDULE, stage=5),
    Setting(
        "night_entity",
        ENTITY,
        None,
        SEC_SCHEDULE,
        stage=5,
        domains=("binary_sensor", "input_boolean", "switch"),
    ),
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
    Setting(
        "rain_sensor",
        ENTITY,
        None,
        SEC_SENSORS,
        stage=4,
        domains=("sensor", "binary_sensor", "input_boolean", "input_number"),
    ),
    Setting("wind_sensor", ENTITY, None, SEC_SENSORS, stage=4, domains=("sensor", "input_number")),
    Setting(
        "outdoor_temperature_sensor",
        ENTITY,
        None,
        SEC_SENSORS,
        stage=3,
        domains=("sensor", "input_number", "number"),
    ),
    Setting(
        "indoor_temperature_sensor",
        ENTITY,
        None,
        SEC_SENSORS,
        stage=3,
        domains=("sensor", "input_number", "number"),
    ),
    Setting("weather_entity", ENTITY, None, SEC_SENSORS, stage=3, domains=("weather",)),
    Setting(
        "forecast_sensor",
        ENTITY,
        None,
        SEC_SENSORS,
        stage=3,
        domains=("sensor", "input_number", "number"),
    ),
    # --- residents ------------------------------------------------------
    Setting("residents_house", ENTITIES, (), SEC_RESIDENTS, stage=3, domains=RESIDENT_DOMAINS),
    Setting(
        "residents_room",
        ENTITIES,
        (),
        SEC_RESIDENTS,
        stage=3,
        levels=COVER_ONLY,
        domains=RESIDENT_DOMAINS,
    ),
    Setting("residents_map", TEXT, None, SEC_RESIDENTS, stage=3),
    Setting(
        "residents_gone_hours", INT, 0, SEC_RESIDENTS, stage=3, minimum=0, maximum=240, unit="h"
    ),
    Setting("presence_up", SELECT, PRESENCE_ALWAYS, SEC_RESIDENTS, stage=3, options=PRESENCE_MODES),
    Setting(
        "presence_down", SELECT, PRESENCE_ALWAYS, SEC_RESIDENTS, stage=3, options=PRESENCE_MODES
    ),
    Setting("sleep_close", BOOL, True, SEC_RESIDENTS, stage=3),
    Setting("wake_open", BOOL, True, SEC_RESIDENTS, stage=3),
    Setting("sleep_allow_open", BOOL, False, SEC_RESIDENTS, stage=3),
    Setting("sleep_allow_ventilate", BOOL, False, SEC_RESIDENTS, stage=3),
    Setting("sleep_allow_shading", BOOL, False, SEC_RESIDENTS, stage=3),
    Setting(
        "self_defense_mode",
        SELECT,
        SELF_DEFENSE_GONE,
        SEC_RESIDENTS,
        stage=3,
        options=SELF_DEFENSE_MODES,
    ),
    Setting(
        "self_defense_delay", INT, 5, SEC_RESIDENTS, stage=3, minimum=0, maximum=240, unit="min"
    ),
    Setting("self_defense_all", BOOL, False, SEC_RESIDENTS, stage=3),
    Setting(
        "guest_entities",
        ENTITIES,
        (),
        SEC_RESIDENTS,
        stage=3,
        levels=COVER_ONLY,
        domains=("person", "device_tracker", "binary_sensor", "input_boolean", "switch", "zone"),
    ),
    Setting("guest_mode", SELECT, GUEST_NO_MORNING, SEC_RESIDENTS, stage=3, options=GUEST_MODES),
    # --- positions ------------------------------------------------------
    _pos("pos_open", 100, 1, entity=True),
    _pos("pos_closed", 0, 1, entity=True),
    _pos("pos_sleep", None, 3),
    _pos("pos_ventilate", 50, 2),
    _pos("pos_comfort", 70, 2),
    _pos("pos_shading", 30, 3, entity=True),
    _pos("pos_shading_alt", None, 3),
    _pos("pos_glare", 40, 5),
    _pos("pos_privacy", 50, 2),
    _pos("pos_privacy_up", None, 2),
    _pos("pos_frost", None, 4),
    _pos("pos_wind", 0, 4),
    _pos("pos_rain", 0, 4),
    _pos("pos_rain_window", 0, 4),
    _pos("pos_night", None, 5),
    _pos("pos_advent", None, 5),
    _pos("pos_emergency", 100, 5),
    _pos("pos_awning", 100, 5),
    Setting(
        "cover_type",
        SELECT,
        TYPE_SHUTTER,
        SEC_POSITIONS,
        stage=5,
        levels=COVER_ONLY,
        options=COVER_TYPES,
    ),
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
    Setting(
        "window_preset",
        SELECT,
        PRESET_CUSTOM,
        SEC_WINDOW,
        stage=5,
        levels=PROFILE_AND_COVER,
        options=WINDOW_PRESETS,
    ),
    Setting("ventilate_enabled", BOOL, True, SEC_WINDOW, stage=2),
    Setting("ventilate_only_up", BOOL, True, SEC_WINDOW, stage=2),
    Setting("window_open_delay", INT, 0, SEC_WINDOW, stage=2, minimum=0, maximum=600, unit="s"),
    Setting("window_close_delay", INT, 0, SEC_WINDOW, stage=2, minimum=0, maximum=600, unit="s"),
    Setting(
        "window_close_return", SELECT, RETURN_TARGET, SEC_WINDOW, stage=2, options=WINDOW_RETURNS
    ),
    Setting("lockout", SELECT, LOCKOUT_OFF, SEC_WINDOW, stage=2, options=LOCKOUTS),
    Setting("lockout_tilted", BOOL, False, SEC_WINDOW, stage=2),
    # --- shading ----------------------------------------------------------
    Setting(
        "shading_mode",
        SELECT,
        PRESENCE_OFF,
        SEC_SHADING,
        stage=3,
        options=PRESENCE_MODES,
        entity="select",
    ),
    Setting(
        "shading_azimuth_start", INT, 105, SEC_SHADING, stage=3, minimum=0, maximum=360, unit="°"
    ),
    Setting(
        "shading_azimuth_end", INT, 255, SEC_SHADING, stage=3, minimum=0, maximum=360, unit="°"
    ),
    Setting(
        "shading_elevation_min",
        FLOAT,
        25.0,
        SEC_SHADING,
        stage=3,
        minimum=-10,
        maximum=90,
        step=0.5,
        unit="°",
    ),
    Setting(
        "shading_elevation_max",
        FLOAT,
        90.0,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=90,
        step=0.5,
        unit="°",
    ),
    Setting(
        "shading_brightness_sensor",
        ENTITY,
        None,
        SEC_SHADING,
        stage=3,
        domains=("sensor", "input_number", "number"),
    ),
    Setting(
        "shading_brightness_start",
        INT,
        35000,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=200000,
        unit="lx",
    ),
    Setting(
        "shading_brightness_end",
        INT,
        20000,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=200000,
        unit="lx",
    ),
    Setting(
        "shading_brightness_average",
        INT,
        0,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=60,
        unit="min",
    ),
    Setting(
        "shading_temp_out_min",
        FLOAT,
        18.0,
        SEC_SHADING,
        stage=3,
        minimum=-30,
        maximum=50,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "shading_temp_in_min",
        FLOAT,
        None,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=40,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "shading_forecast_min",
        FLOAT,
        None,
        SEC_SHADING,
        stage=3,
        minimum=-30,
        maximum=50,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "shading_temp_hysteresis",
        FLOAT,
        1.0,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=10,
        step=0.5,
        unit="K",
    ),
    Setting(
        "shading_weather_conditions",
        MULTI,
        ("sunny", "partlycloudy"),
        SEC_SHADING,
        stage=3,
        options=WEATHER_CONDITIONS,
    ),
    Setting(
        "shading_sensor",
        ENTITY,
        None,
        SEC_SHADING,
        stage=3,
        domains=("binary_sensor", "input_boolean", "switch"),
    ),
    Setting(
        "shading_must",
        MULTI,
        SHADING_CONDITIONS,
        SEC_SHADING,
        stage=3,
        options=SHADING_CONDITIONS,
    ),
    Setting("shading_any", MULTI, (), SEC_SHADING, stage=3, options=SHADING_CONDITIONS),
    Setting(
        "shading_delay_start", INT, 10, SEC_SHADING, stage=3, minimum=0, maximum=240, unit="min"
    ),
    Setting("shading_delay_end", INT, 20, SEC_SHADING, stage=3, minimum=0, maximum=240, unit="min"),
    Setting("shading_end_sun_leaves", BOOL, True, SEC_SHADING, stage=3),
    Setting("shading_end_open", BOOL, True, SEC_SHADING, stage=3),
    Setting("shading_only_down", BOOL, True, SEC_SHADING, stage=3),
    Setting("shading_time_start", TIME, None, SEC_SHADING, stage=3),
    Setting("shading_time_end", TIME, None, SEC_SHADING, stage=3),
    Setting(
        "heat_protection_temp",
        FLOAT,
        None,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=50,
        step=0.5,
        unit="°C",
    ),
    Setting("hot_day", BOOL, False, SEC_SHADING, stage=3),
    Setting(
        "hot_day_temp",
        FLOAT,
        26.0,
        SEC_SHADING,
        stage=3,
        minimum=0,
        maximum=50,
        step=0.5,
        unit="°C",
    ),
    Setting("hot_day_sunny", BOOL, True, SEC_SHADING, stage=3),
    Setting("window_azimuth", INT, None, SEC_SHADING, stage=3, minimum=0, maximum=360, unit="°"),
    Setting("horizon", TEXT, None, SEC_SHADING, stage=5, levels=COVER_ONLY),
    Setting(
        "window_sill",
        INT,
        None,
        SEC_SHADING,
        stage=5,
        levels=COVER_ONLY,
        minimum=0,
        maximum=500,
        unit="cm",
    ),
    Setting(
        "window_height",
        INT,
        None,
        SEC_SHADING,
        stage=5,
        levels=COVER_ONLY,
        minimum=10,
        maximum=600,
        unit="cm",
    ),
    Setting(
        "sun_depth", FLOAT, None, SEC_SHADING, stage=5, minimum=0, maximum=20, step=0.1, unit="m"
    ),
    Setting("glare", BOOL, False, SEC_SHADING, stage=5),
    Setting(
        "glare_brightness_start",
        INT,
        50000,
        SEC_SHADING,
        stage=5,
        minimum=0,
        maximum=200000,
        unit="lx",
    ),
    Setting(
        "glare_brightness_end",
        INT,
        35000,
        SEC_SHADING,
        stage=5,
        minimum=0,
        maximum=200000,
        unit="lx",
    ),
    Setting("glare_delay_start", INT, 5, SEC_SHADING, stage=5, minimum=0, maximum=240, unit="min"),
    Setting("glare_delay_end", INT, 20, SEC_SHADING, stage=5, minimum=0, maximum=240, unit="min"),
    Setting(
        "away_heat_offset",
        FLOAT,
        0.0,
        SEC_SHADING,
        stage=5,
        minimum=0,
        maximum=10,
        step=0.5,
        unit="K",
    ),
    Setting(
        "shading_alt_entity",
        ENTITY,
        None,
        SEC_SHADING,
        stage=3,
        domains=("binary_sensor", "input_boolean", "switch"),
    ),
    # --- tilt (slats) -----------------------------------------------------
    Setting("tilt_entity", ENTITY, None, SEC_TILT, stage=3, levels=COVER_ONLY, domains=("cover",)),
    *(
        Setting(f"tilt_{name}", INT, None, SEC_TILT, stage=3, minimum=0, maximum=100, unit="%")
        for name in ("open", "closed", "sleep", "ventilate", "comfort", "shading", "privacy")
    ),
    Setting("tilt_shading_steps", TEXT, None, SEC_TILT, stage=3),
    Setting("tilt_auto", BOOL, False, SEC_TILT, stage=3),
    Setting("tilt_slat_ratio", FLOAT, 0.9, SEC_TILT, stage=3, minimum=0.3, maximum=2.0, step=0.05),
    Setting("tilt_horizontal", INT, 100, SEC_TILT, stage=3, minimum=0, maximum=100, unit="%"),
    Setting("tilt_vertical", INT, 0, SEC_TILT, stage=3, minimum=0, maximum=100, unit="%"),
    Setting("tilt_mode", SELECT, TILT_STANDSTILL, SEC_TILT, stage=3, options=TILT_MODES),
    Setting("tilt_delay", INT, 2, SEC_TILT, stage=3, minimum=0, maximum=120, unit="s"),
    Setting("tilt_timeout", INT, 120, SEC_TILT, stage=3, minimum=5, maximum=600, unit="s"),
    Setting("tilt_close_first", BOOL, False, SEC_TILT, stage=3),
    Setting("tilt_tolerance", INT, 2, SEC_TILT, stage=3, minimum=0, maximum=20, unit="%"),
    # --- weather protection ----------------------------------------------
    Setting("rain_protection", BOOL, False, SEC_PROTECTION, stage=4),
    Setting(
        "rain_threshold",
        FLOAT,
        0.0,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=100,
        step=0.1,
        unit="mm",
    ),
    Setting(
        "rain_hysteresis",
        FLOAT,
        0.0,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=100,
        step=0.1,
        unit="mm",
    ),
    Setting(
        "rain_delay_start", INT, 0, SEC_PROTECTION, stage=4, minimum=0, maximum=120, unit="min"
    ),
    Setting("rain_delay_end", INT, 15, SEC_PROTECTION, stage=4, minimum=0, maximum=240, unit="min"),
    Setting("rain_window", BOOL, True, SEC_PROTECTION, stage=4),
    Setting(
        "rain_window_states",
        MULTI,
        ("tilted", "open"),
        SEC_PROTECTION,
        stage=4,
        options=("tilted", "open"),
    ),
    Setting(
        "rain_window_threshold",
        FLOAT,
        None,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=100,
        step=0.1,
        unit="mm",
    ),
    Setting("rain_window_over_lockout", BOOL, False, SEC_PROTECTION, stage=4),
    Setting(
        "rain_window_return",
        SELECT,
        RETURN_PREVIOUS,
        SEC_PROTECTION,
        stage=4,
        options=WINDOW_RETURNS,
    ),
    Setting("wind_protection", BOOL, False, SEC_PROTECTION, stage=4),
    Setting(
        "wind_threshold",
        FLOAT,
        50.0,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=300,
        step=1,
        unit="km/h",
    ),
    Setting(
        "wind_hysteresis",
        FLOAT,
        20.0,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=300,
        step=1,
        unit="km/h",
    ),
    Setting("wind_delay_start", INT, 0, SEC_PROTECTION, stage=4, minimum=0, maximum=60, unit="min"),
    Setting("wind_mode", SELECT, WIND_POSITION, SEC_PROTECTION, stage=5, options=WIND_MODES),
    Setting("wind_delay_end", INT, 10, SEC_PROTECTION, stage=4, minimum=0, maximum=240, unit="min"),
    Setting("frost_mode", SELECT, FROST_OFF, SEC_PROTECTION, stage=4, options=FROST_MODES),
    Setting(
        "frost_temp",
        FLOAT,
        2.0,
        SEC_PROTECTION,
        stage=4,
        minimum=-20,
        maximum=10,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "frost_hysteresis",
        FLOAT,
        1.0,
        SEC_PROTECTION,
        stage=4,
        minimum=0,
        maximum=10,
        step=0.5,
        unit="K",
    ),
    Setting(
        "close_above_temp",
        FLOAT,
        None,
        SEC_PROTECTION,
        stage=5,
        minimum=-30,
        maximum=60,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "close_below_temp",
        FLOAT,
        None,
        SEC_PROTECTION,
        stage=5,
        minimum=-40,
        maximum=40,
        step=0.5,
        unit="°C",
    ),
    Setting(
        "winter_temp",
        FLOAT,
        12.0,
        SEC_PROTECTION,
        stage=5,
        levels=GLOBAL_ONLY,
        minimum=-20,
        maximum=30,
        step=0.5,
        unit="°C",
    ),
    # --- force, party, advent, trigger, wiggle, hardware lock ---------------
    *(
        Setting(
            f"force_{name}",
            ENTITY,
            None,
            SEC_SPECIAL,
            stage=4,
            levels=COVER_ONLY,
            domains=("binary_sensor", "input_boolean", "switch"),
        )
        for name in ("close", "open", "ventilate", "shading")
    ),
    Setting("force_return", BOOL, True, SEC_SPECIAL, stage=4),
    Setting(
        "pause_entity",
        ENTITY,
        None,
        SEC_SPECIAL,
        stage=4,
        levels=COVER_ONLY,
        domains=("binary_sensor", "input_boolean", "switch"),
    ),
    Setting("party", BOOL, True, SEC_SPECIAL, stage=4),
    Setting("advent", BOOL, True, SEC_SPECIAL, stage=4),
    Setting(
        "advent_start", SELECT, ADVENT_FIRST_SUNDAY, SEC_SPECIAL, stage=4, options=ADVENT_STARTS
    ),
    Setting("advent_start_date", TEXT, None, SEC_SPECIAL, stage=4),
    Setting("advent_end", SELECT, ADVENT_EPIPHANY, SEC_SPECIAL, stage=4, options=ADVENT_ENDS),
    Setting("advent_end_date", TEXT, None, SEC_SPECIAL, stage=4),
    Setting("trigger_entity", ENTITY, None, SEC_SPECIAL, stage=4, levels=COVER_ONLY),
    Setting("trigger_value", TEXT, "on", SEC_SPECIAL, stage=4, levels=COVER_ONLY),
    Setting(
        "trigger_position",
        INT,
        None,
        SEC_SPECIAL,
        stage=4,
        levels=COVER_ONLY,
        minimum=0,
        maximum=100,
        unit="%",
    ),
    Setting("trigger_value2", TEXT, None, SEC_SPECIAL, stage=4, levels=COVER_ONLY),
    Setting(
        "trigger_position2",
        INT,
        None,
        SEC_SPECIAL,
        stage=4,
        levels=COVER_ONLY,
        minimum=0,
        maximum=100,
        unit="%",
    ),
    Setting("trigger_return", BOOL, True, SEC_SPECIAL, stage=4, levels=COVER_ONLY),
    Setting("summer_no_close", BOOL, False, SEC_SPECIAL, stage=5),
    Setting("summer_start", TEXT, "1.5.", SEC_SPECIAL, stage=5, levels=GLOBAL_ONLY),
    Setting("summer_end", TEXT, "30.9.", SEC_SPECIAL, stage=5, levels=GLOBAL_ONLY),
    Setting(
        "emergency_entities",
        ENTITIES,
        (),
        SEC_SPECIAL,
        stage=5,
        levels=GLOBAL_ONLY,
        domains=("binary_sensor", "input_boolean", "switch"),
    ),
    Setting("emergency_latch", BOOL, True, SEC_SPECIAL, stage=5, levels=GLOBAL_ONLY),
    Setting("holiday_shift", INT, 30, SEC_SPECIAL, stage=5, minimum=0, maximum=120, unit="min"),
    Setting("wiggle_value", INT, 5, SEC_SPECIAL, stage=4, minimum=1, maximum=50, unit="%"),
    Setting("wiggle_wait", INT, 5, SEC_SPECIAL, stage=4, minimum=1, maximum=120, unit="s"),
    Setting(
        "lockout_entity",
        ENTITY,
        None,
        SEC_SPECIAL,
        stage=4,
        levels=COVER_ONLY,
        domains=("switch", "lock", "input_boolean"),
    ),
    # --- extra conditions and actions -----------------------------------
    *(
        Setting(f"condition_{name}", CONDITION, None, SEC_EXTRA, stage=4)
        for name in ("all", "open", "close", "ventilate", "shading")
    ),
    *(
        Setting(f"action_{name}", ACTION, None, SEC_EXTRA, stage=4)
        for name in ("drive", "manual", "override_end", "rain_window")
    ),
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
    Setting("recovery", SELECT, RECOVERY_FAILURE, SEC_DRIVE, stage=5, options=RECOVERY_MODES),
    Setting("logbook", BOOL, True, SEC_DRIVE, stage=5),
    Setting("drive_check", BOOL, True, SEC_DRIVE, stage=5),
    Setting("panel", BOOL, False, SEC_SUMMARY, stage=5, levels=GLOBAL_ONLY),
    Setting(
        "drive_stagger",
        INT,
        0,
        SEC_DRIVE,
        stage=5,
        levels=GLOBAL_ONLY,
        minimum=0,
        maximum=120,
        unit="s",
    ),
    Setting("quiet_start", TIME, None, SEC_DRIVE, stage=5),
    Setting("quiet_end", TIME, None, SEC_DRIVE, stage=5),
    Setting(
        "quiet_start_entity", ENTITY, None, SEC_DRIVE, stage=5, domains=("input_datetime", "time")
    ),
    Setting(
        "quiet_end_entity", ENTITY, None, SEC_DRIVE, stage=5, domains=("input_datetime", "time")
    ),
    Setting("quiet_window", BOOL, True, SEC_DRIVE, stage=5),
    Setting(
        "command_gap",
        FLOAT,
        0.0,
        SEC_DRIVE,
        stage=5,
        levels=GLOBAL_ONLY,
        minimum=0,
        maximum=30,
        step=0.5,
        unit="s",
    ),
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
    Setting("manual_known", BOOL, False, SEC_OVERRIDE, stage=5),
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
    if setting.kind in (MULTI, ENTITIES, CONDITION, ACTION):
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
    if setting.kind in (MULTI, ENTITIES):
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

"""Constants for AutoShuttersControl for HA."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "autoshutterscontrol"

SUBENTRY_PROFILE: Final = "profile"
SUBENTRY_COVER: Final = "cover"

# Keys inside subentry data
CONF_COVER_ENTITY: Final = "cover_entity"
CONF_PROFILE: Final = "profile"
# Alternative profile while an entity shows a value (e.g. summer/winter)
CONF_PROFILE_ALT: Final = "profile_alt"
CONF_PROFILE_SWITCH: Final = "profile_switch_entity"
CONF_PROFILE_SWITCH_VALUE: Final = "profile_switch_value"
CONF_PROFILE_ALT_FROM: Final = "profile_alt_from"
CONF_PROFILE_ALT_TO: Final = "profile_alt_to"
CONF_SETTINGS: Final = "settings"
CONF_NAME: Final = "name"

# Storage
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.state"
STORE_SAVE_DELAY: Final = 5

# Dispatcher signals
SIGNAL_GLOBAL_UPDATE: Final = f"{DOMAIN}_global_update"
SIGNAL_COVER_UPDATE: Final = f"{DOMAIN}_cover_update_{{}}"

# Events
EVENT_DRIVE: Final = f"{DOMAIN}_drive"
EVENT_MANUAL: Final = f"{DOMAIN}_manual"
EVENT_RAIN_WINDOW: Final = f"{DOMAIN}_rain_window"

# Global runtime switches (stored, not part of the settings)
SWITCH_AUTOMATIC: Final = "automatic"
SWITCH_WEEKEND_TIMES: Final = "weekend_times"
SWITCH_MORNING: Final = "morning"
SWITCH_EVENING: Final = "evening"
SWITCH_PAUSE: Final = "pause"
SWITCH_COMFORT: Final = "comfort"
SWITCH_SHADING: Final = "shading"
SWITCH_SELF_DEFENSE: Final = "self_defense"
SWITCH_PARTY: Final = "party"
SWITCH_ADVENT: Final = "advent"
SWITCH_HARDWARE_LOCK: Final = "hardware_lock"
SWITCH_SIMULATION: Final = "simulation"
SWITCH_GUEST: Final = "guest"
SWITCH_HOLIDAY: Final = "holiday"

GLOBAL_SWITCHES: Final = {
    SWITCH_AUTOMATIC: True,
    SWITCH_WEEKEND_TIMES: True,
    SWITCH_MORNING: True,
    SWITCH_EVENING: True,
    SWITCH_PAUSE: False,
    SWITCH_COMFORT: False,
    SWITCH_SHADING: True,
    SWITCH_SELF_DEFENSE: False,
    SWITCH_PARTY: False,
    SWITCH_ADVENT: False,
    SWITCH_HARDWARE_LOCK: True,
    SWITCH_SIMULATION: False,
    SWITCH_HOLIDAY: False,
}

# Per cover runtime switches
COVER_SWITCHES: Final = {
    SWITCH_AUTOMATIC: True,
    SWITCH_PAUSE: False,
    SWITCH_SIMULATION: False,
    SWITCH_GUEST: False,
}

# Inherit marker for select fields in profile and cover forms
INHERIT: Final = "inherit"

# Value sources for effective_config
SOURCE_DEFAULT: Final = "default"
SOURCE_GLOBAL: Final = "global"
SOURCE_PROFILE: Final = "profile"
SOURCE_COVER: Final = "cover"

SERVICE_DRIVE: Final = "drive"
SERVICE_RECALCULATE: Final = "recalculate"
SERVICE_APPLY_TARGET: Final = "apply_target"
SERVICE_CLEAR_OVERRIDE: Final = "clear_override"
SERVICE_SET_OPTION: Final = "set_option"
SERVICE_WIGGLE: Final = "wiggle"
SERVICE_RELEASE_DEFERRED: Final = "release_deferred"
SERVICE_SET_LOCK: Final = "set_lock"

ATTR_POSITION: Final = "position"
ATTR_NAMED_POSITION: Final = "named_position"
ATTR_RESPECT_RULES: Final = "respect_rules"
ATTR_OPTION: Final = "option"
ATTR_VALUE: Final = "value"
ATTR_TARGET_PROFILE: Final = "profile"
ATTR_MODE: Final = "mode"
ATTR_DURATION: Final = "duration"

# Positions that can be driven by name (setting key suffix after "pos_")
NAMED_POSITIONS: Final = (
    "open",
    "closed",
    "sleep",
    "ventilate",
    "comfort",
    "shading",
    "privacy",
)

# Interval of the check of brightness, sun elevation and privacy (seconds)
TICK_SECONDS: Final = 60

# Refresh interval of the weather forecast (seconds)
FORECAST_SECONDS: Final = 1800

# Number of decisions kept per cover for diagnostics
DECISION_HISTORY: Final = 50

"""Constants for AutoShuttersControl for HA."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "autoshutterscontrol"

SUBENTRY_PROFILE: Final = "profile"
SUBENTRY_COVER: Final = "cover"

# Keys inside subentry data
CONF_COVER_ENTITY: Final = "cover_entity"
CONF_PROFILE: Final = "profile"
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

# Global runtime switches (stored, not part of the settings)
SWITCH_AUTOMATIC: Final = "automatic"
SWITCH_WEEKEND_TIMES: Final = "weekend_times"
SWITCH_MORNING: Final = "morning"
SWITCH_EVENING: Final = "evening"
SWITCH_PAUSE: Final = "pause"
SWITCH_COMFORT: Final = "comfort"
SWITCH_SHADING: Final = "shading"
SWITCH_SELF_DEFENSE: Final = "self_defense"

GLOBAL_SWITCHES: Final = {
    SWITCH_AUTOMATIC: True,
    SWITCH_WEEKEND_TIMES: True,
    SWITCH_MORNING: True,
    SWITCH_EVENING: True,
    SWITCH_PAUSE: False,
    SWITCH_COMFORT: False,
    SWITCH_SHADING: True,
    SWITCH_SELF_DEFENSE: False,
}

# Per cover runtime switches
COVER_SWITCHES: Final = {
    SWITCH_AUTOMATIC: True,
    SWITCH_PAUSE: False,
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

ATTR_POSITION: Final = "position"
ATTR_NAMED_POSITION: Final = "named_position"
ATTR_RESPECT_RULES: Final = "respect_rules"
ATTR_OPTION: Final = "option"
ATTR_VALUE: Final = "value"
ATTR_TARGET_PROFILE: Final = "profile"

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

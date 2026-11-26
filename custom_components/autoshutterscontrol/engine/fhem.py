"""Import from FHEM: read the ASC device and the shutters with ``ASC 1/2`` from fhem.cfg.

Only the ``define`` and ``attr`` lines are used. FHEM device names in the
attributes (sensors, window contacts, residents) become references that the
user maps to Home Assistant entities; each shutter is mapped to a cover.
Attributes with Perl code or without a counterpart are listed as not
transferable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import time
import difflib
import re
from typing import Any

from .settings import BY_KEY, LEVEL_COVER, LEVEL_GLOBAL, Setting


@dataclass(frozen=True)
class Ref:
    """Reference to a FHEM device, to be replaced by a Home Assistant entity."""

    device: str


@dataclass
class FhemImport:
    """Result of reading fhem.cfg."""

    asc_device: str | None = None
    global_settings: dict[str, Any] = field(default_factory=dict)
    shutters: dict[str, dict[str, Any]] = field(default_factory=dict)
    not_transferred: list[str] = field(default_factory=list)

    def references(self) -> list[str]:
        """FHEM devices used in the attributes (not the shutters), sorted."""
        found: set[str] = set()
        for values in (self.global_settings, *self.shutters.values()):
            for value in values.values():
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, Ref):
                        found.add(item.device)
        return sorted(found - set(self.shutters))


# --- reading fhem.cfg ---------------------------------------------------------

_ATTR = re.compile(r"^\s*attr\s+(\S+)\s+(\S+)(?:\s+(.*))?$")
_DEFINE = re.compile(r"^\s*define\s+(\S+)\s+(\S+)(?:\s+(.*))?$")


def _lines(text: str) -> Iterable[str]:
    """Logical lines: continuation lines (ending with a backslash) are joined."""
    buffer = ""
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.endswith("\\"):
            buffer += line[:-1] + "\n"
            continue
        yield buffer + line
        buffer = ""
    if buffer:
        yield buffer


def read(text: str) -> tuple[str | None, dict[str, dict[str, str]], dict[str, str]]:
    """(ASC device, attributes per device, type per device) of a fhem.cfg."""
    attrs: dict[str, dict[str, str]] = {}
    types: dict[str, str] = {}
    asc = None
    for line in _lines(text):
        if line.lstrip().startswith("#"):
            continue
        if match := _DEFINE.match(line):
            name, kind = match.group(1), match.group(2)
            types[name] = kind
            if kind == "AutoShuttersControl" and asc is None:
                asc = name
            continue
        if match := _ATTR.match(line):
            name, key, value = match.groups()
            attrs.setdefault(name, {})[key] = (value or "").strip()
    return asc, attrs, types


# --- converting values ----------------------------------------------------------


def _int(value: str) -> int:
    return int(round(float(value)))


def _float(value: str) -> float:
    return float(value)


def _time(value: str) -> time:
    parts = [int(p) for p in value.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0] % 24, parts[1], parts[2])


def _onoff(value: str) -> bool:
    return value.strip().lower() in ("on", "1", "yes", "true")


def _device(value: str) -> Ref:
    """``DEVICE[:READING] ...`` -> reference to DEVICE."""
    return Ref(value.split()[0].split(":")[0])


def _numbers(text: str) -> list[float]:
    return [float(p) for p in re.split(r"[:,]", text) if p.strip()]


_UP_DOWN = {"time": "time", "astro": "astro", "brightness": "brightness", "roommate": "residents"}
_PRESENCE = {"always": "always", "home": "home", "absent": "absent", "off": "off"}
_TWILIGHT = {
    "real": "real",
    "civil": "civil",
    "nautic": "nautical",
    "astronomic": "astronomical",
    "horizon": "horizon",
}

# Simple attributes: ASC attribute -> (setting, converter)
_SIMPLE: dict[str, tuple[str, Any]] = {
    "ASC_Open_Pos": ("pos_open", _int),
    "ASC_Closed_Pos": ("pos_closed", _int),
    "ASC_Ventilate_Pos": ("pos_ventilate", _int),
    "ASC_ComfortOpen_Pos": ("pos_comfort", _int),
    "ASC_Shading_Pos": ("pos_shading", _int),
    "ASC_Sleep_Pos": ("pos_sleep", _int),
    "ASC_Antifreeze_Pos": ("pos_frost", _int),
    "ASC_PrivacyDown_Pos": ("pos_privacy", _int),
    "ASC_WindProtection": ("wind_protection", _onoff),
    "ASC_RainProtection": ("rain_protection", _onoff),
    "ASC_Ventilate_Window_Open": ("ventilate_enabled", _onoff),
    "ASC_Partymode": ("party", _onoff),
    "ASC_Adv": ("advent", _onoff),
    "ASC_WiggleValue": ("wiggle_value", _int),
    "ASC_Time_Up_Early": ("time_up_early_workday", _time),
    "ASC_Time_Up_Late": ("time_up_late_workday", _time),
    "ASC_Time_Down_Early": ("time_down_early_workday", _time),
    "ASC_Time_Down_Late": ("time_down_late_workday", _time),
    "ASC_Drive_Delay": ("delay_random", _int),
    "ASC_Drive_DelayStart": ("delay_fixed", _int),
    "ASC_shuttersDriveDelay": ("drive_stagger", _int),
    "ASC_DriveUpMaxDuration": ("drive_time", _int),
    "ASC_Shading_Min_OutsideTemperature": ("shading_temp_out_min", _float),
    "ASC_freezeTemp": ("frost_temp", _float),
    "ASC_autoAstroModeMorningHorizon": ("horizon_up", _float),
    "ASC_autoAstroModeEveningHorizon": ("horizon_down", _float),
    "ASC_TempSensor": ("indoor_temperature_sensor", _device),
    "ASC_windSensor": ("wind_sensor", _device),
    "ASC_tempSensor": ("outdoor_temperature_sensor", _device),
}

# Attributes that are known but have no counterpart (no message for them)
_IGNORED = frozenset(
    {
        "ASC",
        "ASC_expert",
        "ASC_debug",
        "ASC_Pos_Reading",
        "ASC_Shutter_IdleDetection",
        "ASC_Shutter_IdleDetectionValue",
        "ASC_twilightDevice",
        "ASC_WindowRec_subType",
        "ASC_Up_safe",
        "ASC_Down_safe",
        "ASC_slatDriveCmdInverse",
        "ASC_SlatPosCmd_SlatDevice",
    }
)


def _convert(attrs: Mapping[str, str], out: dict[str, Any], skipped: list[str], who: str) -> None:
    """Convert the ASC attributes of one device into settings."""
    for key, value in attrs.items():
        if not key.startswith("ASC") or key in _IGNORED:
            continue
        if "{" in value:
            skipped.append(f"{who}: {key} (Perl)")
            continue
        try:
            if not _convert_one(key, value, out):
                skipped.append(f"{who}: {key}")
        except (ValueError, IndexError):
            skipped.append(f"{who}: {key} = {value}")


def _convert_one(key: str, value: str, out: dict[str, Any]) -> bool:  # noqa: C901
    """Convert one attribute; False if it has no counterpart."""
    lower = value.strip().lower()
    if key in _SIMPLE:
        setting, conv = _SIMPLE[key]
        out[setting] = conv(value)
        return True
    if key in ("ASC_Up", "ASC_Down"):
        if lower not in _UP_DOWN:
            return False
        out["up_mode" if key == "ASC_Up" else "down_mode"] = _UP_DOWN[lower]
        return True
    if key in ("ASC_Mode_Up", "ASC_Mode_Down", "ASC_Shading_Mode"):
        if lower not in _PRESENCE:
            return False
        out[
            {"ASC_Mode_Up": "presence_up", "ASC_Mode_Down": "presence_down"}.get(
                key, "shading_mode"
            )
        ] = _PRESENCE[lower]
        return True
    if key in ("ASC_autoAstroModeMorning", "ASC_autoAstroModeEvening"):
        if lower not in _TWILIGHT:
            return False
        out["twilight_up" if key.endswith("Morning") else "twilight_down"] = _TWILIGHT[lower]
        return True
    if key == "ASC_Time_Up_WE_Holiday":
        out["time_up_early_free"] = _time(value)
        out["time_up_late_free"] = _time(value)
        return True
    if key == "ASC_LockOut":
        if lower not in ("off", "soft", "hard"):
            return False
        out["lockout"] = lower
        return True
    if key == "ASC_Antifreeze":
        if lower not in ("off", "soft", "hard", "am", "pm"):
            return False
        out["frost_mode"] = lower
        return True
    if key == "ASC_Self_Defense_Mode":
        if lower not in ("off", "absent", "gone"):
            return False
        out["self_defense_mode"] = lower
        return True
    if key == "ASC_Self_Defense_Exclude":
        if _onoff(value):
            out["self_defense_mode"] = "off"
        return True
    if key == "ASC_BlockingTime_afterManual":
        out["override_minutes"] = max(1, round(_int(value) / 60))
        out["override_reset"] = "minutes"
        return True
    if key in ("ASC_PrivacyDownValue_beforeNightClose", "ASC_PrivacyUpValue_beforeDayOpen"):
        minutes = round(_int(value) / 60)
        out["privacy_down_minutes" if "Down" in key else "privacy_up_minutes"] = minutes
        return True
    if key == "ASC_Shading_MinMax_Elevation":
        numbers = _numbers(value)
        out["shading_elevation_min"] = numbers[0]
        if len(numbers) > 1:
            out["shading_elevation_max"] = numbers[1]
        return True
    if key == "ASC_Shading_StateChange_SunnyCloudy":
        numbers = _numbers(value)
        out["shading_brightness_start"] = int(numbers[0])
        out["shading_brightness_end"] = int(numbers[1])
        return True
    if key == "ASC_Shading_WaitingPeriod":
        minutes = round(_int(value) / 60)
        out["shading_delay_start"] = minutes
        out["shading_delay_end"] = minutes
        return True
    if key == "ASC_brightnessDriveUpDown":
        numbers = _numbers(value)
        out["brightness_up"] = int(numbers[0])
        out["brightness_down"] = int(numbers[1])
        return True
    if key == "ASC_BrightnessSensor":
        parts = value.split()
        out["brightness_sensor"] = _device(parts[0])
        if len(parts) > 1:
            numbers = _numbers(parts[1])
            out["brightness_up"] = int(numbers[0])
            if len(numbers) > 1:
                out["brightness_down"] = int(numbers[1])
        return True
    if key == "ASC_WindParameters":
        parts = value.split()
        numbers = _numbers(parts[0])
        out["wind_threshold"] = numbers[0]
        if len(numbers) > 1:
            out["wind_hysteresis"] = numbers[1]
        if len(parts) > 1:
            out["pos_wind"] = _int(parts[1])
        return True
    if key == "ASC_rainSensor":
        parts = value.split()
        out["rain_sensor"] = _device(parts[0])
        if len(parts) > 1:
            numbers = _numbers(parts[1])
            out["rain_threshold"] = numbers[0]
            if len(numbers) > 1:
                out["rain_hysteresis"] = numbers[1]
        if len(parts) > 2:
            out["pos_rain"] = _int(parts[2])
        return True
    if key == "ASC_WindowRec":
        out["window_state_sensor"] = _device(value)
        return True
    if key in ("ASC_Roommate_Device", "ASC_residentsDev"):
        devices = [Ref(d.split(":")[0]) for d in re.split(r"[,\s]+", value) if d]
        out["residents_room" if key == "ASC_Roommate_Device" else "residents_house"] = devices
        return True
    if key == "ASC_ExternalTrigger":
        # DEVICE:READING VALUEACTIVE[:VALUEINACTIVE] POSACTIVE[:POSINACTIVE]
        parts = value.split()
        out["trigger_entity"] = _device(parts[0])
        out["trigger_value"] = parts[1].split(":")[0]
        out["trigger_position"] = _int(parts[2].split(":")[0])
        return True
    if key == "ASC_Shading_Direction":
        out["_direction"] = _float(value)
        return True
    if key in ("ASC_Shading_Angle_Left", "ASC_Shading_Angle_Right"):
        out["_left" if key.endswith("Left") else "_right"] = _float(value)
        return True
    return False


def _sun_range(out: dict[str, Any]) -> None:
    """Shading direction +- angles -> azimuth range."""
    direction = out.pop("_direction", None)
    left = out.pop("_left", None)
    right = out.pop("_right", None)
    if direction is None:
        return
    out["shading_azimuth_start"] = int(round(direction - (left if left is not None else 75))) % 360
    out["shading_azimuth_end"] = int(round(direction + (right if right is not None else 75))) % 360


def convert(text: str) -> FhemImport:
    """Read fhem.cfg and convert the ASC device and its shutters."""
    asc, attrs, _types = read(text)
    result = FhemImport(asc_device=asc)
    if asc is not None:
        _convert(attrs.get(asc, {}), result.global_settings, result.not_transferred, asc)
        _sun_range(result.global_settings)
    for name, values in attrs.items():
        if name == asc or values.get("ASC") not in ("1", "2"):
            continue
        settings: dict[str, Any] = {}
        _convert(values, settings, result.not_transferred, name)
        _sun_range(settings)
        result.shutters[name] = settings
    return result


# --- mapping to Home Assistant ----------------------------------------------------


def _norm(text: str) -> str:
    text = text.lower()
    for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    return re.sub(r"[^a-z0-9]", "", text)


def suggest(device: str, candidates: Mapping[str, str], minimum: float = 0.6) -> str | None:
    """Entity whose id or name is most similar to the FHEM device name."""
    target = _norm(device)
    best, best_score = None, minimum
    for entity_id, name in candidates.items():
        for text in (entity_id.split(".", 1)[-1], name):
            score = difflib.SequenceMatcher(None, target, _norm(text)).ratio()
            if score > best_score:
                best, best_score = entity_id, score
    return best


def resolve(
    values: Mapping[str, Any], mapping: Mapping[str, str | None], level: str
) -> tuple[dict[str, Any], list[str]]:
    """Replace references by entities; drop settings not allowed on the level."""
    out: dict[str, Any] = {}
    unmapped: list[str] = []
    for key, value in values.items():
        setting: Setting | None = BY_KEY.get(key)
        if setting is None or level not in setting.levels:
            continue
        if isinstance(value, list):
            entities = [mapping.get(v.device) if isinstance(v, Ref) else v for v in value]
            unmapped += [
                v.device for v in value if isinstance(v, Ref) and not mapping.get(v.device)
            ]
            value = [e for e in entities if e]
            if not value:
                continue
        elif isinstance(value, Ref):
            entity = mapping.get(value.device)
            if not entity:
                unmapped.append(value.device)
                continue
            value = entity
        out[key] = value
    return out, unmapped


def without_defaults(values: Mapping[str, Any], inherited: Mapping[str, Any]) -> dict[str, Any]:
    """Only the values that differ from what is inherited (or the default)."""
    out = {}
    for key, value in values.items():
        base = inherited.get(key, BY_KEY[key].default)
        if isinstance(base, tuple):
            base = list(base)
        if value != base:
            out[key] = value
    return out


@dataclass
class Plan:
    """What the import creates."""

    global_settings: dict[str, Any] = field(default_factory=dict)
    # (cover entity, title, settings)
    covers: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    skipped_shutters: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)


def plan(
    imp: FhemImport,
    covers: Mapping[str, str | None],
    entities: Mapping[str, str | None],
    current_global: Mapping[str, Any],
    defaults_of: Any,
) -> Plan:
    """Combine the converted values and the mapping into what is created.

    ``defaults_of(global_settings)`` returns the effective global values (python
    values) used to drop cover values that only repeat them. A value that all
    imported shutters share is moved to the global settings.
    """
    result = Plan()
    global_values, unmapped = resolve(imp.global_settings, entities, LEVEL_GLOBAL)
    per_cover: list[tuple[str, str, dict[str, Any]]] = []
    for name, values in imp.shutters.items():
        cover = covers.get(name)
        if not cover:
            result.skipped_shutters.append(name)
            continue
        cover_values, missing = resolve(values, entities, LEVEL_COVER)
        unmapped += missing
        per_cover.append((cover, name, cover_values))
    # Values that every shutter has with the same value -> global
    if len(per_cover) > 1:
        shared = set.intersection(*(set(v) for _c, _n, v in per_cover))
        for key in sorted(shared):
            first = per_cover[0][2][key]
            if LEVEL_GLOBAL in BY_KEY[key].levels and all(
                v[key] == first for _c, _n, v in per_cover
            ):
                global_values.setdefault(key, first)
                for _c, _n, v in per_cover:
                    v.pop(key)
    effective_defaults = {key: s.default for key, s in BY_KEY.items()}
    result.global_settings = without_defaults(global_values, effective_defaults)
    inherited = defaults_of({**current_global, **result.global_settings})
    for cover, name, values in per_cover:
        result.covers.append((cover, name, without_defaults(values, inherited)))
    result.unmapped = sorted(set(unmapped))
    return result

"""Resolve settings: cover -> profile -> global -> default.

An empty value (missing key or ``None``) means "inherit".
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .settings import BY_KEY, LEVEL_COVER, LEVEL_GLOBAL, LEVEL_PROFILE, SETTINGS, from_storage

SOURCE_DEFAULT = "default"


class ResolvedConfig(Mapping[str, Any]):
    """Effective settings of one cover with the source of each value."""

    def __init__(self, values: dict[str, Any], sources: dict[str, str]) -> None:
        self._values = values
        self._sources = sources

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def source(self, key: str) -> str:
        """Return where the value comes from (cover, profile, global, default)."""
        return self._sources[key]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return values and sources for diagnostics."""
        out: dict[str, dict[str, Any]] = {}
        for key, value in self._values.items():
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            elif isinstance(value, tuple):
                value = list(value)
            out[key] = {"value": value, "source": self._sources[key]}
        return out


def _is_set(layer: Mapping[str, Any] | None, key: str) -> bool:
    if not layer:
        return False
    value = layer.get(key)
    if value is None:
        return False
    if isinstance(value, str) and value == "":
        return False
    return True


def resolve(
    global_settings: Mapping[str, Any] | None,
    profile_settings: Mapping[str, Any] | None = None,
    cover_settings: Mapping[str, Any] | None = None,
) -> ResolvedConfig:
    """Resolve all settings for one cover."""
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    layers = (
        (LEVEL_COVER, cover_settings),
        (LEVEL_PROFILE, profile_settings),
        (LEVEL_GLOBAL, global_settings),
    )
    for setting in SETTINGS:
        for level, layer in layers:
            if level not in setting.levels:
                continue
            if _is_set(layer, setting.key):
                values[setting.key] = from_storage(setting, layer[setting.key])  # type: ignore[index]
                sources[setting.key] = level
                break
        else:
            values[setting.key] = setting.default
            sources[setting.key] = SOURCE_DEFAULT
    return ResolvedConfig(values, sources)


def inherited_value(
    key: str,
    level: str,
    global_settings: Mapping[str, Any] | None,
    profile_settings: Mapping[str, Any] | None = None,
) -> tuple[Any, str]:
    """Return the value a field on ``level`` would inherit, and its source."""
    setting = BY_KEY[key]
    if level == LEVEL_COVER and LEVEL_PROFILE in setting.levels and _is_set(profile_settings, key):
        return from_storage(setting, profile_settings[key]), LEVEL_PROFILE  # type: ignore[index]
    if level in (LEVEL_COVER, LEVEL_PROFILE) and _is_set(global_settings, key):
        return from_storage(setting, global_settings[key]), LEVEL_GLOBAL  # type: ignore[index]
    return setting.default, SOURCE_DEFAULT

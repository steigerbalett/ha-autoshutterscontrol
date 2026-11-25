"""Config flow: main entry, options, subentries "profile" and "cover".

All forms are built from the settings registry (engine/settings.py).
On the profile and cover level an empty field means "inherit".
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import time
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector, translation
import voluptuous as vol

from .const import (
    CONF_COVER_ENTITY,
    CONF_NAME,
    CONF_PROFILE,
    CONF_PROFILE_ALT,
    CONF_PROFILE_SWITCH,
    CONF_PROFILE_SWITCH_VALUE,
    CONF_SETTINGS,
    DOMAIN,
    INHERIT,
    SUBENTRY_COVER,
    SUBENTRY_PROFILE,
)
from .engine import fhem
from .engine.resolve import inherited_value, resolve
from .engine.settings import (
    ACTION,
    BOOL,
    BY_KEY,
    CONDITION,
    ENTITIES,
    ENTITY,
    FLOAT,
    INT,
    LEVEL_COVER,
    LEVEL_GLOBAL,
    LEVEL_PROFILE,
    MULTI,
    SELECT,
    TEXT,
    TIME,
    Setting,
    sections_for,
    settings_for,
    to_storage,
)

TITLE = "AutoShuttersControl"
NO_PROFILE = "none"
ON = "on"
OFF = "off"
NONE_OPTION = "none"
STEP_SAVE = "save"
STEP_RESET = "reset"
STEP_BASE = "base"
STEP_FHEM = "fhem_import"
CONF_FHEM_CFG = "fhem_cfg"


# --- form helpers ---------------------------------------------------------


def _selector(setting: Setting, inherit: bool) -> selector.Selector:
    kind = setting.kind
    if kind == BOOL:
        if not inherit:
            return selector.BooleanSelector()
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[INHERIT, ON, OFF],
                translation_key="tristate",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    if kind in (INT, FLOAT):
        config = selector.NumberSelectorConfig(
            min=setting.minimum,
            max=setting.maximum,
            step=setting.step,
            mode=selector.NumberSelectorMode.BOX,
        )
        if setting.unit:
            config["unit_of_measurement"] = setting.unit
        return selector.NumberSelector(config)
    if kind == TIME:
        return selector.TimeSelector()
    if kind == SELECT:
        options = [INHERIT, *setting.options] if inherit else list(setting.options)
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                translation_key=setting.key,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    if kind == MULTI:
        options = [*setting.options, NONE_OPTION] if inherit else list(setting.options)
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                translation_key=setting.key,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
    if kind == TEXT:
        return selector.TextSelector()
    if kind == ENTITY:
        config = (
            selector.EntitySelectorConfig(domain=list(setting.domains))
            if setting.domains
            else selector.EntitySelectorConfig()
        )
        return selector.EntitySelector(config)
    if kind == ENTITIES:
        return selector.EntitySelector(
            selector.EntitySelectorConfig(domain=list(setting.domains), multiple=True)
        )
    if kind == CONDITION:
        return selector.ConditionSelector()
    if kind == ACTION:
        return selector.ActionSelector()
    raise ValueError(kind)


def _form_value(setting: Setting, stored: Any, inherit: bool) -> Any:
    """Stored value -> value shown in the form."""
    if stored is None:
        if setting.kind == SELECT and inherit:
            return INHERIT
        if setting.kind == BOOL and inherit:
            return INHERIT
        return None
    if setting.kind == BOOL and inherit:
        return ON if stored else OFF
    if setting.kind == MULTI and inherit and not stored:
        return [NONE_OPTION]
    return stored


def _stored_value(setting: Setting, value: Any, inherit: bool) -> Any:
    """Form value -> stored value (None = inherit / default)."""
    if value is None or value == "":
        return None
    if setting.kind == BOOL and inherit:
        if value == INHERIT:
            return None
        return value == ON
    if setting.kind == SELECT and value == INHERIT:
        return None
    if setting.kind in (ENTITIES, CONDITION, ACTION):
        return to_storage(setting, value) if value else None
    if setting.kind == MULTI:
        values = [v for v in value if v != NONE_OPTION]
        if inherit and not values and NONE_OPTION not in value:
            return None
        return to_storage(setting, values)
    return to_storage(setting, value)


def _display(setting: Setting, value: Any) -> str:
    """Inherited value as short text for the field description."""
    if value is None:
        return "–"
    if setting.kind == BOOL:
        return "✓" if value else "✗"
    if setting.kind == TIME and isinstance(value, time):
        return value.strftime("%H:%M")
    if setting.kind in (MULTI, ENTITIES):
        return ", ".join(value) if value else "–"
    if setting.kind in (CONDITION, ACTION):
        return f"{len(value)} ×" if value else "–"
    if setting.kind == INT and setting.unit:
        return f"{value} {setting.unit}"
    if setting.kind == FLOAT and setting.unit:
        return f"{value:g} {setting.unit}"
    return str(value)


def build_schema(level: str, section: str, current: Mapping[str, Any]) -> vol.Schema:
    """Schema of one section on one level."""
    inherit = level != LEVEL_GLOBAL
    fields: dict[Any, Any] = {}
    for setting in settings_for(level, section):
        stored = current.get(setting.key)
        if (
            level == LEVEL_GLOBAL
            and stored is None
            and setting.kind
            not in (
                ENTITY,
                ENTITIES,
                CONDITION,
                ACTION,
            )
        ):
            stored = to_storage(setting, setting.default)
        shown = _form_value(setting, stored, inherit)
        if shown is None:
            key = vol.Optional(setting.key)
        else:
            key = vol.Optional(setting.key, description={"suggested_value": shown})
        fields[key] = _selector(setting, inherit)
    return vol.Schema(fields)


def apply_section(
    level: str, section: str, current: Mapping[str, Any], user_input: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge the input of a section into the stored settings."""
    inherit = level != LEVEL_GLOBAL
    result = dict(current)
    for setting in settings_for(level, section):
        value = _stored_value(setting, user_input.get(setting.key), inherit)
        if value is None:
            result.pop(setting.key, None)
        else:
            result[setting.key] = value
    return result


def inherited_placeholders(
    level: str,
    section: str,
    global_settings: Mapping[str, Any],
    profile_settings: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Placeholders {inh_<key>} with the inherited value of every field."""
    out: dict[str, str] = {}
    for setting in settings_for(level, section):
        value, _source = inherited_value(setting.key, level, global_settings, profile_settings)
        out[f"inh_{setting.key}"] = _display(setting, value)
    return out


def _reset_schema(level: str, current: Mapping[str, Any]) -> vol.Schema:
    keys = [s.key for s in settings_for(level) if s.key in current]
    return vol.Schema(
        {
            vol.Optional("keys", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=keys,
                    translation_key="setting_key",
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _optional(key: str, value: Any) -> vol.Optional:
    """Optional field that shows the stored value (and can be cleared)."""
    if value in (None, ""):
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


def _effective(values: Mapping[str, Any]) -> dict[str, Any]:
    """Effective global values (python values) of stored settings."""
    cfg = resolve(values)
    return {key: cfg[key] for key in BY_KEY}


# --- main entry -----------------------------------------------------------


class AscConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the one main entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Global sensors, then done."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            settings = apply_section(LEVEL_GLOBAL, "sensors", {}, user_input)
            return self.async_create_entry(title=TITLE, data={}, options={CONF_SETTINGS: settings})
        return self.async_show_form(
            step_id="user", data_schema=build_schema(LEVEL_GLOBAL, "sensors", {})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Global settings."""
        return AscOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Profiles and covers."""
        return {SUBENTRY_PROFILE: ProfileSubentryFlow, SUBENTRY_COVER: CoverSubentryFlow}


class AscOptionsFlow(OptionsFlow):
    """Global settings, one page per section."""

    def __init__(self) -> None:
        self._settings: dict[str, Any] | None = None
        self._fhem: fhem.FhemImport | None = None
        self._fhem_covers: dict[str, str | None] = {}
        self._fhem_plan: fhem.Plan | None = None

    @property
    def settings(self) -> dict[str, Any]:
        if self._settings is None:
            self._settings = dict(self.config_entry.options.get(CONF_SETTINGS, {}))
        return self._settings

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[*sections_for(LEVEL_GLOBAL), STEP_FHEM, STEP_RESET, STEP_SAVE],
        )

    async def _section(self, section: str, user_input: dict[str, Any] | None) -> ConfigFlowResult:
        if user_input is not None:
            self._settings = apply_section(LEVEL_GLOBAL, section, self.settings, user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id=section, data_schema=build_schema(LEVEL_GLOBAL, section, self.settings)
        )

    async def async_step_schedule(self, user_input=None) -> ConfigFlowResult:
        """Schedule."""
        return await self._section("schedule", user_input)

    async def async_step_sensors(self, user_input=None) -> ConfigFlowResult:
        """Sensors."""
        return await self._section("sensors", user_input)

    async def async_step_positions(self, user_input=None) -> ConfigFlowResult:
        """Positions."""
        return await self._section("positions", user_input)

    async def async_step_drive(self, user_input=None) -> ConfigFlowResult:
        """Drive behaviour."""
        return await self._section("drive", user_input)

    async def async_step_override(self, user_input=None) -> ConfigFlowResult:
        """Manual override."""
        return await self._section("override", user_input)

    async def async_step_light(self, user_input=None) -> ConfigFlowResult:
        """Brightness and sun elevation."""
        return await self._section("light", user_input)

    async def async_step_window(self, user_input=None) -> ConfigFlowResult:
        """Window contacts."""
        return await self._section("window", user_input)

    async def async_step_privacy(self, user_input=None) -> ConfigFlowResult:
        """Privacy."""
        return await self._section("privacy", user_input)

    async def async_step_residents(self, user_input=None) -> ConfigFlowResult:
        """Residents and self defense."""
        return await self._section("residents", user_input)

    async def async_step_shading(self, user_input=None) -> ConfigFlowResult:
        """Shading."""
        return await self._section("shading", user_input)

    async def async_step_tilt(self, user_input=None) -> ConfigFlowResult:
        """Slats."""
        return await self._section("tilt", user_input)

    async def async_step_protection(self, user_input=None) -> ConfigFlowResult:
        """Rain, wind and frost."""
        return await self._section("protection", user_input)

    async def async_step_special(self, user_input=None) -> ConfigFlowResult:
        """Force, pause, party, advent, trigger, wiggle."""
        return await self._section("special", user_input)

    async def async_step_extra(self, user_input=None) -> ConfigFlowResult:
        """Extra conditions and actions."""
        return await self._section("extra", user_input)

    async def async_step_reset(self, user_input=None) -> ConfigFlowResult:
        """Reset fields to the default."""
        if user_input is not None:
            for key in user_input.get("keys", []):
                self.settings.pop(key, None)
            return await self.async_step_init()
        return self.async_show_form(
            step_id=STEP_RESET, data_schema=_reset_schema(LEVEL_GLOBAL, self.settings)
        )

    async def async_step_save(self, user_input=None) -> ConfigFlowResult:
        """Save."""
        return self.async_create_entry(
            data={**self.config_entry.options, CONF_SETTINGS: self.settings}
        )

    # --- import from FHEM ---------------------------------------------------

    def _candidates(self, domain: str | None = None) -> dict[str, str]:
        return {
            state.entity_id: str(state.attributes.get("friendly_name", state.entity_id))
            for state in self.hass.states.async_all(domain)
        }

    async def async_step_fhem_import(self, user_input=None) -> ConfigFlowResult:
        """Paste fhem.cfg (or the lines of the ASC device and the shutters)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._fhem = fhem.convert(user_input.get(CONF_FHEM_CFG, ""))
            if not self._fhem.shutters and not self._fhem.global_settings:
                errors[CONF_FHEM_CFG] = "fhem_nothing_found"
            else:
                return await self.async_step_fhem_covers()
        return self.async_show_form(
            step_id=STEP_FHEM,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FHEM_CFG): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_fhem_covers(self, user_input=None) -> ConfigFlowResult:
        """FHEM shutter -> Home Assistant cover."""
        assert self._fhem is not None
        if user_input is not None or not self._fhem.shutters:
            self._fhem_covers = dict(user_input or {})
            return await self.async_step_fhem_entities()
        covers = self._candidates("cover")
        fields: dict[Any, Any] = {}
        for name in self._fhem.shutters:
            guess = fhem.suggest(name, covers)
            key = (
                vol.Optional(name, description={"suggested_value": guess})
                if guess
                else vol.Optional(name)
            )
            fields[key] = selector.EntitySelector(selector.EntitySelectorConfig(domain="cover"))
        return self.async_show_form(
            step_id="fhem_covers",
            data_schema=vol.Schema(fields),
            description_placeholders={"count": str(len(self._fhem.shutters))},
        )

    async def async_step_fhem_entities(self, user_input=None) -> ConfigFlowResult:
        """FHEM sensors, contacts, residents -> Home Assistant entities."""
        assert self._fhem is not None
        references = self._fhem.references()
        if user_input is not None or not references:
            self._fhem_plan = fhem.plan(
                self._fhem,
                self._fhem_covers,
                dict(user_input or {}),
                self.settings,
                lambda values: _effective(values),
            )
            return await self.async_step_fhem_done()
        entities = self._candidates()
        fields: dict[Any, Any] = {}
        for name in references:
            guess = fhem.suggest(name, entities)
            key = (
                vol.Optional(name, description={"suggested_value": guess})
                if guess
                else vol.Optional(name)
            )
            fields[key] = selector.EntitySelector()
        return self.async_show_form(step_id="fhem_entities", data_schema=vol.Schema(fields))

    async def async_step_fhem_done(self, user_input=None) -> ConfigFlowResult:
        """Summary, then create the covers and save the global settings."""
        plan = self._fhem_plan
        assert plan is not None and self._fhem is not None
        entry = self.config_entry
        existing = {
            sub.data.get(CONF_COVER_ENTITY)
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_COVER
        }
        new = [c for c in plan.covers if c[0] not in existing]
        if user_input is not None:
            for key, value in plan.global_settings.items():
                self.settings[key] = to_storage(BY_KEY[key], value)
            for cover, _name, values in new:
                state = self.hass.states.get(cover)
                title = str(state.attributes.get("friendly_name", cover)) if state else cover
                self.hass.config_entries.async_add_subentry(
                    entry,
                    ConfigSubentry(
                        data={
                            CONF_COVER_ENTITY: cover,
                            CONF_PROFILE: None,
                            CONF_SETTINGS: {k: to_storage(BY_KEY[k], v) for k, v in values.items()},
                        },
                        subentry_type=SUBENTRY_COVER,
                        title=title,
                        unique_id=cover,
                    ),
                )
            return await self.async_step_save()
        dash = "–"
        texts = await translation.async_get_translations(
            self.hass, self.hass.config.language, "options", [DOMAIN]
        )

        def label(key: str) -> str:
            section = BY_KEY[key].section
            return texts.get(f"component.{DOMAIN}.options.step.{section}.data.{key}", key)

        return self.async_show_form(
            step_id="fhem_done",
            data_schema=vol.Schema({}),
            description_placeholders={
                "global": ", ".join(sorted(label(k) for k in plan.global_settings)) or dash,
                "covers": ", ".join(f"{name} → {cover}" for cover, name, _v in new) or dash,
                "existing": ", ".join(c for c, _n, _v in plan.covers if c in existing) or dash,
                "skipped": ", ".join(plan.skipped_shutters) or dash,
                "unmapped": ", ".join(plan.unmapped) or dash,
                "not_transferred": ", ".join(self._fhem.not_transferred) or dash,
            },
        )


# --- subentries -------------------------------------------------------------


class _SettingsSubentryFlow(ConfigSubentryFlow):
    """Menu with sections, reset and save for profiles and covers."""

    level: str

    def __init__(self) -> None:
        self._data: dict[str, Any] = {CONF_SETTINGS: {}}
        self._title: str | None = None

    @property
    def settings(self) -> dict[str, Any]:
        return self._data[CONF_SETTINGS]

    def _load(self) -> None:
        sub = self._get_reconfigure_subentry()
        self._data = {**sub.data, CONF_SETTINGS: dict(sub.data.get(CONF_SETTINGS, {}))}
        self._title = sub.title

    def _profile_settings(self) -> Mapping[str, Any] | None:
        return None

    def _menu(self) -> SubentryFlowResult:
        return self.async_show_menu(
            step_id="menu",
            menu_options=[STEP_BASE, *sections_for(self.level), STEP_RESET, STEP_SAVE],
            description_placeholders={"name": self._title or ""},
        )

    async def async_step_menu(self, user_input=None) -> SubentryFlowResult:
        """Menu."""
        return self._menu()

    async def _section(self, section: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        if user_input is not None:
            self._data[CONF_SETTINGS] = apply_section(
                self.level, section, self.settings, user_input
            )
            return self._menu()
        entry = self._get_entry()
        return self.async_show_form(
            step_id=section,
            data_schema=build_schema(self.level, section, self.settings),
            description_placeholders=inherited_placeholders(
                self.level, section, entry.options.get(CONF_SETTINGS, {}), self._profile_settings()
            ),
        )

    async def async_step_schedule(self, user_input=None) -> SubentryFlowResult:
        """Schedule."""
        return await self._section("schedule", user_input)

    async def async_step_sensors(self, user_input=None) -> SubentryFlowResult:
        """Sensors."""
        return await self._section("sensors", user_input)

    async def async_step_positions(self, user_input=None) -> SubentryFlowResult:
        """Positions."""
        return await self._section("positions", user_input)

    async def async_step_drive(self, user_input=None) -> SubentryFlowResult:
        """Drive behaviour."""
        return await self._section("drive", user_input)

    async def async_step_override(self, user_input=None) -> SubentryFlowResult:
        """Manual override."""
        return await self._section("override", user_input)

    async def async_step_light(self, user_input=None) -> SubentryFlowResult:
        """Brightness and sun elevation."""
        return await self._section("light", user_input)

    async def async_step_window(self, user_input=None) -> SubentryFlowResult:
        """Window contacts."""
        return await self._section("window", user_input)

    async def async_step_privacy(self, user_input=None) -> SubentryFlowResult:
        """Privacy."""
        return await self._section("privacy", user_input)

    async def async_step_residents(self, user_input=None) -> SubentryFlowResult:
        """Residents and self defense."""
        return await self._section("residents", user_input)

    async def async_step_shading(self, user_input=None) -> SubentryFlowResult:
        """Shading."""
        return await self._section("shading", user_input)

    async def async_step_tilt(self, user_input=None) -> SubentryFlowResult:
        """Slats."""
        return await self._section("tilt", user_input)

    async def async_step_protection(self, user_input=None) -> SubentryFlowResult:
        """Rain, wind and frost."""
        return await self._section("protection", user_input)

    async def async_step_special(self, user_input=None) -> SubentryFlowResult:
        """Force, pause, party, advent, trigger, wiggle."""
        return await self._section("special", user_input)

    async def async_step_extra(self, user_input=None) -> SubentryFlowResult:
        """Extra conditions and actions."""
        return await self._section("extra", user_input)

    async def async_step_reset(self, user_input=None) -> SubentryFlowResult:
        """Back to the inherited value."""
        if user_input is not None:
            for key in user_input.get("keys", []):
                self.settings.pop(key, None)
            return self._menu()
        return self.async_show_form(
            step_id=STEP_RESET, data_schema=_reset_schema(self.level, self.settings)
        )

    async def async_step_save(self, user_input=None) -> SubentryFlowResult:
        """Save."""
        if self.source == "user":
            return self.async_create_entry(title=self._title or "", data=self._data)
        return self.async_update_and_abort(
            self._get_entry(), self._get_reconfigure_subentry(), title=self._title, data=self._data
        )

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        """Edit."""
        self._load()
        return self._menu()


class ProfileSubentryFlow(_SettingsSubentryFlow):
    """A profile groups settings for several covers."""

    level = LEVEL_PROFILE

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        """Name of the new profile."""
        return await self.async_step_base(user_input)

    async def async_step_base(self, user_input=None) -> SubentryFlowResult:
        """Name."""
        if user_input is not None:
            self._title = user_input[CONF_NAME]
            return self._menu()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, description={"suggested_value": self._title}
                ): selector.TextSelector()
            }
        )
        return self.async_show_form(step_id=STEP_BASE, data_schema=schema)


class CoverSubentryFlow(_SettingsSubentryFlow):
    """One cover; several can be added at once."""

    level = LEVEL_COVER

    def _profiles(self) -> dict[str, ConfigSubentry]:
        return {
            sub_id: sub
            for sub_id, sub in self._get_entry().subentries.items()
            if sub.subentry_type == SUBENTRY_PROFILE
        }

    def _profile_settings(self) -> Mapping[str, Any] | None:
        profile = self._profiles().get(self._data.get(CONF_PROFILE) or "")
        return profile.data.get(CONF_SETTINGS, {}) if profile else None

    def _profile_selector(self) -> selector.SelectSelector:
        options = [selector.SelectOptionDict(value=NO_PROFILE, label="–")]
        options += [
            selector.SelectOptionDict(value=sub_id, label=sub.title)
            for sub_id, sub in self._profiles().items()
        ]
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options, mode=selector.SelectSelectorMode.DROPDOWN
            )
        )

    def _configured(self) -> set[str]:
        return {
            sub.data.get(CONF_COVER_ENTITY)
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_COVER
        }

    def _cover_title(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state else entity_id

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        """Choose one or more covers and a profile."""
        errors: dict[str, str] = {}
        if user_input is not None:
            covers = [c for c in user_input[CONF_COVER_ENTITY] if c not in self._configured()]
            profile = user_input.get(CONF_PROFILE)
            profile = None if profile in (None, NO_PROFILE) else profile
            if not covers:
                errors[CONF_COVER_ENTITY] = "no_new_cover"
            else:
                entry = self._get_entry()
                for cover in covers[1:]:
                    self.hass.config_entries.async_add_subentry(
                        entry,
                        ConfigSubentry(
                            data={
                                CONF_COVER_ENTITY: cover,
                                CONF_PROFILE: profile,
                                CONF_SETTINGS: {},
                            },
                            subentry_type=SUBENTRY_COVER,
                            title=self._cover_title(cover),
                            unique_id=cover,
                        ),
                    )
                return self.async_create_entry(
                    title=self._cover_title(covers[0]),
                    data={CONF_COVER_ENTITY: covers[0], CONF_PROFILE: profile, CONF_SETTINGS: {}},
                    unique_id=covers[0],
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_COVER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="cover", multiple=True, exclude_entities=sorted(self._configured())
                    )
                ),
                vol.Optional(CONF_PROFILE, default=NO_PROFILE): self._profile_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_base(self, user_input=None) -> SubentryFlowResult:
        """Name and profile of the cover."""
        if user_input is not None:
            self._title = user_input[CONF_NAME]
            for key in (CONF_PROFILE, CONF_PROFILE_ALT):
                profile = user_input.get(key)
                self._data[key] = None if profile in (None, NO_PROFILE) else profile
            self._data[CONF_PROFILE_SWITCH] = user_input.get(CONF_PROFILE_SWITCH) or None
            self._data[CONF_PROFILE_SWITCH_VALUE] = (
                user_input.get(CONF_PROFILE_SWITCH_VALUE) or None
            )
            return self._menu()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, description={"suggested_value": self._title}
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_PROFILE, default=self._data.get(CONF_PROFILE) or NO_PROFILE
                ): self._profile_selector(),
                vol.Optional(
                    CONF_PROFILE_ALT, default=self._data.get(CONF_PROFILE_ALT) or NO_PROFILE
                ): self._profile_selector(),
                _optional(CONF_PROFILE_SWITCH, self._data.get(CONF_PROFILE_SWITCH)): (
                    selector.EntitySelector()
                ),
                _optional(
                    CONF_PROFILE_SWITCH_VALUE, self._data.get(CONF_PROFILE_SWITCH_VALUE)
                ): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_BASE,
            data_schema=schema,
            description_placeholders={"entity_id": self._data.get(CONF_COVER_ENTITY, "")},
        )

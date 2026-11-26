"""Binary sensors."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from . import AscConfigEntry
from .engine.daynight import PRIVACY_DOWN, PRIVACY_UP, effective_down, effective_up, privacy_times
from .engine.hotday import is_hot
from .engine.protection import FROST, RAIN, RAIN_WINDOW, WIND
from .entity import AscCoverEntity, AscGlobalEntity
from .runtime import AscManager, CoverController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    manager = entry.runtime_data
    async_add_entities(
        [
            *(GlobalProtectionBinarySensor(manager, kind) for kind in (RAIN, WIND, FROST)),
            SunnyBinarySensor(manager),
            GlobalHotBinarySensor(manager),
            WinterBinarySensor(manager),
        ]
    )
    for controller in manager.controllers.values():
        async_add_entities(
            [
                DayBinarySensor(controller),
                OverrideBinarySensor(controller),
                SelfDefenseBinarySensor(controller),
                *(
                    ProtectionBinarySensor(controller, kind)
                    for kind in (RAIN, RAIN_WINDOW, WIND, FROST)
                ),
                ForceBinarySensor(controller),
                HotDayBinarySensor(controller),
                QuietBinarySensor(controller),
                GuestBinarySensor(controller),
                GlareBinarySensor(controller),
                StuckBinarySensor(controller),
            ],
            config_subentry_id=controller.subentry_id,
        )


class DayBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On between the morning and the evening drive."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "is_day")

    @property
    def is_on(self) -> bool:
        return self.controller.is_day()

    @property
    def extra_state_attributes(self) -> dict:
        today = dt_util.now(self.controller.tz).date()
        sched = self.controller.schedule_for(today)
        marks = self.controller.marks_for(today)
        privacy = privacy_times(self.controller.cfg, sched, marks)
        return {
            "up_today": effective_up(sched, marks).isoformat(),
            "down_today": effective_down(sched, marks).isoformat(),
            "up_workday": sched.up_workday,
            "down_workday": sched.down_workday,
            "up_dynamic": sched.up_dynamic,
            "down_dynamic": sched.down_dynamic,
            "privacy_up_today": privacy[PRIVACY_UP].isoformat() if PRIVACY_UP in privacy else None,
            "privacy_down_today": (
                privacy[PRIVACY_DOWN].isoformat() if PRIVACY_DOWN in privacy else None
            ),
        }


class OverrideBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On while a manual override is active."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "manual_override")

    @property
    def is_on(self) -> bool:
        return self.controller.override_active

    @property
    def extra_state_attributes(self) -> dict:
        override = self.controller.override or {}
        return {"since": override.get("since"), "until": override.get("until")}


class SelfDefenseBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On while self defense keeps the cover closed."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "self_defense")

    @property
    def is_on(self) -> bool:
        return self.controller.self_defense_active()


class GlobalProtectionBinarySensor(AscGlobalEntity, BinarySensorEntity):
    """Rain, wind or frost by the global sensors (after hysteresis and waits)."""

    def __init__(self, manager: AscManager, kind: str) -> None:
        super().__init__(manager, f"global_{kind}")
        self._kind = kind

    @property
    def is_on(self) -> bool:
        return self.manager.global_protect[self._kind].active


class ProtectionBinarySensor(AscCoverEntity, BinarySensorEntity):
    """Rain, water, wind or frost protection acting on this cover."""

    def __init__(self, controller: CoverController, kind: str) -> None:
        super().__init__(controller, f"protection_{kind}")
        self._kind = kind

    @property
    def is_on(self) -> bool:
        return self.controller.protections()[self._kind]


class ForceBinarySensor(AscCoverEntity, BinarySensorEntity):
    """On while a force function holds the cover."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "force")

    @property
    def is_on(self) -> bool:
        return self.controller.force_kind() is not None

    @property
    def extra_state_attributes(self) -> dict:
        return {"function": self.controller.force_kind()}


class _Refreshed:
    """Write the state every few minutes (values that change without an event)."""

    _refresh_minutes = 10

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()  # type: ignore[misc]
        self.async_on_remove(  # type: ignore[attr-defined]
            async_track_time_interval(
                self.hass,  # type: ignore[attr-defined]
                self._refresh,
                timedelta(minutes=self._refresh_minutes),
            )
        )

    @callback
    def _refresh(self, _now: datetime) -> None:
        self.async_write_ha_state()  # type: ignore[attr-defined]


class SunnyBinarySensor(_Refreshed, AscGlobalEntity, BinarySensorEntity):
    """Weather now is one of the shading weather conditions (global weather entity)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _refresh_minutes = 1

    def __init__(self, manager: AscManager) -> None:
        super().__init__(manager, "sunny")

    @property
    def is_on(self) -> bool | None:
        return self.manager.sunny(self.manager.global_cfg)


class GlobalHotBinarySensor(_Refreshed, AscGlobalEntity, BinarySensorEntity):
    """Hot day by the global forecast (forecast maximum at or above the limit)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: AscManager) -> None:
        super().__init__(manager, "hot")

    @property
    def is_on(self) -> bool:
        cfg = self.manager.global_cfg
        return is_hot({**cfg, "hot_day": True}, *self.manager.forecast_today(cfg))

    @property
    def extra_state_attributes(self) -> dict:
        cfg = self.manager.global_cfg
        temp, condition = self.manager.forecast_today(cfg)
        return {"forecast": temp, "condition": condition, "limit": cfg["hot_day_temp"]}


class HotDayBinarySensor(_Refreshed, AscCoverEntity, BinarySensorEntity):
    """Hot day holds this cover at the shading position (the sun still comes today)."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "hot_day")

    @property
    def is_on(self) -> bool:
        return self.controller.hot_day()


class QuietBinarySensor(_Refreshed, AscCoverEntity, BinarySensorEntity):
    """Quiet hours of this cover."""

    _refresh_minutes = 1

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "quiet")

    @property
    def is_on(self) -> bool:
        return self.controller.quiet_now()


class GuestBinarySensor(AscCoverEntity, BinarySensorEntity):
    """A guest is in the room: no morning opening."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "guest")

    @property
    def is_on(self) -> bool:
        return self.controller.guest_present()


class WinterBinarySensor(_Refreshed, AscGlobalEntity, BinarySensorEntity):
    """Mean outdoor temperature of the last 24 hours below the winter limit."""

    def __init__(self, manager: AscManager) -> None:
        super().__init__(manager, "winter")

    @property
    def is_on(self) -> bool:
        return self.manager.winter

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "mean_24h": self.manager.winter_mean(),
            "limit": self.manager.global_cfg["winter_temp"],
        }


class GlareBinarySensor(AscCoverEntity, BinarySensorEntity):
    """Glare protection holds the cover at the glare position."""

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "glare")

    @property
    def is_on(self) -> bool:
        return self.controller.glare_active

    @property
    def extra_state_attributes(self) -> dict:
        glare = self.controller.state.get("glare") or {}
        return {"state": self.controller.glare_state, "since": glare.get("since")}


class StuckBinarySensor(AscCoverEntity, BinarySensorEntity):
    """The last drive did not arrive, also not after a second try."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, controller: CoverController) -> None:
        super().__init__(controller, "stuck")

    @property
    def is_on(self) -> bool:
        return self.controller.stuck is not None

    @property
    def extra_state_attributes(self) -> dict:
        stuck = self.controller.stuck or {}
        return {
            "target": stuck.get("target"),
            "position": stuck.get("position"),
            "since": stuck.get("time"),
        }

"""Group covers: all covers and one per profile (for dashboards, Assist and voice assistants).

A group command goes to each member through the command queue. The lock-out
protection of every member holds: a member in front of an open door does not go
down. For the members a group command is a manual drive.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import AscConfigEntry
from .const import DOMAIN, SIGNAL_GLOBAL_UPDATE, SUBENTRY_PROFILE
from .entity import global_device
from .runtime import AscManager, CoverController

GROUP_ALL = "all"
_FEATURES = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.STOP
    | CoverEntityFeature.SET_POSITION
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AscConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the group covers."""
    manager = entry.runtime_data
    groups: list[GroupCover] = [GroupCover(manager, GROUP_ALL, None)]
    for sub_id, sub in entry.subentries.items():
        if sub.subentry_type == SUBENTRY_PROFILE:
            groups.append(GroupCover(manager, sub_id, sub.title))
    async_add_entities(groups)


class GroupCover(CoverEntity):
    """All covers, or the covers of one profile."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = _FEATURES
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(self, manager: AscManager, group: str, title: str | None) -> None:
        self.manager = manager
        self._group = group
        self._attr_unique_id = f"{manager.entry.entry_id}_group_{group}"
        self._attr_device_info = global_device(manager)
        if title is None:
            self._attr_translation_key = "group_all"
        else:
            self._attr_translation_key = "group_profile"
            self._attr_translation_placeholders = {"name": title}

    @property
    def members(self) -> list[CoverController]:
        """Shutters of the group (awnings are never part of a group)."""
        return [
            c
            for c in self.manager.controllers.values()
            if not c.awning and (self._group == GROUP_ALL or c.profile == self._group)
        ]

    async def async_added_to_hass(self) -> None:
        """Follow the members."""
        entities = [c.cover_entity for c in self.manager.controllers.values()]
        if entities:
            self.async_on_remove(
                async_track_state_change_event(self.hass, entities, self._on_member)
            )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_GLOBAL_UPDATE, self.async_write_ha_state)
        )

    @callback
    def _on_member(self, _event: Event) -> None:
        self.async_write_ha_state()

    def _states(self) -> list[Any]:
        out = []
        for controller in self.members:
            state = self.hass.states.get(controller.cover_entity)
            if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                out.append(state)
        return out

    @property
    def available(self) -> bool:
        return bool(self._states())

    @property
    def current_cover_position(self) -> int | None:
        positions = [p for p in (c.current_position() for c in self.members) if p is not None]
        if not positions:
            return None
        return int(round(sum(positions) / len(positions)))

    @property
    def is_closed(self) -> bool | None:
        position = self.current_cover_position
        if position is not None:
            return position == 0
        states = self._states()
        if not states:
            return None
        return all(s.state == CoverState.CLOSED for s in states)

    @property
    def is_opening(self) -> bool:
        return any(s.state == CoverState.OPENING for s in self._states())

    @property
    def is_closing(self) -> bool:
        return any(s.state == CoverState.CLOSING for s in self._states())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ENTITY_ID: [c.cover_entity for c in self.members]}

    # --- commands ---------------------------------------------------------------

    def _send(self, service: str, position: int | None = None) -> None:
        parent = self._context
        for controller in self.members:
            if position is not None and controller.lockout_blocks(position):
                controller.group_blocked(position)
                continue
            data: dict[str, Any] = {ATTR_ENTITY_ID: controller.cover_entity}
            member_service = service
            state = self.hass.states.get(controller.cover_entity)
            features = int(state.attributes.get("supported_features", 0)) if state else 0
            if service == "set_cover_position" and not features & CoverEntityFeature.SET_POSITION:
                member_service = "open_cover" if position and position >= 50 else "close_cover"
            if member_service == "set_cover_position":
                data[ATTR_POSITION] = 100 - position if controller.cfg["invert"] else position
            # A context of its own: for the member this is a manual drive
            context = Context(
                user_id=parent.user_id if parent else None,
                parent_id=parent.id if parent else None,
            )
            self.manager.send_cover(member_service, data, context, f"{DOMAIN} group {self._group}")

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open all members."""
        self._send("open_cover")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close all members (not in front of an open door)."""
        self._send("close_cover", 0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop all members."""
        self._send("stop_cover")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move all members to a position."""
        self._send("set_cover_position", int(kwargs[ATTR_POSITION]))

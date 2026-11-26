"""Edit covers in the sidebar page, and the dashboard card."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.typing import WebSocketGenerator
import voluptuous as vol

from custom_components.autoshutterscontrol import editor, panel
from custom_components.autoshutterscontrol.engine.settings import BY_KEY

from .helpers import (
    COVER,
    COVER2,
    cover_subentry,
    mock_cover_services,
    profile_subentry,
    set_cover,
    setup_entry,
    setup_hass,
)

COVER3 = "cover.bath"


async def _setup(hass: HomeAssistant):
    await setup_hass(hass)
    for entity_id in (COVER, COVER2, COVER3):
        set_cover(hass, entity_id, position=100)
    mock_cover_services(hass)
    return await setup_entry(
        hass,
        {"pos_closed": 10},
        [
            profile_subentry("South", {"pos_shading": 30}),
            cover_subentry(
                settings={"pos_open": 90, "window_open_sensor": "binary_sensor.door"},
                profile="sub_profile",
            ),
            cover_subentry(COVER2, sub_id="sub_cover2", settings={"pos_open": 80}),
        ],
    )


async def _ws(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def test_editor_data(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    await _setup(hass)
    client = await hass_ws_client(hass)
    msg = await _ws(client, type="autoshutterscontrol/editor/data")
    assert msg["success"], msg
    data = msg["result"]
    assert data["admin"] is True
    assert [p["title"] for p in data["profiles"]] == ["South"]
    keys = {f["key"] for f in data["fields"]}
    assert "pos_open" in keys and "window_open_sensor" in keys
    # Conditions and actions only in the dialog
    assert not any(f["kind"] in ("condition", "action") for f in data["fields"])
    living = next(c for c in data["covers"] if c["cover_entity"] == COVER)
    assert living["settings"]["pos_open"] == 90
    assert living["inherited"]["pos_closed"] == [10, "global"]
    assert living["inherited"]["pos_shading"] == [30, "profile"]
    kitchen = next(c for c in data["covers"] if c["cover_entity"] == COVER2)
    assert kitchen["inherited"]["pos_shading"][1] == "default"


async def test_bulk_update_only_changed_fields(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["sub_cover", "sub_cover2"],
        set={"pos_sleep": 25, "time_up_late_workday": "09:15"},
        clear=["pos_open"],
        profile="sub_profile",
    )
    assert msg["success"], msg
    assert msg["result"]["changed"] == 2
    await hass.async_block_till_done()
    living = entry.subentries["sub_cover"].data
    kitchen = entry.subentries["sub_cover2"].data
    for data in (living, kitchen):
        assert data["settings"]["pos_sleep"] == 25
        assert data["settings"]["time_up_late_workday"] == "09:15:00"
        assert "pos_open" not in data["settings"]
        assert data["profile"] == "sub_profile"
    # Untouched fields stay
    assert living["settings"]["window_open_sensor"] == "binary_sensor.door"
    manager = entry.runtime_data
    assert manager.controllers["sub_cover2"].cfg["pos_sleep"] == 25


async def test_update_errors(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["sub_cover"],
        set={"pos_open": 150},
    )
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["nope"],
        set={"pos_open": 50},
    )
    assert msg["error"]["code"] == "not_found"
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["sub_cover", "sub_cover2"],
        title="Both",
    )
    assert msg["error"]["code"] == "invalid_format"
    # Nothing was written
    assert entry.subentries["sub_cover"].data["settings"]["pos_open"] == 90
    # The name of one cover
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["sub_cover"],
        title="Wohnzimmer",
    )
    assert msg["success"]
    assert entry.subentries["sub_cover"].title == "Wohnzimmer"


async def test_non_admin_cannot_change(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user
) -> None:
    await _setup(hass)
    hass_admin_user.groups = []
    client = await hass_ws_client(hass)
    msg = await _ws(client, type="autoshutterscontrol/editor/data")
    assert msg["success"]
    assert msg["result"]["admin"] is False
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/update",
        subentry_ids=["sub_cover"],
        set={"pos_open": 50},
    )
    assert msg["error"]["code"] == "unauthorized"
    msg = await _ws(client, type="autoshutterscontrol/editor/delete", subentry_ids=["sub_cover"])
    assert msg["error"]["code"] == "unauthorized"


async def test_add_duplicate_delete(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)
    # Already configured
    msg = await _ws(client, type="autoshutterscontrol/editor/add", cover_entities=[COVER])
    assert msg["error"]["code"] == "invalid_format"
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/duplicate",
        subentry_id="sub_cover",
        cover_entities=[COVER3],
    )
    assert msg["success"], msg
    new_id = msg["result"]["subentry_ids"][0]
    await hass.async_block_till_done()
    sub = entry.subentries[new_id]
    assert sub.data["cover_entity"] == COVER3
    assert sub.data["profile"] == "sub_profile"
    assert sub.data["settings"] == {"pos_open": 90}  # the door contact stays with its window
    assert sub.unique_id == COVER3
    msg = await _ws(client, type="autoshutterscontrol/editor/delete", subentry_ids=[new_id])
    assert msg["success"]
    await hass.async_block_till_done()
    assert new_id not in entry.subentries
    msg = await _ws(
        client,
        type="autoshutterscontrol/editor/add",
        cover_entities=[COVER3],
        profile="sub_profile",
    )
    assert msg["success"], msg
    await hass.async_block_till_done()
    new_id = msg["result"]["subentry_ids"][0]
    assert entry.subentries[new_id].data == {
        "cover_entity": COVER3,
        "profile": "sub_profile",
        "settings": {},
    }
    loaded = hass.config_entries.async_get_entry(entry.entry_id)
    assert new_id in loaded.runtime_data.controllers


def test_check_value() -> None:
    assert editor.check_value(BY_KEY["pos_open"], 55) == 55
    assert editor.check_value(BY_KEY["time_up_late_workday"], "7:30") == "07:30:00"
    assert editor.check_value(BY_KEY["lockout"], "soft") == "soft"
    with pytest.raises(vol.Invalid):
        editor.check_value(BY_KEY["lockout"], "maybe")
    with pytest.raises(vol.Invalid):
        editor.check_value(BY_KEY["pos_open"], True)
    with pytest.raises(vol.Invalid):
        editor.check_value(BY_KEY["brightness_sensor"], "switch.light")
    with pytest.raises(vol.Invalid):
        editor.apply_changes({}, {"no_such_key": 1}, [])


async def test_card_loaded(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    hass.config.components.add("frontend")
    hass.http = AsyncMock()
    with patch.object(panel.frontend, "add_extra_js_url") as add:
        await setup_entry(hass, {})
    assert add.call_count == 1
    assert add.call_args.args[1].startswith("/autoshutterscontrol_static/asc-card.js?v=")
    hass.http.async_register_static_paths.assert_awaited_once()


async def test_summary_for_card(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    await _setup(hass)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    msg = await _ws(client, type="autoshutterscontrol/summary")
    living = next(c for c in msg["result"]["covers"] if c["entity_id"] == COVER)
    assert living["subentry_id"] == "sub_cover"
    assert living["entities"]["automatic"].startswith("switch.")
    assert living["entities"]["apply_target"].startswith("button.")
    assert living["awning"] is False
    assert living["lockout_now"] is False

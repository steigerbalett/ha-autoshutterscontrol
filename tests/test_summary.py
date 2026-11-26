"""Overview page: websocket data and the panel."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.autoshutterscontrol import panel

from .helpers import (
    COVER,
    COVER2,
    cover_subentry,
    local,
    mock_cover_services,
    set_cover,
    setup_entry,
    setup_hass,
)


async def test_summary(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    # No frozen time: the access token of the websocket must stay valid
    await setup_hass(hass)
    hass.config.language = "de"
    set_cover(hass, position=100)
    set_cover(hass, COVER2, position=40)
    hass.states.async_set("sensor.brightness", "23000", {"unit_of_measurement": "lx"})
    hass.states.async_set("binary_sensor.rain", "off")
    mock_cover_services(hass)
    await setup_entry(
        hass,
        {
            "up_mode": "time",
            "brightness_sensor": "sensor.brightness",
            "rain_sensor": "binary_sensor.rain",
        },
        [
            cover_subentry(settings={"window_open_sensor": "binary_sensor.window"}),
            cover_subentry(COVER2, sub_id="sub_cover2"),
        ],
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "autoshutterscontrol/summary"})
    msg = await client.receive_json()
    assert msg["success"], msg
    data = msg["result"]
    names = [c["name"] for c in data["covers"]]
    assert names == ["kitchen", "living_room"]
    living = data["covers"][1]
    assert living["entity_id"] == COVER
    assert living["up_mode"] == "Zeit"
    assert living["down_mode"] == "Sonne"
    assert living["position"] == 100
    assert living["target"]
    assert living["next_up"] is not None
    entities = {(e["entity_id"], e["setting"]): e for e in data["entities"]}
    bright = entities[("sensor.brightness", "brightness_sensor")]
    assert bright["state"] == "23000"
    assert bright["unit"] == "lx"
    assert bright["used_by"][0] == ""  # global
    assert set(bright["used_by"][1:]) == {"kitchen", "living_room"}
    assert bright["setting_name"] != "brightness_sensor"  # translated
    window = entities[("binary_sensor.window", "window_open_sensor")]
    assert window["state"] is None  # missing entity
    assert window["used_by"] == ["living_room"]
    assert "sun_azimuth" in data["global"]
    assert data["global"]["switches"]["automatic"] is True


async def test_panel_registered(hass: HomeAssistant, freezer) -> None:
    await setup_hass(hass)
    freezer.move_to(local(2026, 11, 25, 12, 0))
    set_cover(hass, position=100)
    hass.config.components.add("frontend")
    hass.http = AsyncMock()
    with (
        patch.object(panel.panel_custom, "async_register_panel", AsyncMock()) as register,
        patch.object(panel.frontend, "async_remove_panel") as remove,
        patch.object(panel.frontend, "add_extra_js_url"),
    ):
        entry = await setup_entry(hass, {})
        assert register.call_count == 0  # off by default
        hass.config_entries.async_update_entry(entry, options={"settings": {"panel": True}})
        await hass.async_block_till_done()
        assert register.call_count == 1
        assert register.call_args.kwargs["frontend_url_path"] == "autoshutterscontrol"
        assert register.call_args.kwargs["module_url"].startswith(
            "/autoshutterscontrol_static/summary-panel.js?v="
        )
        # Switched off in the options: removed
        hass.config_entries.async_update_entry(entry, options={"settings": {"panel": False}})
        await hass.async_block_till_done()
        assert remove.call_count == 1
        hass.config_entries.async_update_entry(entry, options={"settings": {"panel": True}})
        await hass.async_block_till_done()
        assert register.call_count == 2
        await hass.config_entries.async_unload(entry.entry_id)
        assert remove.call_count == 2


async def test_summary_in_options(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    hass.config.language = "de"
    set_cover(hass, position=100)
    hass.states.async_set("sensor.brightness", "23000", {"unit_of_measurement": "lx"})
    mock_cover_services(hass)
    entry = await setup_entry(hass, {"brightness_sensor": "sensor.brightness"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"][0] == "summary"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "summary"}
    )
    assert result["step_id"] == "summary"
    placeholders = result["description_placeholders"]
    assert placeholders["covers"].startswith("**living_room**")
    assert "Position: 100 %" in placeholders["covers"]
    assert "Seitenleiste" in placeholders["panel"]
    assert "23000 lx" in placeholders["entities"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["step_id"] == "init"

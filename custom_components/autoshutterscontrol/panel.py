"""Overview page in the sidebar (as the ASC Configuration and Information Summary in FHEM)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL_PATH = DOMAIN
STATIC_URL = f"/{DOMAIN}_static"
ELEMENT = "asc-summary-panel"
_STATIC_DONE = f"{DOMAIN}_static_done"
_PANEL_ON = f"{DOMAIN}_panel_on"
_CARD_DONE = f"{DOMAIN}_card_done"
CARD_FILE = "asc-card.js"
WS_SUMMARY = f"{DOMAIN}/summary"


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register the websocket command of the page."""
    websocket_api.async_register_command(hass, ws_summary)


@websocket_api.websocket_command({"type": WS_SUMMARY})
@callback
def ws_summary(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Everything the overview shows."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "AutoShuttersControl is not loaded")
        return
    connection.send_result(msg["id"], entries[0].runtime_data.summary())


async def _async_static(hass: HomeAssistant) -> None:
    """Serve the files of the page and the card (once)."""
    if not hass.data.get(_STATIC_DONE):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "www"), False)]
        )
        hass.data[_STATIC_DONE] = True


async def async_setup_card(hass: HomeAssistant) -> None:
    """Load the dashboard cards on every page of the frontend."""
    if "frontend" not in hass.config.components or hass.data.get(_CARD_DONE):
        return
    await _async_static(hass)
    version = (await async_get_integration(hass, DOMAIN)).version
    frontend.add_extra_js_url(hass, f"{STATIC_URL}/{CARD_FILE}?v={version}")
    hass.data[_CARD_DONE] = True


async def async_update_panel(hass: HomeAssistant, enabled: bool) -> None:
    """Show or hide the page in the sidebar."""
    if "frontend" not in hass.config.components:
        return
    if not enabled:
        async_remove_panel(hass)
        return
    if hass.data.get(_PANEL_ON):
        return
    await _async_static(hass)
    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=URL_PATH,
        webcomponent_name=ELEMENT,
        sidebar_title="AutoShuttersControl",
        sidebar_icon="mdi:window-shutter-auto",
        module_url=f"{STATIC_URL}/summary-panel.js?v={version}",
        require_admin=False,
    )
    hass.data[_PANEL_ON] = True


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the page from the sidebar."""
    if hass.data.pop(_PANEL_ON, False):
        frontend.async_remove_panel(hass, URL_PATH, warn_if_unknown=False)

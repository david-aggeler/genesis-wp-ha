"""Sidebar panel lifecycle on the loopback emulator."""
from pathlib import Path

from homeassistant.setup import async_setup_component
from .helpers import setup_entry
from .harness import PROFILE_615


# DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-81
async def test_panel_lifecycle(hass, hass_client, start_emulator):
    assert await async_setup_component(hass, "http", {})
    first = await setup_entry(hass, await start_emulator(PROFILE_615))
    panel = hass.data["frontend_panels"]["genesis-wp"]
    assert panel.sidebar_title == "Heat pump"
    assert panel.sidebar_icon == "mdi:heat-pump"
    assert not panel.require_admin
    url = panel.config["_panel_custom"]["module_url"]
    response = await (await hass_client()).get(url)
    assert response.status == 200
    assert await response.read() == Path("custom_components/genesis_wp/frontend/genesis-wp-panel.js").read_bytes()
    second = await setup_entry(hass, await start_emulator(PROFILE_615))
    assert await hass.config_entries.async_unload(first.entry_id)
    assert "genesis-wp" in hass.data["frontend_panels"]
    assert await hass.config_entries.async_unload(second.entry_id)
    assert "genesis-wp" not in hass.data["frontend_panels"]

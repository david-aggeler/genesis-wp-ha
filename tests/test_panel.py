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
    # Every module the panel imports is served next to it.
    frontend = Path("custom_components/genesis_wp/frontend")
    for name in ("patch.js", "genesis-wp-device-card.js", "genesis-wp-heating-curve-card.js", "register-card.js"):
        module = await (await hass_client()).get(url.rsplit("/", 1)[0] + "/" + name)
        assert module.status == 200, name
        assert await module.read() == (frontend / name).read_bytes(), name
    second = await setup_entry(hass, await start_emulator(PROFILE_615))
    assert await hass.config_entries.async_unload(first.entry_id)
    assert "genesis-wp" in hass.data["frontend_panels"]
    assert await hass.config_entries.async_unload(second.entry_id)
    assert "genesis-wp" not in hass.data["frontend_panels"]

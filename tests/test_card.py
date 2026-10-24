"""Heating curve card module served and registered by the integration (requirement-11)."""

from __future__ import annotations

from pathlib import Path

from custom_components.genesis_wp.const import CARD_URL
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.frontend import UrlManager
from homeassistant.setup import async_setup_component

from .helpers import setup_entry

CARD = Path(__file__).parents[1] / "custom_components" / "genesis_wp" / "frontend" / "genesis-wp-heating-curve-card.js"


# DHF-REQ: genesis-wp-ha/requirement-11  DHF-TEST: genesis-wp-ha/ac-35
async def test_card_module_is_served_and_registered(hass, hass_client, start_emulator):
    assert await async_setup_component(hass, "http", {})
    # The frontend component needs the hass_frontend package, absent here; stand in for its module list.
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
    await setup_entry(hass, await start_emulator())

    assert CARD_URL in hass.data[DATA_EXTRA_MODULE_URL].urls
    response = await (await hass_client()).get(CARD_URL)
    assert response.status == 200
    assert await response.read() == CARD.read_bytes()
    assert b"customElements.define(\"genesis-wp-heating-curve-card\"" in CARD.read_bytes()

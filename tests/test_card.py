"""Heating curve card module served and registered by the integration (requirement-11)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from custom_components.genesis_wp.const import CARD_URL
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.frontend import UrlManager
from homeassistant.setup import async_setup_component

from .helpers import setup_entry

SWAP_CHECK = Path(__file__).parent / "frontend" / "registry_swap.mjs"
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
    assert b'const TAG = "genesis-wp-heating-curve-card"' in CARD.read_bytes()


# DHF-REQ: genesis-wp-ha/requirement-11  DHF-TEST: genesis-wp-ha/ac-37 genesis-wp-ha/ac-38
def test_card_is_defined_in_the_registry_home_assistant_swaps_in():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed; run tests/frontend/registry_swap.mjs in node:22-alpine")
    out = subprocess.run([node, str(SWAP_CHECK), str(CARD)], capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == {
        "defined_before_hui_view": False,
        "defined_in_native": False,
        "defined_in_replacement": True,
        "custom_cards": 1,
        "dots": 7,
        "markers": 1,
        "x_label": True,
        "y_label": True,
        "overlay": {"svgs": 1, "curves": 2, "dots": 14, "markers": 2, "legend": 2, "in_plot": True},
        "late_defined_immediately": True,
    }


def test_card_module_is_ascii():
    """Served without a charset, so non-ASCII bytes would decode differently per consumer (issue-6)."""
    CARD.read_bytes().decode("ascii")

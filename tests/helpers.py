"""Config-entry helpers shared by the integration tests."""

from __future__ import annotations

from custom_components.genesis_wp.const import CONF_MODEL
from custom_components.genesis_wp.const import CONF_UNIT
from custom_components.genesis_wp.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import UNIT
from .harness import WPE_I_KIND


def entry_data(emu) -> dict:
    return {CONF_HOST: emu.host, CONF_PORT: emu.port, CONF_UNIT: UNIT, CONF_MODEL: WPE_I_KIND}


async def setup_entry(hass, emu) -> MockConfigEntry:
    """Add and set up a config entry for a running emulator."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(emu), unique_id=f"{emu.host}:{emu.port}:{UNIT}")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

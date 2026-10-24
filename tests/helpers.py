"""Config-entry helpers shared by the integration tests."""

from __future__ import annotations

from custom_components.genesis_wp.const import CONF_ADVANCED
from custom_components.genesis_wp.const import CONF_MODEL
from custom_components.genesis_wp.const import CONF_UNIT
from custom_components.genesis_wp.const import DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import UNIT
from .harness import WPE_I_KIND


def entry_data(emu) -> dict:
    return {CONF_HOST: emu.host, CONF_PORT: emu.port, CONF_UNIT: UNIT, CONF_MODEL: WPE_I_KIND}


def form_input(data, with_model=True) -> dict:
    """Entry data as the config flow form submits it: port inside the advanced section, no unit."""
    fields = {CONF_HOST: data[CONF_HOST], CONF_ADVANCED: {CONF_PORT: data[CONF_PORT]}}
    if with_model:
        fields[CONF_MODEL] = data[CONF_MODEL]
    return fields


async def real_form(hass) -> dict:
    """Start the config flow and pick "Real heat pump" from the menu; returns the host form."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "real"})


async def setup_entry(hass, emu) -> MockConfigEntry:
    """Add and set up a config entry for a running emulator."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(emu))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

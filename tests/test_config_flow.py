"""Config flow: host, port, unit and model, verified by a read (requirement-4)."""

from __future__ import annotations

import logging

import pytest
from custom_components.genesis_wp.const import DOMAIN
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from .helpers import entry_data
from .helpers import setup_entry


async def _submit(hass, data):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-8
async def test_valid_input_creates_an_entry(hass, start_emulator):
    emu = await start_emulator()
    result = await _submit(hass, entry_data(emu))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(emu)
    assert emu.writes == []
    await hass.async_block_till_done()


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-9
async def test_unreachable_host_shows_cannot_connect(hass, socket_enabled):
    class Gone:
        host, port = "127.0.0.1", 1  # nothing listens on port 1

    result = await _submit(hass, entry_data(Gone))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-10
async def test_duplicate_device_aborts(hass, start_emulator):
    emu = await start_emulator()
    await setup_entry(hass, emu)
    result = await _submit(hass, entry_data(emu))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _host_records(caplog, host, prefix):
    return [r for r in caplog.records if r.name.startswith(prefix) and host in r.getMessage()]


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-11
async def test_integration_never_logs_the_host(hass, start_emulator, caplog):
    caplog.set_level(logging.DEBUG)
    emu = await start_emulator()
    entry = await setup_entry(hass, emu)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await emu.stop()  # a failing refresh must not leak the host either
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert _host_records(caplog, emu.host, "custom_components.genesis_wp") == []
    assert _host_records(caplog, emu.host, "homeassistant") == []


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-11
@pytest.mark.xfail(
    strict=True,
    reason="genesis-wp issue-1: the library logs the host when it connects; fixed upstream, then the manifest pin moves",
)
async def test_library_never_logs_the_host(hass, start_emulator, caplog):
    caplog.set_level(logging.DEBUG)
    emu = await start_emulator()
    entry = await setup_entry(hass, emu)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert _host_records(caplog, emu.host, "genesis_wp") == []

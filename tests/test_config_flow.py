"""Config flow: host, port, unit and model, verified by a read (requirement-4); duplicates and reconfigure (requirement-8)."""

from __future__ import annotations

import logging

from custom_components.genesis_wp.const import CONF_UNIT
from custom_components.genesis_wp.const import DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

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
# DHF-REQ: genesis-wp-ha/requirement-8  DHF-TEST: genesis-wp-ha/ac-21
async def test_duplicate_connection_aborts_without_host_unique_id(hass, start_emulator):
    emu = await start_emulator()
    result = await _submit(hass, entry_data(emu))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id is None or not ({emu.host, str(emu.port)} & set(entry.unique_id.split(":")))

    result = await _submit(hass, entry_data(emu))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


def _registry_pairs(hass, entry):
    return {(e.entity_id, e.unique_id) for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


# DHF-REQ: genesis-wp-ha/requirement-8  DHF-TEST: genesis-wp-ha/ac-22
async def test_reconfigure_to_new_host_keeps_entity_ids(hass, start_emulator):
    emu_a = await start_emulator()
    emu_b = await start_emulator()
    entry = await setup_entry(hass, emu_a)
    entry_id, before = entry.entry_id, _registry_pairs(hass, entry)
    assert before

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    new = entry_data(emu_b)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new[CONF_HOST], CONF_PORT: new[CONF_PORT], CONF_UNIT: new[CONF_UNIT]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == emu_b.port
    assert hass.config_entries.async_get_entry(entry_id) is entry
    assert _registry_pairs(hass, entry) == before
    assert hass.data[DOMAIN][entry_id].last_update_success


# DHF-REQ: genesis-wp-ha/requirement-8  DHF-TEST: genesis-wp-ha/ac-21
async def test_reconfigure_onto_another_entry_aborts(hass, start_emulator):
    emu_a = await start_emulator()
    emu_b = await start_emulator()
    entry = await setup_entry(hass, emu_a)
    await setup_entry(hass, emu_b)

    result = await entry.start_reconfigure_flow(hass)
    other = entry_data(emu_b)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: other[CONF_HOST], CONF_PORT: other[CONF_PORT], CONF_UNIT: other[CONF_UNIT]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_PORT] == emu_a.port


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
async def test_library_never_logs_the_host(hass, start_emulator, caplog):
    caplog.set_level(logging.DEBUG)
    emu = await start_emulator()
    entry = await setup_entry(hass, emu)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await emu.stop()  # the failure path must not leak the host either
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    # The in-process emulator logs its own bind address: test topology, not the device.
    library = [r for r in _host_records(caplog, emu.host, "genesis_wp") if not r.name.startswith("genesis_wp.emulator")]
    assert library == []

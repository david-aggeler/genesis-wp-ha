"""Config flow: host, port and model, unit fixed to 1, verified by a read (requirement-4); duplicates and reconfigure (requirement-8)."""

from __future__ import annotations

import logging

from custom_components.genesis_wp.const import CONF_ADVANCED
from custom_components.genesis_wp.const import CONF_UNIT
from custom_components.genesis_wp.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import NumberSelector
from homeassistant.helpers.selector import NumberSelectorMode

from .helpers import entry_data
from .helpers import form_input
from .helpers import real_form
from .helpers import setup_entry


async def _submit(hass, data):
    result = await real_form(hass)
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], form_input(data))


def _advanced_section(schema):
    (advanced,) = [v for k, v in schema.schema.items() if k == CONF_ADVANCED]
    assert isinstance(advanced, section)
    return advanced


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-8
async def test_port_is_a_number_box_in_a_collapsed_section_and_unit_is_not_asked(hass, start_emulator):
    result = await real_form(hass)
    entry = await setup_entry(hass, await start_emulator())
    reconfigure = await entry.start_reconfigure_flow(hass)

    for form in (result, reconfigure):
        schema = form["data_schema"]
        assert {str(k) for k in schema.schema} >= {CONF_HOST, CONF_ADVANCED}
        assert not {CONF_PORT, CONF_UNIT} & {str(k) for k in schema.schema}
        advanced = _advanced_section(schema)
        assert advanced.options["collapsed"] is True
        fields = {str(k): v for k, v in advanced.schema.schema.items()}
        assert set(fields) == {CONF_PORT}  # the WPM-G answers on unit 1; there is no gateway to address
        assert isinstance(fields[CONF_PORT], NumberSelector)
        config = fields[CONF_PORT].config
        assert (config["mode"], config["min"], config["max"], config["step"]) == (NumberSelectorMode.BOX, 1, 65535, 1)


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-8
async def test_valid_input_creates_an_entry(hass, start_emulator):
    emu = await start_emulator()
    result = await _submit(hass, entry_data(emu))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data(emu)  # flat: the section never reaches entry data
    assert result["data"][CONF_UNIT] == 1
    assert type(result["data"][CONF_PORT]) is int and type(result["data"][CONF_UNIT]) is int
    assert emu.writes == []
    await hass.async_block_till_done()


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-8
async def test_selector_floats_are_stored_as_ints(hass, start_emulator):
    emu = await start_emulator()
    data = {**entry_data(emu), CONF_PORT: float(emu.port)}  # NumberSelector returns floats
    result = await _submit(hass, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert type(result["data"][CONF_PORT]) is int and type(result["data"][CONF_UNIT]) is int
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_input(entry_data(emu_b), with_model=False)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PORT] == emu_b.port
    assert entry.data[CONF_UNIT] == 1
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_input(entry_data(emu_b), with_model=False)
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

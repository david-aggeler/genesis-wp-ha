"""Module choices in the setup of a real heat pump, detected-absent modules behind an opt-in (requirement-16)."""

from __future__ import annotations

import pytest
from custom_components.genesis_wp import read_capabilities
from custom_components.genesis_wp.config_flow import SHOW_ABSENT
from custom_components.genesis_wp.config_flow import model_capabilities
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp.capabilities import ABSENT
from genesis_wp import const as c
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .harness import PROFILES
from .harness import WPE_I_KIND
from .harness import gates
from .helpers import entry_data
from .helpers import form_input
from .helpers import real_form
from .test_capabilities import candidates


async def detected(start_emulator, profile) -> tuple:
    """The emulator and the capability states the library detects on it."""
    emu = await start_emulator(profile)
    return emu, await read_capabilities(entry_data(emu))


async def modules_form(hass, emu) -> dict:
    result = await real_form(hass)
    return await hass.config_entries.flow.async_configure(result["flow_id"], form_input(entry_data(emu)))


def fields(form) -> dict:
    return {str(key): key for key in form["data_schema"].schema}


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-53
@pytest.mark.parametrize("profile", PROFILES)
async def test_modules_step_lists_detected_present_and_unknown_modules(hass, start_emulator, profile):
    emu, states = await detected(start_emulator, profile)
    form = await modules_form(hass, emu)

    assert form["type"] is FlowResultType.FORM and form["step_id"] == "modules"
    offered = [n for n in model_capabilities(WPE_I_KIND) if states[n] != ABSENT]
    assert [f for f in fields(form) if f != SHOW_ABSENT] == offered
    assert not {"ksm", "internal_heater", "cooling", "additional_heater"} & fields(form).keys()
    for key in form["data_schema"].schema:
        if str(key) != SHOW_ABSENT:
            assert key.default() == "automatic"
    assert "passive_cooling: unknown" in form["description_placeholders"]["detected"]
    assert emu.writes == []


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-54
@pytest.mark.parametrize("profile", PROFILES)
async def test_opting_in_shows_the_detected_absent_modules(hass, start_emulator, profile):
    emu, states = await detected(start_emulator, profile)
    absent = [n for n in model_capabilities(WPE_I_KIND) if states[n] == ABSENT]
    assert absent  # hot water, pool, active cooling, room sensor, electric meter on the capture

    form = await modules_form(hass, emu)
    assert fields(form)[SHOW_ABSENT].default() is False
    form = await hass.config_entries.flow.async_configure(form["flow_id"], {SHOW_ABSENT: True})
    assert form["type"] is FlowResultType.FORM and form["step_id"] == "absent_modules"
    assert list(fields(form)) == absent
    assert all(key.default() == "automatic" for key in form["data_schema"].schema)

    result = await hass.config_entries.flow.async_configure(form["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-54
@pytest.mark.parametrize("profile", PROFILES)
async def test_without_opting_in_the_entry_is_created_directly(hass, start_emulator, profile):
    emu, _ = await detected(start_emulator, profile)
    form = await modules_form(hass, emu)
    result = await hass.config_entries.flow.async_configure(form["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-55
@pytest.mark.parametrize("profile", PROFILES)
async def test_setup_choices_are_stored_as_options_and_gate_entities(hass, start_emulator, profile):
    emu, _ = await detected(start_emulator, profile)
    form = await modules_form(hass, emu)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"hot_gas_recovery": "not_installed", "passive_cooling": "installed"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    entry = result["result"]
    assert dict(entry.options) == {"hot_gas_recovery": "absent", "passive_cooling": "present"}
    ids = {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert not {coordinator.unique_id(r) for r in gates("hot_gas_recovery")} & ids
    expected = {coordinator.unique_id(r) for r in gates("passive_cooling") & candidates()}
    assert expected
    assert expected <= ids


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-56
@pytest.mark.parametrize("profile", PROFILES)
async def test_options_step_shows_setup_choices_and_hides_absent_modules(hass, start_emulator, profile):
    emu, states = await detected(start_emulator, profile)
    form = await modules_form(hass, emu)
    result = await hass.config_entries.flow.async_configure(form["flow_id"], {"passive_cooling": "not_installed"})
    await hass.async_block_till_done()
    entry = result["result"]

    options = await hass.config_entries.options.async_init(entry.entry_id)
    offered = fields(options)
    assert offered["passive_cooling"].default() == "not_installed"  # hidden now, still shown here
    absent = {n for n in model_capabilities(WPE_I_KIND) if states[n] == ABSENT}
    assert not absent & offered.keys()
    assert SHOW_ABSENT in offered
    assert not {"ksm", "internal_heater", "cooling", "additional_heater"} & offered.keys()

    options = await hass.config_entries.options.async_configure(options["flow_id"], {SHOW_ABSENT: True})
    assert options["step_id"] == "absent_modules" and set(fields(options)) == absent


# DHF-TEST: genesis-wp-ha/requirement-16
# DHF-TEST: genesis-wp-ha/ac-56
@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("page", ["init", "absent_modules"])
async def test_options_submission_keeps_displayed_choices_after_detection_changes(
    hass, start_emulator, profile, page
):
    emu, _ = await detected(start_emulator, profile)
    form = await modules_form(hass, emu)
    result = await hass.config_entries.flow.async_configure(form["flow_id"], {})
    await hass.async_block_till_done()
    entry = result["result"]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    address = c.REGISTERS[c.ATTR_INPUT_ROOM_TEMPERATURE_SENSOR][c.KEY_ADDRESS]

    if page == "init":
        emu.inject_fault("input_registers", address)
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator.thermia.capabilities["room_sensor"].state == "unknown"
    options = await hass.config_entries.options.async_init(entry.entry_id)
    if page == "absent_modules":
        options = await hass.config_entries.options.async_configure(options["flow_id"], {SHOW_ABSENT: True})
    assert options["step_id"] == page
    assert "room_sensor" in fields(options)

    if page == "init":
        emu.clear_faults()
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator.thermia.capabilities["room_sensor"].state == "absent"
    else:
        emu.inject_fault("input_registers", address)
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator.thermia.capabilities["room_sensor"].state == "unknown"

    result = await hass.config_entries.options.async_configure(
        options["flow_id"], {"room_sensor": "installed"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"room_sensor": "present"}
    await hass.async_block_till_done()
    assert emu.writes == []

"""Installed modules declared per entry, independent of switched state (requirement-14)."""

from __future__ import annotations

import pytest

from custom_components.genesis_wp import capability_overrides
from custom_components.genesis_wp.config_flow import model_capabilities
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp import const as c
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import PROFILE_615
from .harness import WPE_I_KIND
from .harness import gates
from .helpers import entry_data
from .test_capabilities import registered
from .test_capabilities import restart
from .test_capabilities import unique_id


async def setup_with_options(hass, emu, options) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(emu), options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def refresh(coordinator):
    await coordinator.async_refresh()
    if not coordinator.last_update_success:  # the client reconnects on the next update
        await coordinator.async_refresh()


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-44
async def test_installed_module_keeps_entities_while_switched_off(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {"hot_water": "present"})
    coordinator = hass.data[DOMAIN][entry.entry_id]
    module = coordinator.thermia.capabilities["hot_water"]
    assert module.state == "present" and module.overridden
    assert "detected absent" in module.evidence[0]  # hot water sensors are not fitted on the capture

    assert {unique_id(entry, r) for r in gates("hot_water")} <= registered(hass, entry)
    registry = er.async_get(hass)
    enable = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, unique_id(entry, c.ATTR_COIL_ENABLE_TAP_WATER)
    )
    # Settings entities start disabled (requirement-9); enable it as a user would.
    registry.async_update_entity(enable, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(enable).state == "off"


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-45
async def test_not_installed_module_gets_no_entities(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_with_options(hass, emu, {"smart_grid": "absent"})
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert "detected unknown" in coordinator.thermia.capabilities["smart_grid"].evidence[0]

    smart_grid = {unique_id(entry, r) for r in gates("smart_grid")}
    assert smart_grid
    assert not smart_grid & registered(hass, entry)


@pytest.fixture
async def entry_with_hot_gas_recovery(hass, start_emulator):
    options = dict.fromkeys(model_capabilities(WPE_I_KIND), "present")
    # Hot water shares the child device with hot gas recovery.
    options["hot_water"] = "absent"
    return await setup_with_options(hass, await start_emulator(PROFILE_615), options)


async def turn_off_hot_gas_recovery(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"hot_gas_recovery": "not_installed"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["hot_gas_recovery"] == "absent"


# DHF-TEST: genesis-wp-ha/requirement-14 genesis-wp-ha/ac-153
async def test_reload_removes_stale_module_entities(hass, entry_with_hot_gas_recovery):
    entry = entry_with_hot_gas_recovery
    before = registered(hass, entry)
    hot_gas = {unique_id(entry, register) for register in gates("hot_gas_recovery")}
    assert hot_gas and hot_gas <= before
    assert f"{entry.entry_id}_derived_hc2_return" in before

    await turn_off_hot_gas_recovery(hass, entry)

    assert registered(hass, entry) == before - hot_gas


# DHF-TEST: genesis-wp-ha/requirement-15 genesis-wp-ha/ac-154
async def test_reload_removes_emptied_child_device(hass, entry_with_hot_gas_recovery):
    entry = entry_with_hot_gas_recovery
    registry = dr.async_get(hass)
    main = registry.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    identifier = (DOMAIN, f"{entry.entry_id}_hot_water")
    child = registry.async_get_child_device_by_identifier(identifier, entry.entry_id)
    before = {device.id for device in dr.async_entries_for_parent_device(registry, main.id)}
    assert child.id in before and len(before) > 1

    await turn_off_hot_gas_recovery(hass, entry)

    assert registry.async_get(main.id) is not None
    assert {device.id for device in dr.async_entries_for_parent_device(registry, main.id)} == before - {child.id}


# DHF-TEST: genesis-wp-ha/requirement-12 genesis-wp-ha/ac-155
async def test_reload_retains_meter_entries_after_partial_read(hass, start_emulator):
    first_phase = c.REGISTERS[c.ATTR_INPUT_ELECTRIC_METER_L1_0_VOLTAGE][c.KEY_ADDRESS]
    second_phase = c.REGISTERS[c.ATTR_INPUT_ELECTRIC_METER_L2_0_VOLTAGE][c.KEY_ADDRESS]
    emu = await start_emulator(
        PROFILE_615,
        overrides={("input_registers", first_phase): 0, ("input_registers", second_phase): 2300},
    )
    entry = await setup_with_options(hass, emu, {})
    meter = {unique_id(entry, register) for register in gates("electric_meter")}
    assert meter and meter <= registered(hass, entry)
    devices = dr.async_get(hass)
    identifier = (DOMAIN, f"{entry.entry_id}_electric_meter_and_energy")
    child = devices.async_get_child_device_by_identifier(identifier, entry.entry_id)
    assert child is not None

    emu.inject_fault("input_registers", second_phase)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert meter <= registered(hass, entry)
    assert devices.async_get(child.id) is not None


# DHF-TEST: genesis-wp-ha/requirement-12 genesis-wp-ha/ac-156
async def test_complete_refresh_confirming_absence_removes_retained_meter(hass, start_emulator, caplog):
    first_phase = c.REGISTERS[c.ATTR_INPUT_ELECTRIC_METER_L1_0_VOLTAGE][c.KEY_ADDRESS]
    second_phase = c.REGISTERS[c.ATTR_INPUT_ELECTRIC_METER_L2_0_VOLTAGE][c.KEY_ADDRESS]
    emu = await start_emulator(
        PROFILE_615,
        overrides={("input_registers", first_phase): 0, ("input_registers", second_phase): 2300},
    )
    entry = await setup_with_options(hass, emu, {})
    meter = {unique_id(entry, register) for register in gates("electric_meter")}
    assert meter and meter <= registered(hass, entry)
    devices = dr.async_get(hass)
    identifier = (DOMAIN, f"{entry.entry_id}_electric_meter_and_energy")
    child = devices.async_get_child_device_by_identifier(identifier, entry.entry_id)
    assert child is not None

    # The meter disappears, and the setup read misses the second phase: cleanup is deferred.
    emu.inject_fault("input_registers", second_phase)
    caplog.clear()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert "Deferring registry cleanup for electric_meter due to unread evidence" in caplog.text
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert meter <= coordinator.setup_retained_entity_ids
    assert meter <= registered(hass, entry)

    # A refresh that still misses the evidence changes nothing.
    await coordinator.async_refresh()
    assert meter <= registered(hass, entry)

    # A complete read confirms the meter absent: the deferred cleanup finishes without a reload.
    port = emu.port
    await emu.stop()
    confirmed = await start_emulator(
        PROFILE_615,
        port=port,
        overrides={("input_registers", first_phase): 0, ("input_registers", second_phase): 0},
    )
    assert confirmed.port == port
    await refresh(coordinator)
    await hass.async_block_till_done()

    assert coordinator.thermia.capabilities["electric_meter"].state == "absent"
    assert hass.data[DOMAIN][entry.entry_id] is coordinator  # no reload
    assert not meter & registered(hass, entry)
    assert devices.async_get(child.id) is None
    assert not coordinator.setup_retained_entity_ids


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-46
async def test_options_step_lists_modules_with_automatic_default(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    fields = {
        str(key): key for key in result["data_schema"].schema
        if str(key) not in {"show_absent", "buffer_volume", "circuit_flow"}
    }
    detected = hass.data[DOMAIN][entry.entry_id].thermia.capabilities
    expected = [name for name in model_capabilities(WPE_I_KIND) if detected[name].state != "absent"]
    assert list(fields) == expected
    assert "hot_water" not in fields and "heating_circuit_3" not in fields  # absent: second page
    for key, select in result["data_schema"].schema.items():
        if str(key) not in fields:
            continue
        assert key.default() == "automatic"
        assert select.config["options"] == ["automatic", "installed", "not_installed"]
    assert "hot_water: absent" in result["description_placeholders"]["detected"]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {"buffer_volume": None, "circuit_flow": None}


# DHF-REQ: genesis-wp-ha/requirement-14
def test_options_step_offers_no_built_in_or_combined_module():
    """Built-in modules cannot be missing and combined ones follow their members (change_request-25)."""
    names = model_capabilities(WPE_I_KIND)
    assert not set(names) & {"ksm", "internal_heater", "cooling", "additional_heater"}
    assert {"external_heater", "passive_cooling", "active_cooling", "hot_gas_recovery"} <= set(names)


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-47
async def test_saving_module_options_applies_them(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    entry_id = entry.entry_id
    hot_water_entities = {unique_id(entry, r) for r in gates("hot_water")}
    assert not hot_water_entities & registered(hass, entry)

    # Hot water and pool are detected absent: they sit on the second page (requirement-16).
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"show_absent": True, "buffer_volume": 300, "circuit_flow": 18.33}
    )
    assert result["step_id"] == "absent_modules"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"hot_water": "installed", "pool": "not_installed"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options == {"hot_water": "present", "pool": "absent", "buffer_volume": 300, "circuit_flow": 18.33}
    assert hass.config_entries.async_get_entry(entry_id) is entry
    assert hot_water_entities <= registered(hass, entry)

    # The stored choice is shown again, not reset to automatic.
    result = await hass.config_entries.options.async_init(entry_id)
    defaults = {
        str(key): key.default() for key in result["data_schema"].schema
        if str(key) in {"hot_water", "pool"}
    }
    assert defaults["hot_water"] == "installed" and defaults["pool"] == "not_installed"
    assert "hot_water: present (set here)" in result["description_placeholders"]["detected"]


async def test_installed_module_does_not_reload_when_switched(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_with_options(hass, emu, {"hot_water": "present"})
    coordinator = hass.data[DOMAIN][entry.entry_id]

    changed = await restart(emu, capabilities={"hot_water": True})  # hot water sensors fitted, coil 8 on
    try:
        await refresh(coordinator)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
    finally:
        await changed.stop()


def test_unknown_module_options_are_dropped(caplog):
    options = {"hot_water": "present", "sauna": "present", "pool": "installed"}
    assert capability_overrides(options) == {"hot_water": "present"}
    assert "sauna" in caplog.text and "pool" in caplog.text

# DHF-TEST: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-118
async def test_hc2_return_options_offer_defaults_and_keep_cleared_fields_blank(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key): key.description for key in result["data_schema"].schema}
    assert fields["buffer_volume"]["suggested_value"] == 300
    assert fields["circuit_flow"]["suggested_value"] == 18.33
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"circuit_flow": 20})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["buffer_volume"] is None
    assert entry.options["circuit_flow"] == 20
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key): key.description for key in result["data_schema"].schema}
    assert fields["buffer_volume"].get("suggested_value") is None
    assert fields["circuit_flow"]["suggested_value"] == 20



@pytest.mark.parametrize("field", ["buffer_volume", "circuit_flow"])
@pytest.mark.parametrize("value", ["NaN", "Infinity"])
async def test_hc2_return_options_reject_nonfinite_values(hass, start_emulator, field, value):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {field: value})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"].get(field)
    assert entry.options == {}

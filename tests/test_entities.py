"""Entity correctness: unavailable when not fitted or not read, device versions, power classes (requirements 6 and 7)."""

from __future__ import annotations

from custom_components.genesis_wp.const import BINARY_SENSOR_TYPES
from custom_components.genesis_wp.const import DOMAIN
from custom_components.genesis_wp.const import HEATPUMP_SENSOR
from custom_components.genesis_wp.const import SENSOR_TYPES
from genesis_wp import const as c
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .harness import PROFILE_615
from .harness import WPE_I_KIND
from .helpers import setup_entry

FITTED = {  # wired on the owner's unit (installer documents)
    "T31 buffer": c.ATTR_INPUT_BUFFER_TANK_TEMPERATURE,
    "T32 mixing group supply": c.ATTR_INPUT_MIX_VALVE_1_SUPPLY_LINE_TEMPERATURE,
    "T33 system supply": c.ATTR_INPUT_SYSTEM_SUPPLY_LINE_TEMPERATURE,
    "T35 outdoor": c.ATTR_INPUT_OUTDOOR_TEMPERATURE,
}
NOT_FITTED = {
    "T34 room": c.ATTR_INPUT_ROOM_TEMPERATURE_SENSOR,
    "T36 tap water top": c.ATTR_INPUT_TAP_WATER_TOP_TEMPERATURE,
    "T37 tap water lower": c.ATTR_INPUT_TAP_WATER_LOWER_TEMPERATURE,
}
POWER = (c.ATTR_INPUT_CURRENT_POWER_OUTPUT, c.ATTR_INPUT_CURRENT_CONSUMED_POWER)


def _unique_id(entry, register):
    """The contract of requirement-8, derived from the library map, not from the integration."""
    spec = c.REGISTERS[register]
    return f"{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}"


def _entity_id(hass, entry, register):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, _unique_id(entry, register))
    assert entity_id, register
    return entity_id


async def _enable(hass, entry, registers):
    registry = er.async_get(hass)
    for register in registers:
        registry.async_update_entity(_entity_id(hass, entry, register), disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


# DHF-REQ: genesis-wp-ha/requirement-6  DHF-TEST: genesis-wp-ha/ac-15
async def test_not_fitted_sensors_are_unavailable(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    await _enable(hass, entry, [*FITTED.values(), *NOT_FITTED.values()])

    for label, register in NOT_FITTED.items():
        assert hass.states.get(_entity_id(hass, entry, register)).state == "unavailable", label
    for label, register in FITTED.items():
        state = hass.states.get(_entity_id(hass, entry, register)).state
        float(state)  # numeric, never 200.0 for a not-fitted sensor
        assert float(state) != 200.0, label


# DHF-REQ: genesis-wp-ha/requirement-6  DHF-TEST: genesis-wp-ha/ac-16
async def test_refused_chunk_degrades_only_its_entities(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_entry(hass, emu)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for register in POWER:
        assert hass.states.get(_entity_id(hass, entry, register)).state != "unavailable"

    address = c.REGISTERS[c.ATTR_INPUT_CURRENT_POWER_OUTPUT][c.KEY_ADDRESS]
    emu.inject_fault("input_registers", address)
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert set(POWER) <= coordinator.thermia.unread
    for register in POWER:
        assert hass.states.get(_entity_id(hass, entry, register)).state == "unavailable"
    heatpump = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_heatpump")
    assert hass.states.get(heatpump).state not in ("unavailable", "unknown")
    assert HEATPUMP_SENSOR not in coordinator.thermia.unread

    emu.clear_faults()
    await coordinator.async_refresh()
    for register in POWER:
        assert hass.states.get(_entity_id(hass, entry, register)).state != "unavailable"


# DHF-REQ: genesis-wp-ha/requirement-7  DHF-TEST: genesis-wp-ha/ac-17
async def test_device_info_carries_firmware_versions(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.sw_version == "6.1.5"
    assert device.hw_version == "17.3.145"
    assert device.manufacturer == "Stiebel-Eltron"


# DHF-REQ: genesis-wp-ha/requirement-7  DHF-TEST: genesis-wp-ha/ac-19
async def test_power_sensors_are_kw_measurement(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    for register in POWER:
        attributes = hass.states.get(_entity_id(hass, entry, register)).attributes
        assert attributes["device_class"] == "power"
        assert attributes["unit_of_measurement"] == "kW"
        assert attributes["state_class"] == "measurement"


# DHF-REQ: genesis-wp-ha/requirement-8  DHF-TEST: genesis-wp-ha/ac-20
async def test_unique_ids_use_register_type_and_address(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    actual = {(e.domain, e.unique_id) for e in entries}

    fitted = lambda types: [r for r in types if c.REGISTERS[r][WPE_I_KIND]]  # noqa: E731
    expected = {("sensor", f"{entry.entry_id}_heatpump")}
    expected |= {("sensor", _unique_id(entry, r)) for r in fitted(SENSOR_TYPES)}
    expected |= {("binary_sensor", _unique_id(entry, r)) for r in fitted(BINARY_SENSOR_TYPES)}
    assert actual == expected
    for _, unique_id in actual:
        assert not any(name in unique_id for name in c.REGISTERS), unique_id


# DHF-REQ: genesis-wp-ha/requirement-8  DHF-TEST: genesis-wp-ha/ac-23
async def test_entities_use_has_entity_name(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    outdoor = c.ATTR_INPUT_OUTDOOR_TEMPERATURE
    await _enable(hass, entry, [outdoor])

    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert entries and all(e.has_entity_name for e in entries)
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    state = hass.states.get(_entity_id(hass, entry, outdoor))
    assert state.attributes["friendly_name"] == f"{device.name} Outdoor Temperature"

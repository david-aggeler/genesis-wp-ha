"""Heat pump settings as read-only entities: holding registers and state coils (requirement-9)."""

from __future__ import annotations

from custom_components.genesis_wp.const import DOMAIN
from genesis_wp import const as c
from genesis_wp.emulator import get_profile
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .harness import PROFILE_615
from .harness import WPE_I_KIND
from .helpers import setup_entry

BLOCKS = {"input": "input_registers", "holding": "holding_registers"}
COMMAND_COILS = {c.ATTR_COIL_RESET_ALL_ALARMS}  # a trigger, not a state


def _flagged(reg_type):
    return [r for r, spec in c.REGISTERS.items() if spec[WPE_I_KIND] and spec[c.KEY_REG_TYPE] == reg_type]


HOLDINGS = _flagged("holding")
STATE_COILS = [r for r in _flagged("coil") if r not in COMMAND_COILS]

# The default-enabled core set, written out by register type and address so the test does not
# share the integration's table.
CORE = {
    ("input", 18): "Heating circuit 1 set temperature",
    ("input", 147): "Heating circuit 2 set temperature",
    ("holding", 5): "Room set point",
    **{("holding", 6 + i): f"Heating circuit 1 curve at {t} °C outdoor" for i, t in enumerate((17, 10, 5, 0, -5, -15, -25))},
    **{("holding", 109 + i): f"Heating circuit 2 curve at {t} °C outdoor" for i, t in enumerate((17, 10, 5, 0, -5, -15, -25))},
}


def _unique_id(entry, register):
    spec = c.REGISTERS[register]
    return f"{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}"


def _register(reg_type, address):
    (register,) = [r for r in _flagged(reg_type) if c.REGISTERS[r][c.KEY_ADDRESS] == address]
    return register


def _emulator_value(profile, register):
    """The value the emulator serves, decoded from the profile with the library's scale."""
    spec = c.REGISTERS[register]
    raw = get_profile(profile).blocks[BLOCKS[spec[c.KEY_REG_TYPE]]].value(spec[c.KEY_ADDRESS])
    if spec[c.KEY_DATATYPE] == "int" and raw >= 0x8000:
        raw -= 0x10000
    return raw / spec[c.KEY_SCALE]


def _registry_entry(hass, entry, domain, register):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, _unique_id(entry, register))
    assert entity_id, register
    return registry.async_get(entity_id)


async def _enable_all(hass, entry):
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registry_entry.disabled_by is not None:
            registry.async_update_entity(registry_entry.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-24
async def test_every_flagged_holding_and_state_coil_has_an_entity(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    actual = {(e.domain, e.unique_id) for e in entries}

    assert (len(HOLDINGS), len(STATE_COILS)) == (66, 24)
    settings = {(domain, u) for domain, u in actual if "_holding_" in u or "_coil_" in u}
    expected = {("sensor", _unique_id(entry, r)) for r in HOLDINGS}
    expected |= {("binary_sensor", _unique_id(entry, r)) for r in STATE_COILS}
    assert settings == expected


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-25
async def test_core_settings_are_enabled_in_celsius_with_emulator_values(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    device_name = device.name

    for (reg_type, address), name in CORE.items():
        register = _register(reg_type, address)
        registry_entry = _registry_entry(hass, entry, "sensor", register)
        assert registry_entry.disabled_by is None, name
        state = hass.states.get(registry_entry.entity_id)
        assert state.attributes["friendly_name"] == f"{device_name} {name}"
        assert state.attributes["unit_of_measurement"] == "°C", name
        assert state.attributes["device_class"] == "temperature", name
        assert float(state.state) == _emulator_value(PROFILE_615, register), name

    core = {_register(t, a) for t, a in CORE}
    for register in [*HOLDINGS, *STATE_COILS]:
        if register in core:
            continue
        domain = "binary_sensor" if register in STATE_COILS else "sensor"
        registry_entry = _registry_entry(hass, entry, domain, register)
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, register


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-26
async def test_all_settings_enabled_read_with_fc1_and_fc3_only(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_entry(hass, emu)
    await _enable_all(hass, entry)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    for _ in range(3):
        await coordinator.async_refresh()
        assert coordinator.last_update_success
    assert set(HOLDINGS) | set(STATE_COILS) <= set(coordinator.attributes)
    assert await hass.config_entries.async_unload(entry.entry_id)

    function_codes = {r.function_code for r in emu.requests}
    assert {1, 3} <= function_codes <= {1, 2, 3, 4}
    assert emu.writes == []


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-27
async def test_fixed_supply_set_point_is_unavailable_while_its_coil_is_off(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)  # the profile has coil 41 off
    entry = await setup_entry(hass, emu)
    await _enable_all(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()

    coil = _registry_entry(hass, entry, "binary_sensor", c.ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT)
    assert hass.states.get(coil.entity_id).state == "off"
    fixed = _registry_entry(hass, entry, "sensor", c.ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT)
    assert hass.states.get(fixed.entity_id).state == "unavailable"
    # The 116 entity subscribes its enable coil, so the library knows it may skip 116.
    assert c.ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT in coordinator.attributes
    assert c.ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT in coordinator.attributes


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-27
async def test_fixed_supply_set_point_reads_while_its_coil_is_on(hass, start_emulator):
    raw = 350
    emu = await start_emulator(
        PROFILE_615, overrides={("coils", 41): 1, ("holding_registers", 116): raw}
    )
    entry = await setup_entry(hass, emu)
    await _enable_all(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # 116 is read only once a previous update has seen coil 41 on.
    for _ in range(2):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    coil = _registry_entry(hass, entry, "binary_sensor", c.ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT)
    assert hass.states.get(coil.entity_id).state == "on"
    fixed = _registry_entry(hass, entry, "sensor", c.ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT)
    scale = c.REGISTERS[c.ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT][c.KEY_SCALE]
    assert float(hass.states.get(fixed.entity_id).state) == raw / scale
    assert any(r.function_code == 3 and r.address <= 116 < r.address + r.count for r in emu.requests)


# DHF-REQ: genesis-wp-ha/requirement-9  DHF-TEST: genesis-wp-ha/ac-31
async def test_negative_curve_points_keep_their_sign_in_the_entity_id(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    signs = {t: f"minus_{-t}" if t < 0 else str(t) for t in (17, 10, 5, 0, -5, -15, -25)}

    for circuit, first in ((1, 6), (2, 109)):
        for i, t in enumerate(signs):
            entity_id = _registry_entry(hass, entry, "sensor", _register("holding", first + i)).entity_id
            assert entity_id.endswith(f"_heating_circuit_{circuit}_curve_at_{signs[t]}_degc_outdoor"), entity_id

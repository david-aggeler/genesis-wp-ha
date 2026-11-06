"""Register-map contract at the entity boundary (requirement-17)."""
from collections import Counter

import pytest
from genesis_wp import const as c
from genesis_wp.capabilities import CAPABILITY_RULES, gated_registers
from homeassistant.helpers import entity_registry as er

from custom_components.genesis_wp.const import DOMAIN, REGISTER_OVERRIDES
from .harness import PROFILES, WPE_I_KIND
from .helpers import setup_entry


# Normative requirement-17 mapping; state registers are categorical, not measurements.
CLASSES = {
    'temperature': ('temperature', 'measurement'),
    'temperature_delta': (None, 'measurement'),
    'pressure': ('pressure', 'measurement'),
    'power': ('power', 'measurement'),
    'energy': ('energy', 'total_increasing'),
    'current': ('current', 'measurement'),
    'voltage': ('voltage', 'measurement'),
    'duration': ('duration', 'measurement'),
    'percent': (None, 'measurement'),
    'speed': (None, 'measurement'),
    'count': (None, 'measurement'),
    'dimensionless': (None, 'measurement'),
    'state': (None, None),
}


@pytest.mark.parametrize('profile', PROFILES)
# DHF-TEST: genesis-wp-ha/requirement-17
# DHF-TEST: genesis-wp-ha/ac-59
# DHF-TEST: genesis-wp-ha/ac-60
# DHF-TEST: genesis-wp-ha/ac-61
async def test_register_metadata_and_coverage(hass, start_emulator, profile):
    entry = await setup_entry(hass, await start_emulator(
        profile, capabilities={rule.name: True for rule in CAPABILITY_RULES if gated_registers(rule, WPE_I_KIND) and not rule.members}
    ))
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    for entity in entries:
        if entity.disabled_by is not None:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Imported here so the red test reaches the existing observable unit defect first.
    sensors = hass.data['sensor'].entities
    for entity in sensors:
        if getattr(entity, 'coordinator', None) is not coordinator or entity.unique_id.endswith('_heatpump'):
            continue
        name = entity.kind
        spec = c.REGISTERS[name]
        override = REGISTER_OVERRIDES.get(name, {})
        if override:
            assert override['reason'].strip(), name
        unit = override.get('unit', spec[c.KEY_UNIT][WPE_I_KIND])
        assert entity.native_unit_of_measurement == unit, name
        expected = CLASSES[override.get('kind', spec[c.KEY_KIND][WPE_I_KIND])]
        assert (entity.device_class, entity.state_class) == expected, name
    from custom_components.genesis_wp.const import REGISTER_EXCLUSIONS
    assert set(REGISTER_EXCLUSIONS) <= c.REGISTERS.keys()
    assert all(REGISTER_EXCLUSIONS.values())
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    counts = Counter(e.unique_id for e in entries)
    for name, spec in c.REGISTERS.items():
        if not spec[WPE_I_KIND]:
            continue
        uid = f'{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}'
        assert counts[uid] == (0 if name in REGISTER_EXCLUSIONS else 1), name
    for name in (c.ATTR_INPUT_COMPRESSOR_AVAILABLE_GEARS, c.ATTR_INPUT_COMPRESSOR_CURRENT_GEAR):
        entity = next(e for e in sensors if getattr(e, 'kind', None) == name)
        assert isinstance(entity.native_value, int)


# DHF-TEST: genesis-wp-ha/requirement-17
async def test_unknown_kind_keeps_numeric_sensor_and_warns_once(hass, start_emulator, monkeypatch, caplog):
    name = c.ATTR_INPUT_COMPRESSOR_AVAILABLE_GEARS
    monkeypatch.setitem(c.REGISTERS[name][c.KEY_KIND], WPE_I_KIND, 'future_kind')
    entry = await setup_entry(hass, await start_emulator())
    registry = er.async_get(hass)
    spec = c.REGISTERS[name]
    uid = f'{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}'
    entity_id = registry.async_get_entity_id('sensor', DOMAIN, uid)
    registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state not in ('unknown', 'unavailable')
    assert state.attributes.get('device_class') is None
    assert state.attributes.get('state_class') == 'measurement'
    warnings = [r for r in caplog.records if r.levelname == 'WARNING' and name in r.message and 'future_kind' in r.message]
    assert len(warnings) == 1


@pytest.mark.parametrize('profile', PROFILES)
# DHF-TEST: genesis-wp-ha/requirement-17
# DHF-TEST: genesis-wp-ha/ac-59
# DHF-TEST: genesis-wp-ha/ac-60
async def test_calculated_heating_demand_is_dimensionless(hass, start_emulator, profile, caplog):
    # The warning is once per process; an earlier test may already have spent it.
    from custom_components.genesis_wp.sensor import _warn_unknown_kind
    _warn_unknown_kind.cache_clear()
    entry = await setup_entry(hass, await start_emulator(profile))
    registry = er.async_get(hass)
    uid = f'{entry.entry_id}_input_30'
    entity_id = registry.async_get_entity_id('sensor', DOMAIN, uid)
    assert entity_id is not None
    registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state not in ('unknown', 'unavailable')
    assert state.attributes.get('unit_of_measurement') is None
    assert state.attributes.get('device_class') is None
    assert state.attributes['state_class'] == 'measurement'
    assert not [record for record in caplog.records
                if record.levelname == 'WARNING'
                and 'input_calculated_heating_demand' in record.message
                and 'unknown value kind' in record.message]

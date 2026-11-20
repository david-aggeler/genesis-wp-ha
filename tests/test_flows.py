"""Estimated condenser and brine flow sensors (requirement-26), against the emulator."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from custom_components.genesis_wp.const import DOMAIN
from genesis_wp.emulator import heating
from genesis_wp.emulator.climate import BUCKETS, LICENSE, SOURCE, ClimateProfile
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import PROFILE_615
from .helpers import entry_data
from .helpers import setup_entry

KEYS = ("condenser_flow", "brine_flow")
START = datetime(2026, 1, 15, 0, 0)


def flat_climate(celsius: float = 5.0) -> ClimateProfile:
    """A constant outdoor temperature, as genesis-wp tests/emulator/test_derived_flows.py builds it."""
    values = tuple(tuple(celsius for _ in range(24)) for _ in range(BUCKETS["month"]))
    return ClimateProfile("month", date(2021, 1, 1), date(2025, 12, 31), 0.0, 0.0, "UTC", SOURCE, LICENSE, values)


def flow_entities(hass, entry) -> dict[str, str]:
    registry = er.async_get(hass)
    return {key: registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_derived_{key}") for key in KEYS}


# DHF-REQ: genesis-wp-ha/requirement-26  DHF-TEST: genesis-wp-ha/ac-106 genesis-wp-ha/issue-23
async def test_flow_sensors_report_the_estimate_in_liters_per_minute(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    coordinator = hass.data[DOMAIN][entry.entry_id]
    ids = flow_entities(hass, entry)
    assert all(ids.values()), ids
    for key, entity_id in ids.items():
        state = hass.states.get(entity_id)
        assert state.attributes["unit_of_measurement"] == "L/min"
        assert state.attributes["register"] == f"derived_{key}"
        # issue-23: the entity name states the value is an estimate.
        expected = {"condenser_flow": "Estimated condenser flow", "brine_flow": "Estimated brine flow"}[key]
        assert state.attributes["friendly_name"].endswith(f" {expected}"), state.attributes["friendly_name"]
        estimate = coordinator.flows[key]
        # One captured update: no window yet and no calibration, so no value; unknown, never 0.
        assert estimate.value is None
        assert state.state == "unknown"
        assert state.attributes["source"] == estimate.source == "unknown"
        assert state.attributes["calibration"] is None


# DHF-REQ: genesis-wp-ha/requirement-26  DHF-TEST: genesis-wp-ha/ac-107 genesis-wp-ha/ac-106
async def test_one_estimator_per_loop_reaches_a_calculated_flow(hass, start_emulator):
    emu = await start_emulator(PROFILE_615, dynamics=True, climate=flat_climate(), start_time=START)
    entry = await setup_entry(hass, emu)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    estimators = dict(coordinator.flow_estimators)
    assert set(estimators) == set(KEYS)
    coordinator.flow_clock = lambda: emu.simulated_time.timestamp()
    for _ in range(8):  # 7 simulated minutes: more than one 300 s window, 60 s apart (gap limit 120 s)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        emu.advance(60)
    assert {k: id(v) for k, v in coordinator.flow_estimators.items()} == {k: id(v) for k, v in estimators.items()}
    data = coordinator.data
    configured = {
        "condenser_flow": heating.CONDENSER_FLOW_PER_PERCENT * data["input_condenser_circulation_pump_speed"],
        "brine_flow": heating.BRINE_FLOW_PER_PERCENT * data["input_brine_circulation_pump_speed"],
    }
    for key, entity_id in flow_entities(hass, entry).items():
        state = hass.states.get(entity_id)
        estimator = estimators[key]
        assert state.attributes["source"] == "calculated", key
        value = float(state.state)
        assert 0 <= value <= estimator.max_flow
        assert value == pytest.approx(configured[key], rel=0.05)
        assert state.attributes["calibration"] == estimator.calibration
        assert estimator.calibration is not None


PUMPS = {"condenser_flow": "input_condenser_circulation_pump_speed", "brine_flow": "input_brine_circulation_pump_speed"}


def storage_key(entry) -> str:
    return f"{DOMAIN}.flow_calibration.{entry.entry_id}"


async def calibrated_entry(hass, start_emulator):
    """An entry whose estimators learned a calibration over more than one window."""
    emu = await start_emulator(PROFILE_615, dynamics=True, climate=flat_climate(), start_time=START)
    entry = await setup_entry(hass, emu)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.flow_clock = lambda: emu.simulated_time.timestamp()
    for _ in range(8):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        emu.advance(60)
    learned = {key: e.calibration for key, e in coordinator.flow_estimators.items()}
    assert all(learned.values()), learned
    return emu, entry, learned


# DHF-REQ: genesis-wp-ha/requirement-26  DHF-TEST: genesis-wp-ha/ac-110
async def test_restart_reports_a_flow_from_the_stored_calibration(hass, hass_storage, start_emulator):
    emu, entry, learned = await calibrated_entry(hass, start_emulator)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[storage_key(entry)]["data"] == learned  # written on unload, not only delayed

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    for key, entity_id in flow_entities(hass, entry).items():
        state = hass.states.get(entity_id)
        assert state.attributes["source"] == "pump_speed", key
        assert state.attributes["calibration"] == learned[key]
        expected = learned[key] * coordinator.data[PUMPS[key]]
        assert float(state.state) == pytest.approx(expected), key


# DHF-REQ: genesis-wp-ha/requirement-26  DHF-TEST: genesis-wp-ha/ac-110
async def test_a_stored_calibration_the_library_rejects_is_dropped(hass, hass_storage, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(emu))
    hass_storage[storage_key(entry)] = {"version": 1, "key": storage_key(entry),
                                        "data": {"condenser_flow": -1.0, "brine_flow": "x"}}
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for entity_id in flow_entities(hass, entry).values():
        state = hass.states.get(entity_id)
        assert state.state == "unknown"
        assert state.attributes["calibration"] is None


# DHF-REQ: genesis-wp-ha/requirement-26  DHF-TEST: genesis-wp-ha/ac-111
async def test_removing_the_entry_discards_its_calibration(hass, hass_storage, start_emulator):
    emu, entry, _ = await calibrated_entry(hass, start_emulator)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(entry) in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(entry) not in hass_storage

    added = await setup_entry(hass, emu)
    for entity_id in flow_entities(hass, added).values():
        assert hass.states.get(entity_id).state == "unknown"

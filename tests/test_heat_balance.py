"""Home Assistant state for the heat balance sensors."""

import math
from datetime import datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import pytest
from genesis_wp.const import ATTR_INPUT_CURRENT_POWER_OUTPUT
from genesis_wp.derived import HC2_PASSIVE_COOLING, HC2_PUMP, ReturnEstimate
from homeassistant.components.sensor.recorder import reset_detected
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import restore_state
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import genesis_wp
from custom_components.genesis_wp.const import DOMAIN

from .harness import PROFILE_615
from .helpers import entry_data, setup_entry
from .test_flows import START, flat_climate


def state_for(hass, entry, key):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_derived_{key}"
    )
    assert entity_id is not None
    return hass.states.get(entity_id)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-137
@pytest.mark.parametrize("cooling", [False, True])
async def test_room_power_follows_emulator_estimate(hass, start_emulator, monkeypatch, cooling):
    monkeypatch.setattr(genesis_wp, "ThermiaGenesis", partial(genesis_wp.ThermiaGenesis, delay=0))
    emu = await start_emulator(
        PROFILE_615, dynamics=True, climate=flat_climate(), start_time=START,
        capabilities={"passive_cooling": True} if cooling else None,
    )
    if cooling:
        emu.hold_outdoor(emu.heating.holding[303] + 1)
    emu.step(60)
    entry = MockConfigEntry(
        domain=DOMAIN, data=entry_data(emu), options={"buffer_volume": 300, "circuit_flow": 18.33}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.flow_clock = lambda: emu.simulated_time.timestamp()
    assert state_for(hass, entry, "heat_to_rooms").state == "unavailable"
    for minute in range(36):
        await coordinator.async_refresh()
        if cooling:
            assert coordinator.data[HC2_PASSIVE_COOLING[1]] is True
        if minute < 30 or cooling:
            assert state_for(hass, entry, "heat_to_rooms").state == "unavailable"
        emu.advance(60)
    if not cooling:
        power = state_for(hass, entry, "heat_to_rooms")
        assert math.isfinite(float(power.state))
        assert float(power.state) == pytest.approx(state_for(hass, entry, "hc2_return").attributes["heat"])
        assert power.attributes["device_class"] == "power"
        assert power.attributes["unit_of_measurement"] == "kW"


@pytest.fixture
async def balance(hass, start_emulator, monkeypatch):
    now = datetime(2026, 1, 15, 20, tzinfo=ZoneInfo("Europe/Zurich"))
    power, heat, mode, fr2 = 0.0, None, None, True
    monkeypatch.setattr(dt_util, "now", lambda: now)
    library_factory = genesis_wp.ThermiaGenesis

    def factory(*args, **kwargs):
        client = library_factory(*args, **kwargs, delay=0)
        update = client.async_update

        async def read(*args, **kwargs):
            data = await update(*args, **kwargs)
            data = {**data, ATTR_INPUT_CURRENT_POWER_OUTPUT: power, HC2_PUMP: fr2}
            if mode is not None:
                data[genesis_wp.OPERATING_MODE] = mode
            return data

        client.async_update = read
        return client

    monkeypatch.setattr(genesis_wp, "ThermiaGenesis", factory)
    monkeypatch.setattr(
        genesis_wp.HeatingCircuit2ReturnEstimator, "add",
        lambda *_: ReturnEstimate(30.0 if heat is not None else None, heat),
    )
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))

    def advance(seconds):
        nonlocal now
        now += timedelta(seconds=seconds)

    async def refresh(produced, rooms, seconds=60, operating=None, pump=True):
        nonlocal power, heat, mode, fr2
        advance(seconds)
        power, heat, mode, fr2 = produced, rooms, operating, pump
        await hass.data[DOMAIN][entry.entry_id].async_refresh()

    return entry, refresh, advance


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-138
async def test_produced_today_trapezoids_and_gaps(hass, balance):
    entry, refresh, _ = balance
    await refresh(3, None, 300)
    for _ in range(60):
        await refresh(3, None)
    await refresh(9, None, 300)
    state = state_for(hass, entry, "heat_produced_today")
    assert float(state.state) == pytest.approx(3)
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["unit_of_measurement"] == "kWh"
    await refresh(3, None, 120)
    assert float(state_for(hass, entry, "heat_produced_today").state) == pytest.approx(3.2)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-139
async def test_rooms_today_counts_only_valid_pairs(hass, balance):
    entry, refresh, _ = balance
    for _ in range(29):
        await refresh(3, None)
    for _ in range(91):
        await refresh(3, 2)
    state = state_for(hass, entry, "heat_to_rooms_today")
    assert float(state.state) == pytest.approx(3)
    assert state.attributes["coverage"] == pytest.approx(75)



# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-139
async def test_coverage_counts_fr2_running_time_only(hass, balance):
    entry, refresh, _ = balance
    for _ in range(29):
        await refresh(3, None)
    for _ in range(91):
        await refresh(3, 2)
    for _ in range(60):
        await refresh(3, None, pump=False)
    state = state_for(hass, entry, "heat_to_rooms_today")
    assert float(state.state) == pytest.approx(3)
    assert state.attributes["coverage"] == pytest.approx(75)
# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-140
async def test_daily_counters_restore_and_roll_over(hass, balance):
    entry, refresh, advance = balance
    await refresh(12.5, 9, 300)
    for _ in range(60):
        await refresh(12.5, 9)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def produced():
        return state_for(hass, entry, "heat_produced_today")

    def rooms():
        return state_for(hass, entry, "heat_to_rooms_today")
    assert float(produced().state) == pytest.approx(12.5)
    assert float(rooms().state) == pytest.approx(9)
    assert rooms().attributes["coverage"] == pytest.approx(3600 / 3900 * 100)
    await refresh(12.5, 9)
    assert float(produced().state) == pytest.approx(12.5 * 61 / 60)
    assert float(rooms().state) == pytest.approx(9 * 61 / 60)

    await refresh(12, 6, 2 * 3600 + 53 * 60 + 30)
    await refresh(12, 6)
    assert float(produced().state) == pytest.approx(0.1)
    assert float(rooms().state) == pytest.approx(0.05)
    assert rooms().attributes["coverage"] == 100
    assert "last_reset" not in produced().attributes
    assert "last_reset" not in rooms().attributes

    assert await hass.config_entries.async_unload(entry.entry_id)
    advance(24 * 3600)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert float(produced().state) == 0
    assert float(rooms().state) == 0


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-171
@pytest.mark.parametrize("cross_midnight", [False, True])
async def test_daily_counters_survive_clock_rollback(hass, balance, cross_midnight):
    entry, refresh, _ = balance
    keys = ("heat_produced_today", "heat_to_rooms_today")
    await refresh(3, 3, 4 * 3600 - 90 if cross_midnight else 300)
    await refresh(3, 3)
    if cross_midnight:
        await refresh(3, 3)
    for key in keys:
        assert float(state_for(hass, entry, key).state) == pytest.approx(
            0.025 if cross_midnight else 0.05
        )

    await refresh(3, 3, -45 if cross_midnight else -30)
    for key in keys:
        assert float(state_for(hass, entry, key).state) == pytest.approx(
            0.025 if cross_midnight else 0.05
        )

    await refresh(3, 3, 75 if cross_midnight else 60)
    for key in keys:
        assert float(state_for(hass, entry, key).state) == pytest.approx(
            0.05 if cross_midnight else 0.075
        )


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-172
@pytest.mark.parametrize("snapshot", [
    [1],
    {"day": "2026-01-15", "energy": 10**400, "covered_seconds": 0, "pump_seconds": 0},
], ids=["array", "oversized-integer"])
async def test_daily_counters_ignore_invalid_restore_data(hass, balance, snapshot):
    entry, refresh, _ = balance
    keys = ("heat_produced_today", "heat_to_rooms_today")
    await refresh(3, 3, 300)
    states = [state_for(hass, entry, key) for key in keys]
    assert await hass.config_entries.async_unload(entry.entry_id)
    stored = restore_state.async_get(hass).last_states
    for state in states:
        stored[state.entity_id] = restore_state.StoredState.from_dict({
            "state": state.as_dict(),
            "last_seen": dt_util.now(),
            "extra_data": snapshot,
        })

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for key in keys:
        assert float(state_for(hass, entry, key).state) == 0
    await refresh(3, 3)
    for key in keys:
        assert float(state_for(hass, entry, key).state) == pytest.approx(0.05)


async def _reload(hass, entry):
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-173
async def test_reload_during_rollback_does_not_recount(hass, balance):
    entry, refresh, advance = balance
    keys = ("heat_produced_today", "heat_to_rooms_today")
    await refresh(3, 3, 300)
    await refresh(3, 3)
    assert await hass.config_entries.async_unload(entry.entry_id)
    advance(-30)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await refresh(3, 3)
    for key in keys:
        assert float(state_for(hass, entry, key).state) == pytest.approx(0.075)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-174
async def test_hot_water_with_fr2_on_adds_no_covered_time(hass, balance):
    entry, refresh, _ = balance
    await refresh(3, 2, 300)
    for _ in range(10):
        await refresh(3, 2)
    for _ in range(10):
        await refresh(3, 2, operating="Hot water")
    state = state_for(hass, entry, "heat_to_rooms_today")
    assert float(state.state) == pytest.approx(2 * 600 / 3600)
    # FR2 ran 1500 s (the opening 300 s gap, 600 s heating, 600 s hot water); 600 s are covered.
    assert state.attributes["coverage"] == pytest.approx(40)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-175
async def test_restored_coverage_is_a_bounded_percentage(hass, balance):
    entry, refresh, _ = balance
    await refresh(3, 3, 300)
    state = state_for(hass, entry, "heat_to_rooms_today")
    assert await hass.config_entries.async_unload(entry.entry_id)
    restore_state.async_get(hass).last_states[state.entity_id] = restore_state.StoredState.from_dict({
        "state": state.as_dict(),
        "last_seen": dt_util.now(),
        "extra_data": {"day": "2026-01-15", "energy": 0, "covered_seconds": 1e307, "pump_seconds": 1e307},
    })
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coverage = state_for(hass, entry, "heat_to_rooms_today").attributes["coverage"]
    assert coverage is None or (math.isfinite(coverage) and 0 <= coverage <= 100)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-176
async def test_missing_sample_during_rollback_breaks_the_pair(hass, balance):
    entry, refresh, _ = balance
    await refresh(3, None, 300)
    await refresh(3, None)
    await refresh(None, None, -30)
    await refresh(3, None)
    assert float(state_for(hass, entry, "heat_produced_today").state) == pytest.approx(0.05)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-177
async def test_rollover_energy_reaches_statistics(hass, balance):
    entry, refresh, _ = balance
    entity_id = state_for(hass, entry, "heat_produced_today").entity_id
    await refresh(0.6, None, 4 * 3600 - 90)
    await refresh(0.6, None)
    assert float(state_for(hass, entry, "heat_produced_today").state) == pytest.approx(0.01)
    states = []
    hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        lambda event: event.data["entity_id"] == entity_id and states.append(event.data["new_state"]),
    )
    # The new day's first contribution (00:00:00 to 00:01:30) exceeds the old day's final 0.01 kWh.
    await refresh(3, None, 120)
    await hass.async_block_till_done()
    previous, added = 0.01, 0.0
    for state in states:
        value = float(state.state)
        if reset_detected(hass, entity_id, value, previous, state):
            added += value
        else:
            added += value - previous
        previous = value
    final = float(state_for(hass, entry, "heat_produced_today").state)
    assert final > 0.01
    assert added == pytest.approx(final)


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-178
async def test_room_energy_has_no_value_when_hc2_is_absent(hass, balance, monkeypatch):
    entry, refresh, _ = balance
    coordinator = hass.data[DOMAIN][entry.entry_id]
    monkeypatch.setattr(
        type(coordinator.thermia), "capability_state",
        lambda self, name: genesis_wp.ABSENT if name == "heating_circuit_2" else "present",
    )
    await refresh(3, 3, 300)
    await refresh(3, 3)
    assert state_for(hass, entry, "heat_to_rooms_today").state in ("unavailable", "unknown")


# DHF-TEST: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-178
async def test_room_energy_absent_without_estimator(hass, start_emulator, monkeypatch):
    monkeypatch.setattr(genesis_wp, "ThermiaGenesis", partial(genesis_wp.ThermiaGenesis, delay=0))
    emu = await start_emulator(PROFILE_615)
    entry = MockConfigEntry(
        domain=DOMAIN, data=entry_data(emu), options={"buffer_volume": 300, "circuit_flow": -1}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_derived_heat_to_rooms_today"
    )
    state = hass.states.get(entity_id) if entity_id else None
    assert state is None or state.state in ("unavailable", "unknown")

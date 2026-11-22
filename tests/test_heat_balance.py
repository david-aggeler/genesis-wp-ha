"""Home Assistant state for the heat balance sensors."""

import math
from datetime import datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import pytest
from genesis_wp.const import ATTR_INPUT_CURRENT_POWER_OUTPUT
from genesis_wp.derived import HC2_PASSIVE_COOLING, HC2_PUMP, ReturnEstimate
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
    power, heat = 0.0, None
    monkeypatch.setattr(dt_util, "now", lambda: now)
    library_factory = genesis_wp.ThermiaGenesis

    def factory(*args, **kwargs):
        client = library_factory(*args, **kwargs, delay=0)
        update = client.async_update

        async def read(*args, **kwargs):
            data = await update(*args, **kwargs)
            return {**data, ATTR_INPUT_CURRENT_POWER_OUTPUT: power, HC2_PUMP: True}

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

    async def refresh(produced, rooms, seconds=60):
        nonlocal power, heat
        advance(seconds)
        power, heat = produced, rooms
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

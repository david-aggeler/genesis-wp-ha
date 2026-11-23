"""Buffer discharge assessment through loopback emulator refreshes."""

from datetime import datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import pytest

from custom_components import genesis_wp
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp.emulator import Emulator
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .helpers import setup_entry


@pytest.fixture
async def buffer(hass, start_emulator, monkeypatch, request):
    now = datetime(2026, 1, 15, 23, tzinfo=ZoneInfo("Europe/Zurich"))
    if getattr(request, "param", False):
        now = datetime.now(dt_util.DEFAULT_TIME_ZONE).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        monkeypatch.setattr(genesis_wp, "SCAN_INTERVAL", timedelta(days=2))
    bits = {199: True, 209: True, 245: False}
    inputs = {1: 4, 12: 3700, 41: 3900, 68: 3400, 147: 3200}
    original = Emulator._action

    async def action(self, function_code, start_address, address, count, registers, values):
        await original(self, function_code, start_address, address, count, registers, values)
        if function_code == 2:
            for index, value in bits.items():
                word, bit = divmod(index - start_address * 16, 16)
                if 0 <= word < len(registers):
                    registers[word] = (registers[word] & ~(1 << bit)) | (int(value) << bit)
        if function_code == 4:
            for index, value in inputs.items():
                if address <= index < address + count:
                    registers[index - start_address] = value

    monkeypatch.setattr(Emulator, "_action", action)
    monkeypatch.setattr(dt_util, "now", lambda: now)
    monkeypatch.setattr(genesis_wp, "ThermiaGenesis", partial(genesis_wp.ThermiaGenesis, delay=0))
    emu = await start_emulator()
    entry = await setup_entry(hass, emu)

    async def sample(on=True, temp=3800, target=3200, *, fr2=True, mode=4, cooling=False, spread=100):
        bits.update({199: on, 209: fr2, 245: cooling})
        inputs.update({1: mode, 12: temp - spread, 41: temp + spread, 147: target})
        await hass.data[DOMAIN][entry.entry_id].async_refresh()

    async def phase(restart, stop=3800, target=3200, *, spread=100):
        await sample(False, stop, target=3000, spread=spread)
        await sample(True, restart, target, spread=spread)

    def read(key):
        entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_derived_{key}")
        assert entity_id is not None, key
        return hass.states.get(entity_id)

    async def reload(hours=0):
        nonlocal now
        assert await hass.config_entries.async_unload(entry.entry_id)
        now += timedelta(hours=hours)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    def advance(hours):
        nonlocal now
        now += timedelta(hours=hours)

    yield sample, phase, read, reload, advance, emu, entry
    assert emu.writes == []


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-142
async def test_completed_discharge(buffer):
    _, phase, read, *_ = buffer
    await phase(3150)
    value = read("last_discharge_restart_margin")
    assert float(value.state) == -0.5
    assert value.attributes["unit_of_measurement"] == "K"
    assert value.attributes["drawn_energy"] == 2.26
    assert value.attributes["cold_tail_share"] == 7.7


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-143
async def test_excluded_samples_invalidate_the_whole_phase(buffer):
    sample, phase, read, *_ = buffer
    await phase(3250)
    for exclusion in ({"fr2": False}, {"mode": 3}, {"cooling": True}):
        await sample(False)
        await sample(False, **exclusion)
        await sample(True, 3350)
        assert float(read("last_discharge_restart_margin").state) == 0.5, exclusion
    daily = read("median_restart_margin_today")
    assert float(daily.state) == 0.5
    assert daily.attributes["phase_count"] == 1


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-144
@pytest.mark.parametrize(("phases", "margin", "share", "judgement"), [
    ([(3150, 3400), (3450, 3800)], 1, 10, "keep"),
    ([(3500, 3800)], 3, 0, "lower"),
    ([(3150, 3367)], -0.5, 23, "raise"),
    ([(3100, 3350), (3500, 3800)], 1, 20, "raise"),
])
async def test_daily_judgement(hass, buffer, phases, margin, share, judgement):
    _, phase, read, reload, _, _, entry = buffer
    assert read("buffer_judgement").state == "unknown"
    for restart, stop in phases:
        await phase(restart, stop)
    daily = read("median_restart_margin_today")
    assert float(daily.state) == margin
    assert daily.attributes["median_cold_tail_share"] == share
    assert read("buffer_judgement").state == judgement

    hass.config_entries.async_update_entry(entry, options={"buffer_reference_offset": None})
    await reload()
    assert read("buffer_judgement").state == "unknown"
    assert float(read("median_restart_margin_today").state) == margin


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-145
@pytest.mark.parametrize("address", [68, 147])
async def test_curve_gap_refresh(hass, buffer, address):
    sample, _, read, _, _, emu, entry = buffer
    assert float(read("curve_gap").state) == 2.0
    emu.inject_fault("input_registers", address)
    await sample()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.last_update_success:
        await sample()
    assert coordinator.last_update_success
    assert read("curve_gap").state == "unavailable"


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-146
@pytest.mark.parametrize("hours", [0, 2])
async def test_daily_phases_restore_only_on_same_day(buffer, hours):
    _, phase, read, reload, _, _, _ = buffer
    for restart in (3250, 3300, 3500):
        await phase(restart)
    await reload(hours)
    await phase(3400)
    daily = read("median_restart_margin_today")
    assert float(daily.state) == (2.0 if hours else 1.5)
    assert daily.attributes["phase_count"] == (1 if hours else 4)


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-146
async def test_local_midnight_clears_daily_values(buffer):
    sample, phase, read, _, advance, _, _ = buffer
    await phase(3250)
    advance(2)
    await sample()
    assert read("median_restart_margin_today").state == "unknown"
    assert read("median_restart_margin_today").attributes["phase_count"] == 0
    assert read("buffer_judgement").state == "unknown"
    assert float(read("last_discharge_restart_margin").state) == 0.5


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-144
@pytest.mark.parametrize(("phases", "spread"), [
    ([(2502, 2602, 2302)], 1),
    ([(2501, 2601, 2501)], 1),
    ([(2502, 2602, 2532), (2600, 2700, 2500)], 2),
])
async def test_judgement_includes_threshold_equalities(buffer, phases, spread):
    _, phase, read, *_ = buffer
    for restart, stop, target in phases:
        await phase(restart, stop, target, spread=spread)
    assert read("buffer_judgement").state == "keep"


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-146
async def test_judgement_restores_with_median_disabled(hass, buffer):
    _, phase, read, reload, _, _, entry = buffer
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_derived_median_restart_margin_today"
    )
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await reload()
    assert read("median_restart_margin_today") is None
    await phase(3500)
    assert read("buffer_judgement").state == "lower"
    await reload()
    assert read("median_restart_margin_today") is None
    assert read("buffer_judgement").state == "lower"


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-142
async def test_drawn_energy_avoids_intermediate_overflow(hass, buffer):
    _, phase, read, reload, _, _, entry = buffer
    hass.config_entries.async_update_entry(entry, options={"buffer_volume": 1e308})
    await reload()
    await phase(3150)
    assert read("last_discharge_restart_margin").attributes["drawn_energy"] == pytest.approx(
        7.547222222222222e305
    )


# DHF-TEST: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-146
@pytest.mark.parametrize("buffer", [True], indirect=True)
async def test_scheduled_local_midnight_clears_daily_values(hass, buffer):
    _, phase, read, _, _, _, _ = buffer
    await phase(3250)
    assert read("median_restart_margin_today").attributes["phase_count"] == 1
    midnight = dt_util.now() + timedelta(seconds=1)
    async_fire_time_changed(hass, midnight)
    await hass.async_block_till_done()
    assert read("median_restart_margin_today").state == "unknown"
    assert read("median_restart_margin_today").attributes["phase_count"] == 0
    assert read("buffer_judgement").state == "unknown"
    assert float(read("last_discharge_restart_margin").state) == 0.5

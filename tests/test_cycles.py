"""Compressor run statistics through emulator refreshes and Home Assistant states."""

import asyncio
from datetime import date, datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

import pytest

from custom_components import genesis_wp
from custom_components.genesis_wp import cycles as cycle_tracking
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp.emulator import Emulator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .helpers import setup_entry


@pytest.fixture
async def cycles(hass, start_emulator, monkeypatch):
    """Drive emulator register samples and the local clock independently."""
    now = datetime(2026, 1, 15, 12, tzinfo=ZoneInfo("Europe/Zurich"))
    elapsed = 0.0
    signal = False
    mode = 4
    original = Emulator._action

    async def action(self, function_code, start_address, address, count, registers, values):
        result = await original(self, function_code, start_address, address, count, registers, values)
        if function_code == 2 and address <= 199 < address + count:
            word, bit = divmod(199 - start_address * 16, 16)
            registers[word] = (registers[word] & ~(1 << bit)) | (int(signal) << bit)
        if function_code == 4 and address <= 1 < address + count:
            registers[1 - start_address] = mode
        return result

    monkeypatch.setattr(Emulator, "_action", action)
    monkeypatch.setattr(dt_util, "now", lambda: now)
    monkeypatch.setattr(cycle_tracking, "monotonic", lambda: elapsed)
    monkeypatch.setattr(genesis_wp, "ThermiaGenesis", partial(genesis_wp.ThermiaGenesis, delay=0))
    emu = await start_emulator()
    entry = await setup_entry(hass, emu)

    async def sample(on, minutes=0, hot_water=False, clock_correction=0):
        nonlocal now, elapsed, signal, mode
        now += timedelta(minutes=minutes + clock_correction)
        elapsed += minutes * 60
        signal = on
        mode = 3 if hot_water else 4
        await hass.data[DOMAIN][entry.entry_id].async_refresh()

    async def run(minutes, hot_water=False):
        await sample(True, hot_water=hot_water)
        await sample(False, minutes)

    def read(key):
        entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_derived_{key}")
        assert entity_id is not None, key
        return hass.states.get(entity_id)

    async def reload(days):
        nonlocal now
        assert await hass.config_entries.async_unload(entry.entry_id)
        now += timedelta(days=days)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    yield sample, run, read, reload, emu, entry
    assert emu.writes == []


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-130
async def test_starts_count_only_signal_edges(cycles):
    sample, run, read, _, _, _ = cycles
    await run(8)
    await sample(True, hot_water=True)
    await sample(True, 20)
    await sample(False, 20)
    await sample(True)
    assert read("starts_today").state == "3"
    assert read("hot_water_starts_today").state == "1"
    assert read("last_run_length").attributes["kind"] == "hot_water"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-131
async def test_heating_lengths_and_total_runtime(cycles):
    _, run, read, _, _, _ = cycles
    for minutes in (8, 25, 70):
        await run(minutes)
    await run(40, hot_water=True)
    assert float(read("heating_run_minimum").state) == 8
    assert read("heating_run_minimum").attributes["band"] == "very_short"
    assert float(read("heating_run_mean").state) == 34.3
    assert read("heating_run_mean").attributes["band"] == "warning"
    assert float(read("heating_run_maximum").state) == 70
    assert read("heating_run_maximum").attributes["band"] == "good"
    assert float(read("running_hours_today").state) == 2.38


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-132
@pytest.mark.parametrize(("minutes", "band"), [(5.9, "short_cycle"), (6, "very_short"),
                                             (10, "short"), (30, "acceptable"), (60, "good")])
async def test_run_bands(cycles, minutes, band):
    _, run, read, _, _, _ = cycles
    await run(minutes)
    assert read("last_run_length").attributes["band"] == band


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-132
@pytest.mark.parametrize(("minutes", "band"), [(29.9, "bad"), (30, "warning"),
                                             (60, "acceptable"), (120, "good")])
async def test_mean_bands(cycles, minutes, band):
    _, run, read, _, _, _ = cycles
    await run(minutes)
    assert read("heating_run_mean").attributes["band"] == band


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-133
async def test_only_heating_runs_under_ten_minutes_count_as_short(cycles):
    _, run, read, _, _, _ = cycles
    for minutes in (5, 9.9, 10):
        await run(minutes)
    await run(4, hot_water=True)
    assert read("short_heating_runs_today").state == "2"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-134
async def test_run_crossing_midnight_is_attributed_to_its_end_day(cycles):
    sample, run, read, _, _, _ = cycles
    await run(5)
    await run(70)
    await sample(True, 625)  # 23:40 local
    await sample(True, 20)
    assert float(read("running_hours_today").state) == 0
    await sample(False, 20)
    await sample(False, 1)
    assert read("starts_today").state == "1"
    assert read("short_heating_runs_today").state == "0"
    assert float(read("heating_run_maximum").state) == 40
    assert float(read("running_hours_today").state) == 0.67


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-135
@pytest.mark.parametrize(("days", "starts", "mean"), [(0, "5", 35), (1, "1", 40)])
async def test_restore_uses_only_current_local_day(cycles, days, starts, mean):
    sample, run, read, reload, _, _ = cycles
    for minutes in (20, 30, 50):
        await run(minutes)
    # Count an interrupted start without contributing a completed duration.
    await sample(True)
    assert read("starts_today").state == "4"
    await reload(days)
    await sample(False)
    await run(40)
    assert read("starts_today").state == starts
    assert float(read("heating_run_mean").state) == mean


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-136
async def test_unavailable_signal_discards_length_and_keeps_start(cycles):
    sample, run, read, _, emu, _ = cycles
    await run(25)
    await sample(True)
    emu.inject_fault("discrete_inputs", 199)
    await sample(True, 15)
    emu.clear_faults()
    await sample(False, 1)
    assert read("starts_today").state == "2"
    assert read("short_heating_runs_today").state == "0"
    for metric in ("minimum", "mean", "maximum"):
        assert float(read(f"heating_run_{metric}").state) == 25


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-157
async def test_reenabled_sensor_restores_latest_history(hass, cycles):
    _, run, read, reload, _, _ = cycles
    await run(20)
    entity_id = read("starts_today").entity_id
    registry = er.async_get(hass)
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await reload(0)
    assert hass.states.get(entity_id) is None
    await run(40)
    registry.async_update_entity(entity_id, disabled_by=None)
    await reload(0)
    assert read("starts_today").state == "2"
    assert float(read("heating_run_mean").state) == 30


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-158
async def test_replacement_entry_does_not_restore_reused_entity_id(hass, cycles):
    _, run, read, _, emu, entry = cycles
    await run(20)
    entity_id = read("starts_today").entity_id
    await hass.config_entries.async_remove(entry.entry_id)
    replacement = await setup_entry(hass, emu)
    registry = er.async_get(hass)
    assert registry.async_get(entity_id).config_entry_id == replacement.entry_id
    assert hass.states.get(entity_id).state == "0"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-159
async def test_clock_correction_does_not_change_elapsed_run_length(cycles):
    sample, _, read, _, _, _ = cycles
    await sample(True)
    await sample(False, 20, clock_correction=30)
    assert float(read("last_run_length").state) == 20


def test_restore_rejects_unrepresentable_duration():
    day = date(2026, 1, 15)
    snapshot = {"day": day.isoformat(), "starts": 1, "hot_water_starts": 0,
                "runs": [["heating", 10**400]]}
    assert cycle_tracking.DailyRuns.from_dict(day, snapshot) is None


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-160
async def test_backward_clock_correction_across_midnight_keeps_the_start(cycles):
    sample, _, read, _, _, _ = cycles
    await sample(False, 724)  # 00:04 local on the next day
    await sample(True, 1)  # 00:05
    await sample(True, clock_correction=-10)  # 23:55 on the previous date
    await sample(False, 1, clock_correction=10)  # 00:06 on the start date
    assert read("starts_today").state == "1"
    assert float(read("last_run_length").state) == 1


def _run_store_key(entry):
    return f"{DOMAIN}.compressor_runs.{entry.entry_id}"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-161
async def test_refresh_finishing_after_removal_writes_no_statistics(hass, hass_storage, cycles, monkeypatch):
    _, run, _, _, _, entry = cycles
    await run(20)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    original = coordinator.thermia.async_update
    reading, release = asyncio.Event(), asyncio.Event()

    async def held_update(**kwargs):
        data = await original(**kwargs)
        reading.set()
        await release.wait()
        return {**data, genesis_wp.COMPRESSOR_SIGNAL: True}  # a start: the tracker changes

    monkeypatch.setattr(coordinator.thermia, "async_update", held_update)
    refresh = hass.async_create_task(coordinator.async_refresh())
    await reading.wait()
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert _run_store_key(entry) not in hass_storage
    release.set()
    await refresh
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)  # flushes every pending delayed save
    await hass.async_block_till_done()
    assert _run_store_key(entry) not in hass_storage


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-162
async def test_snapshot_without_storage_version_does_not_prevent_setup(hass, hass_storage, cycles):
    _, run, read, _, _, entry = cycles
    await run(20)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass_storage[_run_store_key(entry)] = {  # valid payload; only the storage version is missing
        "key": _run_store_key(entry),
        "data": {"day": "2026-01-15", "starts": 1, "hot_water_starts": 0, "runs": [["heating", 20.0]]},
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert read("starts_today").state == "0"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-163
async def test_hot_water_last_run_has_kind_and_no_heating_band(cycles):
    _, run, read, _, _, _ = cycles
    await run(40, hot_water=True)
    state = read("last_run_length")
    assert float(state.state) == 40
    assert state.attributes["kind"] == "hot_water"
    assert "band" not in state.attributes


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-164
async def test_run_on_corrected_previous_date_stays_out_of_the_new_day(cycles):
    sample, _, read, _, _, _ = cycles
    await sample(False, 725)  # 00:05 local on the next day
    await sample(True, clock_correction=-10)  # 23:55 on the previous date
    await sample(False, 4)  # 23:59 on the previous date
    await sample(False, 2)  # 00:01 on the next day again
    assert read("starts_today").state == "0"
    assert read("last_run_length").state == "unknown"


async def _flush_pending_writes(hass):
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-165
async def test_removal_during_setup_retry_leaves_no_statistics(hass, hass_storage, cycles):
    _, _, _, _, emu, entry = cycles
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass_storage.pop(_run_store_key(entry), None)
    await emu.stop()
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert await hass.config_entries.async_remove(entry.entry_id)
    await _flush_pending_writes(hass)
    assert _run_store_key(entry) not in hass_storage


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-166
async def test_removal_after_failed_unload_leaves_no_statistics(hass, hass_storage, cycles, monkeypatch):
    _, run, _, _, _, entry = cycles
    await run(20)  # arms a delayed save
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async def refuse_unload(*_args):
        return False

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", refuse_unload)
    await hass.config_entries.async_remove(entry.entry_id)
    await _flush_pending_writes(hass)
    assert _run_store_key(entry) not in hass_storage
    hass.data[DOMAIN].pop(entry.entry_id, None)
    await coordinator.async_shutdown()
    await coordinator.async_close()


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-167
async def test_snapshot_with_unmatched_hot_water_run_restores_empty(hass, hass_storage, cycles):
    _, run, read, _, _, entry = cycles
    await run(20)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass_storage[_run_store_key(entry)] = {
        "key": _run_store_key(entry), "version": 1,
        "data": {"day": "2026-01-15", "starts": 1, "hot_water_starts": 0, "runs": [["hot_water", 40.0]]},
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert read("starts_today").state == "0"
    assert read("last_run_length").state == "unknown"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-166
async def test_removal_waits_for_a_save_already_in_flight(hass, hass_storage, cycles, monkeypatch):
    _, run, _, _, _, entry = cycles
    await run(20)  # arms a delayed save
    coordinator = hass.data[DOMAIN][entry.entry_id]
    store = genesis_wp.compressor_run_store(hass, entry.entry_id)._store
    original, writing, release = store.async_save, asyncio.Event(), asyncio.Event()

    async def held_save(data):
        writing.set()
        await release.wait()
        await original(data)

    monkeypatch.setattr(store, "async_save", held_save)

    async def refuse_unload(*_args):
        return False

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", refuse_unload)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)  # dispatches the pending save
    await writing.wait()
    run_store = genesis_wp.compressor_run_store(hass, entry.entry_id)
    original_remove, removing = run_store.async_remove, asyncio.Event()

    async def tracked_remove():
        removing.set()  # runs on into the store's lock without yielding first
        await original_remove()

    monkeypatch.setattr(run_store, "async_remove", tracked_remove)
    removal = hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
    await removing.wait()
    release.set()
    await removal
    await _flush_pending_writes(hass)
    assert _run_store_key(entry) not in hass_storage
    hass.data[DOMAIN].pop(entry.entry_id, None)
    await coordinator.async_shutdown()
    await coordinator.async_close()


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-168
async def test_corrected_forward_jump_across_midnight_keeps_the_start(cycles):
    sample, _, read, _, _, _ = cycles
    await sample(True, 711)  # 23:51 local
    await sample(False, 1)  # 23:52, one completed run
    await sample(False, clock_correction=10)  # 00:02 on the next date
    assert read("starts_today").state == "0"
    await sample(False, 1, clock_correction=-10)  # 23:53 on the original date
    assert read("starts_today").state == "1"


# DHF-TEST: genesis-wp-ha/requirement-28 genesis-wp-ha/ac-169
async def test_snapshot_with_unpublishable_start_count_restores_empty(hass, hass_storage, cycles):
    _, run, read, _, _, entry = cycles
    await run(20)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass_storage[_run_store_key(entry)] = {
        "key": _run_store_key(entry), "version": 1,
        "data": {"day": "2026-01-15", "starts": 10**255, "hot_water_starts": 0, "runs": []},
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert read("starts_today").state == "0"

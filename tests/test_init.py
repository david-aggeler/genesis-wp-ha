"""Setup, refresh and unload against genesis-wp-emulator (requirements 1, 3 and 7)."""

from __future__ import annotations

import pytest
from custom_components.genesis_wp.const import DOMAIN
from custom_components.genesis_wp.const import HEATPUMP_SENSOR
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import PROFILES
from .helpers import Unreachable
from .helpers import entry_data
from .helpers import setup_entry


# DHF-REQ: genesis-wp-ha/requirement-1  DHF-TEST: genesis-wp-ha/ac-1
# DHF-REQ: genesis-wp-ha/requirement-3  DHF-TEST: genesis-wp-ha/ac-7
@pytest.mark.parametrize("profile", PROFILES)
async def test_setup_refresh_and_unload(hass, start_emulator, profile):
    emu = await start_emulator(profile)
    entry = await setup_entry(hass, emu)
    assert entry.state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()  # HA raises on blocking calls inside the event loop
    assert coordinator.last_update_success
    assert coordinator.data[HEATPUMP_SENSOR] is not None

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    enabled = [e for e in entities if not e.disabled]
    assert enabled
    states = [hass.states.get(e.entity_id) for e in enabled]
    assert all(state is not None for state in states)
    numeric = [s for s in states if s.state not in ("unknown", "unavailable")]
    assert len(numeric) >= len(enabled) // 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert coordinator.thermia._connection is None  # client closed


async def test_unreachable_device_is_not_ready(hass, socket_enabled):
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(Unreachable))
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


# DHF-REQ: genesis-wp-ha/requirement-7  DHF-TEST: genesis-wp-ha/ac-18
async def test_two_entries_do_not_collide(hass, start_emulator):
    first = await setup_entry(hass, await start_emulator())
    second = await setup_entry(hass, await start_emulator())

    registry = er.async_get(hass)
    ids_first = {e.unique_id for e in er.async_entries_for_config_entry(registry, first.entry_id)}
    ids_second = {e.unique_id for e in er.async_entries_for_config_entry(registry, second.entry_id)}
    assert ids_first and len(ids_first) == len(ids_second)
    assert ids_first.isdisjoint(ids_second)

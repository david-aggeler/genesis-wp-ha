"""Emulated heat pump selectable in the config flow, in-process emulator (requirement-10)."""

from __future__ import annotations

import asyncio

import pytest
from custom_components.genesis_wp.const import CONF_CAPABILITIES
from custom_components.genesis_wp.const import CONF_MODE
from custom_components.genesis_wp.const import CONF_MODEL
from custom_components.genesis_wp.const import CONF_PROFILE
from custom_components.genesis_wp.const import DOMAIN
from custom_components.genesis_wp.const import MODE_EMULATED
from genesis_wp.emulator import get_profile
from genesis_wp import const as c
from genesis_wp.capabilities import CAPABILITY_NAMES
from genesis_wp.emulator import packaged_profiles
from genesis_wp.emulator.capabilities import CapabilityError
from genesis_wp.emulator.capabilities import selection_overrides
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .harness import PROFILE_606
from .harness import PROFILE_615
from .harness import gates
from .harness import WPE_I_KIND
from .helpers import setup_entry


async def _module_step(hass, profile=PROFILE_615):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "emulated"})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: profile})


async def _add_emulated(hass, profile=PROFILE_615, modules=None):
    result = await _module_step(hass, profile)
    assert result["step_id"] == "modules"
    return await hass.config_entries.flow.async_configure(result["flow_id"], modules or {})


async def _emulated_entry(hass, profile=PROFILE_615, modules=None):
    result = await _add_emulated(hass, profile, modules)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


def _device(hass, entry):
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return device


async def _refused(port) -> bool:
    try:
        _, writer = await asyncio.open_connection("127.0.0.1", port)
    except OSError:
        return True
    writer.close()
    return False


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-28
async def test_menu_offers_real_and_emulated(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"real", "emulated"}


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-28
async def test_profile_step_lists_exactly_the_packaged_profiles(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "emulated"})
    assert result["type"] is FlowResultType.FORM
    (selector,) = [v for k, v in result["data_schema"].schema.items() if str(k) == CONF_PROFILE]
    assert [o["value"] for o in selector.config["options"]] == packaged_profiles()


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-28
@pytest.mark.parametrize("profile", [PROFILE_606, PROFILE_615])
async def test_emulated_entry_has_no_host_and_the_profile_firmware(hass, socket_enabled, profile):
    entry = await _emulated_entry(hass, profile)
    assert entry.data[CONF_MODE] == MODE_EMULATED
    assert entry.data[CONF_PROFILE] == profile
    assert entry.data[CONF_MODEL] == WPE_I_KIND  # from the profile, not asked
    assert CONF_HOST not in entry.data
    assert hass.data[DOMAIN][entry.entry_id].last_update_success
    assert _device(hass, entry).sw_version == get_profile(profile).firmware["software"]
    assert await hass.config_entries.async_unload(entry.entry_id)


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-29
async def test_emulator_lives_on_loopback_for_the_entry_lifetime(hass, socket_enabled):
    entry = await _emulated_entry(hass)
    first = hass.data[DOMAIN][entry.entry_id].emulator
    assert first.host == "127.0.0.1" and first.port not in (0, 502, 5020)
    assert first.connections >= 1 and first.requests  # the client talks to this emulator

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await _refused(first.port)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    second = hass.data[DOMAIN][entry.entry_id].emulator
    assert second is not first and second.requests
    states = [hass.states.get(e.entity_id) for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) if not e.disabled]
    assert states and any(s.state != "unavailable" for s in states)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await _refused(second.port)


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-30
async def test_emulated_entry_coexists_with_a_real_entry_and_never_writes(hass, start_emulator):
    real = await setup_entry(hass, await start_emulator())
    emulated = await _emulated_entry(hass)

    assert _device(hass, real).id != _device(hass, emulated).id
    assert _device(hass, emulated).name.endswith("(emulated)")
    assert not _device(hass, real).name.endswith("(emulated)")
    registry = er.async_get(hass)
    real_ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, real.entry_id)}
    emulated_ids = {e.unique_id for e in er.async_entries_for_config_entry(registry, emulated.entry_id)}
    assert real_ids and emulated_ids and not real_ids & emulated_ids

    coordinator = hass.data[DOMAIN][emulated.entry_id]
    emu = coordinator.emulator
    for _ in range(3):
        await coordinator.async_refresh()
        assert coordinator.last_update_success
    assert await hass.config_entries.async_unload(emulated.entry_id)
    assert emu.requests and emu.writes == []
    assert {r.function_code for r in emu.requests} <= {1, 2, 3, 4}


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-30
async def test_emulated_entry_cannot_be_reconfigured(hass, socket_enabled):
    entry = await _emulated_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "emulated_not_reconfigurable"
    assert await hass.config_entries.async_unload(entry.entry_id)


# DHF-REQ: genesis-wp-ha/requirement-10  DHF-TEST: genesis-wp-ha/ac-30
async def test_second_entry_for_the_same_profile_aborts(hass, socket_enabled):
    entry = await _emulated_entry(hass)
    result = await _add_emulated(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


def _accepted_both_ways(profile) -> list[str]:
    """Independent of the integration: every capability the library emulator switches on and off."""
    names = []
    for name in CAPABILITY_NAMES:
        try:
            selection_overrides(profile, {name: True})
            selection_overrides(profile, {name: False})
        except CapabilityError:
            continue
        names.append(name)
    return names


def _unique_ids(hass, entry) -> set[str]:
    return {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


def _register_ids(entry, registers) -> set[str]:
    spec = c.REGISTERS
    return {f"{entry.entry_id}_{spec[r][c.KEY_REG_TYPE]}_{spec[r][c.KEY_ADDRESS]}" for r in registers}


# DHF-REQ: genesis-wp-ha/requirement-13  DHF-TEST: genesis-wp-ha/ac-42
async def test_module_step_offers_only_choices_the_emulator_accepts(hass, socket_enabled):
    result = await _module_step(hass, PROFILE_615)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "modules"
    fields = {str(k): k.default() for k in result["data_schema"].schema}

    assert list(fields) == _accepted_both_ways(get_profile(PROFILE_615))
    assert not fields.keys() & {"ksm", "smart_grid", "additional_heater", "heating_circuit_3", "heating_circuit_4"}
    # Defaults: on where the 6.1.5 capture shows the module (the owner's plant), off elsewhere.
    assert {name for name, on in fields.items() if on} == {"heating_circuit_2", "buffer_tank"}
    assert all(isinstance(v, bool) for v in fields.values())


# DHF-REQ: genesis-wp-ha/requirement-13  DHF-TEST: genesis-wp-ha/ac-43
async def test_emulated_plant_matches_the_chosen_modules(hass, socket_enabled):
    entry = await _emulated_entry(hass, PROFILE_615, {"hot_water": True, "heating_circuit_2": False})
    assert entry.data[CONF_CAPABILITIES] == {"hot_water": True, "heating_circuit_2": False}

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert coordinator.thermia.capability_state("hot_water") == "present"
    assert coordinator.thermia.capability_state("heating_circuit_2") == "absent"

    registered = _unique_ids(hass, entry)
    hot_water = _register_ids(entry, gates("hot_water"))
    assert hot_water and hot_water <= registered
    assert not _register_ids(entry, gates("heating_circuit_2")) & registered
    assert await hass.config_entries.async_unload(entry.entry_id)


# DHF-REQ: genesis-wp-ha/requirement-13  DHF-TEST: genesis-wp-ha/ac-43
@pytest.mark.parametrize("name", _accepted_both_ways(get_profile(PROFILE_615)))
@pytest.mark.parametrize("on", [True, False])
async def test_every_offered_switch_decides_the_detected_state(hass, socket_enabled, name, on):
    entry = await _emulated_entry(hass, PROFILE_615, {name: on})
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    assert coordinator.thermia.capability_state(name) == ("present" if on else "absent")
    assert await hass.config_entries.async_unload(entry.entry_id)


# DHF-REQ: genesis-wp-ha/requirement-13  DHF-TEST: genesis-wp-ha/ac-43
async def test_entry_without_a_selection_runs_the_plain_profile(hass, socket_enabled):
    entry = await _emulated_entry(hass, PROFILE_615)
    assert CONF_CAPABILITIES not in entry.data
    assert await hass.config_entries.async_unload(entry.entry_id)

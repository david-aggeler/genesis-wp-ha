"""Entities follow the plant capabilities the library detects (requirement-12)."""

from __future__ import annotations

import pytest
from custom_components.genesis_wp.const import BINARY_SENSOR_TYPES
from custom_components.genesis_wp.const import COMMAND_COILS
from custom_components.genesis_wp.const import CONF_CAPABILITIES_SEEN
from custom_components.genesis_wp.const import DOMAIN
from custom_components.genesis_wp.const import SENSOR_TYPES
from genesis_wp import const as c
from genesis_wp.emulator import Emulator
from genesis_wp.emulator import get_profile
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import ABSENT_615 as ABSENT
from .harness import PROFILE_615
from .harness import PROFILES
from .harness import WPE_I_KIND
from .harness import gates
from .helpers import entry_data
from .helpers import setup_entry

def candidates() -> set[str]:
    """Every register the integration makes an entity of when no capability is absent."""
    fitted = {r for r, spec in c.REGISTERS.items() if spec[WPE_I_KIND]}
    settings = {r for r in fitted if c.REGISTERS[r][c.KEY_REG_TYPE] in ("holding", "coil")} - set(COMMAND_COILS)
    return (fitted & (set(SENSOR_TYPES) | set(BINARY_SENSOR_TYPES))) | settings


def unique_id(entry, register) -> str:
    spec = c.REGISTERS[register]
    return f"{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}"


def registered(hass, entry) -> set[str]:
    return {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}


async def restart(emu: Emulator, **options) -> Emulator:
    """Stop ``emu`` and serve its profile on the same port with other options: the plant changed."""
    await emu.stop()
    changed = Emulator(get_profile(PROFILE_615), port=emu.port, **options)
    await changed.start()
    return changed


# DHF-REQ: genesis-wp-ha/requirement-12  DHF-TEST: genesis-wp-ha/ac-39
async def test_absent_capabilities_get_no_entities(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    coordinator = hass.data[DOMAIN][entry.entry_id]
    states = {name: cap.state for name, cap in coordinator.thermia.capabilities.items()}
    assert sorted(n for n, s in states.items() if s == "absent") == sorted(ABSENT)

    gated = gates(*ABSENT)
    assert gated & candidates()  # the profile has entity candidates for absent modules
    assert not {unique_id(entry, r) for r in gated} & registered(hass, entry)


# DHF-REQ: genesis-wp-ha/requirement-12  DHF-TEST: genesis-wp-ha/ac-40
async def test_present_unknown_and_ungated_registers_keep_entities(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))

    kept = candidates() - gates(*ABSENT)
    assert kept & gates("heating_circuit_2", "buffer_tank", "ksm")  # present
    assert kept & gates("additional_heater", "smart_grid")  # unknown
    expected = {unique_id(entry, r) for r in kept} | {f"{entry.entry_id}_heatpump"}
    assert registered(hass, entry) == expected


# DHF-REQ: genesis-wp-ha/requirement-12  DHF-TEST: genesis-wp-ha/ac-41
async def test_capability_detected_later_adds_its_entities(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_entry(hass, emu)
    hot_water = {unique_id(entry, r) for r in gates("hot_water")}
    assert hot_water and not hot_water & registered(hass, entry)

    changed = await restart(emu, capabilities={"hot_water": True})  # hot water sensors fitted
    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        if not coordinator.last_update_success:  # the client reconnects on the next update
            await coordinator.async_refresh()
        assert coordinator.thermia.capabilities["hot_water"].state == "present"
        await hass.async_block_till_done()

        assert hot_water <= registered(hass, entry)
        assert hass.data[DOMAIN][entry.entry_id] is not coordinator  # reloaded, not restarted
    finally:
        await changed.stop()


# DHF-REQ: genesis-wp-ha/requirement-12  DHF-TEST: genesis-wp-ha/ac-41
async def test_capability_turning_absent_keeps_entities_until_next_setup(hass, start_emulator):
    emu = await start_emulator(PROFILE_615, capabilities={"hot_water": True})
    entry = await setup_entry(hass, emu)
    hot_water = {unique_id(entry, r) for r in gates("hot_water")}
    assert hot_water <= registered(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    changed = await restart(emu)  # hot water sensors not fitted
    try:
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            await coordinator.async_refresh()
        assert coordinator.thermia.capabilities["hot_water"].state == "absent"
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
        assert hot_water <= registered(hass, entry)
    finally:
        await changed.stop()


async def test_unread_evidence_is_not_a_capability_change(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_entry(hass, emu)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    address = c.REGISTERS[c.ATTR_INPUT_ROOM_TEMPERATURE_SENSOR][c.KEY_ADDRESS]
    emu.inject_fault("input_registers", address)  # room sensor unread: detection says unknown
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.thermia.capabilities["room_sensor"].state == "unknown"
    assert hass.data[DOMAIN][entry.entry_id] is coordinator


# DHF-REQ: genesis-wp-ha/requirement-12
@pytest.mark.parametrize("profile", PROFILES)
async def test_every_capability_evidence_register_is_read(hass, start_emulator, profile):
    """Each register a capability rule reads, running signals included, is subscribed (issue-8)."""
    entry = await setup_entry(hass, await start_emulator(profile))
    coordinator = hass.data[DOMAIN][entry.entry_id]

    not_read = [line for cap in coordinator.thermia.capabilities.values() for line in cap.evidence if "not read" in line]
    assert not_read == []


async def running_passive_cooling(start_emulator) -> Emulator:
    """A plant whose heating circuit 2 cools: passive cooling selected, outdoor above the season start."""
    emu = await start_emulator(PROFILE_615, dynamics=True, capabilities={"passive_cooling": True})
    emu.hold_outdoor(emu.heating.holding[303] + 1)
    emu.step()
    return emu


# DHF-REQ: genesis-wp-ha/requirement-12
async def test_module_seen_running_is_stored_in_the_entry(hass, start_emulator):
    """dinput 245 read as 1 makes passive cooling seen; the entry keeps it (issue-8)."""
    entry = await setup_entry(hass, await running_passive_cooling(start_emulator))
    coordinator = hass.data[DOMAIN][entry.entry_id]

    assert coordinator.thermia.capabilities["passive_cooling"].state == "present"
    assert entry.data[CONF_CAPABILITIES_SEEN] == ["passive_cooling"]


# DHF-REQ: genesis-wp-ha/requirement-12
async def test_module_seen_running_stays_present_after_a_reload(hass, start_emulator):
    """A winter setup still counts a summer observation: passive cooling present without an override."""
    emu = await start_emulator(PROFILE_615)  # captured values: dinput 245 = 0, coil 33 = 0
    entry = MockConfigEntry(domain=DOMAIN, data={**entry_data(emu), CONF_CAPABILITIES_SEEN: ["passive_cooling"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    capability = hass.data[DOMAIN][entry.entry_id].thermia.capabilities["passive_cooling"]
    assert capability.state == "present" and not capability.overridden
    kept = {unique_id(entry, r) for r in gates("passive_cooling") & candidates()}
    assert kept and kept <= registered(hass, entry)

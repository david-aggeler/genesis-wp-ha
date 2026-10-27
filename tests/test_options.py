"""Installed modules declared per entry, independent of switched state (requirement-14)."""

from __future__ import annotations

from custom_components.genesis_wp import capability_overrides
from custom_components.genesis_wp.config_flow import model_capabilities
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp import const as c
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .harness import PROFILE_615
from .harness import WPE_I_KIND
from .harness import gates
from .helpers import entry_data
from .test_capabilities import registered
from .test_capabilities import restart
from .test_capabilities import unique_id


async def setup_with_options(hass, emu, options) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(emu), options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def refresh(coordinator):
    await coordinator.async_refresh()
    if not coordinator.last_update_success:  # the client reconnects on the next update
        await coordinator.async_refresh()


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-44
async def test_installed_module_keeps_entities_while_switched_off(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {"passive_cooling": "present"})
    coordinator = hass.data[DOMAIN][entry.entry_id]
    passive = coordinator.thermia.capabilities["passive_cooling"]
    assert passive.state == "present" and passive.overridden
    assert "detected absent" in passive.evidence[0]  # coil 33 is off on the capture

    assert {unique_id(entry, r) for r in gates("passive_cooling")} <= registered(hass, entry)
    registry = er.async_get(hass)
    enable = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, unique_id(entry, c.ATTR_COIL_ENABLE_PASSIVE_COOLING)
    )
    # Settings entities start disabled (requirement-9); enable it as a user would.
    registry.async_update_entity(enable, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(enable).state == "off"


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-45
async def test_not_installed_module_gets_no_entities(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_with_options(hass, emu, {"smart_grid": "absent"})
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert "detected unknown" in coordinator.thermia.capabilities["smart_grid"].evidence[0]

    smart_grid = {unique_id(entry, r) for r in gates("smart_grid")}
    assert smart_grid
    assert not smart_grid & registered(hass, entry)


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-46
async def test_options_step_lists_modules_with_automatic_default(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    fields = {str(key): key for key in result["data_schema"].schema}
    expected = [name for name in model_capabilities(WPE_I_KIND)]
    assert list(fields) == expected
    assert "passive_cooling" in fields and "heating_circuit_3" not in fields
    for key, select in result["data_schema"].schema.items():
        assert key.default() == "automatic"
        assert select.config["options"] == ["automatic", "installed", "not_installed"]
    assert "passive_cooling: absent" in result["description_placeholders"]["detected"]

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {}


# DHF-REQ: genesis-wp-ha/requirement-14  DHF-TEST: genesis-wp-ha/ac-47
async def test_saving_module_options_applies_them(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {})
    entry_id = entry.entry_id
    passive = {unique_id(entry, r) for r in gates("passive_cooling")}
    assert not passive & registered(hass, entry)

    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"passive_cooling": "installed", "pool": "not_installed"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options == {"passive_cooling": "present", "pool": "absent"}
    assert hass.config_entries.async_get_entry(entry_id) is entry
    assert passive <= registered(hass, entry)

    # The stored choice is shown again, not reset to automatic.
    result = await hass.config_entries.options.async_init(entry_id)
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults["passive_cooling"] == "installed" and defaults["pool"] == "not_installed"
    assert "passive_cooling: present (set here)" in result["description_placeholders"]["detected"]


async def test_installed_module_does_not_reload_when_switched(hass, start_emulator):
    emu = await start_emulator(PROFILE_615)
    entry = await setup_with_options(hass, emu, {"passive_cooling": "present"})
    coordinator = hass.data[DOMAIN][entry.entry_id]

    changed = await restart(emu, capabilities={"passive_cooling": True})  # coil 33 on
    try:
        await refresh(coordinator)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
    finally:
        await changed.stop()


def test_unknown_module_options_are_dropped(caplog):
    options = {"passive_cooling": "present", "sauna": "present", "pool": "installed"}
    assert capability_overrides(options) == {"passive_cooling": "present"}
    assert "sauna" in caplog.text and "pool" in caplog.text

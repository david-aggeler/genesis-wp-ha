"""Entities grouped into one sub-device per plant category (requirement-15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custom_components.genesis_wp.const import CORE_SETTINGS
from custom_components.genesis_wp.const import DOMAIN
from genesis_wp import register_category
from genesis_wp import register_role
from genesis_wp import const as c
from genesis_wp.groups import CATEGORIES
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .harness import PROFILE_615
from .harness import PROFILES
from .helpers import setup_entry
from .test_options import setup_with_options

INTEGRATION = Path(__file__).parents[1] / "custom_components" / DOMAIN


def register_entities(hass, entry) -> dict[str, er.RegistryEntry]:
    """The entry's register entities by register name; the operating-state sensor is not one."""
    by_unique_id = {
        f"{entry.entry_id}_{spec[c.KEY_REG_TYPE]}_{spec[c.KEY_ADDRESS]}": name for name, spec in c.REGISTERS.items()
    }
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    return {by_unique_id[e.unique_id]: e for e in entities if e.unique_id in by_unique_id}


def sub_devices(hass, entry) -> dict[str, dr.ChildDeviceEntry]:
    """The child devices of the entry's heat pump, by category."""
    registry = dr.async_get(hass)
    main = registry.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    prefix = f"{entry.entry_id}_"
    devices = {}
    for device in dr.async_entries_for_parent_device(registry, main.id):
        (identifier,) = (i for d, i in device.identifiers if d == DOMAIN)
        devices[identifier.removeprefix(prefix)] = device
    return devices


# DHF-REQ: genesis-wp-ha/requirement-15  DHF-TEST: genesis-wp-ha/ac-48
@pytest.mark.parametrize("profile", PROFILES)
async def test_register_entities_sit_on_their_category_device(hass, start_emulator, profile):
    entry = await setup_entry(hass, await start_emulator(profile))
    devices = dr.async_get(hass)
    main = devices.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert main is not None and not isinstance(main, dr.ChildDeviceEntry)

    entities = register_entities(hass, entry)
    assert entities
    for name, entity in entities.items():
        device = devices.async_get(entity.device_id)
        assert (DOMAIN, f"{entry.entry_id}_{register_category(name)}") in device.identifiers, name
        assert device.parent_device_id == main.id, name

    heatpump = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_heatpump")
    assert er.async_get(hass).async_get(heatpump).device_id == main.id


# DHF-REQ: genesis-wp-ha/requirement-15  DHF-TEST: genesis-wp-ha/ac-49
async def test_no_sub_device_for_a_category_without_entities(hass, start_emulator):
    entry = await setup_with_options(hass, await start_emulator(PROFILE_615), {"pool": "absent"})

    categories = {register_category(name) for name in register_entities(hass, entry)}
    assert set(sub_devices(hass, entry)) == categories
    assert "pool" not in categories


# DHF-REQ: genesis-wp-ha/requirement-15  DHF-TEST: genesis-wp-ha/ac-50
@pytest.mark.parametrize("profile", PROFILES)
async def test_entity_category_follows_the_register_role(hass, start_emulator, profile):
    entry = await setup_entry(hass, await start_emulator(profile))

    roles = set()
    for name, entity in register_entities(hass, entry).items():
        role = register_role(name)
        roles.add(role)
        if role == "measurement" or name in CORE_SETTINGS:
            assert entity.entity_category is None, name
        else:
            assert entity.entity_category is EntityCategory.DIAGNOSTIC, name
    assert roles == {"measurement", "setting", "alarm"}


# DHF-REQ: genesis-wp-ha/requirement-15  DHF-TEST: genesis-wp-ha/ac-51
def test_every_category_has_a_device_name():
    for path in (INTEGRATION / "strings.json", INTEGRATION / "translations" / "en.json"):
        names = json.loads(path.read_text())["device"]
        assert set(names) == set(CATEGORIES), path
        assert all(names[category]["name"] for category in CATEGORIES)


# DHF-REQ: genesis-wp-ha/requirement-15  DHF-TEST: genesis-wp-ha/ac-51
async def test_sub_devices_show_their_translated_name(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    names = json.loads((INTEGRATION / "strings.json").read_text())["device"]
    devices = sub_devices(hass, entry)
    assert "additional_heating_circuits" in devices  # heating circuit 2
    for category, device in devices.items():
        assert device.name == names[category]["name"], category

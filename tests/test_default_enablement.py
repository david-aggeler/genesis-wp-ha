"""Fresh registrations expose every created entity without manual enabling."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from custom_components.genesis_wp.const import DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from .harness import PROFILES
from .harness import PROFILE_615
from .helpers import entry_data
from .helpers import setup_entry


# DHF-TEST: genesis-wp-ha/requirement-19
# DHF-TEST: genesis-wp-ha/ac-76
@pytest.mark.parametrize("profile", PROFILES)
async def test_every_fresh_entity_is_enabled_and_has_a_state(hass, start_emulator, profile):
    registry = er.async_get(hass)
    assert not registry.entities
    entry = await setup_entry(hass, await start_emulator(profile))
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert entries
    assert {entity.domain for entity in entries} == {"sensor", "binary_sensor"}
    for entity in entries:
        assert entity.disabled_by is None, entity.entity_id
        assert hass.states.get(entity.entity_id) is not None, entity.entity_id


# DHF-TEST: genesis-wp-ha/requirement-19 genesis-wp-ha/ac-182
async def test_setup_reenables_legacy_integration_disabled_entities(hass, start_emulator):
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(await start_emulator(PROFILE_615)))
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_input_9", config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    user = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_input_10", config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(legacy.entity_id).disabled_by is None
    assert hass.states.get(legacy.entity_id) is not None
    assert registry.async_get(user.entity_id).disabled_by == er.RegistryEntryDisabler.USER

    # Home Assistant batches registry-driven re-enablement into one delayed reload.
    with patch.object(hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload) as reload:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1))
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)


# DHF-TEST: genesis-wp-ha/requirement-35 genesis-wp-ha/ac-183
async def test_disabled_entities_diagnostic_tracks_registry_changes(hass, start_emulator):
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data(await start_emulator(PROFILE_615)))
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    disabled = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_input_9", config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    diagnostic, = (entity for entity in entities if entity.translation_key == "disabled_entities")
    assert diagnostic.entity_category == "diagnostic"
    assert diagnostic.disabled_by is None
    state = hass.states.get(diagnostic.entity_id)
    assert state.state == "1"
    assert state.attributes["genesis_wp_diagnostic"] == "disabled_entities"

    registry.async_update_entity(disabled.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id).state == "0"

    registry.async_update_entity(disabled.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id).state == "1"

    registry.async_remove(disabled.entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(diagnostic.entity_id).state == "0"

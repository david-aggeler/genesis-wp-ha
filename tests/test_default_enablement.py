"""Fresh registrations expose every created entity without manual enabling."""

import pytest
from custom_components.genesis_wp.const import DOMAIN
from homeassistant.helpers import entity_registry as er

from .harness import PROFILES
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

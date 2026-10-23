"""The integration never writes to the heat pump (requirement-5)."""

from __future__ import annotations

from pathlib import Path

from custom_components.genesis_wp import PLATFORMS
from custom_components.genesis_wp.const import DOMAIN
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .helpers import entry_data
from .helpers import form_input
from .helpers import setup_entry

PACKAGE = Path(__file__).parents[1] / "custom_components" / "genesis_wp"
WRITE_PLATFORMS = {"button", "climate", "number", "select", "switch", "text", "time", "valve", "water_heater"}


# DHF-REQ: genesis-wp-ha/requirement-5  DHF-TEST: genesis-wp-ha/ac-12
async def test_only_read_platforms_are_forwarded(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator())
    assert sorted(PLATFORMS) == ["binary_sensor", "sensor"]
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {e.domain for e in entities} == {"binary_sensor", "sensor"}
    assert not {p.stem for p in PACKAGE.glob("*.py")} & WRITE_PLATFORMS
    assert not (PACKAGE / "services.yaml").exists()


# DHF-REQ: genesis-wp-ha/requirement-5  DHF-TEST: genesis-wp-ha/ac-13
async def test_whole_lifecycle_sends_zero_writes(hass, start_emulator):
    emu = await start_emulator()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form_input(entry_data(emu)))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]

    coordinator = hass.data[DOMAIN][entry.entry_id]
    for _ in range(3):
        await coordinator.async_refresh()
        assert coordinator.last_update_success
    assert await hass.config_entries.async_unload(entry.entry_id)

    assert emu.requests, "the emulator saw no traffic; the test would prove nothing"
    assert emu.writes == []
    assert not {r.function_code for r in emu.requests} & {5, 6, 15, 16}


# DHF-REQ: genesis-wp-ha/requirement-5  DHF-TEST: genesis-wp-ha/ac-14
async def test_client_is_constructed_read_only(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator())
    assert hass.data[DOMAIN][entry.entry_id].thermia.read_only is True

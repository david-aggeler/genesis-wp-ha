"""Public delivery and rendering contract for the read-only overview card."""
import json
from pathlib import Path
from urllib.parse import urljoin

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.genesis_wp.cycles import MEAN_BANDS, RUN_BANDS

from .harness import PROFILE_615
from .helpers import setup_entry
from .node_harness import run_node_harness
from .test_devices import sub_devices

ROOT = Path(__file__).parents[1]
CARD = ROOT / "custom_components/genesis_wp/frontend/genesis-wp-overview-card.js"


# DHF-TEST: genesis-wp-ha/requirement-31 genesis-wp-ha/ac-147
async def test_overview_delivery(hass, hass_client, start_emulator):
    assert await async_setup_component(hass, "http", {})
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert any(url.endswith(f"/{CARD.name}") for url in urls)
    url = next(url for url in urls if url.endswith(f"/{CARD.name}"))
    client = await hass_client()
    for name in (CARD.name, "overview-bands.js", "register-card.js"):
        response = await client.get(urljoin(url, name))
        assert response.status == 200
        assert await response.read() == (CARD.parent / name).read_bytes()

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    devices = [
        *dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id),
        *sub_devices(hass, entry).values(),
    ]
    fixture = {
        "entry": entry.entry_id,
        "entities": {e.entity_id: {"device_id": e.device_id, "disabled_by": e.disabled_by} for e in entities},
        "devices": {d.id: {"identifiers": list(d.identifiers)} for d in devices},
        "states": {
            e.entity_id: {"state": state.state, "attributes": dict(state.attributes)}
            for e in entities if (state := hass.states.get(e.entity_id)) is not None
        },
        "bands": {"RUN_BANDS": RUN_BANDS, "MEAN_BANDS": MEAN_BANDS},
    }
    run_node_harness(ROOT / "tests/frontend/overview_card.mjs", CARD, stdin=json.dumps(fixture))

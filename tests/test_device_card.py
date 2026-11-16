"""Device card public delivery and emulator-backed rendering contract."""
import json
from pathlib import Path
import shutil
import subprocess
from importlib.util import find_spec

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .helpers import setup_entry
from .harness import PROFILE_615
from .test_devices import register_entities, sub_devices

ROOT = Path(__file__).parents[1]
CARD = ROOT / "custom_components/genesis_wp/frontend/genesis-wp-device-card.js"
URL = "/genesis_wp/genesis-wp-device-card.js"


def run_render(fixture):
    package = find_spec("nodejs_wheel")
    node = shutil.which("node", path=str(Path(package.origin).parent / "bin")) if package else shutil.which("node")
    assert node, "Node.js is required"
    result = subprocess.run([node, str(ROOT / "tests/frontend/device_card.mjs"), str(CARD)],
                            input=json.dumps(fixture), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


# DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-65
async def test_device_card_delivery(hass, hass_client, start_emulator):
    assert await async_setup_component(hass, "http", {})
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
    await setup_entry(hass, await start_emulator(PROFILE_615))
    assert URL in hass.data[DATA_EXTRA_MODULE_URL].urls
    response = await (await hass_client()).get(URL)
    assert response.status == 200
    assert await response.read() == CARD.read_bytes()
    CARD.read_bytes().decode("ascii")
    helper = await (await hass_client()).get("/genesis_wp/register-card.js")
    assert helper.status == 200
    assert await helper.read() == (CARD.parent / "register-card.js").read_bytes()


# DHF-TEST: genesis-wp-ha/requirement-18 genesis-wp-ha/ac-67
async def test_register_anchors_and_render(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(
        PROFILE_615, capabilities={name: True for name in (
            "hot_water", "pool", "active_cooling", "passive_cooling", "electric_meter"
        )},
    ))
    assert {"hot_water", "cooling", "pool", "ksm", "electric_meter_and_energy", "controller"} <= set(sub_devices(hass, entry))
    registry = er.async_get(hass)
    for entity in register_entities(hass, entry).values():
        if entity.disabled_by:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entities = register_entities(hass, entry)
    assert entities
    for entity in entities.values():
        state = hass.states.get(entity.entity_id)
        assert state is not None
        assert state.attributes.get("register") == entity.unique_id.removeprefix(f"{entry.entry_id}_")
        component = hass.data[entity.domain].get_entity(entity.entity_id)
        assert "register" in component._unrecorded_attributes
    fixture = {
        "entry": entry.entry_id,
        "states": {e.entity_id: {"state": hass.states.get(e.entity_id).state,
                                  "attributes": dict(hass.states.get(e.entity_id).attributes)} for e in entities.values()},
        "entities": {e.entity_id: {"device_id": e.device_id, "disabled_by": e.disabled_by} for e in entities.values()},
        "devices": {d.id: {"identifiers": list(d.identifiers), "name": d.name} for d in [*dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id), *sub_devices(hass, entry).values()]},
    }
    run_render(fixture)
    package = find_spec("nodejs_wheel")
    node = shutil.which("node", path=str(Path(package.origin).parent / "bin")) if package else shutil.which("node")
    result = subprocess.run([node, str(ROOT / "tests/frontend/panel.mjs"),
                             str(CARD.parent / "genesis-wp-panel.js")],
                            input=json.dumps(fixture), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

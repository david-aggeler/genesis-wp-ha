"""Input 43 is the controller's mixer signal, not a valve position (issue-25)."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib.util import find_spec
from pathlib import Path

from custom_components.genesis_wp.const import DOMAIN
from genesis_wp import const as c
from homeassistant.helpers import entity_registry as er

from .harness import PROFILE_615
from .helpers import setup_entry
from .test_settings import _unique_id

LABELS = Path(__file__).parents[1] / "custom_components/genesis_wp/frontend/labels.js"


def _node():
    package = find_spec("nodejs_wheel")
    node = shutil.which("node", path=str(Path(package.origin).parent / "bin")) if package else shutil.which("node")
    assert node, "Node.js is required"
    return node


# DHF-TEST: genesis-wp-ha/requirement-17
async def test_input_43_entity_is_named_mixer_signal(hass, start_emulator):
    entry = await setup_entry(hass, await start_emulator(PROFILE_615))
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, _unique_id(entry, c.ATTR_INPUT_MIX_VALVE_1_POSITION))
    assert entity_id
    name = hass.states.get(entity_id).attributes["friendly_name"]
    assert name.endswith("Mixer Signal")
    assert "position" not in name.lower()


# DHF-TEST: genesis-wp-ha/requirement-17
def test_input_43_panel_label_is_mixer_signal():
    script = (
        f"const m = await import({json.dumps(LABELS.as_uri())});"
        "console.log(JSON.stringify(['en','de'].map(l => m.shortLabel({language: l}, 'input_43'))));"
    )
    result = subprocess.run([_node(), "--input-type=module", "-e", script],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["Mixer signal", "Mischer-Stellsignal"]

"""The genesis-wp library is the only Modbus path, pinned to a commit (requirement-3)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).parents[1] / "custom_components" / "genesis_wp"
# hassfest rejects spaces, so the PEP 508 direct reference is written without them.
PIN = re.compile(r"^genesis-wp@git\+https://github\.com/david-aggeler/genesis-wp@[0-9a-f]{40}$")
FORBIDDEN = {"pymodbus", "pyModbusTCP", "pythermiagenesis", "modbus_connection"}


# DHF-REQ: genesis-wp-ha/requirement-3  DHF-TEST: genesis-wp-ha/ac-5
def test_manifest_pins_genesis_wp_to_a_full_commit():
    requirements = json.loads((PACKAGE / "manifest.json").read_text())["requirements"]
    assert len(requirements) == 1
    assert PIN.match(requirements[0]), requirements[0]


# DHF-REQ: genesis-wp-ha/requirement-3  DHF-TEST: genesis-wp-ha/ac-6
def test_no_other_modbus_client_is_imported():
    offenders = []
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            else:
                continue
            offenders += [f"{path.name}: {root}" for root in roots if root in FORBIDDEN]
    assert offenders == []


def test_manifest_matches_requirements_test_pin():
    manifest_pin = json.loads((PACKAGE / "manifest.json").read_text())["requirements"][0]
    sha = manifest_pin.rsplit("@", 1)[1]
    assert sha in (PACKAGE.parents[1] / "requirements_test.txt").read_text()


# DHF-REQ: genesis-wp-ha/requirement-4  DHF-TEST: genesis-wp-ha/ac-32
def test_integration_title_has_no_placeholder():
    files = [PACKAGE / "strings.json", *sorted((PACKAGE / "translations").glob("*.json"))]
    for path in files:
        title = json.loads(path.read_text())["title"]
        assert title and "{" not in title, f"{path.name}: {title}"  # HA formats the title with no context

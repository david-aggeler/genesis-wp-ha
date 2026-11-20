"""Shared runner for frontend Node.js test harnesses."""

import shutil
import subprocess
from importlib.util import find_spec
from pathlib import Path


# DHF-REQ: genesis-wp-ha/requirement-1
def run_node_harness(script, *args, stdin=None):
    """Run a Node.js harness and return stdout preceding the completion marker."""
    package = find_spec("nodejs_wheel")
    node = None
    if package is not None and package.origin is not None:
        node = shutil.which("node", path=str(Path(package.origin).parent / "bin"))
    node = node or shutil.which("node")
    assert node, "Node.js is required; install requirements_test.txt"

    result = subprocess.run(
        [node, str(script), *(str(arg) for arg in args)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )
    diagnostics = f"{script}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, f"Node.js exited with {result.returncode}\n{diagnostics}"
    lines = result.stdout.splitlines(keepends=True)
    assert lines and lines[-1].removesuffix("\n") == "HARNESS-COMPLETE", (
        f"Expected HARNESS-COMPLETE as the final stdout line\n{diagnostics}"
    )
    return "".join(lines[:-1])

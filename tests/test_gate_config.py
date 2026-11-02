"""The committed gate tables run the suite from any unit worktree (issue-11)."""

# DHF-REQ: genesis-wp-ha/requirement-1
# DHF-TEST: genesis-wp-ha/ac-57

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((REPO / "openbrain-client.yaml").read_text(encoding="utf-8"))
WRAPPER = ["bash", "scripts/gate_python.sh"]
RUNGS = ("prose", "static", "unit", "integration", "system")


def test_every_rung_is_declared() -> None:
    gates = CONFIG["transition_gates"]
    assert set(gates) == set(RUNGS)
    for rung in RUNGS:
        assert set(gates[rung]) == {"in_session", "runner_owned"}


def test_python_stages_run_through_the_venv_wrapper() -> None:
    for rung in RUNGS:
        for command in CONFIG["transition_gates"][rung]["in_session"]:
            assert command[:2] == WRAPPER, f"{rung}: {command}"


def test_test_rungs_run_pytest() -> None:
    for rung in ("unit", "integration", "system"):
        commands = CONFIG["transition_gates"][rung]["in_session"]
        assert WRAPPER + ["-m", "pytest"] in commands, rung


# DHF-TEST: genesis-wp-ha/ac-62
def test_runner_owned_stages_prove_every_rung_above_prose() -> None:
    """Merge admission needs a tree the runner itself proved green (issue-14)."""
    gates = CONFIG["transition_gates"]
    assert gates["prose"]["runner_owned"] == []
    for rung in RUNGS[1:]:
        stages = gates[rung]["runner_owned"]
        assert stages, rung
        assert all(command[:2] == WRAPPER for command in stages), rung
    for rung in ("unit", "integration", "system"):
        assert any(command[2:4] == ["-m", "pytest"] for command in gates[rung]["runner_owned"]), rung


def test_stages_are_cumulative() -> None:
    """openbrain-client rejects a rung that drops a stage of the rung below (issue-14)."""
    gates = CONFIG["transition_gates"]
    for lower, upper in zip(RUNGS, RUNGS[1:]):
        for kind in ("in_session", "runner_owned"):
            missing = [c for c in gates[lower][kind] if c not in gates[upper][kind]]
            assert not missing, f"{upper}.{kind} lacks {lower}.{kind} stages {missing}"


# DHF-TEST: genesis-wp-ha/ac-58
def test_merge_command_lands_on_main() -> None:
    """openbrain-client run-queue requires the trunk named main (issue-12)."""
    assert CONFIG["merge_command"] == ["bash", "scripts/merge_unit.sh"]
    script = (REPO / "scripts" / "merge_unit.sh").read_text(encoding="utf-8")
    assert "\nMAIN=main\n" in script


def test_wrapper_runs_the_repo_venv() -> None:
    """From this checkout (primary or worktree) the wrapper runs the venv's interpreter."""
    result = subprocess.run(
        [*WRAPPER, "-c", "import sys; print(sys.prefix)"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(result.stdout.strip()) == Path(sys.prefix)


def test_wrapper_passes_the_exit_code_through() -> None:
    result = subprocess.run(
        [*WRAPPER, "-c", "raise SystemExit(3)"], cwd=REPO, check=False
    )
    assert result.returncode == 3

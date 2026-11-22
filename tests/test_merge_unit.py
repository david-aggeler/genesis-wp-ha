"""Exercise the merge entry point in disposable repositories with a local origin."""

import json
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "merge_unit.sh"
MANIFEST = "custom_components/genesis_wp/manifest.json"
ORIGINAL = b'{\n  "domain": "genesis_wp",\n  "version" : "0.1.0"\n}\n'


def git(repo, *args):
    return subprocess.check_output(("git", *args), cwd=repo, text=True).strip()


@pytest.fixture
def merge_repo(tmp_path):
    repo = tmp_path / "repo"
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    git(tmp_path, "init", "-b", "main", str(repo))
    git(repo, "config", "user.name", "Merge Test")
    git(repo, "config", "user.email", "merge@example.invalid")
    git(repo, "remote", "add", "origin", str(origin))
    manifest = repo / MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(ORIGINAL)
    git(repo, "add", MANIFEST)
    git(repo, "commit", "-m", "Initial manifest")
    git(repo, "branch", "cr-1")
    git(repo, "commit", "--allow-empty", "-m", "Advance main")
    git(repo, "push", "-u", "origin", "main")
    return repo, origin


def prepare_unit(repo, version):
    git(repo, "switch", "cr-1")
    if version is not None:
        (repo / "VERSION").write_text(version)
        git(repo, "add", "VERSION")
    git(repo, "commit", "--allow-empty", "-m", "Implement unit")
    unit = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "main")
    return unit


def merge(repo):
    return subprocess.run(
        ("bash", str(SCRIPT), "cr-1"), cwd=repo, capture_output=True, text=True
    )


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_stamps_its_own_build_number(merge_repo):
    repo, origin = merge_repo
    unit = prepare_unit(repo, "0.4.0\n")
    before = git(repo, "rev-parse", "HEAD")

    result = merge(repo)

    assert result.returncode == 0, result.stderr
    landed = git(repo, "rev-parse", "HEAD")
    assert f"code_change_ref={landed}" in result.stdout.splitlines()
    assert git(repo, "rev-parse", "HEAD^1", "HEAD^2").splitlines() == [before, unit]
    assert git(repo, "rev-list", "--count", "HEAD") == "4"
    assert json.loads(git(repo, "show", f"HEAD:{MANIFEST}"))["version"] == "0.4.0.4"
    assert (repo / MANIFEST).read_bytes() == ORIGINAL.replace(b"0.1.0", b"0.4.0.4")
    assert git(origin, "rev-parse", "main") == landed


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-180
@pytest.mark.parametrize("version", [None, "", "0.4\n", "0.4.0\n\n", "0.4.0\0\n"])
def test_merge_refuses_invalid_version(merge_repo, version):
    repo, origin = merge_repo
    prepare_unit(repo, version)
    before = git(repo, "rev-parse", "HEAD")

    result = merge(repo)

    assert result.returncode != 0
    assert "VERSION" in result.stderr
    assert git(repo, "rev-parse", "main") == before
    assert git(origin, "rev-parse", "main") == before
    assert git(repo, "status", "--porcelain") == ""

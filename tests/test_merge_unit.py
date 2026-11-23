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
@pytest.mark.parametrize("version", [None, "", "0.4.0\r\n", "0.4\n", "0.4.0\n\n", "0.4.0\0\n"])
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


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
@pytest.mark.parametrize("content_conflict", [False, True])
def test_merge_manifest_conflict(merge_repo, content_conflict):
    repo, origin = merge_repo
    prepare_unit(repo, "0.4.0\n")
    for branch, version, domain in (
        ("main", b"0.4.0.3", b"main"),
        ("cr-1", b"0.4.0.4", b"unit"),
    ):
        git(repo, "switch", branch)
        contents = ORIGINAL.replace(b"0.1.0", version)
        if content_conflict:
            contents = contents.replace(b"genesis_wp", domain)
        (repo / MANIFEST).write_bytes(contents)
        git(repo, "commit", "-am", "Update manifest")
    git(repo, "switch", "main")
    before = git(repo, "rev-parse", "HEAD")
    remote_before = git(origin, "rev-parse", "main")

    result = merge(repo)

    if content_conflict:
        assert result.returncode != 0
        assert git(repo, "rev-parse", "HEAD") == before
        assert git(origin, "rev-parse", "main") == remote_before
    else:
        assert result.returncode == 0, result.stderr
        assert (repo / MANIFEST).read_bytes() == ORIGINAL.replace(b"0.1.0", b"0.4.0.6")
    assert git(repo, "status", "--porcelain") == ""


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-180
@pytest.mark.parametrize("path", ["VERSION", MANIFEST])
def test_merge_rejects_untracked_stamp_input(merge_repo, path):
    repo, origin = merge_repo
    prepare_unit(repo, None if path == "VERSION" else "0.4.0\n")
    if path == MANIFEST:
        for branch in ("main", "cr-1"):
            git(repo, "switch", branch)
            git(repo, "rm", MANIFEST)
            git(repo, "commit", "-m", "Remove manifest")
        git(repo, "switch", "main")
    untracked = repo / path
    untracked.parent.mkdir(parents=True, exist_ok=True)
    original = b"0.4.0\n" if path == "VERSION" else ORIGINAL
    untracked.write_bytes(original)
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\ntouch .git/hook-ran\n")
    hook.chmod(0o755)
    before = git(repo, "rev-parse", "HEAD")
    remote_before = git(origin, "rev-parse", "main")

    result = merge(repo)

    assert result.returncode != 0
    assert path in result.stderr
    assert not (repo / ".git/hook-ran").exists()
    assert untracked.read_bytes() == original
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(origin, "rev-parse", "main") == remote_before


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_rolls_back_incorrect_committed_stamp(merge_repo):
    repo, origin = merge_repo
    prepare_unit(repo, "0.4.0\n")
    before = git(repo, "rev-parse", "HEAD")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text(
        f"#!/bin/sh\nsed -i 's/0.4.0.4/0.4.0.999/' {MANIFEST}\ngit add {MANIFEST}\n"
    )
    hook.chmod(0o755)

    result = merge(repo)

    assert result.returncode != 0
    assert "does not match VERSION and its commit count" in result.stderr
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(origin, "rev-parse", "main") == before
    assert git(repo, "status", "--porcelain") == ""


def refused_unchanged(repo, origin, result, before):
    assert result.returncode != 0, result.stdout
    assert git(repo, "rev-parse", "main") == before
    assert git(origin, "rev-parse", "main") == before


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_honors_rejecting_pre_merge_commit_hook(merge_repo):
    repo, origin = merge_repo
    prepare_unit(repo, "0.4.0\n")
    before = git(repo, "rev-parse", "HEAD")
    hook = repo / ".git/hooks/pre-merge-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    result = merge(repo)

    refused_unchanged(repo, origin, result, before)
    assert "pre-merge-commit" in result.stderr
    assert git(repo, "status", "--porcelain") == ""


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
@pytest.mark.parametrize(
    "manifest",
    [
        b'{\n  "domain": "genesis_wp",\n  "version": "0.\\u0031.0"\n}\n',
        b'{"options": {"version": "keep"}, "version" :"0.1.0", "x": ["version"]}',
    ],
    ids=["escaped", "nested"],
)
def test_merge_replaces_only_top_level_version(merge_repo, manifest):
    repo, origin = merge_repo
    (repo / MANIFEST).write_bytes(manifest)
    git(repo, "commit", "-am", "Manifest variant")
    git(repo, "push", "-q", "origin", "main")
    prepare_unit(repo, "0.4.0\n")
    old = b'"0.\\u0031.0"' if b"\\u" in manifest else b'"0.1.0"'

    result = merge(repo)

    assert result.returncode == 0, result.stderr
    expected = manifest.replace(old, b'"0.4.0.5"')
    assert git(repo, "show", f"HEAD:{MANIFEST}").encode() == expected.rstrip(b"\n")
    assert (repo / MANIFEST).read_bytes() == expected


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_rolls_back_symlinked_manifest(merge_repo):
    repo, origin = merge_repo
    prepare_unit(repo, "0.4.0\n")
    before = git(repo, "rev-parse", "HEAD")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text(
        f"#!/bin/sh\nrm {MANIFEST}\nln -s '{{\"version\": \"0.4.0.4\"}}' {MANIFEST}\n"
        f"git add {MANIFEST}\n"
    )
    hook.chmod(0o755)

    result = merge(repo)

    refused_unchanged(repo, origin, result, before)
    assert "regular file" in result.stderr


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_refuses_assume_unchanged_edits(merge_repo):
    repo, origin = merge_repo
    prepare_unit(repo, "0.4.0\n")
    before = git(repo, "rev-parse", "HEAD")
    git(repo, "update-index", "--assume-unchanged", MANIFEST)
    edited = ORIGINAL.replace(b"genesis_wp", b"local_edit")
    (repo / MANIFEST).write_bytes(edited)

    result = merge(repo)

    refused_unchanged(repo, origin, result, before)
    assert "assume-unchanged" in result.stderr
    assert (repo / MANIFEST).read_bytes() == edited


# DHF-TEST: genesis-wp-ha/requirement-32
# DHF-TEST: genesis-wp-ha/ac-179
def test_merge_survives_unit_that_replaces_merge_implementation(merge_repo):
    repo, origin = merge_repo
    scripts = repo / "scripts"
    scripts.mkdir()
    for name in ("merge_unit.sh", "manifest_version.py"):
        (scripts / name).write_bytes((SCRIPT.parent / name).read_bytes())
    git(repo, "add", "scripts")
    git(repo, "commit", "-m", "Add merge implementation")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "branch", "-f", "cr-1", "main")
    git(repo, "switch", "cr-1")
    git(repo, "rm", "-q", "scripts/manifest_version.py")
    (scripts / "merge_unit.sh").write_text("# replaced\n" * 2000 + "exit 7\n")
    (repo / "VERSION").write_text("0.4.0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Replace merge implementation")
    git(repo, "switch", "main")

    result = subprocess.run(
        ("bash", "scripts/merge_unit.sh", "cr-1"), cwd=repo, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(git(repo, "show", f"HEAD:{MANIFEST}"))["version"] == "0.4.0.5"
    assert git(origin, "rev-parse", "main") == git(repo, "rev-parse", "HEAD")

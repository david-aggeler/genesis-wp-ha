"""Stamp the pending merge index and verify the version in the resulting commit."""

import json
from json.decoder import scanstring
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

REGULAR_MODES = {b"100644", b"100755"}
WHITESPACE = re.compile(r"[ \t\n\r]*")


def parse_version(data: bytes) -> str:
    """Read three ASCII numeric components with an optional final LF."""
    version = data.removesuffix(b"\n")
    if not re.fullmatch(rb"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("VERSION must contain MAJOR.MINOR.PATCH")
    return version.decode("ascii")


def git(*args, data=None):
    return subprocess.run(
        ("git", *args), input=data, stdout=subprocess.PIPE, check=True
    ).stdout


def index_entries(path):
    entries = {}
    for line in git("ls-files", "--stage", "-z", "--", path).split(b"\0"):
        metadata, _, name = line.partition(b"\t")
        if name == path.encode():
            mode, blob, stage = metadata.split()
            entries[int(stage)] = mode, blob
    return entries


def index_file(path, entry):
    if entry is None or entry[0] not in REGULAR_MODES:
        raise ValueError(f"{path}: expected a tracked regular file in the merge index")
    return git("cat-file", "blob", entry[1])


def version_span(path, text):
    """Locate the top-level "version" value of a JSON object as a (start, end) span."""
    json.loads(text)  # full validation; the scan below only walks the top level
    decoder = json.JSONDecoder()
    index = WHITESPACE.match(text).end()
    if text[index : index + 1] != "{":
        raise ValueError(f"{path}: expected a JSON object")
    index = WHITESPACE.match(text, index + 1).end()
    span = None
    while text[index : index + 1] != "}":
        key, index = scanstring(text, index + 1)
        index = WHITESPACE.match(text, index).end() + 1  # past ':'
        start = WHITESPACE.match(text, index).end()
        value, index = decoder.raw_decode(text, start)
        if key == "version":
            if span is not None or not isinstance(value, str):
                raise ValueError(f"{path}: expected one top-level string version")
            span = start, index
        index = WHITESPACE.match(text, index).end()
        if text[index : index + 1] == ",":
            index = WHITESPACE.match(text, index + 1).end()
    if span is None:
        raise ValueError(f"{path}: expected a top-level manifest version")
    return span


def replace_version(path, original, stamp):
    # Replace only the bytes of the top-level value; nested "version" keys and
    # escape sequences elsewhere stay byte-identical.
    text = original.decode("utf-8")
    start, end = version_span(path, text)
    updated = (text[:start] + json.dumps(stamp) + text[end:]).encode("utf-8")
    if json.loads(updated).get("version") != stamp:
        raise ValueError(f"{path}: expected one manifest version to stamp")
    return updated


def resolve_manifest(path, entries, stamp):
    if set(entries) != {1, 2, 3} or len({mode for mode, _ in entries.values()}) != 1:
        raise ValueError(f"{path}: expected a content-only manifest conflict")
    # Re-run the three-way merge with a common generated version. Git still
    # rejects conflicts in the rest of the manifest.
    with TemporaryDirectory() as directory:
        files = []
        for stage in (2, 1, 3):  # ours, base, theirs
            file = Path(directory) / str(stage)
            file.write_bytes(replace_version(path, index_file(path, entries[stage]), stamp))
            files.append(file)
        merged = git("merge-file", "-p", *files)
    return replace_version(path, merged, stamp)


def stamp_index(path, build, merge_conflicted):
    version = parse_version(index_file("VERSION", index_entries("VERSION").get(0)))
    stamp = f"{version}.{build}"
    entries = index_entries(path)
    if merge_conflicted:
        conflicts = git("diff", "--name-only", "--diff-filter=U", "-z")
        if conflicts != path.encode() + b"\0":
            raise ValueError(f"{path}: merge has unresolved conflicts outside the manifest")
        updated = resolve_manifest(path, entries, stamp)
        mode = entries[2][0]
    else:
        entry = entries.get(0)
        updated = replace_version(path, index_file(path, entry), stamp)
        mode = entry[0]

    blob = git("hash-object", "-w", "--stdin", data=updated).strip()
    git("update-index", "--cacheinfo", mode, blob, path)
    git("checkout-index", "--force", "-u", "--", path)


def verify_commit(path, commit):
    version_entry = git("ls-tree", commit, "--", "VERSION").split()
    if not version_entry or version_entry[0] not in REGULAR_MODES:
        raise ValueError("VERSION: expected a committed regular file")
    version = parse_version(git("show", f"{commit}:VERSION"))
    build = git("rev-list", "--count", commit).strip().decode("ascii")
    manifest_entry = git("ls-tree", commit, "--", path).split()
    if not manifest_entry or manifest_entry[0] not in REGULAR_MODES:
        raise ValueError(f"{path}: expected a committed regular file")
    manifest = json.loads(git("show", f"{commit}:{path}"))
    if manifest.get("version") != f"{version}.{build}":
        raise ValueError(f"{path}: incorrect committed build stamp")


if __name__ == "__main__":
    action, path, value, *flags = sys.argv[1:]
    try:
        if action == "stamp":
            stamp_index(path, value, flags == ["conflicted"])
        elif action == "verify":
            verify_commit(path, value)
        else:
            raise ValueError(f"Unknown manifest version action: {action}")
    except (ValueError, UnicodeError, AttributeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))

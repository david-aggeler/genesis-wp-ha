#!/usr/bin/env bash
# Run the repo venv's Python with the given arguments, from the primary checkout or any
# worktree under worktrees/. The venv lives only in the primary checkout (CLAUDE.md, Tests),
# found beside the git common dir. Never falls back to the host python3: HA 2026.10.0 needs
# Python 3.14 and the host has 3.13.
set -euo pipefail

common=$(git rev-parse --path-format=absolute --git-common-dir)
python="$(dirname "$common")/.venv/bin/python"
if [[ ! -x $python ]]; then
	printf 'gate_python: %s missing; create it with: uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -r requirements_test.txt\n' "$python" >&2
	exit 1
fi
exec "$python" "$@"

# CLAUDE.md

Rules for coding agents in this repo. Short and blunt on purpose.
`AGENTS.md` is a symlink to this file — one source, every agent.

## ⚠️ The real heat pump is read-only — never write to it

**This is the single most important operational rule.** The integration talks to a production heating plant: the owner's Stiebel Eltron WPE-I 07.1 Plus H 400, which has an internal WPM-G (Thermia Genesis) controller and serves Modbus TCP on port 502, unit 1. A wrong read is a bug. A wrong write can damage a borehole or a compressor.

- **The integration never sends Modbus function codes 5, 6, 15 or 16 to the plant**: not from tests, not from a config flow, not from a service call, not "just once to check".
- Writable entities (switch, number, select, climate setpoints) exist **only behind an explicit opt-in**, off by default, and are exercised **only against `genesis-wp-emulator`**.
- The device host name is topology: keep it out of committed files, records and logs. Tests use loopback emulator addresses.
- The test suite never needs the real device. If a test seems to need it, the emulator is missing a feature; ask wpe-1 to extend it in the genesis-wp repo.

## Conceptional

- **Prefer long term benefits over short term win.**
- **Never harm the plant.** Read-only is the default at every layer: library, emulator profile, and this integration.
- **The library owns the register map.** Names, scales, units, sentinels and enums come from genesis-wp. The integration maps library values to entities; it never decodes registers itself.
- **Emulator first.** Every behavior the integration depends on must be reproducible against the emulator before it is trusted in Home Assistant.
- **Observability is key. No feedback loop without logs.**
- **Prefer strict data handling.** A not-fitted or unavailable value is `None` → entity unavailable/unknown, never a coerced number.
- **Prefer git operations over raw operations.**
- **Expect parallel work to be ongoing.** Work on branches, or in git worktrees under `.claude/worktrees/` where feasible. Simple markdown edits are probably not worth a worktree.

## Language

- **Use concise language.**
- **Use software engineering language.** Name things with the vocabulary of the discipline — interface, boundary, contract, coupling, invariant, call path. Do not reach into another domain for a metaphor when a standard term exists.
- **Use US English spelling in all written output** — code, comments, commit messages, records, chat. Some gold schema enums accept only US spelling (`close_reason: "canceled"` passes, `"cancelled"` is rejected with `enum_mismatch`).
- Entity names and translations follow Home Assistant conventions. German strings belong in `translations/de.json`, not in identifiers.

### Words to avoid

| Avoid | Use instead |
|---|---|
| seam | boundary |

### Abbreviations

Use these only as chat shorthand. **Records always carry the full name.**

| Abbreviation | Definition |
|---|---|
| obc | openbrain-client |
| HA | Home Assistant |
| HACS | Home Assistant Community Store |
| CR | change_request |
| FC | Modbus function code |
| WPM-G | Stiebel's controller in the WPE-I (Thermia Genesis lineage) |

## What genesis-wp-ha is

- The Home Assistant custom integration, openbrain product **genesis-wp-ha**: domain `genesis_wp`, HACS layout (`custom_components/<domain>/`, `hacs.json`), one integration per repo.
- **genesis-wp is a separate product** (library + emulator, repo `/container/genesis-wp`, session wpe-1). This repo consumes it through `manifest.json` `requirements` and keeps **no library code here**. Register, decoding, transport or emulator fixes go to genesis-wp.
- Until genesis-wp is on PyPI, `manifest.json` pins a git direct reference to a library commit: `genesis-wp @ git+https://github.com/david-aggeler/genesis-wp@<sha>`. A PyPI release comes before wider HACS distribution or an HA core submission.
- A fork of [ulrichwi/thermiagenesis](https://github.com/ulrichwi/thermiagenesis), whose code is identical to [CJNE/thermiagenesis](https://github.com/CJNE/thermiagenesis) master `b55fa58`. Remotes: `origin` (ours), `upstream` (ulrichwi), `cjne`.
- **Not** in charge of rollout. The homelab product owns deployment to its Home Assistant and homelab exploration-8. When a stage lands, tell homelab.

Direction and principles live in gold, product genesis-wp-ha (no vision filed yet). The library's direction is genesis-wp vision-1, cited in text only.

## License and third-party material

- **MIT, same as the source.** Keep `Copyright (c) 2021 cjne` in `LICENSE` verbatim. Our notice goes alongside it and never replaces it.
- New dependencies must be MIT-compatible. Check the license before adding one.
- **Never commit manufacturer documents**: no PDFs, manuals, screenshots or display photos.
- **Keep the device serial number out of** the repo, fixtures, diagnostics output, records and logs.

## Operational conventions

- Sessions are driven remotely (Claude Desktop → `/rc` → `claude`, kept alive by `zx`). A permission prompt may go unanswered — don't park work behind one.
- Batch related git operations with `&&` so they land atomically.
- Prefer a reversible move (new commit, branch, stash) over a destructive in-place edit.
- **Outward-facing actions need the owner's OK every time.** That covers `git push`, GitHub releases, HACS submission, and upstream issues, PRs or comments (ulrichwi/thermiagenesis, CJNE/thermiagenesis).

### Access model

| Path | Reaches | Use for |
|---|---|---|
| `mcp__gold__*` | gold (openbrain PROD) | **all** genesis-wp record authoring |
| `mcp__copper__*` | copper (openbrain DEV) | integration diagnostics only — never author genesis-wp records there |
| local Python / pytest | DEV VM | build, tests, emulator |
| homelab's Home Assistant | homelab-2-wpe | owner-approved read-only system check only |
| real heat pump | — | never directly from this repo |

### Standup

Ask cross-session questions of `wpe-ha-standup`. Peers: wpe-1 (library and emulator, `/container/genesis-wp`), homelab-2-wpe (homelab side: deployment, HA instance, exploration-8).

### Scratchpad

Put working files (drafts, one-off scripts, intermediate outputs the user may want to read) in `scratchpad/` at the repo root. It is gitignored and survives the session. Session-private tmp dirs are fine only for files the user never needs to open.

## Skill trees — know which one you're editing

- **Local skills** under `.claude/skills/` that have no `x-openbrain-*` frontmatter are repo files. Edit them directly, under a CR, and add a `!` exception to `.gitignore` so they get tracked.
- **Materialized skills** carry `x-openbrain-*` in their `SKILL.md` frontmatter. Never edit them here. They are authored and released in gold, then pulled with `openbrain-client init-skills`. `.gitignore` ignores `.claude/skills/`, `.claude/agents/` and `.claude/materialization.json` as whole directories for that reason.
- `.claude/agents/<slug>.md` is derived from the gold skill's agent block by the same `init-skills` run. Never hand-edit it.

## genesis-wp-ha Development Documents — Use Gold

Every HELIX01 record type for this product is owned by the **gold** instance, product `genesis-wp-ha`: vision, dd_plan, epic, change_request, requirement, ac, issue, issue_fix, design_decision, and the rest.

- **Author only through `mcp__gold__*`** — `create_<type>` / `update_<type>` / `draft_<type>`; `catalog_*` is read-only from here (the catalog is OpenBrain's). Never as local markdown.
- **Every call takes `product: "genesis-wp-ha"`.**
- **Cross-product refs are rejected.** A genesis-wp-ha record cannot link a `genesis-wp/...` or `homelab/...` record. Mention it in text instead, for example "genesis-wp dd_plan-1" or "homelab exploration-8".
- **Never hand-pick a sequence number.** IDs are allocated server-side.
- **Never cache record status.** It is live data — query it at time of use.
- **Search before creating**, so you update the existing record instead of duplicating it: `search_<type>`, cross-type `search_records`, `list_<type>` (`include_summary=true`), `get_<type>`, and `list_inbound_refs` / `list_relations_for` for links.
- **Then pull the template** with `get_template_for` and write into its structure. The template is what makes a record reviewable, not merely valid.
- **Fill every required field in the create call** — the schema's required set plus whatever `x-status-requires` gates for the target status; `describe_dto_type` gives the current shape. Some fields freeze once written.
- **Feature CRs need requirements.** A `kind: feature` change_request must list at least one requirement. Acceptance criteria are separate `ac` records parented to the requirement, never inline.
- **`summary` is the search surface.** Title + summary are embedded together and truncated at 256 word-piece tokens. Don't repeat the title; keep the summary to ~100–120 words, distinctive nouns first; no refs, status, dates, history, or link lists. Traceability and decisions go in `details`.
- **Closing needs `close_reason`** — a `closed` record without one always rejects.

Anchors:

- The product has no records yet. The first vision and plan are agreed with the owner before they are filed. Don't extend genesis-wp's dd_plan-1 / epic-1.
- Related, text-only: genesis-wp vision-1, dd_plan-1, epic-1 and the library CRs; homelab exploration-8 (rounds 17–19 cover the integration).

### Link records, don't cite refs

Render every gold record named in chat output as a link: `https://openbrain.local.aggeler.com/app/records/<product>/<type>/<seq>` — e.g. `[vision-1](https://openbrain.local.aggeler.com/app/records/genesis-wp-ha/vision/1)`. That host is gold; never link to copper.

### Records with an HTML body

A record written with `details_format: html` is expected to *show* its content. The full rule set (theme-safe SVG, sanitizer constraints) lives in openbrain's `CLAUDE.md`; the short form:

- Add one inline `<svg>` for each larger paragraph that describes structure, flow, sequence or magnitude. Give it a `viewBox` and no fixed pixel width.
- Every SVG carries a legend drawn with SVG primitives (`<text>` + `<rect>`/`<line>` swatches). No `foreignObject`, no `<style>`, no `<img>`, no `style=` on the root — the sanitizer strips them.
- Text and connectors use `fill="currentColor"` / `stroke="currentColor"`. No opaque background. Tint shapes with their stroke hue at `fill-opacity="0.15"`.
- One palette per record. State colors: good `#5fb88a`, warning `#d4a14d`, bad `#d46161`, neutral `currentColor` at `stroke-opacity="0.5"`.

### Charts — every axis carries a unit

- Every axis is labeled `name [unit]` — `temperature [°C]`, `power [kW]`, `pressure [bar(g)]`, `registers [count]`.
- A bar chart states what bar length encodes and whether the scale is linear or log.
- A categorical axis still names its dimension — `[entity platform]`, `[firmware profile]`.

## Change control

EVERY repo change goes through a CR. No silent fixes.

**A SoR record update is NOT a code change and needs NO CR.** Editing a gold record of any HELIX01 type (requirement, ac, issue, design_decision, epic, and so on) is record-plane work with its own change control. Do it directly through `mcp__gold__*`. Do not open a CR for it and do not wait for approval to make the edit.

The loop, always:

1. File records first. Defect or gap → `issue`. Then a `change_request`, parented to the epic it belongs to.
2. Get the CR approved BEFORE writing code.
3. Implement on a branch, test-first against the emulator. Gate green (see *The gate*).
4. Before closing: check the diff against EVERY acceptance criterion, one by one, write down the evidence. Green gate alone is NOT proof.
5. Close the CR with the merge SHA. If an issue drove it, close the issue via an `issue_fix` that references the CR and the SHA.

Small change? Still a CR. Repo docs-only? Still a CR (`transition_gate: prose`).

A fix that belongs in the library (register map, decoding, transport, emulator) is a CR in product genesis-wp, implemented by wpe-1 in the library repo; this repo then bumps the pinned library reference under its own genesis-wp-ha CR.

The rule covers the **repo working tree**: code, tests, packaging, `manifest.json`, `hacs.json`, repo markdown. It does NOT cover:

- **SoR records** (see above).
- **Catalog items.** Materialized skills, templates, methods, runbooks and executors are owned by OpenBrain. Fix them at the source.
- **Local, gitignored state**, such as `openbrain-client.local.yaml` and `.logs/`.

Workflow entry points: `/change-request` (manual, owner-driven), `/automated-change-request` and `/run-queue` (autonomous tail).

## Transition gates

The field is `transition_gate`. Its values are five cumulative evidence classes — `prose` ⊂ `static` ⊂ `unit` ⊂ `integration` ⊂ `system`.

Commands are NEVER read from a record. Every invoker resolves them from the committed `openbrain-client.yaml` at the repo root, under `transition_gates.<rung>`. `openbrain-client.yaml` does not declare `transition_gates` yet. Until it does, run the rung's stages from *The gate* below, in session.

The merge is the git operation ONLY. It runs no gate and tears nothing down.

## The gate

Cumulative by rung — each rung runs everything below it.

| Rung | Stages |
|---|---|
| `prose` | none — diff review only |
| `static` | byte-compile the integration (`python -m compileall custom_components`); hassfest and HACS validation once the repo adopts them |
| `unit` | `python -m pytest` with pytest-homeassistant-custom-component — hermetic, loopback only, library mocked or emulator-backed |
| `integration` | `python -m pytest` including the tests that start genesis-wp-emulator instances and set up the integration against every firmware profile |
| `system` | an owner-approved, read-only check in homelab's Home Assistant, run by homelab — never automated, never a write |

- **Hosted CI is not a gate.** `.github/workflows/tests.yaml` (inherited from upstream) runs on GitHub; its result is informational. Every gate runs locally on the DEV VM.
- **The rungs are not substitutes for one another.** Never satisfy a rung with a lower rung's evidence.

### Reading a gate's result

**Never pipe a gate into `grep`, `head`, or `tail` and then read the exit code.** The shell reports the *filter's* status, so a red gate reads as a pass. Capture first, narrow after:

```zsh
python -m pytest > scratchpad/gate.out 2>&1; rc=$?
rg -i 'failed|error' scratchpad/gate.out; print "gate status: $rc"
```

Copy this form. The capture variable is `rc`, never `status` — in zsh `status` is a readonly alias of `?`, so `status=$?` aborts the compound and loses the result.

## Command surfaces — ask the tool, not this file

This file names commands only by intent. Arguments, flags and exit codes come from the tool when you use it; copies in prose drift.

- `openbrain-client` (from PATH) — `openbrain-client --help-json` for record ops, run-queue, and worktree lifecycle; `<command> --help` for one topic. Agents run it with `--mode ai`.
- `genesis-wp-emulator --help` (installed with the library's `emulator` extra).

## Tests

- pytest with pytest-homeassistant-custom-component. Tests stay hermetic: loopback networking only, no real device, no secrets. `tests/conftest.py` enforces this process-wide and re-applies itself around every test, because pytest-socket resets the socket functions per test. Don't weaken it.
- Environment: HA 2026.10.0 needs Python ≥ 3.14.2, newer than the host's 3.13. The repo `.venv` (gitignored) runs on a uv-managed CPython 3.14. Set it up with `uv venv --python 3.14 .venv`, then `uv pip install --python .venv/bin/python -r requirements_test.txt`. `requirements_test.txt` pins homeassistant, pytest-homeassistant-custom-component, and the genesis-wp commit with its emulator extra. Run the gate with `.venv/bin/python -m pytest`.
- Emulator tests request the `start_emulator` fixture, which pulls in `socket_enabled`. Profiles and constants live in `tests/harness.py`.
- Integration tests start genesis-wp-emulator on loopback with each firmware profile the library ships (currently 6.0.6 and 6.1.5) and drive config flow, setup and a coordinator refresh against it.
- Writable entities are tested only with the write opt-in enabled and only against the emulator.
- Fixtures and firmware profiles belong to the library repo. Don't copy or edit them here.

## Code conventions

- Python, asyncio throughout, following current Home Assistant integration patterns (config entries, `DataUpdateCoordinator`, entity descriptions). No blocking I/O in the event loop.
- Modbus I/O happens only inside the genesis-wp library. The integration never imports pymodbus or modbus-connection clients directly.
- A not-fitted sensor (library returns `None`) is not created, or is unavailable — never shown as 0.
- Write paths stay behind the explicit read-only opt-in. A change that weakens that guard needs its own CR and the owner's approval.

### Never commit

`openbrain-client.local.yaml`, `.logs/`, `scratchpad/`, manufacturer PDFs or photos, the device host name or serial number.

## Key files

- `LICENSE` — MIT with the upstream notice; see *License and third-party material*.
- `openbrain-client.yaml` — committed product truth for `openbrain-client` (product, process, placeholders).
- `custom_components/thermiagenesis/` — the integration as inherited from upstream (domain `thermiagenesis`, requires `pythermiagenesis==0.1.8`). The rename to `genesis_wp` and the switch to the genesis-wp library are pending CRs.
- `hacs.json` — HACS metadata.
- `tests/` — pytest suite inherited from upstream.
- `.github/workflows/tests.yaml` — hosted, upstream-inherited; see *The gate*.

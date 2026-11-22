---
name: publish
description: >
  Publish a genesis-wp-ha integration release: library tag pin and manifest BUILD stamp check,
  gold release notes, integration gate on a clean main, annotated vX.Y.Z tag and GitHub release on
  origin, gold product_version released and the next one opened, old GitHub releases pruned,
  homelab told the tag and SHA. No PyPI or other package index unless the owner decides otherwise. Use when the user says "/publish",
  "publish a version", "publish vX.Y.Z", "cut a release", "release the integration", "tag a release".
allowed-tools: mcp__gold__search_release_notes, mcp__gold__list_release_notes, mcp__gold__get_release_notes, mcp__gold__create_release_notes, mcp__gold__update_release_notes, mcp__gold__get_template_for, mcp__gold__admin_list_product_versions, mcp__gold__admin_get_product_version, mcp__gold__admin_update_product_version, mcp__gold__admin_advance_product_version_status, mcp__gold__admin_create_product_version, mcp__gold__create_baseline, mcp__gold__list_change_request, mcp__gold__get_change_request, mcp__gold__list_issue
disable-model-invocation: true
---

# Publish

This skill cuts one genesis-wp-ha release. It mirrors genesis-wp's publish skill (`/container/genesis-wp/.claude/skills/publish/SKILL.md`), and the two skills keep the same step numbers.

| Part | Where it lives |
|---|---|
| annotated `vX.Y.Z` tag | origin |
| GitHub release | origin, body from the gold release_notes record |
| release_notes record | gold |
| product_version moved to released, next row opened | gold |

The procedure carries user_need-1 and its requirements:

| Requirement | Rule |
|---|---|
| requirement-32 | version MAJOR.MINOR.PATCH.BUILD, stamped by the merge (ac-179 to ac-181) |
| requirement-33 | what a release consists of (ac-189 to ac-192); no package index |
| requirement-34 | release retention: three named bounds (ac-186 to ac-188) |

The skill installs nothing anywhere. homelab owns rollout to DEV and PROD.

**Outward-facing.** The tag push and the GitHub release need the owner's explicit "yes" in this chat, every time (Step 4). A peer session's relayed approval is not that "yes".

**Library first.** A genesis-wp-ha release pins a released genesis-wp tag. If wpe-1 has not sent a library tag and its SHA for the pin, stop before Step 1.

## Step 0: Hard preconditions

Stop at the first failure and report which check failed. All checks run from the primary checkout `/container/genesis-wp-ha`.

```zsh
cd /container/genesis-wp-ha
git fetch origin --tags
git status --porcelain                      # must be empty
git rev-parse --abbrev-ref HEAD             # must be main
git rev-parse main origin/main              # must be equal
git rev-parse --is-shallow-repository       # must be false (BUILD needs the full history)
git worktree list                           # note any live cr-<n> runner; never release mid-drain
```

Then run the package-index check. It must print nothing:

```zsh
git grep -n -I -E 'twine upload|setup\.py upload|gh-action-pypi-publish|upload\.pypi\.org|test\.pypi\.org|PYPI_' -- . ':!.claude/skills/publish/SKILL.md'; git ls-files | rg -x '.*\.pypirc'
```

Check that no release-drafter draft is waiting. `.github/workflows/release-drafter.yml` is inherited from upstream and drafts releases on every push to main:

```zsh
gh release list --repo david-aggeler/genesis-wp-ha --json tagName,isDraft
```

A draft for the target tag must be deleted by hand, with the owner's OK, before Step 5. The workflow itself is removed through a change_request, never inside a release.

## Step 1: Determine the version

1. The repo-root `VERSION` file holds `X.Y.Z` (no `v`). It is the only semver source (requirement-32).
2. Find the previous own release:

   ```zsh
   gh release list --repo david-aggeler/genesis-wp-ha --limit 20
   ```

   The inherited upstream tags 0.0.1 to 0.0.12 have no release of ours. They never count as a previous release.
3. Collect the change_requests merged since the previous tag, or since the first commit for the first release:

   ```zsh
   git log --format='%h %s' <prev-tag>..HEAD | rg -o 'change_request-\d+' | sort -u
   ```

4. Suggest the version:
   - any kind: feature change_request: a minor bump;
   - otherwise: a patch bump.

   The owner may name any version above the latest tag. Ask: "Next version would be vX.Y.Z (N change_requests since <prev>). Use that?"
5. **Release prep is a change_request.** If `VERSION` differs from the chosen `X.Y.Z`, or the manifest does not pin the library tag from wpe-1, file one change_request for both changes:
   - set `VERSION`;
   - pin `genesis-wp @ git+https://github.com/david-aggeler/genesis-wp@<tag>` in `manifest.json` and `requirements_test.txt`;
   - force-reinstall the venv (CLAUDE.md, *Tests*).

   Approve it, then drain it through run-queue so its merge stamps the manifest. Restart at Step 0 afterward. Every repo change goes through a change_request, and this one is no exception.
6. Check the pin. The library tag must resolve to the SHA wpe-1 sent:

   ```zsh
   git ls-remote https://github.com/david-aggeler/genesis-wp "refs/tags/<lib-tag>^{}"
   ```

7. Check the stamp. HEAD must be a merge commit, and its manifest version must be `X.Y.Z.<git rev-list --count HEAD>`:

   ```zsh
   git rev-list --parents -n 1 HEAD               # three ids: a merge
   .venv/bin/python -c 'import json; print(json.load(open("custom_components/genesis_wp/manifest.json"))["version"])'
   git rev-list --count HEAD
   ```

   A hand commit after the last merge, such as an agent-instructions edit, leaves the stamp one merge behind. In that case land the release-prep change_request from 1.5 first, so the release commit is a stamped merge.

## Step 2: Write the release notes in gold

The SoR holds the release notes, and the GitHub release body is generated from them.

1. Find the record with `search_release_notes` for product genesis-wp-ha and version X.Y.Z. If none exists, call `get_template_for release_notes` and create it:
   - `title`: `genesis-wp-ha vX.Y.Z`;
   - `status`: draft;
   - `product_version`: `genesis-wp-ha/X.Y.Z`;
   - `related`: the change_requests from Step 1.3 and the issues they closed.
2. Fill the template skeleton:
   - **Highlights** first, for the owner.
   - Then New, Improved, Fixed and Breaking changes. For a Home Assistant user, a breaking change is:
     - a removed or renamed entity or unique ID;
     - a changed config entry option;
     - a dashboard card config key that no longer works.
   - Upgrade & migration: what the owner does in Home Assistant after updating. No backward compatibility is kept in DEV, so say plainly when an entry must be re-added.
   - Library: the pinned genesis-wp tag and its SHA.
   - Known issues: the open issues from `list_issue`.
   - Artifacts: the tag and "no package index upload".

   Write "None." only after checking. Cite records, not commits.
3. Render the GitHub body to `scratchpad/release-notes-vX.Y.Z.md`. It holds the Highlights through Known issues sections, then a final line linking the record: `https://openbrain.local.aggeler.com/app/records/genesis-wp-ha/release_notes/<seq>`.

## Step 3: Gate at HEAD

Run the integration rung from `openbrain-client.yaml` `transition_gates.integration`. Run its in_session and its runner_owned stages, by hand, and say so. Capture each exit code; never pipe a gate. The full suite takes more than 10 minutes, so run it in the background and read the exit code. Its `-q` output prints progress only.

```zsh
d=$(<scratchpad/nodedir); export PATH=$d:$PATH
bash scripts/gate_python.sh -m compileall -q custom_components tests > scratchpad/release-gate.out 2>&1; rc=$?; print "compileall rc $rc"
bash scripts/gate_python.sh -m pytest >> scratchpad/release-gate.out 2>&1; rc=$?; print "pytest rc $rc"
```

Add any runner_owned stage that the yaml lists beyond these. Any non-zero rc stops the release.

## Step 4: Ask for explicit confirmation

Show the owner:
- version and SHA (`git rev-parse HEAD`);
- BUILD, as the manifest version;
- the pinned library tag and its SHA;
- change_request count;
- gate results;
- the release_notes link;
- the rendered Highlights.

Then ask:

> Release genesis-wp-ha vX.Y.Z at <SHA>? This pushes an annotated tag and creates a GitHub release on origin (no package index), marks the gold product_version released, opens the next version and prunes old GitHub releases. (yes/no)

Proceed only on an explicit yes.

## Step 5: Tag and GitHub release

```zsh
git tag -a vX.Y.Z -m "genesis-wp-ha vX.Y.Z" && git push origin vX.Y.Z
gh release create vX.Y.Z --repo david-aggeler/genesis-wp-ha --verify-tag --title "genesis-wp-ha vX.Y.Z" --notes-file scratchpad/release-notes-vX.Y.Z.md
git cat-file -t vX.Y.Z                                                   # tag
git show vX.Y.Z:VERSION                                                  # X.Y.Z
git show vX.Y.Z:custom_components/genesis_wp/manifest.json | rg '"version"'   # X.Y.Z.<BUILD>
```

- **Remote:** push only to origin, never to upstream or cjne.
- **Ordering:** the release never comes before the tag.
- **Never:** `--force`, re-tagging, or moving a pushed tag.
- **Wrong tag:** if a pushed tag turns out wrong, stop and ask the owner; the fix is a new patch version.

## Step 6: Gold bookkeeping

Do these in order, and report anything partial.

1. Set the release_notes record to `status: released`.
2. Call `create_baseline` named `genesis-wp-ha vX.Y.Z` and capture its ref.
3. `admin_get_product_version` genesis-wp-ha X.Y.Z. If the row does not exist, create it first. Then `admin_update_product_version`, which takes only body, release_notes and new_version. Keep the body and append `Git tag: vX.Y.Z (<SHA>)`, `Library: genesis-wp <lib-tag> (<lib SHA>)` and `SoR baseline: <ref>`, and set release_notes to the release_notes record's link. Never pass new_version: a version is never renamed.
4. `admin_advance_product_version_status` X.Y.Z → released.
5. `admin_create_product_version` for the next version, X.Y.(Z+1) unless the owner named another, as in_development. Never rename a row (keel issue-271). This step is explicit because advancing the status does not open the next row.
6. Bump `VERSION` to the next version through a change_request at the start of the next lane. Builds after the release then stop carrying the released core.

## Step 7: Prune old GitHub releases

requirement-34 sets the keep-set: per MAJOR.MINOR line, ordered newest first.

| Rule | Keeps |
|---|---|
| Terminal rule | the highest patch of each of the 5 newest lines; older lines keep nothing |
| Depth rule | the 5 newest patches of each of the 2 newest lines |

- **Eligibility:** only versions with a GitHub release are eligible.
- **Prune set:** every other release.
- **Tags:** never deleted, upstream tags included.

```zsh
gh api --paginate repos/david-aggeler/genesis-wp-ha/releases --jq '.[].tag_name'   # list
gh release delete <tag> --yes --repo david-aggeler/genesis-wp-ha                    # delete, keeps the tag; never --cleanup-tag
```

Show the keep and prune sets first, as a dry run. Delete only the prune set. Compare `git ls-remote --tags origin` before and after; the two lists must be identical. Once a pruning script is committed through a change_request, use it here instead of the hand computation.

## Step 8: Notify

- **homelab-1:**

  ```
  genesis-wp-ha vX.Y.Z is released
  tag: vX.Y.Z
  full SHA: <git rev-parse vX.Y.Z^{commit}>
  manifest version: X.Y.Z.<BUILD>
  library: genesis-wp <lib-tag> (<lib SHA>)
  ```

  Add the Breaking changes and Upgrade & migration text, quoted. homelab deploys it to DEV first; the owner decides PROD.
- **wpe-1:** a short note, "genesis-wp-ha vX.Y.Z released on genesis-wp <lib-tag>".

## Step 9: Report

Report to the owner:
- release URL;
- tag and SHA;
- manifest version with BUILD;
- library tag;
- release_notes link;
- product_version released and the next one open;
- baseline ref;
- pruned releases, or none;
- who was notified.

For a failure, name the step that failed and what is already live.

## What this skill never does

- Upload to PyPI or any package index, or create a release while an upload path exists. Only the owner can change that rule.
- Release without the owner's explicit yes in this chat.
- Release on a library commit pin instead of a released genesis-wp tag.
- Skip or pipe the gate, or release from a dirty tree, a branch, a worktree, a shallow clone or an unstamped HEAD.
- Change repo files outside a change_request. VERSION and the pin go through one.
- Force-push, push to upstream or cjne, or move or delete a tag, upstream tags included.
- Touch the real heat pump. Releasing never needs the device.
- Edit genesis-wp files or release the library on its behalf.

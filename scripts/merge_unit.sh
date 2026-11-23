#!/usr/bin/env bash
# Land one unit branch cr-<n> on main as a no-ff merge commit titled
# "Merge cr-<n> (change_request-<n>)" and print code_change_ref=<merge sha>.
#
# openbrain-client merge runs this as merge_command (openbrain-client.yaml) and appends one
# argument: the commit SHA it resolved from branch-or-ref. A person may pass the branch
# name instead. Fails closed, leaving main untouched: not on main, a merge, cherry-pick,
# revert, am, rebase, sequencer or bisect already in progress, dirty tracked tree, an
# assume-unchanged or skip-worktree entry, argument that resolves to no single cr-<n> branch,
# nothing ahead of main, merge failure, a rejecting pre-merge-commit hook, a missing or
# malformed VERSION, a merge commit whose subject or parents a hook changed, or whose
# manifest is not a regular file stamped VERSION.<commit count>. Branches are resolved by full refname, so
# a tag named main or cr-<n> changes nothing. After a merge it pushes main to the branch main
# tracks (origin master); a refusal pushes nothing.
#
# Mirrors genesis-wp scripts/merge_unit.sh (same owner, MIT).
set -euo pipefail

MAIN=main
MAIN_REF=refs/heads/$MAIN
UNIT='^cr-[1-9][0-9]*$'

refuse() {
	printf 'merge_unit: %s\n' "$*" >&2
	exit 1
}

# The whole operation is one function, so bash has parsed all of it before the merge
# rewrites this file.
main() {
	[ "$#" -eq 1 ] || refuse "usage: merge_unit.sh <cr-<n> | commit sha>"
	arg=$1

	head=$(git symbolic-ref --quiet HEAD) || refuse "HEAD is detached, want $MAIN"
	[ "$head" = "$MAIN_REF" ] || refuse "on branch ${head#refs/heads/}, want $MAIN"
	for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-apply rebase-merge sequencer BISECT_LOG; do
		[ ! -e "$(git rev-parse --git-path "$marker")" ] || refuse "$marker exists: conclude or abort the operation in progress first"
	done
	changes=$(git status --porcelain --untracked-files=no) || refuse "git status failed"
	[ -z "$changes" ] || refuse "tracked changes in the working tree"
	hidden=$(git ls-files -v | grep -E '^[a-zS] ' || true)
	[ -z "$hidden" ] || refuse "assume-unchanged or skip-worktree entries hide working-tree state: ${hidden//$'\n'/ }"

	if [[ $arg =~ $UNIT ]]; then
		branch=$arg
		sha=$(git rev-parse --quiet --verify "refs/heads/$branch^{commit}") || refuse "no branch $branch"
	else
		sha=$(git rev-parse --quiet --verify "$arg^{commit}") || refuse "cannot resolve $arg to a commit"
		heads=$(git for-each-ref --points-at "$sha" --format='%(refname:lstrip=2)' refs/heads/) || refuse "cannot list the branches at $sha"
		branches=$(printf '%s\n' "$heads" | grep -E "$UNIT" || true)
		count=$(printf '%s' "$branches" | grep -c . || true)
		[ "$count" -eq 1 ] || refuse "$count unit branches point at $sha, want exactly one: ${branches//$'\n'/ }"
		branch=$branches
	fi

	ahead=$(git rev-list --count "$MAIN_REF..$sha") || refuse "cannot count the commits of $branch ahead of $MAIN"
	[ "$ahead" -gt 0 ] || refuse "$branch has nothing ahead of $MAIN"

	main_before=$(git rev-parse --verify "$MAIN_REF")
	subject="Merge $branch (change_request-${branch#cr-})"
	manifest=custom_components/genesis_wp/manifest.json
	# Run the helper from this script's own revision: the merge may change or remove it.
	version_tool=$(mktemp)
	trap 'rm -f "$version_tool"' EXIT
	cp "$(dirname "${BASH_SOURCE[0]}")/manifest_version.py" "$version_tool" || refuse "cannot copy the manifest version helper"

	abort_merge() {
		# MERGE_HEAD was absent before this invocation, so one now belongs to this merge.
		[ -e "$(git rev-parse --git-path MERGE_HEAD)" ] || refuse "$1; no merge started"
		git merge --abort || refuse "$1; git merge --abort failed, MERGE_HEAD left in place"
		refuse "$1; merge aborted"
	}

	merge_state=clean
	if ! git merge --quiet --no-ff --no-commit -m "$subject" "$sha" >&2; then
		[ -e "$(git rev-parse --git-path MERGE_HEAD)" ] || abort_merge "merge of $branch into $MAIN failed"
		merge_state=conflicted
	fi

	# DHF-REQ: genesis-wp-ha/requirement-32
	reachable=$(git rev-list --count "$main_before" "$sha") || abort_merge "cannot count commits for $branch"
	python3 "$version_tool" stamp "$manifest" "$((reachable + 1))" "$merge_state" \
		|| abort_merge "cannot stamp $manifest from VERSION"
	# --no-commit skips the pre-merge-commit hook; run it on the stamped index so a rejecting
	# hook still refuses the merge.
	git hook run --ignore-missing pre-merge-commit >&2 || abort_merge "pre-merge-commit hook rejected the merge of $branch"
	git commit --quiet -m "$subject" >&2 || abort_merge "cannot commit merge of $branch"

	merged=$(git rev-parse --verify HEAD)
	actual=$(git log -1 --format=%s "$merged")
	parents=$(git rev-list --parents -n 1 "$merged")
	problem=
	if [ "$actual" != "$subject" ]; then
		problem="subject is '$actual', want '$subject'"
	elif [ "$parents" != "$merged $main_before $sha" ]; then
		problem="merge commit $merged has parents '${parents#"$merged"}', want '$main_before $sha'"
	elif ! python3 "$version_tool" verify "$manifest" "$merged"; then
		problem="manifest version at $merged does not match VERSION and its commit count"
	fi
	if [ -n "$problem" ]; then
		git reset --quiet --keep "$main_before" && refuse "$problem; $MAIN reset to $main_before"
		# The working tree blocked the reset (e.g. a hook edited a merged file): restore the ref only,
		# if it still points at this merge, and leave the working tree to the operator.
		git update-ref -m "merge_unit: roll back rejected merge" "$MAIN_REF" "$main_before" "$merged" \
			|| refuse "$problem; resetting $MAIN to $main_before failed, $MAIN left at $(git rev-parse "$MAIN_REF")"
		refuse "$problem; $MAIN ref restored to $main_before, working tree left for the operator"
	fi

	printf 'code_change_ref=%s\n' "$merged"

	# Push the landed merge to the branch main tracks. Fast-forward only, never
	# forced. The merge already stands, so a skipped or rejected push is reported, not failed:
	# a non-zero exit would make the runner treat a landed unit as unmerged.
	remote=$(git config --get "branch.$MAIN.remote" || true)
	upstream=$(git config --get "branch.$MAIN.merge" || true)
	if [ -z "$remote" ] || [ -z "$upstream" ]; then
		printf 'merge_unit: %s has no upstream, push skipped\n' "$MAIN" >&2
	elif ! git push --quiet "$remote" "$MAIN_REF:$upstream" >&2; then
		printf 'merge_unit: push of %s to %s %s failed; the merge stands locally\n' "$MAIN" "$remote" "$upstream" >&2
	fi
}

main "$@"
exit

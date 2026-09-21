"""The CI workflow's concurrency group must dedupe `push` + `pull_request`.

`ci.yml` triggers on both events, unfiltered by branch (see its own comment on why:
job 10 missed a runtime crash for five days under `branches: [main]`). A push to a
branch with an open PR therefore fires both events for the same commit. `github.ref`
differs between them (`refs/heads/<branch>` vs `refs/pull/<n>/merge`), so a group keyed
on it never merges the two and every job — Design QA's visual regression included —
used to run in full twice per push.

`head_ref` is set only on `pull_request` and is the bare branch name; `ref_name` is
that same bare name on `push`. This is a text check, not a YAML-semantic one: the
expression lives inside a `${{ }}` template GitHub evaluates, not Python, so parsing
it as YAML would only hand back the literal string anyway. A regression here (back to
`github.ref`, or dropping the `head_ref` fallback) reintroduces the double run
silently, so it is asserted directly rather than left to be noticed in a bill.
"""

from __future__ import annotations

import pathlib
import re

_WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"


def _concurrency_block() -> str:
    text = _WORKFLOW.read_text()
    match = re.search(r"^concurrency:\n((?:  .+\n)+)", text, re.MULTILINE)
    assert match, "ci.yml has no top-level `concurrency:` block"
    return match.group(1)


def test_the_concurrency_group_merges_push_and_pull_request_for_one_branch():
    block = _concurrency_block()
    assert "github.head_ref || github.ref_name" in block, (
        "the concurrency group must key on `github.head_ref || github.ref_name` so "
        "that a branch's `push` and `pull_request` runs share one group — `ref_name` "
        "(push) and `head_ref` (pull_request) are the same bare branch name, unlike "
        "`github.ref`, which differs between the two events and lets both run in full"
    )


def test_cancel_in_progress_still_drops_a_superseded_run():
    block = _concurrency_block()
    assert re.search(r"cancel-in-progress:\s*true", block), (
        "without cancel-in-progress, a new commit on the same branch no longer "
        "replaces its predecessor's still-running CI"
    )

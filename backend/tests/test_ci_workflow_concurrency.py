"""Small guardrails on `ci.yml` values that a routine edit could silently undo.

These are text checks, not YAML-semantic ones: `${{ }}` expressions are a GitHub
template, not Python, so parsing them as YAML would only hand back the literal string
anyway. A plain regex against the file is simpler than a YAML round-trip and adds no
dependency the project doesn't already declare.

**The concurrency group must dedupe `push` + `pull_request`.** `ci.yml` triggers on
both events, unfiltered by branch (see its own comment on why: job 10 missed a runtime
crash for five days under `branches: [main]`). A push to a branch with an open PR
therefore fires both events for the same commit. `github.ref` differs between them
(`refs/heads/<branch>` vs `refs/pull/<n>/merge`), so a group keyed on it never merges
the two and every job — Design QA's visual regression included — used to run in full
twice per push. `head_ref` is set only on `pull_request` and is the bare branch name;
`ref_name` is that same bare name on `push`. A regression here (back to `github.ref`,
or dropping the `head_ref` fallback) reintroduces the double run silently.

**The Playwright job must keep a timeout-minutes cap.** A known intermittent backend
flake (ECONNRESET mid-suite) doesn't hang a single test, it grinds the whole spec list
to failure over 30-52 minutes. Without an explicit cap, GitHub's 360-minute default
applies, and a routine edit that drops the cap would go unnoticed until a flake burned
six hours of runner time. The job now lives in its own `browser-workflows.yml`
(moved out of `ci.yml` 2026-09-22, so its own timeout-cancellation could never again
drag down `ci.yml`'s check-suite, and with it the required "3 · Authorization matrix"
context) -- the cap itself is checked wherever the job actually is.
"""

from __future__ import annotations

import pathlib
import re

_WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows"
_WORKFLOW = _WORKFLOWS_DIR / "ci.yml"
_BROWSER_WORKFLOW = _WORKFLOWS_DIR / "browser-workflows.yml"


def _top_level_block(key: str, workflow: pathlib.Path = _WORKFLOW) -> str:
    text = workflow.read_text()
    match = re.search(rf"^{re.escape(key)}:\n((?:  .+\n)+)", text, re.MULTILINE)
    assert match, f"{workflow.name} has no top-level `{key}:` block"
    return match.group(1)


def _concurrency_block() -> str:
    return _top_level_block("concurrency")


def _job_block(job_key: str, workflow: pathlib.Path = _WORKFLOW) -> str:
    text = workflow.read_text()
    match = re.search(rf"\n  {re.escape(job_key)}:\n((?:    .+\n)+)", text)
    assert match, f"{workflow.name} has no `{job_key}:` job"
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


def test_the_flaky_browser_job_cannot_burn_the_full_360_minute_default():
    """A healthy Playwright run is 3-5 minutes. The known intermittent backend
    ECONNRESET flake doesn't hang a single test past its own 60s timeout -- it grinds
    through the whole spec list failing, which self-resolves at 30-52 minutes.
    Without a job-level `timeout-minutes`, GitHub's default is 360: a silent removal
    of the cap would let that flake burn six hours of runner time before anyone
    notices, rather than the 15 minutes this bounds it to. The job lives in
    `browser-workflows.yml`, not `ci.yml` -- checked at its actual, current location
    rather than assuming a file it moved out of."""
    block = _job_block("browser-workflows", _BROWSER_WORKFLOW)
    assert re.search(r"timeout-minutes:\s*1[0-9]\b", block), (
        "browser-workflows.yml's `browser-workflows` job must keep a timeout-minutes "
        "cap well under GitHub's 360-minute default, so the known ECONNRESET flake "
        "fails fast instead of burning runner time for up to six hours"
    )

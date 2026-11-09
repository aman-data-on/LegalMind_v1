---
paths:
  - "backend/tests/**"
  - "backend/pyproject.toml"
  - "frontend/e2e/**"
  - "frontend/src/**/*.test.*"
  - "frontend/vitest.config.*"
  - "frontend/playwright.config.*"
  - ".github/workflows/**"
---

# Testing — how to run it here (owner, 2026-10-09)

Test in layers, each where it is cheapest. A full suite on this shared 6-core host takes 8–35
min (other sessions compete); on CI about 3 min (job 13) and the whole run about 4.5 min.

| Layer | When | What |
|---|---|---|
| 1 | while coding | the touched module only, e.g. `python3 -m pytest tests/assist/agent -k <name>` |
| 2 | before pushing | `ruff check . && mypy` (CI job 1 runs both — ruff passing says nothing about types) + the affected folders |
| 3 | every PR | CI's full suite — the source of truth except for the models |
| 4 | nightly 02:00 IST | `assist-models-nightly.yml`: the full suite with the three local models (fails if a model does not load) |

## Environment

- DB-backed tests: from `backend/`, `set -a && . /root/.legalmind-test.env && set +a` (role
  `legalmind_test`). Tests never read the production env file (a conftest guard refuses it).
  Two concurrent runs cannot share one database — use your own.
- Source-material tests: `export LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs`
  in a worktree, or six checks skip and the run still says passed.
- Reproduce CI: `LEGALMIND_MODEL_DIR=<empty dir> LEGALMIND_SOURCE_MATERIAL_DIR=<empty dir>`.
  CI has **no model weights**: 48 Ask tests skip there and read green. A test needing an embedder
  carries `@pytest.mark.skipif(not embedding_runtime.available(), reason="no model provisioned")`.
- **Check the skip count, not just "passed"** — a skip is not a pass.
- Before any `DROP DATABASE`, check `pg_database`: nearly every `legalmind_*` database (including
  the Tier-2 gate DB `legalmind_v1_tier2_gate`) is droppable by the test role. Use fresh names.

## Rules

- A full local suite only for a large cross-cutting change: in the background, own DB, never
  blocking the owner. `pytest-xdist` is not adopted (shared test DB).
- After merging `main` into a branch, re-run only what the merge changed; records-only needs no run.
- Do not modify a test only to make CI pass; a changed golden-corpus expectation is a
  specification change (CI job 7).
- API schema change → regenerate `docs/api/openapi.json` with `python3 -m tools.export_openapi`
  and run `tests/test_api_contract.py` (CI job 3); Step 49 wins over the snapshot.
- Frontend: `npx tsc --noEmit`, `npm run lint:hooks`, `npx vitest run`, `npm run check:terms`
  (CI jobs 9 and 15). Visual baselines are CI-cut only — never `--update-snapshots` locally.
- A slow CI run explains itself: job 13 runs `--durations=30 -o faulthandler_timeout=120`; read
  that log before guessing. Job 5 runs the F-4 stability probe as three runs plus a verdict.
- The "Browser workflows" run (`browser-workflows.yml`, historically "job 10") can die mid-run with "socket hang up" — nondeterministic and
  non-gating; never mask it with retries.
- Merge queue is unavailable (personal-account repo): when `main` moves, merge it into the
  branch and push (with the owner's go).
- Attribute every failure before reporting it: compare against a clean worktree at `origin/main`
  (never `git stash` in a shared tree); do the arithmetic out loud ("196 recorded + 9 theirs = 205").

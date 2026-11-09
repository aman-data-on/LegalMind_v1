# CLAUDE.md — LegalMind

LegalMind reviews contracts against LeapSwitch's ratified Company Standards (a deterministic
evaluator produces Findings; humans make Legal Decisions) and answers legal questions in **Ask**
(a grounded RAG lane that never decides). Backend: Python/FastAPI/Postgres+pgvector in
`backend/`. Frontend: Next.js in `frontend/`. **Specification-first**: `IMPL-01` (locked
2026-08-17) authorises building what is locked and nothing that is not.

Detail loads on demand: `.claude/rules/` (by path), `.claude/skills/` (by task). The
pre-2026-11-09 file is archived verbatim at `docs/00-project/archive/CLAUDE_MD_2026-11-09.md`.

## Session start — when the owner says "hi" (or anything that is not a task)

Do not ask what they want. Read, in order: [LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md)
→ [CHANGELOG.md](CHANGELOG.md) `[Unreleased]` top entries → [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)
Build state (the **only** document that may assert build state) → [ENTERPRISE_TRACKER.md](docs/00-project/ENTERPRISE_TRACKER.md).
Reply short, plain language: **where we are** (one line) · **finished last session** (2–3 bullets) ·
**blocked, and on what** · **what I need from you** (or "nothing — next step is X").
Verify every number (run/grep, never quote a stale doc). Never re-ask what is decided —
check [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md) and
[LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) first. End every reply with a status
line ("still working on X" / "waiting for next phase"). A session that finishes a unit of work
updates PROJECT_STATE, CHANGELOG and IMPLEMENTATION_STATUS so the next greeting answers itself.

## How we work — a complete product team

Every task is staffed by the roles it needs: product manager (what the user needs, acceptance
checks), legal-domain expert (rules 7, 13–15, 21), UX/UI designer (`.claude/rules/ui-ux.md`),
full-stack engineer, QA/test engineer, security reviewer (rule 18), DevOps/release (git/deploy
below), technical writer (records). Run the loop in the **`team-delivery`** skill:
**research with official sources → written spec with acceptance checks → build → the same
researcher re-checks against its spec** (fresh context: `.claude/agents/independent-verifier.md`).

- Decide engineering and design yourself; ask the owner only product, legal, security or
  external questions (credentials, real legal material, payments, real people's facts).
- Fix findings in batches of ~5–6 per branch; ask "go" once per batch.
- Fix the class of failure for every agreement type, never one document.
- **Try once before saying "can't"** — one cheap real probe, then do it or report the exact error.
- **Verify before asserting** — a number, a test result, "done". A skip is not a pass.
- Say what you actually did, including what was skipped or blocked.

## Checks — the commands

| What | Command (from) |
|---|---|
| Lint + types (CI job 1 runs both) | `ruff check . && mypy` (`backend/`) |
| One module's tests | `python3 -m pytest tests/<path> -q -k <name>` (`backend/`) |
| DB-backed tests | `set -a && . /root/.legalmind-test.env && set +a` first; own DB per concurrent run |
| Source-material tests in a worktree | `export LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs` (else 6 skip silently) |
| Ask code (prompt, router, retrieval, verifier) | `tests/assist` twice: with models (`LEGALMIND_RERANK=on`) and CI-shaped (`LEGALMIND_MODEL_DIR=/nonexistent`) — CI has no model weights, 48 tests skip green there |
| API schema changed | `python3 -m tools.export_openapi` then `--check`; run `tests/test_api_contract.py` |
| Docs added | `python3 -m pytest tests/test_documentation_index.py -q` (`backend/`) |
| Frontend | `npx tsc --noEmit && npm run lint:hooks && npx vitest run` (`frontend/`); `npm run check:terms` |
| Ask benchmark (zero Gemini) | `python3 -m tools.rag_benchmark` (`backend/`) |

Test in layers: touched module while coding → ruff+mypy+affected folders before pushing → CI
full suite on the PR → nightly with models. No local full suite by default (8–35 min on this
shared host). Details: `.claude/rules/testing.md`.

## The twenty-three rules

**Specification discipline**
1. Specification-first: decide in the spec, then implement — never the reverse.
2. A decision marked LOCKED in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) is settled.
3. Never silently modify a locked decision — not for a bug, cleaner code or a better idea.
4. No feature without an approved specification. Unspecified → stop and ask; no "reasonable default".
5. A contradiction → stop, add it to [CONFLICTS.md](docs/00-project/CONFLICTS.md), report it. Never pick, merge or assume the later wins.
6. To change a lock: name the ID, its text, the proposal and why; wait for yes. **Two owner
   delegations replace the wait:** the Ask/RAG roadmap (2026-09-24, `.claude/rules/ask-rag.md`) and
   "product over locks" (2026-11-02: design the best product, list each colliding lock as a
   proposed amendment). Neither covers legal content (rules 7/21), authorization (rule 18), the
   append-only audit trail, the zero-tolerance Legal Rule, or the Gemini cost guard. Procedure: skill `lock-amendment`.
7. Never invent a legal requirement — no rule, threshold, tolerance, carve-out or evaluator behavior absent from the spec.
8. Never claim an unspecified decision is final. `NOT YET SPECIFIED` is a valid state; preserve it.

**The legal-analysis model**
9. The authoritative lane is deterministic (same inputs + config snapshot + engine version → same result). The assist lane (`AM-25`) makes no determinism claim and never enters a determinism assertion (`AM-28`).
10. No LLM, RAG, embedding or vector DB **decides** anything in the authoritative path (`AI-01`, `AM-25`). `AM-54`/`AM-60` allow the RECOGNITION step only, for every pinned Requirement (local embeddings + the egress seam, accepted only on a verbatim span; model identity, prompt version and payload hash recorded; UNCLEAR fails closed to Needs review, NO leaves the lexical result; no company position enters a payload); comparison, classification and Rule Outcome stay deterministic. Classical NLP (e.g. spaCy) is assist-only. The assist lane (`AM-25`–`AM-30`, Gemini generation the one egress) never produces a Finding, Evaluation, Classification, Rule Outcome, Mapping State, Legal Decision or Lifecycle transition, never writes legal/config tables, never states a position absent from a ratified standard, and never answers "does this meet our standard?". Read `AM-25` before touching that lane.
11. Every Finding and extracted fact traces to source evidence; evidence survives the evaluator.
12. Findings reconstruct as Evidence → Fact → Standard → Rule → Result. No risk score, no "AI confidence"; a retrieval score (`AM-29`) is never shown as legal confidence.
13. Company Standard (what we want) ≠ Legal Rule (tolerance) ≠ Legal Decision (a human's ruling). The engine never produces Legal Decisions.
14. RESOLVED ≠ MATCH; DEVIATION ≠ "unacceptable".
15. Fail closed: insufficient evidence → `UNABLE_TO_EVALUATE`; never guess, never drop a carve-out.

**System guarantees**
16. Configuration is versioned; Reviews use snapshots; publishing never mutates a Review; drafts never affect comparisons.
17. The audit trail is append-only; historical Reviews stay reproducible.
18. Authentication → Authorization → Business Operation → Database, server-side. An ID is never access. UI gating is presentation only and the UI holds no legal logic. Authentication never confers Legal Decision authority (`SEC-01`; the JWT `roles` claim is advisory, `AM-36`); no super-role reaches `legal.decision`/`legal.approve_customization` (`SEC-02`, `ROLE-05`); internal positions never leak (`LEGAL-02`); confidential fields are omitted, not nulled; out-of-scope = byte-identical 404 (`SEC-07`, `API-10`).
19. No architectural change for convenience; no new technology, dependency or service without approval.
20. `docs/` is the implementation specification — reference it, keep it in sync.
21. **Ask for real legal source material; never manufacture it** (fixtures, standards, rules, catalogues, aliases, thresholds, seed data, any test asserting a legal conclusion). Spec examples are illustrations, not positions.
22. `all_lock.md` is **append-only** — never edit, reflow, reorder or delete a line. Locked docs are superseded with a banner, never overwritten.
23. Completed work is completed, whoever did it — another session, terminal or agent counts. Read the state before starting; grep/test before rebuilding; keep five states distinct: already decided · already implemented · material supplied · genuinely missing material · genuinely pending decision. Assume other sessions are live.

## Git, worktrees, deploy

- **Never commit, push, open/update a PR, merge or deploy until the owner says so** (owner
  2026-09-29); each is a separate yes and does not carry to the next task. Exception: the CLM
  branches (`clm-*` worktrees), where the git agent may commit by path, push and open DRAFT PRs —
  never merge to `main` or deploy (owner 2026-11-04).
- Work on a task branch in **your own worktree**: `git worktree add /root/legalmind-worktrees/<task> -b <branch> origin/main`.
  `/root/Legalmind.v1` is the deploy tree — read only, keep it on clean `main`.
- Start with `git status`, `git branch --show-current`, `git worktree list`, `git fetch`.
- Stage by explicit path, never `git add -A`/`.`. Never `reset --hard`, `checkout -- .`, `clean`,
  `stash` or revert files you did not modify. Never `worktree remove --force` one you did not create.
- `main` is branch-protected; before any merge run the ruleset check in [AGENTS.md](AGENTS.md) §13a.
- Deploy only via `sudo legalmind-deploy` (one at a time; `REFUSING: another deploy` is the guard working).
  Never a bare `next build` in the deploy tree; never touch production `:8000`/`:3000` or another
  session's ports/DBs. Full procedure: [AGENTS.md](AGENTS.md), [ops/README.md](ops/README.md).

## Traps

- **A later Step doc beats an older topic doc**: AUTHENTICATION → `STEP_47_…`, FRONTEND_ARCHITECTURE → `STEP_52_…`, TEST_STRATEGY → `STEP_54_…`, DEPLOYMENT → `STEP_55_…`.
- **📁 working documents are not specifications** — their status lines are stale; take outcomes from LOCKED_DECISIONS.md.
- **Search decisions by ID prefix**: `PROD ROLE LEGAL FIND DOC ENG AI ARCH DATA AUD LIABILITY REC AM SEC API FE OBS TEST DEP IMPL`; open items `OD-*`, `C-*`. `F-*` is overloaded (DECISION_FINALIZATION `F-3` ≠ IMPLEMENTATION_STATUS `F-3`) — name the document.
- **`all_lock.md` wins over `docs/`**; report any disagreement. Never edit it (rule 22).
- **Five state axes** (Mapping State, Classification, Rule Outcome, Legal Decision, Review Lifecycle) never share a field — read [DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md) before naming a state.
- **Never name a real client/counterparty or signatory** in the repo, records, PRs or comments — "the client".
- **Source documents are only in `legal-docs/`** (gitignored, locked 54.6). `/root/LegalMind/` is a different project.
- **Statutes are background law**, never a Legal Rule or Company Standard.
- **Take AM/AB numbers only after a collision scan** (skill `lock-amendment`).
- `pkill -f`/`pgrep -f | kill` kills your own shell — kill by PID.

## Where to find X

| Need | Go to |
|---|---|
| Doc index | [docs/README.md](docs/README.md) |
| Locked decisions / open conflicts / status | [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) · [CONFLICTS.md](docs/00-project/CONFLICTS.md) · [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| Architecture end to end | [ARCHITECTURE_REFERENCE.md](docs/00-project/ARCHITECTURE_REFERENCE.md) |
| Who can do what (AB-12 RBAC) | [RBAC_MODEL.md](docs/06-security/RBAC_MODEL.md) |
| Terms; source hierarchy | [GLOSSARY.md](docs/00-project/GLOSSARY.md) · [CLAUDE_WORKING_RULES.md](docs/00-project/CLAUDE_WORKING_RULES.md) |
| Proposing a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Git/GitHub, multi-agent, shared tree | [AGENTS.md](AGENTS.md) |
| Deploy, server | [ops/README.md](ops/README.md) |
| Ask/RAG target + log | [LEGALMIND_RAG_PRODUCTION_ROADMAP.md](docs/LEGALMIND_RAG_PRODUCTION_ROADMAP.md) · [DAILY_CHANGED.md](docs/DAILY_CHANGED.md) |
| UI work | `.claude/rules/ui-ux.md` (loads in `frontend/`) |
| Evaluator, standards, corpus, source material | `.claude/rules/legal-engine-config.md` |
| Records, locks, status labels, IMPL-01 scope | `.claude/rules/records-and-locks.md` |
| Run a local stack / browser test | skill `local-stack` |
| Proposed hooks (not enabled) | [PROPOSED_HOOKS_2026-11-09.md](docs/00-project/PROPOSED_HOOKS_2026-11-09.md) |

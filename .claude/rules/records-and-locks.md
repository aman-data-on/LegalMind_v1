---
paths:
  - "all_lock.md"
  - "CHANGELOG.md"
  - "CONTRIBUTING.md"
  - "docs/**"
---

# Records, locks and specification documents

## all_lock.md (rule 22)

Append-only. Never edit, reflow, reorder, reformat or delete an existing line — not a typo, not a
stale status block, not to apply an approved amendment. Approved changes are **appended** as new
lock records; superseded text stays where it is and is annotated elsewhere. Twelve documents
assert prior line counts are byte-identical, and historical Reviews' reproducibility depends on
it. Never run a formatter on it. CI job 6 checks the prefix. After merging `main` into a branch,
check `all_lock.md`'s `main` prefix is byte-identical. Amendment procedure: skill `lock-amendment`.

The same discipline applies to every locked specification in `docs/`: supersede with a banner,
never overwrite.

## Source hierarchy

`all_lock.md` (authoritative) → [LOCKED_DECISIONS.md](../../docs/00-project/LOCKED_DECISIONS.md)
(the index by ID) → `docs/` (the implementation specification, derived). If `all_lock.md` and
`docs/` disagree, `all_lock.md` wins **and you report the discrepancy**. Look a question up
before deriving it: registry → status → conflicts → glossary → specification. Full hierarchy for
legal questions: [CLAUDE_WORKING_RULES.md](../../docs/00-project/CLAUDE_WORKING_RULES.md) §1.

Re-check [IMPLEMENTATION_STATUS.md](../../docs/00-project/IMPLEMENTATION_STATUS.md) against the
tail of `all_lock.md` (`wc -l all_lock.md`); if the lock record is ahead of the docs, say so.

## Document status labels

| Label | Meaning |
|---|---|
| 🔒 `LOCKED` | Settled. Requires explicit approval to change |
| `PROVISIONAL` / `RECOMMENDED` | Proposed, not settled. Do not build on it as final |
| ⏳ `UNDER REVIEW` / `IN PROGRESS` | Being decided now |
| `PLANNED` / `NOT YET SPECIFIED` | Nothing decided. Do not invent it |
| 📁 `ANALYSIS` / `PROPOSAL` | Working document; decides nothing; its status lines may be stale |

Lifecycle state (specified · locked · implemented · tested · verified · blocked ·
production-ready) is tracked only in IMPLEMENTATION_STATUS.md and never shares a field or enum
with the five legal-domain state axes.

**A later Step document beats an older topic document**; four older files still read `NOT YET
SPECIFIED` for locked areas: AUTHENTICATION.md → `STEP_47_SECURITY_SPECIFICATION.md`,
FRONTEND_ARCHITECTURE.md → `STEP_52_FRONTEND_ARCHITECTURE.md`, TEST_STRATEGY.md →
`STEP_54_TESTING_STRATEGY.md`, DEPLOYMENT.md → `STEP_55_DEPLOYMENT.md`. The 📁 reconciliation
passes, scope audits, DECISION_FINALIZATION and EXTERNAL_REFERENCE_AUDIT record how conclusions
were reached (several still say "45D NOT LOCKED") — never implement from them.

## What IMPL-01 does and does not cover

`IMPL-01` (🔒 2026-08-17) authorises implementing the locked V1 specification in the
[IMPLEMENTATION_READINESS_GATE.md](../../docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md)
§5 sequence; its §6 constraints do not relax and rules 1–23 are unchanged. `IMPL-02`
(2026-08-25) does the same for the assist lane.

**Authorised:** application code, migrations, endpoints, frontend components and test harnesses
that realise a locked decision.

**Still needs explicit approval** (or an owner delegation — CLAUDE.md rule 6):
deciding anything `NOT YET SPECIFIED` · resolving an open conflict ([CONFLICTS.md](../../docs/00-project/CONFLICTS.md))
or `OD-*` (`OD-1`–`OD-15`, tracked in EXTERNAL_REFERENCE_AUDIT.md §16; `OD-9` closed by Step 47) ·
amending a locked decision · a table, column or enum not covered by a lock record · `NORMATIVE`
golden-corpus fixtures (real material only, rule 21) · a technology, dependency or service beyond
the Step 39 stack · altering a domain boundary · changing a golden-corpus expectation.
[CONTRIBUTING.md](../../CONTRIBUTING.md) has the procedure and the six kinds of change.

**The code is not a specification.** A behaviour in the code is not thereby decided; conformance
is verified against the locked corpus. `docs/09-implementation/` describes a target, not built work.

## Keeping the record in sync

- A specification change lands as one synchronized operation: `all_lock.md` appended + the
  registry + status + conflicts + every affected spec.
- Repository changes go in [CHANGELOG.md](../../CHANGELOG.md) `[Unreleased]`; decisions in
  `all_lock.md` and the registry — not interchangeable. Ask/RAG phases also log in
  `docs/DAILY_CHANGED.md`; deploys and server changes in `docs/00-project/DAILY_CHANGES.md`.
- Add every new document to [docs/README.md](../../docs/README.md) in the same change
  (`tests/test_documentation_index.py`, CI job 16).
- A session that finishes a unit of work updates LEGALMIND_PROJECT_STATE.md, CHANGELOG.md and
  IMPLEMENTATION_STATUS.md, plus [ENTERPRISE_TRACKER.md](../../docs/00-project/ENTERPRISE_TRACKER.md).
- Never a real client, counterparty or signatory name in any record — "the client".
- Leave a coordination note in CHANGELOG `[Unreleased]` or the PR when a call affects another
  session's work, including a deliberate decision not to integrate something.

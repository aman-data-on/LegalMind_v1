# CLAUDE.md — Working rules for LegalMind

Read this before doing anything in this repository.

**LegalMind is a specification-first project. It is currently in the specification/design phase. No implementation exists, and implementation must not begin without explicit approval.**

---

## Start here

| | |
|---|---|
| Project overview and doc map | [docs/00-project/PROJECT_OVERVIEW.md](docs/00-project/PROJECT_OVERVIEW.md) |
| Every explicitly locked decision | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| Current step and what is not yet decided | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| Known conflicts — do not resolve these yourself | [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| Terminology and the distinctions that matter | [docs/00-project/GLOSSARY.md](docs/00-project/GLOSSARY.md) |
| The authoritative historical record | [all_lock.md](all_lock.md) |

**`all_lock.md` is authoritative.** The `docs/` tree is the organized implementation reference derived from it. If they disagree, `all_lock.md` wins — and you must report the discrepancy rather than quietly following either one.

---

## The twenty rules

### Specification discipline

1. **LegalMind is specification-first.** Decisions are made in the specification, then implemented — never the reverse.
2. **Locked decisions are authoritative.** A decision marked LOCKED in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) is settled.
3. **Never silently modify a locked decision.** Not to fix a bug, not to make code cleaner, not because a better design occurred to you.
4. **Do not implement features without an approved specification.** If the behavior isn't specified, stop and ask — don't fill the gap with a reasonable-sounding default.
5. **When you discover a contradiction, stop and report it.** Do not pick the version you prefer, do not merge the two, do not assume the later one wins. Add it to [CONFLICTS.md](docs/00-project/CONFLICTS.md) and surface it.
6. **Before changing a locked decision, name it explicitly and request approval.** Say which decision ID, what it currently says, what you propose, and why. Wait for a yes.
7. **Never invent legal requirements.** No rule, threshold, tolerance, carve-out, or evaluator behavior that isn't in the specification. Inventing a plausible legal rule is worse than leaving a gap, because it looks authoritative.
8. **Never claim an unspecified decision is finalized.** "NOT YET SPECIFIED" is a valid, useful state. Preserve it.

### The legal-analysis model

9. **Legal analysis is deterministic in V1.** Same inputs + same configuration snapshot + same engine version → same result.
10. **V1 uses no LLM, RAG, embeddings, or vector database in the authoritative analysis path.** This is locked (`AI-01`) and is not a temporary simplification pending better tooling. Classical NLP (e.g. spaCy) is permitted in an assist-only role.
11. **Evidence traceability is mandatory.** Every finding and every extracted fact traces back to source evidence, and evidence must survive the evaluator.
12. **Findings must be explainable.** Every Finding reconstructs as Evidence → Fact → Standard → Rule → Result. No generic risk score. No "AI confidence" percentage.
13. **Legal Decisions are separate from Company Standards.** A Company Standard is what the organization wants; a Legal Rule is how far it will tolerate departing from that; a Legal Decision is an authorized human's ruling on a specific case. The engine produces Findings — it never produces Legal Decisions.
14. **RESOLVED ≠ MATCH.** A resolved workflow state must never be recorded as a MATCH finding. Likewise `DEVIATION` does not mean "unacceptable."
15. **Fail closed.** Insufficient extraction or evidence produces `UNABLE_TO_EVALUATE` — never a guess, never a silently resolved ambiguity, never a discarded carve-out.

### System guarantees

16. **Configuration is versioned, and Reviews use configuration snapshots.** Publishing new configuration never mutates an existing Review. Drafts never affect comparisons.
17. **Auditability and reproducibility are mandatory.** The audit trail is append-only. Historical Reviews stay reproducible.
18. **Security and ownership checks are server-side.** Authentication → Authorization → Business Operation → Database. Knowing an object's ID is never sufficient for access. The UI never implements legal evaluation logic and never talks to the database directly.
19. **Do not make architectural changes for convenience.** The domain boundaries in [SYSTEM_ARCHITECTURE.md](docs/05-architecture/SYSTEM_ARCHITECTURE.md) are locked. No new technologies, dependencies, or services without approval.
20. **Treat `docs/` as the implementation specification.** Reference it rather than re-deriving decisions, and keep it in sync when the specification advances.

---

## Preserve the examples

The specification is full of worked examples — MATCH vs DEVIATION, RESOLVED ≠ MATCH, APPROVAL_REQUIRED, contract customization, evidence traceability, configuration snapshots, liability evaluation, multiple clauses, conflicting provisions. **These are deliberate.** They exist to show intended behavior precisely where prose is ambiguous.

Never delete an example to make a document shorter. Never "clean up" example values. When you add a specification, add worked examples in the same style.

---

## Document status labels

Every specification document declares its state. Never mix states without labeling them.

| Label | Meaning |
|-------|---------|
| `LOCKED` | Settled. Requires explicit approval to change. |
| `PROVISIONAL` / `RECOMMENDED` | Proposed but not settled. Do not build on it as if it were final. |
| `UNDER REVIEW` | Actively being decided right now. |
| `PLANNED` / `NOT YET SPECIFIED` | Nothing has been decided. Do not invent it. |

---

## What "no implementation" means concretely

Do **not**, without explicit approval:

* write application code, database migrations, API endpoints, or frontend components
* install dependencies or select additional technologies
* create infrastructure or CI configuration
* generate scaffolding "to get started"

Documents under [docs/09-implementation/](docs/09-implementation/) describe a *target*. They are specifications, not records of built work. Their presence is not permission to build.

---

## Current state

**Steps 1–45B and `REC-01`–`REC-07` are locked. Step 45C — Liability Edge Cases — is IN PROGRESS: triage is complete, no edge case is yet decided.**

Only one requirement evaluator exists in specification: `LIABILITY-001`. Termination, Indemnification, Governing Law and every other requirement are NOT YET SPECIFIED — see [docs/04-analysis-engine/EDGE_CASES/](docs/04-analysis-engine/EDGE_CASES/).

**Before naming any state value, read [docs/02-legal-domain/DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md).** It is the canonical cross-layer reference for all five controlled state vocabularies. Mapping State, Finding Classification, Rule Outcome, Legal Decision, and Review Lifecycle are five separate axes and must never share a status field or enum — `AMBIGUOUS` in particular means three different things on three different layers.

Conflicts C-01–C-04 were reconciled on 2026-08-16 (`REC-01`–`REC-07`); four low-severity items remain open in [CONFLICTS.md](docs/00-project/CONFLICTS.md). The `REC-*` decisions are recorded in `all_lock.md` under "Post-Step-44 Cross-Document Reconciliation Decisions".

Always re-check [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) against the tail of [all_lock.md](all_lock.md) at the start of a session — the master specification grows as steps are locked, and the docs tree can lag behind it.

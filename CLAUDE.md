# CLAUDE.md — Working rules for LegalMind

Read this before doing anything in this repository.

**LegalMind is a specification-first project. The V1 specification is complete and implementation is now authorized** — `IMPL-01`, locked 2026-08-17. Specification-first still governs everything: `IMPL-01` authorizes **building what is already locked** and confers no authority to decide what is not. See [What implementation authorization does and does not cover](#what-implementation-authorization-does-and-does-not-cover).

---

## Start here

| | |
|---|---|
| **Where do I find X?** | [docs/README.md](docs/README.md) — the documentation index |
| **How the system works end to end** | [docs/00-project/ARCHITECTURE_REFERENCE.md](docs/00-project/ARCHITECTURE_REFERENCE.md) |
| Project overview | [docs/00-project/PROJECT_OVERVIEW.md](docs/00-project/PROJECT_OVERVIEW.md) |
| Every explicitly locked decision | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| Current step and what is not yet decided | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| Known conflicts — do not resolve these yourself | [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| Terminology and the distinctions that matter | [docs/00-project/GLOSSARY.md](docs/00-project/GLOSSARY.md) |
| How to propose a change, and what needs approval | [CONTRIBUTING.md](CONTRIBUTING.md) |
| The authoritative historical record | [all_lock.md](all_lock.md) |

Reuse what is already decided. The registry, the status document and the conflicts register exist so that you do not re-derive settled questions from `all_lock.md` — read them first, and go to `all_lock.md` for the exact locked text when you need it.

**`all_lock.md` is authoritative.** The `docs/` tree is the organized implementation reference derived from it. If they disagree, `all_lock.md` wins — and you must report the discrepancy rather than quietly following either one.

### Three traps in this repository

**1. A later Step document beats an older topic document.** Where both exist, the Step-numbered one is authoritative and the older one survives only as a record of what was true earlier. Four older files still read `NOT YET SPECIFIED` / `RECOMMENDED` for areas that are now locked — check the successor before concluding anything is undecided:

| Older file says "not specified" | Actually locked by |
|---|---|
| [AUTHENTICATION.md](docs/06-security/AUTHENTICATION.md) | [STEP_47_SECURITY_SPECIFICATION.md](docs/06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| [FRONTEND_ARCHITECTURE.md](docs/05-architecture/FRONTEND_ARCHITECTURE.md) | [STEP_52_FRONTEND_ARCHITECTURE.md](docs/05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) |
| [TEST_STRATEGY.md](docs/08-testing/TEST_STRATEGY.md) | [STEP_54_TESTING_STRATEGY.md](docs/08-testing/STEP_54_TESTING_STRATEGY.md) |
| [DEPLOYMENT.md](docs/09-implementation/DEPLOYMENT.md) | [STEP_55_DEPLOYMENT.md](docs/09-implementation/STEP_55_DEPLOYMENT.md) |

**2. Working documents are not specifications.** The reconciliation passes, scope audits, decision-finalization and external-reference audit files record *how* conclusions were reached. Their internal status lines describe the state at the time of writing and are now stale — several still say "45D NOT LOCKED" when 45D is locked. They carry a 📁 banner. Never implement from them; take the outcome from [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md).

**3. Decision IDs are the fastest way in.** Every locked decision has a stable ID; search the registry by prefix rather than reading `all_lock.md` end to end: `PROD` `ROLE` `LEGAL` `FIND` `DOC` `ENG` `AI` `ARCH` `DATA` `AUD` `LIABILITY` (Steps 1–45B) · `REC` (reconciliation) · `AM` (Amendment Batches AB-1 `AM-1`–`AM-21` and AB-2 `AM-22`–`AM-24`) · `SEC` (Step 47) · `API` `FE` `OBS` `TEST` `DEP` (Steps 49, 52–55) · `IMPL` (implementation authorization). Open items use `OD-*` (open decisions), `C-*` (conflicts), `F-*` (engineering resolutions).

⚠️ **`F-*` is overloaded.** [DECISION_FINALIZATION.md](docs/00-project/DECISION_FINALIZATION.md) §1 uses `F-1`–`F-12` for *engineering resolutions* (`F-3` = escalation recorded at Finding level, cited by `AM-23`), while [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state uses `F-1`/`F-3`/`F-4` for *code-review findings* (`F-3` = Mapping State not persisted). Two different `F-3`. Always name the document you mean; do not merge the two series without an owner decision.

---

## The twenty-two rules

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
18. **Security and ownership checks are server-side.** Authentication → Authorization → Business Operation → Database. Knowing an object's ID is never sufficient for access. The UI never implements legal evaluation logic and never talks to the database directly, and UI permission gating is presentation only.
    **Authentication never confers Legal Decision authority** (`SEC-01`), and no super-role bypass may ever reach `legal.decision` or `legal.approve_customization` (`SEC-02`, `ROLE-05`). Internal legal positions are permission-controlled and must not leak to ordinary users or counterparties (`LEGAL-02`); confidential fields are **omitted, not nulled**, and out-of-scope objects return a byte-identical 404 rather than disclosing existence (`SEC-07`, `API-10`).
19. **Do not make architectural changes for convenience.** The domain boundaries in [SYSTEM_ARCHITECTURE.md](docs/05-architecture/SYSTEM_ARCHITECTURE.md) are locked. No new technologies, dependencies, or services without approval.
20. **Treat `docs/` as the implementation specification.** Reference it rather than re-deriving decisions, and keep it in sync when the specification advances.

### Legal source material

21. **Ask for real legal source material — never manufacture it.** If implementation or validation requires real legal documents, representative contracts, company standards, or other legal source material that is not already in the repository, **stop and ask the owner for it explicitly before proceeding.** Do not invent legal content, and do not promote an arbitrary or illustrative example into production truth.

    This applies to golden-corpus fixtures, Company Standard and Legal Rule configuration, Requirement catalogues, mapping aliases and keyword groups, Step 35 threshold calibration, seed and demo data, and any test whose expected output asserts a legal conclusion.

    The worked examples throughout the specification — 6-month liability caps, Termination, Indemnification, Governing Law — are **illustrations of behavior, not the organization's legal positions**. Rule 7 forbids inventing a legal requirement; this rule closes the adjacent gap, where invented material arrives as *data* rather than as specification. Missing source material is a blocker to be raised, never a gap to be filled.

### The master record

22. **`all_lock.md` is append-only.** Never edit, reflow, reorder, reformat or delete a single existing line of it — not to fix a typo, not to correct a stale status block, not to apply an approved amendment. Every approved change is **appended** as a new lock record; superseded text stays exactly where it is and is annotated as superseded elsewhere. Twelve documents assert that prior line counts are byte-identical, and reproducibility of historical Reviews depends on that being true. The same discipline applies to every locked specification in `docs/`: supersede with a banner, never overwrite.

---

## Preserve the examples

The specification is full of worked examples — MATCH vs DEVIATION, RESOLVED ≠ MATCH, APPROVAL_REQUIRED, contract customization, evidence traceability, configuration snapshots, liability evaluation, multiple clauses, conflicting provisions. **These are deliberate.** They exist to show intended behavior precisely where prose is ambiguous.

Never delete an example to make a document shorter. Never "clean up" example values. When you add a specification, add worked examples in the same style.

---

## Document status labels

Every specification document declares its state. Never mix states without labeling them.

| Label | Meaning |
|-------|---------|
| 🔒 `LOCKED` | Settled. Requires explicit approval to change. |
| `PROVISIONAL` / `RECOMMENDED` | Proposed but not settled. Do not build on it as if it were final. |
| ⏳ `UNDER REVIEW` / `IN PROGRESS` | Actively being decided right now. |
| `PLANNED` / `NOT YET SPECIFIED` | Nothing has been decided. Do not invent it. |
| 📁 `ANALYSIS` / `PROPOSAL` | Working document. Records reasoning, decides nothing. Its status lines may be stale. |

Lifecycle state — specified · locked · implemented · tested · verified · blocked · production-ready — is tracked separately in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which is the only document that may assert build state. It is a documentation convention and must never share a field or enum with one of the five legal-domain state axes.

---

## What implementation authorization does and does not cover

`IMPL-01` (🔒 2026-08-17) authorizes implementation of the locked V1 specification, in the [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5 sequence. Its §6 standing constraints do **not** relax, and rules 1–22 above are unchanged.

**Authorized:** application code, database migrations, API endpoints, frontend components and test harnesses that realize a locked decision.

**Still requires explicit approval — `IMPL-01` grants none of it:**

* deciding anything marked `NOT YET SPECIFIED`
* resolving any open conflict (C-05–C-08, C-10, C-11) or open decision (`OD-*`)
* amending any locked decision
* adding any table, column or enum not covered by a lock record or an approved amendment batch
* authoring `NORMATIVE` golden-corpus fixtures — these need real representative contracts and the organization's real Company Standards, which **must be supplied, never manufactured** (rule 21)
* any technology, dependency or service beyond the Step 39 stack

**The code is not a specification.** A behavior appearing in the implementation does not make it decided. Where the code makes a choice the specification does not fix, that choice is an implementation detail recorded as such — it is not thereby locked. Conformance is verified against the locked corpus, never asserted by the implementation.

Documents under [docs/09-implementation/](docs/09-implementation/) still describe a *target*, not built work. **[IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) is the only document that may assert build state** — read its Build state table rather than inferring progress from the presence of code.

---

## Current state

**The V1 specification is complete.** Steps 1–45D, 47, 49 and 52–55, `REC-01`–`REC-07`, Amendment Batches AB-1 and AB-2, and `IMPL-01` are locked. `all_lock.md` is **15,093 lines**. Step 45E — Golden Corpus — is IN PROGRESS (64 fixtures specified, 6 authored, all `STRUCTURAL`).

**Implementation is authorized and underway.** For what is built, what is merely tested, and what blocks the VERIFIED state, read [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) — never `backend/README.md` or the code itself.

Two evaluators are specified: `LIABILITY-001` (`NUMERIC_COMPARISON`) and the generic `PRESENCE` evaluator. **No specific legal Requirement beyond `LIABILITY-001` is required by any locked decision** — Termination, Indemnification, Governing Law and the rest appear only in illustrative examples and are configuration, not specification — see [docs/04-analysis-engine/EDGE_CASES/](docs/04-analysis-engine/EDGE_CASES/).

**Before naming any state value, read [docs/02-legal-domain/DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md).** It is the canonical cross-layer reference for all five controlled state vocabularies. Mapping State, Finding Classification, Rule Outcome, Legal Decision, and Review Lifecycle are five separate axes and must never share a status field or enum — `AMBIGUOUS` in particular means three different things on three different layers.

Conflicts C-01–C-04 were reconciled on 2026-08-16 (`REC-01`–`REC-07`); **C-09 was resolved on 2026-08-17** by `IMPL-01` and AB-2. **Six remain open** in [CONFLICTS.md](docs/00-project/CONFLICTS.md): C-05–C-08 and C-11 (low severity) and **C-10 (MEDIUM)**. The `REC-*` decisions are recorded in `all_lock.md` under "Post-Step-44 Cross-Document Reconciliation Decisions".

The security track's `OD-1`–`OD-15` are open decisions, of which `OD-9` (authentication) was closed by Step 47. The rest are tracked in [EXTERNAL_REFERENCE_AUDIT.md](docs/00-project/EXTERNAL_REFERENCE_AUDIT.md) §16 — do not resolve one yourself.

---

## Working a session

1. **Re-check [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) against the tail of [all_lock.md](all_lock.md).** The master specification grows as steps are locked and the docs tree can lag behind it. `all_lock.md` is currently **15,093 lines**; if it is longer, the docs may be stale and you should say so.
2. **Look the question up before deriving it.** Registry → status → conflicts → glossary → the specification. Re-deriving a settled question from `all_lock.md` wastes the session and risks a different answer than the one that is locked.
3. **Ask when blocked; do not proceed on an assumption.** Stop and request a decision when the behavior is unspecified (rule 4), a locked decision would have to change (rule 6), two sources contradict (rule 5), or real legal source material is missing (rule 21). Deliver everything that does not depend on the answer, and state plainly what you left out and why.
4. **Keep the record in sync.** A specification change lands as one synchronized operation — `all_lock.md` appended, plus the registry, status, conflicts and every affected specification. Record repository changes in [CHANGELOG.md](CHANGELOG.md) and decisions in `all_lock.md` and the registry; the two are not interchangeable. When you add a document, add it to [docs/README.md](docs/README.md) in the same change.
5. **Say what you actually did.** Report a discrepancy you found even when it is inconvenient, and never describe work as complete when part of it was skipped or blocked.

**Approval is required for:** beginning implementation · changing any locked decision · resolving an open conflict or `OD-*` · adding a technology, dependency or service · altering a domain boundary · changing a golden-corpus expectation. [CONTRIBUTING.md](CONTRIBUTING.md) has the procedure and the six kinds of change.

Once implementation is authorized, the constraints in [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §6 do not relax, and the recommended build sequence is in §5.

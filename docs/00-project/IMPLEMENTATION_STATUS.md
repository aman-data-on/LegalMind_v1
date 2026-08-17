# Implementation Status

**This document records reality, never intent.** It is the authoritative answer to "what state is this in?" — no other document should assert build state.

**Project phase: IMPLEMENTATION.** The V1 specification is complete; implementation is **authorized** (`IMPL-01`, 2026-08-17) and underway.

Documents under [`09-implementation/`](../09-implementation/) remain *specifications of a target*. Where code and specification disagree, the specification wins — `IMPL-01` condition 1: *the code is not a specification.*

Last synchronized against `all_lock.md` at **15,093 lines** (Steps 1–45D, 47, 49, 52–55, `REC-01`–`REC-07`, Amendment Batches AB-1 and AB-2, Implementation Authorization).

---

## Build state

**Authorized 2026-08-17** (`IMPL-01`), recorded retroactively and not backdated: the build preceded the authorization and the lock record says so.

| Unit | Basis | State | Evidence |
|---|---|---|---|
| 1 · Database schema & migrations | Steps 41–42, AB-1, AB-2, Step 47 | IMPLEMENTED · TESTED | 30 tables; 21 invariant tests |
| 2 · Authentication & authorization | Step 47 | IMPLEMENTED · TESTED | 24 authorization + 15 session tests, 21 API authz tests |
| 3 · Document storage & ingestion | Step 34 | IMPLEMENTED · TESTED | 20 ingestion tests |
| 4 · Mapping layer | Steps 28, 35 | IMPLEMENTED · TESTED | 24 mapping + 5 mapping-service tests |
| 5 · Evaluation engine | Steps 44, 45A–45D | IMPLEMENTED · TESTED | 62 evaluation + 16 corpus tests |
| 6 · Decision & review workflow | Steps 4, 22, 30, 31 | IMPLEMENTED · TESTED | 28 workflow tests |
| 7 · HTTP API | Steps 43, 47, 49 | IMPLEMENTED · TESTED | 39 endpoints; 139 API tests |
| 8 · Frontend | Step 52 | IMPLEMENTED · TESTED | 10 of 10 locked 52.6 screens except export; 46 Vitest tests. **Playwright not set up** |
| 9 · Analysis orchestrator | Steps 28, 34, 35, 44 | IMPLEMENTED · TESTED | 20 orchestrator + 19 extraction tests |
| 10 · Golden corpus harness | Steps 45E, 54 | PARTIAL | 6 `STRUCTURAL` fixtures of 64 specified; **no `NORMATIVE` fixture exists** |
| 11 · Observability & deployment | Steps 53, 55 | PARTIAL | Step 53 observability implemented (26 tests); Step 55 preflight register + Dockerfiles + compose (19 tests). **Queue-backed workers, Playwright and CI not wired** |

Backend: **446 tests**. Frontend: **46 tests**. Both green.

**Nothing is VERIFIED or PRODUCTION-READY.** `TESTED` means automated tests exist and pass locally; it does not mean behavior has been confirmed against the specification independently of those tests.

### Pending ratification

`IMPL-01` condition 4 leaves these explicitly unratified. None is locked; each is open to revision without amending anything.

The `review_assignments` and `escalations` tables and Review ownership were previously listed here under `IMPL-01` condition 3. All three were **ratified on 2026-08-17 by Amendment Batch AB-2** (`AM-22`, `AM-23`, `AM-24`) and are no longer pending.

| Item | What it is | Why it needs approval |
|---|---|---|
| `D-1` mapping threshold | An absent `confirm_threshold` refuses at publish time, with a second check at analysis time | An `ENG-09` conformance choice; the *value* still needs 35.10 calibration |
| `D-2` Mapping State persistence | Recorded in `evaluations.result.evaluated_facts`; both evaluators write it | `REC-03` calls the states "persisted" but no locked table carries them |
| `D-3` Requirement applicability | `company_standard_versions.configuration` → `{"applicability": …}`, failing closed to `REQUIRED` | Locked Step 28 lists "Required / Optional"; nothing sourced it |
| `D-4` `UNMATCHED_PROVISION` | The orchestrator writes no rows | `REC-02` defers persistence and surfacing |
| `M-2` mapping `AMBIGUOUS` semantics | Tied supporting clauses are `CONFIRMED` and all retained (Step 28 r2, 35.12); contradiction is caught by the conflict evaluator, producing `CONFLICT` / `DECISION_REQUIRED` | Interprets what locked Step 28's `AMBIGUOUS` means. **Consequence: nothing in V1 produces `MappingState.AMBIGUOUS`** — cross-Requirement ambiguity detection is unimplemented and no producer was invented |
| `tie_margin` | Unread since `M-2`; audited as unused and safe to remove, retained pending owner review | Removal is a configuration-shape change; evidence in [ANALYSIS_ORCHESTRATOR_GAP.md](../04-analysis-engine/EDGE_CASES/ANALYSIS_ORCHESTRATOR_GAP.md) §9 |
| `POST /reviews/{id}/analyze` permission | Mapped to `review.create` | Locked 49.3's table has no analysis row, though 49.8 and 49.10 presuppose the endpoint |
| Second-person approval mechanism | Co-signature within the append-only decision chain | Step 31 r15 permits the requirement without specifying the mechanism |

### Blocking the VERIFIED state

| ID | Item | Severity |
|---|---|---|
| **F-1** | EV-MIN was enforced `AFTER INSERT` on `findings` only, so deleting the last Evaluation orphaned the Finding undetected | ✅ **FIXED 2026-08-17** — migration `9c2f41ab77e3` adds `AFTER DELETE` and `AFTER UPDATE` constraint triggers on `evaluations`, both `DEFERRABLE INITIALLY DEFERRED`. 5 new invariant tests; the preflight verifies all three triggers exist. Migration round-trips twice cleanly |
| **F-3** | Mapping State (axis 1) has no column or enum | ✅ **ANSWERED by `D-2`** — the owner chose JSONB persistence in `evaluations.result.evaluated_facts`, written by **both** evaluators, so a replay can show what mapping concluded. Recorded under Pending ratification rather than left as a blocker |
| **F-4** | **Test suite non-determinism.** ⚙️ **Fixed and verified 2026-08-17** — see below |
| **45E** | Golden corpus is 6 of 64 fixtures, all `STRUCTURAL`. `NORMATIVE` fixtures require real representative contracts and real Company Standards, which must be supplied | Release gate |
| — | **No analysis calibration.** Mapping weights and thresholds are uncalibrated; locked 35.10 requires validation against a representative contract test set | Release gate |
| — | **Playwright not set up.** Locked Step 39/54 make it the browser-workflow tier | Outstanding in unit 11 |
| — | **Analysis runs synchronously in the API.** Locked 55.1 makes it a worker job on the same image; Celery/Redis are in the locked Step 39 stack and the compose file provisions the queue, but no consumer is wired. The orchestrator is a plain service function so moving it changes the caller, not the analysis | Outstanding in unit 11 |
| — | **No CI pipeline.** Locked 55.5 fixes the release sequence and 55.6 records CI/CD tooling as NOT YET SPECIFIED, so the sequence exists as `python -m legalmind.deploy.preflight` plus the test suites rather than as a pipeline definition | Owner decision on tooling |
| — | **`GET /auth/oidc/*` and `POST /reviews/{id}/export` not implemented.** OIDC needs an approved JWT/JWKS dependency plus IdP configuration; export formats are locked NOT YET SPECIFIED | Recorded in `api/permission_map.py` `NOT_IMPLEMENTED` |

#### `F-4` — what was wrong, what was done, how it was checked

The *symptom* was real; the *recorded diagnosis* was not. Two checks disproved it:

* the suite runs green with `LEGALMIND_DATABASE_URL` pointed at a nonexistent host, so nothing in the test path opens the dev database — `api/deps.py`'s lazy engine is never constructed, because `get_db` is overridden by the harness;
* the actual mechanism was that every run shared the `public` schema and reset it with `DROP SCHEMA public CASCADE`. A backend left by an interrupted run held locks, so the reset raced and sometimes left a half-built schema. An intermediate fix using `pg_terminate_backend` then killed the *live* connections of any concurrent suite — `SSL connection has been closed unexpectedly` in whichever process lost. **The second failure mode was introduced by the fix for the first.**

Each run now migrates into a schema private to that process (`t_<epoch>_<random>`), points `search_path` at it for both its own connections and Alembic's, and drops only that schema at teardown. Nothing is terminated. A conservative sweep drops run schemas older than six hours, so debris from a crashed run cannot accumulate indefinitely while a live run — seconds old — is never a candidate. `test_each_axis_has_its_own_enum_type` was scoped to `current_schema()` in the same change; unscoped, it counted identically-named enum types belonging to other runs.

Verification, by concurrency rather than by assertion — the shared-schema design could not survive any of these:

| Check | Result |
|---|---|
| Four concurrent full suites | 4 × `385 passed` |
| Staggered starts, so one run's setup overlaps another's teardown | 4 × `385 passed` |
| A run `kill -9`'d mid-suite, then a clean run | `385 passed` |
| Ten sequential runs | 10 × `385 passed` |
| Suite with the dev database URL pointed at a nonexistent host | `385 passed` |
| A run against a freshly emptied database | `385 passed` |

**24 consecutive clean runs, including 8 concurrent.** This is the author's verification, not an independent one: the row stays visible so CI or a reviewer can confirm it (`IMPL-01` condition 2). The run counts above are the suite size at the time of that verification; the suite has since grown to 446.

---

## Status vocabulary

These seven states describe *lifecycle*. They are a documentation convention only — they are **not** one of the five controlled legal-domain state axes in [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) and must never share a field or enum with one.

| State | Meaning | Evidence required |
|---|---|---|
| **SPECIFIED** | The behavior is written down and internally consistent, but not settled — `PROVISIONAL` or `UNDER REVIEW` | A specification document |
| 🔒 **LOCKED** | Settled. Changing it requires explicit owner approval | An entry in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) and a lock record in `all_lock.md` |
| **IMPLEMENTED** | Code exists that realizes the locked specification | Merged code, referencing the decision IDs it implements |
| **TESTED** | Automated tests cover it, including its golden-corpus fixtures where applicable | Passing tests in CI |
| **VERIFIED** | Behavior confirmed against the specification, not merely against the tests — the golden-corpus expectations hold and the explainability chain reconstructs | A recorded verification run |
| **BLOCKED** | Cannot advance until a named decision or dependency resolves | The blocking ID (`OD-*`, `C-*`, `N-*`) |
| **PRODUCTION-READY** | Verified, plus the deployment blockers register is clear | [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) §55.6 |

Build state is reported in the **Build state** table above, which is the only place in this repository that asserts it. The table below reports **specification status only** — a row reading LOCKED there says the decision is settled, never that code exists for it.

---

## Current step

| | |
|---|---|
| **Steps 1–44** | 🔒 LOCKED |
| **Step 45A — LIABILITY-001** | 🔒 LOCKED |
| **`REC-01`–`REC-07`** | 🔒 LOCKED (reconciliation) |
| **Amendment Batch AB-1** | 🔒 LOCKED |
| **Step 45B — Evaluator Data Contract** | 🔒 LOCKED (revised — `REC-05`, `REC-07`, AB-1) |
| **Step 45C — Liability Edge Cases** | 🔒 LOCKED |
| **Step 45D — Cross-Evaluator Edge Cases** | 🔒 LOCKED |
| **Step 45E — Golden Corpus** | ⏳ IN PROGRESS — [64 fixtures specified](../08-testing/GOLDEN_CORPUS_45E.md) |
| **Amendment Batch AB-2** | 🔒 LOCKED — `AM-22` `review_assignments`, `AM-23` `escalations`, `AM-24` Review ownership |
| **Implementation Readiness Gate** | ✅ [PASSED](../09-implementation/IMPLEMENTATION_READINESS_GATE.md) — all nine criteria met |
| **Implementation Authorization** | 🔒 LOCKED (`IMPL-01`, 2026-08-17) — retroactive, not backdated; see **Build state** above |


The master specification's closing position (`all_lock.md`, "Current position"):

> **The V1 specification is complete.** Remaining work is corpus authoring and implementation.

Two evaluators are specified: `LIABILITY-001` (`NUMERIC_COMPARISON`) and the generic `PRESENCE` evaluator. **No specific legal Requirement beyond `LIABILITY-001` is required by any locked decision.**

---

## Specification status by area

| Area | Status | Canonical documents |
|------|--------|---------------------|
| Product requirements & scope | LOCKED | [01-product/](../01-product/) |
| Roles & permissions | LOCKED | [USER_ROLES.md](../01-product/USER_ROLES.md) |
| Review lifecycle & workflow | LOCKED | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| Legal analysis philosophy & AI boundary | LOCKED | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |
| Company Standards & configuration versioning | LOCKED | [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) |
| Legal Rules & clause library | LOCKED | [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md) |
| Finding classification | LOCKED — canonicalized (`REC-01`) | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| **Decision State Model (five axes)** | LOCKED (`REC-06`) | [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) |
| Legal Decisions & approval | LOCKED | [LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md) |
| Document model & types | LOCKED | [DOCUMENT_MODEL.md](../03-document-model/DOCUMENT_MODEL.md) |
| Document versioning | LOCKED (Step 26) / **PROVISIONAL elaboration (Step 33, `REC-04`)** | [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) |
| Evidence model | LOCKED | [EVIDENCE_MODEL.md](../03-document-model/EVIDENCE_MODEL.md) |
| Ingestion & processing pipeline | LOCKED | [PROCESSING_PIPELINE.md](../03-document-model/PROCESSING_PIPELINE.md) |
| Analysis engine architecture | LOCKED | [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) |
| Requirement mapping | LOCKED (**thresholds provisional**) | [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| Fact extraction | LOCKED | [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md) |
| Rule engine | LOCKED | [RULE_ENGINE.md](../04-analysis-engine/RULE_ENGINE.md) |
| Conflict detection | LOCKED | [CONFLICT_DETECTION.md](../04-analysis-engine/CONFLICT_DETECTION.md) |
| Explainability | LOCKED | [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md) |
| System architecture & domains | LOCKED | [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md) |
| Technology stack | LOCKED (stack table only) | [BACKEND_ARCHITECTURE.md](../05-architecture/BACKEND_ARCHITECTURE.md) |
| Frontend architecture | 🔒 LOCKED (Step 52) | [FRONTEND_ARCHITECTURE.md](../05-architecture/FRONTEND_ARCHITECTURE.md) |
| API architecture | LOCKED (Step 43) + Step 49 specified | [API_ARCHITECTURE.md](../05-architecture/API_ARCHITECTURE.md) |
| Database domain model & schema | LOCKED | [DATABASE_ARCHITECTURE.md](../05-architecture/DATABASE_ARCHITECTURE.md) |
| Exact schema & ERD | LOCKED (+ AB-1, AB-2) | [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) |
| Storage architecture | LOCKED (responsibilities) | [STORAGE_ARCHITECTURE.md](../05-architecture/STORAGE_ARCHITECTURE.md) |
| Authorization & ownership | LOCKED | [AUTHORIZATION.md](../06-security/AUTHORIZATION.md), [OWNERSHIP.md](../06-security/OWNERSHIP.md) |
| Security model | LOCKED (boundaries) | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| Authentication | 🔒 LOCKED — OIDC primary, password fallback (OD-9) | [STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| **Step 47 — Security/Authn/Authz** | 🔒 LOCKED | [STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| **Step 49 — API Finalization** | 🔒 LOCKED | [STEP_49_API_FINALIZATION.md](../05-architecture/STEP_49_API_FINALIZATION.md) |
| **Step 52 — Frontend Architecture** | 🔒 LOCKED | [STEP_52_FRONTEND_ARCHITECTURE.md](../05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) |
| **Step 53 — Observability** | 🔒 LOCKED | [STEP_53_OBSERVABILITY.md](../09-implementation/STEP_53_OBSERVABILITY.md) |
| **Step 54 — Testing Strategy** | 🔒 LOCKED | [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md) |
| **Step 55 — Deployment** | 🔒 LOCKED | [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) |
| Audit trail | LOCKED | [AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md) |
| Reproducibility | LOCKED | [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md) |
| Test strategy, golden corpus, regression | 🔒 LOCKED (Step 54) | [08-testing/](../08-testing/) |
| `LIABILITY-001` evaluator policy | LOCKED | [LIABILITY.md](../04-analysis-engine/EDGE_CASES/LIABILITY.md) |
| `LIABILITY-001` evaluator data contract | 🔒 LOCKED (revised, AB-1) | [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) |
| `PRESENCE` generic evaluator | 🔒 LOCKED (Step 45D) | [PRESENCE_EVALUATOR.md](../04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md) |
| Cross-evaluator structural contract | 🔒 LOCKED (Step 45D) | [EVALUATOR_EDGE_CASES.md](../04-analysis-engine/EVALUATOR_EDGE_CASES.md) |
| Liability edge cases | 🔒 LOCKED (Step 45C) | [LIABILITY_EDGE_CASES.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EDGE_CASES.md) |
| Termination / Indemnification / Governing Law evaluators | **NOT YET SPECIFIED** | [EDGE_CASES/](../04-analysis-engine/EDGE_CASES/) |
| Deployment / infrastructure | 🔒 LOCKED (Step 55) | [09-implementation/](../09-implementation/) |

---

## Explicitly NOT YET SPECIFIED

Do not assume, infer, or invent any of the following. Each requires its own specification step and approval.

**Legal domain**
* Every requirement evaluator other than `LIABILITY-001` — including Termination, Indemnification, Governing Law
* Risk classification rules
* Regulatory reference workflow (DPDP Act, IT Act, GDPR, etc. as *applied* rules)
* Exact legal approval thresholds beyond those locked in `LIABILITY-001`

**Product**
* Exact customization workflow
* Export formats and delivery
* UI/UX design

**Deliberately deferred by owner decision (2026-08-16)**
* The scoring-band → mapping-state mapping — how Step 35's `CANDIDATE-REVIEW` / `NOT MAPPED` / `NO_CONFIDENT_MAPPING` map onto Step 28's `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED`. **Do not infer it.**
* The shape and contents of `rule_configuration` (named in 45B.9, never specified)
* Persistence, surfacing, and review treatment of `UNMATCHED_PROVISION` observations
* The three Step 33 rules with no Step 26 counterpart (sequential version numbering, invalid/withdrawn semantics, predecessor chain)

**Technical**
* Authentication implementation, and integration with any existing authentication system or API
* Exact API endpoint naming (explicitly excluded from the Step 38.24 lock)
* `document_evidence.source_type` and `legal_decisions.decision_type` enum values ("finalized during implementation")
* Step 35 numerical scoring weights and thresholds (explicitly illustrative, pending a representative contract test set)
* Object-storage provider/layout, retention and encryption key management
* Deployment orchestration beyond the Step 39 recommended shape
* Implementation sequencing and milestones

---

## Conflicts

**C-01 through C-04 were reconciled on 2026-08-16** (`REC-01`–`REC-06`). None was a true contradiction. The finding-type enum is no longer blocked: the Step 36 seven-value set is canonical for Finding Classification, and `EXTRA`/`ADDITIONAL` became the document-level `UNMATCHED_PROVISION` observation.

**C-09 was resolved on 2026-08-17** by `IMPL-01` and Amendment Batch AB-2 — implementation authorized retroactively, with the lock record stating plainly that the work preceded the authorization; `review_assignments` and `escalations` ratified as `AM-22` and `AM-23`; Review ownership resolved by `AM-24`. The technical findings that review surfaced are **not** closed by it — they are tracked under **Blocking the VERIFIED state** above.

Four low-severity items remain open (C-05–C-08), tracked in [CONFLICTS.md](CONFLICTS.md), along with **C-10** (MEDIUM — the `roles` seed list vs the canonical role matrix).

One item was **deliberately left unspecified**: the scoring-band → mapping-state mapping (C-02 sub-item). Do not infer it.

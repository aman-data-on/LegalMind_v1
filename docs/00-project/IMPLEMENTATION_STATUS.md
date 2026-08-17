# Implementation Status

**This document records reality, never intent.** It is the authoritative answer to "what state is this in?" — no other document should assert build state.

**Project phase: IMPLEMENTATION.** The V1 specification is complete; implementation is **authorized** (`IMPL-01`, 2026-08-17) and underway.

Documents under [`09-implementation/`](../09-implementation/) remain *specifications of a target*. Where code and specification disagree, the specification wins.

Last synchronized against `all_lock.md` at **15,093 lines** (Steps 1–45D, 47, 49, 52–55, `REC-01`–`REC-07`, Amendment Batches AB-1 and AB-2, Implementation Authorization).

---

## Build state

**Authorized 2026-08-17** (`IMPL-01`). First commit of the implementation: `0730d39`.

| Unit | Basis | State | Evidence |
|---|---|---|---|
| 1 · Database schema & migrations | Steps 41–42, AB-1, AB-2, Step 47 | IMPLEMENTED · TESTED | 30 tables; invariant tests |
| 2 · Authentication & authorization | Step 47 | IMPLEMENTED · TESTED | service-layer + API authz tests |
| 3 · Document storage & ingestion | Step 34 | IMPLEMENTED · TESTED | ingestion tests |
| 4 · Mapping layer | Steps 28, 35 | IMPLEMENTED · TESTED | mapping tests |
| 5 · Evaluation engine | Steps 44, 45A–45D | IMPLEMENTED · TESTED | evaluation + corpus tests |
| 6 · Decision & review workflow | Steps 4, 22, 30, 31 | IMPLEMENTED · TESTED | workflow tests |
| 7 · HTTP API | Steps 43, 47, 49 | IMPLEMENTED · TESTED | 38 endpoints; API tests |
| 8 · Golden corpus harness | Steps 45E, 54 | PARTIAL | 6 `STRUCTURAL` fixtures of 64 specified; **no `NORMATIVE` fixture exists** |
| 9 · Frontend | Step 52 | IMPLEMENTED · TESTED | Next.js + TypeScript; all ten 52.6 screens except export; 46 Vitest tests. **Playwright is not set up** — browser-level workflow testing belongs to unit 10 |
| 10 · Observability & deployment | Steps 53, 55 | NOT STARTED | — |

**Nothing is VERIFIED or PRODUCTION-READY.** `TESTED` here means automated tests exist and pass locally; it does not mean behavior has been confirmed against the specification independently of those tests.

### Blocking the VERIFIED state

| ID | Item | Severity |
|---|---|---|
| **F-1** | EV-MIN is enforced `AFTER INSERT` on `findings` only. No trigger on `evaluations` — deleting the last Evaluation orphans the Finding, undetected. `F-5` chose a database trigger precisely because a migration or backfill can bypass service code | HIGH |
| **F-3** | **Mapping State (axis 1) is not persisted.** No `mapping_state` column or enum exists. `ENG-01`/`REC-03` describe `CONFIRMED`/`AMBIGUOUS`/`UNRESOLVED` as the canonical *persisted* states, and a replay cannot show what mapping concluded | MEDIUM — needs an owner ruling, not a patch |
| **F-4** | **The test suite is non-deterministic.** Five identical runs produced 0, 2, 3 and 62 errors. Recorded diagnosis: `api/deps.py` builds a module-global engine against the *dev* database while `conftest` drops and rebuilds the *test* schema | ⚙️ **Fix landed 2026-08-17 — awaiting independent verification.** See below |
| **45E** | Golden corpus is 6 of 64 fixtures, all `STRUCTURAL`. `NORMATIVE` fixtures require real representative contracts and real Company Standards, which must be supplied | Release gate |

**`F-4` — what the fix was, and why the recorded diagnosis was wrong.**

The *symptom* was real; the stated *mechanism* was not. Two checks:

* The suite runs green with `LEGALMIND_DATABASE_URL` pointed at a nonexistent host. Nothing in the test path opens the dev database — `api/deps.py`'s lazy engine is never constructed, because `get_db` is overridden by the harness.
* The actual mechanism was that every run shared the `public` schema and reset it with `DROP SCHEMA public CASCADE`. A backend left behind by an interrupted run held locks, so the reset raced and sometimes left a half-built schema. An intermediate fix that cleared those locks with `pg_terminate_backend` then killed the *live* connections of any concurrently running suite — surfacing as `SSL connection has been closed unexpectedly` in whichever process lost. The second failure mode was introduced by the fix for the first.

Each run now migrates into a schema private to that process (`t_<random>`), points `search_path` at it for both its own connections and Alembic's, and drops only that schema at teardown. No process touches another's objects and nothing is terminated. `test_each_axis_has_its_own_enum_type` was scoped to `current_schema()` in the same change — unscoped, it counted identically-named enum types belonging to other runs.

Evidence: two suites run concurrently both report `339 passed`, which was previously impossible. The row stays open because a fix asserted by its own author is not a verification (`IMPL-01` condition 2).

### Also blocking VERIFIED, recorded 2026-08-17

| Item | Detail |
|---|---|
| **No analysis orchestrator** | Nothing joins mapping → fact extraction → evaluation into "analyse this Review". Fact extraction from evidence does not exist (`LiabilityFacts` is only constructed by the corpus runner), and Step 35's scoring-band → mapping-state mapping is **deliberately deferred by owner decision** and must not be inferred. Consequence: a Review created through the API or the UI stays in `DRAFT` and never acquires Findings. Every Finding-facing surface is therefore exercised against fixtures, not against a real analysis run. |
| **Playwright not set up** | Locked Step 39 and Step 54 make Playwright the browser-workflow tier. It needs browser binaries and a running stack; deferred to unit 10 with CI. Frontend coverage is currently Vitest rendering and source-level assertions only. |
| **`GET /auth/oidc/*` and `POST /reviews/{id}/export` not implemented** | Both are locked 49.3 endpoints. OIDC needs a JWT/JWKS client dependency (approval required) plus IdP configuration; export formats are locked NOT YET SPECIFIED. Recorded in `backend/legalmind/api/permission_map.py` under `NOT_IMPLEMENTED`. |

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
| **Implementation Authorization** | 🔒 LOCKED (`IMPL-01`, 2026-08-17) — recorded retroactively; see **Build state** above |


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

**C-09 was resolved on 2026-08-17** by `IMPL-01` and Amendment Batch AB-2 — implementation authorized retroactively, with the lock record stating plainly that the work preceded the authorization; `review_assignments` and `escalations` ratified as `AM-22` and `AM-23`; Review ownership resolved by `AM-24`. The three technical findings that review surfaced are **not** closed by it — they are tracked under **Blocking the VERIFIED state** above.

Four low-severity items remain open (C-05–C-08), tracked in [CONFLICTS.md](CONFLICTS.md), along with **C-10** (MEDIUM — the `roles` seed list vs the canonical role matrix).

One item was **deliberately left unspecified**: the scoring-band → mapping-state mapping (C-02 sub-item). Do not infer it.

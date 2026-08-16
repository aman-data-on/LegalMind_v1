# Implementation Status

**Project phase: SPECIFICATION / DESIGN.**

**No implementation has begun. No application code, database migration, API endpoint, frontend component, or infrastructure exists in this repository.**

The presence of documents under [`09-implementation/`](../09-implementation/) does **not** mean implementation has started. Those documents are *specifications of a target*, not records of built work.

Last synchronized against `all_lock.md` at **13,941 lines** (Steps 1–45B + the appended "Post-Step-44 Cross-Document Reconciliation Decisions" section, `REC-01`–`REC-07`).

---

## Current step

| | |
|---|---|
| **Steps 1–44** | 🔒 LOCKED |
| **Step 45A — LIABILITY-001** | 🔒 LOCKED |
| **`REC-01`–`REC-07`** | 🔒 LOCKED (reconciliation) |
| **Step 45B — Evaluator Data Contract** | 🔒 LOCKED (incl. `REC-05` R1 + `REC-07`) |
| **Step 45C — Liability Edge Cases** | ⏳ IN PROGRESS — triage complete, decisions pending |

The master specification's closing recommendation:

> **I recommend locking 45B after one final check, then moving to 45C — Liability Edge Cases.** That is where we test whether this contract survives the difficult real-world cases: multiple caps, carve-outs, per-claim vs aggregate caps, different monetary bases, cross-references, conflicting schedules, and malformed/ambiguous clauses.

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
| Frontend architecture | RECOMMENDED / thin | [FRONTEND_ARCHITECTURE.md](../05-architecture/FRONTEND_ARCHITECTURE.md) |
| API architecture | LOCKED | [API_ARCHITECTURE.md](../05-architecture/API_ARCHITECTURE.md) |
| Database domain model & schema | LOCKED | [DATABASE_ARCHITECTURE.md](../05-architecture/DATABASE_ARCHITECTURE.md) |
| Exact schema & ERD | LOCKED (spec only, unbuilt) | [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) |
| Storage architecture | LOCKED (responsibilities) | [STORAGE_ARCHITECTURE.md](../05-architecture/STORAGE_ARCHITECTURE.md) |
| Authorization & ownership | LOCKED | [AUTHORIZATION.md](../06-security/AUTHORIZATION.md), [OWNERSHIP.md](../06-security/OWNERSHIP.md) |
| Security model | LOCKED (boundaries) | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| Authentication | **PARTIALLY SPECIFIED** | [AUTHENTICATION.md](../06-security/AUTHENTICATION.md) |
| Audit trail | LOCKED | [AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md) |
| Reproducibility | LOCKED | [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md) |
| Test strategy, golden corpus, regression | LOCKED (corpus mandatory) | [08-testing/](../08-testing/) |
| `LIABILITY-001` evaluator policy | LOCKED | [LIABILITY.md](../04-analysis-engine/EDGE_CASES/LIABILITY.md) |
| `LIABILITY-001` evaluator data contract | 🔒 LOCKED | [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) |
| Termination / Indemnification / Governing Law evaluators | **NOT YET SPECIFIED** | [EDGE_CASES/](../04-analysis-engine/EDGE_CASES/) |
| Implementation plan & deployment | **NOT YET SPECIFIED** | [09-implementation/](../09-implementation/) |

---

## Explicitly NOT YET SPECIFIED

Do not assume, infer, or invent any of the following. Each requires its own specification step and approval.

**Legal domain**
* Every requirement evaluator other than `LIABILITY-001` — including Termination, Indemnification, Governing Law
* Step 45C liability edge-case *resolutions* — triage is complete (see [LIABILITY_EDGE_CASES.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EDGE_CASES.md)); no edge case is yet decided
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

Four low-severity items remain open (C-05–C-08), tracked in [CONFLICTS.md](CONFLICTS.md).

One item was **deliberately left unspecified**: the scoring-band → mapping-state mapping (C-02 sub-item). Do not infer it.

# Locked Decision Registry

**This registry lists ONLY decisions the master specification explicitly locks.**

Authoritative source: [`all_lock.md`](../../all_lock.md) — the historical master specification. This registry is an index into it, not a replacement for it. Where this registry and `all_lock.md` disagree, **`all_lock.md` wins** and the discrepancy must be reported, not silently resolved.

## How to read this registry

* **Status: LOCKED** — the master specification explicitly locks this. Do not change it without following the approval process in [CLAUDE.md](../../CLAUDE.md).
* Provisional, recommended, and not-yet-specified items are **deliberately excluded** from this registry. They are tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
* "Source Step" is the step number in `all_lock.md` that locked the decision.
* "Canonical Document" is where the full text, rules, and worked examples live. Substance is not reproduced here.

---

## R. Reconciliation & canonicalization decisions

These decisions were made by the project owner during a cross-step reconciliation session on **2026-08-16**. They are recorded in [`all_lock.md`](../../all_lock.md) under **"Post-Step-44 Cross-Document Reconciliation Decisions"** (appended after Step 45B; the original 13,512 lines are byte-identical and unmodified). They resolve *how existing locked decisions relate to each other*; they do not overturn any locked rule.

| ID | Decision | Status | Source | Canonical Document |
|----|----------|--------|--------|--------------------|
| REC-01 | **Finding Classification supersession chain.** Steps 18 → 27 → 36 are a supersession chain, not a contradiction. The **Step 36 seven-value set** is canonical for Finding Classification (axis 2). Steps 18 and 27 remain locked and unmodified; their vocabularies are annotated as superseded, and their behavioral *rules* remain in force. | LOCKED | Owner, 2026-08-16 (ratifying Step 45A §17) | [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md), [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| REC-02 | **`UNMATCHED_PROVISION`.** `ADDITIONAL` (Step 18) and `EXTRA` (Step 27) are superseded by a **document-level `UNMATCHED_PROVISION` observation**, which is **not** a Finding Classification and must never occupy a Finding's `classification` field. The prior locked rules (not automatically negative; retains evidence; does not determine acceptability) carry over unchanged. | LOCKED | Owner, 2026-08-16 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md), [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) |
| REC-03 | **Mapping State canonicalization.** Step 28's `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED` are the canonical **persisted** mapping states (axis 1). Step 35's band names are internal scoring-stage labels whose weights/thresholds remain PROVISIONAL. | LOCKED | Owner, 2026-08-16 | [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| REC-04 | **Step 33 classification.** Step 33 is a **PROVISIONAL elaboration of locked Step 26**, not a conflict — verified rule-by-rule with no contradiction found. Three Step 33 rules have no Step 26 counterpart and remain unlocked. | LOCKED (classification) | Owner, 2026-08-16 | [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) |
| REC-05 | **Step 45B corrections (R1).** Restore `rule_configuration` to the complete input; add `extraction_diagnostics` alongside `extraction_status`; ratify `cap_status` and `NOT_APPLICABLE` as improvements over 45A. Incorporated into the 45B lock. | LOCKED | Owner, 2026-08-16 | [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) |
| REC-06 | **Five-Axis Decision State Model** established as the canonical cross-layer reference for every controlled state vocabulary. No axis may share an enum with another. | LOCKED | Owner, 2026-08-16 | [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) |
| REC-07 | **`extraction_diagnostics` is PERSISTED** as part of the evaluation/evidence record for auditability and reproducibility. It is diagnostic metadata only and **cannot independently produce or alter a legal finding**. | LOCKED | Owner, 2026-08-16 | [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md), [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md) |

---

## AB. Amendment Batch AB-1 — Evaluator & Decision Model

**Approved and locked 2026-08-17.** Recorded in [`all_lock.md`](../../all_lock.md) under "Amendment Batch AB-1". Representational repair only — no legal policy changed. Every amendment fixes a case where a **locked requirement could not be represented by the locked schema**.

| ID | Target | Amendment | Driver |
|----|--------|-----------|--------|
| AM-1 | 40.12 / 41.21 / 42.17 | `legal_decisions.evaluation_id NOT NULL` + composite FK `(finding_id, evaluation_id)` | A decision resolves one scoped Evaluation |
| AM-12 | 42.17 | `version_number` + `UNIQUE(evaluation_id, version_number)` — append-only supersession | Implements Step 31 r14/r20, which are **not** amended |
| AM-15 | 42.17 | `justification TEXT NOT NULL` (was nullable `decision_text`) | Step 31 r11 was unenforced |
| AM-13 / AM-14 | 41.21 / 40.12 | Aligned to the canonical record | Consistency |
| AM-8′ | 42.15 | `scope_key`, `scope_label`, `evaluation_kind`, `rule_outcome` | Scoped evaluations; rule outcome at Evaluation level only |
| AM-19 | 42.15 | `evaluator_version NOT NULL` | Locked 45B.10 required it; no column existed |
| AM-20 | 42.15 | `legal_rule_version_id` FK → `legal_rule_versions` | Step 32 audit q4 was unanswerable |
| AM-16 | 42.7 / 42.11 / 42.15 | `EVALUATOR_TYPE` defined: `NUMERIC_COMPARISON`, `PRESENCE` | Enum was `NOT NULL` and undefined |
| AM-2 / AM-5 / AM-6 | Step 31 r17 / r4 / r16 | Decisions resolve Evaluations; Finding resolution derived | Evaluation-level decision model |
| AM-7 | Step 36.7 | Workflow language removed from an analytical classification | 44.22 **not** amended — distinct axes |

**New tables (no amendment):** `evaluation_evidence` (zero rows permitted), `unmatched_provisions` (REC-02).

**Withdrawn as redundant:** AM-18 (`standard_kind` — determined by `evaluator_type` + 42.8 JSONB), AM-21 (derivable via configuration snapshot), A-2-as-schema-change (a 42.8 JSONB key).

**Engineering resolutions recorded (F-1 – F-10):** optional Requirement absent → no Finding · second-person approval at Evaluation level · escalation at Finding level · configuration may only widen decision requirements · 45C.22 narrowed to configured precedence · risk is a configured reporting display mapping · alignment is a reporting aggregation.

---

## S47. Step 47 — Security / Authentication / Authorization

**Locked 2026-08-17.** Record in [`all_lock.md`](../../all_lock.md) under "Step 47 — LOCK RECORD". No locked decision amended; two new tables (`sessions`, `user_identities`).

| ID | Decision | Status | Source | Canonical Document |
|----|----------|--------|--------|--------------------|
| SEC-01 | **OD-9 — Authentication.** Corporate SSO via OIDC primary; password fallback. Server-side sessions; session carries `user_id` only; authority resolved fresh per request; immediate revocation. Stateless JWT rejected. **The authentication mechanism never confers Legal Decision authority.** | LOCKED | Owner, 2026-08-17 | [STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| SEC-02 | **Super-role boundary.** A bypass may cover administrative permissions but MUST exclude `legal.decision` and `legal.approve_customization`, enforced in the resolver | LOCKED | Step 23, ROLE-05 | same |
| SEC-03 | **Multi-role, union semantics.** Legal Decision Authority carried as an additional role assignment — how two users with the same primary role differ (Step 4) | LOCKED | 42.3, Step 4 | same |
| SEC-04 | **Permission catalogue** — 11 groups; default grants mapped to Step 23's locked role summary; additions never auto-granted to non-super roles | LOCKED | Step 23 | same |
| SEC-05 | **Legal Decision authority separation.** Explicit grant only; `legal.review` does not confer it; checked at Evaluation level; second-person approval at Evaluation level; never zero authorities | LOCKED | Steps 4, 23, 31 | same |
| SEC-06 | **Object-level authorization** — Decision → Evaluation → Finding → Review → Contract → owner/scope. Knowing an ID is never sufficient | LOCKED | 41.24, 43.23, Step 24 | same |
| SEC-07 | **Denial semantics** — 401 / 404 (out-of-scope, existence not disclosed) / 403 / 409 / 422 | LOCKED | 41.24, LEGAL-02, 43.22 | same |
| SEC-08 | **Security invariants S-1 – S-10** | LOCKED | Step 39, 43.26 | same |
| SEC-09 | **Auth/security events** recorded in the existing locked `audit_events`; no new audit table; `actor_id` null pre-authentication | LOCKED | 42.18, AUD-01 | same |

---

## S49–55. API, Frontend, Observability, Testing, Deployment

**Locked 2026-08-17.** Records in [`all_lock.md`](../../all_lock.md). **No schema impact; no locked decision amended.**

| ID | Decision | Status | Canonical Document |
|----|----------|--------|--------------------|
| API-10 | **Step 49 — API Finalization.** Per-endpoint permission mapping; denial semantics (401/403/404/409/422/429) with byte-identical 404s; Evaluations nested under Findings; derived summary never returned alone; confidential fields omitted not nulled; decisions versioned via create-only with 409 on collision; page_size clamped; `X-Request-Id` correlation | LOCKED | [STEP_49_API_FINALIZATION.md](../05-architecture/STEP_49_API_FINALIZATION.md) |
| FE-01 | **Step 52 — Frontend.** No UI→DB; no UI legal logic; permission gating presentation-only; omitted confidential fields render as absent; decision controls at Evaluation level | LOCKED | [STEP_52_FRONTEND_ARCHITECTURE.md](../05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) |
| OBS-01 | **Step 53 — Observability.** Audit / diagnostics / logs never conflated; log expiry never removes auditable history; `UNABLE_TO_EVALUATE` is correct behavior and not alerted | LOCKED | [STEP_53_OBSERVABILITY.md](../09-implementation/STEP_53_OBSERVABILITY.md) |
| TEST-10 | **Step 54 — Testing.** Golden corpus is Tier 1 and normative; a changed expected output is a specification change; authorization tests are release-blocking | LOCKED | [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md) |
| DEP-01 | **Step 55 — Deployment.** No new technology; API and workers deploy together; migrations forward-only over legal data; reproducibility verified post-migration; production blockers register | LOCKED | [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) |

---

## A. Product & scope

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| PROD-01 | LegalMind V1 is a deterministic legal-document comparison and workflow system; it identifies and structures issues, an authorized human makes the legal decision | LOCKED | Step 1 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-02 | Approving a deviation does NOT automatically modify the contract; customization is a separate, optional, post-approval step | LOCKED | Step 1 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-03 | Approval of a deviation does not change the company standard | LOCKED | Steps 1, 9 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-04 | Uploading is not restricted to Legal users; normal Users may upload, compare, view, and escalate | LOCKED | Step 2 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-05 | The original uploaded file must remain unchanged; a customized contract is a separate version/document | LOCKED | Steps 2, 34 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-06 | Metadata may be suggested via deterministic parsing; no LLM required for this | LOCKED | Step 2 | [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md) |
| PROD-07 | V1 Scope Freeze and V1 acceptance boundary | LOCKED | Step 37 | [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md) |

## B. Roles, authority & access

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| ROLE-01 | LegalMind uses RBAC: User → Role → Permissions → Authorization Check → Action | LOCKED | Step 3 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| ROLE-02 | Business job titles and application authorization roles are separate concepts | LOCKED | Step 3 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| ROLE-03 | A normal User has no legal-decision permissions | LOCKED | Steps 3, 4 | [USER_ROLES.md](../01-product/USER_ROLES.md) |
| ROLE-04 | Escalation is not approval — it means "this requires authorized review" | LOCKED | Step 4 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| ROLE-05 | Admin is a system role and does not automatically confer legal approval authority; approval authority is separately assignable | LOCKED | Step 4 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| ROLE-06 | Canonical roles & permission matrix (User / Legal Reviewer / Legal Admin / Super Admin) — supersedes the Step 3 draft groups | LOCKED | Step 23 | [USER_ROLES.md](../01-product/USER_ROLES.md) |
| ROLE-07 | Review visibility & ownership model (ownership + scope access, 18 rules) | LOCKED | Step 24 | [OWNERSHIP.md](../06-security/OWNERSHIP.md) |

## C. Legal domain & confidentiality

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| LEGAL-01 | Comparison uses both standard documents and internal legal positions | LOCKED | Step 5 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| LEGAL-02 | Internal legal positions are permission-controlled; internal legal strategy must not leak to ordinary users or counterparties | LOCKED | Steps 5, 9 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| LEGAL-03 | Document Type and Legal/Regulatory Reference are separate concepts | LOCKED | Step 6 | [DOCUMENT_MODEL.md](../03-document-model/DOCUMENT_MODEL.md) |
| LEGAL-04 | Comparison is clause/requirement-level, not only document-level | LOCKED | Step 7 | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |
| LEGAL-05 | Comparison = complete alignment report; LegalMind must not show only problems | LOCKED | Step 8 | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |
| LEGAL-06 | A Finding is a clause/requirement-level comparison result and is separate from a Legal Decision; a Finding is not final legal truth | LOCKED | Step 8 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| LEGAL-07 | Every meaningful Finding must be traceable to source evidence | LOCKED | Steps 8, 32 | [EVIDENCE_MODEL.md](../03-document-model/EVIDENCE_MODEL.md) |
| LEGAL-08 | Review is the central historical record; a Report is generated from the Review and is not the source of truth | LOCKED | Step 9 | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |
| LEGAL-09 | Standard Document and Structured Legal Rule remain distinct concepts | LOCKED | Step 9 | [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md) |
| LEGAL-10 | Clause Library & Requirement structure: Clause → Requirement → Company Standard → pre-approved Legal Rule → Legal Decision | LOCKED | Step 20 | [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md) |
| LEGAL-11 | Company Standards are maintained inside LegalMind and are versioned | LOCKED | Steps 9, 21 | [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) |
| LEGAL-12 | Legal Decision vocabulary and approval workflow are controlled and explicit | LOCKED | Step 31 | [LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md) |
| LEGAL-13 | LegalMind must not declare a contract legally approved merely because it aligns with a standard | LOCKED | Step 9 | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |

## D. Findings & review lifecycle

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| FIND-01 | Finding types — Step 18 set: `MATCH` / `DEVIATION` / `MISSING` / `ADDITIONAL` / `UNMAPPED` | LOCKED — **vocabulary superseded** by `REC-01`; step rules 6–11 still in force | Step 18 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| FIND-02 | Finding types — Step 27 set: `MATCH` / `DEVIATION` / `MISSING` / `CONFLICT` / `EXTRA` / `UNABLE_TO_EVALUATE` | LOCKED — **vocabulary superseded** by `REC-01`; step rules 1–18 still in force | Step 27 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| FIND-03 | **CANONICAL** Finding Classification (axis 2) — Step 36 set: `MATCH` / `DEVIATION` / `MISSING` / `CONFLICT` / `AMBIGUOUS` / `UNRESOLVED` / `UNABLE_TO_EVALUATE` | LOCKED — canonical per `REC-01` | Step 36 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| FIND-10 | `UNMATCHED_PROVISION` is a document-level observation, **not** a Finding Classification | LOCKED per `REC-02` | Steps 18, 27 + owner 2026-08-16 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| FIND-11 | Five-axis separation: Mapping State / Finding Classification / Rule Outcome / Legal Decision / Review Lifecycle must never share a status field | LOCKED | Step 30 + `REC-06` | [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) |
| FIND-04 | **RESOLVED ≠ MATCH** — a resolved workflow state must never be recorded as a MATCH finding | LOCKED | Steps 22, 30 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |
| FIND-05 | `DEVIATION` does not mean "unacceptable"; classification and legal-rule outcome are separate | LOCKED | Step 36 | [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) |
| FIND-06 | No generic risk score; no aggregate "AI confidence" percentage | LOCKED | Steps 36, 44 | [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md) |
| FIND-07 | The engine never makes an automatic Legal Decision | LOCKED | Steps 36, 44, 45A | [LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md) |
| FIND-08 | Review lifecycle & status state machine (7 states + exception states) | LOCKED | Step 30 | [WORKFLOWS.md](../01-product/WORKFLOWS.md) |
| FIND-09 | Comparison & Finding generation pipeline is deterministic | LOCKED | Steps 17, 27 | [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md) |

> **Resolved 2026-08-16 (`REC-01`, `REC-02`).** FIND-01/02/03 are a supersession chain, not a contradiction: `ADDITIONAL`→`EXTRA` was a rename, `UNMAPPED` migrated to the mapping layer (axis 1), and `CONFLICT`/`AMBIGUOUS`/`UNRESOLVED`/`UNABLE_TO_EVALUATE` were additive. FIND-03 is canonical. `EXTRA`/`ADDITIONAL` became `UNMATCHED_PROVISION` (FIND-10). Historical locked text was not modified. See [CONFLICTS.md](CONFLICTS.md) C-01.

## E. Documents, versioning & evidence

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| DOC-01 | Document & Contract versioning model: Document / Version / Review / Decision separation | LOCKED | Step 26 | [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) |
| DOC-02 | Document Versions are immutable; a changed document is a new version | LOCKED | Steps 26, 41 | [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) |
| DOC-03 | Document ingestion & parsing rules (formats, OCR provenance, fingerprinting, structure/table/clause/page preservation, extraction status, untrusted input) | LOCKED | Step 34 | [PROCESSING_PIPELINE.md](../03-document-model/PROCESSING_PIPELINE.md) |
| DOC-04 | Evidence must be anchored to a processing run and remain attached to every extracted fact | LOCKED | Steps 32, 41 | [EVIDENCE_MODEL.md](../03-document-model/EVIDENCE_MODEL.md) |
| DOC-05 | Version diff must not be equated with a legal conclusion | LOCKED | Step 33 (see caveat) | [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md) |

> **Step 33 (`REC-04`, 2026-08-16):** Step 33 is a **PROVISIONAL elaboration of locked Step 26**, not a competing decision — a rule-by-rule comparison found no contradiction; Step 33 restates or narrows Step 26 throughout. Three Step 33 rules have no Step 26 counterpart and **remain unlocked**: system-controlled sequential version numbering, invalid/withdrawn-instead-of-delete, and the v1→v2→v3 predecessor chain. Do not implement those until Step 33 is explicitly locked. DOC-05 is listed here because the principle is independently restated in locked steps.

## F. Analysis engine

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| ENG-01 | **CANONICAL** Mapping State (axis 1) — `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED` | LOCKED — canonical per `REC-03` | Step 28 | [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| ENG-02 | Deterministic mapping engine (aliases, keyword groups, negative terms, candidate vs confirmed, many-to-many mapping, no forced mapping, mapping evidence, versioned mapping rules) | LOCKED | Step 35 | [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| ENG-03 | Mapping ≠ Evaluation — separate engines answering separate questions | LOCKED | Steps 35, 38 | [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) |
| ENG-04 | Finding & Evaluation Engine: 7 outcomes, requirement-specific evaluation, evaluation must preserve the calculation, historical reproducibility | LOCKED | Step 36 | [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) |
| ENG-05 | Layered analysis engine (28 locked items): normalization → structural parsing → mapping → evidence selection → fact extraction → negative patterns → conflict detection; no direct text→Finding shortcut | LOCKED | Step 44 | [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) |
| ENG-06 | Requirement-specific structured fact extraction; carve-outs and negative patterns are first-class and must not be discarded | LOCKED | Step 44 | [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md) |
| ENG-07 | Conflict detection is explicit and cross-clause; `MISSING`, `AMBIGUOUS`, `UNRESOLVED`, `UNABLE_TO_EVALUATE` remain distinct states | LOCKED | Step 44 | [CONFLICT_DETECTION.md](../04-analysis-engine/CONFLICT_DETECTION.md) |
| ENG-08 | Explainability contract: Evidence → Fact → Standard → Rule → Result must be reconstructable for every Finding | LOCKED | Step 44 | [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md) |
| ENG-09 | Fail-closed failure philosophy: insufficient extraction produces `UNABLE_TO_EVALUATE`, never a guess | LOCKED | Steps 36, 44, 45A | [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md) |
| ENG-10 | Common engine + specialized per-requirement evaluators; rule *parameters* configurable, core evaluation *code* tested and not user-editable | LOCKED | Step 44 | [RULE_ENGINE.md](../04-analysis-engine/RULE_ENGINE.md) |
| ENG-11 | Engine is versioned and deterministically reproducible | LOCKED | Step 44 | [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) |
| ENG-12 | Golden test corpus is mandatory; regression comparison required before release | LOCKED | Step 44 | [GOLDEN_CORPUS.md](../08-testing/GOLDEN_CORPUS.md), [REGRESSION_TESTING.md](../08-testing/REGRESSION_TESTING.md) |

## G. AI boundary

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| AI-01 | **V1 AI Boundary** — V1 does NOT use LLM, RAG, embeddings, vector databases, semantic retrieval, or autonomous AI legal reasoning in the authoritative analysis path. Changing this requires explicitly revisiting the locked decision. | LOCKED | "V1 AI Boundary" section | [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) |
| AI-02 | Architecture must remain *capable* of adding LLM/RAG post-V1 without redesign, but as an assistive layer, never the authoritative path | LOCKED | Steps "V1 AI Boundary", 38.25 | [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md) |
| AI-03 | Classical NLP (e.g. spaCy) is permitted in an assist-only role; no embeddings or semantic vector search | LOCKED | Step 44 | [RULE_ENGINE.md](../04-analysis-engine/RULE_ENGINE.md) |
| AI-04 | No LLM/RAG/vector DB in V1 restated as a backend/API-level lock | LOCKED | Step 43 | [API_ARCHITECTURE.md](../05-architecture/API_ARCHITECTURE.md) |

## H. Architecture

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| ARCH-01 | V1 architecture and domain separation (21 locked items, Identity/Contracts/Storage/Processing/Configuration/Analysis/Findings/Review/Snapshot/Decision/Audit/Reporting domains) | LOCKED | Step 38 | [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md) |
| ARCH-02 | Security boundary: Authentication → Authorization → Business Operation → Database; checks are server-side | LOCKED | Step 38.21 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| ARCH-03 | No direct UI → database access | LOCKED | Step 38.22 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| ARCH-04 | No UI → analysis-engine shortcuts; one source of truth for legal evaluation | LOCKED | Step 38.23 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| ARCH-05 | API layer orchestrates; endpoint naming explicitly NOT locked | LOCKED (with stated exclusion) | Step 38.24 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| ARCH-06 | Technology stack table (Frontend / Backend / DB / ORM / PDF / DOCX / OCR / Jobs / Storage / Testing / Infra / Monitoring) | LOCKED | Step 39 | [BACKEND_ARCHITECTURE.md](../05-architecture/BACKEND_ARCHITECTURE.md) |
| ARCH-07 | Modular monolith with thin routes, service layer, repository layer, async processing, idempotency, explicit state machines | LOCKED | Step 43 | [API_ARCHITECTURE.md](../05-architecture/API_ARCHITECTURE.md) |

> Note on ARCH-06: only the Step 39 **final stack table** is locked. The surrounding "I recommend…" rationale in Step 39 is RECOMMENDED, not locked.

## I. Data model & persistence

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| DATA-01 | Domain model lock (20 items): Contract ≠ Document Version, versioned Requirements/Standards/Rules, Finding ≠ Decision, evidence traceability, immutability | LOCKED | Step 40 | [DATABASE_ARCHITECTURE.md](../05-architecture/DATABASE_ARCHITECTURE.md) |
| DATA-02 | Schema contract lock (25 items): UUIDs, PostgreSQL as system of record, configuration snapshots, append-only audit, indexing/UTC/soft-delete rules | LOCKED | Step 41 | [DATABASE_ARCHITECTURE.md](../05-architecture/DATABASE_ARCHITECTURE.md) |
| DATA-03 | Critical authorization rule — object-level authorization must traverse User → Review → Contract → Owner/Role → Permission | LOCKED | Step 41.24 | [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md) |
| DATA-04 | Exact table schemas and ERD (22 locked items) | LOCKED | Step 42 | [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) |
| DATA-05 | Schema design rules (UUID, UTC, FKs, immutability, limits on JSONB use) | LOCKED | Step 42.1 | [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) |
| DATA-06 | No database-level "magic" — legal evaluation logic stays in the application layer, not in PostgreSQL triggers | LOCKED | Step 42.22 | [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) |

## J. Configuration, audit & reproducibility

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| AUD-01 | Audit trail is append-only; core audit event schema locked | LOCKED | Step 25 | [AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md) |
| AUD-02 | Evidence, explainability & audit rules, including MISSING/CONFLICT special cases | LOCKED | Step 32 | [AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md) |
| AUD-03 | Configuration is versioned; Draft → Legal Review → Publish → Active; drafts never affect comparisons | LOCKED | Steps 9, 21, 29 | [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) |
| AUD-04 | A Review runs against a **configuration snapshot**; publishing new configuration never mutates an existing Review | LOCKED | Steps 29, 30, 41, 43 | [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md) |
| AUD-05 | Existing Reviews never silently change; historical Reviews remain reproducible and auditable | LOCKED | Steps 9, 26, 36.16 | [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md) |

## K. Requirement-specific evaluators

| ID | Decision | Status | Source Step | Canonical Document |
|----|----------|--------|-------------|--------------------|
| LIABILITY-001 | Canonical Limitation of Liability requirement — full 21-rule lock: 6-month Company Standard; 6mo→`MATCH`; 12mo→`DEVIATION`+`ACCEPTABLE`; >12mo→`DEVIATION`+`APPROVAL_REQUIRED`; `UNLIMITED`→`DEVIATION`+`UNACCEPTABLE`; missing→`MISSING`; insufficient extraction→`UNABLE_TO_EVALUATE`; contradictory provisions→`CONFLICT`; ambiguity never silently resolved; carve-outs never discarded; cross-references resolved only where deterministic; evaluator makes no Legal Decision; no LLM/RAG/embeddings | LOCKED | Step 45A | [EDGE_CASES/LIABILITY.md](../04-analysis-engine/EDGE_CASES/LIABILITY.md) |
| LIABILITY-001-CONTRACT | Evaluator data contract for `LIABILITY-001` — precise input/output field schema (incl. `extraction_diagnostics`, `rule_configuration`), seven worked examples, "evidence must survive the evaluator", "no arbitrary NULL semantics", persistence model | 🔒 LOCKED (revised) | Step 45B (+ REC-05, REC-07, AB-1) | [EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) |

> **Step 45B was RE-LOCKED on 2026-08-17** incorporating Amendment Batch AB-1. Originally locked 2026-08-16, comprising 45B.1–45B.28 unmodified plus the `REC-05` (R1) corrections and the `REC-07` persistence decision. The lock record is appended to `all_lock.md` as "Step 45B — LOCK RECORD". **`rule_configuration` remains `NOT YET SPECIFIED`** — the field is locked as an explicit extension point; its contents are not, and must not be invented.
>
> Note also that an earlier status block inside Step 45A still reads `READY TO LOCK`; the file's final block supersedes it. See [CONFLICTS.md](CONFLICTS.md).

---

## Explicitly NOT in this registry

The following are **not** locked and must not be treated as decided. They are tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md):

* All of Step 33 (contract versioning & re-review) — author declined to lock; see `REC-04`
* Step 35's numerical scoring weights and thresholds — explicitly illustrative
* **The scoring-band → mapping-state mapping** (how `CANDIDATE-REVIEW` / `NOT MAPPED` / `NO_CONFIDENT_MAPPING` map onto `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED`) — explicitly deferred by owner decision, 2026-08-16. Do not infer it.
* The shape/contents of `rule_configuration` (named in 45B.9, never specified)
* Persistence, surfacing, and review treatment of `UNMATCHED_PROVISION` observations
* Step 39's technology *rationale* prose — recommendation only
* Authentication implementation and any existing-auth integration
* Exact API endpoint naming
* `document_evidence.source_type` and `legal_decisions.decision_type` enum values — "finalized during implementation"
* Termination, Indemnification, Governing Law and every other requirement evaluator besides `LIABILITY-001`
* Risk classification rules, export formats, regulatory reference workflow, UI/UX

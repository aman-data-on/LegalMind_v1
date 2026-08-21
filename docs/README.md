# LegalMind Documentation Index

**This file is the navigation map. It contains no decisions.** Every statement of fact about the system lives in the document it links to.

| I want to… | Go to |
|---|---|
| Understand what LegalMind is | [00-project/PROJECT_OVERVIEW.md](00-project/PROJECT_OVERVIEW.md) |
| **Understand how the system works end to end** | [00-project/ARCHITECTURE_REFERENCE.md](00-project/ARCHITECTURE_REFERENCE.md) |
| Know what is settled and may not be changed | [00-project/LOCKED_DECISIONS.md](00-project/LOCKED_DECISIONS.md) |
| Know what is *not* decided | [00-project/IMPLEMENTATION_STATUS.md](00-project/IMPLEMENTATION_STATUS.md) § Explicitly NOT YET SPECIFIED |
| Check the current step / build state | [00-project/IMPLEMENTATION_STATUS.md](00-project/IMPLEMENTATION_STATUS.md) |
| Look up a term precisely | [00-project/GLOSSARY.md](00-project/GLOSSARY.md) |
| Name a state value correctly | [02-legal-domain/DECISION_STATE_MODEL.md](02-legal-domain/DECISION_STATE_MODEL.md) |
| Find a known contradiction | [00-project/CONFLICTS.md](00-project/CONFLICTS.md) |
| Read the authoritative historical record | [`../all_lock.md`](../all_lock.md) |
| Propose a change | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Work here as an AI agent | [`../CLAUDE.md`](../CLAUDE.md) |

---

## Authoritative source by area

One document owns each area. Everything else references it rather than restating it.

| Area | Authoritative document |
|---|---|
| **Everything — historical master record** | [`../all_lock.md`](../all_lock.md) |
| Project overview | [00-project/PROJECT_OVERVIEW.md](00-project/PROJECT_OVERVIEW.md) |
| Locked decision registry | [00-project/LOCKED_DECISIONS.md](00-project/LOCKED_DECISIONS.md) |
| Current status / what is unspecified | [00-project/IMPLEMENTATION_STATUS.md](00-project/IMPLEMENTATION_STATUS.md) |
| Open conflicts | [00-project/CONFLICTS.md](00-project/CONFLICTS.md) |
| Terminology | [00-project/GLOSSARY.md](00-project/GLOSSARY.md) |
| State vocabularies (all five axes) | [02-legal-domain/DECISION_STATE_MODEL.md](02-legal-domain/DECISION_STATE_MODEL.md) |
| System architecture & domain boundaries | [05-architecture/SYSTEM_ARCHITECTURE.md](05-architecture/SYSTEM_ARCHITECTURE.md) |
| Technology stack | [05-architecture/BACKEND_ARCHITECTURE.md](05-architecture/BACKEND_ARCHITECTURE.md) |
| Database schema & ERD | [09-implementation/DATABASE_MIGRATIONS.md](09-implementation/DATABASE_MIGRATIONS.md) |
| API — final contract | [05-architecture/STEP_49_API_FINALIZATION.md](05-architecture/STEP_49_API_FINALIZATION.md) |
| Security / authn / authz | [06-security/STEP_47_SECURITY_SPECIFICATION.md](06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| Frontend | [05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md](05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) |
| Observability | [09-implementation/STEP_53_OBSERVABILITY.md](09-implementation/STEP_53_OBSERVABILITY.md) |
| Testing | [08-testing/STEP_54_TESTING_STRATEGY.md](08-testing/STEP_54_TESTING_STRATEGY.md) |
| **Final review / handoff** | [../HANDOFF.md](../HANDOFF.md) — the entry point for reviewing the build |
| Deployment | [09-implementation/STEP_55_DEPLOYMENT.md](09-implementation/STEP_55_DEPLOYMENT.md) |
| Change history (repository) | [`../CHANGELOG.md`](../CHANGELOG.md) |
| AI/agent instructions | [`../CLAUDE.md`](../CLAUDE.md) |

Where a Step-numbered document and an older topic document cover the same area, **the Step-numbered document is later and authoritative**; the older one is retained for the earlier locked material it records and carries a banner saying so.

---

## Document status labels

Declared at the top of every specification document. Never mix states without labelling them.

| Label | Meaning |
|---|---|
| 🔒 `LOCKED` | Settled. Requires explicit approval to change. |
| `PROVISIONAL` / `RECOMMENDED` | Proposed, not settled. Do not build on it as final. |
| ⏳ `UNDER REVIEW` / `IN PROGRESS` | Being decided now. |
| `PLANNED` / `NOT YET SPECIFIED` | Nothing decided. Do not invent it. |
| `ANALYSIS` / `PROPOSAL` | Working document. Records reasoning, decides nothing. |

---

## The tree

### [00-project/](00-project/) — orientation and control

| File | Purpose |
|---|---|
| [PROJECT_OVERVIEW.md](00-project/PROJECT_OVERVIEW.md) | What LegalMind is, what it is not, the analysis chain |
| [ARCHITECTURE_REFERENCE.md](00-project/ARCHITECTURE_REFERENCE.md) | **Architecture & system-flow map** — the developer entry point. Navigational only; links to every authoritative spec |
| [LOCKED_DECISIONS.md](00-project/LOCKED_DECISIONS.md) | Registry of every explicitly locked decision, by ID |
| [IMPLEMENTATION_STATUS.md](00-project/IMPLEMENTATION_STATUS.md) | Current step, status per area, and everything NOT YET SPECIFIED |
| [CLAUSE_CATALOGUE.md](00-project/CLAUSE_CATALOGUE.md) | The full-document review map: Requirements per document type, sources, and gaps (2026-08-19) |
| [CONFLICTS.md](00-project/CONFLICTS.md) | Known contradictions — resolved (C-01–C-04, C-09, C-11) and open (C-05–C-08, C-10, C-12) |
| [GLOSSARY.md](00-project/GLOSSARY.md) | Terminology, with the distinctions that must not be conflated |
| [DECISION_FINALIZATION.md](00-project/DECISION_FINALIZATION.md) | Working record: classification of every remaining item, F-1–F-12 |
| [EXTERNAL_REFERENCE_AUDIT.md](00-project/EXTERNAL_REFERENCE_AUDIT.md) | Working record: audit of external MoS material; source of OD-1–OD-15 |
| [SOURCE_MATERIAL_INTAKE.md](00-project/SOURCE_MATERIAL_INTAKE.md) | Working record: what the supplied legal source material covers, the owner rulings of 2026-08-18, and where the 44 supplied documents live. **Read before requesting any document** |

### [01-product/](01-product/) — product scope

| File | Purpose |
|---|---|
| [PRODUCT_REQUIREMENTS.md](01-product/PRODUCT_REQUIREMENTS.md) | Locked product decisions and V1 scope |
| [USER_ROLES.md](01-product/USER_ROLES.md) | Canonical roles and permission matrix |
| [WORKFLOWS.md](01-product/WORKFLOWS.md) | Review lifecycle, escalation, RBAC flow |

### [02-legal-domain/](02-legal-domain/) — the legal model

| File | Purpose |
|---|---|
| [LEGAL_ANALYSIS_PHILOSOPHY.md](02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md) | Determinism, the AI boundary, complete-alignment reporting |
| [DECISION_STATE_MODEL.md](02-legal-domain/DECISION_STATE_MODEL.md) | **The five state axes.** Read before naming any state value |
| [COMPANY_STANDARDS.md](02-legal-domain/COMPANY_STANDARDS.md) | What the organization wants; configuration versioning |
| [LEGAL_RULES.md](02-legal-domain/LEGAL_RULES.md) | How far the organization tolerates departing from a Standard |
| [FINDING_CLASSIFICATION.md](02-legal-domain/FINDING_CLASSIFICATION.md) | The seven Finding classifications; RESOLVED ≠ MATCH |
| [LEGAL_DECISIONS.md](02-legal-domain/LEGAL_DECISIONS.md) | Authorized human rulings; the engine never produces one |

### [03-document-model/](03-document-model/) — documents and evidence

| File | Purpose |
|---|---|
| [DOCUMENT_MODEL.md](03-document-model/DOCUMENT_MODEL.md) | Document types vs legal/regulatory references |
| [DOCUMENT_VERSIONING.md](03-document-model/DOCUMENT_VERSIONING.md) | Immutable versions (Step 26 locked; Step 33 provisional) |
| [EVIDENCE_MODEL.md](03-document-model/EVIDENCE_MODEL.md) | Evidence anchoring and traceability |
| [PROCESSING_PIPELINE.md](03-document-model/PROCESSING_PIPELINE.md) | Ingestion, parsing, OCR provenance, extraction status |

### [04-analysis-engine/](04-analysis-engine/) — the engine

| File | Purpose |
|---|---|
| [ANALYSIS_ENGINE.md](04-analysis-engine/ANALYSIS_ENGINE.md) | The layered pipeline and the seven evaluation outcomes |
| [REQUIREMENT_MAPPING.md](04-analysis-engine/REQUIREMENT_MAPPING.md) | Clause → Requirement mapping; mapping ≠ evaluation |
| [FACT_EXTRACTION.md](04-analysis-engine/FACT_EXTRACTION.md) | Requirement-specific structured extraction; carve-outs |
| [RULE_ENGINE.md](04-analysis-engine/RULE_ENGINE.md) | Evaluator architecture; configurable parameters vs code |
| [CONFLICT_DETECTION.md](04-analysis-engine/CONFLICT_DETECTION.md) | Conflict, ambiguity, missing, unresolved kept distinct |
| [EXPLAINABILITY.md](04-analysis-engine/EXPLAINABILITY.md) | Evidence → Fact → Standard → Rule → Result; fail-closed |
| [EVALUATOR_EDGE_CASES.md](04-analysis-engine/EVALUATOR_EDGE_CASES.md) | 🔒 Step 45D — cross-evaluator structural contract |

#### [04-analysis-engine/EDGE_CASES/](04-analysis-engine/EDGE_CASES/) — per-evaluator specification

| File | Purpose |
|---|---|
| [LIABILITY.md](04-analysis-engine/EDGE_CASES/LIABILITY.md) | 🔒 Step 45A — `LIABILITY-001` policy, 21 rules |
| [LIABILITY_EVALUATOR_CONTRACT.md](04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) | 🔒 Step 45B — input/output data contract |
| [LIABILITY_EDGE_CASES.md](04-analysis-engine/EDGE_CASES/LIABILITY_EDGE_CASES.md) | 🔒 Step 45C — multiple caps, carve-outs, cross-references |
| [PRESENCE_EVALUATOR.md](04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md) | 🔒 Step 45D — the generic `PRESENCE` evaluator |
| [TERMINATION.md](04-analysis-engine/EDGE_CASES/TERMINATION.md) · [INDEMNIFICATION.md](04-analysis-engine/EDGE_CASES/INDEMNIFICATION.md) · [GOVERNING_LAW.md](04-analysis-engine/EDGE_CASES/GOVERNING_LAW.md) | **NOT YET SPECIFIED** — placeholders. No locked decision requires these |

Working documents in this directory — analysis only, nothing locked: [OPEN_DECISIONS_ANALYSIS.md](04-analysis-engine/EDGE_CASES/OPEN_DECISIONS_ANALYSIS.md), [LIABILITY_CONTRACT_AMENDMENTS.md](04-analysis-engine/EDGE_CASES/LIABILITY_CONTRACT_AMENDMENTS.md), [V1_SCOPE_AUDIT.md](04-analysis-engine/EDGE_CASES/V1_SCOPE_AUDIT.md), [ANALYSIS_ORCHESTRATOR_GAP.md](04-analysis-engine/EDGE_CASES/ANALYSIS_ORCHESTRATOR_GAP.md), and `RECONCILIATION_PASS_2.md` – `RECONCILIATION_PASS_6.md`. They record how conclusions were reached. Their outcomes are in [LOCKED_DECISIONS.md](00-project/LOCKED_DECISIONS.md); do not implement from them directly.

[ANALYSIS_ORCHESTRATOR_GAP.md](04-analysis-engine/EDGE_CASES/ANALYSIS_ORCHESTRATOR_GAP.md) is the current one: it establishes that the deferred Step 35 band → mapping-state mapping does **not** block the analysis orchestrator, and isolates the four items that do (`D-1` – `D-4`, awaiting owner decision).

### [05-architecture/](05-architecture/) — how the system is built

| File | Purpose |
|---|---|
| [SYSTEM_ARCHITECTURE.md](05-architecture/SYSTEM_ARCHITECTURE.md) | 🔒 Domain boundaries, V1 scope freeze, modular monolith |
| [BACKEND_ARCHITECTURE.md](05-architecture/BACKEND_ARCHITECTURE.md) | 🔒 Technology stack table |
| [DATABASE_ARCHITECTURE.md](05-architecture/DATABASE_ARCHITECTURE.md) | 🔒 Domain model and schema contract (Steps 40–41) |
| [STORAGE_ARCHITECTURE.md](05-architecture/STORAGE_ARCHITECTURE.md) | 🔒 PostgreSQL vs object-storage responsibilities |
| [API_ARCHITECTURE.md](05-architecture/API_ARCHITECTURE.md) | 🔒 Step 43 — modular monolith, envelope, status semantics |
| [STEP_49_API_FINALIZATION.md](05-architecture/STEP_49_API_FINALIZATION.md) | 🔒 **Authoritative API contract** — permissions, denial semantics, pagination |
| [FRONTEND_ARCHITECTURE.md](05-architecture/FRONTEND_ARCHITECTURE.md) | Step 39 stack extract — superseded by Step 52 |
| [STEP_52_FRONTEND_ARCHITECTURE.md](05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) | 🔒 **Authoritative frontend specification** |

### [06-security/](06-security/) — security

| File | Purpose |
|---|---|
| [STEP_47_SECURITY_SPECIFICATION.md](06-security/STEP_47_SECURITY_SPECIFICATION.md) | 🔒 **Authoritative** — OIDC, sessions, permission catalogue, SEC-01–SEC-09 |
| [SECURITY_MODEL.md](06-security/SECURITY_MODEL.md) | 🔒 The server-side boundary; no UI→DB; no UI legal logic |
| [AUTHORIZATION.md](06-security/AUTHORIZATION.md) | 🔒 Object-level authorization rules |
| [OWNERSHIP.md](06-security/OWNERSHIP.md) | 🔒 Review visibility and ownership (Step 24, 18 rules) |
| [EDGE_CASES/LEGAL_ACCESS_GAP.md](06-security/EDGE_CASES/LEGAL_ACCESS_GAP.md) | 📁 `F-6` — why a Legal Reviewer can reach no Review, and the smallest decision that would fix it |
| [AUTHENTICATION.md](06-security/AUTHENTICATION.md) | Step 43 `auth` responsibilities — open items closed by Step 47 |

### [07-audit/](07-audit/) — audit and reproducibility

| File | Purpose |
|---|---|
| [AUDIT_TRAIL.md](07-audit/AUDIT_TRAIL.md) | 🔒 Append-only audit; evidence and explainability rules |
| [REPRODUCIBILITY.md](07-audit/REPRODUCIBILITY.md) | 🔒 Configuration snapshots; historical Reviews never change |

### [08-testing/](08-testing/) — testing

| File | Purpose |
|---|---|
| [STEP_54_TESTING_STRATEGY.md](08-testing/STEP_54_TESTING_STRATEGY.md) | 🔒 **Authoritative test strategy** — tiers, release gates |
| [GOLDEN_CORPUS_45E.md](08-testing/GOLDEN_CORPUS_45E.md) | ⏳ Step 45E — the 64 specified fixtures |
| [GOLDEN_CORPUS.md](08-testing/GOLDEN_CORPUS.md) | 🔒 44.34 — the original corpus requirement |
| [REGRESSION_TESTING.md](08-testing/REGRESSION_TESTING.md) | 🔒 44.35 — regression protection when the evaluator changes |
| [INDEPENDENT_VERIFICATION.md](08-testing/INDEPENDENT_VERIFICATION.md) | 📁 Record — each critical guarantee re-checked by a mechanism *other than* the test that asserts it, and what that found |
| [TEST_STRATEGY.md](08-testing/TEST_STRATEGY.md) | Step 39 tooling extract — superseded by Step 54 |

### [09-implementation/](09-implementation/) — the target build

> These describe a **target**. Their presence is not permission to build.

| File | Purpose |
|---|---|
| [DATABASE_MIGRATIONS.md](09-implementation/DATABASE_MIGRATIONS.md) | 🔒 **Authoritative schema** — exact tables and ERD (Step 42 + AB-1) |
| [API_CONTRACT.md](09-implementation/API_CONTRACT.md) | 🔒 Step 43 per-module contract detail |
| [STEP_53_OBSERVABILITY.md](09-implementation/STEP_53_OBSERVABILITY.md) | 🔒 **Authoritative observability** — audit vs diagnostics vs logs |
| [STEP_55_DEPLOYMENT.md](09-implementation/STEP_55_DEPLOYMENT.md) | 🔒 **Authoritative deployment** — topology, migrations, blockers register |
| [IMPLEMENTATION_READINESS_GATE.md](09-implementation/IMPLEMENTATION_READINESS_GATE.md) | ✅ The nine gate criteria, all met; recommended build sequence |
| [DEPLOYMENT.md](09-implementation/DEPLOYMENT.md) | Step 39 deployment sketch — superseded by Step 55 |
| [IMPLEMENTATION_PLAN.md](09-implementation/IMPLEMENTATION_PLAN.md) | Sequencing — see the readiness gate for the current recommendation |
| [IMPLEMENTATION_READINESS_REVIEW.md](09-implementation/IMPLEMENTATION_READINESS_REVIEW.md) | Superseded by the readiness gate; retained for the record |

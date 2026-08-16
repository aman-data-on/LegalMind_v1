# LegalMind V1 — Project Overview

**Start here.** This is the entry point to the LegalMind documentation.

---

## What LegalMind is

LegalMind V1 stores the organization's legal documents and approved legal standards, compares a selected counterparty contract against those standards, and identifies:

* Matches
* Missing clauses/requirements
* Deviations
* Conflicts

It provides supporting evidence, risk classification, human review, escalation, legal decision tracking, and structured reporting.

**The system identifies and structures the issue. An authorized human makes the legal decision.**

```text
Finding: Limitation of Liability
Result: Conflict
Risk: High
Evidence: Relevant contract clause
Status: Requires review
```

### What LegalMind V1 is not

V1 does **not** use LLMs, AI chat, RAG, embeddings, vector databases, autonomous legal decisions, or AI-generated legal advice in the authoritative analysis path. This is a locked decision (`AI-01`), not a temporary simplification. See [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md).

Legal analysis in V1 is **deterministic**: same inputs + same configuration snapshot + same engine version → same result, with a fully reconstructable explanation.

---

## Current project phase

**SPECIFICATION / DESIGN. Implementation has not begun.**

| | |
|---|---|
| Steps 1–44 | 🔒 LOCKED |
| Step 45A — `LIABILITY-001` | 🔒 LOCKED |
| Step 45B — Evaluator Data Contract | 🔒 LOCKED |
| `REC-01`–`REC-07` — reconciliation | 🔒 LOCKED |
| Step 45C — Liability Edge Cases | ⏳ IN PROGRESS |

Full detail: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

---

## Where authoritative decisions live

| What you need | Where |
|---------------|-------|
| **The historical master specification** — the authoritative record of every decision, in the order it was made | [`all_lock.md`](../../all_lock.md) at the repository root |
| **The locked decision registry** — an index of every explicitly locked decision | [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) |
| **Current status and what is not yet decided** | [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) |
| **Known conflicts that must not be silently resolved** | [CONFLICTS.md](CONFLICTS.md) |
| **Terminology** | [GLOSSARY.md](GLOSSARY.md) |
| **Rules for working on this project** | [CLAUDE.md](../../CLAUDE.md) |

`all_lock.md` remains the authoritative historical record. This `docs/` tree is the **organized implementation reference** derived from it. Where the two disagree, `all_lock.md` wins and the discrepancy must be reported.

---

## Documentation map

| Section | Contains |
|---------|----------|
| [00-project/](.) | Overview, glossary, locked decision registry, status, conflicts |
| [01-product/](../01-product/) | Product requirements, user roles & permission matrix, workflows and review lifecycle |
| [02-legal-domain/](../02-legal-domain/) | Analysis philosophy & AI boundary, Company Standards, Legal Rules, Finding classification, Legal Decisions |
| [03-document-model/](../03-document-model/) | Document types, versioning, evidence model, ingestion/processing pipeline |
| [04-analysis-engine/](../04-analysis-engine/) | Engine architecture, requirement mapping, fact extraction, rule engine, conflict detection, explainability, and per-requirement edge cases |
| [05-architecture/](../05-architecture/) | System, backend, frontend, API, database, storage architecture |
| [06-security/](../06-security/) | Authentication, authorization, ownership, security model |
| [07-audit/](../07-audit/) | Audit trail, reproducibility |
| [08-testing/](../08-testing/) | Test strategy, golden corpus, regression testing |
| [09-implementation/](../09-implementation/) | Target implementation plan, schema spec, API contract, deployment — **specifications, not built work** |

---

## Where the analysis-engine specification lives

The analysis engine is specified across [04-analysis-engine/](../04-analysis-engine/):

* [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) — the layered pipeline and the seven evaluation outcomes (canonical)
* [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md) — how a clause is mapped to a Requirement
* [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md) — structured, requirement-specific fact extraction
* [RULE_ENGINE.md](../04-analysis-engine/RULE_ENGINE.md) — evaluator architecture and what is configurable vs code
* [CONFLICT_DETECTION.md](../04-analysis-engine/CONFLICT_DETECTION.md) — conflict, ambiguity, missing, unresolved
* [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md) — the explainability contract and fail-closed philosophy
* [EDGE_CASES/](../04-analysis-engine/EDGE_CASES/) — per-requirement evaluators; only `LIABILITY-001` is specified so far

---

## Where testing specifications live

[08-testing/](../08-testing/) — test strategy, the mandatory [golden corpus](../08-testing/GOLDEN_CORPUS.md), and [regression testing](../08-testing/REGRESSION_TESTING.md) that guards engine changes.

---

## The chain the whole system is built around

```text
Contract
       ↓
Document Version
       ↓
Evidence
       ↓
Requirement Mapping
       ↓
Fact Extraction
       ↓
Structured Facts
       ↓
Company Standard Comparison
       ↓
Legal Rule Evaluation
       ↓
Finding
       ↓
Evidence + Explanation
       ↓
Review Workflow
       ↓
Authorized Legal Decision
```

Not:

```text
Contract
 ↓
AI/heuristic
 ↓
"High Risk"
 ↓
Reject
```

The second shape would violate the entire V1 architecture.

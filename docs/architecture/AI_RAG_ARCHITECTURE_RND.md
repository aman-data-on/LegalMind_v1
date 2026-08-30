# AI + RAG Architecture — Post-V1 R&D Proposal

**Status: `ANALYSIS` / `PROPOSAL` — decides nothing, locks nothing, authorizes no build.**

> ⚠️ **Superseded in part — read this first (added 2026-08-25).** This document was written on
> 2026-08-24 against the then-current framing that an assistive AI lane was a **post-V1** question.
> **Amendment Batch AB-3 (`AM-25`–`AM-29`) was locked later the same day and put the assist lane inside
> V1 scope**, on nine fixed terms. Three consequences for reading what follows:
>
> 1. **The "post-V1" framing throughout is obsolete.** The lane is in V1. `AI-01`'s timing clause was
>    amended; every other principle in it now binds the lane directly.
> 2. **§11/§25/§26's central open question — whether contract text may reach a third-party model API —
>    is closed by `AM-25` r9 and `AM-26`: it may not.** The generative model, the embedding model and
>    the reranker are all *local, self-hosted and open-weight*; no hosted model, embedding or
>    document-processing service is authorized. §7's "Gemini Flash role" and §25's vendor research are
>    retained as research only, not as a live recommendation.
> 3. **§9's proposed schema is superseded by `AM-27`**, which authorizes nine specific tables in a
>    separate schema and closes with *"No other table is authorized by this record."*
>
> **What still holds and is re-verified:** every §2 codebase finding (§2.3 synchronous ingestion, §2.4
> the absent spaCy precedent, §2.5 zero outbound egress and zero vector/LLM code, §2.10 no
> workspace/tenant primitive), and the §5–§8/§13/§14/§24 design guidance on chunking, hybrid retrieval,
> pre-filtered authorization, output validation and anti-patterns — all of which AB-3 is consistent with.
>
> **For the current-state comparison against the 2026-08-25 product vision and tech-stack documents —
> the reuse matrix, gap analyses, contradiction register and migration order — see
> [EXISTING_BACKEND_REUSE_AUDIT.md](EXISTING_BACKEND_REUSE_AUDIT.md).** This document remains the deeper
> design reference for the retrieval and validation internals.

**Source:** synthesizes locked decisions `AI-01`–`AI-04` (verbatim text in §3), [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md), [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md), [STEP_52_FRONTEND_ARCHITECTURE.md](../05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md), [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md), [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md), [GLOSSARY.md](../00-project/GLOSSARY.md), [CLAUSE_CATALOGUE.md](../00-project/CLAUSE_CATALOGUE.md), a direct read of `backend/legalmind/` as it stands on 2026-08-24, and dated external vendor research (§9, §25).

**Prepared:** 2026-08-24, on explicit request, as a Principal-Solutions-Architect R&D exercise. **Related:** [CLAUDE.md](../../CLAUDE.md) · [LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md) · [all_lock.md](../../all_lock.md).

> **This is research, not implementation.** Producing this document changed no application code, no schema, no dependency, and no test. Nothing described here may be built without the approvals listed in §26. Per rule 21, it proposes no legal content, no Company Standard, no Legal Rule, and no golden-corpus fixture — those stay out of scope regardless of what the architecture eventually looks like.

**Fact/claim labeling used throughout:** every non-obvious claim below is tagged **FACT** (verified from the cited primary source, quoted or closely paraphrased), **RECOMMENDATION** (this document's synthesis/opinion), **ASSUMPTION** (unverified but load-bearing — flagged so it can be checked), or **OPEN QUESTION** (needs vendor, legal, security, or product-owner confirmation before anyone relies on it).

---

## Table of contents

1. [Executive Summary](#1-executive-summary)
2. [Current V1 Architecture Understanding](#2-current-v1-architecture-understanding)
3. [Architectural Principles](#3-architectural-principles-the-locked-ai-boundary-verbatim)
4. [AI vs Deterministic Responsibility Matrix](#4-ai-vs-deterministic-responsibility-matrix)
5. [RAG Architecture](#5-rag-architecture)
6. [Document Intelligence Pipeline](#6-document-intelligence-pipeline)
7. [Gemini Flash Role](#7-gemini-flash-role)
8. [Retrieval Architecture](#8-retrieval-architecture)
9. [Evidence Architecture](#9-evidence-architecture)
10. [Authorization Architecture](#10-authorization-architecture)
11. [Confidentiality / Security Architecture](#11-confidentiality--security-architecture)
12. [Versioning / Reproducibility](#12-versioning--reproducibility)
13. [AI Output Validation](#13-ai-output-validation)
14. [Hybrid Analysis Patterns](#14-hybrid-analysis-patterns)
15. [Architecture Options](#15-architecture-options)
16. [Recommended Architecture](#16-recommended-architecture)
17. [Architecture Diagram](#17-architecture-diagram)
18. [Data Flow](#18-data-flow)
19. [Failure Modes](#19-failure-modes)
20. [Evaluation Framework](#20-evaluation-framework)
21. [Observability](#21-observability)
22. [Cost / Performance Considerations](#22-cost--performance-considerations)
23. [Migration Strategy](#23-migration-strategy)
24. [Anti-patterns](#24-anti-patterns)
25. [Vendor Research — Gemini Flash & pgvector](#25-vendor-research--gemini-flash--pgvector)
26. [Open Questions, by Decision Owner](#26-open-questions-by-decision-owner)
27. [Recommended Next R&D Steps](#27-recommended-next-rd-steps)

---

## 1. Executive Summary

LegalMind V1 is a deterministic legal-comparison engine, locked end to end: parsing → clause mapping → fact extraction → rule evaluation → Finding, with every step traceable, versioned, and reproducible. `AI-01` bars any LLM, RAG, embedding, or vector database from that authoritative path; `AI-02` requires the architecture to be *capable* of accepting an assistive AI layer post-V1 *without becoming the source of truth for a legal decision*, not requiring a rebuild.

This document finds that promise **substantially holds**, with three concrete gaps:

1. **No async ingestion seam exists yet.** Document parsing runs synchronously inside the HTTP request (§2.3). Any embedding-generation step is compute-heavy enough that it cannot run inline — a new (small, additive) dispatch hook is needed, not a redesign.
2. **AI-03's stated precedent is fictional.** The locked text says classical NLP (spaCy) "already" holds the assist-only role. It does not exist anywhere in the codebase (§2.4). There is no working isolation pattern to copy; one has to be designed from the deterministic mapping/extraction gate as a template instead.
3. **No outbound-HTTP infrastructure exists at all today** (§2.5, §11). A third-party LLM call would be the first external network egress this codebase has ever made — genuinely new infrastructure, not an extension of an existing egress client.

Everything else — Review immutability, configuration snapshotting, the five-axis state model, server-side RBAC, the omit-not-null confidentiality idiom — transfers cleanly, provided the new AI layer is built as a **new, structurally isolated consumer** of already-recorded evidence and Findings, never a participant in producing them.

**Recommendation:** Option B (§15) — an AI-assisted layer around the deterministic core, self-hosted embeddings first, generation gated behind an explicit data-egress decision, proven out-of-path with database-enforced grants and a corpus-parity regression test (§16), not merely code-review trust.

---

## 2. Current V1 Architecture Understanding

### 2.1 The analysis chain (locked)

```
Contract upload
   ↓ (synchronous, in the HTTP request — see 2.3)
Document Version (immutable) → Processing Run (append-only) → Evidence (page/offset/section, write-once)
   ↓ (Celery, on-demand per Review — see 2.3)
Requirement ↔ Clause Mapping  (MappingState: CONFIRMED / AMBIGUOUS / UNRESOLVED)   — Step 28/35, deterministic
   ↓ (only CONFIRMED mappings proceed)
Fact Extraction  (regex/phrase, versioned config, fails closed to UNKNOWN)          — Step 44
   ↓
Deterministic Evaluator (NUMERIC_COMPARISON `LIABILITY-001`, or generic PRESENCE)   — Steps 44, 45A–D
   ↓
Finding (classification) → Rule Outcome (organization's tolerance) → Legal Decision (human only)
```

Every stage is closed-vocabulary, versioned, and re-derivable from persisted, immutable inputs — this is what "deterministic" concretely means at the code level (§2.6 below expands this for the two evaluator types).

### 2.2 Domain boundaries (locked, `SYSTEM_ARCHITECTURE.md`, Step 38)

Ten domains, each with one stated responsibility (38.3–38.17): Identity & Access · Contract & Document Management · Document Storage · Document Processing · Legal Configuration · Requirement & Clause Mapping · Evaluation & Findings · Review Workflow · Legal Decisions · Audit & Version History (+ Reporting/Export). The single most load-bearing sentence for this entire document is **38.28's source-of-truth chain**:

> Customer Contract → Evidence → Company Configuration → Deterministic Analysis → Finding → Human Legal Decision. **"The UI, reports, exports, and future AI features are consumers of this source of truth, not replacements for it."**

Any AI subsystem is, by this rule, either a new tenant of the "Analysis Interface" abstraction (38.25, the literal hook `AI-02` cites) or a presentation-layer consumer of already-recorded Findings/Evidence. It is not an eleventh domain, and it cannot write to `findings` or `legal_decisions`.

### 2.3 Ingestion is synchronous today — no Celery parsing task exists

**FACT**, verified by direct code read. Upload, MIME validation, storage, and text/OCR extraction all run **inline in the HTTP request thread**: `POST /contracts/{id}/document-versions` → `ingest_document()` → `process_document_version()` ([backend/legalmind/ingestion/service.py:82-211](../../backend/legalmind/ingestion/service.py#L82-L211)), which calls `parsing.parse()` synchronously and writes `DocumentEvidence` rows before the response returns. The **only** Celery task in the codebase is `analysis.analyse_review` ([backend/legalmind/worker/tasks.py](../../backend/legalmind/worker/tasks.py)), dispatched only when a Review is explicitly created — not on upload.

This matters because the brief that generated this document's predecessor analysis assumed an "upload → Celery parsing" pipeline already existed. It does not. Any embedding-generation step must attach as a **new** async hook — see §6.

### 2.4 AI-03's stated precedent does not exist

**FACT.** `grep -rli spacy` across the entire backend and `pyproject.toml` returns zero matches. No NLP/ML library is installed (`fastapi`, `pydantic`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `pymupdf`, `python-docx`, `celery[redis]` is the complete dependency list). This is a discrepancy between the locked text (44.31: *"A controlled classical NLP layer can be used where it genuinely helps: spaCy"* — permissive, not asserting it's wired in) and this document's earlier framing that assumed a working precedent. **Correction, per rule 5:** `AI-03` *permits* spaCy; it never claims spaCy is already integrated. The nearest actual isolation precedent in the codebase is the mapping/extraction gate: `extract_liability_facts()` is pure regex ([backend/legalmind/extraction/liability.py](../../backend/legalmind/extraction/liability.py)), and facts are only computed from a `MappingState.CONFIRMED` clause ([backend/legalmind/analysis/service.py:396-421](../../backend/legalmind/analysis/service.py#L396-L421)) — an `AMBIGUOUS` mapping yields **no facts at all**, failing the evaluator closed. This discrete-gate pattern, not a copy of working spaCy code, is the template a new assist layer's isolation should follow.

### 2.5 No existing external egress, no existing vector/LLM code

**FACT.** A repo-wide grep for `vector`, `embedding`, `pgvector`, `openai`, `anthropic`, `llm`, `rag` (case-insensitive) returns exactly one hit, a negative/confirming comment: `legalmind/mapping/scoring.py:3-4` — *"Locked 35.1/35.2: mapping is deterministic; no LLM, RAG, vector database or semantic AI."* A separate grep for `httpx`/`requests`/`urllib`/`aiohttp`/any `http(s)://` literal finds **zero outbound HTTP client calls anywhere in `legalmind/`**. `httpx` is present only as a dev/test dependency (`starlette.testclient` needs it). The Celery broker URL is the only externally-configurable network target, and it's an internal message queue, not a third-party API. **Consequence:** a future LLM/embedding API call would be the first external network egress this codebase has ever made — not an extension of a pattern, a wholly new one (redaction hooks, egress logging, timeout/retry policy — none of it exists to reuse).

### 2.6 What "deterministic" concretely means (the two evaluator contracts)

Both evaluators locked in Steps 45A–45D share five properties worth stating precisely, because an LLM-based evaluator violates at least four of them by construction:

| Property | `NUMERIC_COMPARISON` (`LIABILITY-001`) | `PRESENCE` (generic) |
|---|---|---|
| Reads raw clause text at evaluation time? | No — reads only structured `facts` already extracted upstream | **Never** — [PRESENCE_EVALUATOR.md](../04-analysis-engine/EDGE_CASES/PRESENCE_EVALUATOR.md) P.1: *"the evaluator never reads clause text"* |
| Output vocabulary | Closed enums only (`cap_status`, `classification`, `rule_outcome`) | Closed lookup table (P.5.1), no free text |
| Explanation mechanism | *"a deterministic explanation, not AI-generated prose"* (45B, line 724) | Same |
| Reproducibility | Identical input ⇒ byte-identical output (ties to `ENG-11`) | Same |
| Gap-filling | Never invents a value for a missing clause — absence ≠ zero (45B.26) | `DEVIATION` is *structurally unproducible*: "a deviation requires a compared value, which presence-mode has none of" |

An LLM-based evaluator would necessarily (i) read raw text directly — violating PRESENCE's core constraint and blurring Mapping ≠ Evaluation (`ENG-03`); (ii) produce free-text/probabilistic output needing a new discretization step into the five closed axes; (iii) risk non-reproducibility across runs/model versions, in direct tension with Tier-1 golden-corpus normativity (§2.7); and (iv) require an explicit amendment to `AI-01`/`AI-03`/`AI-04` and to locked item 16 (*"the system does not use generic AI confidence scores"* — dropped from the registry's paraphrase, present verbatim in `all_lock.md:11561`) before it could touch this layer at all. It is therefore excluded from this proposal's scope by construction, not by caution — see §4.

### 2.7 Testing philosophy is built on byte-identical determinism — structurally excludes an LLM from Tier 1

**FACT.** [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md) makes the golden corpus (64 fixtures) the *normative* base of the test pyramid, not unit tests: *"a diff is a specification change until proven otherwise"* (54.2). `54.3` requires *"identical inputs + identical configuration snapshot + identical evaluator version → byte-identical output... No hidden inputs: no clock, random source, locale or environment variable changes an evaluation result."* The document never discusses stochastic/ML testing — because V1 has none. A non-deterministic component (temperature > 0, a model that gets silently upgraded, a retrieval index that reranks differently run to run) is structurally incompatible with Tier 1 as currently defined. It could at most live at a new, explicitly non-gating tier — the same precedent [STEP_54_TESTING_STRATEGY.md] already sets for the Playwright browser suite (*"supporting, not a locked tier and not a release gate"*).

### 2.8 Frontend boundary (locked, Step 52)

**FACT.** There is no BFF — Next.js calls `/api/v1/...` directly, session-cookie-authenticated; SSR may pre-fetch *through the API*, never through a repository or DB client (52.2). Three rules the frontend must never violate: never touches the database (52.1.1/38.22); never implements legal logic — *"No classification, no roll-up derivation, no rule evaluation... every such value is rendered as received"* (52.1.2/38.23); permission gating in the UI is presentation only (52.1.3/47.6). `52.4`'s confidentiality rule — omitted fields render as *absent*, never as a placeholder or lock icon, because a visible marker would itself leak that an internal legal position exists — must be inherited server-side by any future AI Q&A surface, not re-implemented client-side. `52.7` establishes the only pattern for long-running async work today: poll or stream via the API, no optimistic UI for anything legal — the template a future LLM job's UI must also follow.

### 2.9 Deployment topology and the dependency-approval precedent

**FACT**, [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md): *"Workers run the same application image as the API; a Review's analysis is a job, not a separate service. No microservice decomposition in V1 (locked 38.26)."* Environments are Development (synthetic data only) / Staging (production-shaped, **no real counterparty contracts**) / Production (real legal documents) — *"Real contracts never leave production."* This bears directly on any future embedding/index/fine-tuning pipeline: real counterparty text cannot be exported to staging, dev, or a third-party API today without a new explicit decision.

`IMPL-01` forbids any technology, dependency, or service beyond the Step 39 stack without ratification — `HANDOFF.md:294-295` shows this gate being exercised for something as mundane as an OIDC JWT/JWKS client library. A GPU/inference runtime, a vector-DB extension, or a third-party LLM SDK all sit squarely in the same category, and — unlike the OIDC case — additionally require the underlying `AI-01` boundary itself to be *"explicitly revisited and changed"* (the Hard V1 Constraint, `all_lock.md:1137`). **Two separate approval gates, not one.**

### 2.10 No workspace/tenant primitive exists

**FACT**, confirmed by grep — `workspace` and `tenant` appear nowhere in `backend/legalmind/db/models.py`, `legalmind/security/`, `SYSTEM_ARCHITECTURE.md`, or `USER_ROLES.md`. V1 is single-tenant at the database level: ownership is `Contract.owner_id → users.id`, and roles (`USER`, `LEGAL_REVIEWER`, `LEGAL_ADMIN`, `SUPER_ADMIN`, `LEGAL_DECISION_AUTHORITY`) are global, not scoped to an organization/workspace object. Several of this brief's questions (§8 "permission-aware retrieval," §11 "tenant isolation") presuppose a workspace concept that does not exist yet. **This is not this document's gap to fill** — if multi-tenant isolation is a real product requirement, it is `NOT YET SPECIFIED` and needs its own product-owner decision entirely independent of AI/RAG (rule 8). Everything below is written against the ownership model that actually exists (`owner_id`, and role-scoped permissions), not an assumed workspace model.

---

## 3. Architectural Principles — the locked AI boundary, verbatim

Per rule 3 ("never silently modify a locked decision") and the finding in §2.4 that the registry paraphrase drops a materially important clause, the exact locked text is reproduced here rather than summarized.

**`AI-01`** — *"V1 AI Boundary — Locked Decision"* (`all_lock.md:1027-1137`):

> LegalMind V1 will remain a deterministic, explainable, versioned, permission-controlled, and auditable legal comparison and workflow system.
>
> **V1 will NOT use:** LLM · RAG · Vector database · Embeddings · AI-generated legal decisions · Autonomous legal reasoning. *These technologies are explicitly outside the V1 implementation scope.*
>
> **Post-V1 AI direction:** *"After V1 is working in real-world usage, actual limitations will determine whether AI capabilities are justified... AI should be added only when a demonstrated V1 problem requires it. It should not be introduced merely because LegalMind is a legal application."*
>
> **Architectural principle for future AI:** *"If AI is introduced after V1, it should sit on top of the V1 foundation, not replace it."* The following remain authoritative: Clause Library, Requirements, Company Standards, Legal Positions, Reviews, Evidence, Version history, RBAC, Audit trail. *"Future AI may assist with language understanding, semantic matching, retrieval, or other clearly defined tasks, but it must not silently become the source of truth for company legal policy or final legal decisions."*
>
> **Hard V1 constraint:** *"Do not introduce LLM, RAG, vector database, embeddings, or AI-generated legal decisions into LegalMind V1 unless this locked decision is explicitly revisited and changed."*

**`AI-02`** — Step 38 locked items 20–21 (`all_lock.md:5972-5973`):

> 20. *"The architecture exposes a clean analysis boundary so future LLM/RAG capabilities can be evaluated later without becoming the V1 legal source of truth."*
> 21. *"The deterministic V1 Analysis Engine remains the authoritative source for V1 Findings."*

(Note: the registry's gloss "without redesign" is a paraphrase — the locked text says "without becoming the V1 legal source of truth." This document treats §2 as the empirical check on the redesign question; the locked text itself doesn't promise "zero code changes," only "no change of authority.")

**`AI-03`** — Step 44, 44.31–44.32 + locked items 16, 19, 20 (`all_lock.md:11167-11565`):

> 44.31: *"A controlled classical NLP layer can be used where it genuinely helps: spaCy, for... sentence segmentation, tokenization, linguistic normalization, selected entity extraction. But it should not become the legal decision-maker. The authoritative result still comes from deterministic evaluators and rules."*
>
> 44.32: *"For V1: no vector database and no semantic retrieval. However, a future architecture may evaluate semantic retrieval separately."*
>
> **Item 16 — easy to miss, load-bearing for this entire document:** *"The system does not use generic AI confidence scores."*
> Item 19: *"Classical NLP libraries such as spaCy may assist extraction/segmentation but cannot determine the legal result."*
> Item 20: *"V1 does not use LLM, RAG, embeddings, or vector search in the authoritative legal-analysis path."*

**`AI-04`** — Step 43 locked item 23 (`all_lock.md:10076`, restated `:10108`):

> 23. *"No LLM/RAG/vector database is introduced into the V1 legal-analysis path."*
> *"Async processing, server-side authorization, idempotency, configuration snapshots, auditability, and the no-LLM/no-RAG V1 boundary are all locked."*

**This document's operating principle**, derived directly from the above: **an AI feature may be added the moment it is (a) assistive only, (b) never the source for any of the five state axes (§4), and (c) architecturally incapable of writing to `findings`/`evaluations`/`legal_decisions`/`configuration_snapshot*`.** No revisiting of `AI-01` is required for anything meeting all three conditions. Any feature that fails one of them is out of scope for a "post-V1 assist layer" and would require `AI-01` to be explicitly reopened — which this document does not propose and is not authorized to propose (rule 6).

---

## 4. AI vs Deterministic Responsibility Matrix

The state model this matrix must never violate ([DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md)) has five controlled axes — **Mapping State**, **Finding Classification**, **Rule Outcome**, **Legal Decision**, **Review Lifecycle** — plus one explicit non-axis, `UNMATCHED_PROVISION`. The single sentence that bounds every row below ([GLOSSARY.md:127](../00-project/GLOSSARY.md)):

> *"Explainability contract — every Finding must be reconstructable as Evidence → Fact → Standard → Rule → Result. ⚠ No generic risk score, no 'AI confidence' percentage."*

**"The LLM found something" vs. "LegalMind determined something"** is the line every row below draws. An LLM may surface a candidate, a rephrasing, or a ranking. It may never itself set a value on any of the five axes, and any signal about its own uncertainty must never be presented as, or stored alongside, a legal outcome — that's the one item (`item 16`) the registry summary silently drops.

| Task | Classification | Why |
|---|---|---|
| Clause identification (locate candidate boundaries) | **LLM allowed** | Pure text-location aid; today done by regex/section detection. An LLM candidate never itself becomes evidence — it's a UI hint, or a second signal for a human/deterministic reviewer. |
| Clause classification → Requirement (Mapping State) | **MUST remain deterministic** for `CONFIRMED`; **LLM allowed** only as a triage aid on `AMBIGUOUS`/`UNRESOLVED` clauses shown to a human | This axis feeds facts into the evaluator (§2.1). Locked Step 28 keeps mapping deterministic; an LLM can highlight candidates for human attention but cannot itself set `CONFIRMED`. |
| Semantic similarity ("clauses like this one") | **LLM allowed** | The canonical RAG use case — informational only, never referenced by any Finding. |
| Obligation / definition / entity extraction, *shown to a reviewer, not persisted to any Fact* | **LLM allowed** | Navigation/comprehension aid. |
| Obligation / entity extraction, *feeding a Fact object the evaluator reads* | **LLM + deterministic validation**, and only if a deterministic check (schema + evidence-grounding) gates before persistence — in practice this is likely **MUST remain deterministic** given the locked Fact Extraction contract's closed vocabulary | Facts feed axis 2/3 directly; the locked evaluator contract already forbids inventing values to fill gaps (45B.26). |
| Cross-reference resolution | **LLM allowed** | Reader-facing navigation, not evaluative. |
| Contract summarization | **LLM recommended**, evidence-grounded, explicitly labeled a summary, never a Finding | Rule 12: every Finding must decompose to Evidence→Fact→Standard→Rule→Result; a summary is not that and must never be styled to look like one. |
| Finding explanation, *rephrasing the existing deterministic explanation in plain language* | **LLM + deterministic validation** — every sentence must trace to a field already in the persisted `explanation` object; no new causal claim permitted | 45B (line 724): *"a deterministic explanation, not AI-generated prose."* The deterministic explanation is ground truth; the LLM may only restate it, never extend it. |
| Evidence extraction feeding a Fact | **MUST remain deterministic** | Locked evaluator input contract requires evidence references, deterministically extracted — line 151: *"the evaluator must not go back and independently search the whole document."* |
| Missing-clause detection *for a catalogued Requirement* | **MUST remain deterministic** | This is the existing `MISSING`/`ABSENT` mapping+PRESENCE-evaluator outcome. |
| Missing-clause *discovery* (a clause type not yet in the 32-Requirement catalogue) | **LLM allowed**, surfaced only to `LEGAL_ADMIN` as a catalogue-gap suggestion, never auto-creating a Requirement | New Requirements require the same rule-21 sourcing discipline as any other Company Standard input. |
| Conflict detection *for the authoritative `CONFLICT` Finding* | **MUST remain deterministic** | Existing fixture `DOC-LIAB-04` (MSA §17.2 vs §17.7) is already produced this way. |
| Conflict/contradiction *triage across a large document set, shown as a candidate list* | **LLM allowed** | Pre-filtering aid for a human reviewer; never itself a Finding. |
| Semantic comparison ("meaning differs," not just text) | **LLM recommended**, always paired with the exact source spans of both sides | Must never replace or precede the deterministic text-diff; shown alongside it, evidence-grounded. |
| Risk explanation | **LLM + deterministic validation**, same grounding discipline as Finding explanation | Same rationale as Finding explanation above. |
| Reviewer prioritization/recommendation (which Findings to look at first) | **LLM recommended**, explicitly non-binding, never hides or reorders what the API/DB consider `requires_decision` | Cannot alter Review-lifecycle-derived server state (52.1.2). |
| Legal conclusion (axis 2/3 value) | **MUST NEVER be produced by the LLM** | This is precisely the deterministic engine's job; `AI-01`/`AI-04`/item 20 bar it outright. |
| Approval / Legal Decision (axis 4) | **Human approval required — not even the deterministic engine may produce this** | [GLOSSARY.md:23](../00-project/GLOSSARY.md): *"Only a human with explicitly assigned legal authority makes one. The engine never does."* A fortiori, neither does an LLM. |
| Policy evaluation (axis 3, `ACCEPTABLE`/`UNACCEPTABLE`) | **MUST remain deterministic** | This is exactly what the zero-tolerance Legal Rule already decides (`memory: legalmind-zero-tolerance-legal-rule`); there is no tolerance band for a probabilistic judgment to occupy. |

---

## 5. RAG Architecture

A single "documents → embeddings → vector DB → Gemini" diagram is insufficient for two reasons specific to this codebase: (a) evidence already carries strong provenance (page/offset/section — §2.6) that a naive chunker would throw away, and (b) the authoritative pipeline's isolation discipline (§2.4) has to be re-derived architecturally, not assumed. The proposed shape:

```
Document Evidence (existing, deterministic, write-once)
        ↓  (read-only; new async worker task — §6)
Clause-aware chunking  (anchored on existing section_number / offsets)
        ↓
Parent/child chunk pairs  (child = fine-grained retrieval unit; parent = full clause, assembled as LLM context)
        ↓
Embedding generation  (self-hosted first — §7, §11)
        ↓
pgvector store, FK-linked to document_evidence (§8, §10)
        ↓
Hybrid retrieval: vector similarity + Postgres full-text search, fused (RRF)
        ↓
Reranking (cross-encoder or equivalent) — OPEN, see §8
        ↓
Context assembly with mandatory per-chunk citations
        ↓
Gemini Flash (generation/interpretation only)
        ↓
Schema + citation + permission + grounding validation (§13)
        ↓
Human-facing suggestion, explicitly labeled, never a Finding
```

### Chunking strategy — comparison and recommendation

| Approach | Fit for legal contracts | Verdict |
|---|---|---|
| Fixed token chunks | Cuts across clause boundaries; breaks the "one chunk = one legal idea" property citations depend on | **Not recommended** as primary strategy |
| Paragraph chunks | Better, but multi-paragraph clauses (common in liability/indemnity sections) still get split with no structural marker | Fallback only, when no section boundary exists (e.g. malformed OCR) |
| **Clause/section-aware chunks** | Matches the document's own numbering (`§17.2`), matches existing `section_number`/`section_title` evidence metadata exactly | **RECOMMENDATION: primary strategy** |
| Hierarchical / parent-child | Retrieve on a small, precise child (a sentence or sub-clause) for relevance; assemble the LLM's context from the full parent clause for coherence | **RECOMMENDATION: layer on top of clause-aware chunking** — this is the two-tier shape RAG literature converges on for long structured documents, and it maps naturally onto the MSA's existing `§17` → `§17.2` nesting |

**RECOMMENDATION:** clause-aware chunking as the child unit, with the parent chunk being the full section the evidence's `section_number` already identifies — both derived mechanically from existing `document_evidence` rows, so chunk boundaries never have to be re-invented from raw text.

### Metadata per chunk

| Field | Source | Why it must be there |
|---|---|---|
| `document_version_id`, `evidence_id` (or offset range) | Existing evidence row | Traceability (rule 11) and the immutability guarantee (§12) |
| `page_number`, `section_number`, `section_title` | Existing evidence row | Citation display |
| `start_offset`/`end_offset` | Existing evidence row | Exact-span grounding |
| `owner_id` (via join, not duplicated) | `contracts.owner_id` | Authorization filter (§10) — **join, never denormalize**, so it can't drift out of sync with the real ownership record |
| `document_type` | `Contract.contract_type` | Scoping (an NDA-typed chunk should never surface for an MSA-liability query, mirroring the existing document-type evaluator filter) |
| `confidentiality_level` | **OPEN QUESTION** — no such field exists on `Contract`/`DocumentVersion` today; would need product-owner definition before being added | Flagging rather than inventing a value (rule 7's adjacent trap: don't manufacture a classification scheme that doesn't exist) |
| `chunking_algorithm_version`, `embedding_model_version`, `assist_run_id` | New, append-only | Reproducibility (§12) |
| `source_type` | Existing evidence row (`NATIVE_TEXT`/`OCR`/`TABLE`/`OTHER`) | An OCR-derived chunk should be visibly lower-confidence for citation display |

"Tenant/workspace" and "upload timestamp" from the brief's example list are addressed by: upload timestamp already exists (`DocumentVersion.created_at`, carried by join, not duplicated); tenant/workspace does not exist as a concept in V1 at all (§2.10) and is not invented here.

---

## 6. Document Intelligence Pipeline

Revising the eight-stage decomposition in the brief against what actually exists:

| Brief's stage | Exists today? | Where it actually lives / what changes |
|---|---|---|
| Document ingestion | **Yes, but synchronous** (§2.3) | Unchanged — the new pipeline reads its output, never its input |
| Document normalization (text, layout, pages, tables) | **Yes** — `legalmind/ingestion/parsing.py` | Unchanged; already produces normalized `content` + `evidence_metadata.original_content` |
| Structural intelligence (clauses, sections, cross-refs, entities) | **Partially** — section numbering only (`detect_clause_number()`); no entity/cross-ref/definition extraction exists | New, assist-only capability (§4 rows) |
| Deterministic analysis | **Yes, locked, unchanged** | Never touched by anything below this line |
| Retrieval (RAG) | **No** | New — §5, §8 |
| LLM reasoning/interpretation | **No** | New — §7 |
| Evidence grounding | **Partially** — evidence exists for the deterministic path; grounding for AI *output* is new | New validation step, §13 |
| AI output validation | **No** | New, §13 |
| Human-facing result | **Yes, for Findings** | AI output is a **new, separate** presentation category, never merged into the Finding/Evidence/Explanation/Recommendation/Decision structure that already exists for the deterministic path |

**The seam:** after `DocumentProcessingRun` reaches `COMPLETED` ([backend/legalmind/ingestion/service.py:130-211](../../backend/legalmind/ingestion/service.py#L130-L211)), a new Celery task (`index_document_version`, symmetric to the existing `analyse_review` dispatch pattern in `worker/dispatch.py`) reads the committed evidence, chunks it, embeds it, and writes to new tables — never touching `document_evidence` itself (write-once) or anything in the analysis/evaluation/workflow modules. This keeps the request path's latency unchanged and requires no change to any existing table.

---

## 7. Gemini Flash Role

Gemini Flash is a plausible fit for extraction/summarization-tier tasks (§4's "LLM allowed"/"LLM recommended" rows) given its cost/latency profile (§25), but it is **not** the only model decision this architecture needs, and should not be asked to do everything:

| Task class | Recommended tier | Why |
|---|---|---|
| Embeddings for retrieval | A dedicated embedding model (self-hosted open embedding model, e.g. a sentence-embedding model run in-cluster), not Gemini generation | Retrieval quality is far less sensitive to model choice than generation; self-hosting keeps clause text off any third-party API for the highest-volume, most mechanical step (§11) |
| Extraction / classification-assist (candidate clause location, entity/definition surfacing) | Gemini Flash **or** a smaller/self-hosted model | Cheap, high-volume, tolerant of occasional error since a human or deterministic gate reviews the output |
| Summarization / explanation rephrasing / semantic comparison | Gemini Flash (or a comparably capable model) | Needs more reasoning quality; still bounded by mandatory grounding validation (§13) |
| Legal conclusion, policy evaluation, Legal Decision | **No model, of any tier** | Barred outright by §4/§3 |

**RECOMMENDATION:** model routing, not a single model — cheap/fast for high-volume mechanical extraction, a stronger model only where reasoning quality materially matters, and the deterministic engine unconditionally for anything in §4's "MUST remain deterministic" or "Human required" rows. This is not a Gemini-specific architectural need; it follows from the task variety in §4 regardless of vendor.

---

## 8. Retrieval Architecture

**RECOMMENDATION: hybrid retrieval, not vector-only.** Lexical search (Postgres full-text search) catches exact defined terms, section numbers, and party names that a paraphrase-tolerant embedding can miss; vector search catches semantic paraphrase lexical search misses. This is now broadly convergent industry practice (§25 item 7) — not a Gemini or pgvector-specific claim, but a property of legal text specifically (dense with exact citations, defined terms, and numbering that must match exactly).

**Reranking: RECOMMENDATION, not settled fact.** A cross-encoder (or equivalent) reranking stage after hybrid fusion, before the LLM call, is common current practice and plausibly worth the added latency for a legal-QA use case where a wrong top-1 chunk is a bigger cost than in casual search — but the specific improvement numbers found in vendor research (§25 item 7) are blog-sourced, not independently verified, and should not be quoted as fact in any decision-grade follow-up.

**Multi-stage retrieval / query expansion / contextual retrieval:** not evaluated in depth here — flagged as an **OPEN QUESTION** for the prototype phase (§27) once real usage patterns (short keyword queries vs. long natural-language questions) are observed, rather than designed against a hypothetical.

**Permission-aware retrieval — where authorization must happen:**

```
User → session (Guard resolves Principal, existing security/sessions.py)
   → guard.<object>(id, permission)   — EXISTING pattern, reused, never re-implemented
   → SQL: WHERE document_version_id IN (subquery of visible ids)   — pre-filter, not post-filter
   → pgvector ANN search + full-text search, already scoped to visible rows
   → reranking (only ever sees pre-authorized candidates)
   → Gemini (only ever sees pre-authorized, already-retrieved chunks)
```

**The LLM never enforces permissions and is never the last line of defense.** Authorization happens once, in the SQL that produces the candidate set, before any vector or lexical scoring runs — this mirrors the exact discipline the existing `Guard` object already applies (visibility-before-permission-before-DB-operation, [api/deps.py:85-213](../../backend/legalmind/api/deps.py#L85-L213)). **Pre-filtering, not post-filtering, matters specifically because post-filtering (search everything, discard afterward) creates a result-count/ranking oracle** — precisely the kind of side channel the existing byte-identical-404 discipline (`API-10`) exists to close. pgvector's **iterative index scans** (v0.8.0+, FACT — §25 item 6) exist to make pre-filtered ANN search efficient under a selective `WHERE` clause; without them, a highly selective permission filter can starve a fixed-candidate ANN scan (pgvector's own README example: ~4 rows returned under a 10%-selectivity filter with default HNSW settings) — this is a real performance risk to design around, not a hypothetical.

---

## 9. Evidence Architecture

Proposed schema (new tables only — nothing existing is altered):

```
document_chunks
    id                       PK
    document_version_id      FK → document_versions.id
    evidence_id               FK → document_evidence.id   (or a start/end range across evidence rows)
    parent_chunk_id           FK → document_chunks.id, nullable (parent/child link)
    page_number, section_number, section_title, source_type   — carried forward from evidence, not re-derived
    start_offset, end_offset
    content                   — the chunk text, a strict substring/concatenation of evidence.content
    chunking_run_id           FK → a new append-only assist_runs table
    chunking_algorithm_version

document_chunk_embeddings
    id                        PK
    chunk_id                  FK → document_chunks.id
    embedding                 vector(N)   (pgvector)
    embedding_model_id, embedding_model_version
    created_at
```

This is the concrete instance of the brief's `Evidence { documentId, documentVersion, page, section, clause, text, offsets, retrievalScore, sourceType }` object — with `retrievalScore` deliberately **not stored on the chunk row itself** (it's a property of one specific query, not the chunk), instead returned only in a query-time result object alongside the chunk. Storing a score on the row would make it look like a persistent property of the document, which it is not.

**No embedding-only, provenance-free row is ever created.** Every embedding traces, via `chunk_id → evidence_id → document_version_id`, back to the exact deterministic evidence it was derived from — the same discipline `finding_evidence`/`evaluation_evidence` already apply to the authoritative path, extended (not copied verbatim, since this is assist-only output) to the assist path.

---

## 10. Authorization Architecture

Every AI-facing read must pass through the same ownership chain the deterministic path already enforces: `document_chunks.document_version_id → document_versions.contract_id → contracts.owner_id`. Concretely:

- **New `Guard` method** (`guard.document_chunk(...)` or reuse `guard.document_version(...)` before running any retrieval), following the exact visibility-then-permission pattern already in [security/authorization.py](../../backend/legalmind/security/authorization.py).
- **New permission** (e.g. `assist.suggestion.view`), added to the existing permission catalogue, gated the same way `legal_position.view` gates `redact_legal_position` today.
- **A `NotVisible` result must be indistinguishable from "no matching chunks"** — the same byte-identical-404 discipline (`API-10`) applies to a semantic search result set as to any other object lookup; result count, ranking, or latency differences that reveal a hidden chunk's near-match are an enumeration oracle exactly as much as a differently-worded 404 would be.
- **Database-level backstop (recommended, not just application-level):** the assist worker's Postgres role should hold SELECT-only grants on `document_evidence`/`document_versions`/`contracts` and INSERT/UPDATE only on the new `assist_*`/`document_chunk*` tables — zero grants on `findings`/`evaluations`/`legal_decisions`/`configuration_snapshot*`/`reviews`. This is enforceable independently of application-code correctness, and is the strongest available evidence for "kept demonstrably outside the authoritative path" (§16, §26).

---

## 11. Confidentiality / Security Architecture

| Concern | Current state | What a RAG/LLM layer must do |
|---|---|---|
| Tenant isolation | **No workspace/tenant primitive exists** (§2.10) | Isolation is per-`owner_id` today; do not design a tenant model that doesn't exist — flag as its own product decision if actually needed |
| Document isolation | `Contract.owner_id`, enforced server-side via `Guard` | Same chain reused (§10) |
| Retrieval isolation | N/A (doesn't exist yet) | Pre-filtered SQL, not post-filtered (§8) |
| Prompt isolation | N/A | Each request's assembled context must be scoped to that user's authorized chunks only — never a shared/cached prompt across users |
| Model API boundaries | **No outbound HTTP call exists in this codebase today** (§2.5) | New infrastructure: an egress client with logging, timeout/retry policy, and (if API-based) a data-minimization step before send |
| Logging / telemetry | `observability/redaction.py` exists for log redaction, wired to nothing today (no egress to redact) | Any new egress call must log metadata (timing, token counts, model version) **never clause text** — extending the existing redaction discipline, not inventing a new one |
| Prompt storage / cached responses | N/A | **OPEN QUESTION** — if caching is used for cost control, cached prompts/responses containing contract text are themselves confidential and need the same access control as the source document, not a separate cache-invalidation-only policy |
| Embeddings / vector DB access | N/A | §10 |
| Deletion / retention | Evidence is write-once/append-only; **no confirmed hard-delete path for Contracts was found in this audit** — flagged as unverified, not assumed | Chunk/embedding deletion should cascade from whatever the real document-deletion/retention policy turns out to be — verify that policy before designing cascade behavior, don't assume `ON DELETE CASCADE` is exercised |
| Encryption | TLS + encrypted storage at rest, per `STEP_55_DEPLOYMENT.md` 55.2 | Applies equally to new tables; no exception |
| Provider data handling / training-use | Not applicable today (no provider relationship exists) | **The load-bearing decision — see §25 item 3.** Free-tier direct Gemini API use is confirmed by primary source to train on submitted content; paid-tier and Vertex AI are directionally better but not fully primary-verified in this pass |
| Real-contract handling under existing environment rules | `55.3`: real contracts never leave production; `54.6`: golden fixtures use only synthetic/cleared text, never real counterparty contracts | Any embedding/index build over real counterparty contracts must happen in production only, and must never be exported to a third party without resolving item 3 above first |

**The single highest-leverage decision in this entire document is item 3 of §25**, because it determines whether generation can touch real contract text via a third-party API at all, or must be self-hosted. This document does not make that decision — see §26.

---

## 12. Versioning / Reproducibility

Everything the brief asks to be versioned maps onto a pattern the codebase already has and enforces (append-only `*_version` rows, `ConfigurationSnapshot`, `evaluator_version` fingerprinting) — extended, not reinvented:

| Must be versioned | Mechanism |
|---|---|
| Source document version | Already exists — `DocumentVersion` |
| Chunking algorithm | New `chunking_algorithm_version` column, append-only re-chunk on change (never overwrite) |
| Embedding model + version | New `embedding_model_id`/`embedding_model_version` on `document_chunk_embeddings`; a model upgrade adds new rows, never overwrites old ones (mirrors how a `RequirementVersion` upgrade works today) |
| Vector index / retrieval configuration | New `assist_runs`-style append-only record per (re)build |
| Reranker version, prompt version, Gemini model version, temperature/config, output schema version | All new — a single **AI Analysis Record** per assist invocation (below) |
| Deterministic legal configuration | Unchanged — `ConfigurationSnapshot`, already immutable |

**Proposed minimum AI Analysis Record** (answers "why did this suggestion appear, on that date"):

```
assist_invocation_id, user_id, document_version_id (or review_id, if in that context)
retrieval_config_version, chunking_algorithm_version, embedding_model_version
retrieved_chunk_ids[]   (exact set, not just a count)
model_id, model_version, prompt_version, system_instructions_version, temperature/config
output_schema_version, raw_output (or a durable reference to it), validated_output
timestamps, human_action_taken (viewed / dismissed / acted-on — never "approved" in the Legal Decision sense)
```

This record must live in its own new table, **never** the `audit_events` table used for the authoritative audit trail — conflating the two would risk exactly the "shared `.status` namespace hazard" this codebase's own recent review history has already flagged once (per the git log) for an unrelated pair of tables. A dedicated `assist_events` table, cross-linked but distinct, keeps the append-only authoritative audit trail (`AUD-*`) uncontaminated by a much higher-volume, non-legal record stream.

**The critical guarantee this must never violate:** because `analysis/service.py` reads only through `configuration_snapshot_items` and the mapping-selected evidence set (§2.6), and none of the new tables above are referenced by either, re-indexing or re-embedding a document — for any reason, including a full model upgrade — **cannot retroactively change an existing Review.** This is architecturally guaranteed by the new tables' isolation, not merely a promise.

---

## 13. AI Output Validation

The brief's proposed validation chain is broadly right; this document tightens it against what already exists in the codebase and adds the one step legal-domain use specifically needs:

```
Gemini output
   ↓ Schema validation        (responseSchema — FACT: syntactically enforced, semantically NOT guaranteed, §25 item 2)
   ↓ Grounding validation      (every claim must map to a specific retrieved chunk_id already authorized for this user)
   ↓ Citation validation       (the cited chunk's content must actually support the claim — not just "a citation exists")
   ↓ Permission validation     (redundant-but-cheap re-check: every cited chunk_id belongs to the pre-authorized candidate set — never trust the model to have respected scope)
   ↓ Deterministic-conflict check   (if the AI output touches anything the deterministic engine has an opinion on — e.g. a Finding's existing classification — the deterministic value always wins; a disagreement is surfaced, never silently overridden in either direction)
   ↓ Confidence/uncertainty surfaced to the human as an assist signal — NEVER stored as, or displayed alongside, a Finding/Evaluation field (item 16)
   ↓ Human review where the task class in §4 requires it
```

**Malformed output / retry:** Google's own docs (§25 item 2) explicitly caveat that `responseSchema` guarantees syntactic JSON validity, not semantic correctness — *"always validate values in your application."* **RECOMMENDATION:** fail closed on the first malformed-JSON response (bounded retry, then surface "assist unavailable" rather than degrading to free text) — this is a direct extension of rule 15's fail-closed philosophy into the assist layer, even though the assist layer's own output is never a Finding.

**Hallucination detection, concretely:** the grounding + citation validation steps above are the actual mechanism, not a separate "hallucination detector" model — an unsupported claim is definitionally one that fails citation validation, so there is no need for (and no reliable way to build) a third, independent hallucination classifier on top.

---

## 14. Hybrid Analysis Patterns

| Pattern | Description | Verdict for LegalMind |
|---|---|---|
| A: LLM → deterministic engine | LLM output feeds the evaluator as if it were extracted fact | **Rejected** — violates the locked evaluator input contract (§2.6); the evaluator "must not go back and independently search the whole document," and an LLM output is exactly that kind of unvetted re-search |
| B: Deterministic engine → LLM explanation | Deterministic Finding/Evaluation is the input; LLM only rephrases | **Recommended for the "explanation" task class** (§4) — directly matches the grounding-validation discipline in §13 |
| C: LLM extraction → deterministic evaluation → LLM explanation | LLM pre-extracts candidate facts, a deterministic step validates/gates them, only validated facts reach the evaluator, then LLM explains the result | **Plausible for a narrow, explicitly-scoped extraction task** (e.g. entity/definition surfacing) — but note the "deterministic evaluation" step here would need real validation logic, not a rubber stamp, or this degenerates into Pattern A with an extra step |
| D: RAG → LLM interpretation → deterministic verification | Retrieval feeds LLM interpretation; a deterministic check verifies the interpretation against ground truth before display | **Recommended for semantic comparison / natural-language investigation** (§4's "show me all provisions that could create uncapped liability" example) — the "deterministic verification" step is the citation/grounding validation of §13, applied per-claim |
| E: Parallel AI + deterministic analysis → reconciliation | Both run independently; a reconciliation layer flags disagreement | **Recommended as a longer-term triage tool**, not a v1-of-the-assist-layer priority — useful for surfacing "the deterministic engine said X, the AI's independent read suggests Y, a human should look" without ever picking a winner automatically |

**RECOMMENDATION:** Patterns B and D cover essentially all of §4's "LLM allowed"/"recommended" rows and are the two to build first. Pattern A is excluded outright. Pattern C is usable only for the narrow non-evaluative extraction tasks in §4, with real (not decorative) deterministic gating. Pattern E is a good idea for later, once B/D have real usage data to reconcile against.

---

## 15. Architecture Options

| | **Option A — Conservative Hybrid** | **Option B — AI-Assisted LegalMind** | **Option C — AI-Native Legal Intelligence** |
|---|---|---|---|
| Description | AI limited to summarization/explanation rephrasing only; no retrieval, no chunk-level semantic search | Full RAG stack (chunking, embeddings, hybrid retrieval, Gemini) around the deterministic core, exactly as designed in §5–§13 | Extensive semantic reasoning (multi-document synthesis, natural-language investigation across a corpus, proactive gap detection) with deterministic controls retained as gates, not the whole story |
| Quality | Lower ceiling — no retrieval means no "find me clauses like X" | High for the assist-only task classes in §4 | Highest, but highest exposure to the discretization/grounding problems in §13 |
| Complexity | Low | Medium — new package, new tables, new async task, new egress client | High — same as B plus multi-document retrieval, cross-document conflict triage, more validation surface |
| Cost | Lowest (few, short LLM calls) | Moderate (embeddings at ingestion volume + generation at query volume) | Highest |
| Latency | Lowest | Bounded by async ingestion (§6) + query-time retrieval/rerank/generation | Same plus multi-document fan-out |
| Security/legal risk | Lowest | Moderate — bounded by §10/§11/§13's controls | Highest — more surface area for a grounding failure to reach a user as an apparently-authoritative claim |
| Explainability/reproducibility | Trivial to preserve | Preserved by design (§12, §13) — requires discipline, not luck | Hardest to preserve as scope grows; §7's "no LLM does everything" discipline gets more important, not less |
| Implementation effort | Small | Medium | Large |
| Migration complexity from V1 | Minimal | The §23 staged plan | Same staged plan, extended further |

**None of the three is "automatically correct"** — the brief's own instruction. Option A under-delivers relative to what `AI-02` explicitly anticipates ("semantic matching, retrieval"). Option C's marginal capability gain over B is not clearly worth its materially larger validation/security surface *until B has real production usage data showing where it falls short* — which is exactly the "add AI only when a demonstrated V1 problem requires it" principle `AI-01` itself states.

---

## 16. Recommended Architecture

**Option B**, built in the phases of §23, with three non-negotiable properties carried through from the analysis above:

1. **Structural isolation, proven by mechanism, not assertion.** A new `legalmind/assist/` package; a CI-enforced static-import test asserting `evaluation/`, `analysis/`, `mapping/`, `extraction/`, `workflow/` never import `legalmind.assist`; a Postgres role for the assist worker with zero grants on any authoritative table (§10). Recommended because code-review discipline alone is exactly the kind of thing that erodes silently over many future PRs — a DB-enforced grant does not.
2. **Self-hosted embeddings before any third-party generation call**, because embeddings are the highest-volume, most mechanical step and the one most easily kept off a third-party API entirely; generation (higher value, harder to self-host well) is gated behind the data-egress decision in §26, not bundled with it.
3. **A corpus-parity regression test**, run on every change to the assist layer: the full 45E golden corpus through analysis with the assist worker disabled and enabled, asserting byte-identical Finding/Evaluation output. This is the concrete, automatically-checked proof that §3's operating principle holds — not a one-time code review conclusion that can rot as the codebase changes.

---

## 17. Architecture Diagram

```
                         User (browser)
                              │
                        Next.js frontend            (52.1: no DB, no legal logic, presentation-only gating)
                              │  fetch, session cookie — same for AI features, no BFF
                              ▼
                        FastAPI  /api/v1/...
                              │
                     Guard: Authentication → Authorization        ◄── SECURITY BOUNDARY (unchanged, reused)
                              │
              ┌───────────────┴────────────────────────┐
              ▼                                          ▼
   Existing authoritative path                  NEW assist path (legalmind/assist/)
   (Contract/Document/Mapping/                          │
    Extraction/Evaluation/Workflow)                     │
              │                                          │
              ▼                                          ▼
   document_evidence, findings,               document_chunks, document_chunk_embeddings,
   evaluations, legal_decisions,              assist_runs, assist_events
   configuration_snapshot*                              │
   ◄── SOURCE OF TRUTH (38.28) ──►                      │  read-only join back to document_evidence /
   never written to by the assist path                  │  document_versions / contracts.owner_id for
              │                                          │  authorization (§10) — never duplicated
              ▼                                          ▼
         PostgreSQL (system of record — locked Step 39, holds BOTH; pgvector is an extension on it, not a new service)
                                                          │
                                                          ▼
                                          Celery worker: chunk → embed (self-hosted first)
                                          → hybrid retrieval → rerank → Gemini Flash (generation only, gated — §26)
                                                          │
                                                          ▼
                                          Schema/grounding/citation/permission validation (§13)
                                                          │
                                                          ▼
                                          Human-facing AI suggestion — visually and structurally
                                          distinct from a Finding, never merged into it
```

**Source of truth:** the existing authoritative tables, unchanged. **AI assistance:** the entire right-hand branch — additive only. **Evidence:** `document_evidence` (authoritative) and `document_chunks` (assist-only derivative of it, never the reverse). **Security boundary:** the `Guard` check, identical on both branches. **Human authority:** Legal Decisions remain human-only regardless of which branch produced the Finding they're deciding on.

---

## 18. Data Flow

**Ingestion-time (async, new):**
`Upload (unchanged, synchronous, §2.3) → DocumentProcessingRun COMPLETED → [NEW] dispatch index_document_version → read evidence (read-only) → chunk → embed → persist to document_chunks/document_chunk_embeddings`. No effect on request latency; no write to any existing table.

**Query-time (new, per user action):**
`User asks a question or requests a suggestion → Guard authorizes the object in scope → pre-filtered SQL candidate set (§8) → hybrid retrieval + rerank over that set only → context assembly with citations → Gemini call (egress, logged, never logging clause text itself — §11) → validation (§13) → AI Analysis Record persisted (§12) → response rendered, visually distinct from a Finding (§2.8's confidentiality/omission discipline inherited server-side)`.

**What never happens:** an AI Analysis Record output value flowing into `analysis/service.py`, `evaluation/`, or `workflow/`; a chunk or embedding being read by anything in the authoritative path; a Review's `configuration_snapshot_id` or `document_version_id` changing because an index was rebuilt.

---

## 19. Failure Modes

| Stage | Failure mode | Fallback |
|---|---|---|
| Document → extraction | Already handled today (`ParseError` → `FAILED`, fails closed, §2.3) | Unchanged — the assist pipeline simply has nothing to index for that version until extraction succeeds |
| Chunking | Bad boundaries (e.g. a malformed section number) | Fall back to paragraph chunking for that segment only; flag the chunk's `chunking_algorithm_version` metadata so it's identifiable later, never silently treated as equal-quality to a clean clause-aware chunk |
| Embedding generation | Model unavailable / timeout | `assist_runs` row marked `FAILED`, same append-only discipline as `document_processing_runs`; retried, never partially applied and treated as complete |
| Retrieval | Wrong/irrelevant evidence returned | Surfaced with visible retrieval score; a "no confident match" state is a valid, honest response — never padded with a low-relevance chunk to look complete |
| Reranker | Wrong ranking | Bounded impact — reranking only reorders an already-authorized, already-retrieved candidate set; a reranker failure degrades relevance, never security |
| Gemini call | Hallucination | Caught by grounding/citation validation (§13), not trusted on the model's own confidence signal |
| Structured output | Malformed JSON | Bounded retry then fail closed to "assist unavailable" (§13) |
| Citation | Unsupported claim | Rejected at validation; never shown to the user as if grounded |
| Deterministic-conflict check | AI output disagrees with an existing Finding | Deterministic value always wins for display; disagreement itself is a useful signal, logged, never auto-resolved either direction |
| Permission | A retrieval query somehow returns a chunk outside the pre-authorized set (defense-in-depth failure) | Redundant permission-validation step in §13 catches this before it reaches the model or the user; this should never happen if §8's pre-filtering is implemented correctly, but the check exists because "should never happen" is not the same as "cannot happen" |
| Model API | Timeout / rate limit (Gemini's own docs disclaim any guaranteed rate limit or, on the standard tier, any SLA — §25 item 5) | Async job, not a blocking user-facing call; user sees "still working" / bounded wait, never a hung request thread |

---

## 20. Evaluation Framework

**Retrieval quality:** Precision/Recall/MRR or nDCG against a held-out query set with known-relevant chunks. **Extraction quality:** Precision/Recall/F1 against manually-labeled spans, for any extraction task class in §4. **Groundedness:** for every claim in an AI output, does the cited chunk actually entail it — measured by human spot-check initially, with the automated citation-validation step (§13) as a cheap proxy, not a substitute. **Citation accuracy:** does the citation's chunk_id/offset genuinely correspond to the quoted text — mechanically checkable, should be close to 100% by construction (a failure here is a bug in §13's validator, not a model-quality metric). **Legal-rule consistency:** for any AI output that touches something the deterministic engine already has an opinion on, agreement rate — tracked, but a *low* agreement rate is not necessarily bad; it might mean the AI is (correctly) surfacing something the catalogue doesn't cover yet (§4's "missing-clause discovery" row), so this metric needs human review to interpret, not an automatic pass/fail threshold.

**Hallucination rate, human acceptance rate, false positive/negative rate, latency, cost per analysis:** all need real usage data before targets can be set meaningfully — this document does not invent target numbers (that would be exactly the kind of invented threshold rule 7 warns against, applied to a product metric instead of a legal one).

**Golden dataset strategy — RECOMMENDATION, with an explicit caveat:** an AI-evaluation dataset is *not* the golden corpus (45E) and must not be confused with it — 45E is normative for the deterministic engine (§2.7) and stays exactly as is. A separate, smaller "AI assist eval set" should be built from the same source-material discipline as the rest of this project (rule 21: real or explicitly-labeled-synthetic specimens, never invented as if real) — and, per §11's environment rules, must respect the same real-contract-never-leaves-production and synthetic-only-in-lower-environments constraints the rest of the testing strategy already enforces.

---

## 21. Observability

Extending [STEP_53_OBSERVABILITY.md](../09-implementation/STEP_53_OBSERVABILITY.md)'s existing audit-vs-diagnostics-vs-logs split (§12 above) to the assist layer's own signals: token usage and cost per call; retrieval latency and generation latency, tracked separately (they fail independently — §19); malformed-output rate and citation-failure rate (both should be near-zero and any rise is a validator or model-version signal, not a UX nuisance to shrug off); retrieval-miss rate (queries returning no confident match); human-correction/dismissal rate on AI suggestions (the single most useful signal for whether the feature is actually helping, and the input a completeness-critic-style review should use to decide what to build next). **None of this should be emitted to the same signal namespace as the existing `workflow.decisions.*`/`authz.*` observability signals** — mixing an assist-layer's noisy, high-volume, non-legal signal stream into the same dashboards as the authoritative workflow's signals would make the latter harder to read, for no benefit.

---

## 22. Cost / Performance Considerations

**Cost drivers, without inventing numbers not independently verified (§25):** embedding cost scales with total document volume at ingestion time (one-time per document version, not per query) — self-hosting removes the per-call API cost entirely, at the cost of running inference infrastructure (itself a rule-19 item, §2.9). Gemini Flash generation cost scales with query volume and context size; batch mode (**FACT** — 50% discount, ~24h turnaround, §25 item 4) is a good fit for any non-interactive workload (e.g. a bulk "re-summarize every contract after a catalogue update" job) but not for interactive Q&A. Storage cost for embeddings is modest at legal-document scale (one document rarely exceeds a few hundred chunks). Reranking adds compute per query, proportional to candidate-set size, not corpus size.

**Strategies:** caching is attractive for cost control but reopens the confidentiality question in §11 (a cached response containing contract text needs the same access control as the source) — **not a free optimization**, evaluate access control cost alongside the savings. Batching fits the ingestion-time embedding step naturally (it's already async and non-interactive). Deduplication: identical clause text across document versions of the same contract should not be re-embedded — a hash-based skip check is cheap and mechanical. Incremental indexing: only chunk/embed a new `DocumentProcessingRun`'s evidence, never the whole corpus, on every upload. Asynchronous processing: already the design (§6) — nothing about the assist layer should ever run synchronously in a request.

---

## 23. Migration Strategy

No rebuild — every phase is additive and independently revertible (disable the feature flag, drop the new tables, nothing upstream notices):

```
V1 (unchanged throughout)
   ↓
Phase 1 — AI infrastructure, no behavior: pgvector extension, new tables, new package skeleton,
          CI import-boundary test, DB-role grants (§10, §16) — all inert, feature-flagged off
   ↓
Phase 2 — Document intelligence (structural, non-evaluative): section/entity/definition surfacing,
          shown to a reviewer, never persisted to any Fact
   ↓
Phase 3 — RAG (retrieval only): self-hosted embeddings, chunking, hybrid retrieval; a read-only
          "similar clauses" endpoint, no generation yet
   ↓
Phase 4 — AI-assisted extraction: candidate clause-location suggestions (§4's "LLM allowed" rows),
          still no generation
   ↓
Phase 5 — AI-assisted explanations (Pattern B, §14): rephrasing of existing deterministic explanations —
          the FIRST phase requiring the data-egress decision (§26), if generation is API-based
   ↓
Phase 6 — AI-assisted review (recommendation/prioritization, Pattern D): natural-language investigation
          over a single document's authorized chunks
   ↓
Phase 7 — Advanced semantic capabilities (cross-document conflict triage, Option C-adjacent features) —
          only after Phases 3-6 have real usage data justifying them (AI-01's own "demonstrated problem" test)
```

Each phase can ship independently; V1's deterministic behavior is untouched by every single one, verified mechanically at each phase by the corpus-parity test in §16.

---

## 24. Anti-patterns

Beyond the brief's own list (all of which this document endorses as genuine anti-patterns for this system), the audit and vendor research surfaced these additional ones specific to LegalMind:

- **Treating the registry's paraphrase of a locked decision as the locked decision itself** (§2.4, §3) — item 16 ("no generic AI confidence scores") is invisible in the registry summary and would be easy to violate by someone who only read `LOCKED_DECISIONS.md`.
- **Assuming a workspace/tenant model exists** because the brief's questions presuppose one (§2.10) — building isolation logic against an imagined schema rather than the real `owner_id` model.
- **Denormalizing ownership metadata into the vector store "for performance"** (§8, §10) — this is the exact confidentiality liability a separate vector-DB option would create, and it's just as real as an anti-pattern inside pgvector if someone "optimizes" by caching a stale `owner_id` on the chunk row instead of joining live.
- **Storing a per-query retrieval score as if it were a permanent property of a chunk** (§9) — conflates "how well this matched one specific question" with "what this chunk is," and would silently rot as queries change.
- **Building an "AI assist eval set" and calling it, or letting it get confused with, the golden corpus** (§20) — the golden corpus's Tier-1 normativity is specifically about the *deterministic* engine; an AI eval set answering a different question must never share that authority.
- **Mixing assist-layer observability signals into the same dashboards/namespaces as the authoritative workflow's signals** (§21) — drowns a low-volume, high-stakes signal in a high-volume, low-stakes one.
- **Treating a vendor's `responseSchema` as a semantic correctness guarantee** (§13, §25 item 2) — Google's own docs explicitly disclaim this; building validation logic that assumes schema-conformance implies correctness is a documented, not hypothetical, risk.

---

## 25. Vendor Research — Gemini Flash & pgvector

*(Full research trail preserved; this section states conclusions with source + date. Web research performed 2026-08-24, prioritizing `ai.google.dev`, `cloud.google.com`, and the `pgvector` GitHub repository over secondary sources, per instruction.)*

1. **FACT** — Gemini Flash model family: current lineup per `ai.google.dev/gemini-api/docs/models` (page dated 2026-08-14) is Gemini 2.5 Flash / 2.5 Flash-Lite and a newer 3.x Flash line (3.7 Flash, launched 2026-08-13). Gemini 2.5 Flash: 1,048,576 input tokens, 65,536 output tokens. **Gemini 2.0 Flash was deprecated/shut down 2026-06-01** — do not spec against it. Both the direct Gemini API and Vertex AI offer the same model families; a capability skew between the two paths was **not confirmed either way** (OPEN QUESTION).

2. **FACT** — structured output: `response_schema` constrains output to a JSON Schema subset, but Google's own docs state explicitly: *"While output is syntactically correct JSON, always validate values in your application"* — a syntactic guarantee, not a semantic one. Function calling / tool use is supported and documented separately.

3. **FACT, with an important verification gap** — data handling: on the **direct Gemini API** (`ai.google.dev/gemini-api/terms`, effective 2026-03-23), the **free tier trains on submitted content** (*"Google uses the content you submit... to provide, improve, and develop Google products... and machine learning technologies"*); the **paid tier does not** (*"Google doesn't use your prompts... or responses to improve our products"*), with abuse-monitoring logs retained 55 days for policy enforcement only. **Users in the EU/Switzerland/UK must use the paid tier regardless of volume.** For **Vertex AI (enterprise)**, search-corroborated (not primary-quote-verified in this pass) sources indicate no training on customer data by default, plus CMEK/VPC-Service-Controls availability — **but the primary policy pages would not render through the fetch tooling used, so this half of item 3 is an OPEN QUESTION requiring a follow-up direct read of `cloud.google.com/terms/service-terms` §17 or a Google Cloud account-team confirmation before it's relied on for a real confidentiality decision.**

4. **FACT** — batch API: 50% discount vs. synchronous pricing, ~24h target turnaround (often faster), 2GB/20MB size limits, results retained 6 weeks. Vertex AI has an equivalent; its specific numbers were **not independently confirmed** (OPEN QUESTION, treat as ASSUMPTION if cited).

5. **FACT** — reliability: the direct API publishes **no SLA** and explicitly disclaims that stated rate limits are guaranteed. Vertex AI uses Dynamic Shared Quota on standard pay-as-you-go (shared capacity, HTTP 429 on overload) with a real SLA **only when paired with paid Provisioned Throughput** — the specific 99.5%-style figures found were search-snippet-sourced only, not primary-verified (OPEN QUESTION).

6. **FACT** — pgvector: current version v0.8.6, Postgres 13+. Supports IVFFlat and HNSW indexes. **Filtered/permission-scoped similarity search is supported via iterative index scans (v0.8.0+)**, specifically built to address the exact problem this architecture depends on (§8) — a selective `WHERE` filter otherwise starves an approximate index of candidates (pgvector's own documented example: ~4 results under a 10%-selectivity filter with default HNSW settings, absent iterative scanning).

7. **Common practice, not a vendor fact** — hybrid retrieval (lexical + vector, fused via reciprocal rank fusion) and a reranking stage before generation are convergent current practice across multiple independent sources; Postgres full-text search is a genuine native feature usable as the lexical half, though **true BM25 in Postgres requires an extension, not the built-in `tsvector`/`ts_rank`** — worth stating precisely if this document's "hybrid search" language is ever quoted elsewhere. A specific "+17pp MRR" reranking-improvement figure found in research is blog-sourced only and should not be cited as fact.

**Explicit list of what remains unverified from a primary source (carry into §26):** Vertex AI's exact training-restriction/retention clause text; whether the Gemini-specific Online Inference SLA uses the same credit tiers as the general Vertex AI Platform SLA; tier-gating of CMEK/VPC-SC/zero-data-retention across Gemini product tiers; Vertex AI batch-inference's specific discount/turnaround numbers; the specific reranking-improvement percentage.

---

## 26. Open Questions, by Decision Owner

**Product-owner decisions:**
- Is a workspace/multi-tenant model actually needed (§2.10)? This is independent of AI/RAG and, if yes, is a prerequisite for any retrieval-isolation design more granular than per-`owner_id`.
- Which task classes in §4's "LLM allowed"/"recommended" rows are actually wanted first — this document scopes what's *permissible*, not what's *prioritized*.
- Is a `confidentiality_level` field on `Contract`/`DocumentVersion` wanted (§5)? None exists today; do not invent a classification scheme without this decision.

**Legal-owner decisions:**
- Whether real counterparty contract text may ever be sent to a third-party LLM API at all, under what conditions, and whether that requires a DPA/vendor security review beyond what §25 item 3 could verify.
- Whether an "AI-suggested" summary/explanation surface needs its own disclaimer language, given rule 12's "no generic risk score" principle and the explicit human/AI distinction this document draws throughout §4.

**Security decisions:**
- Whether the DB-role-grant backstop in §10/§16 is a hard requirement before any assist-layer code ships, or a recommended-but-optional hardening.
- Retention/deletion policy for chunks, embeddings, and any cached prompts/responses (§11) — genuinely unverified in this audit, not assumed.
- Whether prompt/response caching is used at all, and if so, what access-control regime applies to the cache (§11, §22).

**Architecture decisions:**
- Approval to add the pgvector extension (rule 19) — this document recommends it over a separate vector service (§8, restated from the prior turn's analysis) but does not approve it.
- Approval for a GPU/inference runtime if self-hosted embeddings/models are chosen (§7, §2.9) — a new technology beyond the Step 39 stack, per `IMPL-01`.
- Whether the new `docs/architecture/` folder (unnumbered, alongside the existing unnumbered `docs/design/`) is the right home for future non-locked architecture proposals, or whether this should instead live under `docs/05-architecture/` with a `PROPOSAL` status label — flagged explicitly since `docs/README.md`'s documented tree has no `docs/architecture/` entry today (this document adds one, see the accompanying `docs/README.md` change).

**Vendor verification required before any decision-grade reliance:**
- Vertex AI's exact training/retention clause text (§25 item 3) — the single highest-priority item, since it gates the entire generation-via-API path.
- The Gemini-specific Online Inference SLA's actual credit-tier table (§25 item 5).
- Tier-gating of CMEK/VPC-SC/zero-data-retention across Gemini product tiers (§25 item 3).
- Vertex AI batch-inference's actual discount/turnaround figures if batch generation is ever used (§25 item 4).

---

## 27. Recommended Next R&D Steps

1. **Resolve the data-egress decision (§26, legal-owner)** before any further design work on generation — it determines whether Phase 5+ (§23) is even reachable via API, or must be self-hosted-only.
2. **A follow-up vendor-verification pass**, specifically a direct human read of `cloud.google.com/terms/service-terms` §17 and the Vertex AI data-governance page (the automated fetch tooling used here could not render their body text), or a Google Cloud account-team confirmation.
3. **A small, isolated proof-of-concept for Phase 1–3 only** (§23) — pgvector extension, new tables, the CI import-boundary test, self-hosted embeddings over a handful of already-ingested synthetic/cleared documents — explicitly not touching generation, to validate the isolation mechanism (§16) before any confidentiality-sensitive decision needs to be made at all.
4. **Confirm the environment/retention questions in §11 and §26** with whoever owns the actual document-deletion/retention policy, since this audit could not confirm a hard-delete path exists for Contracts.
5. **Decide the documentation home** (§26) — this document currently lives at `docs/architecture/AI_RAG_ARCHITECTURE_RND.md`, a new unnumbered folder; confirm or redirect before it accumulates cross-references elsewhere.

---

## Do not implement

Per the instructions this document was produced under: nothing above authorizes writing code, adding a dependency, modifying the database, or touching the frontend, and nothing in it may proceed to implementation without the approvals enumerated in §26. This document decides nothing that `AI-01`–`AI-04` do not already permit, and reopens none of them.

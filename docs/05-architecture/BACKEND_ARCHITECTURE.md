# Backend Architecture

Source: all_lock.md lines 6024-6800 (Step 39 - Recommended Technology Stack, backend-relevant sections). Canonical source: all_lock.md (Steps 36-39)

Status: This document is primarily RECOMMENDED content from Step 39. The final stack table and the closing "Technology Stack: LOCKED" statement (reproduced at the bottom) are the one part of Step 39 the source explicitly locks; everything else in this document — rationale, design approach, "what I deliberately don't recommend" — is framed by the source as a personal recommendation and is marked Status: RECOMMENDED (not yet locked) accordingly.

See SYSTEM_ARCHITECTURE.md for the locked domain boundaries and architectural rules (Step 38) that this backend implements. Domain separation, security boundary, no-UI-shortcuts, transaction boundaries, etc. are not repeated here.

---

# Step 39 - Recommended Technology Stack (backend-relevant content)

Status: RECOMMENDED (not yet locked), except the final stack table, which the source explicitly locks (see bottom of this file).

My recommendation is a modular monolith + background workers, not microservices.

### Recommended stack (full table, as given in the source)

| Layer            | Recommendation                                      | Why                                                                                       |
| ---------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Frontend         | Next.js + TypeScript                            | Strong admin/dashboard UX, server-side capabilities, mature ecosystem                     |
| Backend/API      | FastAPI + Python                                | Excellent fit for document processing and deterministic analysis                          |
| Database         | PostgreSQL                                      | Strong relational model, transactions, JSONB, constraints, excellent audit/versioning fit |
| ORM              | SQLAlchemy 2 + Alembic                          | Explicit schema/control, mature migrations                                                |
| Document PDF     | PyMuPDF                                         | Fast, strong PDF text/page extraction and positional data                                 |
| DOCX             | python-docx                                     | Reliable structured DOCX parsing                                                          |
| OCR              | OCRmyPDF + Tesseract initially                  | Good deterministic/local OCR pipeline                                                     |
| Background jobs  | Celery + Redis                                  | Mature worker model for document processing/analysis                                      |
| Object storage   | S3-compatible storage                           | Original PDFs/DOCX and derived artifacts                                                  |
| API validation   | Pydantic                                        | Excellent typed validation with FastAPI                                                   |
| Auth             | OIDC/OAuth2-compatible provider                 | Avoid building authentication ourselves                                                   |
| Authorization    | Application-level RBAC + PostgreSQL constraints | Server-side enforcement                                                                   |
| Testing          | Pytest + Playwright                             | Backend/domain + real browser workflow testing                                            |
| Frontend testing | Vitest                                          | Fast TypeScript unit testing                                                              |
| Containers       | Docker                                          | Reproducible development/deployment                                                       |
| Reverse proxy    | Nginx or equivalent                             | TLS, routing, upload handling                                                             |
| CI/CD            | GitHub Actions                                  | Straightforward automated testing/deployment                                              |
| Monitoring       | Sentry + structured application logs            | Error tracking and operational visibility                                                 |

(Frontend/Database rows are cross-referenced here in full for context; see FRONTEND_ARCHITECTURE.md and DATABASE_ARCHITECTURE.md for their dedicated rationale.)

---

# Why I recommend Python for the backend

Status: RECOMMENDED (not yet locked)

This is the most important stack decision.

LegalMind's difficult part isn't the dashboard.

It's:

```text
PDF/DOCX
   ↓
Extraction
   ↓
OCR
   ↓
Normalization
   ↓
Clause detection
   ↓
Deterministic mapping
   ↓
Rule evaluation
   ↓
Evidence
```

Python has an exceptionally strong ecosystem for this kind of document-processing workload.

It also gives us room later to evaluate NLP/LLM capabilities without rewriting the backend.

But V1 remains:

```text
Python
+
Deterministic algorithms
+
Rules
```

—not AI.

---

# Background processing

Status: RECOMMENDED (not yet locked)

Don't do this:

```text
POST /upload

30-second request
      ↓
extract PDF
      ↓
OCR
      ↓
analyze
      ↓
return
```

Instead:

```text
POST /documents
      ↓
Create Document
      ↓
Queue Job
      ↓
202 Accepted
      ↓
Worker
      ↓
Processing
      ↓
Analysis
      ↓
Findings
      ↓
Review Ready
```

The UI can show:

```text
Uploading
    ↓
Processing
    ↓
Extracting
    ↓
Analyzing
    ↓
Review Ready
```

---

# Celery + Redis

Status: RECOMMENDED (not yet locked)

For V1:

```text
FastAPI
   ↓
Redis
   ↓
Celery Worker
```

Workers can handle:

```text
document extraction
OCR
normalization
clause mapping
evaluation
report generation
```

This keeps the web/API process responsive.

---

# Storage

Status: RECOMMENDED (not yet locked)

Use:

```text
PostgreSQL
+
S3-compatible object storage
```

Database:

```text
metadata
relationships
rules
findings
audit
```

Object storage:

```text
original.pdf
original.docx
OCR output
derived artifacts
```

Never put a 20 MB PDF directly into a normal PostgreSQL row unless there is a very specific reason.

---

# Analysis engine design

Status: RECOMMENDED (not yet locked)

This is where I want us to be particularly disciplined.

Create a separate Python domain package:

```text
legalmind/
│
├── analysis/
│   ├── mapping/
│   ├── evaluation/
│   ├── findings/
│   └── evidence/
│
├── documents/
│   ├── pdf/
│   ├── docx/
│   ├── ocr/
│   └── normalization/
│
├── legal/
│   ├── requirements/
│   ├── standards/
│   ├── rules/
│   └── configuration/
│
├── reviews/
├── decisions/
├── audit/
├── auth/
└── reports/
```

This makes the architecture enforceable in code.

---

# The deterministic algorithm stack

Status: RECOMMENDED (not yet locked)

This is more important than choosing a framework.

For V1, I'd use a combination of:

### 1. Structural parsing

Identify:

```text
heading
section
clause
paragraph
table
list
```

### 2. Controlled terminology

```text
liability
liable
aggregate liability
liability cap
maximum liability
```

### 3. Rule-based pattern matching

Regex + normalized phrase matching.

### 4. Negation/exclusion patterns

Detect things such as:

```text
liability shall not be limited
```

rather than incorrectly treating "liability" + "limited" as a positive match.

### 5. Deterministic candidate scoring

Rank candidate clauses based on configured signals.

### 6. Requirement-specific evaluators

```text
NUMERIC_COMPARISON
RANGE_COMPARISON
ALLOWED_VALUES
EXACT_MATCH
BOOLEAN_PRESENT
MULTI_CLAUSE
CONFLICT_DETECTION
```

### 7. Explicit uncertainty states

```text
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

This is the algorithmic foundation I'd use instead of trying to make one "AI-like" algorithm do everything.

---

# API architecture

Status: RECOMMENDED (not yet locked)

I recommend:

```text
Next.js
     ↓
REST API
     ↓
FastAPI
     ↓
Application Services
     ↓
Domain Services
     ↓
Repositories
     ↓
PostgreSQL
```

Keep the domain logic independent from HTTP.

That means the evaluation engine can eventually be tested like:

```text
evaluate(requirement, clause, standard, rule)
```

without running a browser or API server.

That's extremely valuable for legal testing.

(See ../08-testing/TEST_STRATEGY.md for the full testing strategy this enables.)

---

# Security

Status: RECOMMENDED (not yet locked)

Because these are legal documents, security isn't an optional add-on.

V1 should include:

```text
TLS
Authentication
Server-side RBAC
Object-level authorization
Encrypted storage where supported
Secrets outside source code
Upload validation
Safe document parsing
Malware scanning where available
Audit trail
Rate limiting
Session security
Database backups
```

And importantly:

> A user must never be able to access another user's Contract, Document Version, Review, Finding, or Legal Decision merely by changing an ID in an API request.

(See SYSTEM_ARCHITECTURE.md sections 38.21-38.24 for the locked architectural security boundary this recommendation sits on top of.)

---

# Deployment

Status: RECOMMENDED (not yet locked)

For V1, I would keep deployment relatively simple:

```text
                    Internet
                       ↓
                  Reverse Proxy
                       ↓
              Next.js + FastAPI
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
       PostgreSQL          Background Workers
                                  ↓
                                Redis
                                  ↓
                           Object Storage
```

You don't need Kubernetes on day one.

Docker Compose can be enough for development and potentially a small production deployment; production orchestration can evolve based on actual load and availability requirements.

---

# What I deliberately DON'T recommend

Status: RECOMMENDED (not yet locked)

### Microservices from day one

Too much operational complexity for V1.

### Kubernetes immediately

No evidence yet that V1 requires it.

### MongoDB

The data model is heavily relational.

### Vector DB

Not required by the V1 methodology.

### LLM

Explicitly outside V1.

### RAG

Explicitly outside V1.

### Cloud OCR by default

Legal-document privacy makes local/self-hosted OCR preferable initially.

### Building our own authentication

Use a mature identity solution.

### Business logic in Next.js

Legal evaluation belongs in the backend/domain layer.

---

# Final recommended stack

Status: LOCKED — the source explicitly states "Step 39 - Technology Stack: LOCKED" after this diagram (see below).

```text
┌────────────────────────────────────────────┐
│                FRONTEND                    │
│       Next.js + TypeScript                 │
└─────────────────────┬──────────────────────┘
                      │
                      ↓
┌────────────────────────────────────────────┐
│                 API                        │
│              FastAPI                       │
│             Pydantic                       │
└─────────────────────┬──────────────────────┘
                      │
          ┌───────────┴───────────┐
          ↓                       ↓
┌──────────────────┐     ┌──────────────────┐
│ LegalMind Domain │     │ Background Jobs  │
│ / Analysis       │     │ Celery + Redis   │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └────────────┬───────────┘
                      ↓
             ┌────────────────┐
             │  PostgreSQL    │
             └────────────────┘

             ┌────────────────┐
             │ Object Storage │
             │ S3-compatible  │
             └────────────────┘

Document Processing:
PyMuPDF
python-docx
OCRmyPDF
Tesseract

Testing:
Pytest
Vitest
Playwright

Infrastructure:
Docker
Reverse Proxy
GitHub Actions
Sentry
```

## My recommendation

This is the stack I would choose for LegalMind V1.

The most important decision isn't Next.js vs another frontend or FastAPI vs another API framework. The critical decision is that the deterministic analysis engine is a first-class domain component, independently testable, versioned, and completely separated from the UI.

And we should not start implementation yet just because the stack is selected. The next architecture step should define the actual database/domain model and component boundaries before Claude Code starts creating tables and files.

Step 39 - Technology Stack: proposed. I recommend we review it once before locking, particularly the FastAPI + PostgreSQL + Celery/Redis + PyMuPDF/OCRmyPDF choices.

## LOCKED: Step 39 - Technology Stack

Status: LOCKED (source text: "Step 39 - Technology Stack: LOCKED")

The technology direction is now fixed:

```text
Frontend:          Next.js + TypeScript
Backend:           FastAPI + Python
Database:          PostgreSQL
ORM/Migrations:    SQLAlchemy 2 + Alembic
PDF:               PyMuPDF
DOCX:              python-docx
OCR:               OCRmyPDF + Tesseract
Jobs:              Celery + Redis
Storage:           S3-compatible object storage
Testing:           Pytest + Vitest + Playwright
Infrastructure:    Docker
Monitoring:        Sentry + structured logs
```

And importantly:

```text
Modular Monolith
+
Background Workers
+
Deterministic Analysis Engine
```

No microservices/Kubernetes/LLM/RAG/vector DB in V1.

---

## Stack additions — Amendment Batches AB-3 and AB-4

**Status: 🔒 LOCKED.** `AM-26` (AB-3, 2026-08-24) as amended by `AM-30` (AB-4, 2026-08-25).
**Added to this document 2026-08-25**; the registry named this file as the canonical document for
both and the section was never written. The Step 39 stack table above is unchanged — these are
**additions to it**, and everything the two records leave alone stays exactly as locked.

### Added

| Layer | Choice | Note |
|---|---|---|
| Vector index | **pgvector** extension, on the **existing** PostgreSQL instance | Not a new datastore. A second datastore for vectors is **NOT ADDED** and needs separate approval |
| Keyword index | **PostgreSQL full-text search** (`tsvector`/`tsquery`) and **trigram** indexes, same instance | ⚠️ This is `ts_rank`, **not BM25**. True BM25 in PostgreSQL needs an extension, which is not authorized. Do not specify or benchmark against a ranking function the stack does not have |
| Embedding model | **Local, self-hosted, open-weight** | Owner decision 2026-08-25 confirms self-hosted. `AM-30` t1 keeps `embedding input` forbidden from egress, so **full document text never leaves** |
| Reranking model | **Local, self-hosted, open-weight**, cross-encoder | Unchanged by AB-4 |
| Generative model | **Gemini Flash — hosted API** (`AM-30`) | The **one** external dependency in the stack, and the only permitted egress. Behind `AM-26` r1's single interface, so the identity is configuration and no other module knows |
| Inference runtime | Local model-serving process, **no outbound network route** | `AM-30` **scopes** this row rather than removing it: it still serves the embedding and reranking models, and still has no outbound route. It no longer implies generation is served locally |
| GPU runtime | Where required by the selected model | Still required — for the embedding and reranking models. **Not** eliminated by using a hosted generative model |

### Unchanged

Modular monolith — **no microservices, no Kubernetes, no service mesh** (locked 38.26, restated by
`AM-26`). **There is therefore no separate gateway service**: `AM-26` r1's single interface is an
in-process module boundary. Backend and frontend frameworks; PostgreSQL as the system of record;
the existing queue and workers, **reused not replaced**; the existing parser and OCR path as the
**primary** path (so `pymupdf` + `python-docx` + OCRmyPDF/Tesseract stay — a different parsing
library is a new dependency under rule 19 for capability the stack already has); and
"S3-compatible" object storage, whose **provider** is selected under locked 55.6 and needs no
amendment.

### Not added — separate approval required if ever proposed

A second datastore for vectors · a hosted **embedding** service · a hosted document-processing
service · any RAG orchestration framework · any additional message broker · model fine-tuning or
training on the corpus · third-party telemetry in the document path.

⚠️ **Rule 19 is unaffected by `AM-30`.** Authorizing the *capability* to call a hosted model does
**not** authorize any particular client library. A provider SDK or HTTP client is a new dependency
and needs its own approval, exactly as the OIDC JWT/JWKS client does.

### Model selection

`AM-26` r2–r5 govern the embedding and reranking models unchanged: selection from the smallest
candidate upward, stopping at the first that passes; the quality bar measured on a LegalMind
evaluation set built from **real supplied documents**, in which *correct refusal is half the bar*;
the version pinned and recorded against every answer; weights obtained once, checksummed, stored
locally, never fetched at runtime.

For the **generative** model, `AM-30` supersedes r2 (owner selection) and r5 (nothing to
checksum), and `AM-30` t7 replaces it with a **dated pinned model identifier** — a floating alias
such as "latest" is not a pin, and a provider-side rotation is a model change that re-triggers
`AM-26` r4.

### Embedding-model selection — SELECTED BY MEASUREMENT, 2026-08-26

**Status: COMPLETE.** Selected: **`sentence-transformers/all-MiniLM-L6-v2` (384
dimensions, 23M parameters, Apache-2.0)**, with the calibrated refusal gate below. The
dimension is pinned in migration `c4a91f6e2d87` as a DDL literal — a different model
with a different width is a **new migration**, never a config change.

#### The deciding measurement — owner-ratified 77-question set, 15 real documents

Lexical search on **human-phrased** questions collapses (1/64 top-10 — it ANDs every
term; a phrase engine, not a question engine) while refusing perfectly (13/13). Dense
retrieval inverts both: strong recall, **zero natural refusals**. Per candidate:

| Candidate | Params | Hit@10 | Hit@1 | MRR | Gate (refused/retained) at chosen rule |
|---|---:|---:|---:|---:|---|
| **all-MiniLM-L6-v2** ✅ | 23M | 0.938 | 0.438 | 0.606 | **12/13 · 41/64** (J = 0.564) |
| bge-small-en-v1.5 | 33M | 0.922 | 0.484 | 0.617 | 9/13 · 55/64 (J = 0.552) — weak separation |
| gte-small | 33M | 0.969 | 0.516 | 0.662 | 11/13 · 45/64 (J = 0.549) — compressed scores (0.79–0.92) |
| snowflake-arctic-embed-s | 33M | 0.438 | 0.109 | 0.188 | rejected outright on retrieval |
| intfloat/e5-small-v2 | 33M | — | — | — | not measured: publishes ONNX at a non-standard path |

**Why MiniLM, when gte-small retrieves better:** MiniLM is the **smallest candidate and
passes the quality bar** (≥90% top-10 recall; gate refusal ≥10/13 with ≥60% retention).
`AM-26` r2 then decides it: *"stops at the first that meets the quality bar. A larger
model is not adopted for headroom."* MiniLM also has the widest raw score separation
(answerable median 0.539 vs unanswerable 0.416), which is what a threshold lives on.

#### The calibrated gate — derived, not chosen

A single absolute cosine floor was measured first and found insufficient (best J ≈ 0.50
across candidates). The two-feature rule that won the sweep:

```
evidence  =  lexical hits  ∪  vector hits with cosine ≥ 0.50
gate open ⇔  lexical hit  OR  (top cosine ≥ 0.50  AND  top-gap ≥ 0.059)
```

where top-gap = top cosine − mean(rest of top-10): a flat profile means the "best"
chunk is a nearest neighbour, not evidence. Operating point: **12/13 unanswerable
refused, 41/64 answerable retained on vector evidence, Youden's J = 0.564**; the full
sweep curve is reproducible via `tools/benchmark_retrieval.py --eval`. Constants and
provenance: `legalmind/assist/calibration.py`.

**What the gate deliberately does not attempt — measured, not assumed:** the
adversarial near-miss (a topical clause that does not answer the question) scores
*inside* the answerable distribution for every candidate. Those are caught downstream
by claim-level citation verification (`legalmind/assist/guardrails.py`, `AM-29`'s
third outcome) — the layered-refusal design `AM-29` r3 prescribes.

#### Superseded framing (kept for the record)

The section below was written 2026-08-25, while the selection was blocked on
evaluation material. The owner ratified the drafted question set on 2026-08-26 and the
measurement completed. Its methodology description remains accurate.

**Status as then written: IN PROGRESS as of 2026-08-25. No model is selected, and no
vector dimension is pinned.** `AM-26` r2 requires selection *by measurement*, smallest-that-passes, so a name
written here before the measurement exists would settle by assertion what the record says
to settle by evidence. `chunk_embeddings` does not exist for the same reason: its column
width is a property of the chosen weights.

#### The instrument

`backend/tools/benchmark_retrieval.py`. Ingests the real supplied documents through the
**real** pipeline, indexes them, derives probes, and scores any strategy satisfying
`legalmind/assist/embedding.py`'s `RetrievalStrategy`. Metrics: precision@1, recall@10,
MRR, and — for unanswerable probes — correct refusals versus wrongly-answered, because
`AM-28` weighs refusal correctness in **both** directions and calls it half the bar.

**Every probe is derived mechanically; none is authored.** The distinction that licenses
this: a *retrieval* label says "the text about X is in §17.2", which is a locatable fact
about a document and asserts no legal position; an *answer* label says "our cap is 12
months", which is a legal position and must be supplied (`AM-31` m5). Three families come
out honestly — `section_number` (the document states it, so the query is it),
`exact_terminology` (an n-gram computed to occur in exactly one chunk), and
`unanswerable` (an n-gram from another document, verified to contain at least one word
absent from this document's whole vocabulary). No document text enters the repository:
probes are generated at run time from the gitignored source directory, and absence of
that directory is a SKIP, per locked 54.6 and the precedent `test_source_material.py`
already sets.

#### Measured baseline — lexical, 2026-08-25

Six real supplied documents, 180 probes, `PROBES_PER_FAMILY = 12`, top-k 10.

| Family | Probes | P@1 | R@10 | MRR | Correct refusals | Wrongly answered |
|---|---:|---:|---:|---:|---:|---:|
| `exact_terminology` | 72 | 0.833 | 0.931 | 0.870 | — | — |
| `section_number` | 36 | **0.972** | **1.000** | 0.986 | — | — |
| `unanswerable` | 72 | — | — | — | **64** | 8 |

Two caveats stated rather than buried. The wrongly-answered figure was **26** before the
probe required a genuinely out-of-vocabulary word — that first version was measuring the
probe design, not the engine, and the correction is why the number is trustworthy now.
The residual 8 are consistent with stemming equivalence (the probe checks exact strings,
the engine matches stems), so 89% refusal correctness is a **floor**, not a ceiling.

#### What this baseline means for the selection

The lexical strategy is already strong on exactly the two categories a citation depends
on. So an embedding model's value has to show up in **semantic similarity** and **legal
phrasing** — a question whose wording deliberately differs from the document's.

**Those two categories cannot be derived from a document**, and they are not invented
here. Measuring candidates only on the derivable families would score them on the ground
where lexical is strongest and embeddings weakest, and would select a model on evidence
that does not bear on the question. That is the "do not claim a model is best without
measurement" failure wearing a table of numbers.

#### Candidate set — verified, not recalled

Fetched from the HuggingFace model API on 2026-08-25. All permissively licensed, all with
ONNX exports, none requiring a GPU at this size.

| Candidate | Licence | Dim | Params | ONNX |
|---|---|---:|---:|:--:|
| `sentence-transformers/all-MiniLM-L6-v2` | Apache-2.0 | 384 | 23M | yes |
| `BAAI/bge-small-en-v1.5` | MIT | 384 | 33M | yes |
| `intfloat/e5-small-v2` | MIT | 384 | 33M | yes |
| `thenlper/gte-small` | MIT | 384 | 33M | yes |
| `Snowflake/snowflake-arctic-embed-s` | Apache-2.0 | 384 | 33M | yes |
| `sentence-transformers/all-mpnet-base-v2` | Apache-2.0 | 768 | 109M | yes |
| `BAAI/bge-base-en-v1.5` | MIT | 768 | 109M | yes |
| `nomic-ai/nomic-embed-text-v1.5` | Apache-2.0 | 768 | 137M | yes |

Order of evaluation follows `AM-26` r2 — smallest upward, stopping at the first that
passes — so the 384-dimension group is measured before the 768 group, and a larger model
is not adopted for headroom.

`AM-26` r5 requires weights obtained once, checksummed and stored locally, never fetched
at runtime. Every candidate above satisfies that; a model that resolves from a hub on
first use would not be eligible.

#### Candidate measurement — 2026-08-25, three documents, 72 probes

Runtime approved under rule 19 on 2026-08-25: **`onnxruntime` + `tokenizers`**, measured
at **118 MB** installed including numpy. (An earlier estimate of "~50 MB" understated it;
the figure here is measured. It remains far below `torch` + `sentence-transformers` at
roughly 2.5 GB, and the inference-only property that made it the recommendation is
unchanged.)

Four of the five 384-dimension candidates were provisioned and measured smallest-first
per `AM-26` r2. `intfloat/e5-small-v2` publishes its ONNX export at a non-standard path
and was skipped rather than special-cased.

`exact_terminology`, 36 probes:

| Strategy | P@1 | R@10 | MRR |
|---|---:|---:|---:|
| **lexical** (baseline) | **0.833** | 0.917 | 0.875 |
| vector · all-MiniLM-L6-v2 | 0.333 | 0.861 | 0.490 |
| vector · bge-small-en-v1.5 | 0.278 | 0.778 | 0.416 |
| vector · gte-small | 0.167 | 0.694 | 0.344 |
| vector · arctic-embed-s | 0.083 | 0.639 | 0.189 |
| hybrid RRF · all-MiniLM-L6-v2 | 0.694 | **1.000** | 0.836 |
| hybrid RRF · bge-small-en-v1.5 | 0.722 | **1.000** | 0.833 |
| hybrid RRF · gte-small | 0.750 | **1.000** | 0.840 |
| **hybrid RRF · arctic-embed-s** | **0.833** | **1.000** | **0.891** |

`unanswerable`, 36 probes:

| Strategy | Correct refusals | Wrongly answered |
|---|---:|---:|
| lexical | **34** | 2 |
| **every** vector strategy | **0** | **36** |
| **every** hybrid strategy | **0** | **36** |

#### The finding that matters most, and it is not about model choice

**Dense retrieval never refuses.** Nearest-neighbour search always returns its nearest
neighbour, however far away it is — there is no natural empty result, because a ranking
is not a filter. Every candidate scored 0 of 36 correct refusals, and so did every
hybrid, because RRF fuses rankings and inherits the property.

This is architecturally load-bearing, not a tuning detail:

* `AM-29` r3 requires `NO_EVIDENCE_RETRIEVED` and `EVIDENCE_INSUFFICIENT` to be
  reachable, the latter meaning *"the model is not called at all"*.
* `AM-25` r5 requires that no answer reach a user unless every claim resolves to
  retrieved evidence, enforced **mechanically and outside the model**.

So **hybrid retrieval cannot ship without a similarity floor below which the result is
treated as no result.** That floor is a number, and by rule 7's discipline it must be
*measured* against known-unanswerable questions rather than picked — which is the second
reason the evaluation material is needed, independent of choosing a model. Until then the
lexical path is the only one whose refusal behaviour is sound.

Secondary observation, recorded but not acted on: `hybrid RRF · arctic-embed-s` is the
only configuration that matches the lexical baseline's P@1 while improving both MRR
(0.891 vs 0.875) and recall (1.000 vs 0.917) — a strict improvement on this family. It is
**not** therefore the selection: the families an embedding model exists to win are still
unmeasured, and choosing on the families where lexical already wins would be selecting on
evidence that does not bear on the question.

#### Two things block completing the selection

1. **The evaluation material for the two undecidable families.** Owner-supplied; see
   [LEGALMIND_PROJECT_STATE.md](../00-project/LEGALMIND_PROJECT_STATE.md).
2. ~~A local inference runtime is a rule-19 dependency.~~ **Resolved 2026-08-25** —
   `onnxruntime` + `tokenizers` approved and declared in `pyproject.toml`.

⚠️ **A third item, surfaced by the measurement itself:** a similarity floor for dense and
hybrid retrieval. Without one, correct refusal is structurally impossible (see above), and
the threshold has to be measured against known-unanswerable questions rather than chosen.
It is the same blocker as item 1, arrived at from a different direction.

#### Runtime notes, both learned by measurement

**The execution provider is pinned.** onnxruntime ships an `AzureExecutionProvider`
alongside `CPUExecutionProvider`; left to the default list an inference session could
acquire a second network egress, and `AM-30` t1 permits exactly one. The list is pinned to
CPU and a test asserts it.

**Fetching weights lives outside the application package.** `tools/provision_model.py`,
not `legalmind/assist/`. The first draft put a `provision()` helper next to its consumer
and `test_import_boundaries.py` refused it — so `AM-26` r5's *"never fetched at runtime"*
is now structural: no module under `legalmind/` imports a network client, and
`EGRESS_ALLOWED` is still empty.

**Batch size is a memory bound, not a knob.** Embedding a whole document in one call
reached 14 GB RSS and was OOM-killed, because padding takes every sequence to the longest
in the batch. Batches of 16 keep activations in the tens of megabytes; embeddings are
position-independent, so a test asserts batching changes no vector.

#### pgvector — a measured correction

`AM-25` r6 requires authorization applied **inside** the retrieval query. Verified on
**0.6.0**: exact cosine KNN with the authorization `WHERE` clause in the same statement
works correctly and genuinely excludes out-of-scope rows. Exact search loses no recall,
so r6 is fully satisfiable on 0.6.0 — it is simply O(n) over the pre-filtered set, which
for one document's chunks is the right trade anyway.

What **≥ 0.8.0** buys is *iterative index scans*, which matter only for an
**approximate** index under a selective pre-filter, where a filtered HNSW scan can
otherwise starve and silently lose recall. So the version is a prerequisite for
corpus-scale indexed retrieval, not for correctness, and `preflight` reports it as ATTEST
rather than BLOCKED. **The answer to an older build is exact search, never a
post-filter** — `AM-25` r7 forbids the latter outright.

⚠️ **`AM-31` resolves a contradiction here that is easy to miss.** `AM-26` r3 requires the quality
bar to be measured on **real** supplied documents; `AM-31` g1 forbids real counterparty text
reaching the provider until written no-training terms are recorded. So a hosted model may be
selected **provisionally** on an explicitly-labelled synthetic set (`AM-31` m1), but that is
**not** a passed bar (m2), and **no assist answer reaches a user over real counterparty material
on a synthetic-only bar** (m3). The gate is **CLOSED** as of 2026-08-25.

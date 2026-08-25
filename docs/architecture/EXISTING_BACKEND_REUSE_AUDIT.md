# Existing Backend — Reuse Audit against the current product vision

**Status: `ANALYSIS` — an audit. It classifies existing code, records contradictions, and proposes an
order of work. It decides nothing, locks nothing, amends nothing, and authorizes no build.**

**Prepared:** 2026-08-25, on explicit request ("high-level architecture and implementation audit of the
existing repository; reuse as much correct existing engineering as possible").

**Target of comparison (read in full before any implementation decision):**
[legalmind-product-vision.md](../../legalmind-product-vision.md) ·
[legal-mind-tech-stack-and-buildplan-v2.md](../../legal-mind-tech-stack-and-buildplan-v2.md)

**Evidence base:** direct read of `backend/legalmind/` (11,685 LOC), `backend/tests/` (10,510 LOC),
`backend/tools/` (1,966 LOC), `backend/alembic/` (765 LOC), `frontend/src/`, `docker-compose.yml`,
`.github/workflows/ci.yml`, `backend/config/company_standards/` (32 files); a full suite run on
2026-08-25 (**726 passed, 0 failed, 23s**); and the locked records `AI-01`–`AI-04` and **Amendment
Batch AB-3 (`AM-25`–`AM-29`, LOCKED 2026-08-24)**.

**Related:** [AI_RAG_ARCHITECTURE_RND.md](AI_RAG_ARCHITECTURE_RND.md) (the pre-AB-3 R&D proposal; its
codebase findings are re-verified and upheld here) · [CLAUDE.md](../../CLAUDE.md) ·
[IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md) ·
[LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md)

> **Headline, stated before anything else.** The existing backend is healthy and **substantially
> reusable** — the deterministic core, schema, RBAC, parser, audit trail, and the entire 726-test suite
> transfer essentially untouched. But the two target documents **contradict a lock record dated one day
> before they were written**. `AM-25` r9 and `AM-26` forbid any hosted model API and require a *local,
> self-hosted* generative model; both target documents make **Gemini Flash — a hosted API — the single
> permitted external dependency and the core of the design.** Per rules 5 and 6 this audit does **not**
> resolve that. It is [contradiction 1](#c1--gemini-flash-hosted-api-vs-am-25-r9--am-26) and it gates
> Phases 5+ of any plan. Everything not downstream of it is audited, classified and sequenced below.

---

## Table of contents

1. [Executive Summary](#1-executive-summary)
2. [The current target, as extracted](#2-the-current-target-as-extracted)
3. [Reuse Matrix](#3-reuse-matrix)
4. [Architecture Gap Analysis](#4-architecture-gap-analysis)
5. [Database Gap Analysis](#5-database-gap-analysis)
6. [API Gap Analysis](#6-api-gap-analysis)
7. [Retrieval Gap Analysis](#7-retrieval-gap-analysis)
8. [LLM Gap Analysis](#8-llm-gap-analysis)
9. [Guardrail Gap Analysis](#9-guardrail-gap-analysis)
10. [Security Gap Analysis](#10-security-gap-analysis)
11. [Test Gap Analysis](#11-test-gap-analysis)
12. [Architectural Contradictions](#12-architectural-contradictions)
13. [Ambiguities in the target documents themselves](#13-ambiguities-in-the-target-documents-themselves)
14. [Documentation Changes](#14-documentation-changes)
15. [Migration Plan](#15-migration-plan)
16. [Explicit "Do Not Rebuild" List](#16-explicit-do-not-rebuild-list)
17. [Decisions required before implementation](#17-decisions-required-before-implementation)

---

## 1. Executive Summary

### Current backend health: **good**

| Signal | Measurement (2026-08-25) |
|---|---|
| Test suite | **726 passed, 0 failed, 0 skipped**, 23.3s |
| Lint / typecheck | `ruff` and `mypy` at zero; CI job 1 blocking at a zero baseline |
| Schema | 29 ORM tables, 4 migrations, 21 schema-invariant tests, append-only enforced by DB trigger |
| API | 39 endpoints, envelope-consistent, 139 API tests incl. 26 authz tests |
| Frontend | 10 Next.js routes, 58 Vitest + 22 Playwright |
| Dead code | none material; `backend/build/` and `backend/.e2e/` are untracked local artifacts |

This is not a prototype being audited for salvage. It is a disciplined, documented, fully-green
codebase whose every module cites the locked rule it implements.

### Compatibility with the current vision: **high on the foundation, blocked at the top**

The vision's own architecture is *"AI sits on top of the V1 foundation, not replacing it"* — which is
exactly what `AI-01` prescribed and `AB-3` then authorized in V1 scope. The existing code **is** that
foundation, and it needs no demolition:

* **Domain A (Internal Legal Constitution) already exists and is already derived from real source
  documents**, which is precisely what vision §3b demands. 32 ratified Company Standards across four
  document types live in `backend/config/company_standards/`, every position clause-cited to a real
  LeapSwitch document, stored as versioned structured configuration and never hardcoded in application
  code. **Vision §3b is satisfied work, not pending work.**
* **Evidence already carries everything a chunker needs** — page number, section number, section title,
  start/end offsets, source type (`NATIVE_TEXT`/`OCR`/`TABLE`), plus the original pre-normalization
  text. Citation-backed retrieval can be built *on* this rather than re-deriving boundaries from raw
  text.
* **The security model the vision needs is already built and tested** — server-side `Guard`
  (visibility → permission → operation → DB), byte-identical 404s, omit-not-null confidentiality, and
  an append-only audit trail with a redactor that makes logging clause text structurally impossible.

### Approximate reusable percentage

Measured in lines of code across `legalmind/` + `tests/` + `tools/` + `alembic/` (~24,900 LOC):

| Class | Share | What it is |
|---|---:|---|
| **A · REUSE AS-IS** | **~66%** | Deterministic core (evaluation, mapping, extraction, analysis, workflow), schema + migrations, domain enums, parser, all 726 tests, all verification tools |
| **B · REUSE WITH MODIFICATION** | **~33%** | API layer (additive routers), security (new guard method + permissions + RIAAS adapter), worker (one new task + queue), observability (separate signal namespace), deploy preflight (new checks), storage (add an S3/MinIO backend behind the existing Protocol), frontend (unified workspace assembled from existing components) |
| **C · REPLACE** | **~0%** | **Nothing in the existing backend solves the wrong problem.** The only replacement either target document asks for is substituting an LLM for the deterministic evaluator — which this audit recommends against, because `AM-25` r1/r4 forbids it |
| **D · DEPRECATE / REMOVE** | **~0%** | Nothing. No module loses its purpose under the new vision |
| **E · NEEDS VERIFICATION** | 5 items | RIAAS contract · hard-delete path for documents · Domain A/C chunk tables · Evidence Act / NI Act source text · multi-tenant requirement |

How the percentages were determined: by summing measured LOC per package and assigning each package one
class from a read of its actual behavior against the target, then reporting the ratio. They are an
engineering estimate of *volume that survives*, not a schedule. A package counted "with modification"
is mostly unchanged internally — `api/` is 3,351 LOC of which the change is *adding* routers, not
editing existing ones — so the honest reading is that **the modification column overstates the work and
the as-is column understates it.**

### Biggest architectural gaps (target requires, repository has nothing)

1. **No retrieval layer of any kind.** No embeddings, no pgvector, no `tsvector`/`tsquery`, no
   `pg_trgm` — verified by grep, zero hits. Hybrid retrieval is entirely new code.
2. **No generation layer, and no outbound HTTP anywhere.** Grep for `httpx`/`requests`/`urllib`/
   `aiohttp`/any URL literal across `legalmind/` returns **zero** call sites. Whatever model is chosen,
   the client, timeout/retry policy, and egress logging are all new.
3. **No async ingestion seam.** Parsing runs **inline in the HTTP request** (`ingest_document()` →
   `process_document_version()` → `parsing.parse()`, all before the response returns). The only Celery
   task in the codebase is `analysis.analyse_review`, dispatched on Review creation, not on upload.
   Embedding cannot run there; a new dispatch hook is required (small and additive — not a redesign).
4. **No conversational surface.** No conversations, messages, or Q&A endpoint; the frontend has 10
   task-shaped routes and no unified workspace screen.
5. **No object storage implementation.** `StorageBackend` is a clean 3-method Protocol with one
   local-filesystem implementation; MinIO is a small additive class, not a refactor.
6. **No statute corpus (Domain C) and no Legal-Constitution index (Domain A).** Neither has an
   authorized table — see [C3](#c3--domain-a-and-domain-c-have-no-authorized-table).

### Biggest risks

| # | Risk | Severity |
|---|---|---|
| R1 | **The target's core LLM decision is forbidden by a lock dated the day before.** Hosted Gemini vs `AM-25` r9 / `AM-26`. Building it would silently break a locked confidentiality guarantee | **Blocking** |
| R2 | **An LLM producing clause verdicts would replace the deterministic evaluator** — barred by `AM-25` r1/r4 and by the 726-test byte-identical determinism gate (`AM-28` r1). It is also the single largest *unnecessary* rewrite available in this repository | **Blocking** |
| R3 | **Domain A and Domain C retrieval indexes are not authorized by `AM-27`**, whose permitted `chunks` table is defined as derived from a Document *Version* and referencing a Document *Evidence* row. Company Standards are configuration rows; statutes are neither | **High** |
| R4 | **The word "confidence" in the vision's answer surface** collides with `AI-03` locked item 16 ("the system does not use generic AI confidence scores") and rule 12 | **High** |
| R5 | **The "2-day phased plan" is not achievable** against a 25k-LOC codebase plus new schema, plus `AM-26` r2/r3's *selection by measurement* on an evaluation set that does not yet exist | **High** (planning) |
| R6 | Both target docs assume a multi-tenant/external-customer future; **no workspace or tenant primitive exists** and `AM-27` did not add one | Medium |
| R7 | Statute worked examples cite the **NI Act, which was never supplied**; Evidence Act likewise | Medium |
| R8 | The target's per-service folder/container layout is a **microservice decomposition**, which locked 38.26 and `AM-26` explicitly leave unchanged | Medium |

### Rewrite vs migration effort

**Migration, decisively — not a rebuild.** No existing module is architecturally obsolete. The work
divides as:

* **~0% demolition.** Nothing is deleted.
* **~15% adaptation of existing code** — additive routers, one new Celery task, an S3 storage class, a
  guard method, permission entries, a separate observability namespace, preflight checks.
* **~85% genuinely new, purely additive code** in a new `legalmind/assist/` package and a new database
  schema: chunking, embedding, hybrid retrieval, reranking, citation enforcement, conversation
  endpoints, and the unified workspace UI.

The correct mental model is **an additive second lane beside a finished first lane**, with the first
lane's output (Evidence) as the second lane's input. That is what both `AI-01` and `AM-25` prescribe, and
the existing code already has the seam.

---

## 2. The current target, as extracted

Recorded here because the rest of the audit measures against it.

### Product model — three knowledge domains, never blended

| Domain | Content | Answers | Chunking (vision §9.6) |
|---|---|---|---|
| **A · Internal Legal Constitution** | Approved LeapSwitch/CloudPe legal positions; category structure **derived from source documents, never hardcoded** (§3b) | "Does this clause match our approved position?" | clause / sub-clause, by the document's own numbering |
| **B · Uploaded Document** | Whatever is uploaded this session | "What does this document say about X?" | clause / section, preserving page + byte offsets |
| **C · Statute Corpus** | Prioritized Indian statutes from **India Code (official)** — Contract Act, IT Act, DPDP Act, Companies Act (+Evidence, NI if time), plus a **fixed curated** judgment set | "What does Section 138 NI Act say?" | **one Section = one chunk, never split**; judgments by numbered paragraph |

The retrieval layer routes; the user never picks a mode. A query may span domains (B+C, or A+B for
validation).

### Retrieval model (vision §5, tech §1a)

Retrieval **always first**; hybrid = pgvector cosine similarity **+** Postgres native full-text search
(`tsvector`/`tsquery`), explicitly *not* Elasticsearch/OpenSearch; domain-aware; every answer carries
explicit citations; **no retrieval match → no LLM call → "Information not found"**; a code-level (not
model-level) guardrail verifies every citation exists in the retrieved chunk before display.

### LLM architecture (vision §8, tech §2/§3)

Gemini Flash is named as the **only** non-self-hosted component, reached through a single isolated
`llm-gateway` that is the only thing in the stack permitted to touch the internet, sending **only the
matched clause + minimal context** (never the full document), with redaction and per-call audit logging
of a payload *hash*, not the payload.

### Backend / infrastructure

FastAPI with separated ingestion · retrieval · validation · guardrails · audit · persistence · LLM
orchestration. PostgreSQL + pgvector, MinIO, Nginx + Certbot, RIAAS auth, Vault-or-encrypted-`.env`
secrets, Docker network segmentation with deny-by-default `ufw`, Trivy/OpenVAS/ZAP scanning, immutable
`audit_log`, per-service DB roles (least privilege).

---

## 3. Reuse Matrix

Percentages are engineering estimates of the share of each component's existing code that survives.
Method: read the module's behavior, compare against the target requirement, estimate the fraction of
lines needing no edit. "100%" means the file is expected to be byte-identical after migration.

| Component | Existing implementation | Current requirement | Status | Reuse % | Required change | Risk |
|---|---|---|---|---:|---|---|
| **Database schema + migrations** (1,620 LOC) | 29 tables, UUID PKs, UTC timestamps, real FKs, append-only audit enforced by DB trigger, EV-MIN constraint triggers; 21 invariant tests | Locked tables untouched; new assist tables in a **separate schema** (`AM-27` r1–r2) | **A · REUSE AS-IS** | **100%** | None. `AM-27` r2 *forbids* altering them, and makes the unmodified invariant tests the evidence | Low |
| **Domain enums** (285 LOC) | Five controlled legal state vocabularies, closed, serialized into API/audit output | Unchanged; assist answer state is a **separate sixth axis** (`AM-29` r1) | **A · REUSE AS-IS** | **100%** | None. New enum in the new package; `AM-29` r2 forbids reusing any of the nine listed values | Low |
| **Deterministic evaluators** (1,822 LOC) | `NUMERIC_COMPARISON` (`LIABILITY-001`) + generic `PRESENCE`; closed output vocabulary, deterministic explanations, fails closed to `UNABLE_TO_EVALUATE`, never reads clause text at evaluation time | Remains **sole** producer of Findings/Evaluations/Classifications/Rule Outcomes (`AM-25` r1) | **A · REUSE AS-IS** | **100%** | None. The target doc's `validate_clause → verdict` LLM call would *replace* this — see [C2](#c2--llm-produced-clause-verdicts-vs-am-25-r1r4) | Low code risk / **blocking decision risk** |
| **Mapping engine** (578 LOC) | Deterministic alias/phrase scoring with a per-signal explanation; `CONFIRMED`/`UNRESOLVED`/`NONE`; same input + same rule version → same score | Unchanged. Hybrid retrieval is **not** a replacement — it never sets a Mapping State (`AM-25` r1) | **A · REUSE AS-IS** | **100%** | None. Its configured alias/keyword groups are, separately, a good **seed vocabulary for query expansion** in the assist lane — read, never written | Low |
| **Fact extraction** (403 LOC) | Pure regex liability extraction, versioned config, fails closed to `UNKNOWN`, only runs on a `CONFIRMED` mapping | Unchanged | **A · REUSE AS-IS** | **100%** | None | Low |
| **Analysis orchestrator** (586 LOC) | Snapshot-driven per-Requirement run; document-type filter (an NDA produces no liability Finding); `ANALYSIS_FAILED` on undeclared type | Unchanged; the assist lane must not call into it | **A · REUSE AS-IS** | **~95%** | None functionally. Add only the CI import-boundary assertion that it never imports `legalmind.assist` | Low |
| **Review / decision workflow** (499 LOC) | Lifecycle transitions, `UNRULED_DEVIATION_REQUIRES_DECISION`, escalation, human-only Legal Decisions | Unchanged; no assist path may reach `legal.decision` (`AM-25` r8) | **A · REUSE AS-IS** | **100%** | None | Low |
| **Document parser** (327 LOC) | PDF (PyMuPDF) + DOCX (python-docx); per-page native text, OCR fallback via OCRmyPDF/Tesseract, OCR-derived content explicitly flagged, tables preserved, **page numbers, section numbers/titles, start/end offsets**, original text kept beside normalized, partial extraction represented, failures never invent text | Domain B ingestion: PDF/DOCX, text, page tracking, offsets, metadata | **A · REUSE AS-IS** | **~95%** | **None.** Target names `unstructured.io`/`docling`; `AM-26` says the existing parser stays primary and this parser already does every listed job — see [C9](#c9--parser-replacement-vs-am-26) | Low |
| **Document storage** (75 LOC) | `StorageBackend` Protocol (`put`/`get`/`exists`), write-once by construction (no update op), SHA-256 fingerprint, content-addressed keys, `0o440` after write; one local-filesystem implementation | MinIO, S3-compatible, per-tenant bucket policy | **B · REUSE WITH MODIFICATION** | **~90%** | Add an `S3CompatibleStorage` class implementing the same 3-method Protocol. Service layer unchanged. Compose gains a `minio` service. Locked 55.6 leaves the provider open and AB-3 confirms choosing one amends nothing | Low |
| **Ingestion service** (211 LOC) | Upload → MIME/size validation → store → parse → `DocumentProcessingRun` → write `DocumentEvidence`; **synchronous, in-request** | Same, plus a post-commit hook to dispatch indexing | **B · REUSE WITH MODIFICATION** | **~90%** | One dispatch call after `COMPLETED`, mirroring the existing `analyse_review` pattern. Making parsing itself async is **optional and separate** — do not bundle it | Low |
| **Security / authorization** (939 LOC) | `Guard`: visibility → permission → operation → DB; per-object resolvers; `NotVisible` → byte-identical 404; `redact_legal_position` omits (never nulls); 34 authz + 26 API-authz + 14 session tests | Retrieval authorized **before** retrieval, **inside** the query (`AM-25` r6); excluded results indistinguishable from empty (r6/r7); RIAAS tokens, role-scoped | **B · REUSE WITH MODIFICATION** | **~85%** | Add a chunk/document-scope guard method + `assist.*` permissions to the existing catalogue; build retrieval as a **pre-filtered** SQL candidate set, never post-filtered. RIAAS adapter is a separate item below | Medium |
| **Authentication** (302 LOC) | Password login + server-side sessions, HttpOnly/Secure/SameSite=Strict cookies, CSRF cookie, rate limiting, S-7-safe single-message failures; **OIDC routes specified (49.2) but not registered** — needs a JWT/JWKS dependency (rule 19) | "Existing RIAAS layer" | **E · NEEDS VERIFICATION** → then **B** | **~75%** | The RIAAS contract is undefined in both target documents. The session/`Principal` model is the right seam and survives either way; the adapter cannot be written until the contract is supplied. `AM-25` r8 stands: no identity provider grants a role | **High (unspecified)** |
| **Audit trail** (76 LOC + table) | Append-only `audit_events`, enforced by DB trigger; 25 event types; records identifiers, never contract text or legal position; `actor_id` nullable for pre-auth events | Immutable trail; every LLM call logged with clause id, timestamp, **payload hash not payload** | **B · REUSE WITH MODIFICATION** | **~95%** | Add assist event types. `AM-27`: `audit_events` gains new types and **no schema change** — so the target's separate `audit_log` table is unnecessary and would fragment the trail | Low |
| **Log redaction** (163 LOC) | Makes the logger *incapable* of emitting credentials/session material, contract or clause text, internal legal position, or enumeration oracles; no bypass in the logging API; length guard treats over-long values as content | Redaction before any external call; never log clause text | **B · REUSE WITH MODIFICATION** | **~90%** | Reuse as the egress redactor — it is the single most valuable pre-built piece for the LLM path. Note it currently guards *logs*; wiring it to a *payload* is new but small | Low |
| **Observability** (536 LOC) | Structured events, seven named signals, metrics; 33 tests | Assist metrics: token usage, retrieval/generation latency, citation-failure rate, refusal rate | **B · REUSE WITH MODIFICATION** | **~90%** | Additive, in a **separate signal namespace** — never mixed into `workflow.decisions.*`/`authz.*` | Low |
| **HTTP API** (3,351 LOC) | 39 endpoints, consistent envelope, pagination, error semantics, permission map, 139 tests | Add conversation/ask/citation endpoints; unified workspace reads | **B · REUSE WITH MODIFICATION** | **~90%** | Purely additive routers. **No existing endpoint contract changes** — verified: nothing in either target document requires altering one | Low |
| **Worker** (537 LOC) | Celery + Redis, one `analysis` queue, one task, idempotent, `acks_late` handled; 23 tests | An indexing pipeline that cannot run in-request | **B · REUSE WITH MODIFICATION** | **~80%** | Add an `index_document_version` task on a **separate queue** so indexing backlog never starves analysis. `AM-26`: the existing queue/worker infra is *reused, not replaced* | Low |
| **Deploy preflight** (494 LOC) | 18-check register, reproducibility gate, trigger verification; 24 tests | Add infra assertions | **B · REUSE WITH MODIFICATION** | **~70%** | New checks: pgvector extension present, model weights present + checksum match (`AM-26` r5), assist DB role holds **no** INSERT/UPDATE on locked tables (`AM-25` r2), egress posture | Medium |
| **Verification tools** (1,966 LOC) | `verify_invariants`, `verify_reproducibility`, `verify_terminology`, `verify_negative_mapping`, `verify_queue`, `e2e_bootstrap`, `import_ratified_standards` | Unchanged, plus assist-layer equivalents | **A · REUSE AS-IS** | **~95%** | None. `verify_reproducibility` becomes the **corpus-parity harness**: run the corpus with the assist lane off and on, assert byte-identical output | Low |
| **Company Standards config** (32 JSON files) | Ratified per-document-type standards, every position clause-cited to a real LeapSwitch document, zero-tolerance Legal Rule wired, import tool refuses any other rule | Domain A content, **derived from source, versioned, not hardcoded** (§3b) | **A · REUSE AS-IS** | **100%** | **None — vision §3b is already satisfied.** These are the Legal Constitution. Do not re-derive, do not re-ingest, do not "discover categories" afresh | Low |
| **Golden corpus** (9 fixture files, 32 cases, 64-case register) | Tier-1 normative harness; `corpus_coverage.json` tracks all 64; 0 `NORMATIVE` fixtures pending real material | Tier 1 unchanged; a **separate** Tier 2 eval set (`AM-28`) | **A · REUSE AS-IS** | **100%** | None. `AM-28` r3: the corpus stays Tier 1 under rule 21, and the assist eval set never substitutes for it | Low |
| **Test suite** (10,510 LOC, 726 tests) | Green; schema invariants, authz, evaluation, corpus, observability, worker, API contract | Preserved; Tier 2 added beside it | **A · REUSE AS-IS** | **~97%** | Near-zero edits — see [§11](#11-test-gap-analysis). `AM-27` r2 makes "the invariant tests still pass unmodified" the *evidence* the locked model is intact | Low |
| **Frontend** (10 routes, 58 Vitest + 22 Playwright) | Task-shaped routes; design system, shared primitives, typed API client, session context, permission gating (presentation only) | **Unified workspace**: one screen per session — document view + verdict cards + chat panel together | **B · REUSE WITH MODIFICATION** | **~60%** | Components, primitives, API client, session handling and design tokens all reuse. The workspace is a **new route composed of existing components**; existing routes stay (they serve configuration/audit/admin, which the workspace does not replace) | Medium |
| **Docker / compose** | `db`, `queue`, `api`, `worker`, `frontend`; api and worker are the **same image**, different command (locked 55.1); local-filesystem document volume | MinIO, Nginx+TLS, network segmentation, deny-by-default egress, per-service accounts, Vault | **B · REUSE WITH MODIFICATION** | **~50%** | Add `minio`, `nginx`, pgvector-enabled Postgres image, a local inference runtime; add segmented networks and egress rules. **Do not** decompose api/worker into services — see [C5](#c5--per-service-decomposition-vs-locked-3826--am-26) | Medium |
| **CI** (`ci.yml`, 12 jobs) | Blocking lint/type/test at a zero baseline | Plus Trivy, `pip-audit`/`npm audit`, import-boundary and corpus-parity gates | **B · REUSE WITH MODIFICATION** | **~85%** | Additive jobs | Low |
| **Retrieval layer** | **Does not exist** (grep: no `vector`, `embedding`, `pgvector`, `tsvector`, `tsquery`, `pg_trgm`) | Three-domain hybrid retrieval | **New build** | 0% | All new, in `legalmind/assist/` | High |
| **LLM integration** | **Does not exist** (grep: zero outbound HTTP call sites in `legalmind/`) | Isolated single-interface gateway | **New build** | 0% | All new. **Blocked on [C1](#c1--gemini-flash-hosted-api-vs-am-25-r9--am-26)** | **Blocking** |
| **Guardrails** | **No module.** But the *discipline* exists throughout: fail-closed evaluators, evidence-or-nothing, no-invented-text parsing, omit-not-null redaction | Citation verification, no-evidence-no-answer, confidence gate, cross-ref gate — own module, own tests, importing neither prompt nor model code (`AM-28` r2) | **New build**, patterned on existing code | ~10% | New `legalmind/assist/guardrails/`. The fail-closed idiom is copied from `evaluation/`, not invented | High |

### Overall

| | Share of ~24,900 LOC |
|---|---:|
| Directly reusable (A) | **~66%** |
| Reusable with modification (B) | **~33%** |
| Requiring replacement (C) | **~0%** |
| Obsolete (D) | **~0%** |

Plus an estimated **6,000–9,000 LOC of genuinely new, additive code** for the assist lane (retrieval,
guardrails, conversation API, workspace UI) — new work, not rewrite.

---

## 4. Architecture Gap Analysis

| Concern | Current | Target | Gap | Verdict |
|---|---|---|---|---|
| Overall shape | Modular monolith; api + worker are one image, two commands | Per-component containers, own networks/accounts | Target reads as microservice decomposition | **Contradiction [C5]** — keep the monolith; realize isolation at the network/DB-role layer |
| Analysis lane | One deterministic lane | Deterministic lane **+** assist lane, isolated | Assist lane absent | Additive; the seam (`38.25` analysis boundary) already exists |
| Module separation | `ingestion` / `mapping` / `extraction` / `evaluation` / `analysis` / `workflow` / `security` / `observability` | ingestion · retrieval · validation · guardrails · audit · persistence · LLM orchestration | Existing separation already matches for 4 of 7; `retrieval`, `guardrails`, `llm` are new | Add `legalmind/assist/{chunking,retrieval,guardrails,generation}` |
| Ingestion timing | Synchronous, in-request | Async pipeline | Indexing cannot run in-request | Add one dispatch hook; leave parsing synchronous |
| Storage | Local filesystem behind a Protocol | MinIO | Implementation absent, interface present | Small additive class |
| Reverse proxy / TLS | None (compose exposes ports directly) | Nginx + Certbot, internal TLS | Absent | Infra work, no application change |
| Secrets | `.env` / environment | Vault or encrypted `.env` + LUKS | Absent | Infra work |
| Egress control | **No egress exists at all** | Exactly one allow-listed egress | If the model is local (`AM-26`), the correct end state is **zero** egress — stronger than the target | Resolve [C1] first |
| Domain isolation (A/B/C) | Domain A exists as configuration; B as Evidence; C absent | Three indexes, never blended | No index for any domain; A and C have no authorized table | **[C3]** |

---

## 5. Database Gap Analysis

Existing: **29 tables**, all locked, all covered by 21 invariant tests. `AM-27` r2 forbids altering any
of them and makes those tests the evidence of that. **No migration touches an existing table.**

`AM-27` authorizes exactly nine new tables, in a **separate schema**:

| Authorized table | Purpose | Maps to target requirement |
|---|---|---|
| `chunks` | derived text spans of a Document Version, with page + offsets | Domain B chunking |
| `chunk_embeddings` | one row per chunk per embedding model | pgvector store |
| `embedding_models` | embedding model registry | model pinning (`AM-26` r4) |
| `conversations` | an assist-lane session | unified workspace session |
| `messages` | one row per turn | chat panel |
| `retrieval_runs` | query, filters, chunk ids, scores | retrieval audit |
| `ai_answers` | model, prompt version, answer state, latency | answer record |
| `answer_citations` | one verified claim→chunk link per row | citation verification |
| `prompt_versions` | prompt registry | prompt pinning |

*"No other table is authorized by this record."*

### Gaps against the target

| Target need | Authorized? | Note |
|---|---|---|
| Domain B chunks + embeddings + FTS | **Yes** | `chunks` + `chunk_embeddings`; a `tsvector` column and GIN index on `chunks` is within `AM-27` r3's design rules |
| Conversations, messages, answers, citations | **Yes** | Directly named |
| **Domain A index (Legal Constitution chunks)** | **No** | `AM-27` r4 defines a chunk as *derived from a Document Version, referencing a Document Evidence row*. Company Standards are configuration rows with neither → **[C3]** |
| **Domain C index (statutes, judgments)** | **No** | Statutes are neither Contracts nor Document Versions → **[C3]** |
| Per-tenant scoping | **No** | No workspace/tenant primitive exists anywhere; `AM-27` added none |
| `confidentiality_level` on a document | **No** | No such field exists; inventing a classification scheme is a rule-7-adjacent trap |

### Design rules the new tables must satisfy (`AM-27` r3–r6)

UUID PKs · UTC timestamps · real FKs · append-only where the row records something that happened ·
JSONB only for genuinely variable configuration · a chunk carries **no independent provenance** and
creates **no second source of truth** for document content · **deleting a document hard-deletes its
chunks and embeddings** — a soft-deleted document whose chunks stay retrievable is a defect · retrieval
and answer rows store **chunk ids and scores, never duplicated document text**.

> ⚠️ **`AM-27` r5 is not currently satisfiable and this is an open item, not an assumption.** This
> audit found **no confirmed hard-delete path for a Contract or Document Version** — `contract.delete`
> exists as a permission with no endpoint, and evidence is write-once. Cascade behavior cannot be
> designed until the real retention/deletion policy is stated. Do not assume `ON DELETE CASCADE`
> discharges r5.

---

## 6. API Gap Analysis

39 existing endpoints. **None needs its contract changed** — verified by reading both target documents
against the route table. All assist work is additive.

| Existing surface | Status under the target |
|---|---|
| `POST /auth/login`, `GET /auth/session`, `POST /auth/logout`, `DELETE /auth/sessions/{id}` | Keep. RIAAS/OIDC arrives as *additional* routes (49.2 already specifies `GET /auth/oidc/start`; the login page already links it) |
| `GET/POST/PATCH /contracts`, `POST /contracts/{id}/document-versions` | Keep unchanged — this is Domain B ingestion |
| `GET /document-versions/{id}`, `/content` | Keep — the workspace's document pane |
| `GET/POST /reviews`, `POST /reviews/{id}/analyze`, `/findings`, `/report` | Keep — the workspace's verdict cards |
| `GET /findings/{id}`, `/evaluations`, `POST|DELETE /findings/{id}/escalate` | Keep |
| `POST|GET /evaluations/{id}/decisions` | Keep — human-only, `AM-25` r8 |
| Configuration (6 routes), `GET /audit-events`, admin (9 routes) | Keep |

### New endpoints required

| Endpoint | Purpose | Notes |
|---|---|---|
| `POST /conversations` · `GET /conversations/{id}` | assist session | |
| `POST /conversations/{id}/messages` | **the unified ask endpoint** — router picks domain(s) | Must return an `AM-29` answer state, citations, and **no "confidence" number** — see [C15] |
| `GET /messages/{id}/citations` | resolve citations to page/section/offset | Reuses existing evidence serializers |
| `GET /document-versions/{id}/similar-clauses` | retrieval-only, no generation | Shippable before any model decision |
| `GET /indexing-runs/{id}` | async indexing status | Follows 52.7's poll pattern; no optimistic UI |

Rules that carry over unchanged: the response envelope, pagination, `NotVisible` → byte-identical 404,
omit-not-null for confidential fields, and CSRF on writes. `AM-25` r6/r7 additionally require that an
authorization-excluded retrieval result be **indistinguishable** from a genuinely empty one — including
in result count, error shape, and content.

---

## 7. Retrieval Gap Analysis

**Existing: nothing.** Verified by grep — no `vector`, `embedding`, `pgvector`, `tsvector`, `tsquery`,
`pg_trgm` anywhere in the backend. This is the largest genuinely-new component.

| Required | Present | Gap |
|---|---|---|
| Clause-aware chunking with page/offset provenance | **Inputs fully present** — `document_evidence` carries page, section number, section title, start/end offset, source type, and original text | Chunker is new but **mechanical**: it reads committed evidence rows rather than re-parsing text. This is the single biggest reuse win in the retrieval layer |
| Local embedding generation | Absent | New. `AM-26`: local, self-hosted, open-weight; selected by measurement from smallest upward (r2), pinned and recorded per answer (r4), weights fetched once and checksummed (r5) |
| pgvector store + ANN index | Absent | New. `AM-26` locks pgvector on the same instance; a second vector datastore requires separate approval |
| Postgres FTS (keyword half) | Absent | New: `tsvector` column + GIN index + `pg_trgm`. ⚠️ **Not BM25** — see [C10] |
| Fusion (e.g. RRF) + reranking | Absent | New. Cross-encoder, local, open-weight (`AM-26`) |
| Domain routing | Absent | New. Must never blend domains; A and C have no authorized table yet — **[C3]** |
| **Pre-filtered authorization inside the query** | The pattern exists and is tested (`Guard`, visibility resolvers, byte-identical 404) | New SQL, existing discipline. `AM-25` r6: authorization **before** retrieval, **inside** the query; never post-filtered. Post-filtering would create a result-count/ranking oracle — exactly what r7 forbids |
| Metadata filtering (document type, version) | `Contract.contract_type` and `DocumentVersion` already carry it; the analysis path already filters by document type | Reuse the same values; join for `owner_id`, **never denormalize it onto a chunk row** (it would drift out of sync with the real ownership record) |

**Performance note worth designing for, not discovering:** a highly selective permission filter can
starve a fixed-candidate ANN scan. pgvector's iterative index scans (v0.8.0+) exist for exactly this;
pre-filtered ANN search needs them enabled, not assumed.

---

## 8. LLM Gap Analysis

**Existing: nothing, and no outbound HTTP of any kind.** A model call would be the first external
network egress this codebase has ever made — there is no client, no timeout/retry policy, no egress
logging and no redaction-before-send to extend.

| Target requirement | Locked position | Status |
|---|---|---|
| Gemini Flash as the generation model | `AM-26`: generative model is **local, self-hosted, open-weight**; "any hosted model … service" is **NOT ADDED** and needs separate approval. `AM-25` r9: no prompt, chunk, clause text or generated answer leaves LeapSwitch infrastructure | **[C1] — blocking contradiction** |
| Single wrapped interface, callers model-agnostic | `AM-26` r1: *"All generation reaches the application through one interface. The model identity is configuration, and no other code knows which model is running."* | **Agreement.** Build this regardless of which model wins — it is what makes [C1] a config change instead of a rewrite |
| `validate_clause(clause, context) → verdict` | `AM-25` r1/r4 | **[C2] — blocking contradiction** |
| Only retrieved chunks reach the model, never the full document | `AM-25` r5 | **Agreement** |
| Minimal-context sending + redaction | `observability/redaction.py` is ready to serve as the redactor | Reuse |
| Per-call audit log with payload **hash**, not payload | `audit_events` + append-only trigger + a redactor that already forbids logging clause text | Reuse; add event types, no schema change |
| Model version pinned and recorded per answer | `AM-26` r4; `ai_answers` and `prompt_versions` tables authorized | Additive |
| Structured output validated in application code | Never trust a vendor schema as a semantic guarantee | New, in guardrails |

**The isolation the target asks for is exactly what `AM-26` r1 already locks.** Whichever way [C1] is
decided, the one-interface boundary is the right thing to build first, and it is small.

---

## 9. Guardrail Gap Analysis

No `guardrails` module exists. But the *discipline* the target wants is already the house style, and the
new module should copy those idioms rather than invent new ones:

| Existing control (reusable pattern) | Where |
|---|---|
| Fail closed to an explicit "cannot evaluate" state, never a guess | `evaluation/` — `UNABLE_TO_EVALUATE`, `NOT_APPLICABLE` |
| Never invent text when extraction fails | `ingestion/parsing.py` (34.9), every branch |
| Evidence-or-nothing: no facts from a non-`CONFIRMED` mapping | `analysis/service.py` |
| Omit, never null, a field the viewer may not see | `security/authorization.py::redact_legal_position` |
| Byte-identical 404 for out-of-scope objects | `Guard._visible` / `NotVisible` |
| Make the forbidden thing structurally impossible, not merely discouraged | `observability/redaction.py` — no bypass in the logging API |
| Un-ruled outcomes route to a human | `UNRULED_DEVIATION_REQUIRES_DECISION` |

| Required control | Status | Note |
|---|---|---|
| Citation verification — every claim resolves to a retrieved chunk | **New** | `AM-25` r5: enforcement is **mechanical and outside the model**. `AM-28` r2: tested independently, and it **must not import prompt or model code** — *"a guardrail that a prompt change can affect is not a guardrail"* |
| No retrieval → no model call | **New** | `AM-29` r3 distinguishes *no evidence retrieved* from *evidence insufficient* (model **not called at all**) from *claim unsupported* (model answered, verification failed). Three causes, three remedies — record them separately |
| Refusal wording identical regardless of cause | **New** | `AM-29` r4: an empty corpus and an authorization exclusion must read identically, or r6/r7 leak |
| Confidence threshold | **New, and needs care** | `AI-03` item 16 forbids generic AI confidence scores; a retrieval score is never rendered as legal confidence — **[C15]** |
| Cross-reference hard gate | **New** | |
| Never state a legal position absent from a ratified Standard | **New** | `AM-25` r3: where a position is absent, the output is a **gap reported to a human** |
| Never answer "does this meet our standard?" | **New — routing rule** | `AM-25` r4: route to the evaluator or refuse; never answer generatively |
| Confidential positions never leak via an answer | Partly present (`redact_legal_position`) | `AM-25`: omit-not-null applies to assist answers exactly as to deterministic ones |

---

## 10. Security Gap Analysis

| Control | Existing | Target | Gap |
|---|---|---|---|
| AuthN | Password + server-side sessions; HttpOnly/Secure/SameSite=Strict; CSRF; rate limit; S-7-safe failures | RIAAS role-scoped tokens | Adapter needed; **contract unspecified** |
| AuthZ | `Guard`, server-side, before every DB operation; 60+ tests | Same, extended to retrieval | Chunk guard + `assist.*` permissions; pre-filtered SQL |
| Legal authority | `legal.decision` / `legal.approve_customization` explicitly un-inheritable; no super-role bypass | Unchanged | None. `AM-25` r8 reaffirms |
| Object enumeration | Byte-identical 404; `authz.object_not_visible` audited | Extended to retrieval result sets | `AM-25` r6/r7 — new, and the subtlest requirement in the batch |
| Confidentiality | Omit-not-null; `LEGAL_POSITION_FIELDS` |Same in assist answers | Reuse |
| Least privilege (DB) | Single application role | Per-service roles | **New, and load-bearing:** `AM-25` r2 requires a distinct DB role with **no INSERT/UPDATE grant** on the 10 named authoritative tables — *"enforced by a database role … not by convention"* |
| Audit integrity | Append-only, DB-trigger-enforced; no delete grant | Immutable + OS-level auditd/Wazuh | Application side done; OS side new |
| Log hygiene | Redactor with no bypass; length guard | Never log clause text | Done — reuse for egress |
| Network segmentation | None (compose exposes ports) | Segmented networks, deny-by-default `ufw`, one allow-listed egress | New infra |
| Secrets | env vars | Vault or encrypted `.env` + LUKS | New infra |
| Egress | **Zero** | Exactly one, allow-listed | If [C1] resolves to a local model, the right end state is **zero egress** — the existing posture, kept |
| Encryption at rest / in transit | Deployment concern; 55.2 | LUKS + TLS everywhere internally | New infra |
| Dependency / container scanning | `pip-audit` not in CI; no Trivy | Trivy + pip-audit + npm audit + OpenVAS + ZAP | Additive CI jobs |
| Real-contract environment rule | 55.3/54.6: real contracts never leave production; no document text in the repo | Same | **Must extend to embeddings, prompts, cached answers and any eval set** |

---

## 11. Test Gap Analysis

**726 tests, all passing.** The key finding: **essentially no existing test encodes an obsolete product
assumption.** The tests assert the deterministic engine's behavior, and `AM-25` r1 keeps that behavior
authoritative — so they remain valid *by the terms of the amendment that introduced the new vision*.

| Suite | Tests | Verdict |
|---|---:|---|
| `test_schema_invariants` | 21 | **Preserve unmodified** — `AM-27` r2 makes them the evidence the locked model is intact |
| `test_authorization`, `test_api_authz`, `test_sessions` | 74 | Preserve; **extend** with retrieval-authorization and indistinguishability cases |
| `test_evaluation_*`, `test_extraction_*`, `test_mapping*`, `test_analysis` | ~180 | Preserve unmodified — this is Tier 1 |
| `test_golden_corpus`, `test_corpus_coverage`, `test_calibration_*` | 54 | Preserve; Tier 1 under rule 21 (`AM-28` r3) |
| `test_ingestion` | 20 | Preserve; add cases for the post-commit indexing dispatch |
| `test_api_*`, `test_api_contract` | 139 | Preserve; new endpoints get their own tests |
| `test_worker` | 23 | Preserve; extend for the new queue/task |
| `test_observability` | 33 | Preserve; extend for the separate assist namespace |
| `test_deploy_preflight` | 24 | Preserve; extend with pgvector/model-checksum/DB-grant checks |
| `test_source_material` | 5 | Preserve; **extend to assert no document text reaches a chunk fixture or eval set** (54.6) |
| Frontend 58 Vitest + 22 Playwright | 80 | Preserve; the workspace is a new route, so existing selectors are untouched |

### Obsolete tests: **none identified.** Nothing needs deleting.

### Coverage gaps to close (all new)

1. **Corpus-parity regression** — the whole corpus with the assist lane off and on, asserting
   byte-identical Finding/Evaluation output. This is the mechanical proof that `AM-25` r1/r2 hold, and
   it should gate every assist-layer change. `tools/verify_reproducibility.py` is the harness to extend.
2. **CI import-boundary test** — `evaluation/`, `analysis/`, `mapping/`, `extraction/`, `workflow/`
   must never import `legalmind.assist`. Static, cheap, and it is what stops the boundary eroding
   across many future PRs.
3. **DB-grant test** — assert the assist role holds no INSERT/UPDATE on the 10 tables named in
   `AM-25` r2. Enforceable independently of application correctness.
4. **Guardrail unit tests with no prompt/model import** — `AM-28` r2.
5. **Retrieval indistinguishability tests** — an authorization-excluded result must be byte-identical
   to an empty one, including result count and error shape (`AM-25` r6/r7, `AM-29` r4).
6. **Tier 2 evaluation set** — retrieval recall, citation precision, faithfulness, and refusal
   correctness in **both** directions. `AM-28`: built from **real supplied documents**, including
   questions with no answer in the corpus; *"correct refusal is half the bar."* **It does not exist and
   cannot be manufactured** (rule 21).
7. **Chunk-provenance test** — every chunk's text is a strict substring of its evidence row's content;
   no chunk exists without a resolvable evidence ancestor (`AM-27` r4).

---

## 12. Architectural Contradictions

Recorded, not resolved. Each states: existing behavior · intended behavior · why they conflict ·
recommended resolution · whether existing code adapts · whether a rewrite is actually necessary.

### C1 — Gemini Flash (hosted API) vs `AM-25` r9 / `AM-26`

* **Existing:** zero outbound HTTP anywhere in `legalmind/`. No egress has ever existed.
* **Intended:** Gemini Flash, hosted API, the single permitted external dependency; clause-level
  content leaves the infrastructure on every call (the tech doc states this openly as a deliberate
  tradeoff, §8).
* **Why they conflict:** `AM-25` r9, **locked 2026-08-24** — *"No document text, clause text, evidence,
  chunk, embedding input, prompt or generated answer leaves LeapSwitch-controlled infrastructure. No
  hosted model API…"* `AM-26` locks the generative model as *local, self-hosted, open-weight* and lists
  *"any hosted model, embedding or document-processing service"* under **NOT ADDED, requiring separate
  approval**. The target documents are dated 2026-08-25 — one day later — and make the forbidden option
  the centerpiece.
* **Recommended resolution:** **owner decision required; this audit must not pick.** Two coherent
  paths: **(a)** honor AB-3 — local open-weight model, zero egress, and the target's whole
  `llm-gateway`/redaction/egress-allow-list apparatus becomes unnecessary (a *simpler* system than the
  target describes); **(b)** amend `AM-25` r9 and `AM-26` explicitly, by name, with the Gemini
  enterprise zero-retention terms confirmed in writing first — which the tech doc itself makes a hard
  go/no-go gate (§2, §4).
* **Can existing code adapt?** Not applicable — there is no LLM code to adapt either way.
* **Is a rewrite necessary?** No. Build `AM-26` r1's single interface first and the model identity stays
  configuration. **This decision changes ~200 LOC behind one interface, not the architecture** — which
  is precisely why r1 exists. Nothing else in the plan needs to wait for it.

### C2 — LLM-produced clause verdicts vs `AM-25` r1/r4

* **Existing:** `LIABILITY-001` (`NUMERIC_COMPARISON`) and the generic `PRESENCE` evaluator produce
  every Finding, Classification and Rule Outcome deterministically, with a reconstructable
  Evidence → Fact → Standard → Rule → Result chain and byte-identical reproducibility. 1,822 LOC,
  ~180 tests, zero-tolerance Legal Rule wired.
* **Intended:** `validate_clause(clause, context) → verdict` through the gateway (tech §3, §7.4);
  *"clause-by-clause verdicts against Domain A"* (vision §6).
* **Why they conflict:** `AM-25` r1 — the assist lane *"NEVER produces a Finding, an Evaluation, a
  Finding Classification, a Rule Outcome, a Mapping State, a Legal Decision, or a Review Lifecycle
  transition."* r4 — it *"NEVER answers the question 'does this document meet our standard?' … routed to
  the evaluator or refused; never answered generatively."* A verdict is a Classification. Separately,
  `AM-28` r1 bars any assist component from the byte-identical determinism gate the 726-test suite
  enforces, and `AI-03` item 16 forbids the confidence score such a verdict would carry.
* **Recommended resolution:** **keep the deterministic evaluator as the sole verdict producer.** Route
  a "does this meet our standard?" query to it, and give the assist lane the three roles it is good at
  and permitted for: Domain B document Q&A, Domain C statute research, and *rephrasing an existing
  deterministic explanation* in plainer language with every sentence traceable to a field already
  persisted. The user-visible product — cited verdicts beside a chat panel — is fully deliverable this
  way. The **verdict** comes from the engine; the **conversation** comes from the model.
* **Can existing code adapt?** It needs no adaptation. It is already correct.
* **Is a rewrite necessary?** **No — and this is the single largest unnecessary rewrite available in
  this repository.** Replacing the evaluator would discard 1,822 LOC and ~180 tests, forfeit
  reproducibility, and break the locked explainability contract, to reach a *less* defensible answer.

### C3 — Domain A and Domain C have no authorized table

* **Existing:** Domain A exists as 32 ratified Company Standards in versioned JSON configuration.
  Domain C does not exist; the seven supplied statutes sit on disk, unindexed.
* **Intended:** three parallel pgvector + FTS indexes, one per domain.
* **Why they conflict:** `AM-27` r4 defines a chunk as *derived from an existing immutable Document
  Version, referencing the Document Evidence row it came from*, and closes with *"No other table is
  authorized by this record."* Company Standards are configuration rows — no Document Version, no
  Evidence. Statutes are neither Contracts nor Document Versions. So **only Domain B is authorized
  today.**
* **Recommended resolution:** ship Domain B first (fully authorized, and the highest-value surface
  anyway), and raise Domain A and Domain C as an explicit `AM-27` extension request naming the tables
  needed. Two credible shapes, for the owner to choose: ingest the Legal Constitution and the statutes
  *as Document Versions* so `AM-27` r4 is satisfied unchanged (no amendment needed, but it puts statute
  text into the contract tables); or authorize separate `corpus_documents`/`corpus_chunks` tables (an
  amendment, but a cleaner domain boundary). **Do not create either table without approval.**
* **Can existing code adapt?** Yes, in the first shape: the existing ingestion + evidence + chunking
  path would serve all three domains with no new pipeline.
* **Is a rewrite necessary?** No. This is a schema-authorization question, not an engineering one.

### C4 — Statute corpus provenance and coverage

* **Existing:** seven statutes supplied on disk (Contract Act 1872, IT Act 2000, SPDI Rules 2011,
  Companies Act 2013, CERT-In Directions 2022, DPDP Act 2023, IT Rules 2021). CLAUDE.md's standing rule:
  a statute is **not** a Legal Rule and **not** a Company Standard — background law, cited in an
  explanation, never loaded as configuration, and no Requirement, threshold or acceptance position is
  derived from one.
* **Intended:** India Code (`indiacode.nic.in`) as the canonical source — *"a hard rule"* (vision §9.2);
  the v1 set is Contract Act, IT Act, DPDP Act, Companies Act, plus Evidence Act and NI Act if time
  permits; the recurring worked example is *"what does Section 138 of the NI Act say?"*
* **Why they conflict:** partly they do not — Domain C is retrieval-and-citation only, which is
  compatible with the background-law rule. Two real gaps: **(a)** all four prioritized statutes are
  already on disk, but the **NI Act and Evidence Act were never supplied**, so the vision's headline
  worked example cannot be served; **(b)** the four on disk did not come from India Code, so if §9.2 is
  a hard provenance rule they must be re-fetched from the official repository and checksummed, not
  indexed as-is.
* **Recommended resolution:** confirm provenance for the four supplied statutes against India Code
  before indexing; request the NI Act and Evidence Act **from the owner** (rule 21 — missing source
  material is a blocker to raise, never a gap to fill); and pin a hard rule at the loader that a statute
  can never become a Requirement or a threshold. Note that locked 54.6 keeps statute text out of the
  *repository*; the database is not the repository, but no fixture may carry the text.
* **Can existing code adapt?** Yes — the parser handles these PDFs today (`parsing` reports `COMPLETE`
  on the supplied set).
* **Is a rewrite necessary?** No.

### C5 — Per-service decomposition vs locked 38.26 / `AM-26`

* **Existing:** modular monolith. `api` and `worker` are the **same image** with different commands
  (locked 55.1). Repository layout is `backend/` + `frontend/`.
* **Intended:** `/opt/legal-mind/` with eight top-level service directories, each *"its own Docker
  container, own internal network segment, own service account"*, including `llm-gateway` as a separate
  service.
* **Why they conflict:** locked 38.26 forbids microservice decomposition in V1, and `AM-26` lists
  *"Modular monolith — no microservices, no Kubernetes, no service mesh"* explicitly **UNCHANGED**. The
  proposed layout also contradicts the existing repository structure.
* **Recommended resolution:** **keep the monolith; take the isolation, drop the decomposition.** The
  security properties the target actually wants — network segmentation, per-service DB roles,
  deny-by-default egress, non-root service accounts, one auditable egress point — are all achievable
  without splitting the application, and `AM-25` r2's DB-role requirement delivers the strongest of them.
  Realize `llm-gateway` as an in-process module behind `AM-26` r1's single interface (which already
  mandates exactly that boundary) plus network-level egress control. Note that under [C1] path (a) there
  is **no egress at all**, and the gateway's purpose reduces to model-identity isolation.
* **Can existing code adapt?** Nothing needs to change. The compose file gains services (`minio`,
  `nginx`, inference runtime) and segmented networks without splitting `api`/`worker`.
* **Is a rewrite necessary?** **No, and attempting it would be the second-largest unnecessary rewrite
  available here** — it would touch every module's deployment assumptions for no security gain over the
  DB-role + network approach.

### C6 — Two mutually exclusive egress designs *inside* the tech-stack document

* **§2 (stack table):** *"Inference access — Outbound HTTPS call from **`backend-api`** only — no other
  service has network access to call it."*
* **§3 / §4 / §5 / §7:** *"**`llm-gateway`** is the **only** container with outbound internet access …
  no other service in the stack can reach the internet at all."*
* **Why they conflict:** they name different components as the sole egress point. §7's build order and
  the egress-verification script both assume the gateway; §2 assumes the API.
* **Recommended resolution:** the gateway, on weight of evidence (four sections to one) — but this is
  the target document's own inconsistency and its author should confirm. It is moot under [C1] path (a).
* **Rewrite necessary?** No.

### C7 — GPU: required or not, also *inside* the tech-stack document

* **§2 hardware note:** *"Llama 3.1 70B / Mistral Large needs real GPU … Confirm GPU allocation before
  Phase 1 — this is the one dependency that can block the whole timeline if not pre-provisioned."*
* **§5.4:** *"**No GPU provisioning needed** — this is the one infra requirement that drops out
  entirely by using Gemini Flash."*
* **Why they conflict:** §2's note is residue from the fully-self-hosted predecessor. The two statements
  cannot both hold.
* **Recommended resolution:** **the answer follows [C1], and it matters for procurement.** Under AB-3 as
  locked, `AM-26` adds a *"GPU runtime — where required by the selected model"*, so a GPU **is** on the
  critical path and §2's warning is the operative one. Under a Gemini amendment, §5.4 is right. Resolve
  [C1] before anyone sizes hardware.
* **Rewrite necessary?** No — a provisioning question.

### C8 — Vector store: pgvector or Qdrant

* **Existing:** neither.
* **Intended:** vision §9.5 and tech §1a say pgvector + Postgres FTS; tech §2 offers *"pgvector … OR
  Qdrant (self-hosted) if scale demands separation"*, and §3's folder tree has a `db-vector/` for either.
* **Why they conflict:** `AM-26` locks the pgvector extension on the same instance and lists *"a second
  datastore for vectors"* under **NOT ADDED, requiring separate approval**.
* **Recommended resolution:** **pgvector** — settled by `AM-26`, and by the majority of the target
  documents' own statements. The Qdrant line is stale; treat it as closed, revisitable only by explicit
  approval if measured scale ever demands it.
* **Rewrite necessary?** No.

### C9 — Parser replacement vs `AM-26`

* **Existing:** PyMuPDF + python-docx, 327 LOC, 20 tests, implementing locked Step 34: per-page native
  text, OCR fallback with OCR-derived content explicitly flagged, tables preserved, page numbers,
  section numbers and titles, start/end offsets, original text retained beside normalized, partial
  extraction represented, failures never inventing text.
* **Intended:** *"unstructured.io (OSS library) or docling"* (tech §2, §5.3).
* **Why they conflict:** `AM-26` states *"Document parsing — the existing parser and OCR path remain the
  primary path"* under **UNCHANGED**. The existing parser already produces every artifact the target
  lists, and a new library is a new dependency (rule 19).
* **Recommended resolution:** **keep the existing parser.** This is exactly the case the brief's §8
  describes — do not rebuild a parser that already accepts PDF/DOCX, extracts text, preserves page
  numbers, generates offsets and stores metadata. Revisit only if a *measured* extraction-quality gap
  appears on real documents, as a narrow addition, never a replacement.
* **Rewrite necessary?** **No.**

### C10 — "BM25" vs Postgres FTS

* **Existing:** no keyword index.
* **Intended:** vision §5.1 says *"keyword/BM25"*; vision §9.5 and tech §1a say **Postgres native FTS
  (`tsvector`/`tsquery`)**, explicitly not Elasticsearch.
* **Why they conflict:** built-in `tsvector`/`ts_rank` is **not** BM25 — true BM25 in Postgres needs an
  extension, which would be a new dependency (rule 19).
* **Recommended resolution:** implement `tsvector`/`tsquery` with `ts_rank` plus `pg_trgm` for fuzzy
  section/party matching, and **stop calling it BM25** so nobody specs or benchmarks against a ranking
  function the stack does not have. Terminology precision, not an architecture change.
* **Rewrite necessary?** No.

### C11 — "8 clause categories, 22-conflict register" vs what actually exists

* **Existing:** **32 ratified Company Standards across four document types**, every position clause-cited
  to a real LeapSwitch document, derived by full-document review on 2026-08-19 (superseding an earlier
  catalogue), stored as versioned configuration. Coverage of the 64-case corpus register is tracked in
  `backend/tests/corpus_coverage.json`. The owner's conflict register lives in a **different project**
  (`/root/LegalMind/docs/CONFLICT_GAP_ANALYSIS.md`); it was assessed and used as **corroboration only,
  never as a source**, because its own tracker leaves items "Needs owner decision" / "Needs fact-check".
* **Intended:** tech §3 seeds *"8 clause categories, 22-conflict register"*; tech §6 Phase 8 runs *"the
  22-conflict register as live eval set"*; vision §7 says Domain A seeding is *"already largely done"*.
* **Why they conflict:** the numbers are stale placeholders from the earlier product — and vision §3b
  itself says to treat any specific number as a guess until verified against the real document, which
  has already been done and produced neither 8 nor 22. An unresolved register cannot be an eval set.
* **Recommended resolution:** **treat vision §3b as satisfied work, not Phase-1 work.** Do not re-run a
  category-discovery pass; do not seed 8 categories. Build Phase 8's eval set from the 32 ratified
  standards and the 64-case corpus register. If the owner wants the cross-project conflict register
  incorporated, that is a separate, explicit request — it is not v1 source material.
* **Rewrite necessary?** No — this *avoids* rebuilding finished work.

### C12 — RIAAS vs the implemented authentication

* **Existing:** password login + server-side sessions, hardened cookies, CSRF, rate limiting, S-7-safe
  failures. OIDC routes are specified (49.2) but **not registered**: they need a JWT/JWKS library, which
  is a dependency requiring approval. The login page already links `GET /api/v1/auth/oidc/start` so it
  activates when the backend ships.
* **Intended:** *"Auth: Existing RIAAS layer"* — described in one line in each document, with no
  protocol, token format, claims, role mapping or endpoints.
* **Why they conflict:** not a design conflict — an **unspecified interface**. It cannot be built from
  what the documents say.
* **Recommended resolution:** **request the RIAAS integration contract** (protocol, discovery/JWKS
  endpoint, token format, claims, session lifetime, role-mapping rules). The existing `Principal` and
  server-side session model is the right seam and survives any answer, so password login stays as the
  controlled fallback 47.1.3 specifies. **`AM-25` r8 is a hard constraint on whatever arrives: no role
  and no Legal Decision authority is ever granted by an identity provider.**
* **Can existing code adapt?** Yes — an adapter behind `get_principal`, not a rework.
* **Rewrite necessary?** No.

### C13 — MinIO: not a conflict

Recorded so nobody re-litigates it. Locked 55.6 leaves the object-storage **provider** unspecified, and
AB-3 states plainly that selecting an S3-compatible provider *"closes an open item; it does not alter a
lock."* `StorageBackend` is a 3-method Protocol; MinIO is a small additive implementation. **Proceed.**

### C14 — Multi-tenancy / external customers

* **Existing:** single-tenant at the database level. Ownership is `Contract.owner_id → users.id`; roles
  are global. `workspace` and `tenant` appear nowhere in the schema, the security layer, or the locked
  architecture.
* **Intended:** vision §2 — later use by other departments and *"external customers reviewing their own
  contracts"*, with the architecture supporting it *"without rework"*; tech §3/§4 assume per-tenant MinIO
  buckets and RIAAS-scoped tenant isolation.
* **Why they conflict:** per-tenant bucket policies and tenant-scoped retrieval presuppose a primitive
  that does not exist, and `AM-27` authorized no tenant table.
* **Recommended resolution:** **do not invent a tenant model, and do not build isolation logic against
  an imagined schema.** Build retrieval isolation on the real `owner_id` + role model, which is
  sufficient for the stated "now" (internal legal team). Raise multi-tenancy as its own product decision,
  independent of AI/RAG. Note vision §2's own constraint cuts the other way and *helps*: one shared
  central corpus, not per-customer knowledge bases — so the retrieval design does not need tenant
  partitioning even when tenancy arrives.
* **Rewrite necessary?** Not now. Deferring is cheaper than guessing, and a wrong guess *is* the rework
  §2 wants to avoid.

### C15 — "Confidence" in the answer surface

* **Existing:** no confidence value is displayed anywhere. Mapping scores carry an explicit per-signal
  explanation, never an opaque number, and 35.19 forbids an opaque score being the basis of a legal
  conclusion.
* **Intended:** vision §4 and §5 — every answer shows *"text answer + explicit source citation(s) +
  **confidence**"*.
* **Why they conflict:** `AI-03` locked item 16 — *"The system does not use generic AI confidence
  scores"* — and rule 12's explainability contract: *"No generic risk score, no 'AI confidence'
  percentage."* `AM-25`/`AM-29` route around this deliberately: the assist lane records its own retrieval
  scores and a separate **answer state**, and *"a retrieval score is never a Finding, never a
  Classification, and is never rendered to a user as legal confidence."*
* **Recommended resolution:** render the **`AM-29` answer state** — answered · no evidence retrieved ·
  evidence insufficient · claim unsupported — plus per-citation retrieval scores **labeled as retrieval
  scores**, never a single "confidence" figure beside a legal statement. This delivers the honest signal
  the vision wants; it is the *word* that must change, not the intent. **The owner should confirm the
  substitution**, since the vision states "confidence" three times.
* **Rewrite necessary?** No.

### C16 — The two-day plan

* **Intended:** eight phases across two days, ending in production deployment.
* **Why it conflicts with the evidence:** the phases include seeding three domains, a new database
  schema, an inference runtime, hybrid retrieval with reranking, a guardrail module with its own tests,
  a unified workspace UI, a full pen-test pass, and go-live — against a 25k-LOC codebase with 726 tests
  that must all still pass, plus `AM-26` r2/r3's **selection by measurement** on an evaluation set that
  does not exist and cannot be manufactured (rule 21), plus `AM-28`'s Tier-2 gate.
* **Recommended resolution:** keep the phase *sequence* — it is sound and dependency-ordered — and treat
  the durations as placeholders. Phase 2's "Domain A seeding" is already done ([C11]); Phase 8's eval
  sets need real material. §15 below re-orders by dependency against actual repository evidence.

---

## 13. Ambiguities in the target documents themselves

Flagged explicitly, per instruction 10 — not silently resolved.

| # | Ambiguity | Resolvable from the documents? |
|---|---|---|
| 1 | Vector store: pgvector vs Qdrant | **Yes** — pgvector; `AM-26` plus both documents' primary statements ([C8]) |
| 2 | Exact Gemini model/version — *"Gemini Flash (latest, e.g. 3.7)"* | **No.** "Latest" is not a pin, and `AM-26` r4 requires a pinned, recorded version. Moot under [C1] path (a); **decision required** otherwise |
| 3 | Gateway networking: `backend-api` or `llm-gateway` as sole egress | **No** — the document contradicts itself ([C6]). Author must confirm |
| 4 | GPU required or not | **No** — the document contradicts itself ([C7]). Follows [C1] |
| 5 | Database ownership boundaries — *"extraction service can't write to `rules`"* | **Partly.** `AM-25` r2 fixes the assist role's grants exactly; the other per-service roles are named in principle only. **Decision required** for the full grant matrix |
| 6 | Authentication contract (RIAAS) | **No** — one line in each document, no protocol, claims or endpoints ([C12]). **Decision/material required** |
| 7 | Domain-routing behavior — *"the retrieval layer decides"* | **No.** Whether routing is a classifier, a rule set, or always-search-all-then-fuse is unspecified, and it directly affects cost, latency and the never-blend-domains guarantee. **Decision required** |
| 8 | Schema migration strategy for the new tables | **Partly.** `AM-27` r1 requires a separate schema; whether Alembic manages both schemas in one chain or a second chain is an implementation choice this audit recommends recording as such (one chain, one head — simpler, and the reproducibility gate already walks it) |
| 9 | Chunk sizes / overlap / reranker depth / retrieval `top-k` | **No** — no numbers given. Recommend *measuring* rather than inventing values (rule 7's habit applied to a product metric) |
| 10 | "Confidence" semantics | **No** — conflicts with locked item 16 ([C15]). **Owner confirmation required** |
| 11 | Judgment set — *"Legal team supplies a specific list"* | **No** — the list does not exist. Rule 21: request it, never invent it |
| 12 | Which secrets manager — Vault or encrypted `.env` + LUKS | **Partly** — the document offers either; recommend `.env` + LUKS for V1 and record Vault as deferred, since Vault is a new service (rule 19) |

---

## 14. Documentation Changes

Following instructions 12 and 13 — update the canonical document, do not create competitors.

| File | Change | Why |
|---|---|---|
| **`docs/architecture/EXISTING_BACKEND_REUSE_AUDIT.md`** | **New (this file)** | No existing document performs an existing-code-vs-new-target reuse audit. Genuinely new content, placed in the existing `docs/architecture/` home rather than a new tree |
| **`docs/architecture/AI_RAG_ARCHITECTURE_RND.md`** | **Amend the status banner only** — note it predates AB-3, that AB-3 supersedes its "post-V1" framing and its self-hosted-vs-hosted open question, and cross-link this audit. **Body preserved**: its codebase findings (§2.3 synchronous ingestion, §2.5 no egress, §2.10 no tenant model) were re-verified here and hold | It remains the deeper design reference for chunking, retrieval and validation. Rewriting it would destroy valid work; leaving it unbannered would leave two documents appearing to answer the same question with different authority |
| **`docs/README.md`** | Add one index row for this audit under the existing `architecture/` section | Rule: a new document is indexed in the same change |
| **`CHANGELOG.md`** | One `[Unreleased]` entry | Repository change record |
| `docs/00-project/IMPLEMENTATION_STATUS.md` | **Flag, do not edit here.** Its Build-state table reads "653 tests" and *"No Legal Rule exists"*; the suite is now **726** and CLAUDE.md records the zero-tolerance Legal Rule as approved and wired on 2026-08-20 | It is the only document permitted to assert build state, so correcting it is its own change with its own verification — not a side effect of an audit. **Reported, per instruction 6** |
| `docs/00-project/CONFLICTS.md` | **Register C1–C3 and C5** once the owner has seen them | Rule 5: a discovered contradiction is registered and surfaced, never resolved unilaterally |
| `docs/05-architecture/SYSTEM_ARCHITECTURE.md`, `BACKEND_ARCHITECTURE.md` | **No change yet** | 🔒 LOCKED. They may only be superseded with a banner after AB-3's stack additions are reflected by an approved change — never overwritten (rule 22) |
| `legalmind-product-vision.md`, `legal-mind-tech-stack-and-buildplan-v2.md` | **No change** | They are the owner's input documents. This audit reports contradictions against them; it does not edit the owner's brief |

---

## 15. Migration Plan

Ordered by **dependency against repository evidence**, not by the target document's phase numbering.
Every phase is additive and independently revertible. The deterministic lane is untouched throughout,
verified mechanically at each phase by the corpus-parity test.

**Phase 0 — Decisions (no code). BLOCKING for Phases 5+ only.**
Resolve [C1] (hosted vs local model), [C3] (Domain A/C tables), [C12] (RIAAS contract), [C15]
("confidence" wording). Register C1–C3, C5 in `CONFLICTS.md`. Request from the owner: NI Act + Evidence
Act, the curated judgment list, and the Tier-2 evaluation set's real Q&A material.
*Phases 1–4 do not depend on any of this and can start immediately.*

**Phase 1 — Documentation reconciliation (no code).**
This audit; the R&D banner; `docs/README.md`; `CHANGELOG.md`. Report the stale
`IMPLEMENTATION_STATUS.md` figures for separate correction.

**Phase 2 — Isolation scaffolding, inert.**
`legalmind/assist/` package skeleton (empty). **CI import-boundary test** asserting `evaluation/`,
`analysis/`, `mapping/`, `extraction/`, `workflow/` never import it. **Corpus-parity harness** extended
from `tools/verify_reproducibility.py`. Feature flag, default off.
*Rationale for putting this first: the mechanisms that keep the boundary honest are cheapest to add
before there is anything to isolate, and they are what makes every later phase safe.*

**Phase 3 — Schema + infrastructure.**
pgvector extension; the `AM-27`-authorized tables **for Domain B only**, in a separate schema, one
Alembic head; the assist DB role with **zero INSERT/UPDATE on the ten `AM-25` r2 tables**, asserted by a
test; MinIO service + `S3CompatibleStorage` behind the existing Protocol; preflight checks for all of it.
*Existing 21 schema-invariant tests must pass unmodified — that is the `AM-27` r2 evidence.*

**Phase 4 — Chunking + indexing (no model, no generation).**
`index_document_version` Celery task on its own queue, dispatched after `DocumentProcessingRun` reaches
`COMPLETED`. Clause-aware chunking derived from **committed `document_evidence` rows** — page, section,
offsets and source type carried forward, never re-derived. `tsvector` + GIN + `pg_trgm`. Chunk-provenance
tests. **Ships real value with no model at all:** exact-phrase and section-number search over uploaded
documents.

**Phase 5 — Embeddings + hybrid retrieval + authorization.**
Local embedding model (`AM-26` r5: fetched once, checksummed, stored locally, never fetched at runtime).
pgvector index with iterative scans enabled. RRF fusion, then a local cross-encoder reranker.
**Authorization pre-filtered inside the query**, plus the indistinguishability tests (`AM-25` r6/r7,
`AM-29` r4). Ship `GET /document-versions/{id}/similar-clauses` — retrieval only, no generation.
*Depends on [C1] only for the model-hosting question; a local embedding model is already locked, so this
phase proceeds regardless.*

**Phase 6 — Guardrails, before generation exists.**
`legalmind/assist/guardrails/` as its own module with its own tests, importing **neither prompt nor model
code** (`AM-28` r2). Citation verification; no-retrieval-no-call; the three `AM-29` outcome states
recorded separately; identical refusal wording regardless of cause; the `AM-25` r3 gap-report path; the
r4 routing rule that sends "does this meet our standard?" to the evaluator.
*Deliberately before Phase 7: the guardrail is testable against fixtures without a model, and building it
first means generation can never ship ungated.*

**Phase 7 — Generation behind one interface.**
`AM-26` r1's single interface; model identity as configuration. Model selection **by measurement**, from
the smallest candidate upward (r2), against the Tier-2 evaluation set (r3 — *correct refusal is half the
bar*). Version pinned and recorded per answer (r4). Redaction on the payload path, reusing
`observability/redaction.py`. Audit event per call carrying a **payload hash, never the payload**.
**BLOCKED on [C1].**

**Phase 8 — Conversation API + unified workspace.**
The five new endpoints; then the workspace route composed from existing components — document pane,
verdict cards from the deterministic engine, chat panel. Existing routes stay. `AM-29` answer state
rendered; **no confidence figure** ([C15]).

**Phase 9 — Domain A and Domain C.** Gated on [C3] and [C4]. Reuses the entire Phase 4–6 pipeline.

**Phase 10 — Security hardening + Tier-2 gate in CI.**
Network segmentation, `ufw` deny-by-default, egress verification script asserting the expected egress
count (**zero** under [C1] path (a)), Nginx + TLS, secrets, Trivy/`pip-audit`/`npm audit`, OpenVAS/ZAP.
Tier-2 gate wired: a change to retrieval, chunking, prompt or model that worsens faithfulness or the
wrongly-answered rate **does not ship** (`AM-28`).

**Departures from the target's own ordering, and why:** guardrails move **before** generation (they are
testable without a model, and this makes ungated generation impossible rather than merely discouraged);
isolation scaffolding moves to the **front** (cheapest before there is anything to isolate, and it makes
every later phase safe); Domain A/C seeding moves to the **back** (unauthorized tables, plus Domain A is
already built as configuration); and Phase 4 is carved out as a **model-free shippable increment**, which
the two-day plan does not have.

---

## 16. Explicit "Do Not Rebuild" List

These are correct, tested, and load-bearing. Reuse them.

| # | Component | Why it stands |
|---|---|---|
| 1 | **The 29-table locked schema and its 4 migrations** | `AM-27` r2 forbids altering them and makes the unmodified invariant tests the proof the locked model survived |
| 2 | **Both deterministic evaluators** (`NUMERIC_COMPARISON`, `PRESENCE`) | `AM-25` r1 keeps them the sole producer of every legal outcome. Replacing them with an LLM is the largest available unnecessary rewrite ([C2]) |
| 3 | **The document parser** (PyMuPDF + python-docx + OCR) | Already delivers page numbers, offsets, section numbers, OCR flagging, tables, original-text preservation and never-invent-text. `AM-26` keeps it primary ([C9]) |
| 4 | **`document_evidence` and the ingestion pipeline** | The chunker's input. Rebuilding it would create the second source of truth `AM-27` r4 forbids |
| 5 | **The mapping engine** | Deterministic, explained per signal. Hybrid retrieval is not a substitute — it never sets a Mapping State. Its alias/keyword groups are a good *read-only* seed for query expansion |
| 6 | **The `Guard` authorization pattern** | Visibility → permission → operation → DB, 60+ tests, byte-identical 404s. `AM-25` r6/r7 extends it to retrieval; it does not replace it |
| 7 | **The append-only audit trail** | DB-trigger-enforced, records identifiers not content. `AM-27`: new event types, **no schema change** — a separate `audit_log` table would fragment the trail |
| 8 | **`observability/redaction.py`** | The most valuable pre-built asset for any model path: it makes emitting credentials, clause text or legal position structurally impossible, with no bypass |
| 9 | **The 32 ratified Company Standards** | This **is** Domain A, already derived from real source documents, clause-cited, versioned, not hardcoded. Vision §3b is satisfied — do not re-derive it ([C11]) |
| 10 | **The golden corpus and its harness** | Tier 1, normative, unchanged by AB-3 (`AM-28` r3) |
| 11 | **All 726 tests** | None encodes an obsolete assumption. `AM-25` r1 keeps the behavior they assert authoritative |
| 12 | **The `StorageBackend` Protocol** | Correct seam; MinIO is an additive implementation, not a refactor |
| 13 | **Celery worker + queue infrastructure** | `AM-26`: *reused, not replaced*. Add a task and a queue |
| 14 | **The api/worker same-image topology** | Locked 55.1 and `AM-26`'s unchanged modular monolith ([C5]) |
| 15 | **The 39 existing API endpoints** | Not one contract needs changing; all assist work is additive |
| 16 | **The frontend design system, primitives, API client and session handling** | The workspace is a new route *composed of* these, not a redesign |
| 17 | **The verification tools** | `verify_reproducibility` becomes the corpus-parity harness — the mechanical proof that `AM-25` r1/r2 hold |
| 18 | **The zero-tolerance Legal Rule wiring** | Owner-approved 2026-08-20. No threshold, no tolerance band, by policy. The assist lane never touches it |

---

## 17. Decisions required before implementation

Nothing below is decided in this document, and none of it may be inferred.

### Owner / product

1. **[C1] Hosted Gemini Flash, or the locked local self-hosted model?** Blocks Phase 7 only. If hosted:
   `AM-25` r9 and `AM-26` must be amended by name, and the tech doc's own hard gate — Gemini enterprise
   zero-retention terms **confirmed in writing** — must clear first.
2. **[C2] Confirm the deterministic evaluator remains the verdict producer**, with the assist lane doing
   document Q&A, statute research and explanation rephrasing. This audit recommends yes.
3. **[C3] Domain A and Domain C tables** — extend `AM-27`, or ingest both as Document Versions?
4. **[C15] Confirm "confidence" becomes the `AM-29` answer state** plus labeled retrieval scores.
5. **[C14] Is multi-tenancy a real V1 requirement?** Recommend deferring; do not build against an
   imagined schema.
6. **[Ambiguity 7] Domain-routing behavior** — classifier, rule set, or search-all-and-fuse?

### Legal / source material (rule 21 — request, never manufacture)

7. **NI Act and Evidence Act** — absent, and the vision's headline worked example cites Section 138 NI Act.
8. **The curated judgment list** — *"Legal team supplies a specific list"*; it does not exist.
9. **The Tier-2 evaluation set's real Q&A material**, including unanswerable questions (`AM-28` r3).
10. **[C4] India Code provenance** for the four supplied statutes, if §9.2 is a hard rule.
11. **The second document tranche** — still outstanding, still required, still not substitutable.

### Security

12. **The full per-service DB grant matrix.** `AM-25` r2 fixes the assist role exactly; the rest is
    named in principle only.
13. **Retention/deletion policy** — `AM-27` r5 requires hard-deleting chunks with a document, and **no
    hard-delete path for a Contract was found**. Cascade behavior cannot be designed without it.
14. **Prompt/response caching** — used at all? If so, a cached answer containing contract text needs the
    same access control as its source document.

### Architecture (rule 19 — new technology needs approval)

15. **pgvector extension** — locked by `AM-26`; confirm the deployment gate.
16. **Local inference runtime and GPU allocation** — `AM-26` adds both *"where required by the selected
    model"*. Follows [C1]; see [C7].
17. **[C12] The RIAAS integration contract**, plus approval for a JWT/JWKS library.
18. **[C5] Confirm the modular monolith stands** and that isolation is realized at the network + DB-role
    layer rather than by decomposition.
19. **Embedding + reranking model candidates** for `AM-26` r2's smallest-upward selection.

---

**Nothing in this document authorizes writing code, adding a dependency, modifying the database, or
touching the frontend.** It reopens no locked decision and resolves no contradiction. Per rule 5, the
contradictions in §12 are reported for an owner ruling; per rule 6, any change to `AM-25`, `AM-26` or
`AM-27` must be named explicitly and approved before it is made.

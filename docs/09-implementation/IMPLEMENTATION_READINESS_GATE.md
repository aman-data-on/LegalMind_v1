# Implementation Readiness Gate

**Status: ✅ SPECIFICATION COMPLETE — implementation NOT yet authorized.**

Date: 2026-08-17. Master record: `all_lock.md`, **14,885 lines**. Every append verified append-only; no historical locked text has ever been modified.

Supersedes the interim [IMPLEMENTATION_READINESS_REVIEW.md](IMPLEMENTATION_READINESS_REVIEW.md).

---

# 1. Gate criteria

| Criterion | State | Evidence |
|---|---|---|
| **Internally consistent** | ✅ | C-01–C-04 reconciled (REC-01–07); all N/J-series closed; AB-1 repaired every locked requirement the schema could not represent; 5 targeted verification passes, 0 contradictions |
| **Deterministic** | ✅ | ENG-11; no LLM/RAG/embeddings in the authoritative path (AI-01); roll-up is a pure function; Tier-1 ordering recorded as convention, not law |
| **Explainable** | ✅ | `Evidence → Fact → Standard → Rule → Result` holds on every branch including absence; `TEXT_PATTERN` rejected precisely because it would produce a Result without a Fact |
| **Auditable** | ✅ | Append-only audit; decisions versioned append-only; every status transition audited; audit never substitutable by logs |
| **Reproducible** | ✅ | `evaluator_version` + `legal_rule_version_id` persisted (AM-19/20); configuration snapshots pin the rest. **Step 32's five audit questions are all answerable** |
| **Permission-controlled** | ✅ | Step 47 locked: OIDC + fallback, server-side sessions, permission catalogue, super-role boundary, object-level authorization, denial semantics |
| **Implementable** | ✅ | Every contract has a physical representation; no field lacks a home |
| **Fail-closed** | ✅ | ENG-09; six fail-closed paths with fixtures; every absent configuration value fails closed rather than defaulting |
| **Complete for V1** | ✅ | Steps 1–45D, 47, 49, 52–55 locked |

**All nine criteria met.**

---

# 2. Locked scope

```text
Steps 1–44              🔒    Steps 45B / 45C / 45D   🔒
Step 45A                🔒    Step 47  Security       🔒
REC-01 – REC-07         🔒    Step 49  API            🔒
Amendment Batch AB-1    🔒    Steps 52–55             🔒
Step 45E  Golden Corpus ⏳    64 fixtures specified
```

**V1 evaluator coverage:** `LIABILITY-001` (`NUMERIC_COMPARISON`) + the generic `PRESENCE` evaluator + configured Requirements. No additional legal-domain evaluator is required by any locked decision.

---

# 3. Schema delta introduced across the whole programme

| Table | Change | Source |
|---|---|---|
| `legal_decisions` | `evaluation_id`, `version_number`, `justification NOT NULL`, composite FK, unique | AB-1 |
| `evaluations` | `scope_key`, `scope_label`, `evaluation_kind`, `rule_outcome`, `evaluator_version`, `legal_rule_version_id` | AB-1 |
| `evaluation_evidence` | **new** — per-scope evidence, zero rows permitted | AB-1 |
| `unmatched_provisions` | **new** — REC-02 observations | AB-1 |
| `sessions` | **new** — server-side sessions, revocable | Step 47 |
| `user_identities` | **new** — OIDC + password fallback | Step 47 |
| `EVALUATOR_TYPE` | defined: `NUMERIC_COMPARISON`, `PRESENCE` | AB-1 |
| `FINDING_STATUS` | defined: `OPEN`, `DECISION_REQUIRED`, `AWAITING_CLARIFICATION`, `RESOLVED` | J-4 |

Steps 49 and 52–55 add **nothing** to the schema.

---

# 4. What remains before code can ship

| # | Item | Type | Blocks |
|---|---|---|---|
| 1 | **Representative contract set** | Data gathering — **must be supplied by the owner** (§6 rule 11); it cannot be synthesized | Corpus authoring *and* Step 35 threshold calibration — one exercise, two consumers |
| 2 | **Golden corpus authoring** — 64 specified fixtures | Implementation | Release (54.7) |
| 3 | **Step 35 mapping thresholds** | Calibration | Mapping accuracy; fail-closed defaults hold until then |
| 4 | **Retention policy** | Product/legal | Deployment (41.26 defers it) |
| 5 | **Export formats** | Product | The export feature only |
| 6 | **Requirement catalogue (N-24b)** | Legal configuration | Nothing — it is configuration, not code |
| 7 | **Deployment prerequisites** | Operations | Production (55.6 register) |

**None of items 1–7 blocks starting implementation.** Items 1–3 block the release gate; 4–7 block production.

---

# 5. Recommended implementation sequence

```text
1. Schema + migrations         locked Steps 41–42 + AB-1 + Step 47 tables
2. Auth + session + RBAC       Step 47 — earliest, because everything sits behind it
3. Domain + repositories       Steps 40, 43.24–43.26
4. Document ingestion          Step 34
5. Mapping engine              Steps 28, 35 (fail-closed defaults)
6. Evaluators                  LIABILITY-001 (45B) + PRESENCE (45D)
7. Findings/Evaluations/Decisions  AB-1 model
8. API surface                 Step 49
9. Golden corpus harness       Steps 45E, 54
10. Frontend                   Step 52
11. Observability              Step 53
12. Deployment                 Step 55
```

Steps 2 and 9 are the two that are cheapest now and most expensive to retrofit: authorization because every later layer assumes it, and the corpus harness because it is what makes every subsequent change safe.


---

# 5b. Assist-lane implementation sequence (`IMPL-02`)

**Status: 🔒 AUTHORIZED BY REFERENCE.** `IMPL-02`, Amendment Batch AB-4, 2026-08-25. Added
2026-08-25.

`IMPL-01` authorized implementation of the locked V1 specification **in the §5 sequence**. That
sequence predates AB-3 and contains no assist-lane unit, so after AB-3 the lane had locked content
and no authorized order in which to build it. `IMPL-02` closes that gap using the same mechanism
`IMPL-01` used for §5 — **authorization by reference**, so this sequence can be revised on evidence
without amending a lock.

**§6's standing constraints below do not relax.** Note especially that §6 item 1 bars LLM, RAG,
embeddings and vector search from the **authoritative analysis path** — that wording is exact and
still binding. AB-3 permitted an *assistive* lane beside that path; it did not open the path itself.
`AM-25` r1–r8, `AM-27`'s table limit, `AM-28`'s two tiers and `AM-29`'s sixth axis bind throughout.

| # | Unit | Depends on | Note |
|---|---|---|---|
| **A0** | **Boundary guards, before any assist code** | — | **Done 2026-08-25.** `test_import_boundaries.py` (22) and `test_locked_schema_columns.py` (33), plus CI job 13 gating the full suite. Cheapest before there is anything to isolate, and it is what makes `AM-25` r1/r2 and `AM-27` r2 structural rather than stated |
| **A1** | Schema + infrastructure | A0 | **Substantially done 2026-08-25** — migration `b1e7c4d20f39` creates **8 of the 9** `AM-27` tables in a separate schema, derived per test run (`<run>_assist`) so concurrent suites cannot collide as they did under `F-4`; `pg_trgm` plus a **generated** `tsvector` column on `chunks`; `test_assist_schema.py` covers r1/r3/r4/r5/r6, `AM-29` r1–r3, and the absence of a confidence column. `chunk_embeddings` deferred to A3 (its dimension is a property of an embedding model, and `AM-26` r2 has not selected one — writing `vector(768)` now would invent the number). **Preconditions, not migration steps**: pgvector **≥ 0.8.0** and the `legalmind_assist` role each need a privilege the application role deliberately lacks (`vector` is not a trusted extension; `CREATE ROLE` needs CREATEROLE), so `preflight` reports both. MinIO deferred to A10 — locked 55.6 makes the provider a deployment choice and it is not on the retrieval path |
| **A2** | Chunking + keyword index | A1 | **Done 2026-08-25.** `legalmind/assist/{chunking,store,indexing}.py`: a deterministic chunker over committed `document_evidence` (`AM-27` r4 — never re-parsed from raw text, and it carries no provenance of its own), Core-based persistence with the schema resolved at call time, and lexical search on `tsvector` + trigram ordered by `ts_rank` — **not BM25**, which needs an unauthorized extension. Indexing runs on its own `assist` queue and worker, dispatched from the upload endpoint; it **cannot fail an ingestion**, because a derived index breaking the authoritative path is the inversion `AM-25` r1 and Step 38 rule 21 forbid. Re-indexing requires an explicit instruction rather than happening on every upload, since delete-and-reinsert would cascade to `answer_citations` and silently invalidate recorded citations. **Verified end to end with no model**: phrase, quoted-phrase and section-number queries resolve; an absent term returns an honest empty result |
| **A3** | Self-hosted embeddings + hybrid retrieval + authorization | A2 | **Measured 2026-08-25; selection blocked on evaluation material.** Runtime approved under rule 19 (`onnxruntime` + `tokenizers`, 118 MB, CPU-pinned, inference-only). Four 384-dim candidates measured smallest-first per `AM-26` r2: hybrid RRF reaches R@10 1.000 vs lexical 0.917, and `arctic-embed-s` matches lexical P@1 while improving MRR. **But every vector and hybrid strategy refused 0 of 36 unanswerable probes against lexical's 34** — dense retrieval has no natural empty result. `AM-29` r3 and `AM-25` r5 therefore require a **measured similarity floor** before dense or hybrid retrieval can ship; that threshold must be calibrated against known-unanswerable questions, not chosen. `chunk_embeddings` and the dimension stay unpinned. Weight fetching lives in `tools/provision_model.py` so no module under `legalmind/` imports a network client. **Owner input outstanding**: 30–50 real questions (being supplied) |
| **A4** | **Citation enforcement and refusal states — before generation** | A3 | `AM-28` r2 requires it to be tested independently of prompt and model code and to **not import them**. See r4 below: this ordering is **locked by consequence** |
| **A5** | Network egress allow-list | A1 | `AM-30` t8, deny-by-default elsewhere, asserted by a test. **Must exist before A6**, so `AM-31`'s gate never rests on application code alone |
| **A6** | Generation behind one interface | A4, A5 | `AM-26` r1's single in-process interface — **not a service** (`AM-26` keeps the modular monolith). `AM-31`'s gate **default-closed**; `AM-30` t2–t5 payload minimization, `LEGAL-02` as an egress rule, payload-hash audit events |
| **A7** | Conversation API + unified workspace | A6 | Composed from existing frontend primitives. `AM-29` answer state rendered; **no confidence figure** (`AI-03` item 16, rule 12) |
| **A8** | Domain A and Domain C | A3 | **Blocked**: `AM-27` authorizes no corpus table (C-15), the NI Act and Evidence Act were never supplied (C-16), and there is no curated judgment list. Domain A already exists as the 32 ratified Company Standards — this unit indexes existing configuration, it does not rebuild it |
| **A9** | Tier-2 evaluation gate in CI | A4, A6 | Needs real supplied question-and-answer material (`AM-28` r3, `AM-31` m5) — requested, never authored |
| **A10** | Security hardening | A6 | Network segmentation, TLS, secrets, Trivy/`pip-audit`/`npm audit`, OpenVAS/ZAP. The **egress allow-list is not here** — it is A5, a precondition of A6 |

### The two orderings that may not be changed

`IMPL-02` r4 makes ordering revisable engineering judgment **except**:

1. **A4 before A6** — citation enforcement before generation. `AM-28` r2 forbids the guardrail
   importing prompt or model code; built after generation it will, or it needs a retrofit.
2. **A5 before A6** — the egress allow-list before the first real generation call, so `AM-31`'s
   gate is a network control and not only an application one.

### What `IMPL-02` does not authorize

Deciding anything marked `NOT YET SPECIFIED`; resolving an open conflict or open decision; adding a
table beyond `AM-27`'s nine; adding a technology or dependency beyond `AM-26` as amended by
`AM-30` — **including a provider client library, which rule 19 still governs**; or authoring any
legal content, threshold, Company Standard, Legal Rule or corpus fixture.

---

# 6. Standing constraints for implementation

These do not relax when coding begins:

1. No LLM, RAG, embeddings or vector search in the authoritative analysis path (AI-01).
2. The engine never produces a Legal Decision.
3. `RESOLVED ≠ MATCH`. `DEVIATION ≠ unacceptable`.
4. Fail closed — never guess, never silently resolve ambiguity, never discard a carve-out.
5. Evidence survives every branch; **no synthetic evidence** is ever created.
6. Server-side authorization is authoritative; UI gating is presentation only.
7. Authentication never confers Legal Decision authority.
8. Historical legal records are never rewritten.
9. Never invent a legal requirement, threshold or evaluator behavior.
10. A changed golden-corpus expectation is a specification change, not a test fix.
11. **Real legal source material is requested, never manufactured.** Where implementation or validation needs real legal documents, representative contracts, company standards, or other legal source material that the repository does not already contain, **stop and ask the owner for it before proceeding**. Do not invent legal content; do not treat an arbitrary or illustrative example as production truth. This governs items 1–3 and 6 in §4 above — the representative contract set, corpus authoring, threshold calibration, and the Requirement catalogue.

---

# 7. Gate decision

**The V1 specification is complete and internally consistent. Implementation may be authorized.**

Per [CLAUDE.md](../../CLAUDE.md), implementation requires **explicit approval** and does not follow automatically from this assessment. This document reports readiness; it does not grant it.

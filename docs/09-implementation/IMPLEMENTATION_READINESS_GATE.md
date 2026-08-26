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
| **A3** | Self-hosted embeddings + hybrid retrieval + authorization | A2 | **Done 2026-08-26.** Model selected by measurement on the owner-ratified set: `all-MiniLM-L6-v2`, smallest-that-passes (`AM-26` r2). Gate calibrated from measured distributions — a two-feature rule (cosine floor 0.50 + peak-gap 0.059, lexical hit passes) after a single global floor measured insufficient. `chunk_embeddings` migration `c4a91f6e2d87`; hybrid retrieval in SQL, scope inside the query (`AM-25` r6); evidence in `BACKEND_ARCHITECTURE.md` |
| **A4** | **Citation enforcement and refusal states — before generation** | A3 | **Done 2026-08-26.** `guardrails.py`: sentence-level citation markers verified for existence and lexical grounding; the model's own NOT FOUND honoured as `EVIDENCE_INSUFFICIENT`; sufficiency check keeps the model uncalled (`AM-29` r3). Imports no prompt or model code — asserted by test (`AM-28` r2). The identical refusal wording is a single constant (`AM-29` r4) |
| **A5** | Network egress allow-list | A1 | **Application level done**: exactly one module in `EGRESS_ALLOWED`, asserted by test; CI asserts no provider credential is present. The **network-layer** allow-list (`AM-30` t8) is a deployment control, listed in preflight and pending infra |
| **A6** | Generation behind one interface | A4, A5 | **Done 2026-08-26, gate CLOSED.** `generation.py` over stdlib urllib — no provider SDK, so rule 19's separate dependency approval is never triggered. `AM-31` enforced in code: production egress refused while the gate constant is CLOSED; released only alongside the appended record (g3) — an env var cannot open it. Payload screen re-erects LEGAL-02 as an egress rule (t3); dated-pin model id required (t7); per-call `audit_events` row with payload hash (t5) |
| **A7** | Conversation API + unified workspace | A6 | **Done 2026-08-26.** Three endpoints behind the new `assist.ask` permission (the extension AB-3's registry entry anticipated); Guard chain + byte-identical-404 on conversations; compliance-shaped questions routed to the evaluator (`AM-25` r4). Workspace Ask panel: citations with §/page, quiet refusals, retrieval scores labelled as retrieval scores |
| **A8** | Domain A and Domain C | A3 | **Blocked**: `AM-27` authorizes no corpus table (C-15), the NI Act and Evidence Act were never supplied (C-16), and there is no curated judgment list. Domain A already exists as the 32 ratified Company Standards — this unit indexes existing configuration, it does not rebuild it |
| **A9** | Tier-2 evaluation gate in CI | A4, A6 | Needs real supplied question-and-answer material (`AM-28` r3, `AM-31` m5) — requested, never authored |
| **A10** | Security hardening | A6 | **Partial, 2026-08-26.** Network segmentation, TLS and secrets were already reported by `preflight` as deployment-time properties. **Now done**: CI job 14 runs pip-audit and npm audit (both measured zero, blocking) and Trivy against both built images (CRITICAL/HIGH blocking, MEDIUM/LOW reported) — first documented build test of either Dockerfile in CI. **Deliberately not in CI**: OpenVAS/ZAP scan a running instance; orchestrating one inside this workflow is deployment-pipeline work, not an additive scan step — see `AUTO_MODE_DECISIONS.md` #143. The **egress allow-list is not here** — it is A5, a precondition of A6 |

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

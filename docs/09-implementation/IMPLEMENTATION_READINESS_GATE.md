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

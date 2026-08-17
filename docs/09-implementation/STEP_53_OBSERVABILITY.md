# Step 53 — Observability / Error Handling

**Status: 🔒 LOCKED (2026-08-17).** No locked decision changed. Schema impact: none.

Prepared 2026-08-17. Builds on locked Steps 25, 30, 32, 39, REC-07, Step 47 and Step 49.

---

# 53.1 Three record types, never conflated

| | Purpose | Store | Mutability | Audience |
|---|---|---|---|---|
| **Audit events** | What legally happened | `audit_events` (42.18) | **Append-only** (AUD-01) | Auditors, Legal |
| **Diagnostics** | Why the engine reached a result | `evaluations.result` (REC-07) | Immutable with the evaluation | Engineers, explainability |
| **Operational logs** | What the system did | Log pipeline | Retention-bound | Operators |

**Hard rules:**

* An operational log is **never** a substitute for an audit event. Losing logs must never lose legal history.
* Diagnostics are metadata and **cannot independently produce or alter a legal finding** (REC-07).
* Nothing in the log pipeline is authoritative for any legal conclusion.

---

# 53.2 Correlation

`X-Request-Id` (49.9) is the join key across all three:

```text
Request  →  X-Request-Id
             ├── operational log lines
             ├── audit_events.metadata.request_id
             └── background analysis job → Evaluations produced
```

This makes "which request produced this Finding, and who made it" answerable from data rather than reconstruction.

---

# 53.3 What must never be logged

* Credentials, `credential_hash`, session identifiers, OIDC tokens or authorization codes (S-4).
* Contract text or extracted clause content — evidence lives in the document store, not in logs.
* Internal legal position: thresholds, rule outcomes, `rule_configuration` (LEGAL-02).
* Anything that turns a failed-login record into an enumeration oracle (S-7).

Log records carry identifiers, not content.

---

# 53.4 Error handling

Two audiences, deliberately separated:

| | Contains | Goes to |
|---|---|---|
| **User-facing** | Stable `code`, safe `message`, `request_id` (49.5) | API response |
| **Operator-facing** | Stack trace, context, correlation id | Log pipeline only |

An operator-facing detail must never leak into an API response. The `request_id` is the bridge — a user can quote it and an operator can find the detail.

**Analysis failures:** locked Step 30 distinguishes `ANALYSIS_FAILED` (Review-level, the run could not complete) from a Finding of `UNABLE_TO_EVALUATE` (the engine ran and fail-closed correctly). The observability layer must not collapse them — the second is **normal, correct behavior** and must not be alerted as an error.

---

# 53.5 Signals worth collecting

| Signal | Why |
|---|---|
| Analysis pipeline stage durations | Locate bottlenecks across Step 44's layers |
| Evaluator runs by type and version | Reproducibility and rollout tracking |
| Classification distribution | A sudden shift signals a configuration or extraction regression |
| **Fail-closed rate** (`UNABLE_TO_EVALUATE`, `AMBIGUOUS`, `UNRESOLVED`) | The engine's honesty metric. A *falling* rate may mean guessing, not improvement |
| `ANALYSIS_FAILED` rate | Genuine operational failure |
| Authentication failures, permission denials | Security posture (S-5, S-7) |
| Decision throughput and age | Reviews stuck in `DECISION_REQUIRED` |

**Alert on:** `ANALYSIS_FAILED` rate, authentication-failure spikes, repeated permission denials against one object, and jobs exceeding expected duration. **Do not alert on** `UNABLE_TO_EVALUATE` — it is the system working as locked.

---

# 53.6 Retention

Audit events and legal records follow the retention policy, not log retention (41.26: no casual hard deletion of legal history). Operational logs have an independent, shorter retention. **Log expiry must never remove auditable history** — the two are separate stores for exactly this reason.

**NOT YET SPECIFIED:** the retention policy itself (locked 41.26 defers it), log aggregation technology, alert thresholds.

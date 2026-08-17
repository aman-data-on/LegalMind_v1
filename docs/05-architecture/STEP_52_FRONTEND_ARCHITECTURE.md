# Step 52 — Frontend Architecture

**Status: 🔒 LOCKED (2026-08-17).** No locked decision changed. Schema impact: none.

Prepared 2026-08-17. Builds on locked Steps 38 (38.22, 38.23), 39 (stack), 43.31, 47 and 49.

Related: [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) · [STEP_49_API_FINALIZATION.md](STEP_49_API_FINALIZATION.md) (🔒) · [../06-security/STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md) (🔒)

---

# 52.1 The three boundary rules

These are locked and restated because the frontend is where they are most easily violated.

1. **The frontend never touches the database** (38.22). All data comes from `/api/v1/`. The external reference's pattern of pages calling data-access functions directly is **prohibited** — it was rejected as C-EXT-1.
2. **The frontend never implements legal logic** (38.23). No classification, no roll-up derivation, no rule evaluation, no `requires_decision` computation. Every such value is rendered as received.
3. **Permission gating in the UI is presentation only** (47.6, 49.11). Hiding a control is a usability affordance, never a security control; the server authorizes every operation regardless.

Stack is locked by Step 39 (Next.js). No new frontend technology is introduced.

---

# 52.2 Data flow

```text
Next.js page/component
        ↓  fetch, session cookie
    /api/v1/...            ← authorization happens here (43.23)
        ↓
   FastAPI services → repositories → PostgreSQL
```

Server-side rendering may pre-fetch **through the API**, never through a repository or database client. There is no build-time or request-time data path that bypasses the API's authorization.

---

# 52.3 Permission-driven rendering

`GET /api/v1/auth/session` returns the caller's effective permission names (49.2). The frontend uses them to decide what to *show*:

* A control the user cannot invoke is not rendered.
* A section the user cannot view renders an explicit **"Access restricted"** state rather than an empty or broken view (adapted from external U-7).
* Permission arrays are refreshed with the session, never cached across sessions — authority is resolved server-side per request anyway (S-1), so a stale array can only over-hide, never over-permit.

---

# 52.4 Confidentiality rendering — LEGAL-02

Per 49.7 r5, `rule_outcome`, thresholds and `rule_configuration` are **omitted** from responses for callers without `legal_position.view`.

**The UI must render an omitted field as simply absent** — no placeholder, no "hidden", no greyed-out row, no lock icon. A visible marker would disclose that an internal legal position exists, which is exactly what LEGAL-02 prevents. The normal-user and authorized-legal views are structurally different views, not the same view with fields masked.

The same applies to `404` responses (49.5): an out-of-scope object renders identically to a non-existent one.

---

# 52.5 The Review screen — the load-bearing surface

Locked **Step 31 r16** (as amended by AM-6) requires that before deciding, Legal is shown the evidence, Requirement, Company Standard, applicable Legal Rule and Finding — **including every scoped Evaluation with its own applicable Legal Rule**.

Therefore:

* A Finding row shows its derived `classification` **and** is expandable to its Evaluations. It is never presented as a single verdict.
* Each Evaluation row shows scope, classification, rule outcome (when permitted), evidence and explanation.
* An Evaluation whose rule outcome is `APPROVAL_REQUIRED` or `UNACCEPTABLE` is visually distinct, and **a Finding cannot be resolved while any such Evaluation lacks a decision** — the "hidden carve-out" failure is structurally impossible.
* Decision controls attach to the **Evaluation**, not the Finding (AB-1, 49.7). There is no Finding-level decision control.
* Decision history is viewable per Evaluation, with the current version distinguished from superseded ones (Step 31 r20).
* `RESOLVED ≠ MATCH` must remain evident: a resolved Finding still displays its original classification (Step 22, Step 30).

---

# 52.6 Screens in V1 scope

Derived from locked product steps; no new capability invented.

| Screen | Basis |
|---|---|
| Contract list / upload | Steps 2, 34 |
| Review list | Steps 9, 30 |
| **Review detail — Findings + nested Evaluations** | Steps 8, 31; AB-1 |
| Evidence viewer with document location | Steps 32, 42.20 |
| Escalation | Steps 4, 22 |
| Legal decision (per Evaluation) | Step 31; AB-1 |
| Legal configuration admin (draft → review → publish) | Steps 21, 29 |
| Audit view | Step 25 |
| Report view / export | Step 9 |
| User & role administration | Step 23; Step 47 |

**NOT YET SPECIFIED:** visual design, component library, accessibility target, internationalisation. None is determined by a locked decision; each is an implementation-phase choice.

---

# 52.7 Client state

* No derived legal value is computed client-side — classification, roll-up, `requires_decision` and rule outcomes arrive from the API.
* Optimistic UI is **not** used for Legal Decisions. A decision is displayed only after the server confirms it, because a `409` (version collision) is a real and meaningful outcome (49.7).
* Long-running analysis is polled or streamed via the API; the Review lifecycle state (Step 30) is the single source of progress.

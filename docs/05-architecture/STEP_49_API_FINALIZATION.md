# Step 49 — API Finalization

**Status: 🔒 LOCKED (2026-08-17).** Lock record in [`all_lock.md`](../../all_lock.md) under "Step 49 — LOCK RECORD". No locked decision amended; schema impact: none.

Prepared 2026-08-17. Builds on locked Steps 38, 43 and 47, and on Amendment Batch AB-1.

Related: [API_ARCHITECTURE.md](API_ARCHITECTURE.md) · [../06-security/STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md) (🔒) · [../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) (🔒)

---

# 49.0 What is already locked

| Locked | Provides |
|---|---|
| **43.30** | `/api/v1/` from the beginning |
| **43.21** | Response envelope: `{data}`, `{data, pagination}`, `{error: {code, message}}` |
| **43.22** | HTTP status semantics |
| **43.23** | Authorization at the API/service boundary, before any domain operation |
| **43.26** | Transaction boundaries |
| **43.28** | Idempotency — retries must not create duplicate Findings, Evaluations or Decisions |
| **43.31** | What the frontend is allowed to do |
| **38.24** | API/domain boundary — **endpoint naming explicitly NOT locked** |
| **Step 47** | Session contract, permission catalogue, denial semantics, object-level authorization |
| **AB-1** | Finding → Evaluations → Decisions model |

Step 49 fills what those leave open: endpoint naming, per-endpoint permissions, error taxonomy, pagination, correlation, and the resource shapes for the AB-1 model.

---

# 49.1 Conventions

```text
Base path        /api/v1/
Resources        plural nouns, kebab-case
Identifiers      UUID
Verbs            GET (read) · POST (create) · PATCH (partial update)
                 DELETE (remove).  PUT is not used.
Timestamps       ISO-8601, UTC (41.27)
Content type     application/json
```

**No endpoint returns a resource the caller is not authorized to see** (47.6). Authorization runs before the domain operation, never after fetching (43.23).

---

# 49.2 Authentication endpoints

```text
GET    /api/v1/auth/oidc/start        → redirect to the identity provider
GET    /api/v1/auth/oidc/callback     → exchange code, establish session
POST   /api/v1/auth/login             → fallback password path, when enabled
POST   /api/v1/auth/logout            → revoke the current session
GET    /api/v1/auth/session           → current principal + effective permissions
DELETE /api/v1/auth/sessions/{id}     → revoke a session   [user.manage]
```

`GET /auth/session` returns `user_id`, display fields, and the caller's **effective permission names** — the array the frontend uses for presentation-only gating (43.31, 47.6 rule 3). It is a convenience projection; every request is still authorized server-side.

Per Step 47: identical responses for unknown account, wrong credential and disabled account (S-7); no endpoint ever returns credential material (S-4).

---

# 49.3 Resource endpoints and required permissions

Every endpoint declares exactly one required permission. **No endpoint is implicitly public.**

| Method | Path | Permission |
|---|---|---|
| GET | `/contracts` | `contract.view` |
| POST | `/contracts` | `contract.create` |
| GET | `/contracts/{id}` | `contract.view` |
| PATCH | `/contracts/{id}` | `contract.update` |
| POST | `/contracts/{id}/document-versions` | `document.upload` |
| GET | `/document-versions/{id}` | `document.view` |
| GET | `/document-versions/{id}/content` | `document.download` |
| POST | `/reviews` | `review.create` |
| GET | `/reviews` · `/reviews/{id}` | `review.view` |
| GET | `/reviews/{id}/findings` | `finding.view` |
| GET | `/findings/{id}` | `finding.view` |
| GET | `/findings/{id}/evaluations` | `evaluation.view` |
| POST | `/findings/{id}/escalate` | `review.view` |
| POST | `/evaluations/{id}/decisions` | `legal.decision` |
| GET | `/evaluations/{id}/decisions` | `finding.view` |
| GET | `/requirements` · `/requirements/{id}` | `configuration.view` |
| POST | `/requirements/{id}/versions` | `configuration.draft` |
| POST | `/configuration/publish` | `configuration.publish` |
| GET | `/reviews/{id}/report` | `report.view` |
| POST | `/reviews/{id}/export` | `export.generate` |
| GET | `/audit-events` | `audit.view` |
| GET/POST/PATCH | `/users`, `/roles` | `user.manage` / `role.manage` |

**`legal.approve_customization`** is required in addition to `legal.decision` when `decision_type = APPROVE_CUSTOMIZATION` (Step 23, 47.5).

Endpoint naming remains outside the locked boundary (38.24); the **permission mapping** is the part that matters and is normative here.

---

# 49.4 Response envelope

Extends locked 43.21 without changing it.

```json
{ "data": { ... } }

{ "data": [ ... ],
  "pagination": { "page": 1, "page_size": 25, "total": 100 } }
```

Every response carries `X-Request-Id` (49.9).

---

# 49.5 Errors and denial semantics

Locked 43.21 error shape, extended with the Step 47 denial rules.

```json
{ "error": { "code": "FINDING_NOT_FOUND",
             "message": "Finding was not found.",
             "request_id": "..." } }
```

| Status | Meaning | Source |
|---|---|---|
| **401** | No valid session | 47.7 |
| **403** | Object visible; operation permission absent | 47.7 |
| **404** | Object outside the caller's ownership/visibility scope — **existence not disclosed** | 47.7, 41.24 |
| **409** | Conflict — including decision `version_number` collision (49.7) | 43.22 |
| **422** | Business-rule rejection | 43.22 |
| **429** | Rate limit exceeded | S-5 |

**Rules:**

1. A `404` for an out-of-scope object and a `404` for a non-existent object are **byte-identical**. Any difference is an enumeration oracle.
2. Error messages never disclose internal legal position — no thresholds, rule outcomes or `rule_configuration` (LEGAL-02).
3. `code` is a stable machine-readable identifier; `message` is human-readable and carries no confidential detail.
4. Validation errors list offending fields without echoing confidential values.

---

# 49.6 Pagination, filtering, sorting

```text
?page=1&page_size=25
```

* `page_size` **clamped server-side**, maximum 100, regardless of client input. *(Adapted from external U-6.)*
* Ordering is explicit and stable — a deterministic tiebreaker on `id` so pagination cannot drop or duplicate rows.
* Filters are an allow-list per endpoint. Arbitrary field filtering is not supported.
* Collection endpoints apply the same object-level scope as their single-resource counterparts — a list never leaks an object a `GET` would 404 on.

---

# 49.7 The Finding / Evaluation / Decision surface

The part of the API that carries AB-1. **Evaluations are nested, never flat siblings** — a Finding without its Evaluations would present the derived summary as if it were authoritative.

```json
GET /api/v1/findings/{id}

{ "data": {
    "id": "...",
    "review_id": "...",
    "requirement": { "code": "LIABILITY-001", "version_id": "..." },
    "classification": "DEVIATION",
    "status": "DECISION_REQUIRED",
    "requires_decision": true,
    "evaluations": [
      { "id": "...",
        "scope_key": "AGGREGATE", "scope_label": null,
        "evaluation_kind": "PRIMARY",
        "classification": "MATCH", "rule_outcome": "NOT_APPLICABLE",
        "expected_value": {...}, "actual_value": {...},
        "evidence_refs": ["..."],
        "explanation": "...",
        "evaluator_version": "LIABILITY-EVALUATOR-v1",
        "requires_decision": false,
        "current_decision": null },
      { "id": "...",
        "scope_key": "CATEGORY", "scope_label": "confidentiality breach",
        "evaluation_kind": "EXCEPTION",
        "classification": "DEVIATION", "rule_outcome": "UNACCEPTABLE",
        "evidence_refs": ["..."],
        "requires_decision": true,
        "current_decision": null }
    ],
    "evidence": [ ... ]
} }
```

**Normative rules:**

1. `classification` on the Finding is the **derived summary**. It is never returned without `evaluations` (45D / D-1.4).
2. **No Finding-level `rule_outcome` field exists** — none is persisted (J-2). `requires_decision` is derived.
3. `evidence_refs` is always an array and **may be empty** — a `MISSING` from established absence legitimately carries zero (45D.4.10). It is never `null`.
4. `rule_outcome`, thresholds and `rule_configuration` are omitted entirely for callers without `legal_position.view` — omitted, not nulled, so absence conveys nothing (LEGAL-02).
5. No response field can express a Legal Decision produced by the engine (36.15).

## Decisions

```text
POST /api/v1/evaluations/{id}/decisions        [legal.decision]
GET  /api/v1/evaluations/{id}/decisions        → version history
```

**There is no Finding-level decision endpoint** and **no decision update endpoint.** Supersession is a create:

```json
POST /api/v1/evaluations/{id}/decisions
{ "decision_type": "ACCEPT_DEVIATION",
  "justification": "...",
  "expected_version": 1 }
```

* `justification` is mandatory (Step 31 r11, AM-15).
* The server assigns `version_number = expected_version + 1`.
* A `UNIQUE(evaluation_id, version_number)` violation surfaces as **`409`** — optimistic concurrency falls out of the constraint, with no separate ETag mechanism (N-1 Option C).
* Prior versions are never modified; `GET` returns the full chain with the highest version marked current.
* Attempting to resolve a Finding directly is rejected — resolution is derived, never asserted (D-3.6).

---

# 49.8 Idempotency

Implements locked 43.28.

* Analysis job submission accepts an `Idempotency-Key`; a repeat with the same key returns the original result rather than re-running.
* Review creation is idempotent on `(document_version_id, configuration_snapshot_id)`.
* Finding and Evaluation creation is protected by `UNIQUE(review_id, requirement_version_id)` and `UNIQUE(evaluation_id, version_number)` — retries collide rather than duplicating.
* **Decision creation is deliberately not idempotent by key**: it is versioned instead, so a duplicate submission is a `409`, not a silent no-op. A legal decision should fail loudly rather than appear to have succeeded twice.

---

# 49.9 Correlation identifiers

Every request carries or is assigned `X-Request-Id`, which is:

* echoed on every response and in every error body;
* recorded in the `metadata` of every audit event the request produces;
* propagated into background analysis jobs so a Finding traces back to the request that triggered it.

This closes the gap the external reference has no equivalent for, and gives Step 53 its observability anchor.

---

# 49.10 Rate limiting

Per S-5. Applied to authentication endpoints, analysis submission and export generation. Exceeding a limit returns **429** with no detail about the limit's shape. Thresholds are deployment configuration, not specification.

---

# 49.11 Frontend boundary

Restating locked 43.31 and 38.22/38.23 because the API is where they are enforced:

* The frontend calls the API only. **It never reaches the database.**
* It never implements evaluation, classification, roll-up or authorization logic.
* Permission arrays from `GET /auth/session` drive presentation only. Every operation is authorized server-side regardless.

---

# 49.12 Readiness

| Area | State |
|---|---|
| Conventions, versioning | ✅ |
| Authentication endpoints | ✅ |
| Per-endpoint permission mapping | ✅ |
| Response envelope | ✅ (extends 43.21) |
| Error taxonomy & denial semantics | ✅ |
| Pagination / filtering | ✅ |
| Finding/Evaluation/Decision surface | ✅ |
| Idempotency | ✅ |
| Correlation identifiers | ✅ |
| Rate limiting | ✅ control specified |
| Frontend boundary | ✅ |

**Schema impact: none.** Step 49 introduces no table and no column.

## Open, deferred to implementation

* Exact endpoint paths may be adjusted — naming is outside the locked boundary (38.24). The **permission mapping** is normative.
* Export formats (locked as NOT YET SPECIFIED).
* Rate-limit thresholds — deployment configuration.
* OpenAPI document generation.

## What remains before implementation

Step 49 is ready for review and lock. After that the specification track needs only **Step 52 (frontend), Step 53 (observability), Step 54 (testing strategy) and Step 55 (deployment)** — none of which blocks backend implementation of the evaluator, data, security or API layers.

---

# Additions recorded during implementation — NOT locked

**Status: 📁 IMPLEMENTATION RECORD, added 2026-08-26.** Nothing above this line changed
(rule 22). This section exists because 49.3's table is the locked endpoint contract and the
implementation now exposes operations that are not in it. Each is an **implementation
detail under `IMPL-01`** ("the code is not a specification") — recorded here so the gap
between the table and the running system is visible, never silently assumed. 49.0 excludes
exact endpoint naming from the lock; what is asserted below is the permission each
operation requires, and that follows 49.3's own mapping for the object it reads.

| Method | Path | Permission | Basis | Recorded |
|---|---|---|---|---|
| POST | `/conversations` | `assist.ask` | AB-3 — the registry entry authorized "assist-lane access permissions only"; the conversation API realizes `AM-27`'s `conversations`/`messages` tables | AUTO_MODE_DECISIONS #137 |
| GET | `/conversations` | `assist.ask` | 49.6 r4 applied to the lane: creator-only scope, identical to the single GET; `contract_id` the one allow-listed filter (49.6 r3) | #162 |
| GET | `/conversations/{id}` | `assist.ask` | As above; since 2026-08-26 carries per-turn **citations rebuilt from the verified rows** so a reload renders what the live answer showed (`AM-25` r5) | #163 |
| POST | `/conversations/{id}/messages` | `assist.ask` | The ask; response shape in `legalmind/api/routers/assist.py`, refusal states per `AM-29` | #137–#139 |
| GET | `/document-versions/{id}/evidence` | `document.view` | A paginated read projection of the locked Evidence model (42.6, Step 34) under the permission that already governs seeing the version; the target every `evidence_refs` entry and every citation points at | #164 |

`GET /contracts/{id}` additionally returns `document_versions: [...]` (newest first, the
`serialize_document_version` shape, `storage_key` still absent) — added 2026-08-30 so a
document-anchored workspace can reach a contract's document; nothing else listed
versions (#187).

`GET /document-versions/{id}` additionally returns `assist_index: {chunks, embedded_chunks}`
— plain counts, deliberately not a state vocabulary (`AM-29` r1 keeps the assist lane to one
axis) — so a client can tell whether the version is searchable yet (#165).

**The frozen contract.** The complete operation set, request schemas and status codes are
generated from the application into [docs/api/openapi.json](../api/openapi.json) and
drift-tested (`test_the_committed_openapi_snapshot_matches_the_app`). Where that document and
this one disagree, **this one wins** and the disagreement is a defect (rule 5).

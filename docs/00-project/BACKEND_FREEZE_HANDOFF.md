# Backend Freeze & UI/UX Handoff

**Status: 📁 DERIVED — a point-in-time report, prepared 2026-08-27 on owner instruction.**
The owner's directive: *"The project is now in a backend freeze / dependency-wait state...
VERIFY → DOCUMENT → FREEZE → PREPARE HANDOFF → WAIT FOR OWNER INPUT."*

This document asserts no build state of its own — [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
remains the only document permitted to do that. Every number below was **measured on
2026-08-27**, not remembered. Where this report and the frozen contract disagree,
[docs/api/openapi.json](../api/openapi.json) wins; where either disagrees with Step 49,
Step 49 wins.

---

## 0 · The freeze, verified

All verification re-run on 2026-08-27 from the working tree at commit `b182879`
(branch `ui-phase3-through-3.4`, clean):

| Check | Result |
|---|---|
| Backend suite | **901 passed · 1 skipped** (the skip is the `legalmind_assist` grant check — the role is a deployment precondition) |
| `ruff check` | clean |
| `mypy` | clean — 94 source files |
| Frontend typecheck | clean |
| Frontend Vitest | **62 / 62** |
| Playwright browser suite | **27 / 27** (4 setup + 23 tests, including the Ask spec) |
| OpenAPI drift (`tools/export_openapi --check`) | `docs/api/openapi.json` **matches the application** — 45 operations |
| `AM31_GATE` | **CLOSED** — untouched |

No code was changed to produce this report. The freeze is a *state*, not a change:
nothing speculative is added, no guardrail weakened, no threshold moved, no blocked
item worked around.

---

## 1 · Completed — implemented and verified

Genuinely implemented, tested, and (where the register applies) independently verified.
Unit-by-unit evidence lives in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md); this
is the summary.

* **The legal rules engine, end to end** — ingestion (PDF/DOCX incl. scanned, with page
  and position), mapping, both evaluators (`LIABILITY-001` numeric + `PRESENCE`),
  Findings/Evaluations/Decisions, review lifecycle, escalation, evidence traceability,
  fail-closed `UNABLE_TO_EVALUATE`, configuration snapshots, append-only audit.
* **The zero-tolerance Legal Rule, wired** in all 32 ratified Company Standards; any
  deviation routes to a human. Nothing is ever auto-approved.
* **Security** — server-side authn→authz on every route, byte-identical 404 for
  out-of-scope objects, confidential fields omitted (never nulled), no super-role path
  to `legal.decision`.
* **Domain B — contract search and the assist lane through the workspace** — chunking,
  lexical + calibrated vector hybrid retrieval with authorization inside the query, the
  measured refusal gate (12/13 unanswerable refused), mechanical citation guardrails,
  the conversation API with citation replay, and the workspace Ask panel with the three
  `AM-29` refusal states. The Gemini adapter is wired and **gated CLOSED**.
* **Deployment & observability scaffolding** — 14-job CI on every push, dependency +
  image scanning (both currently clean after two real catches), network-segmented
  compose (`data` internal, no route out), the 22-check preflight register, the
  reproducibility gate, and the runnable Tier-2 quality gate proven able to fail.

**Not established, stated plainly:** nothing is `VERIFIED` or `PRODUCTION-READY` in the
register's sense; normative conformance has **0 fixtures** (blocked on rule-21 source
material and the second tranche); mapping calibration (35.10) has not run.

---

## 2 · Blocked by owner decision

| Blocker | Decision required | Why engineering cannot decide it | What depends on it |
|---|---|---|---|
| **C-15** — Domain A/C have no `AM-27`-authorized table | Either amend `AM-27` to authorize tables for Company-Standard and statute chunks, or rule how the nine authorized tables may carry non-Document-Version sources without flattening the domains | `AM-27` is LOCKED ("no other table is authorized") and the owner's 2026-08-25 instruction forbids flattening the domains — any engineering choice violates one of the two authorities (rule 5/6) | All of Domain A search (approved-positions retrieval) and Domain C search (statutes/judgments); the corresponding UI panes |
| **C-10 / C-12 / C-13 / C-14 / C-16** and open `OD-*` | As registered in [CONFLICTS.md](CONFLICTS.md) | Each is an open conflict or open decision; rule 5 forbids self-resolution | C-16 blocks Domain C (see §3 — it is also a missing-input blocker); the rest block nothing today |
| **45E normative corpus** | Ratification of acceptance expectations on real material; second document tranche | Rule 21 — legal source material must be supplied, never manufactured | The 54.7 release gate; the `VERIFIED` state |
| **Export formats** (49.12) · **retention policy** (41.26) · **second-person approval mechanism** (31 r15) · the eight *Pending ratification* items | Each named in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | All locked `NOT YET SPECIFIED` or explicitly unratified | Export blocks the report-export UI flow; the rest block no current work |

## 3 · Blocked by missing input

| Missing input | Needed for | State |
|---|---|---|
| **Google's written no-training terms** (provider, tier, date) | Opening the `AM-31` gate — generated answers on real material | The gate stays CLOSED per the owner's standing 2026-08-26 instruction; only a recorded decision can open it |
| **A Gemini API key** (`LEGALMIND_GEMINI_API_KEY`, server environment only) | Live generation, and the faithfulness / citation-precision half of the Tier-2 quality gate (`AM-31` m4 forbids a synthetic substitute) | Everything up to the generated sentence works and is tested |
| **C-16** — NI Act & Evidence Act, plus India-Code provenance for the seven statutes on disk | Domain C statute search | Never supplied; never authored by us (rule 21) |
| **The curated judgment list** | Domain C | The plan assigns selection to the legal team |
| **RIAAS/OIDC connection details** + a rule-19 JWT/JWKS dependency approval | SSO | Password login works meanwhile |

## 4 · Operator-only — production actions, not engineering

From the 22-check preflight register (`legalmind.deploy.preflight`); each is `ATTEST` or
`BLOCKED` there and **remains so** — none is relabelled complete:

pgvector installation (superuser) · the `legalmind_assist` restricted DB role · the
network egress allow-list (`AM-30` t8, full destination enumeration) · TLS ·
encrypted storage · edge rate limiting · malware scanning · backup/restore ·
log aggregation & alerting stack · OpenVAS/ZAP live-instance scans (deployment
pipeline, decision #143) · the release-time reproducibility and Tier-2 quality gates
(runnable commands the pipeline must invoke).

---

## 5 · The API contract, as verified

The contract is **frozen** as [docs/api/openapi.json](../api/openapi.json) — 45
operations, OpenAPI 3.1.0, regenerated by `tools/export_openapi.py` and drift-tested so
any change is a visible diff. Verified against the running application on 2026-08-27.
Permissions are normative in `legalmind/api/permission_map.py` (locked 49.3), and a test
asserts no route is implicitly public.

**Envelope (locked 43.21 + 49.4/49.5) — three shapes and no others:**

```
{"data": {...}}
{"data": [...], "pagination": {"page", "page_size", "total"}}   // page_size ≤ 100, clamped
{"error": {"code", "message", "request_id", "fields"?}}          // fields never echo values
```

Error codes the UI must handle: `UNAUTHENTICATED` 401 · `FORBIDDEN` 403 · `NOT_FOUND`
404 (byte-identical for absent and out-of-scope — the UI must never distinguish them) ·
`VALIDATION_FAILED` / `UPLOAD_REJECTED` / `EVIDENCE_REQUIRED` 422 · `RATE_LIMITED` 429
(no Retry-After) · `INTERNAL_ERROR` 500 · 409 on optimistic-concurrency conflicts
(52.7: no optimistic UI). Confidential fields are **omitted, never null** — a UI must
key off presence, not value.

### Surface by area (method · path · permission)

**Authentication / session** — cookie session (`HttpOnly`), CSRF pair on mutations via
the Next proxy:
`POST /auth/login` (unauthenticated) · `POST /auth/logout`, `GET /auth/session`
(authenticated) · `DELETE /auth/sessions/{id}` (`user.manage`).
*Not implemented:* `GET /auth/oidc/start|callback` — recorded `NOT_IMPLEMENTED`.

**Contracts & documents:**
`GET|POST /contracts`, `GET|PATCH /contracts/{id}` (`contract.view/create/update`) ·
`POST /contracts/{id}/document-versions` (`document.upload`; document type is
**declared by the uploader**, never inferred) ·
`GET /document-versions/{id}` (`document.view`) — carries
**`assist_index: {chunks, embedded_chunks}`**, counts from which the UI derives
ready / lexical-only / not-indexed (deliberately not an enum) ·
`GET /document-versions/{id}/content` (`document.download`) — original bytes ·
`GET /document-versions/{id}/evidence` (`document.view`) — paginated Evidence rows in
reading order with page numbers and offsets: the document pane and the target of every
citation.

**Reviews & analysis:**
`GET|POST /reviews`, `GET /reviews/{id}` (`review.view/create`) ·
`POST /reviews/{id}/analyze` (`review.create` — flagged interpretation, pending
ratification) — `202` when a broker dispatches, `201` inline; Review lifecycle states
are the locked Step 30 vocabulary, incl. terminal `ANALYSIS_FAILED` (e.g. undeclared
document type) ·
`GET /reviews/{id}/findings` (`finding.view`) · `GET /reviews/{id}/report`
(`report.view`).
*Not implemented:* `POST /reviews/{id}/export` (formats NOT YET SPECIFIED).

**Findings, evaluations, decisions:**
`GET /findings/{id}` (`finding.view`) — a Finding reconstructs Evidence → Fact →
Standard → Rule → Result; **no risk score, no confidence figure exists anywhere in the
contract** ·
`GET /findings/{id}/evaluations` (`evaluation.view`) ·
`POST|DELETE /findings/{id}/escalate` (`review.view` — escalation is not approval) ·
`POST /evaluations/{id}/decisions` (`legal.decision`) ·
`GET /evaluations/{id}/decisions` (`finding.view`).
The five legal state axes (Mapping State, Classification, Rule Outcome, Legal Decision,
Lifecycle) are separate vocabularies and must stay separate in the UI —
[DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) is the reference.

**Assist lane (chat/query)** — all under `assist.ask`, creator-only scope:
`POST /conversations` · `GET /conversations` (own-only, `contract_id` filter,
paginated) · `GET /conversations/{id}` — **replays citations** rebuilt from verified
rows, field-identical to the live reply · `POST /conversations/{id}/messages` — ask.
Answer state is the sixth axis, never mixed with the legal five: `ANSWERED` ·
`NO_EVIDENCE_RETRIEVED` · `EVIDENCE_INSUFFICIENT` · `CLAIM_UNSUPPORTED`. Every refusal
renders one byte-identical sentence (`AM-29` r4): *"Information not found in the
selected document. The available material does not answer this question."* — quiet
surface, no error banner. Scores are **retrieval scores**, labelled as such; the word
"confidence" appears nowhere and must appear nowhere.

**Configuration:** `GET /requirements`, `GET /requirements/{id}`
(`configuration.view`) · `POST /requirements`, `.../versions`, `.../standard`
(`configuration.draft`) · `POST /configuration/publish` (`configuration.publish`).
Drafts never affect analysis; Reviews pin snapshots.

**Audit:** `GET /audit-events` (`audit.view`) — append-only, paginated.

**Administration:** users CRUD + role grants (`user.manage`), roles (`role.manage`).

**Liveness:** `GET /health` — unauthenticated, contentless.

---

## 6 · UI/UX readiness assessment

### Stable — design against these now

Everything in §5 that is implemented: auth/session, contracts, document versions
(metadata · content · evidence · index counts), reviews and async analysis, findings /
evaluations / decisions / escalation, report, configuration browse–draft–publish,
audit, admin, and the assist conversation API **including its response shape**. The
snapshot is drift-tested; a change is a deliberate, visible act.

### Likely to change — design, but loosely coupled

* **The generated-answer text** (`AM-31`): the response *shape* is final; what changes
  when the gate opens is only whether `ANSWERED` text or the identical refusal comes
  back. A UI built to the four answer states needs no rework.
* **Anything Domain A/C** (C-15/C-16): if search over approved positions and statutes
  is later authorized, it will likely add endpoints in the conversation/retrieval
  family. Browsing Domain A *as configuration* is already stable (`/requirements`).

### Blocked — design as placeholders only

1. **Domain A/C search panes** (C-15 + C-16).
2. **Single sign-on** (OIDC/RIAAS) — password login is the stable interim.
3. **Report export** (`POST /reviews/{id}/export`) — formats NOT YET SPECIFIED.
4. **Generated answer text** — placeholder is the refusal state, which is exactly what
   production renders today.

### The two statuses, kept separate

> **The current API surface is stable enough to begin UI/UX implementation.**

> **The overall backend/product remains partially blocked** by C-15, C-16, the Gemini
> written-terms confirmation and API key, and the operator-only Phase 9 requirements.
> "UI can start" is not "product is complete", and nothing here claims otherwise.

UI/UX work does **not** start on this readiness finding. It starts only on the owner's
explicit instruction, at which point: `ui-ux-pro-max` (with `frontend-design`, and
`dataviz` for any chart) per the standing CLAUDE.md procedure; the old design is not a
source of truth; design from the current Product Vision against the frozen contract;
reuse old frontend code only where technically useful.

### The existing frontend

**`LEGACY UI — DEFERRED`.** Preserved, untouched, still green (typecheck · 62 Vitest ·
27 Playwright items) and still exercised by CI — it remains the backend-verification
harness. No cleanup, no redesign, no migration.

---

## 7 · Handoff state

```text
LEGALMIND BACKEND STATUS — 2026-08-27

Domain A (approved positions search): BLOCKED — C-15        (browse-as-configuration: COMPLETE)
Domain B (contract search + assist):  COMPLETE              (generation gated — AM-31 CLOSED)
Domain C (statutes/judgments):        BLOCKED — C-15, C-16
Gemini:                               BLOCKED — written no-training terms + API key
Phase 9 remainder:                    OPERATOR/OWNER DEPENDENT (preflight ATTEST/BLOCKED rows)
Backend engineering in checkout:      NO UNBLOCKED MAJOR WORK

API CONTRACT: STABLE  (45 operations, frozen + drift-tested;
                       placeholders required: Domain A/C search, OIDC, export,
                       generated-answer text)

UI/UX: DEFERRED — awaiting explicit owner authorization
```

**When an owner input arrives, the corresponding thread resumes:** Google terms + key →
record the release decision, open the gate, measure the deferred quality-gate half;
statutes/provenance → Domain C (after C-15); a C-15 ruling → Domain A/C tables and
retrieval; UI/UX authorization → the design phase per §6.

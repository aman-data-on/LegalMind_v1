# LegalMind V1 — backend

Implementation of the locked LegalMind specification. **The specification is the
source of truth**: `../all_lock.md` (authoritative) and `../docs/` (organized
reference). Do not change behaviour that a locked decision fixes — see
`../CLAUDE.md`.

## Stack (locked, Step 39)

Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Celery/Redis ·
Pytest. No new technology without approval.

## Setup

```bash
python3 -m pip install -e '.[dev]'

createdb legalmind_v1_dev
createdb legalmind_v1_test

export LEGALMIND_DATABASE_URL=postgresql+psycopg2://user:pass@host/legalmind_v1_dev
export LEGALMIND_TEST_DATABASE_URL=postgresql+psycopg2://user:pass@host/legalmind_v1_test

python3 -m alembic upgrade head
python3 -m pytest
```

> The databases are named `legalmind_v1_*` deliberately — a different project on
> this machine already owns `legalmind_dev` / `legalmind_test`.

## Layout

```
legalmind/
  domain/enums.py   controlled vocabularies — every value fixed by a locked decision
  db/base.py        column conventions (42.1 design rules)
  db/models.py      the locked schema (Steps 41–42, AB-1, Step 47)
  config.py         environment configuration; secrets never in source (S-6)
  security/         authentication, authorization, guards, audit (Step 47)
  ingestion/        validation, write-once storage, parsing, evidence (Step 34)
  mapping/          provision -> Requirement mapping states (Steps 28, 35)
  evaluation/       the two locked evaluators + persistence (Steps 44, 45A-45D)
  workflow/         decisions, escalation, Review lifecycle (Steps 4, 22, 30, 31)
  api/              the HTTP surface (Steps 43, 47, 49)
alembic/            migrations. Forward-only over legal data (Step 55.4)
tests/              Tier-3 invariant tests (Step 54.5)
```

## Invariants the database enforces

Not by convention — by constraint, so no application bug, migration or manual
script can violate them:

| Invariant | Mechanism |
|---|---|
| **EV-MIN** — every Finding has ≥1 Evaluation | `DEFERRABLE INITIALLY DEFERRED` constraint trigger, checked at COMMIT |
| **Audit is append-only** (AUD-01) | `BEFORE UPDATE OR DELETE` trigger raising on `audit_events` |
| **Decisions are append-only** (Step 31 r14) | same trigger on `legal_decisions` |
| **Current decision is unambiguous** (Step 31 r20) | `UNIQUE(evaluation_id, version_number)`; current = highest version |
| **A decision resolves one Evaluation** (AM-1) | `evaluation_id NOT NULL` + composite FK `(finding_id, evaluation_id)` |
| **One Finding per Requirement per Review** (A-4.1) | `UNIQUE(review_id, requirement_version_id)` |
| **A reason is mandatory** (Step 31 r11) | `justification NOT NULL` |
| **Reproducibility** (45B.10, Step 32 q4) | `evaluator_version NOT NULL`, `legal_rule_version_id` |
| **No arbitrary NULLs** (45B.26) | `rule_outcome NOT NULL`; absence is `NOT_APPLICABLE` |
| **Zero evidence is valid for MISSING-by-absence** (45C.15, N-34) | **no** minimum-row constraint on `evaluation_evidence` |
| **Five axes never share an enum** (REC-06) | separate native PG enum types |

## Status

| Step | State |
|---|---|
| 1. Database schema and migrations | ✅ Complete — 28 tables, 16 invariant tests |
| 2. Authentication and authorization | ✅ Complete — 39 security tests (24 authorization, 15 session/audit) |
| 3. Document storage and ingestion | ✅ Complete — 20 ingestion tests |
| 4. Mapping layer | ✅ Complete — 25 mapping tests |
| 5. Evaluation engine | ✅ Complete — 78 evaluation tests |
| 6. Decision & review workflow | ✅ Complete — 28 workflow tests |
| 7. API | ✅ Complete — 38 routes, 134 API tests |
| 8. Frontend | ⏳ Next |
| 9. Golden corpus & full test harness | ⛔ Blocked — needs real legal source material |
| 10. Observability & deployment | Not started |

Total: **339 tests**, all passing.

### Security layer (Step 47)

```
legalmind/security/
  permissions.py    27-permission catalogue; LEGAL_AUTHORITY_PERMISSIONS
  resolver.py       fresh-per-request resolution, NO bypass
  sessions.py       server-side sessions, immediate revocation
  authorization.py  object-level traversal + Step 24 visibility + LEGAL-02 redaction
  guards.py         escalation guards (S-8, S-9), never-zero-authorities
  audit.py          auth/authz events into the locked audit_events table
  seed.py           idempotent catalogue/role seeding
```

**Design decision — no permission bypass.** SEC-02 permits an administrative
bypass provided it excludes `legal.*`. V1 implements **none**: every permission
is an explicit grant. With 27 permissions the convenience is negligible, and
removing the bypass eliminates the control path the external MoS reference got
wrong. `assert_no_bypass_reaches_legal_authority()` remains as defence in depth.

### Ingestion layer (Step 34)

```
legalmind/ingestion/
  storage.py     write-once object storage; SHA-256 fingerprint
  validation.py  untrusted-input validation; content sniffing, not client claims
  parsing.py     PDF (PyMuPDF) + DOCX (python-docx); clause numbering; OCR hook
  service.py     ingest -> store -> version -> processing run -> evidence
```

Storage has **no update or delete operation** — the original cannot be altered
(34.5, 34.18). Normalization touches whitespace only: it will not "correct"
`6 m0nths`, because 45C.18 permits normalizing an OCR error only when
deterministic and this layer cannot establish that.

### Mapping layer (Steps 28, 35)

```
legalmind/mapping/
  rules.py     versioned mapping configuration; weights/thresholds as data
  scoring.py   deterministic scoring with a per-signal explanation
  engine.py    Step 28 state determination: CONFIRMED/AMBIGUOUS/UNRESOLVED/NONE
  service.py   reads rules from the Review's configuration SNAPSHOT
```

**Scoring weights and thresholds are configuration, not code** — locked 35.10
requires calibration against a representative contract set, so tuning means
publishing a new `mapping_rule_versions` row, never editing Python.

**Step 35's band vocabulary is deliberately not implemented.** The band →
mapping-state mapping was deferred by the owner (B-11). The engine derives state
from locked Step 28's own definitions instead, and emits no `CANDIDATE`,
`CANDIDATE-REVIEW`, `NOT MAPPED` or `NO_CONFIDENT_MAPPING` value. A test asserts
that.

`UNRESOLVED` and `NONE` are kept distinct because the downstream consequence
differs: `NONE` + required → `MISSING`, whereas `UNRESOLVED` → `UNABLE_TO_EVALUATE`
(Step 28 r6). Collapsing them would turn uncertainty into a legal conclusion.

### Evaluation engine (Steps 45B, 45C, 45D)

```
legalmind/evaluation/
  contracts.py   locked 45B input/output shapes
  rollup.py      Tier-1/Tier-2 derivation
  rule_config.py J-5 rule_configuration; every absence fails closed
  numeric.py     NUMERIC_COMPARISON (LIABILITY-001 occupant)
  presence.py    PRESENCE — consumes mapping_state, never text
  registry.py    evaluator dispatch + evaluator versions
  workflow.py    D-3.5 requires-decision, D-3.6 resolution, J-4 status
  service.py     Finding + scoped Evaluations + evidence persistence
  corpus.py      golden-corpus runner and fixture loader
```

**No threshold, standard value or outcome is hardcoded.** Everything comes from
the Company Standard (42.8 JSONB) and Legal Rule (42.9 JSONB) in the evaluator
input — locked Step 20: "Actual Legal Rules must be configured by authorized
Legal/Admin users."

**Tier-1 ordering is an engineering determinism convention, not a legal
hierarchy** — stated in `enums.py`, `rollup.py` and the lock record.

**The PRESENCE evaluator structurally cannot read clause text**: `MappingInput`
has exactly two fields (`mapping_state`, `evidence_refs`) and the builder accepts
no text parameter. Four tests assert this, so a future change cannot quietly
reintroduce pattern matching at the evaluation layer (N-30, ENG-03).

Golden-corpus fixtures declare `provenance`: `STRUCTURAL` (algorithm only, no
legal meaning) or `NORMATIVE` (requires real contracts and real Standards). The
runner refuses a fixture that asserts only the roll-up (45E.1) and refuses an
undeclared provenance.

### Decision & review workflow (Steps 4, 22, 30, 31)

```
legalmind/workflow/
  decisions.py        record a decision against ONE Evaluation; append-only versions
  escalation.py       Finding-level escalation (Step 4: request for review, not approval)
  review_lifecycle.py locked Step 30 state machine; RESOLVED is derived, not asserted
  errors.py           409 VersionConflict, 422 InvalidTransition / SecondPersonRequired
```

`record_decision()` takes `evaluation_id` and **has no `finding_id` parameter** —
there is no Finding-level decision entry point (AB-1.1), asserted by test.
Supersession is create-only; `UNIQUE(evaluation_id, version_number)` surfaces a
concurrent write as **409**, giving optimistic concurrency with no ETag.

**Second-person approval (Step 31 r15)** is implemented as co-signature within
the append-only chain: the current decision and the one before it must share a
`decision_type` and have *different* actors. r15 permits the requirement but does
not specify the mechanism; this needs no schema change, whereas a `co_signed_by`
column would amend locked 42.17.

**Known V1 limitations (recorded, not worked around):**

* **Review ownership transfer is not implemented.** Locked 42.13 carries
  `created_by` and no `owner_id`; Step 24 r2 permits transfer but no locked rule
  requires the capability. Adding it would amend a locked table.
* **`review_assignments` is a new table**, added because Step 24 r5/r6/r16/r17
  require assignment and no locked table represents it. Additive — no locked
  table amended.
* **Escalation is a new table** (`escalations`), added because locked Steps 4/22
  and Step 24 r5 make escalation first-class but no locked table represents it.
  Additive — no locked table amended.
* **No NORMATIVE golden fixtures exist yet.** The 64 fixtures specified in
  Step 45E require real representative contracts and the organization's real
  Company Standards. A test guards against one appearing unverified.
* **OCR toolchain (OCRmyPDF + Tesseract) is not installed in this environment.**
  A PDF with no text layer therefore fails closed: `extraction_status = FAILED`,
  zero evidence, nothing invented (34.4, 34.9). Installing the locked toolchain
  is a deployment prerequisite (Step 55.2); the code path is implemented and
  labels OCR-derived content as `source_type = OCR` (34.8).

---

## API layer (Steps 43, 47, 49)

```
legalmind/api/
  app.py             factory; /api/v1 (43.30); middleware order; registered_routes()
  permission_map.py  THE normative table — 49.3 transcribed as data
  deps.py            Guard: the 43.23 authorization boundary
  envelope.py        {data} / {data,pagination} / {error} — locked 43.21
  errors.py          the 401/403/404/409/422/429 taxonomy; ONE 404 body
  serializers.py     resource projections; omission gate for LEGAL-02
  schemas.py         request bodies (Pydantic, extra="forbid")
  pagination.py      page_size clamped at 100; stable ordering
  context.py         X-Request-Id correlation (49.9); CSRF (S-3)
  ratelimit.py       S-5 / 49.10; thresholds are deployment configuration
  storage.py         injected storage backend
  routers/           auth · contracts · documents · reviews · findings ·
                     decisions · configuration · audit · admin
```

**`permission_map.py` is the normative artifact.** Locked 38.24 leaves endpoint
naming outside the locked boundary and 49.3 says the permission mapping is what
matters. A test asserts every registered route appears in the map and that no map
entry lacks a route, so 49.3's "no endpoint is implicitly public" is enforced
rather than reviewed. Only two routes are deliberately reachable without a
session: `GET /health` and `POST /api/v1/auth/login`.

**Object scope is resolved before the operation permission.** 47.7 describes a 403
as the case where "the object is visible; user lacks the operation permission", so
visibility comes first — and the service layer built in step 2 already worked that
way, so the two cannot disagree.

**There is exactly one 404 body.** `NotVisible`'s own message is discarded on the
way out, so an out-of-scope object, a non-existent object and an unknown route are
byte-identical (49.5 r1). Anything else is an enumeration oracle.

**Responses are dicts, not Pydantic response models.** 49.7 r4 requires
confidential fields to be *omitted, not nulled*; a declared response model would
reintroduce them as `null`, which still signals that a value exists (Step 52.4).
Request bodies *are* Pydantic, with `extra="forbid"`.

**Findings always nest their Evaluations** — in a list as much as in a single
resource. `serialize_finding` has no flag to omit them, so no future endpoint can
present the derived summary as if it were authoritative (49.7 r1, D-1.4).

### What `legal_position.view` gates

`LEGAL_POSITION_FIELDS` in `security/authorization.py` is the single source of
truth. 49.7 r4 names "rule_outcome, thresholds and rule_configuration"; 49.5 r2
adds that no response may disclose thresholds. Applied to the fields an Evaluation
serializes, that is `rule_outcome`, `expected_value`, `operator`, `comparison`,
`explanation`, `rule_configuration`, `legal_rule_version_id`.

`explanation` is included because it reconstructs Evidence → Fact → **Standard →
Rule** → Result and therefore *contains* the standard and the rule. Rule 12's
explainability is satisfied for the audience internal legal positions are for —
every holder of `legal_position.view` — which is exactly what LEGAL-02
permission-controls.

Deliberately **not** gated: `classification`, `actual_value`, `evaluated_facts`,
`evidence` and `requires_decision`. Those describe the counterparty's own contract
and the fact that authorized review is needed; 49.7's own worked example returns
all of them ungated.

### Locked 49.3 endpoints deliberately NOT registered

Recorded in `permission_map.NOT_IMPLEMENTED`, and reported rather than filled:

| Endpoint | Why |
|---|---|
| `GET /auth/oidc/start`, `/auth/oidc/callback` | OIDC needs a JWT/JWKS client library — a dependency requiring approval (rule 19) — plus the deployment's issuer/client configuration. Step 47's password fallback is implemented. |
| `POST /reviews/{id}/export` | 49.12 records export formats as locked **NOT YET SPECIFIED**. There is no format to emit, and the locked 49.5 taxonomy has no status for "specified later". |

### Engineering decisions worth knowing

* **Upload is a raw body plus `X-Filename`**, not multipart. Endpoint shape is
  outside the locked boundary (38.24), and this keeps a multipart parser off the
  path that handles untrusted input — 34.16 and Step 39's upload-validation item
  both argue for the smaller surface. The declared `Content-Type` is treated as a
  claim; magic bytes decide.
* **Password hashing is `hashlib.scrypt`**, not argon2 or bcrypt, because both
  would be a new dependency. The stored format is self-describing, so switching
  later is a dependency approval plus a hash migration, not a redesign.
* **The OpenAPI document is off by default** (`LEGALMIND_ENABLE_DOCS=1` to serve
  it). 49.12 leaves generation to implementation, and an unauthenticated schema
  document sits oddly beside 47.7's 404-over-403 posture.
* **Audit `before_state`/`after_state` are gated behind `legal_position.view`.**
  47.9 puts legal-workflow events in `audit_events` and 49.3 gates the endpoint on
  `audit.view` — which by Step 47's defaults belongs to Super Admin, who has no
  `legal_position.view`. Step 24 r8 says a Super Admin has no automatic access to
  Legal content, so the envelope is returned and the payload is omitted.
* **The Review advances to RESOLVED inside the decision route**, never through an
  endpoint. Step 30 r3 forbids a caller setting Review status and r16 makes the
  summary derived.
* **`POST /reviews` idempotency is scoped to the creator** as well as to
  `(document_version_id, configuration_snapshot_id)`. Two users may legitimately
  review the same document against the same snapshot, and returning one user's
  Review to the other would leak it (Step 24 r4).
* **`Review` is created in `DRAFT`.** Recorded tension, not resolved: locked 42.13
  makes `document_version_id` NOT NULL, so a Review cannot exist before its
  document is uploaded, which leaves Step 30's DRAFT and UPLOADED describing the
  same real situation. Starting at DRAFT keeps every locked transition reachable
  and invents nothing.

### Two defects found in earlier steps and fixed here

* **`assert_legal_authority_remains` counted disabled accounts.** SEC-05 exists so
  a Review requiring a decision can always be resolved; a suspended or disabled
  account cannot authenticate by any route (47.1.3), so counting its grant
  satisfied SEC-05 on paper while leaving exactly the stalled Review the rule
  prevents. Now restricted to ACTIVE users, and split into an absolute check plus
  `assert_legal_authority_preserved`, because 47.5 r6 is a rule about what a
  change may *leave behind* — a deployment that had no authority before a change
  was not left that way by it.
* **The S-8/S-9 guards compared whole permission sets.** Locked S-8 names the
  permissions it applies to — `legal.decision`, `legal.approve_customization`,
  `role.manage`, `platform.manage` — and comparing everything was not merely
  stricter but wrong: Step 23 gives Super Admin no contract access, so an ordinary
  User holds `contract.view` a Super Admin does not, and a whole-set difference
  read that as the User being "more privileged" and locked administration out
  entirely. Different is not higher; the locked list is what distinguishes them.

### API test coverage (134 tests)

| File | Covers |
|---|---|
| `test_api_contract.py` (56) | permission-map completeness · 401 on every non-public route · X-Request-Id round trip and audit correlation · byte-identical 404s · validation errors that echo no values · page_size clamping and stable pagination · CSRF · no PUT |
| `test_api_authz.py` (21) | 404-not-403 across the whole 47.6 traversal · list scope agreeing with `can_see_review` · Super Admin blocked from Reviews *and* decisions · `legal.review` ≠ `legal.decision` · `approve_customization` extra grant · authority ≠ access without assignment · byte-identical login failures · no credential material · immediate revocation · authority revoked mid-session |
| `test_api_findings.py` (12) | evaluations always nested · no Finding-level `rule_outcome` · empty-but-never-null `evidence_refs` · legal position omitted not nulled · no threshold anywhere in a normal user's payload · audit payload gating |
| `test_api_decisions.py` (18) | routes that must not exist · version chain and 409 · mandatory justification · `REQUEST_CLARIFICATION` never effective · second-person co-signature · RESOLVED derived · RESOLVED ≠ MATCH · escalation is not approval |
| `test_api_resources.py` (27) | upload/duplicate/download and magic-byte rejection · review idempotency · report with no risk field · publish failing closed · append-only configuration versions · S-8/S-9/SEC-05/S-10 over HTTP · login rate limiting |

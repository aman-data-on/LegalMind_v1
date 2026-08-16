Source: all_lock.md, Step 42 (lines 8280–9141). Canonical source: all_lock.md (Steps 40-43).

**Status: SPECIFICATION ONLY — no migrations have been implemented; implementation must not begin without explicit approval.**

This document is the target schema specification. For the domain-model rationale ("why") behind these tables, see `docs/05-architecture/DATABASE_ARCHITECTURE.md` (Steps 40–41). This file transcribes only the exact table-by-table schema and ERD from Step 42.

# Step 42 — Exact Database Schema & ERD

This step converts the locked domain model from Step 41 into an **implementation-ready PostgreSQL schema design**.

I am deliberately keeping this at the **schema-contract level** for now: exact tables, columns, relationships, constraints, and indexes. We should not write migrations until this is locked.

---

## 42.1 Design rules — Status: LOCKED

Before the tables, these rules are locked into the schema design:

1. PostgreSQL is the system of record.
2. Domain IDs use UUID.
3. Timestamps are stored in UTC.
4. Foreign keys enforce important relationships.
5. Original documents are immutable.
6. Historical configuration is never silently replaced.
7. Findings are reproducible from persisted evidence + versioned rules.
8. Audit events are append-only.
9. Ownership is represented in the data model.
10. JSON/JSONB is used for genuinely variable configuration, not to hide core relationships.

---

## 42.2 Identity & Access

### `users`

```text
users
-----
id                UUID PK
email             VARCHAR UNIQUE NOT NULL
name              VARCHAR NOT NULL
status            USER_STATUS NOT NULL
created_at        TIMESTAMPTZ NOT NULL
updated_at        TIMESTAMPTZ NOT NULL
```

Recommended statuses:

```text
ACTIVE
SUSPENDED
DISABLED
```

### `roles`

```text
roles
-----
id                UUID PK
code              VARCHAR UNIQUE NOT NULL
name              VARCHAR NOT NULL
```

Initial roles:

```text
USER
ADMIN
SUPER_ADMIN
```

### `user_roles`

```text
user_roles
----------
user_id           UUID FK → users.id
role_id           UUID FK → roles.id

PRIMARY KEY(user_id, role_id)
```

This keeps role assignment flexible.

---

## 42.3 Contracts

### `contracts`

```text
contracts
---------
id                UUID PK
owner_id          UUID FK → users.id
name              VARCHAR NOT NULL
contract_type     VARCHAR
status            CONTRACT_STATUS NOT NULL
created_at        TIMESTAMPTZ NOT NULL
updated_at        TIMESTAMPTZ NOT NULL
```

Indexes:

```text
INDEX(owner_id)
INDEX(status)
INDEX(created_at)
```

---

## 42.4 Document Versions

### `document_versions`

```text
document_versions
-----------------
id                    UUID PK
contract_id           UUID FK → contracts.id
version_number        INTEGER NOT NULL
original_filename     VARCHAR NOT NULL
mime_type             VARCHAR NOT NULL
file_size_bytes       BIGINT NOT NULL
file_hash             VARCHAR NOT NULL
storage_key            VARCHAR NOT NULL
processing_status     PROCESSING_STATUS NOT NULL
extraction_status     EXTRACTION_STATUS
uploaded_by           UUID FK → users.id
created_at            TIMESTAMPTZ NOT NULL
metadata              JSONB
```

Constraint:

```text
UNIQUE(contract_id, version_number)
```

Indexes:

```text
INDEX(contract_id)
INDEX(file_hash)
INDEX(uploaded_by)
INDEX(processing_status)
```

### Important

`file_hash` is indexed for duplicate detection.

It should **not** be globally unique because the same source file may legitimately appear in multiple contracts/workspaces.

---

## 42.5 Document Processing

### `document_processing_runs`

```text
document_processing_runs
------------------------
id                    UUID PK
document_version_id   UUID FK → document_versions.id
run_type              PROCESSING_RUN_TYPE NOT NULL
status                PROCESSING_RUN_STATUS NOT NULL
processor_version     VARCHAR
started_at            TIMESTAMPTZ
completed_at          TIMESTAMPTZ
error_code            VARCHAR
error_message         TEXT
created_at            TIMESTAMPTZ NOT NULL
metadata              JSONB
```

Indexes:

```text
INDEX(document_version_id)
INDEX(status)
INDEX(created_at)
```

This lets us preserve:

```text
Attempt 1 → FAILED
Attempt 2 → COMPLETED
```

instead of overwriting processing history.

---

## 42.6 Evidence

### `document_evidence`

```text
document_evidence
-----------------
id                    UUID PK
document_version_id   UUID FK → document_versions.id
processing_run_id     UUID FK → document_processing_runs.id
page_number           INTEGER
section_number        VARCHAR
section_title         TEXT
content               TEXT NOT NULL
source_type            EVIDENCE_SOURCE_TYPE NOT NULL
start_offset          BIGINT
end_offset            BIGINT
created_at            TIMESTAMPTZ NOT NULL
metadata              JSONB
```

Indexes:

```text
INDEX(document_version_id)
INDEX(processing_run_id)
INDEX(document_version_id, page_number)
```

Possible `source_type`:

```text
NATIVE_TEXT
OCR
TABLE
OTHER
```

---

## 42.7 Legal Configuration

This is deliberately versioned.

### `requirements`

```text
requirements
------------
id                UUID PK
code              VARCHAR UNIQUE NOT NULL
status            CONFIG_STATUS NOT NULL
created_at        TIMESTAMPTZ NOT NULL
updated_at        TIMESTAMPTZ NOT NULL
```

Example:

```text
LIABILITY-001
TERMINATION-001
GOVERNING-LAW-001
```

### `requirement_versions`

```text
requirement_versions
--------------------
id                    UUID PK
requirement_id        UUID FK → requirements.id
version_number        INTEGER NOT NULL
name                  VARCHAR NOT NULL
description           TEXT
evaluator_type        EVALUATOR_TYPE NOT NULL
created_by            UUID FK → users.id
created_at            TIMESTAMPTZ NOT NULL
```

Constraint:

```text
UNIQUE(requirement_id, version_number)
```

---

## 42.8 Company Standards

### `company_standard_versions`

```text
company_standard_versions
-------------------------
id                    UUID PK
requirement_version_id UUID FK → requirement_versions.id
version_number        INTEGER NOT NULL
configuration         JSONB NOT NULL
created_by             UUID FK → users.id
created_at             TIMESTAMPTZ NOT NULL
```

Constraint:

```text
UNIQUE(requirement_version_id, version_number)
```

The JSONB contains evaluator-specific values.

Example:

```text
{
  "unit": "months",
  "preferred": 6
}
```

But core relationships remain relational.

---

## 42.9 Legal Rules

### `legal_rule_versions`

```text
legal_rule_versions
-------------------
id                    UUID PK
requirement_version_id UUID FK → requirement_versions.id
version_number        INTEGER NOT NULL
rule_type             RULE_TYPE NOT NULL
configuration         JSONB NOT NULL
created_by             UUID FK → users.id
created_at             TIMESTAMPTZ NOT NULL
```

Constraint:

```text
UNIQUE(requirement_version_id, version_number)
```

Example:

```text
{
  "acceptable_max": 12,
  "approval_required_above": 12
}
```

---

## 42.10 Mapping Rules

### `mapping_rule_versions`

```text
mapping_rule_versions
---------------------
id                    UUID PK
requirement_version_id UUID FK → requirement_versions.id
version_number        INTEGER NOT NULL
rules                 JSONB NOT NULL
created_by             UUID FK → users.id
created_at             TIMESTAMPTZ NOT NULL
```

The rules may contain:

```text
positive patterns
negative patterns
section hints
terminology
priority
```

---

## 42.11 Evaluation Rules

### `evaluation_rule_versions`

```text
evaluation_rule_versions
------------------------
id                    UUID PK
requirement_version_id UUID FK → requirement_versions.id
version_number        INTEGER NOT NULL
evaluator_type        EVALUATOR_TYPE NOT NULL
rules                 JSONB NOT NULL
created_by             UUID FK → users.id
created_at             TIMESTAMPTZ NOT NULL
```

This maintains the critical separation:

```text
Mapping Rules ≠ Evaluation Rules
```

---

## 42.12 Configuration Snapshot

### `configuration_snapshots`

```text
configuration_snapshots
-----------------------
id                    UUID PK
snapshot_hash         VARCHAR UNIQUE NOT NULL
created_by            UUID FK → users.id
created_at            TIMESTAMPTZ NOT NULL
```

### `configuration_snapshot_items`

```text
configuration_snapshot_items
----------------------------
snapshot_id                  UUID FK
requirement_version_id      UUID FK
company_standard_version_id UUID FK
legal_rule_version_id       UUID FK
mapping_rule_version_id     UUID FK
evaluation_rule_version_id  UUID FK

PRIMARY KEY(
    snapshot_id,
    requirement_version_id
)
```

This is what lets a Review preserve the exact configuration context.

---

## 42.13 Reviews

### `reviews`

```text
reviews
-------
id                    UUID PK
contract_id           UUID FK → contracts.id
document_version_id   UUID FK → document_versions.id
configuration_snapshot_id UUID FK → configuration_snapshots.id
status                REVIEW_STATUS NOT NULL
created_by            UUID FK → users.id
created_at            TIMESTAMPTZ NOT NULL
started_at            TIMESTAMPTZ
completed_at          TIMESTAMPTZ
```

Indexes:

```text
INDEX(contract_id)
INDEX(document_version_id)
INDEX(created_by)
INDEX(status)
INDEX(created_at)
```

---

## 42.14 Findings

### `findings`

```text
findings
--------
id                    UUID PK
review_id             UUID FK → reviews.id
requirement_version_id UUID FK → requirement_versions.id
classification        FINDING_CLASSIFICATION NOT NULL
status                FINDING_STATUS NOT NULL
created_at            TIMESTAMPTZ NOT NULL
updated_at            TIMESTAMPTZ NOT NULL
```

Classifications:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

---

## 42.15 Evaluations

### `evaluations`

```text
evaluations
-----------
id                    UUID PK
finding_id            UUID FK → findings.id
evaluator_type        EVALUATOR_TYPE NOT NULL
expected_value        JSONB
actual_value          JSONB
operator              VARCHAR
result                JSONB NOT NULL
rule_version_id       UUID FK → evaluation_rule_versions.id
created_at            TIMESTAMPTZ NOT NULL
```

Why JSONB here?

Because evaluator inputs differ.

A numeric evaluator might have:

```text
expected = 6
actual = 12
```

while an allowed-value evaluator might have:

```text
expected = ["India"]
actual = "Singapore"
```

The **evaluation relationship itself remains relational**.

---

## 42.16 Finding ↔ Evidence

### `finding_evidence`

```text
finding_evidence
----------------
finding_id          UUID FK → findings.id
evidence_id         UUID FK → document_evidence.id
relationship_type   EVIDENCE_RELATIONSHIP_TYPE NOT NULL

PRIMARY KEY(finding_id, evidence_id)
```

Possible relationship types:

```text
PRIMARY
SUPPORTING
CONFLICTING
```

This supports both:

```text
Finding → multiple Evidence
```

and:

```text
Evidence → multiple Findings
```

---

## 42.17 Legal Decisions

### `legal_decisions`

```text
legal_decisions
---------------
id                UUID PK
finding_id        UUID FK → findings.id
decision_type     DECISION_TYPE NOT NULL
decision_text     TEXT
decided_by        UUID FK → users.id
created_at        TIMESTAMPTZ NOT NULL
```

Indexes:

```text
INDEX(finding_id)
INDEX(decided_by)
INDEX(created_at)
```

The exact decision enum should be finalized with the Legal Decision workflow.

---

## 42.18 Audit Events

### `audit_events`

```text
audit_events
------------
id                UUID PK
actor_id          UUID FK → users.id
action            VARCHAR NOT NULL
entity_type       VARCHAR NOT NULL
entity_id         UUID NOT NULL
timestamp         TIMESTAMPTZ NOT NULL
before_state      JSONB
after_state       JSONB
metadata          JSONB
```

Indexes:

```text
INDEX(actor_id)
INDEX(entity_type, entity_id)
INDEX(timestamp)
```

Audit records are **append-only**.

---

## 42.19 ERD

The complete conceptual relationship is:

```text
                         ┌─────────────┐
                         │    USERS    │
                         └──────┬──────┘
                                │
                         ┌──────┴──────┐
                         │             │
                         ↓             ↓
                    USER_ROLES      CONTRACTS
                                      │
                                      ↓
                              DOCUMENT_VERSIONS
                                      │
                         ┌────────────┼────────────┐
                         ↓            ↓            ↓
               PROCESSING_RUNS    REVIEWS      EVIDENCE
                                      │            │
                                      │            │
                                      ↓            │
                          CONFIGURATION_SNAPSHOT   │
                                      │            │
                    ┌─────────────────┼────────────┘
                    ↓
              REQUIREMENT_VERSION
                    │
             ┌──────┼───────┬───────────┐
             ↓      ↓       ↓           ↓
          STANDARD RULES  MAPPING    EVALUATION
             │      │       RULES       RULES
             └──────┴───────┴───────────┘
                    │
                    ↓
                 FINDINGS
                    │
             ┌──────┼───────────┐
             ↓      ↓           ↓
        EVALUATIONS EVIDENCE  DECISIONS
                         \
                          \
                       AUDIT_EVENTS
```

---

## 42.20 The critical traceability path

A Finding must be traceable like this:

```text
Finding
   ↓
Review
   ↓
Document Version
   ↓
Contract
```

and simultaneously:

```text
Finding
   ↓
Evidence
   ↓
Document Version
   ↓
Page / Section
```

and:

```text
Finding
   ↓
Requirement Version
   ↓
Company Standard Version
   ↓
Legal Rule Version
```

and:

```text
Finding
   ↓
Evaluation
   ↓
Evaluation Rule Version
```

and finally:

```text
Finding
   ↓
Legal Decision
   ↓
Authorized User
```

with audit events recording the important state changes.

---

## 42.21 Important integrity constraints

There are several relationships that require more than simple foreign keys.

### Review consistency

A Review's:

```text
contract_id
document_version_id
```

must correspond to the same Contract.

### Configuration consistency

The configuration snapshot must contain compatible versions of:

```text
Requirement
Standard
Legal Rule
Mapping Rule
Evaluation Rule
```

for the same Requirement.

### Finding consistency

A Finding's Requirement Version must belong to the configuration context used by its Review.

### Evidence consistency

Finding Evidence must belong to the Document Version analyzed by that Review.

These should be enforced through **database constraints where practical and domain-service validation where cross-table constraints become too complex**.

---

## 42.22 Important decision: no database-level "magic" — Status: LOCKED

We should not put complicated legal evaluation logic into PostgreSQL triggers.

For example, don't make a trigger decide:

```text
12 months → DEVIATION
```

That belongs in the Python Evaluation Engine.

Database responsibilities:

```text
Integrity
Relationships
Constraints
Persistence
Transactions
```

Application/domain responsibilities:

```text
Legal rules
Mapping
Evaluation
Workflow
Authorization decisions
```

This keeps the architecture understandable and testable.

---

## 42.23 Step 42 proposed lock — Status: LOCKED

I recommend locking the following:

1. The table groups defined above form the V1 relational schema foundation.
2. All primary domain identifiers use UUID.
3. `users`, `roles`, and `user_roles` implement identity and role assignment.
4. `contracts` represent logical agreements.
5. `document_versions` represent immutable versions of those agreements.
6. Processing attempts are stored independently in `document_processing_runs`.
7. Extracted contract evidence is persisted in `document_evidence`.
8. Requirements and all legal configuration components are versioned.
9. Configuration Snapshots capture the exact configuration used by a Review.
10. Reviews reference both the analyzed Document Version and Configuration Snapshot.
11. Findings reference Requirement Versions.
12. Evaluations are persisted separately from Findings.
13. Finding/Evidence is many-to-many.
14. Legal Decisions are separate from Findings.
15. Audit Events are append-only.
16. Ownership is represented by relational references.
17. Foreign keys enforce core referential integrity.
18. Appropriate indexes support ownership, review, evidence, findings, decisions, and audit queries.
19. Original documents are immutable.
20. JSONB is allowed for evaluator-specific/configuration-specific variable data, but core relationships remain relational.
21. Legal evaluation logic remains in the application/domain layer, not PostgreSQL triggers.
22. The schema must support complete historical reconstruction of any Finding.

### Status

```text
Steps 1–41  🔒 LOCKED

Step 42      ⏳ REVIEW
             Exact Database Schema & ERD
```

**I recommend one serious review before locking Step 42.** Once locked, the next step can be **Step 43 — API Contract & Backend Module Structure**, where we define how the frontend, backend services, analysis engine, workers, database, and authorization layer communicate.

🔒 **Step 42 — Exact Database Schema & ERD: LOCKED**

I'll treat the schema above as the baseline and **not casually change it later**. If implementation reveals a genuine contradiction, we should explicitly reopen the relevant decision rather than silently modifying it.

---

For the domain-model rationale behind this schema (Steps 40–41), see `docs/05-architecture/DATABASE_ARCHITECTURE.md`. For the API modules that operate against this schema (Step 43), see `docs/05-architecture/API_ARCHITECTURE.md` and `docs/09-implementation/API_CONTRACT.md`.

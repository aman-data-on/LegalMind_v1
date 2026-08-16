Source: all_lock.md, Steps 40–41 (lines 6801–8279). Canonical source: all_lock.md (Steps 40-43).

# Step 40 — Database & Domain Model

Now we need to define **exactly what LegalMind stores and how everything is related**.

This is a critical step because almost every later feature depends on this model.

The proposed core relationship is:

```text
User
 │
 ├── Contracts
 │      │
 │      └── Document Versions
 │
 └── Reviews
         │
         ├── Document Version
         │
         ├── Configuration Snapshot
         │
         ├── Findings
         │      │
         │      └── Evidence
         │
         └── Legal Decisions
```

Separately:

```text
Legal Configuration
 │
 ├── Requirements
 │
 ├── Company Standards
 │
 ├── Legal Rules
 │
 ├── Mapping Rules
 │
 └── Evaluation Rules
```

---

## 40.1 User

```text
User
├── id
├── name
├── email
├── role
├── status
├── createdAt
└── updatedAt
```

Roles remain:

```text
USER
ADMIN
SUPER_ADMIN
```

---

## 40.2 Contract

A Contract represents the logical agreement.

```text
Contract
├── id
├── name
├── ownerId
├── contractType
├── status
├── createdAt
└── updatedAt
```

Important distinction:

> **Contract ≠ Document Version**

A contract can have multiple document versions.

---

## 40.3 Document Version

```text
Contract
   ↓
Document Version
```

Example:

```text
MSA
 ├── v1 — uploaded 1 Aug
 ├── v2 — uploaded 5 Aug
 └── v3 — uploaded 10 Aug
```

Each version stores:

```text
DocumentVersion
├── id
├── contractId
├── versionNumber
├── filename
├── mimeType
├── fileHash
├── storageKey
├── processingStatus
├── extractionStatus
├── uploadedBy
├── createdAt
└── metadata
```

The original file is immutable.

---

## 40.4 Review

A Review represents one specific analysis of one specific Document Version.

```text
Review
├── id
├── contractId
├── documentVersionId
├── configurationSnapshotId
├── status
├── createdBy
├── createdAt
├── completedAt
└── metadata
```

This gives us:

```text
Contract
   ↓
Document Version v3
   ↓
Review R-104
```

---

## 40.5 Requirement

A Requirement represents a legal requirement that LegalMind evaluates.

Example:

```text
LIABILITY-001
TERMINATION-001
GOVERNING-LAW-001
```

Conceptually:

```text
Requirement
├── id
├── code
├── name
├── description
├── evaluatorType
├── status
└── version
```

Requirement configuration must be versioned.

---

## 40.6 Company Standard

A Requirement can have a Company Standard.

Example:

```text
Requirement:
LIABILITY-001

Company Standard:
Maximum liability = 6 months
```

This should not simply be a free-text field.

It needs structured configuration so deterministic evaluators can use it.

---

## 40.7 Legal Rule

The Legal Rule defines what happens when the Customer provision differs.

Example:

```text
Preferred:
6 months

Acceptable:
≤12 months

Approval Required:
>12 months

Unacceptable:
Unlimited
```

The important relationship is:

```text
Requirement
   ├── Company Standard
   └── Legal Rule
```

They are related but **not the same thing**.

---

## 40.8 Configuration Version

This is extremely important for historical reproducibility.

Instead of a Review saying:

> "Use the current rules."

it says:

```text
Review R-104
       ↓
Configuration Snapshot C-17
```

And C-17 references the exact versions used.

---

## 40.9 Clause / Evidence

Extracted contract content needs a persistent representation.

Conceptually:

```text
Evidence
├── id
├── documentVersionId
├── pageNumber
├── sectionNumber
├── sectionTitle
├── text
├── sourceType
├── startOffset
├── endOffset
└── metadata
```

Example:

```text
Page: 12
Section: 8.2
Text: "Aggregate liability..."
Source: OCR
```

This is what allows a Finding to point back to the exact contract evidence.

---

## 40.10 Finding

```text
Finding
├── id
├── reviewId
├── requirementId
├── classification
├── evaluationResult
├── status
├── createdAt
└── metadata
```

Classification:

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

## 40.11 Finding ↔ Evidence

Never make a Finding contain only a text explanation.

It must have evidence relationships:

```text
Finding
   ↓
Evidence
   ↓
Document Version
   ↓
Page / Section
```

For conflicts:

```text
Finding
 ├── Evidence A
 └── Evidence B
```

This supports the principle:

> **Every important legal Finding must be traceable to evidence.**

---

## 40.12 Legal Decision

A Legal Decision is separate from a Finding.

```text
Finding
   ↓
Legal Decision
```

Example:

```text
Finding:
DEVIATION

Legal Decision:
APPROVE_CUSTOMIZATION
```

The decision stores:

```text
LegalDecision
├── id
├── findingId
├── decisionType
├── decidedBy
├── justification
├── createdAt
└── metadata
```

---

## 40.13 Audit Event

```text
AuditEvent
├── id
├── actorId
├── action
├── entityType
├── entityId
├── timestamp
├── before
├── after
└── metadata
```

For legal decisions, we should preserve enough information to understand:

```text
Who
What
When
Against which object
What changed
Why
```

---

## 40.14 Critical relationship

The final model should allow us to answer this question:

> **"Why did LegalMind produce this Finding?"**

And traverse:

```text
Finding
 ↓
Evidence
 ↓
Document Version
 ↓
Contract

Finding
 ↓
Requirement
 ↓
Company Standard Version
 ↓
Legal Rule Version

Finding
 ↓
Evaluation
 ↓
Legal Decision
 ↓
Decision Maker

Everything
 ↓
Audit Trail
```

If our database cannot support this traversal cleanly, the model is wrong.

---

## 40.15 One important design rule

We should **not store the entire legal meaning of a Finding as one giant JSON blob**.

Structured fields should be relational where they matter for:

* filtering
* authorization
* reporting
* versioning
* relationships
* audit
* deterministic evaluation

JSON can be used for genuinely variable metadata, but it should not become a substitute for the domain model.

---

## 40.16 Step 40 proposed lock — Status: LOCKED

I recommend locking these principles:

1. `Contract` and `DocumentVersion` are separate entities.
2. A Review analyzes exactly one Document Version.
3. A Review records the exact configuration context used for analysis.
4. Requirements are versioned.
5. Company Standards are versioned.
6. Legal Rules are versioned.
7. Mapping and Evaluation rules are versioned.
8. Evidence is persisted and traceable to the Document Version.
9. Findings reference Requirements and Evidence.
10. Findings and Legal Decisions are separate entities.
11. Legal Decisions record the authorized decision maker and justification.
12. Audit Events are first-class persistent records.
13. The model must support historical reproducibility.
14. Legal evidence must remain traceable to page/section/source where available.
15. Structured domain data should not be hidden entirely inside arbitrary JSON.
16. Object-level ownership/authorization must be enforceable from the data model.
17. Original uploaded documents remain immutable.
18. The model must support multiple evidence items for one Finding and multiple Findings against one Evidence item.
19. The model must support conflicts involving multiple evidence items.
20. The model must allow a complete Finding → Evidence → Requirement → Standard/Rule → Decision → Audit chain.

### Current position

```text
Steps 1–39  🔒 LOCKED

Step 40      ⏳ REVIEW
             Database & Domain Model
```

**Step 40 is the foundation for the actual schema.** I would review this carefully before locking it, because once we move beyond this step, we can start defining the actual PostgreSQL tables, foreign keys, indexes, enums, versioning strategy, and API contracts.

Absolutely. **Step 41 is where we need to be especially careful**, because a weak database schema would undermine the legal traceability we have locked in.

---

# Step 41 — PostgreSQL Schema Design

The goal is **not** to write SQL yet. First we define the exact schema contract that implementation must follow.

The schema must support:

```text
Ownership
Versioning
Evidence
Deterministic analysis
Legal decisions
Auditability
Historical reproducibility
```

---

## 41.1 Core table groups

I recommend these logical groups.

### Identity & access

```text
users
roles
user_roles
```

### Contract & documents

```text
contracts
document_versions
document_processing_runs
document_evidence
```

### Legal configuration

```text
requirements
requirement_versions
company_standard_versions
legal_rule_versions
mapping_rule_versions
evaluation_rule_versions
configuration_snapshots
```

### Reviews & analysis

```text
reviews
findings
finding_evidence
evaluations
```

### Legal decisions

```text
legal_decisions
```

### Audit

```text
audit_events
```

(Note: this is the logical table-group listing from Step 41. The exact column-level table definitions are in Step 42 — see `docs/09-implementation/DATABASE_MIGRATIONS.md`.)

---

## 41.2 `users`

`id` should be a UUID.

Email should have a unique constraint.

Do **not** use email as the primary key because email addresses can change.

---

## 41.3 Roles

For V1, initial roles:

```text
USER
ADMIN
SUPER_ADMIN
```

Using a role table rather than scattering role strings throughout the application gives us room to evolve permissions.

---

## 41.4 `user_roles`

Unique constraint:

```text
(user_id, role_id)
```

This allows the authorization system to remain flexible.

---

## 41.5 `contracts`

Critical:

```text
owner_id → users.id
```

This gives us the foundation for object-level authorization.

---

## 41.6 `document_versions`

Constraints:

```text
UNIQUE(contract_id, version_number)
UNIQUE(file_hash)
```

The second constraint needs one qualification:

A duplicate file may legitimately exist in different contexts. Therefore, **global uniqueness of `file_hash` should not automatically be enforced as a business rule**.

Instead, the hash should be indexed for duplicate detection.

This is an important correction from a simplistic schema.

---

## 41.7 Document immutability

Once a Document Version is created:

```text
Original file
Metadata identifying the source
Version number
File hash
```

must not be silently replaced.

If the contract changes:

```text
Create Document Version 2
```

rather than:

```text
Modify Version 1
```

---

## 41.8 `document_processing_runs`

A document may go through processing more than once.

Therefore, don't put every processing attempt directly into `document_versions`.

Example:

```text
Document v2
   │
   ├── Extraction Run 1 → FAILED
   └── Extraction Run 2 → COMPLETED
```

This is valuable for debugging and auditability.

---

## 41.9 `document_evidence`

This stores extracted evidence.

`source_type` could include:

```text
NATIVE_TEXT
OCR
TABLE
OTHER
```

The exact enum should be finalized during implementation.

---

## 41.10 Why evidence needs a processing run

Suppose:

```text
v1
 ↓
OCR engine version 1
```

Later:

```text
v1
 ↓
OCR engine version 2
```

The extracted evidence can differ.

The database should therefore know **which processing run produced the evidence**.

That makes processing reproducible.

---

## 41.11 Requirements

We should separate the logical Requirement from its versions.

Example:

```text
LIABILITY-001
   ├── v1
   ├── v2
   └── v3
```

---

## 41.12 Company Standard

Company Standards should attach to a specific Requirement Version.

The `configuration` can contain structured evaluator inputs.

For example:

```text
{
  "unit": "months",
  "preferred": 6
}
```

But we should **not blindly put everything into JSON**.

Frequently queried/important fields should be structured relationally.

---

## 41.13 Legal Rules

Example:

```text
{
  "acceptable_max": 12,
  "approval_required_above": 12
}
```

The exact configuration schema depends on the evaluator type.

---

## 41.14 Mapping Rules

These rules can define:

```text
positive patterns
negative patterns
section hints
terminology
priority
```

Again, structured where useful, JSON where genuinely variable.

---

## 41.15 Evaluation Rules

This is separate from mapping.

That preserves the Step 35/36 distinction.

---

## 41.16 Configuration Snapshot

This is one of the most important tables.

A Review references the snapshot.

Therefore:

```text
Review
 ↓
Configuration Snapshot
 ↓
Exact versions used
```

---

## 41.17 Reviews

Important constraint:

The `document_version_id` must belong to the same `contract_id`.

This should be enforced through application logic and, where practical, database constraints/design.

---

## 41.18 Findings

Classification:

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

## 41.19 Evaluations

I recommend separating the **Finding** from the actual deterministic evaluation record.

Why?

Because the Finding says:

> **What did LegalMind conclude?**

while Evaluation says:

> **How did the deterministic evaluator reach that conclusion?**

For a numeric liability example:

```text
Expected: 6
Actual: 12
Operator: >
Result: true
Rule: ≤12 acceptable
```

This is extremely useful for auditability and debugging.

---

## 41.20 Finding ↔ Evidence

Never use a single `evidence_id` on Finding.

Use a junction table with possible relationship types:

```text
PRIMARY
SUPPORTING
CONFLICTING
```

This supports:

```text
One Finding
 ↓
Multiple Evidence items
```

and:

```text
One Evidence item
 ↓
Multiple Findings
```

---

## 41.21 Legal Decisions

Potential decision types are controlled by the workflow.

For example:

```text
ACCEPT_DEVIATION
APPROVE_CUSTOMIZATION
REQUIRE_STANDARD
REJECT
REQUEST_CLARIFICATION
```

The exact final enumeration should be locked when we define the Legal Decision workflow.

---

## 41.22 Audit Events

Audit events should be append-only.

No normal application user should be able to edit historical audit records.

---

## 41.23 Ownership

The schema must make ownership traversable.

Example:

```text
Contract
   ↓ owner_id
User
```

Then:

```text
Review
 ↓
Contract
 ↓
Owner
```

This allows server-side authorization to answer:

> Does this user own the object they are trying to access?

---

## 41.24 Critical authorization rule

Never rely on:

```text
GET /reviews/123
```

and assume that knowing `123` means access is allowed.

The backend must evaluate:

```text
Authenticated User
       ↓
Review
       ↓
Contract
       ↓
Owner / Role
       ↓
Permission
```

This protects against IDOR/object-level authorization failures.

---

## 41.25 Indexing strategy

At minimum, indexes should support:

```text
users.email

contracts.owner_id

document_versions.contract_id
document_versions.file_hash

reviews.contract_id
reviews.document_version_id
reviews.created_by

findings.review_id
findings.requirement_version_id

finding_evidence.finding_id
finding_evidence.evidence_id

legal_decisions.finding_id
legal_decisions.decided_by

audit_events.entity_type + entity_id
audit_events.actor_id
audit_events.timestamp
```

We should add indexes based on actual query patterns rather than indexing every column.

---

## 41.26 Soft delete vs hard delete

For legal records, we should **not casually hard-delete historical information**.

My recommendation:

```text
Active
Archived
```

for business entities where appropriate.

Historical Reviews, Findings, Decisions, and Audit Events should remain available according to the retention policy.

A future retention/deletion policy must explicitly define when legally permissible deletion occurs.

---

## 41.27 Timestamps

Use UTC timestamps in the database.

For example:

```text
created_at
updated_at
started_at
completed_at
decided_at
```

The UI can convert them into the user's local timezone.

---

## 41.28 UUIDs

Use UUID primary keys for externally exposed/domain entities.

Benefits:

* Avoid sequential ID exposure
* Better distributed-system compatibility later
* Safer public identifiers
* Easier future service separation

But UUIDs are **not a substitute for authorization**.

---

## 41.29 Referential integrity

Use foreign keys wherever relationships are mandatory.

For example:

```text
finding.review_id
    → reviews.id
```

and:

```text
legal_decision.finding_id
    → findings.id
```

The database should reject impossible relationships.

---

## 41.30 The complete schema relationship

```text
USER
 │
 └── CONTRACT
       │
       └── DOCUMENT_VERSION
              │
              ├── PROCESSING_RUN
              │       └── EVIDENCE
              │
              └── REVIEW
                    │
                    ├── CONFIGURATION_SNAPSHOT
                    │      ├── REQUIREMENT_VERSION
                    │      ├── COMPANY_STANDARD_VERSION
                    │      ├── LEGAL_RULE_VERSION
                    │      ├── MAPPING_RULE_VERSION
                    │      └── EVALUATION_RULE_VERSION
                    │
                    └── FINDING
                           │
                           ├── EVALUATION
                           │
                           ├── FINDING_EVIDENCE
                           │       └── EVIDENCE
                           │
                           └── LEGAL_DECISION

AUDIT_EVENT
    └── records important actions across the system
```

---

## 41.31 The most important database invariant

For every Finding, LegalMind must be able to answer:

```text
Which contract?
Which document version?
Which evidence?
Which requirement?
Which Company Standard version?
Which Legal Rule version?
Which mapping rules?
Which evaluation rules?
Which evaluation result?
Which Legal Decision?
Who made that decision?
When?
```

If the schema cannot answer all of these without reconstructing information from logs or guessing, **the schema is not acceptable**.

---

## Step 41 proposed lock — Status: LOCKED

I recommend locking these **before writing the actual migrations**:

1. PostgreSQL is the system of record.
2. Domain entities use UUID identifiers.
3. `Contract` and `DocumentVersion` remain separate.
4. Document versions are immutable.
5. Processing attempts are separately recorded.
6. Evidence is tied to both Document Version and Processing Run.
7. Requirements are versioned.
8. Company Standards are versioned.
9. Legal Rules are versioned.
10. Mapping Rules are versioned.
11. Evaluation Rules are versioned.
12. Reviews reference a configuration snapshot.
13. Findings reference the applicable Requirement Version.
14. Evaluations are separately persisted from Findings.
15. Findings support multiple Evidence items.
16. Evidence can support multiple Findings.
17. Legal Decisions are separate from Findings.
18. Audit Events are append-only.
19. Object ownership must be traversable from the database.
20. Foreign keys enforce mandatory relationships.
21. Indexes target real access patterns.
22. Historical legal records are not casually hard-deleted.
23. Database timestamps use UTC.
24. JSON is used only where variability justifies it; core domain relationships remain structured.
25. The schema must support complete historical Finding reproducibility.

### Current status

```text
Steps 1–40  🔒 LOCKED

Step 41      ⏳ REVIEW
             PostgreSQL Schema Design
```

**I would not start creating tables/migrations until you approve and lock Step 41.** Once this is locked, the next step should be **Step 42 — Exact Database Schema & ERD**, where we turn these decisions into the actual table definitions, columns, data types, constraints, indexes, and relationship diagram.

---

---

# Appendix: Step 39 — Database Technology Rationale

Source: all_lock.md lines 6097-6173 (Step 39 - "Why PostgreSQL" and "Why I don't recommend a vector database"). Canonical source: all_lock.md (Steps 36-39)

This section is appended by a separate pass covering Steps 36-39 (technology-stack selection) and is distinct from the Steps 40-41 schema/domain-model content above. It documents *why* PostgreSQL was chosen as the database technology and why a vector database was rejected for V1 — the schema itself is defined above.

Status: RECOMMENDED (not yet locked) for the rationale narrative below, EXCEPT that "PostgreSQL" as the database choice is part of the stack table the source explicitly locks under "Step 39 - Technology Stack: LOCKED" (see BACKEND_ARCHITECTURE.md for the full locked stack listing, which names `Database: PostgreSQL`). "No vector database" is a recommendation/rationale, not itself phrased as a separate locked decision line item, though the locked final stack table contains no vector database entry, consistent with this rationale.

## Why PostgreSQL (Step 39)

Status: RECOMMENDED (not yet locked), except that PostgreSQL as the database technology appears in the locked final stack table.

I would make PostgreSQL the system of record.

LegalMind needs relationships like:

```text
Contract
 ↓
Document Version
 ↓
Review
 ↓
Configuration Snapshot
 ↓
Requirement
 ↓
Finding
 ↓
Evidence
 ↓
Legal Decision
 ↓
Audit Event
```

This is fundamentally relational.

PostgreSQL gives us:

* Foreign keys
* Transactions
* Constraints
* JSONB where genuinely useful
* Indexing
* Full-text capabilities if needed
* Strong consistency
* Excellent migration tooling

I would not introduce MongoDB for V1.

## Why I don't recommend a vector database (Step 39)

Status: RECOMMENDED (not yet locked)

For V1:

```text
❌ Pinecone
❌ Weaviate
❌ Milvus
❌ Qdrant
```

We don't need one.

Our core mapping is:

```text
Requirement
+
Controlled terminology
+
Clause structure
+
Deterministic rules
+
Evidence
```

not:

```text
Embedding similarity
```

If later we introduce semantic retrieval, we can reassess whether PostgreSQL + pgvector is sufficient before adding another database.

---

See also: BACKEND_ARCHITECTURE.md for the "Storage" section (PostgreSQL + S3-compatible object storage division of responsibility) and the full locked Step 39 stack table.

For the exact table-by-table SQL-level schema (Step 42), see `docs/09-implementation/DATABASE_MIGRATIONS.md`.

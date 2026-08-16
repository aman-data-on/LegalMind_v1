Source: all_lock.md, Step 43 (lines 9144–10109). Canonical source: all_lock.md (Steps 40-43).

**Status: SPECIFICATION ONLY — describes the target API contract; no endpoints have been implemented.**

For the overall backend architecture, module list, response envelope, HTTP status semantics, authorization model, service/repository layers, transaction boundaries, idempotency, state machines, and API versioning, see `docs/05-architecture/API_ARCHITECTURE.md`. This document covers only the per-module contract details and the end-to-end example from Step 43.

---

## 43.3 `auth`

Responsibilities:

```text
Authentication
User lookup
Role resolution
Permission checks
Session/token validation
```

It should answer:

```text
Who is this user?
What role do they have?
Are they active?
```

It should **not** decide legal outcomes.

---

## 43.4 `contracts`

Responsibilities:

```text
Create Contract
List user's Contracts
Retrieve Contract
Archive Contract
Ownership validation
```

Example API:

```text
POST   /api/v1/contracts
GET    /api/v1/contracts
GET    /api/v1/contracts/{contract_id}
PATCH  /api/v1/contracts/{contract_id}
```

---

## 43.5 `documents`

Responsibilities:

```text
Upload Document
Create Document Version
Retrieve metadata
List versions
Download authorized original
```

Example:

```text
POST /api/v1/contracts/{contract_id}/documents
GET  /api/v1/contracts/{contract_id}/documents
GET  /api/v1/documents/{document_version_id}
```

The upload endpoint should **not perform the complete analysis synchronously**.

---

## 43.6 Upload workflow

```text
POST upload
    ↓
Authenticate
    ↓
Authorize Contract ownership
    ↓
Validate file
    ↓
Store original
    ↓
Create Document Version
    ↓
Create Processing Run
    ↓
Queue worker
    ↓
Return job/document status
```

The API returns quickly.

---

## 43.7 `processing`

This module owns:

```text
File validation
PDF extraction
DOCX extraction
OCR
Normalization
Evidence generation
Processing status
```

Pipeline:

```text
Document
   ↓
Identify format
   ↓
Extract
   ↓
OCR if necessary
   ↓
Normalize
   ↓
Create Evidence
   ↓
Processing complete
```

---

## 43.8 `requirements`

Responsibilities:

```text
Requirement definitions
Requirement versions
Requirement configuration
```

Admin-facing APIs might include:

```text
GET  /api/v1/requirements
GET  /api/v1/requirements/{id}
POST /api/v1/requirements
POST /api/v1/requirements/{id}/versions
```

Only authorized administrative users can modify legal configuration.

---

## 43.9 `configuration`

This module manages:

```text
Company Standards
Legal Rules
Mapping Rules
Evaluation Rules
Configuration Snapshots
```

Critical principle:

> A Review should never dynamically read "whatever configuration is current."

Instead:

```text
Current configuration
        ↓
Create Snapshot
        ↓
Review uses Snapshot
```

---

## 43.10 `reviews`

Responsibilities:

```text
Create Review
Start analysis
Track status
Retrieve results
```

Example:

```text
POST /api/v1/documents/{document_version_id}/reviews
GET  /api/v1/reviews/{review_id}
GET  /api/v1/reviews/{review_id}/status
GET  /api/v1/reviews/{review_id}/findings
```

---

## 43.11 Review creation

When a Review is created:

```text
Document Version
        +
Current approved configuration
        ↓
Configuration Snapshot
        ↓
Review
```

Then the Review gets queued for analysis.

---

## 43.12 `analysis`

This is the **most important backend module**.

It owns the deterministic legal evaluation pipeline.

```text
Analysis Engine
```

should contain components conceptually like:

```text
EvidenceSelector
RequirementMapper
PatternMatcher
ValueExtractor
RuleEvaluator
FindingGenerator
```

Not:

```text
LLM
RAG
Vector Search
```

for V1.

---

## 43.13 Analysis pipeline

```text
Review
 ↓
Load Configuration Snapshot
 ↓
Load Evidence
 ↓
Requirement Mapping
 ↓
Requirement-specific Evaluation
 ↓
Create Evaluation
 ↓
Create Finding
 ↓
Attach Evidence
 ↓
Persist Results
 ↓
Review Complete
```

---

## 43.14 Requirement Mapping

The system first determines:

> Which parts of the contract are relevant to this Requirement?

Example:

```text
Requirement:
LIABILITY-001
```

The mapper searches relevant:

```text
sections
headings
terminology
positive patterns
negative patterns
```

It produces candidate Evidence.

It does **not yet decide whether the contract complies**.

This distinction is critical:

```text
Mapping
    ≠
Evaluation
```

---

## 43.15 Evaluation

The evaluator receives:

```text
Requirement
Requirement Version
Company Standard
Legal Rule
Mapped Evidence
```

and produces a deterministic result.

Example:

```text
Company Standard:
6 months

Contract:
12 months

Legal Rule:
≤12 months = acceptable
>12 months = approval required
```

The evaluator produces the appropriate result according to the locked Legal Rule.

No model "opinion" is involved.

---

## 43.16 Finding generation

The Evaluation result becomes a Finding.

Example:

```text
Evaluation
    ↓
DEVIATION
    ↓
Finding
    ↓
Evidence attached
```

The Finding should contain enough structured information for the UI to explain the result.

---

## 43.17 `findings`

Responsibilities:

```text
Retrieve findings
Filter findings
Retrieve evidence
Retrieve evaluation details
Track finding status
```

Example:

```text
GET /api/v1/reviews/{review_id}/findings
GET /api/v1/findings/{finding_id}
GET /api/v1/findings/{finding_id}/evidence
GET /api/v1/findings/{finding_id}/evaluation
```

---

## 43.18 `decisions`

This module handles the human/legal decision layer.

```text
Finding
   ↓
Legal Decision
```

Example:

```text
POST /api/v1/findings/{finding_id}/decision
```

Authorization must be checked server-side.

A normal User must not be able to approve a Legal Decision merely by calling the endpoint.

---

## 43.19 Decision workflow

```text
Finding
   ↓
Requires Legal Review
   ↓
Authorized reviewer
   ↓
Decision
   ↓
Audit Event
```

And importantly:

```text
Legal Decision
    ≠
Change to Company Standard
```

A contract-specific approved customization does not automatically modify the Company Standard.

This preserves the locked:

> **RESOLVED ≠ MATCH**

principle.

---

## 43.20 `audit`

The Audit module records important events.

Examples:

```text
Contract created
Document uploaded
Review started
Configuration changed
Finding created
Finding resolved
Legal Decision approved
User role changed
```

API access to audit information should itself be permission-controlled.

---

## 43.32 End-to-end example

Take:

> Liability clause says 12 months.

The flow becomes:

```text
User
 ↓
Uploads MSA
 ↓
POST /contracts/{id}/documents
 ↓
Document Version created
 ↓
Processing Job
 ↓
Evidence extracted
 ↓
User creates Review
 ↓
Configuration Snapshot created
 ↓
Review queued
 ↓
Analysis Worker
 ↓
Requirement Mapper
 ↓
LIABILITY-001 evidence identified
 ↓
Evaluation Engine
 ↓
Company Standard = 6 months
Legal Rule = ≤12 acceptable
Contract = 12 months
 ↓
Evaluation
 ↓
Finding = DEVIATION
 ↓
Evidence attached
 ↓
Finding shown to authorized user
 ↓
Legal Reviewer decides
 ↓
Legal Decision persisted
 ↓
Audit Event created
```

Nothing in this process requires an LLM.

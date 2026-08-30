# System Architecture

Source: all_lock.md lines 5128-6020 (Step 37 - V1 Scope Freeze; Step 38 - LegalMind V1 Architecture, excluding 38.9-38.13 which live in ANALYSIS_ENGINE.md). Canonical source: all_lock.md (Steps 36-39)

This is the canonical system architecture document.

---

# Step 37 - V1 Scope Freeze

Status: LOCKED (confirmed at line 5223: "36 and 37 are also locked")

After Step 36, I recommend we freeze the actual V1 functional boundary before architecture.

This step should explicitly answer:

### V1 includes

```text
Document upload
PDF/DOCX processing
Document versioning
Document evidence
Requirement configuration
Company Standards
Legal Rules
Deterministic clause mapping
Deterministic evaluation
Finding generation
Conflict detection
Legal review
Legal Decisions
Contract-specific customization
Review lifecycle
Audit Trail
Configuration versioning
Contract version comparison
Permissions/RBAC
Exports/reporting as defined by the product requirements
```

### V1 explicitly excludes

```text
LLM
RAG
Vector Database
Semantic AI
AI-generated legal conclusions
Automatic legal clause rewriting
Automatic modified DOCX/PDF generation
Automatic redlining
AI negotiation
AI legal advice
```

And importantly:

> V1 can be designed so these capabilities could be added later without redesigning the core legal data model.

That means we don't build LLM/RAG now, but we also don't make architectural choices that permanently prevent future extension.

---

## Step 37 should also define the V1 acceptance boundary

For example:

```text
A V1 Review is successful only if:

Document
    ↓
Evidence
    ↓
Requirement
    ↓
Standard
    ↓
Legal Rule
    ↓
Finding
    ↓
Legal Decision
    ↓
Audit Trail

is completely traceable.
```

If the system cannot explain a Finding, it should not claim that the analysis is complete.

---

### Current status (as recorded in the source at time of Step 36/37 review)

```text
Step 34  LOCKED
Step 35  LOCKED

Step 36  REVIEW (subsequently locked)
Step 37  REVIEW (subsequently locked)
```

"36 and 37 are also locked."

---

# Step 38 - LegalMind V1 Architecture

Status: LOCKED (confirmed at line 6020: "Step 38 - V1 Architecture is locked.")

Now we move from product/legal decisions into system architecture.

The architecture must serve the decisions already locked in Steps 1-37. We should not choose technologies yet. First we define the responsibilities and boundaries of each component; then Step 39 will select the technology stack.

---

## 38.1 Core architectural principle

LegalMind V1 should be a:

> Modular, deterministic, versioned, auditable application with clear separation between document processing, legal configuration, analysis, workflow, and presentation.

The architecture should make it difficult for one layer to accidentally bypass another.

---

# 38.2 High-level architecture

```text id="4v6x2c"
                    ┌─────────────────────┐
                    │      Web UI         │
                    │  User / Admin /     │
                    │    Super Admin      │
                    └──────────┬──────────┘
                               │
                               ↓
                    ┌─────────────────────┐
                    │ Application / API   │
                    │       Layer         │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ↓                    ↓                    ↓
 ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
 │ Review /       │   │ Configuration  │   │ Authorization  │
 │ Workflow       │   │ & Legal Rules  │   │ / RBAC         │
 └───────┬────────┘   └───────┬────────┘   └────────────────┘
         │                    │
         ↓                    ↓
 ┌────────────────────────────────────────────────────────┐
 │                Deterministic Analysis                  │
 │                                                        │
 │  Document Parsing → Mapping → Evaluation → Findings   │
 └──────────────────────────┬─────────────────────────────┘
                            │
             ┌──────────────┼──────────────┐
             ↓              ↓              ↓
      ┌────────────┐ ┌────────────┐ ┌──────────────┐
      │ PostgreSQL │ │  Document  │ │ Audit Trail  │
      │            │ │  Storage   │ │              │
      └────────────┘ └────────────┘ └──────────────┘
```

This is the conceptual architecture. It is not yet a technology decision.

---

# 38.3 Separate the system into domains

I recommend these primary domains:

```text id="4t7s2d"
1. Identity & Access
2. Contract & Document Management
3. Document Processing
4. Legal Configuration
5. Requirement & Clause Mapping
6. Evaluation & Findings
7. Review Workflow
8. Legal Decisions
9. Audit & Version History
10. Reporting / Export
```

Each domain should have a clear responsibility.

---

# 38.4 Identity & Access

Responsible for:

```text id="5t0q6m"
Users
Roles
Permissions
Authentication
Authorization
```

Locked roles:

```text id="e5n8zq"
User
Admin
Super Admin
```

Authorization must be enforced server-side.

The UI hiding a button is not sufficient security.

---

# 38.5 Contract & Document Management

Responsible for:

```text id="9v3k6b"
Contracts
Document Versions
Uploads
Document metadata
Document fingerprints
Document lifecycle
```

Example:

```text id="d5f1z7"
Contract
  ↓
Document Version v1
Document Version v2
Document Version v3
```

This domain does not determine legal Findings.

---

# 38.6 Document Storage

The original uploaded files should live outside the relational database as binary objects/files.

The database stores metadata such as:

```text id="8w3j9k"
Document ID
Version
Filename
MIME type
Size
Hash
Storage location
Upload timestamp
Uploaded by
Processing status
```

The actual PDF/DOCX is stored in controlled document storage.

This separation keeps the database focused on structured application data.

---

# 38.7 Document Processing

Responsible for:

```text id="x3s7nk"
PDF/DOCX extraction
OCR
Text normalization
Structure detection
Page mapping
Clause/paragraph extraction
Table extraction
Extraction validation
```

Output:

```text id="6k0yqj"
Normalized Document Representation
```

It should not decide:

```text id="v9m2sc"
MATCH
DEVIATION
MISSING
```

That belongs to the Analysis Engine.

---

# 38.8 Legal Configuration

This is one of the most important domains.

It manages:

```text id="7q2c8p"
Requirements
Company Standards
Legal Rules
Mapping Rules
Evaluation Rules
Configuration Versions
```

Example:

```text id="1w9j2x"
LIABILITY-001
        │
        ├── Requirement v3
        ├── Company Standard v3
        ├── Legal Rule v2
        ├── Mapping Rules v4
        └── Evaluation Rules v2
```

The exact configuration used by a Review must be captured.

---

Note: Sections 38.9-38.13 (Analysis Engine, Mapping Engine, Evaluation Engine, Findings Domain, Review Workflow) are documented in ../04-analysis-engine/ANALYSIS_ENGINE.md rather than duplicated here.

---

# 38.14 Configuration Snapshot

I recommend the Review store a configuration snapshot/reference rather than simply asking for the "current configuration."

For example:

```text id="4b8w2q"
Review R-101

Document:
MSA v2

Configuration:
Snapshot C-17

Requirement:
LIABILITY-001 v3

Company Standard:
v3

Legal Rule:
v2

Mapping Rules:
v4

Evaluation Rules:
v2
```

This makes the Review historically reproducible.

---

# 38.15 Legal Decision Layer

This remains separate from automated analysis.

Architecture:

```text id="z5m7qk"
Finding
   ↓
Legal Review
   ↓
Legal Decision
```

Example:

```text id="4j8x2w"
Finding:
DEVIATION

Legal:
APPROVE_CUSTOMIZATION
```

The system must not convert a Finding directly into a Legal Decision without the appropriate authorized Legal action.

---

# 38.16 Audit Layer

Audit should observe important business events across the system.

Example:

```text id="s6y2nz"
Document uploaded
Review created
Analysis completed
Finding created
Configuration published
Legal Decision recorded
Review completed
```

Audit records should be append-only.

---

# 38.17 Reporting / Export

Reporting consumes existing data.

It should not independently recalculate legal conclusions.

For example:

```text id="g3k9wp"
Review
 ↓
Findings
 ↓
Legal Decisions
 ↓
Report
```

The report is a presentation of the recorded analysis, not a second analysis engine.

---

# 38.18 Database responsibility

The relational database should store:

```text id="t0x8kw"
Users
Roles
Contracts
Document metadata
Document Versions
Requirements
Configurations
Rules
Reviews
Findings
Evidence metadata
Legal Decisions
Audit Events
```

It should not necessarily store the original PDF/DOCX binary.

Binary document storage should be separate.

---

# 38.19 Background processing

Document processing and analysis can be expensive.

We should therefore design the architecture so these operations can run asynchronously:

```text id="y8c3qp"
Upload
  ↓
Job
  ↓
Document Processing
  ↓
Analysis
  ↓
Findings
```

The UI should not need to keep an HTTP request open for the entire analysis.

However, whether we use a dedicated queue system, worker process, or another mechanism is a Step 39 technology decision.

---

# 38.20 Transaction boundaries

Legal actions need strong transactional integrity.

For example:

```text id="m1k7zc"
Approve Customization
```

should not result in:

```text id="j3v9xs"
Decision saved
but
Audit event missing
```

The architecture should define appropriate transactional boundaries so important business state and audit state remain consistent.

The exact implementation depends on the database and application technology chosen later.

---

# 38.21 Security boundary

The architecture should enforce:

```text id="p8r2mv"
Authentication
      ↓
Authorization
      ↓
Business Operation
      ↓
Database
```

Never:

```text id="x3k7na"
UI permission
      ↓
Trust user
```

Ownership and role checks happen on the server.

---

# 38.22 No direct UI → database access

The frontend should not directly manipulate the database.

Correct:

```text id="n4q7wf"
UI
 ↓
API/Application Layer
 ↓
Domain Logic
 ↓
Database
```

This allows permissions, validation, audit, and business rules to be enforced centrally.

---

# 38.23 No UI → analysis-engine shortcuts

The UI should never implement its own version of legal evaluation.

For example, don't do:

```text id="d6y3pk"
Frontend:
if liability > 6:
    deviation
```

Instead:

```text id="z1m8qs"
UI
 ↓
Analysis API
 ↓
Evaluation Engine
 ↓
Finding
```

There must be one source of truth for legal evaluation.

---

# 38.24 API/domain boundary

The API layer should orchestrate operations.

For example:

```text id="p7f3wa"
POST /reviews
        ↓
Review Service
        ↓
Document Version
        ↓
Configuration Snapshot
        ↓
Analysis Job
```

The exact endpoint naming is not locked here.

We will determine API design during implementation architecture.

---

# 38.25 Architecture should support future LLM/RAG

Even though V1 does not use them, we should keep the analysis interface modular.

Conceptually:

```text id="n8v3dz"
Analysis Interface
       │
       ├── V1 Deterministic Engine
       │
       └── Future AI-assisted Engine
```

But:

V1 uses only the deterministic engine.

Future AI capabilities must not silently replace the deterministic legal source of truth.

---

# 38.26 What should NOT be a separate microservice in V1

I recommend not over-engineering V1.

We do not need to immediately create:

```text id="k7m3qa"
10 microservices
Kubernetes
Service mesh
Event bus everywhere
Separate database per domain
```

unless actual requirements justify them.

A modular monolith with background workers is likely a much more appropriate starting architecture.

This is an architectural recommendation, not yet a technology lock.

---

# 38.27 Recommended V1 deployment shape

Conceptually:

```text id="r2q8mc"
                    Internet
                       │
                       ↓
                 ┌───────────┐
                 │ Web/API   │
                 │ Application│
                 └─────┬─────┘
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
       PostgreSQL          Document Storage
             │
             ↓
       Background Worker
             │
             ↓
       Analysis Engine
```

This keeps V1 operationally simple while allowing the analysis engine to scale independently later.

---

# 38.28 The critical architectural rule

The architecture must preserve this separation:

```text id="8x5v2m"
SOURCE OF TRUTH

Customer Contract
        ↓
Evidence
        ↓
Company Configuration
        ↓
Deterministic Analysis
        ↓
Finding
        ↓
Human Legal Decision
```

The UI, reports, exports, and future AI features are consumers of this source of truth, not replacements for it.

---

# 38.29 Step 38 proposed locked decisions

Status: LOCKED (Step 38 as a whole was locked at line 6020: "Step 38 - V1 Architecture is locked.")

I recommend locking these:

1. LegalMind V1 uses a modular architecture with clear domain boundaries.
2. V1 should favor a modular monolith plus background processing rather than premature microservices.
3. Identity/Authorization, Contract Management, Document Processing, Legal Configuration, Analysis, Review Workflow, Legal Decisions, Audit, and Reporting have separate responsibilities.
4. Original documents are stored separately from structured relational data.
5. The database stores document metadata and references, not necessarily binary documents.
6. Document Processing is separate from Legal Analysis.
7. Requirement Mapping is separate from Evaluation.
8. Evaluation is separate from Legal Decision.
9. Review is the historical container connecting the Document Version, configuration context, Findings, Decisions, and Audit Trail.
10. Every Review captures the exact configuration context required for reproducibility.
11. Legal Decisions require the appropriate authorized action and are never silently generated from Findings.
12. Audit events are append-only and cover important legal/business actions.
13. Reporting and exports consume recorded analysis results rather than independently recalculating them.
14. Server-side authorization is mandatory.
15. The frontend never directly accesses the database.
16. The frontend never implements its own legal evaluation logic.
17. Long-running document processing/analysis is designed for asynchronous background execution.
18. Important business state changes and their audit records require appropriate transactional consistency.
19. V1 does not require a microservice architecture, Kubernetes, service mesh, or other distributed infrastructure unless a later requirement proves it necessary.
20. The architecture exposes a clean analysis boundary so future LLM/RAG capabilities can be evaluated later without becoming the V1 legal source of truth.
21. The deterministic V1 Analysis Engine remains the authoritative source for V1 Findings.

### Architecture in one picture

```text id="1t9x2v"
                         ┌──────────────────┐
                         │      Web UI      │
                         └────────┬─────────┘
                                  ↓
                         ┌──────────────────┐
                         │ Application/API  │
                         └────────┬─────────┘
                                  ↓
        ┌─────────────────────────┼────────────────────────┐
        ↓                         ↓                        ↓
┌───────────────┐        ┌────────────────┐        ┌──────────────┐
│ Contract &    │        │ Review & Legal │        │ Identity /   │
│ Documents     │        │ Workflow       │        │ RBAC         │
└───────┬───────┘        └───────┬────────┘        └──────────────┘
        ↓                         ↓
┌──────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC ANALYSIS                    │
│                                                              │
│ Document Processing → Mapping → Evaluation → Findings      │
└───────────────────────────────┬──────────────────────────────┘
                                ↓
                    ┌─────────────────────┐
                    │ Legal Configuration │
                    │ Standards / Rules   │
                    └─────────────────────┘

          ┌──────────────────┬──────────────────┐
          ↓                  ↓                  ↓
    PostgreSQL       Document Storage       Audit Trail
```

### Status

```text
Steps 1–37  LOCKED

Step 38      REVIEW
             Architecture

Step 39      → Technology Stack
```

I recommend you review Step 38 before locking it. Once Step 38 is locked, Step 39 is where we can seriously evaluate the actual tech stack - framework, database, document parsers, OCR, queue/worker technology, storage, authentication, testing, and deployment - against these architectural requirements.

Step 38 - V1 Architecture is locked.

---

See also:
- ../04-analysis-engine/ANALYSIS_ENGINE.md for domains 38.9-38.13 (Analysis Engine, Mapping Engine, Evaluation Engine, Findings Domain, Review Workflow) and the full Step 36 Finding & Evaluation Engine.
- BACKEND_ARCHITECTURE.md, FRONTEND_ARCHITECTURE.md, DATABASE_ARCHITECTURE.md for the Step 39 technology stack that implements this architecture.
- ../08-testing/TEST_STRATEGY.md for the Step 39 testing strategy.

---

## Amendment Batches AB-3 and AB-4 — the assist lane

**Status: 🔒 LOCKED.** `AM-25`–`AM-29` (AB-3, 2026-08-24) · `AM-30`, `AM-31`, `IMPL-02` (AB-4,
2026-08-25). **Added to this document 2026-08-25.** The registry named this file as `AM-25`'s
canonical document and the section was never written; that omission is corrected here. Nothing
above this line changes.

### What changed, and what did not

`38.25` anticipated exactly this — an Analysis Interface with the V1 deterministic engine on one
side and a future AI-assisted engine on the other. AB-3 **realizes** that hook rather than
amending it, and Step 38 rules 20–21 are **reaffirmed and strengthened**, not weakened.

The single most load-bearing sentence in this document for the assist lane is **38.28**:

> Customer Contract → Evidence → Company Configuration → Deterministic Analysis → Finding →
> Human Legal Decision. *"The UI, reports, exports, and future AI features are consumers of this
> source of truth, not replacements for it."*

The assist lane is a **consumer** under that rule. It reads already-recorded Evidence; it never
participates in producing a Finding. It is **not an eleventh domain** — the ten domains of
38.3–38.17 are unchanged.

### The nine terms — by reference, not restated

`AM-25`'s nine terms are locked constraints, not guidance, and they are **not reproduced here**:
read them in [`all_lock.md`](../../all_lock.md) AB-3, indexed at
[LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md) §AB3. In summary, the lane never
produces a Finding, Evaluation, Classification, Rule Outcome, Mapping State, Legal Decision or
Lifecycle transition (r1); never writes to the legal or configuration tables, enforced by a
**database role** holding no INSERT or UPDATE grant rather than by convention (r2); never states
an organizational legal position absent from a ratified Standard, published Rule or approved
template (r3); never answers *"does this document meet our standard?"*, which routes to the
evaluator (r4); lets no answer reach a user unless every claim resolves to retrieved evidence,
enforced **mechanically, outside the model** (r5); applies authorization **before** retrieval and
**inside** the query, with an excluded result indistinguishable from an empty one (r6); is never
an existence oracle (r7); confers no Legal Decision authority (r8); and — as amended by `AM-30` —
lets nothing but the generation call leave LeapSwitch-controlled infrastructure (r9).

### Architectural shape

| Concern | Position |
|---|---|
| Decomposition | **Unchanged. Modular monolith.** `AM-26` restates locked 38.26 explicitly: no microservices, no Kubernetes, no service mesh. The assist lane is a package in the same application, and `AM-26` r1's single generation interface is an **in-process module boundary, not a service.** Any proposal for a separate gateway container is a decomposition this document does not authorize |
| Isolation | By **database role** (`AM-25` r2) and by import boundary — `backend/tests/test_import_boundaries.py` fences the deterministic core against a future `legalmind.assist` package with an allow-list, so the rule holds before the package exists |
| Storage | PostgreSQL remains the system of record. pgvector is an **extension on it**, not a new datastore (`AM-26`); a second vector datastore requires separate approval |
| Authorization | The existing `Guard` chain, reused unchanged and extended to retrieval. `SEC-07`/`API-10`'s byte-identical-404 discipline extends to a retrieval result set (`AM-25` r6/r7) |
| Confidentiality | `LEGAL-02` unchanged — omitted, never nulled — and `AM-30` t3 makes it an **egress rule as well as a display rule** |
| Egress | One path only: the generation call (`AM-30`). Embedding, reranking, chunking, parsing and OCR stay local. `AM-31`'s real-contract gate is **CLOSED** as of 2026-08-25 |

### Build state

Specification only. No assist-lane code, table, migration or dependency exists — see
[IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md) unit 12, which is the only
document that may assert build state. The authorized sequence is `IMPL-02` →
[IMPLEMENTATION_READINESS_GATE.md](../09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5b.

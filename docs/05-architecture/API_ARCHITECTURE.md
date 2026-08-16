Source: all_lock.md, Step 43 (lines 9144–10109). Canonical source: all_lock.md (Steps 40-43).

For the per-module API contract details (contracts/documents/reviews/analysis/findings/decisions/audit module descriptions and the end-to-end example), see `docs/09-implementation/API_CONTRACT.md`. For the database schema these modules operate against, see `docs/05-architecture/DATABASE_ARCHITECTURE.md` and `docs/09-implementation/DATABASE_MIGRATIONS.md`.

# Step 43 — API Contract & Backend Module Structure

This step defines **how the LegalMind application actually operates between frontend, API, domain logic, database, and workers**.

The key principle:

> **The API is the application boundary. The frontend never implements legal logic, and the database never implements legal evaluation logic.**

---

## 43.1 Backend architecture

The backend should be structured as a **modular monolith**, not one giant collection of routes.

```text
FastAPI
   │
   ├── Auth / Authorization
   │
   ├── Contracts
   │
   ├── Documents
   │
   ├── Reviews
   │
   ├── Findings
   │
   ├── Legal Decisions
   │
   ├── Legal Configuration
   │
   └── Audit
          │
          ↓
    Domain Services
          │
          ├── Document Processing
          ├── Requirement Mapping
          ├── Deterministic Evaluation
          ├── Finding Generation
          └── Decision Workflow
          │
          ↓
      PostgreSQL
```

Long-running work:

```text
FastAPI
   ↓
Redis
   ↓
Celery
   ↓
Worker
```

---

## 43.2 Proposed backend modules

```text
app/
├── api/
├── auth/
├── contracts/
├── documents/
├── processing/
├── requirements/
├── configuration/
├── reviews/
├── analysis/
├── findings/
├── decisions/
├── audit/
├── storage/
├── workers/
└── core/
```

Each module owns its domain behavior.

(Per-module responsibilities are detailed in `docs/09-implementation/API_CONTRACT.md`.)

---

## 43.21 API response structure

Responses should be consistent.

For successful single-object responses:

```text
{
  "data": {...}
}
```

For collections:

```text
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 100
  }
}
```

Errors should have a predictable structure:

```text
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document was not found."
  }
}
```

The exact final API envelope can be standardized during implementation.

---

## 43.22 HTTP status semantics

Use normal HTTP semantics.

```text
200  Successful retrieval/update
201  Resource created
202  Accepted for asynchronous processing
204  Successful operation with no response body

400  Invalid request
401  Unauthenticated
403  Authenticated but unauthorized
404  Resource not found
409  State/conflict violation
422  Validation failure
500  Unexpected server error
```

For document analysis:

```text
POST /reviews
→ 202 Accepted
```

is appropriate when processing is asynchronous.

---

## 43.23 Authorization model

Authorization should happen at the API/service boundary.

Example:

```text
Request
 ↓
Authentication
 ↓
Role check
 ↓
Object ownership check
 ↓
Operation permission
 ↓
Domain operation
```

Never:

```text
Request
 ↓
Fetch object by ID
 ↓
Return object
```

without checking authorization.

---

## 43.24 Service layer

Routes should remain thin.

Bad:

```text
FastAPI route
 ├── SQL
 ├── legal logic
 ├── permission logic
 ├── document parsing
 └── response formatting
```

Preferred:

```text
API Route
   ↓
Application Service
   ↓
Domain Service
   ↓
Repository
   ↓
Database
```

---

## 43.25 Repository layer

Repositories should handle persistence concerns.

Example:

```text
ContractRepository
DocumentRepository
ReviewRepository
FindingRepository
DecisionRepository
```

They should not contain legal evaluation logic.

---

## 43.26 Transaction boundaries

Important operations should be transactional.

For example, creating a Legal Decision should ensure:

```text
Decision created
+
Audit event created
```

are committed consistently.

We must avoid:

```text
Decision saved
Audit failed
```

leaving an incomplete legal history.

---

## 43.27 Background worker boundaries

Workers should own long-running operations.

```text
DocumentProcessingWorker
ReviewAnalysisWorker
```

Potential future workers can be added without turning the application into microservices.

---

## 43.28 Idempotency

This is an important addition.

Processing and analysis jobs must be designed so accidental retries do not create duplicate legal results.

Example:

```text
Worker starts
 ↓
Network failure
 ↓
Job retries
```

The second execution must not blindly create:

```text
Duplicate Finding
Duplicate Evaluation
Duplicate Decision
```

Use stable processing/review identifiers and database constraints where appropriate.

---

## 43.29 State machines

We should explicitly model lifecycle states.

### Document

```text
UPLOADED
PROCESSING
READY
FAILED
```

### Review

```text
CREATED
QUEUED
ANALYZING
COMPLETED
FAILED
```

### Finding

The exact Finding lifecycle should be defined separately because it interacts with Legal Decisions.

We should **not invent unnecessary states now**.

---

## 43.30 API versioning

Use:

```text
/api/v1/
```

from the beginning.

This gives us a clean compatibility boundary if the API changes later.

---

## 43.31 What the frontend is allowed to do

Frontend:

```text
Display
Filter
Sort
Navigate
Submit actions
Show evidence
Show explanations
Show status
```

Frontend does **not**:

```text
Evaluate legal rules
Decide risk
Determine compliance
Approve findings
Modify company standards directly
```

---

## 43.33 Step 43 proposed lock — Status: LOCKED

Before locking, I recommend we specifically verify these principles:

1. FastAPI is the backend application boundary.
2. Backend is a modular monolith.
3. Frontend contains no legal evaluation logic.
4. API routes remain thin.
5. Domain/application services contain business logic.
6. Repositories handle persistence.
7. Legal evaluation remains inside the deterministic Analysis Engine.
8. Document processing is asynchronous.
9. Review analysis is asynchronous.
10. Configuration Snapshots are created before analysis.
11. Reviews never silently use changing configuration.
12. Findings are generated from deterministic Evaluations.
13. Legal Decisions are a separate human/legal layer.
14. Legal Decisions never silently modify Company Standards.
15. Authorization is checked server-side.
16. Object ownership is enforced.
17. API uses `/api/v1`.
18. Long-running operations return asynchronous status.
19. Processing/analysis operations are idempotent.
20. Important state changes and legal actions are audited.
21. Database transactions protect critical multi-record operations.
22. V1 does not introduce microservices merely for architectural fashion.
23. No LLM/RAG/vector database is introduced into the V1 legal-analysis path.

### Current status

```text
Steps 1–42  🔒 LOCKED

Step 43      ⏳ REVIEW
             API Contract & Backend Module Structure
```

**I would review Step 43 carefully before locking it.** After this, Step 44 should define the **exact Legal Analysis Engine architecture**—the most important technical step because it determines how LegalMind actually turns contract evidence + Company Standards + Legal Rules into deterministic Findings.

🔒 **Step 43 — API Contract & Backend Module Structure: LOCKED**

I rechecked it against Steps 1–42. The separation is now fixed:

```text
Frontend
   ↓
FastAPI
   ↓
Application Services
   ↓
Domain Services
   ↓
Deterministic Analysis Engine
   ↓
Repositories
   ↓
PostgreSQL
```

Async processing, server-side authorization, idempotency, configuration snapshots, auditability, and the **no-LLM/no-RAG V1 boundary** are all locked.

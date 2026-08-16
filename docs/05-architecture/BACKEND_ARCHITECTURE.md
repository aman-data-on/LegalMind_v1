# Backend Architecture

Source: all_lock.md lines 6024-6800 (Step 39 - Recommended Technology Stack, backend-relevant sections). Canonical source: all_lock.md (Steps 36-39)

Status: This document is primarily RECOMMENDED content from Step 39. The final stack table and the closing "Technology Stack: LOCKED" statement (reproduced at the bottom) are the one part of Step 39 the source explicitly locks; everything else in this document — rationale, design approach, "what I deliberately don't recommend" — is framed by the source as a personal recommendation and is marked Status: RECOMMENDED (not yet locked) accordingly.

See SYSTEM_ARCHITECTURE.md for the locked domain boundaries and architectural rules (Step 38) that this backend implements. Domain separation, security boundary, no-UI-shortcuts, transaction boundaries, etc. are not repeated here.

---

# Step 39 - Recommended Technology Stack (backend-relevant content)

Status: RECOMMENDED (not yet locked), except the final stack table, which the source explicitly locks (see bottom of this file).

My recommendation is a modular monolith + background workers, not microservices.

### Recommended stack (full table, as given in the source)

| Layer            | Recommendation                                      | Why                                                                                       |
| ---------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Frontend         | Next.js + TypeScript                            | Strong admin/dashboard UX, server-side capabilities, mature ecosystem                     |
| Backend/API      | FastAPI + Python                                | Excellent fit for document processing and deterministic analysis                          |
| Database         | PostgreSQL                                      | Strong relational model, transactions, JSONB, constraints, excellent audit/versioning fit |
| ORM              | SQLAlchemy 2 + Alembic                          | Explicit schema/control, mature migrations                                                |
| Document PDF     | PyMuPDF                                         | Fast, strong PDF text/page extraction and positional data                                 |
| DOCX             | python-docx                                     | Reliable structured DOCX parsing                                                          |
| OCR              | OCRmyPDF + Tesseract initially                  | Good deterministic/local OCR pipeline                                                     |
| Background jobs  | Celery + Redis                                  | Mature worker model for document processing/analysis                                      |
| Object storage   | S3-compatible storage                           | Original PDFs/DOCX and derived artifacts                                                  |
| API validation   | Pydantic                                        | Excellent typed validation with FastAPI                                                   |
| Auth             | OIDC/OAuth2-compatible provider                 | Avoid building authentication ourselves                                                   |
| Authorization    | Application-level RBAC + PostgreSQL constraints | Server-side enforcement                                                                   |
| Testing          | Pytest + Playwright                             | Backend/domain + real browser workflow testing                                            |
| Frontend testing | Vitest                                          | Fast TypeScript unit testing                                                              |
| Containers       | Docker                                          | Reproducible development/deployment                                                       |
| Reverse proxy    | Nginx or equivalent                             | TLS, routing, upload handling                                                             |
| CI/CD            | GitHub Actions                                  | Straightforward automated testing/deployment                                              |
| Monitoring       | Sentry + structured application logs            | Error tracking and operational visibility                                                 |

(Frontend/Database rows are cross-referenced here in full for context; see FRONTEND_ARCHITECTURE.md and DATABASE_ARCHITECTURE.md for their dedicated rationale.)

---

# Why I recommend Python for the backend

Status: RECOMMENDED (not yet locked)

This is the most important stack decision.

LegalMind's difficult part isn't the dashboard.

It's:

```text
PDF/DOCX
   ↓
Extraction
   ↓
OCR
   ↓
Normalization
   ↓
Clause detection
   ↓
Deterministic mapping
   ↓
Rule evaluation
   ↓
Evidence
```

Python has an exceptionally strong ecosystem for this kind of document-processing workload.

It also gives us room later to evaluate NLP/LLM capabilities without rewriting the backend.

But V1 remains:

```text
Python
+
Deterministic algorithms
+
Rules
```

—not AI.

---

# Background processing

Status: RECOMMENDED (not yet locked)

Don't do this:

```text
POST /upload

30-second request
      ↓
extract PDF
      ↓
OCR
      ↓
analyze
      ↓
return
```

Instead:

```text
POST /documents
      ↓
Create Document
      ↓
Queue Job
      ↓
202 Accepted
      ↓
Worker
      ↓
Processing
      ↓
Analysis
      ↓
Findings
      ↓
Review Ready
```

The UI can show:

```text
Uploading
    ↓
Processing
    ↓
Extracting
    ↓
Analyzing
    ↓
Review Ready
```

---

# Celery + Redis

Status: RECOMMENDED (not yet locked)

For V1:

```text
FastAPI
   ↓
Redis
   ↓
Celery Worker
```

Workers can handle:

```text
document extraction
OCR
normalization
clause mapping
evaluation
report generation
```

This keeps the web/API process responsive.

---

# Storage

Status: RECOMMENDED (not yet locked)

Use:

```text
PostgreSQL
+
S3-compatible object storage
```

Database:

```text
metadata
relationships
rules
findings
audit
```

Object storage:

```text
original.pdf
original.docx
OCR output
derived artifacts
```

Never put a 20 MB PDF directly into a normal PostgreSQL row unless there is a very specific reason.

---

# Analysis engine design

Status: RECOMMENDED (not yet locked)

This is where I want us to be particularly disciplined.

Create a separate Python domain package:

```text
legalmind/
│
├── analysis/
│   ├── mapping/
│   ├── evaluation/
│   ├── findings/
│   └── evidence/
│
├── documents/
│   ├── pdf/
│   ├── docx/
│   ├── ocr/
│   └── normalization/
│
├── legal/
│   ├── requirements/
│   ├── standards/
│   ├── rules/
│   └── configuration/
│
├── reviews/
├── decisions/
├── audit/
├── auth/
└── reports/
```

This makes the architecture enforceable in code.

---

# The deterministic algorithm stack

Status: RECOMMENDED (not yet locked)

This is more important than choosing a framework.

For V1, I'd use a combination of:

### 1. Structural parsing

Identify:

```text
heading
section
clause
paragraph
table
list
```

### 2. Controlled terminology

```text
liability
liable
aggregate liability
liability cap
maximum liability
```

### 3. Rule-based pattern matching

Regex + normalized phrase matching.

### 4. Negation/exclusion patterns

Detect things such as:

```text
liability shall not be limited
```

rather than incorrectly treating "liability" + "limited" as a positive match.

### 5. Deterministic candidate scoring

Rank candidate clauses based on configured signals.

### 6. Requirement-specific evaluators

```text
NUMERIC_COMPARISON
RANGE_COMPARISON
ALLOWED_VALUES
EXACT_MATCH
BOOLEAN_PRESENT
MULTI_CLAUSE
CONFLICT_DETECTION
```

### 7. Explicit uncertainty states

```text
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

This is the algorithmic foundation I'd use instead of trying to make one "AI-like" algorithm do everything.

---

# API architecture

Status: RECOMMENDED (not yet locked)

I recommend:

```text
Next.js
     ↓
REST API
     ↓
FastAPI
     ↓
Application Services
     ↓
Domain Services
     ↓
Repositories
     ↓
PostgreSQL
```

Keep the domain logic independent from HTTP.

That means the evaluation engine can eventually be tested like:

```text
evaluate(requirement, clause, standard, rule)
```

without running a browser or API server.

That's extremely valuable for legal testing.

(See ../08-testing/TEST_STRATEGY.md for the full testing strategy this enables.)

---

# Security

Status: RECOMMENDED (not yet locked)

Because these are legal documents, security isn't an optional add-on.

V1 should include:

```text
TLS
Authentication
Server-side RBAC
Object-level authorization
Encrypted storage where supported
Secrets outside source code
Upload validation
Safe document parsing
Malware scanning where available
Audit trail
Rate limiting
Session security
Database backups
```

And importantly:

> A user must never be able to access another user's Contract, Document Version, Review, Finding, or Legal Decision merely by changing an ID in an API request.

(See SYSTEM_ARCHITECTURE.md sections 38.21-38.24 for the locked architectural security boundary this recommendation sits on top of.)

---

# Deployment

Status: RECOMMENDED (not yet locked)

For V1, I would keep deployment relatively simple:

```text
                    Internet
                       ↓
                  Reverse Proxy
                       ↓
              Next.js + FastAPI
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
       PostgreSQL          Background Workers
                                  ↓
                                Redis
                                  ↓
                           Object Storage
```

You don't need Kubernetes on day one.

Docker Compose can be enough for development and potentially a small production deployment; production orchestration can evolve based on actual load and availability requirements.

---

# What I deliberately DON'T recommend

Status: RECOMMENDED (not yet locked)

### Microservices from day one

Too much operational complexity for V1.

### Kubernetes immediately

No evidence yet that V1 requires it.

### MongoDB

The data model is heavily relational.

### Vector DB

Not required by the V1 methodology.

### LLM

Explicitly outside V1.

### RAG

Explicitly outside V1.

### Cloud OCR by default

Legal-document privacy makes local/self-hosted OCR preferable initially.

### Building our own authentication

Use a mature identity solution.

### Business logic in Next.js

Legal evaluation belongs in the backend/domain layer.

---

# Final recommended stack

Status: LOCKED — the source explicitly states "Step 39 - Technology Stack: LOCKED" after this diagram (see below).

```text
┌────────────────────────────────────────────┐
│                FRONTEND                    │
│       Next.js + TypeScript                 │
└─────────────────────┬──────────────────────┘
                      │
                      ↓
┌────────────────────────────────────────────┐
│                 API                        │
│              FastAPI                       │
│             Pydantic                       │
└─────────────────────┬──────────────────────┘
                      │
          ┌───────────┴───────────┐
          ↓                       ↓
┌──────────────────┐     ┌──────────────────┐
│ LegalMind Domain │     │ Background Jobs  │
│ / Analysis       │     │ Celery + Redis   │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └────────────┬───────────┘
                      ↓
             ┌────────────────┐
             │  PostgreSQL    │
             └────────────────┘

             ┌────────────────┐
             │ Object Storage │
             │ S3-compatible  │
             └────────────────┘

Document Processing:
PyMuPDF
python-docx
OCRmyPDF
Tesseract

Testing:
Pytest
Vitest
Playwright

Infrastructure:
Docker
Reverse Proxy
GitHub Actions
Sentry
```

## My recommendation

This is the stack I would choose for LegalMind V1.

The most important decision isn't Next.js vs another frontend or FastAPI vs another API framework. The critical decision is that the deterministic analysis engine is a first-class domain component, independently testable, versioned, and completely separated from the UI.

And we should not start implementation yet just because the stack is selected. The next architecture step should define the actual database/domain model and component boundaries before Claude Code starts creating tables and files.

Step 39 - Technology Stack: proposed. I recommend we review it once before locking, particularly the FastAPI + PostgreSQL + Celery/Redis + PyMuPDF/OCRmyPDF choices.

## LOCKED: Step 39 - Technology Stack

Status: LOCKED (source text: "Step 39 - Technology Stack: LOCKED")

The technology direction is now fixed:

```text
Frontend:          Next.js + TypeScript
Backend:           FastAPI + Python
Database:          PostgreSQL
ORM/Migrations:    SQLAlchemy 2 + Alembic
PDF:               PyMuPDF
DOCX:              python-docx
OCR:               OCRmyPDF + Tesseract
Jobs:              Celery + Redis
Storage:           S3-compatible object storage
Testing:           Pytest + Vitest + Playwright
Infrastructure:    Docker
Monitoring:        Sentry + structured logs
```

And importantly:

```text
Modular Monolith
+
Background Workers
+
Deterministic Analysis Engine
```

No microservices/Kubernetes/LLM/RAG/vector DB in V1.

# LegalMind V1 — Legal Analysis Philosophy (Canonical)

Source: all_lock.md, lines 1–1140 (Steps 7–9, V1 AI Boundary). Canonical source: all_lock.md (Steps 1-9).

**This is the canonical philosophy document for LegalMind's legal-analysis approach.** It consolidates the locked decisions on clause-level comparison, findings, review/report/versioning, and the V1 AI boundary.

---

## Step 7 — Clause-Level Comparison

**Status: LOCKED**

LegalMind V1 will compare contracts at the **clause/requirement level**, not only at whole-document level.

Example:

```text
Customer MSA
│
├── Payment Terms
├── Termination
├── Confidentiality
├── Limitation of Liability
├── Indemnification
└── Governing Law
```

The comparison should identify corresponding clauses/requirements and compare them.

Initial comparison outcomes:

```text
MATCH
DEVIATION
CONFLICT
MISSING
```

Example:

```text
LIMITATION OF LIABILITY

LeapSwitch Standard:
"Liability is limited to 6 months of fees."

Customer Contract:
"Liability is unlimited."

↓
Finding:
CONFLICT
Risk:
HIGH
```

A completely absent requirement is:

```text
Finding:
Missing Requirement
```

The detailed matching rules remain a later decision (**Status: NOT YET SPECIFIED**).

---

## Step 8 — Complete Comparison + Findings

### Locked decision

**Status: LOCKED**

**Comparison = complete alignment report.**

LegalMind must not show only problems. The user should understand:

* What matches
* What differs
* What is missing
* What conflicts
* Which clauses were reviewed
* Evidence supporting the result

Example:

```text
CONTRACT COMPARISON

Overall alignment: 82%

✓ Payment Terms
   Aligned

✓ Confidentiality
   Aligned

⚠ Limitation of Liability
   Deviation

❌ Data Protection
   Missing

✓ Termination
   Aligned
```

### Finding

A **Finding** is a clause/requirement-level comparison result.

A Finding is not necessarily a problem.

It can be:

```text
MATCH
DEVIATION
CONFLICT
MISSING
```

### Finding is separate from Legal Decision

**Status: LOCKED**

```text
Finding
   ↓
Comparison result
```

versus:

```text
Decision
   ↓
Authorized human legal decision
```

LegalMind must not treat a Finding as the final legal truth.

### Evidence

Every meaningful Finding should be traceable to source evidence:

```text
Finding F-001
│
├── Customer clause
│     └── ABC MSA, Section 12.3
│
└── Company reference
      └── LeapSwitch Standard MSA, Section 10.2
```

---

## Step 9 — Versioned Review, Standards & Reports

### Central record: Review

**Status: LOCKED**

The core object is a **Review**, not simply a Report.

```text
CONTRACT
   ↓
CONTRACT VERSION
   ↓
LEGALMIND REVIEW
   ├── Comparison Basis
   ├── Findings
   ├── Evidence
   ├── Summary
   ├── Escalations
   ├── Decisions
   └── Audit History
```

A Report is generated from the Review and is not the fundamental source of truth.

### Historical traceability

Example:

```text
ABC MSA v1
      ↓
Review R-001
      ↓
LeapSwitch Standard MSA v1
```

Later:

```text
ABC MSA v2
      ↓
Review R-002
      ↓
LeapSwitch Standard MSA v2
```

Review R-001 must never be silently rewritten.

Each Review records the exact context used, including:

* Contract version
* Comparison standard/version
* Legal Position version, where applicable
* Reviewer/creator
* Timestamp
* Review status
* Findings
* Evidence
* Escalations
* Decisions
* Audit history

### Standard Maintenance Inside LegalMind

**Status: LOCKED**

Authorized Admin/Legal users maintain the organization's standards **inside LegalMind**.

For a small change, they do not need to re-upload the entire MSA.

Example:

```text
Admin
  ↓
Legal Standards
  ↓
MSA
  ↓
Edit clause/standard
  ↓
Draft version
  ↓
Review / Approve
  ↓
Publish
  ↓
New Active Version
```

If:

```text
Liability: 6 months → 12 months
```

is changed and published, all **new comparisons automatically use the new active version**.

No code change and no new counterparty upload are required.

### Versioning rule

**Status: LOCKED**

Approved historical standards must not be silently overwritten.

Example:

```text
MSA Standard
│
├── v1
│   Liability = 6 months
│   Status = Superseded
│
└── v2
    Liability = 12 months
    Status = Active
```

Only the latest **published/active** version can be used for new comparisons.

Draft versions must never silently affect comparisons.

### Legal Positions are also versioned

**Status: LOCKED**

Example:

```text
Legal Position v1
Preferred = 6 months
Maximum without approval = 12 months

        ↓ changed

Legal Position v2
Preferred = 12 months
Maximum without approval = 24 months
```

Historical Reviews retain the exact Legal Position version they used.

### Standard Document vs Structured Legal Rule

**Status: LOCKED**

These remain distinct:

```text
SOURCE DOCUMENT
"What does our approved MSA actually say?"

        +

STRUCTURED LEGAL RULE
"How should LegalMind evaluate this provision?"
```

The actual approved legal document remains authoritative for contractual wording.

Structured rules support comparison/evaluation.

### Report

The Report is generated from the Review:

```text
LEGALMIND REVIEW
      │
      ├── Interactive Review Screen
      │
      └── Report
```

The report should summarize:

* Contract information
* Contract version
* Comparison source/version
* Overall alignment
* Match/deviation/conflict/missing counts
* Clause-level findings
* Evidence references
* High-level risk
* Review/escalation status
* Decision information when authorized and available

### Security and Visibility

**Status: LOCKED**

The same Review may produce different views depending on authorization.

```text
                    REVIEW
                      │
             ┌────────┴────────┐
             ↓                 ↓
        NORMAL USER       AUTHORIZED LEGAL/ADMIN
             │                 │
      Comparison result   Internal legal context
      Findings            Approval information
      Evidence            Internal comments
      High-level risk     Decisions
      Escalation
```

Normal users can understand contract alignment but must not automatically see confidential internal legal strategy such as:

```text
Preferred: 6 months
Acceptable: 12 months
Approval threshold: >12 months
Unacceptable: Unlimited
```

unless their permissions explicitly allow it.

See [../01-product/WORKFLOWS.md](../01-product/WORKFLOWS.md) for the escalation/review workflow and RBAC concept, and [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md) for the canonical permission matrix.

---

## V1 AI Boundary — Locked Decision

**Status: LOCKED**

LegalMind V1 will remain a deterministic, explainable, versioned, permission-controlled, and auditable legal comparison and workflow system.

### V1 will NOT use

* LLM
* RAG
* Vector database
* Embeddings
* AI-generated legal decisions
* Autonomous legal reasoning

These technologies are explicitly outside the V1 implementation scope.

### V1 WILL use

* Deterministic document parsing
* Clause Library
* Requirements
* Company Standards
* Legal Positions / Rules
* Evidence-based findings
* Versioning
* RBAC / authorization
* Audit trail
* Human legal review
* Human legal approval

### Why this is locked

The goal of V1 is to prove the core legal workflow and produce results that are explainable and auditable before introducing AI complexity.

The system should first establish a reliable foundation for:

```text
Contract Upload
      ↓
Document Parsing
      ↓
Clause Identification
      ↓
Clause Library
      ↓
Requirement Comparison
      ↓
Company Standard
      ↓
Legal Position / Rules
      ↓
Finding
      ↓
Evidence
      ↓
User View / Escalation
      ↓
Authorized Legal Review
      ↓
Decision
      ↓
Optional Customization
```

### Post-V1 AI direction

After V1 is working in real-world usage, actual limitations will determine whether AI capabilities are justified.

Potential future progression:

```text
V1
Deterministic LegalMind
        ↓
Real-world usage
        ↓
Identify actual limitations
        ↓
V2
Semantic Search / Embeddings (if justified)
        ↓
LLM assistance (if justified)
        ↓
Future
RAG + LLM + advanced legal intelligence (if justified)
```

AI should be added only when a demonstrated V1 problem requires it. It should not be introduced merely because LegalMind is a legal application.

### Architectural principle for future AI

If AI is introduced after V1, it should sit **on top of the V1 foundation**, not replace it.

The following V1 components should remain authoritative:

* Clause Library
* Requirements
* Company Standards
* Legal Positions
* Reviews
* Evidence
* Version history
* RBAC
* Audit trail

Future AI may assist with language understanding, semantic matching, retrieval, or other clearly defined tasks, but it must not silently become the source of truth for company legal policy or final legal decisions.

### Hard V1 constraint

**Status: LOCKED**

> **Do not introduce LLM, RAG, vector database, embeddings, or AI-generated legal decisions into LegalMind V1 unless this locked decision is explicitly revisited and changed.**

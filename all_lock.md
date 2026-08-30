# LegalMind V1 — Steps 1–5 Decisions

**Status:** Working specification
**Progress:** Steps 1–5
**Purpose:** Source of truth for the decisions made so far. This is not yet the complete V1 specification.

---

## Step 1 — LegalMind V1 Goal

LegalMind V1 will store the organization's legal documents and approved legal standards, compare a selected counterparty contract against those standards, identify:

- Matches
- Missing clauses/requirements
- Deviations
- Conflicts

It will provide supporting evidence, risk classification, human review, escalation, legal decision tracking, and structured reporting.

### V1 does NOT require

- LLM
- AI chat
- Vector database
- Autonomous legal decisions
- AI-generated legal advice

### Core example

Company standard: **Liability = 6 months**

Counterparty contract: **Liability = Unlimited**

LegalMind should identify:

```text
Finding: Limitation of Liability
Result: Conflict
Risk: High
Evidence: Relevant contract clause
Status: Requires review
```

The system identifies and structures the issue. An authorized human makes the legal decision.

### Contract customization

An approved deviation may optionally lead to a customized contract version.

**Important:** approving a deviation does NOT automatically modify the contract.

```text
Finding
  ↓
Authorized Legal Decision
  ↓
Approved Exception
  ↓
Optional: Create Customized Contract
  ↓
Human reviews/accepts proposed change
  ↓
New Contract Version
```

The company's standard legal position remains unchanged.

---

## Step 2 — Contract Upload & User Workflow

A normal business user may have a counterparty contract and want to check whether it aligns with the organization's standards.

Therefore, uploading is not restricted only to Legal users.

### Normal User can

- Upload a counterparty contract
- Run a comparison
- View the comparison
- View findings
- Escalate the contract/finding for review

### Normal User cannot

- Approve a legal deviation
- Reject a legal deviation
- Change the organization's legal position
- Customize/finalize a contract
- Change approval rules

### Document metadata

LegalMind should store:

- Document name
- Document type
- Counterparty
- Version
- Effective date, if available
- Status (Draft / Active / Superseded)
- Uploaded by
- Upload timestamp

### Original document preservation

The original uploaded file must remain unchanged. Any customized contract is a separate version/document.

### Metadata extraction

Where information can be safely extracted using deterministic document parsing, the system may suggest metadata instead of requiring manual entry.

No LLM is required for this V1 behavior.

---

## Step 3 — RBAC and Permissions

LegalMind should use **RBAC (Role-Based Access Control)**.

Conceptually:

```text
User
  ↓
Role
  ↓
Permissions
  ↓
Authorization Check
  ↓
Action
```

Job title and application role remain separate.

Example:

```text
Department = Sales
Role = User
```

or:

```text
Department = Legal
Role = Reviewer
```

### Proposed technical roles

- `Super Admin`
- `Admin`
- `Reviewer`
- `User`
- `Viewer`
- `Auditor`

### Working permission groups

These are a draft and are NOT yet the final production matrix:

```text
Documents
- View
- Upload
- Edit
- Delete
- Download

Comparison
- Create
- View

Findings
- View
- Review
- Comment

Escalation
- Create

Legal Decision
- Approve
- Reject
- Request Changes

Customization
- Customize
- Finalize

Legal Positions
- View
- Create
- Edit
- Delete

Reports
- View
- Generate

Administration
- Manage Users
- Manage Roles
- Manage Settings

Audit
- View
```

### Critical rule

A normal `User` does **not** have legal decision permissions.

Their workflow is:

```text
Upload
  ↓
Compare
  ↓
View
  ↓
Escalate
```

---

## Step 4 — Review, Escalation & Legal Authority

### Confirmed principle

A normal User can only:

- Compare
- View
- Escalate

A normal User cannot make a legal decision.

### Workflow

```text
User
  ↓
Upload Contract
  ↓
Run Comparison
  ↓
View Findings
  ↓
Escalate if needed
  ↓
Reviewer / Authorized Legal Authority
  ↓
Legal Decision
```

### Escalation is not approval

An escalation means:

> "This requires authorized review."

It does not mean:

> "I approve this deviation."

Example:

```text
ESC-0001

Contract:
ABC Technologies MSA

Finding:
Unlimited Liability

Risk:
High

Raised by:
User A

Reason:
Please review this deviation.

Status:
Pending Review
```

### Review vs Legal Approval

**Review** means examining the contract, clause, company standard, comparison, evidence, risk, and comments.

**Legal approval** means the organization authorizes a specific deviation/exception.

These are separate authorities.

### Admin vs legal approval authority

`Admin` is a **system role**.

Being an Admin does **not** automatically grant legal approval authority.

Approval authority is a separate permission/capability that can be assigned to specific Admins.

Example:

```text
Admin A
- System administration: YES
- Legal approval: NO

Admin B
- System administration: YES
- Legal approval: YES
```

Later we may introduce granular approval limits, but those are not finalized yet.

---

## Step 5 — Comparison Sources

LegalMind V1 should compare a counterparty contract against:

1. The organization's standard documents
2. The organization's internal legal positions

Conceptually:

```text
                 Counterparty Contract
                         ↓
                Comparison Engine
                    /         \
                   /           \
                  ↓             ↓
       Standard Documents   Legal Positions
                                  ↓
                           Internal Rules
                                  ↓
                              Findings
```

### Why both?

A standard document provides the organization's standard wording/document.

A legal position provides the organization's internal tolerance and decision framework.

Example internal position:

```text
Topic:
Limitation of Liability

Preferred:
6 months

Acceptable:
Up to 12 months

Requires approval:
More than 12 months

Unacceptable:
Unlimited
```

This is useful to the comparison engine but contains internal legal strategy.

---

## Legal Position Visibility

Internal Legal Positions are **permission-controlled information**.

A normal User must not automatically see:

- Preferred positions
- Acceptable thresholds
- Approval thresholds
- Unacceptable positions
- Internal negotiation strategy
- Internal legal comments

### Normal User view

```text
Customer MSA
      ↓
Comparison
      ↓
Finding

Liability clause:
12 months

Status:
Deviation detected

Risk:
Requires Legal Review

[Escalate to Legal]
```

### Authorized Admin view

An authorized Admin can see the internal context needed for the decision:

```text
Customer position:
12 months

Organization position:
6 months

Internal tolerance:
Up to 12 months

Approval requirement:
...

Risk:
...

[Approve]
[Reject]
[Request Changes]
```

### Security principle

The system must separate:

> **What the comparison engine knows**

from:

> **What each user is authorized to see.**

Internal legal strategy must not leak to ordinary users or counterparties.

---

# Confirmed Principles After Steps 1–5

1. LegalMind V1 is primarily a deterministic legal-document comparison and workflow system.
2. No LLM is required for V1.
3. Users can upload and compare counterparty contracts according to permissions.
4. Normal Users can compare, view, and escalate only.
5. Normal Users cannot make legal decisions.
6. Legal approval requires explicitly assigned authority.
7. Admin is a system role and does not automatically imply legal approval authority.
8. Approval of a deviation does not change the company standard.
9. Contract customization is optional and occurs only after authorized approval.
10. Customized contracts are separate versions and the original contract remains preserved.
11. Comparison can use both standard company documents and internal legal positions.
12. Internal legal positions are permission-controlled and must not be exposed to ordinary users or counterparties.
13. Product requirements must be decided before technical implementation.
14. Business job titles and application authorization roles remain separate.

---

# Decisions Still Open

These are intentionally not finalized yet:

- Exact permission matrix for every role
- Exact legal approval thresholds
- Whether Reviewer can approve anything or only review/escalate
- Risk classification rules
- Exact document taxonomy
- Detailed comparison rules
- Data model
- Authentication implementation
- Existing authentication/API integration
- Technology stack
- UI/UX
- Document parsing implementation

These will be decided in later steps rather than assumed early.

---

# Development Discipline

For LegalMind:

- One step at a time
- No silent assumptions
- Confirm requirements before implementation
- Separate confirmed decisions from recommendations
- Challenge incorrect or unsafe approaches
- Prefer least privilege
- Preserve auditability
- Keep V1 simple
- Do not add LLM/AI infrastructure unless a real V1 requirement justifies it
- Do not allow Claude Code to invent legal/business rules

---

**Next:** Step 6 will be defined only after Steps 1–5 are accepted as the current source of truth.

---

# Step 6 — Document Types vs Legal/Regulatory References

These are two different concepts.

## Document Type

Document Type answers:

> "What kind of document is this?"

Initial V1 types:

- MSA — Master Services Agreement
- NDA — Non-Disclosure Agreement
- TOS — Terms of Service
- SLA — Service Level Agreement
- DPA — Data Processing Agreement
- AUP — Acceptable Use Policy
- Privacy Policy
- Order Form
- Amendment / Addendum
- Other

A document can be classified by source:

```text
Document Type = MSA
Source = Organization
```

or:

```text
Document Type = MSA
Source = Counterparty
```

## Legal / Regulatory Reference

A Legal/Regulatory Reference answers:

> "What law, regulation, statute, or legal requirement may be relevant?"

Examples:

- DPDP Act
- Information Technology Act
- GDPR
- Sector-specific regulations

These are not contract types.

Example:

```text
ABC MSA
 │
 ├── Compared with → LeapSwitch Standard MSA
 │
 └── Relevant to → DPDP Act
```

---

# Step 7 — Clause-Level Comparison

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

The detailed matching rules remain a later decision.

---

# Step 8 — Complete Comparison + Findings

## Locked decision

**Comparison = complete alignment report.**

LegalMind must not show only problems. The user should understand:

- What matches
- What differs
- What is missing
- What conflicts
- Which clauses were reviewed
- Evidence supporting the result

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

## Finding

A **Finding** is a clause/requirement-level comparison result.

A Finding is not necessarily a problem.

It can be:

```text
MATCH
DEVIATION
CONFLICT
MISSING
```

## Finding is separate from Legal Decision

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

## Evidence

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

# Step 9 — Versioned Review, Standards & Reports

## Central record: Review

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

## Historical traceability

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

- Contract version
- Comparison standard/version
- Legal Position version, where applicable
- Reviewer/creator
- Timestamp
- Review status
- Findings
- Evidence
- Escalations
- Decisions
- Audit history

---

## Standard Maintenance Inside LegalMind

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

## Versioning rule

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

---

## Legal Positions are also versioned

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

---

## Standard Document vs Structured Legal Rule

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

---

## Report

The Report is generated from the Review:

```text
LEGALMIND REVIEW
      │
      ├── Interactive Review Screen
      │
      └── Report
```

The report should summarize:

- Contract information
- Contract version
- Comparison source/version
- Overall alignment
- Match/deviation/conflict/missing counts
- Clause-level findings
- Evidence references
- High-level risk
- Review/escalation status
- Decision information when authorized and available

---

## Security and Visibility

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

---

# Locked Principles Through Step 9

1. LegalMind V1 is primarily a deterministic legal-document comparison and workflow system.
2. No LLM is required for V1.
3. Users can upload and compare counterparty contracts according to permissions.
4. Normal Users can compare, view, and escalate only.
5. Normal Users cannot make legal decisions.
6. Legal approval requires explicitly assigned authority.
7. Admin is a system role and does not automatically imply legal approval authority.
8. Approval of a deviation does not change the company standard.
9. Contract customization is optional and occurs only after authorized approval.
10. Customized contracts are separate versions and the original contract remains preserved.
11. Comparison can use both standard company documents and internal legal positions.
12. Internal legal positions are permission-controlled and must not be exposed to ordinary users or counterparties.
13. Product requirements are decided before technical implementation.
14. Business job titles and application authorization roles remain separate.
15. Document Type and Legal/Regulatory Reference are separate concepts.
16. Comparison is clause/requirement-level, not only document-level.
17. Comparison shows the complete alignment picture, not only conflicts.
18. Finding is a clause/requirement-level comparison result.
19. Finding can be MATCH, DEVIATION, CONFLICT, or MISSING.
20. Finding is separate from Legal Decision.
21. Findings should have traceable evidence.
22. Review is the central historical record of a comparison.
23. Report is generated from the Review and is not the source of truth.
24. Contract versions are preserved.
25. Standard/legal-position versions are preserved.
26. Authorized Admin/Legal users maintain standards inside LegalMind.
27. Small internal standard/rule changes can be made inside LegalMind without re-uploading a whole contract.
28. Changes are created as a Draft/version and require the appropriate approval/publication flow.
29. Only the active published version affects new comparisons.
30. Existing Reviews never silently change when standards are updated.
31. Every Review records the exact standard/legal-position versions used.
32. Historical reviews remain reproducible and auditable.
33. Draft standards must never silently affect comparisons.
34. Internal legal strategy is permission-controlled.
35. LegalMind must not automatically declare a contract legally approved merely because it aligns with a standard.

---

# Not Yet Locked

- Exact permission matrix for every role
- Exact legal approval thresholds
- Whether Reviewer can approve anything or only review/escalate
- Risk classification rules
- Detailed comparison rules
- Clause identification/mapping mechanism
- Data model
- Authentication implementation
- Existing authentication/API integration
- Technology stack
- UI/UX
- Document parsing implementation
- Whether/where LLM could be useful in a future version
- Exact customization workflow
- Exact audit-log schema
- Export formats and delivery
- Regulatory reference workflow

---

# Next Step

**Step 10 — Clause Identification & Clause Mapping**

The next question is:

> How does LegalMind reliably determine that differently worded provisions in two contracts refer to the same legal topic/requirement?

Example:

```text
Customer:
"Provider's liability shall not exceed..."

LeapSwitch:
"The aggregate liability of the parties..."
```

Both may represent **Limitation of Liability**, but the wording is different.

Step 10 will define this comparison problem before choosing implementation technology or assuming an LLM.

---

# V1 AI Boundary — Locked Decision

**Status: LOCKED**

LegalMind V1 will remain a deterministic, explainable, versioned, permission-controlled, and auditable legal comparison and workflow system.

## V1 will NOT use

- LLM
- RAG
- Vector database
- Embeddings
- AI-generated legal decisions
- Autonomous legal reasoning

These technologies are explicitly outside the V1 implementation scope.

## V1 WILL use

- Deterministic document parsing
- Clause Library
- Requirements
- Company Standards
- Legal Positions / Rules
- Evidence-based findings
- Versioning
- RBAC / authorization
- Audit trail
- Human legal review
- Human legal approval

## Why this is locked

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

## Post-V1 AI direction

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

## Architectural principle for future AI

If AI is introduced after V1, it should sit **on top of the V1 foundation**, not replace it.

The following V1 components should remain authoritative:

- Clause Library
- Requirements
- Company Standards
- Legal Positions
- Reviews
- Evidence
- Version history
- RBAC
- Audit trail

Future AI may assist with language understanding, semantic matching, retrieval, or other clearly defined tasks, but it must not silently become the source of truth for company legal policy or final legal decisions.

## Hard V1 constraint

> **Do not introduce LLM, RAG, vector database, embeddings, or AI-generated legal decisions into LegalMind V1 unless this locked decision is explicitly revisited and changed.**

---

# Step 17 — Comparison Engine (LOCKED)

## Locked Decision

LegalMind V1 will use a **layered, deterministic comparison model**. The comparison engine must not directly expose or embed confidential internal Legal Position thresholds in the normal user-facing comparison result.

The V1 comparison flow is:

```text
1. Identify clause
        ↓
2. Map to Clause Library
        ↓
3. Extract structured provision
        ↓
4. Evaluate Requirement
        ↓
5. Compare with Company Standard
        ↓
6. Create Finding
        ↓
7. Authorized Legal evaluation
```

### Locked rules

- V1 comparison is deterministic; no LLM, RAG, vector database, embeddings, or AI-generated legal decisions.
- Clause identification/mapping is a distinct step from requirement evaluation.
- Customer provisions should be normalized into structured values where applicable before comparison.
- Requirement evaluation is separate from comparison with the Company Standard.
- Company Standard comparison is separate from the confidential Internal Legal Position.
- Normal users receive findings and permitted evidence, but not confidential internal Legal Position thresholds or negotiation boundaries.
- Authorized Legal users may access the internal evaluation according to their permissions.
- A Finding is not a Legal Decision.
- Legal Position is applied only within the authorized Legal workflow where required.
- The comparison engine must preserve evidence linking the finding to the customer provision and applicable company standard.

## Example

```text
Customer provision
        ↓
Clause: Limitation of Liability
        ↓
Structured value: 12 months
        ↓
Requirement: Liability must be capped
        ↓
Requirement result: PASS
        ↓
Company Standard: 6 months
        ↓
Standard comparison: DIFFERENT
        ↓
Finding: Deviation Detected
```

The normal user sees the finding and evidence, not the organization's internal acceptable/approval thresholds.

---

# Step 17 — Implementation Example for Claude Code

The following example is included to make the locked comparison architecture concrete for implementation. It is illustrative only; it does not introduce new business rules beyond the locked decisions above.

```text
Customer Contract
"The Provider's total liability shall not exceed the fees paid
 during the previous twelve months."
        ↓
1. Identify clause
   → Limitation of Liability
        ↓
2. Map to Clause Library
   → Clause ID: CL-003
        ↓
3. Extract structured provision
   → cap_exists = true
   → cap_value = 12
   → cap_unit = months
        ↓
4. Evaluate Requirement
   Requirement: Liability must have a cap
   → PASS
        ↓
5. Compare with Company Standard
   Company Standard: 6 months
   Customer provision: 12 months
   → DIFFERENT
        ↓
6. Create Finding
   → Type: Deviation
   → Evidence: Customer MSA §12.3
   → Company reference: Standard MSA applicable clause
        ↓
7. Authorized Legal evaluation
   → Internal Legal Position may be considered here
   → Normal User does not see confidential thresholds
```

Implementation interpretation:

- The system should not jump directly from raw contract text to a legal decision.
- Each stage should produce an explicit, auditable intermediate result.
- The structured extraction should retain the source location/evidence from which the value was extracted.
- The Requirement result and Standard comparison result should remain separately traceable.
- The Finding should reference both the customer evidence and the applicable company reference.
- The Legal Position should not be returned as part of the ordinary user-facing finding payload unless the requesting user is authorized to view it.
- The example does not authorize any automatic approval or customization.

---

# Step 18 — Finding Types (LOCKED)

## Locked Decision

LegalMind V1 will use exactly these five core finding types:

- `MATCH`
- `DEVIATION`
- `MISSING`
- `ADDITIONAL`
- `UNMAPPED`

## Locked Rules

1. `MATCH` means the provision satisfies the configured comparison criteria.
2. `DEVIATION` means the provision exists but differs from the Company Standard.
3. `MISSING` means an expected configured provision was not found.
4. `ADDITIONAL` means an extra provision exists without a corresponding configured standard requirement.
5. `UNMAPPED` means a provision was detected but could not be reliably mapped to the Clause Library.
6. A finding type does not itself determine legal acceptability.
7. `DEVIATION` does not automatically mean unacceptable.
8. `ADDITIONAL` does not automatically mean unacceptable.
9. `UNMAPPED` must not be silently classified as a match.
10. Every finding must retain evidence showing where the relevant customer provision came from.
11. Legal decisions remain a separate authorized workflow.

## Example

```text
Customer Contract
       ↓
Clause Identification
       ↓
Clause Library
       ↓
Structured Extraction
       ↓
Requirement Evaluation
       ↓
Company Standard Comparison
       ↓
Finding Type
       │
       ├── MATCH
       ├── DEVIATION
       ├── MISSING
       ├── ADDITIONAL
       └── UNMAPPED
       ↓
Evidence
       ↓
User View / Escalation
       ↓
Authorized Legal Decision
```

### Example findings

```text
Confidentiality
→ MATCH

Limitation of Liability
→ DEVIATION

Data Protection
→ MISSING

Audit Rights
→ ADDITIONAL

Unrecognized legal provision
→ UNMAPPED
```

These finding types describe comparison results only. They do not expose or encode confidential internal Legal Position thresholds.

---

---

# Step 20 — Clause Library & Requirement Structure (LOCKED)

## Locked Decision

LegalMind V1 will maintain a centralized Clause Library. A Clause represents a legal concept; a Requirement defines what must be satisfied for that concept.

```text
Clause
  ↓
Requirement
  ↓
Company Standard
  ↓
Pre-approved Legal Rule (if one exists)
  ↓
Legal Decision (if required)
```

### Company Standard

The Company Standard is the organization's default/preferred position. A provision matching it is a `MATCH`.

### Pre-approved Legal Rule

A Pre-approved Legal Rule is an explicitly authorized Legal/Admin rule defining an acceptable variation from the Company Standard. LegalMind must never invent this rule, and not every Clause needs one.

Example:

```text
Company Standard: 6 months
Pre-approved: up to 12 months
Outside rule: Approval Required
```

### Locked Rules

1. Company Standard is the default organizational position.
2. A deviation is a comparison finding, not automatically a risk rating.
3. A Pre-approved Legal Rule may define an explicitly authorized acceptable variation.
4. Not every Clause requires a Pre-approved Legal Rule.
5. Outside an applicable Pre-approved Legal Rule, case-specific Legal approval is required.
6. If no rule exists, LegalMind must not invent an interpretation.
7. Legal Decisions remain separate from automated comparison and rule evaluation.
8. Normal users cannot approve deviations or customizations.
9. Clause, Requirement, Company Standard, and Pre-approved Legal Rule are separate and versioned.
10. Historical Reviews retain the exact configuration/rule versions used.
11. Used Clause Library entries are not physically deleted; they may be deprecated.
12. Document Type and Legal/Regulatory Reference remain separate concepts.

### Example — Limitation of Liability

```text
Company Standard: 6 months
Customer: 12 months
→ DEVIATION
→ Within pre-approved rule
→ No case-by-case approval

Customer: 18 months
→ DEVIATION
→ Outside pre-approved rule
→ APPROVAL REQUIRED
→ Authorized Legal decision
```

This example is illustrative only. Actual Legal Rules must be configured by authorized Legal/Admin users.

---

# Step 21 — Admin/Legal Configuration (LOCKED)

## Locked Decision

Authorized Legal/Admin users manage the Clause Library and related legal configuration through a dedicated configuration workflow.

### Configuration structure

A Clause can contain or reference:

- Requirements
- Company Standard
- Optional Pre-approved Legal Rule

Example:

```text
Clause:
Limitation of Liability

Requirement:
A liability cap must exist.

Company Standard:
6 months

Pre-approved Legal Rule:
Up to 12 months = acceptable

Outside Rule:
Approval Required
```

## Locked Rules

1. Authorized Legal/Admin users manage the Clause Library through a dedicated configuration workflow.
2. A Clause contains its Requirements, Company Standard reference, and optional Pre-approved Legal Rule.
3. Pre-approved Legal Rules are optional; not every Clause needs one.
4. Normal Users cannot modify legal configuration.
5. Legal configuration changes create a new version rather than overwriting historical configuration.
6. Historical Reviews continue using the configuration version that existed when they were reviewed.
7. Legal Rules are controlled legal configuration, not ordinary application settings.
8. Exact role/permission ownership for configuration actions will be defined separately.

## Example Version Change

```text
Limitation of Liability Configuration v1
Company Standard = 6 months

        ↓ Legal configuration change

Limitation of Liability Configuration v2
Company Standard = 12 months
```

Existing reviews remain tied to v1; new reviews use v2.

---

# Step 22 — Review Lifecycle (LOCKED)

## Locked Decision

A Review has its own workflow lifecycle, separate from Findings and Legal Decisions.

### Core workflow

```text
USER
  │
  │ Upload
  ▼
REVIEW
  │
  ▼
COMPARISON
  │
  ▼
FINDINGS
  │
  ├─────────────── No Legal action needed
  │                       ↓
  │                   COMPLETED
  │
  └── Escalate
          ↓
     LEGAL REVIEW
          ↓
     LEGAL DECISION
          │
          ├── Require Standard
          │
          └── Approve Customization
                    ↓
              Contract Exception
                    ↓
                 RESOLVED
```

## Locked Rules

1. A Review has its own lifecycle/status separate from Legal Decisions.
2. Normal Users can upload contracts and create Reviews.
3. Normal Users can view comparison results and evidence.
4. Normal Users can escalate findings.
5. Normal Users cannot approve findings, deviations, customizations, or contracts.
6. Legal decisions are available only to authorized Legal users.
7. A Legal Decision is separate from a Finding.
8. An approved customization creates a contract-specific exception.
9. An exception does not modify the Company Standard.
10. An exception does not automatically modify the Legal Rule.
11. V1 records approved customizations but does not automatically rewrite DOCX/PDF.
12. Historical Reviews retain their original contract/configuration versions.
13. `RESOLVED` means the workflow issue has an authorized resolution; it does not necessarily mean the contract exactly matches the Company Standard.
14. A new contract version receives a new Review.
15. A Review can complete without Legal escalation when no finding requires Legal action.

## Recommended V1 Review Statuses

```text
DRAFT
  ↓
PROCESSING
  ↓
READY_FOR_REVIEW
  ↓
IN_REVIEW
  ↓
ESCALATED
  ↓
LEGAL_REVIEW
  ↓
DECISION_REQUIRED
  ↓
RESOLVED
```

A review with no required Legal action may proceed from user review to `COMPLETED`.

## Example — Approved Customization

```text
Company Standard:
6 months

Customer Contract:
18 months

Finding:
DEVIATION

Legal Decision:
Approve Customization

Exception:
18 months
Scope: ABC MSA v1 only

Review:
RESOLVED
```

The Company Standard remains 6 months. The exception is contract-specific and does not become a new Company Standard.

## Important Distinction

`RESOLVED` does not mean `MATCH`.

Example:

```text
Finding:
DEVIATION

Legal Decision:
Approved Customization

Review:
RESOLVED
```

The contract still differs from the Company Standard; the deviation has simply received an authorized resolution.

### Step 22 Clarification — RESOLVED ≠ MATCH (LOCKED)

```text
Company Standard:
Liability cap = 6 months

Customer Contract:
Liability cap = 18 months

Comparison:
DEVIATION

Legal Decision:
Approved Customization for this specific contract

Review Status:
RESOLVED

Company Standard:
Still 6 months
```

`MATCH` means the customer provision aligns with the Company Standard.

`RESOLVED` means the deviation or workflow issue has received an authorized resolution. It does not mean the customer provision now matches the Company Standard.

---

# Step 23 — Roles & Permission Matrix (LOCKED)

## Locked Decision

LegalMind V1 will use four base roles:

- User
- Legal Reviewer
- Legal Admin
- Super Admin

Roles provide the baseline permission set, while explicit permissions and resource scope provide finer control.

## Locked Rules

1. User cannot make Legal Decisions.
2. User cannot approve contract-specific customizations.
3. User can upload contracts, create Reviews, view permitted comparison results/evidence, and escalate findings.
4. Legal Reviewer handles contract/legal review.
5. Legal Admin manages controlled Legal configuration.
6. Super Admin manages platform, users, roles, and permissions.
7. Super Admin does not automatically have Legal authority.
8. Legal Decision authority is an explicit permission.
9. Approval of contract-specific customization is an explicit permission.
10. Legal configuration permissions are separate from Legal review permissions.
11. Role names alone do not determine resource scope.
12. Permissions support resource scope such as own, assigned, Legal scope, or system scope.
13. Internal Legal Rules are inaccessible to normal Users.
14. User/role administration is separate from Legal configuration.
15. Review visibility/scope is deliberately left for a separate decision before implementation.

## Recommended Permission Model

```text
ROLE
  ↓
PERMISSIONS
  ↓
RESOURCE SCOPE
```

Example:

```text
Legal Reviewer
  + legal.review
  + review.scope = assigned
```

A selected Legal user may additionally have:

```text
legal.decision
legal.approve_customization
```

without automatically receiving Legal configuration permissions.

## Role Summary

```text
USER
- Upload/create Review
- View permitted own Reviews
- View findings/evidence
- Escalate
- No Legal approval
- No Legal configuration

LEGAL REVIEWER
- Legal review
- View assigned/permitted Reviews
- View findings/evidence
- View applicable internal Legal Rules
- Make Legal Decisions when explicitly permitted
- Approve customization when explicitly permitted
- No user/role administration

LEGAL ADMIN
- Legal Reviewer capabilities
- Manage Clause Library
- Manage Requirements
- Configure Company Standards
- Configure Pre-approved Legal Rules
- Version/deprecate Legal configuration
- No automatic platform/user administration

SUPER ADMIN
- Manage users
- Manage roles
- Manage permissions
- Platform/system administration
- Audit/system administration
- No automatic Legal Decision authority
```

## Example

```text
User finds:
Customer Liability = 18 months
Company Standard = 6 months

Finding:
DEVIATION

User:
[View Evidence]
[Escalate to Legal]

User cannot:
[Approve Customization]
```

An authorized Legal user with the explicit approval permission can make the Legal Decision.

A Super Admin without that Legal permission cannot approve the customization merely because they are a Super Admin.

## Important Separation

```text
Legal Review
      ≠
Legal Configuration
      ≠
Platform Administration
```

These responsibilities must remain separately permissioned.

The exact Review visibility model (who can see whose contracts/Reviews) will be defined in a later step.

---

# Step 24 — Review Visibility & Ownership (LOCKED)

## Locked Decision

LegalMind V1 will use an ownership + authorized-scope access model.

Every Review has an owner. The creator is the initial owner unless the Review is explicitly transferred or assigned.

## Locked Rules

1. Every Review has an owner.
2. The Review creator is the initial owner unless explicitly transferred/assigned.
3. A normal User can access their own Reviews.
4. A normal User cannot access another User's Reviews by default.
5. Escalation makes the Review available to the authorized Legal workflow.
6. Legal Reviewer access is controlled by assignment and/or explicit Legal scope.
7. Legal Admin has authorized Legal-scope access but does not automatically have unrestricted platform access.
8. Super Admin does not automatically have access to confidential contract or Legal content.
9. Contract-content access and platform administration are separate permissions.
10. Internal Legal Rules and confidential Legal Decision details are protected from normal Users.
11. A User can see the user-facing outcome of their own Legal review without necessarily seeing confidential internal Legal reasoning or Legal thresholds.
12. Access is based on permission + resource scope, not simply role name.
13. Least-privilege access is the default.
14. Access restrictions must be enforced server-side, not only by hiding UI elements.
15. Access to confidential Legal information must be auditable.
16. A Review may be visible to an authorized Legal Reviewer without transferring ownership from the original User.
17. Legal assignment gives access for Legal work; it does not make the Legal Reviewer the business owner of the Review.
18. A resolved Review remains accessible to its owner according to the same ownership rules, while Legal access remains governed by Legal scope/assignment.

## Example

```text
User A
   │
   │ uploads ABC MSA
   ▼
Review REV-001
Owner = User A
   │
   ▼
Comparison
   │
   ▼
DEVIATION
   │
   │ User A escalates
   ▼
Legal Queue
   │
   │ assigned to
   ▼
Legal Reviewer B
   │
   ▼
Legal Review
   │
   ▼
Approved Customization
   │
   ▼
RESOLVED
```

Access:

```text
User A
✓ Own contract
✓ Own findings/evidence
✓ User-facing resolution

User B
✗ No access by default

Legal Reviewer B
✓ Authorized contract content
✓ Evidence
✓ Findings
✓ Internal Legal evaluation
✓ Legal Decision

Legal Admin
✓ Authorized Legal-scope Reviews
✓ Legal configuration

Super Admin
✓ Platform administration
✗ Legal content unless explicitly granted
```

## Important Separation

```text
Ownership
   ≠
Legal Assignment
   ≠
Platform Administration
```

A Legal Reviewer can be assigned to a Review without becoming its owner.

A Super Admin can administer the platform without automatically gaining Legal content access.

A normal User can own a Review without gaining any Legal approval authority.

---

# Step 25 — Audit Trail & Legal Activity History (LOCKED)

## Locked Decision

LegalMind V1 will maintain an authoritative, append-only Audit Trail separate from the user-facing Activity History.

The purpose is to establish exactly who performed an action, what resource it affected, what changed, when it happened, and what result followed.

## Locked Rules

1. The authoritative Audit Trail is separate from the user-facing Activity History.
2. Audit events are append-only and must not be silently modified or deleted.
3. Every important Legal/workflow action records the authenticated actor.
4. Every Legal Decision records who made it, when, what was decided, and the relevant Review/Finding.
5. Changes to Legal configuration create versioned records and corresponding audit events.
6. Historical Reviews retain the exact configuration versions used when they were performed.
7. Changing a Legal Decision creates a new decision/history event rather than overwriting the previous decision.
8. Clause, Requirement, Company Standard, and Pre-approved Legal Rule changes are auditable.
9. Ownership and Legal-assignment changes are auditable.
10. Permission and role changes are auditable.
11. Findings retain traceability to relevant contract evidence and Company Standard/configuration evidence.
12. Normal Users see an appropriate workflow timeline, not confidential internal Legal information.
13. Authorized Legal/Admin users can access deeper Legal audit information according to permission scope.
14. Super Admin does not automatically gain Legal Decision or confidential Legal content access.
15. Audit access itself is auditable.
16. Any future controlled retention/deletion process for audit records must itself generate an audit event.

## Core Audit Event

Conceptually:

```text
Audit Event

eventId
timestamp
actorId
actorRole
action
resourceType
resourceId
reviewId
findingId              optional
configurationVersion   optional
previousState          optional
newState               optional
reason                 optional
metadata               optional
```

The exact database schema will be determined during implementation.

## Example

```text
User A
  → uploaded contract

System
  → created Review

System
  → generated Finding

User A
  → escalated Finding

Legal Reviewer B
  → reviewed Finding

Legal Reviewer B
  → approved customization

System
  → created contract-specific exception

System
  → resolved Review
```

Each significant event remains in the authoritative Audit Trail.

## Historical Configuration Example

```text
Configuration v1
Liability Standard = 6 months

        ↓

Review REV-001 uses v1

        ↓

Later: Legal Admin changes standard

Configuration v2
Liability Standard = 12 months
```

REV-001 continues to reference v1 and therefore continues to show the original 6-month standard.

## Important Separation

```text
Audit Trail
    ≠
Activity History
    ≠
Legal Decision
```

The Audit Trail records what happened.

The Activity History provides an appropriate user-facing timeline.

The Legal Decision represents the authorized legal outcome.

---

# Step 26 — Document & Contract Versioning (LOCKED)

## Locked Decision

Document identity, Document Version, Review, and Legal Decision are separate but linked records.

A Review is tied to exactly one Document Version and the exact Legal Configuration versions used for that Review.

## Locked Rules

1. A Document and a Document Version are separate concepts.
2. A Review is tied to exactly one Document Version.
3. A Review cannot be silently updated to point to a newer Document Version.
4. A changed contract creates a new Document Version and a new Review.
5. Identical file content does not create a meaningless new version; content fingerprinting should detect duplicates.
6. Filename alone does not determine document version.
7. Historical Reviews remain immutable with respect to the contract version they analyzed.
8. Historical Findings remain attached to their original Review/Document Version.
9. Contract-specific Legal Decisions remain attached to the exact Review/Document Version for which they were made.
10. A Legal Decision or approved customization from an earlier Document Version does not automatically carry forward to a later version.
11. A new Document Version receives a fresh comparison and Legal evaluation where required.
12. Previous Reviews and Legal Decisions may be displayed as historical context, but they do not constitute approval of the new version.
13. LegalMind may show clause-level changes between versions as informational change tracking.
14. Change tracking does not replace the fresh review of the new version.
15. Different Document Types have separate Document identities.
16. Every Review records both the exact Contract/Document Version and the exact Legal Configuration versions used.
17. Contract versioning and Legal configuration versioning operate independently.

## Example

```text
ABC MSA v1
   ↓
Review REV-001
   ↓
Legal approves a contract-specific customization

Customer sends revised contract
   ↓
ABC MSA v2
   ↓
Review REV-002
   ↓
Fresh comparison
   ↓
Fresh Legal evaluation
```

The approval for v1 remains attached to v1 and does not automatically approve v2.

## Historical Context

LegalMind may show:

```text
Previous Review:
REV-001

Previous Decision:
Approved Customization

Current Review:
REV-002

Current Status:
Requires fresh evaluation
```

This provides useful context without treating the old decision as current approval.

## Review Reproducibility

A Review must retain:

```text
Contract Version
       +
Clause/Requirement Version
       +
Company Standard Version
       +
Legal Rule Version
```

This allows LegalMind to reproduce why a particular finding and Legal Decision existed at that point in time.

## Core Rule

```text
OLD CONTRACT
     +
OLD LEGAL APPROVAL
        ≠
NEW CONTRACT
     +
AUTOMATIC APPROVAL
```

Instead:

```text
NEW CONTRACT VERSION
        ↓
NEW REVIEW
        ↓
FRESH COMPARISON
        ↓
FRESH LEGAL EVALUATION
```

---

# Step 27 — Comparison & Finding Generation (LOCKED)

## Locked Decision

LegalMind V1 comparison is deterministic and explainable. V1 will not use an LLM, RAG, vector database, or semantic AI as the Legal decision-maker.

This does not mean simplistic string matching. During the later technical-design phase, LegalMind will select the best appropriate deterministic/NLP algorithms for document parsing, clause segmentation, candidate retrieval, extraction, normalization, matching, and rule evaluation.

## Locked Finding Types

```text
MATCH
DEVIATION
MISSING
CONFLICT
EXTRA
UNABLE_TO_EVALUATE
```

## Locked Rules

1. Comparison operates through structured Requirements and mapped clauses.
2. Every Finding belongs to a specific Review.
3. Every Finding retains traceable evidence.
4. DEVIATION means the customer provision differs from the Company Standard; it does not automatically mean Legal approval is required.
5. CONFLICT means the customer provision directly contradicts a configured required position.
6. MISSING means a required/mapped provision could not be found.
7. EXTRA means an additional provision exists without a corresponding mapped Company Standard requirement; it is not automatically negative.
8. UNABLE_TO_EVALUATE is used when deterministic evaluation cannot establish a reliable result.
9. Finding classification is separate from Legal Rule evaluation.
10. Legal Rule evaluation is separate from the Legal Decision.
11. Legal Decisions are made only by authorized Legal users.
12. Risk/severity is configuration-driven and is not hard-coded solely from Finding type.
13. LegalMind must not invent unsupported contractual values or legal conclusions.
14. The same Contract Version + applicable Company Configuration versions + Legal Rule versions must produce the same deterministic result.
15. Historical Findings retain the exact evidence and configuration versions used to generate them.
16. Multiple independent findings may exist within one Review.
17. The technical implementation must be selected later based on the locked functional requirements; APIs, libraries, algorithms, OCR, database architecture, and application stack are not locked by this step.
18. Candidate retrieval may use appropriate deterministic/NLP techniques, but the final V1 Legal classification and Rule evaluation must remain reproducible and explainable.

## Conceptual Pipeline

```text
Customer Contract
      ↓
Document Parsing
      ↓
Clause Identification
      ↓
Structured Representation
      ↓
Requirement Mapping
      ↓
Company Standard + Legal Rule Evaluation
      ↓
Finding
      ↓
Legal Decision when required
```

## Important Separation

```text
Customer Contract
       ↓
Finding
       ↓
Legal Rule Evaluation
       ↓
Legal Decision
```

A Finding is not itself a Legal Decision.

## Example

```text
Customer:
Liability = 12 months

Company Standard:
Preferred = 6 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required
Unlimited = Unacceptable

Finding:
DEVIATION

Rule Evaluation:
Acceptable

Legal Decision:
Not automatically required
```

---

# Step 28 — Clause & Requirement Mapping (LOCKED)

## Locked Decision

LegalMind V1 maps customer-contract clauses to structured Company Requirements before applying Company Standards and Legal Rules.

A clause is not mapped directly to a Legal conclusion.

## Locked Requirement Model

Each Requirement should conceptually contain:

```text
Requirement ID
Document Type
Clause / Topic
Company Standard
Legal Rule
Required / Optional
Version
```

Example:

```text
LIABILITY-001

Document Type:
MSA

Clause:
Limitation of Liability

Company Standard:
6 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required
Unlimited = Unacceptable
```

## Locked Mapping States

```text
CONFIRMED
AMBIGUOUS
UNRESOLVED
```

### CONFIRMED

The system has sufficient deterministic evidence to map the clause to the Requirement.

### AMBIGUOUS

More than one plausible mapping exists and LegalMind must not silently choose one.

### UNRESOLVED

The system cannot establish the mapping reliably.

An unresolved mapping must not produce an invented Legal conclusion.

## Locked Rules

1. One clause may map to multiple Requirements.
2. One Requirement may be supported by multiple clauses.
3. Explicit document cross-references should be resolved where deterministically possible.
4. If a cross-reference cannot be safely resolved, LegalMind must not guess.
5. A required Requirement with no mapped provision may produce a MISSING Finding.
6. An ambiguous or unresolved mapping may produce UNABLE_TO_EVALUATE rather than a guessed classification.
7. Every mapping retains evidence showing the relevant customer clause and Requirement.
8. Requirement mapping is separate from Company Standard evaluation.
9. Company Standard evaluation is separate from Legal Rule evaluation.
10. Legal Decision remains separate from all automated mapping/evaluation.
11. Administrators can change individual Requirements/Standards/Rules without replacing the entire source contract document.
12. Changes to Requirements/Standards/Rules create new configuration versions.
13. Existing Reviews continue to reference the exact configuration versions used at review time.
14. New Reviews use the currently active applicable configuration versions.
15. A mapping must be reproducible from the relevant Document Version and configuration versions.
16. The technical algorithm used for candidate retrieval/mapping will be selected later during technical design; V1 behavior is locked now.

## Conceptual Pipeline

```text
Customer Clause
      ↓
Candidate Requirement(s)
      ↓
Mapping Status
      ↓
CONFIRMED / AMBIGUOUS / UNRESOLVED
      ↓
Company Standard Evaluation
      ↓
Legal Rule Evaluation
      ↓
Finding
      ↓
Legal Decision when required
```

---

# Step 29 — Admin Legal Configuration Workflow

## Objective

Define how authorized Legal administrators maintain the structured LegalMind configuration without editing or replacing the underlying contract documents.

The configuration is the controlled source of LegalMind's comparison behavior.

## Core Principle

```text
Customer Contract
        ≠
Company Legal Configuration
```

The customer contract is evidence being reviewed.

The Legal Configuration defines what LegalMind should compare it against.

Therefore, changing a Company Standard or Legal Rule does not modify historical contracts or historical Reviews.

## Admin Configuration Areas

The Admin Legal Configuration area should manage:

1. Document Types
2. Requirements
3. Company Standards
4. Legal Rules
5. Clause/Requirement mappings
6. Requirement status (active/inactive)
7. Configuration versions
8. Change history

## Example

An authorized Legal Admin wants to change:

```text
Limitation of Liability
Company Standard:
6 months → 12 months
```

They should be able to:

```text
Legal Configuration
      ↓
Requirements
      ↓
LIABILITY-001
      ↓
Edit Company Standard
      ↓
6 months → 12 months
      ↓
Save as new version
```

They should NOT need to upload the complete MSA again.

## Version Behavior

Before change:

```text
LIABILITY-001
Configuration v1
Standard = 6 months
```

After change:

```text
LIABILITY-001
Configuration v2
Standard = 12 months
```

Historical Reviews continue using v1.

New Reviews use v2.

## Draft → Review → Publish

Recommended workflow:

```text
Draft
  ↓
Review
  ↓
Publish
  ↓
Active
```

A configuration change should not become active merely because an Admin typed a new value.

The authorized Legal workflow should explicitly publish it.

## Effective Date

Every published configuration version should have an effective timestamp.

Conceptually:

```text
Version:
v2

Published:
2026-08-20 11:42

Effective:
2026-08-20 11:42
```

The exact scheduling capability can be decided during technical design; V1 should at minimum support immediate activation upon publish.

## Historical Integrity

A configuration version that has already been used by a Review must remain available as historical data.

It should not be overwritten.

Example:

```text
v1
Liability = 6 months
        ↓
Used by REV-001
        ↓
Cannot be overwritten

v2
Liability = 12 months
        ↓
Used by new Reviews
```

## Deactivation

If a Requirement or Rule is no longer applicable:

```text
ACTIVE
   ↓
DEPRECATED / INACTIVE
```

It should not be hard-deleted if historical Reviews reference it.

Historical references must continue to resolve.

## Permission

Only authorized Legal users with the appropriate Legal Configuration permission can:

- create configuration drafts
- edit drafts
- publish versions
- deactivate/deprecate configuration
- manage Requirements
- manage Company Standards
- manage Legal Rules

A normal User cannot modify Legal Configuration.

A Super Admin does not automatically receive Legal Configuration authority merely because they are a Super Admin.

## Audit

Every configuration change must generate an Audit Trail event containing, at minimum:

```text
Actor
Action
Configuration item
Previous version
New version
Timestamp
Reason, when provided
```

## Important Separation

```text
EDIT
  ↓
DRAFT

PUBLISH
  ↓
ACTIVE

DEPRECATE
  ↓
NO LONGER USED FOR NEW REVIEWS
```

Editing a draft must not affect active Reviews.

Publishing a new version must not rewrite historical Reviews.

Deprecating a configuration item must not break historical Review references.

---

# Step 29 — Admin Legal Configuration Workflow (LOCKED)

## Locked Decision

Legal Configuration is a separate, structured control layer from uploaded contract documents.

Authorized Legal users manage Requirements, Company Standards, Legal Rules, Document Types, and mappings without replacing the underlying MSA/NDA or other source documents.

## Locked Rules

1. Legal Configuration is separate from uploaded contract documents.
2. Authorized Legal users manage Requirements, Company Standards, Legal Rules, Document Types, and mappings through structured configuration.
3. Individual configuration items can be changed without uploading/replacing the entire source document.
4. Configuration changes create new versions; existing versions are never silently overwritten.
5. Configuration changes follow:
   `Draft → Legal Review → Publish → Active`
6. Consequential Legal configuration changes require an independent authorized Legal approval before publication.
7. The person who drafts a consequential change should not be the sole person who approves/publishes it.
8. A Review captures/snapshots the exact applicable configuration versions when analysis begins.
9. A configuration published during an already-running Review does not change that Review.
10. Historical Reviews never silently recalculate against newer configuration versions.
11. A new/current evaluation uses the currently active configuration and should be represented as a new Review/re-analysis context.
12. Incorrect or superseded configurations are deprecated rather than deleted.
13. Historical Reviews continue resolving their original configuration versions.
14. Correcting an already-published configuration creates a new version; it does not rewrite the old version.
15. Company Standard and Legal Rule remain separate concepts.
16. Requirements can be marked Active or Deprecated.
17. Every configuration change, approval, publication, and deprecation generates an Audit Trail event.
18. Configuration changes record the actor, previous version, new version, timestamp, and reason where applicable.
19. Super Admin does not automatically receive Legal Configuration authority.
20. The configuration system supports individual clause/Requirement changes without requiring replacement of the entire source legal document.

## Example

```text
Current:
LIABILITY-001 v1
Company Standard = 6 months

Legal Configuration Editor
        ↓
Creates v2 Draft
Company Standard = 12 months
        ↓
Independent Legal Review
        ↓
Approved
        ↓
Publish
        ↓
v2 Active
```

Historical Reviews using v1 remain unchanged.

## Running Review Example

```text
10:00
Review starts
Configuration = v1

10:05
Legal publishes v2

Review continues:
Configuration = v1
```

The running Review must not change midway.

## Published Configuration Correction

If an incorrect version was already published:

```text
v2
Incorrect value
   ↓
Deprecated

v3
Correct value
   ↓
Approved
   ↓
Active
```

Reviews that actually used v2 retain v2 as their historical configuration. They are not silently rewritten.

## Core Rule

```text
EDIT
 ↓
NEW DRAFT
 ↓
LEGAL APPROVAL
 ↓
PUBLISH
 ↓
NEW ACTIVE VERSION
```

Never:

```text
EDIT
 ↓
REWRITE HISTORY
```

---

# Step 30 — Review Lifecycle & Status Management (LOCKED)

## Locked Decision

LegalMind V1 separates Review lifecycle, Finding status, Legal Decision, and comparison outcome. A single status field must not be used to represent all of these concepts.

## Locked Review Lifecycle

```text
DRAFT
  ↓
UPLOADED
  ↓
PROCESSING
  ↓
ANALYSIS_COMPLETE
  ↓
LEGAL_REVIEW (when required)
  ↓
RESOLVED
  ↓
CLOSED
```

## Exception States

```text
PROCESSING → ANALYSIS_FAILED

DRAFT / UPLOADED → CANCELLED
```

## Locked Definitions

### DRAFT

Review exists but analysis has not started.

### UPLOADED

The required Document Version has been attached to the Review.

### PROCESSING

The system is actively parsing, segmenting, mapping, evaluating, and generating findings.

### ANALYSIS_COMPLETE

Automated V1 analysis has completed and Findings/Evidence have been generated. This does not mean Legal approval.

### LEGAL_REVIEW

One or more Findings require an authorized Legal decision.

### RESOLVED

All required workflow/Legal decisions have been completed and no required action remains.

`RESOLVED ≠ MATCH`

`RESOLVED ≠ Legal approval of the entire contract`

`RESOLVED ≠ Contract matches the Company Standard`

### CLOSED

The Review has been formally completed after resolution.

### ANALYSIS_FAILED

The automated analysis could not complete. This is distinct from a Finding of `UNABLE_TO_EVALUATE`.

### CANCELLED

A controlled terminal state for an eligible Review that is cancelled before completion.

## Locked Rules

1. Review lifecycle and Finding status are separate concepts.
2. Review status follows a controlled state machine.
3. Users cannot arbitrarily set Review status.
4. The applicable configuration versions are fixed when analysis begins.
5. `ANALYSIS_COMPLETE` means automated analysis finished; it does not mean Legal approval.
6. `LEGAL_REVIEW` is entered only when the configured workflow requires Legal intervention.
7. `RESOLVED` means all required workflow/Legal decisions are complete.
8. `RESOLVED` does not mean MATCH.
9. `RESOLVED` does not mean the contract matches the Company Standard.
10. `RESOLVED` does not mean the contract is universally legally approved.
11. `CLOSED` represents formal workflow completion after resolution.
12. A new contract version creates a new Review rather than silently reopening/replacing the old Review.
13. `ANALYSIS_FAILED` is distinct from a Finding of `UNABLE_TO_EVALUATE`.
14. `CANCELLED` is a controlled terminal state for eligible pre-completion Reviews.
15. Historical Reviews and their status transitions remain auditable.
16. Final summaries should be derived from Findings + Legal Decisions rather than relying on a manually editable final-result field.
17. Each status transition generates an Audit Trail event.

## Conceptual Separation

```text
MATCH / DEVIATION / CONFLICT / MISSING
        ↓
Comparison Finding

Legal Decision
        ↓
Authorized Legal action

RESOLVED
        ↓
Required workflow decisions completed

CLOSED
        ↓
Workflow formally finished
```

## Configuration Snapshot Rule

If a Review begins under configuration v1 and Legal publishes v2 while that Review is processing:

```text
Review starts
    ↓
Configuration v1 captured
    ↓
Legal publishes v2
    ↓
Review continues under v1
```

The Review must not change configuration midway.

## Example

```text
User uploads MSA
      ↓
UPLOADED
      ↓
PROCESSING
      ↓
ANALYSIS_COMPLETE
      ↓
Findings:
- Liability → DEVIATION
- Termination → MATCH
- DPA → MISSING
      ↓
Legal intervention required
      ↓
LEGAL_REVIEW
      ↓
Legal decisions completed
      ↓
RESOLVED
      ↓
CLOSED
```

---

# Step 31 — Legal Decision & Approval Workflow (LOCKED)

## Locked Decision

Automated LegalMind analysis never makes the final Legal Decision. Authorized Legal users make decisions on Findings that require Legal review.

## Locked Decision Vocabulary

```text
ACCEPT_DEVIATION
REQUIRE_COMPANY_STANDARD
APPROVE_CUSTOMIZATION
REJECT
REQUEST_CLARIFICATION
```

## Locked Definitions

### ACCEPT_DEVIATION

The specific deviation is accepted for this Review. It does not change the Company Standard.

### APPROVE_CUSTOMIZATION

A contract-specific customization is authorized for this Review. It does not change the Company Standard.

### REQUIRE_COMPANY_STANDARD

The customer provision should conform to the applicable Company Standard.

### REJECT

The specific contractual position/Finding is rejected. This does not automatically mean the entire contract is rejected.

### REQUEST_CLARIFICATION

Required clarification/action is requested and the relevant workflow remains unresolved until completed.

## Locked Rules

1. Automated analysis does not make final Legal Decisions.
2. Authorized Legal users make decisions on Findings requiring Legal review.
3. Legal Decision types use a controlled vocabulary.
4. `ACCEPT_DEVIATION` applies only to the specific Review/Finding.
5. `APPROVE_CUSTOMIZATION` authorizes only a contract-specific customization.
6. Neither `ACCEPT_DEVIATION` nor `APPROVE_CUSTOMIZATION` changes the Company Standard.
7. Company Standard changes use the Step 29 Legal Configuration versioning workflow.
8. `REQUIRE_COMPANY_STANDARD` requires the customer position to conform to the applicable Company Standard.
9. `REJECT` applies to the specific contractual position/Finding and does not automatically reject the entire contract.
10. `REQUEST_CLARIFICATION` leaves the required workflow unresolved until the clarification/action is completed.
11. Every Legal Decision requires a reason/comment.
12. Every Legal Decision records the decision-maker and timestamp.
13. Contract-specific Legal Decisions are separate from Company Configuration changes.
14. Legal Decision history is immutable; a later change creates a new decision version rather than overwriting the previous decision.
15. Requirements may be configured to require independent second-person approval for consequential contract-specific decisions.
16. Before deciding, Legal must be shown the underlying evidence, Requirement, Company Standard, applicable Legal Rule, and Finding.
17. A Legal Decision resolves the relevant Finding; it does not automatically constitute approval of the entire contract.
18. A Review becomes `RESOLVED` only when all required decisions/actions are complete.
19. All Legal Decisions and changes are included in the Audit Trail.
20. The current decision must always be distinguishable from historical decisions.

## Core Separation

```text
COMPANY STANDARD
       ↓
What the company normally wants

LEGAL RULE
       ↓
How the position is evaluated

FINDING
       ↓
What the customer contract contains

LEGAL DECISION
       ↓
What Legal decides for THIS contract

CONFIGURATION CHANGE
       ↓
Changes what future Reviews compare against
```

## Example

```text
Company Standard:
6 months

Customer Contract:
12 months

Finding:
DEVIATION

Legal Decision:
APPROVE_CUSTOMIZATION

Result:
This contract may use 12 months.

Company Standard:
Remains 6 months.
```

## Decision Change Example

```text
Decision v1:
APPROVE_CUSTOMIZATION
        ↓
Superseded

Decision v2:
REQUIRE_COMPANY_STANDARD
```

Both decisions remain in history; v2 is the current decision.

## Decision Record

Each Legal Decision should retain, at minimum:

```text
Review ID
Finding ID
Decision ID
Decision Type
Decision Maker
Decision Timestamp
Reason
Previous Decision ID, when applicable
Applicable Configuration Version
```

---

# Step 32 — Evidence, Explainability & Audit Trail (LOCKED)

## Locked Decision

Every LegalMind V1 Finding must be traceable to the exact contract evidence, Requirement, Company Standard, Legal Rule, evaluation, and Legal Decision where applicable.

V1 explainability is deterministic and evidence-based. LLM/RAG is not required.

## Locked Rules

1. Every Finding must have traceable evidence or an explicit explainable basis for absence, such as `MISSING`.
2. Evidence references an immutable Document Version.
3. Evidence stores relevant source text whenever extraction permits.
4. Evidence stores document location using multiple references where available: section/clause, page, and stable text location.
5. Every Finding references the applicable Requirement version.
6. Every Finding references the Company Standard/configuration version used.
7. Every Finding references the applicable Legal Rule version.
8. A Finding must be reproducible from its document/configuration/mapping/evaluation chain.
9. Configuration changes never rewrite historical evidence or Findings.
10. `MISSING` Findings retain an explainable basis even though no customer clause exists.
11. `CONFLICT` Findings may contain multiple evidence references.
12. Legal Decisions reference the Finding they resolve.
13. Legal Decisions include decision-maker, timestamp, decision type, reason, and applicable configuration context.
14. Legal Audit Trail and technical application logs are separate concepts.
15. Legal Audit Trail is append-only; historical events cannot be overwritten.
16. Configuration, Finding, Review, and Legal Decision changes generate appropriate Audit events.
17. Historical Reviews remain explainable using the exact document/configuration versions used when the Review was analyzed.
18. The UI allows Legal to inspect the complete Evidence → Requirement → Standard → Rule → Finding → Decision chain.

## Locked Special Cases

### MISSING

A MISSING Finding has no customer clause to quote, but it must still explain the Requirement, expected provision, search/mapping result, applicable configuration, and Finding.

### CONFLICT

A CONFLICT Finding may contain multiple evidence references, with each conflicting provision preserved as evidence.

### AMBIGUOUS / UNRESOLVED

If evidence cannot be mapped reliably, LegalMind must not invent a conclusion. It may produce `AMBIGUOUS`, `UNRESOLVED`, or where appropriate `UNABLE_TO_EVALUATE`.

## Locked Audit Principle

For every Finding, LegalMind must be able to answer:

1. What did the customer contract say?
2. Where exactly did it say it?
3. Which Requirement and Company Standard were used?
4. Which Legal Rule was used and what evaluation produced the Finding?
5. If Legal intervened, who decided what, when, and why?
   Yes. Before locking Step 33, we should define it properly.

# Step 33 — Contract Versioning & Re-Review Workflow

This is important because LegalMind is analyzing **contracts that can change over time**.

We already locked that:

> A new contract version creates a new Review rather than silently changing the old Review.

Step 33 should now define **exactly how that works**.

---

## 33.1 Contract vs Contract Version

We need two separate concepts.

### Contract

The logical agreement:

```text
ABC Customer MSA
```

### Contract Version

A particular uploaded version:

```text
ABC Customer MSA
v1
v2
v3
```

So:

```text
Contract
   │
   ├── Version 1
   ├── Version 2
   └── Version 3
```

The contract itself is the continuing agreement.

The versions are the actual documents received over time.

---

# 33.2 Example

Customer initially sends:

```text
ABC MSA
Version 1
```

LegalMind analyzes it:

```text
Review R-001
↓
Document Version v1
↓
Findings
```

Later the customer negotiates the liability clause and sends:

```text
ABC MSA
Version 2
```

We do **not** replace v1.

Instead:

```text
ABC MSA
│
├── v1
│    └── Review R-001
│
└── v2
     └── New Review R-002
```

This preserves the negotiation history.

---

# 33.3 Why this matters legally

Suppose v1 contained:

```text
Liability = Unlimited
```

Legal rejected it.

Customer sends v2:

```text
Liability = 12 months
```

If we overwrite v1, we lose the evidence that:

> The customer originally proposed unlimited liability.

Legal may need that history later.

Therefore:

**Never overwrite a previously analyzed Document Version.**

---

# 33.4 How does LegalMind know it's a new version?

We should support explicit versioning.

But we should also help prevent accidental duplicates.

For example, if the exact same PDF is uploaded again, the system can detect that the document content is identical using a cryptographic hash.

Conceptually:

```text
PDF
 ↓
SHA-256
 ↓
Document Fingerprint
```

If the fingerprint already exists:

```text
Same document
```

If it is different:

```text
Potential new version
```

Important:

> A different file does not automatically mean a legally meaningful version change.

Metadata or formatting could change while the substantive contract remains the same.

So the system should identify it as a **new uploaded document/version candidate**, while preserving the original.

---

# 33.5 Who creates the new version?

The User can upload the new document.

The system should then associate it with the existing Contract when the User selects:

```text
Existing Contract:
ABC Customer MSA
```

rather than creating:

```text
ABC Customer MSA #2
```

by default.

---

# 33.6 Version numbering

Use simple sequential versioning:

```text
v1
v2
v3
v4
```

Do not allow users to manually type arbitrary versions such as:

```text
v1.4-final-final
v2-final
latest
```

The system controls the version number.

---

# 33.7 Every version is immutable

Once a Document Version is analyzed:

```text
v1
```

cannot be edited in place.

If the underlying document changes:

```text
v2
```

must be created.

This protects evidence integrity.

---

# 33.8 Every Review points to exactly one Document Version

Example:

```text
Review R-001
      ↓
ABC MSA v1
```

and:

```text
Review R-002
      ↓
ABC MSA v2
```

A Review must never ambiguously point to:

```text
ABC MSA
latest version
```

because "latest" can change.

It must point to:

```text
ABC MSA v1
```

or:

```text
ABC MSA v2
```

explicitly.

---

# 33.9 Configuration version is also fixed

We already locked this.

Suppose:

```text
Contract Version:
MSA v2

Configuration:
v3
```

Review:

```text
R-002
```

must preserve:

```text
Document Version = MSA v2
Configuration Version = v3
```

Even if later:

```text
MSA v3
Configuration v4
```

exists.

---

# 33.10 Re-review

Sometimes Legal may want to run the **same contract version** again.

For example:

```text
MSA v2
```

was analyzed under an old configuration.

Legal changes the Company Standard.

They may want:

> "Evaluate MSA v2 against the current standard."

That should create a **new Review**, not overwrite the previous one.

Example:

```text
MSA v2
│
├── Review R-002
│   Configuration v3
│
└── Review R-003
    Configuration v4
```

This gives us a powerful historical comparison.

---

# 33.11 Re-review does NOT create a new document version

Important distinction:

```text
Same document
+
New configuration
=
New Review
```

Whereas:

```text
Changed document
=
New Document Version
+
New Review
```

So:

| Situation                    | Document Version | Review                                    |
| ---------------------------- | ---------------- | ----------------------------------------- |
| Same document reviewed again | Same             | New                                       |
| New contract document        | New              | New                                       |
| Configuration changed        | Same document    | New if re-reviewed                        |
| Old Review reopened          | No               | **Not allowed as a silent recalculation** |

---

# 33.12 Example: negotiation lifecycle

```text
Customer sends MSA v1
        ↓
Review R-001
        ↓
Liability = Unlimited
        ↓
Legal rejects
        ↓
Customer negotiates
        ↓
MSA v2
        ↓
Review R-002
        ↓
Liability = 12 months
        ↓
Legal approves customization
        ↓
Resolved
```

Now Legal has a complete negotiation history:

```text
v1 → Unlimited → Rejected
v2 → 12 months → Approved Customization
```

That is much more useful than just storing the final contract.

---

# 33.13 Can a version be deleted?

I recommend:

**No hard deletion after it becomes part of a Review.**

Instead:

```text
ACTIVE
ARCHIVED
```

or another controlled lifecycle status.

Why?

Because a historical Review may depend on it.

---

# 33.14 What if the wrong document was uploaded?

Example:

```text
MSA v3
```

was accidentally uploaded but it was actually an unrelated document.

Do not delete it from history if it has already been used.

Instead:

```text
INVALID / WITHDRAWN
```

with an audit reason.

Then create the correct version.

---

# 33.15 Version comparison

This is something I recommend supporting in V1 because it is deterministic and very useful.

Legal should eventually be able to see:

```text
MSA v1
      ↓
MSA v2
```

and identify changed clauses.

Example:

```text
Limitation of Liability

v1:
Unlimited

v2:
12 months

CHANGE:
Unlimited → 12 months
```

This is **not LLM/RAG**.

It can be done using deterministic document/section comparison.

It also helps Legal quickly understand what changed during negotiation.

---

# 33.16 But don't make version diff equal to Legal conclusion

This is important.

System can say:

```text
Clause changed:
Unlimited → 12 months
```

But it should not automatically say:

```text
Therefore Legal approved it.
```

The change comparison and Legal Decision remain separate.

---

# 33.17 Version relationship

Each new version should know its predecessor.

Conceptually:

```text
v1
 ↓
v2
 ↓
v3
```

So LegalMind can reconstruct the complete document evolution.

---

# 33.18 Audit trail

Version events should be auditable:

```text
Document v1 uploaded
Document v1 analyzed
Document v2 uploaded
Document v2 analyzed
Review R-002 created
Legal decision recorded
```

This connects directly to Step 32.

---

# 33.19 My recommendation for Step 33

I recommend locking these rules:

1. A Contract and its Document Versions are separate entities.
2. A Contract can contain multiple immutable Document Versions.
3. Every Review references exactly one Document Version.
4. A previously analyzed Document Version is never overwritten.
5. A changed contract document creates a new Document Version.
6. Every new Document Version receives a system-controlled sequential version number.
7. Users cannot manually rewrite historical version numbers.
8. Document versions should have a content fingerprint/hash to detect exact duplicate uploads.
9. An identical upload should not automatically create a meaningful new contractual version.
10. A different file is treated as a new upload/version candidate while preserving the original.
11. A new Document Version normally requires a new Review.
12. Re-reviewing the same Document Version creates a new Review rather than modifying the old Review.
13. A Review explicitly stores the Document Version and applicable Configuration Version used.
14. A Review never points to a mutable "latest" document.
15. Document Versions used by historical Reviews cannot be hard-deleted.
16. Incorrect versions are marked invalid/withdrawn rather than erased.
17. Version history preserves the predecessor relationship: v1 → v2 → v3.
18. Deterministic version comparison may identify changed clauses between versions.
19. Version comparison does not itself constitute a Legal Decision.
20. Contract version history and Legal Decision history remain separately auditable.
21. A new Document Version does not modify Findings or Decisions belonging to an earlier version.
22. A re-review does not modify the original Review's historical result.
23. If the same document is re-reviewed against a newer Company Configuration, it keeps the same Document Version but receives a new Review.
24. The system must preserve the complete negotiation history of analyzed contract versions.

## Core model

```text
CONTRACT
   │
   ├── DOCUMENT VERSION v1
   │       └── REVIEW R-001
   │
   ├── DOCUMENT VERSION v2
   │       └── REVIEW R-002
   │
   └── DOCUMENT VERSION v3
           └── REVIEW R-003
```

And:

```text
Same Document Version
+
Different Configuration
        ↓
New Review
```

while:

```text
Changed Document
        ↓
New Document Version
        ↓
New Review
```

**I recommend this as the Step 33 model. Do not lock it yet until you confirm it looks right.**
Yes. I’ll handle **Step 34 and Step 35 together**, but I recommend we **lock them separately** after review because they define two different technical/legal boundaries.

# Step 34 — Document Ingestion & Parsing

This defines how LegalMind gets a reliable, versioned representation of the contract before any legal analysis happens.

## 34.1 Core principle

LegalMind must **never analyze the raw uploaded file directly as if extraction were guaranteed**.

The pipeline should be:

```text
Uploaded File
     ↓
File Validation
     ↓
Document Fingerprint
     ↓
Document Version
     ↓
Text / Structure Extraction
     ↓
Extraction Validation
     ↓
Normalized Document Representation
     ↓
Analysis Engine
```

The original uploaded file must remain preserved.

---

## 34.2 V1 supported formats

I recommend:

### Primary V1

```text
PDF
DOCX
```

These cover the majority of business contracts.

### Not primary V1

```text
XLSX
PPTX
Images
Email files
Scanned handwritten documents
```

They can be evaluated later.

---

# 34.3 Scanned PDFs

This is important.

There are two kinds of PDFs:

### Text PDF

```text
PDF
 ↓
Text extraction
 ↓
Good
```

### Scanned PDF

```text
PDF
 ↓
No usable text
 ↓
OCR
 ↓
Text
```

LegalMind should detect when normal extraction is insufficient and use OCR where supported.

But OCR output must be marked as OCR-derived.

Example:

```text
Evidence Source:
OCR

Extraction Confidence:
LOW / MEDIUM / HIGH
```

We should **never silently treat OCR output as equivalent to clean native text**.

---

# 34.4 OCR failure

Suppose the document is:

- blurry
- handwritten
- rotated badly
- extremely low quality
- password protected
- corrupted

LegalMind should not invent missing text.

Instead:

```text
EXTRACTION_FAILED
```

or, if only part of the document is affected:

```text
PARTIAL_EXTRACTION
```

Then the affected Finding can become:

```text
UNABLE_TO_EVALUATE
```

rather than making a false legal conclusion.

---

# 34.5 Preserve the original file

For every uploaded document:

```text
Original File
     ↓
Immutable Storage
```

Never modify the original file during processing.

Create derived artifacts separately:

```text
Original PDF
   ↓
Extracted Text
   ↓
Normalized Structure
   ↓
Evidence
```

This is important for auditability.

---

# 34.6 Document fingerprint

Every uploaded file should receive a cryptographic fingerprint.

Example:

```text
SHA-256
```

Conceptually:

```text
File
 ↓
SHA-256
 ↓
abcdef123...
```

This lets us detect exact duplicates.

If the exact same file is uploaded again:

```text
Same fingerprint
```

LegalMind should not blindly create another contractual version.

---

# 34.7 Document structure

We shouldn't store only one giant text blob.

The normalized representation should preserve structure such as:

```text
Document
 ├── Page
 ├── Section
 ├── Heading
 ├── Paragraph
 ├── Clause
 ├── Table
 └── List
```

For example:

```text
Section 8
  ↓
8.1
8.2 Limitation of Liability
8.3 Indemnification
```

This directly supports Step 32 Evidence.

---

# 34.8 Clause numbering

The parser should preserve existing numbering.

Example:

```text
8.2
8.2.1
(a)
(b)
(i)
(ii)
```

We should not depend solely on automatically generated numbering.

The original numbering is part of the contract's structure.

---

# 34.9 Tables

Contracts often contain important legal information in tables.

Example:

| Service  | Liability | Term      |
| -------- | --------- | --------- |
| Standard | 6 months  | 12 months |
| Premium  | 12 months | 24 months |

The parser must preserve table content in a structured representation rather than dropping it.

Otherwise LegalMind could miss legally relevant provisions.

---

# 34.10 Headers and footers

Headers and footers should be identified separately.

For example:

```text
CONFIDENTIAL
ABC Corp MSA
Page 7 of 24
```

should not accidentally become part of the liability clause.

However, the original positional information should remain available where needed.

---

# 34.11 Page references

Each extracted element should retain its source page where possible.

Example:

```text
Clause:
8.2

Page:
7

Text:
"...previous twelve months..."
```

This allows the UI to jump back to the original document location.

---

# 34.12 Normalization

We can normalize things like:

```text
multiple spaces
line breaks
hyphenation caused by PDF layout
encoding problems
```

But we must preserve the **original extracted source text** as evidence.

So:

```text
Original Source Text
        +
Normalized Text
```

not:

```text
Original discarded
```

---

# 34.13 Document extraction status

I recommend controlled statuses:

```text
UPLOADED
PROCESSING
EXTRACTED
PARTIALLY_EXTRACTED
EXTRACTION_FAILED
```

This is separate from the Review lifecycle from Step 30.

For example:

```text
Review:
PROCESSING

Document:
PARTIALLY_EXTRACTED
```

The Review should not proceed to normal deterministic analysis if required evidence cannot be reliably extracted.

---

# 34.14 Document ingestion security

The ingestion layer must treat uploaded documents as untrusted input.

At minimum:

```text
File type validation
File size limits
Malware/security scanning where available
Safe parsing
No execution of document macros/scripts
Isolated processing
Access control
```

DOCX files must not be treated as executable content.

---

# 34.15 Step 34 recommended locked rules

1. V1 primarily supports PDF and DOCX.
2. Original uploaded files are preserved immutably.
3. Document Versions are immutable once used by a Review.
4. Every file receives a cryptographic fingerprint/hash.
5. Exact duplicate files should be detectable.
6. Native PDF/DOCX text extraction is preferred.
7. OCR is used when a supported PDF does not contain usable text.
8. OCR-derived content is explicitly identified.
9. Extraction failures never result in invented text or legal conclusions.
10. Partial extraction is explicitly represented.
11. The normalized document representation preserves pages, sections, clauses, paragraphs, lists, and tables where technically available.
12. Existing clause numbering is preserved.
13. Relevant source locations are retained for Evidence.
14. Original extracted text is preserved alongside normalized text.
15. Document extraction status is separate from Review lifecycle status.
16. Uploaded files are treated as untrusted input and processed safely.
17. Documents with insufficient reliable extraction may produce `UNABLE_TO_EVALUATE` rather than a fabricated Finding.
18. The ingestion layer must not alter the original source document.

---

# Step 35 — Requirement & Clause Mapping Engine

This is where things become technically interesting.

The goal is:

```text
Contract
   ↓
Clause
   ↓
Requirement
```

**without LLM, RAG, vector database, or semantic AI.**

---

# 35.1 Core principle

The mapping engine should be:

> **Deterministic first, explainable always.**

We shouldn't ask:

> "Does this paragraph sound like liability?"

Instead, we should have structured Requirements with deterministic matching logic.

---

# 35.2 Requirement definition

A Requirement should contain structured metadata.

Example:

```text
Requirement:
LIABILITY-001

Name:
Limitation of Liability

Category:
Liability

Expected:
Contract must contain a liability limitation.

Required:
YES
```

Then mapping logic can specify what should be looked for.

---

# 35.3 Requirement aliases

Legal language can vary.

For example:

```text
Limitation of Liability
Limitation on Liability
Liability Cap
Aggregate Liability
Maximum Liability
```

These can be configured as deterministic aliases.

This is **not semantic AI**.

It is controlled legal configuration.

---

# 35.4 Keyword groups

Instead of one keyword:

```text
liability
```

use groups.

Example:

```text
GROUP A:
liability
liable
aggregate liability

GROUP B:
cap
limited
shall not exceed
maximum

GROUP C:
fees
amount paid
contract value
```

The engine can evaluate combinations.

For example:

```text
Group A
+
Group B
```

is stronger evidence than:

```text
liability
```

alone.

---

# 35.5 Negative terms

We also need exclusion patterns.

Example:

```text
"liability shall not be limited"
```

contains:

```text
liability
limited
```

but means the opposite of a liability cap.

So rules need:

```text
Positive patterns
+
Negative patterns
```

This is critical.

---

# 35.6 Clause-level mapping

Don't map an entire document at once.

Use:

```text
Document
 ↓
Sections
 ↓
Candidate Clauses
 ↓
Requirement Mapping
```

Example:

```text
Section 8.2
"Aggregate liability shall not exceed..."
        ↓
LIABILITY-001
```

---

# 35.7 Candidate vs confirmed mapping

This is an important safeguard.

The engine should distinguish:

```text
CANDIDATE
```

from:

```text
CONFIRMED
```

For example:

```text
Keyword match:
liability
```

doesn't automatically mean:

```text
Confirmed Liability Requirement
```

A stronger rule must be satisfied.

---

# 35.8 Deterministic scoring

We can use a deterministic scoring/ranking mechanism to rank candidate clauses.

For example:

```text
Exact phrase match       +5
Alias match              +3
Required keyword group   +3
Section heading match    +2
Negative pattern         -5
```

These numbers are **illustrative**, not locked yet.

The important principle is:

> The score is deterministic and explainable.

The engine can say:

```text
Matched:
"limitation of liability"

Matched:
"shall not exceed"

Section:
8.2 Limitation of Liability

Candidate score:
X
```

This is very different from an opaque AI confidence score.

---

# 35.9 Thresholds

We can then have:

```text
High deterministic match
       ↓
CONFIRMED

Medium
       ↓
CANDIDATE / REVIEW

Low
       ↓
NOT MAPPED
```

But I recommend **not locking numerical thresholds yet**.

We should determine them experimentally using a representative contract test set.

That belongs in the algorithm-validation stage.

---

# 35.10 Requirement-specific mapping rules

Not every Requirement should use the same algorithm.

Example:

### Liability

Look for:

```text
liability
liable
aggregate
cap
maximum
fees
```

### Termination

Look for:

```text
terminate
termination
notice
convenience
breach
```

### Governing Law

Look for:

```text
governing law
laws of
jurisdiction
venue
```

So each Requirement can have its own deterministic mapping configuration.

---

# 35.11 Section heading importance

A clause under:

```text
LIMITATION OF LIABILITY
```

should be treated differently from a random sentence mentioning:

```text
liability
```

Therefore section headings can contribute to mapping.

Example:

```text
Heading:
Limitation of Liability

Body:
Aggregate liability shall not exceed...
```

This is extremely strong deterministic evidence.

---

# 35.12 Cross-reference handling

Contracts often say:

> "Subject to Section 12.4."

The engine should preserve cross-references.

For example:

```text
Clause 8.2
      ↓
references 12.4
      ↓
12.4 contains exception
```

This becomes important for Conflict detection later.

We don't necessarily need full legal reasoning here, but the mapping layer must retain the relationship.

---

# 35.13 Multiple clauses can map to one Requirement

Example:

```text
Requirement:
LIABILITY-001
```

might map to:

```text
8.2
14.4
Schedule B
```

That doesn't necessarily mean there are three separate Findings.

The Evaluation Engine in Step 36 decides what those mapped clauses collectively mean.

This separation is important:

```text
Mapping
≠
Evaluation
```

---

# 35.14 One clause can map to multiple Requirements

Example:

```text
Clause 12.3
```

could contain:

```text
Termination
+
Liability
+
Indemnification
```

So:

```text
Clause
 ↓
Requirement A
Requirement B
Requirement C
```

The mapping engine must support many-to-many relationships.

---

# 35.15 No forced mapping

If the engine cannot reliably map a clause:

```text
NO_CONFIDENT_MAPPING
```

It should not force it into a Requirement just to produce a result.

This is important for legal accuracy.

---

# 35.16 Mapping evidence

Every mapping should retain its reason.

Example:

```text
Requirement:
LIABILITY-001

Mapped Clause:
8.2

Why:
- Section heading matched
- Alias matched
- Required keyword group matched
- No exclusion pattern detected
```

This becomes part of the Step 32 explainability chain.

---

# 35.17 Step 35 recommended locked rules

I recommend locking these principles:

1. Clause-to-Requirement mapping is deterministic in V1.
2. V1 does not use LLM, RAG, vector database, or semantic AI for mapping.
3. Requirements contain structured mapping metadata.
4. Requirements may define aliases and controlled terminology.
5. Mapping supports positive and negative patterns.
6. Mapping operates at clause/section level rather than treating the entire document as one text block.
7. Section headings can contribute to deterministic mapping.
8. Mapping distinguishes candidate matches from confirmed mappings.
9. Mapping can use deterministic ranking/scoring where useful.
10. Numerical thresholds should be validated against a representative contract test set before being locked.
11. Different Requirements may use different mapping rules.
12. One Requirement may map to multiple clauses.
13. One clause may map to multiple Requirements.
14. Mapping does not itself determine the final Finding.
15. Mapping and Evaluation remain separate engines.
16. Cross-references should be preserved for downstream evaluation.
17. The engine must allow a clause to remain unmapped when evidence is insufficient.
18. Every confirmed mapping records its deterministic explanation/evidence.
19. No opaque AI confidence score is used as the basis for a V1 Legal conclusion.
20. Mapping rules are versioned as part of Legal Configuration.

---

# The architecture we are heading toward

These two steps establish an important separation:

```text
                 DOCUMENT
                    ↓
          ┌───────────────────┐
          │ Ingestion/Parsing │
          └─────────┬─────────┘
                    ↓
             Normalized Text
                    ↓
          ┌───────────────────┐
          │ Mapping Engine    │
          └─────────┬─────────┘
                    ↓
           Requirement Mapping
                    ↓
          ┌───────────────────┐
          │ Evaluation Engine │  ← Step 36
          └─────────┬─────────┘
                    ↓
                 Finding
                    ↓
             Legal Decision
```

**Step 34 = how we reliably understand the document structure.**

**Step 35 = how we deterministically connect contract clauses to LegalMind Requirements.**

**Step 36 = how we actually evaluate those mapped clauses and produce MATCH / DEVIATION / MISSING / CONFLICT, etc.**

I recommend **not locking either 34 or 35 yet** until you review them, especially the deterministic mapping/scoring approach.
Yes. I reviewed **Step 34 and Step 35 again from a LegalMind/V1 architecture perspective**, not just for completeness but for places where a future implementation could create ambiguity.

## Final review — Step 34

I checked specifically for:

- Original document preservation
- Immutable document versions
- PDF/DOCX handling
- OCR vs native text
- Extraction failure handling
- Tables and clause structure
- Section/clause numbering
- Page-level evidence
- Normalized vs original text
- Duplicate detection
- Security of uploaded documents
- Extraction status vs Review status
- `UNABLE_TO_EVALUATE` instead of guessing

**One important clarification I added mentally to the design:** OCR is an **extraction mechanism**, not a legal-analysis mechanism. OCR output must remain identifiable as OCR-derived evidence.

### Decision

🔒 **STEP 34 — LOCKED**

---

# Step 35 final review

I also rechecked the mapping engine for the biggest V1 risks:

### 1. Keyword matching cannot be enough

Correct. We already require:

```text
Positive patterns
+
Negative patterns
+
Section context
+
Clause context
```

### 2. Mapping ≠ legal evaluation

This is critical and remains locked:

```text
Mapping:
"What Requirement does this clause relate to?"

Evaluation:
"What does this clause mean under our configured rule?"
```

### 3. One-to-many and many-to-one

Both are supported:

```text
One Requirement
    ↓
Multiple clauses
```

and:

```text
One clause
    ↓
Multiple Requirements
```

### 4. No forced mapping

If evidence isn't strong enough:

```text
NO_CONFIDENT_MAPPING
```

rather than inventing a match.

### 5. Scoring

We should **not hard-code arbitrary thresholds now**.

We first need a representative contract test set, then benchmark the deterministic rules and tune thresholds.

That is the correct engineering approach.

### 6. Versioning

Mapping rules themselves must be versioned.

So a historical Review can say:

```text
Requirement Mapping Rules: v4
```

and we don't accidentally reinterpret an old Review using today's rules.

### Decision

🔒 **STEP 35 — LOCKED**

I would **not add 34/35 to the `.md` yet**, consistent with your previous instruction that we can add the accumulated decisions later.

---

# Now Step 36 — Finding & Evaluation Engine

This is the **most important algorithmic step so far**.

Step 35 answers:

> **Which Requirement does this clause belong to?**

Step 36 answers:

> **What does that clause mean according to our Company Standard and Legal Rule?**

## 36.1 The evaluation pipeline

```text
Mapped Clause
      ↓
Requirement
      ↓
Company Standard
      ↓
Legal Rule
      ↓
Deterministic Evaluation
      ↓
Finding
```

Possible V1 outcomes:

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

## 36.2 MATCH

Customer provision conforms to the Company Standard.

Example:

```text
Company Standard:
Liability = 6 months

Customer:
Liability = 6 months

Result:
MATCH
```

---

## 36.3 DEVIATION

Customer provision differs from the Company Standard.

Example:

```text
Company Standard:
6 months

Customer:
12 months

Result:
DEVIATION
```

Important:

**DEVIATION does not automatically mean unacceptable.**

The Legal Rule determines what happens next.

---

## 36.4 MISSING

The Requirement is expected, but no qualifying provision is found.

```text
Requirement:
Limitation of Liability

Customer:
No qualifying liability limitation found

Result:
MISSING
```

---

## 36.5 CONFLICT

Multiple provisions within the same contract produce incompatible positions.

Example:

```text
Section 8.2:
Liability capped at 6 months

Section 14.4:
Liability is unlimited

Result:
CONFLICT
```

Both pieces of evidence remain attached.

---

## 36.6 AMBIGUOUS

The system found potentially relevant provisions but cannot deterministically establish the intended legal position.

```text
Clause:
"Liability may be limited as mutually agreed."

Result:
AMBIGUOUS
```

Legal review is required.

---

## 36.7 UNRESOLVED

The system has identified an issue but cannot complete the evaluation because required information or a required action is missing.

This is different from `AMBIGUOUS`.

---

## 36.8 UNABLE_TO_EVALUATE

The system cannot reliably perform the evaluation because the underlying evidence is unavailable or unreliable.

Example:

```text
Scanned page
   ↓
OCR failed
   ↓
Liability clause cannot be reliably extracted
   ↓
UNABLE_TO_EVALUATE
```

This prevents LegalMind from pretending that "not found" means "missing."

---

# 36.9 The most important rule

The engine must separate:

```text
Deviation
```

from:

```text
Legal acceptability
```

Example:

```text
Company Standard:
6 months

Customer:
12 months

Finding:
DEVIATION
```

Then the Legal Rule says:

```text
Preferred:
6 months

Acceptable:
≤12 months

Approval Required:
>12 months
```

So **DEVIATION is the factual comparison result**.

The Legal Rule determines the required workflow.

---

# 36.10 No generic risk score

I recommend we **do not introduce**:

```text
Risk = 83%
```

or:

```text
Low / Medium / High
```

as the primary V1 legal output.

Instead, LegalMind should produce a deterministic classification based on the configured Legal Rule.

That is much more defensible.

---

# 36.11 Requirement-specific evaluation

Different legal requirements need different evaluation algorithms.

For example:

### Liability

Numeric/range evaluation:

```text
Customer:
12 months

Standard:
6 months

Rule:
≤12 months acceptable

Finding:
DEVIATION
Workflow:
Legal decision may be required according to configuration
```

### Governing Law

Exact/allowed-value evaluation:

```text
Company Standard:
India

Customer:
Singapore

Finding:
DEVIATION
```

### Notice Period

Numeric comparison:

```text
Company Standard:
30 days

Customer:
60 days

Finding:
DEVIATION
```

So we should **not create one universal comparison algorithm** for every legal clause.

The Requirement configuration determines the appropriate deterministic evaluator.

---

# 36.12 Evaluation types

I recommend supporting a controlled set of evaluator types, such as:

```text
EXACT_MATCH
ALLOWED_VALUES
NUMERIC_COMPARISON
RANGE_COMPARISON
BOOLEAN_PRESENT
BOOLEAN_ABSENT
TEXT_PATTERN
MULTI_CLAUSE
CONFLICT_DETECTION
```

This gives us a reusable deterministic engine without introducing AI.

---

# 36.13 Example

```text
Requirement:
LIABILITY-001

Evaluator:
NUMERIC_COMPARISON

Company Standard:
6 months

Customer:
12 months

Legal Rule:
≤12 months = Acceptable
>12 months = Approval Required

Evaluation:
Customer value ≠ Company Standard
Customer value ≤ Acceptable threshold

Finding:
DEVIATION
```

Then Legal decides whether to:

```text
ACCEPT_DEVIATION
APPROVE_CUSTOMIZATION
REQUIRE_COMPANY_STANDARD
REJECT
REQUEST_CLARIFICATION
```

according to Step 31.

---

# 36.14 Evaluation must preserve the calculation

For numeric rules, don't only save:

```text
DEVIATION
```

Save the actual evaluation inputs:

```text
Expected:
6 months

Actual:
12 months

Operator:
>

Acceptable threshold:
12 months

Evaluation:
Actual > Expected
AND
Actual <= Acceptable threshold
```

This makes the result reproducible.

---

# 36.15 No automatic Legal Decision

The Evaluation Engine produces:

```text
FINDING
```

It does **not** produce:

```text
APPROVE_CUSTOMIZATION
```

That remains the Legal Decision layer from Step 31.

---

# 36.16 Historical reproducibility

Every evaluation must preserve:

```text
Document Version
Requirement Version
Company Standard Version
Legal Rule Version
Evaluator Version
Evaluation Inputs
Evaluation Output
```

Therefore:

```text
Same inputs
+
Same versions
=
Same Finding
```

This is exactly what we want from V1.

---

# 36.17 Step 36 recommendation

I recommend locking these principles:

1. Finding generation is deterministic.
2. Mapping and Evaluation are separate engines.
3. `DEVIATION` means deviation from Company Standard; it does not itself mean unacceptable.
4. Legal Rules determine the required workflow for a deviation.
5. V1 supports controlled Finding classifications: `MATCH`, `DEVIATION`, `MISSING`, `CONFLICT`, `AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE`.
6. Different Requirements may use different deterministic evaluator types.
7. No generic opaque risk percentage is used as the primary V1 legal classification.
8. Numeric evaluations preserve their inputs, operators, thresholds, and resulting comparison.
9. Multiple clauses may be evaluated collectively.
10. Conflicting provisions remain separately evidenced.
11. Insufficient evidence must not be converted into a false `MISSING` or `MATCH`.
12. The Evaluation Engine never makes a Legal Decision.
13. Every evaluation is reproducible from versioned inputs and rules.
14. Evaluator logic/configuration is versioned.
15. Historical Findings are never silently recalculated using newer rules.
16. Every Finding retains the Evidence/Requirement/Standard/Rule chain from Step 32.

---

# Step 37 — V1 Scope Freeze

After Step 36, I recommend we **freeze the actual V1 functional boundary** before architecture.

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

> **V1 can be designed so these capabilities could be added later without redesigning the core legal data model.**

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

If the system cannot explain a Finding, it should **not claim that the analysis is complete**.

---

### Current status

```text
Step 34  🔒 LOCKED
Step 35  🔒 LOCKED

Step 36  ⏳ REVIEW
Step 37  ⏳ REVIEW
```

I recommend we **review 36 and 37 together once**, then lock them. After that, we are in a very good position to move into **Step 38 — Architecture**, followed by the actual **technology-stack selection**.
36 and 37 are also locked

# Step 38 — LegalMind V1 Architecture

Now we move from **product/legal decisions** into **system architecture**.

The architecture must serve the decisions already locked in Steps 1–37. We should **not choose technologies yet**. First we define the responsibilities and boundaries of each component; then Step 39 will select the technology stack.

---

## 38.1 Core architectural principle

LegalMind V1 should be a:

> **Modular, deterministic, versioned, auditable application with clear separation between document processing, legal configuration, analysis, workflow, and presentation.**

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

This is the conceptual architecture. **It is not yet a technology decision.**

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

Authorization must be enforced **server-side**.

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

This domain does **not** determine legal Findings.

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

# 38.9 Analysis Engine

This should be isolated from the UI.

Its responsibility:

```text id="r5f2qd"
Normalized Contract
        ↓
Clause Mapping
        ↓
Requirement Mapping
        ↓
Deterministic Evaluation
        ↓
Findings
```

This is the core LegalMind engine.

---

# 38.10 Mapping Engine

Responsible only for:

> **Which Requirement does this clause relate to?**

Example:

```text id="c9w4mv"
Section 8.2
"Aggregate liability shall not exceed..."

        ↓

LIABILITY-001
```

It should not decide whether the customer term is acceptable.

---

# 38.11 Evaluation Engine

Responsible only for:

> **How does the mapped provision compare with the configured Company Standard and Legal Rule?**

Example:

```text id="z2t8kp"
Customer:
12 months

Company Standard:
6 months

Legal Rule:
≤12 months acceptable

        ↓

Finding:
DEVIATION
```

Again:

**Evaluation ≠ Legal Decision.**

---

# 38.12 Findings Domain

Stores the result of deterministic analysis.

Example:

```text id="f5q7mc"
Finding
 ├── Requirement
 ├── Evidence
 ├── Company Standard Version
 ├── Legal Rule Version
 ├── Evaluation
 └── Classification
```

Possible classifications:

```text id="j9x3wa"
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

---

# 38.13 Review Workflow

A Review is the container that connects everything.

Conceptually:

```text id="m8v2rd"
Review
 │
 ├── Contract
 ├── Document Version
 ├── Configuration Snapshot
 ├── Analysis
 ├── Findings
 ├── Legal Decisions
 └── Audit Events
```

This is extremely important.

A Review should represent:

> **What LegalMind analyzed, using which versions, and what happened as a result.**

---

# 38.14 Configuration Snapshot

I recommend the Review store a **configuration snapshot/reference** rather than simply asking for the "current configuration."

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

The report is a **presentation of the recorded analysis**, not a second analysis engine.

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

It should **not necessarily store the original PDF/DOCX binary**.

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

However, whether we use a dedicated queue system, worker process, or another mechanism is a **Step 39 technology decision**.

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

There must be **one source of truth for legal evaluation**.

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

The exact endpoint naming is **not locked here**.

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

**V1 uses only the deterministic engine.**

Future AI capabilities must not silently replace the deterministic legal source of truth.

---

# 38.26 What should NOT be a separate microservice in V1

I recommend **not over-engineering V1**.

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

**This is an architectural recommendation, not yet a technology lock.**

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

The UI, reports, exports, and future AI features are **consumers of this source of truth**, not replacements for it.

---

# 38.29 Step 38 proposed locked decisions

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
Steps 1–37  🔒 LOCKED

Step 38      ⏳ REVIEW
             Architecture

Step 39      → Technology Stack
```

**I recommend you review Step 38 before locking it.** Once Step 38 is locked, **Step 39 is where we can seriously evaluate the actual tech stack**—framework, database, document parsers, OCR, queue/worker technology, storage, authentication, testing, and deployment—against these architectural requirements.
🔒 **Step 38 — V1 Architecture is locked.**

Now we can choose the technology stack. I would optimize for **legal correctness, deterministic processing, auditability, maintainability, and fast V1 delivery**, not for trendy infrastructure.

# Step 39 — Recommended Technology Stack

My recommendation is a **modular monolith + background workers**, not microservices.

### Recommended stack

| Layer            | Recommendation                                      | Why                                                                                       |
| ---------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Frontend         | **Next.js + TypeScript**                            | Strong admin/dashboard UX, server-side capabilities, mature ecosystem                     |
| Backend/API      | **FastAPI + Python**                                | Excellent fit for document processing and deterministic analysis                          |
| Database         | **PostgreSQL**                                      | Strong relational model, transactions, JSONB, constraints, excellent audit/versioning fit |
| ORM              | **SQLAlchemy 2 + Alembic**                          | Explicit schema/control, mature migrations                                                |
| Document PDF     | **PyMuPDF**                                         | Fast, strong PDF text/page extraction and positional data                                 |
| DOCX             | **python-docx**                                     | Reliable structured DOCX parsing                                                          |
| OCR              | **OCRmyPDF + Tesseract** initially                  | Good deterministic/local OCR pipeline                                                     |
| Background jobs  | **Celery + Redis**                                  | Mature worker model for document processing/analysis                                      |
| Object storage   | **S3-compatible storage**                           | Original PDFs/DOCX and derived artifacts                                                  |
| API validation   | **Pydantic**                                        | Excellent typed validation with FastAPI                                                   |
| Auth             | **OIDC/OAuth2-compatible provider**                 | Avoid building authentication ourselves                                                   |
| Authorization    | **Application-level RBAC + PostgreSQL constraints** | Server-side enforcement                                                                   |
| Testing          | **Pytest + Playwright**                             | Backend/domain + real browser workflow testing                                            |
| Frontend testing | **Vitest**                                          | Fast TypeScript unit testing                                                              |
| Containers       | **Docker**                                          | Reproducible development/deployment                                                       |
| Reverse proxy    | **Nginx** or equivalent                             | TLS, routing, upload handling                                                             |
| CI/CD            | **GitHub Actions**                                  | Straightforward automated testing/deployment                                              |
| Monitoring       | **Sentry + structured application logs**            | Error tracking and operational visibility                                                 |

---

# Why I recommend Python for the backend

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

It also gives us room later to evaluate NLP/LLM capabilities **without rewriting the backend**.

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

# Why PostgreSQL

I would make PostgreSQL the **system of record**.

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

- Foreign keys
- Transactions
- Constraints
- JSONB where genuinely useful
- Indexing
- Full-text capabilities if needed
- Strong consistency
- Excellent migration tooling

I would **not introduce MongoDB** for V1.

---

# Why I don't recommend a vector database

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

# Document processing architecture

I would build:

```text
                    Upload
                      ↓
               File Validation
                      ↓
                SHA-256 Hash
                      ↓
              Original Storage
                      ↓
              Processing Queue
                      ↓
          ┌───────────┴───────────┐
          ↓                       ↓
       PDF                     DOCX
          ↓                       ↓
      PyMuPDF                python-docx
          │                       │
          └───────────┬───────────┘
                      ↓
              Extraction Check
                      ↓
             Is text sufficient?
                 /          \
               YES           NO
                ↓             ↓
             Continue      OCRmyPDF
                              ↓
                          Tesseract
                              ↓
                        Extraction Check
                              ↓
                       Normalization
                              ↓
                       Clause Structure
```

---

# OCR choice

For V1 I'd use:

**OCRmyPDF + Tesseract**

rather than sending contracts to a cloud AI/OCR service by default.

Why?

Legal documents can be sensitive.

A local/self-hosted OCR pipeline gives us:

- Better data-control posture
- Reproducibility
- No per-page API dependency
- Easier auditability
- No accidental third-party model processing

If OCR quality later proves insufficient for difficult scans, we can evaluate a stronger OCR provider as an explicit architectural decision.

---

# Background processing

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

# Frontend

I recommend:

**Next.js + TypeScript**

The UI should consume the backend API.

Example:

```text
Next.js
    ↓
FastAPI
    ↓
PostgreSQL
```

The frontend should **never contain legal evaluation logic**.

For example, this should not exist in frontend code:

```text
if customerLiability > companyStandard:
    showDeviation()
```

Instead:

```text
FastAPI
 ↓
Evaluation Engine
 ↓
Finding
 ↓
Next.js displays Finding
```

---

# Analysis engine design

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

---

# Testing strategy

LegalMind needs unusually strong automated tests.

I'd require:

### Unit tests

For:

```text
parsers
normalizers
mapping rules
evaluation rules
conflict detection
versioning
permissions
```

### Golden/test contracts

Create a controlled corpus:

```text
contracts/
├── liability/
├── termination/
├── indemnification/
├── governing-law/
├── conflicts/
├── missing/
└── ambiguous/
```

Each test contract has an expected result.

Example:

```text
Input:
12-month liability

Expected:
DEVIATION

Expected evaluation:
Within acceptable threshold
```

This is how we'll tune the deterministic algorithm instead of guessing thresholds.

### Integration tests

Test:

```text
upload
→ processing
→ analysis
→ findings
→ legal decision
→ audit
```

### Playwright

Test the actual UI workflow.

---

# Security

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

---

# Deployment

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

### ❌ Microservices from day one

Too much operational complexity for V1.

### ❌ Kubernetes immediately

No evidence yet that V1 requires it.

### ❌ MongoDB

The data model is heavily relational.

### ❌ Vector DB

Not required by the V1 methodology.

### ❌ LLM

Explicitly outside V1.

### ❌ RAG

Explicitly outside V1.

### ❌ Cloud OCR by default

Legal-document privacy makes local/self-hosted OCR preferable initially.

### ❌ Building our own authentication

Use a mature identity solution.

### ❌ Business logic in Next.js

Legal evaluation belongs in the backend/domain layer.

---

# Final recommended stack

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

**This is the stack I would choose for LegalMind V1.**

The most important decision isn't Next.js vs another frontend or FastAPI vs another API framework. The critical decision is that the **deterministic analysis engine is a first-class domain component**, independently testable, versioned, and completely separated from the UI.

And we should **not start implementation yet** just because the stack is selected. The next architecture step should define the **actual database/domain model and component boundaries** before Claude Code starts creating tables and files.

**Step 39 — Technology Stack: proposed.** I recommend we review it once before locking, particularly the **FastAPI + PostgreSQL + Celery/Redis + PyMuPDF/OCRmyPDF** choices.
🔒 **Step 39 — Technology Stack: LOCKED**

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

---

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

# 40.4 Review

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

# 40.5 Requirement

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

# 40.6 Company Standard

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

# 40.7 Legal Rule

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

# 40.8 Configuration Version

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

# 40.9 Clause / Evidence

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

# 40.10 Finding

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

# 40.11 Finding ↔ Evidence

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

# 40.12 Legal Decision

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

# 40.13 Audit Event

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

# 40.14 Critical relationship

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

# 40.15 One important design rule

We should **not store the entire legal meaning of a Finding as one giant JSON blob**.

Structured fields should be relational where they matter for:

- filtering
- authorization
- reporting
- versioning
- relationships
- audit
- deterministic evaluation

JSON can be used for genuinely variable metadata, but it should not become a substitute for the domain model.

---

# 40.16 Step 40 proposed lock

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

---

# 41.2 `users`

```text id="d4l8w2"
users
-----
id
email
name
status
created_at
updated_at
```

`id` should be a UUID.

Email should have a unique constraint.

Do **not** use email as the primary key because email addresses can change.

---

# 41.3 Roles

For V1:

```text id="0n6k9c"
roles
-----
id
code
name
```

Initial roles:

```text
USER
ADMIN
SUPER_ADMIN
```

Using a role table rather than scattering role strings throughout the application gives us room to evolve permissions.

---

# 41.4 `user_roles`

```text id="r8w1qm"
user_roles
----------
user_id
role_id
```

Unique constraint:

```text
(user_id, role_id)
```

This allows the authorization system to remain flexible.

---

# 41.5 `contracts`

```text id="9y2c7v"
contracts
---------
id
owner_id
name
contract_type
status
created_at
updated_at
```

Critical:

```text
owner_id → users.id
```

This gives us the foundation for object-level authorization.

---

# 41.6 `document_versions`

```text id="j3m8qa"
document_versions
-----------------
id
contract_id
version_number
original_filename
mime_type
file_size
file_hash
storage_key
processing_status
extraction_status
uploaded_by
created_at
```

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

# 41.7 Document immutability

Once a Document Version is created:

```text id="y4x9bn"
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

# 41.8 `document_processing_runs`

A document may go through processing more than once.

Therefore, don't put every processing attempt directly into `document_versions`.

Use:

```text id="8x4qnt"
document_processing_runs
------------------------
id
document_version_id
run_type
status
started_at
completed_at
error_code
error_message
processor_version
created_at
```

Example:

```text
Document v2
   │
   ├── Extraction Run 1 → FAILED
   └── Extraction Run 2 → COMPLETED
```

This is valuable for debugging and auditability.

---

# 41.9 `document_evidence`

This stores extracted evidence.

```text id="1h7m6p"
document_evidence
-----------------
id
document_version_id
processing_run_id
page_number
section_number
section_title
content
source_type
start_offset
end_offset
created_at
metadata
```

`source_type` could include:

```text
NATIVE_TEXT
OCR
TABLE
OTHER
```

The exact enum should be finalized during implementation.

---

# 41.10 Why evidence needs a processing run

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

# 41.11 Requirements

We should separate the logical Requirement from its versions.

```text id="3v9kq1"
requirements
------------
id
code
status
created_at
updated_at
```

Example:

```text
LIABILITY-001
```

Then:

```text id="0r7s8a"
requirement_versions
--------------------
id
requirement_id
version_number
name
description
evaluator_type
created_by
created_at
```

So:

```text
LIABILITY-001
   ├── v1
   ├── v2
   └── v3
```

---

# 41.12 Company Standard

Company Standards should attach to a specific Requirement Version.

Conceptually:

```text id="9k3w6e"
company_standard_versions
-------------------------
id
requirement_version_id
version_number
configuration
created_by
created_at
```

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

# 41.13 Legal Rules

Similarly:

```text id="3q7m2k"
legal_rule_versions
-------------------
id
requirement_version_id
version_number
rule_type
configuration
created_by
created_at
```

Example:

```text
{
  "acceptable_max": 12,
  "approval_required_above": 12
}
```

The exact configuration schema depends on the evaluator type.

---

# 41.14 Mapping Rules

```text id="7n2x8p"
mapping_rule_versions
---------------------
id
requirement_version_id
version_number
rules
created_by
created_at
```

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

# 41.15 Evaluation Rules

```text id="6m4q9r"
evaluation_rule_versions
-----------------------
id
requirement_version_id
version_number
evaluator_type
rules
created_by
created_at
```

This is separate from mapping.

That preserves the Step 35/36 distinction.

---

# 41.16 Configuration Snapshot

This is one of the most important tables.

```text id="v2c7sa"
configuration_snapshots
----------------------
id
created_at
created_by
snapshot_hash
```

And then:

```text id="w8q1zn"
configuration_snapshot_items
----------------------------
snapshot_id
requirement_version_id
company_standard_version_id
legal_rule_version_id
mapping_rule_version_id
evaluation_rule_version_id
```

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

# 41.17 Reviews

```text id="r4p8yw"
reviews
-------
id
contract_id
document_version_id
configuration_snapshot_id
status
created_by
created_at
started_at
completed_at
```

Important constraint:

The `document_version_id` must belong to the same `contract_id`.

This should be enforced through application logic and, where practical, database constraints/design.

---

# 41.18 Findings

```text id="h7x2mk"
findings
--------
id
review_id
requirement_version_id
classification
status
created_at
updated_at
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

# 41.19 Evaluations

I recommend separating the **Finding** from the actual deterministic evaluation record.

```text id="q9m3va"
evaluations
-----------
id
finding_id
evaluator_type
expected_value
actual_value
operator
result
rule_version_id
created_at
```

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

# 41.20 Finding ↔ Evidence

Never use a single `evidence_id` on Finding.

Use a junction table:

```text id="1c8x5q"
finding_evidence
---------------
finding_id
evidence_id
relationship_type
```

Possible relationship types:

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

# 41.21 Legal Decisions

```text id="4w9n2s"
legal_decisions
--------------
id
finding_id
decision_type
decision_text
decided_by
created_at
```

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

# 41.22 Audit Events

```text id="8q2n5x"
audit_events
------------
id
actor_id
action
entity_type
entity_id
timestamp
before_state
after_state
metadata
```

Audit events should be append-only.

No normal application user should be able to edit historical audit records.

---

# 41.23 Ownership

The schema must make ownership traversable.

Example:

```text id="1m7q3z"
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

# 41.24 Critical authorization rule

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

# 41.25 Indexing strategy

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

# 41.26 Soft delete vs hard delete

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

# 41.27 Timestamps

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

# 41.28 UUIDs

Use UUID primary keys for externally exposed/domain entities.

Benefits:

- Avoid sequential ID exposure
- Better distributed-system compatibility later
- Safer public identifiers
- Easier future service separation

But UUIDs are **not a substitute for authorization**.

---

# 41.29 Referential integrity

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

# 41.30 The complete schema relationship

Conceptually:

```text id="j1f6kx"
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

# 41.31 The most important database invariant

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

# Step 41 proposed lock

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

# Step 42 — Exact Database Schema & ERD

This step converts the locked domain model from Step 41 into an **implementation-ready PostgreSQL schema design**.

I am deliberately keeping this at the **schema-contract level** for now: exact tables, columns, relationships, constraints, and indexes. We should not write migrations until this is locked.

---

## 42.1 Design rules

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

# 42.2 Identity & Access

## `users`

```text id="q4h6n1"
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

```text id="1f2w7s"
ACTIVE
SUSPENDED
DISABLED
```

---

## `roles`

```text id="6x9t2m"
roles
-----
id                UUID PK
code              VARCHAR UNIQUE NOT NULL
name              VARCHAR NOT NULL
```

Initial roles:

```text id="l6q3cv"
USER
ADMIN
SUPER_ADMIN
```

---

## `user_roles`

```text id="8m1k5r"
user_roles
----------
user_id           UUID FK → users.id
role_id           UUID FK → roles.id

PRIMARY KEY(user_id, role_id)
```

This keeps role assignment flexible.

---

# 42.3 Contracts

## `contracts`

```text id="y3f8kp"
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

```text id="k2q7mx"
INDEX(owner_id)
INDEX(status)
INDEX(created_at)
```

---

# 42.4 Document Versions

## `document_versions`

```text id="6m2c8z"
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

```text id="j6t4zr"
UNIQUE(contract_id, version_number)
```

Indexes:

```text id="0a8q2x"
INDEX(contract_id)
INDEX(file_hash)
INDEX(uploaded_by)
INDEX(processing_status)
```

### Important

`file_hash` is indexed for duplicate detection.

It should **not** be globally unique because the same source file may legitimately appear in multiple contracts/workspaces.

---

# 42.5 Document Processing

## `document_processing_runs`

```text id="9b4r1v"
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

```text id="v8y2kx"
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

# 42.6 Evidence

## `document_evidence`

```text id="h5w3qn"
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

```text id="2p6v7m"
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

# 42.7 Legal Configuration

This is deliberately versioned.

## `requirements`

```text id="r7x3k2"
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

---

## `requirement_versions`

```text id="c6v1pz"
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

# 42.8 Company Standards

## `company_standard_versions`

```text id="8j4m2q"
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

# 42.9 Legal Rules

## `legal_rule_versions`

```text id="w3n8kc"
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

# 42.10 Mapping Rules

## `mapping_rule_versions`

```text id="v7q2lm"
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

# 42.11 Evaluation Rules

## `evaluation_rule_versions`

```text id="x9k4rz"
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

# 42.12 Configuration Snapshot

## `configuration_snapshots`

```text id="q6m8ys"
configuration_snapshots
-----------------------
id                    UUID PK
snapshot_hash         VARCHAR UNIQUE NOT NULL
created_by            UUID FK → users.id
created_at            TIMESTAMPTZ NOT NULL
```

---

## `configuration_snapshot_items`

```text id="3v5n1k"
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

# 42.13 Reviews

## `reviews`

```text id="m2q7xk"
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

# 42.14 Findings

## `findings`

```text id="j8p3sv"
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

# 42.15 Evaluations

## `evaluations`

```text id="r5k1mw"
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

# 42.16 Finding ↔ Evidence

## `finding_evidence`

```text id="c3n7xq"
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

# 42.17 Legal Decisions

## `legal_decisions`

```text id="v8m2ks"
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

# 42.18 Audit Events

## `audit_events`

```text id="f4q9zn"
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

# 42.19 ERD

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

# 42.20 The critical traceability path

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

# 42.21 Important integrity constraints

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

# 42.22 Important decision: no database-level "magic"

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

# 42.23 Step 42 proposed lock

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

I’ll treat the schema above as the baseline and **not casually change it later**. If implementation reveals a genuine contradiction, we should explicitly reopen the relevant decision rather than silently modifying it.

---

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

# 43.2 Proposed backend modules

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

---

# 43.3 `auth`

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

# 43.4 `contracts`

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

# 43.5 `documents`

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

# 43.6 Upload workflow

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

# 43.7 `processing`

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

# 43.8 `requirements`

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

# 43.9 `configuration`

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

# 43.10 `reviews`

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

# 43.11 Review creation

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

# 43.12 `analysis`

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

# 43.13 Analysis pipeline

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

# 43.14 Requirement Mapping

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

# 43.15 Evaluation

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

# 43.16 Finding generation

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

# 43.17 `findings`

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

# 43.18 `decisions`

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

# 43.19 Decision workflow

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

# 43.20 `audit`

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

# 43.21 API response structure

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

# 43.22 HTTP status semantics

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

# 43.23 Authorization model

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

# 43.24 Service layer

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

# 43.25 Repository layer

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

# 43.26 Transaction boundaries

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

# 43.27 Background worker boundaries

Workers should own long-running operations.

```text
DocumentProcessingWorker
ReviewAnalysisWorker
```

Potential future workers can be added without turning the application into microservices.

---

# 43.28 Idempotency

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

# 43.29 State machines

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

# 43.30 API versioning

Use:

```text
/api/v1/
```

from the beginning.

This gives us a clean compatibility boundary if the API changes later.

---

# 43.31 What the frontend is allowed to do

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

# 43.32 End-to-end example

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

---

# 43.33 Step 43 proposed lock

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

---

# Step 44 — Legal Analysis Engine Architecture

This is one of the **most important steps in the entire LegalMind design**.

The question we must answer is:

> **How does LegalMind take an actual contract, understand the relevant clause using deterministic methods, compare it against the Company Standard and Legal Rule, and produce a defensible Finding?**

We need something substantially better than simple keyword matching.

The V1 engine should therefore be a **layered deterministic legal analysis pipeline**.

---

# 44.1 The fundamental principle

LegalMind must never jump directly from:

```text
Contract text
      ↓
Finding
```

Instead:

```text
Contract
   ↓
Document Evidence
   ↓
Normalization
   ↓
Requirement Candidate Detection
   ↓
Evidence Selection
   ↓
Structured Fact Extraction
   ↓
Requirement Evaluation
   ↓
Legal Rule Evaluation
   ↓
Finding
   ↓
Evidence + Explanation
```

Every stage should produce inspectable intermediate results.

---

# 44.2 The engine

The core engine should conceptually be:

```text
                ┌──────────────────────┐
                │   Document Evidence │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │    Normalization     │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Requirement Mapping  │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Evidence Selection   │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Fact Extraction      │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Deterministic        │
                │ Evaluation            │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Legal Rule Evaluation│
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │ Finding Generation   │
                └──────────────────────┘
```

---

# 44.3 Layer 1 — Text normalization

Raw extraction is not analysis-ready.

For example, a PDF may produce:

```text
Limitation of Liabil-
ity
```

while the actual clause is:

```text
Limitation of Liability
```

Normalization should handle things such as:

- whitespace
- line breaks
- hyphenation caused by PDF layout
- repeated headers/footers
- page artifacts
- Unicode normalization
- quotation normalization
- common OCR errors where safely detectable
- section numbering normalization

But:

> **Normalization must never silently alter the legal meaning of the original text.**

Original evidence remains preserved.

---

# 44.4 Layer 2 — Structural parsing

Before looking for legal concepts, extract document structure.

For example:

```text
Document
 ├── Page 1
 ├── Page 2
 ├── Section 1
 ├── Section 2
 ├── Section 8
 │     └── 8.2 Limitation of Liability
 └── Appendix A
```

The engine should identify:

- page boundaries
- headings
- numbered sections
- paragraphs
- tables
- bullet lists
- annexures/schedules where detectable

This gives later stages structural signals.

---

# 44.5 Layer 3 — Requirement Mapping

Now LegalMind asks:

> **Where in this contract is the evidence relevant to this Requirement?**

Example:

```text
Requirement:
LIABILITY-001
```

Potential evidence:

```text
Section 8 — Limitation of Liability
Section 8.2 — Aggregate Liability
Schedule B — Liability
```

The mapper should combine multiple deterministic signals.

---

# 44.6 Do NOT use simple keyword matching alone

Weak implementation:

```text
if "liability" in text:
    return liability_clause
```

This will fail badly.

For example:

> "The parties shall have no limitation of liability for fraud."

That contains "limitation of liability" but may represent a specific carve-out rather than the general liability cap.

Instead, use **multi-signal candidate ranking**.

---

# 44.7 Candidate ranking

For every Requirement, candidate evidence can receive a deterministic relevance score based on signals such as:

```text
Heading match
Section-title match
Known terminology
Positive patterns
Negative patterns
Required concepts
Proximity of related terms
Section position
Clause structure
```

Conceptually:

```text
Candidate Score =
    heading_score
  + terminology_score
  + pattern_score
  + concept_score
  + proximity_score
  + structural_score
```

The exact numerical weights should **not be hard-coded globally yet**.

They should be Requirement/evaluator configuration.

---

# 44.8 Why ranking matters

Suppose a contract contains:

```text
Section 4:
Confidentiality

Section 9:
Limitation of Liability

Section 15:
General provisions referring to liability.
```

A simple search might return all three.

The mapper should rank:

```text
Section 9 → strongest candidate
Section 15 → secondary candidate
Section 4 → irrelevant
```

Then the engine can evaluate the strongest relevant evidence while preserving secondary evidence where necessary.

---

# 44.9 Layer 4 — Evidence selection

Mapping produces candidates.

Selection determines:

> **Which evidence is actually sufficient for evaluation?**

Possible outcomes:

```text
FOUND
MULTIPLE_CANDIDATES
MISSING
AMBIGUOUS
```

This distinction is important.

If two contradictory liability clauses exist:

```text
Section 8 → 6 months
Schedule B → unlimited
```

the engine should **not simply choose whichever scored highest**.

It should identify a potential conflict.

---

# 44.10 Layer 5 — Structured fact extraction

This is where LegalMind becomes substantially more powerful than keyword matching.

The engine converts relevant language into structured facts.

Example:

```text
Contract text:

"Aggregate liability shall not exceed an amount
equal to twelve months of fees paid under this Agreement."
```

Fact:

```text
{
  "concept": "liability_cap",
  "value": 12,
  "unit": "months",
  "scope": "aggregate"
}
```

This fact is what the evaluator uses.

---

# 44.11 Fact extraction should be requirement-specific

There should not be one universal parser trying to understand every legal concept.

Instead:

```text
Liability Evaluator
    ↓
liability fact extractor

Termination Evaluator
    ↓
termination fact extractor

Governing Law Evaluator
    ↓
governing-law fact extractor
```

This makes the system much more deterministic and testable.

---

# 44.12 Example — Liability

Input:

> "The aggregate liability of either party shall not exceed six months of fees paid under this Agreement."

Extract:

```text
concept: liability_cap
value: 6
unit: months
scope: aggregate
```

Company Standard:

```text
preferred = 6 months
```

Legal Rule:

```text
preferred = 6
acceptable_max = 12
approval_required_above = 12
```

Evaluation:

```text
6 == 6
```

Result:

```text
MATCH
```

---

# 44.13 Example — Deviation

Contract:

> "Aggregate liability shall not exceed twelve months of fees."

Extract:

```text
liability_cap = 12 months
```

Standard:

```text
preferred = 6 months
```

Rule:

```text
≤12 months = acceptable
```

Result:

```text
DEVIATION
```

It is **not automatically a legal failure**.

That distinction is fundamental.

---

# 44.14 Example — Approval Required

Contract:

> "Aggregate liability shall not exceed twenty-four months of fees."

Extract:

```text
liability_cap = 24 months
```

Rule:

```text
>12 months = APPROVAL_REQUIRED
```

Finding:

```text
DEVIATION
```

with the evaluation state:

```text
APPROVAL_REQUIRED
```

The exact Finding/decision terminology should remain consistent with the previously locked Legal Decision model.

---

# 44.15 Example — Unlimited liability

Contract:

> "Neither party's liability shall be subject to any limitation."

Extract:

```text
liability_cap = UNLIMITED
```

If Company Standard says:

```text
6 months
```

and Legal Rule says:

```text
UNLIMITED = UNACCEPTABLE
```

then:

```text
Finding:
DEVIATION

Rule outcome:
UNACCEPTABLE
```

This is where the Legal Rule—not an arbitrary AI score—determines the outcome.

---

# 44.16 Layer 6 — Negative patterns

Negative patterns are essential.

Suppose we search for:

```text
"liability shall not exceed"
```

But the contract says:

> "Except for liability arising from fraud, the liability cap shall not exceed six months."

The engine must understand that:

```text
fraud
```

is a carve-out.

Therefore, a Requirement may define:

```text
positive patterns
negative patterns
carve-out patterns
scope patterns
```

---

# 44.17 Scope extraction

This is a major legal-analysis requirement.

A clause may contain:

```text
General cap:
6 months

Exceptions:
fraud
wilful misconduct
confidentiality breach
IP infringement
```

LegalMind should not flatten this into:

```text
liability_cap = 6 months
```

only.

It should preserve:

```text
General Rule
+
Exceptions / Carve-outs
```

Example:

```text
{
  "general_cap": {
    "value": 6,
    "unit": "months"
  },
  "exceptions": [
    "fraud",
    "wilful misconduct",
    "confidentiality"
  ]
}
```

This is much more useful for legal evaluation.

---

# 44.18 Layer 7 — Conflict detection

Conflict detection should be a dedicated engine capability.

Example:

```text
Section 8:
Liability limited to 6 months.

Schedule B:
Liability shall be unlimited.
```

The engine should produce:

```text
CONFLICT
```

rather than selecting one clause and ignoring the other.

The Finding should reference:

```text
Evidence A
Evidence B
```

with:

```text
relationship_type = CONFLICTING
```

---

# 44.19 Cross-clause analysis

Some legal requirements cannot be evaluated from one paragraph.

Example:

```text
Section 8:
Liability capped at 6 months.

Section 8.3:
Cap does not apply to confidentiality breaches.
```

The evaluator may need both.

Therefore:

> Requirement evaluators must be able to consume **multiple Evidence items**.

This is already supported by the Step 42 schema.

---

# 44.20 Missing clause detection

Missing clauses are not the same as:

```text
Unable to extract
```

The engine must distinguish:

```text
MISSING
```

from:

```text
UNABLE_TO_EVALUATE
```

Example:

### Missing

No termination provision is found anywhere.

```text
MISSING
```

### Unable to evaluate

A termination clause exists, but extraction is too corrupted to reliably determine the notice period.

```text
UNABLE_TO_EVALUATE
```

These must never be treated as equivalent.

---

# 44.21 Ambiguity

Consider:

> "Liability shall be limited to an amount agreed between the parties."

There is a liability concept, but no determinable amount.

Result:

```text
AMBIGUOUS
```

Not:

```text
MATCH
```

and not automatically:

```text
MISSING
```

---

# 44.22 Unresolved state

`UNRESOLVED` should represent a workflow state rather than a guessed legal conclusion.

For example:

```text
Conflict detected
       ↓
Legal review required
       ↓
UNRESOLVED
```

After an authorized decision:

```text
UNRESOLVED
       ↓
RESOLVED
```

This is different from the analytical classification.

---

# 44.23 No generic "AI confidence score"

We should **not** create something like:

```text
confidence = 87%
```

and present that as legal certainty.

That would create false precision.

Instead, deterministic diagnostics should explain _why_ the engine reached a result.

For example:

```text
Evidence matched:
Section 8.2

Extracted fact:
12 months

Company Standard:
6 months

Applicable Rule:
≤12 months acceptable

Result:
DEVIATION
```

This is much more defensible.

---

# 44.24 Deterministic uncertainty

However, the engine should explicitly represent uncertainty when the evidence is insufficient.

Example:

```text
Extraction:
successful

Mapping:
strong candidate

Fact extraction:
failed

Evaluation:
not possible
```

Result:

```text
UNABLE_TO_EVALUATE
```

This is preferable to guessing.

---

# 44.25 The evaluator interface

Conceptually every Requirement evaluator should follow the same contract:

```text
evaluate(
    requirement_version,
    company_standard,
    legal_rule,
    evidence
)
    ↓
EvaluationResult
```

The result should contain structured information such as:

```text
classification
rule_outcome
facts
evidence_references
explanation
diagnostics
```

---

# 44.26 Evaluator architecture

Example:

```text
Analysis Engine
│
├── LiabilityEvaluator
│    ├── LiabilityMapper
│    ├── LiabilityFactExtractor
│    └── LiabilityRuleEvaluator
│
├── TerminationEvaluator
│    ├── TerminationMapper
│    ├── TerminationFactExtractor
│    └── TerminationRuleEvaluator
│
├── GoverningLawEvaluator
│    ├── GoverningLawMapper
│    ├── GoverningLawFactExtractor
│    └── GoverningLawRuleEvaluator
│
└── ...
```

This allows requirement-specific precision without creating a completely different architecture for every clause.

---

# 44.27 Common engine + specialized evaluators

We should avoid two extremes.

### Bad approach A

One enormous universal legal parser.

```text
UniversalLegalParser
```

Too difficult to test and reason about.

### Bad approach B

Every requirement becomes a completely independent application.

Too much duplication.

### Correct approach

```text
Shared deterministic infrastructure
+
Requirement-specific evaluators
```

Shared:

```text
Normalization
Structure parsing
Pattern engine
Candidate ranking
Evidence model
Fact model
Rule execution
Diagnostics
```

Specialized:

```text
Liability
Termination
Indemnification
Governing Law
```

---

# 44.28 Rule engine

The Rule Engine should execute structured rules.

For example:

```text
IF
    actual_value <= acceptable_max

THEN
    rule_outcome = ACCEPTABLE
```

Another:

```text
IF
    actual_value > approval_threshold

THEN
    rule_outcome = APPROVAL_REQUIRED
```

Rules should be data/configuration driven where practical.

The engine executes them.

It should not require modifying Python code every time an Admin changes a Company Standard.

---

# 44.29 But not everything should be configurable

We should **not** make the entire legal analysis engine arbitrary JSON.

Core evaluator algorithms belong in tested Python code.

Configuration controls things like:

```text
thresholds
allowed values
patterns
terminology
rule parameters
```

Python controls:

```text
parsing algorithms
normalization
fact extraction algorithms
comparison semantics
evaluation execution
conflict detection mechanics
```

This gives us both flexibility and safety.

---

# 44.30 Algorithm selection

For V1, the best approach is a **hybrid deterministic NLP/rule-based pipeline**, not one algorithm.

Use:

### 1. Structural heuristics

For:

```text
headings
sections
paragraphs
tables
```

### 2. Lexical matching

Use:

```text
exact match
case-normalized match
phrase matching
controlled synonyms
```

### 3. Regex/pattern matching

For structured values:

```text
6 months
12 months
30 days
₹10 million
USD 5,000
```

### 4. Finite-state / rule-based extraction

For legal patterns such as:

```text
shall not exceed X
may terminate upon X days' notice
governed by laws of X
```

### 5. Candidate ranking

Use deterministic weighted signals.

### 6. Requirement-specific evaluators

Convert evidence into structured facts.

### 7. Rule evaluation

Compare facts against Company Standards and Legal Rules.

This combination is substantially stronger than plain keyword matching while remaining explainable.

---

# 44.31 What about classical NLP libraries?

A controlled classical NLP layer can be used where it genuinely helps:

```text
spaCy
```

for things such as:

- sentence segmentation
- tokenization
- linguistic normalization
- selected entity extraction

But it should **not become the legal decision-maker**.

The authoritative result still comes from deterministic evaluators and rules.

---

# 44.32 What about embeddings?

For V1:

**No vector database and no semantic retrieval.**

However, a future architecture may evaluate semantic retrieval separately.

The important thing is:

```text
V1:
Deterministic retrieval
```

not:

```text
V1:
Embedding similarity decides legal relevance
```

---

# 44.33 Explainability contract

Every Finding generated by the engine should be capable of producing:

```text
WHY?
WHAT EVIDENCE?
WHAT FACT?
WHAT STANDARD?
WHAT RULE?
WHAT RESULT?
```

Example:

```text
Requirement:
Liability

Evidence:
Section 8.2 — page 12

Extracted:
Liability cap = 12 months

Company Standard:
6 months

Legal Rule:
Up to 12 months = acceptable deviation

Result:
DEVIATION
```

This should be generated from structured engine output—not manually assembled by the frontend.

---

# 44.34 Golden test corpus

The Analysis Engine cannot be considered production-ready based only on unit tests.

We need a curated corpus.

Example:

```text
liability/
├── exact_match_6_months.pdf
├── acceptable_deviation_12_months.pdf
├── approval_required_24_months.pdf
├── unlimited_liability.pdf
├── missing_liability.pdf
├── ambiguous_liability.pdf
├── conflicting_liability.pdf
├── carveout_liability.pdf
└── multi_clause_liability.pdf
```

Each has expected results.

---

# 44.35 Regression protection

Whenever the evaluator changes:

```text
Old test corpus
      ↓
New engine
      ↓
Compare results
```

If:

```text
Expected:
MATCH

Actual:
DEVIATION
```

the change must be investigated before release.

For a legal-analysis system, this is essential.

---

# 44.36 Engine versioning

The analysis engine itself must have a version.

For example:

```text
engine_version = 1.0.0
```

A Review should retain:

```text
configuration_snapshot
+
analysis_engine_version
+
processing_version
```

Then six months later we can answer:

> Which exact engine produced this Finding?

This is an important addition to the historical reproducibility requirement.

---

# 44.37 Deterministic reproducibility

Given identical:

```text
Document Evidence
+
Configuration Snapshot
+
Analysis Engine Version
```

the engine should produce the same result.

Formally:

```text
Same Input
+
Same Rules
+
Same Engine Version
=
Same Output
```

No hidden external model or changing API should alter the result.

---

# 44.38 Failure philosophy

The engine should **fail closed rather than guess**.

If it cannot reliably determine:

```text
What clause applies
What value was stated
Which rule applies
```

it should produce:

```text
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

as appropriate.

It should never manufacture a legal conclusion.

---

# 44.39 End-to-end example

Let's take one realistic example.

Contract:

> "The aggregate liability of the Supplier shall not exceed twenty-four months of fees paid under this Agreement. This limitation shall not apply to fraud or wilful misconduct."

### Step 1 — Mapping

Relevant evidence:

```text
Section 10.2
Page 14
```

### Step 2 — Fact extraction

```text
general_cap = 24 months

exceptions:
- fraud
- wilful misconduct
```

### Step 3 — Company Standard

```text
preferred = 6 months
```

### Step 4 — Legal Rule

```text
≤ 12 months = acceptable
> 12 months = approval required
```

### Step 5 — Evaluation

```text
24 > 12
```

### Step 6 — Result

```text
Finding:
DEVIATION

Rule Outcome:
APPROVAL_REQUIRED
```

### Step 7 — Evidence

Attach:

```text
Section 10.2
Page 14
```

### Step 8 — Explanation

The UI can explain:

```text
Company Standard: 6 months
Contract provision: 24 months
Applicable rule: >12 months requires approval
```

### Step 9 — Legal Decision

Authorized reviewer decides:

```text
APPROVE_CUSTOMIZATION
```

The Company Standard remains:

```text
6 months
```

This preserves the already locked:

> **RESOLVED ≠ MATCH**

principle.

---

# 44.40 Final architecture

The complete V1 Analysis Engine becomes:

```text
                    DOCUMENT
                       │
                       ↓
                 RAW EVIDENCE
                       │
                       ↓
                 NORMALIZATION
                       │
                       ↓
               STRUCTURAL PARSER
                       │
                       ↓
              REQUIREMENT MAPPER
                       │
                       ↓
              CANDIDATE RANKING
                       │
                       ↓
               EVIDENCE SELECTOR
                       │
                       ↓
             FACT EXTRACTION
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
        FACTS VALID?          AMBIGUOUS
             │                   │
             ↓                   ↓
       RULE EVALUATION       UNRESOLVED /
             │               UNABLE_TO_EVALUATE
             ↓
       CONFLICT CHECK
             │
             ↓
        EVALUATION
             │
             ↓
          FINDING
             │
       ┌─────┴─────┐
       ↓           ↓
   EVIDENCE    EXPLANATION
       │
       ↓
 LEGAL DECISION
       │
       ↓
    AUDIT EVENT
```

---

# Step 44 — Proposed Lock

I recommend locking these principles:

1. LegalMind V1 uses a **layered deterministic analysis engine**.
2. Raw contract text is never directly converted into a Finding.
3. Original evidence remains preserved.
4. Normalization never silently changes legal meaning.
5. Document structure is extracted before legal mapping.
6. Requirement Mapping is separate from Evaluation.
7. Candidate selection uses multiple deterministic signals rather than keywords alone.
8. Evidence selection explicitly handles multiple candidates.
9. Requirement-specific fact extraction converts relevant language into structured facts.
10. Evaluators are requirement-specific but use shared deterministic infrastructure.
11. Company Standards and Legal Rules are inputs to evaluation, not hard-coded legal conclusions.
12. Negative patterns and carve-outs are first-class concepts.
13. Cross-clause analysis is supported.
14. Conflicting provisions are explicitly detected rather than silently choosing one.
15. `MISSING`, `AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE` remain distinct states.
16. The system does not use generic AI confidence scores.
17. The system fails closed rather than guessing.
18. V1 uses deterministic NLP/rule-based techniques such as structural heuristics, lexical matching, regex/pattern extraction, finite-state/rule logic, candidate ranking, and requirement-specific evaluators.
19. Classical NLP libraries such as spaCy may assist extraction/segmentation but cannot determine the legal result.
20. V1 does not use LLM, RAG, embeddings, or vector search in the authoritative legal-analysis path.
21. The Rule Engine executes configurable rule parameters while core evaluation algorithms remain tested application code.
22. Every Finding must be explainable through Evidence → Fact → Standard → Rule → Result.
23. The Analysis Engine has its own explicit version.
24. A Review records the Analysis Engine Version alongside its Configuration Snapshot.
25. Identical evidence + identical configuration + identical engine version must produce the same result.
26. A golden contract corpus is mandatory for evaluator validation and regression testing.
27. Every material Finding must remain traceable to the exact evidence used to produce it.
28. LegalMind must never manufacture a legal conclusion when evidence is insufficient.

### Current status

```text
Steps 1–43  🔒 LOCKED

Step 44      ⏳ REVIEW
             Legal Analysis Engine Architecture
```

**I would not lock Step 44 casually.** This is the technical heart of LegalMind. Once this is locked, the next step should define **Step 45 — Requirement/Evaluator Specification**, where we take actual legal areas such as **Liability, Termination, Indemnification, Governing Law, etc.** and specify exactly what each evaluator extracts, what patterns it recognizes, what facts it produces, and how those facts are evaluated against the Company Standard and Legal Rules.
Yes. I rethought **Step 44** against the full master specification and the locked decisions before it. The architecture is sound, and the three clarifications we identified are important enough to make part of the lock.

### 🔒 Step 44 — LOCKED

The final authoritative architecture is:

```text
Document Version
      ↓
Original Evidence
      ↓
Normalization
      ↓
Structural Parsing
      ↓
Requirement Mapping
      ↓
Candidate Selection
      ↓
Evidence Selection
      ↓
Fact Extraction
      ↓
┌──────────────────────────────┐
│ Requirement Evaluation       │
│ Conflict Detection           │
│ Cross-Clause Analysis        │
└──────────────┬───────────────┘
               ↓
        Evaluation Result
               ↓
            Finding
               ↓
      Evidence + Explanation
               ↓
        Review Workflow
               ↓
  Authorized Legal Decision
               ↓
          Audit Event
```

### Final locked clarifications

- **Analysis Engine ends at Finding + Evidence + Explanation.**
  Legal Decision is outside the engine and belongs to the authorized Legal workflow.

- **`AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE` are distinct.**
  The engine must never use uncertainty as an excuse to guess.

- **Conflict Detection is a first-class engine capability.**
  It is not merely a final step after a single clause evaluation.

- The V1 engine remains completely deterministic, versioned, reproducible, and explainable.

- Same:

  ```text
  Evidence
  + Configuration
  + Analysis Engine Version
  ```

  must produce the same analytical result.

- No LLM, RAG, embeddings, vector database, or AI-generated legal decision enters this authoritative V1 path.

This fits the existing locked requirements around deterministic evaluation, evidence traceability, reproducibility, and separation between Findings and Legal Decisions.

## Current position

```text
Steps 1–43  🔒 LOCKED
Step 44      🔒 LOCKED
```

### Next: Step 45 — Requirement / Evaluator Specification

Now we move from **architecture** to the actual legal evaluation design.

We'll define, requirement by requirement:

```text
Requirement
   ↓
Evidence required
   ↓
Fact extraction
   ↓
Positive / negative patterns
   ↓
Carve-outs / exceptions
   ↓
Company Standard
   ↓
Legal Rule
   ↓
Evaluation logic
   ↓
Finding
   ↓
Possible workflow consequence
```

And we should start with **Limitation of Liability** as the first concrete evaluator because it is already our canonical example throughout the specification.

**Step 44 is locked. We move to Step 45.**
Yes. I rethought **Step 44** against the full master specification and the locked decisions before it. The architecture is sound, and the three clarifications we identified are important enough to make part of the lock.

### 🔒 Step 44 — LOCKED

The final authoritative architecture is:

```text
Document Version
      ↓
Original Evidence
      ↓
Normalization
      ↓
Structural Parsing
      ↓
Requirement Mapping
      ↓
Candidate Selection
      ↓
Evidence Selection
      ↓
Fact Extraction
      ↓
┌──────────────────────────────┐
│ Requirement Evaluation       │
│ Conflict Detection           │
│ Cross-Clause Analysis        │
└──────────────┬───────────────┘
               ↓
        Evaluation Result
               ↓
            Finding
               ↓
      Evidence + Explanation
               ↓
        Review Workflow
               ↓
  Authorized Legal Decision
               ↓
          Audit Event
```

### Final locked clarifications

- **Analysis Engine ends at Finding + Evidence + Explanation.**
  Legal Decision is outside the engine and belongs to the authorized Legal workflow.

- **`AMBIGUOUS`, `UNRESOLVED`, and `UNABLE_TO_EVALUATE` are distinct.**
  The engine must never use uncertainty as an excuse to guess.

- **Conflict Detection is a first-class engine capability.**
  It is not merely a final step after a single clause evaluation.

- The V1 engine remains completely deterministic, versioned, reproducible, and explainable.

- Same:

  ```text
  Evidence
  + Configuration
  + Analysis Engine Version
  ```

  must produce the same analytical result.

- No LLM, RAG, embeddings, vector database, or AI-generated legal decision enters this authoritative V1 path.

This fits the existing locked requirements around deterministic evaluation, evidence traceability, reproducibility, and separation between Findings and Legal Decisions.

## Current position

```text
Steps 1–43  🔒 LOCKED
Step 44      🔒 LOCKED
```

### Next: Step 45 — Requirement / Evaluator Specification

Now we move from **architecture** to the actual legal evaluation design.

We'll define, requirement by requirement:

```text
Requirement
   ↓
Evidence required
   ↓
Fact extraction
   ↓
Positive / negative patterns
   ↓
Carve-outs / exceptions
   ↓
Company Standard
   ↓
Legal Rule
   ↓
Evaluation logic
   ↓
Finding
   ↓
Possible workflow consequence
```

And we should start with **Limitation of Liability** as the first concrete evaluator because it is already our canonical example throughout the specification.

**Step 44 is locked. We move to Step 45.**
Yes. I reviewed the existing specification specifically for the **Limitation of Liability evaluator**, and there is an important point before we lock anything:

The master specification already gives us several authoritative liability decisions—especially `6 months` as the Company Standard, `≤12 months` as acceptable, `>12 months` as approval-required, and `Unlimited` as unacceptable.

So we should **not invent a new liability model**. Step 45 should formalize what is already established.

# Step 45A — LIABILITY-001

## 1. Requirement identity

```text
Requirement ID:
LIABILITY-001

Name:
Limitation of Liability

Document Type:
MSA

Category:
Liability

Required:
YES

Evaluator:
Liability-specific deterministic evaluator
```

The Requirement is the evaluation unit. The evaluator is responsible for extracting and evaluating the structured liability facts. The existing specification explicitly says fact extraction should be Requirement-specific.

---

# 2. What the evaluator must determine

The evaluator should answer these questions **in order**:

```text
1. Is there a liability provision?
        ↓
2. Is there an identifiable liability cap?
        ↓
3. What is the cap?
        ↓
4. What unit is the cap expressed in?
        ↓
5. What is the scope of the cap?
        ↓
6. Are there exceptions / carve-outs?
        ↓
7. Are there multiple liability provisions?
        ↓
8. Do those provisions conflict?
        ↓
9. Can the provision be reliably evaluated?
        ↓
10. Compare against Company Standard
        ↓
11. Apply configured Legal Rule
```

This keeps **extraction → evaluation → Finding → Legal Decision** separate.

---

# 3. Structured liability fact

For the basic case:

> "The aggregate liability of either party shall not exceed six months of fees paid under this Agreement."

The evaluator extracts:

```text
{
  concept: "liability_cap",
  cap_exists: true,
  value: 6,
  unit: "months",
  scope: "aggregate"
}
```

This exact pattern is already established in the specification.

But I recommend we expand the internal representation slightly:

```text
LiabilityFact
├── cap_exists
├── cap_type
├── cap_value
├── cap_unit
├── cap_basis
├── scope
├── exceptions
├── evidence_refs
└── extraction_diagnostics
```

### Important

This does **not** mean every field must be populated.

If the contract does not specify a basis, we preserve:

```text
cap_basis = UNKNOWN
```

rather than guessing.

---

# 4. Cap type

We should distinguish at least:

```text
FINITE
UNLIMITED
ABSENT
UNKNOWN
```

Example:

### Finite

```text
6 months
```

→ `FINITE`

### Unlimited

> "Neither party's liability shall be subject to any limitation."

→ `UNLIMITED`

The specification explicitly uses Unlimited as a configured Legal Rule category.

### No identifiable provision

→ `ABSENT`

This can contribute to:

```text
MISSING
```

### Evidence exists but cannot be reliably interpreted

→ `UNKNOWN`

This can contribute to:

```text
UNABLE_TO_EVALUATE
```

---

# 5. Units

The evaluator must preserve the original unit.

Examples:

```text
6 months
12 months
₹10 crore
100% of fees
fees paid in previous 12 months
```

Do **not** automatically convert different bases into a common numerical value unless a deterministic conversion rule has explicitly been configured.

For example:

```text
6 months of fees
```

is not automatically equivalent to:

```text
₹X
```

without the necessary contractual data.

So:

```text
value = 6
unit = months
basis = fees_paid
```

is safer than attempting to calculate a monetary amount.

---

# 6. Scope

This is critical.

A liability provision might apply to:

```text
Aggregate liability
Per claim
Per event
Each party
One party only
Specific category of liability
```

Therefore:

```text
scope = aggregate
```

must not be silently generalized to:

```text
all liability
```

The specification already says scope and carve-outs need to remain represented rather than flattening the clause to a single number.

---

# 7. Carve-outs

Consider:

> "Aggregate liability shall not exceed six months of fees, except for fraud, wilful misconduct and confidentiality breaches."

The structured representation should preserve:

```text
general_cap:
    value: 6
    unit: months

exceptions:
    - fraud
    - wilful misconduct
    - confidentiality breach
```

The master specification explicitly requires this kind of scope/carve-out preservation.

### Critical rule

The evaluator must **not** automatically conclude:

```text
6 months = fully compliant
```

without considering whether the Requirement's configured comparison criteria address those exceptions.

---

# 8. Company Standard

The authoritative existing standard is:

```text
Preferred:
6 months
```

This is already established in the specification.

Therefore:

```text
Customer = 6 months
Company Standard = 6 months
```

produces:

```text
Finding:
MATCH
```

---

# 9. Customer = 12 months

```text
Customer:
12 months

Company Standard:
6 months
```

Comparison:

```text
12 != 6
```

Therefore:

```text
Finding:
DEVIATION
```

Then the Legal Rule is evaluated:

```text
12 <= 12
```

Therefore:

```text
Rule Outcome:
ACCEPTABLE
```

This is explicitly established in the master specification.

And importantly:

```text
DEVIATION
+
ACCEPTABLE
```

does **not** automatically create a Legal Decision.

---

# 10. Customer = 24 months

```text
Customer:
24 months

Company Standard:
6 months
```

Therefore:

```text
Finding:
DEVIATION
```

Then:

```text
24 > 12
```

Therefore:

```text
Rule Outcome:
APPROVAL_REQUIRED
```

The engine stops there.

It does **not** automatically approve or reject the contract.

Legal Decision remains a separate authorized workflow.

---

# 11. Customer = Unlimited

```text
Customer:
UNLIMITED

Company Standard:
6 months

Legal Rule:
UNLIMITED = UNACCEPTABLE
```

Result:

```text
Finding:
DEVIATION

Rule Outcome:
UNACCEPTABLE
```

Again, the Legal Decision remains separate.

---

# 12. Missing liability cap

Suppose the Requirement is:

```text
LIABILITY-001
Required = YES
```

but no qualifying limitation provision can be identified.

Then:

```text
Finding:
MISSING
```

provided the system has sufficient evidence to establish that the provision is genuinely absent.

We must distinguish:

```text
No provision found
```

from:

```text
Provision exists but extraction failed
```

The second case should not be incorrectly classified as `MISSING`; it may be:

```text
UNABLE_TO_EVALUATE
```

The specification explicitly requires this fail-closed behavior.

---

# 13. Ambiguous liability provision

Example:

```text
Section 8:
6 months

Schedule B:
12 months
```

If deterministic rules cannot establish which provision governs:

```text
Finding:
AMBIGUOUS
```

or, depending on the exact stage where the uncertainty arises:

```text
UNRESOLVED
/
UNABLE_TO_EVALUATE
```

The engine must **not** simply select 6 because it appears first, or 12 because it has a stronger keyword score.

The specification explicitly says multiple contradictory provisions must trigger conflict handling rather than silent selection.

---

# 14. Conflict case

Example:

```text
Section 8.2
Aggregate liability = 6 months

Schedule B
Liability = unlimited
```

The result should preserve:

```text
Evidence A
    ↓
6 months

Evidence B
    ↓
Unlimited
```

and produce:

```text
Finding:
CONFLICT
```

rather than:

```text
Finding:
DEVIATION
Actual:
6 months
```

because that would discard material evidence.

---

# 15. Negative patterns

This is particularly important for liability.

Example:

> "Liability shall not be limited in respect of fraud."

This contains words associated with limitation of liability but is actually describing an **exception to the limitation**.

Therefore the extractor/mapping configuration needs:

```text
Positive patterns
Negative patterns
Exception patterns
Scope patterns
```

The master specification explicitly requires negative patterns and carve-outs.

---

# 16. Cross-reference

Example:

> "The limitation set forth in Section 8 shall not apply to the obligations described in Section 14."

The evaluator should preserve:

```text
8
 ↓
references
 ↓
14
```

Then downstream evaluation can inspect Section 14.

We should **not attempt to build general legal reasoning here**. The requirement is simply:

> preserve deterministic cross-reference relationships where they can be safely resolved.

That is already part of the locked architecture.

---

# 17. Final liability evaluation matrix

| Customer provision                            | Finding                    | Rule outcome        |
| --------------------------------------------- | -------------------------- | ------------------- |
| 6 months                                      | `MATCH`                    | —                   |
| 12 months                                     | `DEVIATION`                | `ACCEPTABLE`        |
| 24 months                                     | `DEVIATION`                | `APPROVAL_REQUIRED` |
| Unlimited                                     | `DEVIATION`                | `UNACCEPTABLE`      |
| No required provision                         | `MISSING`                  | —                   |
| Contradictory provisions                      | `CONFLICT`                 | —                   |
| Cannot determine intended provision           | `AMBIGUOUS` / `UNRESOLVED` | —                   |
| Evidence insufficient for reliable evaluation | `UNABLE_TO_EVALUATE`       | —                   |

The exact Finding classifications have some historical evolution in the document, including an earlier five-type model and the later expanded evaluation model. Since Step 44 and the later evaluator sections explicitly use the expanded classifications, **Step 45 should follow the later locked architecture rather than reintroducing the older five-type-only model.**

---

# 18. Most important separation

The final Liability pipeline should be:

```text
CUSTOMER CONTRACT
       ↓
Evidence
       ↓
LIABILITY-001 Mapping
       ↓
Liability Fact Extraction
       ↓
Structured Liability Facts
       ↓
Company Standard Comparison
       ↓
Legal Rule Evaluation
       ↓
Finding
       ↓
Evidence + Explanation
       ↓
Review Workflow
       ↓
Authorized Legal Decision
```

Not:

```text
Contract
 ↓
AI/heuristic
 ↓
"High Risk"
 ↓
Reject
```

That would violate the entire V1 architecture.

---

# 19. Proposed Step 45A lock

I would lock the following:

### 🔒 LIABILITY-001 — LOCKED

1. `LIABILITY-001` is the canonical Limitation of Liability Requirement.
2. It is a required MSA Requirement unless configuration explicitly changes its applicability.
3. Liability extraction is Requirement-specific and deterministic.
4. The evaluator identifies whether a finite cap, unlimited liability, absent provision, or indeterminate provision exists.
5. The evaluator preserves value, unit, basis, scope, and exceptions/carve-outs where deterministically extractable.
6. Original evidence remains attached to every extracted fact.
7. The Company Standard is **6 months**.
8. `6 months` → `MATCH`.
9. `12 months` → `DEVIATION` + configured `ACCEPTABLE` rule outcome.
10. `>12 months` → `DEVIATION` + configured `APPROVAL_REQUIRED` rule outcome.
11. `UNLIMITED` → `DEVIATION` + configured `UNACCEPTABLE` rule outcome.
12. Absence of a required qualifying provision may produce `MISSING`.
13. Insufficient extraction/evidence must produce `UNABLE_TO_EVALUATE`, not a guessed result.
14. Multiple contradictory liability provisions must be preserved and evaluated as `CONFLICT` where incompatibility is established.
15. Ambiguous provisions must not be silently resolved.
16. Carve-outs and exceptions must not be discarded.
17. Cross-references must be preserved and resolved only where deterministic and safe.
18. The evaluator does not make a Legal Decision.
19. Finding classification and Legal Rule outcome remain separate.
20. All evaluation inputs and applicable configuration versions must be retained for reproducibility.
21. No LLM, RAG, embeddings, vector search, or semantic AI is introduced into this evaluator.

### Status

```text
Steps 1–44
🔒 LOCKED

Step 45
⏳ IN PROGRESS

Step 45A — LIABILITY-001
🔒 READY TO LOCK
```

**I recommend we lock 45A now.** Then Step 45B should define the actual **evaluator data contract/schema**—the precise input/output fields for `LIABILITY-001`—before we move on to another legal requirement. That is the point where we turn this from policy into an implementation-ready specification.
Yes. We are now doing **Step 45B — Evaluator Data Contract / Schema**.

I checked the master specification again. It already establishes the important foundation: evaluations are separate from Findings, numeric evaluations preserve expected/actual/operator/rule information, and every evaluation must preserve the exact versioned context used.

# Step 45B — Evaluator Data Contract

The purpose of 45B is to define the **exact contract between Fact Extraction and the Evaluator**, and between the Evaluator and Finding Generation.

The architecture is:

```text
Evidence
   ↓
Requirement-specific Fact Extraction
   ↓
Evaluator Input
   ↓
Deterministic Evaluator
   ↓
Evaluation Result
   ↓
Finding Generator
   ↓
Finding
```

The evaluator must **not go back and independently search the whole document**.

---

# 45B.1 Evaluator Input

For `LIABILITY-001`, the evaluator receives five groups of information:

```text
EvaluatorInput
│
├── Requirement Context
├── Evidence
├── Extracted Facts
├── Company Standard
├── Legal Rule
└── Evaluator Version
```

Conceptually:

```text
EvaluatorInput {
    requirement_version
    evidence[]
    facts
    company_standard
    legal_rule
    evaluator_version
}
```

This is consistent with the master specification's requirement that a Review preserve the Requirement, Standard, Rule, Evaluation Rules and Evidence context.

---

# 45B.2 Requirement Context

The evaluator must know exactly **which Requirement it is evaluating**.

```text
RequirementContext
├── requirement_id
├── requirement_code
├── requirement_version_id
└── document_type
```

For example:

```text
requirement_id:
...

requirement_code:
LIABILITY-001

requirement_version_id:
...

document_type:
MSA
```

The evaluator must never rely only on:

```text
"liability"
```

as its identity.

It must use the versioned Requirement.

---

# 45B.3 Evidence Reference

Every extracted fact must remain traceable to source evidence.

The evidence object should conceptually contain:

```text
EvidenceReference
├── evidence_id
├── document_version_id
├── page_number
├── section_number
├── section_title
├── source_type
└── content_reference
```

The existing schema already establishes `document_evidence` with document version, processing run, page, section, content, source type and offsets.

The evaluator should receive **references**, not duplicated uncontrolled copies of the document.

---

# 45B.4 Liability Facts

For `LIABILITY-001`, the minimum structured fact model should be:

```text
LiabilityFacts
├── cap_status
├── cap_value
├── cap_unit
├── cap_basis
├── scope
├── exceptions[]
├── evidence_refs[]
└── extraction_status
```

### `cap_status`

Controlled values:

```text
FINITE
UNLIMITED
ABSENT
UNKNOWN
```

### `cap_value`

Example:

```text
6
12
24
```

Nullable when the cap is:

```text
UNLIMITED
ABSENT
UNKNOWN
```

### `cap_unit`

Example:

```text
MONTHS
DAYS
CURRENCY
PERCENTAGE
OTHER
```

### `cap_basis`

Example:

```text
FEES_PAID
FEES_PAYABLE
CONTRACT_VALUE
FIXED_AMOUNT
OTHER
UNKNOWN
```

We should **not assume equivalence between different bases**.

---

# 45B.5 Scope

Scope must remain explicit.

Example:

```text
scope:
AGGREGATE
```

Other possible controlled values can include:

```text
PER_CLAIM
PER_EVENT
PARTY_SPECIFIC
CATEGORY_SPECIFIC
OTHER
UNKNOWN
```

The important principle is that the evaluator must not turn:

```text
aggregate liability cap = 6 months
```

into:

```text
all liability = 6 months
```

without evidence.

The master specification specifically requires scope and carve-outs to be preserved.

---

# 45B.6 Exceptions / Carve-outs

Represent them separately:

```text
exceptions: [
    {
        concept: "fraud",
        evidence_ref: "..."
    },
    {
        concept: "wilful misconduct",
        evidence_ref: "..."
    },
    {
        concept: "confidentiality breach",
        evidence_ref: "..."
    }
]
```

This is important because:

```text
General Cap
+
Exceptions
```

is materially different from simply:

```text
Cap = 6 months
```

The specification explicitly gives this liability example.

---

# 45B.7 Extraction Status

The evaluator needs to know whether the facts are actually usable.

Controlled states:

```text
COMPLETE
PARTIAL
AMBIGUOUS
FAILED
```

Example:

```text
cap_status = UNKNOWN
extraction_status = FAILED
```

The evaluator must then be capable of returning:

```text
UNABLE_TO_EVALUATE
```

rather than guessing.

---

# 45B.8 Company Standard Input

For `LIABILITY-001`:

```text
CompanyStandard
├── version_id
├── preferred_value
└── preferred_unit
```

Current authoritative configuration:

```text
preferred_value:
6

preferred_unit:
MONTHS
```

The master specification establishes 6 months as the preferred Company Standard.

---

# 45B.9 Legal Rule Input

The Legal Rule must be separate from the Company Standard.

Conceptually:

```text
LegalRule
├── version_id
├── acceptable_max
├── acceptable_max_unit
├── approval_required_above
├── unlimited_outcome
└── rule_configuration
```

Current authoritative example:

```text
acceptable_max:
12 months

approval_required_above:
12 months

unlimited:
UNACCEPTABLE
```

This separation is critical:

```text
Company Standard:
6 months

Legal Rule:
≤12 months acceptable
>12 months approval required
Unlimited unacceptable
```

The master specification explicitly distinguishes these concepts.

---

# 45B.10 Evaluator Version

Every evaluation must identify the exact evaluator implementation/version.

```text
evaluator_version:
LIABILITY-EVALUATOR-v1
```

This is different from:

```text
Requirement Version
Company Standard Version
Legal Rule Version
```

All four matter.

```text
Requirement v3
+
Company Standard v5
+
Legal Rule v4
+
Evaluator v1
```

This gives us reproducibility.

The specification requires the evaluator version and exact configuration context to be retained for historical reproducibility.

---

# 45B.11 Complete Evaluator Input

So the conceptual contract becomes:

```text
LIABILITY_EVALUATOR_INPUT

{
    requirement: {
        id,
        code,
        version_id
    },

    evidence: [
        {
            evidence_id,
            document_version_id,
            page_number,
            section_number,
            section_title
        }
    ],

    facts: {
        cap_status,
        cap_value,
        cap_unit,
        cap_basis,
        scope,
        exceptions[],
        evidence_refs[],
        extraction_status
    },

    company_standard: {
        version_id,
        preferred_value,
        preferred_unit
    },

    legal_rule: {
        version_id,
        acceptable_max,
        acceptable_max_unit,
        approval_required_above,
        unlimited_outcome
    },

    evaluator_version
}
```

This is the **logical contract**. We do not need to commit to this exact JSON representation in the database yet.

---

# 45B.12 Evaluator Output

The evaluator returns:

```text
EvaluationResult
├── classification
├── rule_outcome
├── expected_value
├── actual_value
├── comparison
├── evaluated_facts
├── evidence_refs[]
├── explanation
├── diagnostics
└── evaluator_version
```

---

# 45B.13 Classification

Controlled V1 classifications:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

The master specification supports this expanded classification model.

---

# 45B.14 Rule Outcome

This is **not the same thing as Finding classification**.

For example:

```text
classification:
DEVIATION

rule_outcome:
ACCEPTABLE
```

or:

```text
classification:
DEVIATION

rule_outcome:
APPROVAL_REQUIRED
```

or:

```text
classification:
DEVIATION

rule_outcome:
UNACCEPTABLE
```

This preserves:

```text
Finding
   ≠
Rule Outcome
   ≠
Legal Decision
```

The specification explicitly says the Evaluation Engine does not produce the Legal Decision.

---

# 45B.15 Comparison Object

For numeric evaluation, preserve the actual calculation.

Example:

```text
comparison: {
    expected_value: 6,
    expected_unit: "MONTHS",

    actual_value: 12,
    actual_unit: "MONTHS",

    operator: "GREATER_THAN",

    acceptable_max: 12,
    acceptable_max_unit: "MONTHS",

    result: "DEVIATION_WITHIN_ACCEPTABLE_RANGE"
}
```

This is much better than storing only:

```text
DEVIATION
```

The specification explicitly requires preservation of expected value, actual value, operator, threshold and evaluation.

---

# 45B.16 Explanation

The evaluator should produce a **deterministic explanation**, not AI-generated prose.

Example:

```text
Customer liability cap:
12 months

Company Standard:
6 months

Comparison:
12 months > 6 months

Configured acceptable maximum:
12 months

Rule:
12 months is within acceptable maximum

Evaluation:
DEVIATION / ACCEPTABLE
```

This explanation can then be presented in the UI.

---

# 45B.17 Diagnostics

Diagnostics are for system/debugging purposes and should not become legal conclusions.

Examples:

```text
diagnostics:
[
    "Cap value successfully extracted",
    "Unit normalized to MONTHS",
    "Scope identified as AGGREGATE",
    "No conflicting cap detected"
]
```

Or:

```text
[
    "Two candidate liability provisions detected",
    "Governing provision could not be determined"
]
```

This helps explain why an evaluation became:

```text
AMBIGUOUS
```

or:

```text
UNABLE_TO_EVALUATE
```

---

# 45B.18 Evidence must survive the evaluator

This is a hard requirement.

For:

```text
Finding F-001
```

we must be able to trace:

```text
F-001
 ↓
Evaluation E-001
 ↓
Evidence EVD-182
 ↓
Document Version DV-4
 ↓
Page 12
 ↓
Section 8.2
 ↓
Original source text
```

The master schema explicitly separates `evaluations` from `findings` and provides `finding_evidence` for this purpose.

---

# 45B.19 Example — MATCH

Input:

```text
Actual:
6 months

Expected:
6 months
```

Output:

```text
classification:
MATCH

rule_outcome:
NOT_APPLICABLE

comparison:
6 == 6
```

---

# 45B.20 Example — ACCEPTABLE DEVIATION

Input:

```text
Actual:
12 months

Expected:
6 months

Acceptable max:
12 months
```

Output:

```text
classification:
DEVIATION

rule_outcome:
ACCEPTABLE

comparison:
12 > 6
AND
12 <= 12
```

---

# 45B.21 Example — Approval Required

```text
Actual:
24 months

Expected:
6 months

Acceptable max:
12 months
```

Output:

```text
classification:
DEVIATION

rule_outcome:
APPROVAL_REQUIRED

comparison:
24 > 6
AND
24 > 12
```

The evaluator stops here.

It does **not** generate:

```text
APPROVE
REJECT
ACCEPT
```

Those belong to the Legal Decision workflow.

---

# 45B.22 Example — Unlimited

```text
cap_status:
UNLIMITED
```

Output:

```text
classification:
DEVIATION

rule_outcome:
UNACCEPTABLE
```

assuming the applicable Legal Rule says Unlimited is unacceptable.

---

# 45B.23 Example — Missing

If the Requirement is required and deterministic evidence establishes that there is no qualifying liability provision:

```text
classification:
MISSING

rule_outcome:
NOT_APPLICABLE
```

We should not put:

```text
actual_value = 0
```

because absence of a clause is not numerically equivalent to zero.

---

# 45B.24 Example — Unable to Evaluate

Suppose:

```text
Evidence exists
    ↓
OCR damaged
    ↓
Cannot reliably determine whether "6" or "8" was extracted
```

Output:

```text
classification:
UNABLE_TO_EVALUATE

rule_outcome:
NOT_APPLICABLE
```

with diagnostics explaining the extraction problem.

---

# 45B.25 Example — Conflict

```text
Evidence A:
6 months

Evidence B:
Unlimited
```

Output:

```text
classification:
CONFLICT

rule_outcome:
NOT_APPLICABLE
```

Both evidence references remain attached.

The evaluator does not silently choose:

```text
6
```

or:

```text
Unlimited
```

---

# 45B.26 Important rule: no arbitrary NULL semantics

We need to explicitly lock this.

These are **not equivalent**:

```text
NULL
0
ABSENT
UNKNOWN
UNLIMITED
```

For example:

```text
cap_value = NULL
cap_status = UNLIMITED
```

means something very different from:

```text
cap_value = NULL
cap_status = UNKNOWN
```

This prevents database-level ambiguity from becoming legal-analysis ambiguity.

---

# 45B.27 Persistence model

The logical evaluator result can be persisted through the existing `evaluations` model:

```text
evaluations
-----------
id
finding_id
evaluator_type
expected_value
actual_value
operator
result
rule_version_id
created_at
```

The master specification already proposes this separation.

However, for `LIABILITY-001`, I recommend that the implementation **not squeeze every structured fact into `expected_value` / `actual_value` strings**.

The complete structured evaluator payload should be retained in a controlled structured field or related tables, while important queryable relationships remain relational.

That is consistent with the broader database rule that structured domain data should not be hidden entirely inside arbitrary JSON.

---

# 45B.28 Final 45B contract

The authoritative flow is now:

```text
                 DOCUMENT EVIDENCE
                        ↓
              LIABILITY FACTS
                        ↓
              ┌─────────────────┐
              │ EVALUATOR INPUT │
              └────────┬────────┘
                       │
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
 Requirement      Company Standard   Legal Rule
 Version              Version          Version
       │               │                │
       └───────────────┼────────────────┘
                       ↓
               Evaluator Version
                       ↓
             DETERMINISTIC EVALUATOR
                       ↓
              EVALUATION RESULT
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
   Classification  Rule Outcome  Comparison
          │            │            │
          └────────────┼────────────┘
                       ↓
                Evidence + Explanation
                       ↓
                    FINDING
                       ↓
                LEGAL WORKFLOW
```

## 🔒 45B proposed lock

I recommend locking these **before moving to 45C**:

1. Evaluators receive structured, versioned inputs.
2. Evaluators do not independently search or reinterpret the whole document.
3. Requirement Version is explicit input.
4. Evidence references are explicit input.
5. Requirement-specific facts are explicit input.
6. Company Standard Version is explicit input.
7. Legal Rule Version is explicit input.
8. Evaluator Version is explicit input.
9. Liability facts preserve cap status, value, unit, basis, scope, exceptions and evidence references.
10. `NULL`, `ABSENT`, `UNKNOWN`, `UNLIMITED`, and numeric zero are distinct concepts.
11. Evaluator output contains both Finding classification and Rule Outcome.
12. Numeric comparisons preserve expected value, actual value, units, operator, threshold and result.
13. Evaluations are persisted separately from Findings.
14. Evidence references remain attached to the evaluation/finding chain.
15. Deterministic explanations are retained.
16. Diagnostics may explain processing/evaluation limitations but do not constitute legal conclusions.
17. `MISSING`, `CONFLICT`, `AMBIGUOUS`, and `UNABLE_TO_EVALUATE` do not manufacture numeric values.
18. Evaluators never produce Legal Decisions.
19. The complete version context is retained for reproducibility.
20. The evaluator contract is implementation-independent: the logical contract is authoritative; the physical PostgreSQL representation can be finalized during schema implementation.

### Current position

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
Step 45B         ⏳ REVIEW
```

**I recommend locking 45B after one final check, then moving to 45C — Liability Edge Cases.** That is where we test whether this contract survives the difficult real-world cases: multiple caps, carve-outs, per-claim vs aggregate caps, different monetary bases, cross-references, conflicting schedules, and malformed/ambiguous clauses.

---
---

# Post-Step-44 Cross-Document Reconciliation Decisions

**Status: LOCKED**
**Date: 2026-08-16**
**Nature: reconciliation only — these decisions resolve how existing locked decisions relate to one another.**

## Scope and authority of this section

This section is **not** a continuation of the Step 1–45 decision sequence. It was produced by a cross-step reconciliation review conducted after Step 45B was drafted, to resolve apparent conflicts between decisions locked in different steps.

Rules governing this section:

1. **No historical text above this section has been modified.** Steps 1–45B remain exactly as originally written.
2. **No locked rule has been overturned.** Where a vocabulary is superseded, the behavioural rules of the originating step remain in force.
3. These decisions establish **canonical status and layer separation**, not new legal policy.
4. Where a reconciliation decision supersedes a vocabulary, the original step remains locked and its text remains authoritative as the historical record of what was decided and when.

---

## REC-01 — Finding Classification supersession chain

**Status: LOCKED**

Steps 18 → 27 → 36 are a **supersession chain, not a contradiction**.

The **Step 36 seven-value set is canonical** for Finding Classification:

```text
MATCH
DEVIATION
MISSING
CONFLICT
AMBIGUOUS
UNRESOLVED
UNABLE_TO_EVALUATE
```

Reconciliation of the differences:

```text
MATCH / DEVIATION / MISSING
    → stable across Steps 18, 27, 36

CONFLICT / UNABLE_TO_EVALUATE
    → added by Step 27 (additive refinement)

AMBIGUOUS / UNRESOLVED
    → added by Step 36 (additive refinement)

ADDITIONAL (Step 18) → EXTRA (Step 27)
    → pure rename; definitions are near-verbatim
    → both now superseded by UNMATCHED_PROVISION (REC-02)

UNMAPPED (Step 18)
    → layer migration, not deletion
    → Step 18 defines it as a mapping failure
    → formalized by Step 28 as mapping state UNRESOLVED
```

The absence of `EXTRA` from Step 36 is **scope narrowing, not repeal**: Step 36 defines the outcome set of evaluating a *mapped Requirement*, and an unmatched provision has no Requirement to evaluate.

This ratifies Step 45A §17, which already stated that Step 45 should follow the later expanded classification model.

**Steps 18 and 27 remain LOCKED.** Their vocabularies are superseded; their behavioural rules (Step 18 rules 6–11, Step 27 rules 1–18) remain fully in force.

---

## REC-02 — UNMATCHED_PROVISION

**Status: LOCKED**

`ADDITIONAL` (Step 18) and `EXTRA` (Step 27) are superseded by:

```text
UNMATCHED_PROVISION
```

A provision that exists in the counterparty document with no corresponding configured Requirement is recorded as an **`UNMATCHED_PROVISION` document-level observation**.

It is **not** a Finding Classification and must never occupy a Finding's `classification` field.

The locked rules that governed `ADDITIONAL`/`EXTRA` carry over unchanged:

1. An unmatched provision is not automatically negative or unacceptable.
2. It retains traceable evidence.
3. It does not itself determine legal acceptability.

**NOT YET SPECIFIED:** the persistence model, surfacing, and review treatment of `UNMATCHED_PROVISION` observations.

---

## REC-03 — Mapping State canonicalization

**Status: LOCKED**

Step 28's mapping states are the canonical **persisted** mapping vocabulary:

```text
CONFIRMED
AMBIGUOUS
UNRESOLVED
```

Step 35's vocabulary (`CANDIDATE`, `CANDIDATE-REVIEW`, `NOT MAPPED`, `NO_CONFIDENT_MAPPING`) consists of **internal scoring-stage labels**, not persisted states. Step 35's numerical weights and thresholds remain PROVISIONAL as originally stated.

Step 28 and Step 35 are different stages of the same layer, not competing vocabularies.

**NOT YET SPECIFIED — explicitly deferred:** how Step 35's scoring bands map onto Step 28's three persisted states. It is **not** established whether `CANDIDATE-REVIEW` corresponds to `AMBIGUOUS`, to `UNRESOLVED`, or to neither. This must not be inferred or implemented until explicitly decided.

---

## REC-04 — Step 33 classification

**Status: LOCKED (classification only)**

Step 33 is a **PROVISIONAL elaboration of locked Step 26**, not a competing or conflicting decision.

A rule-by-rule comparison of Step 26's 17 locked rules against Step 33's 24 proposed rules found **no contradiction**; Step 33 either restates or narrows Step 26 throughout.

Step 33 itself **remains unlocked**, as originally stated ("Do not lock it yet until you confirm it looks right").

Three Step 33 rules have no Step 26 counterpart and therefore **remain unlocked and must not be implemented or assumed**:

1. System-controlled sequential version numbering that users cannot rewrite (33.6; rules 6–7)
2. Incorrect versions marked invalid/withdrawn rather than erased, and versions used by historical Reviews not hard-deletable (33.13–33.14; rules 15–16)
3. The explicit predecessor relationship chain v1 → v2 → v3 (33.17; rule 17)

---

## REC-05 — Step 45B corrections (Revision R1)

**Status: corrections LOCKED; Step 45B itself remains ⏳ REVIEW — NOT LOCKED**

### R1.1 — `rule_configuration` restored to the complete evaluator input

45B.9 lists `rule_configuration` on the `LegalRule` tree, but 45B.11 omits it. This is an internal inconsistency, not a decision. `rule_configuration` **is** part of the evaluator contract.

**NOT YET SPECIFIED:** the shape and contents of `rule_configuration`.

### R1.2 — `extraction_diagnostics` restored to the evaluator input

Step 45A carried `extraction_diagnostics`. Step 45B replaced it with the controlled enum `extraction_status` and placed free-form `diagnostics` only on the evaluator output, leaving the evaluator able to see *that* extraction was `PARTIAL` but not *why*.

Facts carry **both**:

```text
extraction_status        → controlled enum, drives control flow
extraction_diagnostics   → free-form, explains the status
```

### R1.3 — Ratified refinements over Step 45A

```text
cap_exists + cap_type  →  cap_status
    A boolean plus a status enum is two sources of truth,
    and a boolean cannot express UNKNOWN.
    Enum values FINITE / UNLIMITED / ABSENT / UNKNOWN unchanged from 45A §4.

rule outcome "—"       →  NOT_APPLICABLE
    Required by 45B.26 (no arbitrary NULL semantics).
```

### R1.4 — Axis conformance

45B.13's classification set already matches the canonical vocabulary (REC-01); no change required.

`ExtractionStatus.AMBIGUOUS`, `MappingState.AMBIGUOUS` and `Classification.AMBIGUOUS` are **three different values** on three different layers and must not share an enum.

`extraction_status` is a fact-quality signal on the evaluator input, not one of the five axes. A `FAILED` extraction must produce `UNABLE_TO_EVALUATE` rather than a guess.

### Revised evaluator input

```text
facts: {
    cap_status,
    cap_value,
    cap_unit,
    cap_basis,
    scope,
    exceptions[],
    evidence_refs[],
    extraction_status,
    extraction_diagnostics
},

legal_rule: {
    version_id,
    acceptable_max,
    acceptable_max_unit,
    approval_required_above,
    unlimited_outcome,
    rule_configuration
}
```

The evaluator output defined in 45B.12 is unchanged by this revision.

---

## REC-06 — Decision State Model (five axes)

**Status: LOCKED**

This makes explicit the separation already locked in Step 30 ("A single status field must not be used to represent all of these concepts").

Five distinct axes exist. **A single status field must never represent more than one of them, and no axis may share an enum with another.**

```text
AXIS 1 — Mapping State
    Which Requirement does this clause relate to?
    CONFIRMED / AMBIGUOUS / UNRESOLVED
    (Step 28)

AXIS 2 — Finding Classification (= Evaluation Outcome)
    What is the comparison result for this Requirement?
    MATCH / DEVIATION / MISSING / CONFLICT /
    AMBIGUOUS / UNRESOLVED / UNABLE_TO_EVALUATE
    (Steps 36, 44, 45A, 45B)

AXIS 3 — Rule Outcome
    How does the organization tolerate this result?
    ACCEPTABLE / APPROVAL_REQUIRED / UNACCEPTABLE / NOT_APPLICABLE
    (Steps 27, 31, 45B.14)

AXIS 4 — Legal Decision
    What did an authorized human rule?
    ACCEPT_DEVIATION / REQUIRE_COMPANY_STANDARD /
    APPROVE_CUSTOMIZATION / REJECT / REQUEST_CLARIFICATION
    (Step 31)

AXIS 5 — Review Lifecycle
    Where is this Review in the workflow?
    DRAFT → UPLOADED → PROCESSING → ANALYSIS_COMPLETE →
    LEGAL_REVIEW → RESOLVED → CLOSED
    Exceptions: ANALYSIS_FAILED, CANCELLED
    (Step 30)
```

Finding Classification and Evaluation Outcome are the **same axis**, persisted as the `classification` field of the evaluator output. The axis commonly confused with it is Rule Outcome, which 45B.14 already states is "not the same thing as Finding classification."

`UNMATCHED_PROVISION` (REC-02) is a document-level observation and is **not** one of the five axes.

### Locked bridge rules

```text
Axis 1 → Axis 2
    Mapping AMBIGUOUS or UNRESOLVED may produce UNABLE_TO_EVALUATE,
    never a guessed classification.                        (Step 28 rule 6)

    A required Requirement with no mapped provision
    may produce MISSING.                                   (Step 28 rule 5)

Axis 2 → Axis 3
    Classification and Rule Outcome are evaluated separately.
    DEVIATION does not imply unacceptable.                 (Steps 18, 27, 36, 45B.14)

    Where no rule outcome applies, the value is the explicit
    NOT_APPLICABLE — never null.                           (45A §17, 45B.26)

Axis 3 → Axis 4
    The engine never produces a Legal Decision.            (Steps 27, 31, 36.15, 45A, 45B.14)

Axis 5 ⇄ Axis 2
    RESOLVED ≠ MATCH.                                      (Step 22 clarification, Step 30)

    ANALYSIS_FAILED (Review-level) is distinct from
    UNABLE_TO_EVALUATE (Finding-level).                    (Step 30)
```

---

## REC-07 — Extraction diagnostics persistence

**Status: LOCKED**

`extraction_diagnostics` is **persisted** as part of the evaluation/evidence record, for auditability and reproducibility.

Constraints:

1. Diagnostics are **diagnostic metadata only**.
2. Diagnostics **cannot independently produce or alter a legal finding**.
3. Diagnostics must never constitute a legal conclusion (consistent with 45B.17).

This resolves the persistence question left open by 45B.27.

---

## Current position

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
REC-01 – REC-07  🔒 LOCKED
Step 45B         ⏳ REVIEW
```

Step 45B remains under review. The three housekeeping actions identified before locking are now complete:

```text
rule_configuration      → NOT YET SPECIFIED   ✅ recorded
extraction_diagnostics  → PERSISTED           ✅ REC-07
REC-01 – REC-07         → in all_lock.md      ✅ this section
```

Next: final review of Step 45B, then Step 45C — Liability Edge Cases.

---
---

# Step 45B — LOCK RECORD

**Status: 🔒 LOCKED**
**Date: 2026-08-16**

Step 45B — Evaluator Data Contract is hereby locked, comprising:

1. Sections 45B.1 – 45B.28 as originally written above, **unmodified**.
2. The Revision R1 corrections recorded in `REC-05`.
3. The persistence decision recorded in `REC-07`.

## What is locked

```text
Evaluator Input      45B.1 – 45B.11  (as corrected by REC-05 R1.1, R1.2)
Evaluator Output     45B.12 – 45B.17
Evidence survival    45B.18
Worked examples      45B.19 – 45B.25  (seven examples, authoritative)
NULL semantics       45B.26
Persistence model    45B.27  (as completed by REC-07)
Final contract       45B.28
```

## Locked evaluator input

```text
LIABILITY_EVALUATOR_INPUT

{
    requirement: {
        id,
        code,
        version_id
    },

    evidence: [
        {
            evidence_id,
            document_version_id,
            page_number,
            section_number,
            section_title
        }
    ],

    facts: {
        cap_status,
        cap_value,
        cap_unit,
        cap_basis,
        scope,
        exceptions[],
        evidence_refs[],
        extraction_status,
        extraction_diagnostics
    },

    company_standard: {
        version_id,
        preferred_value,
        preferred_unit
    },

    legal_rule: {
        version_id,
        acceptable_max,
        acceptable_max_unit,
        approval_required_above,
        unlimited_outcome,
        rule_configuration
    },

    evaluator_version
}
```

## Locked evaluator output

```text
EvaluationResult
├── classification
├── rule_outcome
├── expected_value
├── actual_value
├── comparison
├── evaluated_facts
├── evidence_refs[]
├── explanation
├── diagnostics
└── evaluator_version
```

## Explicitly NOT locked by this step

```text
rule_configuration — shape and contents
    Status: NOT YET SPECIFIED

The field is a locked part of the contract.
Its contents are not specified and must not be invented.
It is an explicit extension point, not an implied schema.
```

Also not locked by this step: the physical PostgreSQL representation. Per 45B.28 item 20, the logical contract is authoritative and the physical representation is finalized during schema implementation.

## Current position

```text
Steps 1–44       🔒 LOCKED
Step 45A         🔒 LOCKED
REC-01 – REC-07  🔒 LOCKED
Step 45B         🔒 LOCKED
Step 45C         ⏳ IN PROGRESS
```

Next: **Step 45C — Liability Edge Cases.**

---
---

# Amendment Batch AB-1 — Evaluator & Decision Model

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Approved by: project owner**
**Nature: representational repair. No legal policy is changed by any amendment in this batch.**

## Scope and authority

This section amends specific locked decisions. Per the established pattern of the Post-Step-44 Reconciliation section:

1. **No historical text above this section has been modified.** Every step remains exactly as originally written.
2. Each amendment states its target, the original text, and the replacement.
3. Every amendment repairs a case where a **locked requirement could not be represented by the locked schema**. None introduces, removes or reinterprets a legal rule.
4. Where an amendment restates a locked rule, only the named rule changes; the remainder of that step is untouched.

---

## AB-1.1 — `legal_decisions` (amends 40.12, 41.21, 42.17)

Three locked definitions of the Legal Decision record are amended consistently.

### AM-1 · Decisions target a scoped Evaluation

```text
ADD    evaluation_id  UUID FK → evaluations.id  NOT NULL
KEEP   finding_id     UUID FK → findings.id     NOT NULL

CONSTRAINT
    FOREIGN KEY (finding_id, evaluation_id)
        REFERENCES evaluations(finding_id, id)
    requires UNIQUE(id, finding_id) on evaluations
```

A Legal Decision resolves exactly one Evaluation and never implicitly disposes of another Evaluation under the same Finding.

### AM-12 · Decision supersession is append-only

```text
ADD    version_number  INTEGER NOT NULL
       UNIQUE(evaluation_id, version_number)
       INDEX(evaluation_id, version_number DESC)
```

The current decision for an Evaluation is the row with the highest `version_number`. Prior rows are never updated and never deleted. This implements locked Step 31 r14 ("creates a new decision version rather than overwriting") and r20 ("the current decision must always be distinguishable from historical decisions") — **neither of which is amended.**

### AM-15 · A reason is mandatory

```text
CHANGE decision_text TEXT           →  justification TEXT NOT NULL
```

Locked Step 31 r11 requires every Legal Decision to carry a reason. The locked schema left the column nullable, leaving r11 unenforced. `justification` is the canonical field name; `decision_text` (41.21, 42.17) and `justification` (40.12) are reconciled to it. `metadata` (40.12 only) is dropped from the canonical schema.

### AM-13 · 41.21 aligned

`evaluation_id`, `version_number`, `justification NOT NULL` added, keeping Steps 41 and 42 consistent.

### AM-14 · 40.12 aligned

`LegalDecision` gains `evaluationId` and `versionNumber`.

### Canonical record

```text
legal_decisions
---------------
id                UUID PK
finding_id        UUID FK → findings.id        NOT NULL
evaluation_id     UUID FK → evaluations.id     NOT NULL
decision_type     DECISION_TYPE                NOT NULL
justification     TEXT                         NOT NULL
decided_by        UUID FK → users.id           NOT NULL
version_number    INTEGER                      NOT NULL
created_at        TIMESTAMPTZ                  NOT NULL

UNIQUE(evaluation_id, version_number)
FOREIGN KEY (finding_id, evaluation_id) REFERENCES evaluations(finding_id, id)
INDEX(evaluation_id, version_number DESC)
INDEX(decided_by)
INDEX(created_at)
```

### Vocabulary reconciliation (no amendment)

41.21 lists `REQUIRE_STANDARD` under "For example" and defers to the Legal Decision workflow. Step 31 is that workflow and locks `REQUIRE_COMPANY_STANDARD`. **Step 31 governs. 41.21 is not amended** — it was illustrative.

---

## AB-1.2 — `evaluations` (amends 42.15)

### AM-8′ · Scoped evaluation discriminators and rule outcome

```text
ADD    scope_key        VARCHAR           NOT NULL
ADD    scope_label      VARCHAR           NULL
ADD    evaluation_kind  EVALUATION_KIND   NOT NULL     PRIMARY | EXCEPTION
ADD    rule_outcome     RULE_OUTCOME      NOT NULL     ACCEPTABLE | APPROVAL_REQUIRED |
                                                        UNACCEPTABLE | NOT_APPLICABLE
```

`scope_key` is validated against the Requirement's configured scope vocabulary (`rule_configuration.comparable_scopes`), not against a global enum — different Requirements have different sub-scopes. `UNKNOWN` remains reserved for undetermined scope. These are relational columns, not JSONB, because they are core discriminators (42.1 r10).

Rule outcome exists **only** at Evaluation level. No Finding-level rule outcome is persisted; any Finding-level notion is derived.

### AM-19 · Evaluator version

```text
ADD    evaluator_version  VARCHAR  NOT NULL
```

Locked 45B.10 requires every evaluation to identify the exact evaluator version. No column existed.

### AM-20 · Legal Rule version

```text
ADD    legal_rule_version_id  UUID FK → legal_rule_versions.id  NULL
```

The existing `rule_version_id` targets `evaluation_rule_versions` (42.11), a different table from `legal_rule_versions` (42.9). Without this column, locked Step 32's audit question 4 — "Which Legal Rule was used?" — is unanswerable. Nullable because locked Step 20 r4 permits a Requirement with no Pre-approved Legal Rule.

### AM-16 · `EVALUATOR_TYPE` defined

Referenced as `NOT NULL` in 42.7, 42.11 and 42.15; never defined. Defined now as:

```text
EVALUATOR_TYPE

NUMERIC_COMPARISON   Ordinal comparison of an extracted magnitude against
                     one or more configured thresholds.
                     Occupant: LIABILITY-001.

PRESENCE             Comparison of provision existence against the configured
                     expectation.
                     Parameter: expected_presence = PRESENT | ABSENT
                     Occupant: presence-mode Requirements.
```

36.12's wider list was explicitly a recommendation ("such as"). `MULTI_CLAUSE` and `CONFLICT_DETECTION` are engine behaviors, not selectable types (Step 28 r2, 44.18). `TEXT_PATTERN` belongs to mapping (35.4, 35.5, 35.10) and extraction (44.16) — an evaluator matching raw text would produce a Result without a Fact, breaking locked 44.33 explainability. `EXACT_MATCH` is a configuration of set-membership; `RANGE_COMPARISON` is multi-threshold numeric. Additional types are additive amendments when a Requirement needs one.

### Canonical record

```text
evaluations
-----------
id                     UUID PK
finding_id             UUID FK → findings.id                    NOT NULL
evaluator_type         EVALUATOR_TYPE                           NOT NULL
evaluator_version      VARCHAR                                  NOT NULL
scope_key              VARCHAR                                  NOT NULL
scope_label            VARCHAR                                  NULL
evaluation_kind        EVALUATION_KIND                          NOT NULL
classification         FINDING_CLASSIFICATION                   NOT NULL
rule_outcome           RULE_OUTCOME                             NOT NULL
expected_value         JSONB
actual_value           JSONB
operator               VARCHAR
result                 JSONB                                    NOT NULL
rule_version_id        UUID FK → evaluation_rule_versions.id
legal_rule_version_id  UUID FK → legal_rule_versions.id         NULL
created_at             TIMESTAMPTZ                              NOT NULL

UNIQUE(id, finding_id)
```

Extraction diagnostics are carried inside `result` (variable free-form data, sanctioned by 42.1 r10), satisfying REC-07. The Company Standard version is derived through the Review's configuration snapshot; no column is added.

---

## AB-1.3 — Step 31 restatements

Only the named rules change. Step 31's decision vocabulary, definitions, and rules 1–3, 5–15 and 18–20 are **untouched**.

### AM-2 · Rule 17

```text
WAS  A Legal Decision resolves the relevant Finding; it does not automatically
     constitute approval of the entire contract.

NOW  A Legal Decision resolves the relevant Evaluation; a Finding is resolved
     when every Evaluation requiring a decision has a current decision. It does
     not automatically constitute approval of the entire contract.
```

### AM-5 · Rule 4

```text
WAS  ACCEPT_DEVIATION applies only to the specific Review/Finding.
NOW  ACCEPT_DEVIATION applies only to the specific Review/Finding/Evaluation.
```

### AM-6 · Rule 16

```text
WAS  Before deciding, Legal must be shown the underlying evidence, Requirement,
     Company Standard, applicable Legal Rule, and Finding.

NOW  Before deciding, Legal must be shown the underlying evidence, Requirement,
     Company Standard, applicable Legal Rule, and Finding — including every
     scoped Evaluation under that Finding with its own applicable Legal Rule.
```

---

## AB-1.4 — Step 36.7 restatement

### AM-7

```text
WAS  36.7 UNRESOLVED
     The system has identified an issue but cannot complete the evaluation
     because required information or a required action is missing.
     This is different from AMBIGUOUS.

NOW  36.7 UNRESOLVED
     The system has identified relevant material but no usable answer can
     currently be established from the available information. This is different
     from AMBIGUOUS, where multiple plausible candidates exist but none can be
     confidently selected.

     Requirements for human action or clarification are workflow states —
     Finding status or Legal Decision — and are never expressed as a
     Classification.
```

**44.22 is NOT amended.** Its closing sentence — "This is different from the analytical classification" — already distinguishes the workflow state it describes from the axis-2 classification. The two are distinct concepts that shared a word; the workflow vocabulary is Finding status.

---

## AB-1.5 — New tables (no amendment to any locked table)

```text
evaluation_evidence
-------------------
evaluation_id      UUID FK → evaluations.id
evidence_id        UUID FK → document_evidence.id
relationship_type  EVIDENCE_RELATIONSHIP_TYPE NOT NULL   PRIMARY | SUPPORTING | CONFLICTING
PRIMARY KEY(evaluation_id, evidence_id)

No minimum-row constraint. Zero rows is a valid state.
```

Required because locked `finding_evidence` (42.16) cannot attribute evidence to a specific scoped Evaluation, which locked 45B.18 and 45C.25 require once a Finding carries several Evaluations. `finding_evidence` is retained unchanged as the Finding-level roll-up.

```text
unmatched_provisions
--------------------
id            UUID PK
review_id     UUID FK → reviews.id        NOT NULL
evidence_id   UUID FK → document_evidence.id NOT NULL
created_at    TIMESTAMPTZ                 NOT NULL
UNIQUE(review_id, evidence_id)
```

Implements REC-02: `UNMATCHED_PROVISION` is a document-level observation and must never occupy a Finding's `classification`.

---

## AB-1.6 — Additional constraints

```text
findings            UNIQUE(review_id, requirement_version_id)
evaluations         UNIQUE(id, finding_id)          -- supports the composite FK
EV-MIN              every Finding has ≥ 1 Evaluation
                    enforced by DEFERRABLE INITIALLY DEFERRED constraint trigger
                    (checked at COMMIT; service validation retained as fast-fail)
```

Evidence cardinality invariant (service-enforced, spans two tables per 42.21):

> Non-empty evidence is required for `MATCH`, `DEVIATION`, `CONFLICT` and `AMBIGUOUS`. Empty is permitted **only** for `MISSING` arising from established absence. **No synthetic evidence is ever created.**

---

## AB-1.7 — Engineering resolutions recorded

Determined from locked decisions and prior analysis; no legal policy invented.

```text
F-1   Optional Requirement with no mapped provision → NO Finding, NO Evaluation.
      MISSING excluded by 36.4 ("the Requirement is expected"); MATCH excluded
      by 36.2 ("customer provision conforms"). Coverage reporting satisfies
      Step 8's "which clauses were reviewed".

F-2   Second-person approval (Step 31 r15) operates at Evaluation level.

F-3   Escalation is recorded at Finding level (Steps 4, 22) and marks every
      Evaluation under that Finding as requiring a decision.

F-4   Configuration may only WIDEN decision requirements, never narrow them
      (reconciles Step 27 r12 with ENG-09 fail-closed).

F-6   45C.22 is narrowed to configured precedence only. In-document precedence
      language is detected, evidenced and reported — never applied.

F-8   Risk is a configured display mapping from (classification, rule_outcome)
      owned by the reporting layer. The evaluator emits no risk field.
      Honours 36.10 and Step 27 r12; Step 9's report element is satisfied.

F-9   Overall alignment is a reporting aggregation, not an evaluator output.

F-10  UNMATCHED_PROVISION persisted in its own table (AB-1.5).
```

---

## AB-1.8 — Withdrawn proposals

```text
AM-18  company_standard_versions.standard_kind
       WITHDRAWN — redundant. The kind is determined by
       requirement_versions.evaluator_type (42.7), and values live in
       company_standard_versions.configuration JSONB (42.8).

AM-21  company_standard_version_id on evaluations
       WITHDRAWN — derivable via the Review's configuration snapshot.

A-2    company_standard.scope as a schema change
       WITHDRAWN — it is a key inside the locked 42.8 configuration JSONB.
```

---
---

# Step 45B — RE-LOCK RECORD

**Status: 🔒 LOCKED (revised)**
**Date: 2026-08-17**

Step 45B is re-locked comprising 45B.1–45B.28 as originally written, plus REC-05 (R1), REC-07, and Amendment Batch AB-1.

## Locked evaluator input — `LIABILITY-001`

```text
{
    requirement:      { id, code, version_id },
    evidence:         [ { evidence_id, document_version_id,
                          page_number, section_number, section_title } ],
    facts: {
        caps: [ { cap_kind, scope, scope_label, cap_status,
                  cap_value, cap_unit, cap_basis, evidence_refs[] } ],
        extraction_status,
        extraction_diagnostics
    },
    company_standard: { version_id, configuration },
    legal_rule:       { version_id, acceptable_max, acceptable_max_unit,
                        approval_required_above, unlimited_outcome,
                        rule_configuration },
    evaluator_version
}
```

`company_standard.configuration` carries evaluator-specific values (scope, preferred value, unit) per locked 42.8.

## Locked evaluator output

```text
{
    evaluations: [ { scope_key, scope_label, evaluation_kind,
                     classification, rule_outcome,
                     expected_value, actual_value, comparison,
                     evaluated_facts, evidence_refs[],
                     explanation, diagnostics } ],
    finding_classification,
    evaluator_version
}
```

`finding_classification` is a **derived, non-authoritative summary**. The scoped Evaluation results are authoritative.

## Locked roll-up derivation

```text
TIER 1 (result cannot be relied upon — fail closed, ENG-09)
    UNABLE_TO_EVALUATE > CONFLICT > AMBIGUOUS > UNRESOLVED
TIER 2 (evaluated positions)
    MISSING > DEVIATION > MATCH

Any Tier-1 scope dominates every Tier-2 scope.
```

The tier split is derived from ENG-09: a Finding must never read `MATCH` while any scope is unevaluable, contradictory or absent. **The ordering within Tier 1 is an engineering determinism convention only — it is NOT a legal hierarchy.** All four Tier-1 states route to human review and are legally equivalent in consequence; the order exists solely to satisfy ENG-11 determinism.

## Explicitly NOT locked

```text
rule_configuration — shape and contents beyond the fields named in J-5.
    An explicit extension point. Contents must not be invented.
```

---
---

# Step 45C — LOCK RECORD

**Status: 🔒 LOCKED**
**Date: 2026-08-17**

Step 45C — Liability Edge Cases is locked as written (45C.1–45C.25, 45C.21 matrix, 45C.22–45C.25 hard rules), plus:

```text
45C.27  Detected-but-unresolvable precedence
        classification = CONFLICT, rule_outcome = NOT_APPLICABLE
        Every conflicting provision attached as CONFLICTING evidence
        The precedence clause itself attached as SUPPORTING evidence
        Diagnostics record that precedence language was detected and
        no configured rule applied
        The evaluator NEVER applies the document's precedence language.

45C.28  Heterogeneous scoped outcomes
        One Finding may carry Evaluations with different classifications and
        rule outcomes. Each is decided independently. No Evaluation is ever
        implicitly disposed of by a decision on another.

45C.29  Configuration may only widen decision requirements, never narrow them.
```

Locked rules 1–17 of 45C.26 stand, with two additions:

```text
18. A Legal Decision resolves exactly one scoped Evaluation and never
    implicitly disposes of another.
19. Detected precedence language that cannot be deterministically resolved
    produces CONFLICT, with the precedence clause retained as evidence.
```

---
---

# Step 45D — LOCK RECORD

**Status: 🔒 LOCKED**
**Date: 2026-08-17**

Step 45D — Cross-Evaluator Edge Cases specifies evaluator-agnostic behavior. **It specifies no legal Requirement.**

## Locked structural evaluator contract

Every Requirement evaluator must satisfy all twelve.

```text
45D.4.1   Multiplicity — one Evaluation per distinct governed scope; multiple
          provisions in one scope are one Evaluation with multiple evidence
          references, or CONFLICT where incompatible.
45D.4.2   Scope precedes value — no extracted value is treated as a legal
          position before what it applies to is established.
45D.4.3   General position and exceptions are separate; an exception's position
          applies only within its own scope and never generalizes.
45D.4.4   No silent commensurability — differing units, bases or scopes are
          never equated without a configured deterministic conversion rule and
          its required inputs.
45D.4.5   No silent precedence — no positional, ordinal, source-based or
          confidence-based heuristic may resolve competing provisions.
45D.4.6   Deterministic cross-reference only — preserved always, resolved only
          when deterministic; the referent's content is never inferred.
45D.4.7   Negative and exception patterns are first-class.
45D.4.8   Absence is not a position — absence yields MISSING and never
          manufactures a substantive legal position.
45D.4.9   Fail closed on unreliable input.
45D.4.10  Evidence survives every branch. Evidence references are preserved
          whenever evidence exists. MATCH, DEVIATION, CONFLICT and AMBIGUOUS
          must not carry empty evidence where supporting evidence exists.
          MISSING from established absence may legitimately carry zero.
          No synthetic evidence is ever created.
45D.4.11  The evaluator produces no Legal Decision.
45D.4.12  Reproducibility — every Evaluation retains its evaluator version and
          Legal Rule version relationally, its Company Standard version via the
          Review's configuration snapshot, its extracted facts, its extraction
          diagnostics, and its evidence.
```

## Locked boundary

```text
Requirement-specific   the evaluator's fact model and input contract (44.11)
Shared / structural    Finding, Evaluation, classification, rule outcome,
                       scope discriminator, evidence, decision
```

## Locked `PRESENCE` evaluator

```text
Presence is established by the MAPPING layer, never by the evaluator.
The evaluator reads no clause text and no patterns.

mapping_state  applicability   classification          evidence
-------------------------------------------------------------------
CONFIRMED      any             MATCH                   ≥1 required
NONE           REQUIRED        MISSING                 0 permitted
NONE           OPTIONAL        no Finding produced     —
AMBIGUOUS      any             UNABLE_TO_EVALUATE      ≥1 required
UNRESOLVED     any             UNABLE_TO_EVALUATE      ≥1 if candidates exist

An ambiguous or unresolved mapping must NEVER be recorded as absence.
DEVIATION is not producible by this evaluator.
```

A Requirement carrying both a presence condition and value criteria is modelled as **two Requirements over the same clause** (Step 28 r1); `requirement_versions.evaluator_type` is singular (42.7).

## Locked Requirement Specification Template

```text
R.1  identity          R.2  what it determines    R.3  evaluator type
R.4  fact model        R.5  sub-scopes            R.6  units/bases
R.7  exceptions        R.8  Company Standard      R.9  Legal Rule outcomes
R.10 rule_configuration R.11 patterns             R.12 cross-references
R.13 worked example per outcome                   R.14 conflict conditions
R.15 ambiguity/failure R.16 golden cases          R.17 lock statement
```

Structural conformance to 45D.4 is inherited, not restated.

---

## Current position

```text
Steps 1–44        🔒 LOCKED
Step 45A          🔒 LOCKED
REC-01 – REC-07   🔒 LOCKED
Amendment Batch AB-1  🔒 LOCKED
Step 45B          🔒 LOCKED (revised)
Step 45C          🔒 LOCKED
Step 45D          🔒 LOCKED
Step 45E          ⏳ IN PROGRESS — Golden Corpus
```

**V1 minimum evaluator coverage:** `LIABILITY-001` (`NUMERIC_COMPARISON`) + one generic `PRESENCE` evaluator + configured Requirements. No additional legal-domain evaluator is required by any locked decision.

Next: **Step 45E — Golden Corpus**, then the Implementation Readiness Review.

---
---

# Step 47 — LOCK RECORD — Security / Authentication / Authorization

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**No locked decision amended. Two new tables.**

## OD-9 — Authentication (owner decision)

```text
Primary authentication    Corporate SSO via OIDC
Fallback authentication   Password-based login, controlled fallback
Session model             Server-side sessions
Session contents          identity (user_id) ONLY
Authority resolution      fresh from the database on every request
Revocation                immediate, server-side
Rejected                  stateless JWT model
Hard rule                 the authentication mechanism NEVER confers
                          Legal Decision authority
```

Legal authority remains permission/role based under Steps 4, 23 and 31.

## Locked security model

```text
IDENTITY CONTRACT
    Only user_id is trusted from the session.
    Roles, permissions and Legal authority resolve fresh per request.
    The session establishes identity, never authority.
    Revoked/expired session is indistinguishable from signed out.
    No account enumeration on any identity response.

SUPER-ROLE BOUNDARY                             (from Step 23, ROLE-05)
    A super-role bypass may cover administrative permissions.
    It MUST exclude legal.decision and legal.approve_customization.
    Enforced in the permission resolver, not by convention.

ROLE MODEL                                       (from 42.3)
    Multi-role, union semantics.
    Legal Decision Authority is carried as an additional role assignment,
    which is how two users holding the same primary role can differ
    in legal authority (Step 4).

LEGAL DECISION AUTHORITY                         (from Steps 4, 23, 31)
    Requires an explicit grant. Never inherited, never implied,
    never reachable by bypass.
    legal.review does NOT confer legal.decision.
    Legal Configuration authority does NOT confer Legal Decision authority.
    Checked at Evaluation level (AB-1).
    Second-person approval evaluated at Evaluation level, different user.
    A configuration change must never leave zero users holding
    legal.decision.

OBJECT-LEVEL AUTHORIZATION                       (from 41.24, 43.23, Step 24)
    Legal Decision → Evaluation → Finding → Review → Contract
                   → owner/scope → User → Roles → Permissions
    Knowing an ID is never sufficient.
    The UI performs presentation-only gating.

DENIAL SEMANTICS                                 (from 41.24, LEGAL-02, 43.22)
    401  no valid session
    404  object outside the user's ownership/visibility scope
         (existence is not disclosed)
    403  object visible, operation permission absent
    409/422  business-rule rejection
```

## Permission catalogue

```text
contract.view | create | update | delete
document.upload | view | download
review.create | view
finding.view | comment
evaluation.view
legal.review | legal.decision | legal.approve_customization      (Step 23)
legal_position.view
configuration.view | draft | publish | deprecate
report.view | generate | export.generate
audit.view
user.manage | role.manage | platform.manage
```

Default grants follow Step 23's locked role summary. Catalogue additions are idempotent and are never auto-granted to non-super roles.

## Security invariants S-1 – S-10

```text
S-1   Authority resolved fresh per request; never trusted from the session
S-2   Sessions revocable server-side; revocation immediate
S-3   HttpOnly/Secure/SameSite cookies; CSRF protection on state changes
S-4   Credential material never returned; excluded at the repository layer
S-5   Rate limiting on authentication and expensive analysis endpoints
S-6   Secrets outside source control; keys rotatable
S-7   No account enumeration
S-8   A user may not grant an authority they do not themselves hold
S-9   The escalation guard covers granting, editing AND deleting a
      more-privileged account
S-10  Role–permission changes are transactional
```

## New tables

```text
sessions            id, user_id, created_at, last_seen_at, expires_at,
                    revoked_at, revoked_reason

user_identities     id, user_id, provider (OIDC|PASSWORD), provider_subject,
                    credential_hash, created_at, last_used_at
                    UNIQUE(provider, provider_subject)
                    UNIQUE(user_id, provider)
```

Authentication and authorization events are recorded in the existing locked `audit_events` (42.18); `actor_id` is null for pre-authentication events. No new audit table.

## NOT YET SPECIFIED

```text
Granular legal-approval limits      deferred by locked Step 4
Password policy / reset flow        implementation-phase, fallback path only
MFA                                 delegated to the identity provider
Multi-tenancy                       no locked requirement
```

## Current position

```text
Steps 1–44             🔒
Step 45A               🔒
REC-01 – REC-07        🔒
Amendment Batch AB-1   🔒
Steps 45B / 45C / 45D  🔒
Step 47                🔒
Step 45E               ⏳ Golden Corpus
Step 49                ⏳ API Finalization
```

---
---

# Step 49 — LOCK RECORD — API Finalization

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Schema impact: none. No locked decision amended.**

Step 49 completes the API surface left open by locked Steps 38 and 43. It changes nothing already locked: 43.21's envelope, 43.22's status semantics, 43.23's authorization ordering, 43.28's idempotency requirement, 43.30's `/api/v1/` base path and 43.31's frontend boundary are carried forward unchanged and extended.

## Locked conventions

```text
Base path     /api/v1/                                    (43.30)
Resources     plural nouns, kebab-case, UUID identifiers
Verbs         GET / POST / PATCH / DELETE. PUT is not used.
Timestamps    ISO-8601 UTC                                (41.27)
Envelope      { data } | { data, pagination } | { error } (43.21)
Every response carries X-Request-Id.
```

Endpoint **naming** remains outside the locked boundary (38.24). The **permission mapping** is normative.

## Locked: every endpoint declares exactly one required permission

No endpoint is implicitly public. `legal.approve_customization` is required in addition to `legal.decision` when `decision_type = APPROVE_CUSTOMIZATION`.

## Locked: error taxonomy and denial semantics

```text
401  no valid session
403  object visible, operation permission absent
404  object outside the caller's ownership/visibility scope
     — existence is NOT disclosed
409  conflict, including decision version collision
422  business-rule rejection
429  rate limit exceeded

A 404 for an out-of-scope object and a 404 for a non-existent object
are byte-identical. Any difference is an enumeration oracle.

Error bodies never disclose internal legal position.
```

## Locked: Finding / Evaluation / Decision surface

```text
1. Evaluations are NESTED under the Finding, never flat siblings.
2. findings.classification is a DERIVED SUMMARY and is never returned
   without its evaluations.
3. No Finding-level rule_outcome field exists in any response.
   requires_decision is derived.
4. evidence_refs is always an array and MAY BE EMPTY (MISSING from
   established absence). It is never null.
5. rule_outcome, thresholds and rule_configuration are OMITTED — not
   nulled — for callers without legal_position.view.
6. No response field can express a Legal Decision produced by the engine.
```

## Locked: decisions

```text
POST /evaluations/{id}/decisions      create, requires legal.decision
GET  /evaluations/{id}/decisions      full version chain

There is NO Finding-level decision endpoint.
There is NO decision update endpoint — supersession is a create.
justification is mandatory.
A UNIQUE(evaluation_id, version_number) violation surfaces as 409,
which provides optimistic concurrency without a separate ETag mechanism.
Prior versions are never modified.
Resolving a Finding directly is rejected — resolution is derived.
```

## Locked: pagination, idempotency, correlation

```text
page_size clamped server-side, maximum 100, regardless of client input.
Ordering explicit and stable, with a deterministic tiebreaker on id.
Filters are an allow-list per endpoint.
Collections apply the same object-level scope as single-resource reads.

Idempotency (43.28): analysis submission accepts Idempotency-Key;
Review creation idempotent on (document_version_id, configuration_snapshot_id);
Finding/Evaluation duplication prevented by unique constraints.
Decision creation is deliberately NOT idempotent by key — it is versioned,
so a duplicate submission is a 409 rather than a silent no-op.

X-Request-Id is echoed on every response, included in every error body,
recorded in the metadata of every audit event the request produces, and
propagated into background analysis jobs.
```

## NOT specified

```text
Exact endpoint paths      adjustable; naming outside the locked boundary (38.24)
Export formats            NOT YET SPECIFIED
Rate-limit thresholds     deployment configuration
OpenAPI generation        implementation task
```

---
---

# Steps 52–55 — LOCK RECORD

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Schema impact: none. No locked decision amended.**

## Step 52 — Frontend Architecture

```text
1. The frontend NEVER touches the database (38.22). All data via /api/v1/.
2. The frontend NEVER implements legal logic (38.23) — no classification,
   roll-up, rule evaluation or requires_decision computation.
3. UI permission gating is PRESENTATION ONLY (47.6, 49.11).

CONFIDENTIALITY RENDERING (LEGAL-02)
   A field omitted for lack of legal_position.view renders as ABSENT.
   No placeholder, no "hidden", no lock icon — a marker would disclose
   that an internal legal position exists.
   An out-of-scope 404 renders identically to a non-existent one.

REVIEW SCREEN (Step 31 r16 as amended by AM-6)
   A Finding shows its derived classification AND expands to its
   Evaluations. Never presented as a single verdict.
   Decision controls attach to the EVALUATION, not the Finding.
   A Finding cannot be resolved while any Evaluation requiring a
   decision lacks one.
   Decision history shows current vs superseded (Step 31 r20).
   RESOLVED ≠ MATCH remains visible.

No optimistic UI for Legal Decisions — a 409 is a real outcome.
NOT YET SPECIFIED: visual design, component library, accessibility
target, internationalisation.
```

## Step 53 — Observability / Error Handling

```text
THREE RECORD TYPES, NEVER CONFLATED
   Audit events      what legally happened     append-only (AUD-01)
   Diagnostics       why the engine concluded  immutable (REC-07)
   Operational logs  what the system did       retention-bound

   An operational log is NEVER a substitute for an audit event.
   Log expiry must never remove auditable history.

CORRELATION
   X-Request-Id joins logs, audit_events.metadata and background jobs.

NEVER LOGGED
   Credentials, credential_hash, session ids, OIDC tokens/codes;
   contract text or clause content; thresholds, rule outcomes,
   rule_configuration; anything making failed logins an enumeration oracle.

ERROR HANDLING
   User-facing: stable code, safe message, request_id.
   Operator-facing: trace and context, logs only. Never leaked to a response.

   ANALYSIS_FAILED (Step 30) is an operational failure.
   UNABLE_TO_EVALUATE is CORRECT fail-closed behavior and must NOT
   be alerted as an error.

SIGNALS
   Pipeline stage durations; evaluator runs by type/version;
   classification distribution; fail-closed rate (a FALLING rate may
   indicate guessing, not improvement); ANALYSIS_FAILED rate;
   auth failures and permission denials; decision throughput/age.

NOT YET SPECIFIED: retention policy (41.26 defers it), log aggregation
technology, alert thresholds.
```

## Step 54 — Testing Strategy

```text
THE GOLDEN CORPUS IS TIER 1 AND NORMATIVE (ENG-12).
   Every fixture asserts BOTH the exact scoped Evaluation set AND the
   derived Finding summary — never the roll-up alone.
   Every fixture pins configuration versions and evaluator_version.
   A changed expected output is a SPECIFICATION CHANGE, reviewed as such,
   never edited to make a build pass.
   The corpus runs in full on any mapping/extraction/evaluation change.

DETERMINISM (ENG-11)
   Identical inputs + configuration snapshot + evaluator version →
   BYTE-IDENTICAL output. No clock, random source, locale or environment
   variable may affect a result.

REPRODUCIBILITY
   An historical Evaluation replays from persisted facts, evidence,
   evaluator_version and legal_rule_version_id.

AUTHORIZATION TESTS ARE RELEASE-BLOCKING
   IDOR matrix → 404 for out-of-scope objects.
   Out-of-scope 404 and non-existent 404 byte-identical.
   Permission matrix: every endpoint × every role.
   A super-role holder without legal.decision cannot decide by any route.
   legal.review alone does not permit deciding.
   Escalation guard covers grant, edit AND delete.
   A change leaving zero legal.decision holders is rejected.
   Without legal_position.view, confidential fields are ABSENT not null.
   A revoked session fails on the next request.

INVARIANTS
   EV-MIN; evidence cardinality (no synthetic evidence);
   decision version collision; append-only enforcement; uniqueness;
   idempotency.

TEST DATA
   Synthetic or cleared text only. Real counterparty contracts never
   enter the repository. The corpus contract set is the SAME set used to
   calibrate Step 35's provisional thresholds.

NOT YET SPECIFIED: coverage targets, framework selection, CI topology.
```

## Step 55 — Deployment / Infrastructure

```text
SHAPE (Step 39; no new technology, no microservices per 38.26)
   Next.js → FastAPI → PostgreSQL + object storage + worker/queue
   → external OIDC provider.
   Workers run the SAME image as the API — a version skew would break
   evaluator_version reproducibility, so they deploy together.

SECURITY CONFIGURATION (Step 39 checklist)
   TLS; secrets outside source control and rotatable; encrypted storage;
   upload validation; sandboxed resource-limited parsing; malware
   scanning where available; rate limiting at edge AND application;
   automated backups with VERIFIED restore; application DB role holds
   no DDL rights.

ENVIRONMENTS
   Real contracts never leave production. Debugging uses correlation
   identifiers and diagnostics, never data copies.

MIGRATION DISCIPLINE
   Historical legal records are never rewritten.
   Migrations touching legal data are forward-only and additive;
   destructive migrations require explicit approval.
   Reproducibility must survive migration — verified as a release gate.
   Configuration versions are never mutated in place.

PRODUCTION BLOCKERS REGISTER
   OIDC configured; secrets management; backup + verified restore;
   rate limiting; TLS and secure cookie flags; malware scanning
   available or explicitly accepted as absent; retention policy
   (NOT YET SPECIFIED); export formats (NOT YET SPECIFIED).

NOT YET SPECIFIED: hosting platform, orchestration, CI/CD tooling,
object-storage provider, monitoring stack, DR objectives.
```

## Current position

```text
Steps 1–44             🔒        Amendment Batch AB-1   🔒
Step 45A               🔒        Steps 45B / 45C / 45D  🔒
REC-01 – REC-07        🔒        Step 47                🔒
Step 49                🔒        Steps 52 / 53 / 54 / 55 🔒
Step 45E               ⏳        Golden Corpus — 64 fixtures specified
```

**The V1 specification is complete.** Remaining work is corpus authoring and implementation.

---
---

# Implementation Authorization — LOCK RECORD

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Recorded retroactively. No specification decision is changed by this entry.**

## What is authorized

Implementation of the locked V1 specification is authorized, following the
sequence recorded in the Implementation Readiness Gate §5.

This entry authorizes **building what is already locked**. It confers no
authority to decide anything that is not. Every constraint in the Gate §6
standing-constraints list continues to apply, and rules 1–22 of `CLAUDE.md`
are unchanged.

## Honesty of the record

**This authorization is recorded after the work began.** Steps 1–6 of the build
sequence — schema and migrations, authentication and authorization, document
storage and ingestion, mapping, evaluation, and the decision/review workflow —
were implemented on 2026-08-17 before any approval was recorded, and the API
layer was in progress at the time of recording. The discrepancy was detected and
reported as conflict **C-09** rather than discovered later.

Nothing is backdated. The work is authorized as of this entry's date; it was not
authorized when it was written. The record says so deliberately, because a
specification-first project that quietly regularises its own exceptions has
stopped being specification-first.

## Scope of the authorization

```text
AUTHORIZED
    Implementation of locked Steps 1–45D, 47, 49, 52–55
    against the recorded specification, in the Gate §5 sequence.

NOT AUTHORIZED BY THIS ENTRY
    Deciding anything marked NOT YET SPECIFIED.
    Resolving any open conflict (C-05 – C-10) or open decision (OD-*).
    Amending any locked decision.
    Adding any table, column or enum not covered by a lock record
        or an approved amendment batch.
    Authoring NORMATIVE golden-corpus fixtures — these require real
        representative contracts and the organization's real Company
        Standards, which must be supplied, never manufactured.
    Any new technology, dependency or service beyond the Step 39 stack.
```

## Conditions

```text
1.  The code is not a specification. A behavior appearing in the
    implementation does not make it decided. Where the code makes a choice
    the specification does not fix, that choice is an implementation
    detail and is recorded as such — it is not thereby locked.

2.  Conformance is verified against the locked corpus, not asserted by the
    implementation. The release-blocking authorization tests of Step 54
    and the golden corpus of ENG-12 are the mechanism.

3.  Two additive tables created before this authorization —
    `review_assignments` and `escalations` — are ratified separately by
    Amendment Batch AB-2, not by this entry.

4.  A changed golden-corpus expectation remains a specification change.

5.  The master record remains append-only.
```

## Position

```text
Specification    complete — Steps 1–45D, 47, 49, 52–55 locked
Step 45E         ⏳ Golden Corpus — 64 fixtures specified, authoring outstanding
Implementation   authorized as of this entry
```

---
---

# Amendment Batch AB-2 — Review Assignment, Escalation & Ownership

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Two new tables. One locked table clarified. No legal policy changed.**

AB-2 follows the AB-1 pattern: each item repairs a case where a **locked
requirement could not be represented by the locked schema**. No amendment
changes legal meaning.

## AM-22 — `review_assignments` (new table)

**Driver.** Locked Step 24 requires assignment and cannot be implemented without
it:

```text
r6   "Legal Reviewer access is controlled by assignment and/or explicit
      Legal scope."
r16  "A Review may be visible to an authorized Legal Reviewer without
      transferring ownership from the original User."
r17  "Legal assignment gives access for Legal work; it does not make the
      Legal Reviewer the business owner of the Review."
```

No locked table represents assignment. Without one, r16 is unimplementable:
granting a Legal Reviewer access would require transferring ownership, which
r16 forbids.

```text
review_assignments
------------------
id            UUID PK
review_id     UUID FK → reviews.id            NOT NULL   ON DELETE CASCADE
user_id       UUID FK → users.id              NOT NULL   ON DELETE CASCADE
assigned_by   UUID FK → users.id              NOT NULL
created_at    TIMESTAMPTZ                     NOT NULL
revoked_at    TIMESTAMPTZ                     NULL
UNIQUE(review_id, user_id)
INDEX(review_id), INDEX(user_id)
```

Revocation is a timestamp, not a delete — consistent with 41.26.
**Additive. No locked table amended.**

## AM-23 — `escalations` (new table)

**Driver.** Locked Steps 4 and 22 make escalation first-class, and Step 24 r5
gives it an access consequence:

```text
ROLE-04   "Escalation is not approval — it means 'this requires
           authorized review'."
r5        "Escalation makes the Review available to the authorized
           Legal workflow."
```

No locked table represents it.

```text
escalations
-----------
id            UUID PK
finding_id    UUID FK → findings.id           NOT NULL   ON DELETE CASCADE
raised_by     UUID FK → users.id              NOT NULL
reason        TEXT                            NOT NULL
created_at    TIMESTAMPTZ                     NOT NULL
withdrawn_at  TIMESTAMPTZ                     NULL
INDEX(finding_id), INDEX(raised_by)
```

Escalation is recorded at **Finding** level per engineering resolution **F-3**,
and marks every Evaluation under that Finding as requiring a decision. It is a
request for review, never a disposition — it produces no Legal Decision and no
classification.

**Additive. No locked table amended.**

## AM-24 — Review ownership: `created_by` is the owner

**The open question.** Locked Step 24 r1–r2 state that every Review has an owner
and that the creator is the initial owner "unless the Review is explicitly
transferred or assigned." Locked 42.13 `reviews` carries `created_by` and **no
`owner_id`**, so transfer has no representation.

**Owner decision, 2026-08-17:**

```text
reviews.created_by IS the Review owner for V1.

Ownership transfer is DEFERRED TO V2. No locked rule requires the
capability; Step 24 r2 permits it without mandating it.

No schema change. 42.13 is NOT amended — this entry records the
interpretation that resolves r1/r2 against the locked column set.
```

**Consequence.** Every ownership check in Step 24 — r3, r4, r16, r18 — resolves
through `reviews.created_by`. Legal access continues to resolve independently
through `review_assignments` (AM-22) and Legal scope, which is precisely what
r16 and r17 require: access without ownership.

**Deferred to V2:** `reviews.owner_id`, transfer semantics, transfer audit
events, and what happens to an in-flight Review when its owner is deactivated.

## Not amended by AB-2

```text
Step 24's eighteen rules            unchanged
42.13 reviews                       unchanged
Step 31 decision model              unchanged
AB-1 in its entirety                unchanged
The five-axis state model           unchanged
```

## Position

```text
Amendment Batch AB-1   🔒        Amendment Batch AB-2   🔒
Tables added by AB-2   review_assignments · escalations
Schema impact          additive only; no locked table amended
Legal policy impact    none
```

---
---

# Reconciliation Decision REC-08 — CI/CD tooling

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Resolves conflict C-11. No legal policy changed. No schema impact. No new
technology introduced.**

## The contradiction

Two locked records answered the same question in opposite ways.

**Step 39 — technology stack table** (this file, line 6049):

```text
| CI/CD | **GitHub Actions** | Straightforward automated testing/deployment |
```

**Step 55.6 — production blockers** (this file, line 14871):

```text
NOT YET SPECIFIED: hosting platform, orchestration, CI/CD tooling,
object-storage provider, monitoring stack, DR objectives.
```

The consequence was governance-visible rather than technical. `IMPL-01` forbids
"any technology, dependency or service **beyond the Step 39 stack**". Under the
Step 39 reading, a GitHub Actions workflow is inside the authorized stack and
needs no ratification. Under the 55.6 reading it is an implementation choice made
where the specification is silent, which `IMPL-01` condition 4 leaves unratified.
The same file therefore belonged in two different governance categories at once.

The usual tie-breaker did not apply: both sources are Step-numbered lock records,
not a Step document versus an older topic document.

## Owner decision, 2026-08-17

```text
GitHub Actions IS the approved CI/CD tooling for LegalMind V1.

The Step 39 stack table row is the intended CI/CD tooling decision and
GOVERNS. GitHub is already the repository host and GitHub Actions is
already the CI system; this entry makes that the official V1 choice.

Step 55.6's inclusion of "CI/CD tooling" in its NOT YET SPECIFIED list
is SUPERSEDED FOR THAT ONE LINE ITEM ONLY. The 55.6 text stays exactly
where it is and is annotated as superseded elsewhere.

No schema change. No new technology. The existing
.github/workflows/ci.yml implementation is retained as-is.
```

## What this settles

```text
CI/CD tooling            GitHub Actions — 🔒 LOCKED for V1
ci.yml                   an authorized use of the locked Step 39 stack;
                         NOT an unratified implementation choice, and
                         therefore NOT a Pending-ratification item
C-11                     RESOLVED
```

## What this does NOT settle

Every other item in 55.6's list remains exactly as locked. This entry is
deliberately narrow, and confers no authority over any of them:

```text
Hosting platform             NOT YET SPECIFIED
Container orchestration      NOT YET SPECIFIED
Object-storage provider      NOT YET SPECIFIED
Monitoring stack             NOT YET SPECIFIED
Disaster-recovery objectives NOT YET SPECIFIED
```

Nor does it authorize any technology beyond GitHub Actions, alter the release
sequence locked in 55.5, change the production blockers register, or ratify
anything else registered under Pending ratification.

## Not changed by REC-08

```text
Step 39 stack table          unchanged (this entry affirms its CI/CD row)
Step 55.5 release sequence   unchanged
Step 55.6 other line items   unchanged
IMPL-01 and its conditions   unchanged
AB-1, AB-2                   unchanged
The five-axis state model    unchanged
Every locked legal rule      unchanged
```

## Position

```text
REC-01 – REC-07   🔒        REC-08   🔒
Resolves          C-11
Conflicts open    C-05 · C-06 · C-07 · C-08 · C-10
Legal policy      none affected
Schema impact     none
```

---
---

# Reconciliation Decision REC-09 — "Explicit Legal scope" for Review visibility

**Status: 🔒 LOCKED**
**Date: 2026-08-17**
**Defines a term two locked rules use and none defined. Resolves finding `F-6`.
No new permission. No new endpoint. No new table. No schema change. No legal
policy changed.**

## The gap

Locked Step 24 r6 makes Legal Reviewer access depend on a term the specification
never defines:

```text
r6   "Legal Reviewer access is controlled by assignment and/or
      explicit Legal scope."
```

Locked Step 23 r12 names the same term as one of four scope kinds — "own,
assigned, **Legal scope**, or system scope" — and also gives no criterion. No
other locked record supplies one.

Both branches of r6 were therefore unimplementable:

```text
assignment            `review_assignments` exists and is ratified (AM-22),
                      but NO operation creates a row: Step 49 specifies no
                      endpoint and the SEC-04 catalogue of 27 permissions
                      contains nothing that would authorize one.
explicit Legal scope  never defined anywhere in this file.
```

The consequence was not cosmetic. Object visibility resolved on ownership alone,
`LEGAL_REVIEWER` does not hold `review.create`, and so a Legal Reviewer could
reach **no Review at all** — every Legal-facing surface returned 404 to the roles
that exist to use them. Locked Step 24 r5, r6, r7, r16, r17 and r18 and locked
Step 22's escalation path were all unreachable in consequence.

Recorded as `F-6`. Note also that `legal.review` was granted by Step 23's default
grants and enforced at no call site — a locked permission that granted nothing.

## Why an assignment operation could not have fixed it alone

Whoever assigns a Review must first be able to **see** it. Locked Step 24 r8
denies Super Admin access to Legal content, so a platform administrator cannot be
the assigner; locked r7 gives Legal Admin "authorized **Legal-scope** access" —
which is the very term left undefined. The Legal-scope definition was therefore
required either way, and once made, the locked workflow functions without any new
endpoint or permission.

## Owner decision, 2026-08-17

```text
A Review is IN LEGAL SCOPE when either:

  (a) any of its Findings has an escalation that has not been
      withdrawn                                    (Step 24 r5, AM-23)

  (b) its Review lifecycle status is LEGAL_REVIEW   (Step 30)

A holder of `legal.review` MAY VIEW a Review that is in Legal scope.

This grants NEITHER ownership NOR Legal Decision authority.

Per-user assignment is NOT an access path in V1. `review_assignments`
(AM-22) remains ratified and remains read for access as locked, but
nothing populates it; scoping Legal access to individually assigned
Reviews is DEFERRED TO V2.
```

Both conditions are required, and each traces to a locked rule:

```text
(b) alone is insufficient — a user may escalate a Finding on a RESOLVED
    Review, and Step 30's state machine has NO RESOLVED -> LEGAL_REVIEW
    transition. Without (a) that escalation would be invisible to Legal,
    and ROLE-04 fixes escalation's meaning as "this requires authorized
    review".

(a) alone is insufficient — the engine derives LEGAL_REVIEW with no human
    escalation (Step 30 r6), and Step 30 defines that status as "one or
    more Findings require an authorized Legal decision". Without (b) a
    Review the ENGINE says needs a Legal Decision would wait for a human
    to escalate it first.
```

## What this settles

```text
Step 24 r6 "explicit Legal scope"   DEFINED for V1, as above
Step 24 r5                          IMPLEMENTABLE — escalation is
                                    condition (a)
Legal Reviewer / Legal Admin        can reach the Reviews their locked
                                    roles exist to review
`legal.review`                      now has an enforcement site: it is
                                    the permission half of Legal scope
F-6                                 RESOLVED
```

## What this does NOT settle

```text
Per-user assignment (G1)     DEFERRED TO V2. No endpoint, no permission,
                             no rule naming who may assign. Precedent:
                             AM-24 deferred ownership TRANSFER on the same
                             reasoning — r6's "and/or" permits the
                             assignment branch without mandating it.
"Legal Queue" as an object   NOT SPECIFIED. The phrase occurs once in this
                             file, inside Step 24's example diagram. Legal
                             work is found through the existing Review
                             list under the same scope rule; no queue
                             resource is created.
Contract and Document access Unchanged and OWNER-ONLY. This entry governs
                             Reviews, Findings and Evaluations reached
                             through a Review. Whether Legal scope extends
                             to the underlying Contract or to downloading
                             the original document is NOT decided here.
Least privilege (r13)        A `legal.review` holder sees every in-scope
                             Review, which is coarser than Step 23's
                             illustrative `review.scope = assigned`. This
                             is accepted for V1 and narrowing it is the
                             V2 assignment work.
```

## Not changed by REC-09

```text
Ownership (Step 24 r1-r4, AM-24)   unchanged — created_by is the owner
Legal access confers no ownership  unchanged (r16, r17) — REQUIRED by this
                                   entry, not weakened
SEC-02 / ROLE-05                   unchanged — no super-role bypass reaches
                                   legal.decision, and Legal scope confers
                                   no decision authority
SEC-05                             unchanged — legal.review does NOT confer
                                   legal.decision
LEGAL-02 / SEC-07                  unchanged — internal legal position stays
                                   gated on legal_position.view, and is
                                   OMITTED not nulled
41.24 / SEC-06                     unchanged — knowing an ID is never
                                   sufficient; out-of-scope stays a 404
The SEC-04 permission catalogue    unchanged — 27 permissions, none added
Step 49's endpoint table           unchanged — no endpoint added
Every locked table                 unchanged — no schema impact
Step 45E golden corpus             untouched — 58 NORMATIVE fixtures remain
                                   unauthored and blocked on real material
Every locked legal rule            unchanged
```

## Position

```text
REC-01 - REC-08   🔒        REC-09   🔒
Resolves          F-6
Defers to V2      per-user Legal assignment (G1); Legal scope for
                  Contract and Document access
Conflicts open    C-05 · C-06 · C-07 · C-08 · C-10 · C-12
Legal policy      none affected
Schema impact     none
```


---
---

# Document Type Determination & Multi-Document Review — `DOC-06`, `DOC-07`

**Status: 🔒 LOCKED**
**Date: 2026-08-21**
**Two owner decisions on how a document's kind is established and how several
documents are reviewed together. No new table. No new column. No schema change.
No new permission. No new endpoint. No Legal Rule created. No Company Standard
altered. No prior locked decision amended.**

## Why these were decided

A multi-document upload capability was proposed: a user supplies a set of
counterparty documents — an MSA, a Terms of Service, a Service Level Agreement —
and expects to see them reviewed together. Two questions had to be answered
before any of it could be built, and neither was settled in this file.

```text
How is a document's TYPE established?      Step 6 fixes the ten types and is
                                           silent on who determines which one
                                           applies to a given file.

What does it mean to review several        Step 26 r2 ties a Review to exactly
documents "together"?                      one Document Version, and nothing
                                           describes a set.
```

Both were answered by the owner on 2026-08-21. Recorded here because each has
lasting force over what may be built, and because leaving either unwritten would
invite it to be re-derived differently later.

---

## `DOC-06` — Document Type is DECLARED, never inferred

### Owner decision, 2026-08-21

```text
The user SELECTS the Document Type from locked Step 6's ten values.

Automatic detection of Document Type is OUT OF V1 SCOPE. Not deferred
pending better tooling — excluded, on the reasoning below.

It may be reconsidered as an OPTIONAL convenience in a later version if
users ask for it, and only as a SUGGESTION a human confirms. It may never
become the authoritative determination.
```

Owner's stated reasoning, recorded in the owner's own terms:

```text
"Safety over speed. This is a legal tool, not a casual app.
 Accuracy matters more than convenience."
```

### Why this is a legal-safety decision and not a UI preference

The Document Type selects which Requirements are evaluated and therefore which
Company Standards a document is measured against. It is the first input to the
analysis, and every Finding downstream inherits it.

```text
A document typed MSA   is measured against the MSA standards
A document typed TOS   is measured against the TOS standards
A document typed NDA   produces no liability Finding at all
```

So a wrong type does not degrade the answer — it produces a **confident answer to
the wrong question**, against a baseline the document was never meant to meet.
That is the class of quiet error `ENG-09` exists to prevent, and it is
indistinguishable at the output from a correct answer.

### What this settles

```text
Who determines the type            The uploader, by declaration
Vocabulary                         Locked Step 6's ten values; no other
                                   value is accepted
An undeclared type                 Analysis REFUSES. It does not default,
                                   and it does not guess (fail closed)
Automatic detection in V1          EXCLUDED — rule-based, statistical and
                                   model-based alike
```

### What this does NOT settle

```text
The selection UI              Presentation. Not decided here and not
                              constrained by this entry beyond the
                              vocabulary and the refusal.
A later suggestion feature    A deterministic pre-fill a human confirms
                              remains open for a future version. It would
                              need its own decision, and the confirmed
                              value would still be the declared one.
Document SOURCE               Organization vs Counterparty (Step 6) is a
                              separate axis and is untouched.
```

### Relationship to `AI-01`

`AI-01` bars LLM, RAG, embeddings and vector databases from the authoritative
analysis path. Because the Document Type determines which Requirements run, any
detector of it sits inside that path. `DOC-06` therefore does not create a new
constraint so much as make an existing one explicit at the point where it would
otherwise have been argued about. Classical NLP remains permitted in an
assist-only role, and an assist that a human confirms is not an authoritative
determination.

---

## `DOC-07` — Multi-document review is TYPE-MATCHED PAIRING over a grouped set

### Owner decision, 2026-08-21

```text
A user may upload a SET of documents. Each document in the set is
analysed against the Requirements applicable to ITS OWN declared type,
and the results are presented together, per document.

  counterparty MSA  ->  compared with the LeapSwitch MSA standards
  counterparty TOS  ->  compared with the LeapSwitch TOS standards
  counterparty SLA  ->  compared with the LeapSwitch SLA standards

Each document reports, against its own type's Requirements, what MATCHES,
what DEVIATES and what is MISSING.

A document is NEVER measured against another type's Requirements.
```

### The set is a GROUPING, not a legal object

```text
Locked Step 26 r2 stands UNCHANGED and UNWEAKENED:
    "A Review is tied to exactly one Document Version."

A set of N documents is therefore N Contracts, N Document Versions and
N Reviews, each pinning its own configuration snapshot.

"Reviewed together" describes PRESENTATION and submission convenience.
It creates no record that carries a Finding, evidence or a Legal
Decision, and it has no lifecycle of its own.
```

This is the whole reason the decision costs no schema change: the set is not a
thing the legal model has to know about. Every guarantee that matters —
reproducibility, evidence traceability, one snapshot per Review, one Legal
Decision per Evaluation — is per Review and stays per Review.

### Cross-TYPE comparison is OUT OF V1 SCOPE

```text
LegalMind does NOT compare one document type against another, in either
direction:

  a counterparty MSA against a counterparty TOS      NOT PERFORMED
  a counterparty document against a LeapSwitch
    standard of a DIFFERENT type                     NOT PERFORMED
```

Excluded because it would manufacture contradictions where the specification has
already established there are none. Two worked examples, both already settled:

```text
Liability      MSA: 6 months of fees for the affected Services
               TOS: 12 months of total fees
               -> DIFFERENT questions. Different relationship (a signed
                  master agreement vs click-through terms) and different
                  basis (45B.4 forbids equating the two). Not a conflict.

Confidentiality  MSA: 3 years from termination of the Agreement
survival         NDA: 2 years from the LATER of NDA termination and the
                      end of the underlying relationship
                 -> DIFFERENT questions. The anchors differ, so the NDA's
                    two years can run LONGER in absolute time than the
                    MSA's three. "2 < 3" is not a true statement about
                    protection strength.
```

A cross-type comparator would report both pairs as conflicts on the day it was
switched on. It would also have no place to record the result: locked 44.18
places conflict detection after fact extraction **within** a scope, and a Finding
is unique per Review and Requirement version, so a finding spanning two documents
belongs to no Review.

### Conflict detection is unchanged, and already covers the real case

```text
The conflict that matters is TWO PROVISIONS IN ONE DOCUMENT governing one
scope and contradicting each other — the worked example being MSA 17.2's
six-month cap against 17.7's cap with a blank period.

That is CONFLICT, it is Tier 1, all conflicting provisions are retained
as evidence, and a human decides. Grouping documents neither adds to this
nor subtracts from it.
```

### What this settles

```text
Multi-document upload           PERMITTED — N documents, N Reviews
Requirement scoping             UNCHANGED and authoritative: each Review
                                evaluates only its declared type's
                                Requirements
Per-document reporting          MATCH / DEVIATION / MISSING per document,
                                against its own type
The set as a record             NOT a legal object. No table, no column,
                                no lifecycle, no Finding
Cross-type comparison           OUT OF V1 SCOPE
Within-document conflict        UNCHANGED
```

### What this does NOT settle

```text
How the grouping PERSISTS       Whether the set is held in client state
                                only, or correlated through an existing
                                JSONB metadata field, is an implementation
                                choice and is NOT decided here. Either way
                                it adds no table and no column.
Combined export                 Locked 49.12 keeps export formats NOT YET
                                SPECIFIED. Unchanged by this entry.
A cross-document OBSERVATION    A document-level note reporting differing
                                positions across a set WITHOUT classifying
                                them as a conflict — the shape REC-02 uses
                                for UNMATCHED_PROVISION — is neither
                                authorized nor forbidden here. It would
                                need its own decision.
Aggregate scoring across a set  Forbidden already, and not revisited: 36.10
                                bars a risk score as the primary V1 output
                                and F-9 makes the alignment figure carry no
                                legal meaning.
Partial-set behaviour           One document failing analysis does not
                                affect the others — each Review is
                                independent, and ANALYSIS_FAILED is
                                per-Review and terminal. How a partially
                                complete set is PRESENTED is not decided
                                here.
```

---

## Not changed by `DOC-06` or `DOC-07`

```text
Step 6                          unchanged — the ten Document Types stand
Step 26 r2                      unchanged — a Review is tied to exactly one
                                Document Version. REQUIRED by DOC-07, not
                                weakened by it
Step 26 r15                     unchanged — different Document Types have
                                separate Document identities. This is why a
                                set is N Contracts rather than one
Step 28                         unchanged — Requirement scoping by Document
                                Type is reaffirmed as authoritative
AI-01                           unchanged — made explicit at the type
                                boundary by DOC-06, not relaxed
45B.4                           unchanged — bases are never assumed
                                comparable. DOC-07's exclusion of cross-type
                                comparison follows from it
44.18                           unchanged — conflict detection stays within
                                a scope, after fact extraction
REC-02                          unchanged — a document-level observation
                                never occupies a Finding's classification
36.10 / F-9                     unchanged — no risk score, no overall
                                verdict, and none introduced across a set
49.12                           unchanged — export formats NOT YET SPECIFIED
Every locked table              unchanged — no schema impact whatsoever
The SEC-04 permission catalogue unchanged — 27 permissions, none added
Step 49's endpoint table         unchanged — no endpoint added
Every Company Standard          unchanged — no position, threshold or
                                tolerance touched
Every Legal Rule                unchanged — none created, none altered
Step 45E golden corpus          untouched by these entries
```

## Position

```text
DOC-01 - DOC-05   🔒        DOC-06   🔒        DOC-07   🔒
Owner decisions   2026-08-21
Schema impact     none
Legal policy      none affected
Requirement scoping  reaffirmed as authoritative
Out of V1 scope   automatic Document Type detection (DOC-06);
                  cross-TYPE document comparison (DOC-07)
Open, unaffected  C-05 · C-06 · C-07 · C-08 · C-10 · C-12 · C-13
```

---

# Amendment Batch AB-3 — Assistive AI Lane Enters V1 Scope

**Status: LOCKED**

**Owner decision recorded: 2026-08-24.** Effective from this record forward. Nothing in this batch is
retroactive, and no historical Review, Finding, Evaluation, Legal Decision or configuration snapshot is
altered, reinterpreted or invalidated by it.

**Records: `AM-25` – `AM-29`.**

---

## Why this batch exists

The product direction changed: LegalMind V1 now includes a secure, self-hosted AI Legal Workspace —
document Q&A, evidence-grounded answers with page-level citations, and Smart Briefing over long
judgments — running alongside the existing deterministic validation engine.

This batch does **not** repeal the V1 AI boundary. It narrows one clause of it — the clause that placed
the assistive lane *after* V1 rather than *inside* it — and makes every other principle in the
`V1 AI Boundary` record binding on the new lane.

The distinction matters, so it is stated plainly:

```text
NOT amended    the architectural shape of the assist lane
               (AI-01 already prescribes it, verbatim, and AB-3 adopts that text as governing)

AMENDED        the timing clause only
               "if AI is introduced AFTER V1"  ->  "the assist lane is IN V1, on these terms"
```

## The enabling records this batch relies on

These are cited as authority, not superseded. Every one of them anticipated this direction.

```text
AI-01  "Architectural principle for future AI"
       "If AI is introduced after V1, it should sit ON TOP OF the V1 foundation, not replace it."
       "Future AI may assist with language understanding, semantic matching, retrieval, or other
        clearly defined tasks, but it must not silently become the source of truth for company
        legal policy or final legal decisions."
       -> ADOPTED BY AB-3 AS BINDING ON THE ASSIST LANE, without alteration.

AI-01  "Hard V1 constraint"
       "...unless this locked decision is explicitly revisited and changed."
       -> This batch is that explicit revisiting. The path was provided inside the lock itself.

AI-02  Architecture must remain capable of adding LLM/RAG without redesign, as an assistive layer,
       never the authoritative path.
       -> UNCHANGED. This is the authorizing basis for AB-3.

38.25  "Architecture should support future LLM/RAG"
           Analysis Interface
                  |
                  +-- V1 Deterministic Engine
                  |
                  +-- Future AI-assisted Engine
       -> UNCHANGED, and now realized rather than hypothetical.

Step 38 locked rule 20
       "The architecture exposes a clean analysis boundary so future LLM/RAG capabilities can be
        evaluated later without becoming the V1 legal source of truth."
       -> UNCHANGED, and now exercised.

Step 38 locked rule 21
       "The deterministic V1 Analysis Engine remains the authoritative source for V1 Findings."
       -> UNCHANGED. AB-3 strengthens this rule rather than weakening it (see AM-25).

Step 39 (vector database section)
       "If later we introduce semantic retrieval, we can reassess whether PostgreSQL + pgvector is
        sufficient before adding another database."
       -> UNCHANGED, and answered: pgvector is sufficient (AM-26).

Locked 55.6
       Object-storage PROVIDER is NOT YET SPECIFIED.
       -> UNCHANGED and requires no amendment. Selecting an S3-compatible provider closes an open
          item; it does not alter a lock.
```

---

# `AM-25` — The assistive AI lane is in V1 scope, on fixed terms

**Amends:** the `V1 AI Boundary` record's `## V1 will NOT use` list and its `## Hard V1 constraint`
paragraph; the Step 38 `V1 explicitly excludes` entries for `LLM`, `RAG`, `Vector Database` and
`Semantic AI`; `AI-03`'s exclusion of embeddings and semantic vector search; and the `LLM/RAG/vector DB`
portion of the Step 39 stack line `No microservices/Kubernetes/LLM/RAG/vector DB in V1.`

**Does not amend:** anything else in any of those records. In particular the Step 39 exclusion of
microservices and Kubernetes stands unchanged, and `AI-01`'s `## V1 WILL use` list stands unchanged.

## What is now permitted in V1

```text
An assistive AI lane comprising:
  - local, self-hosted embedding generation
  - a vector index and a keyword index over document chunks
  - hybrid retrieval with reranking
  - a local, self-hosted generative model
  - retrieval-grounded answers carrying citations to Document Evidence
  - long-document briefing by hierarchical summarization
```

## What remains forbidden — the terms, in full

These are not aspirations. Each is a locked constraint, and the batch is void of effect for any
component that does not satisfy all nine.

```text
r1   The assist lane NEVER produces a Finding, an Evaluation, a Finding Classification,
     a Rule Outcome, a Mapping State, a Legal Decision, or a Review Lifecycle transition.
     The deterministic engine remains the sole producer of all seven. Step 38 rule 21 is
     reaffirmed, not weakened.

r2   The assist lane NEVER writes to findings, evaluations, legal_decisions,
     requirement_versions, company_standard_versions, legal_rule_versions,
     mapping_rule_versions, evaluation_rule_versions, configuration_snapshots or
     configuration_snapshot_items. This is enforced by a distinct database role holding no
     INSERT or UPDATE grant on those tables, not by convention.

r3   The assist lane NEVER states an organizational legal position that is not already
     present in a ratified Company Standard, a published Legal Rule, or an approved template.
     Where a position is absent, the correct output is a gap reported to a human. Rule 7 and
     rule 21 apply to the assist lane exactly as they apply to everything else: an invented
     legal requirement arriving as a generated answer is still an invented legal requirement.

r4   The assist lane NEVER answers the question "does this document meet our standard?"
     That question belongs to the deterministic evaluator. An assist-lane request of that
     shape is routed to the evaluator or refused; it is never answered generatively.

r5   No answer reaches a user unless every claim in it resolves to retrieved evidence.
     Enforcement is mechanical and sits outside the model. Where evidence is insufficient,
     the response is an explicit statement that the information was not found. A guess,
     a hedge, a partial answer presented as complete, or a cached substitute is a defect.

r6   Authorization is applied BEFORE retrieval, inside the retrieval query, resolved
     server-side from the session. A retrieval result set is never filtered after the fact.
     A user must never retrieve a chunk of a document they are not authorized to read, and a
     result excluded by authorization must be indistinguishable from a genuinely empty
     result — SEC-07 and API-10's byte-identical-404 discipline extend to retrieval.

r7   The assist lane never becomes an existence oracle. It does not confirm, by any
     difference in response, timing-independent content, or error shape, that a document
     outside the requester's scope exists.

r8   Authentication and the assist lane confer no Legal Decision authority. SEC-01, SEC-02
     and ROLE-05 are unchanged: no path through the assist lane reaches legal.decision or
     legal.approve_customization, and no role is granted by an identity provider.

r9   No document text, clause text, evidence, chunk, embedding input, prompt or generated
     answer leaves LeapSwitch-controlled infrastructure. No hosted model API, no hosted
     embedding API, no hosted document-processing service, and no third-party telemetry in
     the document path. Locked 54.6 is unchanged and extends to the assist lane: no document
     and no clause text beyond short cited excerpts enters this repository.
```

## Confidentiality

`LEGAL-02` applies unchanged. Internal legal positions, thresholds, rule configuration and rule
outcomes are permission-controlled, and where a viewer is unauthorized the field is **omitted, not
nulled** — in an assist-lane response exactly as in a deterministic one. An assist-lane answer must
never become the channel through which a confidential position reaches a viewer who could not read it
through the API.

## Determinism

The deterministic lane's guarantee is untouched. Identical inputs, identical configuration snapshot and
identical engine version continue to produce byte-identical output, and the existing determinism gate
continues to enforce it. The assist lane makes no determinism claim and is never admitted to that gate;
see `AM-28`.

---

# `AM-26` — Technology stack addition

**Amends:** the Step 39 locked technology stack, to the extent of the additions below and no further.

```text
ADDED
  Vector index            PostgreSQL pgvector extension, same instance
  Keyword index           PostgreSQL full-text search and trigram indexes, same instance
  Embedding model         local, self-hosted, open-weight
  Reranking model         local, self-hosted, open-weight, cross-encoder
  Generative model        local, self-hosted, open-weight
  Inference runtime       local model-serving process, no outbound network route
  GPU runtime             where required by the selected model

UNCHANGED
  Modular monolith        no microservices, no Kubernetes, no service mesh
  Backend / frontend      unchanged
  PostgreSQL              remains the system of record
  Background workers      the existing queue and worker infrastructure is reused, not replaced
  Document parsing        the existing parser and OCR path remain the primary path
  Object storage          "S3-compatible" is unchanged; the provider is selected under 55.6,
                          which requires no amendment

NOT ADDED, and requiring separate approval if ever proposed
  A second datastore for vectors
  Any hosted model, embedding or document-processing service
  Any RAG orchestration framework
  Any additional message broker
  Model fine-tuning or training on the corpus
```

## Model selection is not locked by this record

No specific model is locked. A model is selected by measurement, not by preference, and the smallest
model meeting the quality bar wins.

```text
r1   All generation reaches the application through one interface. The model identity is
     configuration, and no other code knows which model is running.

r2   Selection proceeds from the smallest candidate upward and stops at the first that meets
     the quality bar. A larger model is not adopted for headroom.

r3   The quality bar is measured on a LegalMind evaluation set built from real supplied
     documents, and it includes questions that have no answer in the corpus. Correct refusal
     is half the bar.

r4   Model version is pinned and recorded against every answer. A model change re-runs the
     evaluation set before it reaches a user.

r5   Weights are obtained once, checksummed, stored locally, and never fetched at runtime.
```

---

# `AM-27` — Workspace schema

**Amends:** the locked schema, by permitting the tables below and no others.

```text
r1   Assist-lane tables live in a database schema separate from the locked tables.

r2   The 30 existing tables are not altered. No column, constraint, index or enum on any
     locked table is added, changed or removed by this batch, and the existing schema
     invariant tests continue to pass unmodified. That is the evidence that this record
     leaves the locked model intact.

r3   The 42.1 design rules apply in full and without exception to the new tables: UUID
     primary keys, UTC timestamps, real foreign keys, append-only where the data is a record
     of something that happened, and JSONB only for genuinely variable configuration.

r4   A chunk is derived from an existing immutable Document Version and references the
     Document Evidence row it came from. It carries no independent provenance and creates no
     second source of truth for document content.

r5   Deleting a document hard-deletes its chunks and embeddings. A soft-deleted document
     whose chunks remain retrievable is a defect, not a state.

r6   Retrieval and answer records store chunk identifiers and scores. They do not duplicate
     document text into a second store; the text remains reachable through the chunk
     reference by a reader already authorized to read that document. The audit trail's
     existing prohibition on recording contract text is thereby preserved.

PERMITTED TABLES
  chunks                  derived text spans of a Document Version, with page and offsets
  chunk_embeddings        one row per chunk per embedding model
  embedding_models        the embedding model registry
  conversations           an assist-lane session
  messages                one row per turn
  retrieval_runs          the retrieval record behind an answer: query, filters, chunk ids, scores
  ai_answers              the answer record: model, prompt version, answer state, latency
  answer_citations        one row per verified claim-to-chunk link
  prompt_versions         the prompt registry

  No other table is authorized by this record.
```

The `audit_events` table gains new event types and **no schema change**.

---

# `AM-28` — Testing: a second tier, and the first tier untouched

**Amends:** the locked testing strategy, by adding a tier.

```text
TIER 1 — deterministic, unchanged
  Byte-identical output for identical inputs, configuration snapshot and engine version.
  The assist lane is NEVER admitted to this tier. No assist-lane component may be added to a
  determinism assertion, and no determinism assertion may be relaxed to accommodate one.

TIER 2 — assistive, new
  The assist lane is measured statistically, not byte-identically, against a LegalMind
  evaluation set of real question-and-answer pairs including unanswerable questions.

  Measured:  retrieval recall
             citation precision — does the cited span actually support the claim
             faithfulness — the share of claims with no valid supporting span
             refusal correctness in BOTH directions:
               refused when the evidence was in fact present
               answered when it should have refused

  Gate:      a change to retrieval, chunking, prompt, or model that worsens faithfulness or
             the wrongly-answered rate does not ship.

r1   The two tiers are never merged, and a Tier 2 result never satisfies a Tier 1 gate.

r2   The citation-enforcement component is tested independently of prompt and model code, and
     does not import them. A guardrail that a prompt change can affect is not a guardrail.

r3   The golden corpus remains a Tier 1 artifact governed by rule 21. The evaluation set is a
     separate artifact and does not substitute for it. AB-3 does not unblock the golden
     corpus, does not author a NORMATIVE fixture, and does not reduce the requirement for
     real supplied legal material.
```

---

# `AM-29` — The assist-lane answer state is a sixth axis

**Amends:** nothing. This record fixes a new vocabulary and is stated so that it is never confused
with an existing one.

The five controlled state axes — Mapping State, Finding Classification, Rule Outcome, Legal Decision,
Review Lifecycle — are unchanged, and none of them gains a value.

```text
r1   Assist-lane answer state is a SIXTH, separate axis. It never shares a field, a column,
     an enum or a name with any of the five legal axes.

r2   No assist-lane state value reuses UNABLE_TO_EVALUATE, NOT_APPLICABLE, AMBIGUOUS,
     MATCH, DEVIATION, MISSING, CONFLICT, ACCEPTABLE or UNACCEPTABLE. 45B.26 stands: no
     fifth RuleOutcome value is added, and an assist-lane state is not a route to adding one
     by another name.

r3   The three distinguishable assist-lane outcomes are recorded separately, because they
     have different causes and different remedies:

       no evidence retrieved       nothing available within the requester's authorized scope
       evidence insufficient       retrieved, but too weak to support an answer; the model
                                   is not called at all
       claim unsupported           the model answered and a claim failed verification

r4   A user-facing refusal is worded identically whether the cause was an empty corpus or an
     authorization exclusion. r6 and r7 of AM-25 depend on this.
```

---

## Not changed by AB-3

```text
Every legal-domain decision   unchanged — PROD, ROLE, LEGAL, FIND, DOC, ENG, ARCH (except
                              the Step 39 stack additions in AM-26), DATA (except the
                              separate-schema permission in AM-27), AUD, LIABILITY
AI-02                         unchanged — it is the authorizing basis for this batch
38.25                         unchanged — realized, not amended
Step 38 rules 20 and 21       unchanged — reaffirmed and strengthened
AI-01 "V1 WILL use"           unchanged
AI-01 architectural principle unchanged — ADOPTED as binding on the assist lane
Step 39 monolith position     unchanged — no microservices, no Kubernetes, no service mesh
The 30 locked tables          unchanged — no column, constraint, index or enum touched
The five state axes           unchanged — no value added to any of them
45B.26                        unchanged — no fifth RuleOutcome value
SEC-01, SEC-02, ROLE-05       unchanged — no super-role bypass, no authority by authentication
LEGAL-02, SEC-07, API-10      unchanged — omitted not nulled, byte-identical 404, extended
                              to retrieval by AM-25 r6 and r7
Locked 54.6                   unchanged — no document, no clause text beyond cited excerpts
                              enters the repository
Rule 7 and rule 21            unchanged — no invented legal requirement, no manufactured
                              legal material, in either lane
The determinism guarantee     unchanged for the deterministic lane; the assist lane makes no
                              such claim
Every Company Standard        unchanged — no position, threshold, basis or tolerance touched
Every Legal Rule              unchanged — none created, none altered; zero tolerance stands
The permission catalogue      extended by assist-lane access permissions only; no legal
                              authority permission added, none altered
Step 45E golden corpus        untouched — still 32 of 64, still zero NORMATIVE, still blocked
                              on real supplied legal material and unblocked by nothing here
C-05 - C-08, C-10, C-12, C-13 unchanged — open, and none resolved by this batch
```

## Position

```text
AM-25 - AM-29     LOCKED
Owner decision    2026-08-24
Effective         from this record forward; not retroactive
Repeals           nothing
Narrows           the V1 AI Boundary timing clause; the Step 38 AI exclusion entries;
                  AI-03's embedding exclusion; the LLM/RAG/vector-DB portion of the
                  Step 39 stack line
Schema impact     new tables in a separate schema; zero change to the 30 locked tables
Legal policy      none affected
Out of V1 scope   e-signature, purchase orders, billing, invoicing, payment settlement,
                  commercial transaction lifecycle, transaction state machines, autonomous
                  or multi-agent systems, fine-tuning, automatic redlining, clause
                  rewriting, AI-generated authoritative legal decisions, hosted model APIs,
                  hosted document processing, multi-tenant external access
Still required    a model selected by measurement (AM-26); an evaluation set built from real
                  supplied documents (AM-28); the golden corpus's outstanding legal material
Open, unaffected  C-05 - C-08, C-10, C-12, C-13
```

---

# Amendment Batch AB-4 — The Generative Model Is a Hosted Service

**Status: LOCKED**

**Owner decision recorded: 2026-08-25.** Effective from this record forward. Nothing in this batch is
retroactive, and no historical Review, Finding, Evaluation, Legal Decision or configuration snapshot is
altered, reinterpreted or invalidated by it.

**Records: `AM-30`, `AM-31`, `IMPL-02`.**

---

## Why this batch exists

The owner selected **Gemini Flash** as the generative model for the assist lane, and reaffirmed that
selection after the conflict with `AM-25` r9 was raised in writing.

`AM-25` r9 is not a preference about where a model runs. It is a confidentiality guarantee: no document
text, clause text, evidence, chunk, embedding input, prompt or generated answer leaves
LeapSwitch-controlled infrastructure. AB-3's `## Position` block lists `hosted model APIs` under
`Out of V1 scope`. A hosted generative model cannot be built without amending both, and the amendment
path is the one `AI-01` provided and AB-3 already used: an explicit, recorded revisiting.

This batch is that revisiting, and it is deliberately **narrow**. One destination changes. The eight
other terms of `AM-25` are untouched, and this batch adds terms of its own so that the posture is
tightened everywhere the egress does not require loosening.

```text
NOT amended    the assist lane's authority boundary
               AM-25 r1-r8 stand in full. The lane still produces no Finding, no Evaluation, no
               Classification, no Rule Outcome, no Mapping State, no Legal Decision and no
               Lifecycle transition, and still never answers "does this meet our standard?"

AMENDED        the destination of the generation call, and nothing else
               "nothing leaves LeapSwitch-controlled infrastructure"
                 ->  "the generation call, and only the generation call, may reach one approved
                      hosted provider, on the terms in AM-30 and the gate in AM-31"
```

## The enabling record

```text
AI-01  "Hard V1 constraint"
       "...unless this locked decision is explicitly revisited and changed."
       -> AB-3 was one such revisiting. This is a second, narrower one, on the same authority.

AM-26  r1  "All generation reaches the application through one interface. The model identity is
            configuration, and no other code knows which model is running."
       -> UNCHANGED, and it is what makes this batch reversible: if the provider relationship ends,
          or AM-31's terms are never confirmed, reverting to a local open-weight generative model is
          a configuration change behind that one interface, not a rewrite.
```

---

# `AM-30` — Gemini Flash is the selected generative model, on minimum-egress terms

**Amends, and only to this extent:**

```text
AM-25 r9         in the GENERATION path only. Every other path r9 names - embedding input,
                 chunking, parsing, OCR, hosted document processing, third-party telemetry -
                 remains closed. "embedding input" in particular STAYS FORBIDDEN from egress:
                 the embedding model is self-hosted (owner decision, 2026-08-25).

AM-26            the ADDED row  "Generative model | local, self-hosted, open-weight"
                 -> a hosted provider is permitted for generation only.

AM-26            the ADDED row  "Inference runtime | local model-serving process, no outbound
                 network route"
                 -> SCOPED, not removed. The local inference runtime continues to serve the
                    embedding and reranking models and continues to have no outbound network
                    route. The row no longer implies that generation is served by it. This clause
                    is named explicitly because leaving it unamended would make this record
                    internally contradictory.

AM-26            the NOT-ADDED entry "Any hosted model, embedding or document-processing service",
                 for a hosted GENERATIVE model ONLY. A hosted embedding service and a hosted
                 document-processing service remain NOT ADDED and still require separate approval.

AM-26 r2         "Selection proceeds from the smallest candidate upward" - for generation only.
                 The generative model is now selected by owner decision. r2 continues to govern
                 the embedding and reranking models without change.

AM-26 r5         "Weights are obtained once, checksummed, stored locally, and never fetched at
                 runtime" - inapplicable to a hosted model, and UNCHANGED for the embedding and
                 reranking models. Replaced, for the hosted model, by t7 below.

AB-3 Position    the "Out of V1 scope" line item  "hosted model APIs".
                 The adjacent item "hosted document processing" is NOT narrowed.
```

**Does not amend:**

```text
AM-25 r1 - r8    every one stands, in full and without qualification. In particular r2's distinct
                 database role holding no INSERT or UPDATE grant; r5's mechanical, off-model
                 citation enforcement; and r6/r7's authorization-inside-the-query and
                 existence-oracle ban.
AM-25            the Confidentiality paragraph. LEGAL-02 stands, and omitted-not-nulled stands.
Locked 54.6      unchanged. It governs what enters THIS REPOSITORY - a different concern from
                 egress, and this record does not touch it. No document, and no clause text
                 beyond short cited excerpts, enters the repository.
AM-26            the modular monolith position - no microservices, no Kubernetes, no service mesh.
                 There is therefore NO separate gateway service; AM-26 r1's single interface is an
                 in-process module boundary.
AM-26            the existing parser and OCR path as the primary path.
AM-26            the existing queue and worker infrastructure, reused not replaced.
AM-26            pgvector on the existing PostgreSQL instance; no second vector datastore.
AM-26            the exclusion of any RAG orchestration framework and any additional broker.
AM-26            the exclusion of fine-tuning and of training on the corpus.
AM-26 r1, r3, r4 one interface; the quality bar, including that correct refusal is half of it; the
                 model version pinned and recorded against every answer. See AM-31 for how r3 is
                 satisfied while the gate is closed.
AM-27            entirely. The nine permitted tables, the separate schema, and "no other table".
AM-28            entirely. Both tiers; the assist lane is still never admitted to Tier 1.
AM-29            entirely. The sixth axis and its three outcomes.
AI-01            the architectural principle for future AI.
Step 38 r20, r21 unchanged. The deterministic engine remains the authoritative source of Findings.
Step 39          the microservices and Kubernetes exclusion.
The five axes    unchanged. No value is added to any of them.
Every Company    unchanged. No position, threshold, basis or tolerance is touched.
Standard, every
Legal Rule
Rule 7, rule 21  unchanged, in both lanes.
```

## The terms

The batch is void of effect for any component that does not satisfy every term.

```text
t1   Generation is the ONLY permitted egress. Embedding, reranking, chunking, parsing and OCR
     remain local and self-hosted. No document, no chunk, and no embedding input leaves
     LeapSwitch-controlled infrastructure for any of them.

t2   Only the requester's question and the retrieved chunk spans required to answer that one
     request may be sent, together with the prompt template. Never a whole Document Version.

t3   LEGAL-02 IS AN EGRESS RULE, NOT ONLY A DISPLAY RULE. No Company Standard value, Legal Rule,
     threshold, rule configuration, Rule Outcome, Evaluation, Finding or other internal legal
     position may be included in an egressing payload. AM-25 r9's blanket ban made this moot; this
     term re-erects it explicitly, so that widening the destination does not silently widen
     LEGAL-02.

t4   No counterparty name, signatory name, contract identifier, user identifier or organizational
     identifier is included in an egressing payload. A real counterparty is never named to a third
     party.

t5   Every call is recorded in audit_events with the model identity, the prompt version, and a
     payload HASH - never the payload. No clause text and no internal legal position enters a log
     line or an audit row. Locked 53.3's redaction discipline applies to the egress payload exactly
     as it applies to a log record.

t6   Provider-side training on submitted content is not permitted. A provider tier that trains on
     submitted content by default is INELIGIBLE, whatever its cost. Fine-tuning and training on the
     corpus remain out of scope.

t7   The model version is pinned to a dated model identifier and recorded against every answer
     (AM-26 r4, reaffirmed). An alias that floats - "latest", or a bare family name - is not a pin.
     A provider-side model rotation is a model change and re-triggers AM-26 r4.

t8   Egress is allow-listed to one provider endpoint at the network layer, deny-by-default
     elsewhere, and that posture is asserted by a test - not by configuration review alone.

t9   The model reaches the application through exactly one interface. No other module knows that
     the provider is hosted, or which provider it is.

t10  No third-party telemetry, analytics or crash reporting is present anywhere in the document
     path. The provider call is the only external call in the stack.
```

## What this record does NOT decide

```text
The provider tier      Paid Gemini API or Vertex AI - not selected here. AM-31 requires whichever is
                       recorded to carry written no-training terms, and t6 makes a
                       trains-by-default tier ineligible.
The model version      No version string is locked. t7 governs.
The provider SDK       Rule 19 is UNAFFECTED. Authorizing the capability to call a hosted model
                       does not authorize any particular client library or dependency; that
                       remains a separate approval.
Embedding hardware     A self-hosted embedding model still needs AM-26's GPU-runtime provision
                       sized. A provisioning decision, not a lock.
Domain A / Domain C    No table is authorized by this record. AM-27's "no other table" stands, and
corpus tables          a corpus schema requires its own amendment with a concrete design.
Retention / deletion   AM-27 r5 requires deleting a document to hard-delete its chunks. No
                       hard-delete path for a Contract exists today, and this record does not
                       create one or assume its shape.
```

---

# `AM-31` — The real-contract egress gate, and how `AM-26` r3 is satisfied while it is closed

**Amends:** nothing. This record adds a control and resolves a contradiction that `AM-30` would
otherwise create.

## The gate

```text
g1   Real counterparty contract text must NOT reach the provider until that provider's no-training
     and data-retention terms are confirmed IN WRITING. This is a locked property, not a
     configuration preference.

g2   Enforcement is mechanical and DEFAULT-CLOSED. Absent a recorded confirmation the egress path
     refuses. A deployment that has not recorded one cannot send real material by changing a
     setting.

g3   The gate is released only by a FURTHER APPENDED RECORD citing the written terms - provider,
     tier, date. It is not released by a feature flag, an environment variable, a code review or a
     configuration change. This is the same discipline AM-25 r2 applies to the assist database
     role: a confidentiality boundary is enforced by mechanism, never by convention.

g4   STATUS AS OF THIS RECORD: CLOSED. No written confirmation exists. Only synthetic or explicitly
     cleared material may egress.

g5   The mechanism is implementation, not lock. Locked 55.3 already provides most of it - real
     contracts never leave production, and development and staging are synthetic-only - so the gate
     is expected to compose with the existing environment separation rather than introduce a new
     classification scheme. AM-27 r2 forbids a new column on a locked table, and AM-27 authorizes
     no new table for this purpose; a marker, if one is needed, therefore lives in existing JSONB
     or on a permitted assist table. Inventing a confidentiality classification scheme is a rule-7
     adjacent trap and is not authorized here.
```

## The contradiction this record resolves

`AM-26` r3 requires the quality bar to be *"measured on a LegalMind evaluation set built from real
supplied documents"*, and `AM-28` requires *"real question-and-answer pairs"*. `g1` forbids real
counterparty text reaching the provider. Under `AM-30` alone, model selection by measurement would be
impossible for a hosted model, and the likely outcome is that someone measures on synthetic material
and cites r3 as satisfied. That is closed here rather than left to discretion:

```text
m1   A provisional selection MAY be made on an explicitly-labelled SYNTHETIC evaluation set. The
     label is part of the record; a synthetic result is never reported as an AM-26 r3 result.

m2   A provisional selection is NOT a passed quality bar. AM-26 r3 is satisfied only by a run on
     real supplied material, which requires the gate in g1-g3 to be open first.

m3   NO ASSIST-LANE ANSWER REACHES A USER over real counterparty material on a synthetic-only bar.
     Until AM-26 r3 is satisfied on real material, the assist lane serves synthetic or cleared
     material only.

m4   AM-28's Tier 2 gate is unchanged, and a synthetic result never satisfies it - exactly as
     AM-28 r1 already forbids a Tier 2 result satisfying a Tier 1 gate.

m5   The evaluation set is subject to locked 54.6 and rule 21 without exception: it does not carry
     document text into the repository, and its real question-and-answer material is SUPPLIED, never
     manufactured.
```

---

# `IMPL-02` — The assist-lane build sequence is authorized by reference

**Amends:** nothing. `IMPL-01` is unchanged and remains in force.

`IMPL-01` authorized implementation of the locked V1 specification *in the Implementation Readiness Gate
§5 sequence*. That sequence predates AB-3 and contains no assist-lane unit, so the assist lane - now
locked - has locked content and no authorized order in which to build it.

```text
r1   The assist lane is authorized for implementation in the sequence recorded as
     IMPLEMENTATION_READINESS_GATE.md section 5b, by the same mechanism IMPL-01 used for section 5:
     authorization by reference, so the sequence can be revised without amending a lock.

r2   The Gate's section 6 standing constraints do NOT relax, and AM-25's nine terms, AM-27's table
     limit, AM-28's two tiers and AM-29's sixth axis are binding throughout.

r3   IMPL-02 authorizes building what is already locked. It confers no authority to decide anything
     marked NOT YET SPECIFIED, to resolve an open conflict or open decision, to add a table beyond
     AM-27's nine, or to add a technology or dependency beyond AM-26 as amended by AM-30.

r4   Ordering within 5b is an engineering judgment, revisable on evidence, EXCEPT for two properties
     which are locked by consequence and may not be reordered:
       - the citation-enforcement component is built BEFORE generation. AM-28 r2 requires it to be
         tested independently of prompt and model code and to not import them; built afterwards it
         will import them or need a retrofit.
       - the network egress allow-list (AM-30 t8) exists BEFORE the first real generation call, so
         AM-31's gate does not rest on application code alone.
```

---

## Not changed by AB-4

```text
Every legal-domain decision   unchanged - PROD, ROLE, LEGAL, FIND, DOC, ENG, ARCH, DATA, AUD,
                              LIABILITY. No legal policy is affected by this batch.
AM-25 r1 - r8                 unchanged - the authority boundary is untouched
AM-27, AM-28, AM-29           unchanged in full
IMPL-01                       unchanged and in force
The deterministic engine      unchanged - still the sole producer of every Finding, Evaluation,
                              Classification and Rule Outcome (Step 38 rule 21, AM-25 r1)
The five state axes           unchanged - no value added to any of them
The locked tables             unchanged - no column, constraint, index or enum touched
Locked 54.6                   unchanged - and it governs the repository, not egress
Locked 55.3                   unchanged - real contracts never leave production
Rule 7 and rule 21            unchanged - no invented legal requirement, no manufactured legal
                              material, in either lane
Rule 19                       unchanged - no dependency or client library is authorized here
The golden corpus             untouched - still blocked on real supplied legal material, and
                              unblocked by nothing here
C-05 - C-08, C-10, C-12,      unchanged - open, and none resolved by this batch
C-13
```

## Position

```text
AM-30, AM-31, IMPL-02   LOCKED
Owner decision          2026-08-25
Effective               from this record forward; not retroactive
Repeals                 nothing
Narrows                 nothing
Widens                  AM-25 r9, for the generation call alone, onto one approved hosted provider
Adds                    a default-closed gate on real-contract egress (AM-31), and an authorized
                        build sequence by reference (IMPL-02)
Schema impact           none
Legal policy            none affected
Still forbidden         hosted embedding; hosted document processing; third-party telemetry in the
                        document path; sending a whole Document Version; sending any internal legal
                        position; naming a counterparty to a third party; fine-tuning; training on
                        the corpus; any assist-lane Finding, Evaluation, Classification, Rule
                        Outcome, Mapping State, Legal Decision or Lifecycle transition
Gate status             AM-31 CLOSED as of this record - no written no-training confirmation
                        exists, so real counterparty contract text may not egress and the assist
                        lane serves synthetic or cleared material only
Still required          the written provider terms (AM-31 g1); an evaluation set from real supplied
                        material (AM-26 r3, AM-28); the golden corpus's outstanding legal material
Open, unaffected        C-05 - C-08, C-10, C-12, C-13
```

================================================================================
AMENDMENT BATCH AB-5 — Domain A and Domain C corpus tables
Approved by the owner on 2026-08-27 ("AM-32 approved").
Proposal: docs/00-project/AB5_DOMAIN_CORPUS_PROPOSAL.md
Resolves C-15. Does not touch C-16, which remains open until statute material with
recorded provenance is supplied.
================================================================================

# `AM-32` — Domain A and Domain C corpus tables

**Amends:** `AM-27`, by permitting the tables below and no others beyond AM-27's nine.
This is the amendment AM-30's "What this record does NOT decide" anticipated.

```text
r1   The three retrieval domains remain distinct, per the owner instruction of
     2026-08-25: separate tables, separate ingestion, separate provenance, separate
     citation semantics, separate access control. No shared content table, no
     domain-discriminator column on a content table, no flattening.

r2   AM-27 r1-r3 apply to every new table: same separate schema, the 30 locked tables
     untouched (schema invariant tests pass unmodified as the evidence), 42.1 design
     rules in full - UUID keys, UTC timestamps, REAL foreign keys, append-only where
     the data records something that happened.

r3   Domain A chunks derive from a published company_standard_versions row and
     reference it by real foreign key. There is no positions content table: the
     ratified standard remains the single source of truth. When a standard version is
     superseded, its chunks and their embeddings are hard-deleted and the new version
     is chunked (the AM-27 r5 principle, applied to configuration).

r4   Domain A output is EXTRACTIVE ONLY. AM-30 t3 forbids any Company Standard value
     in an egressing payload; therefore no Domain A retrieval result, in whole or in
     part, is ever included in a generation call. A Domain A answer is the ratified
     text quoted verbatim with its citation (standard code, version, source clause) -
     which is precisely the statement AM-25 r3 permits. No exception while t3 stands.

r5   Domain A retrieval requires assist.ask AND configuration.view, applied inside the
     query before retrieval (AM-25 r6). LEGAL-02 and SEC-07 apply: to a caller without
     configuration.view, Domain A results are indistinguishable from an empty corpus,
     and the identical AM-29 r4 refusal sentence is rendered.

r6   Domain C chunks derive from a statutes registry row. Every statutes row records:
     official title, act number and year, jurisdiction, the authoritative source
     (India Code for Indian statutes - the product vision's hard rule), source URL or
     gazette reference, version/as-amended date, the supplied file's SHA-256, and who
     supplied it and when. A statute with no provenance record cannot be ingested;
     the ingestion tool refuses it. Rule 21 stands: statute material is supplied,
     never authored, never fetched by the application.

r7   Domain C chunking is SECTION-based (section number, sub-section, marginal note
     preserved), not clause-based; a Domain C citation is Act + section, never a page
     alone. A statute is background law (source-material ruling, 2026-08-18): no
     Requirement, Company Standard, Legal Rule, threshold or acceptance position is
     derived from Domain C content, and Domain C output never enters the evaluator.

r8   Domain C content is public law and MAY be included in generation payloads,
     subject to the AM-31 gate and every AM-30 term. Domain A content may not (r4).

PERMITTED TABLES (six, in the AM-27 schema; no other table)
  position_chunks               derived text spans of a published Company Standard
                                version, with source-clause citation fields
  position_chunk_embeddings     one row per position chunk per embedding model
  statutes                      the statute registry: identity + provenance (r6)
  statute_chunks                section-based text spans of a statute (r7)
  statute_chunk_embeddings      one row per statute chunk per embedding model
  (sixth slot reserved)         judgments registry - NOT authorized here; a further
                                record names it when the curated list is supplied

MODIFIED AM-27 TABLES (two, both AM-27-batch tables; no locked table is touched)
  retrieval_runs                gains nullable position_chunk / statute_chunk FK
                                references alongside the existing chunk references
  answer_citations              gains nullable position_chunk_id and statute_chunk_id,
                                with a CHECK that exactly one chunk reference is set

r9   The embedding model, the calibrated refusal gate, the guardrails, the sixth-axis
     answer states and the refusal sentence are shared machinery across domains; the
     Tier 2 evaluation set gains Domain A and Domain C questions, including
     unanswerable ones, before either domain ships (AM-28's gate applies per domain).

r10  audit_events gains new event types for Domain A/C ingestion and retrieval, and
     no schema change. No statute text or standard text enters a log line (53.3).
```

--------------------------------------------------------------------------------
Owner rulings recorded alongside AB-5 on 2026-08-27 (conflict resolutions, no
locked text modified — rule 22; superseded text is annotated in
docs/00-project/CONFLICTS.md, never edited):

C-10 RESOLVED — "Code list authoritative maano, doc update karo." The role set the
     code carries (legalmind/security/permissions.py) is canonical: USER,
     LEGAL_REVIEWER, LEGAL_ADMIN, SUPER_ADMIN, plus LEGAL_DECISION_AUTHORITY as the
     SEC-03 additional grant. This is Step 23 (ROLE-06) as implemented; 42.2's
     "Initial roles: USER, ADMIN, SUPER_ADMIN" is hereby annotated as illustrative
     seed data superseded by Step 23. ADMIN is never seeded.

C-08 RESOLVED — "Permission checks server-side strict hain - code ko follow karo."
     Step 4's open question ("whether Reviewer can approve anything or only
     review/escalate") is closed as the code implements it: a Legal Reviewer views
     within Legal scope (REC-09) and may escalate; approval requires legal.decision,
     which no role carries by default and only LEGAL_DECISION_AUTHORITY grants
     (SEC-01/SEC-03 unchanged).

C-05, C-06, C-07 RESOLVED BY ANNOTATION — "Annotations add karo, lines edit mat karo
     (rule 22)." The stale 45A status block, the duplicate Step 29 heading and the
     superseded draft lists remain byte-identical in this file; their annotations
     live in docs/00-project/CONFLICTS.md, which now states for each exactly which
     text is superseded and by what.
================================================================================

# LegalMind V1 — Product Requirements

Source: all_lock.md, lines 1–1140 (Steps 1–2). Canonical source: all_lock.md (Steps 1-9).

---

## Step 1 — LegalMind V1 Goal

**Status: LOCKED**

LegalMind V1 will store the organization's legal documents and approved legal standards, compare a selected counterparty contract against those standards, identify:

* Matches
* Missing clauses/requirements
* Deviations
* Conflicts

It will provide supporting evidence, risk classification, human review, escalation, legal decision tracking, and structured reporting.

### V1 does NOT require

* LLM
* AI chat
* Vector database
* Autonomous legal decisions
* AI-generated legal advice

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

**Status: LOCKED**

A normal business user may have a counterparty contract and want to check whether it aligns with the organization's standards.

Therefore, uploading is not restricted only to Legal users.

### Normal User can

* Upload a counterparty contract
* Run a comparison
* View the comparison
* View findings
* Escalate the contract/finding for review

### Normal User cannot

* Approve a legal deviation
* Reject a legal deviation
* Change the organization's legal position
* Customize/finalize a contract
* Change approval rules

See [WORKFLOWS.md](./WORKFLOWS.md) for the fuller review/escalation/legal-authority workflow, and the (forthcoming) [USER_ROLES.md](./USER_ROLES.md) for the canonical permission matrix.

### Document metadata

LegalMind should store:

* Document name
* Document type
* Counterparty
* Version
* Effective date, if available
* Status (Draft / Active / Superseded)
* Uploaded by
* Upload timestamp

See [../03-document-model/DOCUMENT_MODEL.md](../03-document-model/DOCUMENT_MODEL.md) for how Document Type relates to Legal/Regulatory Reference.

### Original document preservation

The original uploaded file must remain unchanged. Any customized contract is a separate version/document.

### Metadata extraction

Where information can be safely extracted using deterministic document parsing, the system may suggest metadata instead of requiring manual entry.

No LLM is required for this V1 behavior.

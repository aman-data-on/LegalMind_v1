# Company Standards

Source: all_lock.md Steps 20, 21, 29. Canonical source: all_lock.md (Steps 20-21, 29).

Related: [LEGAL_RULES.md](./LEGAL_RULES.md) · [LEGAL_DECISIONS.md](./LEGAL_DECISIONS.md) · [../03-document-model/DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)

## What a Company Standard Is

**Status: LOCKED** (Step 20)

The Company Standard is the organization's default/preferred position for a given Clause. A customer provision matching it produces a `MATCH` finding.

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

### Locked Rules (Step 20)

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

## Configuration Structure (Step 21)

**Status: LOCKED**

Authorized Legal/Admin users manage the Clause Library and related legal configuration through a dedicated configuration workflow.

A Clause can contain or reference:

* Requirements
* Company Standard
* Optional Pre-approved Legal Rule

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

### Locked Rules (Step 21)

1. Authorized Legal/Admin users manage the Clause Library through a dedicated configuration workflow.
2. A Clause contains its Requirements, Company Standard reference, and optional Pre-approved Legal Rule.
3. Pre-approved Legal Rules are optional; not every Clause needs one.
4. Normal Users cannot modify legal configuration.
5. Legal configuration changes create a new version rather than overwriting historical configuration.
6. Historical Reviews continue using the configuration version that existed when they were reviewed.
7. Legal Rules are controlled legal configuration, not ordinary application settings.
8. Exact role/permission ownership for configuration actions will be defined separately (see [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md)).

### Example Version Change

```text
Limitation of Liability Configuration v1
Company Standard = 6 months

        ↓ Legal configuration change

Limitation of Liability Configuration v2
Company Standard = 12 months
```

Existing reviews remain tied to v1; new reviews use v2.

## Draft → Review → Publish Lifecycle (Step 29)

**Status: PROVISIONAL** (Step 29 begins as a "Recommended workflow" section, not explicitly re-marked LOCKED; the subsequent re-issued Step 29 header below is explicitly LOCKED and formalizes the same lifecycle)

### Core Principle

```text
Customer Contract
        ≠
Company Legal Configuration
```

The customer contract is evidence being reviewed. The Legal Configuration defines what LegalMind should compare it against. Therefore, changing a Company Standard or Legal Rule does not modify historical contracts or historical Reviews.

### Admin Configuration Areas

The Admin Legal Configuration area should manage:

1. Document Types
2. Requirements
3. Company Standards
4. Legal Rules
5. Clause/Requirement mappings
6. Requirement status (active/inactive)
7. Configuration versions
8. Change history

### Example

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

### Draft → Review → Publish

```text
Draft
  ↓
Review
  ↓
Publish
  ↓
Active
```

A configuration change should not become active merely because an Admin typed a new value. The authorized Legal workflow should explicitly publish it.

### Effective Date

Every published configuration version should have an effective timestamp.

```text
Version:
v2

Published:
2026-08-20 11:42

Effective:
2026-08-20 11:42
```

The exact scheduling capability can be decided during technical design; V1 should at minimum support immediate activation upon publish.

### Historical Integrity

A configuration version that has already been used by a Review must remain available as historical data. It should not be overwritten.

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

### Deactivation

If a Requirement or Rule is no longer applicable:

```text
ACTIVE
   ↓
DEPRECATED / INACTIVE
```

It should not be hard-deleted if historical Reviews reference it. Historical references must continue to resolve.

### Permission

Only authorized Legal users with the appropriate Legal Configuration permission can:

* create configuration drafts
* edit drafts
* publish versions
* deactivate/deprecate configuration
* manage Requirements
* manage Company Standards
* manage Legal Rules

A normal User cannot modify Legal Configuration. A Super Admin does not automatically receive Legal Configuration authority merely because they are a Super Admin.

### Audit

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

See [../07-audit/AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md).

### Important Separation

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

Editing a draft must not affect active Reviews. Publishing a new version must not rewrite historical Reviews. Deprecating a configuration item must not break historical Review references.

## Admin Legal Configuration Workflow (Step 29, re-issued as LOCKED)

**Status: LOCKED**

### Locked Decision

Legal Configuration is a separate, structured control layer from uploaded contract documents.

Authorized Legal users manage Requirements, Company Standards, Legal Rules, Document Types, and mappings without replacing the underlying MSA/NDA or other source documents.

### Locked Rules

1. Legal Configuration is separate from uploaded contract documents.
2. Authorized Legal users manage Requirements, Company Standards, Legal Rules, Document Types, and mappings through structured configuration.
3. Individual configuration items can be changed without uploading/replacing the entire source document.
4. Configuration changes create new versions; existing versions are never silently overwritten.
5. Configuration changes follow: `Draft → Legal Review → Publish → Active`
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

### Example

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

### Running Review Example

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

### Published Configuration Correction

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

### Core Rule

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

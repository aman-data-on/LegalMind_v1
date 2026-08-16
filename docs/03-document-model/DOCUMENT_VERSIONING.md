# Document & Contract Versioning

Source: all_lock.md Step 26. Canonical source: all_lock.md (Step 26).

Related: [../02-legal-domain/COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md) · [../02-legal-domain/LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md) · [../07-audit/AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md)

> Note: this file now covers **Step 26 (LOCKED)** and **Step 33 (PROVISIONAL)**. Step 33 elaborates Step 26's locked versioning model; it is not itself locked. See [../00-project/CONFLICTS.md](../00-project/CONFLICTS.md) for the C-03 reconciliation record.

## Locked Decision

**Status: LOCKED**

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

# Step 33 — Contract Versioning & Re-Review Workflow

Source: all_lock.md Step 33. Canonical source: all_lock.md (Step 33).

**Status: PROVISIONAL — elaboration of locked Step 26, not itself locked.**

Step 33 does **not** contradict Step 26. It is a refinement and elaboration of the Step 26 locked model: it keeps every Step 26 locked rule intact and describes in more detail how contract versioning and re-review operate. Where Step 33 goes beyond Step 26, it adds detail rather than reversing a locked decision.

The source closes Step 33 with: "I recommend this as the Step 33 model. Do not lock it yet until you confirm it looks right." Accordingly, nothing in this Step 33 section is LOCKED.

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

## 33.2 Example

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

## 33.3 Why this matters legally

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

## 33.4 How does LegalMind know it's a new version?

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

## 33.5 Who creates the new version?

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

## 33.6 Version numbering

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

## 33.7 Every version is immutable

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

## 33.8 Every Review points to exactly one Document Version

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

## 33.9 Configuration version is also fixed

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

## 33.10 Re-review

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

## 33.11 Re-review does NOT create a new document version

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

## 33.12 Example: negotiation lifecycle

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

## 33.13 Can a version be deleted?

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

## 33.14 What if the wrong document was uploaded?

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

## 33.15 Version comparison

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

## 33.16 But don't make version diff equal to Legal conclusion

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

## 33.17 Version relationship

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

## 33.18 Audit trail

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

## 33.19 My recommendation for Step 33

The source proposes locking these rules. They are recorded here as **PROVISIONAL** and are not locked.

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

---

## Step 33 rules with no Step 26 counterpart (remain UNLOCKED)

The following three Step 33 rules are genuinely new material. They have no counterpart among the Step 26 locked rules and are therefore **not** covered by the Step 26 lock:

1. **System-controlled sequential version numbering that users cannot rewrite** (33.6 / rules 6–7).
2. **Incorrect versions are marked invalid/withdrawn rather than erased, and Document Versions used by historical Reviews cannot be hard-deleted** (33.13–33.14 / rules 15–16).
3. **The explicit predecessor relationship chain v1 → v2 → v3** (33.17 / rule 17).

These three must not be implemented or assumed until Step 33 is explicitly locked.

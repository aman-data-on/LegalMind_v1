# Review Ownership & Visibility

Source: all_lock.md Step 24. Canonical source: all_lock.md (Step 24).

Related: [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md) (Step 24 also reproduced there alongside the role matrix) · [AUTHORIZATION.md](./AUTHORIZATION.md) (authorization mechanics) · [../07-audit/AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md)

## Locked Decision

**Status: LOCKED**

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

### Access

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

**Status: LOCKED**

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

## 📎 Implementation note — appended 2026-08-17, locked text unchanged

Nothing above is modified. Locked **`REC-09`** defines r6's *"explicit Legal scope"*,
which this document names and does not define:

```text
A Review is in Legal scope when EITHER any Finding has a non-withdrawn
escalation (r5, AM-23) OR its status is LEGAL_REVIEW (Step 30).
A `legal.review` holder may VIEW such a Review — no ownership (r16, r17),
no decision authority (SEC-02, SEC-05).
```

Until `REC-09`, both branches of r6 were unimplementable — nothing populates
`review_assignments`, and Legal scope had no criterion — so a Legal Reviewer could reach
**no Review at all** (`F-6`).

**Per-user assignment is deferred to V2.** `review_assignments` (`AM-22`) remains
ratified and is still read for access; nothing writes it. Assignment is r6's other
branch, and *"and/or"* permits it without mandating it — the same reasoning by which
`AM-24` deferred ownership transfer.

**Contract and Document access are unchanged and owner-only.** Whether Legal scope
extends to the underlying Contract or to downloading the original document is **not**
decided by `REC-09`.

Full trace: [EDGE_CASES/LEGAL_ACCESS_GAP.md](EDGE_CASES/LEGAL_ACCESS_GAP.md).

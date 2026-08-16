# Authorization

Source: all_lock.md Steps 23, 24 (authorization mechanics only). Canonical source: all_lock.md (Steps 23-24).

Related: [../01-product/USER_ROLES.md](../01-product/USER_ROLES.md) is the **canonical** source for the full role/permission matrix and role summaries — this file focuses on authorization mechanics and principles, not the full table. See also [OWNERSHIP.md](./OWNERSHIP.md) for ownership-specific rules.

## Permission Model Mechanics (Step 23)

**Status: LOCKED**

* Role names alone do not determine resource scope.
* Permissions support resource scope such as own, assigned, Legal scope, or system scope.
* Internal Legal Rules are inaccessible to normal Users.
* User/role administration is separate from Legal configuration.
* Legal Decision authority is an explicit permission.
* Approval of contract-specific customization is an explicit permission.
* Legal configuration permissions are separate from Legal review permissions.
* Super Admin does not automatically have Legal authority.

### Recommended Model Shape

**Status: PROVISIONAL**

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

### Important Separation

**Status: LOCKED**

```text
Legal Review
      ≠
Legal Configuration
      ≠
Platform Administration
```

These responsibilities must remain separately permissioned.

## Authorization Principles (Step 24)

**Status: LOCKED**

1. Access is based on permission + resource scope, not simply role name.
2. Least-privilege access is the default.
3. Access restrictions must be enforced server-side, not only by hiding UI elements.
4. Access to confidential Legal information must be auditable.
5. Internal Legal Rules and confidential Legal Decision details are protected from normal Users.
6. A User can see the user-facing outcome of their own Legal review without necessarily seeing confidential internal Legal reasoning or Legal thresholds.
7. Contract-content access and platform administration are separate permissions.
8. Legal Admin has authorized Legal-scope access but does not automatically have unrestricted platform access.
9. Super Admin does not automatically have access to confidential contract or Legal content.

### Server-Side Enforcement

**Status: LOCKED**

> "Access restrictions must be enforced server-side, not only by hiding UI elements." — this is stated as an explicit locked rule (Step 24, rule 14) and is the primary authorization-mechanics takeaway of this range: authorization decisions cannot be a client-side/UI-only concern.

### Auditability of Access

**Status: LOCKED**

Access to confidential Legal information must itself be auditable — see [../07-audit/AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md) for the Audit Trail model that captures this (including the locked rule that "Audit access itself is auditable," Step 25).

## Example (Step 23)

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

An authorized Legal user with the explicit approval permission can make the Legal Decision. A Super Admin without that Legal permission cannot approve the customization merely because they are a Super Admin.

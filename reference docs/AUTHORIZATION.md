# LegalMind — Authorization System

**Version:** 1.0  
**Last Updated:** 2026-09-01  
**Status:** Reference (reflects `ui-phase3-through-3.4` branch state; verify against current code if read later)  
**Specification:** Step 23 (ROLE-01–ROLE-07), Step 47 §47.5 (SEC-01–SEC-07)

---

## Overview

LegalMind uses **Role-Based Access Control (RBAC)** with a flat, code-defined permission catalogue
(21 permissions, 5 canonical roles) and **no bypass mechanism.** Authorization is **always**
server-side, applied **before** any domain operation, at the API/service boundary (locked 43.23).

**Crucially:** This is NOT a "super-admin can do anything" system. A Super Admin cannot view a
regular User's Contracts or legal decisions. Administrative authority and content access are
entirely separate.

---

## Key Features

- ✅ **No Bypass Mechanism** — Every permission is an explicit grant; no wildcard or role override
- ✅ **Code-Defined Permissions** — 21 permission constants (not DB-editable)
- ✅ **5 Canonical Roles** — User, Legal Reviewer, Legal Admin, Super Admin, Legal Decision Authority
- ✅ **Multi-Role with Union Semantics** — A user can hold multiple roles; permissions are the union
- ✅ **Fresh-Per-Request Resolution** — Permissions resolved from database on every request (S-1)
- ✅ **Object Visibility Before Permission** — 404 if object not visible, 403 if permission denied (SEC-07)
- ✅ **Escalation Guards** — S-8: can't grant what you don't hold; S-9: same for edit/delete
- ✅ **Legal Authority Preservation** — Never zero legal.decision holders (SEC-05)
- ✅ **Field-Level Redaction** — Sensitive fields omitted (never nulled) when permission denied (LEGAL-02)
- ✅ **Audit Trail** — Every permission check, denial, and authority change is logged

---

## Permission Catalogue

21 permissions, organized by domain. **All permission names are string constants in
`security/permissions.py`; they are code-defined, not database-editable.**

### Contracts & Documents (4 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `contract.view` | List contracts, view contract metadata | User can see the Documents page |
| `contract.create` | Create new contract | Upload new document |
| `contract.update` | Update contract details (name, owner) | Edit metadata |
| `contract.delete` | Delete a contract | Remove a contract (soft-delete in practice) |

### Documents (3 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `document.upload` | Upload a new document version | Upload initial file or revised version |
| `document.view` | Read document content | Workspace document pane, download link |
| `document.download` | Download PDF/DOCX | Export document to local storage |

### Reviews, Findings, Evaluations (3 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `review.create` | Create new review, run analysis | Start analysis on a contract |
| `review.view` | List reviews, view review details | Browse legal queue, view findings |
| `finding.view` | View findings and evaluations | See findings pane, read evidence |
| `finding.comment` | Add comments to findings | Discussion on specific findings |
| `evaluation.view` | View evaluation details, rule outcome | Read the legal standard and rule applied |

### Legal Authority (3 permissions — Never Bypassable)

| Permission | Description | Scope |
|------------|-------------|-------|
| `legal.review` | Access reviews in Legal scope | View a review that is in Legal workflow (escalated or LEGAL_REVIEW status) |
| `legal.decision` | Make a Legal Decision | Approve/reject a deviation, mark RESOLVED |
| `legal.approve_customization` | Approve a contract customization | Additional grant, required alongside legal.decision for APPROVE_CUSTOMIZATION decisions |

**⚠️ These are locked by name (Step 23). They cannot be inherited, cannot bypass authentication,
and no Super Admin has them by default.**

### Internal Legal Position (1 permission)

| Permission | Description | Field-Gating |
|------------|-------------|---------------|
| `legal_position.view` | View internal legal positions | When denied, fields like `rule_outcome`, `expected_value`, `explanation` are **omitted** from JSON responses (never nulled) |

### Legal Configuration (4 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `configuration.view` | View Requirements, Legal Rules | Browse configured standards |
| `configuration.draft` | Create/edit Requirements | Define new Requirement versions |
| `configuration.publish` | Publish configuration snapshot | Deploy configuration to live |
| `configuration.deprecate` | Deprecate old configurations | Archive outdated standards |

### Reporting (3 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `report.view` | View review report | Summary page (counts, status) |
| `report.generate` | Generate full report | Underlying data for rendering |
| `export.generate` | Export review (PDF/DOCX) | Save review with findings to file |

### Assist (1 permission)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `assist.ask` | Ask a question about document | Use the Ask pane, get Gemini-assisted answers |

### Audit (1 permission)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `audit.view` | View audit trail | Browse who did what, when |

### Administration (3 permissions)

| Permission | Description | Use Case |
|------------|-------------|----------|
| `user.manage` | Create, list, edit users; grant/revoke roles | User admin page |
| `role.manage` | Create, list, edit roles; manage permissions | Role admin page |
| `platform.manage` | System-level operations | Future: system settings, feature flags |

---

## Canonical Roles (Step 23)

5 roles, defined in `security/permissions.py`:

### 1. USER

**Display Name:** User

**Default Permissions:**
- `contract.view`, `contract.create`, `contract.update`
- `document.upload`, `document.view`, `document.download`
- `review.create`, `review.view`
- `finding.view`, `finding.comment`, `evaluation.view`
- `report.view`, `export.generate`
- `assist.ask`

**Use Case:** Regular employee uploading contracts, viewing findings, asking questions.

**Legal Authority:** None. `legal.*` permissions are never granted.

### 2. LEGAL_REVIEWER

**Display Name:** Legal Reviewer

**Default Permissions:**
- `contract.view`, `document.view`, `document.download`
- `review.view`
- `finding.view`, `finding.comment`, `evaluation.view`
- `legal.review` (can see reviews in Legal scope)
- `legal_position.view` (can see internal rule outcomes)
- `configuration.view`
- `report.view`, `report.generate`, `export.generate`
- `assist.ask`

**Use Case:** Attorney reviewing findings, understanding legal standards applied, collaborating
with other reviewers.

**Legal Authority:** `legal.review` only. **Cannot** make decisions; can only review and comment.

### 3. LEGAL_ADMIN

**Display Name:** Legal Admin

**Default Permissions:**
- Same as LEGAL_REVIEWER, plus:
- `configuration.draft`, `configuration.publish`, `configuration.deprecate`

**Use Case:** Senior legal counsel managing the legal standards and requirements.

**Legal Authority:** Same as LEGAL_REVIEWER; still cannot make decisions.

### 4. SUPER_ADMIN

**Display Name:** Super Admin

**Default Permissions:**
- `user.manage`, `role.manage`, `platform.manage`, `audit.view`

**⚠️ Explicitly does NOT include:**
- No `contract.view`, `contract.create`, `contract.update`, `contract.delete`
- No `review.view`, `finding.view`, `finding.comment`
- No `legal.*` permissions (locked Step 23 / SEC-02)
- No `legal_position.view`
- No `configuration.*`

**Use Case:** System administrator managing accounts, roles, and permissions. **Cannot view
contracts or legal decisions.**

**Legal Authority:** None. System administrators are not attorneys; they manage the system, not the law.

### 5. LEGAL_DECISION_AUTHORITY

**Display Name:** Legal Decision Authority

**Default Permissions:**
- `legal.decision`
- `legal.approve_customization`

**Use Case:** An **additional** role, never a primary one. Assigned to a user who *already holds*
another role (e.g., LEGAL_ADMIN), granting them legal decision-making power.

**Distinct from other roles:** This role carries no other permissions. It is purely a holder of
legal authority, enabling the two-role model (Step 4: Admin A can review, Admin B can review + decide).

**Legal Authority:** Both permissions above.

---

## Permission Grants (DEFAULT_ROLE_GRANTS)

Defined in `security/permissions.py` lines 138-171. Seeded idempotently by `security/seed.py`:

```python
def seed_default_grants(db, *, only_if_role_empty=True):
    """Apply defaults from Step 23. Never re-grants a trimmed permission."""
```

**Key behavior:** If a role already has permissions assigned, the seeder does NOT overwrite them
(preserves admin customizations). New deployments start with the locked defaults.

---

## Authorization Boundary: The Guard Class

**File:** `api/deps.py` (lines 121–249)

Every handler receives a `Guard` dependency:

```python
@router.get("/reviews/{review_id}")
def view_review(review_id: UUID, guard: Guard = Depends(get_guard)):
    # guard has already checked authentication
    review = guard.review(review_id, P.REVIEW_VIEW)
    # Now domain operation
    return data(serialize_review(review))
```

**Guard methods:**

| Method | Purpose |
|--------|---------|
| `guard.permission(permission)` | Check permission (e.g., `user.manage`). Used for collection endpoints. |
| `guard.contract(id, permission)` | Fetch contract, check visibility, then check permission. |
| `guard.review(id, permission)` | Fetch review, check visibility (ownership/scope), then check permission. |
| `guard.finding(id, permission)` | Fetch finding (via review traversal), check permission. |
| `guard.evaluation(id, permission)` | Fetch evaluation (via finding traversal), check permission. |
| `guard.document_version(id, permission)` | Fetch document (via contract traversal), check permission. |

**Ordering (locked 43.23):** Object visibility is resolved **first**, then permission:

```python
def review(self, review_id, permission):
    review = self._visible(require_review_visible, review_id, "review")
    # If not visible → raises NotVisible (404) here
    self._require(permission, "review", review_id)
    # If permission denied → raises Forbidden (403) here
    return review
```

**Result:** A 404 never discloses whether the object exists (SEC-07). An unauthorized caller always
gets the same response whether the object exists or they lack access.

---

## Endpoint Permission Mapping

**File:** `api/permission_map.py` (lines 34–151)

A **data table** mapping every HTTP endpoint to its required permission:

```python
ENDPOINT_PERMISSIONS: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/contracts"): P.CONTRACT_VIEW,
    ("POST", "/api/v1/contracts"): P.CONTRACT_CREATE,
    ("GET", "/api/v1/users"): P.USER_MANAGE,
    ("POST", "/api/v1/users"): P.USER_MANAGE,
    ...
}
```

**Why a table, not decorators?** Locked 49.3 requires explicit permission mapping for every
endpoint, and a test (`test_all_routes_in_permission_map`) asserts that every registered route
appears in this table. No implicitly-public endpoints.

---

## Permission Resolution (S-1)

**File:** `security/resolver.py`

`effective_permissions(db, user_id)` returns a frozenset of permission strings:

```python
def effective_permissions(db: DBSession, user_id: UUID) -> frozenset[str]:
    """Resolve all permissions this user holds via their assigned roles."""
    return frozenset(
        db.execute(
            select(M.Permission.name)
            .join(M.RolePermission, ...)
            .join(M.UserRole, ...)
            .where(M.UserRole.user_id == user_id)
        ).scalars().all()
    )
```

**Resolved fresh on every request** (not cached across requests — locked S-1). A permission
revocation mid-session takes effect on the very next request.

---

## Escalation Guards (S-8, S-9, SEC-05)

**File:** `security/guards.py`

Three guards protect the authority layer:

### 1. Require Can Grant Role (S-8)

```python
def require_can_grant_role(db, actor_id, role_id):
    """A user may not grant an authority they do not themselves hold."""
    actor_perms = effective_permissions(db, actor_id)
    target_perms = _role_permissions(db, role_id)
    escalation = target_perms - actor_perms
    if escalation:
        raise Forbidden("escalation refused: ...")
```

**Applied when:** `POST /users/{id}/roles` (granting a role to a user)

**Enforcement:** The role's permissions are compared against the actor's permissions. If the target
role grants a permission the actor doesn't have, the grant is refused.

### 2. Require Can Administer User (S-9)

```python
def require_can_administer_user(db, actor_id, target_user_id):
    """Cannot edit/delete a user who holds permissions you don't."""
    if actor_id == target_user_id:
        return  # OK to edit yourself
    actor_perms = effective_permissions(db, actor_id)
    target_perms = effective_permissions(db, target_user_id)
    excess = target_perms - actor_perms  # Perms target has but actor doesn't
    if excess:
        raise Forbidden("escalation refused: ...")
```

**Applied when:**
- `PATCH /users/{id}` (editing a user's name/status)
- `DELETE /auth/sessions/{id}` (revoking another user's session)
- `POST /users/{id}/roles` (granting roles)

**Rationale:** Without S-9, a user could not *grant* legal authority but could disable the account
holding it — reaching the same outcome by another route. This guard covers edit and delete, not
only granting.

### 3. Preserve Legal Authority (SEC-05)

```python
def count_legal_authorities(db) -> int:
    """How many ACTIVE users can currently make a Legal Decision."""
    return db.execute(
        select(func.count(func.distinct(M.UserRole.user_id)))
        .where(M.Permission.name == P.LEGAL_DECISION, M.User.status == E.UserStatus.ACTIVE)
    ).scalar_one()

def assert_legal_authority_preserved(db, before_count):
    """Refuse if this change would leave zero legal authorities."""
    if before_count and count_legal_authorities(db) == 0:
        raise Forbidden("refused: this change would leave no user able to make a Legal Decision")
```

**Applied when:**
- Disabling/suspending a user (`PATCH /users/{id}`)
- Revoking a role with `legal.decision` (`DELETE /users/{id}/roles/{code}`)

**Constraint:** If there was at least one legal authority before the change, there must still be
one after. The system can start with zero (fresh deploy) but can never reach zero after the first
one is appointed (locked SEC-05).

---

## Object Visibility Model

**File:** `security/authorization.py` (lines 23–231)

### Contracts: Ownership Only

A user sees only their own contracts.

```python
def require_contract_visible(db, user_id, contract_id):
    c = db.get(M.Contract, contract_id)
    if c is None or c.owner_id != user_id:
        raise NotVisible("contract not found")  # 404
    return c
```

**No delegation, no shared contracts in V1.** Ownership is created and never transferred.

### Reviews: Three-Way Visibility

A user can see a review if any of:

1. **Owner:** The user created the review (`review.created_by == user_id`)
2. **Legal Assignment:** A `ReviewAssignment` row exists, not revoked
3. **Legal Scope (REC-09):** The user has `legal.review` permission AND the review is in Legal scope

```python
def can_see_review(db, user_id, review):
    if _is_review_owner(review, user_id):
        return True
    if _has_legal_assignment(db, review.id, user_id):
        return True
    if has_permission(db, user_id, LEGAL_REVIEW):
        return review_in_legal_scope(db, review)
    return False

def review_in_legal_scope(db, review):
    """Review is in Legal scope if status is LEGAL_REVIEW
    OR any Finding has a non-withdrawn Escalation."""
    if review.status == ReviewStatus.LEGAL_REVIEW:
        return True
    # Check escalations
    return db.execute(
        select(M.Escalation.id)
        .where(M.Finding.review_id == review.id,
               M.Escalation.withdrawn_at.is_(None))
        .limit(1)
    ).first() is not None
```

**Locked REC-09 defines "Legal scope":**

> (a) any Finding has an escalation not yet withdrawn, OR  
> (b) the Review lifecycle status is LEGAL_REVIEW

Both must be possible independently; neither implies the other.

**Super Admin does not automatically see Legal content** (locked Step 24 r8). The `legal.review`
permission is what gates it, and Super Admin's defaults include no `legal.*`.

---

### Findings & Evaluations: Transitive Visibility

A user sees a finding/evaluation only if they see the owning review:

```python
def require_finding_visible(db, user_id, finding_id):
    finding = db.get(M.Finding, finding_id)
    if finding is None:
        raise NotVisible("finding not found")
    require_review_visible(db, user_id, finding.review_id)  # 404 if review not visible
    return finding
```

---

### Document Versions: Contract Traversal

A document version is reachable only through a contract the caller can see:

```python
def Guard.document_version(self, id, permission):
    version = self.db.get(M.DocumentVersion, id)
    if version is None:
        raise NotVisible("document version not found")
    self._visible(require_contract_visible, version.contract_id, "contract")
    self._require(permission, "document_version", id)
    return version
```

---

## Field-Level Redaction (LEGAL-02)

**File:** `security/authorization.py` (lines 188–232)

Internal legal positions (the organization's standards, rule outcomes, thresholds) are omitted
from responses when the user lacks `legal_position.view`:

**Redacted fields (omitted, never nulled):**
- `rule_outcome`
- `expected_value`
- `operator`
- `comparison`
- `explanation`
- `rule_configuration`
- `legal_rule_version_id`

**Not redacted (always present if object is visible):**
- `classification` (what the provision is — counterparty's language)
- `actual_value` (what the contract says)
- `requires_decision` (whether human approval is needed)
- Evidence and facts (the extraction layer)

**Rationale:** A Regular User can see that a clause "requires decision" and can ask for
clarification (assist.ask), but cannot see the organization's internal standard that triggered it.

---

## Audit Trail

**File:** `security/audit.py`

Every permission check (success or denial) is logged:

```python
def log_access(request, user, status, route_info):
    log_event("auth.permission_granted", request_id=..., actor_id=..., permission=...)
```

Every denied check also records:

```python
def _deny(self, permission, entity_type, entity_id):
    A.record(db, action=A.AUTHZ_PERMISSION_DENIED, ...)
    log_event("authz.denied", signal="authz.denial_count", ...)
```

Locked 53.5 requires this for security monitoring: repeated denials on the same object can surface
an enumeration attack.

---

## Testing Authorization

### Manual Testing Steps

1. **Create a user with no roles** — `POST /users` → new user has empty role set
2. **Try to view a contract with no permissions:**
   - `GET /api/v1/contracts` → 403 Forbidden (missing contract.view)
3. **Grant `contract.view` permission** → `POST /users/{id}/roles?role=USER`
4. **Retry step 2** → 200 OK, now can see (but can't create; contract.create denied)
5. **Try to grant yourself `legal.decision`:** → 403 (escalation guard; you don't hold it)
6. **Try to disable the last legal authority:** → 403 (SEC-05 guard)

---

## Common Issues

### Issue 1: 403 Forbidden — Missing Permission

**Response:** `{"detail": "missing permission: contract.view"}`

**Cause:** User's roles don't include a role with this permission.

**Solution:** Check `GET /api/v1/users/{id}` to see their current roles, then `POST /users/{id}/roles` to grant a role that includes the needed permission.

### Issue 2: 404 Not Found — Object Not Visible

**Response:** `{"detail": "contract not found"}`

**Cause:** Either the object doesn't exist, or the user doesn't own it (contracts) or can't see it
(reviews, findings).

**Solution:** Confirm the object ID is correct and the user has the right to access it. Admin can
check the audit log for access denials.

### Issue 3: Escalation Refused — Can't Grant Authority

**Response:** `{"detail": "escalation refused: cannot grant permissions the actor does not hold: ['legal.decision']"}`

**Cause:** S-8 guard: trying to grant a permission to a role that the current user doesn't have.

**Solution:** Only a user who holds `legal.decision` can create a role granting it. Check the current user's permissions and roles.

### Issue 4: Escalation Refused — Can't Edit More-Privileged User

**Response:** `{"detail": "escalation refused: target holds permissions the actor does not: ['legal.decision']"}`

**Cause:** S-9 guard: trying to edit/disable a user who holds permissions you don't have.

**Solution:** Escalate to a user (e.g., a Super Admin + LEGAL_DECISION_AUTHORITY) who can make the change.

---

## Related Documentation

- [User Management](./USERS.md) — User/role CRUD API
- [Authentication](./AUTHENTICATION.md) — Session + JWT auth
- [Step 47 Security Spec](../06-security/STEP_47_SECURITY_SPECIFICATION.md) — Locked auth & authz decisions
- [Ownership & Scope](../06-security/OWNERSHIP.md) — Object visibility detailed rules
- [Locked Decisions](../00-project/LOCKED_DECISIONS.md) — ROLE-01–ROLE-07, SEC-01–SEC-07

---

**Last Updated:** 2026-09-01  
**Status:** Reference Documentation  
**Completeness:** 100%

"""Users and roles — locked 49.3, 42.2, 42.3, Step 47 §47.5, S-8, S-9, S-10.

This is the module where authority is created and destroyed, so all three of Step
47's escalation controls apply to every route:

* **S-8** — a user may not grant an authority they do not themselves hold.
* **S-9** — the guard covers editing and deleting a more-privileged account, not
  only granting to one. Without it, an administrator who cannot *grant*
  ``legal.decision`` could disable the account that holds it and reach the same
  outcome by another route.
* **SEC-05** — a change must never leave the system with no user able to make a
  Legal Decision, which would stall every Review requiring one (Step 31 r18,
  Step 30 r7).

Note what is *not* here: no route can confer legal authority implicitly. Granting
``PLATFORM_ADMIN`` grants no ``legal.*`` permission, because Step 23's locked role
summary gives the platform administrator none and the resolver has no bypass at
all. Nor does it grant any contract content: departments (AB-12 r3) are managed
here because they are ACCOUNT administration — which department a person is in —
and the administrator still cannot open a single deal in any of them (Step 24 r9).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    RoleCreate,
    RoleGrant,
    RoleUpdate,
    UserCreate,
    UserUpdate,
)
from legalmind.api.serializers import (
    UserContext,
    serialize_department,
    serialize_role,
    serialize_user,
)
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible
from legalmind.security.guards import (
    assert_administrative_authority_preserved,
    assert_legal_authority_preserved,
    count_administrative_authorities,
    count_legal_authorities,
    require_can_administer_user,
    require_can_grant_role,
)
from legalmind.security.resolver import effective_permissions
from legalmind.security.sessions import revoke_all_for_user

router = APIRouter(tags=["administration"])


# ==========================================================================
# Users
# ==========================================================================
#: Last successful authentication, as a scalar subquery so the list can order by
#: it. `user_identities.last_used_at` is stamped by both the password and OIDC
#: paths, so this is the real answer rather than a proxy for it.
def _last_login():
    return (select(func.max(M.UserIdentity.last_used_at))
            .where(M.UserIdentity.user_id == M.User.id)
            .correlate(M.User).scalar_subquery())


#: 49.6 — sorting is an ALLOW-LIST, exactly like filtering. An administrator may
#: order by these and nothing else, so a sort parameter can never become a probe
#: for a column the projection does not serve.
USER_SORTS = {
    "name_asc": lambda: (M.User.name.asc(), M.User.id.asc()),
    "name_desc": lambda: (M.User.name.desc(), M.User.id.desc()),
    "email_asc": lambda: (M.User.email.asc(), M.User.id.asc()),
    "email_desc": lambda: (M.User.email.desc(), M.User.id.desc()),
    "created_desc": lambda: (M.User.created_at.desc(), M.User.id.desc()),
    "created_asc": lambda: (M.User.created_at.asc(), M.User.id.asc()),
    # NULLS LAST so "never signed in" sorts to the end rather than masquerading
    # as the most recent login.
    "last_login_desc": lambda: (_last_login().desc().nullslast(), M.User.id.desc()),
}


@router.get("/users")
def list_users(guard: Guard = Depends(get_guard),
               page: Page = Depends(page_params),
               status: E.UserStatus | None = Query(default=None),
               search: str | None = Query(default=None, max_length=200),
               role: str | None = Query(default=None, max_length=100),
               department_id: UUID | None = Query(default=None),
               unassigned: bool = Query(default=False),
               sort: str = Query(default="name_asc")) -> dict:
    """The administration roster — 49.6's allow-listed filters and sorting.

    ``role`` and ``department_id`` are the two questions an administrator
    actually asks of this list ("who leads Sales?", "who is in no department?"),
    and both are answered in SQL rather than by filtering a page client-side —
    otherwise a filter would only ever see the 25 rows already on screen, which
    is the same class of defect the Dashboard's status filter had.

    ``unassigned`` is separate from ``department_id`` because "no department" is
    not a department id, and it matters: an account nobody has placed is invisible
    to every Department Lead, so finding those accounts is an administrative task
    in its own right.
    """
    guard.permission(P.USER_MANAGE)
    if sort not in USER_SORTS:
        raise BusinessRuleRejected(
            f"unknown sort {sort!r}; expected one of {sorted(USER_SORTS)}")
    stmt = select(M.User)
    if status is not None:
        stmt = stmt.where(M.User.status == status)
    if search:
        search_term = f"%{search.lower()}%"
        stmt = stmt.where(
            (M.User.email.ilike(search_term)) |
            (M.User.name.ilike(search_term))
        )
    if role:
        stmt = stmt.where(M.User.id.in_(
            select(M.UserRole.user_id)
            .join(M.Role, M.Role.id == M.UserRole.role_id)
            .where(M.Role.code == role.strip().upper())))
    if unassigned:
        stmt = stmt.where(M.User.department_id.is_(None))
    elif department_id is not None:
        stmt = stmt.where(M.User.department_id == department_id)

    rows, total = run(guard.db, stmt, page, *USER_SORTS[sort]())
    context = UserContext(guard.db, list(rows))
    return paginated(
        [serialize_user(guard.db, u, context=context) for u in rows],
        page=page.page, page_size=page.page_size, total=total)


@router.post("/users", status_code=201)
def create_user(body: UserCreate, guard: Guard = Depends(get_guard)) -> dict:
    """47.1.3 r3 — LegalMind never self-provisions an account.

    An account still holds **no roles unless one is named here**, and naming one
    is not a shortcut around anything: the grant runs the same `require_can_grant_role`
    (S-8) the standalone endpoint runs, and records the same audit events. What
    it removes is the three-step provisioning dance — create, then place, then
    grant — during which the account exists in a state nobody chose.

    A refusal at any step aborts the whole request: 43.26 puts the transaction
    around the request, so a half-provisioned account is not representable.
    """
    guard.permission(P.USER_MANAGE)
    email = body.email.strip().lower()
    if guard.db.execute(select(M.User.id).where(M.User.email == email)).first():
        raise Conflict("a user with that email already exists")

    department = None
    if body.department_id is not None:
        department = guard.db.get(M.Department, body.department_id)
        if department is None:
            raise BusinessRuleRejected("unknown department")

    role = None
    if body.role_code is not None:
        role = guard.db.execute(
            select(M.Role).where(M.Role.code == body.role_code.strip().upper())
        ).scalars().first()
        if role is None:
            raise BusinessRuleRejected(f"unknown role: {body.role_code}")
        # S-8 BEFORE the account exists, so a refusal leaves nothing behind.
        require_can_grant_role(guard.db, guard.user_id, role.id)

    user = M.User(email=email, name=body.name, status=E.UserStatus.ACTIVE,
                  department_id=department.id if department else None)
    guard.db.add(user)
    guard.db.flush()
    A.record(guard.db, action="admin.user_created", entity_type="user",
             entity_id=user.id, actor_id=guard.user_id,
             request_id=guard.request_id,
             after={"email": email,
                    "department_id": str(department.id) if department else None})
    if role is not None:
        guard.db.add(M.UserRole(user_id=user.id, role_id=role.id))
        guard.db.flush()
        _audit_role_change(guard, user.id, role, granted=True)
    return data(serialize_user(guard.db, user))


@router.get("/users/{user_id}")
def get_user(user_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.USER_MANAGE)
    user = guard.db.get(M.User, user_id)
    if user is None:
        raise NotVisible("user not found")
    return data(serialize_user(guard.db, user))


@router.patch("/users/{user_id}")
def update_user(user_id: UUID, body: UserUpdate,
                guard: Guard = Depends(get_guard)) -> dict:
    """Editing an account is covered by S-9, not only granting to one."""
    guard.permission(P.USER_MANAGE)
    user = guard.db.get(M.User, user_id)
    if user is None:
        raise NotVisible("user not found")
    require_can_administer_user(guard.db, guard.user_id, user_id)

    before = {"name": user.name, "status": user.status.value,
              "department_id": str(user.department_id) if user.department_id else None}
    authorities_before = count_legal_authorities(guard.db)
    admins_before = count_administrative_authorities(guard.db)
    if body.name is not None:
        user.name = body.name
    if body.status is not None:
        user.status = body.status
    if "department_id" in body.model_fields_set:
        # AB-12 r3 — placing someone in a department is what makes a Lead's
        # scope reach their deals, so it is an explicit, audited act. Null
        # removes them from every department.
        if (body.department_id is not None
                and guard.db.get(M.Department, body.department_id) is None):
            raise BusinessRuleRejected("unknown department")
        user.department_id = body.department_id
    user.updated_at = datetime.now(UTC)
    guard.db.flush()

    if body.status is not None and body.status is not E.UserStatus.ACTIVE:
        # SEC-05 counts only ACTIVE holders, so disabling the last one is refused
        # here rather than discovered later by a Review that cannot be resolved.
        assert_legal_authority_preserved(guard.db, authorities_before)
        assert_administrative_authority_preserved(guard.db, admins_before)
        # S-2 — revocation is immediate. A disabled account must not keep working
        # for the remainder of a live session.
        revoked = revoke_all_for_user(guard.db, user_id, reason="account disabled")
        A.record(guard.db, action=A.AUTH_SESSION_REVOKED, entity_type="user",
                 entity_id=user_id, actor_id=guard.user_id,
                 request_id=guard.request_id, after={"sessions_revoked": revoked})

    A.record(guard.db, action="admin.user_updated", entity_type="user",
             entity_id=user_id, actor_id=guard.user_id,
             request_id=guard.request_id, before=before,
             after={"name": user.name, "status": user.status.value,
                    "department_id": (str(user.department_id)
                                      if user.department_id else None)})
    return data(serialize_user(guard.db, user))


@router.delete("/users/{user_id}")
def delete_user(user_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Delete a user. Only DISABLED users can be deleted."""
    # S-9 covers deleting, not only editing: without the guard an administrator
    # who cannot *grant* `legal.decision` could delete the account holding it and
    # destroy that authority by another route. No authority-preservation check is
    # needed — only a DISABLED account is deletable, and neither count includes
    # non-ACTIVE users, so neither count can change here.
    guard.permission(P.USER_MANAGE)
    user = guard.db.get(M.User, user_id)
    if user is None:
        raise NotVisible("user not found")
    require_can_administer_user(guard.db, guard.user_id, user_id)   # S-9

    # Only allow deleting DISABLED users (soft delete protection)
    if user.status is not E.UserStatus.DISABLED:
        raise BusinessRuleRejected(
            "Only disabled users can be deleted. Disable the account first."
        )

    user_email = user.email
    guard.db.delete(user)
    guard.db.flush()
    A.record(guard.db, action="admin.user_deleted", entity_type="user",
             entity_id=user_id, actor_id=guard.user_id,
             request_id=guard.request_id, after={"email": user_email})
    return data({"deleted": True})


@router.post("/users/{user_id}/roles", status_code=201)
def grant_role(user_id: UUID, body: RoleGrant,
               guard: Guard = Depends(get_guard)) -> dict:
    """Multi-role with union semantics (47.3 / SEC-03).

    This is the mechanism locked Step 4 depends on: two users holding the same
    primary role differ in legal authority because one *additionally holds* a
    Legal Decision Authority role.
    """
    guard.permission(P.USER_MANAGE)
    user = guard.db.get(M.User, user_id)
    if user is None:
        raise NotVisible("user not found")
    role = guard.db.execute(
        select(M.Role).where(M.Role.code == body.role_code)
    ).scalars().first()
    if role is None:
        raise BusinessRuleRejected(f"unknown role: {body.role_code}")

    require_can_administer_user(guard.db, guard.user_id, user_id)   # S-9
    require_can_grant_role(guard.db, guard.user_id, role.id)        # S-8

    if guard.db.execute(
        select(M.UserRole).where(M.UserRole.user_id == user_id,
                                 M.UserRole.role_id == role.id)
    ).first() is None:
        guard.db.add(M.UserRole(user_id=user_id, role_id=role.id))
        guard.db.flush()

    _audit_role_change(guard, user_id, role, granted=True)
    return data(serialize_user(guard.db, user))


@router.delete("/users/{user_id}/roles/{role_code}")
def revoke_role(user_id: UUID, role_code: str,
                guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.USER_MANAGE)
    user = guard.db.get(M.User, user_id)
    if user is None:
        raise NotVisible("user not found")
    role = guard.db.execute(
        select(M.Role).where(M.Role.code == role_code)
    ).scalars().first()
    if role is None:
        raise BusinessRuleRejected(f"unknown role: {role_code}")

    require_can_administer_user(guard.db, guard.user_id, user_id)   # S-9

    link = guard.db.execute(
        select(M.UserRole).where(M.UserRole.user_id == user_id,
                                 M.UserRole.role_id == role.id)
    ).scalars().first()
    if link is not None:
        authorities_before = count_legal_authorities(guard.db)
        admins_before = count_administrative_authorities(guard.db)
        guard.db.delete(link)
        guard.db.flush()
        assert_legal_authority_preserved(guard.db, authorities_before)   # SEC-05
        assert_administrative_authority_preserved(guard.db, admins_before)
        _audit_role_change(guard, user_id, role, granted=False)
    return data(serialize_user(guard.db, user))


# ==========================================================================
# Roles
# ==========================================================================
@router.get("/roles")
def list_roles(guard: Guard = Depends(get_guard),
               page: Page = Depends(page_params)) -> dict:
    guard.permission(P.ROLE_MANAGE)
    rows, total = run(guard.db, select(M.Role), page, M.Role.code, M.Role.id)
    return paginated([serialize_role(guard.db, r) for r in rows],
                     page=page.page, page_size=page.page_size, total=total)


@router.get("/permissions")
def list_permissions(guard: Guard = Depends(get_guard)) -> dict:
    """The permission catalogue, grouped — SEC-04's eleven groups as the
    administrator sees them.

    `permissions.permission_group` has been stored since the catalogue was seeded
    and served nowhere, so the Roles screen had to render bare dotted strings and
    an administrator had to know that `legal.decision` is not like `report.view`.
    This is a read projection of data that already exists: no new permission, no
    new grant, and nothing that changes what any role may do.

    `confers_legal_authority` marks the two SEC-02/ROLE-05 permissions no bypass
    may ever reach, so a screen can separate them without hardcoding their names.
    Unpaginated by design: the catalogue is a fixed 30 rows, not a collection.
    """
    guard.permission(P.ROLE_MANAGE)
    described = {
        row.name: row.description
        for row in guard.db.execute(select(M.Permission)).scalars()
    }
    return data({
        "groups": [
            {
                "group": group,
                "permissions": [
                    {"name": name,
                     "description": described.get(name),
                     "confers_legal_authority": P.is_legal_authority(name)}
                    for name in names
                ],
            }
            for group, names in P.CATALOGUE.items()
        ],
    })


@router.post("/roles", status_code=201)
def create_role(body: RoleCreate, guard: Guard = Depends(get_guard)) -> dict:
    """A new role starts with **no permissions**. Granting them is a separate,
    S-8-guarded act."""
    guard.permission(P.ROLE_MANAGE)
    code = body.code.strip().upper()
    if guard.db.execute(select(M.Role.id).where(M.Role.code == code)).first():
        raise Conflict("a role with that code already exists")
    role = M.Role(code=code, name=body.name)
    guard.db.add(role)
    guard.db.flush()
    A.record(guard.db, action=A.ADMIN_PERMISSION_CHANGED, entity_type="role",
             entity_id=role.id, actor_id=guard.user_id,
             request_id=guard.request_id, after={"code": code, "permissions": []})
    return data(serialize_role(guard.db, role))


@router.patch("/roles/{role_id}")
def update_role(role_id: UUID, body: RoleUpdate,
                guard: Guard = Depends(get_guard)) -> dict:
    """Replace a role's permission set — S-10, locked 43.26.

    The replacement is transactional: the whole set changes or none of it does. The
    external reference's non-transactional delete-then-insert is rejected (C-EXT-7)
    because a failure between the two leaves a role with *no* permissions, which is
    a silent authority change.
    """
    guard.permission(P.ROLE_MANAGE)
    role = guard.db.get(M.Role, role_id)
    if role is None:
        raise NotVisible("role not found")

    before = serialize_role(guard.db, role)["permissions"]
    authorities_before = count_legal_authorities(guard.db)
    admins_before = count_administrative_authorities(guard.db)
    if body.name is not None:
        role.name = body.name

    if body.permissions is not None:
        requested = sorted(set(body.permissions))
        unknown = [p for p in requested if p not in P.ALL_PERMISSIONS]
        if unknown:
            raise BusinessRuleRejected(f"unknown permissions: {unknown}")

        # S-8 applied to permissions rather than roles: an administrator may not
        # construct a role granting an authority they do not hold themselves. This
        # is the route that would otherwise bypass require_can_grant_role.
        actor = effective_permissions(guard.db, guard.user_id)
        escalation = set(requested) - set(before) - actor
        if escalation:
            from legalmind.security.errors import Forbidden
            raise Forbidden(
                "escalation refused: cannot grant permissions the actor does "
                f"not hold: {sorted(escalation)}")

        rows = guard.db.execute(
            select(M.RolePermission).where(M.RolePermission.role_id == role_id)
        ).scalars().all()
        for row in rows:
            guard.db.delete(row)
        guard.db.flush()

        catalogue = {p.name: p.id for p in
                     guard.db.execute(select(M.Permission)).scalars()}
        for name in requested:
            guard.db.add(M.RolePermission(role_id=role_id,
                                          permission_id=catalogue[name]))
        guard.db.flush()
        assert_legal_authority_preserved(guard.db, authorities_before)   # SEC-05
        assert_administrative_authority_preserved(guard.db, admins_before)

    after = serialize_role(guard.db, role)["permissions"]
    A.record(guard.db, action=A.ADMIN_PERMISSION_CHANGED, entity_type="role",
             entity_id=role_id, actor_id=guard.user_id,
             request_id=guard.request_id,
             before={"permissions": before}, after={"permissions": after})
    return data(serialize_role(guard.db, role))


def _audit_role_change(guard: Guard, user_id: UUID, role: M.Role, *,
                       granted: bool) -> None:
    """47.9 — a legal-authority change gets its own action, distinct from an
    ordinary role change, so it is findable in the audit trail without knowing
    which role codes happen to carry ``legal.*``."""
    perms = set(serialize_role(guard.db, role)["permissions"])
    legal = bool(perms & P.LEGAL_AUTHORITY_PERMISSIONS)
    A.record(guard.db,
             action=(A.ADMIN_ROLE_GRANTED if granted else A.ADMIN_ROLE_REVOKED),
             entity_type="user", entity_id=user_id, actor_id=guard.user_id,
             request_id=guard.request_id, after={"role": role.code})
    if legal:
        A.record(guard.db,
                 action=(A.ADMIN_LEGAL_AUTHORITY_GRANTED if granted
                         else A.ADMIN_LEGAL_AUTHORITY_REVOKED),
                 entity_type="user", entity_id=user_id, actor_id=guard.user_id,
                 request_id=guard.request_id, after={"role": role.code})


# ==========================================================================
# Departments — AB-12 r3
# ==========================================================================
def _department_rollup(guard: Guard,
                       departments: list[M.Department]) -> dict[UUID, dict]:
    """Members, active members and leads per department — three grouped queries.

    "Lead" is DERIVED, never stored: it is whoever in the department holds
    `DEPARTMENT_LEAD`. There is deliberately no `departments.lead_id` column —
    that would be a second place for the same fact to live, and the two would
    eventually disagree about who can actually see the department's deals. The
    role assignment is what grants the scope, so the role assignment is the
    answer.

    A department may legitimately have no lead (nobody appointed yet) or more
    than one (cover during leave), so this is a list, not a single value.
    """
    ids = [d.id for d in departments]
    out: dict[UUID, dict] = {
        d.id: {"members": 0, "active_members": 0, "leads": []} for d in departments}
    if not ids:
        return out

    for department_id, status, count in guard.db.execute(
        select(M.User.department_id, M.User.status, func.count())
        .where(M.User.department_id.in_(ids))
        .group_by(M.User.department_id, M.User.status)
    ):
        entry = out[department_id]
        entry["members"] += count
        if status is E.UserStatus.ACTIVE:
            entry["active_members"] += count

    for department_id, name, email in guard.db.execute(
        select(M.User.department_id, M.User.name, M.User.email)
        .join(M.UserRole, M.UserRole.user_id == M.User.id)
        .join(M.Role, M.Role.id == M.UserRole.role_id)
        .where(M.User.department_id.in_(ids),
               M.Role.code == P.ROLE_DEPARTMENT_LEAD,
               M.User.status == E.UserStatus.ACTIVE)
        .order_by(M.User.name)
    ):
        out[department_id]["leads"].append({"name": name, "email": email})
    return out


@router.get("/departments")
def list_departments(guard: Guard = Depends(get_guard),
                     page: Page = Depends(page_params)) -> dict:
    """Departments with their lead and member counts.

    Counts only — never the deals. A department is a boundary around contract
    visibility, and listing it tells an administrator how many people it contains
    and who oversees them, which is account administration (Step 24 r9). It
    discloses nothing about what those people are working on.
    """
    guard.permission(P.USER_MANAGE)
    rows, total = run(guard.db, select(M.Department), page,
                      M.Department.name, M.Department.id)
    rollup = _department_rollup(guard, list(rows))
    return paginated(
        [{**serialize_department(d), **rollup[d.id]} for d in rows],
        page=page.page, page_size=page.page_size, total=total)


@router.get("/departments/{department_id}")
def get_department(department_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """One department, its rollup, and its members as accounts.

    The member list is the same account projection the user list serves — one
    place decides what an account looks like — and it is bounded by the
    department, so this is not a second unfiltered roster.
    """
    guard.permission(P.USER_MANAGE)
    department = guard.db.get(M.Department, department_id)
    if department is None:
        raise NotVisible("department not found")
    members = guard.db.execute(
        select(M.User).where(M.User.department_id == department_id)
        .order_by(M.User.name, M.User.id)
    ).scalars().all()
    context = UserContext(guard.db, list(members))
    rollup = _department_rollup(guard, [department])[department_id]
    return data({
        **serialize_department(department), **rollup,
        "member_accounts": [serialize_user(guard.db, u, context=context)
                            for u in members],
    })


@router.patch("/departments/{department_id}")
def update_department(department_id: UUID, body: DepartmentUpdate,
                      guard: Guard = Depends(get_guard)) -> dict:
    """Rename a department. The CODE is deliberately immutable.

    The name is a label; the code is the identifier an administrator recognises
    a boundary by, and it appears in audit rows that are append-only. Letting it
    change would make yesterday's trail read as if it referred to somewhere else.
    Membership is not edited here either — it is a property of each account and
    changes one audited act at a time through `PATCH /users/{id}`.
    """
    guard.permission(P.USER_MANAGE)
    department = guard.db.get(M.Department, department_id)
    if department is None:
        raise NotVisible("department not found")
    before = {"name": department.name}
    department.name = body.name.strip()
    guard.db.flush()
    A.record(guard.db, action=A.ADMIN_DEPARTMENT_UPDATED, entity_type="department",
             entity_id=department.id, actor_id=guard.user_id,
             request_id=guard.request_id, before=before,
             after={"name": department.name})
    rollup = _department_rollup(guard, [department])[department_id]
    return data({**serialize_department(department), **rollup})


@router.post("/departments", status_code=201)
def create_department(body: DepartmentCreate,
                      guard: Guard = Depends(get_guard)) -> dict:
    """A department is created empty. Membership is set per user through
    ``PATCH /users/{id}`` — one audited act per person, never a bulk move."""
    guard.permission(P.USER_MANAGE)
    code = body.code.strip().upper()
    if guard.db.execute(select(M.Department.id).where(M.Department.code == code)).first():
        raise Conflict("a department with that code already exists")
    department = M.Department(code=code, name=body.name.strip())
    guard.db.add(department)
    guard.db.flush()
    A.record(guard.db, action=A.ADMIN_DEPARTMENT_CREATED, entity_type="department",
             entity_id=department.id, actor_id=guard.user_id,
             request_id=guard.request_id, after={"code": code, "name": department.name})
    return data(serialize_department(department))


@router.get("/departments/mine/members")
def my_department_members(guard: Guard = Depends(get_guard)) -> dict:
    """Who a Department Lead may transfer a deal to: the ACTIVE accounts in the
    caller's OWN department, by id, name and email — nothing else about them.

    Gated on `department.view` rather than `user.manage`, because this is the
    Lead's screen, not the administrator's: a Lead is not an account
    administrator and must not need to become one to cover a colleague's leave.
    A caller in no department gets an empty list — never everyone (AB-12 r3).
    """
    guard.permission(P.DEPARTMENT_VIEW)
    if guard.department_id is None:
        return data({"department": None, "members": []})
    members = guard.db.execute(
        select(M.User)
        .where(M.User.department_id == guard.department_id,
               M.User.status == E.UserStatus.ACTIVE)
        .order_by(M.User.name, M.User.id)
    ).scalars().all()
    return data({
        "department": (serialize_department(department)
                       if (department := guard.db.get(M.Department, guard.department_id))
                       else None),
        "members": [{"id": str(u.id), "name": u.name, "email": u.email} for u in members],
    })

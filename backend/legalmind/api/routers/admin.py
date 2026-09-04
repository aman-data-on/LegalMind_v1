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
``SUPER_ADMIN`` grants no ``legal.*`` permission, because Step 23's locked role
summary gives Super Admin none and the resolver has no bypass at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import (
    RoleCreate,
    RoleGrant,
    RoleUpdate,
    UserCreate,
    UserUpdate,
)
from legalmind.api.serializers import serialize_role, serialize_user
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
@router.get("/users")
def list_users(guard: Guard = Depends(get_guard),
               page: Page = Depends(page_params),
               status: E.UserStatus | None = Query(default=None),
               search: str | None = Query(default=None)) -> dict:
    """List users with optional filtering by status and search by email/name."""
    guard.permission(P.USER_MANAGE)
    stmt = select(M.User)
    if status is not None:
        stmt = stmt.where(M.User.status == status)
    if search:
        search_term = f"%{search.lower()}%"
        stmt = stmt.where(
            (M.User.email.ilike(search_term)) |
            (M.User.name.ilike(search_term))
        )
    rows, total = run(guard.db, stmt, page, M.User.email, M.User.id)
    return paginated([serialize_user(guard.db, u) for u in rows],
                     page=page.page, page_size=page.page_size, total=total)


@router.post("/users", status_code=201)
def create_user(body: UserCreate, guard: Guard = Depends(get_guard)) -> dict:
    """47.1.3 r3 — LegalMind never self-provisions an account.

    The new account holds **no roles**. Authority is always a later, deliberate
    grant, never a side effect of creation.
    """
    guard.permission(P.USER_MANAGE)
    email = body.email.strip().lower()
    if guard.db.execute(select(M.User.id).where(M.User.email == email)).first():
        raise Conflict("a user with that email already exists")
    user = M.User(email=email, name=body.name, status=E.UserStatus.ACTIVE)
    guard.db.add(user)
    guard.db.flush()
    A.record(guard.db, action="admin.user_created", entity_type="user",
             entity_id=user.id, actor_id=guard.user_id,
             request_id=guard.request_id, after={"email": email})
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

    before = {"name": user.name, "status": user.status.value}
    authorities_before = count_legal_authorities(guard.db)
    admins_before = count_administrative_authorities(guard.db)
    if body.name is not None:
        user.name = body.name
    if body.status is not None:
        user.status = body.status
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
             after={"name": user.name, "status": user.status.value})
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

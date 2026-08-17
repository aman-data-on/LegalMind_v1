"""Permission resolution — Step 47 §47.2 / SEC-02, SEC-03.

Two rules govern this module:

1. **Authority is resolved fresh from the database on every request** (S-1).
   Nothing about what a user MAY DO is ever carried in a session or token. A
   permission revoked mid-session takes effect on the very next request.

2. **There is no bypass.** Locked Step 23 says Super Admin has "No automatic
   Legal Decision authority"; locked Step 24 r8 says Super Admin "does not
   automatically have access to confidential contract or Legal content".

   Step 47/SEC-02 permits a bypass for administrative permissions provided it
   excludes ``legal.*``. V1 implements NO bypass at all: every permission is an
   explicit grant. With a 27-permission catalogue the convenience a bypass buys
   is negligible, and removing it eliminates the single most dangerous control
   path — the one the external MoS reference got wrong (its ``is_super``
   "returns true immediately without consulting grants at all").

   ``assert_no_bypass_reaches_legal_authority`` remains as defence in depth so
   that if a bypass is ever introduced, it cannot reach legal authority.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.security import permissions as P


def effective_permissions(db: DBSession, user_id: UUID) -> frozenset[str]:
    """Union of every permission granted by every role the user holds (SEC-03).

    Resolved fresh; never cached across requests.
    """
    rows = db.execute(
        select(M.Permission.name)
        .join(M.RolePermission, M.RolePermission.permission_id == M.Permission.id)
        .join(M.UserRole, M.UserRole.role_id == M.RolePermission.role_id)
        .where(M.UserRole.user_id == user_id)
    ).scalars().all()
    return frozenset(rows)


def has_permission(db: DBSession, user_id: UUID, permission: str) -> bool:
    """Single-permission check. No bypass path exists."""
    granted = effective_permissions(db, user_id)
    if P.is_legal_authority(permission):
        # Defence in depth: legal authority is ONLY ever an explicit grant.
        return permission in granted
    return permission in granted


def require_permission(db: DBSession, user_id: UUID, permission: str) -> None:
    from legalmind.security.errors import Forbidden

    if not has_permission(db, user_id, permission):
        raise Forbidden(f"missing permission: {permission}")


def holds_legal_decision_authority(db: DBSession, user_id: UUID) -> bool:
    """SEC-05. Note that ``legal.review`` does NOT confer this."""
    return has_permission(db, user_id, P.LEGAL_DECISION)


def assert_no_bypass_reaches_legal_authority(bypass_permissions: set[str]) -> None:
    """Guard for any future bypass implementation (SEC-02).

    If someone later adds a role-level or wildcard bypass, routing its permission
    set through here makes the locked exclusion unavoidable.
    """
    leaked = set(bypass_permissions) & P.LEGAL_AUTHORITY_PERMISSIONS
    if leaked:
        raise AssertionError(
            "SEC-02 violated: a bypass would confer legal authority "
            f"{sorted(leaked)}. Locked Step 23: Super Admin has no automatic "
            "Legal Decision authority."
        )

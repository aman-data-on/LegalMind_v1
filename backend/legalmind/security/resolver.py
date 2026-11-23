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
   explicit grant. With a 30-permission catalogue the convenience a bypass buys
   is negligible, and removing it eliminates the single most dangerous control
   path — the one the external MoS reference got wrong (its ``is_super``
   "returns true immediately without consulting grants at all").

   ``assert_no_bypass_reaches_legal_authority`` remains as defence in depth so
   that if a bypass is ever introduced, it cannot reach legal authority.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import TextClause, event, select
from sqlalchemy.orm import ORMExecuteState
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.security import permissions as P

#: The tables a user's authority is read from. A write to any of them empties the memo.
#: ``User``: deleting one cascades its ``user_roles`` in Postgres, past the ORM.
_GRANT_TABLES = (M.Permission, M.Role, M.RolePermission, M.UserRole, M.User)

#: user id -> permissions, for ONE request (BE-7, 2026-11-23: the same user was resolved
#: 7-9 times per request). Set only by `request_memo` around a request, so a worker, a
#: script or a test calling in directly resolves fresh every time, exactly as before.
_MEMO: ContextVar[dict[UUID, frozenset[str]] | None] = ContextVar("permission_memo",
                                                                 default=None)


@contextmanager
def request_memo() -> Iterator[None]:
    """Memoise `effective_permissions` for the life of one request — never across
    requests (S-1), never across users (keyed by user id)."""
    token = _MEMO.set({})
    try:
        yield
    finally:
        _MEMO.reset(token)


def _grants_pending(db: DBSession) -> bool:
    return any(isinstance(o, _GRANT_TABLES) for o in (*db.new, *db.dirty, *db.deleted))


@event.listens_for(DBSession, "after_flush")
def _forget_on_grant_flush(db: DBSession, _ctx: object) -> None:
    memo = _MEMO.get()
    if memo and _grants_pending(db):      # pre-flush state is still visible here
        memo.clear()


@event.listens_for(DBSession, "after_soft_rollback")
def _forget_on_rollback(_db: DBSession, _tx: object) -> None:
    """A rolled-back grant write (savepoint or whole) must not live on in the memo."""
    memo = _MEMO.get()
    if memo:
        memo.clear()


@event.listens_for(DBSession, "do_orm_execute")
def _forget_on_bulk_write(state: ORMExecuteState) -> None:
    """A bulk ``delete``/``update``/``insert`` (the user erasure deletes ``user_roles``
    this way) or raw SQL through ``Session.execute`` bypasses the flush: anything but a
    read forgets everything."""
    memo = _MEMO.get()
    if memo and not (state.is_select or _raw_select(state.statement)):
        memo.clear()


def _raw_select(statement: object) -> bool:
    return (isinstance(statement, TextClause)
            and statement.text.lstrip().upper().startswith("SELECT"))


def effective_permissions(db: DBSession, user_id: UUID) -> frozenset[str]:
    """Union of every permission granted by every role the user holds (SEC-03).

    Resolved fresh for every request; within one request, memoised (`request_memo`)
    until the request writes a grant table.
    """
    memo = _MEMO.get()
    if memo is not None and user_id in memo and not _grants_pending(db):
        return memo[user_id]
    rows = db.execute(
        select(M.Permission.name)
        .join(M.RolePermission, M.RolePermission.permission_id == M.Permission.id)
        .join(M.UserRole, M.UserRole.role_id == M.RolePermission.role_id)
        .where(M.UserRole.user_id == user_id)
    ).scalars().all()
    granted = frozenset(rows)
    if memo is not None:
        memo[user_id] = granted
    return granted


def role_permissions(db: DBSession, role_id: UUID) -> frozenset[str]:
    """Every permission one role grants — what S-8 compares and what the OIDC
    provisioning whitelist inspects (AB-12 r11)."""
    rows = db.execute(
        select(M.Permission.name)
        .join(M.RolePermission, M.RolePermission.permission_id == M.Permission.id)
        .where(M.RolePermission.role_id == role_id)
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

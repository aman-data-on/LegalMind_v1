"""Session lifecycle — Step 47 §47.1 / SEC-01 (OD-9).

Server-side sessions. The stateless-JWT model is rejected: a system holding
confidential legal strategy under append-only audit must be able to terminate a
session on demand — after a role change, a departure or a suspected compromise.

The session carries IDENTITY ONLY. Authority is resolved per request (S-1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security.errors import Unauthenticated

SESSION_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True)
class Principal:
    """The authenticated principal. Deliberately carries no authority."""

    user_id: UUID
    session_id: UUID
    authenticated_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(db: DBSession, user: M.User,
                   lifetime: timedelta = SESSION_LIFETIME) -> M.UserSession:
    """Establish a session for an already-authenticated user.

    Status gating applies to EVERY authentication route (Step 47 §47.1.3): a
    disabled or suspended account cannot obtain a session by any mechanism.
    """
    if user.status is not E.UserStatus.ACTIVE:
        raise Unauthenticated("account is not active")
    s = M.UserSession(user_id=user.id, expires_at=_now() + lifetime)
    db.add(s)
    db.flush()
    return s


def resolve_session(db: DBSession, session_id: UUID) -> Principal:
    """Validate a session id and return the principal.

    A revoked, expired or unknown session is indistinguishable from being
    signed out — never an error that discloses account state (S-7).
    """
    s = db.get(M.UserSession, session_id)
    if s is None or s.revoked_at is not None or s.expires_at <= _now():
        raise Unauthenticated("no valid session")
    s.last_seen_at = _now()
    return Principal(user_id=s.user_id, session_id=s.id, authenticated_at=s.created_at)


def revoke_session(db: DBSession, session_id: UUID, reason: str) -> None:
    """Immediate server-side revocation (SEC-01)."""
    s = db.get(M.UserSession, session_id)
    if s is None or s.revoked_at is not None:
        return
    s.revoked_at = _now()
    s.revoked_reason = reason
    db.flush()


def revoke_all_for_user(db: DBSession, user_id: UUID, reason: str) -> int:
    """Used when authority changes or an account is disabled."""
    sessions = db.execute(
        select(M.UserSession).where(
            M.UserSession.user_id == user_id,
            M.UserSession.revoked_at.is_(None),
        )
    ).scalars().all()
    for s in sessions:
        s.revoked_at = _now()
        s.revoked_reason = reason
    db.flush()
    return len(sessions)

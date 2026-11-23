"""Session lifecycle — Step 47 §47.1 / SEC-01 (OD-9).

Server-side sessions. The stateless-JWT model is rejected: a system holding
confidential legal strategy under append-only audit must be able to terminate a
session on demand — after a role change, a departure or a suspected compromise.

The session carries IDENTITY ONLY. Authority is resolved per request (S-1).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import inf
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.security.errors import Unauthenticated

SESSION_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True)
class Principal:
    """The authenticated principal. Deliberately carries no authority."""

    user_id: UUID
    session_id: UUID
    authenticated_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


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
    _stamp_last_seen(db, session_id)
    s = db.get(M.UserSession, session_id)
    if s is None or s.revoked_at is not None or s.expires_at <= _now():
        raise Unauthenticated("no valid session")
    return Principal(user_id=s.user_id, session_id=s.id, authenticated_at=s.created_at)


#: How stale ``last_seen_at`` may get. Nothing reads it to the second (full-stack audit
#: BE-1, 2026-11-23: no reader at all); Step 47 §47.1.2 defines the column only.
LAST_SEEN_EVERY = timedelta(minutes=1)
_asked: dict[UUID, float] = {}     # session id -> when this process last stamped it


def _stamp_last_seen(db: DBSession, session_id: UUID) -> None:
    """Move ``last_seen_at`` at most once a minute, in its OWN transaction committed at
    once — never in the request's. Written inside the request's transaction, the row
    lock was held for the whole request, so one user's parallel requests ran one at a
    time (BE-1: ``/auth/session`` 37 ms alone, 1.5 s beside ``/contracts``).

    Runs BEFORE the request reads anything, so the request never holds a pooled
    connection while waiting for this one. ``SKIP LOCKED``: if anyone holds the row
    (a logout or revocation in flight) the stamp is skipped, never waited for. Only a
    live session is stamped; validity is still decided by the fresh read after this.
    This process asks at most once a minute per session, so most requests pay nothing.
    """
    now = time.monotonic()
    if now - _asked.get(session_id, -inf) < LAST_SEEN_EVERY.total_seconds():
        return
    if len(_asked) > 10_000:      # ponytail: crude bound; sessions live 12 h
        _asked.clear()
    _asked[session_id] = now
    S = M.UserSession
    live = (select(S.id)
            .where(S.id == session_id, S.revoked_at.is_(None), S.expires_at > func.now(),
                   S.last_seen_at < func.now() - LAST_SEEN_EVERY)
            .with_for_update(skip_locked=True).scalar_subquery())
    try:                    # bookkeeping: a failed stamp never fails the request
        with db.get_bind().engine.begin() as conn:
            conn.execute(update(S).where(S.id == live).values(last_seen_at=func.now()))
    except SQLAlchemyError as exc:    # _asked stays set: no retry storm
        log_event("session.stamp_failed", level=logging.WARNING, error=type(exc).__name__)


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

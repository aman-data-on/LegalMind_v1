"""Session lifecycle and auth events — Step 47 §47.1, §47.9 / SEC-01, SEC-09."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security.errors import Unauthenticated
from legalmind.security.sessions import (
    create_session,
    resolve_session,
    revoke_all_for_user,
    revoke_session,
)
from tests.conftest import make_user


def test_session_carries_identity_only(db):
    """SEC-01 — the session establishes identity, never authority.

    Guards against the drift that would let a token carry grants; the Principal
    dataclass has no permission field at all.
    """
    u = make_user(db)
    s = create_session(db, u)
    p = resolve_session(db, s.id)
    assert p.user_id == u.id
    assert set(vars(p)) == {"user_id", "session_id", "authenticated_at"}
    assert not hasattr(p, "permissions")
    assert not hasattr(p, "roles")


def test_revocation_is_immediate(db):
    """SEC-01 / S-2 — a revoked session fails on the very next request."""
    u = make_user(db)
    s = create_session(db, u)
    assert resolve_session(db, s.id).user_id == u.id

    revoke_session(db, s.id, reason="role_change")
    with pytest.raises(Unauthenticated):
        resolve_session(db, s.id)


def test_expired_session_is_rejected(db):
    u = make_user(db)
    s = create_session(db, u, lifetime=timedelta(seconds=-1))
    with pytest.raises(Unauthenticated):
        resolve_session(db, s.id)


def test_unknown_session_is_indistinguishable_from_signed_out(db):
    """S-7 — never an error that discloses account state."""
    u = make_user(db)
    revoked = create_session(db, u)
    revoke_session(db, revoked.id, reason="logout")

    errors = []
    for sid in (uuid.uuid4(), revoked.id):
        with pytest.raises(Unauthenticated) as e:
            resolve_session(db, sid)
        errors.append(e.value)
    assert {type(e) for e in errors} == {Unauthenticated}
    assert {e.status_code for e in errors} == {401}
    assert len({str(e) for e in errors}) == 1      # identical message


@pytest.mark.parametrize("status", [E.UserStatus.DISABLED, E.UserStatus.SUSPENDED])
def test_inactive_account_cannot_obtain_a_session(db, status):
    """Step 47 §47.1.3 — status gating applies to EVERY authentication route,
    so a disabled account cannot authenticate by OIDC or by password."""
    u = make_user(db, status=status)
    with pytest.raises(Unauthenticated):
        create_session(db, u)


def test_revoke_all_sessions_for_user(db):
    """Used when authority changes or an account is disabled."""
    u = make_user(db)
    sessions = [create_session(db, u) for _ in range(3)]
    assert revoke_all_for_user(db, u.id, reason="account_disabled") == 3
    for s in sessions:
        with pytest.raises(Unauthenticated):
            resolve_session(db, s.id)


def test_sessions_are_per_user(db):
    a, b = make_user(db), make_user(db)
    sa, sb = create_session(db, a), create_session(db, b)
    revoke_all_for_user(db, a.id, reason="x")
    with pytest.raises(Unauthenticated):
        resolve_session(db, sa.id)
    assert resolve_session(db, sb.id).user_id == b.id    # unaffected


# ------------------------------------------------------------------ identities
def test_oidc_subject_is_unique_across_users(db):
    """Step 47 — UNIQUE(provider, provider_subject): one OIDC subject cannot
    map to two LegalMind accounts."""
    from sqlalchemy.exc import IntegrityError
    a, b = make_user(db), make_user(db)
    sub = "oidc-subject-123"
    db.add(M.UserIdentity(user_id=a.id, provider=E.IdentityProvider.OIDC,
                          provider_subject=sub))
    db.flush()
    db.add(M.UserIdentity(user_id=b.id, provider=E.IdentityProvider.OIDC,
                          provider_subject=sub))
    with pytest.raises(IntegrityError):
        db.flush()


def test_user_may_hold_both_oidc_and_password_identities(db):
    """OD-9 — OIDC primary with a controlled password fallback."""
    u = make_user(db)
    db.add(M.UserIdentity(user_id=u.id, provider=E.IdentityProvider.OIDC,
                          provider_subject="sub-1"))
    db.add(M.UserIdentity(user_id=u.id, provider=E.IdentityProvider.PASSWORD,
                          credential_hash="$argon2id$fake"))
    db.flush()
    rows = db.execute(select(M.UserIdentity)
                      .where(M.UserIdentity.user_id == u.id)).scalars().all()
    assert {r.provider for r in rows} == {E.IdentityProvider.OIDC,
                                         E.IdentityProvider.PASSWORD}


def test_one_identity_per_provider_per_user(db):
    from sqlalchemy.exc import IntegrityError
    u = make_user(db)
    db.add(M.UserIdentity(user_id=u.id, provider=E.IdentityProvider.PASSWORD,
                          credential_hash="a"))
    db.flush()
    db.add(M.UserIdentity(user_id=u.id, provider=E.IdentityProvider.PASSWORD,
                          credential_hash="b"))
    with pytest.raises(IntegrityError):
        db.flush()


# ------------------------------------------------------------- audit of auth
def test_auth_events_recorded_in_locked_audit_table(db):
    """SEC-09 — no new audit table; 42.18 accommodates these directly."""
    u = make_user(db)
    s = create_session(db, u)
    ev = A.record(db, action=A.AUTH_LOGIN_SUCCEEDED, entity_type="session",
                  entity_id=s.id, actor_id=u.id, request_id="req-42")
    assert ev.event_metadata["request_id"] == "req-42"     # correlation (49.9)


def test_failed_login_for_unknown_account_has_no_actor(db):
    """Step 47 — actor_id nullable for pre-authentication events."""
    ev = A.record(db, action=A.AUTH_LOGIN_FAILED,
                  entity_type="authentication", request_id="req-43")
    assert ev.actor_id is None


def test_auth_events_cannot_be_rewritten(db):
    """AUD-01 — enforced by trigger, so no code path can revise auth history."""
    from sqlalchemy.exc import DBAPIError
    u = make_user(db)
    ev = A.record(db, action=A.AUTH_LOGIN_FAILED, entity_type="authentication",
                  actor_id=u.id)
    sp = db.begin_nested()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_events SET action='auth.login_succeeded' "
                        "WHERE id=:i"), {"i": ev.id})
    sp.rollback()


def test_no_credential_material_in_audit_metadata(db):
    """S-4 / 53.3 — audit rows carry identifiers, not secrets.

    A structural check on the recorder's own contract: it accepts only a
    request_id, so there is no parameter through which a credential, session
    token or OIDC code could be recorded.
    """
    import inspect
    sig = inspect.signature(A.record)
    forbidden = {"password", "credential", "credential_hash", "token",
                 "session_token", "code", "secret"}
    assert not (set(sig.parameters) & forbidden)


# =====================================================================
# BE-1 (2026-11-23) — last_seen_at never holds the session row for a request
# =====================================================================
@pytest.fixture
def committed_session(engine):
    """A real, COMMITTED session row, last seen five minutes ago: a row lock is only
    visible across connections, which the per-test transaction cannot show."""
    from sqlalchemy.orm import Session
    with Session(engine) as s:
        u = M.User(email=f"p1-{uuid.uuid4().hex[:8]}@example.test", name="P1",
                   status=E.UserStatus.ACTIVE)
        s.add(u); s.flush()
        row = create_session(s, u)
        row.last_seen_at = row.created_at - timedelta(minutes=5)
        s.commit()
        ids = (u.id, row.id)
    yield ids[1]
    with engine.begin() as c:
        c.execute(M.UserSession.__table__.delete().where(M.UserSession.id == ids[1]))
        c.execute(M.User.__table__.delete().where(M.User.id == ids[0]))


def _last_seen(engine, sid):
    with engine.connect() as c:
        return c.execute(select(M.UserSession.last_seen_at)
                         .where(M.UserSession.id == sid)).scalar_one()


def test_a_request_never_holds_its_session_row(engine, committed_session):
    """Two requests on one session ran one at a time: the first held the row from its
    `last_seen_at` write until it committed (1.5 s waits behind `/contracts`). Now the
    stamp commits on its own and the request's transaction locks nothing."""
    from sqlalchemy.orm import Session
    before = _last_seen(engine, committed_session)
    with Session(engine) as request_a:
        resolve_session(request_a, committed_session)
        request_a.flush()                     # what the handler's first query autoflushes
        with engine.connect() as request_b:   # would raise LockNotAvailable if held
            request_b.execute(text("SET LOCAL lock_timeout = '200ms'"))
            request_b.execute(select(M.UserSession.id).where(
                M.UserSession.id == committed_session).with_for_update(nowait=True))
        stamped = _last_seen(engine, committed_session)
        assert stamped > before               # committed already, outside request A
    with Session(engine) as again:            # within the minute: no second write
        resolve_session(again, committed_session)
    assert _last_seen(engine, committed_session) == stamped


def test_a_held_session_row_is_skipped_never_waited_for(engine, committed_session):
    import time

    from sqlalchemy.orm import Session
    before = _last_seen(engine, committed_session)
    with engine.connect() as holder:
        holder.execute(select(M.UserSession.id).where(
            M.UserSession.id == committed_session).with_for_update())
        started = time.monotonic()
        with Session(engine) as request:
            assert resolve_session(request, committed_session).session_id == committed_session
        assert time.monotonic() - started < 1.0
    assert _last_seen(engine, committed_session) == before


def test_a_revoked_stale_session_still_fails_and_is_not_stamped(engine, committed_session):
    from sqlalchemy.orm import Session
    with Session(engine) as s:
        revoke_session(s, committed_session, reason="logout")
        s.commit()
    before = _last_seen(engine, committed_session)
    with Session(engine) as request, pytest.raises(Unauthenticated):
        resolve_session(request, committed_session)
    assert _last_seen(engine, committed_session) == before


def test_a_failed_last_seen_stamp_never_fails_the_request(db, monkeypatch):
    """The stamp is bookkeeping: a database error writing it is logged, never raised,
    and the session still resolves (verifier D2, 2026-11-23)."""
    from sqlalchemy.exc import OperationalError

    from legalmind.security import sessions

    class _Boom:
        def __enter__(self):
            raise OperationalError("stamp", {}, Exception("pool gone"))

        def __exit__(self, *a):
            return False

    sid = uuid.uuid4()
    monkeypatch.setattr(sessions, "_asked", {})
    monkeypatch.setattr(type(db.get_bind().engine), "begin", lambda self: _Boom())
    sessions._stamp_last_seen(db, sid)              # must not raise
    assert sid in sessions._asked                   # no retry storm

"""Authentication endpoints — locked 49.2, Step 47 §47.1, SEC-01.

Locked 47.1.3 (OD-9): corporate SSO via OIDC is primary, password login is a
controlled fallback, sessions are server-side and carry identity only, and **the
authentication mechanism never confers Legal Decision authority**. Nothing in this
module touches a role, a permission or a grant — the two concerns meet only at
``user_id``.

**The OIDC routes (49.2 lines 1–2) are not registered.** They need a JWT/JWKS
client library, which is a dependency requiring approval (rule 19), plus the
deployment's issuer, client id and secret. Both are reported gaps; see
``permission_map.NOT_IMPLEMENTED``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.api import ratelimit
from legalmind.api.context import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    new_csrf_token,
    request_id_of,
)
from legalmind.api.deps import Guard, get_db, get_guard, get_principal
from legalmind.api.envelope import data
from legalmind.api.serializers import serialize_session_identity
from legalmind.api.schemas import LoginRequest
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import Unauthenticated
from legalmind.security.guards import require_can_administer_user
from legalmind.security.passwords import verify_password
from legalmind.security.sessions import (
    Principal,
    create_session,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Module-level so a deployment can swap it for the Redis-backed limiter without
# touching a route (see ratelimit.InProcessRateLimiter's docstring).
limiter: ratelimit.RateLimiter = ratelimit.InProcessRateLimiter()

# S-3 — the session cookie is HttpOnly so script cannot read it; the CSRF cookie
# deliberately is not, because our own script must echo it in a header.
_COOKIE_KW = dict(secure=True, samesite="strict", path="/")


def _set_session_cookies(response: Response, session_id: UUID,
                         max_age: int) -> None:
    response.set_cookie(SESSION_COOKIE, str(session_id), httponly=True,
                        max_age=max_age, **_COOKIE_KW)
    response.set_cookie(CSRF_COOKIE, new_csrf_token(), httponly=False,
                        max_age=max_age, **_COOKIE_KW)


@router.post("/login")
def login(request: Request, response: Response, body: LoginRequest,
          db: DBSession = Depends(get_db)) -> dict:
    """Fallback password authentication.

    S-7 — an unknown account, a wrong credential and a disabled account produce
    **the same response**. That is enforced structurally: every failure path
    raises the same ``Unauthenticated``, whose handler renders one fixed body, and
    an unknown account still pays for a scrypt verification so timing does not
    distinguish it either.
    """
    # S-5 / 49.10 — keyed on the client address rather than the submitted email,
    # so an attacker cannot lock a named user out by failing their login.
    client = request.client.host if request.client else "unknown"
    limiter.check(f"login:{client}", ratelimit.LOGIN)

    rid = request_id_of(request)
    user = db.execute(
        select(M.User).where(M.User.email == body.email.strip().lower())
    ).scalars().first()

    identity = None
    if user is not None:
        # S-4 — credential_hash is selected here and by no other query.
        identity = db.execute(
            select(M.UserIdentity).where(
                M.UserIdentity.user_id == user.id,
                M.UserIdentity.provider == E.IdentityProvider.PASSWORD)
        ).scalars().first()

    ok = verify_password(body.password,
                         identity.credential_hash if identity else None)

    if user is None or identity is None or not ok:
        # 47.9 — actor_id is NULL when the account is unknown, which is why 42.18
        # makes it nullable. The submitted email is NOT recorded: a surfaced audit
        # view must not become an enumeration oracle.
        A.record(db, action=A.AUTH_LOGIN_FAILED, entity_type="authentication",
                 actor_id=user.id if user else None, request_id=rid)
        db.commit()          # the request is about to abort; the event must survive
        raise Unauthenticated("authentication failed")

    if user.status is not E.UserStatus.ACTIVE:
        # 47.1.3 — status gating applies to every mechanism, and the refusal is
        # indistinguishable from a wrong credential.
        A.record(db, action=A.AUTH_LOGIN_FAILED, entity_type="authentication",
                 actor_id=user.id, request_id=rid)
        db.commit()
        raise Unauthenticated("authentication failed")

    session = create_session(db, user)
    identity.last_used_at = session.created_at
    A.record(db, action=A.AUTH_LOGIN_SUCCEEDED, entity_type="session",
             entity_id=session.id, actor_id=user.id, request_id=rid)

    max_age = int((session.expires_at - session.created_at).total_seconds())
    _set_session_cookies(response, session.id, max_age)
    # The response body carries identity and the presentation-only permission
    # array (43.31); the session id itself travels only in the HttpOnly cookie.
    return data(serialize_session_identity(db, user))


@router.get("/session")
def current_session(db: DBSession = Depends(get_db),
                    principal: Principal = Depends(get_principal)) -> dict:
    """49.2 — the caller's identity plus their **effective permission names**.

    A convenience projection for presentation gating only (43.31, 47.6 r3).
    Resolved fresh from the database here, not read from the session (S-1), so it
    can never be staler than the checks that actually enforce anything.
    """
    user = db.get(M.User, principal.user_id)
    if user is None:                                    # pragma: no cover
        raise Unauthenticated("no valid session")
    return data({
        **serialize_session_identity(db, user),
        "session_id": str(principal.session_id),
        "authenticated_at": principal.authenticated_at.isoformat(),
    })


@router.post("/logout")
def logout(request: Request, response: Response,
           db: DBSession = Depends(get_db),
           principal: Principal = Depends(get_principal)) -> dict:
    revoke_session(db, principal.session_id, reason="logout")
    A.record(db, action=A.AUTH_LOGOUT, entity_type="session",
             entity_id=principal.session_id, actor_id=principal.user_id,
             request_id=request_id_of(request))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return data({"revoked": True})


@router.delete("/sessions/{session_id}")
def revoke(session_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Immediate server-side revocation (SEC-01, S-2).

    Returns the same body whether or not the session existed: a session id is an
    opaque identifier and confirming one exists would disclose that its owner is
    signed in.
    """
    guard.permission(P.USER_MANAGE)
    session = guard.db.get(M.UserSession, session_id)
    if session is not None:
        # S-9 — the escalation guard covers acting ON a more-privileged account,
        # not only granting to one. Terminating a Legal Decision Authority's
        # session is acting on that account.
        require_can_administer_user(guard.db, guard.user_id, session.user_id)
        revoke_session(guard.db, session_id, reason="revoked by administrator")
        A.record(guard.db, action=A.AUTH_SESSION_REVOKED, entity_type="session",
                 entity_id=session_id, actor_id=guard.user_id,
                 request_id=guard.request_id)
    return data({"revoked": True})

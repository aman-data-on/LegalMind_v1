"""Authentication endpoints — locked 49.2, Step 47 §47.1, SEC-01.

Locked 47.1.3 (OD-9): corporate SSO via OIDC is primary, password login is a
controlled fallback, sessions are server-side and carry identity only, and **the
authentication mechanism never confers Legal Decision authority**. Nothing in this
module touches a role, a permission or a grant — the two concerns meet only at
``user_id``.

**The OIDC routes (49.2 lines 1–2) are registered as of 2026-09-01.** They need no
new dependency — see ``security/oidc.py``'s module docstring for why no JWT/JWKS
client library is required — but they DO need the deployment's issuer, client id,
secret and redirect URI. Absent those, both routes refuse in exactly the way an
unconfigured mechanism should: they behave as if sign-in failed, and the reason
reaches the operator log only.
"""

from __future__ import annotations

import logging
from typing import Literal, TypedDict
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.api import ratelimit
from legalmind.api.context import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    new_csrf_token,
    request_id_of,
)
from legalmind.api.deps import Guard, get_db, get_guard, get_principal
from legalmind.api.envelope import data
from legalmind.api.schemas import LoginRequest
from legalmind.api.serializers import serialize_session_identity
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.security import audit as A
from legalmind.security import oidc, tokens
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
#
# A `TypedDict` rather than `dict[str, object]`: these are the locked S-3 attributes,
# and typing them means a change that weakened `secure` or mistyped `samesite` fails
# the typecheck instead of only the preflight. The `Literal` on `samesite` is the
# load-bearing part — "Strict" or a typo would silently become a laxer cookie.
class _CookieKeywords(TypedDict):
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str


# ⚠️ RESTORED to "strict" on 2026-09-01. It had been changed to "lax" so that a
# plain 302 from the OIDC callback would carry the session cookie — a real
# problem, solved the wrong way: `samesite` here governs EVERY session cookie in
# the application, including password login, so the whole app's CSRF posture was
# relaxed to fix one redirect. Locked OD-9 / S-3 fixes these attributes precisely
# so a deployment cannot weaken them by accident, and `AM-36` t6 restates it.
#
# The redirect problem is solved instead by `_same_site_landing`, which lands the
# browser on our own origin first so the follow-up navigation is same-site. See
# that function for how the back-button issue is handled without this trade.
_COOKIE_KW: _CookieKeywords = {
    "secure": True,
    "samesite": "strict",
    "path": "/",
}


def _signal_auth_failure(client: str, request_id: str) -> None:
    """Locked 53.5 — "authentication failures … security posture (S-5, S-7)".

    Named as a signal so a spike is detectable, and deliberately **without the
    submitted email**: 53.3's fourth prohibition is "anything that turns a
    failed-login record into an enumeration oracle", and a searchable log index is
    exactly such a surface. The source address is carried instead, which is what makes
    a spike attributable and is already what S-5's limiter keys on. `email` is a
    forbidden key in the redactor besides, so passing one would be dropped.
    """
    log_event("auth.login_failed", level=logging.WARNING, request_id=request_id,
              client=client, signal="auth.failure_count")


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
        _signal_auth_failure(client, rid)
        db.commit()          # the request is about to abort; the event must survive
        raise Unauthenticated("authentication failed")

    if user.status is not E.UserStatus.ACTIVE:
        # 47.1.3 — status gating applies to every mechanism, and the refusal is
        # indistinguishable from a wrong credential.
        A.record(db, action=A.AUTH_LOGIN_FAILED, entity_type="authentication",
                 actor_id=user.id, request_id=rid)
        _signal_auth_failure(client, rid)
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
    # `AM-36` t4 — the token cannot be revoked server-side, so clearing it from the
    # browser is the only thing logout CAN do about it, and not doing it would
    # leave a live 24-hour credential behind after an explicit sign-out.
    response.delete_cookie(tokens.TOKEN_COOKIE, path="/")
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


# ==========================================================================
# OIDC — locked 49.2 lines 1–2, Step 47 §47.1.3 (OD-9)
# ==========================================================================
# Locked 47.1.3 makes corporate SSO the PRIMARY mechanism; the password route
# above stays as its "controlled fallback". The provider mechanics live in
# ``security/oidc.py``; what is here is the HTTP shape and the session hand-off.
#
# Both routes are GET top-level navigations, so neither is subject to the CSRF
# middleware (which covers unsafe methods only). The flow's own CSRF defence is
# the ``state`` parameter, checked before the authorization code is ever spent.

# The transaction cookie must survive a cross-site top-level navigation back from
# the IdP, which `samesite="strict"` would not. See `oidc.Transaction`.
_TX_COOKIE_KW: _CookieKeywords = {
    "secure": True,
    "samesite": "lax",
    "path": "/",
}


def _same_site_landing(target: str, heading: str) -> HTMLResponse:
    """Land the browser on our own origin, then navigate from there.

    **Why not a 302.** A redirect from this callback still belongs to the chain
    that began at the identity provider, so the follow-up request is cross-site
    and a `SameSite=Strict` cookie is withheld — the user would arrive signed
    out. Landing here first makes the next navigation *same-site*, which is what
    lets locked S-3 keep `strict` instead of being relaxed to `lax` for the whole
    application.

    **The back button.** A `<meta http-equiv="refresh">` leaves this callback URL
    in session history, so Back re-runs the callback with a spent transaction
    cookie and shows a bogus "sign-in failed". That was the real defect behind the
    302 experiment, and it is fixed here rather than by trading the cookie:
    `location.replace()` navigates AND drops this entry from history, so Back
    skips straight past it. The meta refresh stays as the no-script fallback and
    the anchor as the no-meta fallback — in that degraded case the history entry
    remains, which is a cosmetic annoyance rather than a security property.

    No CSP is configured on this deployment (checked 2026-09-01), so the inline
    script needs no `script-src` allowance. If a CSP is ever added it needs a
    nonce or hash for this one script, and the meta refresh keeps the flow
    working in the meantime.
    """
    return HTMLResponse(
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        f"<meta http-equiv=\"refresh\" content=\"0;url={target}\">"
        "<title>Signing in…</title></head>"
        f"<body><p>{heading}</p>"
        f"<p><a href=\"{target}\">Continue</a></p>"
        f"<script>location.replace({target!r})</script>"
        "</body></html>",
        # Never cached: this response carries Set-Cookie for a session.
        headers={"Cache-Control": "no-store"},
    )


@router.get("/oidc/start")
def oidc_start(request: Request) -> Response:
    """Begin corporate SSO — redirect the browser to the identity provider.

    Rate-limited on the same S-5 bucket shape as password login and keyed on the
    client address: an unauthenticated route that performs an outbound discovery
    request must not be a free amplifier.
    """
    client = request.client.host if request.client else "unknown"
    limiter.check(f"oidc:{client}", ratelimit.LOGIN)
    rid = request_id_of(request)

    try:
        transaction = oidc.new_transaction()
        target = oidc.authorization_url(transaction)
    except oidc.OidcFailure as failure:
        # An unconfigured or unreachable IdP is an operational condition, not
        # something to explain to an anonymous caller.
        oidc.log_failure(failure.reason, client, rid)
        return _same_site_landing("/login?sso=unavailable",
                                  "Single sign-on is unavailable.")

    response = RedirectResponse(target, status_code=302)
    response.set_cookie(oidc.TRANSACTION_COOKIE, transaction.encode(),
                        httponly=True, max_age=oidc.TRANSACTION_MAX_AGE,
                        **_TX_COOKIE_KW)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oidc/callback")
def oidc_callback(request: Request, db: DBSession = Depends(get_db)) -> Response:
    """Complete corporate SSO and establish the server-side session.

    S-7 governs the failure shape. An account bound to another subject, a disabled
    account, an unverified email, a replayed state and a provider error all render
    the identical page and the identical query string — a distinguishable message
    would turn the login screen into a directory of who has a LegalMind account.

    **One refusal is deliberately distinguishable: the corporate-domain check.** It
    runs before any database lookup, and the permitted domain is already public in
    the authorization request's ``hd`` parameter, so naming it discloses nothing an
    attacker could not already read. Telling a user with a personal Gmail address
    exactly why they were turned away is worth far more than the nothing it costs.
    Everything else stays indistinguishable, and `oidc.OidcDomainRefused` being its
    own class is what keeps that boundary deliberate rather than accidental.
    """
    client = request.client.host if request.client else "unknown"
    limiter.check(f"oidc:{client}", ratelimit.LOGIN)
    rid = request_id_of(request)

    # `error` is the IdP's own refusal (the user cancelled, consent denied). It is
    # not a failure of ours and produces no audit event — no account was named.
    if request.query_params.get("error"):
        oidc.log_failure("provider returned an error parameter", client, rid)
        return _fail_sso()

    try:
        transaction = oidc.Transaction.decode(
            request.cookies.get(oidc.TRANSACTION_COOKIE))
        claims = oidc.exchange_code(
            code=request.query_params.get("code", ""),
            transaction=transaction,
            state=request.query_params.get("state", ""))
        user, identity = oidc.resolve_user(db, claims)
    except oidc.OidcDomainRefused as refusal:
        # No audit event and no actor: the domain check precedes every lookup, so
        # no account was named and there is nothing to attribute this to.
        oidc.log_failure(refusal.reason, client, rid)
        return _fail_sso("domain")
    except oidc.OidcFailure as failure:
        oidc.log_failure(failure.reason, client, rid)
        # 47.9 — the attempt is recorded, without the submitted email and without
        # an actor when no account was resolved, exactly as the password path does.
        A.record(db, action=A.AUTH_LOGIN_FAILED, entity_type="authentication",
                 request_id=rid)
        _signal_auth_failure(client, rid)
        db.commit()          # the response is about to be sent; the event survives
        return _fail_sso()

    session = create_session(db, user)
    identity.last_used_at = session.created_at
    # Fill a blank display name from the provider, but never overwrite one that is
    # already set — an administrator's correction outranks Google's profile.
    if not (user.name or "").strip():
        user.name = claims.name
    A.record(db, action=A.AUTH_LOGIN_SUCCEEDED, entity_type="session",
             entity_id=session.id, actor_id=user.id, request_id=rid)
    db.commit()

    max_age = int((session.expires_at - session.created_at).total_seconds())
    # A same-site landing page, not a 302 — see `_same_site_landing`. The 302 that
    # briefly replaced it required weakening the session cookie to SameSite=Lax
    # application-wide, which locked S-3 forbids.
    response = _same_site_landing(config.oidc_post_login_path(),
                                  "Signed in. Taking you to LegalMind…")
    _set_session_cookies(response, session.id, max_age)
    _set_token_cookie(response, db, user)
    # The pre-authentication transaction is spent; it must not be replayable.
    response.delete_cookie(oidc.TRANSACTION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response

def _set_token_cookie(response: Response, db: DBSession, user: M.User) -> None:
    """Issue the `AM-36` (AB-8) stateless token alongside the session.

    **Alongside, not instead.** `AM-36` t1 leaves server-side sessions permitted,
    and `get_principal` prefers the session when both cookies are present — so a
    normal browser sign-in stays fully revocable and the token is what survives if
    the session is ever dropped.

    Cookie attributes are S-3's, unchanged: t6 requires exactly them, and the
    token is a credential — it goes in no response body, no URL and no log line.

    Failure to sign is NOT fatal to the sign-in. t5 forbids a downgrade, so an
    unset or weak key means no token is issued at all; the session cookie has
    already established the caller and the flow completes normally.

    (Restored 2026-09-01: this helper was removed by accident while reverting the
    unrelated `oidc_provider_tokens` feature, which sat immediately above it.)
    """
    try:
        # The roles claim is `AM-36` t2's requirement and is ADVISORY (t3) — read
        # here purely to fill the claim, and never consulted when authorizing.
        roles = tuple(db.execute(
            select(M.Role.code)
            .join(M.UserRole, M.UserRole.role_id == M.Role.id)
            .where(M.UserRole.user_id == user.id)
        ).scalars())
        token = tokens.issue(user_id=user.id, email=user.email, roles=roles)
    except tokens.TokenRefused as refusal:
        log_event("auth.token_not_issued", level=logging.WARNING,
                  reason=refusal.reason)
        return
    response.set_cookie(
        tokens.TOKEN_COOKIE, token, httponly=True,
        max_age=int(tokens.TOKEN_LIFETIME.total_seconds()), **_COOKIE_KW)


def _fail_sso(outcome: str = "failed") -> Response:
    """The SSO failure outcomes — two, and only two.

    `failed` is the S-7 outcome: one page, one query value, for every cause that
    could disclose account state. The login screen renders a fixed sentence for it
    and the operator log holds the actual reason against the request id.

    `domain` is the one safe exception, argued at the callback. Adding a third
    value is a security decision, not a UX tweak — every additional outcome is
    another bit an attacker can read off the login screen.
    """
    response = _same_site_landing(f"/login?sso={outcome}",
                                  "Sign-in did not complete.")
    response.delete_cookie(oidc.TRANSACTION_COOKIE, path="/")
    return response

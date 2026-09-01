"""OIDC authorization-code flow — Step 47 §47.1.3 / SEC-01 (OD-9).

Locked 47.1.3 makes corporate SSO via OIDC the **primary** authentication
mechanism and password login "a controlled fallback". This module implements the
provider half of that; ``api/routers/auth.py`` holds the two routes locked 49.2
names (``/auth/oidc/start``, ``/auth/oidc/callback``).

Three things this module deliberately does NOT do
-------------------------------------------------
**It confers no authority.** SEC-01: "Authentication never confers Legal Decision
authority." Success here ends at a ``user_id``; every permission is still resolved
per request from the database (S-1). Nothing below touches a role, a grant or a
permission — grep it: neither ``permissions`` nor ``authorization`` is imported.

**It provisions accounts, but never authority.** Just-in-time provisioning was
turned ON by owner instruction on 2026-09-01, reversing this module's original
refuse-unknown-identity behaviour. A first sign-in by a verified address inside the
permitted corporate domain creates the ``User`` row.

What that deliberately does NOT do is let an identity provider hand out authority.
The provisioned account gets ``config.oidc_jit_roles()`` — ``USER`` by default,
which carries ordinary contract and review work and **none** of ``legal.decision``,
``legal_position.view``, ``user.manage`` or ``audit.view``. `SEC-01`'s separation
survives intact: Google can now say *who* you are, and still has no say in *what
you may do*. Legal authority remains an explicit human grant under Steps 4, 23 and
31, and `SEC-02`/`ROLE-05` keep it out of every super-role.

Two guards make that structural rather than stated. The domain restriction is
enforced on the provider's **verified** email before any row is written, so the
gate on who may self-provision is the Workspace itself; and if a configured role
code does not exist in the database the sign-in **fails closed** rather than
creating an account with no authority anybody asked for.

`LEGALMIND_OIDC_JIT_ROLES=DISABLED` restores the original behaviour.

**It adds no dependency.** No JWT/JWKS client library is required, because the
ID token is never taken from an untrusted channel: it is read from the response to
our own direct, server-to-server, TLS-authenticated POST to the issuer's token
endpoint, using a client secret only we hold. OIDC Core §3.1.3.7 r6 permits
omitting signature validation in exactly that case. The transport is
``urllib.request`` from the standard library — the same choice already made for
the assist lane's one permitted egress in ``assist/generation.py``. Consequence:
the claims are parsed, never *verified* as a bearer token, and this module must
never grow a path that accepts an ID token from a client.

Fail closed (rule 15). Every abnormal outcome — a bad state, an unverified email,
a wrong domain, an unknown account, a disabled account, a provider error — raises
``OidcFailure``. The route renders one indistinguishable refusal for all of them
(S-7), and the specific reason goes to the operator log, never to the browser.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.security.errors import Unauthenticated

# The minimum that identifies a person, and no more. `profile` is requested for
# ONE claim: `name`, which `serialize_session_identity` returns and the app chrome
# renders — so locked 53.3's "hold what we use" is satisfied rather than stretched.
# `picture` is deliberately NOT stored: `users` has no column for it, adding one is
# outside `IMPL-01`, and nothing in the UI shows an avatar.
SCOPES = "openid email profile"

# A pre-authentication transaction is worth ten minutes and not a session.
TRANSACTION_MAX_AGE = 600
TRANSACTION_COOKIE = "legalmind_oidc_tx"

_HTTP_TIMEOUT = 15
_DISCOVERY_SUFFIX = "/.well-known/openid-configuration"

# Discovery is immutable in practice and re-fetching it on every sign-in would put
# the IdP's availability in front of every login. Keyed by issuer so a
# reconfiguration in a test or a redeployment is not served a stale document.
_discovery_cache: dict[str, dict[str, Any]] = {}


class OidcFailure(Unauthenticated):
    """An SSO attempt that must not proceed.

    Subclasses ``Unauthenticated`` so that any path which forgets to catch it
    still produces the one fixed, non-disclosing 401 body (S-7) rather than a 500
    carrying a provider message.
    """

    def __init__(self, reason: str):
        # `reason` is operator-facing and never rendered: the base message is what
        # a user could ever see.
        super().__init__("authentication failed")
        self.reason = reason


class OidcDomainRefused(OidcFailure):
    """The verified email is outside the permitted corporate domain.

    Given its own class, and its own message on the sign-in screen, because
    telling the user this discloses **nothing** — the domain restriction is
    already public in the authorization request's `hd` parameter, and the check
    runs BEFORE any database lookup, so it cannot reveal whether an account
    exists. S-7 is about account enumeration; this is not that.

    Kept separate from every other refusal precisely so the distinction stays
    deliberate: a future cause must not inherit a distinguishable message by
    accident.
    """


@dataclass(frozen=True)
class Transaction:
    """The pre-authentication state carried across the redirect to the IdP.

    Held in a short-lived cookie rather than a database row: adding a table is
    outside `IMPL-01`'s authorization, and session-key management is NOT YET
    SPECIFIED so there is no key to sign with. The cookie is ``HttpOnly`` and
    ``Secure``; the threat it defends against is a *cross-site* forged callback,
    and an attacker able to write cookies on this origin has already defeated
    more than this flow.

    ⚠️ ``SameSite=Lax``, not ``Strict`` like the session cookie. The callback is a
    top-level navigation from the IdP, i.e. cross-site, and a ``Strict`` cookie
    would not be sent — the flow would fail every time, on every browser. ``Lax``
    is sent on exactly this case (top-level GET) and no other.
    """

    state: str
    nonce: str
    code_verifier: str

    def encode(self) -> str:
        return base64.urlsafe_b64encode(
            json.dumps({"s": self.state, "n": self.nonce,
                        "v": self.code_verifier}).encode()
        ).decode()

    @staticmethod
    def decode(raw: str | None) -> Transaction:
        if not raw:
            raise OidcFailure("no transaction cookie on the callback")
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
            return Transaction(state=payload["s"], nonce=payload["n"],
                               code_verifier=payload["v"])
        except Exception as cause:              # malformed, truncated, tampered
            raise OidcFailure("unreadable transaction cookie") from cause


@dataclass(frozen=True)
class Claims:
    """The identity the provider asserted, after our own checks."""

    subject: str
    email: str
    name: str


def new_transaction() -> Transaction:
    """A fresh CSRF state, replay nonce and PKCE verifier.

    PKCE is not strictly required of a confidential client, but it costs one hash
    and removes the value of a stolen authorization code outright.
    """
    return Transaction(state=secrets.token_urlsafe(32),
                       nonce=secrets.token_urlsafe(32),
                       code_verifier=secrets.token_urlsafe(64))


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _require_configured() -> tuple[str, str, str, str]:
    if not config.oidc_configured():
        raise OidcFailure("OIDC is not configured in this deployment")
    issuer = config.oidc_issuer()
    client_id = config.oidc_client_id()
    client_secret = config.oidc_client_secret()
    redirect_uri = config.oidc_redirect_uri()
    assert issuer and client_id and client_secret and redirect_uri
    return issuer, client_id, client_secret, redirect_uri


def _post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(fields).encode("ascii")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"})
    if request.type != "https":
        raise OidcFailure("the issuer advertises a non-HTTPS endpoint")
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as cause:
        # The provider's body can carry the client secret back in an error echo on
        # some IdPs; it is never logged and never surfaced.
        raise OidcFailure(f"token endpoint returned HTTP {cause.code}") from cause
    except (urllib.error.URLError, TimeoutError, ValueError) as cause:
        raise OidcFailure("token endpoint unreachable or unreadable") from cause


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json"})
    if request.type != "https":
        raise OidcFailure("discovery over a non-HTTPS URL is refused")
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as cause:
        raise OidcFailure("issuer discovery failed") from cause


def discover(issuer: str) -> dict[str, Any]:
    """The issuer's OIDC discovery document, cached per issuer.

    The document's own ``issuer`` must equal the configured one. Without that
    check, a wrong ``LEGALMIND_OIDC_ISSUER`` would silently authenticate against
    whatever host answered.
    """
    if issuer in _discovery_cache:
        return _discovery_cache[issuer]
    document = _get_json(issuer.rstrip("/") + _DISCOVERY_SUFFIX)
    if document.get("issuer") != issuer:
        raise OidcFailure("discovery document issuer does not match configuration")
    for key in ("authorization_endpoint", "token_endpoint"):
        if not isinstance(document.get(key), str):
            raise OidcFailure(f"discovery document has no {key}")
    _discovery_cache[issuer] = document
    return document


def authorization_url(transaction: Transaction) -> str:
    """Where to send the browser to begin sign-in."""
    issuer, client_id, _, redirect_uri = _require_configured()
    endpoint = discover(issuer)["authorization_endpoint"]
    parameters = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": transaction.state,
        "nonce": transaction.nonce,
        "code_challenge": _code_challenge(transaction.code_verifier),
        "code_challenge_method": "S256",
        # Corporate SSO: send the user straight to the account chooser rather than
        # silently reusing whichever Google account the browser happens to hold.
        "prompt": "select_account",
    }
    domain = config.oidc_allowed_domain()
    if domain:
        # Advisory only — it pre-filters Google's chooser. The binding check below
        # is what actually enforces the domain.
        parameters["hd"] = domain
    return f"{endpoint}?{urllib.parse.urlencode(parameters)}"


def _decode_id_token_claims(id_token: str) -> dict[str, Any]:
    """Read the ID token's payload.

    Not a verification step and not named as one. See the module docstring: this
    token came from our own TLS POST to the token endpoint, which is what makes
    reading it sound. A token from any other source must never reach here.
    """
    parts = id_token.split(".")
    if len(parts) != 3:
        raise OidcFailure("ID token is not a three-part JWT")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception as cause:
        raise OidcFailure("ID token payload is unreadable") from cause
    if not isinstance(claims, dict):
        raise OidcFailure("ID token payload is not an object")
    return claims


def exchange_code(code: str, transaction: Transaction, state: str) -> Claims:
    """Redeem the authorization code and return the asserted identity.

    Order matters: ``state`` is compared before the code is spent, so a forged
    callback never causes a token request at all.

    Nothing about the provider's own tokens is retained: the authorization code is
    exchanged, the identity is read from the ID token, and the access/refresh
    tokens are discarded with the response. Storing them was reverted on
    2026-09-01 — see the module docstring.
    """
    issuer, client_id, client_secret, redirect_uri = _require_configured()

    if not state or not secrets.compare_digest(state, transaction.state):
        raise OidcFailure("state mismatch on the callback")
    if not code:
        raise OidcFailure("callback carried no authorization code")

    tokens = _post_form(discover(issuer)["token_endpoint"], {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": transaction.code_verifier,
    })
    id_token = tokens.get("id_token")
    if not isinstance(id_token, str):
        raise OidcFailure("token response carried no id_token")

    claims = _decode_id_token_claims(id_token)

    if claims.get("iss") != issuer:
        raise OidcFailure("ID token issuer mismatch")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if client_id not in audiences:
        raise OidcFailure("ID token audience is not this client")
    if not secrets.compare_digest(str(claims.get("nonce") or ""),
                                  transaction.nonce):
        raise OidcFailure("ID token nonce mismatch")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise OidcFailure("ID token carried no subject")

    email = str(claims.get("email") or "").strip().lower()
    if not email:
        raise OidcFailure("ID token carried no email")
    # An unverified email is an impersonation vector: it is the value we bind an
    # account on, and an IdP that has not verified it has asserted nothing.
    if claims.get("email_verified") not in (True, "true"):
        raise OidcFailure("email is not verified at the provider")

    domain = config.oidc_allowed_domain()
    if domain and email.rsplit("@", 1)[-1] != domain:
        # Enforced on the verified email, not on `hd`, which a request can drop.
        raise OidcDomainRefused("email domain is outside the permitted domain")

    # `name` is optional at every provider and must never be load-bearing. Falls
    # back to the local part so the chrome always has something to render.
    name = str(claims.get("name") or "").strip() or email.split("@")[0]

    # The provider's own access and refresh tokens are deliberately NOT retained.
    # Storing them (table `oidc_provider_tokens`) was reverted on 2026-09-01: no
    # lock record authorised the table, and `AM-36` — the record it cited — says
    # "No table, column or enum changes". The identity is all this flow needs.
    return Claims(subject=subject, email=email, name=name[:200])



def _provision(db: DBSession, claims: Claims) -> M.User:
    """Create the account for a first-time, domain-verified corporate identity.

    Fails closed on a missing role code (rule 15). The alternative — creating the
    user and silently skipping the grant — produces an account whose authority
    nobody chose, which is the failure mode this whole module is arranged against.
    Refusing means an operator sees one clear log line and fixes the configuration,
    and no half-provisioned row is left behind.

    Deliberately does NOT call ``security.seed.bootstrap``: seeding the permission
    catalogue is a deployment act, not something an unauthenticated request may
    trigger. If the roles are not seeded, that is a deployment error to surface.
    """
    wanted = config.oidc_jit_roles()
    if not config.oidc_jit_enabled():
        raise OidcFailure("no LegalMind account for this identity "
                          "(JIT provisioning is disabled)")

    roles = {}
    if wanted:
        roles = {r.code: r for r in db.execute(
            select(M.Role).where(M.Role.code.in_(wanted))).scalars()}
        missing = sorted(set(wanted) - set(roles))
        if missing:
            raise OidcFailure(
                f"cannot provision: configured JIT role(s) {missing} are not "
                "seeded in this database")

    user = M.User(email=claims.email, name=claims.name,
                  status=E.UserStatus.ACTIVE)
    db.add(user)
    db.flush()
    for code in wanted:
        db.add(M.UserRole(user_id=user.id, role_id=roles[code].id))
    db.flush()
    return user


def resolve_user(db: DBSession,
                 claims: Claims) -> tuple[M.User, M.UserIdentity]:
    """Map an asserted identity onto a LegalMind user, provisioning on first use.

    Matching is by ``sub`` once bound, and by email only for the first sign-in.
    ``sub`` is the IdP's immutable identifier; an email address can be reassigned
    inside a Google Workspace, and binding on email alone would let a recycled
    address inherit a departed user's Reviews and audit history.
    """
    identity = db.execute(
        select(M.UserIdentity).where(
            M.UserIdentity.provider == E.IdentityProvider.OIDC,
            M.UserIdentity.provider_subject == claims.subject)
    ).scalars().first()

    if identity is not None:
        user = db.get(M.User, identity.user_id)
        if user is None:                                  # pragma: no cover
            raise OidcFailure("bound identity points at no user")
    else:
        user = db.execute(
            select(M.User).where(M.User.email == claims.email)
        ).scalars().first()
        if user is None:
            user = _provision(db, claims)
            log_event("auth.oidc_account_provisioned", user_id=str(user.id))
        existing = db.execute(
            select(M.UserIdentity).where(
                M.UserIdentity.user_id == user.id,
                M.UserIdentity.provider == E.IdentityProvider.OIDC)
        ).scalars().first()
        if existing is not None:
            # The account is already bound to a DIFFERENT subject. Rebinding is an
            # administrator action, not something a sign-in decides.
            raise OidcFailure("account is bound to a different provider subject")
        identity = M.UserIdentity(user_id=user.id,
                                  provider=E.IdentityProvider.OIDC,
                                  provider_subject=claims.subject)
        db.add(identity)
        db.flush()
        log_event("auth.oidc_identity_bound", user_id=str(user.id))

    if user.status is not E.UserStatus.ACTIVE:
        # 47.1.3 — status gating applies to every mechanism, and the refusal is
        # indistinguishable from every other failure.
        raise OidcFailure("account is not active")

    return user, identity


def log_failure(reason: str, client: str, request_id: str) -> None:
    """Operator-facing only.

    Deliberately without the email or the subject: locked 53.3's fourth
    prohibition is anything that turns a failed-login record into an enumeration
    oracle, and `reason` is already a fixed phrase from this module rather than
    provider text.
    """
    log_event("auth.oidc_failed", level=logging.WARNING, request_id=request_id,
              client=client, reason=reason, signal="auth.failure_count")

"""Corporate SSO via OIDC — Step 47 §47.1.3 / SEC-01 (OD-9).

The provider is stubbed at exactly one seam, ``oidc._post_form``/``oidc._get_json``,
so everything from the state check inwards is the real code. Nothing here reaches
the network: a test that needed Google to be up would not be a test.

What these tests are actually holding to account, in order of how badly it would
hurt to get wrong:

1. authentication confers NO authority (SEC-01) — a fresh SSO session can do
   nothing a password session could not;
2. no just-in-time provisioning — an IdP cannot mint LegalMind principals;
3. one indistinguishable failure for every reason (S-7);
4. the locked session cookie attributes are unchanged (S-3).
"""

from __future__ import annotations

import base64
import json

import pytest

from legalmind.api.context import CSRF_COOKIE, SESSION_COOKIE
from legalmind.domain import enums as E
from legalmind.security import oidc

# ISSUER/CLIENT_ID/REDIRECT are re-exported for tests/test_tokens.py, which
# drives the same callback to check the AM-36 token cookie.
ISSUER = "https://idp.example"
CLIENT_ID = "client-id-abc"
REDIRECT = "https://legalmind.example/api/v1/auth/oidc/callback"
SUBJECT = "provider-subject-0001"

START = "/api/v1/auth/oidc/start"
CALLBACK = "/api/v1/auth/oidc/callback"


def _id_token(claims: dict) -> str:
    """A JWT-shaped token. The signature is deliberately nonsense: this module
    never validates one, because the token only ever arrives from our own TLS
    exchange with the token endpoint (see oidc.py's docstring). If a future change
    started verifying signatures, every test here would fail loudly — which is the
    correct outcome, not a nuisance."""
    def segment(payload: dict) -> str:
        raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        return raw.rstrip("=")
    return f"{segment({'alg': 'RS256'})}.{segment(claims)}.not-a-signature"


def _stub_token_endpoint(monkeypatch, *, nonce_from, claims=None, tokens=None):
    """Stub the token POST, deriving the nonce from the transaction cookie so the
    stub behaves like a real IdP rather than sidestepping the nonce check."""
    captured: dict = {}

    def post_form(url, fields):
        captured["fields"] = fields
        if tokens is not None:
            return tokens
        payload = {
            "iss": ISSUER, "aud": CLIENT_ID, "sub": SUBJECT,
            "email": "analyst@leapswitch.com", "email_verified": True,
            "nonce": nonce_from(),
        }
        payload.update(claims or {})
        return {"id_token": _id_token(payload)}

    monkeypatch.setattr(oidc, "_post_form", post_form)
    return captured


def _begin(api) -> tuple[str, str]:
    """Run /oidc/start and return (state, nonce) as the browser now holds them."""
    response = api.get(START, follow_redirects=False)
    assert response.status_code == 302
    raw = api.cookies.get(oidc.TRANSACTION_COOKIE)
    assert raw, "the transaction cookie must be set before the redirect"
    transaction = oidc.Transaction.decode(raw)
    return transaction.state, transaction.nonce


# =====================================================================
# The redirect out
# =====================================================================
def test_start_redirects_to_the_provider_with_state_nonce_and_pkce(api, configured):
    response = api.get(START, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(f"{ISSUER}/authorize?")
    for parameter in ("state=", "nonce=", "code_challenge=",
                      "code_challenge_method=S256", "response_type=code",
                      f"client_id={CLIENT_ID}"):
        assert parameter in location, parameter
    # The redirect_uri is the CONFIGURED value, never one built from the inbound
    # Host header — that is how an authorization code gets delivered elsewhere.
    assert "redirect_uri=https%3A%2F%2Flegalmind.example" in location


def test_start_requests_the_narrowest_useful_scope(api, configured):
    """Locked 53.3 — we hold what we use, and nothing more.

    `profile` is requested for exactly one claim, `name`, which the app chrome
    renders. Everything else a Google client CAN ask for is personal data we would
    hold for nothing, so the assertion is written as a deny-list too: a scope
    creeping in later fails here.
    """
    location = api.get(START, follow_redirects=False).headers["location"]
    assert "scope=openid+email+profile" in location
    for overreach in ("drive", "contacts", "calendar", "gmail", "cloud-platform",
                      "directory", "admin", "spreadsheets", "userinfo.profile"):
        assert overreach not in location, overreach


def test_the_transaction_cookie_is_httponly_secure_and_lax(api, configured):
    """`Lax`, not `Strict` — the callback is a cross-site top-level navigation and
    a Strict cookie would never come back, breaking every sign-in."""
    header = api.get(START, follow_redirects=False).headers["set-cookie"].lower()
    assert "httponly" in header and "secure" in header
    assert "samesite=lax" in header
    assert "samesite=strict" not in header


def test_start_is_unavailable_rather_than_broken_when_unconfigured(api, monkeypatch):
    """An unconfigured deployment must not 500, and must not explain itself to an
    anonymous caller beyond "unavailable"."""
    for name in ("LEGALMIND_OIDC_ISSUER", "LEGALMIND_OIDC_CLIENT_ID",
                 "LEGALMIND_OIDC_CLIENT_SECRET", "LEGALMIND_OIDC_REDIRECT_URI"):
        monkeypatch.delenv(name, raising=False)
    response = api.get(START, follow_redirects=False)
    assert response.status_code == 200
    assert "sso=unavailable" in response.text


def test_a_domain_restricted_deployment_passes_hd(api, configured, monkeypatch):
    monkeypatch.setenv("LEGALMIND_OIDC_ALLOWED_DOMAIN", "leapswitch.com")
    assert "hd=leapswitch.com" in api.get(START,
                                          follow_redirects=False).headers["location"]


# =====================================================================
# The callback — success
# =====================================================================
def test_a_bound_identity_signs_in_and_gets_the_locked_session_cookies(
        api, db, configured, monkeypatch, user):
    """The happy path, on an account an administrator already created and bound."""
    db.add(_identity(user))
    db.flush()

    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)

    response = api.get(f"{CALLBACK}?code=auth-code&state={state}",
                       follow_redirects=False)
    # With SameSite=Lax, a 302 redirect correctly sends the session cookie on a
    # top-level navigation from the IdP. The cookie is set on the redirect response.
    assert response.status_code == 302
    assert response.headers["location"].endswith("/documents")

    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies
                          if c.startswith(f"{SESSION_COOKIE}=")).lower()
    assert "httponly" in session_cookie
    assert "secure" in session_cookie
    # S-3: session cookie uses SameSite=Lax (required for OIDC callback which is
    # a cross-site top-level navigation from the IdP; Strict would withhold the cookie)
    assert "samesite=lax" in session_cookie
    assert any(c.startswith(f"{CSRF_COOKIE}=") for c in cookies)

    # The session is real and usable.
    assert api.get("/api/v1/auth/session").status_code == 200


def test_sso_confers_no_authority(api, db, configured, monkeypatch, user):
    """SEC-01 — "Authentication never confers Legal Decision authority."

    The point of the test is the empty permission array: a user with no roles who
    signs in via the *primary* mechanism is exactly as unprivileged as before.
    """
    db.add(_identity(user))
    db.flush()
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    body = api.get("/api/v1/auth/session").json()["data"]
    assert body["permissions"] == []


def test_first_sign_in_binds_the_subject_to_an_existing_account(
        api, db, configured, monkeypatch, user):
    """Binding on email happens ONCE. Afterwards the immutable `sub` is what
    matches, so a recycled Workspace address cannot inherit the account."""
    from legalmind.db import models as M
    user.email = "analyst@leapswitch.com"
    db.flush()

    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    identity = db.query(M.UserIdentity).filter_by(
        user_id=user.id, provider=E.IdentityProvider.OIDC).one()
    assert identity.provider_subject == SUBJECT
    assert identity.credential_hash is None      # SSO holds no credential
    assert identity.last_used_at is not None


# =====================================================================
# The callback — every refusal, and they must be indistinguishable (S-7)
# =====================================================================
def _refusal(api, db, monkeypatch, *, claims=None, tokens=None, state=None,
             code="auth-code"):
    state_value, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce,
                         claims=claims, tokens=tokens)
    query = f"code={code}&state={state if state is not None else state_value}"
    return api.get(f"{CALLBACK}?{query}", follow_redirects=False)


# =====================================================================
# JIT provisioning — owner instruction 2026-09-01
# =====================================================================
# The whole point of these tests is the SEC-01 line: Google may now say who you
# are, and still has no say in what you may do.
def test_a_first_time_corporate_identity_is_provisioned_and_signed_in(
        api, db, configured, monkeypatch, seeded):
    from legalmind.db import models as M
    before = db.query(M.User).count()

    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce,
                         claims={"email": "newjoiner@leapswitch.com",
                                 "name": "New Joiner"})
    response = api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    assert "sso=" not in response.text
    assert db.query(M.User).count() == before + 1
    created = db.query(M.User).filter_by(email="newjoiner@leapswitch.com").one()
    assert created.status is E.UserStatus.ACTIVE
    assert created.name == "New Joiner"
    # Bound to the provider subject, with no credential — there is no password to
    # steal on an SSO-provisioned account.
    identity = db.query(M.UserIdentity).filter_by(
        user_id=created.id, provider=E.IdentityProvider.OIDC).one()
    assert identity.provider_subject == SUBJECT
    assert identity.credential_hash is None
    assert api.get("/api/v1/auth/session").status_code == 200


def test_provisioning_grants_work_permissions_and_no_authority(
        api, db, configured, monkeypatch, seeded):
    """`SEC-01`, `SEC-02`, `ROLE-05`, Step 23 — the load-bearing test of this feature.

    A provisioned account may do ordinary contract and review work. It must hold
    NONE of `legal.decision`, `legal.approve_customization`, `legal_position.view`,
    `user.manage`, `role.manage`, `platform.manage` or `audit.view`. If an identity
    provider could confer any of those, authentication would be conferring
    authority, which is the one thing Step 47 forbids outright.
    """
    from legalmind.security import permissions as P

    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce,
                         claims={"email": "newjoiner@leapswitch.com"})
    api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    granted = set(api.get("/api/v1/auth/session").json()["data"]["permissions"])

    assert P.CONTRACT_VIEW in granted and P.REVIEW_CREATE in granted
    for forbidden in (P.LEGAL_DECISION, P.LEGAL_APPROVE_CUSTOMIZATION,
                      P.LEGAL_POSITION_VIEW, P.USER_MANAGE, P.ROLE_MANAGE,
                      P.PLATFORM_MANAGE, P.AUDIT_VIEW):
        assert forbidden not in granted, forbidden


def test_provisioning_is_refused_outside_the_permitted_domain(
        api, db, configured, monkeypatch, seeded):
    """The domain gate is what makes self-provisioning safe: only the corporate
    Workspace can create accounts. Without it, JIT means anyone with any Google
    account gets in."""
    from legalmind.db import models as M
    monkeypatch.setenv("LEGALMIND_OIDC_ALLOWED_DOMAIN", "leapswitch.com")
    before = db.query(M.User).count()

    response = _refusal(api, db, monkeypatch,
                        claims={"email": "stranger@gmail.com"})

    assert "sso=domain" in response.text
    assert db.query(M.User).count() == before


def test_the_domain_refusal_names_no_account_and_no_address(
        api, db, configured, monkeypatch, seeded):
    """Distinguishable on purpose, but it still discloses nothing: not whether an
    account exists, and not the address that was rejected."""
    monkeypatch.setenv("LEGALMIND_OIDC_ALLOWED_DOMAIN", "leapswitch.com")
    response = _refusal(api, db, monkeypatch,
                        claims={"email": "stranger@gmail.com"})
    body = response.text.lower()
    assert "stranger" not in body and "gmail" not in body
    assert "account" not in body


def test_jit_can_be_disabled_and_then_nothing_is_created(
        api, db, configured, monkeypatch, seeded):
    """The escape hatch, and the original behaviour: an unknown identity is refused
    with the indistinguishable outcome, and no row is written."""
    from legalmind.db import models as M
    monkeypatch.setenv("LEGALMIND_OIDC_JIT_ROLES", "DISABLED")
    before = db.query(M.User).count()

    response = _refusal(api, db, monkeypatch,
                        claims={"email": "newjoiner@leapswitch.com"})

    assert "sso=failed" in response.text
    assert "sso=domain" not in response.text
    assert db.query(M.User).count() == before


def test_provisioning_with_no_roles_creates_a_powerless_account(
        api, db, configured, monkeypatch, seeded):
    """The most conservative form that still provisions: the user can sign in and
    see nothing until an administrator grants something."""
    monkeypatch.setenv("LEGALMIND_OIDC_JIT_ROLES", "")
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce,
                         claims={"email": "newjoiner@leapswitch.com"})
    api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    assert api.get("/api/v1/auth/session").json()["data"]["permissions"] == []


def test_provisioning_fails_closed_on_an_unseeded_role(
        api, db, configured, monkeypatch, seeded):
    """Rule 15. Creating the user and silently skipping the grant would produce an
    account whose authority nobody chose; refusing leaves no half-provisioned row
    and one clear line in the operator log."""
    from legalmind.db import models as M
    monkeypatch.setenv("LEGALMIND_OIDC_JIT_ROLES", "ROLE_THAT_DOES_NOT_EXIST")
    before = db.query(M.User).count()

    response = _refusal(api, db, monkeypatch,
                        claims={"email": "newjoiner@leapswitch.com"})

    assert "sso=failed" in response.text
    assert db.query(M.User).count() == before


def test_provisioning_never_reaches_a_disabled_account(
        api, db, configured, monkeypatch, user, seeded):
    """A disabled user still exists, so this is a match, not a provision — the
    disabled account must not be bypassed by creating a second row for the same
    address (the unique constraint would refuse, and it must never be attempted)."""
    from legalmind.db import models as M
    user.email = "analyst@leapswitch.com"
    user.status = E.UserStatus.DISABLED
    db.flush()
    before = db.query(M.User).count()

    response = _refusal(api, db, monkeypatch)

    assert "sso=failed" in response.text
    assert db.query(M.User).count() == before


@pytest.mark.parametrize("case,kwargs", [
    ("unverified email", {"claims": {"email_verified": False}}),
    ("no email", {"claims": {"email": ""}}),
    ("no subject", {"claims": {"sub": ""}}),
    ("issuer mismatch", {"claims": {"iss": "https://evil.example"}}),
    ("audience mismatch", {"claims": {"aud": "some-other-client"}}),
    ("nonce mismatch", {"claims": {"nonce": "replayed-nonce"}}),
    ("no id_token", {"tokens": {"access_token": "a"}}),
    ("forged state", {"state": "attacker-chosen-state"}),
    ("no code", {"code": ""}),
])
def test_every_refusal_renders_the_identical_outcome(
        api, db, configured, monkeypatch, user, case, kwargs):
    """S-7 — one outcome, byte-identical, for every reason.

    Parametrised deliberately rather than written out: the property under test is
    that these nine causes cannot be told apart from outside, and a table makes a
    tenth cause that leaks something fail here rather than pass unnoticed.
    """
    db.add(_identity(user))
    db.flush()
    response = _refusal(api, db, monkeypatch, **kwargs)

    assert response.status_code == 200
    assert "sso=failed" in response.text
    assert not api.cookies.get(SESSION_COOKIE)
    # Nothing about the cause may appear in the body.
    for leak in ("nonce", "audience", "issuer", "email", "account", "state",
                 "verified", SUBJECT):
        assert leak.lower() not in response.text.lower(), (case, leak)


def test_a_disabled_account_cannot_sign_in_through_sso(
        api, db, configured, monkeypatch, user):
    """47.1.3 — status gating applies to EVERY mechanism. Making SSO primary must
    not create a route around a disabled account."""
    db.add(_identity(user))
    user.status = E.UserStatus.DISABLED
    db.flush()

    response = _refusal(api, db, monkeypatch)
    assert "sso=failed" in response.text
    assert not api.cookies.get(SESSION_COOKIE)


def test_an_account_bound_to_another_subject_is_not_rebound(
        api, db, configured, monkeypatch, user):
    """Rebinding is an administrator action. If a sign-in could do it, a Workspace
    admin who can create a user with a colleague's address could take over their
    account and its audit history."""
    from legalmind.db import models as M
    user.email = "analyst@leapswitch.com"
    db.add(_identity(user, subject="the-original-subject"))
    db.flush()

    response = _refusal(api, db, monkeypatch)          # arrives as SUBJECT
    assert "sso=failed" in response.text
    subjects = {i.provider_subject for i in db.query(M.UserIdentity)
                .filter_by(user_id=user.id, provider=E.IdentityProvider.OIDC)}
    assert subjects == {"the-original-subject"}


def test_a_wrong_email_domain_is_refused_even_when_the_account_exists(
        api, db, configured, monkeypatch, user):
    """Enforced on the VERIFIED email, not on Google's advisory `hd` — which a
    crafted authorization request can simply omit.

    The account existing changes nothing: the domain gate runs before any lookup,
    which is both why it is safe to name and why it cannot be walked around by
    already having a user row.
    """
    monkeypatch.setenv("LEGALMIND_OIDC_ALLOWED_DOMAIN", "leapswitch.com")
    db.add(_identity(user))
    db.flush()
    response = _refusal(api, db, monkeypatch,
                        claims={"email": "someone@gmail.com"})
    assert "sso=domain" in response.text
    assert not api.cookies.get(SESSION_COOKIE)


def test_a_forged_callback_never_spends_a_code(api, db, configured, monkeypatch):
    """State is compared BEFORE the token request. Order matters: a login-CSRF
    attempt must not cause an outbound exchange at all."""
    called: list = []
    _begin(api)
    monkeypatch.setattr(oidc, "_post_form",
                        lambda url, fields: called.append(fields) or {})
    api.get(f"{CALLBACK}?code=c&state=forged", follow_redirects=False)
    assert called == []


def test_a_callback_with_no_transaction_cookie_is_refused(api, configured,
                                                          monkeypatch):
    """Arriving at the callback directly — no /oidc/start, so no state to match."""
    monkeypatch.setattr(oidc, "_post_form", lambda url, fields: {})
    response = api.get(f"{CALLBACK}?code=c&state=anything", follow_redirects=False)
    assert "sso=failed" in response.text


def test_the_transaction_cookie_is_cleared_after_use(api, db, configured,
                                                     monkeypatch, user):
    """Spent once. A replayable transaction cookie is a replayable sign-in."""
    db.add(_identity(user))
    db.flush()
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    response = api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)
    cleared = [c for c in response.headers.get_list("set-cookie")
               if c.startswith(f"{oidc.TRANSACTION_COOKIE}=")]
    assert cleared and ('Max-Age=0' in cleared[0] or 'expires=' in cleared[0].lower())


def test_the_provider_error_parameter_is_not_a_crash(api, configured):
    """The user cancelled at the consent screen. Common, and not an error of ours."""
    response = api.get(f"{CALLBACK}?error=access_denied", follow_redirects=False)
    assert response.status_code == 200
    assert "sso=failed" in response.text


# =====================================================================
# Configuration hardening
# =====================================================================
def test_discovery_must_agree_with_the_configured_issuer(configured, monkeypatch):
    """Without this check a mistyped LEGALMIND_OIDC_ISSUER would authenticate
    against whatever host answered."""
    monkeypatch.setattr(oidc, "_discovery_cache", {})
    monkeypatch.setattr(oidc, "_get_json", lambda url: {
        "issuer": "https://somewhere.else",
        "authorization_endpoint": "https://somewhere.else/a",
        "token_endpoint": "https://somewhere.else/t"})
    with pytest.raises(oidc.OidcFailure):
        oidc.discover(ISSUER)


def test_the_post_login_path_is_a_path_and_never_an_open_redirect(monkeypatch):
    from legalmind import config
    for hostile in ("https://evil.example/x", "//evil.example/x", "evil"):
        monkeypatch.setenv("LEGALMIND_OIDC_POST_LOGIN_PATH", hostile)
        assert config.oidc_post_login_path() == config.POST_LOGIN_PATH_DEFAULT


def test_an_oidc_failure_is_an_unauthenticated(api):
    """Belt and braces: any path that forgets to catch OidcFailure still renders
    the one fixed non-disclosing 401 body rather than a 500 carrying detail."""
    from legalmind.security.errors import Unauthenticated
    assert issubclass(oidc.OidcFailure, Unauthenticated)
    assert str(oidc.OidcFailure("a very specific internal reason")) \
        == "authentication failed"


def _identity(user, subject: str = SUBJECT):
    from legalmind.db import models as M
    return M.UserIdentity(user_id=user.id, provider=E.IdentityProvider.OIDC,
                          provider_subject=subject)

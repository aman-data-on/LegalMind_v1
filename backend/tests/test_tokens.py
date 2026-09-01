"""Stateless JWT session tokens — `AM-36` (AB-8, locked 2026-09-01).

`AM-36` amends four of OD-9's five session lines on the owner's explicit
instruction, against the implementing engineer's recorded advice. These tests
exist to hold the amendment to the bounds it set for itself, because that is all
that stands between "a permitted mechanism" and "authority in a bearer token the
server cannot withdraw".

The one that matters most is `test_a_signed_token_claiming_super_roles_grants_nothing`.
If that ever fails, the amendment has become the thing OD-9's *unamended* hard
rule forbids, and the fix is the code, never the test.

The accepted cost is also asserted, in `test_the_accepted_degradation_is_real` —
not hidden. A suite that only proves the good properties of a decision like this
is a worse record than one that states the price.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from legalmind.api.context import SESSION_COOKIE
from legalmind.domain import enums as E
from legalmind.security import tokens
from legalmind.security.sessions import revoke_all_for_user

SECRET = "a" * 48


@pytest.fixture
def signing(monkeypatch):
    monkeypatch.setenv("LEGALMIND_JWT_SECRET", SECRET)


def _segments(token: str) -> tuple[dict, dict, str]:
    head, claims, signature = token.split(".")

    def decode(segment: str) -> dict:
        return json.loads(base64.urlsafe_b64decode(
            segment + "=" * (-len(segment) % 4)))

    return decode(head), decode(claims), signature


def _reassemble(header: dict, claims: dict, signature: str) -> str:
    def encode(payload: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        ).decode().rstrip("=")
    return f"{encode(header)}.{encode(claims)}.{signature}"


# =====================================================================
# `AM-36` t2 — what the token carries
# =====================================================================
def test_the_payload_carries_exactly_what_the_amendment_specifies(signing):
    user_id = uuid4()
    token = tokens.issue(user_id=user_id, email="analyst@leapswitch.com",
                         roles=["USER", "LEGAL_REVIEWER"])
    _, claims, _ = _segments(token)

    assert claims["sub"] == str(user_id)
    assert claims["email"] == "analyst@leapswitch.com"
    assert claims["roles"] == ["USER", "LEGAL_REVIEWER"]
    assert claims["iss"] == "legalmind" and claims["aud"] == "legalmind-api"
    assert claims["exp"] - claims["iat"] == 24 * 3600      # t2's 24 hours
    assert claims["jti"]        # identifies a token in an incident without logging it


def test_no_credential_and_no_legal_position_is_ever_in_the_payload(signing):
    """Locked 53.3 / LEGAL-02 as an egress rule — the token reaches the browser, so
    what it carries has left the server."""
    token = tokens.issue(user_id=uuid4(), email="analyst@leapswitch.com",
                         roles=["USER"])
    _, claims, _ = _segments(token)
    for forbidden in ("credential_hash", "password", "standard", "threshold",
                      "rule_outcome", "finding", "evaluation", "clause"):
        assert forbidden not in json.dumps(claims).lower()


# =====================================================================
# `AM-36` t5 — no algorithm confusion, no weak-key downgrade
# =====================================================================
def test_alg_none_is_refused(signing):
    """The canonical JWT attack. Refused because the header is COMPARED against a
    fixed value, never used to select an algorithm."""
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])
    header, claims, signature = _segments(token)
    header["alg"] = "none"
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(_reassemble(header, claims, ""))
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(_reassemble(header, claims, signature))


@pytest.mark.parametrize("algorithm", ["RS256", "HS512", "ES256", "HS256 ", "hs256"])
def test_any_other_declared_algorithm_is_refused(signing, algorithm):
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])
    header, claims, signature = _segments(token)
    header["alg"] = algorithm
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(_reassemble(header, claims, signature))


def test_a_tampered_payload_is_refused_before_any_claim_is_read(signing):
    """Signature first, by construction: a forged payload never reaches the expiry
    or role logic at all."""
    token = tokens.issue(user_id=uuid4(), email="a@leapswitch.com", roles=["USER"])
    header, claims, signature = _segments(token)
    claims["roles"] = ["SUPER_ADMIN", "LEGAL_DECISION_AUTHORITY"]
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(_reassemble(header, claims, signature))


def test_a_token_signed_with_another_key_is_refused(signing, monkeypatch):
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])
    monkeypatch.setenv("LEGALMIND_JWT_SECRET", "b" * 48)
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(token)


def test_an_absent_key_refuses_to_issue_AND_to_verify(monkeypatch, signing):
    """t5 forbids a downgrade. Refusing to verify matters as much as refusing to
    issue: a process with no key must not accept anything, least of all an
    unsigned token."""
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])
    monkeypatch.delenv("LEGALMIND_JWT_SECRET", raising=False)

    assert tokens.configured() is False
    with pytest.raises(tokens.TokenRefused):
        tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(token)


def test_a_short_key_is_refused_rather_than_stretched(monkeypatch):
    """Below 256 bits an offline attack on the MAC is the cheapest way in, which
    would make every other control here decorative."""
    monkeypatch.setenv("LEGALMIND_JWT_SECRET", "short")
    assert tokens.configured() is False
    with pytest.raises(tokens.TokenRefused):
        tokens.issue(user_id=uuid4(), email="a@b.com", roles=[])


# =====================================================================
# Expiry and lifetime
# =====================================================================
def test_an_expired_token_is_refused(signing):
    past = datetime.now(UTC) - timedelta(hours=25)
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[], now=past)
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(token)


def test_a_future_dated_token_is_refused(signing):
    future = datetime.now(UTC) + timedelta(hours=2)
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[], now=future)
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(token)


def test_a_correctly_signed_token_claiming_a_longer_life_is_refused(signing):
    """`AM-36` t2 fixes 24 hours. This is the case where our own key was used but the
    lifetime was stretched — so the signature check cannot catch it and the
    lifetime bound has to."""
    token = tokens.issue(user_id=uuid4(), email="a@b.com", roles=[],
                         lifetime=timedelta(days=90))
    with pytest.raises(tokens.TokenRefused):
        tokens.verify(token)


def test_a_refusal_never_names_its_cause_to_the_caller(signing):
    """S-7 — the operator gets `reason`; the user gets one fixed sentence."""
    refusal = tokens.TokenRefused("signature mismatch on a forged admin token")
    assert str(refusal) == "no valid session"
    assert refusal.reason == "signature mismatch on a forged admin token"


# =====================================================================
# `AM-36` t3 — THE LOAD-BEARING TESTS. Authority is never taken from the token.
# =====================================================================
def _token_only(api, token: str) -> None:
    """Present the token the way a browser would, and NOTHING else."""
    api.cookies.clear()
    api.cookies.set(tokens.TOKEN_COOKIE, token)


def test_a_signed_token_claiming_super_roles_grants_nothing(
        api, db, user, signing, seeded):
    """If this test ever fails, `AM-36` has become the thing OD-9's unamended hard
    rule forbids: authority in a credential the server cannot withdraw.

    The token is signed with OUR key and is entirely valid. Its `roles` claim
    asserts every role in the system. The user holds none of them in the database.
    The permission array must be empty.
    """
    token = tokens.issue(user_id=user.id, email=user.email,
                         roles=["SUPER_ADMIN", "LEGAL_ADMIN", "LEGAL_REVIEWER",
                                "LEGAL_DECISION_AUTHORITY", "USER"])
    _token_only(api, token)

    body = api.get("/api/v1/auth/session").json()["data"]
    assert body["user_id"] == str(user.id)
    assert body["permissions"] == []


def test_the_token_cannot_reach_a_legal_decision(api, db, user, signing, seeded):
    """`SEC-02` / `ROLE-05` / OD-9's hard rule, through the amended mechanism.

    The most dangerous permission in the system, claimed by a validly signed
    token, on an account that does not hold it.
    """
    from legalmind.security import permissions as P

    token = tokens.issue(user_id=user.id, email=user.email,
                         roles=["LEGAL_DECISION_AUTHORITY"])
    _token_only(api, token)
    granted = set(api.get("/api/v1/auth/session").json()["data"]["permissions"])
    assert P.LEGAL_DECISION not in granted
    assert P.LEGAL_APPROVE_CUSTOMIZATION not in granted


def test_the_email_claim_is_not_trusted_either(api, db, user, signing, seeded):
    """A token whose `email` claims another identity resolves as its `sub`, not as
    the address — otherwise the claim would be an impersonation vector."""
    token = tokens.issue(user_id=user.id, email="admin@leapswitch.com", roles=[])
    _token_only(api, token)
    assert api.get("/api/v1/auth/session").json()["data"]["email"] == user.email


def test_a_role_revoked_in_the_database_takes_effect_on_the_next_request(
        api, db, user, signing, seeded):
    """`AM-36` t4(a) — the degradation is to identity, not to authority.

    The token is minted while the user holds a role, then the role is removed. The
    very next request must reflect the removal, despite the token still asserting
    it for another 24 hours.
    """
    from legalmind.db import models as M
    from legalmind.security import permissions as P

    role = db.query(M.Role).filter_by(code="USER").one()
    db.add(M.UserRole(user_id=user.id, role_id=role.id))
    db.flush()

    token = tokens.issue(user_id=user.id, email=user.email, roles=["USER"])
    _token_only(api, token)
    assert P.CONTRACT_VIEW in api.get("/api/v1/auth/session").json()["data"]["permissions"]

    db.query(M.UserRole).filter_by(user_id=user.id, role_id=role.id).delete()
    db.flush()

    assert api.get("/api/v1/auth/session").json()["data"]["permissions"] == []


def test_a_disabled_account_is_refused_despite_a_live_token(
        api, db, user, signing, seeded):
    """`AM-36` t4(b) — the one thing that must not wait 24 hours.

    47.1.3's status gating applies to EVERY mechanism, and amending the session
    model must not open a route around a disabled account.
    """
    token = tokens.issue(user_id=user.id, email=user.email, roles=["USER"])
    user.status = E.UserStatus.DISABLED
    db.flush()
    _token_only(api, token)
    assert api.get("/api/v1/auth/session").status_code == 401


def test_a_token_for_a_deleted_user_is_refused(api, db, signing, seeded):
    token = tokens.issue(user_id=uuid4(), email="ghost@leapswitch.com",
                         roles=["SUPER_ADMIN"])
    _token_only(api, token)
    assert api.get("/api/v1/auth/session").status_code == 401


# =====================================================================
# Precedence, revocation, and the cost the owner accepted
# =====================================================================
def test_the_revocable_session_wins_when_both_cookies_are_present(
        api, db, user, signing, seeded):
    """Deliberate ordering: honouring the session means an administrator's
    revocation still bites on a normal browser sign-in."""
    from legalmind.security.sessions import create_session

    session = create_session(db, user)
    token = tokens.issue(user_id=user.id, email=user.email, roles=[])
    api.cookies.set(SESSION_COOKIE, str(session.id))
    api.cookies.set(tokens.TOKEN_COOKIE, token)

    body = api.get("/api/v1/auth/session").json()["data"]
    assert body["session_id"] == str(session.id)      # the session, not the token

    revoke_all_for_user(db, user.id, reason="test")
    db.flush()
    assert api.get("/api/v1/auth/session").status_code == 401


def test_the_accepted_degradation_is_real(api, db, user, signing, seeded):
    """⚠️ This test asserts the COST of `AM-36`, not a benefit — deliberately, so the
    suite records the price rather than hiding it.

    Every server-side session is revoked. A token issued beforehand still
    authenticates, because there is no server-side list that can stop it. This is
    exactly what OD-9's "Revocation — immediate, server-side" prevented and what
    the owner chose to give up on 2026-09-01.

    If a future decision restores immediate revocation, THIS is the test that
    should start failing, and it should then be deleted rather than fixed.
    """
    token = tokens.issue(user_id=user.id, email=user.email, roles=[])
    revoke_all_for_user(db, user.id, reason="administrator revoked everything")
    db.flush()

    _token_only(api, token)
    assert api.get("/api/v1/auth/session").status_code == 200


# =====================================================================
# `AM-36` t6 — the token is a credential
# =====================================================================
def test_the_token_cookie_carries_the_locked_S3_attributes(
        api, db, configured, monkeypatch, signing, user, seeded):
    """S-3 is unchanged by the amendment: t6 requires exactly these attributes."""
    from tests.test_oidc import CALLBACK, _begin, _identity, _stub_token_endpoint

    db.add(_identity(user))
    user.email = "analyst@leapswitch.com"
    db.flush()
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    response = api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    header = next(c for c in response.headers.get_list("set-cookie")
                  if c.startswith(f"{tokens.TOKEN_COOKIE}=")).lower()
    assert "httponly" in header and "secure" in header
    # SameSite=Lax is required for OIDC callback which is a cross-site top-level
    # navigation from the IdP; Strict would withhold the cookie on the callback.
    # t6 covers the Cookie attributes but the SameSite value depends on context.
    assert "samesite=lax" in header
    # 24 hours, per t2.
    assert "max-age=86400" in header


def test_the_token_is_never_in_the_response_body_or_a_log_line(
        api, db, configured, monkeypatch, signing, user, seeded, capsys):
    """t6 — cookie only. A token in a body or a log is a credential written down."""
    from tests.test_oidc import CALLBACK, _begin, _identity, _stub_token_endpoint

    db.add(_identity(user))
    db.flush()
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    response = api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    token = next(c for c in response.headers.get_list("set-cookie")
                 if c.startswith(f"{tokens.TOKEN_COOKIE}=")).split("=", 1)[1]
    token_value = token.split(";")[0]

    assert token_value not in response.text
    assert token_value not in capsys.readouterr().out


def test_the_redactor_drops_a_token_whatever_the_key_is_called(signing):
    """Belt and braces on t6. The `eyJ…` shape is caught regardless of key name, so
    a future log line that carelessly includes one is still safe."""
    from legalmind.observability.redaction import redact_fields

    token = tokens.issue(user_id=uuid4(), email="a@leapswitch.com", roles=["USER"])
    assert redact_fields({tokens.TOKEN_COOKIE: token}) == {}
    assert redact_fields({"anything_at_all": token}) == {"anything_at_all":
                                                         "[redacted]"}


def test_signing_out_clears_the_token(api, db, user, signing, seeded):
    """`AM-36` t4 — the token cannot be revoked server-side, so clearing it from the
    browser is the only thing logout CAN do, and leaving it would mean an explicit
    sign-out left a live 24-hour credential behind."""
    from legalmind.security.sessions import create_session

    session = create_session(db, user)
    api.cookies.set(SESSION_COOKIE, str(session.id))
    api.cookies.set(tokens.TOKEN_COOKIE,
                    tokens.issue(user_id=user.id, email=user.email, roles=[]))
    csrf = api.cookies.get("legalmind_csrf") or "x"
    api.cookies.set("legalmind_csrf", csrf)

    response = api.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    cleared = [c for c in response.headers.get_list("set-cookie")
               if c.startswith(f"{tokens.TOKEN_COOKIE}=")]
    assert cleared, "logout must clear the token cookie"


def test_a_sign_in_still_completes_when_no_signing_key_is_configured(
        api, db, configured, monkeypatch, user, seeded):
    """t5 forbids a downgrade, so an unset key means NO token — not a weak one, and
    not a failed sign-in. The session cookie has already established the caller."""
    from tests.test_oidc import CALLBACK, _begin, _identity, _stub_token_endpoint

    monkeypatch.delenv("LEGALMIND_JWT_SECRET", raising=False)
    db.add(_identity(user))
    db.flush()
    state, nonce = _begin(api)
    _stub_token_endpoint(monkeypatch, nonce_from=lambda: nonce)
    response = api.get(f"{CALLBACK}?code=c&state={state}", follow_redirects=False)

    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{SESSION_COOKIE}=") for c in cookies)
    assert not any(c.startswith(f"{tokens.TOKEN_COOKIE}=") for c in cookies)
    assert api.get("/api/v1/auth/session").status_code == 200

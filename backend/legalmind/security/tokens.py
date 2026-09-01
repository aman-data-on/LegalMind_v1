"""Stateless JWT session tokens — `AM-36` (AB-8, locked 2026-09-01).

`AM-36` amends OD-9 to permit a stateless JWT for the OIDC path. Read that record
before changing anything here; in particular read its **recorded dissent**, which
explains what this mechanism gives up and why the two guards below exist.

The three properties this module is arranged to hold
----------------------------------------------------
**`AM-36` t3 — the token's authority is advisory and is never enforced.** The
``roles`` claim exists because the owner specified it. Nothing reads it to make a
decision: ``get_principal`` extracts ``sub`` and discards the rest, and every
permission check still resolves from the database on the request (S-1). A code path
that authorized from this claim would put authority in a bearer credential the
server cannot withdraw — which OD-9's *unamended* hard rule forbids. There is a
test that fails if the claim is ever consulted.

**`AM-36` t5 — no weak-key and no algorithm-confusion path.** The classic JWT
failures are a token declaring ``alg: none``, a token declaring a different
algorithm than the verifier expected, and a verifier that trusts the token's own
header. None is reachable here: this module computes exactly one MAC,
HMAC-SHA256, and compares it in constant time. The incoming header is *validated
against a fixed expected value*, never used to select an algorithm. An absent or
short key means refuse-to-issue **and** refuse-to-verify, never a downgrade.

**`AM-36` t6 — the token is a credential.** HttpOnly, Secure, SameSite=Strict
cookie only. Never a response body, never a URL, never a log line. ``TOKEN_COOKIE``
is in the redactor's forbidden set for the same reason ``credential_hash`` is.

Why no JWT library, though `AM-36` t7 authorizes one
----------------------------------------------------
It is not needed, and not taking it is the better outcome. HS256 verification is
one stdlib HMAC and a constant-time compare; what a JWT library adds beyond that
is multi-algorithm negotiation and JWKS fetching — precisely the machinery behind
the algorithm-confusion class of bug, and precisely what this module refuses to
have. The same reasoning already applies elsewhere in this codebase: `AM-30`'s
generation adapter uses stdlib ``urllib`` rather than a provider SDK. So t7's
authorization goes deliberately unused, and rule 19's dependency surface does not
grow. (`PyJWT` is also un-installable in this environment under PEP 668, which
would have made the authorized route a deployment liability besides.)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from legalmind.security.errors import Unauthenticated

# `AM-36` t2 — the owner specified 24 hours. This is the amendment's number, not a
# tunable: shortening it is a security improvement and lengthening it is a
# regression, so either is a decision rather than configuration.
TOKEN_LIFETIME = timedelta(hours=24)

TOKEN_COOKIE = "legalmind_token"

# `AM-36` t5 — pinned at both ends. The header is compared against this exact
# object; it is never parsed to decide what to do.
_ALGORITHM = "HS256"
_HEADER = {"alg": _ALGORITHM, "typ": "JWT"}
_ISSUER = "legalmind"
_AUDIENCE = "legalmind-api"

# 256 bits. Below this an offline attack on the MAC is the cheapest way in, which
# would make every other control here decorative.
MIN_SECRET_BYTES = 32


class TokenRefused(Unauthenticated):
    """A token that must not be honoured.

    Subclasses ``Unauthenticated`` so a forgotten catch still renders the one
    fixed, non-disclosing 401 body (S-7) rather than a 500 naming the cause.
    """

    def __init__(self, reason: str):
        super().__init__("no valid session")
        self.reason = reason


@dataclass(frozen=True)
class TokenClaims:
    """What the token asserted.

    ``roles`` is carried because `AM-36` t2 requires it and is **advisory**
    (t3). It is deliberately not a set and not resolved against the permission
    catalogue — nothing here should make it convenient to authorize from.
    """

    user_id: UUID
    email: str
    roles: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def signing_key() -> bytes:
    """`AM-36` t5 — a deployment secret, never defaulted.

    Raises rather than returning a fallback. A generated-per-process key would be
    worse than no key: tokens would silently stop verifying after a restart, and
    the failure would look like a session bug rather than a missing secret.
    """
    raw = os.environ.get("LEGALMIND_JWT_SECRET", "")
    if not raw:
        raise TokenRefused("LEGALMIND_JWT_SECRET is not set")
    key = raw.encode("utf-8")
    if len(key) < MIN_SECRET_BYTES:
        raise TokenRefused(
            f"LEGALMIND_JWT_SECRET is {len(key)} bytes; "
            f"at least {MIN_SECRET_BYTES} are required")
    return key


def configured() -> bool:
    """Whether tokens can be issued at all. Used by the preflight and by the
    callback, which must not half-sign a session."""
    try:
        signing_key()
    except TokenRefused:
        return False
    return True


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(signing_key(), payload, hashlib.sha256).digest())


def issue(*, user_id: UUID, email: str, roles: tuple[str, ...] | list[str],
          lifetime: timedelta = TOKEN_LIFETIME,
          now: datetime | None = None) -> str:
    """Mint a signed token. `AM-36` t2."""
    issued = now or datetime.now(UTC)
    claims = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": str(user_id),
        "email": email,
        "roles": list(roles),
        "iat": int(issued.timestamp()),
        "exp": int((issued + lifetime).timestamp()),
        # A unique id per token, so a specific token is identifiable in an
        # incident without the token itself ever being written down.
        "jti": secrets.token_urlsafe(16),
    }
    header_segment = _b64(json.dumps(_HEADER, separators=(",", ":"),
                                     sort_keys=True).encode())
    claims_segment = _b64(json.dumps(claims, separators=(",", ":"),
                                     sort_keys=True).encode())
    body = f"{header_segment}.{claims_segment}".encode("ascii")
    return f"{header_segment}.{claims_segment}.{_sign(body)}"


def verify(token: str, *, now: datetime | None = None) -> TokenClaims:
    """Validate a token and return its claims. Refuses on anything unexpected.

    Order is deliberate: the signature is checked BEFORE any claim is read, so a
    forged payload never reaches the parsing or expiry logic at all.
    """
    if not token or token.count(".") != 2:
        raise TokenRefused("not a three-part token")
    header_segment, claims_segment, signature = token.split(".")

    body = f"{header_segment}.{claims_segment}".encode("ascii")
    try:
        expected = _sign(body)
    except TokenRefused:
        raise                                  # no key: refuse, never downgrade
    if not hmac.compare_digest(signature, expected):
        raise TokenRefused("signature mismatch")

    # Only now is anything from the token read. The header is COMPARED, never
    # used to choose an algorithm — this is the whole defence against algorithm
    # confusion, including `alg: none`.
    try:
        header = json.loads(_unb64(header_segment))
        claims = json.loads(_unb64(claims_segment))
    except Exception as cause:
        raise TokenRefused("unreadable token segments") from cause
    if header != _HEADER:
        raise TokenRefused(f"unexpected header {header!r}")
    if not isinstance(claims, dict):
        raise TokenRefused("claims are not an object")

    if claims.get("iss") != _ISSUER:
        raise TokenRefused("issuer mismatch")
    if claims.get("aud") != _AUDIENCE:
        raise TokenRefused("audience mismatch")

    moment = now or datetime.now(UTC)
    try:
        expires = datetime.fromtimestamp(float(claims["exp"]), UTC)
        issued = datetime.fromtimestamp(float(claims["iat"]), UTC)
    except (KeyError, TypeError, ValueError, OverflowError) as cause:
        raise TokenRefused("missing or unreadable iat/exp") from cause
    if expires <= moment:
        raise TokenRefused("token has expired")
    # A token minted in the future is a clock problem or a forgery attempt; either
    # way it is not something to honour. Small allowance for skew between hosts.
    if issued > moment + timedelta(minutes=5):
        raise TokenRefused("token issued in the future")
    # `AM-36` t2 fixes the lifetime. A token claiming a longer one was not minted
    # by this code, whatever its signature says.
    if expires - issued > TOKEN_LIFETIME + timedelta(minutes=5):
        raise TokenRefused("token lifetime exceeds the amended maximum")

    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as cause:
        raise TokenRefused("missing or unreadable subject") from cause

    roles = claims.get("roles")
    return TokenClaims(
        user_id=user_id,
        email=str(claims.get("email") or ""),
        # Advisory (t3). Normalised only so the type is predictable.
        roles=tuple(str(r) for r in roles) if isinstance(roles, list) else (),
        issued_at=issued,
        expires_at=expires,
    )

"""Password hashing for the Step 47 fallback path only.

Locked 47.1.3 makes corporate SSO via OIDC primary and password login "a
controlled fallback", and explicitly defers "password policy specifics, reset-token
flow and mail transport" to the implementation phase.

``hashlib.scrypt`` is used rather than argon2 or bcrypt because both would be a
new dependency, and locked rule 19 requires approval for one. scrypt is memory-hard
and in the standard library, so the fallback path needs no new technology. If the
owner prefers argon2id, that is a dependency approval and a hash-format migration,
not a redesign — which is why the format below is self-describing.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCHEME = "scrypt"
_N = 2 ** 14          # 16 MiB per hash at r=8 — scrypt's "interactive" setting
_R = 8
_P = 1
_DKLEN = 64
# OpenSSL's own default ceiling is 32 MiB and it raises rather than degrading.
# Stated explicitly so the cost parameters above are the only thing that decides
# what this costs, and a future increase fails at the parameter rather than here.
_MAXMEM = 128 * 1024 * 1024

# Verified against when no account exists, so an unknown account costs the same
# work as a wrong password. S-7 forbids enumeration, and a timing difference is a
# way to enumerate.
_DUMMY = None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                            n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAXMEM)
    return f"{_SCHEME}${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Constant-time comparison; ``None`` still does the work (S-7)."""
    global _DUMMY
    if encoded is None:
        if _DUMMY is None:
            _DUMMY = hash_password(secrets.token_urlsafe(16))
        verify_password(password, _DUMMY)
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if scheme != _SCHEME:
            return False
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(digest_hex)),
            maxmem=_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest_hex)

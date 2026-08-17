"""What must never be logged — locked 53.3.

Locked 53.3 is a prohibition, and a prohibition that relies on every caller
remembering it will be violated eventually. So this module makes the logger
*incapable* of emitting the forbidden classes rather than merely discouraging it:
every field passes through `redact_fields` before it can reach a log record, and
there is no bypass in the logging API.

The four classes, from 53.3 verbatim:

* Credentials, ``credential_hash``, session identifiers, OIDC tokens or
  authorization codes (S-4).
* Contract text or extracted clause content — "evidence lives in the document
  store, not in logs".
* Internal legal position: thresholds, rule outcomes, ``rule_configuration``
  (LEGAL-02).
* Anything that turns a failed-login record into an enumeration oracle (S-7).

Locked 53.3's closing line is the design rule: **"Log records carry identifiers, not
content."** Hence the length guard below — an identifier is short, and contract text
is not, so an over-long value is treated as content regardless of what it is called.
"""

from __future__ import annotations

import re
from typing import Any

from legalmind.security.authorization import LEGAL_POSITION_FIELDS

REDACTED = "[redacted]"

# --- S-4: credential and session material --------------------------------
_SECRET_KEYS = frozenset({
    "password", "new_password", "current_password",
    "credential", "credential_hash", "secret", "client_secret",
    "token", "access_token", "refresh_token", "id_token", "bearer",
    "authorization", "cookie", "set-cookie", "csrf", "csrf_token",
    "session", "session_id", "sessionid",
    "code", "authorization_code", "state", "nonce",
    "api_key", "apikey", "private_key",
})

# --- 53.3: contract text and extracted clause content --------------------
# Evidence lives in the document store; a log line references it by id.
_CONTENT_KEYS = frozenset({
    "content", "original_content", "clause", "clause_text", "text", "body",
    "paragraph", "evidence_content", "extract", "document_text", "snippet",
    "justification",          # a Legal Decision's reason is legal content
    "reason",                 # an escalation's reason likewise
    # Audit payloads. Listed explicitly because `state` is exact-match only (see
    # `_EXACT_ONLY_KEYS`), so no suffix rule would catch these.
    "before_state", "after_state",
})

# --- S-7: no account enumeration -----------------------------------------
# An email in a failed-login log line is exactly the oracle S-7 forbids. Dropped
# unconditionally rather than only on the failure path, because a log pipeline is
# searchable and the two paths end up in the same index.
_ENUMERATION_KEYS = frozenset({"email", "username", "user_email", "account"})

# --- LEGAL-02 / 53.3: internal legal position ----------------------------
# Reuses the API's single source of truth so the two cannot drift, plus the names
# 53.3 adds that never appear in an API payload.
_LEGAL_POSITION_KEYS = frozenset(LEGAL_POSITION_FIELDS) | {
    "threshold", "thresholds", "acceptable_max", "approval_required_above",
    "company_standard", "legal_rule", "preferred", "cap_value", "expected",
}

FORBIDDEN_KEYS = (
    _SECRET_KEYS | _CONTENT_KEYS | _ENUMERATION_KEYS | _LEGAL_POSITION_KEYS
)

# An identifier is short. Anything longer is treated as content (53.3's "log records
# carry identifiers, not content"), whatever the caller named it.
MAX_VALUE_LENGTH = 200

# Values that look like credential material regardless of their key.
_SECRET_SHAPED = re.compile(
    r"(scrypt\$|bcrypt\$|\$argon2|-----BEGIN|eyJ[A-Za-z0-9_-]{10,}\.)")


# Words that mean "secret" wherever they appear in a key, so `password_hash` and
# `oidc_id_token` are caught without needing to be enumerated.
#
# Deliberately narrow. An earlier version also matched a forbidden name as a *prefix*
# of any key, which dropped `clause_count` — a count, not content. The lesson is that
# over-broad redaction is its own failure: it silently removes the operational signal
# 53.5 asks for, and a log pipeline missing its counts is no more useful than one
# leaking content. So positional matching is limited to words that cannot appear
# innocently.
_SECRET_TOKENS = frozenset({
    "password", "secret", "credential", "token", "apikey", "passphrase",
})

# Names that are dangerous only as a WHOLE key, never as a suffix, because the word
# is ordinary in this domain:
#
#   state   OIDC's CSRF nonce — but `mapping_state`, `review_state`, `after_state`
#   code    an OIDC authorization code — but `requirement_code`, `error_code`
#   nonce   OIDC only
#
# Matching these as suffixes dropped `mapping_state`, which is a locked axis value
# and one of the more useful things a log line can carry. `after_state` and
# `before_state` are therefore listed explicitly below rather than relying on a
# suffix rule that would sweep up the rest.
_EXACT_ONLY_KEYS = frozenset({"state", "code", "nonce"})

_SUFFIX_MATCHED_KEYS = FORBIDDEN_KEYS - _EXACT_ONLY_KEYS


def _is_forbidden_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in FORBIDDEN_KEYS:
        return True
    tokens = set(normalized.split("_"))
    if tokens & _SECRET_TOKENS:
        return True
    # Suffix form only: `user_password`, `raw_content`, `evidence_text`. NOT prefix,
    # and not for `_EXACT_ONLY_KEYS` — see the notes above.
    return any(normalized.endswith(f"_{f}") for f in _SUFFIX_MATCHED_KEYS)


def redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to log — locked 53.3.

    Forbidden keys are **dropped entirely** rather than replaced with a marker where
    the key itself would disclose something: a log line reading
    ``rule_outcome=[redacted]`` still tells a reader that an internal legal position
    exists for this object, which is the disclosure LEGAL-02 prevents. Values that
    are merely too long are marked, because the field name is harmless and the
    truncation is useful signal.
    """
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        if _is_forbidden_key(key):
            continue                                  # dropped, not marked
        if isinstance(value, dict):
            nested = redact_fields(value)
            if nested:
                safe[key] = nested
            continue
        if isinstance(value, (list, tuple)):
            # A list of identifiers is fine; a list of clause text is not. Recurse
            # through the same rules by treating each element as a value.
            safe[key] = [_redact_value(v) for v in value]
            continue
        safe[key] = _redact_value(value)
    return safe


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_fields(value)
    if not isinstance(value, str):
        return value
    if _SECRET_SHAPED.search(value):
        return REDACTED
    if len(value) > MAX_VALUE_LENGTH:
        # Length alone, not content inspection: a long string in a log line is
        # content by 53.3's definition regardless of what it holds.
        return f"[{len(value)} chars omitted]"
    return value

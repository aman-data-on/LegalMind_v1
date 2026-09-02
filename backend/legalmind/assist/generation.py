"""Generation behind one interface — `AM-26` r1, `AM-30` t1–t10, `AM-31`.

THE ONLY MODULE IN THE APPLICATION PERMITTED TO REACH THE NETWORK. `AM-30` t1 makes the
generation call the sole egress, `tests/test_import_boundaries.py` names this module in
`EGRESS_ALLOWED` citing that record, and adding network imports anywhere else fails CI.

`AM-26` r1: callers know `generate()` — not which provider, not that a provider is
hosted. Reverting to a local model is a change inside this file plus configuration.

--------------------------------------------------------------------------
The AM-31 gate, exactly as locked
--------------------------------------------------------------------------
g1  Real counterparty contract text must NOT reach the provider until its no-training
    and data-retention terms are confirmed in writing.
g2  Enforcement is mechanical and DEFAULT-CLOSED.
g3  Released only by a FURTHER APPENDED RECORD — never a flag, env var or review.
g4  Status as of 2026-08-25: CLOSED. RELEASED 2026-08-31 by the appended record
    "AM-31 GATE RELEASE" (owner's written terms confirmation of the same day;
    provider Google Gemini API, paid tier, gemini-3.6-flash).
g5  The mechanism composes with locked 55.3's environment separation: development and
    staging are synthetic-only environments; production is where real contracts live.

The composition of g5 with g2/g3 gives the mechanism below: while the gate constant is
CLOSED, egress is refused outright in the production environment — the only environment
real counterparty text inhabits — and permitted in development/staging, which 55.3
already constrains to synthetic material. Opening it requires editing AM31_GATE in this
file, which is a reviewed code change that must land alongside the appended lock record
`tests/test_generation.py` checks it against. An environment variable deliberately
cannot open it (g3).

--------------------------------------------------------------------------
What is sent, and what never is (AM-30 t2-t4)
--------------------------------------------------------------------------
The requester's question, the retrieved chunk texts for that one request, and the
prompt template. Never a whole document. Never a Company Standard value, Legal Rule,
threshold or Rule Outcome — enforced by `_forbidden_payload_check`, which reuses the
locked 53.3 redaction vocabulary as an egress screen (t3: LEGAL-02 is an egress rule).
Never a counterparty, signatory, contract, user or organizational identifier (t4) —
chunk text is document content and is permitted; the check bars the *structured* fields.
Every call is recorded in audit_events with the model identity, prompt version and a
payload SHA-256 — never the payload (t5).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from legalmind.observability.logs import log_event

# --------------------------------------------------------------------------
# AM-31 g4 — the gate. A constant, not configuration: g3 forbids a flag from opening
# it. Change ONLY alongside the appended lock record that releases the gate, carrying
# the provider, tier and date of the written confirmation.
# --------------------------------------------------------------------------
AM31_GATE = "RELEASED-2026-08-31"

# AM-30 t7: a pinned model identifier — a floating alias is not a pin, and
# `generate()` refuses "latest". 2026-08-31: "gemini-2.5-flash" was retired for
# new accounts (the provider's own 404 said to move to gemini-3.6-flash); AM-30
# locks the FAMILY (Gemini Flash), not the version — "No version string is
# locked. t7 governs." The change is recorded in AUTO_MODE_DECISIONS.md, and the
# model identity is recorded against every answer (AM-26 r4), so which version
# produced which answer stays a fact, never a guess.
DEFAULT_MODEL = "gemini-3.6-flash"

_ENDPOINT_TEMPLATE = ("https://generativelanguage.googleapis.com/v1beta/models/"
                      "{model}:generateContent")

PROMPT_VERSION = "grounded-answer-1"
PROMPT_TEMPLATE = """You are a legal document assistant. Answer the question using ONLY \
the numbered evidence excerpts below. Rules, all mandatory:
1. Every sentence of your answer MUST end with citation markers like [1] or [2][3] \
naming the excerpt(s) that support it.
2. Use nothing but the excerpts. No outside knowledge, no assumptions, no legal advice.
3. If the excerpts do not answer the question, reply exactly: NOT FOUND
4. Never state whether anything complies with any standard or policy.

EVIDENCE:
{evidence}

QUESTION: {question}

ANSWER:"""


class GenerationRefused(Exception):
    """Raised when the egress gate or a payload screen refuses the call."""


class GenerationUnavailable(Exception):
    """Raised when the provider cannot be reached or returns an error."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    prompt_version: str
    payload_sha256: str
    latency_ms: int


# A credential that is present but is obviously not a credential.
#
# 2026-09-01: `/root/.legalmind.env` held the literal three characters `***` for
# hours — a masking command written back over the file instead of piped to stdout.
# Everything downstream reported the key as CONFIGURED, the preflight said PASS,
# and the only symptom was Google answering 400 `API_KEY_INVALID` while the
# assist lane degraded silently to "not confident". Two debugging cycles went into
# a problem that was visible in the value itself.
#
# So a placeholder is now treated as ABSENT, not as a key. Absent fails loudly and
# in the right place; a placeholder fails at the provider, four layers away.
_PLACEHOLDERS = frozenset({
    "***", "****", "changeme", "change-me", "todo", "tbd", "xxx",
    "your-api-key", "your_api_key", "redacted", "<redacted>", "none", "null",
    "placeholder", "unset", "paste-key-here", "<paste-key-here>",
})


def is_placeholder_credential(value: str) -> bool:
    """True when a value is filled in but plainly not a real credential.

    Deliberately narrow: an exact match against known placeholders, plus a
    length floor. It does NOT try to validate the provider's key format — a
    guess at that would reject a legitimate key after a provider change, which
    is a worse failure than the one this prevents.
    """
    stripped = value.strip().strip('"').strip("'")
    if not stripped:
        return True
    if stripped.lower() in _PLACEHOLDERS:
        return True
    if set(stripped) <= {"*", "x", "X", "•", "-", "_", "."}:
        return True          # any all-mask string, whatever its length
    # A deliberately LOW floor. The first draft used 20, which rejected
    # `test-not-a-secret` (17) — the suite's own non-secret sentinel — and turned
    # two real assist-lane tests into "no credential configured". The lesson: the
    # length floor is not the mechanism that should be catching things. Masks are
    # caught by shape and by the exact set above; the floor exists only so a
    # one- or two-character slip cannot pass for a credential.
    return len(stripped) < 8


def _api_key() -> str | None:
    raw = os.environ.get("LEGALMIND_GEMINI_API_KEY") or ""
    if is_placeholder_credential(raw):
        return None
    return raw.strip()


def credential_present() -> bool:
    """Whether a usable generation credential is configured.

    Public because the Tier-2 gate needs to distinguish "cannot measure" from
    "measured badly", and reaching into `_api_key` from a tool would couple the
    harness to a private name. Placeholder handling lives in `_api_key`, so this
    answers the question the caller actually has rather than "is the variable
    set" — the distinction that let a literal `***` read as configured for hours
    on 2026-09-01.
    """
    return _api_key() is not None


def _model() -> str:
    return os.environ.get("LEGALMIND_GENERATION_MODEL", DEFAULT_MODEL)


def gate_permits_egress(environment: str) -> tuple[bool, str]:
    """The AM-31 decision, pure so it is trivially testable.

    Returns (permitted, reason). While the gate is CLOSED, production egress is
    refused unconditionally — production is where real counterparty text lives
    (locked 55.3), and g1 forbids exactly that text reaching the provider.
    """
    if AM31_GATE != "CLOSED":
        return True, "gate released by appended record"
    if environment == "production":
        return False, ("AM-31 gate is CLOSED: no written no-training confirmation is "
                       "recorded, so real counterparty material may not egress")
    return True, "non-production environment; synthetic-only material (locked 55.3)"


# Structured internal-legal-position fields that must never appear in an egress
# payload — AM-30 t3 re-erects LEGAL-02 as an egress rule. These are the same names
# the locked 53.3 redactor guards in logs.
_FORBIDDEN_KEYS = ("acceptable_max", "approval_required_above", "rule_outcome",
                   "deviation_outcome", "unlimited_outcome", "legal_rule",
                   "rule_configuration", "credential_hash")


def _forbidden_payload_check(payload: str) -> None:
    lowered = payload.lower()
    for key in _FORBIDDEN_KEYS:
        if key in lowered:
            raise GenerationRefused(
                f"payload contains internal legal-position field {key!r}; "
                "LEGAL-02 governs egress (AM-30 t3)")


def generate(question: str, evidence: list[str], *,
             environment: str, request_id: str | None = None) -> GenerationResult:
    """One grounded generation call — the Ask flow's entry to the single seam.

    Raises GenerationRefused when the gate, the payload screen or configuration
    forbids the call — the caller maps that to the identical user-facing refusal
    (`AM-29` r4). Raises GenerationUnavailable on provider failure.
    """
    numbered = "\n".join(f"[{i}] {text}" for i, text in enumerate(evidence, start=1))
    prompt = PROMPT_TEMPLATE.format(evidence=numbered, question=question)
    return generate_raw(prompt, prompt_version=PROMPT_VERSION,
                        environment=environment, request_id=request_id,
                        evidence_count=len(evidence))


def generate_raw(prompt: str, *, prompt_version: str, environment: str,
                 request_id: str | None = None,
                 evidence_count: int | None = None,
                 max_output_tokens: int = 1024) -> GenerationResult:
    """The transport under every assist-lane prompt. STILL the single egress seam
    (AM-30 t1): every gate, payload screen, pin check and audit-hash rule applies
    identically whatever the prompt — a second prompt shape must never mean a
    second network path.
    """
    import time

    permitted, reason = gate_permits_egress(environment)
    if not permitted:
        raise GenerationRefused(reason)

    key = _api_key()
    if not key:
        raise GenerationRefused(
            "no generation credential is configured (LEGALMIND_GEMINI_API_KEY)")

    model = _model()
    if "latest" in model:
        raise GenerationRefused(
            f"model identifier {model!r} is a floating alias; AM-30 t7 requires a pin")

    _forbidden_payload_check(prompt)

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        # Gemini 3.x Flash are thinking models; unconstrained thinking consumes
        # the output budget before any text is produced (measured: 45 of 50
        # tokens on a one-word reply). MINIMAL keeps the grounded-extraction
        # task deterministic and the answer inside the budget. thinkingBudget:0
        # is refused by 3.6-flash (HTTP 400) — the level form is the one it
        # accepts.
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": max_output_tokens,
                             "thinkingConfig": {"thinkingLevel": "MINIMAL"}},
    }).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()

    request = urllib.request.Request(
        _ENDPOINT_TEMPLATE.format(model=model),
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST")

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            parsed = json.load(response)
    except urllib.error.HTTPError as exc:
        # Status and hash only — never the payload, never the key (53.3, AM-30 t5).
        log_event("assist.generation.failed", level=logging.WARNING,
                  request_id=request_id, model=model, status=str(exc.code),
                  payload_sha256=digest, operational_failure=True)
        raise GenerationUnavailable(f"provider returned HTTP {exc.code}") from exc
    except Exception as exc:
        log_event("assist.generation.failed", level=logging.WARNING,
                  request_id=request_id, model=model, error=type(exc).__name__,
                  payload_sha256=digest, operational_failure=True)
        raise GenerationUnavailable(type(exc).__name__) from exc
    latency_ms = int((time.monotonic() - started) * 1000)

    try:
        text = parsed["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationUnavailable("provider response had no text candidate") from exc

    log_event("assist.generation.completed", request_id=request_id, model=model,
              prompt_version=prompt_version, payload_sha256=digest,
              latency_ms=latency_ms, evidence_count=evidence_count)
    return GenerationResult(text=text, model=model, prompt_version=prompt_version,
                            payload_sha256=digest, latency_ms=latency_ms)

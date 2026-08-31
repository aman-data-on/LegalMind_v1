"""Document-type suggestion — assist lane, human-confirmed (owner, 2026-08-31).

The owner reopened Q9's workflow (this session, recorded in CHANGELOG): the assist
lane may SUGGEST a Step 6 document type from the filename plus the document's own
opening text, but the authoritative ``contract_type`` is only ever written by an
explicit human confirmation in the UI. Q9's substance therefore stands — the
recorded value is 100% human-declared — and AI-01/rule 9 are untouched: nothing
here can reach the ``contracts`` table, and a suggestion is never a Classification,
a Finding or any other authoritative-lane value.

Egress goes through ``generation.generate_raw`` — the same AM-31 gate, the same
LEGAL-02 payload screen, the same audit-hash-only record (AM-30 t5). Every failure
degrades to "not confident": the UI then behaves exactly as it did before this
feature existed (an empty select the user fills in).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import generation
from legalmind.db import models as M
from legalmind.domain.document_types import DOCUMENT_TYPES
from legalmind.observability.logs import log_event

PROMPT_VERSION = "type-suggestion-1"

# The opening of the document is where a legal document names itself. Six evidence
# rows at ~600 characters keeps the payload small and the signal high.
_MAX_EXCERPTS = 6
_EXCERPT_CHARS = 600

PROMPT_TEMPLATE = """You classify a legal document into exactly one type code. \
The permitted codes, and nothing else:
{codes}

Reply with exactly two lines:
TYPE: <one code from the list above, or NONE if you are not certain>
REASON: <one short sentence naming what in the text or filename identifies it>

Answer NONE unless the document's own text clearly identifies its kind. Never \
state whether the document complies with any standard or policy.

FILENAME: {filename}

OPENING TEXT:
{excerpts}
"""


@dataclass(frozen=True)
class TypeSuggestion:
    suggested_type: str | None
    confident: bool
    reason: str


NOT_CONFIDENT = TypeSuggestion(suggested_type=None, confident=False, reason="")


def _parse(text: str) -> TypeSuggestion:
    """Defensive by design: only an exact Step 6 code is ever suggested.

    Anything else — a near-miss, a lowercase code, prose, NONE — degrades to
    not-confident. Mirrors ``validate_document_type``'s no-normalisation rule.
    """
    suggested: str | None = None
    reason = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("TYPE:"):
            suggested = stripped[len("TYPE:"):].strip()
        elif stripped.upper().startswith("REASON:"):
            reason = stripped[len("REASON:"):].strip()
    if suggested not in DOCUMENT_TYPES:
        return NOT_CONFIDENT
    return TypeSuggestion(suggested_type=suggested, confident=True,
                          reason=reason[:300])


def suggest_document_type(db: DBSession, *, document_version_id: UUID,
                          request_id: str | None = None) -> TypeSuggestion:
    """Suggest a Step 6 type for one document version, or say honestly that it
    cannot. Reads evidence; writes ONLY an audit event — no path to ``contracts``.
    """
    version = db.get(M.DocumentVersion, document_version_id)
    if version is None:
        return NOT_CONFIDENT

    rows = db.execute(
        select(M.DocumentEvidence.content)
        .where(M.DocumentEvidence.document_version_id == document_version_id)
        .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                  M.DocumentEvidence.id.asc())
        .limit(_MAX_EXCERPTS)).scalars().all()
    if not rows:
        return NOT_CONFIDENT

    prompt = PROMPT_TEMPLATE.format(
        codes="\n".join(DOCUMENT_TYPES),
        filename=version.original_filename or "(unknown)",
        excerpts="\n---\n".join(r[:_EXCERPT_CHARS] for r in rows))

    try:
        result = generation.generate_raw(
            prompt, prompt_version=PROMPT_VERSION,
            environment=config.environment(), request_id=request_id,
            evidence_count=len(rows), max_output_tokens=200)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.type_suggestion.unavailable", request_id=request_id,
                  cause=type(exc).__name__,
                  document_version_id=str(document_version_id))
        return NOT_CONFIDENT

    # AM-30 t5 — the record of what left the building: model, prompt version,
    # payload hash. Never the payload, and never the document text.
    from legalmind.security import audit as audit_log

    suggestion = _parse(result.text)
    audit_log.record(
        db, action=audit_log.ASSIST_TYPE_SUGGESTION_CALLED,
        entity_type="document_version", entity_id=document_version_id,
        request_id=request_id,
        after={"model": result.model, "prompt_version": result.prompt_version,
               "payload_sha256": result.payload_sha256,
               "suggested_type": suggestion.suggested_type,
               "confident": suggestion.confident})
    return suggestion

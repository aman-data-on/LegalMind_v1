"""Key Obligations extraction — assist lane, descriptive only (owner, 2026-08-31).

What each party has to do, grouped under the DOCUMENT'S OWN role labels, each
line grounded in the evidence row it was read from. Never a Finding, an
Evaluation, a Classification, a Rule Outcome or any judgment (AM-25): the
boundary is enforced mechanically by `guardrails.is_judgment_language` — a
line carrying compliance/risk vocabulary is discarded before persistence —
and by grounding: a line whose source marker does not resolve to a real
evidence row is discarded too (rule 11's spirit in the assist lane).

Egress goes through `generation.generate_raw` — the same AM-31 gate, LEGAL-02
payload screen and audit-hash record as every other assist call. Extraction
runs synchronously in the request, the Ask precedent: one bounded generation
call, no queue. Every outcome — including "the provider is unavailable" — is
recorded as a run row, so "never extracted" and "extracted, nothing found"
stay distinguishable states.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import generation, guardrails
from legalmind.db import models as M
from legalmind.observability.logs import log_event

PROMPT_VERSION = "obligation-extraction-1"

_MAX_ROWS = 120
_ROW_CHARS = 500
_MAX_OBLIGATIONS = 40
_ROLE_HINTS = frozenset({"ORGANIZATION", "COUNTERPARTY", "BOTH", "UNKNOWN"})

PROMPT_TEMPLATE = """You extract party obligations from a legal document. The \
numbered passages below are the document's text.

Reply with one line per obligation, at most {max_obligations}, exactly in this form:
PARTY: <the role label the document itself uses, e.g. Customer> | OBLIGATION: \
<one short sentence stating what that party must do, taken from the text> | [n]

where [n] is the number of the ONE passage the obligation comes from. Rules:
- Use only the passages. Extract, never interpret.
- Never state whether anything complies with, meets, or deviates from any \
standard, policy or expectation. Never assess risk. Never recommend.
- If the document states no party obligations, reply exactly: NONE

PASSAGES:
{passages}
"""


@dataclass(frozen=True)
class ExtractedObligation:
    party_label: str
    obligation_text: str
    evidence_id: UUID


@dataclass(frozen=True)
class ExtractionResult:
    extracted: bool
    obligations: list[ExtractedObligation] = field(default_factory=list)
    error_code: str | None = None


def _parse(text_out: str, evidence_ids: list[UUID]) -> list[ExtractedObligation]:
    """Defensive line parser: only well-formed, grounded, judgment-free lines
    survive. Everything else is dropped, never repaired."""
    import re

    out: list[ExtractedObligation] = []
    line_shape = re.compile(
        r"^PARTY:\s*(?P<party>[^|]{1,200}?)\s*\|\s*OBLIGATION:\s*"
        r"(?P<obligation>[^|]{1,600}?)\s*\|\s*\[(?P<n>\d{1,3})\]\s*$")
    for line in (text_out or "").splitlines():
        match = line_shape.match(line.strip())
        if not match:
            continue
        n = int(match.group("n"))
        if not (1 <= n <= len(evidence_ids)):
            continue  # ungrounded — discarded, never stored
        party = match.group("party").strip()
        obligation = match.group("obligation").strip()
        if not party or not obligation:
            continue
        if guardrails.is_judgment_language(obligation) or \
                guardrails.is_judgment_language(party):
            continue  # a judgment is not an obligation — discarded
        out.append(ExtractedObligation(party_label=party,
                                       obligation_text=obligation,
                                       evidence_id=evidence_ids[n - 1]))
        if len(out) >= _MAX_OBLIGATIONS:
            break
    return out


def _record_run(db: DBSession, document_version_id: UUID, *, status: str,
                model: str | None = None, prompt_version: str | None = None,
                error_code: str | None = None) -> UUID:
    schema = config.assist_schema()
    run_id = uuid.uuid4()
    db.execute(text(f"""
        INSERT INTO "{schema}".obligation_extraction_runs
            (id, document_version_id, status, model_identity, prompt_version,
             error_code)
        VALUES (:i, :d, :s, :m, :p, :e)
    """), {"i": run_id, "d": document_version_id, "s": status, "m": model,
           "p": prompt_version, "e": error_code})
    return run_id


def completed_run_exists(db: DBSession, document_version_id: UUID) -> bool:
    schema = config.assist_schema()
    return db.execute(text(f"""
        SELECT 1 FROM "{schema}".obligation_extraction_runs
         WHERE document_version_id = :d AND status = 'COMPLETED' LIMIT 1
    """), {"d": document_version_id}).first() is not None


def extract_obligations(db: DBSession, *, document_version_id: UUID,
                        request_id: str | None = None) -> ExtractionResult:
    """One extraction pass over a document version's committed evidence.

    Idempotent-by-refusal: a version with a COMPLETED run keeps it — the
    extraction is a property of the immutable version's text, so re-running
    it buys nothing.
    """
    if completed_run_exists(db, document_version_id):
        return ExtractionResult(extracted=True)

    rows = db.execute(
        select(M.DocumentEvidence.id, M.DocumentEvidence.content)
        .where(M.DocumentEvidence.document_version_id == document_version_id)
        .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                  M.DocumentEvidence.id.asc())
        .limit(_MAX_ROWS)).all()
    if not rows:
        _record_run(db, document_version_id, status="FAILED",
                    error_code="NO_EVIDENCE")
        return ExtractionResult(extracted=False, error_code="NO_EVIDENCE")

    evidence_ids = [r[0] for r in rows]
    passages = "\n".join(
        f"[{i}] {r[1][:_ROW_CHARS]}" for i, r in enumerate(rows, start=1))
    prompt = PROMPT_TEMPLATE.format(max_obligations=_MAX_OBLIGATIONS,
                                    passages=passages)

    try:
        result = generation.generate_raw(
            prompt, prompt_version=PROMPT_VERSION,
            environment=config.environment(), request_id=request_id,
            evidence_count=len(rows), max_output_tokens=4096)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.obligations.unavailable", request_id=request_id,
                  cause=type(exc).__name__,
                  document_version_id=str(document_version_id))
        _record_run(db, document_version_id, status="FAILED",
                    error_code=type(exc).__name__)
        return ExtractionResult(extracted=False, error_code=type(exc).__name__)

    # AM-30 t5 — the record of what left the building: hash only, never payload.
    from legalmind.security import audit as audit_log

    audit_log.record(
        db, action=audit_log.ASSIST_GENERATION_CALLED,
        entity_type="document_version", entity_id=document_version_id,
        request_id=request_id,
        after={"model": result.model, "prompt_version": result.prompt_version,
               "payload_sha256": result.payload_sha256,
               "evidence_chunks": len(rows)})

    obligations = _parse(result.text, evidence_ids)
    run_id = _record_run(db, document_version_id, status="COMPLETED",
                         model=result.model, prompt_version=result.prompt_version)
    schema = config.assist_schema()
    for ordinal, obligation in enumerate(obligations):
        db.execute(text(f"""
            INSERT INTO "{schema}".obligation_extractions
                (id, run_id, document_version_id, evidence_id, party_label,
                 obligation_text, ordinal)
            VALUES (:i, :r, :d, :e, :p, :t, :o)
        """), {"i": uuid.uuid4(), "r": run_id, "d": document_version_id,
               "e": obligation.evidence_id, "p": obligation.party_label,
               "t": obligation.obligation_text, "o": ordinal})
    log_event("assist.obligations.extracted", request_id=request_id,
              document_version_id=str(document_version_id),
              obligations=str(len(obligations)))
    return ExtractionResult(extracted=True, obligations=obligations)


def read_obligations(db: DBSession, document_version_id: UUID) -> dict:
    """The GET shape: `extracted` plus groups under the document's own labels."""
    schema = config.assist_schema()
    extracted = completed_run_exists(db, document_version_id)
    if not extracted:
        return {"extracted": False, "groups": []}
    rows = db.execute(text(f"""
        SELECT o.id, o.party_label, o.obligation_text, o.evidence_id,
               e.section_number, e.page_number
          FROM "{schema}".obligation_extractions o
          JOIN "{schema}".obligation_extraction_runs r ON r.id = o.run_id
          JOIN document_evidence e ON e.id = o.evidence_id
         WHERE o.document_version_id = :d AND r.status = 'COMPLETED'
         ORDER BY o.party_label, o.ordinal
    """), {"d": document_version_id}).all()
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row[1], []).append({
            "id": str(row[0]),
            "obligation_text": row[2],
            "evidence_id": str(row[3]),
            "section_ref": row[4],
            "page_number": row[5],
        })
    return {"extracted": True,
            "groups": [{"party_label": label, "items": items}
                       for label, items in groups.items()]}

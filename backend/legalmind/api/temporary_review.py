"""A chat file's temporary contract review — `AM-143` (owner, 2026-10-15).

"Dashboard aur Ask attachment dono mein same authoritative contract-review engine use
hona chahiye. Ask attachment ka result temporary rahe; use Dashboard par Contract ke roop
mein save na kiya jaye." The AI understands a clause and pairs it with a standard (the
engine's grounded recognition, `AM-54`); code computes the result; a person decides.

So a review question about a chat FILE runs the Dashboard's own engine — `run_analysis`
over evidence rows written by the upload's own writer from the file's parser segments —
inside a SAVEPOINT that is always rolled back. The Contract, Version, Review and Findings
it builds exist only for the length of that call: nothing is committed, so nothing
appears on the Dashboard, in a list or in the audit trail as a Contract (`AM-133` r1
stands). No storage write is made either — a chat file keeps no bytes (A-15). Only each
model call's hash-only audit row outlives it, re-filed under the conversation; the
recognition verdicts the engine cached hold the file's words and are rolled back too.

It runs in the request, not the worker (locked 55.1 governs a RECORDED Review's analysis;
this one records nothing and its reader is waiting — `AM-143` r6).

This lives in the API layer because the assist lane may not import the evaluator
(`AM-25` r1; `test_import_boundaries`): routing such a question "is the API layer's job".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.api.angles import review_angles
from legalmind.api.reporting import review_findings
from legalmind.api.serializers import serialize_finding
from legalmind.assist.agent import attachments
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.extraction import commercial
from legalmind.ingestion import parsing
from legalmind.ingestion.service import PROCESSOR_VERSION, write_evidence
from legalmind.mapping.engine import Clause
from legalmind.observability.logs import log_event
from legalmind.security import audit as A


@dataclass(frozen=True)
class TemporaryReview:
    """What the reader sees: the file's name and the engine's Findings, serialized as
    the Findings endpoint serializes them for this caller (`LEGAL-02` omission kept).
    `refused` is the engine's own refusal code when it would not analyse the file."""
    filename: str
    findings: list[dict[str, Any]]
    refused: str | None = None
    #: `AM-229`: the file reviewed, and what the Dashboard's review page adds to the
    #: Findings (`angles.review_angles`: each point's action and counter-proposal, the
    #: client's tracked changes, the document's own precedence clause) — read inside the
    #: same rolled-back savepoint. None unless asked for.
    attachment_id: UUID | None = None
    angles: dict[str, Any] | None = None
    #: `AM-236`: the pages a partial read could not recover — named to the reader, never
    #: reviewed (`AM-143` r5)
    unread: list[int] = field(default_factory=list)


def _segments(raw: list[dict]) -> list[parsing.Segment]:
    return [parsing.Segment(
        content=s["content"], original_content=s.get("original_content") or s["content"],
        source_type=E.EvidenceSourceType(s["source_type"]),
        page_number=s.get("page_number"), section_number=s.get("section_number"),
        section_title=s.get("section_title"), start_offset=s.get("start_offset"),
        end_offset=s.get("end_offset"), metadata=s.get("metadata") or {})
        for s in raw]


def _egress_calls(db: DBSession, review_id: UUID) -> list[dict]:
    """The hash-only audit states of the model calls the engine made inside the
    savepoint (`AM-30`): an egress is never unaudited, so they outlive the rollback.
    The recognition verdicts it cached do NOT — each holds a verbatim span of the
    file, and a chat file's text expires with it (A4-2)."""
    return [e.after_state or {} for e in db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.ASSIST_GENERATION_CALLED,
        M.AuditEvent.entity_id == review_id)).scalars()]


def review_file(db: DBSession, *, conversation_id: UUID, user_id: UUID,
                legal_position: bool, request_id: str | None,
                found: tuple[attachments.Attachment, dict] | None = None,
                with_angles: bool = False,
                deal_fixed_term: bool = False,
                document_type: str | None = None) -> TemporaryReview | None:
    """A chat file — the conversation's newest unless `found` names one — reviewed by the
    Dashboard's engine against the newest published snapshot, or None when there is no
    such file or no snapshot. Every row written here is rolled back before returning.
    ``document_type``: the type the reader settled (`AM-236`: "we are buying" →
    VENDOR_AGREEMENT), declared on the temporary contract as an upload would."""
    found = found or attachments.file_segments(db, conversation_id)
    snapshot = db.execute(
        select(M.ConfigurationSnapshot)
        .order_by(M.ConfigurationSnapshot.created_at.desc(),
                  M.ConfigurationSnapshot.id.desc())
        .limit(1)).scalar_one_or_none()
    if found is None or snapshot is None:
        return None
    attachment, parse = found
    if "segments" not in parse:      # a partial parse is never reviewed (`AM-143` r5)
        return None
    raw = parse["segments"]
    filename = attachment.filename or "Attached file"
    review: M.Review | None = None
    calls: list[dict] = []
    savepoint = db.begin_nested()
    try:
        contract = M.Contract(owner_id=user_id, name=filename,
                              status=E.ContractStatus.DRAFT, contract_type=document_type)
        db.add(contract)
        db.flush()
        digest = hashlib.sha256(repr(raw).encode("utf-8")).hexdigest()
        version = M.DocumentVersion(
            contract_id=contract.id, version_number=1, original_filename=filename,
            mime_type=attachment.mime_type, file_size_bytes=attachment.byte_size,
            # never stored and never read: the evidence below is written directly
            file_hash=digest, storage_key=f"temporary:{digest}",
            processing_status=E.ProcessingStatus.COMPLETED,
            extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=user_id)
        db.add(version)
        db.flush()
        run = M.DocumentProcessingRun(
            document_version_id=version.id, run_type=E.ProcessingRunType.PARSE,
            status=E.ProcessingRunStatus.COMPLETED, processor_version=PROCESSOR_VERSION)
        db.add(run)
        db.flush()
        write_evidence(db, version, run, _segments(raw))
        review = M.Review(contract_id=contract.id, document_version_id=version.id,
                          configuration_snapshot_id=snapshot.id,
                          status=E.ReviewStatus.DRAFT, created_by=user_id)
        db.add(review)
        db.flush()
        try:
            outcome = run_analysis(db, review, actor_id=user_id, request_id=request_id,
                                   deal_fixed_term=deal_fixed_term)
        except AnalysisNotPermitted as exc:
            return TemporaryReview(filename, [], refused=str(exc) or "not_analysable")
        if review.status is E.ReviewStatus.ANALYSIS_FAILED:
            return TemporaryReview(filename, [], refused=outcome.review_status)
        findings = [serialize_finding(db, f, legal_position=legal_position)
                    for f in review_findings(db, review.id)]
        angles = (review_angles(db, review, legal_position=legal_position)
                  if with_angles else None)
        log_event("assist.attachment.reviewed", request_id=request_id,
                  conversation_id=str(conversation_id), attachment_id=str(attachment.id),
                  findings=str(len(findings)), snapshot_id=str(snapshot.id))
        return TemporaryReview(filename, findings, attachment_id=attachment.id,
                               angles=angles)
    finally:
        try:
            if review is not None and review.id is not None:
                calls = _egress_calls(db, review.id)
        except SQLAlchemyError:     # an aborted savepoint: the original error propagates,
            pass                    # and the request's transaction goes with it
        savepoint.rollback()
        for call in calls:      # the Review is gone; the call is the conversation's
            A.record(db, action=A.ASSIST_GENERATION_CALLED, entity_type="conversation",
                     entity_id=conversation_id, actor_id=user_id, request_id=request_id,
                     after={**call, "attachment_id": str(attachment.id)})


def states_fixed_term(segments: list[dict]) -> bool:
    """Whether a chat file's stored parse commits to a term — the reader's own detector
    (`commercial.states_fixed_term`) over clauses built from the segments, no database."""
    clauses = [Clause(evidence_id=uuid4(), content=s.get("content") or "",
                      section_number=s.get("section_number"),
                      section_title=s.get("section_title"),
                      page_number=s.get("page_number"),
                      is_heading=bool((s.get("metadata") or {}).get("heading")))
               for s in segments]
    return bool(clauses) and commercial.states_fixed_term(clauses)


def review_files(db: DBSession, *, conversation_id: UUID, user_id: UUID,
                 legal_position: bool, request_id: str | None,
                 document_type: str | None = None) -> list[TemporaryReview]:
    """Every chat file of the conversation, oldest first, each reviewed on its own and
    rolled back, with what the review page adds (`AM-229`). Files the engine cannot
    read whole are returned refused, never skipped silently."""
    out = []
    files = attachments.files_segments(db, conversation_id)
    # a term any file of the deal states counts for every file (`AM-229` r6)
    deal_fixed_term = any(states_fixed_term(parse.get("segments") or [])
                          for _, parse in files)
    for found in files:
        attachment, parse = found
        if "segments" not in parse:
            out.append(TemporaryReview(attachment.filename or "Attached file", [],
                                       refused="PARTIAL_READ",
                                       attachment_id=attachment.id,
                                       unread=list(parse.get("pages_failed") or [])))
            continue
        reviewed = review_file(db, conversation_id=conversation_id, user_id=user_id,
                               legal_position=legal_position, request_id=request_id,
                               found=found, with_angles=True,
                               deal_fixed_term=deal_fixed_term,
                               document_type=document_type)
        if reviewed is not None:
            out.append(reviewed)
    return out

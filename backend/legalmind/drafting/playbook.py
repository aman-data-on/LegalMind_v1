"""The negotiation playbook read from a template or a contract (`AM-305`): the
analysis half (`analysis.playbook`) derives each line from a Review; this half finds the
Review — our version's, or a temporary one of the published template's rendered file —
and the fallbacks a Legal approver recorded on the template's clause versions."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import negotiation
from legalmind.analysis.playbook import from_review
from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import model as model_
from legalmind.drafting import publish, render_contract
from legalmind.ingestion import parsing
from legalmind.ingestion.service import PROCESSOR_VERSION, write_evidence


def template_fallbacks(db: DBSession, tv: M.TemplateVersion | None) -> dict[str, list]:
    """Steps a Legal approver recorded on the template's pinned clause versions."""
    out: dict[str, list] = {}
    for row in (publish.pinned_clauses(db, tv).values() if tv else ()):
        for f in (row.source or {}).get("fallbacks") or ():
            if isinstance(f, dict) and f.get("requirement_code"):
                out.setdefault(f["requirement_code"], []).append(f)
    return out


def for_contract(db: DBSession, contract: M.Contract) -> list[dict[str, Any]]:
    """Our paper's playbook: the version we made from a template (its draft row), else
    our earliest version DECLARED ours (`COMPANY_DRAFT`). Anything else — the client's
    paper, or an upload nobody said was ours — opens at the ratified standard's own
    position, never at the document's figure (`AM-317` r4, audit N9: a client's 90 days
    read as "We start at 90 days")."""
    draft = db.execute(select(M.ContractDraft).where(
        M.ContractDraft.contract_id == contract.id)
        .order_by(M.ContractDraft.created_at)).scalars().first()
    versions = db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number)).scalars().all()
    ours = (db.get(M.DocumentVersion, draft.document_version_id) if draft
            else next((v for v in versions if (v.doc_metadata or {}).get("version_role")
                       == "COMPANY_DRAFT"), None))
    tv = db.get(M.TemplateVersion, draft.template_version_id) if draft else None
    provider = contract.contract_type in negotiation.PROVIDER_TYPES
    if ours is None:       # not provably ours: its figures are never our opening
        return from_review(db, negotiation._latest_review(db, versions[-1]),
                           provider=provider, openings=False) if versions else []
    return from_review(db, negotiation._latest_review(db, ours), provider=provider,
                       fallbacks=template_fallbacks(db, tv))


# -------------------------------------------- a published template's own playbook
#: (template version, snapshot) -> entries. A PUBLISHED version's text is frozen by the
#: database trigger, so a cached reading holds until a new snapshot is published.
# ponytail: per-process dict, unbounded; a handful of templates — a shared cache if many
_CACHE: dict[tuple[UUID, UUID], list[dict]] = {}


def for_template(db: DBSession, tv: M.TemplateVersion, *, actor_id: UUID,
                 request_id: str | None = None) -> list[dict[str, Any]] | None:
    """The engine's reading of the published template's rendered file — the same as the
    publish gate's (recognition off, no model, no egress), in a savepoint always rolled
    back. None: nothing published to read against, or the engine would not read it."""
    snapshot = publish.latest_snapshot(db)
    if snapshot is None:
        return None
    key = (tv.id, snapshot.id)
    if key in _CACHE:
        return _CACHE[key]
    rows = publish.pinned_clauses(db, tv)
    try:
        model = model_.resolve(publish.template_dict(tv),
                               {k: publish.clause_dict(c) for k, c in rows.items()},
                               (tv.layout or {}).get("check_values", {}))
    except model_.ModelError:
        return None
    docx = render_contract.render(model, tv.assets, contract_ref="PLAYBOOK",
                                  version_number=tv.version,
                                  model_hash=model_.model_hash(model))
    # ponytail: the same temporary Review as `publish._findings`, which returns only
    # classifications; fold the two into one helper once the gate work there has landed
    savepoint = db.begin_nested()
    try:
        contract = M.Contract(owner_id=actor_id, name=f"Playbook {tv.template_key}",
                              status=E.ContractStatus.DRAFT, contract_type=tv.doc_type,
                              issuing_entity=publish.issuing_entity(tv.brand))
        db.add(contract)
        db.flush()
        digest = hashlib.sha256(docx).hexdigest()
        version = M.DocumentVersion(
            contract_id=contract.id, version_number=1, original_filename="playbook.docx",
            mime_type=publish.DOCX_MIME, file_size_bytes=len(docx), file_hash=digest,
            storage_key=f"temporary:{digest}",
            processing_status=E.ProcessingStatus.COMPLETED,
            extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=actor_id)
        db.add(version)
        db.flush()
        run = M.DocumentProcessingRun(
            document_version_id=version.id, run_type=E.ProcessingRunType.PARSE,
            status=E.ProcessingRunStatus.COMPLETED, processor_version=PROCESSOR_VERSION)
        db.add(run)
        db.flush()
        write_evidence(db, version, run, parsing.parse_docx(docx).segments)
        review = M.Review(contract_id=contract.id, document_version_id=version.id,
                          configuration_snapshot_id=snapshot.id,
                          status=E.ReviewStatus.DRAFT, created_by=actor_id)
        db.add(review)
        db.flush()
        try:
            run_analysis(db, review, actor_id=actor_id, request_id=request_id,
                         recognition=False)
        except AnalysisNotPermitted:
            return None
        if review.status is E.ReviewStatus.ANALYSIS_FAILED:
            return None
        found = from_review(db, review,
                            provider=tv.doc_type in negotiation.PROVIDER_TYPES,
                            fallbacks=template_fallbacks(db, tv))
    finally:
        savepoint.rollback()
    if tv.status == "PUBLISHED":
        _CACHE[key] = found
    return found

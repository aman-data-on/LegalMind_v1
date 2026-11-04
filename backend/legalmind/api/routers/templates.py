"""Contract templates: a lawyer approves each clause, then publishes (`AM-282`/`AM-283`).

Who sees what (SEC-07): a holder of ``legal.approve_customization`` sees every version;
anyone else needs ``contract.create`` and sees PUBLISHED versions only — a DRAFT, its
reference text and its flags are a 404 to them, byte-identical to an id that does not
exist. Every write is the approver's alone: each clause action writes a new APPROVED
clause version with the recorded lawyer source (`drafting.library`), and publishing runs
`drafting.publish`'s gate, refusing with every named problem.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select

from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import attachment_headers, data
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.routers.negotiation import PdfNotMade
from legalmind.api.schemas import Body
from legalmind.api.storage import get_storage
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import (
    blank,
    library,
    pdf,
    preflight,
    publish,
    render_contract,
    special_conditions,
)
from legalmind.drafting import model as model_
from legalmind.ingestion import parsing
from legalmind.ingestion.service import PROCESSOR_VERSION, write_evidence
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible
from legalmind.worker.dispatch import dispatch_blank_pdf

router = APIRouter(tags=["templates"], route_class=CommitBeforeResponse)

PUBLISH_REFUSED = "template.publish_refused"


class Reasoned(Body):
    reason: str = Field(min_length=1, max_length=2000)


class Replacement(Body):
    #: required to record (409 without one); a dry run may come before it is typed
    reason: str = Field(default="", max_length=2000)
    #: the lawyer's wording, word for word; its markers (4.1, (a), “X” means, | rows)
    #: become the clause's structure (`library.parse_wording`)
    text: str = Field(min_length=1, max_length=20000)
    #: true: return how it will be numbered (``outline``) and write nothing
    dry_run: bool = False


class PublishRequest(Body):
    #: who approved the text outside LegalMind, e.g. "Management approval, email of
    #: 5 Nov 2026" — optional, recorded with the publish (`AM-302` r6)
    approval_reference: str = Field(default="", max_length=300)


class PublishProblems(BusinessRuleRejected):
    code = "PUBLISH_REFUSED"

    def __init__(self, problems: list[str]) -> None:
        super().__init__(f"This template cannot be published: {len(problems)} "
                         f"problem{'s' if len(problems) != 1 else ''}.")
        self.extra = {"problems": problems}


def _approver(guard: Guard) -> bool:
    return P.LEGAL_APPROVE_CUSTOMIZATION in guard.permissions


def _visible(guard: Guard, template_id: UUID, *, lock: bool = False) -> M.TemplateVersion:
    stmt = select(M.TemplateVersion).where(M.TemplateVersion.id == template_id)
    tv = guard.db.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
    if tv is None or (tv.status != "PUBLISHED" and not _approver(guard)):
        raise NotVisible("template not found")
    if not _approver(guard):
        guard.permission(P.CONTRACT_CREATE)
    return tv


def _summary(guard: Guard, tv: M.TemplateVersion) -> dict[str, Any]:
    done, total = library.progress(guard.db, tv)
    return {"id": str(tv.id), "template_key": tv.template_key, "version": tv.version,
            "status": tv.status, "doc_type": tv.doc_type, "brand": tv.brand,
            "title": (tv.layout or {}).get("title"),
            # the file it was imported from: tells two templates of one type apart
            "source_file": (tv.source or {}).get("file"),
            # a local demo copy published by hand says so ("DEMO — not approved by Legal")
            "label": (blank.demo_label(tv) if tv.status == "PUBLISHED"
                      else library.DRAFT_LABEL),
            "clauses_approved": done, "clauses_total": total,
            "progress": f"{done} of {total} clauses approved",
            "published_at": tv.published_at.isoformat() if tv.published_at else None}


@router.get("/templates")
def list_templates(guard: Guard = Depends(get_guard)) -> dict:
    stmt = select(M.TemplateVersion).order_by(M.TemplateVersion.template_key,
                                              M.TemplateVersion.version)
    if not _approver(guard):
        guard.permission(P.CONTRACT_CREATE)
        stmt = stmt.where(M.TemplateVersion.status == "PUBLISHED")
    return data([_summary(guard, tv) for tv in guard.db.execute(stmt).scalars()])


@router.get("/templates/{template_id}")
def get_template(template_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    tv = _visible(guard, template_id)
    rows = publish.pinned_clauses(guard.db, tv)
    approver = _approver(guard)
    live = _published(guard, tv) if approver else None
    live_pins = {p["clause_key"]: p["version"]
                 for p in (library.pins(live) if live else [])}
    clauses = []
    for pin in library.pins(tv):
        row = rows.get((pin["clause_key"], pin["version"]))
        if row is None:
            continue
        source = row.source or {}
        item = {"clause_key": row.clause_key, "version": row.version, "title": row.title,
                "body": row.body, "realises": row.realises, "status": row.status,
                "variables": library.slots(row.body),
                "label": library.label(row)}
        if approver:
            item |= {"flags": source.get("flags", []),
                     "wording": library.wording(row.body,
                                                library.number_of(tv, row.clause_key)),
                     "approval": None if row.status != "APPROVED" else {
                         "decision": source.get("decision"),
                         "approved_by": str(row.approved_by),
                         "approved_by_name": getattr(
                             guard.db.get(M.User, row.approved_by), "name", None),
                         "approved_at": row.approved_at.isoformat() if row.approved_at
                         else None,
                         "approval_ref": source.get("approval_ref"),
                         "reason": source.get("reason")},
                     # the version the published template uses (None: not in it)
                     "published_version": live_pins.get(row.clause_key)}
        clauses.append(item)
    body = _summary(guard, tv) | {"variables": tv.variables, "clauses": clauses,
                                  # AM-307: can this template carry Special Conditions
                                  "special_conditions": special_conditions.readiness(
                                      guard.db, tv)}
    if approver:
        body["flags"] = (tv.source or {}).get("flags", [])
        body["published"] = None if live is None else {"id": str(live.id),
                                                       "version": live.version}
        # AM-302 r6: who approved this text outside LegalMind, as the publish recorded it
        said = guard.db.execute(select(M.AuditEvent.after_state).where(
            M.AuditEvent.action == publish.TEMPLATE_PUBLISHED,
            M.AuditEvent.entity_id == tv.id)).scalars().first()
        body["approval_reference"] = (said or {}).get("approval_reference")
    return data(body)


def _published(guard: Guard, tv: M.TemplateVersion) -> M.TemplateVersion | None:
    """The PUBLISHED version of this template's key, when it is not ``tv`` itself."""
    return guard.db.execute(select(M.TemplateVersion).where(
        M.TemplateVersion.template_key == tv.template_key,
        M.TemplateVersion.status == "PUBLISHED",
        M.TemplateVersion.id != tv.id)).scalar_one_or_none()


@router.get("/templates/{template_id}/clauses/{clause_key}/versions")
def clause_versions(template_id: UUID, clause_key: str,
                    guard: Guard = Depends(get_guard)) -> dict:
    """Every recorded version of one clause of this template, newest first — who
    approved it, how, and the reason they gave (the approver's governance trail)."""
    tv = _visible(guard, template_id)
    guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                entity_type="template_version", entity_id=tv.id)
    pin = next((p for p in library.pins(tv) if p["clause_key"] == clause_key), None)
    if pin is None:
        raise NotVisible("clause not found")
    live = _published(guard, tv) or (tv if tv.status == "PUBLISHED" else None)
    live_version = next((p["version"] for p in library.pins(live)
                         if p["clause_key"] == clause_key), None) if live else None
    number = library.number_of(tv, clause_key)
    out = []
    for row in guard.db.execute(select(M.ClauseVersion).where(
            M.ClauseVersion.clause_key == clause_key)
            .order_by(M.ClauseVersion.version.desc())).scalars():
        source = row.source or {}
        by = guard.db.get(M.User, row.approved_by) if row.approved_by else None
        out.append({"version": row.version, "status": row.status,
                    "decision": source.get("decision"), "reason": source.get("reason"),
                    "supplier_kind": source.get("kind"),
                    "approved_by_name": getattr(by, "name", None),
                    "approved_at": row.approved_at.isoformat() if row.approved_at
                    else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "in_this_template": row.version == pin["version"],
                    "published": row.version == live_version,
                    "wording": library.wording(row.body, number)})
    return data(out)


def _decide(guard: Guard, template_id: UUID, clause_key: str, decision: str,
            reason: str, text: str | None = None, dry_run: bool = False) -> dict:
    tv = _visible(guard, template_id, lock=not dry_run)
    guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                entity_type="template_version", entity_id=tv.id)
    try:
        if dry_run:
            body = library.replacement(guard.db, tv, clause_key, text or "")
            return data({"clause_key": clause_key, "dry_run": True, "body": body,
                         "outline": library.outline(
                             body, library.number_of(tv, clause_key))})
        row = library.decide(guard.db, tv, clause_key, decision, actor_id=guard.user_id,
                             reason=reason, text=text, request_id=guard.request_id)
    except library.LibraryRefused as exc:
        if str(exc) == "not a clause of this template":
            raise NotVisible("clause not found") from exc
        raise Conflict(str(exc)) from exc
    done, total = library.progress(guard.db, tv)
    out = {"clause_key": row.clause_key, "version": row.version,
           "status": row.status, "content_hash": row.content_hash,
           "approval_ref": row.source["approval_ref"],
           "progress": f"{done} of {total} clauses approved"}
    if decision == "REPLACE":
        out["outline"] = library.outline(row.body, library.number_of(tv, clause_key))
    return data(out)


@router.post("/templates/{template_id}/clauses/{clause_key}/approve")
def approve_clause(template_id: UUID, clause_key: str,
                   guard: Guard = Depends(get_guard)) -> dict:
    return _decide(guard, template_id, clause_key, "APPROVE", "")


@router.post("/templates/{template_id}/clauses/{clause_key}/replace")
def replace_clause(template_id: UUID, clause_key: str, body: Replacement,
                   guard: Guard = Depends(get_guard)) -> dict:
    """The lawyer's wording for a clause. ``dry_run`` returns ``outline`` — each line as
    it will be numbered ("4.1", "(a)") — and writes nothing, so it can be shown before
    the wording is recorded; the recorded reply carries the same ``outline``."""
    return _decide(guard, template_id, clause_key, "REPLACE", body.reason, body.text,
                   body.dry_run)


@router.post("/templates/{template_id}/clauses/{clause_key}/no-position")
def no_position(template_id: UUID, clause_key: str, body: Reasoned,
                guard: Guard = Depends(get_guard)) -> dict:
    return _decide(guard, template_id, clause_key, "NO_POSITION", body.reason)


@router.post("/templates/{template_id}/publish")
def publish_template(template_id: UUID, body: PublishRequest | None = None,
                     guard: Guard = Depends(get_guard)) -> dict:
    tv = _visible(guard, template_id, lock=True)
    guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                entity_type="template_version", entity_id=tv.id)
    if tv.status == "PUBLISHED":
        raise Conflict("this template version is already published")
    savepoint = guard.db.begin_nested()
    try:
        library.mark_approved(guard.db, tv, actor_id=guard.user_id)
        done = publish.publish_template(
            guard.db, tv.id, actor_id=guard.user_id, request_id=guard.request_id,
            approval_reference=" ".join((body or PublishRequest()).approval_reference
                                        .split()))
    except publish.PublishRefused as exc:
        savepoint.rollback()
        A.record(guard.db, action=PUBLISH_REFUSED, entity_type="template_version",
                 entity_id=tv.id, actor_id=guard.user_id, request_id=guard.request_id,
                 after={"template_key": tv.template_key, "version": tv.version,
                        "problems": exc.problems})
        guard.db.commit()                  # the refusal is recorded; nothing else is
        raise PublishProblems(exc.problems) from exc
    savepoint.commit()
    return data({**_summary(guard, tv), "snapshot_id": str(done.snapshot_id),
                 "model_hash": done.model_hash, "findings": done.findings,
                 "pdf_checked": done.pdf_checked})


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", library.SLOT.sub(" ", text).lower()).strip()


def _clause_of(evidence: str, texts: dict[str, str]) -> str | None:
    """The clause whose text holds this evidence row's first eight words (the rendered
    file fills each slot, so a row that opens on a slot is placed by no clause)."""
    needle = " ".join(_norm(evidence).split()[:8])
    return next((k for k, t in texts.items() if len(needle) > 20 and needle in t), None)


@router.get("/templates/{template_id}/check")
def check_template(template_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """What the publish gate would say of the text AS IT STANDS — every clause taken as
    approved, the file rendered, preflighted and read by the engine exactly as
    `drafting.publish` does — run inside a savepoint that is always rolled back, so
    nothing is approved, recorded or kept. Unlike the gate it does not stop at the
    first failing step: the lawyer sees the preflight problems AND each standard the
    engine finds not met, placed on the clause its evidence is read from.
    Nothing here decides: the engine classifies; this only reports (rule 13)."""
    tv = _visible(guard, template_id)
    guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                entity_type="template_version", entity_id=tv.id)
    if tv.status != "DRAFT":  # its clauses are fixed: there is nothing left to check
        raise Conflict(f"this template is {tv.status}; only a draft is checked")
    positions = guard.sees_legal_position
    # the check takes seconds: end the request's own transaction first, so the session
    # row it touched is not held locked while this reader's other requests wait on it
    guard.db.commit()
    savepoint = guard.db.begin_nested()
    try:
        for (key, _), row in publish.pinned_clauses(guard.db, tv).items():
            if row.status != "APPROVED":
                library.decide(guard.db, tv, key, "APPROVE", actor_id=guard.user_id)
        rows = publish.pinned_clauses(guard.db, tv)
        texts = {k: _norm(" ".join(library.texts(r.body))) for (k, _), r in rows.items()}
        try:
            model = model_.resolve(publish.template_dict(tv),
                                   {k: publish.clause_dict(c) for k, c in rows.items()},
                                   (tv.layout or {}).get("check_values", {}))
        except model_.ModelError as exc:
            return data({"publishable": False, "problems": [f"MODEL: {exc}"],
                         "standards": []})
        docx = render_contract.render(model, tv.assets, contract_ref="PUBLISHCHECK",
                                      version_number=tv.version,
                                      model_hash=model_.model_hash(model))
        pdf_bytes = None
        # Synchronous on purpose (`AM-293` r2 governs the CLIENT PDF only): this is the
        # internal publish gate's check of a PUBLISHCHECK render — its PDF is read for
        # the preflight and discarded, never stored, downloaded or sent, and the lawyer
        # pressing Publish needs the verdict in this response.
        if os.environ.get("LEGALMIND_SOFFICE"):
            docx, result = pdf.convert_contract(docx)
            pdf_bytes = result.pdf
        problems = [f"PREFLIGHT {p.code}: {p.detail}"
                    for p in preflight.check(docx, model=model, pdf=pdf_bytes)]
        standards = _engine_check(guard, tv, docx, texts, positions)
        if standards is None:
            problems.append("ANALYSIS: the engine could not analyse the file")
            standards = []
        return data({"publishable": not problems and all(s["in_our_favour"]
                                                          for s in standards),
                     "problems": problems, "standards": standards,
                     # AM-307: read with every clause taken as approved, like the rest
                     "special_conditions": special_conditions.readiness(guard.db, tv)})
    finally:
        savepoint.rollback()


def _engine_check(guard: Guard, tv: M.TemplateVersion, docx: bytes,
                  texts: dict[str, str], positions: bool) -> list[dict] | None:
    """Every non-MATCH Finding on the rendered file (`publish._findings`' rows, kept
    long enough to place each on the clauses its evidence is read from), or None when
    the engine will not analyse the file."""
    db, actor = guard.db, guard.user_id
    snapshot = db.execute(select(M.ConfigurationSnapshot).order_by(
        M.ConfigurationSnapshot.created_at.desc(), M.ConfigurationSnapshot.id.desc())
        .limit(1)).scalar_one_or_none()
    if snapshot is None:
        return None
    contract = M.Contract(owner_id=actor, name=f"Publish check {tv.template_key}",
                          status=E.ContractStatus.DRAFT, contract_type=tv.doc_type,
                          issuing_entity=publish.issuing_entity(tv.brand))
    db.add(contract)
    db.flush()
    digest = hashlib.sha256(docx).hexdigest()
    version = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="publish-check.docx",
        mime_type=publish.DOCX_MIME, file_size_bytes=len(docx), file_hash=digest,
        storage_key=f"temporary:{digest}", processing_status=E.ProcessingStatus.COMPLETED,
        extraction_status=E.ExtractionStatus.COMPLETE, uploaded_by=actor)
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
                      status=E.ReviewStatus.DRAFT, created_by=actor)
    db.add(review)
    db.flush()
    try:
        run_analysis(db, review, actor_id=actor, request_id=guard.request_id,
                     recognition=False)
    except AnalysisNotPermitted:
        return None
    if review.status is E.ReviewStatus.ANALYSIS_FAILED:
        return None
    out = []
    for f, rv, code, cs in db.execute(
            select(M.Finding, M.RequirementVersion, M.Requirement.code,
                   M.CompanyStandardVersion.configuration)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .outerjoin(M.ConfigurationSnapshotItem,
                       (M.ConfigurationSnapshotItem.snapshot_id == snapshot.id)
                       & (M.ConfigurationSnapshotItem.requirement_version_id
                          == M.Finding.requirement_version_id))
            .outerjoin(M.CompanyStandardVersion,
                       M.CompanyStandardVersion.id
                       == M.ConfigurationSnapshotItem.company_standard_version_id)
            .where(M.Finding.review_id == review.id,
                   M.Finding.classification != E.FindingClassification.MATCH)
            .order_by(M.Requirement.code)):
        rows = db.execute(
            select(M.DocumentEvidence.content, M.FindingEvidence.relationship_type)
            .join(M.FindingEvidence,
                  M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
            .where(M.FindingEvidence.finding_id == f.id)).all()
        primary = [c for c, r in rows if r is E.EvidenceRelationshipType.PRIMARY]
        clauses = list(dict.fromkeys(k for c in primary or [c for c, _ in rows]
                                     if (k := _clause_of(c, texts))))
        item = {"code": code, "name": rv.name, "description": rv.description,
                # the Constitution's topic for it ("Liability") — a label, never a value
                "topic": ((cs or {}).get("constitution") or {}).get("topic"),
                "classification": f.classification.value, "clause_keys": clauses,
                # AM-303: better for us than the standard — said, and not a block
                "in_our_favour": publish.in_our_favour(db, f, code)}
        if positions:
            item["position"] = (cs or {}).get("position_statement")
        out.append(item)
    return out


# ------------------------------------- `AM-302`: the blank template, the review copy
_FORMAT = Query("docx", pattern="^(docx|pdf)$", description="docx or pdf")
#: who may download a DRAFT's review copy for management: a Legal approver, a Legal
#: Decision Authority or the department Lead — never a salesperson
_REVIEWERS = frozenset({P.LEGAL_APPROVE_CUSTOMIZATION, P.LEGAL_DECISION,
                        P.DEPARTMENT_VIEW})


def _download(guard: Guard, storage: StorageBackend, tv: M.TemplateVersion, kind: str,
              fmt: str) -> Response:
    """The file (`drafting.blank`), audited; a PDF by the worker (202 while it is made,
    503 when it could not be — the Word file still can)."""
    if fmt == "docx":
        content, model = blank.render(guard.db, tv, kind)
        media = publish.DOCX_MIME
    else:
        model = blank.blank_model(guard.db, tv)
        digest = model_.model_hash(model)
        found = pdf.blank_record(guard.db, tv.id, digest, kind)
        rec = found if found is not None and not pdf.stale(found) and (
            found["status"] != pdf.READY or storage.exists(found["storage_key"])
        ) else dispatch_blank_pdf(guard.db, tv.id, digest, kind,
                                  request_id=guard.request_id)
        if rec["status"] == pdf.FAILED:
            raise PdfNotMade(f"The PDF could not be made: {rec['error']}. The Word file "
                             "can still be downloaded.")
        if rec["status"] == pdf.RENDERING:
            return JSONResponse(status_code=202, content=data({"status": "rendering"}),
                                headers={"Retry-After": "3"})
        content, media = storage.get(rec["storage_key"]), "application/pdf"
    A.record(guard.db, action=A.TEMPLATE_BLANK_DOWNLOADED, entity_type="template_version",
             entity_id=tv.id, actor_id=guard.user_id, request_id=guard.request_id,
             after={"template_key": tv.template_key, "version": tv.version,
                    "status": tv.status, "kind": kind, "format": fmt,
                    "template_id": blank.identifier(tv, model, kind)})
    title = (tv.layout or {}).get("title") or tv.template_key
    what = "blank template" if kind == blank.BLANK else "review copy"
    return Response(content=content, media_type=media, headers=attachment_headers(
        f"{title} - {what} v{tv.version}.{fmt}", f"template.{fmt}"))


@router.get("/templates/{template_key}/blank",
            responses={202: {"description": "the worker is still making the PDF"}})
def download_blank(template_key: str, format: str = _FORMAT,
                   version: int | None = Query(None, ge=1),
                   guard: Guard = Depends(get_guard),
                   storage: StorageBackend = Depends(get_storage)) -> Response:
    """The PUBLISHED template's approved text with every field a highlighted placeholder,
    to fill outside LegalMind (owner, 2026-11-04). Anyone who may create a contract. A
    DRAFT (or unknown) version is the same 404 as no template; a RETIRED one is 409,
    naming the current version. Every download is audited."""
    guard.permission(P.CONTRACT_CREATE)
    stmt = select(M.TemplateVersion).where(M.TemplateVersion.template_key == template_key)
    tv = guard.db.execute(stmt.where(M.TemplateVersion.version == version)
                          if version is not None
                          else stmt.where(M.TemplateVersion.status == "PUBLISHED")
                          ).scalar_one_or_none()
    if tv is None or tv.status not in ("PUBLISHED", "RETIRED"):
        raise NotVisible("template not found")
    if tv.status == "RETIRED":
        current = guard.db.execute(stmt.where(M.TemplateVersion.status == "PUBLISHED")
                                   ).scalar_one_or_none()
        raise Conflict(f"Version {tv.version} of this template is retired"
                       + (f"; download the current one (v{current.version})." if current
                          else "."))
    return _download(guard, storage, tv, blank.BLANK, format)


@router.get("/templates/{template_id}/review-copy",
            responses={202: {"description": "the worker is still making the PDF"}})
def download_review_copy(template_id: UUID, format: str = _FORMAT,
                         guard: Guard = Depends(get_guard),
                         storage: StorageBackend = Depends(get_storage)) -> Response:
    """A not-yet-published template's full text for management to approve, headed
    "DRAFT FOR MANAGEMENT APPROVAL — not for client use", placeholders highlighted.
    Only a Legal approver, a Legal Decision Authority or the Lead; anyone else (and an
    unknown id) is the same 404. A published version is 409 — that is the blank."""
    tv = guard.db.get(M.TemplateVersion, template_id)
    if tv is None or not (_REVIEWERS & guard.permissions):
        raise NotVisible("template not found")
    if tv.status not in ("DRAFT", "APPROVED"):
        raise Conflict("This template is no longer a draft; download the blank template "
                       "instead.")
    return _download(guard, storage, tv, blank.REVIEW, format)

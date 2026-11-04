"""Publish a template version — the gate between an approved template and a client.

A holder of ``legal.approve_customization`` publishes (checked here, in the service; the
API arrives with slice S4). The gate, in order, each step refusing with named problems:

1. the template version is APPROVED and EVERY pinned clause version is APPROVED;
2. its ``layout.check_values`` resolve into a model (`drafting.model`);
3. the rendered DOCX passes `preflight` (numbering round-trip, xrefs, slots, markup,
   relationships, images, terms) — and, where LibreOffice is configured, so does its PDF;
   (1 also: every variable has a label a person can read — `model.key_like`)
4. the file is read by the parser and analysed by the Dashboard's own engine against the
   newest published snapshot, inside a SAVEPOINT that is always rolled back (the
   `AM-143` temporary-review pattern, `api.temporary_review`) with recognition OFF — no
   embedding, no model, no egress: our own approved text must match our standards on its
   words alone. EVERY Finding must be MATCH;
5. then PUBLISHED, with the snapshot it was checked against; the previously published
   version of the same key is RETIRED in the same transaction (one PUBLISHED per key).

Nothing here decides a legal outcome: the engine classifies, this module only refuses
to publish over anything but MATCH (rule 13; `AM-33`).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.negotiation import lower_cap_in_our_favour
from legalmind.analysis.service import AnalysisNotPermitted, run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import model as model_
from legalmind.drafting import pdf, preflight, render_contract
from legalmind.ingestion import parsing
from legalmind.ingestion.service import PROCESSOR_VERSION, write_evidence
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.resolver import effective_permissions

TEMPLATE_PUBLISHED = "template.published"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class PublishRefused(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Published:
    template_version_id: UUID
    snapshot_id: UUID
    model_hash: str
    findings: int
    pdf_checked: bool


#: `AM-287` r1 — the brands a contract may be issued by
BRANDS = ("LEAPSWITCH", "CLOUDPE")


def issuing_entity(brand: str | None) -> str | None:
    """A template's brand as a contract's issuing entity (the placeholder's is none)."""
    return brand if brand in BRANDS else None


def clause_dict(cv: M.ClauseVersion) -> dict[str, Any]:
    return {"clause_key": cv.clause_key, "version": cv.version, "title": cv.title,
            "body": cv.body, "realises": cv.realises, "stance": cv.stance,
            "content_hash": cv.content_hash, "status": cv.status}


def template_dict(tv: M.TemplateVersion) -> dict[str, Any]:
    return {"template_key": tv.template_key, "version": tv.version,
            "content_hash": tv.content_hash, "doc_type": tv.doc_type, "brand": tv.brand,
            "layout": tv.layout, "clauses": tv.clauses, "variables": tv.variables,
            "annexures": tv.annexures, "assets": tv.assets}


def pinned_clauses(db: DBSession,
                   tv: M.TemplateVersion) -> dict[tuple[str, int], M.ClauseVersion]:
    pins = [(p["clause_key"], p["version"])
            for a in [{"clauses": tv.clauses}, *tv.annexures]
            for p in a.get("clauses", [])]
    rows = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key.in_({k for k, _ in pins}))).scalars()
    found = {(c.clause_key, c.version): c for c in rows}
    return {pin: found[pin] for pin in pins if pin in found}


def latest_snapshot(db: DBSession) -> M.ConfigurationSnapshot | None:
    return db.execute(select(M.ConfigurationSnapshot).order_by(
        M.ConfigurationSnapshot.created_at.desc(), M.ConfigurationSnapshot.id.desc())
        .limit(1)).scalar_one_or_none()


def in_our_favour(db: DBSession, finding: M.Finding, code: str) -> bool:
    """`AM-303`: our own template may open with a position better for us than the
    standard. A Finding passes the gate when every Evaluation is a MATCH, a DEVIATION
    the approved favourable rule accepted (`AM-239` r1), or a mutual cap no higher than
    ours on the same or a dominated basis (`AM-299` r3 / `AM-301`). A one-party cap, a
    CONFLICT or a MISSING never does."""
    if finding.classification not in (E.FindingClassification.DEVIATION,
                                      E.FindingClassification.UNABLE_TO_EVALUATE):
        return False
    evaluations = db.execute(select(M.Evaluation).where(
        M.Evaluation.finding_id == finding.id)).scalars().all()
    return bool(evaluations) and all(
        ev.classification is E.FindingClassification.MATCH
        or (ev.classification is E.FindingClassification.DEVIATION
            and ev.rule_outcome is E.RuleOutcome.ACCEPTABLE)
        or lower_cap_in_our_favour(code, ev.expected_value, ev.actual_value)
        for ev in evaluations)


def engine_findings(db: DBSession, docx_bytes: bytes, tv: M.TemplateVersion, *,
                    actor_id: UUID, request_id: str | None = None
                    ) -> list[tuple[str, str, str, bool]]:
    """Step 4 on any rendered file: the engine's Findings, nothing kept (the New
    contract page's early check reads the same thing the gate does)."""
    snapshot = latest_snapshot(db)
    if snapshot is None:
        return []
    return _findings(db, docx_bytes=docx_bytes, tv=tv, snapshot=snapshot,
                     actor_id=actor_id, request_id=request_id)


def _findings(db: DBSession, *, docx_bytes: bytes, tv: M.TemplateVersion,
              snapshot: M.ConfigurationSnapshot, actor_id: UUID,
              request_id: str | None) -> list[tuple[str, str, str, bool]]:
    """(requirement code, classification, requirement name, in our favour) of every
    Finding the engine makes on the rendered file, computed inside a savepoint that is
    always rolled back."""
    parsed = parsing.parse_docx(docx_bytes)
    savepoint = db.begin_nested()
    try:
        contract = M.Contract(owner_id=actor_id, name=f"Publish check {tv.template_key}",
                              status=E.ContractStatus.DRAFT, contract_type=tv.doc_type,
                              issuing_entity=issuing_entity(tv.brand))
        db.add(contract)
        db.flush()
        digest = hashlib.sha256(docx_bytes).hexdigest()
        version = M.DocumentVersion(
            contract_id=contract.id, version_number=1,
            original_filename="publish-check.docx",
            mime_type=DOCX_MIME, file_size_bytes=len(docx_bytes), file_hash=digest,
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
        write_evidence(db, version, run, parsed.segments)
        review = M.Review(contract_id=contract.id, document_version_id=version.id,
                          configuration_snapshot_id=snapshot.id,
                          status=E.ReviewStatus.DRAFT, created_by=actor_id)
        db.add(review)
        db.flush()
        try:
            run_analysis(db, review, actor_id=actor_id, request_id=request_id,
                         recognition=False)
        except AnalysisNotPermitted as exc:
            raise PublishRefused([f"ANALYSIS: the engine would not analyse the file "
                                  f"({exc or 'not analysable'})"]) from exc
        if review.status is E.ReviewStatus.ANALYSIS_FAILED:
            raise PublishRefused(["ANALYSIS: the engine could not analyse the file"])
        return [(code, f.classification.value, name, in_our_favour(db, f, code))
                for f, code, name in db.execute(
            select(M.Finding, M.Requirement.code, M.RequirementVersion.name)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .where(M.Finding.review_id == review.id))]
    finally:
        savepoint.rollback()


def publish_template(db: DBSession, template_version_id: UUID, *, actor_id: UUID,
                     request_id: str | None = None,
                     approval_reference: str | None = None) -> Published:
    """Publish, or `PublishRefused` naming every reason. ``approval_reference``: who
    approved the text outside LegalMind ("Management approval, email of 5 Nov 2026"),
    recorded with the publish (`AM-302` r6)."""
    if P.LEGAL_APPROVE_CUSTOMIZATION not in effective_permissions(db, actor_id):
        raise PublishRefused(["NOT_PERMITTED: publishing a template needs "
                              f"{P.LEGAL_APPROVE_CUSTOMIZATION}"])
    tv = db.execute(select(M.TemplateVersion)
                    .where(M.TemplateVersion.id == template_version_id)
                    .with_for_update()).scalar_one_or_none()
    if tv is None:
        raise PublishRefused(["NOT_FOUND: no such template version"])
    problems = [] if tv.status == "APPROVED" else [
        f"TEMPLATE_NOT_APPROVED: {tv.template_key}@{tv.version} is {tv.status}"]
    rows = pinned_clauses(db, tv)
    for a in [{"clauses": tv.clauses}, *tv.annexures]:
        for pin in a.get("clauses", []):
            row = rows.get((pin["clause_key"], pin["version"]))
            if row is None or row.status != "APPROVED":
                problems.append("CLAUSE_NOT_APPROVED: "
                                f"{pin['clause_key']}@{pin['version']}"
                                f" is {row.status if row else 'missing'}")
    problems += [f"LABEL: {v['key']} has no label a person can read; give it one "
                 "(and help) in the template" for v in tv.variables if model_.key_like(v)]
    if problems:
        raise PublishRefused(problems)
    try:
        model = model_.resolve(template_dict(tv),
                               {k: clause_dict(c) for k, c in rows.items()},
                               (tv.layout or {}).get("check_values", {}))
    except model_.ModelError as exc:
        raise PublishRefused([f"MODEL: {exc}"]) from exc
    digest = model_.model_hash(model)
    docx_bytes = render_contract.render(model, tv.assets, contract_ref="PUBLISHCHECK",
                                        version_number=tv.version, model_hash=digest)
    pdf_bytes = None
    if os.environ.get("LEGALMIND_SOFFICE"):
        docx_bytes, result = pdf.convert_contract(docx_bytes)
        pdf_bytes = result.pdf
    found = preflight.check(docx_bytes, model=model, pdf=pdf_bytes)
    if found:
        raise PublishRefused([f"PREFLIGHT {p.code}: {p.detail}" for p in found])
    snapshot = latest_snapshot(db)
    if snapshot is None:
        raise PublishRefused(["NO_SNAPSHOT: nothing is published to check against"])
    findings = _findings(db, docx_bytes=docx_bytes, tv=tv, snapshot=snapshot,
                         actor_id=actor_id, request_id=request_id)
    off = [f"NOT_MATCH: {code} is {cls}" for code, cls, _, ours in findings
           if cls != E.FindingClassification.MATCH.value and not ours]
    if off:
        raise PublishRefused(off)
    now = datetime.now(UTC)
    for old in db.execute(select(M.TemplateVersion).where(
            M.TemplateVersion.template_key == tv.template_key,
            M.TemplateVersion.status == "PUBLISHED")).scalars():
        old.status = "RETIRED"
    db.flush()
    tv.status, tv.checked_snapshot_id = "PUBLISHED", snapshot.id
    tv.published_by, tv.published_at = actor_id, now
    db.flush()
    A.record(db, action=TEMPLATE_PUBLISHED, entity_type="template_version",
             entity_id=tv.id, actor_id=actor_id, request_id=request_id,
             after={"template_key": tv.template_key, "version": tv.version,
                    "content_hash": tv.content_hash, "model_hash": digest,
                    "snapshot_id": str(snapshot.id), "findings": len(findings),
                    "pdf_checked": pdf_bytes is not None,
                    "approval_reference": approval_reference or None})
    return Published(tv.id, snapshot.id, digest, len(findings), pdf_bytes is not None)

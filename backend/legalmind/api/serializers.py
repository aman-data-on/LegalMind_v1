"""Resource projections — locked 49.7, LEGAL-02, 45D/D-1.4.

Two structural guarantees live here rather than in prose:

* **A Finding's ``classification`` is never serialized without its
  ``evaluations``** (49.7 r1). ``serialize_finding`` has no flag to omit them, so
  no caller and no future endpoint can present the derived summary as if it were
  authoritative. The list endpoints nest evaluations for the same reason.
* **Confidential fields are omitted, not nulled** (49.7 r4, Step 52.4). The gate
  is ``redact_legal_position``, which is the single source of truth for what
  counts as an internal legal position.

``evidence_refs`` is always an array and may legitimately be empty — a MISSING
established by absence carries zero (49.7 r3, 45D.4.10). It is never ``null``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import FindingStatus
from legalmind.evaluation.workflow import (
    current_decision,
    evaluation_requires_decision,
)
from legalmind.security import permissions as P
from legalmind.security.authorization import redact_legal_position
from legalmind.security.resolver import effective_permissions
from legalmind.workflow.escalation import is_escalated

# For any PERSISTED Finding, `requirement_required=True` is not a fallback — it is
# correct. F-1 (via presence.py) means an optional Requirement with no mapped
# provision produces no Finding at all, so MISSING can only ever have come from a
# required Requirement, and MISSING is the only branch of D-3.5 where the flag
# changes the answer. Read-time derivation therefore needs no stored applicability
# column, and inventing a configuration key for one would be inventing structure.
_REQUIREMENT_REQUIRED = True


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


# ==========================================================================
# Evaluations — the authoritative layer (AB-1, 45B re-lock)
# ==========================================================================
def evidence_refs(db: DBSession, evaluation_id: UUID) -> list[str]:
    rows = db.execute(
        select(M.EvaluationEvidence.evidence_id)
        .where(M.EvaluationEvidence.evaluation_id == evaluation_id)
        .order_by(M.EvaluationEvidence.evidence_id)
    ).scalars().all()
    return [str(r) for r in rows]


def serialize_evaluation(db: DBSession, ev: M.Evaluation, *,
                         legal_position: bool,
                         escalated: bool = False) -> dict[str, Any]:
    result = ev.result or {}
    payload: dict[str, Any] = {
        "id": str(ev.id),
        "finding_id": str(ev.finding_id),
        "scope_key": ev.scope_key,
        "scope_label": ev.scope_label,
        "evaluation_kind": ev.evaluation_kind.value,
        "classification": ev.classification.value,
        "rule_outcome": ev.rule_outcome.value,
        "expected_value": ev.expected_value,
        "actual_value": ev.actual_value,
        "operator": ev.operator,
        "comparison": result.get("comparison"),
        "explanation": list(result.get("explanation") or []),
        # REC-07 — extraction diagnostics are persisted with the Evaluation for
        # auditability. Diagnostic metadata only: they cannot independently
        # produce or alter a legal finding, and they are not a legal position.
        "diagnostics": list(result.get("diagnostics") or []),
        "evaluated_facts": result.get("evaluated_facts"),
        "evidence_refs": evidence_refs(db, ev.id),
        "evaluator_type": ev.evaluator_type.value,
        "evaluator_version": ev.evaluator_version,
        "legal_rule_version_id": (str(ev.legal_rule_version_id)
                                  if ev.legal_rule_version_id else None),
        "requires_decision": evaluation_requires_decision(
            classification=ev.classification,
            rule_outcome=ev.rule_outcome,
            requirement_required=_REQUIREMENT_REQUIRED,
            escalated=escalated,
        ),
        "current_decision": None,
        "created_at": _iso(ev.created_at),
    }
    decision = current_decision(db, ev.id)
    if decision is not None:
        payload["current_decision"] = serialize_decision(decision)
    return redact_legal_position(payload, legal_position)


# ==========================================================================
# Findings — the derived summary layer
# ==========================================================================
def serialize_finding(db: DBSession, finding: M.Finding, *,
                      legal_position: bool) -> dict[str, Any]:
    """49.7 r1 — ``classification`` and ``evaluations`` travel together, always.

    There is deliberately no Finding-level ``rule_outcome``: none is persisted
    (J-2), and ``requires_decision`` is derived rather than stored (49.7 r2).
    """
    escalated = is_escalated(db, finding.id)
    evaluations = db.execute(
        select(M.Evaluation)
        .where(M.Evaluation.finding_id == finding.id)
        .order_by(M.Evaluation.scope_key, M.Evaluation.id)
    ).scalars().all()

    requirement = db.execute(
        select(M.RequirementVersion, M.Requirement)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.RequirementVersion.id == finding.requirement_version_id)
    ).first()
    rv, req = requirement if requirement else (None, None)

    return {
        "id": str(finding.id),
        "review_id": str(finding.review_id),
        "requirement": {
            "code": req.code if req else None,
            "name": rv.name if rv else None,
            "version_id": str(finding.requirement_version_id),
            "version_number": rv.version_number if rv else None,
        },
        # Derived, non-authoritative summary (45B re-lock, D-1.1).
        "classification": finding.classification.value,
        "status": finding.status.value,
        "requires_decision": finding.status in {
            FindingStatus.DECISION_REQUIRED,
            FindingStatus.AWAITING_CLARIFICATION,
        },
        "escalated": escalated,
        "evaluations": [
            serialize_evaluation(db, ev, legal_position=legal_position,
                                 escalated=escalated)
            for ev in evaluations
        ],
        "evidence": finding_evidence(db, finding.id),
        "created_at": _iso(finding.created_at),
        "updated_at": _iso(finding.updated_at),
    }


def finding_evidence(db: DBSession, finding_id: UUID) -> list[dict[str, Any]]:
    """Evidence must survive the evaluator (rule 11): every Finding carries the
    source locations its Evaluations were built from (42.16, 34.13)."""
    rows = db.execute(
        select(M.DocumentEvidence, M.FindingEvidence.relationship_type)
        .join(M.FindingEvidence,
              M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
        .where(M.FindingEvidence.finding_id == finding_id)
        .order_by(M.DocumentEvidence.page_number, M.DocumentEvidence.start_offset)
    ).all()
    return [
        {
            "id": str(e.id),
            "relationship_type": rel.value if hasattr(rel, "value") else str(rel),
            "page_number": e.page_number,
            "section_number": e.section_number,
            "section_title": e.section_title,
            "content": e.content,
            "source_type": e.source_type.value,
        }
        for e, rel in rows
    ]


# ==========================================================================
# Legal Decisions — append-only version chain (Step 31 r14/r20, AM-12)
# ==========================================================================
def serialize_decision(d: M.LegalDecision, *,
                       is_current: bool = True) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "evaluation_id": str(d.evaluation_id),
        "finding_id": str(d.finding_id),
        "decision_type": d.decision_type.value,
        "justification": d.justification,
        "decided_by": str(d.decided_by),
        "version_number": d.version_number,
        "is_current": is_current,
        "created_at": _iso(d.created_at),
    }


def serialize_decision_chain(chain: list[M.LegalDecision]) -> list[dict[str, Any]]:
    """The full chain, oldest first, with the highest version marked current
    (49.7). Prior versions are returned unmodified — they are never rewritten."""
    highest = max((d.version_number for d in chain), default=None)
    return [serialize_decision(d, is_current=d.version_number == highest)
            for d in chain]


# ==========================================================================
# Contracts, documents, reviews
# ==========================================================================
def serialize_contract(c: M.Contract) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "owner_id": str(c.owner_id),
        "name": c.name,
        "contract_type": c.contract_type,
        "status": c.status.value,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


def serialize_document_version(dv: M.DocumentVersion) -> dict[str, Any]:
    """``storage_key`` is deliberately absent: it is an internal storage
    coordinate, and the download endpoint is the only sanctioned way to the
    bytes."""
    return {
        "id": str(dv.id),
        "contract_id": str(dv.contract_id),
        "version_number": dv.version_number,
        "original_filename": dv.original_filename,
        "mime_type": dv.mime_type,
        "file_size_bytes": dv.file_size_bytes,
        "file_hash": dv.file_hash,
        # 34.15 — a document concern, deliberately separate from Review
        # lifecycle status (Step 30 r13).
        "processing_status": dv.processing_status.value,
        "extraction_status": (dv.extraction_status.value
                              if dv.extraction_status else None),
        "uploaded_by": str(dv.uploaded_by),
        "created_at": _iso(dv.created_at),
    }


def serialize_evidence(e: M.DocumentEvidence) -> dict[str, Any]:
    """One Evidence row as the document pane and every citation target see it.

    Locked 42.6 / Step 34: page number, section number and title, the verbatim
    content, its source (native text vs OCR — 34.8), and the character offsets that
    make "show me where you got that" a position rather than a paraphrase. The
    processing-run id is an internal lineage coordinate and is not exposed; the
    metadata JSONB is parser-internal and likewise stays server-side.
    """
    return {
        "id": str(e.id),
        "document_version_id": str(e.document_version_id),
        "page_number": e.page_number,
        "section_number": e.section_number,
        "section_title": e.section_title,
        "content": e.content,
        "source_type": e.source_type.value,
        "start_offset": e.start_offset,
        "end_offset": e.end_offset,
    }


def serialize_review(r: M.Review) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "contract_id": str(r.contract_id),
        "document_version_id": str(r.document_version_id),
        # Locked Step 30 / AUD-04: the snapshot is what makes the Review
        # reproducible, so it is part of the resource, not an internal detail.
        "configuration_snapshot_id": str(r.configuration_snapshot_id),
        "status": r.status.value,
        "created_by": str(r.created_by),
        "created_at": _iso(r.created_at),
        "started_at": _iso(r.started_at),
        "completed_at": _iso(r.completed_at),
    }


# ==========================================================================
# Configuration
# ==========================================================================
def serialize_requirement(db: DBSession, req: M.Requirement,
                          *, include_values: bool = False) -> dict[str, Any]:
    """Requirement with its version list.

    ``include_values=True`` additionally returns each version's Company Standard
    and Legal Rule **configuration values** plus ``created_by`` — the read path an
    admin screen needs ("current: 12 months; changed by X on Y"). Values were
    previously write-only through this API, which made the stored configuration
    unreviewable. Confidentiality holds because every caller is gated on
    `configuration.view`, and both roles holding it (Legal Reviewer, Legal Admin)
    also hold `legal.position.view` — the Legal Rule is the confidential Internal
    Legal Position (LEGAL-02), and it is never serialized on any other surface.
    """
    versions = db.execute(
        select(M.RequirementVersion)
        .where(M.RequirementVersion.requirement_id == req.id)
        .order_by(M.RequirementVersion.version_number)
    ).scalars().all()

    def _version(v: M.RequirementVersion) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": str(v.id),
            "version_number": v.version_number,
            "name": v.name,
            "description": v.description,
            "evaluator_type": v.evaluator_type.value,
            "created_at": _iso(v.created_at),
        }
        if include_values:
            cs = db.execute(
                select(M.CompanyStandardVersion)
                .where(M.CompanyStandardVersion.requirement_version_id == v.id)
                .order_by(M.CompanyStandardVersion.version_number.desc())
                .limit(1)).scalars().first()
            lr = db.execute(
                select(M.LegalRuleVersion)
                .where(M.LegalRuleVersion.requirement_version_id == v.id)
                .order_by(M.LegalRuleVersion.version_number.desc())
                .limit(1)).scalars().first()
            row["created_by"] = str(v.created_by) if v.created_by else None
            row["company_standard"] = cs.configuration if cs else None
            # Omitted, not nulled, when absent (49.7 r4 pattern): a Legal Rule
            # is genuinely optional (Step 20 r4).
            if lr is not None:
                row["legal_rule"] = {"rule_type": lr.rule_type.value,
                                     "configuration": lr.configuration}
        return row

    return {
        "id": str(req.id),
        "code": req.code,
        "status": req.status.value,
        "versions": [_version(v) for v in versions],
        "created_at": _iso(req.created_at),
    }


# ==========================================================================
# Audit
# ==========================================================================
def serialize_audit_event(e: M.AuditEvent, *,
                          legal_position: bool) -> dict[str, Any]:
    """``before_state``/``after_state`` are gated behind ``legal_position.view``.

    Locked 47.9 puts legal-workflow events in this table and 49.3 gates the
    endpoint on ``audit.view`` — which by Step 47's own default grants belongs to
    Super Admin, who has **no** ``legal_position.view``. Locked Step 24 r8 says a
    Super Admin "does not automatically have access to confidential contract or
    Legal content", so returning ``after_state: {"decision_type": ...}`` to them
    would defeat it. The envelope — who did what to which entity, when — is
    always returned; the payload is omitted, not nulled.
    """
    payload: dict[str, Any] = {
        "id": str(e.id),
        "actor_id": str(e.actor_id) if e.actor_id else None,
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id) if e.entity_id else None,
        "timestamp": _iso(e.timestamp),
        "request_id": (e.event_metadata or {}).get("request_id"),
    }
    if legal_position:
        payload["before_state"] = e.before_state
        payload["after_state"] = e.after_state
    return payload


# ==========================================================================
# Identity & access
# ==========================================================================
def serialize_user(db: DBSession, u: M.User) -> dict[str, Any]:
    """S-4 — no endpoint returns credential material. ``user_identities`` is not
    joined here at all, so ``credential_hash`` is not merely filtered out of the
    response: it is never selected."""
    roles = db.execute(
        select(M.Role.code)
        .join(M.UserRole, M.UserRole.role_id == M.Role.id)
        .where(M.UserRole.user_id == u.id)
        .order_by(M.Role.code)
    ).scalars().all()
    return {
        "id": str(u.id),
        "email": u.email,
        "name": u.name,
        "status": u.status.value,
        "roles": list(roles),
        "created_at": _iso(u.created_at),
    }


def serialize_role(db: DBSession, r: M.Role) -> dict[str, Any]:
    perms = db.execute(
        select(M.Permission.name)
        .join(M.RolePermission,
              M.RolePermission.permission_id == M.Permission.id)
        .where(M.RolePermission.role_id == r.id)
        .order_by(M.Permission.name)
    ).scalars().all()
    return {
        "id": str(r.id),
        "code": r.code,
        "name": r.name,
        "permissions": list(perms),
        # Makes the SEC-02/ROLE-05 boundary visible to an administrator without
        # them having to know which names are special.
        "confers_legal_authority": sorted(
            set(perms) & P.LEGAL_AUTHORITY_PERMISSIONS),
    }


def serialize_session_identity(db: DBSession, u: M.User) -> dict[str, Any]:
    """``GET /auth/session`` — 49.2, 43.31, 47.6 r3.

    The permission array is a **convenience projection for presentation gating
    only**. Every request is authorized server-side regardless of it, which is
    why it is safe to hand over and why it is resolved fresh here rather than
    read from the session (S-1).
    """
    return {
        "user_id": str(u.id),
        "email": u.email,
        "name": u.name,
        "status": u.status.value,
        "permissions": sorted(effective_permissions(db, u.id)),
    }

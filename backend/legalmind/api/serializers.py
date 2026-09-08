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
from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for
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
                         escalated: bool = False,
                         requirement_code: str | None = None) -> dict[str, Any]:
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
    prohibition = constitution_prohibition_for(requirement_code, ev.actual_value)
    if prohibition is not None:
        payload["constitution_prohibition"] = prohibition
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
                                 escalated=escalated,
                                 requirement_code=req.code if req else None)
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
        # AB-12 r6 — set means read-only and out of the working lists; never a
        # sixth ContractStatus value.
        "archived_at": _iso(c.archived_at),
        # AB-13 r2 — who this deal is with. `null` when unlinked, which is the
        # honest state for every contract predating the record.
        "counterparty_id": (str(c.counterparty_id) if c.counterparty_id else None),
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


#: The declared keys of `document_versions.metadata` (locked 42.4 JSONB) that
#: are part of the resource. `duplicate_of` is not: it is reported once, on the
#: upload response (34.5), not as a standing attribute.
DECLARED_KEYS: tuple[str, ...] = ("source", "counterparty", "effective_date")


def declared_metadata(dv: M.DocumentVersion) -> dict[str, Any]:
    """Source / counterparty / effective date, present ONLY when declared.

    Omitted, never nulled — the same discipline `SEC-07` applies to confidential
    fields, applied here for a different reason: an absent declaration is a
    fact ("nobody said"), and every version created before 2026-09-06 has none.
    """
    meta = dv.doc_metadata or {}
    return {k: meta[k] for k in DECLARED_KEYS if meta.get(k) is not None}


def serialize_counterparty(c: M.Counterparty) -> dict[str, Any]:
    """AB-13 r1. `industry` and `relationship_notes` are OMITTED when nobody has
    typed them — the same discipline `SEC-07` applies to confidential fields,
    for a different reason: an unknown industry is a fact, and a null would
    invite the UI to render "Industry: —" as though it had been checked."""
    payload: dict[str, Any] = {
        "id": str(c.id),
        "name": c.name,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }
    if c.industry:
        payload["industry"] = c.industry
    if c.relationship_notes:
        payload["relationship_notes"] = c.relationship_notes
    return payload


def serialize_document_version(dv: M.DocumentVersion) -> dict[str, Any]:
    """``storage_key`` is deliberately absent: it is an internal storage
    coordinate, and the download endpoint is the only sanctioned way to the
    bytes."""
    return {
        **declared_metadata(dv),
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
    meta = e.evidence_metadata or {}
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
        # Whether this row BEGINS a section, as recorded at segmentation. The
        # rest of the metadata JSONB stays server-side as the note above says;
        # this one field is exposed because the document outline is otherwise
        # unbuildable client-side — the alternative is the UI re-deriving
        # structure from text, which is exactly the re-derivation rule 18 keeps
        # out of the interface. Presentation only: it decides no legal outcome.
        "is_heading": bool(meta.get("heading")),
        # The document's OWN annexure/schedule title when this row is one (44.4,
        # 2026-09-06) — present only then, so the outline can divide the parts
        # the file declares without the UI guessing at them.
        **({"annexure": meta["annexure"]} if meta.get("annexure") else {}),
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
#: Actions whose payloads are IDENTITY AND ACCESS administration and nothing else.
#:
#: `before_state`/`after_state` are gated behind `legal_position.view` because
#: this one table also carries legal-workflow events, and locked Step 24 r8 says a
#: platform administrator "does not automatically have access to confidential
#: contract or Legal content" — returning `after_state: {"decision_type": ...}`
#: to them would defeat it.
#:
#: But that gate, applied to EVERY action, also hides `{"role": "USER"}` from the
#: administrator who just granted it, which makes the trail useless for the one
#: job it is theirs to do. These prefixes are the exception, and they are chosen
#: by what the payloads actually contain:
#:
#:   admin.*   {"email"}, {"role"}, {"name","status","department_id"},
#:             {"code","name"}, {"permissions"}          — accounts and access
#:   auth.*    {"sessions_revoked"}, session ids          — sign-in lifecycle
#:
#: Everything else stays gated, and two in particular MUST: `contract.archived`
#: carries the contract's NAME in `before`, and `contract.ownership_transferred`
#: carries the free-text reason a Department Lead wrote about a deal. Neither is
#: identity administration, and a Platform Admin has no business reading either.
#: Prefix-matched deliberately: a future `admin.*` event inherits the rule, and a
#: future `contract.*` or `legal.*` one inherits the gate.
ADMINISTRATIVE_ACTION_PREFIXES = ("admin.", "auth.")

#: Entity kinds whose display label may be resolved for the audit view. Contracts,
#: reviews, findings and evaluations are deliberately ABSENT: naming them would
#: hand a Platform Admin the one thing the whole scope model withholds, through a
#: screen they are entitled to open. An entity outside this set is shown by type
#: and id, which is what an auditor needs to correlate it anyway.
AUDIT_LABELLED_ENTITIES = frozenset({"user", "department", "role", "session"})


def is_administrative_action(action: str) -> bool:
    return action.startswith(ADMINISTRATIVE_ACTION_PREFIXES)


def serialize_audit_event(e: M.AuditEvent, *, legal_position: bool,
                          actors: dict[UUID, M.User] | None = None,
                          labels: dict[UUID, str] | None = None) -> dict[str, Any]:
    """Who did what, to what, when — and, where it is theirs to see, with what.

    The envelope is always returned. The payload follows
    `ADMINISTRATIVE_ACTION_PREFIXES`: omitted, never nulled, so an absent field
    conveys nothing.

    ``actors``/``labels`` are the batched lookups from the list endpoint. Without
    them the event still serializes — the ids are the fact, the names are the
    courtesy.
    """
    actor = (actors or {}).get(e.actor_id) if e.actor_id else None
    payload: dict[str, Any] = {
        "id": str(e.id),
        "actor_id": str(e.actor_id) if e.actor_id else None,
        # Null actor is not "unknown": 42.18 makes it nullable so a
        # pre-authentication event (a failed login for an account that may not
        # exist) can be recorded without inventing a principal for it.
        "actor": ({"id": str(actor.id), "name": actor.name, "email": actor.email}
                  if actor is not None else None),
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": str(e.entity_id) if e.entity_id else None,
        "entity_label": ((labels or {}).get(e.entity_id)
                         if e.entity_id and e.entity_type in AUDIT_LABELLED_ENTITIES
                         else None),
        "administrative": is_administrative_action(e.action),
        "timestamp": _iso(e.timestamp),
        "request_id": (e.event_metadata or {}).get("request_id"),
    }
    if legal_position or is_administrative_action(e.action):
        payload["before_state"] = e.before_state
        payload["after_state"] = e.after_state
    return payload


def audit_lookups(db: DBSession,
                  events: list[M.AuditEvent]) -> tuple[dict, dict]:
    """Actor accounts and entity labels for a page of events, in three queries.

    Only `AUDIT_LABELLED_ENTITIES` are resolved — see that constant for why a
    contract's name is not among them.
    """
    actor_ids = {e.actor_id for e in events if e.actor_id}
    actors = {} if not actor_ids else {
        u.id: u for u in db.execute(
            select(M.User).where(M.User.id.in_(actor_ids))).scalars()
    }
    labels: dict[UUID, str] = {}
    by_type: dict[str, set] = {}
    for e in events:
        if e.entity_id and e.entity_type in AUDIT_LABELLED_ENTITIES:
            by_type.setdefault(e.entity_type, set()).add(e.entity_id)
    if by_type.get("user"):
        for uid, email in db.execute(
            select(M.User.id, M.User.email)
            .where(M.User.id.in_(by_type["user"]))
        ):
            labels[uid] = email
    if by_type.get("department"):
        for did, name in db.execute(
            select(M.Department.id, M.Department.name)
            .where(M.Department.id.in_(by_type["department"]))
        ):
            labels[did] = name
    if by_type.get("role"):
        for rid, name in db.execute(
            select(M.Role.id, M.Role.name).where(M.Role.id.in_(by_type["role"]))
        ):
            labels[rid] = name
    return actors, labels


# ==========================================================================
# Identity & access
# ==========================================================================
def serialize_department(d: M.Department) -> dict[str, Any]:
    """Non-optional on purpose: a caller that may have no department says so at
    the call site, so `None` never travels through here as a valid value."""
    return {"id": str(d.id), "code": d.code, "name": d.name,
            "created_at": _iso(d.created_at)}


def _department_of(db: DBSession, u: M.User) -> M.Department | None:
    return db.get(M.Department, u.department_id) if u.department_id else None


class UserContext:
    """Everything an administration screen shows about a page of accounts,
    fetched in four grouped queries instead of four per row.

    Why it exists: ``serialize_user`` ran one roles query per user, and the
    administration list needs three more facts per user on top of that. At 25
    rows that is 100 round trips for one screen. Every field here comes from a
    table LegalMind already keeps — nothing is invented and no column is added:

    ```text
    roles          user_roles  ⋈  roles
    department     users.department_id  →  departments
    identities     user_identities.provider / .last_used_at   (never the hash)
    provisioned_by the `admin.user_created` audit row's actor  (AUD-01)
    ```

    ``credential_hash`` is not merely filtered out of the response — S-4 means it
    is never selected, so the identity query names its columns explicitly.
    """

    __slots__ = ("actors", "departments", "identities", "provisioned_by", "roles")

    def __init__(self, db: DBSession, users: list[M.User]) -> None:
        ids = [u.id for u in users]
        self.roles: dict[UUID, list[str]] = {}
        self.departments: dict[UUID, M.Department] = {}
        self.identities: dict[UUID, list[tuple[str, Any]]] = {}
        self.provisioned_by: dict[UUID, UUID] = {}
        self.actors: dict[UUID, M.User] = {}
        if not ids:
            return

        for user_id, code in db.execute(
            select(M.UserRole.user_id, M.Role.code)
            .join(M.Role, M.Role.id == M.UserRole.role_id)
            .where(M.UserRole.user_id.in_(ids))
            .order_by(M.Role.code)
        ):
            self.roles.setdefault(user_id, []).append(code)

        department_ids = {u.department_id for u in users if u.department_id}
        if department_ids:
            self.departments = {
                d.id: d for d in db.execute(
                    select(M.Department).where(M.Department.id.in_(department_ids))
                ).scalars()
            }

        # S-4: the columns are named, so the hash is never in the result set.
        for user_id, provider, last_used in db.execute(
            select(M.UserIdentity.user_id, M.UserIdentity.provider,
                   M.UserIdentity.last_used_at)
            .where(M.UserIdentity.user_id.in_(ids))
        ):
            self.identities.setdefault(user_id, []).append(
                (provider.value, last_used))

        # Who provisioned each account. The audit trail is append-only (AUD-01),
        # so the earliest `admin.user_created` row for an account is the record
        # of its creation — there is no `created_by` column and none is added.
        # An account with no such row was not created through the admin API: the
        # seed made it, or (47.1.3 r2) an SSO identity was linked to it.
        for entity_id, actor_id in db.execute(
            select(M.AuditEvent.entity_id, M.AuditEvent.actor_id)
            .where(M.AuditEvent.action == "admin.user_created",
                   M.AuditEvent.entity_type == "user",
                   M.AuditEvent.entity_id.in_(ids))
            .order_by(M.AuditEvent.timestamp)
        ):
            if entity_id is not None and actor_id is not None:
                self.provisioned_by.setdefault(entity_id, actor_id)

        if self.provisioned_by:
            self.actors = {
                a.id: a for a in db.execute(
                    select(M.User).where(
                        M.User.id.in_(set(self.provisioned_by.values())))
                ).scalars()
            }


def serialize_user(db: DBSession, u: M.User, *,
                   context: UserContext | None = None) -> dict[str, Any]:
    """S-4 — no endpoint returns credential material.

    ``context`` is the batched form used by the list endpoints; omit it and the
    same facts are gathered for this one account. Both paths produce the same
    shape, so a single user and a row in a list can never disagree.
    """
    ctx = context if context is not None else UserContext(db, [u])
    identities = ctx.identities.get(u.id, [])
    last_used = [t for _, t in identities if t is not None]
    provisioner = ctx.actors.get(ctx.provisioned_by.get(u.id))  # type: ignore[arg-type]
    department = (ctx.departments.get(u.department_id)
                  if u.department_id else None)
    return {
        "id": str(u.id),
        "email": u.email,
        "name": u.name,
        "status": u.status.value,
        "roles": ctx.roles.get(u.id, []),
        # AB-12 r3 — the boundary a Department Lead's scope is bounded by.
        "department": serialize_department(department) if department else None,
        # How this account can sign in. Names only — never a subject, never a
        # hash (S-4). Empty means no credential has been provisioned yet, which
        # is a real and useful administrative state: the account exists and
        # cannot yet authenticate by any route.
        "auth_providers": sorted({p for p, _ in identities}),
        # Last successful authentication, from `user_identities.last_used_at`,
        # which both the password and OIDC paths stamp on sign-in. Null means
        # never signed in — not "unknown".
        "last_login_at": _iso(max(last_used)) if last_used else None,
        "provisioned_by": ({"id": str(provisioner.id), "name": provisioner.name,
                            "email": provisioner.email}
                           if provisioner is not None else None),
        "created_at": _iso(u.created_at),
        "updated_at": _iso(u.updated_at),
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
        # AB-12 r10 — what KIND of role this is, so a screen can say "Department
        # Lead" and keep the retained legal roles out of the everyday picker
        # without anyone decoding a code. Roles created through the API are
        # "custom".
        "tier": P.ROLE_TIERS.get(r.code, "custom"),
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
        # AB-12 r3 — presentation only, like `permissions`: lets the UI say
        # "Department deals" for the right department, or explain that the
        # account is in none yet. The server scopes every query on its own.
        "department": (serialize_department(department)
                       if (department := _department_of(db, u)) else None),
    }

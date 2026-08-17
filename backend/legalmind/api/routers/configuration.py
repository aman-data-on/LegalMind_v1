"""Legal Configuration — locked 49.3, Step 29, 42.7–42.12, ENG-09.

The rule that shapes this module is rule 21 rather than any API rule: **LegalMind
must never manufacture legal source material.** Every ``configuration`` payload is
therefore accepted opaquely and stored exactly as the authorized Legal admin
supplied it. Nothing here supplies a default threshold, a tolerance, a carve-out or
a keyword group, and no endpoint invents a Requirement.

Locked rule 16 is the other constraint: configuration is versioned, Reviews use
snapshots, publishing never mutates an existing Review, and drafts never affect a
comparison. Publishing produces a new immutable snapshot; it never edits one.
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.pagination import Page, page_params, run
from legalmind.api.schemas import (
    ConfigurationPublish,
    RequirementCreate,
    RequirementVersionCreate,
)
from legalmind.api.serializers import serialize_requirement
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["configuration"])


@router.get("/requirements")
def list_requirements(guard: Guard = Depends(get_guard),
                      page: Page = Depends(page_params),
                      status: E.ConfigStatus | None = Query(default=None)) -> dict:
    guard.permission(P.CONFIGURATION_VIEW)
    stmt = select(M.Requirement)
    if status is not None:
        stmt = stmt.where(M.Requirement.status == status)
    rows, total = run(guard.db, stmt, page,
                      M.Requirement.code, M.Requirement.id)
    return paginated([serialize_requirement(guard.db, r) for r in rows],
                     page=page.page, page_size=page.page_size, total=total)


@router.get("/requirements/{requirement_id}")
def get_requirement(requirement_id: UUID,
                    guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONFIGURATION_VIEW)
    req = guard.db.get(M.Requirement, requirement_id)
    if req is None:
        raise NotVisible("requirement not found")
    return data(serialize_requirement(guard.db, req))


@router.post("/requirements", status_code=201)
def create_requirement(body: RequirementCreate,
                       guard: Guard = Depends(get_guard)) -> dict:
    """A Requirement starts as DRAFT and carries no content until a version
    exists. Which Requirements V1 ships with is **N-24b, an open owner
    decision** — this endpoint is the mechanism, not the answer."""
    guard.permission(P.CONFIGURATION_DRAFT)
    code = body.code.strip()
    if guard.db.execute(
        select(M.Requirement.id).where(M.Requirement.code == code)
    ).first():
        raise Conflict("a Requirement with that code already exists")
    req = M.Requirement(code=code, status=E.ConfigStatus.DRAFT)
    guard.db.add(req)
    guard.db.flush()
    return data(serialize_requirement(guard.db, req))


@router.post("/requirements/{requirement_id}/versions", status_code=201)
def create_requirement_version(requirement_id: UUID,
                               body: RequirementVersionCreate,
                               guard: Guard = Depends(get_guard)) -> dict:
    """Draft one new version of a Requirement and its configuration artifacts.

    They are created together because locked 42.12 makes the company standard,
    mapping rules and evaluation rules NOT NULL in a snapshot item: a Requirement
    version without them can never be published, so allowing the halfway state
    would only produce a publish that fails later. The Legal Rule is genuinely
    optional (Step 20 r4).

    Existing versions are never edited. A new version is appended, which is what
    keeps a historical Review reproducible (rule 16, AUD-04).
    """
    guard.permission(P.CONFIGURATION_DRAFT)
    req = guard.db.get(M.Requirement, requirement_id)
    if req is None:
        raise NotVisible("requirement not found")

    next_version = (guard.db.execute(
        select(func.max(M.RequirementVersion.version_number))
        .where(M.RequirementVersion.requirement_id == requirement_id)
    ).scalar() or 0) + 1

    rv = M.RequirementVersion(
        requirement_id=requirement_id,
        version_number=next_version,
        name=body.name,
        description=body.description,
        # 42.7 — SINGULAR. A presence condition plus value criteria are two
        # Requirements over the same clause, not one with two evaluators (N-36).
        evaluator_type=body.evaluator_type,
        created_by=guard.user_id,
    )
    guard.db.add(rv)
    guard.db.flush()

    guard.db.add(M.CompanyStandardVersion(
        requirement_version_id=rv.id, version_number=1,
        configuration=body.company_standard, created_by=guard.user_id))
    guard.db.add(M.MappingRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        rules=body.mapping_rules, created_by=guard.user_id))
    guard.db.add(M.EvaluationRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        # ENG-03 — Mapping Rules are not Evaluation Rules; the evaluator type is
        # carried on both so a mismatch is detectable rather than assumed.
        evaluator_type=body.evaluator_type,
        rules=body.evaluation_rules, created_by=guard.user_id))
    if body.legal_rule is not None:
        guard.db.add(M.LegalRuleVersion(
            requirement_version_id=rv.id, version_number=1,
            rule_type=body.legal_rule.rule_type,
            configuration=body.legal_rule.configuration,
            created_by=guard.user_id))
    guard.db.flush()
    return data(serialize_requirement(guard.db, req))


@router.post("/configuration/publish", status_code=201)
def publish(body: ConfigurationPublish,
            guard: Guard = Depends(get_guard)) -> dict:
    """Create an immutable configuration snapshot — locked Step 29, 42.12, AUD-04.

    ``requirement_codes`` activates those Requirements (DRAFT → ACTIVE); the
    snapshot then pins the latest version of every ACTIVE Requirement. Requirements
    still in DRAFT are excluded, which is locked rule 16's "drafts never affect
    comparisons" enforced at the only place it can be.

    **Fail closed (ENG-09).** If any ACTIVE Requirement version is missing its
    company standard, mapping rules or evaluation rules, the publish is refused and
    names the Requirement. Publishing a partial snapshot would produce Reviews that
    silently skipped a Requirement.
    """
    guard.permission(P.CONFIGURATION_PUBLISH)

    if body.requirement_codes:
        for code in body.requirement_codes:
            req = guard.db.execute(
                select(M.Requirement).where(M.Requirement.code == code)
            ).scalars().first()
            if req is None:
                raise BusinessRuleRejected(f"unknown Requirement code: {code}")
            if req.status is E.ConfigStatus.DRAFT:
                req.status = E.ConfigStatus.ACTIVE
        guard.db.flush()

    active = guard.db.execute(
        select(M.Requirement)
        .where(M.Requirement.status == E.ConfigStatus.ACTIVE)
        .order_by(M.Requirement.code)
    ).scalars().all()
    if not active:
        raise BusinessRuleRejected(
            "nothing to publish: no Requirement is ACTIVE")

    items: list[dict[str, str | None]] = []
    incomplete: list[str] = []
    for req in active:
        rv = guard.db.execute(
            select(M.RequirementVersion)
            .where(M.RequirementVersion.requirement_id == req.id)
            .order_by(M.RequirementVersion.version_number.desc())
            .limit(1)
        ).scalars().first()
        if rv is None:
            incomplete.append(f"{req.code}: no version")
            continue
        cs = _latest(guard, M.CompanyStandardVersion, rv.id)
        mr = _latest(guard, M.MappingRuleVersion, rv.id)
        er = _latest(guard, M.EvaluationRuleVersion, rv.id)
        lr = _latest(guard, M.LegalRuleVersion, rv.id)      # optional, Step 20 r4
        missing = [n for n, v in (("company standard", cs), ("mapping rules", mr),
                                  ("evaluation rules", er)) if v is None]
        if missing:
            incomplete.append(f"{req.code}: missing {', '.join(missing)}")
            continue
        items.append({
            "requirement_version_id": str(rv.id),
            "company_standard_version_id": str(cs.id),
            "legal_rule_version_id": str(lr.id) if lr else None,
            "mapping_rule_version_id": str(mr.id),
            "evaluation_rule_version_id": str(er.id),
        })

    if incomplete:
        raise BusinessRuleRejected(
            "configuration is incomplete: " + "; ".join(sorted(incomplete)))

    digest = hashlib.sha256(
        json.dumps(sorted(items, key=lambda i: i["requirement_version_id"]),
                   sort_keys=True).encode("utf-8")
    ).hexdigest()

    existing = guard.db.execute(
        select(M.ConfigurationSnapshot)
        .where(M.ConfigurationSnapshot.snapshot_hash == digest)
    ).scalars().first()
    if existing is not None:
        # Republishing identical configuration yields the identical snapshot —
        # which is what makes `UNIQUE(snapshot_hash)` the right constraint and
        # keeps determinism (rule 9) rather than accumulating equivalent rows.
        return data(_snapshot_payload(existing, items, reused=True))

    snapshot = M.ConfigurationSnapshot(snapshot_hash=digest,
                                       created_by=guard.user_id)
    guard.db.add(snapshot)
    guard.db.flush()
    for item in items:
        guard.db.add(M.ConfigurationSnapshotItem(
            snapshot_id=snapshot.id,
            requirement_version_id=UUID(item["requirement_version_id"]),
            company_standard_version_id=UUID(item["company_standard_version_id"]),
            legal_rule_version_id=(UUID(item["legal_rule_version_id"])
                                   if item["legal_rule_version_id"] else None),
            mapping_rule_version_id=UUID(item["mapping_rule_version_id"]),
            evaluation_rule_version_id=UUID(item["evaluation_rule_version_id"]),
        ))
    guard.db.flush()
    return data(_snapshot_payload(snapshot, items, reused=False))


def _latest(guard: Guard, model, requirement_version_id: UUID):
    return guard.db.execute(
        select(model)
        .where(model.requirement_version_id == requirement_version_id)
        .order_by(model.version_number.desc())
        .limit(1)
    ).scalars().first()


def _snapshot_payload(snapshot: M.ConfigurationSnapshot,
                      items: list[dict], *, reused: bool) -> dict:
    return {
        "id": str(snapshot.id),
        "snapshot_hash": snapshot.snapshot_hash,
        "created_at": snapshot.created_at.isoformat(),
        "requirement_count": len(items),
        "reused_existing": reused,
    }

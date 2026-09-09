"""The three words a reader sees — owner's FINAL product decision, 2026-09-09.

ACCEPTED · NEEDS_REVIEW · NOT_ACCEPTED. Derived here, server-side, from the
authoritative result and nothing else: the classification, the approved
Legal Rule's own disposition (`rule_outcome`) and the Constitution citation.
Never stored, never an axis (DECISION_STATE_MODEL keeps five; this is a
projection of them), never read by an evaluator, never fed by the LLM.

Not a rename of the four classifications:

  MATCH                              -> ACCEPTED
  Constitution prohibition cited     -> NOT_ACCEPTED (the narrowest condition)
  DEVIATION / MISSING with the approved rule's own UNACCEPTABLE
                                     -> NOT_ACCEPTED (evidence-supported: the
                                        evaluator only rules a value it read)
  DEVIATION / MISSING left unruled (NOT_APPLICABLE, APPROVAL_REQUIRED)
                                     -> NEEDS_REVIEW
  UNABLE_TO_EVALUATE / CONFLICT / anything unknown
                                     -> NEEDS_REVIEW, always: uncertainty is
                                        never converted into a rejection.

Today the zero-tolerance rule disposes every DEVIATION as UNACCEPTABLE, and
no approved rule disposes absence — so a MISSING is NEEDS_REVIEW until one
does (a lawyer may find the missing clause acceptable as-is; owner,
2026-09-09). That is the rule's silence, read honestly, not a hardcoded
outcome: give the rule a disposition for absence and this function follows it.
"""
from __future__ import annotations

from legalmind.domain.enums import FindingClassification as C, RuleOutcome as R

ACCEPTED, NEEDS_REVIEW, NOT_ACCEPTED = "ACCEPTED", "NEEDS_REVIEW", "NOT_ACCEPTED"
_RANK = {ACCEPTED: 0, NEEDS_REVIEW: 1, NOT_ACCEPTED: 2}
_RULED = {C.DEVIATION, C.MISSING}


def user_status(classification: C, rule_outcome: R | None = None,
                prohibited: bool = False) -> str:
    if prohibited:
        return NOT_ACCEPTED
    if classification is C.MATCH:
        return ACCEPTED
    if classification in _RULED and rule_outcome is R.UNACCEPTABLE:
        return NOT_ACCEPTED
    return NEEDS_REVIEW


def worst(statuses: list[str], fallback: str) -> str:
    """A Finding's status is its worst Evaluation's; with none, the fallback."""
    return max(statuses, key=_RANK.__getitem__) if statuses else fallback


def by_finding(db, review_ids) -> dict:
    """{review_id: {finding_id: status}} for whole reviews in one query — the
    report, the dashboard list and the version comparison all use this so a
    count never disagrees with the card it summarises."""
    from sqlalchemy import select
    from legalmind.db import models as M
    from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for
    ids = list(review_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(M.Finding.review_id, M.Finding.id, M.Finding.classification,
               M.Evaluation.classification, M.Evaluation.rule_outcome,
               M.Evaluation.actual_value, M.Requirement.code)
        .outerjoin(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
        .join(M.RequirementVersion,
              M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id.in_(ids))
    ).all()
    per: dict = {}
    for review_id, finding_id, f_cls, e_cls, outcome, actual, code in rows:
        found = per.setdefault(review_id, {}).setdefault(finding_id, [])
        if e_cls is not None:
            prohibited = constitution_prohibition_for(code, actual) is not None
            found.append(user_status(e_cls, outcome, prohibited))
        else:
            found.append(user_status(f_cls))
    return {rid: {fid: worst(statuses, NEEDS_REVIEW) for fid, statuses in fs.items()}
            for rid, fs in per.items()}


def counts(statuses_by_finding: dict) -> dict:
    out = {ACCEPTED: 0, NEEDS_REVIEW: 0, NOT_ACCEPTED: 0}
    for status in statuses_by_finding.values():
        out[status] += 1
    return out

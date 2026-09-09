"""The three words a reader sees — owner's decision, 2026-09-09 (AM-56, superseding
AM-53's vocabulary and mapping).

ACCEPTABLE · REQUIRES_MODIFICATION · NEEDS_DECISION. Derived here, server-side,
from the engine's five determinations — never stored, never an axis
(DECISION_STATE_MODEL keeps five; this is a projection of them), never read by
an evaluator, never fed by the LLM. The backend keeps every determination;
only the reader's word is three-valued.

  Does the clause match the Constitution?            MATCH     -> ACCEPTABLE
  Does it deviate from a defined position?           DEVIATION -> REQUIRES_MODIFICATION
  Is a required clause missing?                      MISSING   -> REQUIRES_MODIFICATION
     (an optional absence produces no Finding at all — F-1 — so every MISSING
      Finding is a required one)
  Is the clause or the Constitution unclear/conflicting?
                                UNABLE_TO_EVALUATE / CONFLICT   -> NEEDS_DECISION
  Does the Constitution have no position on the topic?
     A clause with no Requirement to compare against is never a Finding: it is
     recorded as an UNMATCHED PROVISION (REC-02) and routed to a person on the
     report — the same "needs a decision" destination, outside this function.

The Rule Outcome and any Constitution citation still travel with the Evaluation
for the reader who may see them; they no longer move the word.
"""
from __future__ import annotations

from legalmind.domain.enums import FindingClassification as C
from legalmind.domain.enums import RuleOutcome as R

ACCEPTABLE = "ACCEPTABLE"
REQUIRES_MODIFICATION = "REQUIRES_MODIFICATION"
NEEDS_DECISION = "NEEDS_DECISION"
_RANK = {ACCEPTABLE: 0, NEEDS_DECISION: 1, REQUIRES_MODIFICATION: 2}
_MODIFY = {C.DEVIATION, C.MISSING}


def user_status(classification: C, rule_outcome: R | None = None,
                prohibited: bool = False) -> str:
    """`rule_outcome` and `prohibited` are accepted for the callers' sake and
    recorded beside the word; since AM-56 the word follows the classification."""
    if classification is C.MATCH:
        return ACCEPTABLE
    if classification in _MODIFY:
        return REQUIRES_MODIFICATION
    return NEEDS_DECISION


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
    return {rid: {fid: worst(statuses, NEEDS_DECISION) for fid, statuses in fs.items()}
            for rid, fs in per.items()}


def counts(statuses_by_finding: dict) -> dict:
    out = {ACCEPTABLE: 0, REQUIRES_MODIFICATION: 0, NEEDS_DECISION: 0}
    for status in statuses_by_finding.values():
        out[status] += 1
    return out

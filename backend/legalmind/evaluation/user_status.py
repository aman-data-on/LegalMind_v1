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

import json
import re

# The pure mapping lives in `legalmind.domain.user_status` since 2026-09-10 (the
# assist lane reads it; it may import `domain`, never `evaluation`). Re-exported
# here so every existing caller keeps its import.
from legalmind.domain.user_status import (  # noqa: F401
    _MODIFY,
    _RANK,
    ACCEPTABLE,
    NEEDS_DECISION,
    REQUIRES_MODIFICATION,
    user_status,
    worst,
)


def by_finding(db, review_ids) -> dict:
    """{review_id: {finding_id: status}} for whole reviews in one query — every
    RAW Finding gets its own entry. The version comparison wants exactly this
    (one status per Finding, section by section); a reader-facing TOTAL wants
    `folded_user_status_counts` below instead, which is what the dashboard list
    and the exported report use — see its docstring for why they differ."""
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


# The abbreviations our own requirement codes use, spelt out for a reader's
# title — copied from `requirementTitle`'s `CODE_WORDS` in
# frontend/src/components/workspace/findingLanguage.ts. Keep the two in sync by
# hand; there is no shared runtime between the two languages to enforce it.
_CODE_WORDS = {
    "GOVLAW": "governing law", "CONF": "confidentiality", "LIAB": "liability",
    "TERM": "termination", "AUTORENEW": "auto-renewal", "IP": "IP", "KYC": "KYC",
    "CARVEOUTS": "carve-outs", "CARVEOUT": "carve-out", "NON": "Non",
}


def _requirement_title(code: str | None, name: str | None, type_codes: set[str]) -> str:
    """Ported from `requirementTitle` (findingLanguage.ts): two Findings in
    DIFFERENT document-type families fold into one card exactly when they
    reduce to the SAME reader title (`AUTORENEW-MSA-001` and
    `AUTORENEW-TOS-001` both read "Auto-renewal"), so the fold key needs this
    parsed title, not the raw requirement code."""
    name = (name or "").strip()
    code = (code or "").strip()
    if name and name != code:
        return name
    if not code:
        return "Requirement"
    words = [_CODE_WORDS.get(part.upper(), part.lower())
             for part in re.split(r"[-_\s]+", code)
             if part and not part.isdigit() and part.upper() not in type_codes]
    if not words:
        return code
    sentence = re.sub(r"\bNon ", "Non-", " ".join(words))
    return sentence[0].upper() + sentence[1:]


def _stable_json(value):
    return json.dumps(value, sort_keys=True, default=str) if value is not None else None


def folded_user_status_counts(db, review_ids) -> dict:
    """{review_id: {ACCEPTABLE: n, REQUIRES_MODIFICATION: n, NEEDS_DECISION: n}}
    — the reader-facing TOTAL, folded the same way the Summary tab and findings
    pane fold client-side (`mergeEquivalentFindings` in findingLanguage.ts).

    AM-51 measures one clause against more than one Requirement family on
    purpose (an NDA confidentiality-survival clause is measured against both
    the NDA and the MSA standard for it) — both Findings are real, auditable
    work, but a reader who opens the document sees one card for it, not two.
    Before this function existed, the dashboard list and the exported report
    called `by_finding`/`counts` directly and counted every raw Finding, while
    the Summary tab folded first — so the SAME review showed two different
    totals depending on which screen you read it from.

    ponytail: the fold key omits `nextStep`'s one extra distinguishing case (a
    Finding that already carries a recorded Legal Decision) to avoid an extra
    per-evaluation query on a batched list endpoint — two otherwise-identical
    Findings that differ only in whether a decision has been recorded on them
    would fold into one card here. Widen the key with `current_decision` if
    that proves to matter in practice.
    """
    from sqlalchemy import select

    from legalmind.db import models as M
    from legalmind.domain.document_types import DOCUMENT_TYPES
    from legalmind.domain.enums import FindingStatus
    from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for

    ids = list(review_ids)
    zero = {ACCEPTABLE: 0, REQUIRES_MODIFICATION: 0, NEEDS_DECISION: 0}
    out = {rid: dict(zero) for rid in ids}
    if not ids:
        return out

    rows = db.execute(
        select(M.Finding.review_id, M.Finding.id, M.Finding.classification,
               M.Finding.status, M.Evaluation.id, M.Evaluation.classification,
               M.Evaluation.rule_outcome, M.Evaluation.actual_value,
               M.Evaluation.expected_value, M.Requirement.code,
               M.RequirementVersion.name)
        .outerjoin(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
        .join(M.RequirementVersion,
              M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id.in_(ids))
        .order_by(M.Evaluation.scope_key, M.Evaluation.id)
    ).all()

    eval_ids = [row[4] for row in rows if row[4] is not None]
    evidence_by_eval: dict = {}
    if eval_ids:
        for eval_id, evidence_id in db.execute(
            select(M.EvaluationEvidence.evaluation_id, M.EvaluationEvidence.evidence_id)
            .where(M.EvaluationEvidence.evaluation_id.in_(eval_ids))
        ).all():
            evidence_by_eval.setdefault(eval_id, set()).add(str(evidence_id))

    per: dict = {}
    meta: dict = {}
    for row in rows:
        (review_id, finding_id, f_cls, f_status, eval_id, e_cls, outcome,
         actual, expected, code, name) = row
        meta[finding_id] = (code, name, f_cls, f_status)
        group = per.setdefault(review_id, {}).setdefault(finding_id, [])
        if e_cls is not None:
            prohibited = constitution_prohibition_for(code, actual) is not None
            group.append({"eval_id": eval_id, "classification": e_cls,
                          "status": user_status(e_cls, outcome, prohibited),
                          "actual": actual, "expected": expected})
        else:
            group.append({"eval_id": None, "classification": f_cls,
                          "status": user_status(f_cls), "actual": None, "expected": None})

    type_codes = {t.upper() for t in DOCUMENT_TYPES}
    for review_id, findings in per.items():
        seen_keys: set = set()
        for finding_id, group in findings.items():
            code, name, f_cls, f_status = meta[finding_id]
            status = worst([g["status"] for g in group], NEEDS_DECISION)

            evidence: set = set()
            for g in group:
                if g["eval_id"] is not None:
                    evidence |= evidence_by_eval.get(g["eval_id"], set())

            key = None
            if evidence:
                lead = next((g for g in group if g["classification"] == f_cls), group[0])
                requires_decision = f_status in {FindingStatus.DECISION_REQUIRED,
                                                 FindingStatus.AWAITING_CLARIFICATION}
                key = (
                    tuple(sorted(evidence)),
                    _requirement_title(code, name, type_codes),
                    f_cls.value if hasattr(f_cls, "value") else str(f_cls),
                    status,
                    requires_decision,
                    _stable_json(lead["actual"]),
                    _stable_json(lead["expected"]),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)

            out[review_id][status] += 1
    return out

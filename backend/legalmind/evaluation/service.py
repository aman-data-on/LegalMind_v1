"""Evaluation persistence — locked AB-1, EV-MIN, 45C.25/N-34.

Writes one Finding per (Review, Requirement Version) with its scoped
Evaluations, in a single transaction so the EV-MIN deferred constraint trigger
sees a complete Finding at COMMIT.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.db import models as M
from legalmind.domain.enums import (
    FindingClassification,
    FindingStatus,
    MappingState,
)
from legalmind.evaluation.contracts import (
    CompanyStandard,
    EvidenceRef,
    EvaluatorInput,
    EvaluatorOutput,
    LegalRule,
    MappingInput,
    RequirementContext,
)
from legalmind.evaluation.presence import OptionalRequirementAbsent
from legalmind.evaluation.registry import evaluate, version_for
from legalmind.evaluation.workflow import derive_finding_status

# Classifications for which empty evidence is legitimate (N-34, 45C.15).
_EVIDENCE_OPTIONAL = frozenset({FindingClassification.MISSING})


class EvidenceCardinalityViolation(Exception):
    """N-34 — non-empty evidence is required except for MISSING-by-absence.

    Raised rather than silently accepting, because the alternative failure mode
    is fabricating evidence to satisfy a constraint — which locked 45C.25
    forbids outright.
    """


@dataclass(frozen=True)
class PersistedFinding:
    finding: M.Finding
    evaluations: tuple[M.Evaluation, ...]


def persist_evaluation(
    db: DBSession,
    *,
    review: M.Review,
    requirement_version_id: UUID,
    output: EvaluatorOutput,
    legal_rule_version_id: UUID | None = None,
    evaluation_rule_version_id: UUID | None = None,
    requirement_required: bool = True,
) -> PersistedFinding:
    """Persist a Finding and its scoped Evaluations."""
    # findings.status is NOT NULL, so an initial value is written and then
    # replaced by the DERIVED one below. It is never asserted by a caller
    # (Step 30 r16: summaries are derived, not manually editable).
    finding = M.Finding(
        review_id=review.id,
        requirement_version_id=requirement_version_id,
        classification=output.finding_classification,
        status=FindingStatus.OPEN,
    )
    db.add(finding)
    db.flush()

    persisted: list[M.Evaluation] = []
    for result in output.evaluations:
        if (not result.evidence_refs
                and result.classification not in _EVIDENCE_OPTIONAL):
            raise EvidenceCardinalityViolation(
                f"{result.classification.value} evaluation for scope "
                f"{result.scope_key} has no evidence; synthetic evidence must "
                "not be created (N-34)")

        evaluation = M.Evaluation(
            finding_id=finding.id,
            evaluator_type=_evaluator_type_of(db, requirement_version_id),
            evaluator_version=result.evaluator_version,
            scope_key=result.scope_key,
            scope_label=result.scope_label,
            evaluation_kind=result.evaluation_kind,
            classification=result.classification,
            rule_outcome=result.rule_outcome,
            expected_value=result.expected_value,
            actual_value=result.actual_value,
            operator=result.operator,
            result={
                "comparison": result.comparison,
                "evaluated_facts": result.evaluated_facts,
                "explanation": list(result.explanation),
                # REC-07 — diagnostics persisted with the evaluation; diagnostic
                # metadata only, and cannot alter a legal finding.
                "diagnostics": list(result.diagnostics),
            },
            rule_version_id=evaluation_rule_version_id,
            legal_rule_version_id=legal_rule_version_id,
        )
        db.add(evaluation)
        db.flush()

        for evidence_id in result.evidence_refs:
            db.add(M.EvaluationEvidence(
                evaluation_id=evaluation.id,
                evidence_id=evidence_id,
                relationship_type=result.evidence_relationships.get(
                    evidence_id, "PRIMARY"),
            ))
        # Finding-level roll-up of evidence is retained alongside (42.16).
        for evidence_id in result.evidence_refs:
            exists = db.execute(
                select(M.FindingEvidence).where(
                    M.FindingEvidence.finding_id == finding.id,
                    M.FindingEvidence.evidence_id == evidence_id)
            ).first()
            if not exists:
                db.add(M.FindingEvidence(
                    finding_id=finding.id, evidence_id=evidence_id,
                    relationship_type=result.evidence_relationships.get(
                        evidence_id, "PRIMARY")))
        persisted.append(evaluation)

    db.flush()
    finding.status = derive_finding_status(
        db, finding, requirement_required=requirement_required)
    db.flush()
    return PersistedFinding(finding=finding, evaluations=tuple(persisted))


def _evaluator_type_of(db: DBSession, requirement_version_id: UUID):
    return db.execute(
        select(M.RequirementVersion.evaluator_type)
        .where(M.RequirementVersion.id == requirement_version_id)
    ).scalar_one()


def build_presence_input(
    *,
    requirement: RequirementContext,
    company_standard: CompanyStandard,
    mapping_state: MappingState,
    evidence: tuple[EvidenceRef, ...] = (),
    legal_rule: LegalRule | None = None,
) -> EvaluatorInput:
    """Assemble a PRESENCE evaluator input.

    Note what cannot be passed: there is no clause-text parameter, so the
    evaluator structurally cannot inspect text (45D / N-30).
    """
    return EvaluatorInput(
        requirement=requirement,
        company_standard=company_standard,
        evaluator_version=version_for(requirement.evaluator_type),
        evidence=evidence,
        mapping=MappingInput(mapping_state=mapping_state, evidence_refs=evidence),
        legal_rule=legal_rule,
    )

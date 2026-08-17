"""Evaluator input/output contract — locked Step 45B (re-locked with AB-1).

The locked input/output shapes, as Python dataclasses. Field names follow the
locked contract exactly.

Two locked rules are structural here, not merely documented:

* **The evaluator produces no Legal Decision** (36.15, 45A r18, 45B.14) — there
  is no field on ``EvaluationResult`` through which one could be expressed.
* **``rule_outcome`` exists at Evaluation level only** (J-2) — ``EvaluatorOutput``
  carries no Finding-level rule outcome, because none is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from legalmind.domain.enums import (
    EvaluationKind,
    EvaluatorType,
    ExtractionStatus,
    FindingClassification,
    MappingState,
    RuleOutcome,
)

# Reserved scope key for scope that could not be determined (45C.20).
SCOPE_UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------- input side
@dataclass(frozen=True)
class RequirementContext:
    """45B.2. ``applicability`` drives the required/optional distinction that
    Step 28 r5 and F-1 depend on."""

    requirement_version_id: UUID
    code: str
    evaluator_type: EvaluatorType
    required: bool = True


@dataclass(frozen=True)
class EvidenceRef:
    """45B.3. Locations retained for Evidence (34.13)."""

    evidence_id: UUID
    page_number: int | None = None
    section_number: str | None = None
    section_title: str | None = None


@dataclass(frozen=True)
class Cap:
    """One element of the locked ``facts.caps[]`` (45B.4 as amended by A-1/A-3).

    ``cap_kind`` generalizes liability's GENERAL/EXCEPTION so the shared
    persistence layer carries no liability-specific vocabulary (N-19).
    """

    cap_kind: EvaluationKind
    scope: str
    cap_status: str                     # FINITE | UNLIMITED | ABSENT | UNKNOWN
    scope_label: str | None = None
    cap_value: float | None = None
    cap_unit: str | None = None
    cap_basis: str | None = None
    evidence_refs: tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LiabilityFacts:
    """45B.4 + REC-05 R1.2 (``extraction_diagnostics`` retained alongside the
    controlled ``extraction_status``)."""

    caps: tuple[Cap, ...] = field(default_factory=tuple)
    extraction_status: ExtractionStatus = ExtractionStatus.COMPLETE
    extraction_diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CompanyStandard:
    """45B.8. ``configuration`` is the locked 42.8 JSONB payload — which is why
    AM-18 (`standard_kind`) was withdrawn: the kind is already determined by
    ``requirement_versions.evaluator_type``."""

    version_id: UUID
    configuration: dict


@dataclass(frozen=True)
class LegalRule:
    """45B.9. OPTIONAL — locked Step 20 r4: not every Clause requires a
    Pre-approved Legal Rule. Absent => ``rule_outcome = NOT_APPLICABLE``."""

    version_id: UUID
    configuration: dict = field(default_factory=dict)
    rule_configuration: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MappingInput:
    """45D — the ONLY source of presence for the PRESENCE evaluator.

    Deliberately carries no clause text: the presence evaluator must never
    inspect raw text, or it becomes the text-pattern evaluator that locked
    44.33 and ENG-03 rule out (N-30).
    """

    mapping_state: MappingState
    evidence_refs: tuple[EvidenceRef, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvaluatorInput:
    """The complete locked evaluator input (45B.11 as corrected by REC-05)."""

    requirement: RequirementContext
    company_standard: CompanyStandard
    evaluator_version: str
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    facts: LiabilityFacts | None = None
    mapping: MappingInput | None = None
    legal_rule: LegalRule | None = None


# --------------------------------------------------------------- output side
@dataclass(frozen=True)
class EvaluationResult:
    """One scoped Evaluation (45B.12 as amended by AM-8', AM-19, AM-20).

    ``evidence_refs`` may legitimately be EMPTY for a ``MISSING`` arising from
    established absence (45C.15, N-34). No synthetic evidence is ever created to
    satisfy a cardinality rule.
    """

    scope_key: str
    evaluation_kind: EvaluationKind
    classification: FindingClassification
    rule_outcome: RuleOutcome
    evaluator_version: str
    scope_label: str | None = None
    expected_value: dict | None = None
    actual_value: dict | None = None
    operator: str | None = None
    comparison: dict | None = None
    evaluated_facts: dict | None = None
    evidence_refs: tuple[UUID, ...] = field(default_factory=tuple)
    evidence_relationships: dict[UUID, str] = field(default_factory=dict)
    explanation: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvaluatorOutput:
    """45B.12. ``finding_classification`` is a DERIVED, NON-AUTHORITATIVE
    summary; the scoped results are authoritative (D-1.1)."""

    evaluations: tuple[EvaluationResult, ...]
    finding_classification: FindingClassification
    evaluator_version: str

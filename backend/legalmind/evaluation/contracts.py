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
    #: Why an UNKNOWN cap was not read (2026-10-16): `NO_FIGURE_STATED`,
    #: `SEVERAL_FIGURES` or `MODEL_UNVERIFIED` — said to the reader instead of
    #: "not readable". Never set on a cap that was read; never alters a result.
    reason: str | None = None
    #: The figures the clause states, verbatim ("15 days", "3 consecutive days").
    candidates: tuple[str, ...] = field(default_factory=tuple)
    #: Whose liability the cap limits — "both", "ours", "theirs" — read from the cap
    #: sentence for a standard that declares a mutual cap (Constitution §9); None when
    #: the words do not say or the standard does not ask.
    cap_party: str | None = None


@dataclass(frozen=True)
class LiabilityFacts:
    """45B.4 + REC-05 R1.2 (``extraction_diagnostics`` retained alongside the
    controlled ``extraction_status``)."""

    caps: tuple[Cap, ...] = field(default_factory=tuple)
    extraction_status: ExtractionStatus = ExtractionStatus.COMPLETE
    extraction_diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StatedValue:
    """One configured value a clause states (AM-148): ``value`` is the configured key
    ("BENGALURU"), ``text`` the clause's own words that name it ("Bangalore")."""

    value: str
    text: str
    evidence_id: UUID


@dataclass(frozen=True)
class CategoricalFacts:
    """What the mapped clauses state, read by `evaluation.categorical.read_values` —
    the extraction step, so the evaluator itself compares and reads no text (45D)."""

    values: tuple[StatedValue, ...] = field(default_factory=tuple)
    evidence_refs: tuple[UUID, ...] = field(default_factory=tuple)
    #: Values named only to exclude them ("courts other than Pune", "Pune courts
    #: shall have no jurisdiction") — never read as stated (QA-003).
    excluded: tuple[str, ...] = field(default_factory=tuple)


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
    #: `AM-152` — whether the clause found WAIVES or OPPOSES the position (a configured
    #: waiver phrase, or the selected model's OPPOSED verdict on a verbatim span). A
    #: fact set by the mapping layer, never text: the evaluator still reads no clause
    #: (45D, N-30); the waiving sentence is recorded by the analysis, not passed here.
    opposed: bool = False
    #: `AM-154` — whether the clause found goes BEYOND the position in a way the owner
    #: ruled too broad (an indemnity covering indirect or consequential loss or lost
    #: profits, or restricting our control of the defence). A fact, never text (45D).
    too_broad: bool = False
    #: Whether the clause found reaches only PART of the position — a data-loss exclusion
    #: limited to losses the customer or a third party caused, where the Constitution's
    #: position (L1.14 §9) also covers our own operational error (2026-10-21). A fact.
    too_narrow: bool = False
    #: Whether another confirmed clause STATES the position the waiver opposes: a
    #: contradiction for a person (Step 28 r8, 44.18), never the document's waiver.
    contested: bool = False
    #: Constitution §31.11 "by reference … — not restated independently": the paper's own
    #: section on the topic states its terms and never points to the governing agreement
    #: (2026-10-23). A fact set by the analysis, never text (45D).
    restated: bool = False


@dataclass(frozen=True)
class EvaluatorInput:
    """The complete locked evaluator input (45B.11 as corrected by REC-05)."""

    requirement: RequirementContext
    company_standard: CompanyStandard
    evaluator_version: str
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    facts: LiabilityFacts | CategoricalFacts | None = None
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

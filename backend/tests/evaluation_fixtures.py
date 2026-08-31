"""Structural test configuration for the evaluation engine.

⚠ IMPORTANT — these values are **synthetic and structural only**. They exercise
the algorithm (comparison, grouping, fail-closed paths, roll-up). They are NOT a
LegalMind Company Standard and NOT a legal position.

Locked Step 20: "Actual Legal Rules must be configured by authorized Legal/Admin
users." Locked Step 45E additionally requires that normative golden fixtures be
authored from real representative contracts and the organization's real
Standards — inventing them would make a fabricated legal conclusion normative
under Step 54.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from legalmind.domain.enums import EvaluationKind, EvaluatorType
from legalmind.evaluation.contracts import (
    Cap,
    CompanyStandard,
    EvaluatorInput,
    LegalRule,
    LiabilityFacts,
    RequirementContext,
)
from legalmind.evaluation.registry import version_for

STRUCTURAL_SCOPE = "SCOPE_A"
STRUCTURAL_UNIT = "UNIT_X"
STRUCTURAL_BASIS = "BASIS_P"


def structural_standard(preferred: float = 10, **overrides) -> CompanyStandard:
    """Synthetic Standard. `preferred=10` is an arbitrary structural number
    chosen precisely so it cannot be mistaken for a real policy value."""
    config = {"preferred": preferred, "unit": STRUCTURAL_UNIT,
              "basis": STRUCTURAL_BASIS, "scope_key": STRUCTURAL_SCOPE}
    config.update(overrides)
    return CompanyStandard(version_id=uuid4(), configuration=config)


def multi_scope_rule(*scopes: str, **kwargs) -> LegalRule:
    """A rule declaring several scopes comparable to the Standard's scope.

    Needed because an undeclared scope correctly fails closed (45C.5), so a test
    exercising two comparable scopes must configure them.
    """
    return structural_rule(rule_configuration={
        "scope_required": True,
        "comparable_scopes": [STRUCTURAL_SCOPE, *scopes],
        "comparable_bases": [STRUCTURAL_BASIS],
    }, **kwargs)


def structural_rule(*, deviation_outcome: str | None = "UNACCEPTABLE",
                    acceptable_max: float | None = None,
                    approval_required_above: float | None = None,
                    unlimited_outcome: str | None = "UNACCEPTABLE",
                    rule_configuration: dict | None = None) -> LegalRule:
    """The AUTHORIZED blanket rule form by default (AM-33 r6). The band kwargs
    exist ONLY so regression tests can prove the withdrawn form is refused."""
    config: dict = {}
    if deviation_outcome is not None:
        config["deviation_outcome"] = deviation_outcome
    if acceptable_max is not None:
        config["acceptable_max"] = acceptable_max
    if approval_required_above is not None:
        config["approval_required_above"] = approval_required_above
    if unlimited_outcome is not None:
        config["unlimited_outcome"] = unlimited_outcome
    return LegalRule(
        version_id=uuid4(),
        configuration=config,
        rule_configuration=rule_configuration or {
            "scope_required": True,
            "comparable_scopes": [STRUCTURAL_SCOPE],
            "comparable_bases": [STRUCTURAL_BASIS],
        },
    )


def cap(value: float | None, *, status: str = "FINITE",
        scope: str = STRUCTURAL_SCOPE, kind: EvaluationKind = EvaluationKind.PRIMARY,
        label: str | None = None, unit: str | None = STRUCTURAL_UNIT,
        basis: str | None = STRUCTURAL_BASIS,
        evidence: tuple[UUID, ...] | None = None) -> Cap:
    return Cap(cap_kind=kind, scope=scope, cap_status=status, cap_value=value,
               cap_unit=unit if value is not None else None, cap_basis=basis,
               scope_label=label,
               evidence_refs=evidence if evidence is not None else (uuid4(),))


_UNSET = object()


def numeric_input(caps, *, standard=None, rule=_UNSET, required=True,
                  extraction_status=None, diagnostics=()) -> EvaluatorInput:
    """`rule=None` means "no Legal Rule configured" (Step 20 r4); omitting it
    supplies the structural default. The sentinel keeps those distinct."""
    from legalmind.domain.enums import ExtractionStatus
    facts = LiabilityFacts(
        caps=tuple(caps),
        extraction_status=extraction_status or ExtractionStatus.COMPLETE,
        extraction_diagnostics=tuple(diagnostics))
    return EvaluatorInput(
        requirement=RequirementContext(
            requirement_version_id=uuid4(), code="STRUCTURAL-NUMERIC-001",
            evaluator_type=EvaluatorType.NUMERIC_COMPARISON, required=required),
        company_standard=standard or structural_standard(),
        legal_rule=structural_rule() if rule is _UNSET else rule,
        evaluator_version=version_for(EvaluatorType.NUMERIC_COMPARISON),
        facts=facts)

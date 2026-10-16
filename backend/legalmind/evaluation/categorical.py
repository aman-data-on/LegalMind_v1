"""`CATEGORICAL` evaluator — AM-148 (2026-10-16).

A clause can state a VALUE the Constitution fixes: "courts at Pune … seated in Pune"
(§22). PRESENCE asks only whether a dispute clause exists (45D), so a customer's markup
moving both to Bengaluru read "Acceptable". This evaluator compares the values a clause
STATES with the values the standard ALLOWS.

The split 45D insists on is kept: `extraction.categorical.read_values` is the
extraction step — it reads the mapped clauses for the standard's configured terms (a
closed lexicon, longest match, the same word boundaries as mapping) — and
`evaluate_categorical` compares what it was given and reads no text. Nothing is
inferred: a value counts only where the clause's own words name it, and a clause that
names none is UNABLE_TO_EVALUATE, never a match.
"""

from __future__ import annotations

from legalmind.domain.enums import (
    EvaluationKind,
    FindingClassification,
    MappingState,
    RuleOutcome,
)
from legalmind.evaluation.contracts import (
    CategoricalFacts,
    EvaluationResult,
    EvaluatorInput,
    EvaluatorOutput,
)
from legalmind.evaluation.presence import OptionalRequirementAbsent, _deviation_outcome
from legalmind.evaluation.rollup import roll_up

ALLOWED_KEY = "allowed_values"
RECOGNISED_KEY = "recognised_values"
#: Why no value was compared — read by the reader's sentence (findingLanguage).
NO_VALUE_STATED = "NO_VALUE_STATED"


class CategoricalMisconfigured(Exception):
    """The Standard declares no allowed values, or names one it cannot recognise."""


def configured(standard: dict) -> tuple[list[str], dict[str, list[str]]]:
    allowed = standard.get(ALLOWED_KEY) or []
    recognised = standard.get(RECOGNISED_KEY) or {}
    if not allowed or any(v not in recognised for v in allowed):
        raise CategoricalMisconfigured(
            f"Company Standard must declare {ALLOWED_KEY!r}, each one a key of "
            f"{RECOGNISED_KEY!r}")
    return allowed, recognised


def evaluate_categorical(evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    standard = evaluator_input.company_standard.configuration or {}
    allowed, _ = configured(standard)
    scope_key = standard.get("scope_key") or "DEFAULT"
    mapping = evaluator_input.mapping
    state = mapping.mapping_state if mapping else MappingState.UNRESOLVED
    facts = evaluator_input.facts if isinstance(evaluator_input.facts,
                                                CategoricalFacts) else None
    evidence = facts.evidence_refs if facts else tuple(
        ref.evidence_id for ref in (mapping.evidence_refs if mapping else ()))
    expected = {ALLOWED_KEY: allowed}
    stated = sorted({v.value for v in facts.values}) if facts else []
    words = list(dict.fromkeys(v.text for v in facts.values)) if facts else []

    if state is MappingState.NONE:
        if not evaluator_input.requirement.required:
            raise OptionalRequirementAbsent(
                f"{evaluator_input.requirement.code} is optional and absent (F-1)")
        classification = FindingClassification.MISSING
        outcome = RuleOutcome.NOT_APPLICABLE
        actual: dict = {"values": []}
        explanation: tuple[str, ...] = ("mapping layer mapped no provision",)
        evidence = ()                                       # 45C.15
    elif state is not MappingState.CONFIRMED or not stated:
        classification, outcome = (FindingClassification.UNABLE_TO_EVALUATE,
                                   RuleOutcome.NOT_APPLICABLE)
        actual = {"values": [], "reason": NO_VALUE_STATED}
        explanation = ((f"mapping {state.value}: no value compared (Step 28 r6)",)
                       if state is not MappingState.CONFIRMED else
                       ("the mapped clause names none of the configured values",
                        "nothing is inferred; a person reads the clause"))
    elif set(stated) <= set(allowed):
        classification = FindingClassification.MATCH
        outcome = (RuleOutcome.ACCEPTABLE if evaluator_input.legal_rule is not None
                   else RuleOutcome.NOT_APPLICABLE)
        actual = {"values": words}
        explanation = (f"the clause states {', '.join(words)}; "
                       f"allowed: {', '.join(allowed)}",)
    else:
        classification = FindingClassification.DEVIATION
        outcome = _deviation_outcome(evaluator_input.legal_rule)
        others = [v for v in stated if v not in allowed]
        actual = {"values": words}
        explanation = (f"the clause states {', '.join(words)}; "
                       f"{', '.join(others)} is not among the allowed "
                       f"{', '.join(allowed)}",)

    result = EvaluationResult(
        scope_key=scope_key,
        evaluation_kind=EvaluationKind.PRIMARY,
        classification=classification,
        rule_outcome=outcome,
        evaluator_version=evaluator_input.evaluator_version,
        expected_value=expected,
        actual_value=actual,
        operator="one_of",
        comparison={"allowed": allowed, "stated": stated, "mapping_state": state.value},
        evaluated_facts={"mapping_state": state.value, "stated": stated},
        evidence_refs=evidence,
        evidence_relationships=dict.fromkeys(evidence, "PRIMARY"),
        explanation=explanation,
        diagnostics=(f"{len(words)} value term(s) read",),
    )
    return EvaluatorOutput(evaluations=(result,),
                           finding_classification=roll_up([result.classification]),
                           evaluator_version=evaluator_input.evaluator_version)

"""`PRESENCE` evaluator — locked Step 45D.

**The evaluator never inspects clause text.** It consumes ``mapping_state`` from
the locked mapping layer and nothing else. An evaluator that scanned text would
duplicate the locked mapping mechanism (35.4, 35.5, 35.10), collapse ENG-03
(Mapping != Evaluation), and produce a Result without a Fact — breaking locked
44.33 explainability. That is why ``EvaluatorInput.mapping`` carries no text
field at all: the constraint is structural, not a convention.

The single most important rule: **an ambiguous or unresolved mapping must NEVER
be recorded as absence.** Doing so would convert uncertainty into the legal
conclusion "no such provision exists" (ENG-09, 45C.15).
"""

from __future__ import annotations

from legalmind.domain.enums import (
    EvaluationKind,
    FindingClassification,
    MappingState,
    RuleOutcome,
)
from legalmind.evaluation.contracts import (
    EvaluationResult,
    EvaluatorInput,
    EvaluatorOutput,
)
from legalmind.evaluation.rollup import roll_up

EXPECTED_PRESENCE_KEY = "expected_presence"
PRESENT = "PRESENT"
ABSENT = "ABSENT"
INDETERMINATE = "INDETERMINATE"

DEFAULT_SCOPE_KEY = "DEFAULT"


class PresenceMisconfigured(Exception):
    """The Standard does not declare ``expected_presence``.

    A configuration error, not a runtime state: guessing the expectation would
    invent the organization's position (45B.26).
    """


def evaluate_presence(evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    """Compare provision existence against the configured expectation."""
    standard = evaluator_input.company_standard.configuration or {}
    if EXPECTED_PRESENCE_KEY not in standard:
        raise PresenceMisconfigured(
            f"Company Standard must declare {EXPECTED_PRESENCE_KEY!r}")

    expected = standard[EXPECTED_PRESENCE_KEY]
    scope_key = standard.get("scope_key") or DEFAULT_SCOPE_KEY
    mapping = evaluator_input.mapping
    if mapping is None:
        raise PresenceMisconfigured("PRESENCE evaluation requires mapping input")

    has_legal_rule = evaluator_input.legal_rule is not None
    evidence = tuple(ref.evidence_id for ref in mapping.evidence_refs)
    state = mapping.mapping_state

    if state is MappingState.CONFIRMED:
        actual = PRESENT
        classification = (FindingClassification.MATCH if expected == PRESENT
                          else FindingClassification.DEVIATION)
        outcome = (RuleOutcome.ACCEPTABLE if has_legal_rule
                   else RuleOutcome.NOT_APPLICABLE)
        explanation = (
            f"mapping CONFIRMED for {evaluator_input.requirement.code}",
            f"expected {expected}; a qualifying provision is present",
        )
        diagnostics = ("presence established by the mapping layer",
                       f"{len(evidence)} provision(s) mapped")

    elif state is MappingState.NONE:
        actual = ABSENT
        if expected == ABSENT:
            classification = FindingClassification.MATCH
            outcome = (RuleOutcome.ACCEPTABLE if has_legal_rule
                       else RuleOutcome.NOT_APPLICABLE)
        elif evaluator_input.requirement.required:
            # Step 28 r5 — a REQUIRED Requirement with no mapped provision.
            classification = FindingClassification.MISSING
            outcome = RuleOutcome.NOT_APPLICABLE
        else:
            # F-1: an optional Requirement with no mapped provision produces NO
            # Finding. Reaching here means the caller should not have evaluated
            # it; surfacing it as an error beats inventing a classification.
            raise OptionalRequirementAbsent(
                f"{evaluator_input.requirement.code} is optional and absent; "
                "no Finding is produced (F-1)")
        explanation = (
            "mapping layer completed and mapped no provision",
            "absence established by mapping, not by evaluator inspection",
        )
        diagnostics = ("no provision mapped",)
        evidence = ()          # 45C.15 — zero evidence is the correct state

    else:
        # AMBIGUOUS or UNRESOLVED. Locked Step 28 r6 — fail closed.
        actual = INDETERMINATE
        classification = FindingClassification.UNABLE_TO_EVALUATE
        outcome = RuleOutcome.NOT_APPLICABLE
        explanation = (
            f"mapping {state.value}: presence could not be established "
            "deterministically",
            "failing closed per Step 28 rule 6; NOT recorded as absence",
        )
        diagnostics = (f"mapping state {state.value}",
                       f"{len(evidence)} candidate provision(s) retained")

    result = EvaluationResult(
        scope_key=scope_key,
        evaluation_kind=EvaluationKind.PRIMARY,
        classification=classification,
        rule_outcome=outcome,
        evaluator_version=evaluator_input.evaluator_version,
        expected_value={"presence": expected},
        actual_value={"presence": actual},
        operator="presence",
        comparison={"expected": expected, "actual": actual,
                    "mapping_state": state.value},
        evaluated_facts={"mapping_state": state.value},
        evidence_refs=evidence,
        evidence_relationships={eid: "PRIMARY" for eid in evidence},
        explanation=explanation,
        diagnostics=diagnostics,
    )
    return EvaluatorOutput(
        evaluations=(result,),
        finding_classification=roll_up([result.classification]),
        evaluator_version=evaluator_input.evaluator_version,
    )


class OptionalRequirementAbsent(Exception):
    """F-1 — an optional, absent Requirement produces no Finding at all."""

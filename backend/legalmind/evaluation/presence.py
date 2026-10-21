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
#: `AM-152` — the provision is present and waives or negates the position.
WAIVED = "WAIVED"
#: `AM-154` — the provision is present and broader than the position allows.
TOO_BROAD = "TOO_BROAD"
TOO_NARROW = "TOO_NARROW"

DEFAULT_SCOPE_KEY = "DEFAULT"


def _deviation_outcome(legal_rule) -> RuleOutcome:
    """Map a presence DEVIATION onto the configured `deviation_outcome`.

    Same key and same fail-closed semantics as the numeric evaluator's
    `_rule_outcome_for`: with no Legal Rule, no key, or an unrecognised value,
    the outcome is NOT_APPLICABLE — the deviation stands and a human decides.
    """
    if legal_rule is None:
        return RuleOutcome.NOT_APPLICABLE
    raw = (legal_rule.configuration or {}).get("deviation_outcome")
    if raw is None:
        return RuleOutcome.NOT_APPLICABLE
    try:
        return RuleOutcome(raw)
    except ValueError:
        return RuleOutcome.NOT_APPLICABLE


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

    relationship = "PRIMARY"
    if (state is MappingState.CONFIRMED and mapping.opposed and mapping.contested
            and expected == PRESENT):
        # One confirmed clause states the position, another waives it (a charge for the
        # unexpired term in §14, "no minimum commitment" in a schedule): a contradiction
        # for a person (Step 28 r8, 44.18; 45C.2), never MATCH and never WAIVED.
        actual = INDETERMINATE
        classification = FindingClassification.CONFLICT
        outcome = RuleOutcome.NOT_APPLICABLE
        relationship = "CONFLICTING"
        explanation: tuple[str, ...] = (
            f"mapping CONFIRMED for {evaluator_input.requirement.code}",
            "one clause found states the position and another waives it",
            "reported as CONFLICT; all provisions retained (45C.2)")
        diagnostics: tuple[str, ...] = ("polarity CONTESTED",
                                        f"{len(evidence)} provision(s) mapped")

    elif state is MappingState.CONFIRMED and mapping.opposed and expected == PRESENT:
        # `AM-152` — the clause is there and WAIVES what the standard requires ("No
        # lock-in, early termination charges … shall apply"): never a match. A
        # DEVIATION, disposed by the zero-tolerance rule like any other.
        actual = WAIVED
        classification = FindingClassification.DEVIATION
        outcome = _deviation_outcome(evaluator_input.legal_rule)
        explanation = (
                       f"mapping CONFIRMED for {evaluator_input.requirement.code}",
                       "the clause found waives the position (AM-152)",
                       "expected PRESENT; the document states the opposite (AM-152)")
        diagnostics = (
                       "presence established by the mapping layer; polarity OPPOSED",
                       f"{len(evidence)} provision(s) mapped")

    elif state is MappingState.CONFIRMED and mapping.too_broad and expected == PRESENT:
        # `AM-154` — present, and broader than the position allows: a DEVIATION for a
        # person (the zero-tolerance rule routes it to a Legal Decision).
        actual = TOO_BROAD
        classification = FindingClassification.DEVIATION
        outcome = _deviation_outcome(evaluator_input.legal_rule)
        explanation = (f"mapping CONFIRMED for {evaluator_input.requirement.code}",
                       "the clause found is broader than the position (AM-154)")
        diagnostics = ("presence established by the mapping layer; breadth flagged",
                       f"{len(evidence)} provision(s) mapped")

    elif state is MappingState.CONFIRMED and mapping.too_narrow and expected == PRESENT:
        # present, but reaching only part of the position (owner, 2026-10-21; G-F):
        # never a match — a DEVIATION a person weighs, disposed like any other
        actual = TOO_NARROW
        classification = FindingClassification.DEVIATION
        outcome = _deviation_outcome(evaluator_input.legal_rule)
        explanation = (f"mapping CONFIRMED for {evaluator_input.requirement.code}",
                       "the clause found is narrower than the position: it is limited to "
                       "the causes it lists")
        diagnostics = ("presence established by the mapping layer; narrowing flagged",
                       f"{len(evidence)} provision(s) mapped")

    elif state is MappingState.CONFIRMED:
        actual = PRESENT
        classification = (FindingClassification.MATCH if expected == PRESENT
                          else FindingClassification.DEVIATION)
        if classification is FindingClassification.MATCH:
            outcome = (RuleOutcome.ACCEPTABLE if has_legal_rule
                       else RuleOutcome.NOT_APPLICABLE)
        else:
            # A provision present where the Standard expects ABSENT is a
            # DEVIATION and must never inherit MATCH's ACCEPTABLE. The approved
            # zero-tolerance rule (owner, 2026-08-20) disposes it via
            # `deviation_outcome`; anything unconfigured or unrecognised fails
            # closed to NOT_APPLICABLE and a human (Step 20 r4, ENG-09).
            outcome = _deviation_outcome(evaluator_input.legal_rule)
        explanation = (
            f"mapping CONFIRMED for {evaluator_input.requirement.code}",
            f"expected {expected}; a qualifying provision is present",
        )
        diagnostics = (
            "presence established by the mapping layer",
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
        evidence_relationships=dict.fromkeys(evidence, relationship),
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

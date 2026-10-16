"""Evaluator dispatch — locked AM-16 vocabulary.

Exactly three evaluator types exist in V1: AM-16's two, and CATEGORICAL, added by
the additive amendment AM-148 (2026-10-16). Adding another is an additive
amendment, not a code-only change (AM-16).
"""

from __future__ import annotations

from collections.abc import Callable

from legalmind.domain.enums import EvaluatorType
from legalmind.evaluation.categorical import evaluate_categorical
from legalmind.evaluation.contracts import EvaluatorInput, EvaluatorOutput
from legalmind.evaluation.numeric import evaluate_numeric
from legalmind.evaluation.presence import evaluate_presence

# Evaluator implementation versions. Locked 45B.10 requires every evaluation to
# identify the exact evaluator version, persisted via AM-19.
EVALUATOR_VERSIONS: dict[EvaluatorType, str] = {
    EvaluatorType.NUMERIC_COMPARISON: "NUMERIC-COMPARISON-v1",
    EvaluatorType.PRESENCE: "PRESENCE-v1",
    EvaluatorType.CATEGORICAL: "CATEGORICAL-v1",
}

_EVALUATORS: dict[EvaluatorType, Callable[[EvaluatorInput], EvaluatorOutput]] = {
    EvaluatorType.NUMERIC_COMPARISON: evaluate_numeric,
    EvaluatorType.PRESENCE: evaluate_presence,
    EvaluatorType.CATEGORICAL: evaluate_categorical,
}


class UnknownEvaluatorType(Exception):
    """No evaluator is registered for this type."""


def evaluator_for(evaluator_type: EvaluatorType):
    try:
        return _EVALUATORS[evaluator_type]
    except KeyError as exc:
        raise UnknownEvaluatorType(str(evaluator_type)) from exc


def version_for(evaluator_type: EvaluatorType) -> str:
    return EVALUATOR_VERSIONS[evaluator_type]


def evaluate(evaluator_input: EvaluatorInput) -> EvaluatorOutput:
    return evaluator_for(evaluator_input.requirement.evaluator_type)(evaluator_input)

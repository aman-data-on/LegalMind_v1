"""Finding classification roll-up — locked Step 45B re-lock record / D-1.2.

    TIER 1 (result cannot be relied upon — fail closed, ENG-09)
        UNABLE_TO_EVALUATE > CONFLICT > AMBIGUOUS > UNRESOLVED
    TIER 2 (evaluated positions)
        MISSING > DEVIATION > MATCH

Any Tier-1 scope dominates every Tier-2 scope.

The TIER SPLIT is derived from ENG-09: a Finding must never read ``MATCH`` while
any scope is unevaluable, contradictory or absent.

**The ordering WITHIN Tier 1 is an engineering determinism convention only. It
is NOT a legal hierarchy.** All four Tier-1 states route to human review and are
legally equivalent in consequence; the order exists solely so the derivation is
deterministic (ENG-11). Any total order would be equally correct.
"""

from __future__ import annotations

from collections.abc import Iterable

from legalmind.domain.enums import (
    ROLLUP_PRECEDENCE,
    ROLLUP_TIER_1,
    ROLLUP_TIER_2,
    FindingClassification,
)

_RANK = {c: i for i, c in enumerate(ROLLUP_PRECEDENCE)}


class EmptyEvaluationSet(Exception):
    """Raised when a roll-up is attempted with no Evaluations.

    EV-MIN (AB-1.6 / D-3.4) makes this a defect, not a valid state: a Finding
    always has at least one Evaluation, including MISSING and
    UNABLE_TO_EVALUATE Findings.
    """


def roll_up(classifications: Iterable[FindingClassification]) -> FindingClassification:
    """Derive the single Finding classification from its scoped Evaluations."""
    ranked = sorted(classifications, key=lambda c: _RANK[c])
    if not ranked:
        raise EmptyEvaluationSet(
            "EV-MIN: a Finding must have at least one Evaluation")
    return ranked[0]


def is_tier_1(classification: FindingClassification) -> bool:
    """Tier 1 = the result cannot be relied upon."""
    return classification in ROLLUP_TIER_1


def is_tier_2(classification: FindingClassification) -> bool:
    return classification in ROLLUP_TIER_2


def tier_of(classification: FindingClassification) -> int:
    return 1 if is_tier_1(classification) else 2

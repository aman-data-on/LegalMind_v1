"""Signals worth collecting — locked 53.5.

This module deliberately holds **classification and naming, not a metrics backend**.
Locked 53.6 records the monitoring stack as NOT YET SPECIFIED, so choosing one would
be inventing an operational decision. What is locked is *which* signals matter and —
far more importantly — which of them is not an error.

--------------------------------------------------------------------------
The rule this module exists to enforce
--------------------------------------------------------------------------
Locked 53.5: **"Do not alert on `UNABLE_TO_EVALUATE` — it is the system working as
locked."** And locked 53.4: the observability layer must not collapse
`ANALYSIS_FAILED` (Review-level, the run could not complete) into a Finding of
`UNABLE_TO_EVALUATE` (the engine ran and fail-closed correctly).

Getting this backwards is the most damaging observability mistake available here. An
operator who treats fail-closed outcomes as errors will pressure the engine toward
guessing, and locked 53.5 names the trap precisely: the fail-closed rate is "the
engine's honesty metric. A *falling* rate may mean guessing, not improvement."

So `is_operational_failure` is the single place that decides what may be alerted on,
and it returns False for every fail-closed classification by construction.
"""

from __future__ import annotations

from legalmind.domain.enums import FindingClassification, ReviewStatus
from legalmind.evaluation.rollup import ROLLUP_TIER_1

# Locked 53.5's table, as stable signal names. A metrics backend maps these; nothing
# here assumes which one.
ANALYSIS_SIGNALS: dict[str, str] = {
    "analysis.stage_duration_ms": "pipeline stage durations across Step 44's layers",
    "analysis.evaluator_runs": "evaluator runs by type and version (reproducibility)",
    "analysis.classification_count": "classification distribution; a sudden shift "
                                     "signals a configuration or extraction regression",
    "analysis.fail_closed_rate": "UNABLE_TO_EVALUATE / AMBIGUOUS / UNRESOLVED — the "
                                 "engine's honesty metric. NOT an error rate",
    "analysis.review_failed_rate": "ANALYSIS_FAILED — genuine operational failure",
    "auth.failure_count": "authentication failures (S-5, S-7)",
    "authz.denial_count": "permission denials; repeated denials on one object matter",
    "decision.outstanding_age": "Reviews stuck in DECISION_REQUIRED",
}

# 53.5's fail-closed set. Tier 1 is the roll-up's "cannot be relied upon" tier, which
# is exactly this set — derived rather than restated so the two cannot drift.
FAIL_CLOSED_CLASSIFICATIONS = frozenset(ROLLUP_TIER_1)

# Signals that may raise an alert (53.5's "Alert on" list). Deliberately explicit:
# anything absent here is not alertable, so adding one is a visible change.
ALERTABLE_SIGNALS = frozenset({
    "analysis.review_failed_rate",
    "auth.failure_count",
    "authz.denial_count",
    "analysis.stage_duration_ms",     # jobs exceeding expected duration
})


def classification_signal(classification: FindingClassification) -> str:
    """Which 53.5 signal a Finding classification contributes to."""
    if classification in FAIL_CLOSED_CLASSIFICATIONS:
        return "analysis.fail_closed_rate"
    return "analysis.classification_count"


def is_operational_failure(*, classification: FindingClassification | None = None,
                           review_status: ReviewStatus | None = None) -> bool:
    """Whether an outcome is an operational failure worth alerting on.

    **A fail-closed classification is never one.** `UNABLE_TO_EVALUATE`, `CONFLICT`,
    `AMBIGUOUS` and `UNRESOLVED` are the engine declining to guess, which locked
    45B/45C/Step 28 r6 require it to do — alerting on them would invert the incentive
    the specification is built around.

    `ANALYSIS_FAILED` is a genuine failure: the run could not complete, so no legal
    conclusion was reached at all (Step 30 r13, 34.15).
    """
    if review_status is ReviewStatus.ANALYSIS_FAILED:
        return True
    if classification is not None:
        return False        # no classification is ever an operational failure
    return False


def fail_closed_rate(counts: dict[FindingClassification, int]) -> float | None:
    """The honesty metric (53.5). ``None`` when nothing was classified.

    Reported, never targeted. Locked 53.5 warns that a *falling* rate may mean the
    engine has started guessing, so this is deliberately not exposed as something to
    drive down.
    """
    total = sum(counts.values())
    if not total:
        return None
    failed_closed = sum(n for c, n in counts.items()
                        if c in FAIL_CLOSED_CLASSIFICATIONS)
    return round(failed_closed / total, 4)

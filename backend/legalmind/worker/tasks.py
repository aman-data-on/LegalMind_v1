"""The analysis job — locked 55.1, 44.2/44.40, 43.26, 43.28.

One task, one Review. The task owns no legal logic whatsoever: it opens a
transaction, calls `analysis.service.run_analysis`, and commits. Every rule about
what analysis produces — fail-closed outcomes, the Review lifecycle, EV-MIN — is
enforced where it already was, so the queued path and the inline path cannot diverge.

--------------------------------------------------------------------------
The transaction is the serialization point, not the queue
--------------------------------------------------------------------------
Two workers can be handed the same Review — `task_acks_late` redelivers after a
crash, and a caller can submit twice. Nothing in the queue prevents that, and nothing
needs to:

* `assert_analysable` refuses a Review that already has Findings (43.28);
* `UNIQUE(review_id, requirement_version_id)` makes a genuine race collide, and the
  loser's transaction rolls back **entirely** — including its lifecycle transitions,
  so no Review is left half-analysed;
* the loser's retry then finds the Findings and reports the work already done.

The database is where duplicate legal output is prevented. A queue-level lock would
be a second, weaker mechanism guarding the same thing.

--------------------------------------------------------------------------
Why a failed job leaves the Review alone
--------------------------------------------------------------------------
Locked Step 30 makes `ANALYSIS_FAILED` **terminal** — it has no outgoing transitions.
So this task never marks a Review failed because of an infrastructure fault: a broken
broker, a version skew or a lost connection would otherwise burn a Review
permanently, with no locked path back. `ANALYSIS_FAILED` is set only where it always
was, inside `run_analysis`, for a document that genuinely cannot be analysed (34.9,
Step 30 r13).

The lifecycle transition into `PROCESSING` is therefore left to `run_analysis` too,
inside the job's own transaction. A crashed job rolls back to the state it started
from, and re-analysis is possible because nothing was consumed.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.service import (
    AnalysisNotPermitted,
    AnalysisRun,
    run_analysis,
)
from legalmind.db import models as M
from legalmind.db import session as db_session
from legalmind.observability.logs import log_event, log_exception
from legalmind.worker.app import TASK_ANALYSE_REVIEW, celery_app, evaluator_fingerprint

#: How long to wait before retrying a job the worker cannot correctly run *yet*.
#: Skew is fixed by deploying the API and workers together (55.1), which takes
#: minutes, not seconds — retrying sooner would just spin.
SKEW_RETRY_SECONDS = 60

#: A transient operational failure (a dropped connection, a lock timeout). Short,
#: because the work is idempotent and cheap to re-attempt.
ERROR_RETRY_SECONDS = 10

MAX_RETRIES = 5


class EvaluatorVersionSkew(Exception):
    """This worker would not run the evaluator versions the caller dispatched.

    Locked 55.1: "a version skew would break `evaluator_version` reproducibility, so
    they deploy together." Raised *before* anything is written, so refusing costs
    nothing and produces no partial legal record.

    Both fingerprints are carried as attributes, not only inside the message. They are
    logged as separate short fields because 53.3 treats an over-long value as content
    and truncates it — and a truncated skew diagnostic loses the one thing the
    operator needs. Found in a real worker log reading ``[209 chars omitted]``.
    """

    def __init__(self, dispatched: str, local: str):
        super().__init__(
            f"dispatched by an API running {dispatched!r}; this worker runs "
            f"{local!r}. Locked 55.1 deploys them together")
        self.dispatched = dispatched
        self.local = local


def assert_no_skew(dispatched: str | None) -> None:
    """Refuse to analyse on behalf of a differently-versioned caller.

    `None` means the message predates the guard or was dispatched by a caller that
    did not stamp it; that is not skew, and refusing it would strand messages during
    the very upgrade the guard exists to protect.
    """
    if dispatched is None:
        return
    local = evaluator_fingerprint()
    if dispatched != local:
        raise EvaluatorVersionSkew(dispatched, local)


def _session() -> DBSession:
    """Indirection point, so a test can bind the job to its own engine."""
    return db_session.new_session()


@celery_app.task(bind=True, name=TASK_ANALYSE_REVIEW, max_retries=MAX_RETRIES)
def analyse_review(self, *, review_id: str, actor_id: str | None = None,
                   request_id: str | None = None,
                   evaluator_fingerprint: str | None = None) -> dict:
    """Analyse one Review.

    The message carries **identifiers only** — a Review id, the acting user's id and
    the correlation id (49.9 / 53.2). No clause text, no configuration and no legal
    position travels through the broker: everything needed is read from the database
    under the Review's pinned configuration snapshot, which is also what keeps the job
    reproducible (AUD-04).
    """
    try:
        assert_no_skew(evaluator_fingerprint)
    except EvaluatorVersionSkew as exc:
        # Alertable: this is a genuine deployment fault, unlike any fail-closed
        # legal outcome (53.4, 53.5).
        log_event("analysis.job.version_skew", request_id=request_id,
                  review_id=review_id, reason_code="evaluator_version_skew",
                  dispatched_by=exc.dispatched, worker_runs=exc.local,
                  operational_failure=True)
        raise self.retry(exc=exc, countdown=SKEW_RETRY_SECONDS) from exc

    db = _session()
    try:
        review = db.get(M.Review, UUID(review_id))
        if review is None:
            # A message whose Review does not exist. The honest response is to drop
            # it: there is nothing to analyse and nothing to record. Reviews are
            # never deleted, so in practice this means the enqueuing transaction did
            # not commit.
            log_event("analysis.job.unknown_review", request_id=request_id,
                      review_id=review_id, reason_code="review_not_found")
            return {"review_id": review_id, "analysed": False,
                    "reason_code": "review_not_found"}

        run = run_analysis(
            db, review,
            actor_id=UUID(actor_id) if actor_id else None,
            request_id=request_id)
        db.commit()
        return _summary(run)

    except AnalysisNotPermitted as exc:
        # 43.28 — a redelivered or duplicated message finding the work already done.
        # Not an error, and explicitly not a retry: retrying would never succeed.
        db.rollback()
        log_event("analysis.job.already_analysed", request_id=request_id,
                  review_id=review_id, reason_code="already_analysed",
                  detail=str(exc))
        return {"review_id": review_id, "analysed": False,
                "reason_code": "already_analysed"}

    except Exception as exc:
        # One transaction per job (43.26's property, applied to a worker): the
        # rollback returns the Review to its pre-analysis state, including any
        # lifecycle transition, so a retry starts from a clean slate.
        db.rollback()
        log_exception("analysis.job.failed", request_id=request_id,
                      review_id=review_id, operational_failure=True)
        raise self.retry(exc=exc, countdown=ERROR_RETRY_SECONDS) from exc

    finally:
        db.close()


def _summary(run: AnalysisRun) -> dict:
    """A JSON-safe echo of the run, for logs and tests.

    Not a result store — `task_ignore_result` discards it. Locked 52.7 keeps the
    Review lifecycle as the single source of progress, and this is not it.
    """
    return {
        "review_id": str(run.review_id),
        "analysed": True,
        "review_status": run.review_status,
        "requirements_in_snapshot": run.requirements_in_snapshot,
        "findings_created": run.findings_created,
        "skipped_as_optional": run.skipped_as_optional,
        "failures": len(run.failures),
    }

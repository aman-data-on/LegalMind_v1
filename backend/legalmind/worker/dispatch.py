"""Submitting an analysis — locked 55.1, 52.7, 43.28.

The caller does not choose whether analysis is queued. This module does, from whether
a broker is configured:

```text
LEGALMIND_BROKER_URL set      QUEUED   the locked 55.1 shape: a worker job
              unset           INLINE   development convenience; the production
                                       preflight fails a deployment like this
```

Both modes call exactly the same `run_analysis`, so the mode cannot change a legal
outcome — only who waits for it.

--------------------------------------------------------------------------
Queued mode writes nothing before it enqueues, on purpose
--------------------------------------------------------------------------
The obvious design — mark the Review `PROCESSING`, then enqueue — creates a dual
write across two systems that cannot commit together, and both failure directions are
bad: commit-then-lost-message leaves a Review stuck in `PROCESSING`, and locked Step
30 gives `PROCESSING` no way out except `ANALYSIS_COMPLETE` or the **terminal**
`ANALYSIS_FAILED`. There is no locked path back, so an infrastructure hiccup would
cost a Review permanently.

So dispatch performs **no writes at all**. It reads, refuses early if the Review is
not analysable, and enqueues; the worker's own transaction owns every state change.
A message lost before pickup therefore costs nothing but a re-submission, which is
the recoverable direction to fail in.

The visible cost is that a queued Review shows its pre-analysis lifecycle state until
a worker picks the job up. Locked Step 30 has no `QUEUED` state and none is invented
here (rule 4): 52.7 makes the Review lifecycle the single source of progress, and a
state the specification does not define would be a second one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session as DBSession

from legalmind.analysis.service import AnalysisRun, assert_analysable, run_analysis
from legalmind.db import models as M
from legalmind.observability.logs import log_event
from legalmind.worker.app import (
    QUEUE_ANALYSIS,
    configure_broker,
    evaluator_fingerprint,
)


class DispatchMode(str, Enum):
    QUEUED = "queued"
    INLINE = "inline"


@dataclass(frozen=True)
class AnalysisDispatch:
    mode: DispatchMode
    review_id: UUID
    review_status: str
    #: Present in INLINE mode only — in QUEUED mode there is no run yet, and
    #: inventing a placeholder summary would misreport what happened.
    run: AnalysisRun | None = None
    task_id: str | None = None


def dispatch_analysis(db: DBSession, review: M.Review, *,
                      actor_id: UUID | None = None,
                      request_id: str | None = None) -> AnalysisDispatch:
    """Run the analysis, or queue it — locked 55.1.

    Raises `AnalysisNotPermitted` in both modes for a Review that must not be
    analysed (43.28). Checking before enqueueing matters: a refusal the caller can
    see is worth more than a job that is silently discarded by the worker.
    """
    broker = configure_broker()
    if broker is None:
        run = run_analysis(db, review, actor_id=actor_id, request_id=request_id)
        return AnalysisDispatch(mode=DispatchMode.INLINE, review_id=review.id,
                                review_status=run.review_status, run=run)

    assert_analysable(db, review)

    # Imported here rather than at module scope: `tasks` imports the Celery app,
    # which imports `tasks` back to register the task. Keeping this local means the
    # inline path — the one the test suite and a broker-less developer use — never
    # depends on that cycle resolving.
    from legalmind.worker.tasks import analyse_review

    async_result = analyse_review.apply_async(
        kwargs={
            # Identifiers only. Nothing about the document, the configuration or the
            # legal position travels through the broker (53.3's instinct applied to a
            # queue): the worker reads all of it from the pinned snapshot, which is
            # also what keeps the job reproducible (AUD-04).
            "review_id": str(review.id),
            "actor_id": str(actor_id) if actor_id else None,
            "request_id": request_id,
            # 55.1 — the worker refuses the job if its evaluator versions differ.
            "evaluator_fingerprint": evaluator_fingerprint(),
        },
        queue=QUEUE_ANALYSIS,
    )

    # A log line, not an audit event. Locked 53.1: "nothing in the log pipeline is
    # authoritative for any legal conclusion" — and a *request* to analyse produces no
    # legal record. The audit trail gains its entries when the job actually runs, from
    # the lifecycle transitions (Step 30 r17) and the analysis record itself.
    log_event("analysis.queued", request_id=request_id,
              review_id=str(review.id), task_id=async_result.id,
              queue=QUEUE_ANALYSIS)

    return AnalysisDispatch(mode=DispatchMode.QUEUED, review_id=review.id,
                            review_status=review.status.value,
                            task_id=async_result.id)


# --------------------------------------------------------------------------
# Assist-lane indexing — Gate section 5b unit A2
# --------------------------------------------------------------------------
def dispatch_indexing(db: DBSession, document_version_id: UUID, *,
                      request_id: str | None = None) -> str:
    """Index a document version, on the queue if there is one and inline if not.

    Returns the dispatch mode, for logging. Never raises: an upload whose parsing
    succeeded must not be undone because a derived index could not be started.

    --------------------------------------------------------------------------
    Why this may enqueue before the commit, where `dispatch_analysis` may not
    --------------------------------------------------------------------------
    `dispatch_analysis` refuses to write anything before enqueueing, because marking a
    Review `PROCESSING` and then losing the message would burn it: Step 30 gives
    `PROCESSING` no path back out, so a committed state change plus a lost message is
    an unrecoverable Review.

    Indexing has no such state. If the caller's transaction rolls back, the enqueued
    message simply finds no document version and drops — the task's documented
    behaviour. Nothing is marked, so nothing is stranded. The dual-write hazard that
    ruled out mark-then-enqueue for analysis does not arise here, and requiring a
    post-commit hook for a job that is safe to lose would be complexity for its own
    sake.

    Inline is the broker-less fallback, as for analysis. Chunking is cheap — a
    transformation of rows already in memory-range, with no model and no network — so
    running it in the request is acceptable in development in a way that embedding
    generation will not be.
    """
    from legalmind.assist.indexing import index_safely
    from legalmind.worker.app import QUEUE_ASSIST, configure_broker

    broker = configure_broker()
    if broker is None:
        index_safely(db, document_version_id)
        return DispatchMode.INLINE.value

    try:
        from legalmind.worker.tasks import index_document_version

        async_result = index_document_version.apply_async(
            kwargs={"document_version_id": str(document_version_id),
                    "request_id": request_id},
            queue=QUEUE_ASSIST)
        log_event("assist.index.queued", request_id=request_id,
                  document_version_id=str(document_version_id),
                  task_id=async_result.id, queue=QUEUE_ASSIST)
        return DispatchMode.QUEUED.value
    except Exception as exc:
        # A broker that is unreachable is an operational fault, and it must not fail
        # the upload that triggered it. Logged so it is countable rather than silent.
        log_event("assist.index.dispatch_failed", level=logging.WARNING,
                  request_id=request_id,
                  document_version_id=str(document_version_id),
                  error=type(exc).__name__, operational_failure=True)
        return "FAILED"

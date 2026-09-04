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
from legalmind.domain import enums as E
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


# --------------------------------------------------------------------------
# Deferred OCR — the second half of an upload whose parse said ocr_required
# --------------------------------------------------------------------------
def dispatch_ocr(document_version_id: UUID, *,
                 request_id: str | None = None) -> str:
    """Run the deferred OCR pass in a background thread.

    Why a thread and not the queue: this deployment runs no broker (55.1's
    inline fallback is the operative mode everywhere today), and an "inline
    fallback" here would put the ~60s OCR right back inside the upload request —
    the exact problem the deferral exists to remove. A daemon thread in the API
    process is the smallest mechanism that actually backgrounds the work in the
    deployment that exists; if a broker is ever deployed, this is the seam where
    a Celery task replaces the thread.

    Durability is NOT the thread's job — a daemon thread dies with its process.
    It is the state model's: the version is committed PROCESSING, every attempt
    commits its own STARTED run before doing risky work (42.5's history, used
    as the crash record), and `reconcile_interrupted_ocr` at API startup
    re-dispatches whatever a death interrupted, up to `OCR_MAX_ATTEMPTS`.

    Never raises: the upload has already succeeded and the version is honestly
    PROCESSING. A dispatch failure is logged; startup reconciliation is the
    retry path.
    """
    import threading

    try:
        thread = threading.Thread(
            target=_run_ocr_in_background,
            args=(document_version_id, request_id),
            name=f"legalmind-ocr-{document_version_id}",
            daemon=True,
        )
        thread.start()
        log_event("ingest.ocr.dispatched", request_id=request_id,
                  document_version_id=str(document_version_id), mode="thread")
        return "THREAD"
    except Exception as exc:                     # pragma: no cover - OS resource limits
        log_event("ingest.ocr.dispatch_failed", level=logging.WARNING,
                  request_id=request_id,
                  document_version_id=str(document_version_id),
                  error=type(exc).__name__, operational_failure=True)
        return "FAILED"


#: An OCR job that has died this many times is abandoned rather than retried
#: forever: a document that reliably kills its process (a pathological page
#: that OOMs the renderer, say) must not turn Restart=always into a crash loop.
#: Three attempts is one real try plus two restarts' worth of benefit of the
#: doubt.
OCR_MAX_ATTEMPTS = 3


def _ocr_lock_key(document_version_id: UUID) -> int:
    """A stable 64-bit advisory-lock key for one document version.

    ``hash(UUID)`` delegates to ``hash(self.int)`` — unlike str/bytes hashing,
    int hashing is not affected by ``PYTHONHASHSEED``, so this is stable across
    processes and already fits Postgres's signed-bigint range.
    """
    return hash(document_version_id)


def _ocr_attempt_state(db: DBSession, document_version_id: UUID) -> str:
    """What a would-be OCR attempt should do, from committed state alone.

    * ``"concluded"`` — the version is gone or no longer PROCESSING: another
      attempt finished the job (or the upload rolled back). Nothing to do.
    * ``"abandon"`` — `OCR_MAX_ATTEMPTS` OCR runs already exist. Each attempt
      commits its STARTED run before parsing, so a crashed attempt is exactly
      as countable as a failed one; hitting the cap means this document has
      repeatedly taken its process down and must fail closed, not loop.
    * ``"run"`` — otherwise: claim a new run and do the work.

    Pure read; the caller decides under the advisory lock, so two concurrent
    deciders cannot both act on the same answer.
    """
    from sqlalchemy import func, select

    version = db.get(M.DocumentVersion, document_version_id)
    if version is None or version.processing_status is not E.ProcessingStatus.PROCESSING:
        return "concluded"
    attempts = db.execute(
        select(func.count(M.DocumentProcessingRun.id)).where(
            M.DocumentProcessingRun.document_version_id == document_version_id,
            M.DocumentProcessingRun.run_type == E.ProcessingRunType.OCR,
        )
    ).scalar_one()
    if attempts >= OCR_MAX_ATTEMPTS:
        return "abandon"
    return "run"


def _abandon_ocr(db: DBSession, document_version_id: UUID) -> None:
    """The deterministic terminal state for a job that keeps dying.

    FAILED on both axes — recoverable exactly as any failed extraction is (a
    reprocess is a NEW run, 42.5) — plus one committed FAILED run stating why,
    so the attempt history explains itself instead of ending mid-sentence.
    """
    from legalmind.ingestion.service import PROCESSOR_VERSION, _now

    version = db.get(M.DocumentVersion, document_version_id)
    if version is None or version.processing_status is not E.ProcessingStatus.PROCESSING:
        return
    version.processing_status = E.ProcessingStatus.FAILED
    version.extraction_status = E.ExtractionStatus.FAILED
    db.add(M.DocumentProcessingRun(
        document_version_id=document_version_id,
        run_type=E.ProcessingRunType.OCR,
        status=E.ProcessingRunStatus.FAILED,
        processor_version=PROCESSOR_VERSION,
        started_at=_now(),
        completed_at=_now(),
        error_code="EXTRACTION_FAILED",
        error_message=(f"abandoned after {OCR_MAX_ATTEMPTS} interrupted OCR "
                       "attempts; the document repeatedly took its worker down"),
    ))
    db.flush()


def _run_ocr_in_background(document_version_id: UUID,
                           request_id: str | None) -> None:
    """The thread body: lock, decide, claim, work, index — each a separate,
    honestly-committed step, so a death at any point leaves recoverable state.

    * **Advisory lock** (session-level, held on a dedicated connection for the
      whole job): at most one OCR job per version across every process that
      shares the database. Released automatically when the connection closes —
      including by process death, which is the point.
    * **Claim before work**: the STARTED run row is committed before parsing,
      so an attempt that dies with its process is still countable (42.5's
      attempt history as the crash record).
    * **The work is one transaction**: run outcome + evidence + version
      statuses commit together — a death mid-parse rolls back cleanly to
      "claimed but unfinished", which reconciliation retries.

    The dispatching request's transaction commits after the thread starts, so
    the version row may not be visible yet — bounded retries cover that window.
    If it never appears the request rolled back, and there is honestly nothing
    to do (the same reasoning as dispatch_indexing's drop-on-rollback).
    """
    import time

    from sqlalchemy import text

    from legalmind.api.storage import get_storage
    from legalmind.assist.indexing import index_safely
    from legalmind.db.session import engine, session_factory
    from legalmind.ingestion.service import PROCESSOR_VERSION, _now, run_ocr_pass

    try:
        factory = session_factory()

        visible = False
        for _ in range(20):                      # ~10s window for the commit
            with factory() as probe:
                if probe.get(M.DocumentVersion, document_version_id) is not None:
                    visible = True
                    break
            time.sleep(0.5)
        if not visible:
            log_event("ingest.ocr.version_not_visible", request_id=request_id,
                      document_version_id=str(document_version_id))
            return

        # One job per version, database-wide. pg_try_advisory_lock never
        # blocks: a second trigger (a concurrent reconciler, a future second
        # worker) simply steps aside and lets the holder finish. The `with`
        # closes the connection on every exit path — including an exception —
        # which releases its session-level advisory lock; process death does
        # the same, which is what makes the lock safe.
        with engine().connect() as lock_conn:
            got = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": _ocr_lock_key(document_version_id)},
            ).scalar()
            if not got:
                log_event("ingest.ocr.already_running", request_id=request_id,
                          document_version_id=str(document_version_id))
                return

            with factory() as db:
                state = _ocr_attempt_state(db, document_version_id)
                if state == "concluded":
                    return
                if state == "abandon":
                    _abandon_ocr(db, document_version_id)
                    db.commit()
                    log_event("ingest.ocr.abandoned", level=logging.ERROR,
                              request_id=request_id,
                              document_version_id=str(document_version_id),
                              operational_failure=True)
                    return
                # Claim: committed BEFORE the risky work, so this attempt exists
                # even if the process dies mid-parse.
                claim = M.DocumentProcessingRun(
                    document_version_id=document_version_id,
                    run_type=E.ProcessingRunType.OCR,
                    status=E.ProcessingRunStatus.STARTED,
                    processor_version=PROCESSOR_VERSION,
                    started_at=_now(),
                )
                db.add(claim)
                db.commit()
                claim_id = claim.id

            with factory() as db:
                row = db.get(M.DocumentVersion, document_version_id)
                claim = db.get(M.DocumentProcessingRun, claim_id)
                assert row is not None and claim is not None   # just committed
                run = run_ocr_pass(db, get_storage(), row, run=claim)
                # The derived search index, in the SAME transaction — exactly as
                # the inline path indexes inside the upload's own transaction. One
                # commit means one outcome: a version is never COMPLETED without
                # its index having had its chance, and a death anywhere here rolls
                # back to "claimed but unfinished", which reconciliation retries.
                # index_safely swallows its own faults, so an indexing failure can
                # degrade search ("Not yet searchable") without failing the OCR.
                if run.status is E.ProcessingRunStatus.COMPLETED:
                    index_safely(db, document_version_id)
                db.commit()
                log_event("ingest.ocr.completed", request_id=request_id,
                          document_version_id=str(document_version_id),
                          run_status=run.status.value,
                          extraction_status=(row.extraction_status.value
                                             if row.extraction_status else None))
    except Exception as exc:
        log_event("ingest.ocr.failed", level=logging.ERROR,
                  request_id=request_id,
                  document_version_id=str(document_version_id),
                  error=type(exc).__name__, operational_failure=True)
        # Best-effort: leave a terminal state rather than a version that says
        # PROCESSING forever. FAILED is recoverable (a reprocess is a new run,
        # 42.5) where an eternal PROCESSING is just a lie about ongoing work.
        try:
            from legalmind.db.session import session_factory
            with session_factory()() as db:
                row = db.get(M.DocumentVersion, document_version_id)
                if row is not None and \
                        row.processing_status is E.ProcessingStatus.PROCESSING:
                    row.processing_status = E.ProcessingStatus.FAILED
                    row.extraction_status = E.ExtractionStatus.FAILED
                    db.commit()
        except Exception:                        # pragma: no cover - double fault
            pass


def interrupted_ocr_versions(db: DBSession) -> list[UUID]:
    """Every document version whose processing was interrupted.

    A committed PROCESSING is only ever the deferred-OCR in-between state (the
    inline path commits PENDING→terminal in one request transaction), and OCR
    jobs are threads that die with their process — so at API startup, every
    PROCESSING version is by definition orphaned and safe to re-dispatch. The
    advisory lock covers the one exception (another live process already picked
    it up).
    """
    from sqlalchemy import select

    return list(db.execute(
        select(M.DocumentVersion.id).where(
            M.DocumentVersion.processing_status == E.ProcessingStatus.PROCESSING)
    ).scalars().all())


def reconcile_interrupted_ocr() -> int:
    """Re-dispatch every interrupted OCR job — called once at API startup.

    This is what makes the background thread durable WITHOUT a queue: the
    database is the ledger (PROCESSING version + committed claim runs), the
    thread is disposable, and a restart replays whatever the last process left
    unfinished. `Restart=always` on the service unit turns any crash into this
    path. A version at the attempt cap is failed closed by the dispatched
    attempt itself (`_ocr_attempt_state` → "abandon"), so a document that keeps
    killing its process converges to FAILED instead of looping.

    Never raises — a reconciliation failure must not stop the API from serving.
    """
    try:
        from legalmind.db.session import session_factory
        with session_factory()() as db:
            orphans = interrupted_ocr_versions(db)
        for version_id in orphans:
            dispatch_ocr(version_id, request_id="startup-reconcile")
        if orphans:
            log_event("ingest.ocr.reconciled", count=len(orphans),
                      document_version_ids=[str(v) for v in orphans])
        return len(orphans)
    except Exception as exc:                     # pragma: no cover - startup guard
        log_event("ingest.ocr.reconcile_failed", level=logging.WARNING,
                  error=type(exc).__name__, operational_failure=True)
        return 0

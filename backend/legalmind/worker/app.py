"""The Celery application — locked Step 39 (Celery + Redis) and locked 55.1.

Locked 55.1's shape:

```text
Next.js → FastAPI → PostgreSQL + object storage + worker/queue
Workers run the SAME image as the API — a version skew would break
evaluator_version reproducibility, so they deploy together.
```

So this is not a separate service. It is the same package, imported by a different
entry point:

```text
api      uvicorn legalmind.api.app:app
worker   celery -A legalmind.worker.app worker
```

Nothing here decides anything legal. The worker is a transport: it moves one
`review_id` from a queue into `analysis.service.run_analysis`, which is the same
function the inline path calls. That is deliberate — if the queued and inline paths
could produce different Findings, `ENG-11` determinism would depend on how a Review
happened to be submitted.

--------------------------------------------------------------------------
Why there is no result backend
--------------------------------------------------------------------------
Locked 52.7: "the Review lifecycle state is the single source of progress." A Celery
result backend would be a *second* store of job state, and the two could disagree —
a job marked SUCCESS beside a Review still in `PROCESSING` would leave a reader with
two answers and no way to choose. The Review is the answer; results are ignored.
"""

from __future__ import annotations

from celery import Celery, bootsteps, signals
from celery.exceptions import ImproperlyConfigured

from legalmind import config
from legalmind.db import session as db_session
from legalmind.evaluation.registry import EVALUATOR_VERSIONS
from legalmind.observability.logs import configure_logging, log_event

#: Stable task name. Pinned explicitly rather than derived from the module path,
#: because a rename would orphan every message already on the queue — the messages
#: name the task, and a worker that no longer registers that name cannot run them.
TASK_ANALYSE_REVIEW = "legalmind.analysis.analyse_review"

QUEUE_ANALYSIS = "analysis"

celery_app = Celery("legalmind")

celery_app.conf.update(
    # --- serialization ---------------------------------------------------
    # JSON only. Pickle would let a broker-adjacent attacker execute code during
    # deserialization, which sits badly beside Step 39's untrusted-input posture —
    # and JSON has the useful side effect of *forcing* the message to carry
    # identifiers rather than objects (53.3: "log records carry identifiers, not
    # content" is the same instinct, and a queue message is no more private than a
    # log line).
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # --- results ---------------------------------------------------------
    # See the module docstring: 52.7 makes the Review lifecycle the single source of
    # progress, so there is deliberately nowhere else to look.
    result_backend=None,
    task_ignore_result=True,

    # --- delivery guarantees ---------------------------------------------
    # Acknowledge AFTER the job finishes, so a worker killed mid-analysis has its
    # message redelivered instead of silently losing the Review. Safe only because
    # re-delivery is harmless: `run_analysis` is one transaction, and 43.28 makes it
    # refuse a Review that already has Findings, so a redelivered message either
    # completes the work or reports that it was already done.
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # One job at a time per process. Analysis is long and variable; prefetching would
    # strand queued Reviews behind whichever document happened to be slowest.
    worker_prefetch_multiplier=1,

    # An operational ceiling, not a specified one (see `config`). The hard limit
    # kills the process, which rolls the transaction back — so a Review is never left
    # half-analysed by a timeout.
    task_time_limit=config.analysis_time_limit_seconds(),
    task_soft_time_limit=max(config.analysis_time_limit_seconds() - 60, 60),

    # --- how long a lost message stays lost -------------------------------
    # `task_acks_late` alone does NOT make recovery prompt, which is the kind of thing
    # only a real crash reveals: killing a worker with SIGKILL left 23 of 24 Reviews
    # analysed and one apparently lost. It was not lost. The Redis transport tracks
    # delivered-but-unacked messages in a sorted set and restores them only once their
    # **visibility timeout** expires, and kombu's default is 3600 seconds — so a
    # crashed worker's in-flight Review would sit untouched for an hour, looking stuck.
    #
    # A graceful stop restores immediately (kombu's `restore_at_shutdown`), so only an
    # abrupt death is affected — precisely the case the setting exists for.
    #
    # It must stay ABOVE `task_time_limit`: a timeout shorter than the longest task
    # would redeliver a job that is still running, and two workers analysing one Review
    # would collide on `UNIQUE(review_id, requirement_version_id)`. Correct, but
    # wasteful — so the two values are derived together here rather than set apart and
    # left to drift.
    broker_transport_options={
        "visibility_timeout": config.analysis_time_limit_seconds() + 60,
    },

    task_default_queue=QUEUE_ANALYSIS,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)


def evaluator_fingerprint() -> str:
    """A stable fingerprint of the evaluator versions this process would run.

    Locked 55.1 gives the reason this exists: "a version skew would break
    `evaluator_version` reproducibility, so they deploy together." A queue makes skew
    reachable in a way a single process never was — an API from release N can enqueue
    a Review that a worker from release N-1 picks up, and the Evaluations would then
    record a version the caller never ran.

    Derived from `EVALUATOR_VERSIONS` (locked 45B.10 / AM-19) rather than from a
    build tag, because that mapping is exactly what reproducibility depends on.
    """
    return ";".join(f"{t.value}={v}" for t, v in sorted(
        EVALUATOR_VERSIONS.items(), key=lambda kv: kv[0].value))


def configure_broker() -> str | None:
    """Point the app at the configured broker, reading the environment each time.

    Re-read on every dispatch rather than only at import, so a deployment can set the
    broker without import order deciding whether it took effect.
    """
    url = config.broker_url()
    if celery_app.conf.broker_url != url:
        celery_app.conf.broker_url = url
    return url


# Applied at import as well, because `celery -A legalmind.worker.app worker` never
# calls `dispatch_analysis`: it reads the app's configuration and starts consuming. An
# earlier version configured the broker only on dispatch, and the worker silently
# connected to Celery's `amqp://localhost` default instead — a RabbitMQ that is not in
# the locked Step 39 stack and does not exist. It idled without error.
configure_broker()


# --------------------------------------------------------------------------
# Worker lifecycle
# --------------------------------------------------------------------------
@signals.setup_logging.connect
def _use_legalmind_logging(**_kwargs) -> None:
    """Take logging away from Celery — locked 53.2 / 53.3.

    Connecting this signal at all is what stops Celery configuring the root logger
    its own way. That matters more here than it looks: our formatter is the thing
    that applies 53.3's redaction, so a worker logging through Celery's default
    handlers would be the one process in the system able to print unredacted fields.
    """
    configure_logging()


class RequireBroker(bootsteps.Step):
    """Refuse to start a worker that has nowhere to consume from — rule 15.

    Celery's default broker is `amqp://localhost`, so an unconfigured worker starts
    *cleanly*, prints a banner and consumes nothing. That failure mode is the worst
    available here: a queue that appears to be served and is not, which for analysis
    means Reviews that quietly never acquire Findings, with no error anywhere.

    A bootstep rather than a `worker_init` signal handler, because Celery signals
    swallow receiver exceptions by design — "in Celery `send` and `send_robust` do the
    same thing" — so a signal cannot abort startup. This was found by starting a real
    worker with no broker and watching it come up on `amqp://` regardless.
    """

    def __init__(self, worker, **kwargs):
        super().__init__(worker, **kwargs)
        if configure_broker() is None:
            raise ImproperlyConfigured(
                "LEGALMIND_BROKER_URL is not set. A worker with no broker falls back "
                "to Celery's amqp:// default, which is not in the locked Step 39 "
                "stack (Celery + Redis) and would consume nothing")


celery_app.steps["worker"].add(RequireBroker)


@signals.worker_process_init.connect
def _reset_engine_after_fork(**_kwargs) -> None:
    """Never inherit a database connection across `fork`.

    A pooled connection shared by parent and child corrupts both sides of the wire.
    Dropping the engine in each worker process forces a fresh pool, which for an
    append-only legal record is not a subtlety worth risking.
    """
    db_session.reset()


@signals.worker_ready.connect
def _announce(**_kwargs) -> None:
    log_event("worker.ready",
              queue=QUEUE_ANALYSIS,
              evaluator_fingerprint=evaluator_fingerprint())


# Import for its side effect: registering the task on this app. Placed last so the
# module's configuration is complete before the task module reads it.
from legalmind.worker import tasks as _tasks  # noqa: E402,F401

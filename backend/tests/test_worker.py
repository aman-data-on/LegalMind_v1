"""Queued analysis — locked 55.1, Step 39, 52.7, 43.28, 43.26.

Locked 55.1 is the whole basis for this layer:

```text
Workers run the SAME image as the API — a version skew would break
evaluator_version reproducibility, so they deploy together.
```

So the tests below are mostly about the properties that make a queue *safe* here
rather than about Celery working:

* the queued and inline paths call the same `run_analysis`, so submission mode cannot
  change a legal outcome;
* the message carries identifiers only — no clause text reaches the broker;
* a differently-versioned worker refuses the job instead of recording Evaluations
  under an `evaluator_version` the caller never ran;
* a failed job leaves the Review analysable, because locked Step 30 makes
  `ANALYSIS_FAILED` terminal and an infrastructure fault must not consume a Review.

**Every configured value here is STRUCTURAL and carries no legal meaning** (rule 21).
The fixtures are imported from `test_analysis`, which states the same.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from legalmind.analysis.service import AnalysisNotPermitted
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.evaluation.registry import EVALUATOR_VERSIONS
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.worker import dispatch as D
from legalmind.worker.app import (
    QUEUE_ANALYSIS,
    TASK_ANALYSE_REVIEW,
    celery_app,
    evaluator_fingerprint,
)
from legalmind.worker.tasks import (
    MAX_RETRIES,
    EvaluatorVersionSkew,
    analyse_review,
    assert_no_skew,
)
from tests.conftest import make_user
from tests.test_analysis import (
    LEGAL_RULE,
    MAPPING,
    STANDARD,
    Builder,
)

BROKER = "redis://localhost:6379/15"


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


@pytest.fixture
def review(db, storage):
    """A Review with a real document and a real snapshot, ready to analyse."""
    builder = Builder(db, storage, make_user(db))
    builder.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                        mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    return builder.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 24 months of fees paid.",
    ])


@pytest.fixture(autouse=True)
def restore_broker_configuration():
    """`configure_broker` writes to the Celery app, which outlives a test.

    Without this, a test that configures a broker would leave every later test
    dispatching to a queue that is not there.
    """
    original = celery_app.conf.broker_url
    yield
    celery_app.conf.broker_url = original


@pytest.fixture
def no_broker(monkeypatch):
    monkeypatch.delenv("LEGALMIND_BROKER_URL", raising=False)


@pytest.fixture
def queued(monkeypatch):
    """A configured broker with the send captured, so no Redis is required.

    Deliberately not Celery's ``task_always_eager``: that would execute the job in
    the caller's process and prove nothing about what is actually put on the wire,
    which is the part with a confidentiality rule attached (53.3).
    """
    monkeypatch.setenv("LEGALMIND_BROKER_URL", BROKER)
    sent: list[dict] = []

    class _Sent:
        id = "task-" + uuid.uuid4().hex[:8]

    def fake_apply_async(**call):
        sent.append(call)
        return _Sent()

    monkeypatch.setattr(analyse_review, "apply_async", fake_apply_async)
    return sent


class JoinedSession:
    """The job's session, joined to the test transaction by a savepoint.

    Same device as the `api` fixture's ``request_scoped_db``, and for the same
    reason: the job's ``commit`` and ``rollback`` must behave like a real
    transaction boundary, or a test could pass for the wrong reason. A ``rollback``
    that reached the outer transaction would also discard the *test's* setup, which
    is how the earlier version of this class hid its own bug.

    Everything else is the real `Session` — the job is not given a mock to write into.

    One limit, stated rather than hidden: deferred constraint triggers fire at real
    `COMMIT`, so nothing here can demonstrate EV-MIN. That is covered in
    `test_schema_invariants`; what is under test here is the job wrapper, not the
    invariants it inherits.
    """

    def __init__(self, db):
        self._db = db
        self._savepoint = db.begin_nested()

    def __getattr__(self, name):
        return getattr(self._db, name)

    def commit(self):
        self._db.flush()
        if self._savepoint.is_active:
            self._savepoint.commit()
        self._savepoint = self._db.begin_nested()

    def rollback(self):
        if self._savepoint.is_active:
            self._savepoint.rollback()
        self._savepoint = self._db.begin_nested()

    def close(self):
        if self._savepoint.is_active:
            self._savepoint.commit()


@pytest.fixture
def job_session(db, monkeypatch):
    monkeypatch.setattr("legalmind.worker.tasks._session",
                        lambda: JoinedSession(db))


def findings_of(db, review) -> list[M.Finding]:
    return list(db.execute(
        select(M.Finding).where(M.Finding.review_id == review.id)
    ).scalars().all())


# =====================================================================
# The Celery application — configuration that is load-bearing, not incidental
# =====================================================================
def test_there_is_no_result_backend():
    """52.7 — "the Review lifecycle state is the single source of progress."

    A result backend would be a second store of job state, and a job marked SUCCESS
    beside a Review still in `PROCESSING` would leave a reader with two answers and
    no rule for choosing between them.
    """
    assert celery_app.conf.result_backend is None
    assert celery_app.conf.task_ignore_result is True


def test_only_json_crosses_the_broker():
    """Pickle would make the broker a code-execution path, which sits badly beside
    Step 39's untrusted-input posture — and JSON forces the message to carry
    identifiers rather than objects."""
    assert celery_app.conf.task_serializer == "json"
    assert list(celery_app.conf.accept_content) == ["json"]


def test_a_lost_worker_does_not_lose_the_review():
    """`acks_late` + `reject_on_worker_lost`: a worker killed mid-analysis has its
    message redelivered. Safe only because redelivery is harmless — 43.28 makes the
    job refuse a Review that already has Findings."""
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_the_task_name_is_pinned():
    """A message names the task it wants. Renaming the task — or deriving its name
    from the module path and then moving the module — orphans every message already
    on the queue."""
    assert analyse_review.name == TASK_ANALYSE_REVIEW == \
        "legalmind.analysis.analyse_review"
    assert TASK_ANALYSE_REVIEW in celery_app.tasks


def test_a_job_cannot_outlive_its_time_limit():
    """A hard kill rolls the transaction back, so a timeout leaves no half-analysed
    Review. The value is operational, not specified."""
    assert celery_app.conf.task_time_limit > celery_app.conf.task_soft_time_limit > 0


def test_a_crashed_worker_is_recovered_from_promptly():
    """`acks_late` is not enough on the Redis transport — and this test exists because
    asserting the flags alone was not enough either.

    A real `SIGKILL` against a real worker recovered 23 of 24 Reviews and appeared to
    lose one. Nothing was lost: the Redis transport restores a delivered-but-unacked
    message only after its **visibility timeout**, and kombu's default is 3600 seconds,
    so the Review would have looked stuck for an hour.

    The invariant asserted here is the relationship, not the number: the timeout must
    exceed `task_time_limit`, or a still-running job would be redelivered to a second
    worker.
    """
    visibility = celery_app.conf.broker_transport_options["visibility_timeout"]
    assert visibility > celery_app.conf.task_time_limit
    # And nowhere near kombu's default, which is what made the recovery look like a loss.
    assert visibility < 3600


# =====================================================================
# Dispatch — locked 55.1
# =====================================================================
def test_without_a_broker_analysis_runs_inline(db, review, no_broker):
    """Development convenience, and the reason the preflight fails a production
    deployment configured this way."""
    result = D.dispatch_analysis(db, review)

    assert result.mode is D.DispatchMode.INLINE
    assert result.run is not None and result.run.findings_created == 1
    assert findings_of(db, review)


def test_with_a_broker_the_request_writes_nothing(db, review, queued):
    """The dual-write trap, avoided by not writing.

    Marking the Review `PROCESSING` before enqueueing would be a write to Postgres
    paired with a send to Redis that cannot commit together. Locked Step 30 gives
    `PROCESSING` no way out but `ANALYSIS_COMPLETE` or the **terminal**
    `ANALYSIS_FAILED`, so a lost message would strand the Review permanently. Dispatch
    therefore only reads: a message lost before pickup costs a re-submission.
    """
    result = D.dispatch_analysis(db, review)

    assert result.mode is D.DispatchMode.QUEUED
    assert result.run is None
    assert result.task_id
    # Nothing happened to the Review, and no legal output exists yet.
    assert review.status is E.ReviewStatus.DRAFT
    assert findings_of(db, review) == []


def test_the_message_carries_identifiers_only(db, review, queued):
    """53.3's rule, applied to the broker: "log records carry identifiers, not
    content." A queue message is no more private than a log line, and everything the
    job needs is reachable from the Review's pinned snapshot (AUD-04).
    """
    D.dispatch_analysis(db, review, actor_id=review.created_by,
                        request_id="trace-42")

    kwargs = queued[0]["kwargs"]
    assert set(kwargs) == {"review_id", "actor_id", "request_id",
                           "evaluator_fingerprint"}
    for value in kwargs.values():
        assert value is None or isinstance(value, str)
    # No clause text, no configuration, no threshold, no legal position.
    blob = repr(kwargs).lower()
    for forbidden in ("shall not exceed", "liability", "months", "fees",
                      "acceptable_max"):
        assert forbidden not in blob
    assert queued[0]["queue"] == QUEUE_ANALYSIS


def test_dispatch_refuses_an_already_analysed_review_before_enqueueing(
        db, review, queued):
    """43.28 — and it refuses *before* sending, so the caller sees the refusal
    instead of the worker silently discarding a job."""
    from legalmind.analysis.service import run_analysis
    run_analysis(db, review)

    with pytest.raises(AnalysisNotPermitted):
        D.dispatch_analysis(db, review)
    assert queued == []


def test_both_modes_refuse_on_identical_grounds(db, review, queued):
    """One `assert_analysable`, not two. If the queued path refused on different
    grounds from the inline path, whether a Review could be analysed would depend on
    how it was submitted."""
    from legalmind.analysis import service

    assert D.assert_analysable is service.assert_analysable


# =====================================================================
# Version skew — locked 55.1's stated reason for deploying together
# =====================================================================
def test_the_fingerprint_tracks_the_evaluator_versions(monkeypatch):
    """Derived from `EVALUATOR_VERSIONS` (45B.10 / AM-19) rather than a build tag,
    because that mapping is what reproducibility actually depends on."""
    before = evaluator_fingerprint()
    monkeypatch.setitem(EVALUATOR_VERSIONS, E.EvaluatorType.PRESENCE, "PRESENCE-v2")
    assert evaluator_fingerprint() != before
    assert "PRESENCE-v2" in evaluator_fingerprint()


def test_a_differently_versioned_worker_refuses():
    stale = "NUMERIC_COMPARISON=NUMERIC-COMPARISON-v0;PRESENCE=PRESENCE-v0"
    with pytest.raises(EvaluatorVersionSkew) as raised:
        assert_no_skew(stale)

    # Both fingerprints survive as short, separate fields. A single prose `detail`
    # was tried first and a real worker log came back reading "[209 chars omitted]":
    # 53.3's length guard treats an over-long value as content, which is correct, and
    # the diagnostic has to fit rather than the guard being relaxed.
    from legalmind.observability.redaction import MAX_VALUE_LENGTH, redact_fields

    fields = redact_fields({"dispatched_by": raised.value.dispatched,
                            "worker_runs": raised.value.local})
    assert fields["dispatched_by"] == stale
    assert fields["worker_runs"] == evaluator_fingerprint()
    assert len(stale) < MAX_VALUE_LENGTH


def test_a_matching_worker_accepts():
    assert_no_skew(evaluator_fingerprint())          # does not raise


def test_an_unstamped_message_is_not_skew():
    """`None` means the message predates the guard. Refusing it would strand
    messages during exactly the upgrade the guard exists to protect."""
    assert_no_skew(None)


def test_skew_retries_without_touching_the_review(db, review, job_session,
                                                  monkeypatch):
    """The check runs before anything is written, so refusing costs nothing.

    It must not mark the Review `ANALYSIS_FAILED`: that state is terminal in locked
    Step 30, and a version skew is a deployment fault fixed by deploying together —
    not a reason to consume a Review.
    """
    class Retried(Exception):
        pass

    monkeypatch.setattr(analyse_review, "retry",
                        lambda **kw: Retried(str(kw.get("exc"))))

    with pytest.raises(Retried):
        analyse_review.apply(kwargs={
            "review_id": str(review.id),
            "evaluator_fingerprint": "PRESENCE=PRESENCE-v0",
        }, throw=True)

    assert review.status is E.ReviewStatus.DRAFT
    assert findings_of(db, review) == []


# =====================================================================
# The job itself
# =====================================================================
def test_the_job_produces_the_same_findings_as_the_inline_path(db, review,
                                                              job_session):
    """The point of the whole design: one `run_analysis`, two callers.

    If queued and inline analysis could differ, `ENG-11` determinism would depend on
    how a Review happened to be submitted.
    """
    result = analyse_review.apply(kwargs={
        "review_id": str(review.id),
        "actor_id": str(review.created_by),
        "request_id": "trace-worker",
        "evaluator_fingerprint": evaluator_fingerprint(),
    }, throw=True).get()

    assert result["analysed"] is True
    assert result["findings_created"] == 1
    assert result["review_status"] == "LEGAL_REVIEW"
    assert review.status is E.ReviewStatus.LEGAL_REVIEW
    assert len(findings_of(db, review)) == 1


def test_a_redelivered_message_reports_rather_than_duplicates(db, review,
                                                              job_session):
    """`acks_late` means redelivery happens. 43.28 makes it harmless, and the job
    says so instead of raising — a retry would never succeed."""
    from legalmind.analysis.service import run_analysis
    run_analysis(db, review)
    before = len(findings_of(db, review))

    result = analyse_review.apply(kwargs={"review_id": str(review.id)},
                                  throw=True).get()

    assert result == {"review_id": str(review.id), "analysed": False,
                      "reason_code": "already_analysed"}
    assert len(findings_of(db, review)) == before


def test_a_message_for_a_review_that_does_not_exist_is_dropped(db, job_session):
    """Reviews are never deleted, so in practice this means the enqueuing
    transaction did not commit. There is nothing to analyse and nothing to record."""
    result = analyse_review.apply(
        kwargs={"review_id": str(uuid.uuid4())}, throw=True).get()

    assert result["analysed"] is False
    assert result["reason_code"] == "review_not_found"


def test_a_failed_job_leaves_the_review_analysable(db, review, job_session,
                                                   monkeypatch):
    """43.26's property, applied to a worker: one transaction per job.

    The rollback undoes the lifecycle transition too, so the Review returns to its
    pre-analysis state and a retry starts from a clean slate. Critically it is NOT
    left in `PROCESSING` — which locked Step 30 can only leave for
    `ANALYSIS_COMPLETE` or the terminal `ANALYSIS_FAILED`.
    """
    class Retried(Exception):
        pass

    def explode(*a, **kw):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("legalmind.worker.tasks.run_analysis", explode)
    monkeypatch.setattr(analyse_review, "retry", lambda **kw: Retried())

    with pytest.raises(Retried):
        analyse_review.apply(kwargs={"review_id": str(review.id)}, throw=True)

    assert review.status is E.ReviewStatus.DRAFT
    assert findings_of(db, review) == []
    assert MAX_RETRIES > 0


# =====================================================================
# The API surface
# =====================================================================
def _api_case(api, db, storage):
    from tests.conftest import grant_role, sign_in

    owner = make_user(db)
    grant_role(db, owner, "USER")
    builder = Builder(db, storage, owner)
    builder.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                        mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    review = builder.review([
        "1. Limitation of Liability",
        "Liability shall not exceed 24 months of fees paid.",
    ])
    sign_in(api, db, owner)
    return review


def test_a_queued_submission_is_202_not_201(api, db, storage, seeded, queued):
    """202 accepted, not 201 created: no Finding exists yet, and claiming otherwise
    would make the response disagree with the Review (52.7)."""
    review = _api_case(api, db, storage)

    response = api.post(f"/api/v1/reviews/{review.id}/analyze")

    assert response.status_code == 202
    body = response.json()["data"]
    assert body["mode"] == "queued"
    assert body["task_id"]
    # The Review's real lifecycle state, unchanged. Locked Step 30 has no QUEUED
    # state and none is invented (rule 4).
    assert body["review_status"] == "DRAFT"
    assert "findings_created" not in body


def test_an_inline_submission_still_reports_its_outcome(api, db, storage, seeded,
                                                        no_broker):
    review = _api_case(api, db, storage)

    response = api.post(f"/api/v1/reviews/{review.id}/analyze")

    assert response.status_code == 201
    assert response.json()["data"]["mode"] == "inline"
    assert response.json()["data"]["findings_created"] == 1


# =====================================================================
# Deployment
# =====================================================================
def test_the_preflight_fails_an_inline_production_deployment(monkeypatch):
    """55.1 — analysis is a worker job. Inline analysis returns the same 2xx, so the
    difference is invisible from outside and has to be checked rather than noticed."""
    from legalmind.deploy.preflight import FAIL, PASS, run_preflight

    monkeypatch.delenv("LEGALMIND_BROKER_URL", raising=False)
    checks = {c.name: c for c in run_preflight()}
    assert checks["analysis_worker"].status == FAIL
    assert "55.1" in checks["analysis_worker"].basis

    monkeypatch.setenv("LEGALMIND_BROKER_URL", BROKER)
    assert {c.name: c for c in run_preflight()}["analysis_worker"].status == PASS

"""Queue guarantees, verified against real processes — locked 55.1, 43.28.

`tests/test_worker.py` asserts these properties by inspecting configuration and by
calling the task in-process. That is worth having and it is not verification: "a
message is redelivered when a worker dies" is a claim about a broker and an operating
system, and the only way to check it is to kill a real worker.

Two claims, two mechanisms:

* **`acks_late` + `reject_on_worker_lost` lose nothing.** A batch of Reviews is queued,
  a worker is `kill -9`ed while it is working through them, and every Review must still
  end analysed. Timing is not raced: the batch is long enough that the kill lands
  mid-flight, and the assertion is over the whole batch rather than one message.
* **Duplicate delivery cannot duplicate legal output.** The same Review is enqueued
  five times with two workers running. Exactly one Finding may exist per Requirement —
  proving the claim that the database, not the queue, is the serialization point.
"""

from __future__ import annotations

import io
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.e2e_bootstrap import STRUCTURAL_CONFIGURATION, STRUCTURAL_PARAGRAPHS

PASS, FAIL = "PASS", "FAIL"

DOCX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document")

#: Short task time limit for the verification run, so the derived Redis visibility
#: timeout (limit + 60s) is short enough to observe a redelivery in bounded time.
VERIFY_TIME_LIMIT = 30
RECOVERY_BUDGET = VERIFY_TIME_LIMIT + 60 + 90


def _docx() -> bytes:
    import docx

    document = docx.Document()
    for paragraph in STRUCTURAL_PARAGRAPHS:
        document.add_paragraph(paragraph)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _seed(db, storage, owner_id, snapshot_id) -> uuid.UUID:
    """One analysable Review. Not the thing under verification — the delivery is."""
    contract = M.Contract(owner_id=owner_id, name="Verify contract",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(db, storage, contract_id=contract.id,
                             uploaded_by=owner_id, data=_docx(),
                             filename="verify.docx", declared_mime=DOCX_MIME)
    review = M.Review(contract_id=contract.id,
                      document_version_id=result.document_version.id,
                      configuration_snapshot_id=snapshot_id,
                      status=E.ReviewStatus.DRAFT, created_by=owner_id)
    db.add(review)
    db.flush()
    return review.id


def _configuration(db, owner_id) -> uuid.UUID:
    cfg = STRUCTURAL_CONFIGURATION
    requirement = M.Requirement(code=f"VERIFY-{uuid.uuid4().hex[:6]}",
                                status=E.ConfigStatus.ACTIVE)
    db.add(requirement)
    db.flush()
    rv = M.RequirementVersion(
        requirement_id=requirement.id, version_number=1, name=str(cfg["name"]),
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=owner_id)
    db.add(rv)
    db.flush()
    cs = M.CompanyStandardVersion(requirement_version_id=rv.id, version_number=1,
                                  configuration=cfg["company_standard"],
                                  created_by=owner_id)
    mr = M.MappingRuleVersion(requirement_version_id=rv.id, version_number=1,
                              rules=cfg["mapping_rules"], created_by=owner_id)
    er = M.EvaluationRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
        rules=cfg["evaluation_rules"], created_by=owner_id)
    lr = M.LegalRuleVersion(
        requirement_version_id=rv.id, version_number=1,
        rule_type=E.RuleType.THRESHOLD,
        configuration=cfg["legal_rule"]["configuration"], created_by=owner_id)
    db.add_all([cs, mr, er, lr])
    db.flush()
    snapshot = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex,
                                       created_by=owner_id)
    db.add(snapshot)
    db.flush()
    db.add(M.ConfigurationSnapshotItem(
        snapshot_id=snapshot.id, requirement_version_id=rv.id,
        company_standard_version_id=cs.id, legal_rule_version_id=lr.id,
        mapping_rule_version_id=mr.id, evaluation_rule_version_id=er.id))
    db.flush()
    return snapshot.id


def _start_worker(env: dict[str, str], log: Path) -> subprocess.Popen:
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("w")
    return subprocess.Popen(
        ["celery", "-A", "legalmind.worker.app", "worker", "-Q", "analysis",
         "--concurrency", "1", "--loglevel", "INFO"],
        stdout=handle, stderr=subprocess.STDOUT, env=env,
        # Own process group, so the kill below cannot reach this process.
        start_new_session=True)


def _wait_for(predicate, timeout: float, interval: float = 0.5) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def run(*, redis_port: int, database_url: str) -> dict[str, tuple[str, str, str]]:
    broker = f"redis://127.0.0.1:{redis_port}/1"
    storage_root = Path(".e2e/verify-objects").resolve()
    # The Redis transport restores an abruptly-lost message only after its visibility
    # timeout, which `worker.app` derives from the task time limit. Production's is
    # 30 minutes + 60s; verifying the MECHANISM does not require waiting that long, so
    # the time limit is shortened here and the timeout follows it. What is verified is
    # that redelivery happens at all — the production number is asserted by
    # `test_worker.py` as a relationship, not a duration.
    env = {**os.environ,
           "PYTHONPATH": str(Path.cwd()),
           "LEGALMIND_DATABASE_URL": database_url,
           "LEGALMIND_BROKER_URL": broker,
           "LEGALMIND_STORAGE_ROOT": str(storage_root),
           "LEGALMIND_ANALYSIS_TIME_LIMIT": str(VERIFY_TIME_LIMIT),
           "LEGALMIND_LOG_LEVEL": "INFO"}
    os.environ["LEGALMIND_ANALYSIS_TIME_LIMIT"] = str(VERIFY_TIME_LIMIT)
    os.environ.update({k: env[k] for k in
                       ("LEGALMIND_DATABASE_URL", "LEGALMIND_BROKER_URL",
                        "LEGALMIND_STORAGE_ROOT")})

    # Imported after the broker is in the environment, so the app configures itself
    # against it at import (the defect that made a real worker consume nothing).
    from legalmind.worker.app import configure_broker
    from legalmind.worker.tasks import analyse_review, evaluator_fingerprint

    configure_broker()
    subprocess.run(["redis-cli", "-p", str(redis_port), "-n", "1", "flushdb"],
                   capture_output=True)

    engine = create_engine(database_url, future=True)
    Session = sessionmaker(bind=engine, future=True)
    storage = LocalFilesystemStorage(storage_root)

    outcomes: dict[str, tuple[str, str, str]] = {}

    with Session() as db:
        owner = M.User(email=f"verify-{uuid.uuid4().hex[:8]}@example.test",
                       name="Verify", status=E.UserStatus.ACTIVE)
        db.add(owner)
        db.flush()
        snapshot_id = _configuration(db, owner.id)
        batch = [_seed(db, storage, owner.id, snapshot_id) for _ in range(24)]
        duplicate = _seed(db, storage, owner.id, snapshot_id)
        db.commit()
        owner_id = owner.id

    def findings(review_id) -> int:
        with Session() as db:
            return db.execute(
                select(func.count()).select_from(M.Finding)
                .where(M.Finding.review_id == review_id)).scalar_one()

    # ---------------------------------------------------------------- 1
    # A hard kill mid-batch must lose nothing (acks_late, reject_on_worker_lost).
    log = Path(".e2e/verify-worker-kill.log")
    worker = _start_worker(env, log)
    try:
        for review_id in batch:
            analyse_review.apply_async(
                kwargs={"review_id": str(review_id), "actor_id": str(owner_id),
                        "request_id": "verify-kill",
                        "evaluator_fingerprint": evaluator_fingerprint()},
                queue="analysis")

        # Kill once some work has demonstrably started, so the SIGKILL lands
        # mid-flight rather than before or after the batch.
        started = _wait_for(
            lambda: any(findings(r) for r in batch), timeout=90, interval=0.2)
        os.killpg(os.getpgid(worker.pid), signal.SIGKILL)
        killed_after = sum(1 for r in batch if findings(r))
    finally:
        if worker.poll() is None:                       # pragma: no cover
            try:
                os.killpg(os.getpgid(worker.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        worker.wait(timeout=30)

    # A fresh worker takes over. Redelivery is the guarantee under test: the
    # in-flight message must not have died with the process.
    worker2 = _start_worker(env, Path(".e2e/verify-worker-recover.log"))
    try:
        completed = _wait_for(
            lambda: all(findings(r) for r in batch),
            timeout=RECOVERY_BUDGET, interval=0.5)
        analysed = sum(1 for r in batch if findings(r))
    finally:
        worker2.terminate()
        worker2.wait(timeout=30)

    outcomes["queue_survives_kill_9"] = (
        PASS if (started and completed and analysed == len(batch)) else FAIL,
        f"{analysed}/{len(batch)} Reviews analysed after SIGKILL mid-batch "
        f"({killed_after} were done when the kill landed). The in-flight message was "
        f"redelivered within the {VERIFY_TIME_LIMIT + 60}s visibility timeout; with "
        "kombu's 3600s default it would have looked lost for an hour",
        "real worker process, real SIGKILL to the process group",
    )

    # ---------------------------------------------------------------- 2
    # Five deliveries of ONE Review, two workers. The database is the
    # serialization point; the queue never was.
    workers = [_start_worker(env, Path(f".e2e/verify-worker-dup{i}.log"))
               for i in range(2)]
    try:
        for _ in range(5):
            analyse_review.apply_async(
                kwargs={"review_id": str(duplicate), "actor_id": str(owner_id),
                        "request_id": "verify-duplicate",
                        "evaluator_fingerprint": evaluator_fingerprint()},
                queue="analysis")
        _wait_for(lambda: findings(duplicate) > 0, timeout=120, interval=0.3)
        # Settle, so a duplicate written late would still be caught.
        time.sleep(5)
        count = findings(duplicate)
        with Session() as db:
            evaluations = db.execute(
                select(func.count()).select_from(M.Evaluation)
                .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
                .where(M.Finding.review_id == duplicate)).scalar_one()
    finally:
        for w in workers:
            w.terminate()
            w.wait(timeout=30)

    outcomes["duplicate_delivery_produces_one_finding_set"] = (
        PASS if count == 1 and evaluations == 1 else FAIL,
        f"5 deliveries, 2 workers → {count} Finding(s), {evaluations} Evaluation(s). "
        "UNIQUE(review_id, requirement_version_id) plus 43.28's refusal, not a "
        "queue-level lock",
        "two real worker processes competing over one Review",
    )

    engine.dispose()
    return outcomes

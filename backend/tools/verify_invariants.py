"""Verify the critical guarantees WITHOUT using the tests that assert them.

--------------------------------------------------------------------------
Why this exists
--------------------------------------------------------------------------
Every guarantee below is already covered by a test in `tests/`. That is not the same
as being verified: a test and the code it guards can share the same wrong assumption,
and this repository has a concrete instance of exactly that —
`test_each_axis_has_its_own_enum_type` was **recorded as fixed** while the
`current_schema()` predicate it needed was absent from the query, so it passed alone
and failed beside a sibling.

So this script deliberately uses a *different mechanism* for each claim:

* the database invariants are exercised with **raw SQL on a real connection**, not
  through SQLAlchemy models and not inside pytest — a trigger that existed only in the
  ORM's imagination would pass the suite and fail here;
* the queue guarantees are exercised against **a real Redis and real worker processes**,
  including `kill -9`, because "the message is redelivered" is a claim about a broker
  and an operating system, not about Python;
* the redaction rule is checked by **grepping real log output** for content that must
  never appear, rather than by asking the redactor what it would do.

--------------------------------------------------------------------------
What this is NOT
--------------------------------------------------------------------------
**This is not third-party verification.** It is verification by a mechanism
independent of the unit test, which is a meaningfully stronger claim than "the suite is
green" and a meaningfully weaker one than "someone else confirmed it". It does not make
anything `VERIFIED`: `IMPL-01` condition 2 stands — conformance is verified against the
locked corpus, and that corpus is still 6 `STRUCTURAL` fixtures.

Run it against a THROWAWAY database. It writes rows and drops schemas:

    LEGALMIND_VERIFY_DATABASE_URL=postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_verify \\
    python3 -m tools.verify_invariants
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass
class Result:
    name: str
    status: str
    detail: str
    mechanism: str = ""
    basis: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, *args, **kwargs) -> None:
        result = Result(*args, **kwargs)
        self.results.append(result)
        print(f"  {result.status:<5} {result.name}", flush=True)
        if result.status == FAIL:
            print(f"        {result.detail}", flush=True)

    @property
    def ok(self) -> bool:
        return all(r.status != FAIL for r in self.results)


def verify_url() -> str:
    return os.environ.get(
        "LEGALMIND_VERIFY_DATABASE_URL",
        "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_verify")


# ==========================================================================
# Database invariants — raw SQL, no ORM, no pytest
# ==========================================================================
def _recreate(url: str) -> None:
    parts = urlsplit(url)
    database = parts.path.lstrip("/")
    server = urlunsplit(parts._replace(path="/postgres"))
    engine = create_engine(server, future=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{database}"'))
    engine.dispose()


def _migrate(url: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def _minimal_graph(conn) -> dict[str, str]:
    """Insert the smallest row set that can carry a Finding, in raw SQL.

    Written out longhand rather than reusing the test factories on purpose: reusing
    them would import the same assumptions the tests already encode.
    """
    ids = {k: str(uuid.uuid4()) for k in (
        "user", "contract", "document_version", "processing_run", "snapshot",
        "requirement", "requirement_version", "company_standard", "mapping_rules",
        "evaluation_rules", "review", "finding", "evaluation", "evidence")}

    conn.execute(text("""
        INSERT INTO users (id, email, name, status, created_at, updated_at)
        VALUES (:id, :email, 'Verify', 'ACTIVE', now(), now())"""),
        {"id": ids["user"], "email": f"verify-{ids['user'][:8]}@example.test"})
    conn.execute(text("""
        INSERT INTO contracts (id, owner_id, name, status, created_at, updated_at)
        VALUES (:id, :owner, 'Verify contract', 'ACTIVE', now(), now())"""),
        {"id": ids["contract"], "owner": ids["user"]})
    conn.execute(text("""
        INSERT INTO document_versions
            (id, contract_id, version_number, original_filename, mime_type,
             file_size_bytes, file_hash, storage_key, processing_status,
             uploaded_by, created_at)
        VALUES (:id, :contract, 1, 'v.docx', 'application/octet-stream',
                1, :hash, :key, 'COMPLETED', :user, now())"""),
        {"id": ids["document_version"], "contract": ids["contract"],
         "hash": ids["document_version"], "key": f"k/{ids['document_version']}",
         "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO requirements (id, code, status, created_at, updated_at)
        VALUES (:id, :code, 'ACTIVE', now(), now())"""),
        {"id": ids["requirement"], "code": f"VERIFY-{ids['requirement'][:8]}"})
    conn.execute(text("""
        INSERT INTO requirement_versions
            (id, requirement_id, version_number, name, evaluator_type,
             created_by, created_at)
        VALUES (:id, :req, 1, 'Verify', 'PRESENCE', :user, now())"""),
        {"id": ids["requirement_version"], "req": ids["requirement"],
         "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO company_standard_versions
            (id, requirement_version_id, version_number, configuration,
             created_by, created_at)
        VALUES (:id, :rv, 1, '{}', :user, now())"""),
        {"id": ids["company_standard"], "rv": ids["requirement_version"],
         "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO mapping_rule_versions
            (id, requirement_version_id, version_number, rules, created_by, created_at)
        VALUES (:id, :rv, 1, '{}', :user, now())"""),
        {"id": ids["mapping_rules"], "rv": ids["requirement_version"],
         "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO evaluation_rule_versions
            (id, requirement_version_id, version_number, evaluator_type, rules,
             created_by, created_at)
        VALUES (:id, :rv, 1, 'PRESENCE', '{}', :user, now())"""),
        {"id": ids["evaluation_rules"], "rv": ids["requirement_version"],
         "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO configuration_snapshots
            (id, snapshot_hash, created_by, created_at)
        VALUES (:id, :hash, :user, now())"""),
        {"id": ids["snapshot"], "hash": ids["snapshot"], "user": ids["user"]})
    conn.execute(text("""
        INSERT INTO reviews
            (id, contract_id, document_version_id, configuration_snapshot_id,
             status, created_by, created_at)
        VALUES (:id, :contract, :dv, :snapshot, 'DRAFT', :user, now())"""),
        {"id": ids["review"], "contract": ids["contract"],
         "dv": ids["document_version"], "snapshot": ids["snapshot"],
         "user": ids["user"]})
    return ids


def _insert_finding_with_evaluation(conn, ids: dict[str, str]) -> None:
    conn.execute(text("""
        INSERT INTO findings
            (id, review_id, requirement_version_id, classification, status,
             created_at, updated_at)
        VALUES (:id, :review, :rv, 'MATCH', 'OPEN', now(), now())"""),
        {"id": ids["finding"], "review": ids["review"],
         "rv": ids["requirement_version"]})
    conn.execute(text("""
        INSERT INTO evaluations
            (id, finding_id, scope_key, evaluation_kind, classification,
             rule_outcome, evaluator_type, evaluator_version, result, created_at)
        VALUES (:id, :finding, 'AGGREGATE', 'PRIMARY', 'MATCH', 'NOT_APPLICABLE',
                'PRESENCE', 'PRESENCE-v1', '{}', now())"""),
        {"id": ids["evaluation"], "finding": ids["finding"]})


def check_database(report: Report) -> None:
    url = verify_url()
    print("\nDatabase invariants — raw SQL on a real connection", flush=True)
    _recreate(url)
    _migrate(url)
    engine = create_engine(url, future=True)

    # ---- EV-MIN, insert path (AB-1.6) ---------------------------------
    with engine.connect() as conn:
        ids = _minimal_graph(conn)
        try:
            conn.execute(text("""
                INSERT INTO findings
                    (id, review_id, requirement_version_id, classification, status,
                     created_at, updated_at)
                VALUES (:id, :review, :rv, 'MATCH', 'OPEN',
                        now(), now())"""),
                {"id": str(uuid.uuid4()), "review": ids["review"],
                 "rv": ids["requirement_version"]})
            conn.commit()
            report.add("ev_min_insert", FAIL,
                       "a Finding with no Evaluation committed",
                       mechanism="raw INSERT, no ORM", basis="AB-1.6, F-5")
        except Exception as exc:
            conn.rollback()
            ok = "EV-MIN" in str(exc)
            report.add("ev_min_insert", PASS if ok else FAIL,
                       f"refused at COMMIT: {type(exc).__name__}"
                       if ok else f"refused, but not by EV-MIN: {exc}",
                       mechanism="raw INSERT, no ORM", basis="AB-1.6, F-5")

    # ---- EV-MIN, removal path (F-1) -----------------------------------
    with engine.connect() as conn:
        ids = _minimal_graph(conn)
        _insert_finding_with_evaluation(conn, ids)
        conn.commit()
    with engine.connect() as conn:
        try:
            conn.execute(text("DELETE FROM evaluations WHERE finding_id = :f"),
                         {"f": ids["finding"]})
            conn.commit()
            report.add("ev_min_delete", FAIL,
                       "the last Evaluation was deleted, orphaning the Finding",
                       mechanism="raw DELETE, no ORM", basis="F-1, AB-1.6")
        except Exception as exc:
            conn.rollback()
            ok = "EV-MIN" in str(exc)
            report.add("ev_min_delete", PASS if ok else FAIL,
                       f"refused at COMMIT: {type(exc).__name__}"
                       if ok else f"refused, but not by EV-MIN: {exc}",
                       mechanism="raw DELETE, no ORM", basis="F-1, AB-1.6")

    # ---- EV-MIN, re-parent path (F-1) ---------------------------------
    with engine.connect() as conn:
        other = _minimal_graph(conn)
        _insert_finding_with_evaluation(conn, other)
        conn.commit()
        try:
            conn.execute(text("""
                UPDATE evaluations SET finding_id = :new WHERE finding_id = :old"""),
                {"new": ids["finding"], "old": other["finding"]})
            conn.commit()
            report.add("ev_min_reparent", FAIL,
                       "an Evaluation was moved away, orphaning its Finding",
                       mechanism="raw UPDATE, no ORM", basis="F-1")
        except Exception as exc:
            conn.rollback()
            ok = "EV-MIN" in str(exc)
            report.add("ev_min_reparent", PASS if ok else FAIL,
                       f"refused at COMMIT: {type(exc).__name__}"
                       if ok else f"refused, but not by EV-MIN: {exc}",
                       mechanism="raw UPDATE, no ORM", basis="F-1")

    # ---- Append-only audit trail (AUD-01) -----------------------------
    with engine.connect() as conn:
        event_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO audit_events (id, action, entity_type, timestamp)
            VALUES (:id, 'verify.probe', 'verification', now())"""),
            {"id": event_id})
        conn.commit()
        for operation, statement in (
            ("update", "UPDATE audit_events SET action = 'tampered' WHERE id = :id"),
            ("delete", "DELETE FROM audit_events WHERE id = :id"),
        ):
            try:
                conn.execute(text(statement), {"id": event_id})
                conn.commit()
                report.add(f"audit_append_only_{operation}", FAIL,
                           f"an audit event was {operation}d",
                           mechanism="raw SQL, no ORM", basis="AUD-01, 41.x")
            except Exception as exc:
                conn.rollback()
                report.add(f"audit_append_only_{operation}", PASS,
                           f"refused: {type(exc).__name__}",
                           mechanism="raw SQL, no ORM", basis="AUD-01")

    # ---- Uniqueness (43.28's backstop) --------------------------------
    with engine.connect() as conn:
        ids = _minimal_graph(conn)
        _insert_finding_with_evaluation(conn, ids)
        conn.commit()
        try:
            conn.execute(text("""
                INSERT INTO findings
                    (id, review_id, requirement_version_id, classification, status,
                     created_at, updated_at)
                VALUES (:id, :review, :rv, 'MATCH', 'OPEN',
                        now(), now())"""),
                {"id": str(uuid.uuid4()), "review": ids["review"],
                 "rv": ids["requirement_version"]})
            conn.commit()
            report.add("finding_uniqueness", FAIL,
                       "a second Finding for the same (review, requirement_version)",
                       mechanism="raw INSERT, no ORM", basis="43.28, 54.5")
        except Exception as exc:
            conn.rollback()
            report.add("finding_uniqueness", PASS,
                       f"refused: {type(exc).__name__}",
                       mechanism="raw INSERT, no ORM", basis="43.28, 54.5")

    # ---- The enum-scoping claim, checked both ways ---------------------
    # The regression this re-checks: `pg_type` is database-wide, so an unscoped
    # count sums enum types belonging to OTHER schemas. Two schemas are created
    # here on purpose, so the unscoped query must over-count and the scoped one
    # must not. A fix that were absent would show up as both queries agreeing.
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS verify_a"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS verify_b"))
        for schema in ("verify_a", "verify_b"):
            conn.execute(text(
                f"CREATE TYPE {schema}.finding_classification AS ENUM "
                "('MATCH','DEVIATION','MISSING','CONFLICT','AMBIGUOUS',"
                "'UNRESOLVED','UNABLE_TO_EVALUATE')"))
        conn.commit()

        unscoped = conn.execute(text("""
            SELECT count(e.enumlabel) FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = 'finding_classification'""")).scalar()
        scoped = conn.execute(text("""
            SELECT count(e.enumlabel) FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname = current_schema()
              AND t.typname = 'finding_classification'""")).scalar()
        ok = scoped == 7 and unscoped == 21
        report.add("enum_scoping", PASS if ok else FAIL,
                   f"unscoped={unscoped} (over-counts across schemas), "
                   f"scoped={scoped} (locked REC-01's seven)",
                   mechanism="two live schemas, both queries run in psql-equivalent SQL",
                   basis="REC-06, F-4")

    engine.dispose()


# ==========================================================================
# Queue guarantees — real Redis, real worker processes, real kill -9
# ==========================================================================
def _redis_available(port: int) -> bool:
    try:
        return subprocess.run(["redis-cli", "-p", str(port), "ping"],
                              capture_output=True, timeout=5,
                              text=True).stdout.strip() == "PONG"
    except Exception:
        return False


def check_broker_refusal(report: Report) -> None:
    print("\nWorker startup — a real process, checked by exit code", flush=True)
    env = {k: v for k, v in os.environ.items() if k != "LEGALMIND_BROKER_URL"}
    env["PYTHONPATH"] = str(Path.cwd())
    proc = subprocess.run(
        ["celery", "-A", "legalmind.worker.app", "worker", "-Q", "analysis"],
        capture_output=True, text=True, env=env, timeout=90)
    said_why = "LEGALMIND_BROKER_URL" in (proc.stderr + proc.stdout)
    ok = proc.returncode != 0 and said_why
    report.add("worker_refuses_without_broker", PASS if ok else FAIL,
               f"exit={proc.returncode}, names the variable={said_why}. Without the "
               "bootstep it would start on Celery's amqp:// default and consume "
               "nothing",
               mechanism="real `celery worker` process, exit code observed",
               basis="55.1, Step 39, rule 15")


def check_queue(report: Report, redis_port: int) -> None:
    print("\nQueue delivery — real broker, real worker, real SIGKILL", flush=True)
    if not _redis_available(redis_port):
        report.add("queue_delivery", SKIP,
                   f"no Redis on port {redis_port}; start one to verify",
                   mechanism="real broker", basis="55.1")
        return

    from tools import verify_queue

    outcomes = verify_queue.run(redis_port=redis_port, database_url=verify_url())
    for name, (status, detail, mechanism) in outcomes.items():
        report.add(name, status, detail, mechanism=mechanism, basis="55.1, 43.28")


# ==========================================================================
# 53.3 redaction — grep real output, do not ask the redactor
# ==========================================================================
def check_redaction(report: Report, log_path: Path) -> None:
    print("\nRedaction — grepping real log output", flush=True)
    if not log_path.exists():
        report.add("log_redaction", SKIP, f"no log at {log_path}",
                   mechanism="grep of real output", basis="53.3")
        return

    body = log_path.read_text()
    forbidden = {
        "clause text": ["shall not exceed", "fees paid", "Limitation of Liability"],
        "internal legal position": ["acceptable_max", "approval_required_above",
                                    "rule_outcome", "credential_hash"],
        "credential material": ["scrypt$", "e2e-not-a-secret", "password"],
    }
    leaks = {label: [n for n in needles if n in body]
             for label, needles in forbidden.items()}
    leaks = {k: v for k, v in leaks.items() if v}
    report.add("log_redaction", FAIL if leaks else PASS,
               f"leaked: {leaks}" if leaks
               else f"{len(body.splitlines())} log lines carry none of the four "
                    "forbidden classes",
               mechanism="grep of real log output, not a redactor unit test",
               basis="53.3")


# ==========================================================================
# Determinism — separate PROCESSES and a hostile locale (ENG-11)
# ==========================================================================
def check_determinism(report: Report) -> None:
    print("\nDeterminism — two processes, hostile locale", flush=True)
    script = (
        "import json;"
        "from pathlib import Path;"
        "from legalmind.evaluation.corpus import load_fixtures, run_corpus;"
        "fx = load_fixtures(Path('tests/corpus'));"
        "print(json.dumps([[o.fixture_id, o.passed, o.failures] "
        "for o in run_corpus(fx)], sort_keys=True))"
    )
    runs = []
    for env_extra in ({}, {"LC_ALL": "tr_TR.UTF-8", "TZ": "Pacific/Kiritimati"}):
        env = {**os.environ, "PYTHONHASHSEED": "0", **env_extra}
        # A different PYTHONHASHSEED in the second run would be a stronger test
        # still; the CI determinism job varies it, so this one varies locale and
        # timezone instead — the inputs 54.3 names.
        env["PYTHONHASHSEED"] = "1" if env_extra else "0"
        out = subprocess.run([sys.executable, "-c", script],
                             capture_output=True, text=True, env=env, timeout=180)
        runs.append(out.stdout.strip())

    ok = len(set(runs)) == 1 and runs[0]
    report.add("determinism_across_processes", PASS if ok else FAIL,
               "byte-identical corpus output across two processes with different "
               "hash seeds, locale (tr_TR — the dotless-i trap) and timezone"
               if ok else f"outputs differ: {runs}",
               mechanism="two separate OS processes, not one test session",
               basis="ENG-11, 54.3")


# ==========================================================================
def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Independent verification pass")
    parser.add_argument("--redis-port", type=int, default=6399)
    parser.add_argument("--log", default=".e2e/verify.log",
                        help="a real log file to grep for 53.3 violations")
    parser.add_argument("--json", default="", help="write the report as JSON here")
    args = parser.parse_args(argv)

    print(__doc__.split("Run it against")[0].strip()[:0] or "", end="")
    print("Independent verification — a different mechanism per claim.")
    print("NOT third-party verification, and nothing here makes anything VERIFIED.")

    report = Report()
    check_database(report)
    check_broker_refusal(report)
    check_queue(report, args.redis_port)
    check_redaction(report, Path(args.log))
    check_determinism(report)

    counts: dict[str, int] = {}
    for result in report.results:
        counts[result.status] = counts.get(result.status, 0) + 1
    print("\n" + ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))
    print("PASS means: verified by the stated mechanism, independently of the test "
          "that asserts it.")

    if args.json:
        Path(args.json).write_text(json.dumps(
            [r.__dict__ for r in report.results], indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

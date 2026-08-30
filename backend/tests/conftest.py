from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from legalmind.config import test_database_url
from legalmind.db import models as M
from legalmind.domain import enums as E

# --------------------------------------------------------------------------
# `F-4` — test isolation
# --------------------------------------------------------------------------
# Schemas are named `t_<epoch-seconds>_<random>`. The timestamp is not decoration:
# it is what lets a later run sweep debris left by a crashed one without any risk
# of touching a live run's schema (see `_sweep_stale_schemas`).
_SCHEMA_PREFIX = "t_"
# A run older than this cannot still be executing — the whole suite takes ~20s.
_STALE_AFTER_SECONDS = 6 * 60 * 60


def _sweep_stale_schemas(admin) -> None:
    """Drop schemas abandoned by crashed runs, and only those.

    A run killed mid-suite leaves its schema behind. Without a sweep those
    accumulate indefinitely, which is how a harness becomes un-robust over time.
    Age is read from the schema name rather than from catalogue metadata, so the
    decision is explicit and a live run — seconds old — is never a candidate.
    """
    cutoff = int(time.time()) - _STALE_AFTER_SECONDS
    names = admin.execute(text(
        "SELECT nspname FROM pg_namespace WHERE nspname LIKE :p"
    ), {"p": f"{_SCHEMA_PREFIX}%"}).scalars().all()
    # `AM-27` r1 gives each run a second schema, `<run>_assist`, so a name now has
    # three parts or four. Sorted longest-first so `<run>_assist` is dropped before
    # `<run>`: its foreign keys point into the locked schema, and Postgres refuses to
    # drop a schema another still depends on.
    for name in sorted(names, key=len, reverse=True):
        parts = name.split("_")
        if len(parts) == 4 and parts[3] != "assist":
            continue                     # not ours; leave it alone
        if len(parts) not in (3, 4) or not parts[1].isdigit():
            continue                     # not ours; leave it alone
        if int(parts[1]) < cutoff:
            admin.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


@pytest.fixture(scope="session")
def engine():
    """Build the test schema by running the REAL Alembic migration, into a
    schema private to this test process.

    Tests must exercise what ships. Using ``metadata.create_all()`` here would
    bypass the hand-written trigger DDL (EV-MIN, append-only) and silently stop
    testing the invariants that matter most.

    **Why a private schema — `F-4`.** Earlier revisions shared ``public`` and reset
    it with ``DROP SCHEMA public CASCADE``. That made the suite non-deterministic in
    two ways, the second caused by the fix for the first:

    * a backend left by an interrupted run held locks, so the DROP raced and
      occasionally left a half-built schema — runs reported 0, 2, 3 and 62 errors
      from identical input;
    * adding ``pg_terminate_backend`` to clear those locks then killed the *live*
      connections of any concurrently running suite, surfacing as
      ``SSL connection has been closed unexpectedly`` in whichever process lost.

    Both disappear once no process touches another's objects. Each run creates
    ``t_<epoch>_<random>``, points ``search_path`` at it for its own connections and
    for Alembic's, and drops only that schema at teardown. Nothing is terminated, so
    two suites — or an xdist worker pool — can share one database safely.

    Note this also means the diagnosis originally recorded for `F-4` (a module-global
    engine in ``api/deps.py`` pointed at the *dev* database) is **not** the
    mechanism. Verified by running the suite green with ``LEGALMIND_DATABASE_URL``
    pointed at a nonexistent host: nothing in the test path opens the dev database.
    """
    from alembic.config import Config

    from alembic import command

    base_url = test_database_url()
    schema = f"{_SCHEMA_PREFIX}{int(time.time())}_{uuid.uuid4().hex[:10]}"
    # psycopg2 accepts libpq `options` in the DSN, which is how Alembic's own engine
    # — built inside env.py from this URL — lands in the same schema.
    scoped_url = f"{base_url}?options=-csearch_path%3D{schema}"

    # `AM-27` r1 puts the assist tables in a schema separate from the locked ones.
    # Derived per run rather than the production default, for the same reason the
    # locked schema is: a hardcoded `assist` would be shared by every concurrent
    # suite, and `F-4` is the record of what that costs. Set before Alembic runs,
    # because the migration reads it through `config.assist_schema()`.
    #
    # Restored in teardown rather than left set: the variable is process-global, and
    # leaking it would silently repoint a later run in the same process.
    assist_schema = f"{schema}_assist"
    previous_assist_schema = os.environ.get("LEGALMIND_ASSIST_SCHEMA")
    os.environ["LEGALMIND_ASSIST_SCHEMA"] = assist_schema

    admin_engine = create_engine(base_url, future=True)
    with admin_engine.begin() as c:
        _sweep_stale_schemas(c)
        c.execute(text(f'CREATE SCHEMA "{schema}"'))

    # A container-fresh test database (every CI job) has no pgvector, and the
    # c4a91 migration refuses to create it — a deployment precondition there, a
    # harness's own job here. Best-effort: succeeds where the role is superuser
    # (CI's service image), no-ops where the extension already exists (local),
    # and the migration's own error follows where neither holds.
    from tools.pg_extensions import ensure_vector_extension
    ensure_vector_extension(base_url)

    cfg = Config("alembic.ini")
    # Alembic reads options through configparser, which treats `%` as
    # interpolation — the percent-encoded `=` has to be escaped for it.
    cfg.set_main_option("sqlalchemy.url", scoped_url.replace("%", "%%"))
    command.upgrade(cfg, "head")

    eng = create_engine(scoped_url, future=True)
    try:
        yield eng
    finally:
        # Teardown runs even on a keyboard interrupt or a collection error, so the
        # ordinary exit path does not itself become a source of debris.
        eng.dispose()
        with admin_engine.begin() as c:
            # The assist schema first: its foreign keys point INTO the locked schema,
            # so dropping the locked one first would fail on the dependency.
            c.execute(text(f'DROP SCHEMA IF EXISTS "{assist_schema}" CASCADE'))
            c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
        if previous_assist_schema is None:
            os.environ.pop("LEGALMIND_ASSIST_SCHEMA", None)
        else:
            os.environ["LEGALMIND_ASSIST_SCHEMA"] = previous_assist_schema


@pytest.fixture
def db(engine) -> Session:
    """Each test runs in its own transaction and is rolled back."""
    conn = engine.connect()
    tx = conn.begin()
    s = sessionmaker(bind=conn, future=True)()
    yield s
    s.close()
    if tx.is_active:
        tx.rollback()
    conn.close()


# ---------------------------------------------------------------- fixtures
def _now():
    return datetime.now(UTC)


@pytest.fixture
def user(db):
    u = M.User(email=f"u{uuid.uuid4().hex[:8]}@example.test", name="Test User",
               status=E.UserStatus.ACTIVE)
    db.add(u); db.flush()
    return u


@pytest.fixture
def review(db, user):
    contract = M.Contract(owner_id=user.id, name="ACME MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    dv = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="msa.pdf",
        mime_type="application/pdf", file_size_bytes=1234, file_hash="abc",
        storage_key="s3://k", processing_status=E.ProcessingStatus.COMPLETED,
        uploaded_by=user.id)
    db.add(dv); db.flush()
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id)
    db.add(snap); db.flush()
    r = M.Review(contract_id=contract.id, document_version_id=dv.id,
                 configuration_snapshot_id=snap.id,
                 status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=user.id)
    db.add(r); db.flush()
    r._document_version = dv
    return r


@pytest.fixture
def requirement_version(db, user):
    req = M.Requirement(code=f"LIABILITY-{uuid.uuid4().hex[:4]}",
                        status=E.ConfigStatus.ACTIVE)
    db.add(req); db.flush()
    rv = M.RequirementVersion(
        requirement_id=req.id, version_number=1, name="Limitation of Liability",
        evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON, created_by=user.id)
    db.add(rv); db.flush()
    return rv


def make_finding(db, review, rv, classification=E.FindingClassification.DEVIATION,
                 status=E.FindingStatus.DECISION_REQUIRED):
    f = M.Finding(review_id=review.id, requirement_version_id=rv.id,
                  classification=classification, status=status)
    db.add(f); db.flush()
    return f


def make_evaluation(db, finding, *, scope_key="AGGREGATE",
                    kind=E.EvaluationKind.PRIMARY,
                    classification=E.FindingClassification.DEVIATION,
                    rule_outcome=E.RuleOutcome.ACCEPTABLE):
    ev = M.Evaluation(
        finding_id=finding.id, evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
        evaluator_version="LIABILITY-EVALUATOR-v1", scope_key=scope_key,
        evaluation_kind=kind, classification=classification,
        rule_outcome=rule_outcome, result={"diagnostics": []})
    db.add(ev); db.flush()
    return ev


# ------------------------------------------------------- security fixtures
@pytest.fixture
def seeded(db):
    """Permission catalogue + canonical roles + Step 23 default grants."""
    from legalmind.security.seed import bootstrap
    bootstrap(db)
    return True


def make_user(db, email=None, status=E.UserStatus.ACTIVE):
    u = M.User(email=email or f"u{uuid.uuid4().hex[:10]}@example.test",
               name="Test User", status=status)
    db.add(u); db.flush()
    return u


def grant_role(db, user, role_code):
    from sqlalchemy import select
    role = db.execute(select(M.Role).where(M.Role.code == role_code)).scalar_one()
    db.add(M.UserRole(user_id=user.id, role_id=role.id))
    db.flush()
    return role


# ------------------------------------------------------------ API harness
@pytest.fixture
def api(db, tmp_path):
    """A TestClient wired to the test transaction.

    ``get_db`` is overridden so the whole request runs inside the test's
    transaction and is rolled back with it. One consequence to keep in mind: the
    deferred EV-MIN trigger fires at real COMMIT only, so it is exercised by
    ``test_schema_invariants``, not here.

    ``base_url`` is https because the session cookie is ``Secure`` (S-3) and would
    not be sent over http — the harness must not quietly weaken a locked control.
    """
    from fastapi.testclient import TestClient

    from legalmind.api import ratelimit
    from legalmind.api import storage as api_storage
    from legalmind.api.app import create_app
    from legalmind.api.deps import get_db
    from legalmind.api.routers import auth as auth_router
    from legalmind.api.routers import reviews as reviews_router
    from legalmind.ingestion.storage import LocalFilesystemStorage

    def request_scoped_db():
        """Mirrors the real ``get_db``: commit on success, roll back on failure.

        A plain ``lambda: db`` would silently skip locked 43.26's transaction
        boundary, so a handler that raised *after* a write would leave the write
        visible and the test would pass for the wrong reason. The session is bound
        to a connection already inside a transaction, so SQLAlchemy's
        ``conditional_savepoint`` mode makes each commit a savepoint release and
        the outer test transaction still rolls everything back at teardown.
        """
        savepoint = db.begin_nested()
        try:
            yield db
            if savepoint.is_active:
                savepoint.commit()
        except Exception:
            if savepoint.is_active:
                savepoint.rollback()
            raise

    app = create_app()
    app.dependency_overrides[get_db] = request_scoped_db
    api_storage.set_storage(LocalFilesystemStorage(tmp_path / "objects"))
    # Fresh limiters per test. A shared window would leak across tests and make the
    # suite order-dependent — the class of non-determinism F-4 is about.
    auth_router.limiter = ratelimit.InProcessRateLimiter()
    reviews_router._limiter = ratelimit.InProcessRateLimiter()

    # TestClient runs the ASGI app on its own portal thread. The overridden
    # get_db hands that thread the *test's* Session, which is bound to a
    # connection the main thread also uses. Leaving the client open lets the
    # portal outlive the test, so a later test can find the connection torn
    # down mid-statement ("SSL connection has been closed unexpectedly").
    # Closing the client joins the portal thread before the db fixture
    # rolls back and closes the connection.
    client = TestClient(app, base_url="https://testserver")
    client.app_instance = app
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
        api_storage.set_storage(None)


def sign_in(api, db, user):
    """Establish a real server-side session and present it like a browser would.

    Deliberately does NOT go through ``POST /auth/login``: most tests are about
    authorization, and making every one of them depend on the password fallback
    would couple them to a mechanism locked 47.1.3 treats as secondary.
    """
    from legalmind.api.context import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
    from legalmind.security.sessions import create_session

    session = create_session(db, user)
    token = "test-csrf-token"
    # domain="" so cookielib treats these as host-agnostic; a bare hostname like
    # "testserver" is not a domain it will match against.
    api.cookies.set(SESSION_COOKIE, str(session.id))
    api.cookies.set(CSRF_COOKIE, token)
    api.headers[CSRF_HEADER] = token
    return session


def sign_out(api):
    api.cookies.clear()
    api.headers.pop("X-CSRF-Token", None)


def bespoke_role(db, code, permissions):
    """A role granting exactly the named permissions.

    Needed because the seeded roles bundle grants the way Step 23 describes them;
    isolating one permission is the only way to test that a boundary holds on its
    own rather than because a bundle happened to exclude it.
    """
    from sqlalchemy import select

    role = M.Role(code=code, name=code.title())
    db.add(role); db.flush()
    for name in permissions:
        pid = db.execute(
            select(M.Permission.id).where(M.Permission.name == name)
        ).scalar_one()
        db.add(M.RolePermission(role_id=role.id, permission_id=pid))
    db.flush()
    return role


def grant(db, user, role):
    db.add(M.UserRole(user_id=user.id, role_id=role.id))
    db.flush()


def make_review_for(db, owner):
    contract = M.Contract(owner_id=owner.id, name="ACME MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    dv = M.DocumentVersion(
        contract_id=contract.id, version_number=1, original_filename="msa.pdf",
        mime_type="application/pdf", file_size_bytes=10, file_hash="h",
        storage_key="k", processing_status=E.ProcessingStatus.COMPLETED,
        uploaded_by=owner.id)
    db.add(dv); db.flush()
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id)
    db.add(snap); db.flush()
    r = M.Review(contract_id=contract.id, document_version_id=dv.id,
                 configuration_snapshot_id=snap.id,
                 status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=owner.id)
    db.add(r); db.flush()
    return r

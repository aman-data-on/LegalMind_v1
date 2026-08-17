from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from legalmind.config import test_database_url
from legalmind.db.base import Base
from legalmind.db import models as M
from legalmind.domain import enums as E


@pytest.fixture(scope="session")
def engine():
    """Build the test schema by running the REAL Alembic migration.

    Tests must exercise what ships. Using metadata.create_all() here would
    bypass the hand-written trigger DDL (EV-MIN, append-only) and silently
    stop testing the invariants that matter most.
    """
    from alembic import command
    from alembic.config import Config

    url = test_database_url()
    eng = create_engine(url, future=True)
    with eng.begin() as c:
        # A leftover backend from an interrupted run holds locks on these tables,
        # which made the DROP below race and occasionally leave the schema
        # half-built. Scoped to THIS database by current_database(), so a stray
        # connection to another LegalMind database is never touched.
        c.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"))
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    yield eng
    eng.dispose()


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
    return datetime.now(timezone.utc)


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

    from legalmind.api import ratelimit, storage as api_storage
    from legalmind.api.app import create_app
    from legalmind.api.deps import get_db
    from legalmind.api.routers import auth as auth_router
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
    auth_router.limiter = ratelimit.InProcessRateLimiter()   # fresh per test

    client = TestClient(app, base_url="https://testserver")
    client.app_instance = app
    yield client
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

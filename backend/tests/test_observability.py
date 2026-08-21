"""Observability — locked Step 53.

The important tests here are **negative**. Locked 53.3 is a prohibition, and the way
a prohibition fails is by something forbidden appearing, not by something expected
being absent. So most of this file asserts that credentials, contract text, internal
legal position and account identifiers cannot reach a log line even when a caller
hands them over directly.

The second theme is locked 53.4/53.5's rule that a fail-closed outcome is **not** an
error. Getting that backwards is the most damaging observability mistake available
here: an operator who alerts on `UNABLE_TO_EVALUATE` will pressure the engine toward
guessing, and 53.5 warns that a falling fail-closed rate "may mean guessing, not
improvement".
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from legalmind.domain.enums import FindingClassification, ReviewStatus
from legalmind.observability import log_event, log_exception, redact_fields
from legalmind.observability import logs as logs_module
from legalmind.observability.logs import (
    LOGGER_NAME,
    JsonFormatter,
    configure_logging,
    timed,
)
from legalmind.observability.metrics import (
    ALERTABLE_SIGNALS,
    ANALYSIS_SIGNALS,
    FAIL_CLOSED_CLASSIFICATIONS,
    classification_signal,
    fail_closed_rate,
    is_operational_failure,
)
from legalmind.observability.redaction import MAX_VALUE_LENGTH

V1 = "/api/v1"


@pytest.fixture
def captured(monkeypatch):
    """Capture emitted log lines as parsed JSON.

    Substitutes the module's logger rather than swapping handlers on the shared
    ``legalmind`` logger: pytest's logging plugin manages that logger's handlers for
    its own capture, so a fixture that reassigns them is silently undone and the test
    sees nothing. Patching the module attribute is deterministic and independent of
    the framework — `configure_logging` itself is covered separately below.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    probe = logging.getLogger(f"{LOGGER_NAME}.capture-probe")
    probe.handlers = [handler]
    probe.setLevel(logging.DEBUG)
    probe.propagate = False
    # Asserted rather than assumed: `logging.config.fileConfig` disables every
    # pre-existing logger unless told otherwise, and Alembic calls it. `alembic/env.py`
    # now passes `disable_existing_loggers=False`, and this line keeps the fixture
    # honest if anything else ever disables it.
    probe.disabled = False
    monkeypatch.setattr(logs_module, "_logger", probe)

    def read():
        handler.flush()
        return [json.loads(line) for line in stream.getvalue().splitlines() if line]

    return read


# =====================================================================
# 53.3 — what must never be logged
# =====================================================================
def test_credential_material_never_reaches_a_log_line(captured):
    """S-4 — credentials, hashes, session identifiers, tokens, codes."""
    log_event(
        "auth.attempt",
        password="correct horse battery staple",
        credential_hash="scrypt$16384$8$1$abc$def",
        session_id="8f14e45f-ea1a-4f6b-9c2e-000000000001",
        access_token="eyJhbGciOiJIUzI1NiJ9.payload.signature",
        authorization_code="4/0AY0e-g7",
        client_secret="s3cr3t",
        cookie="legalmind_session=abc",
        csrf_token="tok",
        user_id="ok-to-log",
    )
    line = captured()[0]
    raw = json.dumps(line)
    for forbidden in ("correct horse", "scrypt$", "eyJhbGciOi", "4/0AY0e-g7",
                      "s3cr3t", "legalmind_session=abc", "tok"):
        assert forbidden not in raw
    for key in ("password", "credential_hash", "session_id", "access_token",
                "authorization_code", "client_secret", "cookie", "csrf_token"):
        assert key not in line
    # The identifier survives — 53.3: "log records carry identifiers, not content".
    assert line["user_id"] == "ok-to-log"


def test_contract_text_never_reaches_a_log_line(captured):
    """53.3 — "evidence lives in the document store, not in logs"."""
    clause = ("Aggregate liability shall not exceed an amount equal to twelve "
              "months of fees paid under this Agreement.")
    log_event("analysis.stage", content=clause, clause_text=clause,
              original_content=clause, evidence_id="ev-1")
    line = captured()[0]
    raw = json.dumps(line)
    assert "Aggregate liability" not in raw
    assert "twelve months" not in raw
    for key in ("content", "clause_text", "original_content"):
        assert key not in line
    assert line["evidence_id"] == "ev-1"


def test_internal_legal_position_never_reaches_a_log_line(captured):
    """LEGAL-02 / 53.3 — thresholds, rule outcomes, rule_configuration."""
    log_event("evaluation.done", rule_outcome="UNACCEPTABLE",
              expected_value={"months": 6}, comparison="3 < 6",
              explanation=["Standard requires >= 6 months"],
              rule_configuration={"scope_required": True},
              threshold=12, acceptable_max=12,
              classification="DEVIATION", evaluation_id="ev-9")
    line = captured()[0]
    raw = json.dumps(line)
    assert "UNACCEPTABLE" not in raw
    assert "3 < 6" not in raw
    assert "Standard requires" not in raw
    for key in ("rule_outcome", "expected_value", "comparison", "explanation",
                "rule_configuration", "threshold", "acceptable_max"):
        assert key not in line
    # Classification is not an internal legal position — 49.7 returns it ungated.
    assert line["classification"] == "DEVIATION"
    assert line["evaluation_id"] == "ev-9"


def test_account_identifiers_never_reach_a_log_line(captured):
    """S-7 — an email in a log line is the enumeration oracle 53.3 forbids.

    Dropped on every path, not only the failure path: a log pipeline is searchable
    and both paths land in the same index.
    """
    log_event("auth.login_failed", email="victim@example.test",
              username="victim", actor_id="uuid-ok")
    line = captured()[0]
    assert "victim" not in json.dumps(line)
    assert "email" not in line and "username" not in line
    assert line["actor_id"] == "uuid-ok"


def test_a_forbidden_key_is_dropped_not_marked(captured):
    """A marker would itself be a disclosure.

    `rule_outcome=[redacted]` still tells a reader that an internal legal position
    exists for this object — the same reasoning as 49.7 r4's omit-don't-null.
    """
    log_event("evaluation.done", rule_outcome="UNACCEPTABLE")
    line = captured()[0]
    assert "rule_outcome" not in line
    assert "redacted" not in json.dumps(line)


def test_long_values_are_treated_as_content_whatever_they_are_called(captured):
    """53.3's design rule: "log records carry identifiers, not content."

    An identifier is short. A long value is content by definition, so the guard is
    length-based and does not depend on guessing what a field holds.
    """
    log_event("x", innocuous_looking_field="A" * (MAX_VALUE_LENGTH + 50))
    line = captured()[0]
    assert "AAAA" not in json.dumps(line)
    assert "chars omitted" in line["innocuous_looking_field"]


def test_redaction_reaches_into_nested_structures():
    safe = redact_fields({
        "outer": {"password": "x", "user_id": "keep",
                  "inner": {"credential_hash": "scrypt$1$2$3$a$b", "id": "keep2"}},
        "list_of_ids": ["a", "b"],
    })
    assert safe == {"outer": {"user_id": "keep", "inner": {"id": "keep2"}},
                   "list_of_ids": ["a", "b"]}


def test_secret_shaped_values_are_caught_regardless_of_key():
    """Defence in depth: a hash or JWT under an innocent key is still a secret."""
    safe = redact_fields({"note": "scrypt$16384$8$1$aa$bb",
                          "other": "eyJhbGciOiJIUzI1NiJ9.abc",
                          "pem": "-----BEGIN PRIVATE KEY-----"})
    assert all(v == "[redacted]" for v in safe.values())


def test_key_variants_are_caught():
    """`user_password`, `oidc_id_token`, `raw_content` must not slip through on a
    naming technicality."""
    safe = redact_fields({"user_password": "x", "oidc_id_token": "y",
                          "raw_content": "z", "Session-Id": "s",
                          "password_hash": "h", "keep": "k"})
    assert safe == {"keep": "k"}


def test_redaction_is_not_over_broad(captured):
    """Over-broad redaction is its own failure mode.

    An earlier version matched a forbidden name as a *prefix* of any key, which
    dropped `clause_count` — a count, not content. That silently removes the
    operational signal 53.5 asks for, and a log pipeline missing its counts is no more
    useful than one leaking content. These are the fields the analysis stages actually
    emit; every one must survive.
    """
    log_event("analysis.stage.load", clause_count=3, requirement_count=2,
              evidence_count=7, content_length=1024, findings_created=1,
              classification_counts={"MATCH": 2}, fail_closed_rate=0.25,
              duration_ms=12.5, evaluator_version="NUMERIC-COMPARISON-v1",
              mapping_state="CONFIRMED", scope_key="GENERAL",
              requirement_code="LIABILITY-001", error_code="UPLOAD_REJECTED",
              reason_code="no_extracted_clauses", review_status="LEGAL_REVIEW",
              operational_failure=False)
    line = captured()[0]
    for key, value in [("clause_count", 3), ("requirement_count", 2),
                       ("evidence_count", 7), ("content_length", 1024),
                       ("findings_created", 1), ("fail_closed_rate", 0.25),
                       ("duration_ms", 12.5),
                       ("evaluator_version", "NUMERIC-COMPARISON-v1"),
                       ("mapping_state", "CONFIRMED"), ("scope_key", "GENERAL"),
                       ("requirement_code", "LIABILITY-001"),
                       ("error_code", "UPLOAD_REJECTED"),
                       ("reason_code", "no_extracted_clauses"),
                       ("review_status", "LEGAL_REVIEW"),
                       ("operational_failure", False)]:
        assert line[key] == value, key
    assert line["classification_counts"] == {"MATCH": 2}


def test_oidc_parameters_and_audit_payloads_are_still_caught(captured):
    """The exact-only exemption must not open a hole.

    `state`, `code` and `nonce` stop being suffix-matched so that `mapping_state` and
    `requirement_code` survive — so the OIDC forms and the audit payloads are denied
    by exact name instead.
    """
    log_event("auth.callback", state="csrf-nonce-value", code="4/0AY0e-g7",
              nonce="n-1", before_state={"status": "OPEN"},
              after_state={"decision_type": "ACCEPT_DEVIATION"},
              request_id="keep")
    line = captured()[0]
    raw = json.dumps(line)
    for key in ("state", "code", "nonce", "before_state", "after_state"):
        assert key not in line, key
    assert "ACCEPT_DEVIATION" not in raw
    assert "4/0AY0e-g7" not in raw
    assert line["request_id"] == "keep"


# =====================================================================
# 53.4 — two audiences, never crossed
# =====================================================================
def test_operator_facing_detail_stays_in_the_log(captured):
    """53.4 — the stack goes to the log pipeline only; the API response carries a
    stable code, a safe message and the request id.

    The trace is rendered as **structure** rather than as a formatted blob, because
    53.3 applies to it too — see `test_a_database_error_does_not_log_clause_text`.
    """
    try:
        raise RuntimeError("connection reset while writing")
    except RuntimeError:
        log_exception("http.request_failed", request_id="req-1", route="/api/v1/x")

    line = captured()[0]
    assert line["level"] == "ERROR"
    assert line["request_id"] == "req-1"
    # Where it failed, in frames an operator can open.
    assert line["exception_type"] == "RuntimeError"
    assert any("test_observability.py" in frame for frame in line["exception_frames"])
    # And what failed — a short diagnosis survives intact.
    assert line["exception_chain"][0] == {
        "type": "RuntimeError", "message": "connection reset while writing"}


def test_a_database_error_does_not_log_clause_text(captured):
    """53.3 versus 53.4, in the one place they meet.

    A driver embeds the failing statement, the offending row and the bound parameters
    in its message, so a database error while writing `document_evidence` would put
    contract text into an operational log line. That was confirmed against a real
    `IntegrityError` before this guard existed — and it reached the log through the
    only path that skipped `redact_fields`, because `exc_info` was formatted by the
    handler rather than redacted.

    Both rules are satisfied rather than traded off: the frames and the exception type
    are identifiers and survive; the message is a value and is cut at the payload
    marker, then length-guarded like every other logged value.
    """
    clause = "Liability shall not exceed 24 months of fees paid."
    inner = Exception(
        'null value in column "id" violates not-null constraint\n'
        f"DETAIL:  Failing row contains (null, '{clause}').")
    try:
        raise RuntimeError(
            f"(psycopg2.errors.NotNullViolation) {inner}\n"
            f"[SQL: INSERT INTO document_evidence (clause_text) VALUES (%(t)s)]\n"
            f"[parameters: {{'t': '{clause}'}}]") from inner
    except RuntimeError:
        log_exception("db.write_failed", request_id="req-2")

    line = captured()[0]
    blob = json.dumps(line)
    assert clause not in blob
    assert "parameters" not in blob
    # The diagnosis is kept: an operator still learns which constraint failed.
    assert "not-null constraint" in line["exception_chain"][0]["message"]
    assert "[payload omitted]" in line["exception_chain"][0]["message"]


def test_the_exception_chain_is_bounded(captured):
    """A cause chain is walked, not followed indefinitely — a cyclic or very deep
    chain must not turn one failure into an unbounded log line."""
    from legalmind.observability.logs import MAX_CAUSES

    exc: BaseException = ValueError("root")
    for depth in range(6):
        exc = RuntimeError(f"layer {depth}").with_traceback(None)
        exc.__cause__ = ValueError("root")
    try:
        raise exc
    except RuntimeError:
        log_exception("deep.failure", request_id="req-3")

    assert len(captured()[0]["exception_chain"]) <= MAX_CAUSES


def test_request_id_is_the_join_key(captured):
    """53.2 — the same id appears on the log line, in audit metadata and on the
    Evaluations a request produced. Here: the log side."""
    log_event("analysis.completed", request_id="corr-7", review_id="r-1")
    assert captured()[0]["request_id"] == "corr-7"


def test_timed_reports_a_duration_and_lets_the_stage_add_counts(captured):
    """53.5 — pipeline stage durations."""
    with timed("analysis.stage.load", request_id="corr-8") as stage:
        stage["clause_count"] = 3
    line = captured()[0]
    assert line["event"] == "analysis.stage.load"
    assert isinstance(line["duration_ms"], (int, float))
    assert line["clause_count"] == 3


def test_the_logging_api_offers_no_raw_string_payload():
    """There is deliberately no way to log an arbitrary formatted string.

    `log_event` takes an event name plus keyword fields, so a caller cannot smuggle
    clause text through an f-string. That closes the gap 53.3 would otherwise leave
    to caller discipline.
    """
    import inspect
    params = inspect.signature(log_event).parameters
    assert next(iter(params)) == "event"
    assert params["event"].annotation == "str"
    # Everything else arrives as keywords and is redacted.
    assert any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


# =====================================================================
# 53.4 / 53.5 — a fail-closed outcome is NOT an error
# =====================================================================
@pytest.mark.parametrize("classification", sorted(
    FAIL_CLOSED_CLASSIFICATIONS, key=lambda c: c.value))
def test_fail_closed_classifications_are_never_operational_failures(classification):
    """53.5 — "Do not alert on UNABLE_TO_EVALUATE — it is the system working as
    locked." The same holds for every Tier-1 classification: each is the engine
    declining to guess, which 45B/45C/Step 28 r6 require of it."""
    assert is_operational_failure(classification=classification) is False


def test_no_classification_at_all_is_an_operational_failure():
    for classification in FindingClassification:
        assert is_operational_failure(classification=classification) is False


def test_analysis_failed_is_an_operational_failure():
    """53.4 / Step 30 r13 — ANALYSIS_FAILED means the run could not complete, so no
    legal conclusion was reached. Genuinely alertable, and never the same thing as a
    Finding of UNABLE_TO_EVALUATE."""
    assert is_operational_failure(review_status=ReviewStatus.ANALYSIS_FAILED) is True
    for status in (ReviewStatus.LEGAL_REVIEW, ReviewStatus.RESOLVED,
                   ReviewStatus.ANALYSIS_COMPLETE):
        assert is_operational_failure(review_status=status) is False


def test_the_fail_closed_set_is_exactly_tier_1():
    """Derived from the roll-up rather than restated, so the two cannot drift."""
    assert {c.value for c in FAIL_CLOSED_CLASSIFICATIONS} == {
        "UNABLE_TO_EVALUATE", "CONFLICT", "AMBIGUOUS", "UNRESOLVED"}


def test_fail_closed_rate_is_reported_not_targeted():
    counts = {FindingClassification.MATCH: 3,
              FindingClassification.UNABLE_TO_EVALUATE: 1}
    assert fail_closed_rate(counts) == 0.25
    assert fail_closed_rate({}) is None


def test_classification_routes_to_the_right_signal():
    assert classification_signal(FindingClassification.UNABLE_TO_EVALUATE) == \
        "analysis.fail_closed_rate"
    assert classification_signal(FindingClassification.MATCH) == \
        "analysis.classification_count"


def test_the_fail_closed_rate_is_not_alertable():
    """The single most important line in this file.

    53.5 lists what to alert on and the fail-closed rate is deliberately absent. An
    alert on it would push the engine toward guessing — the opposite of what every
    fail-closed rule in the specification exists to achieve.
    """
    assert "analysis.fail_closed_rate" in ANALYSIS_SIGNALS
    assert "analysis.fail_closed_rate" not in ALERTABLE_SIGNALS
    assert "analysis.classification_count" not in ALERTABLE_SIGNALS
    # What IS alertable, per 53.5's "Alert on" list.
    assert {
        "analysis.review_failed_rate", "auth.failure_count",
        "authz.denial_count", "analysis.stage_duration_ms"} == ALERTABLE_SIGNALS


# =====================================================================
# 53.1 — no log line is load-bearing
# =====================================================================
def test_logging_never_writes_an_audit_event():
    """53.1 — "an operational log is never a substitute for an audit event", and
    "losing logs must never lose legal history". Asserted structurally: the
    observability package must not import the audit writer or the models."""
    from pathlib import Path

    package = Path(__file__).resolve().parents[1] / "legalmind" / "observability"
    for module in package.glob("*.py"):
        source = module.read_text()
        assert "security.audit" not in source, module.name
        assert "db import models" not in source, module.name
        assert "db.models" not in source, module.name


# =====================================================================
# The global wiring, covered separately from field handling
# =====================================================================
def test_configure_logging_installs_one_json_handler():
    """Idempotent, so calling it from both the app factory and a worker entry point
    cannot double-log. Destination is stdout because locked 53.6 records log
    aggregation as NOT YET SPECIFIED — the platform collects it."""
    logger = logging.getLogger(LOGGER_NAME)
    before = list(logger.handlers)
    try:
        configure_logging("DEBUG")
        configure_logging("DEBUG")          # idempotent
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JsonFormatter)
        assert logger.level == logging.DEBUG
        # propagate is off so a host application's root handlers cannot re-emit
        # these lines in a different, unredacted format.
        assert logger.propagate is False
    finally:
        logger.handlers = before


# =====================================================================
# 53.5 — every named signal has an emission site
# =====================================================================
def test_every_alertable_signal_has_an_emission_site():
    """Locked 53.5 lists the signals worth collecting, and 53.6 leaves the monitoring
    stack NOT YET SPECIFIED — so "collected" can only mean *emitted somewhere*.

    Three of them had no emission site at all: authentication failures, permission
    denials and decision throughput. A named signal nothing emits is a metric that
    exists only in a document.
    """
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    sources = "\n".join(
        path.read_text() for path in (backend / "legalmind").rglob("*.py"))

    for signal in ALERTABLE_SIGNALS | {"decision.outstanding_age",
                                       "analysis.classification_count",
                                       "analysis.fail_closed_rate"}:
        assert signal in sources, f"{signal} is named in 53.5 and emitted nowhere"


def test_an_authentication_failure_is_signalled_without_the_email(
        api, captured, db, seeded):
    """53.5 wants the failure count; 53.3's fourth prohibition forbids anything that
    turns a failed login into an enumeration oracle. Both at once: the signal carries
    the source address and never the submitted address.

    Two harness details, both learned the hard way and both worth stating:

    * it uses the `captured` fixture rather than adding a handler to the shared logger,
      because pytest's logging plugin owns those handlers — which is exactly why that
      fixture patches the module attribute instead;
    * `api` is requested **before** `captured`, because `create_app()` calls
      `configure_logging()`, which reconfigures whatever `logs._logger` points at. Built
      in the other order it silently strips the probe's handler and the test sees
      nothing.
    """
    response = api.post(f"{V1}/auth/login",
                        json={"email": "nobody@example.test", "password": "wrong"})
    assert response.status_code == 401

    failures = [line for line in captured() if line["event"] == "auth.login_failed"]
    assert failures, "an authentication failure emitted no signal"
    assert failures[0]["signal"] == "auth.failure_count"
    assert failures[0]["level"] == "WARNING"
    body = json.dumps(failures[0])
    assert "nobody@example.test" not in body
    assert "wrong" not in body


def test_a_permission_denial_is_signalled_with_the_object(api, captured, db, seeded):
    """53.5 — "permission denials; **repeated denials on one object** matter", which
    is why the object id is deliberately included rather than omitted."""
    from tests.conftest import bespoke_role, grant, make_review_for, make_user, sign_in

    owner = make_user(db)
    grant(db, owner, bespoke_role(db, "REVIEW_VIEW_ONLY", ["review.view"]))
    review = make_review_for(db, owner)
    sign_in(api, db, owner)

    # Visible (owned) but the operation is not permitted → 403 and a denial signal.
    assert api.post(f"{V1}/reviews/{review.id}/analyze").status_code == 403

    denials = [line for line in captured() if line["event"] == "authz.denied"]
    assert denials, "a permission denial emitted no signal"
    assert denials[0]["signal"] == "authz.denial_count"
    assert denials[0]["entity_id"] == str(review.id)
    assert denials[0]["permission"] == "review.create"


def test_a_recorded_decision_signals_its_age(captured, db, seeded, user, review,
                                             requirement_version):
    """53.5 — "decision throughput and age", emitted where a decision is recorded so
    no scheduler is needed. Deliberately without `decision_type`: 53.5 asks for
    throughput and age, and a disposition is nearer the internal legal position
    LEGAL-02 protects than a count is."""
    from legalmind.domain.enums import DecisionType
    from legalmind.workflow.decisions import record_decision
    from tests.conftest import (
        bespoke_role,
        grant,
        make_evaluation,
        make_finding,
    )

    # The Review's own owner, so visibility comes from ownership (Step 24 r3) and this
    # test is about the signal rather than about REC-09's scope.
    actor = user
    grant(db, actor, bespoke_role(db, "DECIDER", ["legal.decision"]))
    finding = make_finding(db, review, requirement_version)
    evaluation = make_evaluation(db, finding)

    record_decision(db, actor_id=actor.id, evaluation_id=evaluation.id,
                    decision_type=DecisionType.ACCEPT_DEVIATION,
                    justification="structural", request_id="req-9")

    recorded = [line for line in captured()
                if line["event"] == "legal.decision_recorded"]
    assert recorded, "a recorded decision emitted no signal"
    assert recorded[0]["signal"] == "decision.outstanding_age"
    assert recorded[0]["waited_seconds"] is not None
    assert recorded[0]["version_number"] == 1
    # Not the disposition.
    assert "ACCEPT_DEVIATION" not in json.dumps(recorded[0])


def test_the_outstanding_decision_query_lives_in_the_domain_layer(db, seeded, review,
                                                                 requirement_version):
    """53.5's other half — "Reviews stuck in DECISION_REQUIRED".

    A query rather than a counter, because Finding status is derived (Step 30 r16). It
    lives in `workflow.decisions`, not in `observability.metrics`: that package must
    not import the legal store, which is what keeps 53.1's separation structural —
    see `test_logging_never_writes_an_audit_event`, which caught this being put in the
    wrong place.
    """
    from legalmind.workflow.decisions import outstanding_decisions
    from tests.conftest import make_evaluation, make_finding

    before = outstanding_decisions(db)["outstanding"]
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding)
    db.flush()

    after = outstanding_decisions(db)
    assert after["outstanding"] == before + 1
    assert after["signal"] == "decision.outstanding_age"
    assert after["oldest_created_at"] is not None


def test_running_migrations_does_not_disable_application_logging():
    """A latent defect worth a permanent guard — locked 53.4.

    `logging.config.fileConfig` disables every pre-existing logger unless told
    otherwise, and Alembic's `env.py` calls it. Migrations run in-process in the test
    harness, in `tools/e2e_bootstrap`, in `tools/verify_*`, and in any deployment that
    migrates from the application image — so the default would switch the application's
    own logging off for the remainder of the process, silently.

    Nothing legal would break (53.1 makes logs non-authoritative) and nothing would be
    observable either, which is the failure 53.4's operator-facing half exists to
    prevent. It surfaced as a test that logged after touching the database and captured
    nothing at all.
    """
    from logging.config import fileConfig
    from pathlib import Path

    application = logging.getLogger(LOGGER_NAME)
    application.disabled = False
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"

    # The default that would break it, asserted so the guard cannot be misread as
    # paranoia: this is what `env.py` deliberately does not do.
    fileConfig(str(ini))
    assert application.disabled is True, (
        "if this fails, fileConfig no longer disables existing loggers and the "
        "explanation in alembic/env.py should be revisited")

    # And what `env.py` actually does.
    application.disabled = False
    fileConfig(str(ini), disable_existing_loggers=False)
    assert application.disabled is False
    assert application.isEnabledFor(logging.INFO)


def test_alembic_env_passes_disable_existing_loggers_false():
    """Asserted against the source, because the behaviour above is only correct if
    `env.py` actually passes the flag — and a migration-time regression would be
    invisible until an operator needed a log line that was never written."""
    from pathlib import Path

    env = (Path(__file__).resolve().parents[1] / "alembic" / "env.py").read_text()
    assert "disable_existing_loggers=False" in env

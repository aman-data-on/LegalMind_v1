"""Schema-level enforcement of locked invariants.

These are Tier-3 invariant tests (Step 54.5). Each asserts that the DATABASE
enforces a locked requirement — not merely that application code intends to.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.conftest import make_evaluation, make_finding


# ---------------------------------------------------------------- EV-MIN
def _force_deferred(db):
    """Fire DEFERRABLE INITIALLY DEFERRED constraints without a real COMMIT.

    Tests run inside a transaction that is rolled back, so session.commit()
    never reaches a true COMMIT and deferred triggers would never fire.
    SET CONSTRAINTS ALL IMMEDIATE forces the check at this point instead.
    """
    db.flush()
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_ev_min_finding_without_evaluation_fails_at_commit(db, review, requirement_version):
    """AB-1.6 / D-3.4: every Finding has >= 1 Evaluation."""
    make_finding(db, review, requirement_version)
    with pytest.raises(DBAPIError) as exc:
        _force_deferred(db)
    assert "EV-MIN violated" in str(exc.value)


def test_ev_min_satisfied_when_evaluation_present(db, review, requirement_version):
    f = make_finding(db, review, requirement_version)
    make_evaluation(db, f)
    _force_deferred(db)          # deferred check passes
    assert db.get(M.Finding, f.id) is not None


# --------------------------------------------------- EV-MIN on the removal path
# `F-1`. The INSERT-side trigger enforces AB-1.6 when a Finding is created and never
# again, so an existing Finding could be orphaned by deleting its last Evaluation.
# `F-5` chose a database trigger precisely because "a migration or backfill can
# bypass service code" — these assert the removal path is covered too.
def test_ev_min_deleting_the_last_evaluation_fails(db, review, requirement_version):
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    _force_deferred(db)                       # the Finding is valid at this point

    db.delete(ev)
    with pytest.raises(Exception) as exc:
        _force_deferred(db)
    assert "EV-MIN violated" in str(exc.value)


def test_ev_min_deleting_one_of_several_evaluations_is_allowed(
        db, review, requirement_version):
    """One Requirement may produce several scoped Evaluations (45C.1). Removing one
    while others remain leaves the invariant intact."""
    f = make_finding(db, review, requirement_version)
    make_evaluation(db, f, scope_key="AGGREGATE")
    doomed = make_evaluation(db, f, scope_key="CATEGORY")
    _force_deferred(db)

    db.delete(doomed)
    _force_deferred(db)                       # passes: one Evaluation remains
    assert db.get(M.Finding, f.id) is not None


def test_ev_min_reparenting_the_last_evaluation_fails(
        db, review, requirement_version, user):
    """Moving an Evaluation to another Finding vacates the first one. Covered by the
    same guard, because otherwise the delete check would be trivially bypassable."""
    import uuid as _uuid
    from legalmind.domain import enums as _E

    other_req = M.Requirement(code=f"R-{_uuid.uuid4().hex[:6]}",
                              status=_E.ConfigStatus.ACTIVE)
    db.add(other_req); db.flush()
    other_rv = M.RequirementVersion(
        requirement_id=other_req.id, version_number=1, name="Other",
        evaluator_type=_E.EvaluatorType.PRESENCE, created_by=user.id)
    db.add(other_rv); db.flush()

    first = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, first)
    second = make_finding(db, review, other_rv)
    make_evaluation(db, second, scope_key="OTHER")
    _force_deferred(db)

    ev.finding_id = second.id                 # vacates `first`
    with pytest.raises(Exception) as exc:
        _force_deferred(db)
    assert "EV-MIN violated" in str(exc.value)


# ------------------------------------------------- decisions target Evaluations
def test_decision_requires_evaluation_id(db, review, requirement_version, user):
    """AM-1: evaluation_id is NOT NULL — a decision resolves one Evaluation."""
    f = make_finding(db, review, requirement_version)
    make_evaluation(db, f)
    db.add(M.LegalDecision(
        finding_id=f.id, evaluation_id=None,
        decision_type=E.DecisionType.ACCEPT_DEVIATION,
        justification="x", decided_by=user.id, version_number=1))
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_evaluation_must_belong_to_same_finding(db, review, requirement_version, user):
    """AB-1.1 composite FK — enforced declaratively, not by service check."""
    f1 = make_finding(db, review, requirement_version)
    ev1 = make_evaluation(db, f1)

    req2 = M.Requirement(code=f"OTHER-{uuid.uuid4().hex[:4]}", status=E.ConfigStatus.ACTIVE)
    db.add(req2); db.flush()
    rv2 = M.RequirementVersion(requirement_id=req2.id, version_number=1, name="Other",
                               evaluator_type=E.EvaluatorType.PRESENCE, created_by=user.id)
    db.add(rv2); db.flush()
    f2 = make_finding(db, review, rv2)
    make_evaluation(db, f2)

    # decision claims finding f2 but evaluation ev1 (which belongs to f1)
    db.add(M.LegalDecision(
        finding_id=f2.id, evaluation_id=ev1.id,
        decision_type=E.DecisionType.ACCEPT_DEVIATION,
        justification="mismatched", decided_by=user.id, version_number=1))
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_justification_is_mandatory(db, review, requirement_version, user):
    """AM-15 — Step 31 r11 requires a reason; previously unenforced."""
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    db.add(M.LegalDecision(
        finding_id=f.id, evaluation_id=ev.id,
        decision_type=E.DecisionType.REJECT,
        justification=None, decided_by=user.id, version_number=1))
    with pytest.raises(IntegrityError):
        db.flush()


# ------------------------------------------------------ decision supersession
def test_decision_version_collision_rejected(db, review, requirement_version, user):
    """AM-12: UNIQUE(evaluation_id, version_number).

    Two writers both computing version N+1 -> one fails. This is what gives
    optimistic concurrency without a separate ETag mechanism, and why a lost
    update cannot silently produce two 'current' decisions.
    """
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    for _ in range(2):
        db.add(M.LegalDecision(
            finding_id=f.id, evaluation_id=ev.id,
            decision_type=E.DecisionType.ACCEPT_DEVIATION,
            justification="reason", decided_by=user.id, version_number=1))
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_supersession_is_append_only(db, review, requirement_version, user):
    """Step 31 r14 — a later change creates a new version, never an overwrite."""
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    d1 = M.LegalDecision(finding_id=f.id, evaluation_id=ev.id,
                         decision_type=E.DecisionType.ACCEPT_DEVIATION,
                         justification="v1", decided_by=user.id, version_number=1)
    db.add(d1); db.flush()

    db.add(M.LegalDecision(finding_id=f.id, evaluation_id=ev.id,
                           decision_type=E.DecisionType.REJECT,
                           justification="v2", decided_by=user.id, version_number=2))
    db.flush()

    rows = db.execute(text(
        "SELECT version_number, decision_type FROM legal_decisions "
        "WHERE evaluation_id = :e ORDER BY version_number"), {"e": ev.id}).all()
    assert [r[0] for r in rows] == [1, 2]
    assert rows[0][1] == "ACCEPT_DEVIATION"     # v1 intact, not rewritten


def test_legal_decisions_cannot_be_updated_or_deleted(db, review, requirement_version, user):
    """Step 31 r14 enforced in the database, not by convention."""
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    d = M.LegalDecision(finding_id=f.id, evaluation_id=ev.id,
                        decision_type=E.DecisionType.REJECT,
                        justification="v1", decided_by=user.id, version_number=1)
    db.add(d); db.flush()
    did = d.id

    sp = db.begin_nested()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE legal_decisions SET justification='tampered' "
                        "WHERE id=:i"), {"i": did})
    sp.rollback()

    sp = db.begin_nested()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM legal_decisions WHERE id=:i"), {"i": did})
    sp.rollback()


# ----------------------------------------------------------------- audit trail
def test_audit_events_are_append_only(db, user):
    """AUD-01. No application bug or manual script can rewrite legal history."""
    a = M.AuditEvent(actor_id=user.id, action="auth.login_succeeded",
                     entity_type="session", entity_id=uuid.uuid4(),
                     event_metadata={"request_id": "req-1"})
    db.add(a); db.flush()
    aid = a.id

    sp = db.begin_nested()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_events SET action='x' WHERE id=:i"), {"i": aid})
    sp.rollback()

    sp = db.begin_nested()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM audit_events WHERE id=:i"), {"i": aid})
    sp.rollback()


def test_audit_actor_nullable_for_preauth_events(db):
    """Step 47 — a failed login for an unknown account has no actor."""
    db.add(M.AuditEvent(actor_id=None, action="auth.login_failed",
                        entity_type="authentication", entity_id=None,
                        event_metadata={"request_id": "req-2"}))
    db.flush()


# --------------------------------------------------------------- cardinalities
def test_one_finding_per_requirement_per_review(db, review, requirement_version):
    """A-4.1 — UNIQUE(review_id, requirement_version_id)."""
    f1 = make_finding(db, review, requirement_version)
    make_evaluation(db, f1)
    f2 = M.Finding(review_id=review.id, requirement_version_id=requirement_version.id,
                   classification=E.FindingClassification.MATCH,
                   status=E.FindingStatus.OPEN)
    db.add(f2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_evaluation_evidence_permits_zero_rows(db, review, requirement_version):
    """N-34 / N-37: a MISSING from established absence carries NO evidence.

    A minimum-cardinality constraint here would make locked 45C.15
    unrepresentable and would force synthetic evidence — which is forbidden.
    """
    f = make_finding(db, review, requirement_version,
                     classification=E.FindingClassification.MISSING)
    ev = make_evaluation(db, f, classification=E.FindingClassification.MISSING,
                         rule_outcome=E.RuleOutcome.NOT_APPLICABLE)
    db.flush()
    count = db.execute(text("SELECT count(*) FROM evaluation_evidence "
                            "WHERE evaluation_id=:e"), {"e": ev.id}).scalar()
    assert count == 0


def test_rule_outcome_is_not_nullable(db, review, requirement_version):
    """45B.26 — no arbitrary NULL semantics; absence is NOT_APPLICABLE."""
    f = make_finding(db, review, requirement_version)
    db.add(M.Evaluation(
        finding_id=f.id, evaluator_type=E.EvaluatorType.PRESENCE,
        evaluator_version="v1", scope_key="DEFAULT",
        evaluation_kind=E.EvaluationKind.PRIMARY,
        classification=E.FindingClassification.MATCH,
        rule_outcome=None, result={}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_evaluator_version_is_mandatory(db, review, requirement_version):
    """AM-19 — locked 45B.10 requires the exact evaluator version."""
    f = make_finding(db, review, requirement_version)
    db.add(M.Evaluation(
        finding_id=f.id, evaluator_type=E.EvaluatorType.PRESENCE,
        evaluator_version=None, scope_key="DEFAULT",
        evaluation_kind=E.EvaluationKind.PRIMARY,
        classification=E.FindingClassification.MATCH,
        rule_outcome=E.RuleOutcome.NOT_APPLICABLE, result={}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_legal_rule_version_is_optional(db, review, requirement_version):
    """AM-20 nullable — Step 20 r4: not every Clause needs a Legal Rule."""
    f = make_finding(db, review, requirement_version)
    ev = make_evaluation(db, f)
    assert ev.legal_rule_version_id is None
    db.flush()


# ------------------------------------------------------------- axis separation
def test_each_axis_has_its_own_enum_type(db):
    """REC-06 — no axis may share an enum type with another.

    AMBIGUOUS means three different things on three layers; if they shared a
    type the distinction would be unenforceable.
    """
    rows = db.execute(text("""
        SELECT t.typname, count(e.enumlabel)
        FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE t.typname IN ('finding_classification','rule_outcome','decision_type',
                            'review_status','finding_status','extraction_status',
                            'evaluator_type','evaluation_kind')
        GROUP BY t.typname ORDER BY t.typname""")).all()
    got = dict(rows)
    assert got["finding_classification"] == 7
    assert got["rule_outcome"] == 4
    assert got["decision_type"] == 5
    assert got["review_status"] == 9
    assert got["finding_status"] == 4
    assert got["evaluator_type"] == 2       # AM-16: exactly two
    assert got["evaluation_kind"] == 2
    # extraction_status is a separate type from finding_classification even
    # though both contain AMBIGUOUS
    assert got["extraction_status"] == 4


# ------------------------------------------------- trigger presence (CI gate)
def test_locked_invariants_are_enforced_by_triggers_not_convention(db):
    """The append-only and EV-MIN guarantees exist as DATABASE triggers.

    F-5 chose a constraint trigger over service-layer validation precisely
    because "a migration or backfill can bypass service code". A refactor that
    dropped the trigger DDL from the migration would leave every other test in
    this file still passing — they exercise behaviour through the ORM, which
    would simply start succeeding where it used to raise. This asserts the
    mechanism itself is present.

    Scoped to ``current_schema()``: each run migrates into its own private
    schema, so an unscoped pg_trigger query would also see triggers belonging
    to other runs' schemas and pass even if this run's migration produced none.
    """
    rows = db.execute(text("""
        SELECT cl.relname, t.tgname
        FROM pg_trigger t
        JOIN pg_class cl ON cl.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        WHERE NOT t.tgisinternal
          AND n.nspname = current_schema()""")).all()
    by_table = {table for table, _ in rows}

    assert "audit_events" in by_table, "AUD-01: audit_events must be append-only"
    assert "legal_decisions" in by_table, "Step 31 r14: decisions must be append-only"
    assert "findings" in by_table, "AB-1.6: EV-MIN must be enforced at COMMIT"


def test_ev_min_triggers_are_deferred_to_commit(db):
    """All three EV-MIN triggers are DEFERRABLE INITIALLY DEFERRED — asserted against
    `pg_trigger` rather than by behaviour, and deliberately so.

    Deferral is what makes two legitimate sequences legal inside one transaction:
    deleting an Evaluation and inserting a replacement, and deleting a Finding
    together with its Evaluations. Neither can be demonstrated behaviourally in this
    suite, because `_force_deferred` issues `SET CONSTRAINTS ALL IMMEDIATE`, which
    applies for the remainder of the transaction — after that first call nothing is
    deferred any more. Rather than build a committing-session fixture whose real
    COMMITs would leak rows into the shared per-run schema and contaminate tests
    that count rows, this asserts the property that produces the behaviour.

    `F-5` chose a trigger over a service invariant; this is the part of that choice
    which makes the trigger usable rather than merely strict.

    Scoped to ``current_schema()``: each run migrates into its own private schema, so
    an unscoped pg_trigger query would also match triggers belonging to other runs.
    """
    rows = db.execute(text("""
        SELECT t.tgname, t.tgdeferrable, t.tginitdeferred
        FROM pg_trigger t
        JOIN pg_class cl ON cl.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        WHERE NOT t.tgisinternal
          AND n.nspname = current_schema()
          AND t.tgname IN ('trg_findings_ev_min',
                           'trg_evaluations_ev_min_delete',
                           'trg_evaluations_ev_min_reparent')
        ORDER BY t.tgname
    """)).all()

    found = {r[0]: (r[1], r[2]) for r in rows}
    assert set(found) == {
        "trg_findings_ev_min",              # insert side (original)
        "trg_evaluations_ev_min_delete",    # F-1: removal side
        "trg_evaluations_ev_min_reparent",  # F-1: re-parenting side
    }
    for name, (deferrable, initially_deferred) in found.items():
        assert deferrable, f"{name} is not DEFERRABLE"
        assert initially_deferred, f"{name} is not INITIALLY DEFERRED"

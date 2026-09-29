"""At most one ACTIVE escalation per Finding, held by the database — decision 339
(2026-09-29, from the production system design review §14.4 / §28.4).

Locked 43.28 makes escalation idempotent. The check-then-insert that enforced it
could be passed by two simultaneous requests, and `withdraw_escalation` then
withdrew one of the two rows. `uq_escalations_one_active` closes that; the service
catches it under a savepoint and returns the row that won.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from legalmind.workflow import escalation
from tests.conftest import grant_role, make_evaluation, make_finding


@pytest.fixture
def finding(db, seeded, user, review, requirement_version):
    grant_role(db, user, P.ROLE_USER)
    f = make_finding(db, review, requirement_version)
    make_evaluation(db, f, rule_outcome=E.RuleOutcome.ACCEPTABLE)
    return f


def _active(db, finding_id):
    return db.execute(select(M.Escalation).where(
        M.Escalation.finding_id == finding_id,
        M.Escalation.withdrawn_at.is_(None))).scalars().all()


def test_the_database_refuses_a_second_active_escalation(db, user, finding):
    db.add(M.Escalation(finding_id=finding.id, raised_by=user.id, reason="one"))
    db.flush()
    db.add(M.Escalation(finding_id=finding.id, raised_by=user.id, reason="two"))
    with pytest.raises(IntegrityError, match="uq_escalations_one_active"):
        db.flush()


def test_two_simultaneous_escalations_share_one_row(db, user, finding, monkeypatch):
    """The race: both requests read 'no active escalation' before either inserts.
    Simulated by letting the check say None once more than it should."""
    first = escalation.escalate_finding(db, actor_id=user.id, finding_id=finding.id,
                                        reason="please review")
    real = escalation._active_escalation
    calls = {"stale": 1}

    def stale_once(db_, finding_id):
        if calls["stale"]:
            calls["stale"] -= 1
            return None
        return real(db_, finding_id)
    monkeypatch.setattr(escalation, "_active_escalation", stale_once)

    second = escalation.escalate_finding(db, actor_id=user.id, finding_id=finding.id,
                                         reason="please review again")
    assert second.id == first.id
    assert len(_active(db, finding.id)) == 1
    # The request survived the refused insert and the session is still usable.
    assert db.execute(select(M.Escalation).where(
        M.Escalation.id == first.id)).scalar_one().reason == "please review"


def test_withdrawing_then_escalating_again_is_a_new_active_row(db, user, finding):
    """History is kept: a withdrawn escalation does not block the next one."""
    first = escalation.escalate_finding(db, actor_id=user.id, finding_id=finding.id,
                                        reason="first")
    escalation.withdraw_escalation(db, actor_id=user.id, finding_id=finding.id)
    again = escalation.escalate_finding(db, actor_id=user.id, finding_id=finding.id,
                                        reason="second")
    assert again.id != first.id
    assert len(_active(db, finding.id)) == 1
    assert db.execute(select(M.Escalation).where(
        M.Escalation.finding_id == finding.id)).scalars().all().__len__() == 2

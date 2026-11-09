"""A Legal Decision is made once per deal on the same words (`AM-317` r7, owner
2026-11-09 option a; amends Step 26 r10/r12; audit N3/B9): Legal accepts an 18-month cap
on version 1; version 2 (the client changed only payment days) and our version 3 read
the clause byte for byte, so the point stands as decided — a `decision.carried_forward`
audit row naming the original decision, NO new Legal Decision, the classification still
DEVIATION. One word changed in the clause and nothing carries. Synthetic wording only
(rule 21); the standard is the ratified file.
"""
from __future__ import annotations

from sqlalchemy import func, select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.evaluation.workflow import DECISION_CARRIED_FORWARD
from legalmind.workflow.decisions import carry_forward
from tests.legal_regression.test_effect_for_us import CAP, OURS, _version
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified
from tests.test_negotiation_wording import _lawyer

CAPPED = OURS.replace("twelve (12)", "eighteen (18)")


def _cap_finding(db, review):
    return db.execute(
        select(M.Finding)
        .join(M.RequirementVersion, M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id == review.id, M.Requirement.code == CAP)).scalar_one()


def _deal(build, db, seeded):
    _ratified(build, CAP)
    contract = M.Contract(owner_id=build.owner.id, name="Deal", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    _, r1 = _version(build, db, contract, CAPPED)
    f1 = _cap_finding(db, r1)
    assert f1.status is E.FindingStatus.DECISION_REQUIRED
    lawyer = _lawyer(db)
    lawyer.name = "Lawyer Test"
    [ev] = db.scalars(select(M.Evaluation).where(M.Evaluation.finding_id == f1.id)).all()
    decision = M.LegalDecision(finding_id=f1.id, evaluation_id=ev.id,
                               decision_type=E.DecisionType.ACCEPT_DEVIATION,
                               justification="accepted for this deal",
                               decided_by=lawyer.id, version_number=1)
    db.add(decision); db.flush()
    return contract, decision


def _carried(db, finding):
    return db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == DECISION_CARRIED_FORWARD,
        M.AuditEvent.entity_id == finding.id)).all()


def test_an_unchanged_point_stays_decided_on_every_later_version(build, db, seeded):
    contract, decision = _deal(build, db, seeded)
    for _ in (2, 3):                                  # the client's v2, our v3
        _, review = _version(build, db, contract, CAPPED)
        finding = _cap_finding(db, review)
        assert finding.status is E.FindingStatus.RESOLVED          # not in Legal's queue
        assert finding.classification is E.FindingClassification.DEVIATION  # never MATCH
        [event] = _carried(db, finding)
        assert event.after_state["decision_ids"] == [str(decision.id)]   # the original
        assert event.after_state["from_version_number"] == 1
        assert event.actor_id is None
        assert db.scalar(select(func.count()).select_from(M.LegalDecision)
                         .where(M.LegalDecision.finding_id == finding.id)) == 0
        assert carry_forward(db, review) == 0                      # idempotent
    from legalmind.api.serializers import serialize_finding
    said = serialize_finding(db, finding, legal_position=False)["carried_decision"]
    assert (said["version_number"], said["decided_by_name"]) == (1, "Lawyer Test")


def test_one_word_changed_and_the_point_reopens(build, db, seeded):
    contract, _ = _deal(build, db, seeded)
    _, review = _version(build, db, contract,
                         CAPPED.replace("total aggregate", "entire aggregate"))
    finding = _cap_finding(db, review)
    assert finding.status is E.FindingStatus.DECISION_REQUIRED
    assert _carried(db, finding) == []


def test_an_undecided_earlier_point_carries_nothing(build, db, seeded):
    _ratified(build, CAP)
    contract = M.Contract(owner_id=build.owner.id, name="Deal", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    _version(build, db, contract, CAPPED)
    _, review = _version(build, db, contract, CAPPED)
    assert _cap_finding(db, review).status is E.FindingStatus.DECISION_REQUIRED


# ------------------------------------------------- AM-321 r1: every hop re-checked
def _carried_v2(build, db, seeded):
    contract, decision = _deal(build, db, seeded)
    _, r2 = _version(build, db, contract, CAPPED)
    f2 = _cap_finding(db, r2)
    assert f2.status is E.FindingStatus.RESOLVED and _carried(db, f2)
    return contract, decision, f2


def _escalate(build, db, finding):
    db.add(M.Escalation(finding_id=finding.id, raised_by=build.owner.id, reason="look again"))
    db.flush()


def _decide(db, finding, kind, n=1):
    [ev] = db.scalars(select(M.Evaluation).where(M.Evaluation.finding_id == finding.id)).all()
    db.add(M.LegalDecision(finding_id=finding.id, evaluation_id=ev.id, decision_type=kind,
                           justification="Legal's latest word", decided_by=_lawyer(db).id,
                           version_number=n))
    db.flush()


def _v3_open(build, db, contract):
    _, r3 = _version(build, db, contract, CAPPED)
    f3 = _cap_finding(db, r3)
    return f3.status is E.FindingStatus.DECISION_REQUIRED and not _carried(db, f3)


def test_an_escalated_intermediate_version_breaks_the_chain(build, db, seeded):
    contract, _, f2 = _carried_v2(build, db, seeded)
    _escalate(build, db, f2)
    assert _v3_open(build, db, contract)


def test_legals_later_reject_on_an_intermediate_version_is_what_stands(build, db, seeded):
    contract, _, f2 = _carried_v2(build, db, seeded)
    _decide(db, f2, E.DecisionType.REJECT)
    assert _v3_open(build, db, contract)


def test_escalated_then_rejected_on_an_intermediate_version_carries_nothing(
        build, db, seeded):
    contract, _, f2 = _carried_v2(build, db, seeded)
    _escalate(build, db, f2)
    _decide(db, f2, E.DecisionType.REJECT)
    assert _v3_open(build, db, contract)


def test_a_decider_who_lost_the_right_carries_nothing_down_the_chain(build, db, seeded):
    contract, decision, _ = _carried_v2(build, db, seeded)
    db.execute(M.UserRole.__table__.delete().where(
        M.UserRole.user_id == decision.decided_by))
    db.flush()
    assert _v3_open(build, db, contract)


def test_an_original_decision_superseded_since_carries_nothing(build, db, seeded):
    """v1's acceptance is replaced by Legal's REJECT (version 2 of its chain) after v2
    carried it: v3 carries nothing — the latest human word on the chain stands."""
    contract, decision, _ = _carried_v2(build, db, seeded)
    f1 = db.get(M.Finding, decision.finding_id)
    _decide(db, f1, E.DecisionType.REJECT, n=2)
    assert _v3_open(build, db, contract)


def test_a_real_decision_on_the_intermediate_version_carries_from_there(build, db, seeded):
    """Legal re-decided on v2 (ACCEPT again): v3 references v2's decision, not v1's."""
    contract, _, f2 = _carried_v2(build, db, seeded)
    _decide(db, f2, E.DecisionType.ACCEPT_DEVIATION)
    _, r3 = _version(build, db, contract, CAPPED)
    f3 = _cap_finding(db, r3)
    [event] = _carried(db, f3)
    assert f3.status is E.FindingStatus.RESOLVED
    assert event.after_state["from_version_number"] == 2

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

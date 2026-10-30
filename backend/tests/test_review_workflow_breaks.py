"""Break tests for the review workflow (owner, 2026-10-22; plan docs/00-project/REVIEW_WORKFLOW_PLAN.md).

Each test states the rule the approved plan sets (AB-103) and was written BEFORE the fix, so
it is red on the code it was written against. Assertions that need an API which does not
exist yet are `xfail(strict=True)` with the reason, so the fix flips them visibly. Expected
values come from the rule, never from what the code returns; counts are recomputed here
from the persisted `legal_decisions` and `evaluations`, never read back from the code under
test.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import (
    grant,
    grant_role,
    make_evaluation,
    make_finding,
    make_review_for,
    make_user,
    sign_in,
)
from tests.legal_regression.test_legal_regression import (
    FIXED_TERM_EXIT,
    INAPPLICABLE,
    _angles,
    _findings,
    _review,
)
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_review_assignment import _reviewer, _send

V1 = "/api/v1"
WHY = "break-test decision (synthetic; not a legal position)"


# ------------------------------------------------------------------ helpers
@pytest.fixture
def owner(db, seeded):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    return user


def _points(db, review, rv, n):
    """`n` points that each need a decision: a DEVIATION ruled UNACCEPTABLE, one requirement
    each (a review holds one finding per requirement)."""
    evaluations = []
    for i in range(n):
        if i:
            req = M.Requirement(code=f"BREAK-{uuid.uuid4().hex[:6]}",
                                status=E.ConfigStatus.ACTIVE)
            db.add(req); db.flush()
            rv = M.RequirementVersion(requirement_id=req.id, version_number=1,
                                      name=f"Point {i + 1}", created_by=review.created_by,
                                      evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON)
            db.add(rv); db.flush()
        finding = make_finding(db, review, rv)
        evaluations.append(make_evaluation(
            db, finding, classification=E.FindingClassification.DEVIATION,
            rule_outcome=E.RuleOutcome.UNACCEPTABLE))
    db.flush()
    return evaluations


def _decide(api, evaluation, kind, *, expected=None, omit_version=False):
    body = {"decision_type": kind, "justification": WHY}
    if not omit_version:
        body["expected_version"] = expected if expected is not None else _version(api, evaluation)
    return api.post(f"{V1}/evaluations/{evaluation.id}/decisions", json=body)


def _version(api, evaluation) -> int:
    chain = api.get(f"{V1}/evaluations/{evaluation.id}/decisions").json()["data"]
    return max((d["version_number"] for d in chain), default=0)


def _status(db, review) -> str:
    db.expire_all()
    return db.get(M.Review, review.id).status.value


def _outcome(api, review, outcome="SIGN_AS_IS"):
    history = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]["history"]
    return api.post(f"{V1}/reviews/{review.id}/outcome",
                    json={"outcome": outcome, "justification": WHY,
                          "expected_version": len(history)})


def _recount(db, review) -> dict:
    """Independent recompute from persisted rows: per evaluation, its current decision."""
    latest = (select(M.LegalDecision.evaluation_id,
                     func.max(M.LegalDecision.version_number).label("v"))
              .group_by(M.LegalDecision.evaluation_id).subquery())
    rows = db.execute(
        select(M.Evaluation.id, M.LegalDecision.decision_type)
        .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .outerjoin(latest, latest.c.evaluation_id == M.Evaluation.id)
        .outerjoin(M.LegalDecision, (M.LegalDecision.evaluation_id == M.Evaluation.id)
                   & (M.LegalDecision.version_number == latest.c.v))
        .where(M.Finding.review_id == review.id)).all()
    clarify = E.DecisionType.REQUEST_CLARIFICATION
    return {"evaluations": len(rows),
            "decided": sum(1 for _, t in rows if t is not None and t is not clarify),
            "clarification": sum(1 for _, t in rows if t is clarify),
            "undecided": sum(1 for _, t in rows if t is None)}


@pytest.fixture
def mixed(api, db, owner, requirement_version):
    """T1's contract: five points, sent to a designated reviewer who decides them."""
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    points = _points(db, review, requirement_version, 5)
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    assert _send(api, review, reviewer).status_code == 201
    sign_in(api, db, reviewer)
    return review, points, reviewer


# ============================================================ T1 — mixed decisions
def test_t1_mixed_decisions_keep_the_review_open_while_a_clarification_is_pending(
        api, db, mixed):
    review, (accept, change1, change2, reject, clarify), _ = mixed
    for ev, kind in [(accept, "ACCEPT_DEVIATION"), (change1, "REQUIRE_COMPANY_STANDARD"),
                     (change2, "REQUIRE_COMPANY_STANDARD"), (reject, "REJECT"),
                     (clarify, "REQUEST_CLARIFICATION")]:
        assert _decide(api, ev, kind).status_code == 201
    assert _status(db, review) == "LEGAL_REVIEW"            # one point still pending
    assert _recount(db, review) == {"evaluations": 5, "decided": 4,
                                    "clarification": 1, "undecided": 0}
    assert _outcome(api, review).status_code == 422          # no contract decision yet


def test_t1_a_late_clarification_on_a_resolved_review_reopens_it(api, db, mixed):
    """AM-175 / AM-178: today the review stays RESOLVED and the contract can be decided."""
    review, points, _ = mixed
    for ev in points:
        _decide(api, ev, "ACCEPT_DEVIATION")
    assert _status(db, review) == "RESOLVED"
    assert _decide(api, points[0], "REQUEST_CLARIFICATION").status_code == 201
    assert _status(db, review) == "LEGAL_REVIEW", "a point needs work again: reopened"
    assert _outcome(api, review).status_code == 422, "no contract decision while clarifying"


def test_t1_a_late_change_request_on_a_closed_review_reopens_it(api, db, mixed):
    review, points, _ = mixed
    for ev in points:
        _decide(api, ev, "ACCEPT_DEVIATION")
    assert _outcome(api, review).status_code == 201
    assert _status(db, review) == "CLOSED"
    assert _decide(api, points[1], "REQUIRE_COMPANY_STANDARD").status_code == 201
    # O5: Change needed reopens. Every point is still decided, so the review settles at
    # RESOLVED (Step 30 r7) with the decision on the CONTRACT due again — never CLOSED.
    assert _status(db, review) == "RESOLVED"
    assert db.get(M.Review, review.id).reopened_at is not None
    assert db.execute(select(func.count()).select_from(M.AuditEvent).where(
        M.AuditEvent.action == "review.reopened",
        M.AuditEvent.entity_id == review.id)).scalar() == 1
    assert _outcome(api, review, "SIGN_WITH_CHANGES").status_code == 201


def test_t1_a_late_accept_on_a_closed_review_does_not_reopen_it(api, db, mixed):
    review, points, _ = mixed
    for ev in points:
        _decide(api, ev, "REQUIRE_COMPANY_STANDARD")
    assert _outcome(api, review, "SIGN_WITH_CHANGES").status_code == 201
    assert _decide(api, points[0], "ACCEPT_DEVIATION").status_code == 201
    assert _status(db, review) == "CLOSED", "O5: Accept never reopens"


def test_t1_an_escalation_on_a_resolved_review_reopens_it(api, db, owner, mixed):
    review, points, _ = mixed
    for ev in points:
        _decide(api, ev, "ACCEPT_DEVIATION")
    assert _status(db, review) == "RESOLVED"
    sign_in(api, db, owner)
    raised = api.post(f"{V1}/findings/{points[2].finding_id}/escalate",
                      json={"reason": "the client sent new wording"})
    assert raised.status_code == 201
    assert _status(db, review) == "LEGAL_REVIEW", "an escalation reopens a finished review"


def test_t1_progress_matches_the_persisted_decisions(api, db, mixed):
    review, points, _ = mixed
    for ev, kind in zip(points, ["ACCEPT_DEVIATION", "REJECT", "REQUEST_CLARIFICATION",
                                 "REQUIRE_COMPANY_STANDARD", "NOT_APPLICABLE_TO_CONTRACT"], strict=True):
        _decide(api, ev, kind)
    got = api.get(f"{V1}/reviews/{review.id}/progress")
    assert got.status_code == 200
    body, want = got.json()["data"], _recount(db, review)
    assert (body["decided"], body["clarification"], body["to_decide"]) == (
        want["decided"], want["clarification"], want["undecided"])
    assert body["stage"] == "WAITING_FOR_CLARIFICATION"


# ============================================================ T2 — conflicting clauses
EXIT_CODES = ["CONVENIENCE-NOTICE-MSA-001", "EARLY-TERM-RESTRICTION-MSA-001"]
TWO_NOTICES = [*FIXED_TERM_EXIT, "20. Miscellaneous",
               "20.1 Either party may terminate for convenience by providing thirty (30) "
               "days' written notice to the other party."]


def test_t2_two_notice_periods_are_a_conflict_citing_both_clauses(build, db):
    """45B / numeric evaluator: two different values for one scope are a CONFLICT, never a
    deviation measured on one of them. Both clauses are cited with their pages."""
    review, _ = _review(build, db, EXIT_CODES, TWO_NOTICES, kind="OTHER")
    notice = _findings(db, review)["CONVENIENCE-NOTICE-MSA-001"]
    assert notice["classification"] == "CONFLICT"
    assert {("13.1", 2), ("20.1", 2)} <= set(notice["cited"])


def test_t2_the_conflict_is_read_with_the_exit_clauses_and_never_settled_by_the_code(
        build, db):
    review, _ = _review(build, db, EXIT_CODES, TWO_NOTICES, kind="OTHER")
    item = next(i for i in _angles(db, review)["legal"]["items"]
                if i["requirement_code"] == "CONVENIENCE-NOTICE-MSA-001")
    assert {"13.2", "13.3"} <= {r["clause"] for r in item["related"]}
    assert item["case"]["recommendation"] == "Seek legal review"


def test_t2_money_is_exactly_fee_times_term(build, db):
    review, _ = _review(build, db, EXIT_CODES, TWO_NOTICES, kind="OTHER")
    assert _angles(db, review)["commercial"]["committed_value"] == 1_200_000


def test_t2_no_money_is_shown_without_a_stated_fee(build, db):
    no_fee = [p for p in TWO_NOTICES if not str(p).startswith(("2. Fees", "2.1"))]
    review, _ = _review(build, db, EXIT_CODES, no_fee, kind="OTHER")
    angles = _angles(db, review)
    assert angles["commercial"]["committed_value"] is None
    assert angles["commercial"]["missing"]
    money = [p["money"] for p in angles["business"] if p.get("money")]
    # AM-156 R1: no amount is invented; where a figure would belong, the reason is said
    assert money and not any(("₹" in m or "Rs" in m) for m in money)
    assert all("states no monthly fee" in m for m in money)


# ============================================================ T3 — applicability
def test_t3_an_inapplicable_standard_is_uncertain_while_a_valid_one_is_kept(build, db):
    paragraphs = [*INAPPLICABLE, "17. Limitation of Liability",
                  "17.1 The total aggregate liability of each party shall not exceed the fees "
                  "paid in the six (6) months preceding the claim."]
    review, _ = _review(build, db, ["KYC-RETENTION-TOS-001", "LIABILITY-MSA-001"], paragraphs)
    found = _findings(db, review)
    assert found["KYC-RETENTION-TOS-001"]["classification"] == "UNABLE_TO_EVALUATE"
    assert found["KYC-RETENTION-TOS-001"]["actual"].get("reason") == "APPLICABILITY_UNCERTAIN"
    assert found["LIABILITY-MSA-001"]["classification"] == "DEVIATION"


# ============================================================ T4 — authority and audit
def test_t4_who_may_decide(api, db, owner, requirement_version):
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    (ev,) = _points(db, review, requirement_version, 1)
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, owner)
    assert _decide(api, ev, "ACCEPT_DEVIATION", expected=0).status_code == 403
    sign_in(api, db, stranger)
    assert _decide(api, ev, "ACCEPT_DEVIATION", expected=0).status_code == 404
    # O2: an owner who holds legal.decision may decide their own points
    grant(db, owner, _decider_role(db))
    sign_in(api, db, owner)
    assert _decide(api, ev, "ACCEPT_DEVIATION", expected=0).status_code == 201


def _decider_role(db):
    from tests.conftest import bespoke_role
    return bespoke_role(db, "BREAK_T4_DECIDER", [P.LEGAL_DECISION])


def test_t4_a_revoked_assignee_loses_a_review_outside_legal_scope(api, db, owner,
                                                                  requirement_version):
    review = make_review_for(db, owner)                     # ANALYSIS_COMPLETE: no Legal scope
    _points(db, review, requirement_version, 1)
    reviewer = _reviewer(db)
    sign_in(api, db, owner)
    _send(api, review, reviewer)
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 200
    sign_in(api, db, owner)
    api.delete(f"{V1}/reviews/{review.id}/assignments/{reviewer.id}")
    sign_in(api, db, reviewer)
    assert api.get(f"{V1}/reviews/{review.id}").status_code == 404


def test_t4_a_decided_contract_can_still_be_deleted(api, db, mixed, owner):
    """AM-55 r3 destroys a contract's decisions with it; the append-only trigger must let a
    cascade through (AM-176). Today the trigger refuses the cascaded DELETE."""
    review, points, _ = mixed
    _decide(api, points[0], "ACCEPT_DEVIATION")
    sign_in(api, db, owner)
    try:
        with db.begin_nested():
            gone = api.delete(f"{V1}/contracts/{review.contract_id}")
    except DBAPIError as exc:
        pytest.fail(f"deleting a decided contract raised: {exc.orig!r}")
    assert gone.status_code == 204


def test_t4_a_decision_row_can_never_be_deleted_directly(api, db, mixed):
    _, points, _ = mixed
    _decide(api, points[0], "ACCEPT_DEVIATION")
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM legal_decisions WHERE evaluation_id = :e"),
                   {"e": points[0].id})


def test_t4_an_archived_contract_takes_no_decision(api, db, mixed, owner):
    review, points, reviewer = mixed
    sign_in(api, db, owner)
    assert api.post(f"{V1}/contracts/{review.contract_id}/archive").status_code == 200
    sign_in(api, db, reviewer)
    assert _decide(api, points[0], "ACCEPT_DEVIATION").status_code == 409


def test_t4_the_decision_audit_names_its_review_finding_and_version(api, db, mixed):
    review, points, _ = mixed
    _decide(api, points[0], "ACCEPT_DEVIATION")
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "legal.decision_recorded")).scalars().one()
    assert event.after_state["review_id"] == str(review.id)
    assert event.after_state["finding_id"] == str(points[0].finding_id)
    assert event.after_state["document_version_id"] == str(review.document_version_id)


# ============================================================ T5 — versions and retries
def _version_two(db, review, owner):
    v2 = M.DocumentVersion(
        contract_id=review.contract_id, version_number=2, original_filename="msa-v2.pdf",
        mime_type="application/pdf", file_size_bytes=10, file_hash="h2", storage_key="k2",
        processing_status=E.ProcessingStatus.PENDING, uploaded_by=owner.id)
    db.add(v2); db.flush()
    return v2


def _analysed(db, review, v2, owner):
    v2.processing_status = E.ProcessingStatus.COMPLETED
    db.add(M.Review(contract_id=review.contract_id, document_version_id=v2.id,
                    configuration_snapshot_id=review.configuration_snapshot_id,
                    status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=owner.id))
    db.flush()


def test_t5_version_one_stays_decidable_until_version_two_is_analysed(api, db, owner, mixed):
    review, points, reviewer = mixed
    v2 = _version_two(db, review, owner)
    assert _decide(api, points[0], "ACCEPT_DEVIATION").status_code == 201   # O6: pending v2
    _analysed(db, review, v2, owner)
    assert _decide(api, points[1], "ACCEPT_DEVIATION").status_code == 409, (
        "a superseded version is read-only history (AM-178)")


def test_t5_a_decision_without_its_expected_version_is_refused(api, db, mixed):
    _, points, _ = mixed
    assert _decide(api, points[0], "ACCEPT_DEVIATION", omit_version=True).status_code == 422
    assert db.execute(select(func.count()).select_from(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == points[0].id)).scalar() == 0


def test_t5_a_retried_decision_is_recorded_once(api, db, mixed):
    _, points, _ = mixed
    first = _decide(api, points[0], "ACCEPT_DEVIATION", expected=0)
    again = _decide(api, points[0], "ACCEPT_DEVIATION", expected=0)
    assert (first.status_code, again.status_code) == (201, 409)
    assert db.execute(select(func.count()).select_from(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == points[0].id)).scalar() == 1


def test_t5_version_one_reads_as_superseded(api, db, owner, mixed):
    review, _, _ = mixed
    _analysed(db, review, _version_two(db, review, owner), owner)
    body = api.get(f"{V1}/reviews/{review.id}/progress").json()["data"]
    assert body["stage"] == "SUPERSEDED"


# ============================================================ T6 — one card, several requirements
@pytest.fixture
def folded(api, db, owner):
    """One clause measured against two families (AM-51): two findings, one point."""
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    run = M.DocumentProcessingRun(document_version_id=review.document_version_id,
                                  run_type=E.ProcessingRunType.PARSE,
                                  status=E.ProcessingRunStatus.COMPLETED)
    db.add(run); db.flush()
    clause = M.DocumentEvidence(document_version_id=review.document_version_id,
                                processing_run_id=run.id,
                                content="Liability is capped at 6 months of fees.",
                                source_type=E.EvidenceSourceType.NATIVE_TEXT)
    db.add(clause); db.flush()

    def point(code):
        req = M.Requirement(code=code, status=E.ConfigStatus.ACTIVE)
        db.add(req); db.flush()
        rv = M.RequirementVersion(requirement_id=req.id, version_number=1, name=code,
                                  evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                                  created_by=owner.id)
        db.add(rv); db.flush()
        finding = make_finding(db, review, rv)
        ev = make_evaluation(db, finding, classification=E.FindingClassification.DEVIATION,
                             rule_outcome=E.RuleOutcome.UNACCEPTABLE)
        ev.actual_value = {"cap_value": 6, "cap_unit": "MONTHS"}
        ev.expected_value = {"cap_value": 12, "cap_unit": "MONTHS"}
        db.add(M.EvaluationEvidence(evaluation_id=ev.id, evidence_id=clause.id,
                                    relationship_type=E.EvidenceRelationshipType.PRIMARY))
        db.flush()
        return ev

    a, b = point("BREAKCAP-MSA-001"), point("BREAKCAP-TOS-001")
    sign_in(api, db, _reviewer(db))
    return review, a, b


def _groups(api, review):
    rows = api.get(f"{V1}/reviews/{review.id}/findings").json()["data"]
    return {r["id"]: r["group_id"] for r in rows}


def _group_post(api, review, evs, versions, kind="ACCEPT_DEVIATION"):
    return api.post(f"{V1}/reviews/{review.id}/decisions", json={
        "evaluation_ids": [str(e.id) for e in evs], "decision_type": kind,
        "justification": WHY, "expected_versions": {str(e.id): v for e, v in zip(
            evs, versions, strict=True)}})


def test_t6_two_requirements_on_one_clause_are_one_point_that_stays_one(api, db, folded):
    review, a, b = folded
    before = _groups(api, review)
    assert before[str(a.finding_id)] == before[str(b.finding_id)]
    assert _decide(api, b, "REJECT").status_code == 201
    after = _groups(api, review)
    assert after[str(a.finding_id)] == after[str(b.finding_id)], (
        "deciding one member never splits the point (AM-179)")


def test_t6_one_decision_covers_the_named_items_and_skips_decided_ones(api, db, folded):
    review, a, b = folded
    assert _decide(api, b, "REJECT").status_code == 201        # already decided: skipped
    done = _group_post(api, review, [a, b], [0, 1])
    assert done.status_code == 201
    body = done.json()["data"]
    assert [d["evaluation_id"] for d in body["decided"]] == [str(a.id)]
    assert body["skipped"] == [str(b.id)]
    assert _version(api, b) == 1 and _version(api, a) == 1
    assert _recount(db, review) == {"evaluations": 2, "decided": 2,
                                    "clarification": 0, "undecided": 0}


def test_t6_a_group_decision_is_all_or_nothing(api, db, folded):
    review, a, b = folded
    assert _group_post(api, review, [a, b], [0, 7]).status_code == 409   # b is stale
    assert _recount(db, review)["decided"] == 0, "nothing recorded when one item fails"


def test_t6_an_item_from_another_point_is_refused(api, db, folded, requirement_version):
    review, a, _ = folded
    (other,) = _points(db, review, requirement_version, 1)
    assert _group_post(api, review, [a, other], [0, 0]).status_code == 422


def test_t6_a_group_approval_without_the_authority_is_refused_and_audited(api, db, folded):
    """The group route refuses APPROVE_CUSTOMIZATION exactly as the single route does:
    the denial is audited and committed before the request aborts (code review, #229)."""
    review, a, b = folded
    assert _group_post(api, review, [a, b], [0, 0],
                       kind="APPROVE_CUSTOMIZATION").status_code == 403
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "authz.permission_denied",
        M.AuditEvent.entity_id == review.id)).scalars().first()
    assert event is not None
    assert event.after_state["permission"] == P.LEGAL_APPROVE_CUSTOMIZATION
    assert _recount(db, review)["decided"] == 0


# ============================================================ the stage, step by step
def _stage(api, review):
    body = api.get(f"{V1}/reviews/{review.id}/progress").json()["data"]
    return body["stage"], body["outcome"], body["next"]["who"]


def test_the_stage_follows_the_review_from_sent_to_complete_and_back(api, db, owner, mixed):
    review, points, reviewer = mixed
    assert _stage(api, review) == ("WITH_LEGAL", None, "reviewer")
    for ev in points:
        _decide(api, ev, "ACCEPT_DEVIATION")
    assert _stage(api, review) == ("CONTRACT_DECISION_PENDING", None, "reviewer")
    _outcome(api, review, "ON_HOLD")
    assert _stage(api, review) == ("CONTRACT_DECISION_PENDING", "ON_HOLD", "reviewer")
    _outcome(api, review, "SIGN_AS_IS")
    assert _stage(api, review) == ("COMPLETE", "SIGN_AS_IS", "owner")
    # a late change request: every point still decided, the contract decision is due again
    _decide(api, points[0], "REJECT")
    assert _stage(api, review) == ("CONTRACT_DECISION_PENDING", None, "reviewer")
    # an escalation reopens with a point to decide again
    sign_in(api, db, owner)
    api.post(f"{V1}/findings/{points[1].finding_id}/escalate", json={"reason": "new"})
    assert _stage(api, review) == ("REOPENED", None, "reviewer")
    sign_in(api, db, reviewer)
    _decide(api, points[1], "REQUEST_CLARIFICATION")
    assert _stage(api, review)[0] == "WAITING_FOR_CLARIFICATION"


def test_an_unsent_review_waits_on_its_owner(api, db, owner, requirement_version):
    review = make_review_for(db, owner)
    review.status = E.ReviewStatus.LEGAL_REVIEW
    _points(db, review, requirement_version, 2)
    sign_in(api, db, owner)
    body = api.get(f"{V1}/reviews/{review.id}/progress").json()["data"]
    assert (body["stage"], body["to_decide"], body["next"]["who"]) == ("NOT_SENT", 2, "owner")


def test_points_still_to_decide_lead_over_a_pending_clarification(api, db, mixed):
    """The client's answer leads only once nothing else waits on the reviewer."""
    review, points, _ = mixed
    _decide(api, points[0], "REQUEST_CLARIFICATION")
    body = api.get(f"{V1}/reviews/{review.id}/progress").json()["data"]
    assert (body["stage"], body["to_decide"], body["clarification"]) == ("WITH_LEGAL", 4, 1)


def test_an_archived_contract_offers_no_contract_decision_and_says_why(api, db, mixed, owner):
    """QA-022: `ready` stayed true on a RESOLVED review of an archived contract, so the
    form was offered and every attempt answered with a misleading 'someone decided'."""
    review, points, reviewer = mixed
    for ev in points:
        assert _decide(api, ev, "ACCEPT_DEVIATION").status_code == 201
    state = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]
    assert state["ready"] is True and state["read_only"] is None
    sign_in(api, db, owner)
    assert api.post(f"{V1}/contracts/{review.contract_id}/archive").status_code == 200
    sign_in(api, db, reviewer)
    state = api.get(f"{V1}/reviews/{review.id}/outcome").json()["data"]
    assert state["ready"] is False and "archived" in state["read_only"]
    refused = _outcome(api, review)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "REVIEW_READ_ONLY"

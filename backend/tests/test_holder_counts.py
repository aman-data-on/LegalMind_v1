"""Batch 1 (c)/(e): "yours" means held by me, never "may decide"; the final contract
waits on open points too. Synthetic fixtures; no legal conclusion is asserted."""

from __future__ import annotations

from datetime import UTC, datetime

from legalmind.api.routers import negotiation as N
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import sign_in
from tests.test_todo import _todo, _user, world  # noqa: F401  (fixture)
from tests.test_version_comparison import V1


def _counts(api, db, user, contract_id):
    sign_in(api, db, user)
    r = api.get(f"{V1}/contracts/{contract_id}")
    assert r.status_code == 200, r.text
    return r.json()["data"]["counts"]


def _decide(api, db, user):
    return [i for i in _todo(api, db, user) if i["kind"] == "decide"]


def test_a_review_assigned_to_a_colleague_is_not_yours(api, db, world):
    deal = world["review"].contract_id                  # assigned to a, not b
    a, b = _counts(api, db, world["a"], deal), _counts(api, db, world["b"], deal)
    assert a["points_open"] == b["points_open"] == a["points_for_me"] >= 1
    assert b["points_for_me"] == 0
    assert len(_decide(api, db, world["a"])) == 1
    assert _decide(api, db, world["b"]) == []


def test_an_escalated_review_nobody_holds_is_every_lawyers(api, db, world):
    world["sent"].revoked_at = datetime.now(UTC)        # nobody assigned …
    db.add(M.Escalation(finding_id=world["finding"].id, raised_by=world["owner"].id,
                        reason="please look"))          # … but escalated: with Legal
    db.flush()
    deal = world["review"].contract_id
    for lawyer in (world["a"], world["b"]):
        n = _counts(api, db, lawyer, deal)
        assert n["points_for_me"] == n["points_open"] >= 1
        assert len(_decide(api, db, lawyer)) == 1


def test_the_review_list_says_which_are_yours(api, db, world):
    rid = str(world["review"].id)
    for lawyer, yours in ((world["a"], True), (world["b"], False)):
        sign_in(api, db, lawyer)
        items = api.get(f"{V1}/reviews", params={"with_me": "true"}).json()["data"]
        [row] = [i for i in items if i["id"] == rid]     # the team view is unchanged
        assert row["yours"] is yours


def test_holder_changes_count_only_for_the_holder():
    holder_row = {"answer": None, "route": N.negotiation.HOLDER}
    assert N._mine(holder_row, can_decide=True, holds=True, can_answer=True)
    assert not N._mine(holder_row, can_decide=True, holds=False, can_answer=True)
    owner_row = {"answer": None, "route": N.negotiation.OWNER}
    assert not N._mine(owner_row, can_decide=True, holds=False, can_answer=True)


def test_prepare_final_waits_on_open_points(api, db, seeded, monkeypatch):
    from legalmind.api.routers import todo

    owner = _user(db, P.ROLE_USER)
    c = M.Contract(owner_id=owner.id, name="Deal", status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    stage = {"stage": "CLIENT_RETURNED", "since": datetime.now(UTC).isoformat(), "days": 0}
    monkeypatch.setattr(todo, "negotiation_stages", lambda g, cs: {x.id: stage for x in cs})
    answered = {"changes_total": 4, "changes_left": 0, "changes_left_for_me": 0,
                "changes_ours": 0}
    done = {"points_open": 0, "points_waiting": 0, "sent_to_legal": False}
    for counts, kinds in (({**answered, **done}, ["prepare_final"]),
                          ({**answered, **done, "points_open": 3}, ["client_returned"]),
                          ({**answered, **done, "points_open": 3, "sent_to_legal": True}, []),
                          # D3: a point waiting on the client keeps the final contract back
                          ({**answered, **done, "points_waiting": 1}, ["client_returned"]),
                          (answered, ["client_returned"])):          # absent: closed
        monkeypatch.setattr(todo, "deal_counts", lambda g, cs, n=counts: {x.id: n for x in cs})
        assert [i["kind"] for i in _todo(api, db, owner)] == kinds


def test_counts_say_whether_the_review_is_with_legal(api, db, world):
    deal = world["review"].contract_id
    n = _counts(api, db, world["owner"], deal)
    assert n["sent_to_legal"] is True and n["points_waiting"] == 0
    world["sent"].revoked_at = datetime.now(UTC)          # withdrawn: not with Legal
    db.flush()
    assert _counts(api, db, world["owner"], deal)["sent_to_legal"] is False


def _orphan_check(api, db, world):
    deal = world["review"].contract_id
    for lawyer in (world["b"],):                         # never assigned: now holds it
        n = _counts(api, db, lawyer, deal)
        assert n["points_for_me"] == n["points_open"] >= 1
        assert len(_decide(api, db, lawyer)) == 1


def test_a_suspended_assignee_leaves_the_review_with_every_lawyer(api, db, world):
    world["a"].status = E.UserStatus.SUSPENDED
    db.flush()
    _orphan_check(api, db, world)


def test_an_assignee_who_lost_legal_decision_leaves_it_with_every_lawyer(api, db, world):
    roles = db.query(M.UserRole).join(
        M.RolePermission, M.RolePermission.role_id == M.UserRole.role_id).join(
        M.Permission, M.Permission.id == M.RolePermission.permission_id).filter(
        M.UserRole.user_id == world["a"].id, M.Permission.name == P.LEGAL_DECISION).all()
    assert roles
    for row in roles:
        db.delete(row)
    db.flush()
    _orphan_check(api, db, world)


def test_the_contract_decision_is_the_holders(api, db, world):
    world["review"].status = E.ReviewStatus.RESOLVED
    db.flush()
    assert any(i["kind"] == "contract_decision" for i in _todo(api, db, world["a"]))
    assert all(i["kind"] != "contract_decision" for i in _todo(api, db, world["b"]))

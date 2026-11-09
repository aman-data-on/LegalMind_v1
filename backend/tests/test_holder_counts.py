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
    for counts, sent, kinds in (({**answered, "points_open": 0}, False, ["prepare_final"]),
                                ({**answered, "points_open": 3}, False, ["client_returned"]),
                                ({**answered, "points_open": 3}, True, []),
                                (answered, False, ["client_returned"])):   # absent: closed
        monkeypatch.setattr(todo, "deal_counts", lambda g, cs, n=counts: {x.id: n for x in cs})
        monkeypatch.setattr(todo, "_points_with_legal", lambda db, contract, s=sent: s)
        assert [i["kind"] for i in _todo(api, db, owner)] == kinds

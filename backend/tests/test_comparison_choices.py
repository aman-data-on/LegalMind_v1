"""Diff-Talk's drafting choices, kept by LegalMind — AB-81 / `AM-136` (2026-10-13).

One row per difference per pair, shared and last-writer-wins (r1, r5); read by anyone
who can read both sides, written only by the owner of every stored side (r3, r4); gone
with a deleted document (r6); and the read served by the pair index (r1) — the owner
asked for SQL that holds up at scale.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text

from legalmind.analysis import document_comparison as dc
from legalmind.db import models as M
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_document_comparison import V1, _contract
from tests.test_version_comparison import _version

URL = f"{V1}/comparisons/choices"
A = "CHANGED|11111111-1111-1111-1111-111111111111|22222222-2222-2222-2222-222222222222"
B = "ADDED||33333333-3333-3333-3333-333333333333#2"


def _pair(db, owner):
    ours = _version(db, _contract(db, owner, "MSA"), 1, [("1", "Fees", "1. Fees are due.")])
    theirs = _version(db, _contract(db, owner, "MSA"), 1, [("1", "Fees", "1. Fees due.")])
    return str(ours.id), str(theirs.id)


def _rows(db):
    return db.scalar(select(func.count()).select_from(M.ComparisonChoice))


@pytest.fixture
def owner(api, db, seeded):
    user = make_user(db)
    user.name = "Aman"
    grant_role(db, user, P.ROLE_USER)
    sign_in(api, db, user)
    return user


def test_choices_are_kept_shared_and_replaced_never_duplicated(api, db, owner):
    left, right = _pair(db, owner)
    r = api.patch(URL, json={"left": left, "right": right, "choices": {A: "ours", B: "theirs"}})
    assert r.status_code == 200, r.text
    assert {k: v["choice"] for k, v in r.json()["data"].items()} == {A: "ours", B: "theirs"}
    api.patch(URL, json={"left": left, "right": right, "choices": {A: "theirs"}})
    body = api.get(URL, params={"left": left, "right": right}).json()["data"]
    assert body["can_choose"] is True
    assert body["choices"][A]["choice"] == "theirs"              # replaced, not added
    assert body["choices"][A]["decided_by"] == "Aman" and body["choices"][A]["decided_by_me"]
    assert _rows(db) == 2
    # The pair is ordered: the same two documents the other way round are another pair.
    assert api.get(URL, params={"left": right, "right": left}).json()["data"]["choices"] == {}


def test_a_website_side_is_one_pair_not_a_new_row_each_time(api, db, owner):
    """NULLS NOT DISTINCT: without it a website side (a NULL version id) let the same
    choice be stored twice."""
    _, right = _pair(db, owner)
    for choice in ("ours", "theirs", "ours"):
        r = api.patch(URL, json={"left": "TOS-leapswitch", "right": right, "choices": {A: choice}})
        assert r.status_code == 200, r.text
    assert _rows(db) == 1


def test_a_reader_who_may_not_write_sees_the_choices_and_cannot_change_them(api, db, seeded):
    """AB-12: a Department Lead reads the department's deals and writes none of them."""
    sales = M.Department(code="SALES", name="Sales")
    db.add(sales)
    db.flush()
    aman, neha = make_user(db), make_user(db)
    aman.name, neha.name = "Aman", "Neha"
    aman.department_id = neha.department_id = sales.id
    grant_role(db, aman, P.ROLE_USER)
    grant_role(db, neha, P.ROLE_DEPARTMENT_LEAD)
    db.flush()
    left, right = _pair(db, aman)
    sign_in(api, db, aman)
    api.patch(URL, json={"left": left, "right": right, "choices": {A: "ours"}})
    sign_in(api, db, neha)
    body = api.get(URL, params={"left": left, "right": right}).json()["data"]
    assert body["can_choose"] is False
    assert body["choices"][A] | {"updated_at": None} == {
        "choice": "ours", "decided_by": "Aman", "decided_by_me": False, "updated_at": None}
    r = api.patch(URL, json={"left": left, "right": right, "choices": {A: "theirs"}})
    assert r.status_code == 404, r.text                         # owner-scoped write
    assert db.scalar(select(M.ComparisonChoice.choice)) == "ours"


def test_a_document_the_caller_cannot_read_is_not_found_for_reading_or_writing(
        api, db, seeded, owner):
    left, right = _pair(db, make_user(db))                       # someone else's
    assert api.get(URL, params={"left": left, "right": right}).status_code == 404
    r = api.patch(URL, json={"left": left, "right": right, "choices": {A: "ours"}})
    assert r.status_code == 404
    assert _rows(db) == 0


def test_deleting_a_document_deletes_its_choices(api, db, owner):
    left, right = _pair(db, owner)
    api.patch(URL, json={"left": left, "right": right, "choices": {A: "ours", B: "ours"}})
    contract_id = db.get(M.DocumentVersion, uuid.UUID(right)).contract_id
    db.execute(text("DELETE FROM contracts WHERE id = :id"), {"id": contract_id})
    assert _rows(db) == 0                                        # CASCADE, r6


@pytest.mark.parametrize("change", [
    {"choices": {A: "maybe"}},                                   # not a choice
    {"choices": {"Fees": "ours"}},                               # not a difference
    {"choices": {f"CHANGED|{'a' * 120}|{'b' * 120}": "ours"}},   # longer than a key is
    {"choices": {}},                                             # nothing to record
    {"choices": {f"ADDED||{n}": "ours" for n in range(501)}},    # past one request's cap
])
def test_input_that_is_not_a_choice_is_refused(api, db, owner, change):
    left, right = _pair(db, owner)
    r = api.patch(URL, json={"left": left, "right": right} | change)
    assert r.status_code == 422, r.text
    assert _rows(db) == 0


def test_the_same_document_twice_is_refused(api, db, owner):
    left, _ = _pair(db, owner)
    r = api.patch(URL, json={"left": left, "right": left, "choices": {A: "ours"}})
    assert r.status_code == 422 and "two different" in r.text


def test_the_read_is_served_by_the_pair_index(db, owner):
    """`= value` / `IS NULL` per column, never IS NOT DISTINCT FROM — which no index
    serves. With sequential scans off, a query no index can answer still plans a Seq
    Scan, so this fails if the filter ever loses its indexable shape."""
    _, right = _pair(db, owner)
    side = (uuid.UUID(right), None)
    for website in (False, True):
        left = (None, "TOS-leapswitch") if website else (uuid.uuid4(), None)
        stmt = select(M.ComparisonChoice.row_key).where(dc._pair_filter(left, side))
        compiled = stmt.compile(dialect=db.get_bind().dialect,
                                compile_kwargs={"literal_binds": True})
        db.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(r[0] for r in db.execute(text(f"EXPLAIN {compiled}")))
        # An index answers it (the pair's, or the left version's) — never a full scan.
        assert "Index" in plan and "Seq Scan" not in plan, plan


def test_choices_hidden_by_a_website_refresh_do_not_count_against_the_cap(
        api, db, owner, monkeypatch):
    """AB-81 r6: a refreshed website document has new clause ids, so a choice made
    against the earlier copy is kept, never shown and NEVER COUNTED — it counted
    against `PAIR_MAX`, and enough of them blocked every new choice."""
    _, right = _pair(db, owner)
    stale = f"CHANGED|{uuid.uuid4()}|"                   # an id of no CURRENT copy
    assert api.patch(URL, json={"left": "TOS-leapswitch", "right": right,
                                "choices": {stale: "ours"}}).status_code == 200
    monkeypatch.setattr(dc, "PAIR_MAX", 1)
    r = api.patch(URL, json={"left": "TOS-leapswitch", "right": right,
                             "choices": {B: "theirs"}})
    assert r.status_code == 200, r.text
    assert _rows(db) == 2                                  # kept, not deleted


def test_two_website_pages_are_written_only_by_whoever_publishes_positions(
        api, db, owner, seeded):
    """S7 (2026-10-14) — a website-only pair has no owner to scope to and its
    choices are shared by every reader, so `contract.update` alone let anyone
    overwrite them. It is held to `configuration.publish`."""
    pair = {"left": "TOS-leapswitch", "right": "SLA-leapswitch"}
    r = api.patch(URL, json=pair | {"choices": {A: "ours"}})
    assert r.status_code == 403, r.text
    assert api.get(URL, params=pair).json()["data"]["can_choose"] is False
    assert _rows(db) == 0
    lead = make_user(db)
    grant_role(db, lead, P.ROLE_DEPARTMENT_LEAD)
    sign_in(api, db, lead)
    assert api.patch(URL, json=pair | {"choices": {A: "ours"}}).status_code == 200
    assert api.get(URL, params=pair).json()["data"]["can_choose"] is True

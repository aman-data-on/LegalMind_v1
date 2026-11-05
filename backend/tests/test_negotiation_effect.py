"""What a client change does for us, and who accepts it (`AM-299`/`AM-301`, the manager's
request 2026-11-04): Better for us / No change for us are the deal owner's to accept,
together if they like, each recorded with who and why; Worse for us — and anything
unmeasured or unclear — goes to Legal. Synthetic wording only; no client is named.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from legalmind.analysis import negotiation as N
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import audit
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import (
    LIAB,
    _contract,
    _first,
    _pair,
    _review,
    _url,
    owner,  # noqa: F401 — fixture
)
from tests.test_version_comparison import _version

STD = {"preferred": 12, "unit": "MONTHS", "basis": "FEES_PAID", "scope_key": "AGGREGATE"}


def _cap(months, basis="FEES_PAID", party="both", unit="MONTHS", scope="AGGREGATE"):
    return {"cap_value": months, "cap_unit": unit, "cap_basis": basis, "scope": scope,
            **({"cap_party": party} if party else {})}


@pytest.mark.parametrize(("actual", "ours"), [
    (_cap(6), True),                                         # the manager's example
    (_cap(6, party=None), False),                            # party not read (AM-314)
    (_cap(12), False),                                       # same basis, equal: a MATCH
    (_cap(18), False),
    (_cap(6, "FEES_PAID_FOR_AFFECTED_SERVICES"), True),      # AM-301, never worse
    (_cap(12, "FEES_PAID_FOR_AFFECTED_SERVICES"), True),     # ≤, the dominance itself
    (_cap(13, "FEES_PAID_FOR_AFFECTED_SERVICES"), False),
    (_cap(6, None), False),                                  # basis not read
    (_cap(6, "FEES_RECEIVED"), False),                       # any other basis
    (_cap(6, party="ours"), False),                          # one party (AM-239 r2, §9)
    (_cap(6, party="theirs"), False),
    (_cap(0.5, unit="YEARS"), False),                        # not converted here
    (_cap(6, scope="DATA_BREACH"), False),
    (_cap(None), False),                                     # unlimited / unread
])
def test_a_lower_cap_is_ours_only_where_measured_so(actual, ours):
    assert N.lower_cap_in_our_favour("LIABILITY-MSA-001", STD, actual) is ours


def test_a_cap_protecting_the_customer_only_or_unread_is_never_ours():
    """`AM-314` (owner 2026-11-05, rule 15): a lower cap limiting only the customer's
    liability, or one whose party is not read, goes to a person — on every path: the
    negotiation/publish predicate, the evaluator's favourable rule and the playbook."""
    from legalmind.evaluation.rule_config import in_our_favour
    std = {**STD, "mutual": True, "favourable_direction": "LOWER"}
    for party in ("theirs", None):
        assert not N.lower_cap_in_our_favour("LIABILITY-MSA-001", STD, _cap(6, party=party))
        assert not in_our_favour(6, "MONTHS", std, party)
    assert in_our_favour(6, "MONTHS", std, "both")
    assert N.lower_cap_in_our_favour("LIABILITY-MSA-001", STD, _cap(6))


def test_the_dominance_is_one_way_and_only_for_the_declared_standards():
    """Total fees against an affected-services standard is never read as ours, and no
    other cap standard is read at all — a direction is declared, never inferred."""
    affected = {**STD, "basis": "FEES_PAID_FOR_AFFECTED_SERVICES"}
    assert not N.lower_cap_in_our_favour("LIABILITY-MSA-001", affected, _cap(6))
    assert not N.lower_cap_in_our_favour("LIAB-OTHER-001", STD, _cap(6))


def test_effect_follows_the_route_and_fails_closed():
    assert [N.effect_for_us(r) for r in (N.FAVOUR, N.OWNER, N.HOLDER, "anything")] \
        == ["POSITIVE", "NEUTRAL", "NEGATIVE", "NEGATIVE"]


MATCH = (0, E.FindingClassification.MATCH, E.RuleOutcome.ACCEPTABLE)
FAVOURED = (0, E.FindingClassification.DEVIATION, E.RuleOutcome.ACCEPTABLE)


@pytest.mark.parametrize(("findings", "effect"), [
    ([MATCH], "NEUTRAL"),                       # still matches our standard
    ([FAVOURED], "POSITIVE"),                   # AM-239 accepted it in our favour
    ([], "NEGATIVE"),                           # nothing measured it (or not yet)
    ([(0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)], "NEGATIVE"),
    ([(0, E.FindingClassification.MISSING, E.RuleOutcome.UNACCEPTABLE)], "NEGATIVE"),
    ([(0, E.FindingClassification.CONFLICT, E.RuleOutcome.NOT_APPLICABLE)], "NEGATIVE"),
    ([(0, E.FindingClassification.UNABLE_TO_EVALUATE, E.RuleOutcome.NOT_APPLICABLE)],
     "NEGATIVE"),
    ([MATCH, (0, E.FindingClassification.DEVIATION, E.RuleOutcome.UNACCEPTABLE)],
     "NEGATIVE"),                               # one standard worse is worse
])
def test_effect_for_us_from_what_the_engine_measured(db, owner, findings, effect):
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped.", "9. Liability is capped at fees.")
    _review(db, v2, findings)
    change = N.changes(db, c, v1, v2, legal_position=True)["changes"][0]
    assert change["effect_for_us"] == effect


def test_a_match_that_lost_a_standard_or_carries_a_risk_reason_is_worse(db, owner):
    """A standard that measured our clause and no longer measures theirs is unclear;
    a sentence code reads as moving risk onto us (`AM-224`) is worse — both NEGATIVE."""
    c = _contract(db, owner)
    v1, v2 = _pair(db, c, "9. Liability is capped.", "9. Liability is capped at fees.")
    _review(db, v1, [MATCH, MATCH])
    _review(db, v2, [MATCH])
    assert N.changes(db, c, v1, v2, legal_position=True)["changes"][0]["effect_for_us"] \
        == "NEGATIVE"
    c2 = _contract(db, owner)
    w1, w2 = _pair(db, c2, "9. Liability is capped.",
                   "9. Liability is capped. LeapSwitch shall indemnify the Customer for "
                   "all losses.")
    _review(db, w2, [MATCH])
    change = N.changes(db, c2, w1, w2, legal_position=True)["changes"][0]
    assert change["triage"]["reasons"] and change["effect_for_us"] == "NEGATIVE"


def test_summary_counts_each_effect(db, owner):
    c = _contract(db, owner)
    _version(db, c, 1, [(*LIAB, "9. Liability is capped."),
                        ("10", "Fees", "10. The Customer\u2019s fees \u2014 monthly.")])
    _version(db, c, 2, [(*LIAB, "9. Liability is uncapped."),
                        ("10", "Fees", "10. The Customer's fees - monthly.")])
    v1, v2 = _versions(db, c)
    summary = N.changes(db, c, v1, v2, legal_position=True)["summary"]
    assert (summary["positive"], summary["neutral"], summary["negative"]) == (0, 1, 1)


# ------------------------------------------------------------------ routing (API)
def _three(db, owner):
    """A returned copy with one change of each effect: 9 better, 10 the same, 11 worse."""
    c = _contract(db, owner)
    _version(db, c, 1, [("9", "Liability", "9. Liability is capped."),
                        ("10", "Fees", "10. Fees are monthly."),
                        ("11", "Notices", "11. Notices by post.")])
    v2 = _version(db, c, 2, [("9", "Liability", "9. Liability is capped lower."),
                             ("10", "Fees", "10. Fees are monthly in advance."),
                             ("11", "Notices", "11. Notices by fax.")])
    _review(db, v2, [FAVOURED, (1, *MATCH[1:])])
    rows = {ch["clause"]["number"]: ch for ch in _changes_for(db, c)}
    return c, rows


def _versions(db, c):
    return db.scalars(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == c.id).order_by(M.DocumentVersion.version_number))


def _changes_for(db, c):
    v1, v2 = _versions(db, c)
    return N.changes(db, c, v1, v2, legal_position=True)["changes"]


def test_the_owner_accepts_better_and_same_one_by_one_with_the_effect_as_reason(
        api, db, owner):
    c, rows = _three(db, owner)
    assert {n: r["effect_for_us"] for n, r in rows.items()} \
        == {"9": "POSITIVE", "10": "NEUTRAL", "11": "NEGATIVE"}
    for n, said in (("9", "Better for us"), ("10", "No change for us")):
        r = api.post(_url(c, rows[n]["row_key"]), json=_first("accept_theirs"))
        assert r.status_code == 201, r.text
        assert (r.json()["data"]["answer"]["reason"],
                r.json()["data"]["answer"]["decided_by"]) == (said, "Owner")
    worse = api.post(_url(c, rows["11"]["row_key"]), json=_first("accept_theirs"))
    assert worse.status_code == 403
    assert worse.json()["error"]["code"] == "LEGAL_DECISION_REQUIRED"


def test_accept_together_is_one_write_all_or_none_and_audited(api, db, owner):
    c, rows = _three(db, owner)
    url = f"{_url(c)}/accept"
    # a worse-for-us row among them refuses the whole request
    mixed = api.post(url, json={"effect": "POSITIVE",
                                "row_keys": [rows["9"]["row_key"], rows["11"]["row_key"]]})
    assert mixed.status_code == 422, mixed.text
    wrong = api.post(url, json={"effect": "NEUTRAL", "row_keys": [rows["9"]["row_key"]]})
    assert wrong.status_code == 422
    never = api.post(url, json={"effect": "NEGATIVE", "row_keys": [rows["11"]["row_key"]]})
    assert never.status_code == 422
    assert db.scalar(select(func.count()).select_from(M.ComparisonChoice)) == 0
    for effect, n, said in (("POSITIVE", "9", "Better for us"),
                            ("NEUTRAL", "10", "No change for us")):
        done = api.post(url, json={"effect": effect, "row_keys": [rows[n]["row_key"]]})
        assert done.status_code == 201, done.text
        [row] = done.json()["data"]["rows"]
        assert (row["answer"]["answer"], row["answer"]["reason"]) == ("accept_theirs", said)
    assert api.post(url, json={"effect": "POSITIVE",
                               "row_keys": [rows["9"]["row_key"]]}).status_code == 409
    events = db.scalars(select(M.AuditEvent).where(
        M.AuditEvent.action == audit.NEGOTIATION_ACCEPTED_BY_EFFECT)).all()
    assert sorted(e.after_state["effect"] for e in events) == ["NEUTRAL", "POSITIVE"]
    assert all(e.actor_id == owner.id for e in events)


def test_a_legal_holder_reopens_an_owner_acceptance(api, db, owner):
    """The owner's acceptance is a row, never the last word: a holder answers again and
    both stay in the history, who and why (append-only, `AM-253`)."""
    c, rows = _three(db, owner)
    key = rows["10"]["row_key"]
    assert api.post(f"{_url(c)}/accept",
                    json={"effect": "NEUTRAL", "row_keys": [key]}).status_code == 201
    team = M.Department(code=f"T{uuid.uuid4().hex[:6]}", name="Team")
    db.add(team)
    db.flush()
    holder = make_user(db)
    holder.name = "Counsel"
    grant_role(db, holder, P.ROLE_DEPARTMENT_LEAD)
    grant_role(db, holder, P.ROLE_LEGAL_DECISION_AUTHORITY)
    owner.department_id = holder.department_id = team.id
    db.flush()
    sign_in(api, db, holder)
    r = api.post(_url(c, key), json={"answer": "keep_ours", "expected_version": 1,
                                     "reason": "reopened by Legal"})
    assert r.status_code == 201, r.text
    assert [(h["answer"], h["decided_by"], h["reason"]) for h in r.json()["data"]["history"]] \
        == [("accept_theirs", "Owner", "No change for us"),
            ("keep_ours", "Counsel", "reopened by Legal")]

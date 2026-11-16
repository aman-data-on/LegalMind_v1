"""Priyen's rule (owner "change and update", 2026-11-16): better for us or no change for
us is accepted without a Legal Decision — automatically, recorded, reopenable by Legal;
only worse (and anything unsure or never conceded) goes to Legal. Synthetic wording only.
"""
from __future__ import annotations

import glob
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from legalmind.analysis import negotiation as N
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.user_status import ACCEPTABLE, REQUIRES_MODIFICATION, point_effect
from legalmind.evaluation.rule_config import (
    APPROVED_FAVOURABLE_RULE,
    APPROVED_ZERO_TOLERANCE_RULE,
    OWNER_EFFECT_RULE,
)
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_negotiation import _url, owner  # noqa: F401 — fixture
from tests.test_negotiation_effect import _three

C = E.FindingClassification
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("cls", "word", "effect"), [
    (C.DEVIATION, ACCEPTABLE, "POSITIVE"),           # accepted in our favour (AM-239)
    (C.MATCH, ACCEPTABLE, "NEUTRAL"),
    (C.DEVIATION, REQUIRES_MODIFICATION, "NEGATIVE"),
    (C.MISSING, "MISSING", "NEGATIVE"),
    (C.UNABLE_TO_EVALUATE, "NEEDS_DECISION", "NEGATIVE"),   # unsure: fail closed
    (C.CONFLICT, "NEEDS_DECISION", "NEGATIVE"),
])
def test_each_point_says_what_it_does_for_us(cls, word, effect):
    assert point_effect(cls, word) == effect


@pytest.mark.parametrize(("effect", "auto", "accepted"), [
    ("POSITIVE", True, True), ("NEUTRAL", True, True),
    ("FALLBACK", True, False),          # a concession below our paper: the owner's call
    ("NEGATIVE", True, False),
    ("POSITIVE", False, False),         # an older snapshot: the rule it was made under
])
def test_only_good_and_neutral_are_accepted_automatically(effect, auto, accepted):
    got = N.auto_answer(None, effect, auto)
    assert (got is not None) is accepted
    if got:
        assert (got["answer"], got["auto"], got["version_number"]) \
            == ("accept_theirs", True, 0)


def test_a_persons_answer_always_beats_the_rule():
    mine = {"answer": "keep_ours"}
    assert N.auto_answer(mine, "POSITIVE", True) is mine


def test_every_standard_carries_the_new_rule_verbatim_and_the_rule_changes_no_outcome():
    files = [json.loads(Path(f).read_text())
             for f in glob.glob(str(ROOT / "config/company_standards/*.json"))]
    rules = [d["legal_rule"]["configuration"] for d in files if "legal_rule" in d]
    assert rules and all(r == OWNER_EFFECT_RULE for r in rules)
    # the Rule Outcome keys are the favourable form's, unchanged: a deviation is still
    # UNACCEPTABLE except on a declared favourable side
    assert {k: OWNER_EFFECT_RULE[k] for k in APPROVED_FAVOURABLE_RULE} \
        == APPROVED_FAVOURABLE_RULE
    assert OWNER_EFFECT_RULE["deviation_outcome"] \
        == APPROVED_ZERO_TOLERANCE_RULE["deviation_outcome"] == "UNACCEPTABLE"


def test_the_never_concede_list_starts_empty_for_legal_to_supply():
    cfg = json.loads((ROOT / "config/never_concede.json").read_text())
    assert cfg["requirement_codes"] == [] and "LEGAL TO SUPPLY" in cfg["_about"]


def _snapshot_rule(db, review, configuration):
    rv = db.scalars(select(M.RequirementVersion)).first()
    who = review.created_by
    std = M.CompanyStandardVersion(requirement_version_id=rv.id, version_number=98,
                                   configuration={}, created_by=who)
    mapping = M.MappingRuleVersion(requirement_version_id=rv.id, version_number=98,
                                   rules={}, created_by=who)
    rules = M.EvaluationRuleVersion(requirement_version_id=rv.id, version_number=98,
                                    evaluator_type=E.EvaluatorType.NUMERIC_COMPARISON,
                                    rules={}, created_by=who)
    legal = M.LegalRuleVersion(requirement_version_id=rv.id, version_number=98,
                               rule_type=E.RuleType.THRESHOLD,
                               configuration=configuration, created_by=who)
    db.add_all([std, mapping, rules, legal])
    db.flush()
    db.add(M.ConfigurationSnapshotItem(
        snapshot_id=review.configuration_snapshot_id, requirement_version_id=rv.id,
        company_standard_version_id=std.id, mapping_rule_version_id=mapping.id,
        evaluation_rule_version_id=rules.id, legal_rule_version_id=legal.id))
    db.flush()


@pytest.mark.parametrize(("configuration", "applies"), [
    (OWNER_EFFECT_RULE, True),
    (APPROVED_FAVOURABLE_RULE, False),          # a Review made before the rule
    (APPROVED_ZERO_TOLERANCE_RULE, False),
])
def test_the_rule_applies_only_to_a_snapshot_that_pins_it(db, owner, configuration,
                                                          applies):
    c, _ = _three(db, owner)
    review = db.scalars(select(M.Review).where(M.Review.contract_id == c.id)).one()
    assert N.auto_rule(db, review) is False             # nothing pinned: fail closed
    _snapshot_rule(db, review, configuration)
    assert N.auto_rule(db, review) is applies
    assert N.auto_rule(db, None) is False


def test_good_and_neutral_accepted_automatically_worse_to_legal_legal_reopens(
        api, db, owner, monkeypatch):
    monkeypatch.setattr(N, "auto_rule", lambda db, review: True)
    c, rows = _three(db, owner)
    said = {n: (r["effect_for_us"], (r["answer"] or {}).get("auto")) for n, r in rows.items()}
    assert said == {"9": ("POSITIVE", True), "10": ("NEUTRAL", True),
                    "11": ("NEGATIVE", None)}
    assert rows["9"]["answer"]["decided_by"] == N.AUTO_BY
    assert db.scalar(select(M.ComparisonChoice.id).limit(1)) is None   # nothing written
    # the deal owner cannot accept the worse one
    worse = api.post(_url(c, rows["11"]["row_key"]),
                     json={"answer": "accept_theirs", "expected_version": 0})
    assert worse.status_code == 403
    # Legal reopens the automatic acceptance by answering the row, with a reason
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
    key = rows["10"]["row_key"]
    no_reason = api.post(_url(c, key), json={"answer": "keep_ours", "expected_version": 0})
    assert no_reason.status_code == 422
    r = api.post(_url(c, key), json={"answer": "keep_ours", "expected_version": 0,
                                     "reason": "reopened by Legal"})
    assert r.status_code == 201, r.text
    assert (r.json()["data"]["answer"]["answer"], r.json()["data"]["answer"]["decided_by"]) \
        == ("keep_ours", "Counsel")


def test_a_never_concede_point_goes_to_legal_even_when_better(db, owner, monkeypatch):
    monkeypatch.setattr(N, "auto_rule", lambda db, review: True)
    class Every(frozenset):                 # Legal lists every code the test makes
        def __and__(self, other):
            return set(other)
    monkeypatch.setattr(N, "NEVER_CONCEDE_CODES", Every())
    _, rows = _three(db, owner)
    assert (rows["9"]["effect_for_us"], rows["9"]["route_reason"], rows["9"]["answer"]) \
        == ("NEGATIVE", N.NEVER_CONCEDE, None)

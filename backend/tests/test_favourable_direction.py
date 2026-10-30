"""AM-239 (AB-139, owner 2026-10-30): a deviation in LeapSwitch's favour.

ACCEPTABLE only under the approved favourable rule, only on paper where LeapSwitch is the
provider, never where a Counsel check is declared — and it stays a DEVIATION (rule 14).
Synthetic clauses; every expectation names a ratified standard by code (rule 21).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.api.angles import ACCEPT_FAVOURABLE, FAVOURABLE, action
from legalmind.db import models as M
from legalmind.domain.enums import FindingClassification as C
from legalmind.domain.enums import RuleOutcome as R
from legalmind.domain.user_status import ACCEPTABLE, REQUIRES_MODIFICATION, user_status
from legalmind.evaluation.rule_config import (
    APPROVED_FAVOURABLE_RULE,
    APPROVED_RULES,
    in_our_favour,
)
from tests.legal_regression.test_legal_regression import _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

LOWER = {"favourable_direction": "LOWER", "preferred": 21, "unit": "DAYS"}
HIGHER = {"favourable_direction": "HIGHER", "preferred": 2, "unit": "PERCENT_PER_MONTH"}


def test_the_side_is_the_one_the_standard_names_and_never_inferred():
    assert in_our_favour(10, "DAYS", LOWER) and not in_our_favour(30, "DAYS", LOWER)
    assert not in_our_favour(21, "DAYS", LOWER)                      # a match is no favour
    assert in_our_favour(3, "PERCENT_PER_MONTH", HIGHER)
    assert not in_our_favour(10, "DAYS", {**LOWER, "favourable_direction": None})
    assert not in_our_favour(1, "MONTHS", LOWER)                     # another unit: never


def test_working_days_count_only_where_the_answer_cannot_depend_on_conversion():
    assert in_our_favour(5, "WORKING_DAYS", {**LOWER, "preferred": 15})   # <= 10 calendar
    assert not in_our_favour(10, "WORKING_DAYS", {**LOWER, "preferred": 15})


def test_the_favourable_rule_is_the_zero_tolerance_rule_plus_one_key():
    zero, favourable = APPROVED_RULES
    assert favourable == APPROVED_FAVOURABLE_RULE == {**zero, "favourable_outcome": "ACCEPTABLE"}


def test_the_reader_word_follows_an_accepted_deviation_and_nothing_else():
    assert user_status(C.DEVIATION, R.ACCEPTABLE) == ACCEPTABLE
    assert user_status(C.DEVIATION, R.UNACCEPTABLE) == REQUIRES_MODIFICATION
    assert user_status(C.DEVIATION, R.ACCEPTABLE, prohibited=True) != ACCEPTABLE


def _outcome(db, review, code: str):
    return db.execute(
        select(M.Evaluation.classification, M.Evaluation.rule_outcome)
        .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .join(M.RequirementVersion, M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id == review.id, M.Requirement.code == code)).first()


PAYS_IN_TEN = ["8. Payment",
               "8.1 The Customer shall pay each invoice within ten (10) days of the invoice date."]


def test_a_shorter_payment_period_on_our_msa_is_acceptable_and_still_a_deviation(build, db):
    review, _ = _review(build, db, ["PAYMENT-PERIOD-MSA-001"], PAYS_IN_TEN, kind="MSA")
    assert tuple(_outcome(db, review, "PAYMENT-PERIOD-MSA-001")) == (C.DEVIATION, R.ACCEPTABLE)


@pytest.mark.parametrize("kind", ["OTHER", "VENDOR_AGREEMENT"])
def test_the_same_clause_on_paper_whose_role_is_not_established_goes_to_a_person(
        build, db, kind):
    review, _ = _review(build, db, ["PAYMENT-PERIOD-MSA-001"], PAYS_IN_TEN, kind=kind)
    found = _outcome(db, review, "PAYMENT-PERIOD-MSA-001")
    assert found is None or found[1] is not R.ACCEPTABLE


def test_a_favourable_window_with_a_counsel_check_is_never_accepted(build, db):
    clauses = ["8. Payment", "8.3 Invoice disputes must be raised in writing within five (5) "
               "days of the invoice date, failing which the invoice is deemed accepted."]
    review, _ = _review(build, db, ["DISPUTE-WINDOW-MSA-001"], clauses, kind="MSA")
    assert tuple(_outcome(db, review, "DISPUTE-WINDOW-MSA-001")) == (C.DEVIATION,
                                                                     R.UNACCEPTABLE)


def test_the_action_says_accept_or_counsel_never_send_our_wording():
    row = {"classification": "DEVIATION", "code": "PAYMENT-PERIOD-MSA-001", "actual": {},
           "outcome": "ACCEPTABLE"}
    assert action(row, has_wording=True) == ACCEPT_FAVOURABLE
    row = {"classification": "DEVIATION", "code": "DISPUTE-WINDOW-MSA-001",
           "outcome": "UNACCEPTABLE", "document_type": "MSA",
           "actual": {"cap_value": 5, "cap_unit": "DAYS"},
           "standard": {**LOWER, "preferred": 15, "favourable_counsel_check": "s.28(b)"}}
    assert action(row, has_wording=True) == f"{FAVOURABLE}. Counsel confirms it holds: s.28(b)"


def test_a_figure_beside_the_word_invoice_is_never_read_as_a_period_we_accept(build, db):
    """MSA 8.6 (2026-10-30): "inform … 10 days prior to the date of invoice" of a GST
    change was read as a 10-day payment period — and, in our favour, would have been
    accepted. "invoice" alone is no payment sentence (the QA-018 rule)."""
    clauses = ["8. Payment", "8.6 The Customer shall inform Leapswitch at-least 10 days "
               "prior to the date of invoice of any modification to its GST registration."]
    review, _ = _review(build, db, ["PAYMENT-PERIOD-MSA-001"], clauses, kind="MSA")
    found = _outcome(db, review, "PAYMENT-PERIOD-MSA-001")
    assert found is None or found[1] is not R.ACCEPTABLE

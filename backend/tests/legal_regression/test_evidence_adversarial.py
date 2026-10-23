"""Adversarial round (owner, 2026-10-23: "make tests that break your fix, see why, fix
it — the real tests you will face"). Each case is a shape real paper takes that the
evidence-gated fixes could get wrong, in our own synthetic wording (54.6, rule 21)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.domain.document_types import title_type
from legalmind.mapping.engine import Clause
from tests.legal_regression.test_evidence_gated import _read


def _c(*texts: str) -> list[Clause]:
    return [Clause(evidence_id=uuid4(), content=t) for t in texts]


# ------------------------------------------------------------- the title names the type
@pytest.mark.parametrize("lines, expected", [
    # a letterhead above the title — the most common real first line
    (["LeapSwitch Networks Private Limited", "MASTER SERVICES AGREEMENT"], "MSA"),
    (["Ref: LS/2026/114", "Date: 22 October 2026", "PURCHASE ORDER"], "ORDER_FORM"),
    # an amendment names the agreement it amends: it is still an amendment
    (["AMENDMENT NO. 2 TO THE MASTER SERVICES AGREEMENT"], "AMENDMENT"),
    (["ADDENDUM TO NON-DISCLOSURE AGREEMENT"], "AMENDMENT"),
    (["SERVICE ORDER FORM"], "ORDER_FORM"),
    # never a title read from the body
    (["1. Definitions", "1.1 \"Purchase Order\" means an order issued under this MSA."], None),
    # two kinds in one title and no "to": no guess
    (["MASTER SERVICES AGREEMENT AND SERVICE LEVEL AGREEMENT"], None),
    # a combined agreement whose title ends like an NDA's is no NDA
    (["MASTER SERVICES AND CONFIDENTIALITY AGREEMENT"], None),
])
def test_the_title_is_found_where_real_paper_puts_it(lines, expected):
    assert title_type(_c(*lines)) == expected


# ------------------------------------------------------------- periods in other words
@pytest.mark.parametrize("text, value", [
    ("13.2 If the breaching party fails to remedy it within thirty (30) days of notice, "
     "the other may terminate.", 30.0),
    ("13.2 The defaulting party shall cure the same within a period of 15 days.", 15.0),
])
def test_a_cure_period_in_everyday_words_is_read(text, value):
    caps, _ = _read("CURE-PERIOD-MSA-001", text)
    assert [(c.cap_status, c.cap_value) for c in caps] == [("FINITE", value)]


def test_two_cure_periods_in_one_clause_are_never_one():
    caps, _ = _read("CURE-PERIOD-MSA-001",
                    "13.2 A party shall remedy a breach within 30 days of notice, or within "
                    "7 days where the breach is non-payment.")
    assert all(c.cap_status != "FINITE" for c in caps)


def test_a_survival_period_for_something_else_is_not_the_survival():
    """Under "Confidentiality", "afterwards" about support is not a survival period."""
    caps, _ = _read("CONF-SURVIVAL-MSA-001",
                    "11.4 The Vendor will provide technical support during the Term and "
                    "for 2 years afterwards.")
    assert all(c.cap_status != "FINITE" for c in caps)


@pytest.mark.parametrize("blank", ["[●]", "[ ]", "____", "[*]", "[insert]"])
def test_every_kind_of_blank_is_a_blank(blank):
    caps, _ = _read("PAYMENT-PERIOD-MSA-001",
                    f"7.1 Each invoice is payable within {blank} days of the invoice date.")
    assert [(c.cap_status, c.reason) for c in caps] == [("UNKNOWN", "PLACEHOLDER")]


# ------------------------------------------------------------- the same cap, or not
def test_one_partys_cap_is_never_merged_with_the_others():
    caps, _ = _read("LIABILITY-MSA-001",
                    "10.1 The Customer's liability is capped at the amount paid by the "
                    "customer in the preceding 6 months.",
                    "10.2 LeapSwitch's liability is capped at the amount paid by the "
                    "customer in the preceding 6 months.")
    assert len(caps) == 2 or all(c.cap_party in (None, "both") for c in caps)


@pytest.mark.parametrize("footer", ["Page 6", "6 | Confidential", "- 6 -",
                                    "Confidential  Page 6 of 9  Version 3"])
def test_a_footer_figure_is_never_a_second_cap_figure(footer):
    caps, _ = _read("LIABILITY-MSA-001",
                    f"10.1 Liability is capped at the amount paid by the customer in the "
                    f"preceding 6 months\n{footer}")
    assert [(c.cap_status, c.cap_value) for c in caps] == [("FINITE", 6.0)]


# ------------------------------------------------------------- equivalence never flips
def test_remedy_it_does_not_turn_an_exclusion_into_a_cure_period():
    caps, _ = _read("CURE-PERIOD-MSA-001",
                    "13.2 No party is obliged to remedy it within 30 days where the "
                    "failure is caused by a force majeure event.")
    assert all(c.cap_status != "FINITE" or c.cap_value != 30.0 for c in caps)


# ------------------------------------------------- §31.11 shapes, attacked (2026-10-23)
from tests.legal_regression.test_evidence_gated import BY_REFERENCE  # noqa: E402
from tests.legal_regression.test_legal_regression import _findings, _review  # noqa: E402
from tests.test_analysis import build, storage  # noqa: E402,F401


def test_a_po_that_says_it_is_not_under_any_msa_does_not_reference_one(build, db):
    review, _ = _review(build, db, BY_REFERENCE, [
        "PURCHASE ORDER", "1. Order",
        "1.1 This PO is a standalone order and is not subject to any MSA.",
        "7. Payment", "7.1 Payment is due within 21 days of the invoice date."], kind=None)
    found = _findings(db, review)
    assert found["REFERENCE-GOVERNING-MSA-ORDER_FORM-001"]["classification"] == "MISSING"
    assert found["PAYMENT-TERMS-ORDER_FORM-001"]["classification"] == "DEVIATION"


@pytest.mark.parametrize("names_msa, expected", [(True, "MATCH"), (False, "MISSING")])
def test_a_po_silent_on_payment_follows_its_msa_or_misses_it(build, db, names_msa,
                                                             expected):
    lines = ["PURCHASE ORDER", "1. Order",
             "1.1 This PO is issued under the Master Services Agreement dated 1 June "
             "2026." if names_msa else "1.1 The Vendor shall supply the listed items.",
             "2. Delivery", "2.1 Delivery is to the Buyer's data centre."]
    review, _ = _review(build, db, BY_REFERENCE, lines, kind=None)
    assert _findings(db, review)["PAYMENT-TERMS-ORDER_FORM-001"]["classification"] \
        == expected


def test_a_non_payment_heading_is_not_the_payment_terms_section(build, db):
    review, _ = _review(build, db, BY_REFERENCE, [
        "PURCHASE ORDER", "1. Order",
        "1.1 This PO is issued under the Master Services Agreement dated 1 June 2026.",
        "9. Non-payment and suspension",
        "9.1 The Vendor may suspend the Services on 15 days' notice of non-payment."],
        kind=None)
    assert _findings(db, review)["PAYMENT-TERMS-ORDER_FORM-001"]["classification"] \
        == "MATCH"


# ------------------------------------------------- who "the Buyer" is (2026-10-23)
CAP_BY_BUYER = ["10. Limitation of Liability",
                "10.1 The Vendor's liability is capped at the amount paid by the Buyer in "
                "the preceding 6 months."]


def test_on_a_customers_order_the_buyer_is_the_customer(build, db):
    review, _ = _review(build, db, ["LIABILITY-MSA-001"],
                        ["PURCHASE ORDER", *CAP_BY_BUYER], kind=None)
    cap = _findings(db, review)["LIABILITY-MSA-001"]
    assert (cap["classification"], cap["actual"].get("cap_basis")) == (
        "DEVIATION", "FEES_PAID")


def test_on_a_vendor_agreement_the_buyer_is_never_read_as_the_customer(build, db):
    review, _ = _review(build, db, ["LIABILITY-MSA-001"],
                        ["VENDOR AGREEMENT", *CAP_BY_BUYER], kind=None)
    cap = _findings(db, review).get("LIABILITY-MSA-001", {})
    assert cap.get("actual", {}).get("cap_basis") != "FEES_PAID"


def test_a_schedules_payment_heading_is_not_the_orders_payment_section(build, db):
    review, _ = _review(build, db, BY_REFERENCE, [
        "PURCHASE ORDER", "7. Payment", "7.1 Payment is due within 21 days of invoice.",
        "8. Delivery", "8.1 Delivery is to the Buyer's site.",
        "SCHEDULE C - SERVICE CREDITS", "3. Payment of service credits",
        "3.1 Credits are paid against the next invoice."], kind=None)
    payment = _findings(db, review)["PAYMENT-TERMS-ORDER_FORM-001"]
    assert {s for s, _ in payment["cited"]} == {"7", "7.1"}

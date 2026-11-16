"""`AM-311` — a mutual §10 clause does not speak for the rest of the indemnity. STRUCTURAL:
the shape of a template's clause 16 (mutual 16.1, the §10 customer heads 16.2, a one-way
customer indemnity 16.3, a defence for us alone 16.4), in our own synthetic wording
(locked 54.6, rule 21). Only the Constitution's own §10 words are quoted.
"""
from __future__ import annotations

import pytest

from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified  # noqa: F401 — fixture

INDEMNITY = "INDEMNITY-MSA-001"
RATIFIED_AS_IS = {"test_our_msa_customer_only_indemnity_matches",
                  "test_any_indemnity_we_or_each_party_give_is_for_a_person"}


@pytest.fixture
def section_10_mechanism(request, monkeypatch):
    """`AM-380`/`AM-381` r2: our MSA's indemnity standard is customer-only (MSA 16.1). The
    Constitution §10 mutual-framework reading (R-1, `AM-311`) still serves a standard
    without `customer_indemnity_only`; these tests pin it on a copy without the flag."""
    if request.node.originalname in RATIFIED_AS_IS:   # AM-381 r2 tests below
        return
    import tests.test_hard_test_fixes as hard
    real = hard._standard

    def without_flag(code: str) -> dict:
        payload = real(code)
        if code == INDEMNITY:
            payload["configuration"].pop("customer_indemnity_only", None)
        return payload
    monkeypatch.setattr(hard, "_standard", without_flag)


pytestmark = pytest.mark.usefixtures("section_10_mechanism")
MUTUAL = ("16.1 Each Party (the “Indemnifying Party”) shall defend, indemnify and hold "
          "harmless the other Party against third-party claims arising from the "
          "Indemnifying Party's gross negligence or wilful misconduct, or an allegation "
          "that its platform or content infringes a third party's intellectual property "
          "rights.")
HEADS = ["16.2 The Customer shall also indemnify the Provider against claims arising from:",
         "16.2.1 content the Customer provides;",
         "16.2.2 the Customer's unlawful use of the Services;",
         "16.2.3 the conduct of the Customer or its end users;",
         "16.2.4 violations of the Acceptable Use Policy; and",
         "16.2.5 the Customer's breach of applicable law relating to its use or content."]
ONE_WAY = ["16.3 The Customer shall defend, indemnify and hold harmless the Provider and its "
           "officers against all claims and losses arising from:",
           "16.3.1 any breach by the Customer of this Agreement;",
           "16.3.2 any claim connected with the Customer's use of the Services."]
DEFENCE = ("16.4 The Provider shall have the right to participate in the defence of any "
           "such claim at the Customer's expense, and the Customer shall not settle any "
           "claim without the Provider's prior written consent.")


def _indemnity(build, db, *clauses: str) -> dict:
    review, _ = _review(build, db, [INDEMNITY], ["16. Indemnification", *clauses],
                        kind="MSA")
    return _findings(db, review)[INDEMNITY]


def test_the_mutual_section_10_clause_with_its_customer_heads_matches(build, db):
    assert _indemnity(build, db, MUTUAL, *HEADS)["classification"] == "MATCH"


@pytest.mark.parametrize("extra", [[*ONE_WAY, DEFENCE], ONE_WAY, [DEFENCE]])
def test_a_one_way_sub_clause_beside_the_mutual_one_is_a_deviation(build, db, extra):
    found = _indemnity(build, db, MUTUAL, *HEADS, *extra)
    assert found["classification"] == "DEVIATION"
    assert found["actual"]["presence"] == "ONE_SIDED"


def test_the_one_way_finding_names_the_offending_sub_clause(build, db):
    review, _ = _review(build, db, [INDEMNITY],
                        ["16. Indemnification", MUTUAL, *HEADS, *ONE_WAY], kind="MSA")
    found = _findings(db, review)[INDEMNITY]
    assert found["classification"] == "DEVIATION"
    assert "16.3" in {s for s, _ in found["cited"]}


def test_a_defence_given_to_both_sides_is_not_one_sided(build, db):
    both = DEFENCE + (" The Customer shall have the right to participate in the defence "
                      "of any claim against it, and the Provider shall not settle any "
                      "claim without the Customer's prior written consent.")
    assert _indemnity(build, db, MUTUAL, *HEADS, both)["classification"] == "MATCH"


# ------------------------- AM-381 r2: the ratified MSA standard, customer-only (MSA 16.1)
OURS_16_1 = ["16.1 The Customer shall, at its sole cost and expense, defend, indemnify, and "
             "hold harmless Leapswitch, its affiliates, officers, directors, employees, agents, "
             "and subcontractors from and against any and all claims arising out of or "
             "relating to:", *ONE_WAY[1:]]


def test_our_msa_customer_only_indemnity_matches(build, db):
    found = _indemnity(build, db, *OURS_16_1)
    assert found["classification"] == "MATCH", found


@pytest.mark.parametrize("ours", [
    MUTUAL,
    "16.5 Leapswitch shall indemnify the Customer against third-party claims that the "
    "Services infringe a third party's intellectual property rights.",
])
def test_any_indemnity_we_or_each_party_give_is_for_a_person(build, db, ours):
    found = _indemnity(build, db, *OURS_16_1, ours)
    assert (found["classification"], found["actual"]["presence"]) == (
        "DEVIATION", "TOO_BROAD"), found

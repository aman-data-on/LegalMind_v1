"""The negotiation playbook agrees with what a client change does for us (`AM-305`, the
manager's examples, 2026-11-04): our MSA opens at 6 months of the affected services'
fees and 7-day payment; the ratified standards (12 months of total fees, mutual; 21 days)
are how far the deal owner goes without Legal. Every client figure the playbook calls
"within" is Better or No change for us through the real pipeline, and every other one
goes to Legal. Synthetic wording only (rule 21); the standards are the ratified files.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from legalmind.analysis import negotiation, playbook
from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import playbook as read
from legalmind.ingestion.service import ingest_document
from legalmind.security import permissions as P
from tests.conftest import (
    bespoke_role,
    grant,
    grant_role,
    make_review_for,
    make_user,
    sign_in,
)
from tests.legal_regression.test_effect_for_us import AFFECTED, ONE_PARTY, OURS
from tests.legal_regression.test_legal_regression import _docx
from tests.test_analysis import DOCX_MIME, build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified
from tests.test_version_comparison import V1

CAP, PAY = "LIABILITY-MSA-001", "PAYMENT-PERIOD-MSA-001"
PAID = "8.5 Customer shall pay all undisputed invoices within {} days of the invoice date."


ACCOUNT = "3.1 The Customer's account is personal to the Customer."


def _version(build, db, contract, cap, paid, account=ACCOUNT):
    v = ingest_document(db, build.storage, contract_id=contract.id,
                        uploaded_by=build.owner.id,
                        data=_docx(["3. Accounts", account, "8. Payment and Invoicing", paid,
                                    "17. Limitation of Liability", cap]),
                        filename="contract.docx", declared_mime=DOCX_MIME).document_version
    review = M.Review(contract_id=contract.id, document_version_id=v.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    run_analysis(db, review)
    return v, review


def _contract(build, db):
    _ratified(build, CAP)
    _ratified(build, PAY)
    contract = M.Contract(owner_id=build.owner.id, name="Negotiated MSA",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    return contract


def _ours(build, db, contract):
    v = _version(build, db, contract, AFFECTED, PAID.format("seven (7)"))[0]
    v.doc_metadata = {"version_role": "COMPANY_DRAFT"}      # declared ours (AM-317 r4)
    db.flush()
    return v


def _their_change(build, db, contract, ours, number, sentence):
    """The client's version (one clause changed) -> (that change, its single figure)."""
    texts = {"17.2": AFFECTED, "8.5": PAID.format("seven (7)"), number: sentence}
    theirs, review = _version(build, db, contract, texts["17.2"], texts["8.5"])
    [change] = [c for c in negotiation.changes(db, contract, ours, theirs,
                                               legal_position=True)["changes"]
                if c["clause"]["number"] == number]
    code = CAP if number == "17.2" else PAY
    return change, db.execute(_actual(review.id, code)).scalar_one()


def _actual(review_id, code):
    return (select(M.Evaluation.actual_value)
            .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
            .join(M.RequirementVersion,
                  M.RequirementVersion.id == M.Finding.requirement_version_id)
            .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
            .where(M.Finding.review_id == review_id, M.Requirement.code == code))


def test_the_playbook_lines_are_the_managers(build, db):
    contract = _contract(build, db)
    _ours(build, db, contract)
    points = {p["requirement_code"]: p for p in read.for_contract(db, contract)}
    assert points[CAP]["line"] == (
        "We start at 6 months of fees for the affected services. You can agree up to "
        "12 months of total fees, the same for both sides. Anything more goes to Legal.")
    assert points[PAY]["line"] == ("We start at 7 days. You can agree up to 21 days. "
                                   "Anything more goes to Legal.")
    assert points[CAP]["kind"] == points[PAY]["kind"] == playbook.RANGE


@pytest.mark.parametrize(("number", "sentence", "inside"), [
    ("17.2", OURS, True),                                      # 12 months of total fees
    ("17.2", OURS.replace("twelve (12)", "eighteen (18)"), False),
    ("17.2", ONE_PARTY, False),                                # caps LeapSwitch only
    ("8.5", PAID.format("fifteen (15)"), True),
    ("8.5", PAID.format("twenty-one (21)"), True),
    ("8.5", PAID.format("thirty (30)"), False),
])
def test_effect_for_us_agrees_with_the_playbook(build, db, number, sentence, inside):
    contract = _contract(build, db)
    ours = _ours(build, db, contract)
    points = {p["requirement_code"]: p for p in read.for_contract(db, contract)}
    change, actual = _their_change(build, db, contract, ours, number, sentence)
    assert playbook.within(points[CAP if number == "17.2" else PAY], actual) is inside
    assert (change["effect_for_us"] != "NEGATIVE") is inside


def test_a_standard_with_no_direction_offers_only_its_own_value():
    e = playbook.entry("CURE-PERIOD-MSA-001", {"preferred": 30, "unit": "DAYS",
                                               "basis": "BREACH_CURE_PERIOD"},
                       {"deviation_outcome": "UNACCEPTABLE"},
                       {"value": 15, "unit": "DAYS", "basis": "BREACH_CURE_PERIOD",
                        "party": None}, provider=True)
    assert e["kind"] == playbook.EXACT
    assert e["line"] == ("We start at 15 days. You can agree to 30 days. "
                         "Anything else goes to Legal.")
    side = {"cap_unit": "DAYS", "cap_basis": "BREACH_CURE_PERIOD"}
    assert playbook.within(e, {**side, "cap_value": 30})
    assert not playbook.within(e, {**side, "cap_value": 20})


def test_a_counsel_check_or_a_customers_paper_is_never_a_range():
    std = {"preferred": 15, "unit": "DAYS", "basis": "B", "favourable_direction": "LOWER"}
    rule = {"favourable_outcome": "ACCEPTABLE"}
    assert playbook.entry("X", {**std, "favourable_counsel_check": "s.28"}, rule, None,
                          provider=True)["kind"] == playbook.EXACT
    assert playbook.entry("X", std, rule, None, provider=False)["kind"] == playbook.EXACT
    assert playbook.entry("X", std, rule, None, provider=True)["kind"] == playbook.RANGE


def test_a_presence_standard_is_legal_only_and_a_fallback_outside_the_band_is_dropped():
    assert playbook.entry("INDEMNITY-MSA-001", {}, None, None, provider=True)["line"] \
        == "Legal decides any change."
    std = {"preferred": 21, "unit": "DAYS", "basis": "B", "favourable_direction": "LOWER"}
    e = playbook.entry("X", std, {"favourable_outcome": "ACCEPTABLE"}, None, provider=True,
                       fallbacks=[{"value": 14, "unit": "DAYS", "basis": "B"},
                                  {"value": 30, "unit": "DAYS", "basis": "B"}])
    assert [f["value"] for f in e["fallbacks"]] == [14]
    assert "offer 14 days first" in e["line"]


def test_the_endpoint_needs_the_positions_permission_and_hides_another_users_deal(
        api, db, seeded):
    owner, stranger, blind = make_user(db), make_user(db), make_user(db)
    grant_role(db, owner, P.ROLE_USER)
    grant_role(db, stranger, P.ROLE_USER)
    grant(db, blind, bespoke_role(db, f"PB_{blind.id.hex[:6]}", [P.CONTRACT_VIEW,
                                                                 P.DOCUMENT_VIEW]))
    contract = db.get(M.Contract, make_review_for(db, owner).contract_id)
    url = f"{V1}/contracts/{contract.id}/playbook"
    sign_in(api, db, owner)
    assert api.get(url).json()["data"] == {"contract_id": str(contract.id), "points": []}
    sign_in(api, db, stranger)
    assert api.get(url).status_code == 404                     # SEC-07: not in scope
    contract.owner_id = blind.id
    db.flush()
    sign_in(api, db, blind)
    assert api.get(url).status_code == 403                     # LEGAL-02


def test_room_is_only_where_something_lies_between_our_opening_and_our_limit():
    std = {"preferred": 30, "unit": "DAYS", "basis": "B", "favourable_direction": "LOWER"}
    rule = {"favourable_outcome": "ACCEPTABLE"}
    at = {"value": 30, "unit": "DAYS", "basis": "B", "party": None}
    e = playbook.entry("X", std, rule, at, provider=True)
    assert (e["room"], e["line"]) == (False, "We start at 30 days, which is also our limit. "
                                             "Anything more goes to Legal.")
    assert playbook.entry("X", std, rule, {**at, "value": 7}, provider=True)["room"]
    assert not playbook.entry("Y", {}, None, None, provider=True)["room"]


TOTAL = OURS.replace("twelve (12)", "{}")


@pytest.mark.parametrize(("number", "sentence", "effect"), [
    ("17.2", TOTAL.format("three (3)"), "POSITIVE"),          # better than our 6 months
    ("3.1", ACCOUNT.replace("'", "\u2019"), "NEUTRAL"),        # formatting only
    ("17.2", TOTAL.format("twelve (12)"), "FALLBACK"),        # our standard, a concession
    ("17.2", TOTAL.format("eighteen (18)"), "NEGATIVE"),
    ("8.5", PAID.format("fifteen (15)"), "FALLBACK"),         # within 21, worse than our 7
    ("8.5", PAID.format("thirty (30)"), "NEGATIVE"),
])
def test_a_move_away_from_our_paper_inside_our_standard_is_a_fallback(
        build, db, number, sentence, effect):
    """`AM-306` (owner, 2026-11-04): Preferred / Fallback / Escalate."""
    contract = _contract(build, db)
    ours = _ours(build, db, contract)
    texts = {"17.2": AFFECTED, "8.5": PAID.format("seven (7)"), "3.1": ACCOUNT,
             number: sentence}
    theirs, _ = _version(build, db, contract, texts["17.2"], texts["8.5"], texts["3.1"])
    [change] = [c for c in negotiation.changes(db, contract, ours, theirs,
                                               legal_position=True)["changes"]
                if c["clause"]["number"] == number]
    assert change["effect_for_us"] == effect
    assert all("figure" not in f for f in change["review"]["after"])


def test_paper_not_declared_ours_opens_at_our_standard_never_its_own_figure(build, db):
    """Audit N9 (`AM-317` r4): the client's paper — or an upload nobody declared ours —
    says 7 days; what we start at is the standard's 21 days, never the document's."""
    contract = _contract(build, db)
    _version(build, db, contract, AFFECTED, PAID.format("seven (7)"))
    points = {p["requirement_code"]: p for p in read.for_contract(db, contract)}
    assert points[PAY]["line"].startswith("We start at 21 days")
    assert "7 days" not in points[PAY]["line"]
    assert points[CAP]["line"].startswith("We start at 12 months of total fees")

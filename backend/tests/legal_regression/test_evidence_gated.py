"""Evidence-gated findings (owner, 2026-10-23): a result is right only when the clause it
cites says it. Written BEFORE the fix from a customer purchase order that was misread on
22 Oct 2026 — every case is the shape that failed, in our own synthetic wording (locked
54.6, rule 21: no client text; expectations name ratified standards by code and never
copy their values). Each case states the cited clause AND the expected result, and each
has its opposite trap, so "the engine agrees with itself" can never pass a test.
"""
from __future__ import annotations

import pytest

from tests.legal_regression.test_legal_regression import PAGE, _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

PO = [
    "PURCHASE ORDER",
    "1. Order",
    "1.2 The Vendor's Terms and Conditions apply. Where this PO expressly provides for a "
    "matter, this PO governs that matter.",
    "7. Payment",
    "7.1 Each monthly invoice is payable by the 1st day of the service month, provided it "
    "is received at least [7] days before that date.",
    "10. Liability",
    "10.1 The Vendor's liability is capped at the amount paid by the Buyer in the "
    "preceding 6 months.",
    "11. Confidentiality",
    "11.1 The Vendor will keep all Buyer information confidential during the Term and for "
    "3 years afterwards.",
    "11.3 Each party will comply with applicable law.",
    "12. Termination",
    "12.3 Either party may terminate if the other commits a material breach and fails to "
    "remedy it within 30\ndays of written notice.",
    PAGE,
    "ANNEXURE B - VENDOR TERMS",
    "Limitation of Liability",
    "- Liability capped at amount paid by customer in last 6 months",
    # an annexure that restarts its numbering: its "7." is never the order's "7. Payment"
    "ANNEXURE C - SERVICE LEVELS",
    "7. Acts of God or other events beyond the Vendor's reasonable control.",
]
CODES = ["CONF-SURVIVAL-MSA-001", "CURE-PERIOD-MSA-001", "PAYMENT-PERIOD-MSA-001",
         "LIABILITY-MSA-001", "COMPLIANCE-INDEMNIFICATION-VENDOR_AGREEMENT-001",
         "RESIDUALS-NDA-001", "TRADE-SECRET-CARVEOUT-NDA-001",
         "ORDER-PRECEDENCE-PO-ORDER_FORM-001"]


def _po(build, db, *replace: tuple[str, str]):
    paragraphs = list(PO)
    for old, new in replace:
        paragraphs = [p.replace(old, new) if isinstance(p, str) else p for p in paragraphs]
    return _review(build, db, CODES, paragraphs, kind=None)


@pytest.fixture
def po(build, db):
    review, run = _po(build, db)
    return _findings(db, review), run


# --------------------------------------------- the paper's own title names its type
def test_an_undeclared_purchase_order_is_read_as_one_from_its_title(po):
    _, run = po
    assert run.document_type == "ORDER_FORM"


def test_a_vendor_position_is_not_measured_on_a_customer_purchase_order(po):
    found, run = po
    assert "COMPLIANCE-INDEMNIFICATION-VENDOR_AGREEMENT-001" not in found
    row = next(r for r in run.applicability
               if r["code"] == "COMPLIANCE-INDEMNIFICATION-VENDOR_AGREEMENT-001")
    assert row["outcome"] == "NOT_APPLICABLE"


def test_nda_only_positions_are_not_raised_as_missing_on_a_purchase_order(po):
    found, _ = po
    for code in ("RESIDUALS-NDA-001", "TRADE-SECRET-CARVEOUT-NDA-001"):
        assert found.get(code, {}).get("classification") != "MISSING", code


# --------------------------------------------- a figure in other words is still read
def test_confidentiality_for_three_years_afterwards_is_read_and_cited(po):
    found, _ = po
    survival = found["CONF-SURVIVAL-MSA-001"]
    assert survival["classification"] == "MATCH"
    assert "11.1" in {s for s, _ in survival["cited"]}


def test_a_shorter_survival_in_the_same_words_is_a_deviation(build, db):
    review, _ = _po(build, db, ("for 3 years afterwards", "for 1 year afterwards"))
    assert _findings(db, review)["CONF-SURVIVAL-MSA-001"]["classification"] == "DEVIATION"


def test_a_cure_period_broken_across_a_line_is_read_and_cited(po):
    found, _ = po
    cure = found["CURE-PERIOD-MSA-001"]
    assert cure["classification"] == "MATCH"
    assert "12.3" in {s for s, _ in cure["cited"]}


def test_a_shorter_cure_period_in_the_same_words_is_a_deviation(build, db):
    review, _ = _po(build, db, ("within 30\ndays", "within 15\ndays"))
    assert _findings(db, review)["CURE-PERIOD-MSA-001"]["classification"] == "DEVIATION"


# ------------------------- clause level: what a found clause says (no model needed)
def _read(code: str, *texts: str):
    """The real standard's extraction over clauses the mapping found — as the analysis
    runs it, minus the mapping: what these words state for this standard."""
    import json
    from pathlib import Path
    from uuid import uuid4

    from legalmind.extraction.liability import (
        LiabilityExtractionConfig,
        extract_liability_facts,
    )
    from legalmind.mapping.engine import Clause
    standard = json.loads((Path(__file__).resolve().parents[2] / "config"
                           / "company_standards" / f"{code}.json").read_text())
    from dataclasses import replace

    from legalmind.analysis.service import topic_terms
    config = replace(LiabilityExtractionConfig.from_config(standard["configuration"]),
                     topic_terms=topic_terms(standard.get("mapping_rules")))
    clauses = [Clause(evidence_id=uuid4(), content=t) for t in texts]
    return extract_liability_facts(clauses, config).caps, clauses


def test_the_same_cap_stated_twice_is_one_cap_citing_both():
    caps, clauses = _read(
        "LIABILITY-MSA-001",
        "10.1 The Vendor's liability is capped at the amount paid by the Buyer in the "
        "preceding 6 months.",
        "- Liability capped at amount paid by customer in last 6 months")
    assert len(caps) == 1
    cap = caps[0]
    assert (cap.cap_status, cap.cap_value, cap.cap_unit, cap.cap_basis) == (
        "FINITE", 6.0, "MONTHS", "FEES_PAID")
    assert set(cap.evidence_refs) == {c.evidence_id for c in clauses}


def test_two_different_caps_stay_two():
    caps, _ = _read(
        "LIABILITY-MSA-001",
        "10.1 The Vendor's liability is capped at the amount paid by the Buyer in the "
        "preceding 6 months.",
        "- Liability capped at amount paid by customer in last 3 months")
    assert sorted(c.cap_value for c in caps) == [3.0, 6.0]


def test_a_bracketed_blank_figure_is_read_as_a_blank_never_absent():
    caps, _ = _read(
        "PAYMENT-PERIOD-MSA-001",
        "7.1 Each monthly invoice is payable by the 1st day of the service month, "
        "provided it is received at least [7] days before that date.")
    assert [(c.cap_status, c.reason) for c in caps] == [("UNKNOWN", "PLACEHOLDER")]


def test_a_figure_no_wording_reads_is_unconfirmed_never_absent():
    caps, _ = _read("CONF-SURVIVAL-MSA-001",
                    "11.1 The Vendor will keep all Buyer information confidential for "
                    "5 years.")
    assert [(c.cap_status, c.reason) for c in caps] == [("UNKNOWN", "FIGURE_NOT_READ")]


def test_a_found_clause_with_no_figure_at_all_is_still_absent():
    """45C.14 stands: a found clause that states no figure in the term's units."""
    caps, _ = _read("CONF-SURVIVAL-MSA-001",
                    "11.1 The Vendor will keep all Buyer information confidential.")
    assert [c.cap_status for c in caps] == ["ABSENT"]


# --------------------------------------------- MISSING means no clause at all
def test_a_found_clause_whose_figure_is_unread_is_never_missing(build, db):
    review, _ = _po(build, db, ("for 3 years afterwards", "for 3 years in all"))
    survival = _findings(db, review)["CONF-SURVIVAL-MSA-001"]
    assert survival["classification"] == "UNABLE_TO_EVALUATE"
    assert "11.1" in {s for s, _ in survival["cited"]}, "the found clause is cited"


# --------------------------------------------- the payment clause is found by structure
def test_the_payment_clause_under_its_heading_is_found_and_its_blank_said(po):
    """§7.1 under "7. Payment", with "invoice" and "[7] days": no configured phrase
    names it and the model's shortlist skipped it on the real PO (22 Oct)."""
    found, _ = po
    payment = found["PAYMENT-PERIOD-MSA-001"]
    assert {s for s, _ in payment["cited"]} >= {"7.1"}
    assert payment["classification"] == "UNABLE_TO_EVALUATE"
    assert payment["actual"].get("reason") == "PLACEHOLDER"      # the blank speaks


# ------------------------- real-world breaks met on the client's PDF (22-23 Oct)
def test_the_blank_in_a_later_sentence_of_the_clause_is_still_found():
    caps, _ = _read(
        "PAYMENT-PERIOD-MSA-001",
        "7.1 The first invoice is payable before service activation. Each subsequent "
        "monthly invoice is payable in advance by the 1st day of the service month, "
        "provided it is received at least [7] days before that date.")
    assert [(c.cap_status, c.reason) for c in caps] == [("UNKNOWN", "PLACEHOLDER")]


def test_capped_at_reads_for_a_standard_whose_list_says_is_limited_to():
    caps, _ = _read("LIABILITY-TOS-001",
                    "- Liability capped at amount paid by customer in last 6 months")
    assert [(c.cap_status, c.cap_value, c.cap_unit) for c in caps] == [
        ("FINITE", 6.0, "MONTHS")]


def test_including_but_not_limited_to_is_never_a_cap():
    caps, _ = _read("LIABILITY-TOS-001",
                    "Damages include, but are not limited to, loss of data within 6 "
                    "months of the incident.")
    assert all(c.cap_status != "FINITE" for c in caps)


def test_a_bulleted_annex_with_a_page_footer_reads_one_figure_per_bullet():
    caps, _ = _read("LIABILITY-MSA-001",
                    "Confidentiality\n\u2013 Confidentiality obligation continues for 3 years "
                    "after termination\nLimitation of Liability\n\u2013 No liability for "
                    "indirect or consequential damages\n\u2013 Liability capped at amount paid "
                    "by customer in last 6 months\nACME \u2013 Vendor PO | Page 6 of 9")
    assert [(c.cap_status, c.cap_value, c.cap_unit) for c in caps] == [
        ("FINITE", 6.0, "MONTHS")]


# ---------------------- §31.11: "by reference to the governing MSA — not restated"
PO_TERMS = ["PURCHASE ORDER",
            "7. Payment",
            "7.1 Each invoice is payable within 21 days of the invoice date by bank "
            "transfer.",
            "11. Confidentiality and data protection",
            "11.1 The Vendor will keep all Buyer information confidential."]
BY_REFERENCE = ["PAYMENT-TERMS-ORDER_FORM-001",
                "CONFIDENTIALITY-DATA-PROTECTION-ORDER_FORM-001",
                "REFERENCE-GOVERNING-MSA-ORDER_FORM-001"]


def test_a_po_that_restates_its_own_terms_is_a_change_not_a_match(build, db):
    review, _ = _review(build, db, BY_REFERENCE, PO_TERMS, kind=None)
    found = _findings(db, review)
    for code in ("PAYMENT-TERMS-ORDER_FORM-001",
                 "CONFIDENTIALITY-DATA-PROTECTION-ORDER_FORM-001"):
        assert found[code]["classification"] == "DEVIATION", code
        assert found[code]["actual"].get("presence") == "RESTATED", code
    assert "7.1" in {s for s, _ in found["PAYMENT-TERMS-ORDER_FORM-001"]["cited"]}


def test_a_po_that_names_no_msa_is_missing_its_reference(build, db):
    review, _ = _review(build, db, BY_REFERENCE, PO_TERMS, kind=None)
    reference = _findings(db, review)["REFERENCE-GOVERNING-MSA-ORDER_FORM-001"]
    assert reference["classification"] == "MISSING"
    assert reference["cited"] == []


def test_a_po_issued_under_the_msa_that_refers_to_it_matches(build, db):
    """The opposite trap: the PO names its MSA and points to it for payment and
    confidentiality — every one is a Match, citing where it says so."""
    review, _ = _review(build, db, BY_REFERENCE, [
        "PURCHASE ORDER",
        "1. Order",
        "1.1 This PO is issued under the Master Services Agreement dated 1 June 2026 "
        "between the parties.",
        "7. Payment",
        "7.1 Payment terms are as set out in the Master Services Agreement.",
        "11. Confidentiality and data protection",
        "11.1 Confidentiality and data protection are governed by the MSA.",
    ], kind=None)
    found = _findings(db, review)
    for code in BY_REFERENCE:
        assert found[code]["classification"] == "MATCH", code
    assert "1.1" in {s for s, _ in found["REFERENCE-GOVERNING-MSA-ORDER_FORM-001"]["cited"]}

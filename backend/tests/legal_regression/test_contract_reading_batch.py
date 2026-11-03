"""Contract-reading fixes R-1…R-7 (ENTERPRISE_TRACKER.md group 3, 2026-11-03). Each case is
the shape that was misread, in our own synthetic wording (locked 54.6, rule 21: no client
text), with an opposite case written to break the fix. Expectations name ratified standards
by code and quote only the Constitution's own words.
"""
from __future__ import annotations

import pymupdf
import pytest
from sqlalchemy import select

from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.parsing import detect_clause_number, parse_pdf
from legalmind.ingestion.service import ingest_document
from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified

# ------------------------------------------- R-1: §10 "a defined mutual framework"
INDEMNITY = "INDEMNITY-MSA-001"
#: the customer's indemnity, carrying every §10 limb, so only its direction is in question
THEIRS = ("9.1 The Customer shall defend, indemnify and hold harmless Leapswitch against "
          "third-party claims arising from the Customer's content, its end users' conduct, "
          "any breach of the Acceptable Use Policy or breach of applicable law.")


def _indemnity(build, db, *clauses: str, kind: str = "MSA") -> dict:
    review, _ = _review(build, db, [INDEMNITY], ["9. Indemnity", THEIRS, *clauses],
                        kind=kind)
    return _findings(db, review)[INDEMNITY]


@pytest.mark.parametrize("ours", [
    (),
    # a refusal to indemnify is no indemnity given
    ("9.2 Leapswitch shall have no obligation to indemnify the Customer for any failure "
     "of the Services.",),
    # the role named only in procedure binds no-one to indemnify (review, 2026-11-03)
    ("9.2 The Indemnified Party shall promptly notify the Indemnifying Party of any claim "
     "in writing.",),
    # we are indemnified, passively — we give nothing
    ("9.2 The Provider shall be indemnified and held harmless by the Customer against any "
     "such claim.",),
])
def test_a_customer_only_indemnity_is_one_sided(build, db, ours):
    found = _indemnity(build, db, *ours)
    assert found["classification"] == "DEVIATION"
    assert found["actual"]["presence"] == "ONE_SIDED"
    assert "9.1" in {s for s, _ in found["cited"]}


@pytest.mark.parametrize("ours", [
    "9.2 Leapswitch shall indemnify the Customer against third-party claims that the "
    "Services infringe a third party's intellectual property rights.",
    # the Constitution's own §10 drafting: a defined role, not a party name
    "9.2 Each Party (the “Indemnifying Party”) shall defend, indemnify and hold "
    "harmless the other Party against third-party claims arising from the Indemnifying "
    "Party's gross negligence or wilful misconduct.",
    "9.2 The Service Provider (“Leapswitch”) shall indemnify the Customer against "
    "claims arising from its wilful misconduct.",
    # mutual wordings the first pass missed (review, 2026-11-03)
    "9.2 The Parties shall mutually indemnify each other against third-party claims "
    "arising from their gross negligence or wilful misconduct.",
    "9.2 Each of the Parties shall indemnify the other against third-party claims "
    "arising from its gross negligence or wilful misconduct.",
    "9.2 Each Party hereby agrees to indemnify the other against third-party claims "
    "arising from its gross negligence or wilful misconduct.",
    "9.2 Leapswitch hereby indemnifies the Customer against third-party claims that the "
    "Services infringe a third party's intellectual property rights.",
])
def test_an_indemnity_given_both_ways_is_not_one_sided(build, db, ours):
    assert _indemnity(build, db, ours)["classification"] == "MATCH"


def test_an_aside_between_shall_and_indemnify_is_still_read_both_ways(build, db):
    review, _ = _review(build, db, [INDEMNITY], [
        "16. Indemnification",
        "16.1 The Customer shall, at its sole cost and expense, defend, indemnify and hold "
        "harmless Leapswitch against third-party claims arising from its content, its end "
        "users' conduct or any breach of the Acceptable Use Policy."])
    assert _findings(db, review)[INDEMNITY]["actual"]["presence"] == "ONE_SIDED"


def test_an_aside_in_our_own_indemnity_still_makes_it_mutual(build, db):
    assert _indemnity(build, db, "9.2 Leapswitch shall, at its own cost, indemnify the "
                      "Customer against claims that the Services infringe a third "
                      "party's intellectual property rights.")["classification"] == "MATCH"


def test_the_aside_shape_is_also_read_for_the_customers_narrow_indemnity(build, db):
    # AM-212 never saw "shall, at its sole cost and expense, defend": now it does
    review, _ = _review(build, db, [INDEMNITY], [
        "16. Indemnification",
        "16.1 The Customer shall, at its sole cost and expense, defend and indemnify "
        "Leapswitch against claims arising from the Customer's content.",
        "16.2 Leapswitch shall indemnify the Customer against claims that the Services "
        "infringe a third party's intellectual property rights."])
    assert _findings(db, review)[INDEMNITY]["actual"]["presence"] == "TOO_NARROW"


def test_the_published_terms_one_way_indemnity_is_not_held_to_the_mutual_framework(
        build, db):
    # §10 Applicability: "For the published Terms of Service … the live one-way customer
    # indemnity governs"
    assert _indemnity(build, db, kind="TOS")["actual"].get("presence") != "ONE_SIDED"


@pytest.mark.parametrize("title", ["TERMS OF SERVICE", "ACCEPTABLE USE POLICY"])
def test_our_published_terms_uploaded_as_other_are_not_held_to_it_either(build, db, title):
    review, _ = _review(build, db, [INDEMNITY], [title, "9. Indemnity", THEIRS],
                        kind="OTHER")
    assert _findings(db, review)[INDEMNITY]["actual"].get("presence") != "ONE_SIDED"


# ------------------------------- R-3: another family's figure on clauses already measured
MSA_EXIT = ["7. Term and Termination",
            "7.3 Either party may terminate this Agreement for convenience by giving thirty "
            "(30) days' written notice to the other party.",
            "7.4 This Agreement may be terminated by either party if the other fails to cure "
            "a material breach within fifteen (15) days of written notice."]
EXIT_CODES = ["CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001", "TERM-NOTICE-NDA-001"]


def test_an_nda_term_notice_is_not_read_off_an_msas_own_exit_clauses(build, db):
    review, run = _review(build, db, EXIT_CODES, MSA_EXIT, kind="MSA")
    found = _findings(db, review)
    assert "TERM-NOTICE-NDA-001" not in found, (found, run.applicability)
    assert found["CONVENIENCE-NOTICE-MSA-001"]["classification"] == "MATCH"
    reason = next(c for c in run.applicability if c["code"] == "TERM-NOTICE-NDA-001")
    assert reason["outcome"] == "SAME_TOPIC" and "CURE-PERIOD-MSA-001" in reason["reason"]


def test_an_nda_term_notice_confirmed_only_by_the_topic_name_is_not_read_on_an_msa(
        build, db):
    # "termination" under "7. TERM AND TERMINATION" names the topic; no sentence states
    # the NDA's notice — the MSA's purge and dues figures were read as its notice
    review, run = _review(build, db, EXIT_CODES, [
        "7. TERM AND TERMINATION",
        "7.6 Leapswitch shall purge all Customer data within fifteen (15) days of "
        "termination.",
        "7.7 If the Customer fails to settle all dues within ten (10) days of termination, "
        "Leapswitch may recover them."], kind="MSA")
    assert "TERM-NOTICE-NDA-001" not in _findings(db, review)
    assert next(c for c in run.applicability
                if c["code"] == "TERM-NOTICE-NDA-001")["outcome"] == "SAME_TOPIC"


def test_a_commercial_pillar_absent_from_customer_paper_is_still_measured(build, db):
    # the rule reads only another family's CONFIRMED clauses; a pillar measured on every
    # customer service paper (AM-152) stays measured where the paper is silent
    review, _ = _review(build, db, ["CURE-PERIOD-MSA-001", "DATA-RETRIEVAL-TOS-001"], [
        "13. Termination",
        "13.1 After termination the Customer may retrieve its data for thirty (30) days."],
        kind="TOS")
    assert "CURE-PERIOD-MSA-001" in _findings(db, review)


def test_an_nda_term_notice_is_still_measured_on_an_nda(build, db):
    review, _ = _review(build, db, EXIT_CODES, [
        "5. Term",
        "5.1 This Agreement remains in force for two years unless earlier terminated by "
        "either Party in writing with thirty (30) days' notice."], kind="NDA")
    assert _findings(db, review)["TERM-NOTICE-NDA-001"]["classification"] == "MATCH"


# ----------------------------------- R-4 / R-5: what a clause number is, and what it is not
LONG = ("This Agreement remains in force for two years from the Effective Date, and the "
        "obligations of confidentiality survive for a further three years after its expiry "
        "or termination for any reason, whichever is the later of the two dates.")


@pytest.mark.parametrize("line, number", [
    (f"9. Term and Survival: {LONG}", "9"),                     # R-4
    (f"12. Governing Law and Jurisdiction: {LONG}", "12"),
    ("50 Mbps dedicated internet bandwidth on a 1 Gbps port", None),   # R-5
    ("8 GB RAM and 4 vCPU per instance", None),
    ("12 Months", None),
    # a heading is still a heading
    ("5 Fees", "5"),
    ("17 Limitation of Liability", "17"),
    ("11 No Waiver", "11"),
    # a unit word that opens a Title-Case heading is the heading's (review, 2026-11-03)
    ("3 IP Rights", "3"),
    ("8 IP Ownership", "8"),
    ("5 Core Services", "5"),
    ("4 Second Party Obligations", "4"),
    ("9 USD Pricing", "9"),
    ("5 U.S. Export Controls", "5"),
    ("1.5 Days of notice are counted as working days.", "1.5"),
    # a long line that is not a labelled clause stays prose
    (f"The Parties agree: {LONG}", None),
    (f"9. the parties agree: {LONG}", None),
    (f"2026. Payment Terms: {LONG}", None),
])
def test_a_clause_number_is_read_only_where_the_document_states_one(line, number):
    assert detect_clause_number(line)[0] == number


def test_the_labelled_clause_keeps_its_label_as_title():
    assert detect_clause_number(f"9. Term and Survival: {LONG}") == ("9", "Term and Survival")


# ------------------------------------------------ R-7: one clause across a page break
def _pdf(*pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for number, lines in enumerate(pages, 1):
        page = doc.new_page()
        for i, line in enumerate([*lines, f"Page {number} of {len(pages)}"]):
            page.insert_text((72, 72 + 16 * i), line, fontsize=10)
    return doc.tobytes()


SPLIT_CAP = (["17. Limitation of Liability",
              "17.1 Each Party's aggregate liability under this Agreement shall not exceed "
              "the", "total fees paid by the Customer in the"],
             ["Twelve (12) months preceding the event giving rise to the claim.",
              "17.2 Neither Party shall be liable for any indirect or consequential loss."])


def test_a_clause_running_over_a_page_footer_is_one_segment():
    segments = parse_pdf(_pdf(*SPLIT_CAP), ocr=False, docling=False).segments
    cap = next(s for s in segments if s.section_number == "17.1")
    assert "Twelve (12) months preceding" in cap.content
    assert "Page 1 of 2" not in cap.content                 # the footer is not the clause
    assert "Page 1 of 2" in cap.original_content            # …but nothing is lost (34.13)
    assert (cap.page_number, cap.metadata["end_page"]) == (1, 2)
    assert [s.section_number for s in segments] == ["17", "17.1", "17.2"]


@pytest.mark.parametrize("last", [
    "Signed for and on behalf of the Customer",       # unpunctuated, but a sentence's end
    "17.1 Each Party's liability is capped at the fees paid in twelve (12) months.",
])
def test_a_page_that_ends_a_sentence_is_not_continued(last):
    segments = parse_pdf(_pdf(["17. Limitation of Liability", last],
                              ["Twelve (12) months is the period of this Agreement."]),
                         ocr=False, docling=False).segments
    assert segments[-1].page_number == 2 and segments[-1].content.startswith("Twelve")
    assert all("end_page" not in s.metadata for s in segments)


def test_a_cap_split_by_its_page_break_is_one_cap_never_a_conflict(build, db):
    _ratified(build, "LIABILITY-MSA-001")
    contract = M.Contract(owner_id=build.owner.id, name="Split cap", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    result = ingest_document(db, build.storage, contract_id=contract.id,
                             uploaded_by=build.owner.id, data=_pdf(*SPLIT_CAP),
                             filename="contract.pdf", declared_mime="application/pdf")
    review = M.Review(contract_id=contract.id,
                      document_version_id=result.document_version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    run_analysis(db, review)
    found = _findings(db, review)["LIABILITY-MSA-001"]
    assert found["classification"] == "MATCH", found
    assert found["cited"] == [("17.1", 1)]
    assert db.execute(select(M.DocumentEvidence.section_number)
                      .where(M.DocumentEvidence.document_version_id
                             == result.document_version.id)).scalars().all().count(None) == 0


# ------------------------------------- R-2: a clause's body is never its heading
PRICE = "PRICE-CHANGE-NOTICE-MSA-001"
CAP_BODY = ("17.7. Each Party's total aggregate liability, whether in contract, tort or "
            "otherwise, shall not exceed the total fees paid by the Customer in the months "
            "preceding the claim.")


def test_a_liability_cap_that_mentions_fees_is_never_price_change_evidence(build, db):
    review, _ = _review(build, db, [PRICE], ["17. Limitation of Liability", CAP_BODY])
    found = _findings(db, review).get(PRICE, {})
    assert "17.7" not in {s for s, _ in found.get("cited", ())}, found


def test_a_price_clause_under_its_fees_heading_is_still_found(build, db):
    review, _ = _review(build, db, [PRICE], [
        "8. Fees", "8.4 Prices may be changed with thirty (30) days' written notice to the "
        "Customer.", "17. Limitation of Liability", CAP_BODY])
    found = _findings(db, review)[PRICE]
    assert found["classification"] == "MATCH" and {s for s, _ in found["cited"]} == {"8.4"}


@pytest.mark.parametrize("line, title", [
    (CAP_BODY, None),
    ("17. LIMITATION OF LIABILITY", "LIMITATION OF LIABILITY"),
    ("8.4 Fees: Prices may be changed with thirty (30) days' written notice.", "Fees"),
    ("12.2 Fees", "Fees"),
    # a short sentence is no heading because it is short (review, 2026-11-03)
    ("17.7 The aggregate liability shall not exceed the total fees paid.", None),
    ("1. Definitions.", "Definitions"),
])
def test_the_title_is_a_heading_or_a_label_never_the_sentence(line, title):
    assert detect_clause_number(line)[1] == title


# ----------------------------- R-6: "amendments in writing" is not a change/cancellation
CHANGES = "CHANGES-CANCELLATION-ORDER_FORM-001"


def _changes(build, db, clause: str) -> dict:
    review, _ = _review(build, db, [CHANGES], [
        "PURCHASE ORDER", "1. Services", "1.1 Bare metal server, Rs. 1,00,000 per month.",
        clause], kind="ORDER_FORM")
    return _findings(db, review)[CHANGES]


def test_an_amendment_formality_is_not_a_change_or_cancellation_position(build, db):
    found = _changes(build, db, "12. Changes: Any change to this Purchase Order shall follow "
                                "the general terms and be agreed in writing by both parties.")
    assert found["classification"] == "UNABLE_TO_EVALUATE"      # Needs a decision
    assert "12" in {s for s, _ in found["cited"]}


@pytest.mark.parametrize("clause", [
    "12. Changes: Any change to or cancellation of this Purchase Order shall follow the "
    "general change procedure of the Master Services Agreement.",
    "12. Changes: Any change to this Purchase Order shall follow the general notice and "
    "objection procedure, and either party may terminate before it takes effect.",
])
def test_a_change_clause_that_names_its_procedure_still_matches(build, db, clause):
    assert _changes(build, db, clause)["classification"] == "MATCH"


def test_a_bare_year_ending_a_page_is_kept_as_text():
    from legalmind.ingestion.parsing import _without_footer
    assert _without_footer("This Agreement is dated 1 March\n2025").endswith("2025")
    assert _without_footer("… in the\nPage 3 of 9\n12") == "… in the"

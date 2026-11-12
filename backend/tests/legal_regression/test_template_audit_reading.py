"""Engine misreads found auditing our own MSA and NDA templates (2026-11-04). Each case is
the shape that was misread, in synthetic wording (locked 54.6, rule 21: no client text),
beside an opposite case written to break the fix. R-3 is ported from main's AM-248 r2.
"""
from __future__ import annotations

from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

# ------------------------------- R-3: another family's figure on clauses already measured
MSA_EXIT = ["7. Term and Termination",
            "7.3 Either party may terminate this Agreement for convenience by giving thirty "
            "(30) days' written notice to the other party.",
            "7.4 This Agreement may be terminated by either party if the other fails to cure "
            "a material breach within fifteen (15) days of written notice."]
EXIT_CODES = ["CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001", "TERM-NOTICE-NDA-001"]


def _reason(run, code):
    return next(c for c in run.applicability if c["code"] == code)


def test_an_nda_term_notice_is_not_read_off_an_msas_own_exit_clauses(build, db):
    review, run = _review(build, db, EXIT_CODES, MSA_EXIT, kind="MSA")
    found = _findings(db, review)
    assert "TERM-NOTICE-NDA-001" not in found, (found, run.applicability)
    assert found["CONVENIENCE-NOTICE-MSA-001"]["classification"] == "MATCH"
    reason = _reason(run, "TERM-NOTICE-NDA-001")
    assert reason["outcome"] == "SAME_TOPIC" and "CURE-PERIOD-MSA-001" in reason["reason"]


def test_an_nda_term_notice_confirmed_only_by_the_topic_name_is_not_read_on_an_msa(
        build, db):
    review, run = _review(build, db, EXIT_CODES, [
        "7. TERM AND TERMINATION",
        "7.6 Leapswitch shall purge all Customer data within fifteen (15) days of "
        "termination.",
        "7.7 If the Customer fails to settle all dues within ten (10) days of termination, "
        "Leapswitch may recover them."], kind="MSA")
    assert "TERM-NOTICE-NDA-001" not in _findings(db, review)
    assert _reason(run, "TERM-NOTICE-NDA-001")["outcome"] == "SAME_TOPIC"


def test_a_commercial_pillar_absent_from_customer_paper_is_still_measured(build, db):
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


# ----------------------- the payment period: never another obligation's figure (MSA 8.6)
PAYMENT = "PAYMENT-PERIOD-MSA-001"
GST_NOTICE = ("8.6 The Customer shall inform Leapswitch at least 10 days prior to the date "
              "of invoice of any modification to its GST registration certificate.")


def test_a_gst_notice_before_the_invoice_is_never_the_payment_period(build, db):
    review, _ = _review(build, db, [PAYMENT], [
        "8. Payment and Invoicing",
        "8.2 Payment terms shall be set out in the Service Order Form.", GST_NOTICE])
    found = _findings(db, review)[PAYMENT]
    assert found["classification"] != "MATCH"
    assert found["actual"].get("cap_value") is None
    assert "10 days" not in (found["actual"].get("candidates") or [])


def test_the_payment_sentence_beside_the_gst_notice_is_still_read(build, db):
    review, _ = _review(build, db, [PAYMENT], [
        "8. Payment and Invoicing", GST_NOTICE,
        "8.7 The Customer shall pay all undisputed invoices within twenty-one (21) days of "
        "the invoice date."])
    found = _findings(db, review)[PAYMENT]
    assert found["classification"] == "MATCH", found


# ------------------- a period whose subject is named only in its (a), (b) items (NDA 10)
NON_SOLICIT = "NON-SOLICIT-NDA-001"


def _solicit(build, db, years: str) -> dict:
    review, _ = _review(build, db, [NON_SOLICIT], [
        "10. Non-Solicitation",
        f"During the term of this Agreement and for a period of {years} following its "
        "termination or expiry, the Receiving Party shall not, directly or indirectly:",
        "(a) solicit any employee of the Disclosing Party to terminate their engagement; or",
        "(b) solicit any customer of the Disclosing Party for a competing service."],
        kind="NDA")
    return _findings(db, review)[NON_SOLICIT]


def test_a_non_solicit_period_named_in_its_items_is_read(build, db):
    assert _solicit(build, db, "two (2) years")["classification"] == "MATCH"


def test_a_different_non_solicit_period_named_in_its_items_still_deviates(build, db):
    found = _solicit(build, db, "five (5) years")
    assert found["classification"] == "DEVIATION"
    assert found["actual"]["cap_value"] == 5.0


# -------------------- the two-part definition, in "reasonably should be understood" words
DEFINITION = "CONF-DEFINITION-NDA-001"


def test_a_reasonable_person_definition_with_should_is_read(build, db):
    review, _ = _review(build, db, [DEFINITION], [
        "1. Confidential Information",
        "For the purposes of this Agreement, \"Confidential Information\" means all "
        "information disclosed by the Disclosing Party that is designated as confidential "
        "or that reasonably should be understood to be confidential given the nature of the "
        "information."], kind="NDA")
    assert _findings(db, review)[DEFINITION]["classification"] == "MATCH"

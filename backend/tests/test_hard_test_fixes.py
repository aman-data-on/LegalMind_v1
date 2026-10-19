"""AM-163 / AM-164 / AM-165 — the fixes the senior-lawyer hard test (2026-10-19) found.

Synthetic shapes only (54.6). Each test is one trap a careless system falls into, with
the lawyer's answer; the negative controls are what the fix must NOT touch.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from legalmind.analysis import reading as R
from legalmind.analysis import service as S
from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.constitution_boundaries import (
    constitution_prohibition_for as prohibited,
)
from legalmind.extraction.liability import (
    LiabilityExtractionConfig,
    cap_disapplied,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

STANDARDS = Path(__file__).resolve().parents[1] / "config" / "company_standards"


def _standard(code: str) -> dict:
    return json.loads((STANDARDS / f"{code}.json").read_text())


def _ratified(build, code: str):
    p = _standard(code)
    build.requirement(code, E.EvaluatorType[p.get("evaluator_type", "NUMERIC_COMPARISON")], mapping=p["mapping_rules"],
                      standard=p["configuration"], legal_rule=p["legal_rule"]["configuration"],
                      evaluation_rules=p.get("evaluation_rules"))


def _finding(db, review, code):
    rows = db.execute(
        select(M.Finding, M.Evaluation.actual_value)
        .join(M.RequirementVersion, M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .outerjoin(M.Evaluation, M.Evaluation.finding_id == M.Finding.id)
        .where(M.Finding.review_id == review.id, M.Requirement.code == code)).all()
    assert rows, f"no finding for {code}"
    return rows[0][0].classification.value, rows[0][1] or {}


def _clause(text: str, number: str | None = None) -> Clause:
    return Clause(evidence_id=uuid4(), content=text, section_number=number)


# ---------------------------------------------------------------- A: the cap (AM-164)
CAP = ("5.1 Each Party's aggregate liability under this Agreement shall not exceed the "
       "total fees paid by the Customer in the twelve (12) months preceding the claim.")


def test_a_sentence_that_takes_any_breach_out_of_the_cap_is_seen():
    hit = "5.3 The limitation in clause 5.1 shall not apply to any breach of this Agreement."
    assert cap_disapplied([_clause(CAP), _clause(hit)])[0].content == hit
    # a named carve-out, or one the law requires, is not "uncapped"
    for fine in (
            "The cap shall not apply to any breach of confidentiality or to fraud.",
            "The limitation of liability shall not apply to death or personal injury.",
            "Clause 5.1 does not apply to any claims arising from a data breach.",
            "The limitations will not apply to any liability that cannot be excluded by law."):
        assert cap_disapplied([_clause(fine)]) == ()


def test_a_will_not_exceed_about_credits_or_hours_is_not_a_liability_cap():
    config = LiabilityExtractionConfig.from_config(
        _standard("LIABILITY-MSA-001")["configuration"])
    for text in ("Credit Limits: SLA credits will not exceed the full monthly amount of "
                 "the server affected. Claims must be made by an account user.",
                 "Scheduled maintenance shall not exceed 4 hours per month."):
        facts = extract_liability_facts([_clause(text)], config)
        assert {c.cap_status for c in facts.caps} == {"ABSENT"}, text
    facts = extract_liability_facts([_clause(CAP)], config)
    assert [(c.cap_status, c.cap_value) for c in facts.caps] == [("FINITE", 12.0)]


def test_an_unlimited_limb_or_no_cap_in_an_msa_is_the_uncapped_position():
    unlimited = {"caps": [{"cap_status": "FINITE", "cap_value": 12.0},
                          {"cap_status": "UNLIMITED"}]}
    assert prohibited("LIABILITY-MSA-001", unlimited)["section"] == "9"
    assert prohibited("LIABILITY-MSA-001", {"cap_status": "ABSENT"})["section"] == "9"
    # the company's own published TOS may state no cap (§9 Applicability)
    assert prohibited("LIABILITY-TOS-001", {"cap_status": "ABSENT"}) is None
    assert prohibited("LIABILITY-MSA-001", {"cap_status": "FINITE", "cap_value": 12}) is None


def test_a_conflict_with_an_unlimited_limb_must_change_before_signing():
    from legalmind.api import angles as A
    row = {"code": "LIABILITY-MSA-001", "classification": "CONFLICT", "evidence": None,
           "actual": {"caps": [{"cap_status": "FINITE"}, {"cap_status": "UNLIMITED"}]}}
    assert A.action(row, False) == A.MUST_CHANGE
    row["actual"] = {"caps": [{"cap_status": "FINITE"}, {"cap_status": "FINITE"}]}
    assert A.action(row, False) == A.CONFLICT_DECIDE


def test_a_cap_an_exception_wipes_out_is_never_accepted_end_to_end(build, db):
    """T04: 12 months, then 'shall not apply to any breach of this Agreement'."""
    _ratified(build, "LIABILITY-MSA-001")
    review = build.review(["5. Limitation of Liability", CAP,
                           "5.3 The limitation in clause 5.1 shall not apply to any breach "
                           "of this Agreement by LeapSwitch."])
    run_analysis(db, review)
    classification, actual = _finding(db, review, "LIABILITY-MSA-001")
    assert classification == "CONFLICT" and prohibited("LIABILITY-MSA-001", actual)


def test_liability_that_shall_not_be_limited_to_a_figure_is_unlimited_end_to_end(build, db):
    _ratified(build, "LIABILITY-MSA-001")
    review = build.review(["5. Limitation of Liability",
                           "5.1 Each Party's liability under this Agreement shall not be "
                           "limited to the fees paid in the twelve (12) months preceding the "
                           "claim."])
    run_analysis(db, review)
    classification, actual = _finding(db, review, "LIABILITY-MSA-001")
    assert (classification, actual.get("cap_status")) == ("DEVIATION", "UNLIMITED")


def test_an_msa_with_no_limitation_of_liability_has_no_cap(build, db):
    """MSA2/MSA3: 'shall not exceed 4 hours' and a credit limit are not a cap."""
    _ratified(build, "LIABILITY-MSA-001")
    review = build.review([
        "5. Limitation of Liability",
        "5.1 Service credits will not exceed the full monthly amount of the server affected.",
        "6. Maintenance", "6.1 Scheduled maintenance shall not exceed 4 hours per month."])
    run_analysis(db, review)
    classification, actual = _finding(db, review, "LIABILITY-MSA-001")
    assert (classification, actual.get("cap_status")) == ("MISSING", "ABSENT")
    assert prohibited("LIABILITY-MSA-001", actual)


# ------------------------------------------------- B: indemnity and residuals (AM-165)
def _cfg(code):
    return _standard(code)["configuration"]


def test_an_indemnity_covering_indirect_loss_is_too_broad_for_either_party():
    """§10: "materially broader … for either party" — the owner's AM-154 ruling reads the
    indemnity's words, not who gives it."""
    cfg = _cfg("INDEMNITY-MSA-001")
    ours = "LeapSwitch shall indemnify the Customer against all losses, including indirect losses."
    theirs = ("The Customer shall indemnify LeapSwitch against all losses, including "
              "indirect and consequential losses.")
    assert S.breadth_hit([_clause(ours, "6.1")], cfg) == "indirect"
    assert S.breadth_hit([_clause(theirs, "6.1")], cfg) == "indirect"
    assert S.breadth_hit([_clause("6. INDEMNIFICATION", "6"), _clause(ours, "6.1")], cfg)


def test_an_in_no_event_exclusion_naming_indemnity_is_not_an_indemnity():
    cfg = _cfg("INDEMNITY-MSA-001")
    clause = _clause("13.2 In no event, whether in contract, indemnity, warranty or tort, "
                     "shall Leapswitch be liable for: loss of use; cost of capital; "
                     "any special, consequential or incidental damages; or claims of "
                     "customers, and Customer will indemnify Leapswitch against them.")
    assert S.breadth_hit([clause], cfg) is None


def test_a_bare_indemnity_from_leapswitch_covering_indirect_loss_is_too_broad(build, db):
    """T15: no 'hold harmless', no 'defend' — still an indemnity, still too broad."""
    _ratified(build, "INDEMNITY-MSA-001")
    review = build.review(["6. INDEMNITY",
                           "6.1 LeapSwitch shall indemnify the Customer against all "
                           "losses, including indirect and consequential losses and loss of "
                           "profits, arising from the Services."])
    run_analysis(db, review)
    assert _finding(db, review, "INDEMNITY-MSA-001") == ("DEVIATION", {"presence": "TOO_BROAD"})


def test_a_residuals_clause_for_any_purpose_is_wider_than_ours(build, db):
    _ratified(build, "RESIDUALS-NDA-001")
    wide = build.review(["9. Residuals", "9.1 Each Party may freely use any information "
                         "retained in the unaided memory of its personnel, including "
                         "Confidential Information, for any purpose."])
    run_analysis(db, wide)
    assert _finding(db, wide, "RESIDUALS-NDA-001")[1] == {"presence": "TOO_BROAD"}


def test_a_residuals_clause_in_the_ratified_words_still_matches(build, db):
    _ratified(build, "RESIDUALS-NDA-001")
    ours = build.review(["9. Residuals", "9.1 The Receiving Party's personnel may retain and "
                         "use, in the conduct of its ordinary business activities, any "
                         "Confidential Information that is incidentally retained in the "
                         "unaided memory of such personnel."])
    run_analysis(db, ours)
    assert _finding(db, ours, "RESIDUALS-NDA-001") == ("MATCH", {"presence": "PRESENT"})


# -------------------------------------------- C: in our favour, survival wording, ₹ reason
def test_a_payment_period_shorter_than_ours_is_in_our_favour_and_never_send_our_wording():
    from legalmind.api import angles as A
    std = _cfg("PAYMENT-PERIOD-MSA-001")
    row = {"code": "PAYMENT-PERIOD-MSA-001", "classification": "DEVIATION", "evidence": None,
           "standard": std, "actual": {"cap_value": 15.0, "cap_unit": "DAYS"}}
    assert A.action(row, True) == A.FAVOURABLE and "send our wording" in A.FAVOURABLE
    row["actual"] = {"cap_value": 45.0, "cap_unit": "DAYS"}          # later: against us
    assert A.action(row, True) == A.SEND_WORDING
    row["actual"] = {"cap_value": 1.0, "cap_unit": "MONTHS"}         # another unit: never read
    assert A.action(row, True) == A.SEND_WORDING


def test_a_confidentiality_survival_stated_after_the_verb_is_read(build, db):
    _ratified(build, "CONF-SURVIVAL-MSA-001")
    review = build.review([
        "16. Confidentiality",
        "16.5 The obligations of confidentiality shall survive the termination or expiry "
        "of this Agreement for a period of five (5) years."])
    run_analysis(db, review)
    classification, actual = _finding(db, review, "CONF-SURVIVAL-MSA-001")
    assert (classification, actual.get("cap_value"), actual.get("cap_unit")) == (
        "DEVIATION", 5.0, "YEARS")


def test_with_no_term_the_reason_for_no_rupee_value_is_the_term():
    from legalmind.extraction import commercial
    facts = commercial.read([_clause("The Customer shall pay fees of Rs. 50,000 per month "
                                     "for the Services.")])
    assert facts.committed_value is None and facts.missing == (
        "the document states no fixed term")


# ------------------------------------------------- D: the counterparty's own city as venue
def test_a_venue_at_the_customers_head_office_is_a_place_that_is_not_ours():
    from legalmind.extraction.categorical import read_values
    facts = read_values(
        [_clause("Seat and venue of arbitration: Customer\u2019s Head Office city.")],
        _cfg("DISPUTE-VENUE-MSA-001"))
    assert [v.value for v in facts.values] == ["COUNTERPARTY_LOCATION"]


# ----------------------------------------------------- data loss (AM-163): the standard
def test_the_data_loss_standard_matches_the_exclusion_and_waives_on_the_provider_taking_it(
        build, db):
    _ratified(build, "DATA-LOSS-EXCLUSION-MSA-001")
    ok = build.review(["17. Limitation of Liability",
                       "17.6 LeapSwitch shall not be liable for loss of data, or the cost of "
                       "restoring or recovering data, whether direct or indirect."])
    run_analysis(db, ok)
    assert _finding(db, ok, "DATA-LOSS-EXCLUSION-MSA-001")[0] == "MATCH"


def test_a_provider_that_takes_responsibility_for_data_loss_is_a_deviation(build, db):
    _ratified(build, "DATA-LOSS-EXCLUSION-MSA-001")
    bad = build.review(["12. Data", "12.4 LeapSwitch shall be liable for any service "
                        "interruptions or data loss resulting from its failure to maintain "
                        "the platform."])
    run_analysis(db, bad)
    classification, actual = _finding(db, bad, "DATA-LOSS-EXCLUSION-MSA-001")
    assert classification == "DEVIATION" and actual.get("presence") == "WAIVED"


# -------------------------------------------------------------- E: the second read
def _rows(*texts):
    return [_clause(t, str(n)) for n, t in enumerate(texts, start=1)]


def _say(**cats) -> str:
    return json.dumps({k: cats.get(k, []) for k in R.CATEGORIES})


def test_the_documents_own_names_for_the_parties_are_read_from_its_parties_block():
    head = _rows('This Partner Agreement is made between LeapSwitch Networks Pvt. Ltd., a '
                 'company having its registered office at Pune (the "Company") and Acme '
                 'Technologies Limited, having its registered office at Delhi (the "Partner").')
    assert R._aliases(head) == (["company"], ["partner"])
    nda = _rows('Between LeapSwitch Networks Pvt. Ltd. (hereinafter the “Receiving '
                'Party”) and Zed Limited (hereinafter the “Disclosing Party”).')
    assert R._aliases(nda) == (["receiving party"], ["disclosing party"])
    # a defined term that is not a role is never a party
    assert R._aliases(_rows('LeapSwitch Pvt. Ltd. (the "Customer Business") sells (the '
                            '"Services").')) == ([], [])


def test_a_receiving_party_non_solicit_binds_us_when_the_documents_names_say_so():
    rows = _rows('Between LeapSwitch Networks Pvt. Ltd. (the "Receiving Party") and Zed '
                 'Limited (the "Disclosing Party").',
                 "The Receiving Party shall not, for two (2) years following termination, "
                 "solicit the Disclosing Party's employees or customers.",
                 "The Disclosing Party reserves the right to discontinue discussions.")
    quote = ("The Receiving Party shall not, for two (2) years following termination, "
             "solicit the Disclosing Party's employees or customers.")
    kept = R.verify(_say(RESTRAINT=[{"row": 2, "quote": quote}]), rows, "NDA")
    assert [i["category"] for i in kept] == ["RESTRAINT"]
    assert R.verify(_say(RESTRAINT=[{"row": 2, "quote": quote}]), _rows(rows[1].content),
                    "NDA") == []                       # no parties block: not guessed


def test_each_party_obligations_bind_us_but_either_party_rights_do_not():
    assert R._side("Each Party shall not solicit the other's employees for two years.",
                   False) == "MUTUAL_DUTY"
    assert R._side("Either Party may terminate on 30 days' notice.", False) is None


def test_our_rights_and_shields_are_never_burdens_in_any_direction():
    for sentence in ("LeapSwitch shall bill the Customer as per applicable GST rates.",
                     "The only obligation of Leapswitch is to re-perform the Services.",
                     "Leapswitch's liability is subject to timely payment by the Customer.",
                     "The Customer shall pay the stamp duty on this Agreement."):
        assert R._side(sentence, False) is None, sentence


def test_stamp_duty_and_sole_remedy_count_only_in_our_direction():
    rows = _rows("The stamp duty payable on this Agreement shall be borne by LeapSwitch.",
                 "The stamp duty payable on this Agreement shall be borne by the Customer.",
                 "The Customer's sole and exclusive remedy is a service credit.",
                 "LeapSwitch's sole remedy for non-payment is suspension of the Services.")
    def got(cat, i):
        return R.verify(_say(**{cat: [{"row": i, "quote": rows[i - 1].content}]}), rows, "MSA")
    assert got("STAMP_COSTS", 1) and not got("STAMP_COSTS", 2)
    assert not got("SOLE_REMEDY", 3) and got("SOLE_REMEDY", 4)


def test_a_filled_default_or_a_signature_line_is_not_a_blank():
    for filled in ("dated [19 JULY 2025]", "Currency: [Indian Rupees (INR)]",
                   "Currency: [INR]", "dated [July]",
                   "Signed by: ______________________ Name: A. Person"):
        assert not R._has_blank(filled), filled
    for blank in ("within [30] days of the invoice date", "effective as of ________ 2025",
                  "the Partner [Name] shall"):
        assert R._has_blank(blank), blank


def test_uncapped_is_kept_on_wording_real_drafts_use_and_precedence_only_when_another_prevails():
    rows = _rows("LeapSwitch shall be liable for any damages, costs, penalties or losses "
                 "arising from a data breach.",
                 "In the event of conflict, the Purchase Order terms shall prevail over this "
                 "Agreement.",
                 "This Agreement shall prevail over any other document.")
    def keep(cat, i):
        return R.verify(_say(**{cat: [{"row": i, "quote": rows[i - 1].content}]}), rows, "MSA")
    assert keep("UNCAPPED", 1)
    assert keep("PRECEDENCE", 2) and not keep("PRECEDENCE", 3)


def test_one_issue_a_clause_the_most_specific_category():
    rows = _rows("LeapSwitch shall be liable for any damages arising from data loss.")
    q = rows[0].content
    kept = R.verify(_say(DATA_LOSS=[{"row": 1, "quote": q}], UNCAPPED=[{"row": 1, "quote": q}]),
                    rows, "MSA")
    assert [i["category"] for i in kept] == ["UNCAPPED"]


@pytest.mark.parametrize("quote", ["x" * 5])
def test_a_quote_too_short_to_mean_anything_is_dropped(quote):
    rows = _rows("LeapSwitch shall indemnify.")
    assert R.verify(_say(UNCAPPED=[{"row": 1, "quote": quote}]), rows, "MSA") == []


def test_the_reading_module_stays_off_the_findings_path():
    assert SimpleNamespace(**{"enabled": R.enabled()}).enabled is False


# ------------------------------------------------ late interest on an MSA (AM-166, §16)
def _late_interest(build, db, text):
    _ratified(build, "LATE-INTEREST-MSA-001")
    review = build.review(["6. Payment", text])
    run_analysis(db, review)
    classification, actual = _finding(db, review, "LATE-INTEREST-MSA-001")
    return classification, actual


def test_late_interest_at_the_constitutions_two_percent_a_month_matches(build, db):
    assert _late_interest(build, db, "6.3 Late payments accrue interest at 2% per month, "
                          "subject to applicable law.")[0] == "MATCH"


def test_late_interest_at_another_rate_a_month_is_a_deviation_for_a_person(build, db):
    classification, actual = _late_interest(
        build, db, "6.3 Overdue amounts shall carry interest at 3% per month.")
    assert (classification, actual.get("cap_value")) == ("DEVIATION", 3.0)


def test_a_rate_stated_per_annum_is_not_converted_it_goes_to_a_person(build, db):
    """24% a year equals 2% a month only as simple interest; code does not assume it."""
    classification, actual = _late_interest(
        build, db, "6.3 If payment is delayed the Customer shall be liable to pay interest at "
        "a rate equivalent to twenty four percent (24%) per annum on the unpaid amount.")
    assert classification == "UNABLE_TO_EVALUATE" and actual.get("candidates") == ["24%"]


def test_the_published_tos_is_never_measured_against_the_msa_late_interest():
    std = _standard("LATE-INTEREST-MSA-001")["configuration"]
    assert std["not_applicable_to"] == ["TOS"] and std["preferred"] == 2
    assert _standard("LATE-FEE-TOS-001")["configuration"]["preferred"] == 5

"""What a clause DOES decides the finding, never the words it shares with our position
(owner, 2026-10-26: "no matter what the file name is, it is all about what is included").
A real customer MOU let the customer leave a one-year term on 30 days' notice — "an early
termination fee may apply", no amount — and was shown as matching Constitution §14
because it said "early termination fee". Synthetic shapes only (54.6)."""
from __future__ import annotations

import pytest

from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

CODE = "EARLY-TERM-RESTRICTION-MSA-001"
TERM = ["1. Term", "1.1 The term of this Agreement shall be one (1) year.",
        "2. Fees", "2.1 The Customer shall pay Rs. 1,00,000 per month, exclusive of GST."]
OUR_POSITION = ("7.1 The Customer shall have no right to terminate this Agreement before "
                "the expiry of the Term. If the Customer elects to terminate this Agreement "
                "for any reason not expressly permitted under this Agreement, the Customer "
                "shall remain fully liable to pay an early termination fee equal to the "
                "total fees that would have become payable for the remainder of the Term.")


def _early_exit(build, db, *clauses: str) -> str:
    review, _ = _review(build, db, [CODE], [*TERM, "7. Termination", *clauses],
                        kind="OTHER")
    return _findings(db, review)[CODE]["classification"]


def test_a_customer_exit_on_notice_with_an_unstated_fee_waives_the_term(build, db):
    assert _early_exit(build, db,
                       "7.1 The Customer may terminate the Services (i) by providing "
                       "thirty (30) days' prior written notice, in which case an early "
                       "termination fee may apply; or (ii) by providing seven (7) days' "
                       "written notice if the uptime commitment is not met.") == "DEVIATION"


def test_either_party_leaving_for_convenience_waives_the_term(build, db):
    assert _early_exit(build, db,
                       "7.1 Either party may terminate this Agreement for convenience "
                       "on thirty (30) days' written notice.") == "DEVIATION"


@pytest.mark.parametrize("exit_right", [
    # the customer may leave, but pays the rest of the term: the position, held
    "7.2 The Customer may terminate on thirty (30) days' notice, provided it pays the "
    "fees for the remainder of the Term.",
    # an exit for OUR breach is a carve-out from the position, never a waiver of it
    "7.2 The Customer may terminate this Agreement on thirty (30) days' notice if "
    "Leapswitch commits a material breach and fails to cure it.",
    # an exit an event triggers: force majeure (our own MSA §18.3), our failure
    "7.2 If a force majeure event continues for more than sixty (60) days, either party "
    "may terminate this Agreement upon written notice to the other party.",
    "7.2 The Customer may terminate this Agreement by immediate written notice if "
    "Leapswitch fails to provide the Services as agreed.",
    # our right to leave is not the customer's
    "7.2 Leapswitch may terminate this Agreement on thirty (30) days' notice.",
])
def test_an_exit_that_keeps_the_position_is_not_a_waiver(build, db, exit_right):
    assert _early_exit(build, db, OUR_POSITION, exit_right) == "MATCH"


# ------------------------------------------------ the contract's own term is read
from uuid import uuid4  # noqa: E402

from legalmind.extraction.commercial import states_fixed_term  # noqa: E402
from legalmind.mapping.engine import Clause  # noqa: E402


@pytest.mark.parametrize("text,term", [
    ("This Agreement is for a period of one (1) year.", True),
    ("The term of this Agreement shall be one (1) year from the Effective Date.", True),
    ("The Agreement is valid for one year.", True),
    ("This MOU is valid for a period of 1 year.", True),
    ("Contract Agreement: 1 Year", True),
    ("This Agreement shall remain in force for a period of 12 months.", True),
    # a price's, a quote's or an invoice's validity is never the contract's term
    ("The Pricing as per quote is valid for a period of 1 year.", False),
    ("The quotation shall be valid for 30 days.", False),
    ("Each invoice is valid for 12 months.", False),
    ("This Agreement is for the provision of services for 12 months of hosting.", False),
])
def test_the_contract_term_is_read_in_everyday_wordings(text, term):
    assert states_fixed_term([Clause(evidence_id=uuid4(), content=text)]) is term


# ------------------------------------------ what WE promise to indemnify (§10)
INDEMNITY = "INDEMNITY-MSA-001"
THEIRS = ("9.1 The Customer shall, at its sole cost and expense, defend, indemnify and hold "
          "harmless Leapswitch against third-party claims arising from the Customer's "
          "content, unlawful use of the Services or breach of applicable law.")


def _indemnity(build, db, ours: str) -> str:
    review, _ = _review(build, db, [INDEMNITY], ["9. Indemnity", THEIRS, ours],
                        kind="OTHER")
    return _findings(db, review)[INDEMNITY]["classification"]


@pytest.mark.parametrize("ours", [
    # the MOU's own shape: every service failure becomes our indemnity
    "9.2 Leapswitch shall indemnify and hold harmless the Customer against all third-"
    "party claims arising from Leapswitch's breach of applicable laws, or any failure, "
    "deficiency, disruption or other issue arising from the provision of the Services.",
    "9.2 The Service Provider shall indemnify the Customer against any loss arising from "
    "its negligence or breach of this Agreement.",
    "9.2 Each party shall indemnify the other against claims arising from its breach of "
    "its confidentiality or data protection obligations.",
])
def test_an_indemnity_we_give_beyond_section_10_is_too_broad(build, db, ours):
    assert _indemnity(build, db, ours) == "DEVIATION"


@pytest.mark.parametrize("ours", [
    # §10's own framework: IP infringement, gross negligence, wilful misconduct
    "9.2 Leapswitch shall indemnify the Customer against third-party claims that the "
    "Services infringe a third party's intellectual property rights.",
    "9.2 Each party shall indemnify the other against claims arising from its gross "
    "negligence or wilful misconduct.",
    # the customer's breach of law is THEIR indemnity to us, never ours
    "9.2 Leapswitch shall have no obligation to indemnify the Customer for any failure "
    "of the Services.",
])
def test_an_indemnity_within_section_10_is_not_too_broad(build, db, ours):
    assert _indemnity(build, db, ours) == "MATCH"


# -------------------------------- which document wins over the MSA (§31.11 precedence)
PRECEDENCE = "ORDER-PRECEDENCE-PO-ORDER_FORM-001"
ORDER = ["1. Services", "1.1 Bare metal server, Rs. 1,00,000 per month, as per quotation "
         "Q-1 under the Master Services Agreement (MSA)."]


def _precedence(build, db, clause: str) -> str | None:
    review, _ = _review(build, db, [PRECEDENCE], [*ORDER, "9. General", clause],
                        kind="OTHER")
    return _findings(db, review).get(PRECEDENCE, {}).get("classification")


@pytest.mark.parametrize("clause", [
    # the MOU's own words: the paper ranks itself above the MSA
    "9.1 In case of any inconsistency, this MOU shall prevail, followed by the MSA and "
    "then any online terms or policies.",
    "9.1 In the event of any inconsistency, the following order of precedence applies: "
    "(i) this MoU; (ii) the MSA; and (iii) any online terms or policies.",
    "9.1 Where this Purchase Order conflicts with the Master Services Agreement, this "
    "Purchase Order shall take precedence.",
])
def test_a_paper_that_ranks_itself_above_the_msa_deviates(build, db, clause):
    assert _precedence(build, db, clause) == "DEVIATION"


@pytest.mark.parametrize("clause", [
    "9.1 In the event of any conflict between this Order Form and the MSA, the MSA shall "
    "prevail.",
    "9.1 The order of precedence is: (i) the Master Services Agreement; (ii) this "
    "Order Form.",
])
def test_a_paper_that_ranks_the_msa_first_states_our_position(build, db, clause):
    assert _precedence(build, db, clause) == "MATCH"


# ------------------------------------- prepaid is a payment term, never a missing one
PAYMENT = "PAYMENT-PERIOD-MSA-001"


def _payment(build, db, *clauses: str) -> dict:
    review, _ = _review(build, db, [PAYMENT], ["4. Payment Terms", *clauses],
                        kind="OTHER")
    return _findings(db, review)[PAYMENT]


def test_payment_in_advance_is_found_and_left_to_a_person(build, db):
    found = _payment(build, db, "4.1 Payment Terms: Monthly [PREPAID].",
                     "4.2 Services are billed in advance and payment must be received "
                     "before service activation.")
    assert found["classification"] == "UNABLE_TO_EVALUATE"
    assert found["actual"].get("reason") == "PAID_IN_ADVANCE"
    assert {"4.1", "4.2"} & {c for c, _ in found["cited"]}


def test_a_stated_invoice_period_is_still_compared_beside_advance_billing(build, db):
    found = _payment(build, db, "4.1 Fees are billed monthly in advance.",
                     "4.2 Invoices are payable within 45 days of the invoice date.")
    assert found["classification"] == "DEVIATION"


@pytest.mark.parametrize("clause", [
    "4.1 Prepaid credits are non-refundable once used.",
    # our own February MSA draft §8.2: the choice is left to the order form
    "4.1 All charges will be invoiced in advance or arrears as may be mutually agreed "
    "under the Service Order Form.",
])
def test_a_clause_that_does_not_take_payment_in_advance_is_not_read_so(build, db, clause):
    assert _payment(build, db, clause)["actual"].get("reason") != "PAID_IN_ADVANCE"


# ------------------------------ what KIND of paper: its title, else its content (§31.13)
from legalmind.analysis.service import customer_service_paper  # noqa: E402
from legalmind.domain.document_types import title_type  # noqa: E402


def _clauses(*texts: str) -> list[Clause]:
    return [Clause(evidence_id=uuid4(), content=t) for t in texts]


@pytest.mark.parametrize("title,kind", [
    ("Memorandum of Understanding is in Between", "OTHER"),
    ("LETTER OF INTENT", "OTHER"),
    ("Acceptable Usage Policy", "AUP"),
    ("PRIVACY POLICY", "PRIVACY_POLICY"),
    ("Data Processing Addendum", "DPA"),                  # never an Amendment
    ("Addendum No. 2 to the Master Services Agreement", "AMENDMENT"),
])
def test_the_title_names_the_kind(title, kind):
    assert title_type(_clauses(title, "1. Scope")) == kind


def test_untitled_paper_serving_a_customer_for_a_fee_is_an_other_agreement():
    assert customer_service_paper(_clauses(
        "The Customer shall pay Rs. 7,57,000 per month for the Services.",
        "Contract Agreement: 1 Year"))


@pytest.mark.parametrize("texts", [
    # we buy: a vendor's paper is a relationship §31 states positions for
    ("The Vendor shall supply the servers to Leapswitch.", "Fees: Rs. 10,000 per month."),
    # no fee and no term: nothing says what kind of service paper it is
    ("Each party shall keep the other's Confidential Information confidential.",),
])
def test_paper_that_is_not_plainly_customer_service_is_never_typed(texts):
    assert not customer_service_paper(_clauses(*texts))


def test_a_partner_position_never_measures_untitled_customer_paper(build, db):
    review, run = _review(build, db, ["CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001",
                                      "CONVENIENCE-NOTICE-MSA-001"],
                          ["Details of Services", "Contract Agreement: 1 Year",
                           "Service Costing: Rs. 7,57,000 per month.",
                           "13. The Customer may terminate the Services by providing "
                           "thirty (30) days' prior written notice."], kind=None)
    found = _findings(db, review)
    assert run.document_type == "OTHER" and run.document_type_source == "content"
    assert "CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001" not in found
    assert any(a["code"] == "CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001"
               and "31.13" in a["reason"] for a in run.applicability)


# ----------------------- §11: credits are the only remedy, as a credit note (AM-193)
CREDITS = "SLA-CREDIT-REMEDY-SLA-001"


def _credits(build, db, heading: str, *clauses: str) -> str | None:
    review, _ = _review(build, db, [CREDITS], [heading, *clauses], kind="OTHER")
    return _findings(db, review).get(CREDITS, {}).get("classification")


def test_a_penalty_on_top_of_credits_paid_in_cash_deviates(build, db):
    assert _credits(build, db, "Penalty Clause",
                    "If Leapswitch fails to provide Services, Leapswitch shall credit the "
                    "Customer account on the prorated base charges from the day the Trouble "
                    "Ticket is issued. Service Credits shall also be payable where the "
                    "downtime exceeds the threshold under the SLA. Any accrued Service "
                    "Credits shall be refunded or adjusted against outstanding dues upon "
                    "termination.") == "DEVIATION"


def test_our_published_credit_wording_states_the_position(build, db):
    assert _credits(build, db, "Service Credits",
                    "Service credits are your sole and exclusive remedy for any service "
                    "interruption, and are issued as a credit note against future bills "
                    "for the same service.") == "MATCH"


# ------------------------------------ §16: price changes need 30 days' written notice
PRICE = "PRICE-CHANGE-NOTICE-MSA-001"


def _price(build, db, clause: str) -> dict:
    review, _ = _review(build, db, [PRICE], ["Terms & Conditions", clause], kind="OTHER")
    return _findings(db, review).get(PRICE, {})


def test_a_price_change_communicated_in_advance_states_no_notice_period(build, db):
    found = _price(build, db,
                   "1. The above-mentioned Pricing as per quote Q-1 is valid for a period of "
                   "1 year and may be subject to change thereafter and will be communicated "
                   "in advance. If the resources are upgraded or downgraded, the Service "
                   "price will change accordingly.")
    assert found.get("classification") in ("UNABLE_TO_EVALUATE", "MISSING")
    # its only figure is the price's validity ("1 year"): no notice period is stated
    assert found["actual"].get("reason") in ("NO_FIGURE_STATED", "FIGURE_NOT_READ")
    assert found["cited"]                                   # the clause itself, cited


def test_a_price_change_on_fifteen_days_notice_deviates(build, db):
    assert _price(build, db, "1. Prices may be changed with fifteen (15) days' written "
                             "notice to the Customer.")["classification"] == "DEVIATION"


# ---------------- §13 data export and §9 data loss: measured on every customer contract
@pytest.mark.parametrize("code", ["DATA-PURGE-MSA-001", "DATA-LOSS-EXCLUSION-MSA-001"])
def test_customer_paper_silent_on_data_after_exit_is_never_silent_here(build, db, code):
    review, run = _review(build, db, [code], [
        "1. Contract Term: twelve (12) months.",
        "2. The Customer shall pay Rs. 1,00,000 per month.",
        "3. Either party may terminate for material breach not cured within thirty (30) "
        "days."], kind="OTHER")
    assert code in _findings(db, review), run.applicability


# ------ §9: no carve-out from the cap for confidentiality, data, IP (AM-195, amends AM-164)
from legalmind.extraction.liability import cap_carved_out  # noqa: E402


@pytest.mark.parametrize("text", [
    # the MOU's own sentence: fraud is protected, the rest is not
    "Liability capped at amount paid by customer in last 12 months, provided that such cap "
    "shall not apply to Leapswitch's liability arising from fraud, wilful misconduct, gross "
    "negligence, breach of confidentiality or data protection obligations, or infringement "
    "of third-party intellectual property rights.",
    "The limitation in clause 9.1 shall not apply to a party's indemnification obligations.",
    "Claims for data breach shall not be subject to the limitation of liability.",
])
def test_a_cap_disapplied_for_a_class_section_9_names_is_carved_out(text):
    assert cap_carved_out(_clauses(text))


@pytest.mark.parametrize("text", [
    # what the law will not let anyone limit is never a carve-out we chose
    "The limitation shall not apply to liability for death or personal injury caused by "
    "negligence, or for fraud.",
    "Nothing in this Agreement limits liability that cannot be excluded by law.",
    # confidentiality obligations themselves are no carve-out from the cap
    "Each party shall keep the other's confidential information confidential.",
])
def test_a_cap_that_keeps_section_9_classes_inside_is_not_carved_out(text):
    assert not cap_carved_out(_clauses(text))


# --------------- §15 NDA: the confidentiality period is read however it is worded
SURVIVAL = "CONF-SURVIVAL-NDA-001"


def _survival(build, db, clause: str) -> dict:
    review, _ = _review(build, db, [SURVIVAL], ["6. Term of Confidentiality", clause],
                        kind="NDA")
    return _findings(db, review)[SURVIVAL]


def test_a_period_from_disclosure_is_found_never_missing(build, db):
    found = _survival(build, db,
                      "6.1 The Receiving Party's obligations with respect to the "
                      "Confidential Information shall expire one (1) year from the date "
                      "of disclosure.")
    assert found["classification"] != "MISSING"
    assert found["cited"]


@pytest.mark.parametrize("clause,result", [
    ("6.1 The obligations of confidentiality shall continue for two (2) years after the "
     "termination of this Agreement.", "DEVIATION"),
    ("6.1 The obligations of confidentiality shall continue for three (3) years after "
     "the termination of this Agreement.", "MATCH"),
])
def test_a_period_after_the_agreement_ends_is_compared(build, db, clause, result):
    assert _survival(build, db, clause)["classification"] == result


# ------------ §15: confidentiality is mutual — read from the roles, never the title
from legalmind.analysis.service import fixed_roles  # noqa: E402


@pytest.mark.parametrize("text", [
    # a "MUTUAL" NDA whose roles are bound to one named party and a blank
    "any business information that one party (“Disclosing Party (ACME)”) "
    "discloses to the other (“Receiving Party (____________”).",
    "ACME Software Private Limited (the “Disclosing Party”) and Leapswitch "
    "Networks Pvt. Ltd. (the “Receiving Party”)",
])
def test_a_role_bound_to_a_named_party_is_one_directional(text):
    assert fixed_roles(_clauses(text))


@pytest.mark.parametrize("text", [
    "any information that one party (“Disclosing Party”) discloses to the other "
    "(“Receiving Party”).",
    "Each party (the “Receiving Party”) shall keep the Confidential Information "
    "of the other party (the “Disclosing Party”) confidential.",
    "Either party may be a Disclosing Party or a Receiving Party under this Agreement.",
    # an executed MSA's own mutual wording (replay, 2026-10-26)
    'Each Party ("Receiving Party") agrees that it will not disclose any information '
    'belonging to the other Party ("Disclosing Party").',
])
def test_roles_that_either_party_may_hold_are_mutual(text):
    assert not fixed_roles(_clauses(text))


def test_a_one_directional_nda_deviates_whatever_its_title(build, db):
    review, _ = _review(build, db, ["CONF-MUTUAL-NDA-001"], [
        "MUTUAL NON-DISCLOSURE AGREEMENT",
        "1. Confidential Information is any business information that one party "
        "(“Disclosing Party (ACME)”) discloses to the other (“Receiving Party "
        "(____________”).",
        "2. The Receiving Party shall hold all Confidential Information in confidence."],
        kind="NDA")
    assert _findings(db, review)["CONF-MUTUAL-NDA-001"]["classification"] == "DEVIATION"


def test_a_mutual_nda_states_the_position(build, db):
    review, _ = _review(build, db, ["CONF-MUTUAL-NDA-001"], [
        "1. Each party shall keep the Confidential Information of the other party "
        "confidential, whichever party discloses it."], kind="NDA")
    assert _findings(db, review)["CONF-MUTUAL-NDA-001"]["classification"] == "MATCH"


# ------ §15: confidential information is marked OR what a reasonable person would see
from legalmind.analysis.service import marking_only  # noqa: E402


@pytest.mark.parametrize("texts", [
    ("4. Confidential Information shall not be subject to the restrictions of Paragraph 2 "
     "unless (a) if in a writing, it is clearly marked as proprietary or confidential when "
     "disclosed or (b) if not in tangible form, it is identified as confidential at the "
     "time of disclosure and is summarized in a writing so marked within 30 days.",),
    ("Information is Confidential Information only if it is marked “Confidential”.",),
])
def test_protection_only_for_marked_information_is_the_one_part_test(texts):
    assert marking_only(_clauses(*texts))


@pytest.mark.parametrize("texts", [
    ("Confidential Information means information marked confidential or which a "
     "reasonable person would understand to be confidential given its nature.",),
    # a marking rule beside the reasonable-person limb elsewhere is the two-part test
    ("Written information shall be marked confidential.",
     "Confidential Information includes information that by its nature would reasonably "
     "be understood to be confidential."),
])
def test_the_two_part_test_is_not_marking_only(texts):
    assert not marking_only(_clauses(*texts))


def test_the_trade_secret_carve_out_is_never_a_second_period(build, db):
    """The executed NDA: 2 years after termination, and trade secrets for as long as they
    remain secret — one period, a deviation; never a conflict with the carve-out."""
    assert _survival(build, db,
                     "6.1 The Receiving Party's confidentiality obligations shall survive for "
                     "two (2) years from the date of termination or expiry of this Agreement; "
                     "provided, however, that with respect to any Confidential Information "
                     "that qualifies as a trade secret under applicable law, such obligations "
                     "shall continue for so long as such information remains a trade "
                     "secret.")["classification"] == "DEVIATION"


# --------------- a sentence broken by a page break is read whole (AM-207, 2026-10-26)
def test_a_cure_period_split_across_a_page_reads_as_one_clause(build, db):
    """Our own MSA 7.4: "…not cured within thirty (30) days after receipt of written
    notice" | page 7 | "from Leapswitch specifying the breach, or (b) with thirty (30)
    days' written notice for non-payment" — one clause, never a conflict with itself."""
    from tests.legal_regression.test_legal_regression import PAGE
    review, _ = _review(build, db, ["CURE-PERIOD-MSA-001"], [
        "7. Termination",
        "7.4 Termination for Breach: Leapswitch may terminate this Agreement (a) if the "
        "Customer breaches any provision of this Agreement and such breach is not cured "
        "within thirty (30) days after receipt of written notice",
        "7", PAGE,
        "from Leapswitch specifying the breach, or (b) with thirty (30) days' written notice "
        "for non-payment of any invoiced amounts."], kind="MSA")
    assert _findings(db, review)["CURE-PERIOD-MSA-001"]["classification"] == "MATCH"

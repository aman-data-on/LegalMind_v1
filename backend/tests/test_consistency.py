"""AM-159 A5 — what a careful reader notices across one document. Synthetic shapes only
(54.6): each detector's positive case and the negative controls it must stay silent on."""
from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.analysis import consistency as K
from legalmind.mapping.engine import Clause


def _doc(*rows: tuple[str | None, str | None, str]) -> list[Clause]:
    return [Clause(evidence_id=uuid4(), section_number=n, section_title=t, content=c)
            for n, t, c in rows]


def _kinds(clauses: list[Clause]) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    found = K.observe(clauses)
    for item in found["structural"] + found["additional"]:
        out.setdefault(item["kind"], []).append(item["clauses"])
    return out


def _numbered(*extra: tuple[str | None, str | None, str]) -> list[Clause]:
    """A document whose numbering is read (1–9), so a missing clause can be asserted."""
    base = [(str(i), title, f"{i}. {title}") for i, title in enumerate(
        ["Definitions", "Services", "Fees", "Payment Terms", "Term", "Confidentiality",
         "Termination for Cause", "Liability", "Notices"], start=1)]
    return _doc(*base, *extra)


def test_renewal_stated_two_ways_is_one_observation():
    doc = _doc(("1", "Definitions", "1. Renewal Term means each further year for which this "
                "Agreement shall automatically renew."),
               ("5", "Renewal", "5. This Agreement may be renewed upon the mutual written "
                "agreement of the parties."))
    assert _kinds(doc)[K.RENEWAL_TWO_WAYS] == [["1", "5"]]
    one_way = _doc(("5", "Renewal", "5. This Agreement shall automatically renew for one "
                    "year unless either party gives notice, or as mutually agreed."))
    assert K.RENEWAL_TWO_WAYS not in _kinds(one_way)


def test_an_exit_clause_subject_to_the_minimum_term_is_read_with_it():
    doc = _doc(("5", "Minimum Service Period", "5. The Customer shall pay the fees for the "
                "minimum service period on any early termination."),
               ("14", "Termination", "14. Subject to Clause 5 above, either party may "
                "terminate this Agreement on 90 days' notice."))
    found = K.observe(doc)["structural"]
    assert [(o["kind"], o["clauses"]) for o in found] == [(K.SUBJECT_TO, ["14", "5"])]
    assert found[0]["basis"]["section"] == "31.2"
    # the term stated as a service period of a year is the commitment too (MSA3 5.1)
    period = _doc(("5.1", "Term", "5.1 Services are subject to a service period of one (1) "
                   "year from the Service Commencement Date."),
                  ("14.3", "Termination for Convenience", "14.3 Subject to Clause 5.1, either "
                   "Party may terminate for convenience on 30 days' notice."))
    assert K.SUBJECT_TO in _kinds(period)
    # a chain that has nothing to do with the term or an exit is not one
    other = _doc(("3", "Fees", "3. Fees are payable monthly in advance."),
                 ("6", "Taxes", "6. Subject to Clause 3, all taxes are borne by the Customer."))
    assert K.SUBJECT_TO not in _kinds(other)


def test_the_documents_precedence_rule_is_reported_never_applied():
    doc = _doc(("29", "Precedence", "29. In the event of any conflict between this Agreement "
                "and a Purchase Order, the terms of this Agreement shall prevail."))
    found = K.observe(doc)["structural"]
    assert found[0]["kind"] == K.PRECEDENCE and found[0]["basis"]["section"] == "31.11"


def test_a_provider_exit_with_no_non_payment_remedy_is_noticed():
    silent = _doc(("25", "Termination", "25.1 The Customer may terminate on 30 days' notice. "
                   "25.2 Termination by the Service Provider requires 60 days' notice."))
    found = K.observe(silent)["structural"]
    assert found[0]["kind"] == K.NO_NONPAYMENT_REMEDY and found[0]["basis"]["section"] == "13"
    remedied = _doc(("25", "Termination", "25.2 The Service Provider may terminate on 60 "
                     "days' notice. 25.3 The Service Provider may suspend the Services for "
                     "non-payment."))
    assert K.NO_NONPAYMENT_REMEDY not in _kinds(remedied)
    # two different notice periods for two different parties are not a contradiction
    assert set(_kinds(silent)) == {K.NO_NONPAYMENT_REMEDY}


def test_a_cross_reference_to_the_wrong_clause_or_to_none():
    doc = _numbered(("4.2", None, "4.2 Late payment is grounds for termination for cause under "
                     "Section 9."),
                    ("2.1", None, "2.1 See Section 12 for the service levels."))
    hits = _kinds(doc)[K.CROSS_REFERENCE]
    assert ["4.2", "9", "7"] in hits                  # "termination for cause" is clause 7
    assert ["2.1"] in hits                            # there is no clause 12


def test_a_statute_or_a_document_whose_numbering_was_not_read_is_never_a_bad_reference():
    doc = _numbered(("8.1", None, "8.1 Content prohibited under IPC Sections 292\u2013294 and "
                     "Section 70B of the Information Technology Act is barred."),
                    ("8.2", None, "8.2 Nothing in Section 67 of the IT Act applies."),
                    ("8.3", None, "8.3 Liability under IPC Section 34 is excluded."))
    assert K.CROSS_REFERENCE not in _kinds(doc)
    unread = _doc(("2", "Services", "2. Services."),
                  ("2.1", None, "2.1 See Section 30 for the service levels."))
    assert K.CROSS_REFERENCE not in _kinds(unread)    # too few numbers read to say "missing"
    # a reference whose words match its own heading is fine
    fine = _numbered(("2.2", None, "2.2 Fees are invoiced under Section 4 (Payment Terms)."),
                     ("2.3", None, "2.3 Repeated late payment allows termination for cause "
                      "under Section 4 (Payment Terms)."))
    assert K.CROSS_REFERENCE not in _kinds(fine)


def test_review_negative_controls_stay_silent():
    """AM-159 r9–r14 (the R2 review): each shape a detector misread."""
    # D2: an agreed renewal PRICE is not renewal by agreement
    priced = _doc(("5", "Renewal", "5. This Agreement shall automatically renew for one "
                   "year."),
                  ("6", "Renewal Pricing", "6. Renewal pricing shall be determined by "
                   "mutual agreement."))
    assert K.RENEWAL_TWO_WAYS not in _kinds(priced)
    # D3: a for-cause exit turning on the notices clause is not an exit made subject to
    # the commitment
    cause = _doc(("9", "Notices", "9. Notices shall be in writing."),
                 ("14", "Termination", "14. Subject to Clause 9, either party may "
                  "terminate for material breach on written notice."))
    assert K.SUBJECT_TO not in _kinds(cause)
    # D4: a governing-law clause's "conflict of laws" is not a precedence rule
    law = _doc(("22", "Governing Law", "22. Any conflict of laws principle notwithstanding, "
                "the laws of India shall govern this Agreement."))
    assert K.PRECEDENCE not in _kinds(law)
    # D1: the sentence's subject is not a clause heading
    subject = _numbered(("4.1", None, "4.1 The Customer shall pay the fees in accordance "
                         "with Section 4."),
                        ("10", "Customer Obligations", "10. Customer Obligations"))
    assert K.CROSS_REFERENCE not in _kinds(subject)
    # a clause numbered 0 never divides by zero
    assert K.observe(_doc(("0", "Preamble", "0. See Section 5.")))


@pytest.mark.parametrize("remedy", [
    "25.3 Non-payment: the Service Provider may suspend the Services.",
    "25.3 Where an invoice is not paid within 30 days the Service Provider may suspend "
    "the Services.",
    "25.3 If the Customer does not pay, the Service Provider may terminate.",
    "25.3 Any delay in payment entitles the Service Provider to suspend the Services.",
    "25.3 Either party may terminate this Agreement for material breach.",
    # passive, with words between (LeapSwitch's own Terms of Service)
    "25.3 Services associated with overdue invoices may be suspended after 7 days of "
    "non-payment."])
def test_a_non_payment_remedy_in_any_of_its_shapes_is_found(remedy):
    doc = _doc(("25", "Termination", "25.2 The Service Provider may terminate on 60 days' "
                f"notice. {remedy}"))
    assert K.NO_NONPAYMENT_REMEDY not in _kinds(doc)


def test_the_customers_exit_for_our_breach_is_not_our_remedy():
    doc = _doc(("25", "Termination", "25.1 The Customer may terminate this Agreement for "
                "material breach by the Service Provider. 25.2 The Service Provider may "
                "terminate on 60 days' notice."))
    assert K.NO_NONPAYMENT_REMEDY in _kinds(doc)


def test_a_document_where_we_are_not_the_provider_is_never_asked_for_a_remedy():
    silent = _doc(("25", "Termination", "25.2 The Service Provider may terminate on 60 "
                   "days' notice."))
    assert K.observe(silent, "MSA")["structural"]
    for document_type in ("NDA", "VENDOR_AGREEMENT"):
        assert not K.observe(silent, document_type)["structural"]


def test_second_review_negative_controls_stay_silent():
    """AM-159 r18–r22 (the review of the corrections)."""
    # D2: a negated automatic renewal is none; one clause stating a rule is one rule
    assert K.RENEWAL_TWO_WAYS not in _kinds(_doc(
        ("1.1", None, "1.1 This Agreement shall not automatically renew; any renewal "
         "shall be by mutual written agreement of the Parties.")))
    assert K.RENEWAL_TWO_WAYS not in _kinds(_doc(
        ("5.1", None, "5.1 This Agreement shall automatically renew for successive one-year "
         "terms, and any renewal on different terms shall be by mutual written agreement.")))
    assert K.RENEWAL_TWO_WAYS not in _kinds(_doc(
        ("1.1", None, "1.1 There shall be no automatic renewal of this Agreement."),
        ("2.1", None, "2.1 The Agreement may be renewed upon mutual written agreement "
         "of the Parties.")))
    # D3: a notice or survival period is not the commitment
    for period in ("3.1 Either Party shall give a notice period of three (3) months.",
                   "3.1 These obligations survive for a period of three (3) years after "
                   "termination."):
        assert K.SUBJECT_TO not in _kinds(_doc(
            ("3.1", None, period),
            ("4.1", None, "4.1 Subject to Clause 3.1, either Party may terminate this "
             "Agreement for convenience on 30 days' notice.")))
    # D4: hyphenated conflict-of-laws
    assert K.PRECEDENCE not in _kinds(_doc(
        ("2", "Governing Law", "2.1 Without regard to its conflict-of-laws principles, "
         "the laws of India shall govern this Agreement.")))
    # D1: a defined term under the Definitions clause is pointed right
    defined = _numbered(("2.4", None, "2.4 The Supplier shall comply with the Customer "
                         "Obligations under Clause 1 at all times."),
                        ("10", "Customer Obligations", "10. Customer Obligations"))
    assert K.CROSS_REFERENCE not in _kinds(defined)


def test_a_wrong_reference_is_quoted_without_its_function_word():
    doc = _numbered(("4.2", None, "4.2 Late payment is grounds for termination for cause "
                     "under Section 9."))
    [hit] = [o for o in K.observe(doc)["additional"] if len(o["clauses"]) == 3]
    assert "“termination for cause”" in hit["text"]


@pytest.mark.parametrize("not_ours", [
    # boilerplate on what is paid at termination is no right to suspend for non-payment
    "25.3 Upon termination, the Customer shall pay all unpaid charges for Services "
    "rendered up to the date of termination.",
    "25.3 Termination shall not relieve the Customer of its payment obligations accrued "
    "before termination.",
    # a denied remedy, and the customer's remedy against us
    "25.3 The Service Provider shall not suspend or terminate the Services on account of "
    "non-payment of any disputed amount.",
    "25.3 The Service Provider may not suspend the Services for non-payment of a disputed "
    "invoice.",
    "25.3 The Customer may terminate this Agreement if the Service Provider fails to pay "
    "any service credit when due."])
def test_only_our_own_right_for_non_payment_is_a_remedy(not_ours):
    doc = _doc(("25", "Termination", "25.2 The Service Provider may terminate on 60 days' "
                f"notice. {not_ours}"))
    assert K.NO_NONPAYMENT_REMEDY in _kinds(doc)

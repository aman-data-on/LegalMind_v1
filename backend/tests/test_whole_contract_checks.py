"""AM-241 (AB-139, 2026-10-30): what a lawyer reads across the whole contract — each check
both ways. Synthetic clauses only (locked 54.6, rule 21); observations, never Findings."""
from __future__ import annotations

from uuid import uuid4

from legalmind.analysis import consistency as cx
from legalmind.mapping.engine import Clause


def _kinds(texts: list[tuple[str | None, str]], document_type: str = "MSA") -> dict:
    clauses = [Clause(evidence_id=uuid4(), content=t, section_number=n) for n, t in texts]
    out = cx.observe(clauses, document_type)
    return {o["kind"]: o for group in out.values() for o in group}


def test_our_company_named_as_another_entity_is_seen_and_ours_is_not():
    seen = _kinds([(None, "Signed by Leapswitch Data Services Private Limited, Director")])
    assert "“Leapswitch Data Services Private Limited”" in seen[cx.OUR_ENTITY]["text"]
    for ours in ("LeapSwitch Networks Private Limited", "Leapswitch Networks Pvt. Ltd.",
                 "Leap Switch Networks Pvt Ltd"):
        assert cx.OUR_ENTITY not in _kinds([(None, f"Signed by {ours}, Director")])


TERM_RELIED_ON = [("7.1", "This Agreement shall remain in force for the entire tenure "
                          "specified in this Agreement (the “Term”)."),
                  ("7.2", "The Customer shall pay the fees for the remainder of the Term.")]


def test_a_term_relied_on_but_never_stated_is_seen():
    assert cx.NO_TERM_LENGTH in _kinds(TERM_RELIED_ON)


def test_a_stated_term_is_not_mistaken_for_a_renewal_or_a_look_back_period():
    stated = [("7.1", "The initial term of this Agreement is twelve (12) months."),
              *TERM_RELIED_ON[1:]]
    assert cx.NO_TERM_LENGTH not in _kinds(stated)
    only_other_periods = [*TERM_RELIED_ON,
                          ("7.3", "This Agreement renews for successive periods of six (6) "
                                  "months."),
                          ("17.2", "Liability shall not exceed the fees paid in the six (6) "
                                   "month period preceding the claim.")]
    assert cx.NO_TERM_LENGTH in _kinds(only_other_periods)


def test_a_period_left_blank_is_seen_and_a_filled_one_is_not():
    blank = "Liability shall not exceed the total fees paid in the months preceding the claim."
    assert "months blank" in _kinds([("17.7", blank)])[cx.BLANK_FIGURE]["text"]
    filled = blank.replace("the months", "the twelve (12) months")
    assert cx.BLANK_FIGURE not in _kinds([("17.7", filled)])


def test_non_payment_with_different_notice_is_shown_and_none_is_chosen():
    seen = _kinds([("8.9", "If the Customer fails to pay dues, Leapswitch may suspend the "
                           "Services by giving five (5) days' written notice."),
                   ("15.3", "LeapSwitch may suspend Services if the Customer fails to pay "
                            "dues on time.")])[cx.NONPAYMENT_TWO_WAYS]
    assert "clause 8.9: 5 days" in seen["text"] and "clause 15.3: no notice stated" in seen["text"]
    assert seen["basis"]["section"] == "16"
    same = _kinds([("8.9", "Leapswitch may suspend the Services for non-payment on five (5) "
                           "days' written notice."),
                   ("15.3", "LeapSwitch may suspend Services for non-payment on five (5) "
                            "days' written notice.")])
    assert cx.NONPAYMENT_TWO_WAYS not in same


def test_a_definition_pointing_at_the_wrong_clause_names_the_right_one():
    doc = [("1.9", "“Force Majeure” shall have the meaning set forth in Clause 8 of this "
                   "Agreement."),
           (None, "8. PAYMENT AND INVOICING"), ("8.1", "The Customer shall pay the charges."),
           (None, "18. FORCE MAJEURE"), ("18.1", "Neither party is liable for delay.")]
    texts = [o["text"] for o in cx.observe(
        [Clause(evidence_id=uuid4(), content=t, section_number=n) for n, t in doc],
        "MSA")["additional"]]
    assert any("clause 18 is" in t for t in texts)
    right = [(n, t.replace("Clause 8 ", "Clause 18 ")) if n == "1.9" else (n, t)
             for n, t in doc]
    assert not any("defines" in o["text"] for o in cx.observe(
        [Clause(evidence_id=uuid4(), content=t, section_number=n) for n, t in right],
        "MSA")["additional"])


def test_a_name_written_twice_is_ours_and_a_breach_of_another_duty_is_not_non_payment():
    assert cx.OUR_ENTITY not in _kinds(
        [(None, "Leapswitch Networks Leapswitch Networks Private Limited, Pune")])
    other = _kinds([("14.2", "Leapswitch may terminate on immediate written notice when "
                             "payments have not been paid within fifteen (15) days of the "
                             "Due Date."),
                    ("20.3", "A failure to notify a change of address is a material breach "
                             "and shall entitle Leapswitch to terminate the Agreement.")])
    assert cx.NONPAYMENT_TWO_WAYS not in other

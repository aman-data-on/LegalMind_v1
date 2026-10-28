"""V12 (`AM-217`): our position is never the customer's, a duty stays with the party the
record names, a rule keeps its condition. Each case is a real error from the AM-90
claim set or a trap measured on 2026-10-27 (production replies, statute provisos,
boilerplate). No database, no model."""
import pytest

from legalmind.assist.verification import agent_verify as av

FM = ("Either party may terminate on 60 days' notice if a force majeure event continues "
      "for more than 60 days.")
CONF = ("Confidentiality obligations survive termination for 3 years, except that "
        "obligations relating to trade secrets survive for as long as the information "
        "remains a trade secret.")
RENEW = ("Unless cancelled prior to the renewal date, Services will automatically renew "
         "for the same billing period.")
EXIT = ("The Customer shall have no right to terminate before the expiry of the Term. If "
        "the Customer elects to terminate for any reason not expressly permitted, the "
        "Customer shall pay an early termination fee equal to the remaining fees.")
PAY = "Payments are due within 21 days of the invoice date, subject to applicable law."
PROVISO = ("The award shall be made within twelve months. Provided that the award in "
           "international commercial arbitration may be made as expeditiously as possible.")


def v12(sentence, text, source="positions"):
    return av._party_and_condition(sentence, [], [av.Evidence("P1", text, "§1", None,
                                                              False, source)])


@pytest.mark.parametrize("sentence, text", [
    ("The customer's reading of the law cites the Arbitration and Conciliation Act 1996.",
     "22. Governing Law: arbitration under the Arbitration and Conciliation Act, 1996."),
    ("According to the customer position, the cap applies mutually to both parties.",
     "The 12-month liability cap applies mutually to both parties."),
    ("If the company elects to terminate for any reason not expressly permitted, the "
     "company shall pay an early termination fee equal to the remaining fees.", EXIT),
    ("Services will automatically renew for the same billing period.", RENEW),
    ("Confidentiality obligations survive termination for a period of 3 years.", CONF),
])
def test_a_real_error_is_caught(sentence, text):
    assert v12(sentence, text)


@pytest.mark.parametrize("sentence, text, source", [
    # a contrast that names our side too is not an attribution
    ("Unlike our standard, the customer's position is a 6-month cap.",
     "The 12-month liability cap applies mutually to both parties.", "positions"),
    # the customer's own material, restated to them: their words, not our position
    ("The customer's policy requires 30 days' notice.", "30 days' notice.", "attachments"),
    ("Either party may terminate on 60 days' notice if a force majeure event continues "
     "for more than 60 days.", FM, "positions"),
    ("If the Customer elects to terminate early, the Customer shall pay the remaining "
     "fees.", EXIT, "positions"),
    ("Services renew automatically unless cancelled before the renewal date.", RENEW,
     "positions"),
    ("Payments are due within 21 days of the invoice date.", PAY, "positions"),
    ("The award shall be made within twelve months.", PROVISO, "statutes"),
    # production 2026-10-27: a two-party sentence on the reader's own email
    ("Your email states that if Leapswitch fails to fix it within 15 days, the customer "
     "may end the contract.", "LeapSwitch shall fix any failure within 15 days of notice. "
     "The Client may end the contract if it is not fixed.", "attachments"),
])
def test_a_true_or_out_of_scope_sentence_is_left_be(sentence, text, source):
    assert v12(sentence, text, source) is None


def test_the_answer_check_reports_it_as_v12():
    shown = {"P1": av.Evidence("P1", CONF, "§15", None, False, "positions")}
    blocks = [{"kind": "sourced", "text": "Confidentiality obligations survive "
               "termination for a period of 3 years.", "cites": ["P1"]}]
    found = [x for x in av.verify(blocks, shown, document_selected=False,
                                  assessment="n/a") if x.check == "V12"]
    assert found and "trade secrets" in found[0].detail


def test_review_of_pr_244_true_restatements_pass():
    """Code review of PR #244: "you" in a published policy is the customer; in a contract
    LeapSwitch may be the customer, so sides are read on our own records only; and a
    condition after a semicolon governs the next clause, not the one restated."""
    assert v12("The customer shall pay all fees within 30 days of the invoice date.",
               "You shall pay all fees within 30 days of the invoice date.",
               "constitution") is None
    assert v12("Leapswitch shall pay all fees within 30 days of the invoice.",
               "The Customer shall pay all fees within 30 days of the invoice.",
               "documents") is None
    assert v12("The Customer shall pay all fees within 30 days of invoice.",
               "The Customer shall pay all fees within 30 days of invoice; if any amount "
               "is disputed, the Customer shall notify Leapswitch in writing.",
               "documents") is None

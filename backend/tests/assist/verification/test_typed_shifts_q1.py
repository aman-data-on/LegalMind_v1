"""Q-1 (2026-11-03): typed polarity / modality / alignment checks for the shapes the
PHASE 11 held-out perturbations still slipped past the answer check. Each case keeps
the SHAPE of a real accepted perturbation; the wording is paraphrased and synthetic —
these are verifier inputs, not company positions or legal rules.

Measured on the real-claim eval (`tools.eval_verification`, held-out 476 claims, local
NLI, zero Gemini): overstatement accepted 12/44 → 6/44, negation 17/106 → 12/106, and
real-claim false rejections 42 → 42 (none moved on the final, dev and final2 sets
either). Two wider first versions each refused a real claim and were narrowed."""
import pytest

from legalmind.assist.synthesis import answer
from legalmind.assist.verification import verify


@pytest.mark.parametrize("source,claim", [
    # a permission given by a VERB ("permits … to"), reported as a duty
    ("The statute permits a lease to specify a deposit payable on default.",
     "A lease must specify a deposit payable on default."),
    # the modal ten words before its verb, across a parenthetical
    ("The regulator may, after giving the party an opportunity of being heard, impose "
     "a fine set out in the schedule.",
     "The regulator must impose a fine set out in the schedule."),
    # an act stated only as a condition ("unless earlier terminated") is no duty
    ("This licence runs for five years unless earlier terminated by either party in "
     "writing with sixty days' notice.",
     "Either party must terminate in writing with sixty days' notice."),
    # a verb ending -ment/-tion is still a verb: the noun guard must not open the check
    ("The Provider may implement encryption for stored data.",
     "The Provider must implement encryption for stored data."),
    ("The Customer may document each incident in the portal.",
     "The Customer must document each incident in the portal."),
    ("The Supplier may mention the Customer as a reference client.",
     "The Supplier must mention the Customer as a reference client."),
])
def test_an_obligation_the_source_only_permits_is_caught(source, claim):
    assert verify._aligned_shift(claim, source) == \
        "an obligation the evidence only permits or advises"


@pytest.mark.parametrize("source,claim", [
    # the use the claim reports is the BEST-aligned one, not any use of the verb
    ("If the report is filed within three months of the request, the auditor shall "
     "receive a bonus. If the report is not filed within the time allowed, the "
     "engagement ends.",
     "If the report is not filed within three months of the request, the auditor "
     "receives a bonus."),
    # alignment a few words further on: "(with stated reasons) if …"
    ("Earned fees are paid out, except that fees may be withheld with stated reasons "
     "if termination was for fraud.",
     "Fees may not be withheld if termination was for fraud."),
    ("This licence runs for five years unless earlier terminated by either party in "
     "writing with sixty days' notice.",
     "Either party may not terminate in writing with sixty days' notice."),
    # "is not THAT …" negates the proposition after it
    ("Contracts with a fixed term automatically renew for further terms.",
     "The policy is not that contracts with a fixed term automatically renew for "
     "further terms."),
])
def test_a_negation_of_what_the_source_asserts_is_caught(source, claim):
    assert verify._aligned_shift(claim, source) == \
        "the claim negates what its evidence asserts"


@pytest.mark.parametrize("source,claim", [
    ("The statute permits a lease to specify a deposit payable on default.",
     "A lease may specify a deposit payable on default."),
    ("The regulator may, after giving the party an opportunity of being heard, impose "
     "a fine set out in the schedule.",
     "The regulator may impose a fine set out in the schedule."),
    # a modal outranks a nearer condition: "shall, if requested, return" is a duty
    ("The Supplier shall, if requested, return all materials.",
     "The Supplier must return all materials."),
    ("If the report is filed within three months of the request, the auditor shall "
     "receive a bonus. If the report is not filed within the time allowed, the "
     "engagement ends.",
     "If the report is filed within three months of the request, the auditor receives "
     "a bonus."),
    # "Nothing in clause (b) shall apply" negates as "not" does
    ("Nothing in clause (b) shall apply to loans by a lender from other lenders.",
     "Nor do loans from other lenders fall under clause (b)."),
    # "required" as an adjective governs no verb
    ("The statute permits a contract to fix a sum payable on breach.",
     "The required contractual sum remains subject to assessment by a court."),
    # a noun made from the verb is not what a modal before it governs
    ("The Board may impose a penalty up to the stated limit for non-fulfilment of "
     "these duties.",
     "A notified fiduciary must fulfil the additional duties under the section."),
    # one shared word far after the verb is chance, not alignment
    ("Disputes go to the courts named by such Court; failing any agreement referred to "
     "in clause 2, each party appoints one arbitrator.",
     "If there is no such agreement in a three-member tribunal, each party appoints "
     "one arbitrator."),
])
def test_a_faithful_claim_is_not_refused(source, claim):
    assert verify._aligned_shift(claim, source) is None


def test_a_negated_figure_its_cited_text_states_is_not_context():
    """"The cap is not set at 12 months [1]" against a 12-month cap was read as a
    reader's figure named as ABSENT and skipped the verifier entirely."""
    claim = "The standard cap is not set at 12 months [1]."
    asked = ("12 months",)
    assert answer.is_context(claim, asked)                      # no evidence: as before
    assert not answer.is_context(claim, asked, ["The standard cap is 12 months."])
    assert answer.is_context(claim, asked, ["The standard cap is 6 months."])

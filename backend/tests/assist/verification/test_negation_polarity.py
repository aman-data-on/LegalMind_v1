"""A claim may not reverse its clause — and a faithful paraphrase is not a reversal
(2026-10-30). Industry practice for legal RAG checks polarity and modality as their own
claim types (must/shall vs may, prohibited vs permitted, any not/unless/except; typed
legal hallucination auditing, 2026), because general NLI models are weak on negation.

Three sets, measured before the fix on the shipped verifier: flips caught 37/38, but 12
of 34 faithful paraphrases refused ("non-refundable" → "cannot be refunded", "shall not
assign without consent" → "needs consent to assign", "shall pay" → "may pay" missed).
After: 38/38 caught, 0/34 refused. The third set was written after the fix and never
tuned on before its first run (3/7 → 1/7, then the clause-opening "No" was fixed).

On 1,047 real labelled claims (`tools.eval_verification`, PHASE 11 held-out + final sets)
the fix changes no verdict: false rejects 9.1 % / 5.3 % before and after, and one more
perturbation caught in each set. An earlier version that let "non-" and a clause-opening
"No" scope too widely moved 7 real claims and 2 perturbations the wrong way; both fixed.

These are verifier inputs, not company positions: the clauses are synthetic.
"""
import pytest

from legalmind.assist.verification import agent_verify as av
from legalmind.assist.verification import guardrails as g
from legalmind.assist.verification import verify

FLIPS = [
    ('The Provider shall not be liable for indirect or consequential losses.',
     'The Provider is liable for indirect or consequential losses.'),
    ('The Customer shall not assign this Agreement without the prior written consent of the Provider.',
     'The Customer may assign this Agreement without the prior written consent of the Provider.'),
    ('Confidential Information shall not be disclosed to any third party.',
     'Confidential Information may be disclosed to any third party.'),
    ('The Customer shall pay all invoices within 30 days.',
     'The Customer may pay invoices within 30 days.'),
    ('The Provider may suspend the Services for non-payment.',
     'The Provider must suspend the Services for non-payment.'),
    ('Either party may terminate on thirty days written notice.',
     'Neither party may terminate on thirty days written notice.'),
    ("Service credits are the Customer's sole and exclusive remedy.",
     "Service credits are not the Customer's sole and exclusive remedy."),
    ('The Customer is prohibited from reselling the Services.',
     'The Customer is permitted to resell the Services.'),
    ("This Agreement does not grant the Customer any licence to the Provider's software.",
     "This Agreement grants the Customer a licence to the Provider's software."),
    ('The Provider will not be responsible for data loss caused by the Customer.',
     'The Provider is responsible for data loss caused by the Customer.'),
    ('Late payment shall attract interest at 1.5% per month.',
     'Late payment shall not attract interest at 1.5% per month.'),
    ('The Provider shall indemnify the Customer against third-party IP claims.',
     'The Provider shall not indemnify the Customer against third-party IP claims.'),
    ('The fees are non-refundable.',
     'The fees are refundable.'),
    ("The Customer shall not, directly or indirectly, solicit the Provider's employees.",
     "The Customer may solicit the Provider's employees."),
    ('Data shall not be transferred outside India without consent.',
     'Data may be transferred outside India without consent.'),
    ('The warranty does not cover hardware damage caused by misuse.',
     'The warranty covers hardware damage caused by misuse.'),
    ('The Provider is not obliged to provide backups of Customer data.',
     'The Provider is obliged to provide backups of Customer data.'),
    ('The Agreement shall automatically renew for successive one-year terms.',
     'The Agreement shall not automatically renew for successive one-year terms.'),
    ('Neither party shall be liable for delays caused by force majeure.',
     'Each party shall be liable for delays caused by force majeure.'),
    ('The Customer must not use the Services to store unlawful content.',
     'The Customer may use the Services to store unlawful content.'),
    ("The Supplier shall not subcontract any part of the Services without the Buyer's approval.",
     "The Supplier may subcontract any part of the Services without the Buyer's approval."),
    ('The Licensee shall not reverse engineer the Software.',
     'The Licensee may reverse engineer the Software.'),
    ('Payment shall be made within fifteen days of the invoice date.',
     'Payment may be made within fifteen days of the invoice date.'),
    ('The Provider is not liable for losses caused by third-party networks.',
     'The Provider is liable for losses caused by third-party networks.'),
    ('Customer data will not be used for training models.',
     'Customer data will be used for training models.'),
    ('The deposit is non-transferable.',
     'The deposit is transferable.'),
    ('The Customer may request a copy of its data on termination.',
     'The Customer must request a copy of its data on termination.'),
    ('The Vendor must maintain insurance cover of at least one crore rupees.',
     'The Vendor need not maintain insurance cover of at least one crore rupees.'),
    ('Any dispute shall be resolved by arbitration in Pune.',
     'No dispute shall be resolved by arbitration in Pune.'),
    ('Price increases are prohibited during the initial term.',
     'Price increases are permitted during the initial term.'),
    ('The Customer shall notify the Provider of any breach within 24 hours.',
     'The Customer may notify the Provider of any breach within 24 hours.'),
    ("The Provider owes no duty of care to the Customer's end users.",
     "The Provider owes a duty of care to the Customer's end users."),
    ('The Reseller shall not offer the Services under its own brand.',
     'The Reseller may offer the Services under its own brand.'),
    ('The Client must give ninety days notice before termination.',
     'The Client may give ninety days notice before termination.'),
    ('Interest is not payable on disputed amounts.',
     'Interest is payable on disputed amounts.'),
    ('The Partner is forbidden from sharing pricing with competitors.',
     'The Partner is allowed to share pricing with competitors.'),
    ("The Provider may audit the Customer's usage once a year.",
     "The Provider must audit the Customer's usage once a year."),
    ('Setup fees are non-recoverable.',
     'Setup fees are recoverable.'),
]
FAITHFUL = [
    ('Liability shall not exceed the fees paid in the preceding 12 months.',
     'Liability is capped at the fees paid in the preceding 12 months.'),
    ('The Provider shall not be liable for indirect or consequential losses.',
     'The Provider is not liable for indirect or consequential losses.'),
    ('The Customer shall not assign this Agreement without the prior written consent of the Provider.',
     "The Customer needs the Provider's prior written consent to assign this Agreement."),
    ('Either party may terminate on thirty days written notice.',
     'Either party may end the agreement with thirty days written notice.'),
    ('The fees are non-refundable.',
     'The fees cannot be refunded.'),
    ('Confidential Information shall not be disclosed to any third party.',
     'Confidential Information must not be disclosed to any third party.'),
    ('The Customer is prohibited from reselling the Services.',
     'The Customer may not resell the Services.'),
    ("Service credits are the Customer's sole and exclusive remedy.",
     "Service credits are the Customer's only remedy."),
    ('The Customer shall pay all invoices within 30 days.',
     'The Customer must pay all invoices within 30 days.'),
    ('No amendment is valid unless made in writing and signed by both parties.',
     'An amendment is valid only if made in writing and signed by both parties.'),
    ('The Provider will not be responsible for data loss caused by the Customer.',
     'The Provider is not responsible for data loss the Customer causes.'),
    ('Neither party shall be liable for delays caused by force majeure.',
     'Neither party is liable for delays caused by force majeure.'),
    ('The warranty does not cover hardware damage caused by misuse.',
     'Hardware damage caused by misuse is excluded from the warranty.'),
    ('Data shall not be transferred outside India without consent.',
     'Data may be transferred outside India only with consent.'),
    ('The Provider may suspend the Services for non-payment.',
     'The Provider can suspend the Services if the Customer does not pay.'),
    ("The Supplier shall not subcontract any part of the Services without the Buyer's approval.",
     "The Supplier may subcontract only with the Buyer's approval."),
    ('The Licensee shall not reverse engineer the Software.',
     'The Licensee is prohibited from reverse engineering the Software.'),
    ('Payment shall be made within fifteen days of the invoice date.',
     'Payment must be made within fifteen days of the invoice date.'),
    ('The Provider is not liable for losses caused by third-party networks.',
     "Losses caused by third-party networks are not the Provider's liability."),
    ('Customer data will not be used for training models.',
     'Customer data is never used for training models.'),
    ('The deposit is non-transferable.',
     'The deposit cannot be transferred.'),
    ('The Customer may request a copy of its data on termination.',
     'On termination the Customer can request a copy of its data.'),
    ('Price increases are prohibited during the initial term.',
     'Prices cannot be increased during the initial term.'),
    ('The Customer shall notify the Provider of any breach within 24 hours.',
     'The Customer must tell the Provider of any breach within 24 hours.'),
    ('No refund is payable unless the Provider fails to deliver the Services.',
     'A refund is payable only if the Provider fails to deliver the Services.'),
    ("The Provider owes no duty of care to the Customer's end users.",
     "The Provider has no duty of care towards the Customer's end users."),
    ('Neither party may disclose the terms of this Agreement.',
     'Neither party is allowed to disclose the terms of this Agreement.'),
    ('The Reseller shall not offer the Services under its own brand.',
     'The Reseller is not allowed to offer the Services under its own brand.'),
    ('The Client must give ninety days notice before termination.',
     'The Client is required to give ninety days notice before terminating.'),
    ('Interest is not payable on disputed amounts.',
     'No interest is payable on disputed amounts.'),
    ('The Partner is forbidden from sharing pricing with competitors.',
     'The Partner must not share pricing with competitors.'),
    ("The Provider may audit the Customer's usage once a year.",
     "The Provider has the right to audit the Customer's usage once a year."),
    ('Setup fees are non-recoverable.',
     'Setup fees cannot be recovered.'),
    ('The Customer shall not export data unless the Provider agrees in writing.',
     'The Customer may export data only if the Provider agrees in writing.'),
]


def _checks(source, claim):
    shown = {"D1": av.Evidence("D1", source, "4.2", "the selected document", False,
                               "documents")}
    return {v.check for v in av.verify(
        av.normalise([{"kind": "sourced", "text": claim, "cites": ["D1"]}]), shown,
        document_selected=True, assessment="n/a")}


@pytest.mark.parametrize("source,claim", FAITHFUL)
def test_the_deterministic_screens_pass_a_faithful_paraphrase(source, claim):
    """Model-free, so CI runs it: no polarity, modality or negation-parity rule refuses."""
    assert g._entailment_failure(claim, g._content_words(claim), [source],
                                 quantities=False) is None
    assert verify._aligned_shift(claim, source) is None
    assert not (av._NEGATION.search(claim) and not av._negates(source))
    assert not av._affirms_what_source_negates(claim, source)


@pytest.mark.parametrize("source,claim", [
    ("The Customer shall pay all invoices within 30 days.",
     "The Customer may pay invoices within 30 days."),
    ("The Customer shall notify the Provider of any breach within 24 hours.",
     "The Customer may notify the Provider of any breach within 24 hours."),
])
def test_a_duty_reported_as_an_option_is_caught_without_the_model(source, claim):
    """A three-letter verb is still a verb: "shall pay" reported as "may pay" slipped by."""
    assert g._entailment_failure(claim, g._content_words(claim), [source],
                                 quantities=False)


def test_no_later_than_is_not_a_negation():
    words = g._words("No later than thirty days the Customer shall pay the invoice")
    assert not g._negated(words, words.index("pay"))


needs_model = pytest.mark.skipif(verify._load() is None, reason="needs the local NLI model")


@needs_model
@pytest.mark.parametrize("source,claim", FLIPS)
def test_every_reversal_is_refused(source, claim):
    assert _checks(source, claim) & {"V3", "V4"}


@needs_model
@pytest.mark.parametrize("source,claim", FAITHFUL)
def test_no_faithful_paraphrase_is_refused(source, claim):
    assert not _checks(source, claim)

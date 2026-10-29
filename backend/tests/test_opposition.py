"""QA-001 (2026-10-29): a clause stating the OPPOSITE of a presence position is a
DEVIATION for Legal, never Acceptable. The tester's six synthetic sentences each MATCHED
the ratified standard on keyword co-occurrence alone (54.6: synthetic text only)."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from legalmind.analysis.opposition import opposing_signals
from legalmind.analysis.service import _sentences, opposed_span, our_indemnity_beyond
from legalmind.domain.enums import MappingState
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules

OPPOSITE = {
    "GOVLAW-MSA-001": "This Agreement shall be governed by and construed in accordance "
                      "with the laws of Singapore.",
    "IP-OWNERSHIP-MSA-001": "The Customer shall be the sole and exclusive owner of all "
                            "right, title, and interest in and to the Services.",
    "LIAB-EXCLUSIONS-MSA-001": "LeapSwitch shall be liable to the Customer for indirect, "
                               "incidental, special, consequential damages.",
    "ARBITRATION-MSA-001": "No dispute arising under this Agreement shall be referred to "
                           "arbitration; the courts alone shall decide it.",
    "SUSPENSION-NOTICE-CURE-MSA-001": "LeapSwitch may suspend the Services for non-payment "
                                      "immediately, without any written notice or cure "
                                      "period.",
}
#: The position as LeapSwitch's own paper words it: never opposed.
STATED = {
    "GOVLAW-MSA-001": "This Agreement shall be governed by and construed in accordance "
                      "with the laws of India, without regard to conflict of law "
                      "principles.",
    "IP-OWNERSHIP-MSA-001": "LeapSwitch is and shall remain the sole and exclusive owner "
                            "of all right, title, and interest in the Services. The "
                            "Customer shall remain the sole and exclusive owner of "
                            "Customer Data.",
    "LIAB-EXCLUSIONS-MSA-001": "In no event shall either party be liable for indirect, "
                               "incidental, special or consequential damages.",
    "ARBITRATION-MSA-001": "Any dispute not resolved amicably within thirty days shall be "
                           "referred to arbitration by a sole arbitrator.",
    "SUSPENSION-NOTICE-CURE-MSA-001": "LeapSwitch may suspend the Services for non-payment "
                                      "after fifteen days' prior written notice and a "
                                      "reasonable opportunity to cure.",
}


def _map(code: str, text: str):
    payload = json.loads((RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())
    rules = MappingRules.from_config(payload["mapping_rules"])
    clause = Clause(evidence_id=uuid4(), content=text, section_number="1")
    signals = opposing_signals([clause], payload["configuration"]["scope_key"],
                               rules.confirm_threshold, _sentences)
    return map_requirement(uuid4(), rules, [clause], extra_signals=signals)


@pytest.mark.parametrize("code", sorted(OPPOSITE))
def test_the_opposite_of_the_position_is_confirmed_and_opposed(code):
    mapping = _map(code, OPPOSITE[code])
    assert mapping.state is MappingState.CONFIRMED
    assert opposed_span(mapping)


@pytest.mark.parametrize("code", sorted(STATED))
def test_the_position_in_our_own_words_is_never_opposed(code):
    assert opposed_span(_map(code, STATED[code])) is None


def test_suspension_without_notice_for_another_cause_is_not_the_non_payment_position():
    """§13 is about non-payment; LeapSwitch's own MSA suspends without notice for
    security, which is a different clause."""
    mapping = _map("SUSPENSION-NOTICE-CURE-MSA-001",
                   "LeapSwitch may suspend the Services without prior notice in cases of "
                   "severe or imminent harm to the network.")
    assert opposed_span(mapping) is None


def test_an_indemnity_we_give_that_names_no_section_10_cause_is_too_broad():
    """The tester's "LeapSwitch shall indemnify, defend and hold harmless the Customer"
    named no cause, so §10's breadth check found nothing beyond it and it MATCHED."""
    def beyond(text):
        return our_indemnity_beyond([Clause(evidence_id=uuid4(), content=text,
                                            section_number="9")])
    assert beyond("LeapSwitch shall indemnify, defend and hold harmless the Customer "
                   "from and against all third-party claims.")
    assert beyond("LeapSwitch shall indemnify the Customer against third-party claims "
                  "that the Services infringe intellectual property rights.") is None
    assert beyond("LeapSwitch shall have no obligation to indemnify the Customer.") is None

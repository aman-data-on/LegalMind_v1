"""Grounding comparison — what "the same word" means (P1 item 3, 2026-09-11).

`_content_words` feeds two guardrails: the Ask answer's citation overlap (floor
0.5) and the Finding explanation's (floor 0.75). Both compare by set membership,
so a word counts as grounded only when both sides produce the identical token.

Measured on the live explanation corpus before this change: of 63 rejected
explanations, most were rejected for "ungrounded words" that ARE present in the
source in another surface form — `leapswitch's` against `Leapswitch`, `2,`
against `2`, `ends` against `end`, `specifies` against `specify`. The sentences
were grounded; the comparison was not measuring it.

Neither floor moved. These tests pin both halves of the contract: a real surface
variant now grounds, and invented content still does not. Every string below is
synthetic and asserts no legal conclusion (rule 21).
"""

from __future__ import annotations

import pytest

from legalmind.assist import explanations, guardrails
from legalmind.assist.explanations import Grounding
from legalmind.assist.state import AssistAnswerState


# ==========================================================================
# The normaliser itself
# ==========================================================================
@pytest.mark.parametrize("claim_word, source_text", [
    ("ends", "the term shall end on the final day"),
    ("ending", "the term shall end on the final day"),
    ("specifies", "the parties specify the notice period"),
    ("specifying", "the parties specify the notice period"),
    ("excludes", "this clause shall exclude consequential damages"),
    ("excluding", "this clause shall exclude consequential damages"),
    ("companies", "each company shall keep records"),
    ("obligations", "the obligation survives termination"),
    ("notices", "a written notice is required"),
])
def test_a_regular_surface_variant_grounds_in_its_stem(claim_word, source_text):
    assert guardrails._content_words(claim_word) & guardrails._content_words(source_text), \
        f"{claim_word!r} should ground in {source_text!r}"


@pytest.mark.parametrize("claim_word, source_text", [
    ("leapswitch's", "Leapswitch shall provide the services"),
    ("party's", "the party shall give notice"),
    ("2,", "clause 2 applies to renewals"),
    ("30,", "a period of 30 days applies"),
    ("one-year", "a one year term commences"),
    ("non-disclosure", "the Non-Disclosure obligation applies"),
    ("nondisclosure", "the non-disclosure obligation applies"),
])
def test_punctuation_and_compounds_ground(claim_word, source_text):
    assert guardrails._content_words(claim_word) & guardrails._content_words(source_text), \
        f"{claim_word!r} should ground in {source_text!r}"


def test_the_comparison_is_symmetric():
    """Both sides go through the same normaliser, so groundedness cannot depend
    on which text happened to be written first."""
    a = "The supplier's obligations end after thirty days."
    b = "The supplier obligation shall end after 30 days."
    assert guardrails._content_words(a) & guardrails._content_words(b)
    assert (guardrails._content_words(a) & guardrails._content_words(b)) == \
           (guardrails._content_words(b) & guardrails._content_words(a))


@pytest.mark.parametrize("invented", [
    "cyber insurance of five million dollars",
    "a penalty payable to the regulator",
    "arbitration seated in Singapore",
])
def test_invented_content_still_grounds_nowhere(invented):
    source = ("Neither party aggregate liability shall exceed the total fees paid "
              "in the twelve months preceding the claim.")
    claim = guardrails._content_words(invented)
    assert len(claim & guardrails._content_words(source)) / len(claim) < 0.5


def test_the_floors_are_unchanged_by_this_work():
    assert guardrails._GROUNDING_OVERLAP == 0.5
    assert explanations._GROUNDING_OVERLAP == 0.75


# ==========================================================================
# Ask's answer verification, end to end through the guardrail
# ==========================================================================
CHUNKS = [
    "Either party may terminate this Agreement on ninety days written notice.",
    "The Customer shall pay every undisputed invoice within thirty days of receipt.",
]


def test_a_paraphrased_but_grounded_answer_now_verifies():
    answer = "Either party terminates this Agreement by giving ninety days written notice [1]."
    assert guardrails.verify_answer(answer, CHUNKS).passed


def test_a_fabricated_answer_is_still_rejected():
    answer = "The Customer must maintain cyber insurance of five million dollars [1]."
    v = guardrails.verify_answer(answer, CHUNKS)
    assert not v.passed and v.state is AssistAnswerState.CLAIM_UNSUPPORTED


# ==========================================================================
# The explanation validator — a representative corpus (synthetic, inert)
# ==========================================================================
def _g(description, passages, classification="DEVIATION"):
    import uuid
    return Grounding(title="Widget handling", description=description,
                     classification=classification, passages=tuple(passages),
                     requirement_version_id=uuid.uuid4())


CORPUS = [
    # (label, classification, description, passages, sentence, should_be_accepted)
    ("simple MATCH", "MATCH", "The document must state a notice period.",
     ["Either party may terminate on ninety days written notice."],
     "The document states that either party may terminate on ninety days written notice.", True),
    ("paraphrased DEVIATION", "DEVIATION", "The document must state a renewal period.",
     ["The Agreement renews for successive periods of six months."],
     "The document renews for successive periods of six months, differing from the approved wording.",
     True),
    ("MISSING with description only", "MISSING",
     "The document must state how confidential information is returned.", [],
     "The document does not state how confidential information is returned.", True),
    ("short evidence", "DEVIATION", "The document must state a cure period.",
     ["Cure period: fifteen days."],
     "The document states a cure period of fifteen days.", True),
    ("multi-clause evidence", "DEVIATION", "The document must state payment timing.",
     ["Invoices are payable within thirty days.",
      "Late payment accrues interest at two percent per month.",
      "Disputed invoices are excluded from late interest."],
     "The document states invoices are payable within thirty days and disputed invoices are excluded.",
     True),
    ("legally sensitive wording is refused", "DEVIATION",
     "The document must state a liability position.",
     ["Liability is capped at the fees paid in the preceding twelve months."],
     "This clause is unenforceable and should be amended.", False),
    ("a number from nowhere is refused", "DEVIATION",
     "The document must state a notice period.",
     ["Either party may terminate on ninety days written notice."],
     "The document states a notice period of forty-five days, being 45 days.", False),
    ("invented subject matter is refused", "DEVIATION",
     "The document must state a notice period.",
     ["Either party may terminate on ninety days written notice."],
     "The document requires cyber insurance cover for every subcontractor engaged.", False),
]


@pytest.mark.parametrize("label, cls, description, passages, sentence, accept",
                         CORPUS, ids=[c[0] for c in CORPUS])
def test_the_explanation_validator_over_a_representative_corpus(
        label, cls, description, passages, sentence, accept):
    ok, reason = explanations.validate(sentence, _g(description, passages, cls))
    assert ok is accept, f"{label}: expected accept={accept}, got {ok} ({reason})"

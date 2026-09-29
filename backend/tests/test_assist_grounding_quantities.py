"""What a claim ASSERTS must be in the text it cites — `AM-25` r5, `AM-76`.

Two exact checks beside the lexical ratio: the FIGURES a claim states, and the
POLARITY it uses (negation, exclusivity, exception). `AM-76` requires a grounded
explanation to add no "facts, conditions, exceptions, quantities, or legal
conclusions not supported by evidence"; the ratio cannot enforce that, because each
of those is written in the source's own vocabulary and so scores high.

The overlap check in `verify_answer` is a bag-of-words ratio, so one decisive token is
diluted by the copied words around it. Measured against the ratified corpus on
2026-09-21, every answer in `UNSUPPORTED_FIGURES` below scored ABOVE the 0.5 grounding
floor and would have reached a reader: a notice period changed from 30 days to 90, an
invented liability cap, an invented expiry on a trade-secret obligation.

A notice period, a cap and an expiry are the whole content of a legal answer. Two
answers differing only in the number a reader will act on are not equally grounded,
however similar their vocabulary — which is why this is checked exactly and separately
rather than by lowering or raising the ratio.
"""
from __future__ import annotations

import pytest

from legalmind.assist import guardrails
from legalmind.assist.state import AssistAnswerState

PARTNER = (
    "CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001 §31.3 (Partner Agreement) Either party "
    "may terminate a Partner Agreement for convenience, for any reason, by providing at "
    "least 30 days' prior written notice to the other party. No early-termination fee "
    "or compensation is payable by either party."
)
LIABILITY = (
    "LIABILITY-TOS-001 13 Limitation of Liability (TOS) LEAPSWITCH'S TOTAL AGGREGATE "
    "LIABILITY TO YOU FOR ALL CLAIMS SHALL NOT EXCEED THE TOTAL FEES PAID BY YOU DURING "
    "THE TWELVE (12) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM."
)
NDA = (
    "CONF-SURVIVAL-NDA-001 §15 (NDA) Obligations survive termination or expiry for 3 "
    "years, except that obligations relating to trade secrets survive for as long as "
    "the information remains a trade secret."
)


@pytest.mark.parametrize("chunk,answer,figure", [
    # Each of these scored 0.57-0.92 on overlap alone and was ADMITTED before this check.
    (PARTNER, "Either party may terminate a Partner Agreement for convenience by "
              "providing at least 90 days' prior written notice to the other party [1].",
     "90"),
    (LIABILITY, "Leapswitch's total aggregate liability to you for all claims shall not "
                "exceed fifty lakh rupees [1].", "50"),
    (NDA, "Obligations survive termination or expiry for 3 years [1]. Trade secret "
          "obligations expire after ten years [1].", "10"),
])
def test_a_figure_the_evidence_does_not_state_is_refused(chunk, answer, figure):
    result = guardrails.verify_answer(answer, [chunk])
    assert result.state is AssistAnswerState.CLAIM_UNSUPPORTED
    assert any(figure in f for f in result.failures), result.failures


@pytest.mark.parametrize("chunk,answer", [
    # Quoting is always grounded.
    (PARTNER, "Either party may terminate a Partner Agreement for convenience, for any "
              "reason, by providing at least 30 days' prior written notice to the other "
              "party [1]."),
    # A paraphrase keeping the figure is grounded — the point of checking figures
    # exactly is that it does NOT punish different wording.
    (PARTNER, "Either side can end a Partner Agreement for any reason with at least 30 "
              "days' written notice [1]."),
    # "twelve (12) months" in the source matches "12 months" in the claim.
    (LIABILITY, "Our liability is capped at the total fees paid in the 12 months "
                "preceding the claim [1]."),
    # A claim stating no figure at all is unaffected by this check.
    (NDA, "Trade secret obligations continue for as long as the information remains a "
          "trade secret [1]."),
])
def test_a_claim_whose_figures_are_in_the_evidence_still_passes(chunk, answer):
    assert guardrails.verify_answer(answer, [chunk]).state is AssistAnswerState.ANSWERED


def test_a_number_word_used_as_an_article_is_not_a_quantity():
    """"either one of the parties" asserts no number. Treating it as one would refuse
    honest paraphrases for a figure the writer never stated.

    The UNIT travels with the number (2026-09-22). "30 days" and "30 months" are not
    the same quantity, and a set holding only {"30"} cannot tell them apart — a
    months-to-years swap scored identically and passed. The unit is normalised to the
    singular so "12 month period" still supports "12 months".
    """
    assert guardrails._quantities("either one of the parties may terminate") == set()
    assert guardrails._quantities("at least 30 days") == {"30", "day"}
    assert guardrails._quantities("ten years") == {"10", "year"}
    # Spelled-out and digit forms are the same quantity.
    assert guardrails._quantities("twelve months") == guardrails._quantities("12 months")


def test_a_unit_swap_is_a_different_quantity():
    """The reason the unit is tracked at all: every content word of "twelve years" is
    in a clause that says "twelve (12) months", so overlap alone admits it."""
    cap = ("The total liability shall not exceed the fees paid in the twelve (12) "
           "months preceding the claim.")
    swapped = "Liability is capped at the fees paid in the twelve years preceding the claim [1]."
    assert not guardrails.verify_answer(swapped, [cap]).passed


# --------------------------------------------------------------------------
# Polarity — `AM-76`'s "conditions" and "exceptions"
# --------------------------------------------------------------------------
@pytest.mark.parametrize("chunk,answer,carried", [
    # Inverts the position: the source says either party MAY terminate on notice.
    # Measured overlap 0.62 — it PASSED before this check.
    (PARTNER, "A Partner Agreement may only be terminated with the written consent "
              "of both parties [1].", "exclusivity"),
    # A carve-out the cap clause does not make. Measured overlap 0.67 — PASSED.
    (LIABILITY, "Our liability is capped at the fees paid in the 12 months before "
                "the claim, except in cases of gross negligence [1].", "exception"),
])
def test_a_polarity_the_evidence_does_not_carry_is_refused(chunk, answer, carried):
    result = guardrails.verify_answer(answer, [chunk])
    assert result.state is AssistAnswerState.CLAIM_UNSUPPORTED
    assert any(carried in f for f in result.failures), result.failures


@pytest.mark.parametrize("chunk,answer", [
    # The source itself carves out trade secrets, so a paraphrase may restate it.
    (NDA, "Obligations survive for 3 years, except that trade secret obligations "
          "continue for as long as the information remains a trade secret [1]."),
    # The source itself negates ("No early-termination fee"), so a negation is not
    # introduced — this must NOT be read as a new condition.
    (PARTNER, "Either side can end a Partner Agreement for any reason with at least "
              "30 days' written notice, and no early-termination fee is payable [1]."),
])
def test_restating_a_polarity_the_evidence_carries_is_not_an_invention(chunk, answer):
    assert guardrails.verify_answer(answer, [chunk]).state is AssistAnswerState.ANSWERED


def test_polarity_is_compared_by_class_not_by_word():
    """The point of classes: the evidence's "No ..." licenses the claim's "neither",
    so a paraphrase is not refused merely for choosing a different negator."""
    assert guardrails._introduced_polarity("neither party pays a fee",
                                           ["No fee is payable"]) == []
    assert guardrails._introduced_polarity("only on written consent",
                                           ["No fee is payable"]) == ["exclusivity"]

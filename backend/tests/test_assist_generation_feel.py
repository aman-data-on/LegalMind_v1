"""The answer's WORDING is part of the product — Phase 3 "feel", 2026-09-18.

Owner goal: Ask answers should read clear and natural, "without changing retrieval,
authority, security, gate, or legal decisions". These tests pin the two prose rules
that were added for it and, more importantly, pin the boundary they must not cross:
grounding is still decided mechanically by `verify_answer`, not by the prompt.
"""
from __future__ import annotations

from legalmind.assist import generation, guardrails


def test_the_prompt_asks_for_the_answer_first_and_plain_prose():
    template = generation.PROMPT_TEMPLATE
    assert "Open with the answer itself" in template
    assert "do not restate the question" in template
    assert "no asterisks for emphasis" in template


def test_the_citation_rule_is_untouched():
    """Rule 1 is the grounding contract. Phase 3 changed wording, not grounding."""
    template = generation.PROMPT_TEMPLATE
    assert "Every sentence of your answer MUST end with citation markers" in template
    assert "Use nothing but the excerpts" in template
    assert "Never state whether anything complies" in template


def test_the_version_was_bumped_with_the_template():
    """A changed prompt under an unchanged version is an unauditable payload
    (`AM-30` t5 — the prompt version is recorded with every answer)."""
    assert generation.PROMPT_VERSION == "grounded-answer-3"


def test_the_rag_preamble_was_not_merely_UGLY_it_cost_answers():
    """Rule 6 is safety-POSITIVE, which is why it is worth making.

    The grounding check scores a sentence's content words against its cited chunk.
    "Based on the provided excerpts, ..." injects `based`, `provided` and `excerpts`
    — words no contract clause contains — into the claim itself, so the identical
    fact fails grounding when it is prefaced and passes when it is not. The
    preamble was not just a retrieval tell; it was spending the reader's answer.
    """
    chunks = ["total aggregate liability shall not exceed the total fees paid "
              "during the twelve months preceding the claim"]
    natural = guardrails.verify_answer(
        "The cap is twelve months of total fees paid [1].", chunks)
    prefaced = guardrails.verify_answer(
        "Based on the provided excerpts, the cap is twelve months of fees [1].",
        chunks)
    assert natural.state.name == "ANSWERED", natural.failures
    assert prefaced.state.name == "CLAIM_UNSUPPORTED"


def test_an_uncited_opening_sentence_still_fails_closed():
    """The regression rule 6 could have introduced, pinned so it cannot."""
    chunks = ["liability shall not exceed the total fees paid in twelve months"]
    verification = guardrails.verify_answer(
        "Here is what the agreement says. The cap is twelve months of fees [1].",
        chunks)
    assert verification.state.name != "ANSWERED"
    assert any("no citation" in f for f in verification.failures)

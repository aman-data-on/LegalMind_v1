"""The general-knowledge question — recognised, and deliberately not answered.

"What is an NDA?" used to return three Company Standards (NON-SOLICIT, GOVLAW,
RESIDUALS), because a document-less Ask has no primary route and the POSITIONS fallback
is unconditional. The organization's positions were presented as though they defined
what an NDA is.

`AM-25` r5 forbids generating the answer — "no answer reaches a user unless every claim
in it resolves to retrieved evidence", and a general explanation resolves to none. So
the fix is the half that needs no amendment: recognise the question, search nothing, and
say plainly what this system does answer.
"""

from __future__ import annotations

import pytest

from legalmind import config
from legalmind.assist import intent, routing, service

PERMS = frozenset({"assist.ask", "configuration.view", "legal_position.view"})


@pytest.mark.parametrize("question", [
    "What is an NDA?",
    "What is arbitration?",
    "What is a warranty?",
    "What does indemnity mean?",
    "Explain force majeure",
    "Explain indemnity in simple language",
    "NDA kya hota hai?",
    "indemnity ka matlab kya hai?",
])
def test_a_general_legal_question_is_recognised(question):
    assert intent.is_general_knowledge_question(question) is True


@pytest.mark.parametrize("question", [
    # The owner's own 2026-09-09 case. A compound TERM, not a bare concept, and it is
    # answered from the ratified positions — a rule matching any single concept word
    # would have swallowed it.
    "What is the termination notice period?",
    "How long do confidentiality duties last?",
    # Possessive or deictic: a particular instrument, which a real source answers.
    "What is our NDA confidentiality period?",
    "What is our liability cap?",
    "What does this agreement say about confidentiality?",
    "Ismein confidentiality period kya hai?",
    # Other shapes keep their own routes.
    "What can LegalMind do?",
    "What does section 138 of the NI Act say?",
    "Does this comply with our standard?",
])
def test_a_question_a_real_source_can_answer_is_not_general_knowledge(question):
    """The costly error is the false POSITIVE: sending a question about the
    organization's own position to a general explanation. The rule is narrow for that
    reason — a possessive, a deictic, a statute reference or a compound term all
    exclude it."""
    assert intent.is_general_knowledge_question(question) is False


def test_the_route_searches_nothing():
    """It is not that the Constitution is searched and discarded — it is never searched.
    No authorised source holds the definition of "indemnity"."""
    plan = routing.plan("What is an NDA?", has_document=True, permissions=PERMS,
                        statutes_available=True)
    assert plan.general_knowledge is True
    assert plan.domains == () and plan.fallback == () and plan.searched == ()


def test_the_answer_says_what_it_is_not(monkeypatch):
    """`AM-25` r3: the lane never states an organizational legal position absent from a
    ratified source. The reply must not be mistakable for one."""
    text = service.GENERAL_KNOWLEDGE_TEXT.lower()
    assert "not your company's position" in text
    assert "approved" in text and "standards" in text
    # It redirects rather than dead-ends — the reader is told what to ask next.
    assert "upload" in text or "open a document" in text


def test_the_answer_states_no_legal_position():
    assert intent.is_verdict_statement(service.GENERAL_KNOWLEDGE_TEXT) is False


def test_generation_is_off_until_am_71(monkeypatch):
    """`AM-25` r5 forbids generating it. The flag exists so the amendment can turn it
    on; until then the system declines to answer rather than inventing one."""
    monkeypatch.delenv("LEGALMIND_GENERAL_KNOWLEDGE", raising=False)
    assert config.general_knowledge_generation_enabled() is False

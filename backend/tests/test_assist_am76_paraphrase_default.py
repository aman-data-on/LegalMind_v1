"""`AM-76` (AB-26, owner 2026-09-21) — a paraphrase by default, verbatim on request.

`AM-67` r3 required the ratified quote to sit beside every Domain A answer, always.
Measured on the live corpus, that is what made Ask read as an extract rather than an
answer: the reader's question was met with a fixed pointer sentence and the clause.

`AM-76` supersedes it. A normal question is answered with a short grounded paraphrase
and its citation; the ratified text is shown in full only when the reader ASKED for it,
or when the paraphrase could not be verified (r4 — fail closed to the authorized
quote, `AM-67` r8's behaviour, unchanged).

The quote never leaves the payload: it stays in `positions` for the citation and its
provenance (`AM-32` r4). What changed is whether the reader is shown it INSTEAD of an
explanation.
"""

from __future__ import annotations

import pytest

from legalmind.assist import generation, service
from legalmind.assist.intent import is_exact_text_request
from tests.test_assist_ask import (  # noqa: F401  (fixtures)
    NOTICE_POSITION,
    USER_PERMS,
    _conversation,
    _fake_generation,
    _ratified_positions,
    indexed_contract,
    storage,
)

QUESTION = "What notice is needed to end the agreement early?"
EXACT = "Give me the exact wording about ending the agreement early."
PARAPHRASE = ("Either party can end the agreement early by giving thirty (30) days' "
              "written notice [1].")


def _aid(monkeypatch, text):
    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")
    monkeypatch.setattr(
        generation, "generate_position_reading_aid",
        lambda *a, **k: generation.GenerationResult(
            text=text, model="fake", prompt_version="position-reading-aid-2",
            payload_sha256="0" * 64, latency_ms=1))


def _ask(db, user, contract, question):
    return service.ask(db, conversation_id=_conversation(db, user, contract),
                       document_version_id=None, permissions=USER_PERMS,
                       question=question)


# --------------------------------------------------------------------------
# r1 — a normal question gets the explanation, NOT the clause
# --------------------------------------------------------------------------
def test_a_normal_question_is_answered_by_paraphrase_without_the_quote_sentence(
        db, user, indexed_contract, tmp_path, monkeypatch):
    contract, _ = indexed_contract
    _ratified_positions(db, user, tmp_path, NOTICE_POSITION)
    _aid(monkeypatch, PARAPHRASE)
    out = _ask(db, user, contract, QUESTION)

    assert out.text == PARAPHRASE, out.text
    # The defect AM-76 exists to end: the pointer sentence is no longer appended.
    assert "quoted below" not in out.text
    assert out.exact_text_requested is False
    # ...and the quote is still in the payload for the citation (`AM-32` r4).
    assert out.positions and out.positions[0]["content"]


# --------------------------------------------------------------------------
# r2 — the reader asked for the source's own words
# --------------------------------------------------------------------------
def test_an_explicit_exact_text_request_returns_the_verbatim_wording(
        db, user, indexed_contract, tmp_path, monkeypatch):
    contract, _ = indexed_contract
    _ratified_positions(db, user, tmp_path, NOTICE_POSITION)

    def must_not_run(*a, **k):
        raise AssertionError("a paraphrase was generated for an exact-text request")

    monkeypatch.setenv("LEGALMIND_POSITION_SYNTHESIS", "on")
    monkeypatch.setattr(generation, "generate_position_reading_aid", must_not_run)
    out = _ask(db, user, contract, EXACT)

    assert out.exact_text_requested is True
    assert out.text == service.POSITIONS_EXACT_TEXT
    assert out.positions and "thirty (30) days" in out.positions[0]["content"]


# --------------------------------------------------------------------------
# r4 — a paraphrase that cannot be verified falls back to the authorized quote
# --------------------------------------------------------------------------
def test_an_unverifiable_paraphrase_falls_back_to_the_quote(
        db, user, indexed_contract, tmp_path, monkeypatch):
    """The figure is wrong, so the guardrail refuses it. The reader must still get the
    real text rather than nothing — the locked fallback, not a refusal."""
    contract, _ = indexed_contract
    _ratified_positions(db, user, tmp_path, NOTICE_POSITION)
    _aid(monkeypatch, "Either party can end the agreement on ninety (90) days' "
                      "written notice [1].")
    out = _ask(db, user, contract, QUESTION)

    assert out.text == service.POSITIONS_ONLY_TEXT
    assert out.positions and "thirty (30) days" in out.positions[0]["content"]


# --------------------------------------------------------------------------
# The detector itself — both directions, every script (`AM-69`)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    "Give me the exact wording about partner termination.",
    "quote the clause on liability",
    "show me verbatim",
    "what exactly does the Constitution say?",
    "give me the original text",
    "I want the exact language of the clause",
    "मुझे मूल शब्द चाहिए",
    "hubahu wording dijiye",
])
def test_an_explicit_request_for_the_source_text_is_detected(question):
    assert is_exact_text_request(question), question


@pytest.mark.parametrize("question", [
    # The whole point: ordinary questions must NOT get a wall of clause text.
    "How can a partner agreement be ended?",
    "What is our liability cap for the terms of service?",
    "Tell me about MSA auto-renewal.",
    "Who handles support for partner customers?",
    "Does the constitution say anything about MSA auto-renewal?",
    # "exactly" alone is emphasis, and "say"/"clause" alone is how normal questions
    # are phrased — neither may trigger verbatim on its own.
    "what exactly is the cap?",
    "What does the clause say about termination?",
    "What does our standard state about liability?",
    "पार्टनर एग्रीमेंट कैसे खत्म होता है?",
    "partner agreement kaise end kar sakte hain",
])
def test_an_ordinary_question_is_not_an_exact_text_request(question):
    assert not is_exact_text_request(question), question


# --------------------------------------------------------------------------
# r2 — the request carries no subject of its own
# --------------------------------------------------------------------------
def test_an_exact_text_request_inherits_the_subject_of_the_previous_turn(
        db, user, indexed_contract, tmp_path, monkeypatch):
    """"Quote the termination clause verbatim" names no clause. Its own words are
    "quote", "clause" and "verbatim", which match nothing in any contract, so left
    unresolved the document lane retrieves NOTHING and the question falls through to
    whatever else the reader may read.

    Measured on a live NDA (2026-09-22), asked straight after a termination answer:
    zero document chunks retrieved, and the reader was shown two ratified standards
    for VENDOR_AGREEMENT and DISTRIBUTION_AGREEMENT — neither their document nor its
    type. An exact-text request is always ABOUT something already discussed, so it
    inherits the previous turn's subject through the same resolver a follow-up uses.
    """
    from legalmind.assist import intent

    contract, version = indexed_contract
    conversation = _conversation(db, user, contract)

    _fake_generation(monkeypatch, PARAPHRASE)
    service.ask(db, conversation_id=conversation, document_version_id=version.id,
                permissions=USER_PERMS, question=QUESTION)

    bare = "Quote that clause verbatim."
    # The premise: it is NOT a follow-up by wording, which is why this needed fixing.
    assert not intent.is_follow_up(bare)
    assert intent.is_exact_text_request(bare)

    # The observable effect of the fix: the subject resolver runs for this turn.
    # Asserted at that seam rather than on citations, because whether a two-clause
    # synthetic fixture clears the evidence gate is a property of the fixture, not of
    # this change — the live-corpus behaviour is in the commit message, measured.
    seen: list[str] = []
    real = service._resolve_follow_up
    monkeypatch.setattr(service, "_resolve_follow_up",
                        lambda prior, q: (seen.append(q), real(prior, q))[1])
    service.ask(db, conversation_id=conversation, document_version_id=version.id,
                permissions=USER_PERMS, question=bare)
    assert bare in seen, "the exact-text request did not inherit the previous subject"


def test_a_first_turn_exact_text_request_is_unchanged(
        db, user, indexed_contract, tmp_path, monkeypatch):
    """With no previous turn there is nothing to inherit, and the question is used as
    asked — the fix must not invent a subject where the conversation has none."""
    from legalmind.assist import intent

    contract, version = indexed_contract
    prior: list = []
    assert not (bool(prior) and (intent.is_follow_up("Quote that clause verbatim.")
                                 or intent.is_exact_text_request("Quote that clause verbatim.")))

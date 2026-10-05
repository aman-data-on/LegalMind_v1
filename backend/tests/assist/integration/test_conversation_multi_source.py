"""Roadmap §15 — conversation intelligence, through the multi-source Ask path
(`AM-94`). The roadmap's six behaviours, each proven on `service.ask` with the flag
on, no provider: a first question; a follow-up inheriting its topic; an ambiguous
follow-up; a changed topic; a follow-up carrying an unverified user claim; and the
guarantee that conversation text is context, never evidence, and that whole history
is never injected into a retrieval query.

Sources are the real Constitution (`constitution.ingest`) beside the inert synthetic
statute the Ask tests use, so topic carryover is exercised on actual records.
"""
import logging

import pytest

from legalmind import config
from legalmind.assist import service
from legalmind.assist.knowledge import constitution
from legalmind.assist.llm import generation
from legalmind.assist.verification import verify
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _synthetic_statute,
    storage,
)
from tools.eval_generation import stub

PERMS = frozenset({"assist.ask", "legal_position.view", "configuration.view"})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    go_offline(monkeypatch)


def go_offline(monkeypatch):
    """The stub model, the stand-in reranker and a passing verifier — no network."""
    monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", "no_document")
    monkeypatch.setattr(verify, "check_answer",
                        lambda text_, *a, **k: verify.Result(True, text_, [], []))
    monkeypatch.setattr(generation, "generate_contract_answer", stub)
    monkeypatch.setattr(generation, "generate",
                        lambda q, chunks, **k: generation.GenerationResult(
                            "Every handler shall handle every widget with synthetic care "
                            "[1].", "legacy-fake", "grounded-answer-5", "0" * 64, 1))
    # No cross-encoder in CI: a deterministic stand-in scores a text by how much of the
    # QUERY's content it shares — relevant when it shares any, so a follow-up whose
    # query carries the anchor's subject finds the anchor's sources, as the real
    # reranker does (measured, PHASE 8).
    from legalmind.assist.retrieval import rerank
    from legalmind.assist.verification import guardrails

    def fake_scores(q, texts, **k):
        need = guardrails._content_words(q)
        return [10.0 if need & guardrails._content_words(t) else -10.0 for t in texts]
    monkeypatch.setattr(rerank, "scores", fake_scores)
    monkeypatch.setattr(rerank, "scores_many",
                        lambda qs, texts, **k: [fake_scores(q, texts) for q in qs])


@pytest.fixture
def corpus(db, tmp_path):
    constitution.ingest(db)
    _synthetic_statute(db, tmp_path)
    return db


def _traces(caplog):
    return [r.legalmind_fields for r in caplog.records
            if r.getMessage() == "assist.ask.trace"]


def _thread(db, user, *questions, caplog):
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    out = []
    for i, q in enumerate(questions):
        out.append(service.ask(db, conversation_id=conv, question=q,
                               document_version_id=None, permissions=PERMS,
                               request_id=f"conv-{i}"))
    return conv, out, _traces(caplog)


def _query(db, conv, ordinal):
    return db.execute(__import__("sqlalchemy").text(
        f'SELECT r.query_text FROM "{config.assist_schema()}".retrieval_runs r JOIN '
        f'"{config.assist_schema()}".messages m ON m.id = r.message_id WHERE '
        f"m.conversation_id = :c AND m.ordinal = :o"), {"c": conv, "o": ordinal}).scalar()


FIRST = "What does our Constitution say about early termination of a fixed-term deal?"
CLAIM = "What if the customer says they were promised 6 months?"


def test_a_follow_up_inherits_the_topic_and_the_claim_stays_a_claim(corpus, user, caplog):
    caplog.set_level(logging.INFO)
    conv, (first, second), traces = _thread(corpus, user, FIRST, CLAIM, caplog=caplog)
    assert traces[0]["path"] == traces[1]["path"] == service.MULTI_SOURCE
    assert first.answer_state.value == second.answer_state.value == "ANSWERED"
    # The topic carries through the PLAN; the retrieval query stays the reader's own
    # turn (it is not anaphoric), so no earlier question is pasted into it.
    assert _query(corpus, conv, 2) == CLAIM
    assert second.text.count(FIRST) == 0
    # The reader's figure is context, never the position (`AM-78`, roadmap §15).
    assert "No company position states 6 months" in second.text
    assert not any("policy is 6 months" in s for s in second.text.split(". "))
    assert any(r.startswith("CONST:14") for r in traces[1]["evidence_refs"]), \
        "topic carried: the early-exit section answers the follow-up"


def test_an_ambiguous_follow_up_keeps_the_last_self_contained_anchor(corpus, user, caplog):
    caplog.set_level(logging.INFO)
    conv, outs, traces = _thread(corpus, user, FIRST, CLAIM, "And what about the law on that?",
                                 caplog=caplog)
    third = _query(corpus, conv, 4)
    assert FIRST not in third, "the whole history is never injected into the query"
    # The early-exit topic has two homes: §14 (the position) and §28.4.1 (the
    # company's reading of Contract Act ss. 73/74 on early-termination compensation).
    # "And what about the law on that?" asks for the second; which of the two leads
    # depends on vector ranking, which CI does not have (2026-09-28, PR #121).
    assert any(r.startswith(("CONST:14", "CONST:28.4.1"))
               for r in traces[2]["evidence_refs"]), \
        "three turns on, the first turn's topic still carries"


def test_a_changed_topic_is_not_expanded_with_the_earlier_one(corpus, user, caplog):
    caplog.set_level(logging.INFO)
    new_topic = "What does section 3 of the Synthetic Widgets Act say about widget handling?"
    conv, outs, traces = _thread(corpus, user, FIRST, new_topic, caplog=caplog)
    assert _query(corpus, conv, 2) == new_topic
    assert not any(r.startswith("CONST:14") for r in traces[1]["evidence_refs"])
    assert any(r.startswith("STAT:Synthetic") for r in traces[1]["evidence_refs"])


def test_an_earlier_answer_never_becomes_evidence_for_a_later_turn(corpus, user, caplog,
                                                                  monkeypatch):
    caplog.set_level(logging.INFO)
    seen = []
    real = generation.generate_contract_answer

    def spy(question, block, **k):
        seen.append(block)
        return real(question, block, **k)
    monkeypatch.setattr(generation, "generate_contract_answer", spy)
    conv, (first, second), _ = _thread(corpus, user, FIRST, CLAIM, caplog=caplog)
    assert first.text.split(" [")[0][:60] not in seen[1], "no earlier ANSWER in a payload"
    assert "[A] WHAT THE READER SAID" in seen[1]
    assert seen[1].count("\n- ") <= 2, "only the bounded prior questions travel"


def test_a_follow_up_never_widens_what_the_caller_may_read(corpus, user, caplog):
    caplog.set_level(logging.INFO)
    reader = frozenset({"assist.ask"})            # no positions, no Constitution
    conv = service.create_conversation(corpus, user_id=user.id, contract_id=None)
    for q in (FIRST, CLAIM):
        service.ask(corpus, conversation_id=conv, question=q, document_version_id=None,
                    permissions=reader, request_id="conv-x")
    for t in _traces(caplog):
        assert "CONSTITUTION" not in t.get("retrievers", []) and \
            "POSITIONS" not in t.get("retrievers", [])

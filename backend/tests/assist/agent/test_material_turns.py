"""O-8 (owner, 2026-11-02): an Ask chat file's text reaches a model ONLY on a turn about
it — attached with the message, named by the reader's words, or a short follow-up to an
answer that cited it. Decided in code; asserted on the payload the fake provider
receives. Synthetic text only (rule 21)."""
from __future__ import annotations

import dataclasses
import json

from legalmind.assist import service
from legalmind.assist.agent import agent, attachments, tools
from legalmind.assist.agent.attachments import (
    ATTACHED_NOW,
    FOLLOW_UP,
    NAMED,
    NOT_ABOUT_IT,
    material_reason,
)
from legalmind.ingestion.validation import DOCX_MIME
from tests.assist.agent.test_assist_agent import PERMS, Scripted
from tests.assist.agent.test_assist_attachments import _add
from tests.test_ingestion import build_docx

MARKER = "zephyrine"          # a word only the file holds
FILE = build_docx(["SUPPLY AGREEMENT",
                   f"5. The {MARKER} supplier shall deliver within 30 days.",
                   f"7. Either party may terminate the {MARKER} supply on 60 days' notice."])


def _chat(db, user, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    ctx = tools.ToolContext.open(
        db, user_id=user.id, permissions=PERMS,
        conversation_id=service.create_conversation(db, user_id=user.id,
                                                    contract_id=None))
    return ctx, ctx.conversation_id


def _attach(db, conv):
    _add(db, conversation_id=conv, data=FILE, kind=attachments.FILE,
         filename="supply-terms.docx", mime=DOCX_MIME)


def _ask(db, ctx, question):
    """The service's order: the question stored (linking files sent with it), then the
    turn. Returns the turn and everything the provider was sent."""
    service._append_turn(db, ctx.conversation_id, "USER", question)
    p = Scripted()
    t = agent.run_turn(p, ctx, question)
    return t, p


def _sent(p) -> str:
    return json.dumps([c["contents"] for c in p.seen])


def _answer_citing_the_file(db, ctx, t):
    """Store the reply as `_agent_answer` does, citing one of the file's records."""
    reply = service._append_turn(db, ctx.conversation_id, "ASSISTANT",
                                 f"Clause 5 says the {MARKER} supplier delivers in 30 days.")
    answer = service._persist_answer(db, reply, None, service.AssistAnswerState.ANSWERED,
                                     model=None, prompt_version_id=None, latency_ms=None)
    att = [k for k, s in t.registry.shown.items()
           if s.record.source_ref.startswith("ATT:")]
    assert att
    t.registry.persist(reply, answer, att[:1])


def test_a_file_sent_with_the_question_is_read(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    t, p = _ask(db, ctx, "Is the delivery period reasonable?")
    assert t.material == ATTACHED_NOW and MARKER in _sent(p)
    assert agent.turn_log(t)["material"] == ATTACHED_NOW


def test_an_unrelated_question_sends_nothing_of_the_file(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    first, _ = _ask(db, ctx, "What does clause 5 of this say?")
    _answer_citing_the_file(db, ctx, first)

    t, p = _ask(db, ctx, "Under Indian law, what makes a contract voidable for coercion "
                         "and undue influence in general?")
    assert t.material == NOT_ABOUT_IT
    sent = _sent(p)
    assert MARKER not in sent and "<user_material" not in sent
    assert "supply-terms" not in sent                       # not even its name
    offered = {d["name"] for s in p.seen for d in (s["tools"] or [])}
    assert offered and not offered & {"search_attachment", "list_attachments"}
    # and were the model to ask anyway, the tools return nothing
    quiet = dataclasses.replace(ctx, material=False)
    att_id = str(attachments.list_for(db, conv)[0].id)
    found = tools.run(quiet, "search_attachment", {"attachment_id": att_id,
                                                   "query": "delivery"})
    assert found.error == "NOT_FOUND" and not found.records


def test_naming_the_file_and_a_short_follow_up_read_it(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    _ask(db, ctx, "Hello")                                  # the file went with this one
    service._append_turn(db, conv, "ASSISTANT", "Hello! How can I help?")

    t, p = _ask(db, ctx, "What does clause 5 of this say?")
    assert t.material == NAMED and MARKER in _sent(p)
    _answer_citing_the_file(db, ctx, t)

    t, p = _ask(db, ctx, "and clause 7?")
    assert t.material == NAMED and MARKER in _sent(p)
    _answer_citing_the_file(db, ctx, t)

    t, p = _ask(db, ctx, "What about the termination notice?")
    assert t.material == FOLLOW_UP and MARKER in _sent(p)
    _answer_citing_the_file(db, ctx, t)

    t, p = _ask(db, ctx, "What does our Constitution say on late fees?")
    assert t.material == NOT_ABOUT_IT and MARKER not in _sent(p)


def test_the_files_own_name_is_naming_it(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    service._append_turn(db, conv, "USER", "hi")
    service._append_turn(db, conv, "ASSISTANT", "Hello!")
    for question, reason in (
            ("Summarise supply-terms for me", NAMED),
            ("Summarise", NAMED),                        # a document task, no topic
            ("Can you check the attached?", NAMED),
            ("isme termination kya hai?", NAMED),
            ("What is the stamp duty on a lease deed in Maharashtra under the Act "
             "and the rules?", NOT_ABOUT_IT),
            ("What is force majeure?", NOT_ABOUT_IT)):
        service._append_turn(db, conv, "USER", question)
        assert material_reason(db, conv, question) == reason, question
        service._append_turn(db, conv, "ASSISTANT", "An answer.")


def test_a_chat_with_no_material_has_no_reason(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    assert material_reason(db, conv, "What does clause 5 of this say?") is None


def _reviewed(db, conv):
    """The AM-143 file review, stored as the router stores it — no ledger citation."""
    service._append_turn(db, conv, "ASSISTANT", "Hello!")
    service.record_file_review(db, conversation_id=conv, question="review this file",
                               filename="supply-terms.docx", findings=[], refused=None,
                               request_id=None)


def test_a_follow_up_after_a_file_review_reads_the_file(db, user, monkeypatch):
    """Review (2): after "review this", the next short questions are about the file —
    never answered from the Constitution as if it were the contract's cap."""
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    service._append_turn(db, conv, "USER", "hi")
    for question in ("What's the liability cap?", "is this okay?", "kya ye theek hai?",
                     "Who are the parties?"):
        _reviewed(db, conv)
        t, p = _ask(db, ctx, question)
        assert t.material in (FOLLOW_UP, NAMED), question
        assert MARKER in _sent(p), question


def test_a_statute_named_with_a_clause_number_is_not_the_file(db, user, monkeypatch):
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    service._append_turn(db, conv, "USER", "hi")
    service._append_turn(db, conv, "ASSISTANT", "Hello!")
    for question, reason in (
            ("Check clause 12 against the Contract Act", NOT_ABOUT_IT),
            ("What does the Indian Contract Act say on penalties?", NOT_ABOUT_IT),
            ("Check clause 12 of this against the Contract Act", NAMED)):
        service._append_turn(db, conv, "USER", question)
        assert material_reason(db, conv, question) == reason, question
        service._append_turn(db, conv, "ASSISTANT", "An answer.")


def test_no_earlier_turn_carries_the_material_into_an_unrelated_turn(db, user,
                                                                     monkeypatch):
    """Review (1): the history is a path too — a paste kept as the question itself, the
    reply that quoted the file, the contract review's clause list."""
    ctx, conv = _chat(db, user, monkeypatch)
    _attach(db, conv)
    paste = (f"From the customer: the {MARKER} rollout slipped by nine days because the "
             "racks arrived late and the cabling vendor could not finish the work in the "
             "agreed window, and our team then had to rebuild two of the storage nodes "
             "after the firmware update failed on both of them during the first night, "
             "which pushed the handover past the date the customer had announced. The "
             "customer now wants a credit for every day of delay and a written plan for "
             "the remaining sites before the next billing cycle starts.")
    assert attachments.carries_material(paste)
    service._append_turn(db, conv, "USER", paste)
    service._append_turn(db, conv, "ASSISTANT", f"The {MARKER} delay was nine days.")
    service.record_deal_turn(
        db, conversation_id=conv, question="review this agreement", answers=None,
        text_out="Reviewed.", request_id=None,
        payload={"kind": "deal_review", "rows": [
            {"topic": f"{MARKER} delivery", "needs": "MUST_CHANGE",
             "cells": {"f": {"clause": "5"}}}]})
    t, p = _ask(db, ctx, "Under Indian law, what makes a contract voidable for coercion "
                         "and undue influence in general?")
    assert t.material == NOT_ABOUT_IT
    sent = _sent(p)
    assert MARKER not in sent and attachments.MATERIAL_TURN_PLACEHOLDER in sent

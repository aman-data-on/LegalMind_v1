"""The Ask agent loop in shadow — Phase 3 (2026-10-03). A scripted fake provider, so no
test spends a model call. Synthetic text only (rule 21)."""
from __future__ import annotations

import json
import logging

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import agent, generation, service, tools
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    _ratified_positions,
    indexed_contract,
    storage,
)
from tests.test_assist_attachments import _add

PERMS = frozenset({"assist.ask", "legal_position.view"})
FINAL = json.dumps({"blocks": [{"kind": "reasoning", "text": "An answer."}],
                    "assessment": "n/a"})


def _turn(*, calls=(), text_=""):
    parts = tuple({"functionCall": c} for c in calls) or ({"text": text_},)
    return generation.TurnResult(text=text_, model="fake-model", prompt_version="x",
                                 payload_sha256="0" * 64, latency_ms=1,
                                 prompt_tokens=10, output_tokens=2, model_version="v-1",
                                 parts=parts, function_calls=tuple(calls))


class Scripted:
    """Returns the scripted turns in order; records every call it received."""

    def __init__(self, *turns, final=FINAL, fail_final=False):
        self.turns, self.final, self.fail_final = list(turns), final, fail_final
        self.seen: list[dict] = []

    def turn(self, system, contents, *, tools, schema, timeout_s, request_id):
        self.seen.append({"system": system, "contents": json.loads(json.dumps(contents)),
                          "tools": tools, "schema": schema, "timeout_s": timeout_s})
        if schema is not None:
            if self.fail_final:
                raise generation.GenerationUnavailable("down")
            return _turn(text_=self.final)
        return self.turns.pop(0) if self.turns else _turn(text_="done")


def _ctx(db, user, contract=None):
    conv = service.create_conversation(db, user_id=user.id,
                                       contract_id=contract.id if contract else None)
    return tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                  conversation_id=conv)


SEARCH = {"name": "search_knowledge", "args": {"query": "terminate for convenience"}}


# ==========================================================================
# B2 — budget
# ==========================================================================
def test_three_decisions_then_one_tool_free_final_call(db, user, indexed_contract):
    contract, _ = indexed_contract
    p = Scripted(*[_turn(calls=[SEARCH])] * 6)
    t = agent.run_turn(p, _ctx(db, user, contract), "What is the notice period?")
    roles = [c.role for c in t.calls]
    assert roles == ["decision"] * 3 + ["final"] and len(t.calls) <= agent.MAX_CALLS
    assert all(s["tools"] for s in p.seen[:3]) and p.seen[-1]["tools"] is None
    assert p.seen[-1]["schema"] == agent.ANSWER_SCHEMA
    assert t.outcome == "answered" and t.blocks == [{"kind": "reasoning",
                                                     "text": "An answer.", "cites": []}]


def test_the_tool_cap_holds_whatever_the_model_asks(db, user, indexed_contract):
    contract, _ = indexed_contract
    p = Scripted(*[_turn(calls=[SEARCH] * 5)] * 3)
    t = agent.run_turn(p, _ctx(db, user, contract), "q")
    assert len(t.tool_execs) == agent.MAX_TOOL_EXECS and "tool_cap" in t.flags
    refused = [r for c in p.seen[-1]["contents"] for part in c["parts"]
               if (r := part.get("functionResponse"))
               and r["response"].get("error") == "TOOL_BUDGET_EXHAUSTED"]
    assert len(refused) == 15 - agent.MAX_TOOL_EXECS


def test_a_failed_final_call_still_answers_from_what_was_found(db, user, indexed_contract):
    contract, _ = indexed_contract
    p = Scripted(_turn(calls=[SEARCH]), fail_final=True)
    t = agent.run_turn(p, _ctx(db, user, contract), "Can we terminate for convenience?")
    assert t.outcome == "fallback" and t.blocks
    assert t.blocks[-1]["kind"] == "next_step"
    assert any(b["kind"] == "sourced" and b["cites"] for b in t.blocks)


def test_the_hard_deadline_skips_to_an_answer(db, user, indexed_contract):
    contract, _ = indexed_contract
    ticks = iter([0.0, 0.0, 0.0] + [agent.HARD_S + 1] * 50)
    t = agent.run_turn(Scripted(_turn(calls=[SEARCH])), _ctx(db, user, contract), "q",
                       clock=lambda: next(ticks))
    assert t.calls == [] and t.outcome == "fallback" and t.blocks
    assert "soft_deadline" in t.flags or "hard_deadline" in t.flags


def test_after_the_soft_deadline_no_new_decision_starts(db, user, indexed_contract):
    contract, _ = indexed_contract
    clock = iter([0.0] * 6 + [agent.SOFT_S + 1] * 50)
    p = Scripted(*[_turn(calls=[SEARCH])] * 3)
    t = agent.run_turn(p, _ctx(db, user, contract), "q", clock=lambda: next(clock))
    assert [c.role for c in t.calls].count("decision") <= 1
    assert t.calls[-1].role == "final" and "soft_deadline" in t.flags


# ==========================================================================
# B4 — context: order, no duplication, user material only as data
# ==========================================================================
def test_context_order_and_no_duplication(db, user, indexed_contract):
    contract, _ = indexed_contract
    ctx = _ctx(db, user, contract)
    paste = b"From the customer: the outage lasted nine hours on the database cluster."
    _add(db, conversation_id=ctx.conversation_id, data=paste, kind="PASTE")
    service._append_turn(db, ctx.conversation_id, "USER", "What is the notice period?")
    service._append_turn(db, ctx.conversation_id, "ASSISTANT", "Ninety days, per 22.")
    service._append_turn(db, ctx.conversation_id, "USER", "And the outage?")
    p = Scripted()
    agent.run_turn(p, ctx, "And the outage?")
    first = p.seen[0]
    parts = [x["text"] for x in first["contents"][0]["parts"]]
    heads = [x.split("\n", 1)[0] for x in parts]
    assert heads[0].startswith("ATTACHMENTS") and heads[1].startswith("CONVERSATION")
    assert heads[-1] == "NEW MESSAGE:"
    whole = json.dumps(first["contents"])
    assert whole.count("And the outage?") == 1, "the new message was duplicated or lost"
    assert whole.count("nine hours on the database cluster") == 1
    assert "[prior reply — not evidence] Ninety days" in parts[1]
    assert "<user_material" in parts[0] and "nine hours" not in first["system"]


def test_pinned_evidence_is_re_fetched_with_the_ledgers_own_keys(db, user,
                                                                 indexed_contract):
    contract, _ = indexed_contract
    ctx = _ctx(db, user, contract)
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "Ninety days.",
                                    "cites": ["D1"]}], "assessment": "supported"})
    first = agent.run_turn(Scripted(_turn(calls=[SEARCH]), final=final), ctx, "Notice?")
    assert first.cited == ["D1"] and "D1" in first.shown
    reply = service._append_turn(db, ctx.conversation_id, "ASSISTANT", first.text())
    answer = service._persist_answer(db, reply, None, service.AssistAnswerState.ANSWERED,
                                     model=None, prompt_version_id=None, latency_ms=None)
    first.registry.persist(reply, answer, first.cited)
    p = Scripted()
    agent.run_turn(p, ctx, "Is that still current?")
    pinned = next(x["text"] for x in p.seen[0]["contents"][0]["parts"]
                  if x["text"].startswith("EVIDENCE CITED BY THE LATEST REPLY"))
    ev = json.loads(pinned.split("\n", 1)[1])["evidence"]
    assert [(e["evidence_id"], e["state"]) for e in ev] == [("D1", "current")]


# ==========================================================================
# B5 — weak evidence is marked and counted
# ==========================================================================
def test_a_gate_shut_document_hit_is_weak_and_counted_if_cited(db, user,
                                                               indexed_contract):
    contract, _ = indexed_contract
    ctx = _ctx(db, user, contract)
    vague = {"name": "search_knowledge",
             "args": {"query": "zebra quantum lighthouse", "sources": ["documents"]}}
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "x", "cites": ["D1"]}],
                        "assessment": "supported"})
    t = agent.run_turn(Scripted(_turn(calls=[vague]), final=final), ctx, "q")
    assert "D1" in t.weak and t.weak_cited == ["D1"]


def test_an_unknown_citation_is_recorded_not_trusted(db, user, indexed_contract):
    contract, _ = indexed_contract
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "x", "cites": ["C99"]}],
                        "assessment": "supported"})
    t = agent.run_turn(Scripted(final=final), _ctx(db, user, contract), "q")
    assert t.invalid_cites == ["C99"] and t.cited == []


# ==========================================================================
# B6 — the flag: shadow never reaches a reader; audit rows carry the provider
# ==========================================================================
@pytest.mark.parametrize("mode", ["shadow", "on"])
def test_the_shipped_answer_is_identical_whatever_the_mode(db, user, indexed_contract,
                                                          monkeypatch, caplog, mode):
    contract, version = indexed_contract
    monkeypatch.setattr(generation, "generate", lambda *a, **k: (_ for _ in ()).throw(
        generation.GenerationUnavailable("off")))
    monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", "off")

    def ask():
        conv = service.create_conversation(db, user_id=user.id, contract_id=contract.id)
        out = service.ask(db, conversation_id=conv, document_version_id=version.id,
                          question="What is the notice period?", permissions=PERMS)
        return conv, out

    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "off")
    _, off = ask()
    fake = Scripted(_turn(calls=[SEARCH]))
    monkeypatch.setattr(agent, "GeminiProvider", lambda: fake)
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", mode)
    caplog.set_level(logging.INFO)
    conv, shadowed = ask()
    assert (shadowed.text, shadowed.answer_state, shadowed.citations) == \
        (off.text, off.answer_state, off.citations)
    assert fake.seen, "the shadow agent did not run"
    logged = [r for r in caplog.records if r.getMessage() == "assist.agent.shadow"]
    assert logged and "An answer" not in str(logged[0].__dict__), "agent text was logged"
    audit = db.execute(text("SELECT after_state FROM audit_events WHERE entity_id = :c "
                            "AND action = 'assist.generation_called'"),
                       {"c": str(conv)}).scalars().all()
    assert any(a.get("provider") == "gemini" and a.get("model_version") == "v-1"
               for a in audit)


def test_an_unknown_mode_reads_as_off(monkeypatch):
    for value, want in (("shadow", "shadow"), ("ON", "on"), ("yes", "off"), ("", "off")):
        monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", value)
        assert config.ask_agent_mode() == want


def test_weakness_is_judged_per_record_by_each_sources_own_rule():
    """A-37: a result-level rule marked 46 valid Constitution/position citations weak."""
    def rec(source, matched=None, query_terms=None):
        return tools.Record(ref="x", source=source, authority="a", status="current",
                            location=None, text="t", matched_terms=matched,
                            query_terms=query_terms)
    shut = tools.Quality(gate_open=False, lexical_hit=False, top_score=0.6,
                         count_returned=3)
    near = tools.Quality(gate_open=True, lexical_hit=False, top_score=0.52,
                         count_returned=3)
    strong = tools.Quality(gate_open=True, lexical_hit=True, top_score=0.7,
                           count_returned=3)
    assert agent._weak(rec("documents"), shut) and agent._weak(rec("documents"), near)
    assert not agent._weak(rec("documents"), strong)
    assert agent._weak(rec("constitution", 1, 4), strong)        # below its 2-term floor
    assert not agent._weak(rec("constitution", 2, 4), None)
    assert not agent._weak(rec("statutes", 1, 1), None)          # one-word query: floor 1
    assert not agent._weak(rec("positions"), shut)               # admitted past its gate


def test_a_pinned_key_is_citable_again_under_the_same_key(db, user, indexed_contract):
    contract, _ = indexed_contract
    ctx = _ctx(db, user, contract)
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "Ninety days.",
                                    "cites": ["D1"]}], "assessment": "supported"})
    first = agent.run_turn(Scripted(_turn(calls=[SEARCH]), final=final), ctx, "Notice?")
    reply = service._append_turn(db, ctx.conversation_id, "ASSISTANT", first.text())
    answer = service._persist_answer(db, reply, None, service.AssistAnswerState.ANSWERED,
                                     model=None, prompt_version_id=None, latency_ms=None)
    first.registry.persist(reply, answer, first.cited)
    again = agent.run_turn(Scripted(final=final), ctx, "Still true?")    # no new search
    assert again.cited == ["D1"] and again.invalid_cites == []


def test_only_the_services_log_only_hook_reaches_the_agent():
    """B6 / A-35: until Phase 5 no route returns agent output. The only importer is
    `service.ask`'s shadow hook, whose outcome is the shipped one (tested above)."""
    import pathlib
    root = pathlib.Path(agent.__file__).resolve().parents[1]
    importers = sorted(str(p.relative_to(root)) for p in root.rglob("*.py")
                       if p.name != "agent.py"
                       and ("assist import agent" in p.read_text()
                            or "assist.agent" in p.read_text()))
    assert importers == ["assist/service.py"]

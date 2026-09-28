"""Roadmap PHASE 13 / `AM-94`: the validated multi-source path wired into production
Ask behind `LEGALMIND_ASK_MULTI_SOURCE`, with a per-request trace and a rollback.

No provider is called: generation is the offline evaluator's deterministic stub (it
restates each approved claim), and the entailment layer passes through — it is pinned
in `test_claim_verification.py`. The statute is the inert synthetic Act the Ask tests
already use.
"""
import logging
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import generation, service, verify
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _synthetic_statute,
    indexed_contract,
    storage,
)
from tools.eval_generation import stub

QUESTION = "What does section 3 of the Synthetic Widgets Act say about widget handling?"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(verify, "check_answer",
                        lambda text_, *a, **k: verify.Result(True, text_, [], []))
    monkeypatch.setattr(generation, "generate_contract_answer", stub)
    # No cross-encoder in CI: a deterministic stand-in scores the synthetic Act's own
    # text relevant and anything else not (the bundle fails closed without scores).
    from legalmind.assist import rerank
    monkeypatch.setattr(rerank, "scores", lambda q, texts, **k: [
        10.0 if "widget" in t.lower() else -10.0 for t in texts])
    monkeypatch.setattr(generation, "generate",
                        lambda q, chunks, **k: generation.GenerationResult(
                            "Every handler shall handle every widget with synthetic care "
                            "[1].", "legacy-fake", "grounded-answer-5", "0" * 64, 1))


def _flag(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("LEGALMIND_ASK_MULTI_SOURCE", raising=False)
    else:
        monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", value)


def _traces(caplog):
    return [r.legalmind_fields for r in caplog.records
            if r.getMessage() == "assist.ask.trace"]


def _ask(db, user, question=QUESTION, contract=None, version=None,
         permissions=USER_PERMS):
    conv = service.create_conversation(db, user_id=user.id,
                                       contract_id=contract.id if contract else None)
    return service.ask(db, conversation_id=conv, question=question,
                       document_version_id=version.id if version else None,
                       permissions=permissions, request_id="req-13")


@pytest.mark.parametrize("value, expected", [
    (None, "on"), ("off", "off"), ("no_document", "no_document"), ("ON", "on"),
    ("yes", "off"), ("", "off")])
def test_the_new_path_is_the_default_and_an_unknown_value_is_off(monkeypatch, value,
                                                                  expected):
    """`AM-106`: every reader gets the verified path unless production is rolled back;
    a value that cannot be read rolls back to the proven path rather than guessing."""
    _flag(monkeypatch, value)
    assert config.ask_multi_source() == expected


@pytest.mark.parametrize("value, doc, path", [
    ("off", False, service.LEGACY), ("off", True, service.LEGACY),
    ("no_document", False, service.MULTI_SOURCE), ("no_document", True, service.LEGACY),
    ("on", False, service.MULTI_SOURCE), ("on", True, service.MULTI_SOURCE)])
def test_only_the_flag_and_the_document_decide_the_path(monkeypatch, value, doc, path):
    _flag(monkeypatch, value)
    assert service._ask_path(object() if doc else None) == path


def test_flag_off_never_touches_the_new_path_rollback(db, user, tmp_path, monkeypatch,
                                                      caplog):
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "off")
    monkeypatch.setattr(service, "_ask_multi_source",
                        lambda *a, **k: pytest.fail("the multi-source path ran"))
    caplog.set_level(logging.INFO)
    out = _ask(db, user)
    assert out.statutes and out.statutes["answer_state"] == "ANSWERED", "legacy answer"
    (trace,) = _traces(caplog)
    assert trace["path"] == trace["selected_path"] == service.LEGACY
    assert trace["flag"] == "off"


def test_a_document_conversation_stays_on_the_legacy_path(db, user, indexed_contract,
                                                          monkeypatch):
    _flag(monkeypatch, "no_document")
    monkeypatch.setattr(service, "_ask_multi_source",
                        lambda *a, **k: pytest.fail("a document conversation was routed"))
    contract, version = indexed_contract
    _ask(db, user, "What is the termination notice?", contract, version)


def test_a_no_document_question_is_answered_by_the_validated_path(db, user, tmp_path,
                                                                  monkeypatch, caplog):
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    caplog.set_level(logging.INFO)
    out = _ask(db, user)
    (trace,) = _traces(caplog)
    assert trace["path"] == service.MULTI_SOURCE, trace
    assert out.answer_state.value == "ANSWERED"
    assert "[1]" in out.text and "\n\nSources\n\n" in out.text
    assert "[A]" not in out.text and "[M]" not in out.text, "internal markers removed"
    assert out.citations == [], "no document evidence, so no document sources"
    assert out.statutes and out.statutes["citations"][0]["section_number"] == "3"
    run = db.execute(text(f'SELECT filters, results, strategy_version FROM '
                          f'"{config.assist_schema()}".retrieval_runs ORDER BY '
                          f'created_at DESC LIMIT 1')).one()
    assert run.strategy_version == service.MULTI_SOURCE_STRATEGY
    assert run.filters["path"] == service.MULTI_SOURCE
    assert run.results["cited"] and all(":" in r for r in run.results["cited"])
    audited = db.execute(text("SELECT count(*) FROM audit_events WHERE action = :a"),
                         {"a": "assist.generation_called"}).scalar()
    assert audited >= 1, "every egress is audited (AM-30 t5)"
    assert trace["path"] == trace["selected_path"] == service.MULTI_SOURCE
    assert trace["generated"] is True and trace["cited_statutes"] >= 1
    assert "STATUTES" in trace["retrievers"] and trace["evidence_refs"]


def test_the_trace_carries_no_question_answer_or_source_text(db, user, tmp_path,
                                                            monkeypatch, caplog):
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    caplog.set_level(logging.INFO)
    out = _ask(db, user)
    (trace,) = _traces(caplog)
    flat = repr(trace)
    for secret in ("widget handling", "synthetic care", out.text[:40]):
        assert secret not in flat, secret
    assert trace["request_id"] == "req-13" and "latency_ms" in trace
    assert {"gemini_calls", "prompt_tokens", "output_tokens", "model"} <= set(trace)


def _draft(monkeypatch, said):
    reply = generation.GenerationResult(said, "fake", generation.CONTRACT_PROMPT_VERSION,
                                        "0" * 64, 1)
    monkeypatch.setattr(generation, "generate_contract_answer", lambda *a, **k: reply)
    monkeypatch.setattr(generation, "generate_bundle_repair", lambda *a, **k: reply)


def test_a_wrong_sentence_citing_a_claim_is_replaced_by_the_approved_text(
        db, user, tmp_path, monkeypatch):
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    _draft(monkeypatch, "The law says every widget must be painted red at once [1].")
    out = _ask(db, user)
    assert "painted red" not in out.text
    assert out.statutes and out.statutes["text"] == "", "answered by the new path"
    assert "The law" in out.text and "[1]" in out.text


def test_an_answer_that_fails_verification_falls_back_to_the_legacy_path(
        db, user, tmp_path, monkeypatch, caplog):
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    unverified = "Widgets must always be painted red, whatever the Act says."
    _draft(monkeypatch, unverified)
    caplog.set_level(logging.INFO)
    out = _ask(db, user)
    assert "painted red" not in out.text
    assert out.statutes and out.statutes.get("answer_state") == "ANSWERED", out.statutes
    (trace,) = _traces(caplog)
    assert trace["selected_path"] == service.MULTI_SOURCE and trace["path"] == service.LEGACY
    assert trace["fallback_kind"] == "multi_source_not_verified"


def test_an_error_in_the_new_path_leaves_the_legacy_answer_intact(db, user, tmp_path,
                                                                  monkeypatch, caplog):
    from legalmind.assist import retrieval
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    monkeypatch.setattr(retrieval, "candidates",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    caplog.set_level(logging.INFO)
    out = _ask(db, user)
    assert out.statutes and out.statutes["answer_state"] == "ANSWERED"
    (trace,) = _traces(caplog)
    assert trace["fallback_kind"] == "multi_source_error:RuntimeError"


def test_the_callers_own_permissions_scope_every_search(db, user, tmp_path, monkeypatch):
    from legalmind.assist import retrieval
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    seen = []
    real = retrieval.candidates

    def spy(db_, plan, route, *, permissions, document_version_id=None, **k):
        seen.append(permissions)
        pool = real(db_, plan, route, permissions=permissions,
                    document_version_id=document_version_id, **k)
        seen.append(pool.searched)
        return pool
    monkeypatch.setattr(retrieval, "candidates", spy)
    reader = frozenset({"assist.ask"})                   # no legal_position.view
    _ask(db, user, permissions=reader)
    assert seen[0] == reader
    assert "CONSTITUTION" not in seen[1] and "POSITIONS" not in seen[1], \
        "a caller who may not read positions never searches them or the Constitution"


def test_markers_are_renumbered_in_first_use_and_resolved_by_the_legend():
    from legalmind.assist import answer as answer_mod
    src = {r: NS(ref=r) for r in ("CONST:14", "POS:X-1", "STAT:Act:3")}
    bundle = NS(shown=lambda: list(src.values()))
    ans = NS(text="Law first [3]. Then position [2][A]. Missing [M]. Again [3].",
             refs=["CONST:14", "POS:X-1", "STAT:Act:3"])
    orig = answer_mod.citation
    try:
        answer_mod.citation = lambda s: f"label of {s.ref}"
        text_out, refs = service._multi_source_text(ans, bundle)
    finally:
        answer_mod.citation = orig
    assert refs == ["STAT:Act:3", "POS:X-1"], "CONST:14 was never cited"
    assert text_out.startswith("Law first [1]. Then position [2]. Missing. Again [1].")
    assert text_out.endswith("Sources\n\n- [1] label of STAT:Act:3\n- [2] label of POS:X-1")


def test_removing_the_internal_markers_leaves_no_stray_comma():
    from legalmind.assist import answer as answer_mod
    bundle = NS(shown=lambda: [NS(ref="CONST:13")])
    ans = NS(text="No position states 6 months [1], [A]. Missing, [M].", refs=["CONST:13"])
    orig = answer_mod.citation
    try:
        answer_mod.citation = lambda s: "label"
        text_out, _ = service._multi_source_text(ans, bundle)
    finally:
        answer_mod.citation = orig
    assert text_out.startswith("No position states 6 months [1]. Missing.")


@pytest.mark.parametrize("share", [None, "0", "10", "50", "x"])
def test_no_percentage_splits_readers_between_engines(monkeypatch, share):
    """`AM-106` withdrew the 10% canary: every conversation, with or without a
    document, takes the same path, and a leftover share setting changes nothing."""
    import uuid
    monkeypatch.delenv("LEGALMIND_ASK_MULTI_SOURCE", raising=False)
    if share is None:
        monkeypatch.delenv("LEGALMIND_ASK_MULTI_SOURCE_PERCENT", raising=False)
    else:
        monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE_PERCENT", share)
    for _ in range(200):
        assert service._ask_path(None) == service.MULTI_SOURCE
        assert service._ask_path(uuid.uuid4()) == service.MULTI_SOURCE
    assert not hasattr(config, "ask_multi_source_percent")


def test_a_later_sentence_need_not_rename_an_act_already_named():
    from legalmind.assist import contracts as cx
    c = cx.Contract(1, "STAT:Synthetic Widgets Act, 2099:3", "s. 3", cx.LAW, "CURRENT",
                    "Every handler shall handle every widget with synthetic care.", "",
                    "", "", "MANDATORY", False, (), (), None,
                    referent="Synthetic Widgets Act, 2099")
    later = "The law states that every handler shall handle every widget with synthetic " \
            "care [1]."
    assert any("not resolved" in f for f in cx.check(later, [c]))
    assert not any("not resolved" in f for f in cx.check(
        later, [c], "Under the Synthetic Widgets Act, 2099, handlers have duties."))


def test_claims_of_one_source_share_one_number_in_the_legend():
    """Three claims of §16 were three identical "§16" lines in the legend."""
    from legalmind.assist import answer as answer_mod
    bundle = NS(shown=lambda: [NS(ref="CONST:16"), NS(ref="POS:X-1")])
    ans = NS(text="Notice [1][2]. Position [3]. Cure [2].",
             refs=["CONST:16", "CONST:16", "POS:X-1"])
    orig = answer_mod.citation
    try:
        answer_mod.citation = lambda s: f"label of {s.ref}"
        text_out, refs = service._multi_source_text(ans, bundle)
    finally:
        answer_mod.citation = orig
    assert refs == ["CONST:16", "POS:X-1"]
    assert text_out.startswith("Notice [1]. Position [2]. Cure [1].")
    assert text_out.endswith("Sources\n\n- [1] label of CONST:16\n- [2] label of POS:X-1")


def test_an_error_after_the_provider_returned_still_audits_the_call(
        db, user, tmp_path, monkeypatch):
    """AM-30 t5: the egress happened, so it is audited even when the new path then
    fails and the legacy answer is shown (security review, `AM-104`)."""
    from legalmind.assist import answer
    _synthetic_statute(db, tmp_path)
    _flag(monkeypatch, "no_document")
    monkeypatch.setattr(answer, "verify_answer",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    _ask(db, user)
    versions = db.execute(text("SELECT after_state->>'prompt_version' FROM audit_events "
                               "WHERE action = :a"),
                          {"a": "assist.generation_called"}).scalars().all()
    assert "offline" in versions, versions   # the stub's own call, audited


def test_a_failure_quoting_evidence_reaches_the_trace_as_its_kind_only():
    said = ("antecedent of 'that sum' in [2] lost ('the fee of five lakh rupees'): "
            "'The fee is payable'")
    assert service._failure_kind(said) == "antecedent of"
    assert service._failure_kind("temporal status of [1] lost ('NOT YET')") == \
        "temporal status"


def test_the_documents_own_clauses_take_the_first_numbers():
    """`AM-106`: the document view links marker [n] to the answer's n-th citation, and
    only the document's clauses are citations — so they are numbered first."""
    from legalmind.assist import answer as answer_mod
    bundle = NS(shown=lambda: [NS(ref="CONST:14"), NS(ref="DOC:c1"), NS(ref="DOC:c2")])
    ans = NS(text="Position [1]. Clause [2]. Another clause [3]. Position again [1].",
             refs=["CONST:14", "DOC:c1", "DOC:c2"])
    orig = answer_mod.citation
    try:
        answer_mod.citation = lambda s: f"label of {s.ref}"
        text_out, refs = service._multi_source_text(ans, bundle)
    finally:
        answer_mod.citation = orig
    assert refs == ["DOC:c1", "DOC:c2", "CONST:14"]
    assert text_out.startswith("Position [3]. Clause [1]. Another clause [2]. Position again [3].")
    # the clauses are the answer's citation cards, so the text legend names only the rest
    assert text_out.endswith("Sources\n\n[3] label of CONST:14")

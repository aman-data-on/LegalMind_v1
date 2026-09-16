"""The evidence-rescue judge — a second look at a refusal, never at an answer.

Measured 2026-09-16 on the ratified 77-question set: the calibrated gate refuses 21 of
64 answerable questions, and **15 of those already have the gold chunk retrieved**.
Recall 0.625 could reach 0.859 by fixing the decision alone, with no retrieval change.

Three cheaper fixes were measured first and none works — a 35-point threshold sweep
(no configuration raises recall without raising wrongly-answered), an IDF-weighted
overlap feature (false refusals 0.185 vs unanswerable 0.196, indistinguishable), and a
different embedding model (gte-small 11/13 · 45/64 against MiniLM 12/13 · 41/64).

What is asserted hardest here is the SAFETY SHAPE, not the feature: the judge can only
turn a refusal into an attempt, and that attempt still faces every mechanical screen.
"""

from __future__ import annotations

import uuid

import pytest

from legalmind.assist import generation, rescue


def _fake(text: str):
    return generation.GenerationResult(text=text, model="fake", prompt_version="test",
                                       payload_sha256="0" * 64, latency_ms=1)


CHUNKS = ["Either party may terminate on thirty (30) days written notice.",
          "The Receiving Party shall keep Confidential Information secret.",
          "Fees are payable within forty-five (45) days of invoice."]


def test_it_is_on_since_the_owner_approved_it(monkeypatch):
    """Approved 2026-09-16 after measurement: recall 0.625 -> 0.828 with
    wrongly-answered unchanged at 1/13."""
    monkeypatch.delenv("LEGALMIND_EVIDENCE_RESCUE", raising=False)
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("YES 1"))
    assert rescue.rescue_indices("what is the notice period?", CHUNKS) == [0]


def test_the_flag_is_the_rollback(monkeypatch):
    """Off restores the pre-rescue behaviour with a restart and no deploy, and makes
    no provider call at all."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "off")

    def boom(*a, **k):
        raise AssertionError("no provider call may be made while disabled")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert rescue.rescue_indices("what is the notice period?", CHUNKS) == []


@pytest.mark.parametrize("reply,expected", [
    ("YES 1", [0]),
    ("YES 1 3", [0, 2]),
    ("yes 2", [1]),
    ("YES", [0, 1, 2]),          # a YES naming nothing means the whole set
    ("NO", []),
    ("no", []),
    ("", []),                    # unparseable is a refusal, not a guess
    ("MAYBE", []),
    ("I think excerpt 1 helps", []),   # not the required shape
])
def test_the_judges_reply_is_parsed_strictly(monkeypatch, reply, expected):
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake(reply))
    assert rescue.rescue_indices("q", CHUNKS) == expected


def test_an_index_the_judge_invented_is_dropped(monkeypatch):
    """An index outside the set is not evidence. Dropping it rather than trusting it
    keeps the rescued evidence a subset of what retrieval actually found."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("YES 2 9 44"))
    assert rescue.rescue_indices("q", CHUNKS) == [1]


def test_a_provider_failure_leaves_the_refusal_standing(monkeypatch):
    """Every failure path returns [], and [] means today's behaviour. Nothing
    degrades when the judge cannot run."""
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")
    for exc in (generation.GenerationUnavailable("no key"),
                generation.GenerationRefused("LEGAL-02")):
        def raiser(*a, _e=exc, **k):
            raise _e
        monkeypatch.setattr(generation, "generate_raw", raiser)
        assert rescue.rescue_indices("q", CHUNKS) == []


def test_no_evidence_means_no_call(monkeypatch):
    monkeypatch.setenv("LEGALMIND_EVIDENCE_RESCUE", "on")

    def boom(*a, **k):
        raise AssertionError("nothing to judge; no call should be made")

    monkeypatch.setattr(generation, "generate_raw", boom)
    assert rescue.rescue_indices("q", []) == []


def test_the_prompt_asks_for_a_decision_not_an_answer():
    """The judge must not answer the question — that is generation's job, and its
    output faces the grounding screens. A judge that answered would route model prose
    around them."""
    t = rescue.RESCUE_PROMPT_TEMPLATE.lower()
    assert "do not answer the question itself" in t
    assert "near-miss is no" in t


def test_rescue_imports_no_retrieval_and_writes_nothing():
    """It reads a decision out of the model and returns indices. If it could retrieve
    or persist, a later edit could give it authority it must never have."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(rescue.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {a.name for a in node.names}
    assert not (imported & {"store", "positions", "statutes", "sqlalchemy"}), imported


# --------------------------------------------------------------------------
# `reconsider` — ONE application of the judge, shared by the service and the gate
# --------------------------------------------------------------------------
# The gate re-implemented the retrieval step instead of calling it, so when the
# rescue landed in `service.ask` the gate kept printing the pre-rescue number:
# 0.625 against the 0.828 users were getting. A release gate that measures a
# different pipeline than the one that ships is the defect these tests pin shut.
def _outcome(*, gate_open: bool, candidates: list[str]):
    from legalmind.assist.store import RetrievalOutcome, SearchHit

    hits = [SearchHit(chunk_id=uuid.uuid4(), evidence_id=uuid.uuid4(), content=c,
                      page_number=1, section_number=None, section_title=None,
                      source_type="DOCUMENT", retrieval_score=0.4) for c in candidates]
    return RetrievalOutcome(hits=hits if gate_open else [], gate_open=gate_open,
                            lexical_hit=True, vector_top_score=0.44,
                            vector_peak_gap=0.01, strategy_version="test",
                            embedding_model="test",
                            candidates=[] if gate_open else hits)


def test_a_shut_gate_is_reopened_on_the_chunks_the_judge_named(monkeypatch):
    monkeypatch.delenv("LEGALMIND_EVIDENCE_RESCUE", raising=False)
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake("YES 1 3"))
    shut = _outcome(gate_open=False, candidates=CHUNKS)
    out = rescue.reconsider(shut, "what is the notice period?")
    assert out.gate_open is True
    assert [h.content for h in out.hits] == [CHUNKS[0], CHUNKS[2]]


def test_an_open_gate_is_never_reconsidered(monkeypatch):
    """The safety shape: the judge can widen an attempt, never narrow one. An open
    gate must not even reach the provider."""
    monkeypatch.delenv("LEGALMIND_EVIDENCE_RESCUE", raising=False)

    def boom(*a, **k):
        raise AssertionError("an answered question must not be re-judged")

    monkeypatch.setattr(generation, "generate_raw", boom)
    open_gate = _outcome(gate_open=True, candidates=CHUNKS)
    assert rescue.reconsider(open_gate, "anything") is open_gate


@pytest.mark.parametrize("reply", ["NO", ""])
def test_a_refusal_the_judge_upholds_is_returned_unchanged(monkeypatch, reply):
    monkeypatch.delenv("LEGALMIND_EVIDENCE_RESCUE", raising=False)
    monkeypatch.setattr(generation, "generate_raw", lambda *a, **k: _fake(reply))
    shut = _outcome(gate_open=False, candidates=CHUNKS)
    assert rescue.reconsider(shut, "what colour is the sky?") is shut


def test_neither_the_service_nor_the_quality_gate_applies_the_judge_itself():
    """Both must route through `reconsider`, or they drift apart again — which is
    exactly what happened between `service.ask` and `verify_assist_quality.measure`.

    Asserted on the AST rather than on the source text so that rewording a comment
    cannot turn this red, and so that a second copy of the logic cannot hide behind
    a differently-spelled call.
    """
    import ast
    import pathlib

    for path in ("legalmind/assist/service.py", "tools/verify_assist_quality.py"):
        tree = ast.parse(pathlib.Path(path).read_text())
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert "rescue_indices" not in called, \
            f"{path} applies the judge itself instead of calling rescue.reconsider"
    # Since 2026-09-17 the ONE reconsideration lives in `service.retrieve_document`,
    # which the gate calls; the service is the only module that reconsiders directly.
    service_tree = ast.parse(pathlib.Path("legalmind/assist/service.py").read_text())
    assert "reconsider" in {n.func.attr for n in ast.walk(service_tree)
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}


# --------------------------------------------------------------------------
# The reranker reorders; it decides nothing (2026-09-17)
# --------------------------------------------------------------------------
def test_the_reranker_never_changes_the_gate_or_the_membership(monkeypatch):
    """`calibration.gate_is_open` keeps its calibrated inputs and its decision, and the
    evidence list keeps its members — only the order moves. Measured 2026-09-17: a
    rerank floor CANNOT reopen a shut gate, because the top score on the answerable
    questions the gate wrongly refuses overlaps the 13 unanswerable almost entirely."""
    from legalmind.assist import rerank

    monkeypatch.setenv("LEGALMIND_RERANK", "on")
    rerank.reset_for_tests()
    shut = _outcome(gate_open=False, candidates=CHUNKS)
    # Reversing is the most disruptive reordering available.
    monkeypatch.setattr(rerank, "_load", lambda: _ReverseScorer())
    open_gate = _outcome(gate_open=True, candidates=CHUNKS)
    reordered = rerank.reorder("anything", open_gate.hits)
    assert [h.content for h in reordered] == list(reversed(CHUNKS))
    assert {h.chunk_id for h in reordered} == {h.chunk_id for h in open_gate.hits}
    # A shut gate carries no hits, so there is nothing to reorder and nothing to open.
    assert rerank.reorder("anything", shut.hits) == []


def test_the_reranker_is_off_by_default_and_makes_no_call(monkeypatch):
    from legalmind.assist import rerank

    monkeypatch.delenv("LEGALMIND_RERANK", raising=False)
    rerank.reset_for_tests()

    def boom():
        raise AssertionError("no model may be loaded while disabled")

    monkeypatch.setattr(rerank, "_load", boom)
    hits = _outcome(gate_open=True, candidates=CHUNKS).hits
    assert rerank.reorder("anything", hits) is hits
    assert rerank.available() is False


def test_an_unavailable_reranker_leaves_the_order_untouched(monkeypatch):
    from legalmind.assist import rerank

    monkeypatch.setenv("LEGALMIND_RERANK", "on")
    rerank.reset_for_tests()
    monkeypatch.setattr(rerank, "_load", lambda: None)
    hits = _outcome(gate_open=True, candidates=CHUNKS).hits
    assert rerank.reorder("anything", hits) is hits


def test_the_reranker_reaches_no_retrieval_and_no_network():
    import ast
    import pathlib

    from legalmind.assist import rerank

    tree = ast.parse(pathlib.Path(rerank.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {a.name for a in node.names}
    assert not (imported & {"store", "positions", "statutes", "sqlalchemy",
                            "urllib", "urllib.request", "requests", "calibration"}), imported


class _ReverseScorer:
    """Scores so that the reversal of the input order is the ranked order."""

    identity = "test-reranker@0"

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(i) for i in range(len(passages))]


def test_the_quality_gate_retrieves_through_the_service_composition():
    """2026-09-17: the gate no longer calls `search_hybrid` or `reconsider` itself —
    it calls `service.retrieve_document`, the same function `service.ask` calls, so a
    step added to the product (the rescue, then the reranker, then the planner) cannot
    go missing from the measurement. The AST test above keeps `rescue_indices` out of
    both; this pins the composition."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("tools/verify_assist_quality.py").read_text())
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "retrieve_document" in called and "plan_question" in called
    assert "search_hybrid" not in called, "the gate re-implements retrieval"

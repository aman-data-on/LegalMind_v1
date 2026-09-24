"""Roadmap PHASE 9 / `AM-88`: the evidence bundle, its states and its controls."""
import pytest

from legalmind.assist import evidence, query_plan, retrieval
from legalmind.assist import rerank as cross_encoder
from legalmind.assist.retrieval import Candidate, Evidence, Pool

GOLDEN = ("A client says their signed MSA mentions 6 months of compensation for early "
          "termination, but we cannot find the final signed copy. What does our Legal "
          "Constitution say about early termination compensation? Is it enforceable "
          "under Indian law?")


@pytest.fixture
def relevance(monkeypatch):
    """Context is the span; relevance is looked up from the text."""
    monkeypatch.setattr(retrieval, "with_context",
                        lambda db, cs: [Evidence(c, c.text) for c in cs])
    table: dict[str, float] = {}
    monkeypatch.setattr(cross_encoder, "scores",
                        lambda q, texts, **_: [table.get(t, -11.0) for t in texts])
    return table


def _c(domain, ref, text, *, authority="", status="CURRENT", lanes=()):
    return Candidate(domain, ref, None, text, 0.0, authority, status, lanes)


def test_a_repealed_act_never_answers_a_current_question(relevance):
    old = _c("STATUTES", "STAT:Companies Act, 1956:291", "board powers",
             authority="PRIMARY_LAW", status="REPEALED")
    relevance["board powers"] = 9.0
    plan = query_plan.plan("Who may exercise the powers of the board?")
    b = evidence.build(None, plan, Pool(), [old])
    assert b.sources[0].reason == "NOT_CURRENT" and b.shown() == [] and not b.answerable


def test_an_unratified_passage_never_supports(relevance):
    c = _c("CONSTITUTION", "CONST:31.6a", "tiered structure",
           authority="COMPANY_CONSTITUTION", status="UNRATIFIED")
    relevance["tiered structure"] = 9.0
    b = evidence.build(None, query_plan.plan("What is our partner tier structure?"),
                       Pool(), [c])
    assert b.sources[0].reason == "UNRATIFIED"


def test_no_reranker_fails_closed(relevance, monkeypatch):
    monkeypatch.setattr(cross_encoder, "scores", lambda *a, **k: None)
    b = evidence.build(None, query_plan.plan("What is our liability cap?"), Pool(),
                       [_c("POSITIONS", "POS:L", "cap")])
    assert b.sources[0].reason == "RELEVANCE_UNAVAILABLE" and not b.answerable


def test_a_document_needs_its_gate_as_well_as_relevance(relevance):
    relevance["thirty days notice"] = 9.0
    doc = _c("DOCUMENT", "DOC:1", "thirty days notice")
    plan = query_plan.plan("What notice does this agreement require?", has_document=True)
    shut = evidence.build(None, plan, Pool(document_gate=False), [doc])
    assert shut.sources[0].reason == "DOCUMENT_GATE_CLOSED"
    assert evidence.build(None, plan, Pool(document_gate=True), [doc]).answerable


def test_the_golden_question_keeps_its_kinds_apart(relevance):
    position = _c("CONSTITUTION", "CONST:14", "full remaining committed-term value",
                  authority="COMPANY_CONSTITUTION",
                  lanes=(query_plan.COMPANY_POSITION,))
    law = _c("STATUTES", "STAT:Indian Contract Act, 1872:74", "reasonable compensation",
             authority="PRIMARY_LAW", lanes=(query_plan.LAW,))
    history = _c("CONSTITUTION", "CONST:31.2", "past negotiated exception of 6 months",
                 authority="HISTORICAL_EXCEPTION", status="HISTORICAL",
                 lanes=(query_plan.HISTORICAL_EXCEPTION,))
    for t in ("full remaining committed-term value", "reasonable compensation",
              "past negotiated exception of 6 months"):
        relevance[t] = 5.0
    b = evidence.build(None, query_plan.plan(GOLDEN, has_document=False), Pool(),
                       [position, law, history])
    kinds = {s.ref: s.kind for s in b.shown()}
    assert kinds == {"CONST:14": query_plan.COMPANY_POSITION,
                     "STAT:Indian Contract Act, 1872:74": query_plan.LAW,
                     "CONST:31.2": query_plan.HISTORICAL_EXCEPTION}
    assert b.missing_document
    assert [a.unstated for a in b.assertions] == [("6 months",)], \
        "the reader's figure is an assertion no company position states"
    assert [a.stated_by for a in b.assertions] == [(query_plan.HISTORICAL_EXCEPTION,)], \
        "6 months found only in a historical exception is history, never policy"
    assert {p.state for p in b.parts} <= {evidence.SUPPORTED,
                                             evidence.PARTIALLY_SUPPORTED}


def test_an_irrelevant_set_is_insufficient_and_shows_nothing(relevance):
    b = evidence.build(None, query_plan.plan("What is the weather in Pune today?"),
                       Pool(), [_c("POSITIONS", "POS:X", "governing law venue")])
    assert [p.state for p in b.parts] == [evidence.INSUFFICIENT] and b.shown() == []

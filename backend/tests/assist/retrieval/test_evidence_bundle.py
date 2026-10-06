"""Roadmap PHASE 9 / `AM-88`: the evidence bundle, its states and its controls."""
import pytest

from legalmind.assist.query import query_plan
from legalmind.assist.retrieval import evidence, retrieval
from legalmind.assist.retrieval import rerank as cross_encoder
from legalmind.assist.retrieval.retrieval import Candidate, Evidence, Pool

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


def test_a_named_section_of_a_named_act_is_never_answered_by_another_act(relevance):
    """Roadmap §7/§14 (PHASE 13, `AM-94`): "section 194J of the Income-tax Act, 1961" —
    a section the supplied 1961 text predates — was answered by the CGST Act. A
    question naming an Act and a section takes evidence from that Act alone; when it
    holds nothing, the lane is insufficient and the answer says so."""
    q = "What did section 194J of the Income-tax Act, 1961 say about professional fees?"
    plan = query_plan.plan(q, has_document=False)
    assert plan.section_hint == "194J"
    cgst = _c("STATUTES", "STAT:Central Goods and Services Tax Act, 2017:10",
              "professional fees are chargeable", authority="PRIMARY_LAW",
              lanes=(query_plan.LAW,))
    relevance["professional fees are chargeable"] = 9.0
    b = evidence.build(None, plan, Pool(), [cgst])
    assert b.sources[0].reason == "WRONG_ACT" and not b.answerable
    same_act = _c("STATUTES", "STAT:Income-tax Act, 1961:194", "the principal officer",
                  authority="PRIMARY_LAW", lanes=(query_plan.LAW,))
    relevance["the principal officer"] = 9.0
    assert evidence.build(None, plan, Pool(), [same_act]).sources[0].reason != "WRONG_ACT"
    # No Act named: a section number alone never makes any Act wrong.
    bare = query_plan.plan("What does section 74 provide about penalties?",
                           has_document=False)
    assert evidence.build(None, bare, Pool(), [cgst]).sources[0].reason != "WRONG_ACT"


def test_a_roman_hindi_question_is_judged_on_its_english_topic_for_the_kinds_asked(
        relevance, monkeypatch):
    """PHASE 13 (golden K-02/K-04): the English cross-encoder scores Roman-Hindi words
    as noise, so the right sources were retrieved and rejected. The planner's English
    topic phrase is scored as well — but only for a source of a kind the plan asked
    for, or a licence-termination statute passes for a data-retention question."""
    from legalmind.assist.retrieval import rerank
    plan = query_plan.plan("hamara liability cap kitna hai?", has_document=False)
    assert plan.language == "hinglish" and plan.topic
    position = _c("CONSTITUTION", "CONST:9", "the standard 12-month liability cap",
                  authority="COMPANY_CONSTITUTION", lanes=(query_plan.COMPANY_POSITION,))
    statute = _c("STATUTES", "STAT:Copyright Act, 1957:32B", "termination of licence",
                 authority="PRIMARY_LAW", lanes=(query_plan.LAW,))

    def english_only(q, texts, **k):          # noise for Hinglish, signal for English
        if any(w in q for w in ("hamara", "kitna")):
            return [-8.0 for _ in texts]
        return [8.0 for _ in texts]
    monkeypatch.setattr(rerank, "scores", english_only)
    b = evidence.build(None, plan, Pool(), [position, statute])
    reasons = {s.ref: s.reason for s in b.sources}
    assert reasons["CONST:9"] is None, "the asked-for kind passes on its English topic"
    assert reasons["STAT:Copyright Act, 1957:32B"] == "NOT_RELEVANT", "other kinds do not"
    english = query_plan.plan("What is our liability cap?", has_document=False)
    assert english.language == "en"


def test_a_named_section_the_text_does_not_hold_is_answered_by_no_other(relevance):
    """PHASE 13 (golden H-02): "section 194J of the Income-tax Act, 1961" against a
    text that predates s. 194J showed s. 199 as the answer. When the named section of
    the named Act is absent, the Act's other sections cannot say what it said; when
    it is present, they stay admissible as context."""
    plan = query_plan.plan("What did section 194J of the Income-tax Act, 1961 say?",
                           has_document=False)
    s199 = _c("STATUTES", "STAT:Income-tax Act, 1961:199", "credit for tax deducted",
              authority="PRIMARY_LAW", status="REPEALED", lanes=(query_plan.LAW,))
    relevance["credit for tax deducted"] = 9.0
    pool = Pool(by_domain={"STATUTES": [s199]})
    assert evidence.build(None, plan, pool, [s199]).sources[0].reason == \
        "NAMED_SECTION_ABSENT"
    named = _c("STATUTES", "STAT:Income-tax Act, 1961:194J", "fees for professional",
               authority="PRIMARY_LAW", status="REPEALED", lanes=(query_plan.LAW,))
    relevance["fees for professional"] = 9.0
    both = Pool(by_domain={"STATUTES": [named, s199]})
    reasons = {s.ref: s.reason for s in evidence.build(None, plan, both,
                                                       [named, s199]).sources}
    assert reasons["STAT:Income-tax Act, 1961:194J"] is None
    assert reasons["STAT:Income-tax Act, 1961:199"] != "NAMED_SECTION_ABSENT"


def test_a_standard_on_another_topic_is_never_evidence(relevance):
    """PHASE 13 (golden GT-03's trap): with more evidence selected, the §9 12-month
    LIABILITY cap passed the relevance floor for "do we charge 12 months of fees on
    early exit?". A ratified standard whose Constitution topic is none of the topics
    the question's words place is judged out; a two-topic question keeps both."""
    plan = query_plan.plan("Do we charge 12 months of fees if a customer exits a "
                           "fixed-term contract early?", has_document=False)
    cap = _c("POSITIONS", "POS:LIABILITY-MSA-001", "liability shall not exceed 12 months",
             authority="COMPANY_STANDARD", lanes=(query_plan.COMPANY_POSITION,))
    exit_ = _c("POSITIONS", "POS:EARLY-TERM-RESTRICTION-MSA-001", "remaining term fees",
               authority="COMPANY_STANDARD", lanes=(query_plan.COMPANY_POSITION,))
    relevance["liability shall not exceed 12 months"] = 9.0
    relevance["remaining term fees"] = 9.0
    reasons = {s.ref: s.reason for s in evidence.build(None, plan, Pool(),
                                                       [cap, exit_]).sources}
    assert reasons == {"POS:LIABILITY-MSA-001": "OFF_TOPIC",
                       "POS:EARLY-TERM-RESTRICTION-MSA-001": None}
    both = query_plan.plan("Our liability cap does not apply to indemnity obligations. "
                           "What indemnity do customers owe us?", has_document=False)
    assert evidence.build(None, both, Pool(), [cap]).sources[0].reason is None
    unplaced = query_plan.plan("What is the weather in Pune today?", has_document=False)
    assert evidence.build(None, unplaced, Pool(), [cap]).sources[0].reason != "OFF_TOPIC"
    # filed under Payment Terms, but its own text is about suspension (golden G-03)
    cure = _c("POSITIONS", "POS:SUSPENSION-NOTICE-CURE-MSA-001",
              "we may suspend the services after a 30-day cure notice",
              authority="COMPANY_STANDARD", lanes=(query_plan.COMPANY_POSITION,))
    relevance["we may suspend the services after a 30-day cure notice"] = 9.0
    suspend = query_plan.plan("Can we suspend service immediately, without the 30-day "
                              "cure period?", has_document=False)
    assert evidence.build(None, suspend, Pool(), [cure]).sources[0].reason is None


def test_an_open_document_gate_admits_a_clause_the_cross_encoder_scores_low(relevance):
    """`AM-106`: the web-trained cross-encoder scores lay questions against contract
    drafting at -5 to -11, below its floor, so gold clauses the document's own gate had
    opened for were rejected. The gate decides; a shut gate still refuses."""
    relevance["the customer shall have no right to terminate before the term"] = -9.0
    doc = _c("DOCUMENT", "DOC:1", "the customer shall have no right to terminate before the term")
    plan = query_plan.plan("Can we walk away before it expires?", has_document=True)
    assert evidence.build(None, plan, Pool(document_gate=True), [doc]).sources[0].reason \
        is None
    assert evidence.build(None, plan, Pool(document_gate=False), [doc]).sources[0].reason \
        == "DOCUMENT_GATE_CLOSED"

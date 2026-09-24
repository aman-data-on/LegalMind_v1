"""Roadmap PHASE 7 / `AM-86`: plan-driven candidate pools and diverse evidence."""
from legalmind.assist import constitution, query_plan, retrieval, routing
from legalmind.assist.retrieval import Candidate, Pool
from tests.test_assist_answer_integrity import _statute

PERMS = frozenset({"assist.ask", "legal_position.view"})


def _route(question):
    return routing.plan(question, has_document=False, permissions=PERMS,
                        statutes_available=True)


def test_selection_gives_every_lane_its_best_source_before_any_second():
    plan = query_plan.plan("What does our Constitution say about early exit, and is it "
                           "enforceable under Indian law?")
    pool = Pool(by_domain={
        "POSITIONS": [Candidate("POSITIONS", f"POS:P{i}", None, "", 1.0,
                                lanes=(query_plan.COMPANY_POSITION,)) for i in range(6)],
        "STATUTES": [Candidate("STATUTES", "STAT:Act:74", None, "", 0.1,
                               lanes=(query_plan.LAW,))]},
        primary={"POSITIONS"})
    refs = [c.ref for c in retrieval.select(pool, plan, k=3)]
    assert "STAT:Act:74" in refs, "five similar standards displaced the statute"


def test_an_unplaced_question_takes_evidence_only_from_the_primary_route():
    plan = query_plan.plan("What is the weather in Pune today?")
    pool = Pool(by_domain={"STATUTES": [Candidate("STATUTES", "STAT:X:1", None, "", 1.0)],
                           "POSITIONS": [Candidate("POSITIONS", "POS:P", None, "", 1.0)]},
                primary={"POSITIONS"})
    assert [c.ref for c in retrieval.select(pool, plan)] == ["POS:P"]


def test_the_pool_reaches_the_constitution_and_the_law(db):
    constitution.ingest(db)
    _statute(db, "The Synthetic Widgets Act, 2099", [("1", 1)])
    q = ("What does our Constitution say about early termination, and is a handler "
         "enforceable under Indian law to record the synthetic outcome with care?")
    plan = query_plan.plan(q)
    pool = retrieval.candidates(db, plan, _route(q), permissions=PERMS,
                                embed_query=lambda _q: None)
    assert pool.by_domain.get("CONSTITUTION"), "the Constitution is not in the pool"
    assert any(c.ref.startswith("STAT:Synthetic Widgets Act") for c in
               pool.by_domain.get("STATUTES", []))
    refs = pool.refs()
    assert len(refs) == len(set(refs)), "one source took two places"


def _stat(ref, status="CURRENT", text="t"):
    return Candidate("STATUTES", ref, None, text, 0.0, status=status)


def test_rerank_puts_a_repealed_source_behind_every_current_one(monkeypatch):
    from legalmind.assist import rerank as cross_encoder
    monkeypatch.setattr(cross_encoder, "scores", lambda q, texts, **_: [9.0, 1.0, 5.0])
    pool = Pool(by_domain={
        "STATUTES": [_stat("old", "REPEALED"), _stat("a"), _stat("b")],
        "POSITIONS": [Candidate("POSITIONS", "POS:P", None, "", 1.0)]}, primary=set())
    out = retrieval.rerank(pool, query_plan.plan("Who may exercise board powers?"))
    assert [c.ref for c in out.by_domain["STATUTES"]] == ["b", "a", "old"]
    assert out.by_domain["POSITIONS"] is pool.by_domain["POSITIONS"], \
        "the cross-encoder must not reorder company positions"


def test_rerank_without_a_model_keeps_the_fused_order(monkeypatch):
    from legalmind.assist import rerank as cross_encoder
    monkeypatch.setattr(cross_encoder, "scores", lambda *a, **k: None)
    pool = Pool(by_domain={"STATUTES": [_stat("a"), _stat("b")]}, primary=set())
    out = retrieval.rerank(pool, query_plan.plan("anything"))
    assert out.by_domain["STATUTES"] == pool.by_domain["STATUTES"]


def test_a_span_missing_from_its_context_is_appended_never_dropped():
    pos = Candidate("POSITIONS", "POS:P", None, "the ratified quote", 1.0)
    [ev] = retrieval.with_context(None, [pos])
    assert ev.context == "the ratified quote"

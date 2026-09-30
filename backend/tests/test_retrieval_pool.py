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


GOLDEN = ("A client says their signed MSA mentions 6 months of compensation for early "
          "termination, but we cannot find the final signed copy. What does our Legal "
          "Constitution say about early termination compensation?")


def test_a_section_holding_history_serves_the_history_lane():
    """PHASE 13 (`AM-94`): the golden question's history lives in §31.2, whose best-
    matching child is its POSITION paragraph. Read by that child alone the section
    could never serve the history lane, and §31.15's renewal deals — a section whose
    best child happened to be historical — were shown as the early-exit history."""
    plan = query_plan.plan(GOLDEN, has_document=False)
    assert query_plan.HISTORICAL_EXCEPTION in plan.lanes
    lanes = tuple(sorted(plan.lanes))
    s14 = Candidate("CONSTITUTION", "CONST:14", None, "full committed-term value", 0.03,
                    "COMPANY_CONSTITUTION", lanes=lanes,
                    authorities=("COMPANY_CONSTITUTION", "SECONDARY_REFERENCE"))
    s312 = Candidate("CONSTITUTION", "CONST:31.2", None, "no early exit without the fee",
                     0.03, "COMPANY_CONSTITUTION", lanes=lanes,
                     authorities=("COMPANY_CONSTITUTION", "HISTORICAL_EXCEPTION"))
    s3115 = Candidate("CONSTITUTION", "CONST:31.15", None, "[Customer B] 6-month renewal",
                      0.01, "HISTORICAL_EXCEPTION", lanes=lanes,
                      authorities=("COMPANY_CONSTITUTION", "HISTORICAL_EXCEPTION"))
    assert retrieval.kinds_of(s312) == {query_plan.COMPANY_POSITION,
                                        query_plan.HISTORICAL_EXCEPTION}
    assert retrieval.kind_of(s312) == query_plan.COMPANY_POSITION, "labelling unchanged"
    pool = Pool(by_domain={"CONSTITUTION": [s14, s312, s3115]}, primary={"CONSTITUTION"})
    picked = [c.ref for c in retrieval.select(pool, plan, k=2)]
    assert picked == ["CONST:14", "CONST:31.2"], picked


def test_the_constitution_search_reports_every_kind_a_section_holds(db):
    constitution.ingest(db)
    hits = constitution.search(db, query="signed MSAs 30-day no-penalty exit historical "
                               "exceptions early termination", permissions=PERMS,
                               limit=12, embed_query=lambda _q: None)
    s312 = next(h for h in hits if h.section_path == "31.2")
    assert "HISTORICAL_EXCEPTION" in s312.authorities
    assert "COMPANY_CONSTITUTION" in s312.authorities


def test_scores_many_returns_the_same_numbers_as_scores_per_query(monkeypatch):
    """PHASE 13 (`AM-94`): contracts are scored in one batched call; the numbers must
    be exactly what a per-query `scores` call gives, row per query, in order."""
    from legalmind.assist import rerank

    class Backend:
        def pair_logits(self, pairs):
            return [[float(len(q) * 10 + len(t))] for q, t in pairs]

        def score(self, query, passages):
            return [row[0] for row in self.pair_logits([(query, p) for p in passages])]
    monkeypatch.setattr(rerank, "_load", lambda: Backend())
    monkeypatch.setattr(rerank.config, "rerank_enabled", lambda: True)
    queries, texts = ["ab", "cdef"], ["x", "yy", "zzz"]
    assert rerank.scores_many(queries, texts) == [rerank.scores(q, texts) for q in queries]
    assert rerank.scores_many([], texts) is None and rerank.scores_many(queries, []) is None


def test_a_named_section_of_a_named_act_survives_the_rerank(monkeypatch):
    """Roadmap §7/§8 (PHASE 13, golden A-04): search ranks the named s. 74 first; the
    cross-encoder, reading "section 74" in the question but not in the section's own
    text, demoted it to tenth. The exact reference sorts first after the rerank."""
    from legalmind.assist import rerank
    plan = query_plan.plan("What does section 74 of the Indian Contract Act provide?",
                           has_document=False)
    s74 = Candidate("STATUTES", "STAT:Indian Contract Act, 1872:74", None,
                    "When a contract has been broken, if a sum is named", 0.9, "PRIMARY_LAW")
    s16 = Candidate("STATUTES", "STAT:Indian Contract Act, 1872:16", None,
                    "undue influence defined", 0.5, "PRIMARY_LAW")
    other = Candidate("STATUTES", "STAT:Companies Act, 2013:74", None, "deposits", 0.4,
                      "PRIMARY_LAW")
    monkeypatch.setattr(rerank, "scores", lambda q, texts, **k: [
        {"undue influence defined": 5.0}.get(t, -5.0) for t in texts])
    pool = retrieval.rerank(Pool(by_domain={"STATUTES": [s74, s16, other]}), plan)
    order = [c.ref for c in pool.by_domain["STATUTES"]]
    assert order[0] == "STAT:Indian Contract Act, 1872:74", order
    assert retrieval.exact_reference(s74, plan)
    assert not retrieval.exact_reference(other, plan), "same number, another Act"
    assert retrieval.names_other_act(other, plan)
    bare = query_plan.plan("What does section 74 provide?", has_document=False)
    assert not retrieval.exact_reference(s74, bare), "no Act named: never pinned"


def test_the_cross_encoder_scores_a_statute_with_its_section_title(monkeypatch):
    """Golden E-01/GT-11: s. 73's best chunk is an illustration about cargo; scored
    without the marginal note, the damages section ranked below unrelated Acts. The
    note survives the merge of lanes and is never the evidence text."""
    from legalmind.assist import rerank as cross_encoder
    seen = []
    monkeypatch.setattr(cross_encoder, "scores",
                        lambda q, texts, **_: seen.extend(texts) or [0.0] * len(texts))
    s73 = Candidate("STATUTES", "STAT:Indian Contract Act, 1872:73", None,
                    "A avails himself of those opportunities", 1.0,
                    note="Compensation for loss or damage caused by breach of contract")
    monkeypatch.setattr(retrieval, "_search", lambda *a, **k: [s73])
    plan = query_plan.plan("What does the Contract Act say about compensation?")
    pool = retrieval.candidates(None, plan, _route(plan.question),
                                permissions=frozenset({"assist.ask"}) | PERMS)
    out = retrieval.rerank(pool, plan)
    assert "Compensation for loss or damage caused by breach of contract. A avails " \
        "himself of those opportunities" in seen
    assert out.by_domain["STATUTES"][0].text == "A avails himself of those opportunities"


def test_a_section_on_the_asked_topic_answers_for_the_position_whatever_matched():
    """§14's note on ss. 73/74 matched "early termination of a fixed-term deal", its
    position paragraph did not, so §14 was law only and never answered the question it
    is about (2026-09-27, golden G-03). A section on another topic is not lifted."""
    plan = query_plan.plan("What does our Constitution say about early termination of a "
                           "fixed-term deal?", has_document=False)
    reading = {"authority": "SECONDARY_REFERENCE", "lanes": (query_plan.COMPANY_POSITION,)}
    pool = Pool(by_domain={"CONSTITUTION": [
        Candidate("CONSTITUTION", "CONST:14", None, "", 1.0, **reading),
        Candidate("CONSTITUTION", "CONST:9", None, "", 0.9, **reading)]},
        primary={"CONSTITUTION"})
    refs = [c.ref for c in retrieval.select(pool, plan)]
    assert "CONST:14" in refs and "CONST:9" not in refs


def test_the_document_lane_takes_two_picks_a_round():
    """`AM-106`: a document conversation's own document gets its share of the evidence
    even for a question the planner reads as a company-position question — before, the
    document was a one-slot extra (1 of 8 units here)."""
    plan = query_plan.plan("Can we walk away before it expires, and what would it cost us?",
                           has_document=True)
    docs = [Candidate("DOCUMENT", f"DOC:{i}", None, "", 1.0,
                      lanes=(query_plan.CONTRACT,)) for i in range(6)]
    lane = (query_plan.COMPANY_POSITION,)
    pool = Pool(by_domain={
        "DOCUMENT": docs,
        "POSITIONS": [Candidate("POSITIONS", f"POS:P{i}", None, "", 1.0,
                                "COMPANY_STANDARD", lanes=lane) for i in range(6)],
        "CONSTITUTION": [Candidate("CONSTITUTION", f"CONST:{i}", None, "", 1.0,
                                   "COMPANY_CONSTITUTION", lanes=lane) for i in range(6)],
        "STATUTES": [Candidate("STATUTES", f"STAT:Act:{i}", None, "", 1.0,
                               lanes=(query_plan.LAW,)) for i in range(6)]},
        primary={"DOCUMENT", "POSITIONS", "CONSTITUTION"})
    refs = [c.ref for c in retrieval.select(pool, plan, k=8)]
    assert sum(r.startswith("DOC:") for r in refs) >= 3, refs


def test_the_document_gate_gets_the_pin_and_the_rescue_of_the_previous_path(monkeypatch):
    """`AM-106`: the gate on the reader's own question is opened by a Finding's cited
    clauses, or by the rescue judge when it is shut — `service.retrieve_document`'s
    two openings — and by nothing else."""
    import dataclasses
    import uuid

    from legalmind.assist import rescue, store
    shut = store.RetrievalOutcome(hits=[], gate_open=False, lexical_hit=False,
                                  vector_top_score=None, vector_peak_gap=None,
                                  strategy_version="t", embedding_model=None)
    monkeypatch.setattr(store, "search_hybrid", lambda *a, **k: shut)
    monkeypatch.setattr(store, "section_headings", lambda db, ids: {})   # no database
    monkeypatch.setattr(store, "version_role", lambda db, v: None)       # no database
    asked = []
    monkeypatch.setattr(rescue, "reconsider",
                        lambda r, q, **k: asked.append(q) or dataclasses.replace(r))
    pool = Pool()
    retrieval._search(None, "DOCUMENT", "q", permissions=frozenset(), route=None,
                      document_version_id=uuid.uuid4(), embed_query=None, pool=pool,
                      question="q")
    assert asked == ["q"] and pool.document_gate is False, "a refused rescue stays shut"
    asked.clear()
    retrieval._search(None, "DOCUMENT", "q plus topic", permissions=frozenset(),
                      route=None, document_version_id=uuid.uuid4(), embed_query=None,
                      pool=pool, question="q")
    assert asked == [], "only the reader's own question decides the gate"
    cited = store.SearchHit(uuid.uuid4(), uuid.uuid4(), "the cited clause", None, "7",
                            None, "DOCUMENT", 1.0)
    monkeypatch.setattr(store, "chunks_for_evidence", lambda *a, **k: [cited])
    out = retrieval._search(None, "DOCUMENT", "q", permissions=frozenset(), route=None,
                            document_version_id=uuid.uuid4(), embed_query=None,
                            pool=pool, question="q", pinned_evidence=(uuid.uuid4(),))
    assert pool.document_gate is True and out[0].ref == f"DOC:{cited.chunk_id}"
    assert asked == [], "a pinned Finding needs no rescue"

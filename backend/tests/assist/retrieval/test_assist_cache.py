"""Ask's caches (`AM-126`, owner spec D2a, 2026-10-08) and the D1 latency fixes.

Tier 1 is shared across users, so what must NOT happen is pinned as closely as what
must: a document or the reader's material never enters it, a caller with other
permissions never shares an entry, a corpus change misses at once, and only the exact
query hits — s. 73 never answers for s. 74, however close MiniLM puts them (0.947). Tier 2 replays a user's own first turn as a fresh turn
with fresh rows, misses when anything it cited is gone, and never serves a re-ask.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from legalmind.assist.query import query_plan, routing
from legalmind.assist.retrieval import cache, retrieval
from legalmind.assist.retrieval import rerank as cross_encoder
from tests.assist.agent.test_assist_agent import ranked  # noqa: F401  (fixture)
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures)
    indexed_contract,
    storage,
)
from tests.assist.knowledge.test_positions import ratified_dir  # noqa: F401  (fixture)

S73 = "section 73 of the Indian Contract Act"
S74 = "section 74 of the Indian Contract Act"


# ------------------------------------------------------------------- the store
def test_an_entry_expires_and_the_oldest_is_evicted():
    now = [0.0]
    store = cache.Store(ttl_s=10, maxsize=2, clock=lambda: now[0])
    store.put("a", 1)
    store.put("b", 2)
    store.put("c", 3)
    assert store.get("a") is None and store.get("b") == 2      # LRU bound
    now[0] = 11
    assert store.get("b") is None                                # TTL


def test_only_the_exact_query_hits_never_a_paraphrase_or_its_opposite():
    """Exact keys only: s. 73 never answers for s. 74, "excluded" never for "included"."""
    runs = []
    for q in (S73, S74, "Is consequential loss excluded?",
              "Is consequential loss included?", S73):
        cache.public_search(("k", q), lambda q=q: runs.append(q) or [q])
    assert runs == [S73, S74, "Is consequential loss excluded?",
                    "Is consequential loss included?"]
    assert cache.SEARCHES.hits == 1


def test_minilm_puts_opposites_past_092_which_is_why_there_is_no_paraphrase_hit():
    from legalmind.assist.ingestion import embedding_runtime
    if not embedding_runtime.available():
        pytest.skip("no provisioned embedding model")
    for a, b in ((S73, S74), ("Is consequential loss excluded?",
                              "Is consequential loss included?")):
        (va, _), (vb, _) = (embedding_runtime.embed_query(q) for q in (a, b))
        assert sum(x * y for x, y in zip(va, vb, strict=True)) >= 0.92


# ------------------------------------------------------------- candidate search
@pytest.fixture
def counted_search(monkeypatch):
    """`retrieval._search` counted per (domain, query); the corpus stamp is ours."""
    calls: list[tuple[str, str]] = []
    stamp = ["v1"]

    def search(db, domain, query, **kw):
        calls.append((domain, query))
        return [retrieval.Candidate(domain, f"{domain}:{query}", None, query, 1.0)]
    monkeypatch.setattr(retrieval, "_search", search)
    monkeypatch.setattr(cache, "corpus_version", lambda db: stamp[0])
    return calls, stamp


def _pool(perms=frozenset({"assist.ask"}), *, document=False, superseded=False):
    plan = query_plan.plan("What does section 74 of the Indian Contract Act provide?",
                           has_document=document)
    domains = (routing.Domain.STATUTES, *((routing.Domain.DOCUMENT,) if document else ()))
    route = routing.RoutePlan(comparison=False, domains=domains, statute_shaped=True,
                              include_superseded=superseded)
    return retrieval.candidates(None, plan, route, permissions=perms,
                                document_version_id="v" if document else None)


def test_a_public_search_is_shared_and_a_document_search_never_is(counted_search):
    calls, _ = counted_search
    _pool(document=True)
    first = list(calls)
    assert {d for d, _ in first} == {"STATUTES", "DOCUMENT"}
    _pool(document=True)
    assert [d for d, _ in calls[len(first):]] == [d for d, _ in first if d == "DOCUMENT"]


def test_other_permissions_superseded_or_corpus_never_share_an_entry(counted_search):
    calls, stamp = counted_search
    _pool()
    n = len(calls)
    _pool(frozenset({"assist.ask", "contract.view"}))   # same domains, other set
    assert len(calls) == 2 * n, "a caller with other permissions searched afresh"
    _pool(superseded=True)
    assert len(calls) == 3 * n
    stamp[0] = "v2"                                    # a re-ingest, a retired standard
    _pool()
    assert len(calls) == 4 * n


def test_a_plans_own_queries_never_stand_in_for_each_other(counted_search, monkeypatch):
    """The question and its sub-question "limitation of liability cap …" sit past 0.92:
    each is searched, never served the other's list (14 of 82 golden seed searches
    changed when a paraphrase hit let them)."""
    from legalmind.assist.ingestion import embedding_runtime
    calls, _ = counted_search
    monkeypatch.setattr(embedding_runtime, "embed_query", lambda q: ((1.0, 0.0), "e"))
    plan = query_plan.plan("What is our liability cap, and does Indian law let us "
                           "recover a stipulated damages amount in full?")
    route = routing.RoutePlan(comparison=False, domains=(routing.Domain.STATUTES,),
                              statute_shaped=True)
    retrieval.candidates(None, plan, route, permissions=frozenset({"assist.ask"}))
    statutes = [q for d, q in calls if d == "STATUTES"]
    assert len(statutes) >= 2 and len(set(statutes)) == len(statutes)


def test_the_flag_off_is_the_rollback(counted_search, monkeypatch):
    calls, _ = counted_search
    monkeypatch.setenv("LEGALMIND_ASK_CACHE_PUBLIC", "off")
    _pool()
    _pool()
    assert len(calls) == 2 * len({q for _, q in calls})


# --------------------------------------------------------------- score memo
class _Backend:
    identity = "fake@1"

    def __init__(self):
        self.pairs: list = []

    def pair_logits(self, pairs):
        self.pairs += pairs
        return [[float(len(q) + len(t))] for q, t in pairs]

    def score(self, query, passages):
        return [row[0] for row in self.pair_logits([(query, p) for p in passages])]


@pytest.fixture
def backend(monkeypatch):
    b = _Backend()
    monkeypatch.setattr(cross_encoder, "_load", lambda: b)
    monkeypatch.setattr(cross_encoder.config, "rerank_enabled", lambda: True)
    return b


def test_a_public_score_is_memoised_and_a_private_one_never_is(backend):
    first = cross_encoder.scores_many(["q"], ["law", "clause"], public=[True, False])
    assert cross_encoder.scores_many(["q"], ["law", "clause"],
                                     public=[True, False]) == first
    assert backend.pairs == [("q", "law"), ("q", "clause"), ("q", "clause")]
    assert cross_encoder.scores("q", ["law changed"], public=True) == [12.0]
    assert backend.pairs[-1] == ("q", "law changed"), "changed text misses"


def test_no_memo_with_the_flag_off(backend, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_CACHE_PUBLIC", "off")
    cross_encoder.scores("q", ["law"], public=True)
    cross_encoder.scores("q", ["law"], public=True)
    assert len(backend.pairs) == 2


# ------------------------------------------------------------------ D1 fixes
def test_a_query_is_embedded_once(monkeypatch):
    from legalmind.assist.ingestion import embedding_runtime
    seen = []

    class Fake:
        identity = "e@1"

        def embed(self, texts):
            seen.extend(texts)
            return [[0.5]] * len(texts)
    fake = Fake()
    monkeypatch.setattr(embedding_runtime, "_load", lambda: fake)
    embedding_runtime.reset_for_tests()
    assert embedding_runtime.embed_query("cap") == embedding_runtime.embed_query("cap")
    assert seen == ["cap"]
    embedding_runtime.reset_for_tests()
    embedding_runtime.embed_query("cap")
    assert seen == ["cap", "cap"], "a reset forgets"


def test_the_bundle_scores_every_query_in_one_call(backend, monkeypatch):
    """D1: one backend call for the question and its sub-questions, the same numbers
    as one call per query, and only public text memoised."""
    from legalmind.assist.retrieval import evidence
    monkeypatch.setattr(retrieval, "with_context",
                        lambda db, cs: [retrieval.Evidence(c, c.text) for c in cs])
    calls = []
    real = backend.pair_logits
    backend.pair_logits = lambda pairs: calls.append(len(pairs)) or real(pairs)
    plan = query_plan.plan("What is our liability cap and what does the law say?")
    cands = [retrieval.Candidate("STATUTES", "STAT:A:1", None, "law text", 0.0),
             retrieval.Candidate("DOCUMENT", "DOC:1", None, "clause text", 0.0)]
    queries = list(dict.fromkeys([plan.question, *(s.query for s in plan.sub_questions)]))
    b = evidence.build(None, plan, retrieval.Pool(), cands)
    assert len(calls) == 1 and calls[0] == 2 * len(queries)
    assert [s.relevance for s in b.sources] == [
        max(len(q) + len(c.text) for q in queries) for c in cands]
    evidence.build(None, plan, retrieval.Pool(), cands)
    assert calls[1] == len(queries), "the statute's scores came from the memo"


def test_the_citation_hop_searches_each_act_and_section_once(monkeypatch):
    from legalmind.assist.agent import tools
    queries = []
    monkeypatch.setattr(tools.statute_corpus, "search_statutes",
                        lambda db, **k: queries.append(k["query"]) or [])
    texts = ["Liability: Sections 73 and 74 of the Indian Contract Act, 1872 cap it.",
             "Liability basis: Indian Contract Act 1872, Sections 73-74 for the cap."]
    ctx = SimpleNamespace(db=None, permissions=frozenset())
    tools._cited_sections(ctx, texts, set(), "what is the liability cap?")
    assert len(queries) == 1, queries


# ----------------------------------------------------------------- tier 2 (DB)
def _ask(api, conv, question="What is the notice period?"):
    return api.post(f"/api/v1/conversations/{conv}/messages",
                    json={"question": question}).json()["data"]


@pytest.fixture
def answering(api, db, seeded, user, indexed_contract, ranked, monkeypatch):
    from legalmind.assist.agent import agent
    from tests.assist.agent.test_assist_agent import SEARCH, Scripted, _turn
    from tests.conftest import grant_role, sign_in
    contract, _ = indexed_contract
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "Ninety days.",
                                    "cites": ["D1"]}], "assessment": "supported"})
    made = []
    monkeypatch.setattr(agent, "GeminiProvider", lambda: made.append(1) or Scripted(
        _turn(calls=[SEARCH]), final=final))
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)

    def chat():
        return api.post("/api/v1/conversations",
                        json={"contract_id": str(contract.id)}).json()["data"]["id"]
    return chat, made


def _rows(db, table, conv):
    from sqlalchemy import text

    from legalmind import config
    return db.execute(text(
        f'SELECT count(*) FROM "{config.assist_schema()}".{table} t '
        + ("JOIN \"" + config.assist_schema() + "\".messages m ON m.id = t.message_id "
           "WHERE m.conversation_id = :c" if table == "ai_answers"
           else "WHERE t.conversation_id = :c")), {"c": conv}).scalar_one()


def test_a_users_repeat_first_question_is_replayed_as_a_fresh_turn(api, db, answering):
    from sqlalchemy import text

    from legalmind.security import audit
    chat, made = answering
    first_conv, second_conv = chat(), chat()
    first = _ask(api, first_conv)
    second = _ask(api, second_conv)
    assert len(made) == 1, "the second chat's identical first turn made no model call"
    assert second["text"] == first["text"] and "Ninety days" in second["text"]
    assert [s["key"] for s in second["sources"]] == [s["key"] for s in first["sources"]]
    for table in ("ai_answers", "conversation_evidence"):
        assert _rows(db, table, second_conv) == _rows(db, table, first_conv) > 0
    replayed = db.execute(text("SELECT count(*) FROM audit_events WHERE action = :a "
                               "AND entity_id = :c"),
                          {"a": audit.ASSIST_ANSWER_REPLAYED, "c": second_conv}).scalar()
    assert replayed == 1
    assert not db.execute(text("SELECT count(*) FROM audit_events WHERE action = :a "
                               "AND entity_id = :c"),
                          {"a": audit.ASSIST_GENERATION_CALLED, "c": second_conv}).scalar()


def test_a_re_ask_in_the_same_chat_always_runs_fresh(api, db, answering):
    chat, made = answering
    conv = chat()
    _ask(api, conv)
    _ask(api, conv)
    assert len(made) == 2


def test_a_deleted_source_chat_or_the_flag_off_misses(api, db, answering, monkeypatch):
    chat, made = answering
    first = chat()
    _ask(api, first)
    assert api.delete(f"/api/v1/conversations/{first}").status_code in (200, 204)
    _ask(api, chat())
    assert len(made) == 2, "the pointer's message is gone: answered afresh"
    monkeypatch.setenv("LEGALMIND_ASK_CACHE_USER", "off")
    _ask(api, chat())
    assert len(made) == 3


def test_a_turn_that_listed_other_documents_is_never_remembered(api, db, answering,
                                                                monkeypatch):
    """Names from find_documents are not ledger records: a replay could not re-check
    that the reader may still read them, so such a turn is not cached."""
    from legalmind.assist.agent import agent
    from tests.assist.agent.test_assist_agent import Scripted, _turn
    chat, made = answering
    from tests.assist.agent.test_assist_agent import SEARCH
    find = {"name": "find_documents", "args": {"name": "Ask MSA"}}
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "Ninety days.",
                                    "cites": ["D1"]}], "assessment": "supported"})
    monkeypatch.setattr(agent, "GeminiProvider", lambda: made.append(1) or Scripted(
        _turn(calls=[find, SEARCH]), final=final))
    _ask(api, chat())
    _ask(api, chat())
    assert len(made) == 2


def test_a_changed_cited_record_misses(api, db, answering):
    from sqlalchemy import text

    from legalmind import config
    chat, made = answering
    first = chat()
    _ask(api, first)
    s = config.assist_schema()
    changed = db.execute(text(f"""
        UPDATE "{s}".chunks SET content = content || ' Amended.' WHERE id IN (
          SELECT chunk_id FROM "{s}".conversation_evidence WHERE conversation_id = :c)"""),
        {"c": first}).rowcount
    db.commit()
    assert changed > 0
    _ask(api, chat())
    assert len(made) == 2, "the cited clause changed: answered afresh"


def test_a_not_helpful_answer_is_never_replayed(api, db, answering, user):
    """A retry in a new chat after a Not helpful rating wants a new answer."""
    from sqlalchemy import text

    from legalmind import config
    from legalmind.assist import feedback
    chat, made = answering
    first = chat()
    _ask(api, first)
    reply = db.execute(text(f'SELECT id FROM "{config.assist_schema()}".messages '
                            "WHERE conversation_id = :c AND role = 'ASSISTANT'"),
                       {"c": first}).scalar_one()
    feedback.record(db, message_id=reply, user_id=user.id, kind=feedback.RATING,
                    rating=feedback.DOWN)
    db.commit()
    _ask(api, chat())
    assert len(made) == 2


def test_another_users_pointer_is_never_served(api, db, answering, indexed_contract):
    """Even under a colliding key, on the same document, the replay re-reads the reply
    as THIS user's."""
    from uuid import uuid4
    chat, _ = answering
    _ask(api, chat())
    ((_, (_, pointer)),) = list(cache.ANSWERS._data.items())
    cache.ANSWERS.put("collision", pointer)
    stranger = SimpleNamespace(user_id=uuid4(), conversation_id=uuid4(),
                               contract_id=indexed_contract[0].id,
                               permissions=frozenset({"assist.ask"}))
    assert cache.replay(db, stranger, "collision", request_id=None, started=0.0) is None


def test_the_key_moves_with_user_permissions_and_document_version(db, user, storage,
                                                                  indexed_contract):
    from uuid import uuid4

    from legalmind.ingestion.service import ingest_document
    from tests.assist.integration.test_assist_ask import DOCX_MIME, PARAGRAPHS, build_docx
    contract, _ = indexed_contract

    def key(**over):
        ctx = SimpleNamespace(**{"user_id": user.id, "conversation_id": uuid4(),
                                 "contract_id": contract.id,
                                 "permissions": frozenset({"assist.ask"}), **over})
        return cache.answer_key(db, ctx, "What is the notice period?", uuid4(),
                                model="m", prompt_version="p")
    base = key()
    assert key() == base
    assert key(user_id=uuid4()) != base
    assert key(permissions=frozenset({"assist.ask", "contract.view"})) != base
    ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                    data=build_docx([*PARAGRAPHS, "A new clause."]), filename="v2.docx",
                    declared_mime=DOCX_MIME)
    assert key() != base, "a new document version misses"


# --------------------------------------------------------- corpus_version (DB)
def test_the_corpus_stamp_moves_on_an_in_place_rewrite_a_status_or_a_retirement(
        db, user, tmp_path, ratified_dir):
    from sqlalchemy import text

    from legalmind import config
    from tests.assist.integration.test_assist_ask import _synthetic_statute
    from tests.assist.knowledge.test_positions import _indexed, _retire
    s = config.assist_schema()
    _synthetic_statute(db, tmp_path)
    _indexed(db, user, ratified_dir)
    seen = [cache.corpus_version(db)]

    def moved(sql: str) -> None:
        # a savepoint gets its own xid: the test's stand-in for ingest's own commit
        with db.begin_nested():
            if sql:
                db.execute(text(sql.format(s=s)))
            else:
                _retire(db, "TESTPOS-MSA-001")
        seen.append(cache.corpus_version(db))
        assert seen[-1] != seen[-2], sql or "retired"
    # a re-ingest rewrites a kept section in place: same rows, file and label
    moved('UPDATE "{s}".statute_chunks SET content = content || \' x\' '
          "WHERE id = (SELECT min(id::text)::uuid FROM \"{s}\".statute_chunks)")
    moved('UPDATE "{s}".statutes SET status = \'REPEALED\'')
    moved("")
    assert cache.corpus_version(db) == seen[-1], "deterministic"


def test_a_floor_answer_names_no_prompt_and_is_never_remembered(api, db, answering,
                                                                 monkeypatch):
    """No model wrote a floor answer's words: no prompt version on its row, no replay."""
    from sqlalchemy import text

    from legalmind import config
    from legalmind.assist.agent import agent
    from tests.assist.agent.test_assist_agent import SEARCH, Scripted, _turn
    chat, made = answering
    monkeypatch.setattr(agent, "GeminiProvider", lambda: made.append(1) or Scripted(
        _turn(calls=[SEARCH]), fail_final=True))
    conv = chat()
    _ask(api, conv)
    s = config.assist_schema()
    assert db.execute(text(f'SELECT a.prompt_version_id FROM "{s}".ai_answers a JOIN '
                           f'"{s}".messages m ON m.id = a.message_id '
                           "WHERE m.conversation_id = :c"), {"c": conv}).all() == [(None,)]
    _ask(api, chat())
    assert len(made) == 2

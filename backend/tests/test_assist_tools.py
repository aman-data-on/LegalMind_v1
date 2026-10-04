"""The Ask agent tool layer — Phase 2 exit tests (2026-10-01).

Authorization (B3), schemas (B5), read-only (B6), evidence states (B7) and quality
signals (B4) for the seven tools in `legalmind/assist/tools.py`. Every document and
standard here is synthetic (rule 21); nothing asserts a legal position.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import attachments, generation, ledger, service, tools
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security.errors import NotVisible
from tests.conftest import make_user
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _ratified_positions,
    _synthetic_statute,
    indexed_contract,
    storage,
)

ALL = frozenset({"assist.ask", "legal_position.view"})


@pytest.fixture(autouse=True)
def no_egress(monkeypatch):
    """B6: a tool that reached the provider fails the test, whatever it was doing."""
    def refuse(*a, **k):
        raise AssertionError("a tool reached the model provider")
    monkeypatch.setattr(generation, "generate_raw", refuse)


def _conv(db, user, contract=None):
    return service.create_conversation(db, user_id=user.id,
                                       contract_id=contract.id if contract else None)


def _ctx(db, user, conv, perms=ALL):
    return tools.ToolContext.open(db, user_id=user.id, permissions=perms,
                                  conversation_id=conv)


def _material(db, conv, data=b"Clause 4. The fee is payable within forty five days."):
    from legalmind.api.routers.assist import extract_material
    mime, extracted = extract_material(data, attachments.PASTE, None, "text/plain")
    return attachments.add(db, conversation_id=conv, data=data, kind=attachments.PASTE,
                           mime=mime, extracted=extracted)


def _other_users_version(db, storage):
    from legalmind.assist.indexing import index_document_version
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.test_ingestion import build_docx
    stranger = make_user(db)
    contract = M.Contract(owner_id=stranger.id, name="Theirs", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    v = ingest_document(db, storage, contract_id=contract.id, uploaded_by=stranger.id,
                        data=build_docx(["9. Fees", "The fee is payable within thirty "
                                         "days of the invoice date."]),
                        filename="theirs.docx", declared_mime=DOCX_MIME).document_version
    index_document_version(db, v.id)
    return stranger, v


# ==========================================================================
# B3 — authorization: one response for "not yours"
# ==========================================================================
def test_every_unresolvable_document_id_returns_the_identical_response(
        db, user, storage, indexed_contract):
    contract, version = indexed_contract
    _, theirs = _other_users_version(db, storage)
    ctx = _ctx(db, user, _conv(db, user, contract))

    def ask(doc_id):
        return tools.run(ctx, "search_knowledge", {
            "query": "terminate for convenience", "sources": ["documents"],
            "document_version_id": doc_id}).model_dump()

    malformed, nonexistent, unauthorized = (
        ask("not-a-uuid"), ask(str(uuid.uuid4())), ask(str(theirs.id)))
    assert malformed == nonexistent == unauthorized
    assert malformed["error"] == "NOT_FOUND" and malformed["records"] == ()

    authorized = ask(str(version.id))
    assert authorized["error"] is None
    omitted = tools.run(ctx, "search_knowledge", {"query": "terminate for convenience",
                                                  "sources": ["documents"]})
    assert omitted.error is None                      # missing → the conversation's own
    assert [r.ref for r in omitted.records] == [r["ref"] for r in authorized["records"]]
    assert omitted.records and all(r.ref.startswith("DOC:") for r in omitted.records)


def test_a_cross_user_conversation_cannot_be_opened(db, user, indexed_contract):
    contract, _ = indexed_contract
    theirs = _conv(db, user, contract)
    stranger = make_user(db)
    with pytest.raises(NotVisible):
        tools.ToolContext.open(db, user_id=stranger.id, permissions=ALL,
                               conversation_id=theirs)
    with pytest.raises(NotVisible):
        tools.ToolContext.open(db, user_id=stranger.id, permissions=ALL,
                               conversation_id=uuid.uuid4())


def test_another_conversations_attachment_is_indistinguishable_from_none(db, user):
    mine, other = _conv(db, user), _conv(db, user)
    a = _material(db, other)
    ctx = _ctx(db, user, mine)

    def search(att):
        return tools.run(ctx, "search_attachment",
                         {"attachment_id": att, "query": "fee payable"}).model_dump()
    assert search(str(a.id)) == search(str(uuid.uuid4())) == search("garbage") \
        == {**search("garbage"), "error": "NOT_FOUND"}
    own = _material(db, mine, b"Clause 7. The fee is payable within ninety days.")
    found = tools.run(ctx, "search_attachment",
                      {"attachment_id": str(own.id), "query": "fee payable"})
    assert found.error is None and found.records
    assert all(r.authority == "USER_MATERIAL" for r in found.records)


def test_a_contract_the_caller_lost_is_out_of_scope_for_every_tool(
        db, user, storage, indexed_contract):
    contract, version = indexed_contract
    conv = _conv(db, user, contract)
    contract.owner_id = make_user(db).id               # ownership moved away
    db.flush()
    ctx = _ctx(db, user, conv)
    assert ctx.contract_id is None
    r = tools.run(ctx, "search_knowledge", {"query": "terminate", "sources": ["documents"],
                                            "document_version_id": str(version.id)})
    assert r.error == "NOT_FOUND"
    r = tools.run(ctx, "search_knowledge", {"query": "terminate", "sources": ["documents"]})
    assert r.records == () and r.by_source["documents"].count_returned == 0


@pytest.mark.parametrize("smuggled", [
    {"user_id": "x"}, {"permissions": ["legal.decision"]}, {"conversation_id": "x"},
    {"department": "all"}, {"contract_id": "x"}, {"owner": "x"}])
def test_authorization_cannot_be_supplied_through_arguments(db, user, smuggled):
    ctx = _ctx(db, user, _conv(db, user))
    for name, base in [("search_knowledge", {"query": "fees"}),
                       ("get_company_position", {"topic": "fees"}),
                       ("search_statutes", {"query": "fees"}),
                       ("get_evidence", {"evidence_ids": ["C1"]}),
                       ("list_attachments", {}),
                       ("search_attachment", {"attachment_id": "x", "query": "fees"}),
                       ("ask_user", {"question": "Which document?"})]:
        assert tools.run(ctx, name, {**base, **smuggled}).error == "INVALID_ARGUMENT", name


def test_filters_can_only_narrow_never_widen(db, user, tmp_path):
    _ratified_positions(db, user, tmp_path)
    ctx = _ctx(db, user, _conv(db, user))
    for sources in (["all"], ["statutes"], ["documents", "admin"], [], ["*"]):
        assert tools.run(ctx, "search_knowledge",
                         {"query": "widgets", "sources": sources}).error == "INVALID_ARGUMENT"
    # Asking for positions without the permission returns what an empty corpus returns.
    bare = _ctx(db, user, _conv(db, user), perms=frozenset({"assist.ask"}))
    r = tools.run(bare, "get_company_position", {"topic": "widgets handled with care"})
    assert r.error is None and r.records == ()
    assert tools.run(ctx, "get_company_position",
                     {"topic": "widgets handled with care"}).records


# ==========================================================================
# B5 — strict schemas
# ==========================================================================
@pytest.mark.parametrize("name,args", [
    ("search_knowledge", {"query": "fees", "k": 9}),
    ("search_knowledge", {"query": "fees", "k": 0}),
    ("search_knowledge", {"query": "fees", "k": "5"}),
    ("search_knowledge", {"query": "fees", "k": 5.0}),
    ("search_knowledge", {"query": ""}),
    ("search_knowledge", {"query": "   "}),
    ("search_knowledge", {"query": "x" * 501}),
    ("search_knowledge", {}),
    ("search_knowledge", {"query": "fees", "document_version_id": "x" * 65}),
    ("search_statutes", {"query": "fees", "include_superseded": "yes"}),
    ("get_evidence", {"evidence_ids": []}),
    ("get_evidence", {"evidence_ids": ["C1"] * 9}),
    ("get_evidence", {"evidence_ids": "C1"}),
    ("search_attachment", {"query": "fees"}),
    ("ask_user", {"question": "q", "options": ["a", "b", "c", "d", "e"]}),
    ("ask_user", {"question": "x" * 301}),
    ("delete_attachment", {"attachment_id": "x"}),
])
def test_out_of_schema_arguments_are_refused(db, user, name, args):
    ctx = _ctx(db, user, _conv(db, user))
    assert tools.run(ctx, name, args).error == "INVALID_ARGUMENT"


def test_arguments_must_be_an_object(db, user):
    ctx = _ctx(db, user, _conv(db, user))
    assert tools.run(ctx, "search_knowledge", ["fees"]).error == "INVALID_ARGUMENT"  # type: ignore[arg-type]


# ==========================================================================
# B6 — read-only
# ==========================================================================
def _writes(db) -> int:
    return db.execute(text(
        "SELECT coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) "
        "FROM pg_stat_xact_user_tables")).scalar_one()


def test_no_tool_writes_anything(db, user, storage, tmp_path, indexed_contract):
    contract, version = indexed_contract
    _ratified_positions(db, user, tmp_path)
    _synthetic_statute(db, tmp_path)
    conv = _conv(db, user, contract)
    att = _material(db, conv)
    db.flush()
    ctx = _ctx(db, user, conv)
    calls = [("search_knowledge", {"query": "terminate for convenience"}),
             ("get_company_position", {"topic": "widgets handled with care"}),
             ("search_statutes", {"query": "widget handling"}),
             ("get_evidence", {"evidence_ids": ["U1", "C1"]}),
             ("list_attachments", {}),
             ("search_attachment", {"attachment_id": str(att.id), "query": "fee payable"}),
             ("ask_user", {"question": "Which agreement do you mean?",
                           "options": ["The MSA", "The NDA"]})]
    messages = db.execute(text(f'SELECT count(*) FROM "{config.assist_schema()}".messages'
                               )).scalar_one()
    for name, args in calls:
        before = _writes(db)
        result = tools.run(ctx, name, args)
        assert result.error is None, name
        assert _writes(db) == before, f"{name} wrote to the database"
    assert db.execute(text(f'SELECT count(*) FROM "{config.assist_schema()}".messages'
                           )).scalar_one() == messages, "ask_user changed the conversation"


def test_a_tool_that_tried_to_write_leaves_nothing_behind(db, user, monkeypatch):
    """The savepoint is the structural guarantee behind the test above."""
    conv = _conv(db, user)
    schema = config.assist_schema()

    def sneaky(ctx, a):
        ctx.db.execute(text(f'DELETE FROM "{schema}".conversations WHERE id = :c'),
                       {"c": ctx.conversation_id})
        return tools.ToolResult(tool="list_attachments")
    monkeypatch.setitem(tools.TOOLS, "list_attachments", (tools.ListAttachmentsArgs, sneaky))
    before = _writes(db)
    tools.run(_ctx(db, user, conv), "list_attachments", {})
    # The detector sees an ATTEMPTED write even though the savepoint undid it — so the
    # read-only test above cannot pass by not looking.
    assert _writes(db) > before
    assert db.execute(text(f'SELECT count(*) FROM "{schema}".conversations WHERE id = :c'),
                      {"c": conv}).scalar_one() == 1


# ==========================================================================
# B7 — get_evidence: current, stale, unavailable, deterministic
# ==========================================================================
def _answered_with(db, conv):
    turn = service._append_turn(db, conv, "ASSISTANT", "x")
    answer = service._persist_answer(db, turn, None, service.AssistAnswerState.ANSWERED,
                                     model=None, prompt_version_id=None, latency_ms=None)
    return turn, answer


def test_get_evidence_states_are_exact_and_deterministic(db, user, storage,
                                                         indexed_contract):
    from legalmind.assist import store
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.test_ingestion import build_docx
    contract, version = indexed_contract
    conv = _conv(db, user, contract)
    att = _material(db, conv)
    # Two records cited by an answer: a document clause (D1) and the material (U1).
    hits = store.search_chunks(db, document_version_id=version.id, query="terminate")
    turn, answer = _answered_with(db, conv)
    service._persist_citations(db, answer, [1], hits)
    chunk = db.execute(text(f'SELECT id, content FROM "{config.assist_schema()}"'
                            ".attachment_chunks WHERE attachment_id = :a"),
                       {"a": att.id}).first()
    keys = ledger.record_answer(db, conversation_id=conv, answer_id=answer,
                                turn_message_id=turn, extra=[ledger.Record(
                                    "U", f"ATT:{chunk.id}", chunk.id, chunk.content,
                                    "USER_MATERIAL", "current")])
    assert keys == ["D1", "U1"]
    ctx = _ctx(db, user, conv)

    def states(*ids):
        r = tools.run(ctx, "get_evidence", {"evidence_ids": list(ids)})
        return [(e.evidence_id, e.state, e.text is not None) for e in r.evidence]

    assert states("D1", "U1") == [("D1", "current", True), ("U1", "current", True)]
    assert states("D1", "U1") == states("D1", "U1")             # deterministic

    # stale: a newer version of the contract exists; the clause is still visible.
    ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                    data=build_docx(["22. Termination", "Either party may terminate on "
                                     "thirty days notice."]),
                    filename="v2.docx", declared_mime=DOCX_MIME)
    assert states("D1") == [("D1", "stale", True)]

    # missing, invalid, another conversation's: one shape, no text.
    other = _conv(db, user)
    ctx_other = _ctx(db, user, other)
    r = tools.run(ctx, "get_evidence", {"evidence_ids": ["D9", "'; DROP x;--"]})
    assert [(e.state, e.text, e.ref) for e in r.evidence] == [("unavailable", None, None)] * 2
    r = tools.run(ctx_other, "get_evidence", {"evidence_ids": ["D1", "U1"]})
    assert [(e.state, e.text) for e in r.evidence] == [("unavailable", None)] * 2

    # unavailable: the material expired and was purged; the contract left scope.
    attachments.purge_expired(db, now=att.expires_at)
    assert states("U1") == [("U1", "unavailable", False)]
    contract.owner_id = make_user(db).id
    db.flush()
    lost = _ctx(db, user, conv)
    r = tools.run(lost, "get_evidence", {"evidence_ids": ["D1"]})
    assert [(e.state, e.text) for e in r.evidence] == [("unavailable", None)]
    assert r.count_returned == 0 and r.quality is None


# ==========================================================================
# B4 — quality signals from existing semantics
# ==========================================================================
def test_search_tools_report_quality_and_others_only_a_count(db, user, storage, tmp_path,
                                                             indexed_contract):
    contract, _ = indexed_contract
    _ratified_positions(db, user, tmp_path)
    _synthetic_statute(db, tmp_path)
    ctx = _ctx(db, user, _conv(db, user, contract))
    pos = tools.run(ctx, "get_company_position", {"topic": "widgets handled with care"})
    assert pos.quality and pos.quality.gate_open and pos.quality.lexical_hit
    assert pos.quality.count_returned == len(pos.records) and pos.quality.top_score
    stat = tools.run(ctx, "search_statutes", {"query": "widget handling"})
    assert stat.quality and stat.quality.count_returned == len(stat.records) > 0
    assert all(r.ref.startswith("STAT:") and r.location for r in stat.records)
    none = tools.run(ctx, "search_statutes", {"query": "zebra quantum lighthouse"})
    assert none.quality == tools.Quality(gate_open=False, lexical_hit=False,
                                         top_score=None, count_returned=0)
    docs = tools.run(ctx, "search_knowledge", {"query": "terminate this agreement for "
                                               "convenience", "sources": ["documents"]})
    q = docs.by_source["documents"]
    assert q.gate_open and q.lexical_hit and q.count_returned == len(docs.records)
    listed = tools.run(ctx, "list_attachments", {})
    asked = tools.run(ctx, "ask_user", {"question": "Which agreement?"})
    for r in (listed, asked):
        assert r.quality is None and r.by_source is None
    assert asked.question == "Which agreement?" and asked.count_returned == 0


# ==========================================================================
# A-65 — controlled cross-document retrieval (owner, 2026-10-04)
# ==========================================================================
def _my_other_version(db, storage, user, name="SLA-Northwind"):
    from legalmind.assist.indexing import index_document_version
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.test_ingestion import build_docx
    contract = M.Contract(owner_id=user.id, name=name, contract_type="SLA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    v = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                        data=build_docx(["4. Service Credits", "Below ninety five percent "
                                         "uptime the credit is twenty percent of the "
                                         "monthly charge."]),
                        filename="northwind.docx", declared_mime=DOCX_MIME).document_version
    index_document_version(db, v.id)
    return contract, v


def test_another_readable_document_is_searchable_and_labelled_as_itself(
        db, user, storage, indexed_contract):
    """Source mixing guard at the source: another document's records never carry the
    selected document's scope."""
    contract, _ = indexed_contract
    _, mine = _my_other_version(db, storage, user)
    ctx = _ctx(db, user, _conv(db, user, contract))
    r = tools.run(ctx, "search_knowledge", {"query": "service credit uptime",
                                            "sources": ["documents"],
                                            "document_version_id": str(mine.id)})
    assert r.error is None and r.records
    assert {x.scope for x in r.records} == {'another document: "SLA-Northwind"'}
    own = tools.run(ctx, "search_knowledge", {"query": "terminate for convenience",
                                              "sources": ["documents"]})
    assert {x.scope for x in own.records} == {"the selected document"}


def test_find_documents_never_reveals_a_document_the_caller_cannot_read(
        db, user, storage, indexed_contract):
    """Access control unchanged: another user's document is never found, never
    searchable — the same NOT_FOUND as a document that does not exist."""
    contract, _ = indexed_contract
    _, theirs = _other_users_version(db, storage)        # named "Theirs"
    _, mine = _my_other_version(db, storage, user)
    ctx = _ctx(db, user, _conv(db, user, contract))
    found = tools.run(ctx, "find_documents", {"name": "Theirs Northwind"}).documents
    assert [d["name"] for d in found] == ["SLA-Northwind"]
    assert found[0]["document_version_id"] == str(mine.id) and not found[0]["selected"]
    missing = tools.run(ctx, "search_knowledge", {"query": "fee", "sources": ["documents"],
                                                  "document_version_id": str(uuid.uuid4())})
    hidden = tools.run(ctx, "search_knowledge", {"query": "fee", "sources": ["documents"],
                                                 "document_version_id": str(theirs.id)})
    assert hidden.model_dump() == missing.model_dump()
    assert hidden.error == "NOT_FOUND"


def _my_doc(db, storage, user, paragraphs, table=None, name="Synthetic MSA"):
    from legalmind.assist.indexing import index_document_version
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.test_ingestion import build_docx
    contract = M.Contract(owner_id=user.id, name=name, contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    v = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                        data=build_docx(paragraphs, table), filename="synthetic.docx",
                        declared_mime=DOCX_MIME).document_version
    index_document_version(db, v.id)
    return contract, v


def test_c1_1_a_clause_split_mid_sentence_reads_whole_with_its_number(db, user, storage,
                                                                     monkeypatch):
    """C1.1: 17.1 was stored as two blocks ("… or any third" | "party for any indirect
    …"); the second ranks but read as an orphaned fragment with no clause number. Read
    time joins it to the block it continues (A-71); nothing stored changes."""
    contract, _ = _my_doc(db, storage, user, [
        "17. Limitation of Liability",
        "17.1 Exclusion of Certain Damages: The Supplier shall not be liable to the "
        "Customer or any third",
        "party for any indirect, incidental or consequential damages, including loss of "
        "data or profits.",
        "17.2 Monetary Cap: The aggregate liability shall not exceed the fees paid in the "
        "six months before the claim."])
    ctx = _ctx(db, user, _conv(db, user, contract))
    ask = {"query": "indirect damages loss of data", "sources": ["documents"]}
    # read whole (A-77): the body is joined to its head — one clause, one record
    whole = tools.run(ctx, "search_knowledge", ask).records
    clause = next(r for r in whole if "party for any indirect" in r.text)
    assert clause.text.startswith("17.1 Exclusion") and clause.location == "17.1"
    assert not any(r.text.startswith("party for any indirect") for r in whole)
    # ranked (a document too large to read whole): the body carries its head (A-71)
    monkeypatch.setattr(tools, "WHOLE_DOCUMENT_CHARS", 0)
    body = next(r for r in tools.run(ctx, "search_knowledge", ask).records
                if "party for any indirect" in r.text)
    assert body.text.startswith("17.1 Exclusion of Certain Damages")
    assert body.location == "17.1"


def test_c4_1_a_table_never_borrows_the_last_heading_as_its_location():
    """C4.1: a DOCX table is extracted after the body text, so the nearest heading is
    the document's LAST one; the table is located as a table, not as that section."""
    from legalmind.assist.store import SearchHit
    def hit(source_type, section=None, page=None):
        return SearchHit(chunk_id=uuid.uuid4(), evidence_id=uuid.uuid4(),
                         content="Tier Benefits Gold Technical Account Manager",
                         page_number=page, section_number=section, section_title=None,
                         source_type=source_type, retrieval_score=0.0)
    last = "15 · Miscellaneous Provisions"
    assert tools.document_location(hit("TABLE"), last) == "a table in the document"
    assert tools.document_location(hit("EvidenceSourceType.TABLE", page=4), last) == "p.4"
    assert tools.document_location(hit("NATIVE_TEXT"), last) == last
    assert tools.document_location(hit("NATIVE_TEXT", section="3.2"), last) == "3.2"

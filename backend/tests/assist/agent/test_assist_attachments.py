"""Conversation-scoped user material — Ask plan 1.1–1.5 (2026-10-01). Synthetic text
only (rule 21)."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import service
from legalmind.assist.agent import attachments
from tests.assist.integration.test_assist_ask import storage  # noqa: F401  (fixture)
from tests.test_ingestion import build_docx

EMAIL = ("From the customer: we need the service credit for the March outage applied "
         "before renewal.\n\nThe outage lasted nine hours on the primary database "
         "cluster and breached the monthly availability commitment.\n\nPlease confirm "
         "the credit amount and the date it will appear on the invoice.")


def _add(db, *, conversation_id, data, kind, filename=None, mime="text/plain"):
    """The endpoints' own path: validate and parse in the API layer, then store."""
    from legalmind.api.routers.assist import extract_material
    mime, extracted = extract_material(data, kind, filename, mime)
    return attachments.add(db, conversation_id=conversation_id, data=data, kind=kind,
                           mime=mime, extracted=extracted, filename=filename)


def _conversation(db, user):
    return service.create_conversation(db, user_id=user.id, contract_id=None)


def _chunks(db, attachment_id):
    return db.execute(text(f'SELECT content, annotations FROM "{config.assist_schema()}"'
                           ".attachment_chunks WHERE attachment_id = :a ORDER BY ordinal"),
                      {"a": attachment_id}).all()


def test_a_paste_is_stored_ready_and_searchable_in_its_own_conversation(db, user):
    mine, other = _conversation(db, user), _conversation(db, user)
    a = _add(db, conversation_id=mine, data=EMAIL.encode(),
                        kind=attachments.PASTE)
    assert (a.status, a.failure_code, a.filename) == ("READY", None, None)
    assert a.expires_at - a.created_at == timedelta(days=30)
    assert "".join(c.content for c in _chunks(db, a.id)).replace("\n", "") \
        .startswith("From the customer")

    found = attachments.search(db, conversation_id=mine, query="outage service credit",
                               embed_query=None)
    assert found.gate_open and found.hits and found.hits[0].attachment_id == a.id
    # Scope is the conversation, not the user: the owner's other chat sees nothing.
    assert attachments.search(db, conversation_id=other, query="outage service credit",
                              embed_query=None).hits == []


def test_the_same_paste_twice_is_one_attachment(db, user):
    c = _conversation(db, user)
    first = _add(db, conversation_id=c, data=EMAIL.encode(),
                            kind=attachments.PASTE)
    again = _add(db, conversation_id=c, data=EMAIL.encode(),
                            kind=attachments.PASTE)
    assert first.id == again.id and len(attachments.list_for(db, c)) == 1


def test_a_docx_file_keeps_its_name_and_blank_fields_are_marked(db, user):
    c = _conversation(db, user)
    data = build_docx(["4. Term", "This agreement runs for ____ months from the start "
                       "date and renews for successive one year periods."])
    a = _add(db, conversation_id=c, data=data, kind=attachments.FILE,
                        filename="draft.docx", mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document"))
    assert (a.status, a.filename) == ("READY", "draft.docx")
    rows = _chunks(db, a.id)
    assert any("____" in r.content and r.annotations.get("blank_fields") for r in rows)


def test_refusals_and_failures_carry_a_code_never_the_material(db, user, monkeypatch):
    c = _conversation(db, user)
    with pytest.raises(attachments.AttachmentRejected) as e:
        _add(db, conversation_id=c, data=b"%PDF-1.4 not really",
                        kind=attachments.FILE, filename="x.txt", mime="text/plain")
    assert e.value.code
    monkeypatch.setenv("LEGALMIND_ASK_PASTE_MAX_CHARS", "10")
    with pytest.raises(attachments.AttachmentRejected) as e:
        _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    assert e.value.code == "PASTE_TOO_LONG"
    assert attachments.list_for(db, c) == [], "a refusal stored something"

    monkeypatch.delenv("LEGALMIND_ASK_PASTE_MAX_CHARS")
    blank = _add(db, conversation_id=c, data=b"   \n\n  ",
                            kind=attachments.PASTE)
    assert (blank.status, blank.failure_code) == ("FAILED", "NO_TEXT")


def test_expired_material_loses_its_text_and_keeps_its_row(db, user):
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    assert attachments.purge_expired(db, now=datetime.now(UTC)) == 0
    assert attachments.purge_expired(db, now=a.expires_at + timedelta(seconds=1)) == 1
    [row] = attachments.list_for(db, c)
    assert row.status == "EXPIRED" and _chunks(db, a.id) == []
    assert attachments.search(db, conversation_id=c, query="outage",
                              embed_query=None).hits == []


# ==========================================================================
# On the current path (plan exit G1/G4): searched, labelled, cited as the reader's
# ==========================================================================
@pytest.fixture
def offline(monkeypatch):
    from tests.assist.integration.test_conversation_multi_source import go_offline
    go_offline(monkeypatch)
    monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", "on")
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    from legalmind.assist.llm import generation
    from tools.eval_generation import stub
    blocks: list[str] = []

    def keep(question, block, **k):
        blocks.append(block)
        return stub(question, block, **k)
    monkeypatch.setattr(generation, "generate_contract_answer", keep)
    return blocks


def test_a_question_about_pasted_material_is_answered_from_it_as_the_readers(
        db, user, offline):
    c = _conversation(db, user)
    _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    out = service.ask(db, conversation_id=c, document_version_id=None,
                      question="How many hours did the outage last?",
                      permissions=frozenset({"assist.ask"}))
    assert out.answer_state.value == "ANSWERED", out.text
    block = offline[-1]
    assert "SAY AS: Your material (user-provided" in block and "nine hours" in block
    assert "The contract" not in block and "The contract" not in out.text, \
        "the reader's own text was presented as the contract"
    assert out.text.startswith("Your material") and "user-provided" in out.text


def test_without_the_flag_material_is_never_searched(db, user, offline, monkeypatch):
    c = _conversation(db, user)
    _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "off")
    assert attachments.scope(db, c) is None
    service.ask(db, conversation_id=c, document_version_id=None,
                question="How long did the database outage last?",
                permissions=frozenset({"assist.ask"}))
    assert not any("nine hours" in b for b in offline)


def test_split_paste_takes_the_asking_paragraph_and_keeps_the_rest_whole():
    long = "x " * 1500
    assert attachments.split_paste(f"{long}\n\nWhat is the notice period?") == \
        ("What is the notice period?", long.strip())
    assert attachments.split_paste(f"Is this acceptable?\n\n{long}") == \
        ("Is this acceptable?", long.strip())
    assert attachments.split_paste(long) == ("", long.strip())


# ==========================================================================
# The API: flag, long paste, file status, isolation
# ==========================================================================
def _api_conversation(api, db, user):
    from tests.conftest import grant_role, sign_in
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    return api.post("/api/v1/conversations", json={}).json()["data"]["id"]


def test_off_a_long_question_is_still_refused_and_attachments_do_not_exist(
        api, db, seeded, user, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "off")
    conv = _api_conversation(api, db, user)
    r = api.post(f"/api/v1/conversations/{conv}/messages",
                 json={"question": "x " * 1500 + "?"})
    assert r.status_code >= 400 and "2000" in r.text
    assert api.get(f"/api/v1/conversations/{conv}/attachments").status_code >= 400


def test_on_a_long_paste_is_saved_and_a_text_file_shows_its_status(
        api, db, seeded, user, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = _api_conversation(api, db, user)
    r = api.post(f"/api/v1/conversations/{conv}/messages",
                 json={"question": (EMAIL + "\n\n") * 8})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["text"] == attachments.MATERIAL_SAVED
    assert [a["status"] for a in body["attachments_saved"]] == ["READY"]

    up = api.post(f"/api/v1/conversations/{conv}/attachments",
                  content=b"Clause 9. Either party may end this on 30 days notice.",
                  headers={"Content-Type": "text/plain", "X-Filename": "note.txt"})
    assert up.status_code == 201, up.text
    assert up.json()["data"]["status"] == "READY"
    listed = api.get(f"/api/v1/conversations/{conv}/attachments").json()["data"]
    assert [a["filename"] for a in listed] == [None, "note.txt"]

    from tests.conftest import grant_role, make_user, sign_in
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    import uuid
    theirs = api.get(f"/api/v1/conversations/{conv}/attachments")
    nobody = api.get(f"/api/v1/conversations/{uuid.uuid4()}/attachments")
    assert theirs.status_code == nobody.status_code == 404
    assert theirs.json() == nobody.json() or \
        theirs.json()["error"]["message"] == nobody.json()["error"]["message"]


# ==========================================================================
# The ledger (plan 1.6–1.8): keys per answer, re-fetch live, stale / unavailable
# ==========================================================================
ASK = frozenset({"assist.ask"})


def test_an_answer_stores_its_ledger_keys_and_refetch_reads_them_live(db, user, offline):
    from legalmind.assist.agent import ledger
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    out = service.ask(db, conversation_id=c, document_version_id=None,
                      question="How many hours did the outage last?", permissions=ASK)
    answer_id = db.execute(text(f'SELECT id FROM "{config.assist_schema()}".ai_answers '
                                "WHERE message_id = :m"), {"m": out.message_id}).scalar()
    keys = ledger.keys_for_answer(db, answer_id)
    assert keys and all(k.startswith("U") for k in keys)
    [got] = ledger.refetch(db, conversation_id=c, keys=keys[:1], permissions=ASK,
                           contract_id=None)
    assert got.state == "current" and "nine hours" in (got.text or "") \
        and got.authority == "USER_MATERIAL"

    # Asked again: the same record keeps its key.
    again = service.ask(db, conversation_id=c, document_version_id=None,
                        question="How many hours did the outage last?", permissions=ASK)
    second = db.execute(text(f'SELECT id FROM "{config.assist_schema()}".ai_answers '
                             "WHERE message_id = :m"), {"m": again.message_id}).scalar()
    assert ledger.keys_for_answer(db, second) == keys

    attachments.purge_expired(db, now=a.expires_at)
    gone, unknown = ledger.refetch(db, conversation_id=c, keys=[keys[0], "U99"],
                                   permissions=ASK, contract_id=None)
    assert gone == ledger.Fetched(keys[0], "unavailable")
    assert unknown == ledger.Fetched("U99", "unavailable")
    # Another conversation never reaches this one's keys.
    other = _conversation(db, user)
    assert ledger.refetch(db, conversation_id=other, keys=keys[:1], permissions=ASK,
                          contract_id=None)[0].state == "unavailable"


def test_a_document_record_goes_stale_on_a_new_version_and_unavailable_out_of_scope(
        db, user, storage):
    from legalmind.assist.agent import ledger
    from legalmind.assist.ingestion.indexing import index_document_version
    from legalmind.assist.knowledge import store
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.assist.ingestion.test_assist_indexing import _ingested
    paras = ["9. Termination", "Either party may terminate this agreement on thirty days "
             "written notice to the other party."]
    v1 = _ingested(db, storage, user, paras)
    index_document_version(db, v1.id)
    c = service.create_conversation(db, user_id=user.id, contract_id=v1.contract_id)
    hits = store.search_chunks(db, document_version_id=v1.id, query="terminate notice")
    turn = service._append_turn(db, c, "ASSISTANT", "x")
    answer_id = service._persist_answer(db, turn, None, service.AssistAnswerState.ANSWERED,
                                        model=None, prompt_version_id=None, latency_ms=None)
    service._persist_citations(db, answer_id, [1], hits)
    [key] = ledger.record_answer(db, conversation_id=c, answer_id=answer_id,
                                 turn_message_id=turn)
    assert key == "D1"

    def state(contract):
        return ledger.refetch(db, conversation_id=c, keys=[key], permissions=ASK,
                              contract_id=contract)[0].state
    assert state(v1.contract_id) == "current"
    ingest_document(db, storage, contract_id=v1.contract_id, uploaded_by=user.id,
                    data=build_docx([*paras, "10. Notices are in writing."]),
                    filename="v2.docx", declared_mime=DOCX_MIME)
    assert state(v1.contract_id) == "stale"
    assert state(None) == "unavailable"


# ==========================================================================
# Owner checks before the Phase 1 exit (2026-10-01)
# ==========================================================================
def _count(db, sql, **params):
    return db.execute(text(sql.format(s=config.assist_schema())), params).scalar_one()


def test_the_retention_purge_removes_chunks_embeddings_and_ledger_records(
        db, user, offline):
    from legalmind.assist.agent import ledger
    from legalmind.assist.knowledge import store
    from legalmind.assist.retrieval import calibration
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=EMAIL.encode(), kind=attachments.PASTE)
    # An embedding row, whether or not a model is installed here.
    model = store.register_embedding_model(
        db, name="test-model", version="t", checksum="t",
        dimensions=calibration.EMBEDDING_DIMENSIONS)
    chunk = db.execute(text(f'SELECT id FROM "{config.assist_schema()}".attachment_chunks '
                            "WHERE attachment_id = :a LIMIT 1"), {"a": a.id}).scalar()
    db.execute(text(f'INSERT INTO "{config.assist_schema()}".attachment_chunk_embeddings '
                    f"(id, chunk_id, embedding_model_id, embedding) VALUES (gen_random_uuid(),"
                    f" :c, :m, CAST(:v AS {store.vector_type(db)}))"),
               {"c": chunk, "m": model, "v": "[" + ",".join(["0.1"] * 384) + "]"})
    out = service.ask(db, conversation_id=c, document_version_id=None,
                      question="How many hours did the outage last?", permissions=ASK)
    assert out.answer_state.value == "ANSWERED"
    for_a = "IN (SELECT id FROM {s}.attachment_chunks WHERE attachment_id = :a)"
    before = (_count(db, "SELECT count(*) FROM {s}.attachment_chunks WHERE attachment_id = :a", a=a.id),
              _count(db, "SELECT count(*) FROM {s}.attachment_chunk_embeddings WHERE chunk_id " + for_a, a=a.id),
              _count(db, "SELECT count(*) FROM {s}.conversation_evidence WHERE conversation_id = :c "
                         "AND source_class = 'U'", c=c))
    assert all(before), before

    # Expiry is reached by the purge a NEW attachment runs — in any conversation.
    db.execute(text(f'UPDATE "{config.assist_schema()}".conversation_attachments '
                    "SET expires_at = now() - interval '1 second' WHERE id = :a"), {"a": a.id})
    _add(db, conversation_id=_conversation(db, user), data=b"Another note entirely.",
         kind=attachments.PASTE)
    assert _count(db, "SELECT count(*) FROM {s}.attachment_chunks WHERE attachment_id = :a",
                  a=a.id) == 0
    assert _count(db, "SELECT count(*) FROM {s}.attachment_chunk_embeddings e WHERE NOT "
                      "EXISTS (SELECT 1 FROM {s}.attachment_chunks c WHERE c.id = e.chunk_id)") == 0
    assert _count(db, "SELECT count(*) FROM {s}.attachment_chunk_embeddings WHERE chunk_id = :x",
                  x=chunk) == 0
    assert _count(db, "SELECT count(*) FROM {s}.conversation_evidence WHERE conversation_id = :c "
                      "AND source_class = 'U'", c=c) == 0
    [row] = attachments.list_for(db, c)
    assert row.status == "EXPIRED"            # ids, size and hash kept for the audit trail
    assert ledger.refetch(db, conversation_id=c, keys=["U1"], permissions=ASK,
                          contract_id=None)[0].state == "unavailable"


def test_the_purge_command_runs_and_reports_a_count_only(monkeypatch, capsys):
    from tools import purge_attachments

    class _Db:
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(purge_attachments, "new_session", _Db)
    monkeypatch.setattr(attachments, "purge_expired", lambda db: 3)
    assert purge_attachments.main() == 0
    assert capsys.readouterr().out.strip() == "purged 3 expired attachment(s)"


def test_another_users_attachments_answer_exactly_as_missing_ones(
        api, db, seeded, user, monkeypatch):
    import uuid

    from tests.conftest import grant_role, make_user, sign_in
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = _api_conversation(api, db, user)
    assert api.post(f"/api/v1/conversations/{conv}/attachments", content=b"Clause 4 text.",
                    headers={"Content-Type": "text/plain",
                             "X-Filename": "a.txt"}).status_code == 201
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    missing = str(uuid.uuid4())
    for method, kwargs in (("get", {}), ("post", {"content": b"x", "headers": {
            "Content-Type": "text/plain", "X-Filename": "b.txt"}})):
        theirs = getattr(api, method)(f"/api/v1/conversations/{conv}/attachments", **kwargs)
        absent = getattr(api, method)(f"/api/v1/conversations/{missing}/attachments", **kwargs)
        assert theirs.status_code == absent.status_code == 404
        assert theirs.json()["error"]["message"] == absent.json()["error"]["message"]
    # Nothing was stored in the owner's conversation by the stranger's attempt.
    assert len(attachments.list_for(db, uuid.UUID(conv))) == 1


def test_api_layer_parsing_is_the_ingestion_parser_itself(monkeypatch):
    from legalmind.api.routers import assist as router
    from legalmind.ingestion import parsing, validation
    seen = []
    real_parse, real_validate = parsing.parse, validation.validate_upload
    monkeypatch.setattr(parsing, "parse",
                        lambda *a, **k: seen.append("parse") or real_parse(*a, **k))
    monkeypatch.setattr(validation, "validate_upload",
                        lambda *a, **k: seen.append("validate") or real_validate(*a, **k))
    mime, segments = router.extract_material(b"Clause 7. Fees are due in 30 days.",
                                             attachments.FILE, "f.txt", "text/plain")
    assert seen == ["validate", "parse"] and mime == "text/plain" and segments
    with pytest.raises(attachments.AttachmentRejected):    # the same magic-byte sniffing
        router.extract_material(b"%PDF-1.4 x", attachments.FILE, "f.txt", "text/plain")


def test_a_paste_that_repeats_itself_is_stored_once(db, user, offline):
    """Live G1 (2026-10-01): a thread pasted with its quotes cited one sentence six
    times and dropped the other half of the question. Identical text is one chunk."""
    c = _conversation(db, user)
    a = _add(db, conversation_id=c, data=(EMAIL + "\n\n") .encode() * 6,
             kind=attachments.PASTE)
    contents = [r.content for r in _chunks(db, a.id)]
    assert contents and len(contents) == len(set(contents))
    out = service.ask(db, conversation_id=c, document_version_id=None,
                      question="How many hours did the outage last?", permissions=ASK)
    assert out.text.count("nine hours") == 1


@pytest.mark.skipif(not __import__("legalmind.assist.retrieval.rerank", fromlist=["x"]).available(),
                    reason="needs the local cross-encoder (CI has none); a stand-in "
                           "scorer does not reproduce the live ranking")
def test_each_part_of_a_two_part_question_keeps_its_own_clause(db, user, monkeypatch):
    """Live G1 (2026-10-01): parts anchored on whole-question relevance, so "how many
    hours… and what credit…?" claimed only the outage line, and the answer said the
    material named no credit. Each part of the reader's own text keeps its clause.
    Real reranker, stub model, zero Gemini."""
    from legalmind.assist.llm import generation
    from legalmind.assist.verification import verify
    from tools.eval_generation import stub
    monkeypatch.setenv("LEGALMIND_ASK_MULTI_SOURCE", "on")
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    monkeypatch.setenv("LEGALMIND_RERANK", "on")
    blocks: list[str] = []
    monkeypatch.setattr(generation, "generate_contract_answer",
                        lambda q, b, **k: (blocks.append(b), stub(q, b, **k))[1])
    monkeypatch.setattr(verify, "check_answer",
                        lambda t, *a, **k: verify.Result(True, t, [], []))
    c = _conversation(db, user)
    _add(db, conversation_id=c, kind=attachments.PASTE, data=(
        b"Subject: March outage and the service credit\n\n"
        b"From the customer: the outage on 14 March lasted nine hours on the primary "
        b"database cluster and breached the monthly availability commitment.\n\n"
        b"We ask that a service credit of fifteen percent of the monthly fee be "
        b"applied to the April invoice, before the renewal date.\n\n") * 6)
    service.ask(db, conversation_id=c, document_version_id=None,
                question="How many hours did the outage last, and what credit is asked for?",
                permissions=ASK)
    assert blocks and "nine hours" in blocks[-1] and "fifteen percent" in blocks[-1]


def test_a_large_upload_never_takes_the_small_paste_before_it_off_the_context(
        db, user, monkeypatch):
    """A-85 (C3): material summing over the inline budget showed NONE of it — a large
    upload took the e-mail pasted before it off the model's context. Each attachment is
    now inlined whole, the newest first, while it fits; shown in arrival order."""
    from legalmind.assist.agent import agent, tools
    conv = _conversation(db, user)
    _add(db, conversation_id=conv, data=EMAIL.encode(), kind=attachments.PASTE)
    big = "\n\n".join(f"Paragraph {i}: the draft sets service level {i} for the "
                      "customer's production workloads and their credits." for i in range(60))
    _add(db, conversation_id=conv, data=big.encode(), kind=attachments.PASTE)
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=frozenset(
        {"assist.ask"}), conversation_id=conv)

    def shown(budget):
        monkeypatch.setattr(agent, "INLINE_MATERIAL_CHARS", budget)
        return " ".join(agent._inline_material(ctx, agent.EvidenceRegistry(db, conv)))
    small = shown(len(EMAIL) + 50)                 # room for the paste, not the upload
    assert "nine hours" in small and "Paragraph 59" not in small
    both = shown(10 * len(big))
    assert "nine hours" in both and "Paragraph 59" in both
    assert both.index("nine hours") < both.index("Paragraph 0")       # arrival order

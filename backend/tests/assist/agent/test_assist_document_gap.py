"""A selected document whose text is missing or incomplete (document-reading audit,
2026-10-15: R1–R6, F8, LOC-1, PROV-1). Before: a version with no chunks was "read whole"
with its gate open and no records, nothing told the reader, and OCR provenance and the
page never reached the model or the Sources. A scripted fake provider — no model call.
Synthetic text only (rule 21)."""
from __future__ import annotations

import json

from sqlalchemy import text

from legalmind import config
from legalmind.assist import service
from legalmind.assist.agent import agent, tools
from legalmind.assist.ingestion import indexing
from legalmind.assist.knowledge import store
from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.domain import enums as E
from tests.assist.agent.test_assist_agent import PERMS, Scripted, _ctx
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    indexed_contract,
    storage,
)

#: The model says the document lacks something — what an unread document invites.
ABSENT = json.dumps({"blocks": [{"kind": "reasoning",
                                 "text": "The document does not state a liability cap."}],
                     "assessment": "n/a"})


def _search(ctx, **kw):
    return tools.run(ctx, "search_knowledge", {"query": "liability cap", **kw})


def _run_meta(db, version, **meta):
    run = db.get(M.DocumentProcessingRun, latest_completed_run_id(db, version.id))
    run.run_metadata = {**(run.run_metadata or {}), **meta}
    db.flush()


def _ocr_page(db, version, page=3):
    """The liability clause's evidence row, re-labelled as OCR of page `page`."""
    db.execute(text("UPDATE document_evidence SET source_type = 'OCR', page_number = :p "
                    "WHERE document_version_id = :v AND content LIKE '%aggregate%'"),
               {"p": page, "v": version.id})
    db.flush()


# ------------------------------------------------------------------- R1 / R6 / R4
def test_a_version_with_no_chunks_shuts_the_gate_and_says_why(db, user, indexed_contract):
    contract, version = indexed_contract
    store.delete_chunks(db, version.id)
    ctx = _ctx(db, user, contract)
    assert tools.document_gap(db, version.id) == tools.Gap("not_indexed")
    for kw in ({"sources": ["documents"]}, {}):          # alone, and with every source
        q = _search(ctx, **kw).by_source["documents"]
        assert (q.gate_open, q.lexical_hit, q.count_returned) == (False, False, 0)
        assert q.document_state == "not searchable yet"


def test_an_outline_task_over_no_chunks_does_not_open_the_gate(db, user, storage):
    from legalmind.assist.query import query_plan, routing
    from legalmind.assist.retrieval import retrieval
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.test_ingestion import build_docx
    contract = M.Contract(owner_id=user.id, name="Outlined", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                              data=build_docx([
                                  "1. Either party may terminate this Agreement for "
                                  "convenience on ninety days prior written notice to "
                                  "the other party."]),
                              filename="o.docx", declared_mime=DOCX_MIME).document_version
    indexing.index_document_version(db, version.id)
    plan = query_plan.plan("Give me a short summary.", has_document=True, prior=(),
                           instruction="Give me a short summary.")
    route = routing.RoutePlan(comparison=False, domains=(routing.Domain.DOCUMENT,),
                              statute_shaped=False)
    assert plan.presentation.document_wide
    pool = retrieval.candidates(db, plan, route, permissions=PERMS,
                                document_version_id=version.id, rescue=False)
    assert pool.document_gate is True                   # it has an outline
    store.delete_chunks(db, version.id)
    pool = retrieval.candidates(db, plan, route, permissions=PERMS,
                                document_version_id=version.id, rescue=False)
    assert pool.document_gate is False


def test_an_integrity_refusal_is_kept_on_the_run(db, user, indexed_contract, monkeypatch):
    _, version = indexed_contract
    store.delete_chunks(db, version.id)
    monkeypatch.setattr(indexing, "integrity_failures", lambda rows, chunks: [
        "CONTENT_LOSS: 50% of the evidence text is missing"])
    run = db.get(M.DocumentProcessingRun, latest_completed_run_id(db, version.id))
    before = dict(run.run_metadata or {})
    result = indexing.index_document_version(db, version.id)
    db.flush()
    db.refresh(run)
    assert result.chunks_written == 0 and store.count_chunks(db, version.id) == 0
    # codes only, merged into the run's metadata — never replacing it
    assert run.run_metadata == {**before, "assist_index_refused": ["CONTENT_LOSS"]}
    # said as a refusal, never "not searchable yet" (an index that is not coming)
    assert tools.document_gap(db, version.id) == tools.Gap("index_refused")
    assert "failed the reading checks" in tools.gap_reason(tools.Gap("index_refused"))
    # a later index of the same reading that passes clears it (review, 2026-10-16)
    monkeypatch.setattr(indexing, "integrity_failures", lambda rows, chunks: [])
    assert indexing.index_document_version(db, version.id).chunks_written > 0
    db.flush()
    db.refresh(run)
    assert "assist_index_refused" not in run.run_metadata
    assert tools.document_gap(db, version.id) is None


# ------------------------------------------------------------------- R2 / R5
def test_a_document_still_processing_is_said_first_in_code(db, user, indexed_contract):
    contract, version = indexed_contract
    version.processing_status = E.ProcessingStatus.PROCESSING
    db.flush()
    ctx = _ctx(db, user, contract)
    q = _search(ctx).by_source["documents"]
    assert not q.gate_open and q.document_state == "still being processed"
    p = Scripted(final=ABSENT)
    t = agent.run_turn(p, ctx, "What is the liability cap?")
    assert t.blocks[0]["kind"] == "next_step" and not t.blocks[0]["cites"]
    assert "still being processed" in t.blocks[0]["text"]
    assert "doc:processing" in t.flags
    # nothing was read, so the model's "does not state a liability cap" never ships
    assert not any("does not state" in b["text"] for b in t.blocks)
    assert "Its text is not available (still being processed)" in json.dumps(
        p.seen[0]["contents"])


def test_a_partly_read_document_names_its_unread_pages(db, user, indexed_contract):
    contract, version = indexed_contract
    version.extraction_status = E.ExtractionStatus.PARTIAL
    _run_meta(db, version, pages_failed=[2])
    ctx = _ctx(db, user, contract)
    assert tools.document_gap(db, version.id) == tools.Gap("partial", (2,))
    q = _search(ctx).by_source["documents"]
    assert q.gate_open and q.count_returned            # read as before
    assert q.document_state == "incomplete: page(s) 2 could not be read"
    header, _ = agent._selected_document(ctx)
    assert header.endswith(" Its text is incomplete: page(s) 2 could not be read — "
                           "never say the document lacks something that could be on "
                           "those pages.")
    t = agent.run_turn(Scripted(final=ABSENT), ctx, "What is the liability cap?")
    assert t.blocks[-1]["kind"] == "next_step" and "page(s) 2" in t.blocks[-1]["text"]
    assert t.blocks[0]["kind"] != "next_step" and "doc:partial" in t.flags


def test_a_fully_read_document_is_unchanged(db, user, indexed_contract):
    contract, version = indexed_contract
    ctx = _ctx(db, user, contract)
    assert tools.document_gap(db, version.id) is None
    assert agent._selected_document(ctx) == (
        f'SELECTED DOCUMENT: "Ask MSA" (MSA), version {version.version_number}, draft '
        'or unsigned. "This agreement", "the clause", "this MSA" refer to it; it is the '
        "primary source for questions about it.", False)
    q = _search(ctx).by_source["documents"]
    assert q.gate_open and q.document_state is None
    presented = agent._present(_search(ctx), agent.EvidenceRegistry(db, ctx.conversation_id))
    assert "document_state" not in json.dumps(presented)
    t = agent.run_turn(Scripted(), ctx, "What is the liability cap?")
    assert not any(f.startswith("doc:") for f in t.flags)
    assert not any("selected document's text" in b["text"] for b in t.blocks)


def test_the_unread_note_speaks_the_readers_language():
    for lang in ("en", "hinglish", "hi"):
        line = agent.agent_verify.note("document_unread", lang).format("not searchable yet")
        assert "not searchable yet" in line and "{}" not in line


# ------------------------------------------------------------------- F8 / PROV-1
def test_an_ocr_record_carries_its_page_and_how_it_was_read(db, user, indexed_contract,
                                                           monkeypatch):
    contract, version = indexed_contract
    _ocr_page(db, version)
    for limit in (tools.WHOLE_DOCUMENT_CHARS, 0):        # read whole, then ranked
        monkeypatch.setattr(tools, "WHOLE_DOCUMENT_CHARS", limit)
        ctx = _ctx(db, user, contract)
        found = _search(ctx, sources=["documents"])
        ocr = [r for r in found.records if "aggregate" in r.text]
        assert ocr and (ocr[0].page, ocr[0].read_by) == (3, "OCR"), limit
        reg = agent.EvidenceRegistry(db, ctx.conversation_id)
        shown = agent._present(found, reg)["records"]
        assert any(r.get("page") == 3 and r.get("read_by") == "OCR" for r in shown)
        assert all("read_by" not in r for r in shown if "aggregate" not in r["text"])


def test_read_by_reads_the_enum_however_it_arrives():
    assert tools.read_by("OCR") == tools.read_by("EvidenceSourceType.OCR") == "OCR"
    assert tools.read_by("EvidenceSourceType.TABLE") == "TABLE"
    assert tools.read_by("NATIVE_TEXT") is None and tools.read_by(None) is None


def test_re_fetched_evidence_keeps_its_location(db, user):
    reg = agent.EvidenceRegistry(db, _ctx(db, user).conversation_id)
    result = tools.ToolResult(tool="get_evidence", evidence=(tools.EvidenceRecord(
        evidence_id="D1", state="current", ref="DOC:x", text="t", location="13.1"),))
    assert agent._present(result, reg)["evidence"][0]["location"] == "13.1"


# ------------------------------------------------------------------- LOC-1
def test_a_source_names_its_page_and_ocr_live_and_on_replay(db, user, indexed_contract):
    _, version = indexed_contract
    _ocr_page(db, version, page=4)
    rows = db.execute(text(
        f'SELECT c.id, c.content FROM "{config.assist_schema()}".chunks c '
        "WHERE c.document_version_id = :v ORDER BY ordinal"), {"v": version.id}).all()
    items = [(f"D{i}", body, "17.2", f"DOC:{cid}", "the selected document", "current")
             for i, (cid, body) in enumerate(rows, 1)]
    views = service.source_views(db, items)
    ocr = [v for v in views if "aggregate" in v["text"]]
    assert ocr and ocr[0]["page"] == 4 and ocr[0]["read_by"] == "OCR"
    assert ocr[0]["location"] == "17.2"                  # never folded into location
    assert all("read_by" not in v for v in views if "aggregate" not in v["text"])
    # live and replay both build the Sources here, from the same rows
    assert service.source_views(db, items) == views

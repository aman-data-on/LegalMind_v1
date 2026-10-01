"""Per-tool latency for the Ask agent tool layer (Phase 2, B8) — zero Gemini.

    python3 -m tools.measure_tool_latency --db <SCRATCH url>

Runs every tool in `assist/tools.py` through `tools.run` — the entry point the Phase 3
loop will use — once per question of the frozen 77-question set, and prints p50/p95 per
tool. SCRATCH ONLY: it WRITES a user, the ratified standards, the supplied documents, a
conversation, an attachment and a ledger answer the first time (idempotent after that);
the live database is refused. The Constitution and statute corpus must already be there
(a restored rehearsal copy holds both).
"""
from __future__ import annotations

import argparse
import statistics
import sys

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import attachments, ledger, positions, service, store, tools
from legalmind.db import models as M
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.benchmark_retrieval import _ingest_corpus, _load_eval_dataset
from tools.verify_assist_quality import DATASET, _documents

PERMS = frozenset({"assist.ask", "legal_position.view", "configuration.view"})
MATERIAL = (b"From the customer: the outage on 14 March lasted nine hours on the primary "
            b"database cluster.\n\nWe ask that a service credit of fifteen percent of the "
            b"monthly fee be applied to the April invoice.")


def _setup(db, questions) -> dict[str, M.Contract]:
    contracts = {c.name: c for c in db.execute(select(M.Contract)).scalars()}
    if not contracts:
        _ingest_corpus(db, LocalFilesystemStorage(".e2e/tool-latency-objects"),
                       _documents(questions))
        db.commit()
        contracts = {c.name: c for c in db.execute(select(M.Contract)).scalars()}
    schema = config.assist_schema()
    if not db.execute(text(f'SELECT 1 FROM "{schema}".position_chunks LIMIT 1')).first():
        import tools.import_ratified_standards as imp
        owner = db.get(M.User, next(iter(contracts.values())).owner_id)
        imp.import_standards(db, actor_email=owner.email, publish=True)
        positions.chunk_ratified_standards(db)
        db.commit()
    return contracts


def _conversation(db, contract) -> tuple[tools.ToolContext, list[str], str]:
    conv = service.create_conversation(db, user_id=contract.owner_id,
                                       contract_id=contract.id)
    from legalmind.api.routers.assist import extract_material
    mime, extracted = extract_material(MATERIAL, attachments.PASTE, None, "text/plain")
    att = attachments.add(db, conversation_id=conv, data=MATERIAL, kind=attachments.PASTE,
                          mime=mime, extracted=extracted)
    version = db.execute(text("SELECT id FROM document_versions WHERE contract_id = :k "
                              "ORDER BY version_number DESC LIMIT 1"),
                         {"k": contract.id}).scalar()
    hits = store.search_chunks(db, document_version_id=version, query="liability")[:3]
    turn = service._append_turn(db, conv, "ASSISTANT", "latency fixture")
    answer = service._persist_answer(db, turn, None, service.AssistAnswerState.ANSWERED,
                                     model=None, prompt_version_id=None, latency_ms=None)
    service._persist_citations(db, answer, list(range(1, len(hits) + 1)), hits)
    keys = ledger.record_answer(db, conversation_id=conv, answer_id=answer,
                                turn_message_id=turn)
    db.commit()
    ctx = tools.ToolContext.open(db, user_id=contract.owner_id, permissions=PERMS,
                                 conversation_id=conv)
    return ctx, keys or ["D1"], str(att.id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()
    if args.db.rsplit("/", 1)[-1] in {"legalmind_v1_dev", "legalmind"}:
        raise SystemExit("refusing the live database: this tool writes")
    engine = create_engine(args.db, future=True)
    db = sessionmaker(bind=engine, future=True)()
    questions = _load_eval_dataset(DATASET)
    contracts = _setup(db, questions)
    contexts = {}
    tools.TIMINGS = timings = []
    try:
        for q in questions:
            contract = contracts.get(q["document"].rsplit(".", 1)[0])
            if contract is None:
                continue
            if contract.id not in contexts:
                contexts[contract.id] = _conversation(db, contract)
            ctx, keys, att = contexts[contract.id]
            query = q["question"][:tools.MAX_QUERY_CHARS]
            for name, arguments in (
                    ("search_knowledge", {"query": query}),
                    ("get_company_position", {"topic": query}),
                    ("search_statutes", {"query": query}),
                    ("get_evidence", {"evidence_ids": keys[:tools.MAX_K]}),
                    ("list_attachments", {}),
                    ("search_attachment", {"attachment_id": att, "query": query}),
                    ("ask_user", {"question": "Which agreement do you mean?"})):
                result = tools.run(ctx, name, arguments)
                if result.error:
                    raise SystemExit(f"{name} returned {result.error} for {q['id']}")
    finally:
        tools.TIMINGS = None
        db.rollback()
        db.close()
        engine.dispose()
    by: dict[str, list[float]] = {}
    for name, ms in timings:
        by.setdefault(name, []).append(ms)
    print(f"tool latency over {len(questions)} frozen questions (ms):")
    for name in tools.TOOLS:
        xs = sorted(by.get(name, []))
        if xs:
            p95 = xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))]
            print(f"  {name:22} n={len(xs):3}  p50={statistics.median(xs):8.1f}"
                  f"  p95={p95:8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

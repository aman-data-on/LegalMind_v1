"""The query-understanding evaluation matrix — 16 classes, the whole pipeline.

    python3 -m tools.eval_understanding --out baseline.json          # routing only, free
    python3 -m tools.eval_understanding --out baseline.json --full   # + answers (Gemini)

Phase A is deterministic and calls no provider: it records what the router UNDERSTANDS
and the domain plan it produces. Phase B runs the same questions through `service.ask`
against the live corpus inside a transaction that is ALWAYS rolled back — no
conversation, answer, citation or audit row survives.

The point of the file is parity: a refactor that changes no behaviour must reproduce
phase A byte for byte.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

MATRIX = pathlib.Path(__file__).resolve().parents[1] / "tests/assist_eval/understanding_matrix.json"
# Real documents in the live corpus, by the type the matrix names.
DOCS = {"NDA": "5a30b979-05f2-45ef-996e-0e1a10dfdaed",
        "MSA": "16f1d1dd-67b9-4b0b-ada2-4cb7accd371c"}


def _db_url() -> str:
    import os
    if "LEGALMIND_DATABASE_URL" in os.environ:
        return os.environ["LEGALMIND_DATABASE_URL"]
    with open("/root/.legalmind.env") as handle:
        for line in handle:
            if line.startswith("LEGALMIND_DATABASE_URL"):
                return line.split("=", 1)[1].strip()
    raise SystemExit("no database url")


def understanding(question: str, *, has_document: bool, permissions, statutes: bool,
                  jurisdictions: frozenset = frozenset()) -> dict:
    """Everything today's code derives about a question, in one record."""
    from legalmind.assist import intent, routing

    route = routing.plan(question, has_document=has_document, permissions=permissions,
                         statutes_available=statutes,
                         statute_jurisdictions=jurisdictions)
    from legalmind.assist import understanding as U
    u = U.understand(question)
    signals = intent.legal_question_signals(question)
    return {
        "requested_fact": u.requested_fact,
        "authority": sorted(u.authority),
        "jurisdiction": u.jurisdiction,
        "temporal": u.temporal.kind,
        "temporal_date": u.temporal.date,
        "include_superseded": route.include_superseded,
        "capability": bool(getattr(route, "capability", False)),
        "general_knowledge": bool(getattr(route, "general_knowledge", False)),
        "comparison": route.comparison,
        "statute_shaped": route.statute_shaped,
        "statute_signals": list(route.statute_signals),
        "signals_fired": list(signals.because),
        "exact_text": intent.is_exact_text_request(question),
        "follow_up": intent.is_follow_up(question),
        "mentions_organization": intent.mentions_organization(question),
        "domains": [d.value for d in route.domains],
        "fallback": [d.value for d in getattr(route, "fallback", ())],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--full", action="store_true", help="also run answers (uses Gemini)")
    args = ap.parse_args()

    from sqlalchemy import create_engine
    from sqlalchemy import text as sql
    from sqlalchemy.orm import sessionmaker

    from legalmind.assist import generation, service
    from legalmind.assist import statutes as st
    from legalmind.security import permissions as P

    perms = frozenset({P.ASSIST_ASK, P.CONTRACT_VIEW, P.FINDING_VIEW,
                       P.LEGAL_POSITION_VIEW, P.CONFIGURATION_VIEW})
    cases = json.loads(MATRIX.read_text())["cases"]
    calls = {"n": 0}
    for name in ("generate", "generate_raw", "generate_position_reading_aid"):
        fn = getattr(generation, name)
        setattr(generation, name, (lambda f: (lambda *a, **k: (
            calls.__setitem__("n", calls["n"] + 1), f(*a, **k))[1]))(fn))

    db = sessionmaker(bind=create_engine(_db_url(), future=True), future=True)()
    rows = []
    try:
        have_statutes = st.available(db)
        have_jurisdictions = st.jurisdictions(db)
        uid = db.execute(sql("SELECT id FROM users WHERE status='ACTIVE' LIMIT 1")).scalar()
        for case in cases:
            ver = DOCS.get(case.get("doc") or "")
            rec = {k: case.get(k) for k in
                   ("class", "q", "doc", "after", "intent", "requested_fact",
                    "authority", "must_refuse", "ambiguous", "temporal", "jurisdiction",
                    "must_not_cite_repealed", "may_cite_repealed")}
            rec["expected_temporal"] = case.get("temporal")
            rec["understanding"] = understanding(
                case["q"], has_document=bool(ver), permissions=perms,
                statutes=have_statutes, jurisdictions=have_jurisdictions)
            if args.full:
                conv = db.execute(sql('INSERT INTO "assist".conversations (id, user_id) '
                                      "VALUES (:i, :u) RETURNING id"),
                                  {"i": uuid.uuid4(), "u": uid}).scalar_one()
                if case.get("after"):
                    service.ask(db, conversation_id=conv,
                                document_version_id=uuid.UUID(ver) if ver else None,
                                question=case["after"], permissions=perms, request_id="warm")
                calls["n"] = 0
                started = time.monotonic()
                out = service.ask(db, conversation_id=conv,
                                  document_version_id=uuid.UUID(ver) if ver else None,
                                  question=case["q"], permissions=perms, request_id="matrix")
                section = out.statutes or {}
                rec["result"] = {
                    "state": out.answer_state.value,
                    "text": out.text,
                    "statute_text": section.get("text"),
                    "statute_citations": [c.get("citation") for c in
                                          (section.get("citations") or [])],
                    "doc_citations": len(out.citations or []),
                    "positions": len(out.positions or []),
                    "domains_used": list(out.domains or []),
                    "gemini": calls["n"],
                    "ms": int((time.monotonic() - started) * 1000),
                }
            rows.append(rec)
    finally:
        db.rollback()
        db.close()
    pathlib.Path(args.out).write_text(json.dumps(rows, indent=1, default=str))
    print(f"{len(rows)} cases written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

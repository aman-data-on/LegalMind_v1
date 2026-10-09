"""Ask answer feedback for operators (`AM-123`) — evaluation only, nothing is tuned.

    python3 -m tools.feedback_report --flags
    python3 -m tools.feedback_report --month 2026-10 --out /var/lib/legalmind/feedback/2026-10.json

``--flags`` lists the query types at or over the owner's alert threshold (3+ Not
helpful in the rolling window) — the same query the WARNING log line raises on.

``--month`` writes that month's Not helpful cases — question, answer, reason, model,
prompt version, cited records and corpus version — for a human to curate into golden-set
NEGATIVE examples. The file holds real readers' text, so it is written OUTSIDE any git
checkout (rule 21, locked 54.6), owner-readable only, and nothing is ever appended to
`tests/assist_eval/rag_benchmark.json` by this tool.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from sqlalchemy import text

from legalmind import config
from legalmind.assist import feedback
from legalmind.db.session import new_session


def inside_a_checkout(path: Path) -> bool:
    """True when ``path`` would land in any git working tree (a worktree's ``.git`` is a
    file, the deploy tree's a directory) — refused, so a case never enters a repo."""
    return any((p / ".git").exists() for p in path.resolve().parents)


def flags(db) -> list[dict]:
    rows = db.execute(text(f"""
        SELECT query_type, count(*) FROM "{config.assist_schema()}".answer_feedback
         WHERE kind = 'RATING' AND rating = 'DOWN'
           AND created_at > now() - make_interval(days => :d)
         GROUP BY query_type HAVING count(*) >= :n ORDER BY count(*) DESC, query_type"""),
        {"d": feedback.DOWN_CLUSTER_DAYS, "n": feedback.DOWN_CLUSTER_MIN}).all()
    return [{"query_type": q, "count": n} for q, n in rows]


def month_cases(db, month: str) -> list[dict]:
    start = date.fromisoformat(f"{month}-01")
    s = config.assist_schema()
    rows = db.execute(text(f"""
        SELECT f.id, f.query_type, f.reason, f.corpus_version, f.created_at,
               a.id, a.content, an.model_identity, pv.code,
               (SELECT u.content FROM "{s}".messages u
                 WHERE u.conversation_id = a.conversation_id AND u.role = 'USER'
                   AND u.ordinal < a.ordinal ORDER BY u.ordinal DESC LIMIT 1),
               (SELECT coalesce(json_agg(json_build_object(
                         'key', ce.evidence_key, 'domain', ce.domain,
                         'source_ref', ce.source_ref, 'source_version', ce.source_version,
                         'chunk_id', coalesce(ce.chunk_id, ce.position_chunk_id,
                                              ce.statute_chunk_id, ce.knowledge_item_id,
                                              ce.attachment_chunk_id))
                         ORDER BY ae.claim_ordinal), '[]'::json)
                  FROM "{s}".answer_evidence ae
                  JOIN "{s}".conversation_evidence ce ON ce.id = ae.ledger_id
                 WHERE ae.answer_id = an.id)
          FROM "{s}".answer_feedback f
          JOIN "{s}".messages a ON a.id = f.message_id
          LEFT JOIN "{s}".ai_answers an ON an.message_id = a.id
          LEFT JOIN "{s}".prompt_versions pv ON pv.id = an.prompt_version_id
         WHERE f.kind = 'RATING' AND f.rating = 'DOWN'
           AND f.created_at >= :start AND f.created_at < (:start + interval '1 month')
         ORDER BY f.created_at"""), {"start": start}).all()
    return [{"feedback_id": str(r[0]), "query_type": r[1], "reason": r[2],
             "corpus_version": r[3], "recorded_at": r[4].isoformat(),
             "message_id": str(r[5]), "answer": r[6], "model": r[7],
             "prompt_version": r[8], "question": r[9], "cited": r[10]} for r in rows]


def write_cases(cases: list[dict], out: Path) -> None:
    if inside_a_checkout(out):
        raise SystemExit(f"refused: {out} is inside a git checkout; feedback cases hold "
                         "readers' text and are written outside any repository")
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)          # the mode above applies only to a file it creates
    with os.fdopen(fd, "w") as fh:
        json.dump({"negative_examples_for_curation": cases}, fh, indent=2,
                  ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--flags", action="store_true")
    parser.add_argument("--month", help="YYYY-MM")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if bool(args.month) != bool(args.out) or not (args.flags or args.month):
        parser.error("give --flags, or --month with --out")
    if args.out and inside_a_checkout(args.out):     # before touching the database
        write_cases([], args.out)
    db = new_session()
    try:
        if args.flags:
            print(json.dumps(flags(db), indent=2))
        if args.month:
            cases = month_cases(db, args.month)
            write_cases(cases, args.out)
            print(f"wrote {len(cases)} case(s) to {args.out}")   # a count, never text
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

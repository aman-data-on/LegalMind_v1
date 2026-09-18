"""Deterministic gate diagnostic — can a false refusal be recovered SAFELY?

No Gemini anywhere: local embeddings and SQL only, so this can be run as often
as an idea needs testing (CLAUDE.md § Gemini cost guard).

It answers two questions the Tier-2 gate cannot:

  1. WHERE do the refusals of answerable questions come from — did the gate
     refuse evidence it already held, or did retrieval never find the gold
     chunk? Only the first is reachable by a gate change at all.
  2. Is there ANY threshold, on any candidate peak feature, that opens some of
     those refusals while opening NONE of the correctly-refused unanswerable
     ones? That is the only shape of change worth proposing: the owner rule of
     2026-09-14 is that recall may improve only WITHOUT wrongly-answered rising.

Run it against a gate database that already holds an ingested corpus (the
Tier-2 gate leaves one behind):

    python3 tools/probe_gate.py

MEASURED 2026-09-18 — seven features have now failed this test. The 35-point
threshold sweep, a second similarity feature and an alternative embedding model
(all 2026-09-16), the rerank floor (2026-09-17, PR #74), a strict lexical match
on the planner's canonical legal term, and here `gap_second`, `ratio` and
`margin3`. The shipped `gap_mean` is the best of them and a threshold above
every unanswerable value recovers exactly ONE question of 21 — itself fitted to
the maximum of only 12 unanswerable samples, so it would not survive a
thirteenth. The gate is unchanged as a result, and the recovery work is already
being done: the rescue judge turns the raw gate's 21 refusals into 3 end to end.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("LEGALMIND_SOURCE_MATERIAL_DIR", "/root/Legalmind.v1/legal-docs")

from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import (
    calibration,
    embedding_runtime,
    guardrails,
    store,
)
from legalmind.assist.store import vector_schema, vector_type
from tools.benchmark_retrieval import (
    _chunks,
    _load_eval_dataset,
    _resolve_anchors,
)
from tools.verify_assist_quality import DATASET, _gate_url

FEATURES = ("gap_mean", "gap_second", "ratio", "margin3")


def _features(scores: list[float]) -> dict | None:
    """Every peak measure that can be read off one vector pass."""
    if len(scores) < 2:
        return None
    top, second, rest = scores[0], scores[1], scores[1:]
    return {"top": top,
            "gap_mean": top - sum(rest) / len(rest),      # what ships
            "gap_second": top - second,                    # peak to next
            "ratio": top / second if second else 99.0,
            "margin3": top - sum(scores[1:4]) / len(scores[1:4])}


def main() -> int:
    db = sessionmaker(bind=create_engine(_gate_url(), future=True), future=True)()
    questions = _load_eval_dataset(DATASET)
    versions: dict[str, UUID] = {}
    for name, dv in db.execute(text(
            "SELECT dv.original_filename, dv.id FROM document_versions dv "
            "ORDER BY dv.created_at DESC")).all():
        versions.setdefault(name, dv)
    if not versions:
        print("no ingested corpus in the gate database; run the Tier-2 gate first")
        return 1
    expected, _ = _resolve_anchors(
        questions, {n: _chunks(db, d) for n, d in versions.items()})

    schema, vschema, vtype = config.assist_schema(), vector_schema(db), vector_type(db)
    op = f'OPERATOR("{vschema}".<=>)'

    def scores(dv, question: str) -> list[float]:
        vector = embedding_runtime.embed_query(question)
        if vector is None:
            return []
        embedded, _ = vector
        literal = "[" + ",".join(f"{x:.6f}" for x in embedded) + "]"
        return [float(r[0]) for r in db.execute(text(f"""
            SELECT 1 - (ce.embedding {op} CAST(:q AS {vtype})) AS cosine
              FROM "{schema}".chunk_embeddings ce
              JOIN "{schema}".chunks c ON c.id = ce.chunk_id
             WHERE c.document_version_id = :dv
             ORDER BY cosine DESC LIMIT 20"""), {"q": literal, "dv": dv}).all()]

    opened = 0
    recoverable: list[tuple] = []     # answerable, refused, gold WAS present
    unreachable: list[tuple] = []     # answerable, refused, gold never found
    refused_ok: list[tuple] = []      # unanswerable, correctly refused
    wrongly_opened: list[str] = []
    for q in questions:
        if q["document"] not in versions:
            continue
        outcome = store.search_hybrid(
            db, document_version_id=versions[q["document"]], query=q["question"],
            embed_query=embedding_runtime.embed_query)
        sufficient = outcome.gate_open and guardrails.evidence_is_sufficient(
            [h.content for h in outcome.hits])
        feats = _features(scores(versions[q["document"]], q["question"]))
        gold = bool(expected.get(q["id"], set())
                    & {h.chunk_id for h in (outcome.hits or outcome.candidates)})
        row = (q["id"], q["difficulty"], outcome.lexical_hit, feats, gold,
               q["question"][:56])
        if q["expected"] == "NOT_FOUND":
            if sufficient:
                wrongly_opened.append(q["id"])
            elif feats:
                refused_ok.append(row)
        elif sufficient:
            opened += 1
        elif gold:
            recoverable.append(row)
        else:
            unreachable.append(row)

    print(f"COSINE_FLOOR={calibration.COSINE_FLOOR}  "
          f"PEAK_MARGIN={calibration.PEAK_MARGIN}\n")
    print(f"answerable opened by the raw gate      {opened}")
    print(f"answerable refused, gold WAS present   {len(recoverable)}  "
          f"<- the only set a gate change can reach")
    print(f"answerable refused, gold never found   {len(unreachable)}  "
          f"<- a retrieval defect, not a gate one")
    print(f"unanswerable correctly refused         {len(refused_ok)}")
    print(f"unanswerable wrongly opened            {len(wrongly_opened)}  "
          f"{wrongly_opened}\n")

    print("Is there a SAFE threshold — one strictly above every correctly-refused")
    print("unanswerable question, so it cannot raise wrongly-answered?\n")
    for name in FEATURES:
        worst = max(r[3][name] for r in refused_ok)
        gained = [r[0] for r in recoverable if r[3][name] > worst]
        ships = " (ships)" if name == "gap_mean" else ""
        print(f"  {name:11}{ships:9} highest unanswerable {worst:.4f}  "
              f"recovers {len(gained):2}  {gained}")
    print("\nA threshold set above the maximum of a 12-question sample is fitted to")
    print("that sample. Treat any small gain here as noise, not a finding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

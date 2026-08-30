"""Tier-2 release gate — `AM-28`, run as a command rather than held as a convention.

`AM-28` locks the gate in one sentence: *"a change to retrieval, chunking, prompt, or
model that worsens faithfulness or the wrongly-answered rate does not ship."* Until this
tool existed the gate was a stated rule with no runner — exactly the state
`preflight.py`'s docstring warns about: a register nobody runs is an implicit assumption
with extra steps.

--------------------------------------------------------------------------
What is measured, and what honestly cannot be yet
--------------------------------------------------------------------------
`AM-28` names four quantities. They split cleanly by what they require:

    MEASURED HERE      retrieval recall            needs documents + the local model
                       refusal correctness         (both directions, at the gate)

    BLOCKED            faithfulness                need a GENERATED answer to score, so
                       citation precision          they require the `AM-31` gate open
                                                   plus a key — and `AM-31` m4 forbids
                                                   substituting a synthetic result

The blocking comparison is exactly the locked sentence: the WRONGLY-ANSWERED RATE must
not worsen against the recorded baseline. Recall and retention deltas are printed and
flagged, but `AM-28`'s gate names faithfulness and the wrongly-answered rate, and this
tool does not widen a locked gate on its own authority. When generation measurement
becomes possible, faithfulness joins the blocking set — the placeholder in the baseline
file marks where.

--------------------------------------------------------------------------
Why this measures the SHIPPED path, not a mirror of it
--------------------------------------------------------------------------
Every question runs through `store.search_hybrid` itself — the production SQL, the
production RRF fusion, the production `gate_is_open` — against a database populated by
the production ingestion and indexing pipeline (`ingest_document` →
`index_document_version`, which writes `chunk_embeddings` through `embedding_runtime`).
The earlier calibration harness (`benchmark_retrieval.py --eval`) ranks candidates from
an in-memory cache because it compares models that are not installed; a RELEASE gate has
the opposite job — proving the one pipeline that ships still meets its recorded bar —
so a re-implementation here would be measuring the mirror, not the product.

--------------------------------------------------------------------------
Where it runs
--------------------------------------------------------------------------
Locally, where the source documents (54.6 keeps them out of the repository, so out of
CI) and the provisioned model live. No source material → SKIP, exit 0, same honesty as
the calibration harness. Source material present but no model → exit 1: the shipped
pipeline includes the model, and a gate that quietly measured the lexical-only
degradation would pass a broken provisioning.

The baseline (`tests/assist_eval/baseline.json`) carries numbers, hashes and identities
only — no document text — so it can live in the repository and make "worsened" a diffable
fact.

Run it:   python -m tools.verify_assist_quality              # compare against baseline
          python -m tools.verify_assist_quality --write-baseline   # record a new bar
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import calibration, embedding_runtime, store
from legalmind.ingestion.storage import LocalFilesystemStorage
from tools.benchmark_retrieval import (
    _bench_url,
    _chunks,
    _ingest_corpus,
    _load_eval_dataset,
    _resolve_anchors,
)

BASELINE = pathlib.Path("tests/assist_eval/baseline.json")
DATASET = pathlib.Path("tests/assist_eval/questions_draft.json")

# A distinct database from the calibration harness's, so a gate run and a benchmark
# run cannot clobber each other's ingest — the F-4 lesson applied preemptively.
GATE_DBNAME = "legalmind_v1_tier2_gate"


def _gate_url() -> str:
    return _bench_url().rsplit("/", 1)[0] + "/" + GATE_DBNAME


SETUP_INSTRUCTIONS = f"""\
FAIL  the gate database is not provisioned. One-time superuser setup (the same
      deployment precondition preflight reports for every environment — `vector`
      is not a trusted extension, so the application role cannot create it):

        CREATE DATABASE {GATE_DBNAME};
        \\c {GATE_DBNAME}
        CREATE SCHEMA extensions;
        CREATE EXTENSION vector SCHEMA extensions;
        GRANT ALL ON DATABASE {GATE_DBNAME} TO legalmind;

      The extension lives in its own schema so this tool's per-run reset (dropping
      and rebuilding public + assist) never destroys it. All application SQL
      resolves the extension's schema at run time, so the location is immaterial."""


def _reset_schemas() -> bool:
    """Rebuild the application schemas inside the standing gate database.

    The DATABASE persists between runs because the pgvector extension inside it can
    only be created by a superuser — recreating the database per run would demand
    superuser rights per run, which is exactly the privilege posture 55.2 forbids
    the application role to hold. Only public + assist are dropped; the extension's
    own schema survives untouched.
    """
    try:
        engine = create_engine(_gate_url(), isolation_level="AUTOCOMMIT",
                               future=True)
        with engine.connect() as c:
            has_vector = c.execute(text(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
            if not has_vector:
                print(SETUP_INSTRUCTIONS)
                return False
            assist = os.environ.get("LEGALMIND_ASSIST_SCHEMA", "assist")
            c.execute(text(f'DROP SCHEMA IF EXISTS "{assist}" CASCADE'))
            c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            c.execute(text("CREATE SCHEMA public"))
        engine.dispose()
    except Exception as exc:
        print(f"could not reach the gate database: {type(exc).__name__}: {exc}")
        print(SETUP_INSTRUCTIONS)
        return False

    from alembic.config import Config

    from alembic import command
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _gate_url())
    os.environ.setdefault("LEGALMIND_ASSIST_SCHEMA", "assist")
    command.upgrade(cfg, "head")
    return True


def _documents(questions: list[dict]) -> list[pathlib.Path]:
    source = pathlib.Path(config.source_material_dir())
    names = sorted({q["document"] for q in questions})
    documents = []
    for name in names:
        p = source / name
        if not p.exists():
            p = source / "Indian_Laws_and_Acts" / name
        if not p.exists():
            raise SystemExit(f"dataset references {name}, absent from source material")
        documents.append(p)
    return documents


def measure(db, versions: dict, all_chunks: dict, questions: list[dict]) -> dict:
    """Run every question through the production `search_hybrid` and score it."""
    expected, failures = _resolve_anchors(questions, all_chunks)
    if failures:
        raise SystemExit("anchor resolution failed:\n  " + "\n  ".join(failures))

    answerable = wrongly_answered = refused = retained = hits10 = hits1 = 0
    wrong_ids: list[str] = []
    for q in questions:
        outcome = store.search_hybrid(
            db, document_version_id=versions[q["document"]],
            query=q["question"], embed_query=embedding_runtime.embed_query)
        if q["expected"] == "NOT_FOUND":
            if outcome.gate_open:
                wrongly_answered += 1
                wrong_ids.append(q["id"])
            else:
                refused += 1
            continue
        answerable += 1
        if not outcome.gate_open:
            continue
        retained += 1
        exp = expected.get(q["id"], set())
        ranked = [h.chunk_id for h in outcome.hits]
        if any(cid in exp for cid in ranked):
            hits10 += 1
        if ranked and ranked[0] in exp:
            hits1 += 1

    unanswerable = refused + wrongly_answered
    return {
        "answerable": answerable, "unanswerable": unanswerable,
        "wrongly_answered": wrongly_answered,
        "wrongly_answered_ids": wrong_ids,
        "correct_refusals": refused,
        "retained": retained,
        "false_refusals": answerable - retained,
        # End-to-end: a gate-refused answerable question is a miss here, so this is
        # lower than the calibration's ungated hit@10 by construction — it is the
        # recall a USER experiences, which is what a release gate should hold steady.
        "recall_at_10": round(hits10 / answerable, 3) if answerable else None,
        "hit_at_1": round(hits1 / answerable, 3) if answerable else None,
    }


def _baseline_payload(metrics: dict, dataset_sha: str, n_questions: int) -> dict:
    return {
        "recorded": "2026-08-26",
        "dataset": {"path": str(DATASET), "sha256": dataset_sha,
                    "questions": n_questions},
        "pipeline": {
            "embedding_model": embedding_runtime.identity(),
            "strategy_version": calibration.RETRIEVAL_STRATEGY_VERSION,
            "cosine_floor": calibration.COSINE_FLOOR,
            "peak_margin": calibration.PEAK_MARGIN,
            "top_k": calibration.RETRIEVAL_TOP_K,
        },
        "metrics": {k: v for k, v in metrics.items()
                    if k != "wrongly_answered_ids"},
        "not_yet_measurable": {
            "faithfulness": "requires generated answers: AM-31 gate CLOSED, and "
                            "AM-31 m4 forbids a synthetic substitute",
            "citation_precision": "same blocker; joins the blocking set when "
                                  "generation measurement becomes possible",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-baseline", action="store_true",
                    help="record the current measurement as the new bar — a "
                         "deliberate act, reviewed like any diff")
    args = ap.parse_args(argv)

    if not pathlib.Path(config.source_material_dir()).exists():
        print("SKIP  no source material on this machine; the Tier-2 gate runs where "
              "the documents live (54.6 keeps them out of the repository and CI).")
        return 0
    if not embedding_runtime.available():
        print("FAIL  source material is present but the calibrated model is not "
              "provisioned. The shipped pipeline includes the model; measuring the "
              "lexical-only degradation would pass a broken provisioning. Run "
              "tools/provision_model.py first.")
        return 1

    questions = _load_eval_dataset(DATASET)
    dataset_sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()

    print(f"Tier-2 gate — {len(questions)} questions through the shipped pipeline\n")
    if not _reset_schemas():
        return 1
    engine = create_engine(_gate_url(), future=True)
    db = sessionmaker(bind=engine, future=True)()
    storage = LocalFilesystemStorage(".e2e/tier2-gate-objects")
    try:
        versions = _ingest_corpus(db, storage, _documents(questions))
        missing = sorted({q["document"] for q in questions} - set(versions))
        if missing:
            raise SystemExit(f"could not ingest: {missing}")
        all_chunks = {name: _chunks(db, dv) for name, dv in versions.items()}
        db.commit()   # search_hybrid reads chunk_embeddings written by indexing
        metrics = measure(db, versions, all_chunks, questions)
    finally:
        db.rollback(); db.close(); engine.dispose()

    print(f"\n  wrongly answered   {metrics['wrongly_answered']}"
          f"/{metrics['unanswerable']}"
          + (f"   ({', '.join(metrics['wrongly_answered_ids'])})"
             if metrics["wrongly_answered_ids"] else ""))
    print(f"  correct refusals   {metrics['correct_refusals']}"
          f"/{metrics['unanswerable']}")
    print(f"  retained           {metrics['retained']}/{metrics['answerable']}"
          f"   (false refusals {metrics['false_refusals']})")
    print(f"  recall@10          {metrics['recall_at_10']}   (end-to-end: a "
          f"gate-refused answerable counts as a miss)")
    print(f"  hit@1              {metrics['hit_at_1']}")
    print("  faithfulness       BLOCKED — needs generated answers; AM-31 gate CLOSED")
    print("  citation precision BLOCKED — same; m4 forbids a synthetic substitute\n")

    if args.write_baseline:
        BASELINE.write_text(json.dumps(
            _baseline_payload(metrics, dataset_sha, len(questions)), indent=1) + "\n")
        print(f"BASELINE WRITTEN  {BASELINE}")
        return 0

    if not BASELINE.exists():
        print(f"FAIL  no baseline at {BASELINE}. Record one deliberately with "
              "--write-baseline (and review the diff like any other).")
        return 1
    baseline = json.loads(BASELINE.read_text())

    if baseline["dataset"]["sha256"] != dataset_sha:
        print("FAIL  the dataset changed since the baseline was recorded, so the "
              "numbers are not comparable. Re-baseline deliberately with "
              "--write-baseline — a dataset change is reviewable in the same diff.")
        return 1

    base = baseline["metrics"]
    verdicts: list[str] = []
    blocking_failures = 0

    if metrics["wrongly_answered"] > base["wrongly_answered"]:
        blocking_failures += 1
        verdicts.append(
            f"BLOCK  wrongly-answered rate worsened: "
            f"{base['wrongly_answered']} -> {metrics['wrongly_answered']} "
            f"of {metrics['unanswerable']}. AM-28: does not ship.")
    else:
        verdicts.append(
            f"pass   wrongly-answered rate held: {metrics['wrongly_answered']} "
            f"<= baseline {base['wrongly_answered']}")

    for name in ("recall_at_10", "retained"):
        if base.get(name) is not None and metrics[name] < base[name]:
            verdicts.append(
                f"WARN   {name} regressed: {base[name]} -> {metrics[name]} "
                f"(reported, not blocking — AM-28's gate names faithfulness and "
                f"the wrongly-answered rate)")
        else:
            verdicts.append(f"pass   {name} held: {metrics[name]} "
                            f">= baseline {base[name]}")

    for line in verdicts:
        print(line)
    if blocking_failures:
        print(f"\nNOT SHIPPABLE — {blocking_failures} blocking regression(s).")
        return 1
    print("\nSHIPPABLE — the measurable half of the AM-28 gate holds. Faithfulness "
          "and citation precision remain unmeasured until generation is possible "
          "on real material (AM-31).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

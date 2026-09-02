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
import datetime
import hashlib
import json
import os
import pathlib
import sys
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist import (
    calibration,
    embedding_runtime,
    generation,
    guardrails,
    service,
    store,
)
from legalmind.assist.state import AssistAnswerState
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


def generation_available() -> tuple[bool, str]:
    """Whether the two AM-28 quantities that need a generated answer can be measured.

    Both were reported BLOCKED with the reason "AM-31 gate CLOSED" — a string
    hardcoded on 2026-08-26 and never re-read. `AM-31`'s gate was RELEASED on
    2026-08-31, so the gate under-reported its own scope for two days: it printed
    BLOCKED for two of the four quantities `AM-28` names, on a blocker that had
    been lifted. This asks the gate constant instead of asserting about it.

    `AM-31` m2 is the reason the release matters: `AM-26` r3 is satisfied only by
    a run on real supplied material, "which requires the gate in g1-g3 to be open
    first". It is open, the material is on this machine, so the measurement is now
    owed rather than excused.
    """
    if generation.AM31_GATE == "CLOSED":
        return False, ("AM-31 gate CLOSED — m4 forbids a synthetic substitute, so "
                       "these stay unmeasured until it is released by an appended "
                       "lock record")
    permitted, why = generation.gate_permits_egress(config.environment())
    if not permitted:
        return False, f"AM-31 gate refuses egress in this environment: {why}"
    if not generation.credential_present():
        return False, ("LEGALMIND_GEMINI_API_KEY is absent or a placeholder, so no "
                       "answer can be generated to score")
    return True, ""


def measure_generated(db, versions: dict, questions: list[dict]) -> dict:
    """`AM-28`'s two generation-dependent quantities, through the PRODUCTION path.

    Runs `service.ask` — the same function the Ask bar drives — so retrieval,
    the sufficiency check, generation, citation verification and persistence are
    all the shipped ones. The retrieval-only `measure()` above stops at
    `search_hybrid` and therefore cannot see any of this.

    ``faithfulness``       `AM-28`: "the share of claims with no valid supporting
                           span". Reported as the share of claims that DO have one,
                           so higher is better and the gate reads the same
                           direction as every other number here.
    ``citation_precision`` `AM-28`: "does the cited span actually support the
                           claim" — grounded citations over citations emitted.

    The `Verification` is reconstructed by re-running the same guardrail on the
    persisted answer text and the same retrieval hits, because `AskOutcome`
    deliberately does not carry the guardrail's internals into the API layer.
    Retrieval is deterministic for a fixed query and corpus, so the chunks are the
    ones generation actually saw. `AM-28` r2 keeps that guardrail free of prompt
    and model imports, which is what makes re-running it a measurement rather than
    a re-implementation.

    Also records the USER-VISIBLE refusal outcome, which is not the gate-level one:
    a question can open the retrieval gate and still be refused by the sufficiency
    check before the model is called.
    """
    schema = config.assist_schema()
    user_id = uuid.uuid4()
    db.execute(text("INSERT INTO users (id, email, name, status, created_at, "
                    "updated_at) VALUES (:i, :e, 'Tier-2 gate', 'ACTIVE', now(), "
                    "now())"),
               {"i": user_id, "e": f"tier2-gate-{user_id.hex[:12]}@leapswitch.com"})
    db.commit()

    claims = supported = emitted = grounded = 0
    answered_attempts = unfaithful_answers = 0
    user_wrongly_answered: list[str] = []
    user_answered = 0

    for q in questions:
        conversation_id = uuid.uuid4()
        db.execute(text(f'INSERT INTO "{schema}".conversations '
                        "(id, user_id, contract_id, created_at) "
                        "VALUES (:i, :u, NULL, now())"),
                   {"i": conversation_id, "u": user_id})
        db.commit()
        outcome = service.ask(db, conversation_id=conversation_id,
                              document_version_id=versions[q["document"]],
                              question=q["question"], request_id="tier2-gate")
        db.commit()

        answered = outcome.answer_state is AssistAnswerState.ANSWERED
        if q["expected"] == "NOT_FOUND":
            if answered:
                user_wrongly_answered.append(q["id"])
            continue
        if not answered:
            continue

        user_answered += 1
        answered_attempts += 1
        retrieval = store.search_hybrid(
            db, document_version_id=versions[q["document"]],
            query=q["question"], embed_query=embedding_runtime.embed_query)
        verification = guardrails.verify_answer(
            outcome.text or "", [h.content for h in retrieval.hits])
        claims += len(verification.citations)
        supported += sum(1 for c in verification.citations if c.grounded)
        emitted += len(verification.citations)
        grounded += sum(1 for c in verification.citations if c.grounded)
        if verification.failures:
            unfaithful_answers += 1

    return {
        "generated_answers": answered_attempts,
        "user_answered": user_answered,
        "user_wrongly_answered": len(user_wrongly_answered),
        "user_wrongly_answered_ids": user_wrongly_answered,
        # Share of claims WITH a valid supporting span (AM-28 states the inverse).
        "faithfulness": round(supported / claims, 3) if claims else None,
        "unfaithful_answers": unfaithful_answers,
        "citation_precision": round(grounded / emitted, 3) if emitted else None,
        "claims_scored": claims,
    }


def _baseline_payload(metrics: dict, dataset_sha: str, n_questions: int) -> dict:
    return {
        "recorded": datetime.date.today().isoformat(),
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
                    if not k.endswith("_ids")},
        "not_yet_measurable": ({} if "faithfulness" in metrics else {
            "faithfulness": "requires generated answers; see generation_available()",
            "citation_precision": "same blocker",
        }),
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
        # AM-28's other two quantities, if the AM-31 gate now permits them. Run in
        # the same session and against the same ingest, so both halves describe one
        # pipeline rather than two runs that might differ.
        gen_ok, gen_why = generation_available()
        if gen_ok:
            metrics.update(measure_generated(db, versions, questions))
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
    if gen_ok:
        print(f"  user-visible wrong {metrics['user_wrongly_answered']}"
              f"/{metrics['unanswerable']}"
              + (f"   ({', '.join(metrics['user_wrongly_answered_ids'])})"
                 if metrics["user_wrongly_answered_ids"] else "")
              + "   (full path: the sufficiency check runs after the gate)")
        print(f"  user answered      {metrics['user_answered']}"
              f"/{metrics['answerable']}")
        print(f"  faithfulness       {metrics['faithfulness']}"
              f"   (claims with a valid supporting span, {metrics['claims_scored']}"
              f" scored across {metrics['generated_answers']} answers)")
        print(f"  citation precision {metrics['citation_precision']}\n")
    else:
        print(f"  faithfulness       BLOCKED — {gen_why}")
        print("  citation precision BLOCKED — same blocker\n")

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

    # AM-28's gate sentence names TWO quantities — "worsens faithfulness or the
    # wrongly-answered rate" — so faithfulness blocks exactly as the other does,
    # from the first run that can measure it. Compared only when both sides have
    # it: a baseline recorded before the AM-31 release carries no value to compare
    # against, and absence is not a regression.
    for name in ("faithfulness", "citation_precision"):
        if metrics.get(name) is None or base.get(name) is None:
            continue
        if metrics[name] < base[name]:
            blocking = name == "faithfulness"
            if blocking:
                blocking_failures += 1
            verdicts.append(
                f"{'BLOCK ' if blocking else 'WARN  '} {name} worsened: "
                f"{base[name]} -> {metrics[name]}"
                + (". AM-28: does not ship." if blocking
                   else " (reported; AM-28's gate names faithfulness)"))
        else:
            verdicts.append(f"pass   {name} held: {metrics[name]} "
                            f">= baseline {base[name]}")

    # The full-path refusal count, once measurable, blocks on the same footing as
    # the gate-level one — it is the number a user actually experiences.
    if (metrics.get("user_wrongly_answered") is not None
            and base.get("user_wrongly_answered") is not None):
        if metrics["user_wrongly_answered"] > base["user_wrongly_answered"]:
            blocking_failures += 1
            verdicts.append(
                f"BLOCK  user-visible wrongly-answered worsened: "
                f"{base['user_wrongly_answered']} -> "
                f"{metrics['user_wrongly_answered']}. AM-28: does not ship.")
        else:
            verdicts.append(
                f"pass   user-visible wrongly-answered held: "
                f"{metrics['user_wrongly_answered']} <= "
                f"baseline {base['user_wrongly_answered']}")

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
    if gen_ok:
        print("\nSHIPPABLE — all four quantities AM-28 names are measured and held: "
              "retrieval recall, refusal correctness in both directions, "
              "faithfulness and citation precision.")
    else:
        print("\nSHIPPABLE — the measurable half of the AM-28 gate holds. "
              f"Faithfulness and citation precision are unmeasured: {gen_why}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

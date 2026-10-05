"""Demo-mission runner: scripted conversations through `service.ask` with agent mode on.

    python3 -m tools.ask_demo --db <SCRATCH url> --scripts <private json> \
        --out <private dir> [--only D1,D3] [--runs 2]

SCRATCH ONLY — it writes conversations; the live database is refused. The key comes from
the environment (LEGALMIND_GEMINI_API_KEY) and never from this file. The scripts and the
answers stay outside the repository; this prints ids, pass/fail, calls, tokens, latency.

Script format (JSON list): {"id": "D1", "contract": <contract name> | null, "turns":
[{"say": str, "lang": "en" | "hinglish" | "hi", "must": [[label, regex]],
"must_not": [[label, regex]], "shorter": bool}]}. A critical item fails when a must
regex finds nothing, a must-not regex matches, or the reply's language differs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import statistics
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.assist import service
from legalmind.assist.agent import agent
from legalmind.assist.llm import generation
from legalmind.assist.query import query_plan
from legalmind.assist.verification import agent_verify

PERMS = frozenset({"assist.ask", "legal_position.view", "configuration.view"})
CALLS: list[dict] = []
TURNS: list = []
#: Responses by request hash, private (mission: cache during evaluation). With
#: --cached an identical request is answered from here and never egresses, so a
#: verifier-only change is re-scored for free; any change to the context misses.
CACHE = pathlib.Path("/root/.legalmind/diagnosis/cache")
USE_CACHE = False
_real_send = generation._send
_real_run_turn = agent.run_turn


def _run_turn(*a, **kw):
    TURNS.append(_real_run_turn(*a, **kw))
    return TURNS[-1]


DROPPED: list[dict] = []
_real_settle = agent_verify.settle


def _settle(blocks, shown, found, **kw):
    """Which claims the verifier dropped, and why — the private run file only."""
    kept, n = _real_settle(blocks, shown, found, **kw)
    DROPPED.extend({"text": b["text"], "cites": b["cites"],
                    "why": [x.line() for x in found if x.block == i]}
                   for i, b in enumerate(blocks) if b not in kept)
    return kept, n


def _send(payload: dict, **kw):
    """The free tier rate-limits: back off on 429 (5 tries), record every call."""
    digest = hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()
    cached = CACHE / f"{digest}.json"
    if USE_CACHE and cached.exists():
        parsed = json.loads(cached.read_text())
        CALLS.append({"model": parsed.get("modelVersion"), "ms": 0, "in": 0, "out": 0,
                      "cached": True})
        return parsed, kw.get("model") or generation._model(), digest, 0
    for wait in (4, 8, 16, 32, 64, None):
        try:
            parsed, model, digest, ms = _real_send(payload, **kw)
        except generation.GenerationUnavailable as exc:
            if "429" not in str(exc) or wait is None:
                raise
            time.sleep(wait)
            continue
        CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
        cached.write_text(json.dumps(parsed))
        os.chmod(cached, 0o600)
        usage = parsed.get("usageMetadata") or {}
        CALLS.append({"model": parsed.get("modelVersion") or model, "ms": ms,
                      "in": usage.get("promptTokenCount") or 0,
                      "out": usage.get("candidatesTokenCount") or 0})
        return parsed, model, digest, ms
    raise AssertionError("unreachable")


def _reply_language(reply: str) -> str:
    return query_plan.language(reply.split("\n\nSources\n")[0])


def score(turn: dict, reply: str, previous: str | None) -> list[str]:
    """The critical items this reply fails, by label."""
    failed = [label for label, rx in turn.get("must", [])
              if not re.search(rx, reply, re.I | re.M)]
    failed += [label for label, rx in turn.get("must_not", [])
               if re.search(rx, reply, re.I | re.M)]
    if _reply_language(reply) != turn["lang"]:
        failed.append(f"language {_reply_language(reply)} != {turn['lang']}")
    if turn.get("shorter") and previous is not None and len(reply) >= len(previous):
        failed.append("not shorter than the previous reply")
    return failed


def run_script(db, sc: dict, run: int, pause: float) -> list[dict]:
    contract_id, version_id, owner = db.execute(text(
        "SELECT c.id, dv.id, c.owner_id FROM contracts c JOIN document_versions dv "
        "ON dv.contract_id = c.id WHERE c.name = :n ORDER BY dv.version_number DESC "
        "LIMIT 1"), {"n": sc["contract"]}).one()
    conv = service.create_conversation(db, user_id=owner, contract_id=contract_id)
    db.commit()
    rows, previous = [], None
    for n, turn in enumerate(sc["turns"], 1):
        CALLS.clear()
        TURNS.clear()
        DROPPED.clear()
        if n > 1:
            time.sleep(pause)              # a reader types; the free tier is per minute
        started = time.monotonic()
        out = service.ask(db, conversation_id=conv, document_version_id=version_id,
                          question=turn["say"], permissions=PERMS,
                          request_id=f"demo-{sc['id']}.{n}-r{run}")
        db.commit()
        ms = int((time.monotonic() - started) * 1000)
        failed = score(turn, out.text, previous)
        t = TURNS[-1] if TURNS else None
        rows.append({"script": sc["id"], "turn": n, "run": run, "reply": out.text,
                     "failed": failed, "ms": ms, "calls": list(CALLS),
                     "violations_first": t.violations_first if t else [],
                     "violations_shipped": t.violations_shipped if t else [],
                     "dropped": t.dropped if t else 0, "outcome": t.outcome if t else None,
                     "dropped_claims": list(DROPPED)})
        previous = out.text
        print(f"{sc['id']}.{n} r{run} {'PASS' if not failed else 'FAIL'} "
              f"calls={len(CALLS)} in={sum(c['in'] for c in CALLS)} "
              f"out={sum(c['out'] for c in CALLS)} ms={ms} {failed or ''}", flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--scripts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--cached", action="store_true",
                    help="answer identical requests from the private cache")
    ap.add_argument("--pause", type=float, default=20.0,
                    help="seconds between turns (not counted in latency)")
    args = ap.parse_args()
    if "demo" not in args.db.rsplit("/", 1)[-1]:
        raise SystemExit("refusing: --db must be a demo scratch database")
    os.environ["LEGALMIND_ASK_AGENT_MODE"] = "on"
    os.environ["LEGALMIND_ENVIRONMENT"] = "development"
    os.environ["LEGALMIND_ASK_ATTACHMENTS"] = "on"
    global USE_CACHE
    USE_CACHE = args.cached
    generation._send = _send
    agent.run_turn = _run_turn
    agent_verify.settle = _settle
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    only = set(filter(None, args.only.split(",")))
    scripts = [s for s in json.loads(pathlib.Path(args.scripts).read_text())
               if not only or s["id"] in only]
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    rows = [r for run in range(1, args.runs + 1) for sc in scripts
            for r in run_script(db, sc, run, args.pause)]
    db.close()
    path = out / f"demo-{time.strftime('%Y%m%dT%H%M%S')}.json"
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    os.chmod(path, 0o600)
    calls = [c for r in rows for c in r["calls"]]
    lat = sorted(r["ms"] for r in rows)
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else 0
    print(json.dumps({"turns": len(rows), "passed": sum(not r["failed"] for r in rows),
                      "calls": len(calls), "in": sum(c["in"] for c in calls),
                      "out": sum(c["out"] for c in calls),
                      "models": sorted({c["model"] for c in calls}),
                      "p50_ms": statistics.median(lat) if lat else 0, "p95_ms": p95,
                      "file": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

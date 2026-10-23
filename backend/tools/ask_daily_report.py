"""One day of Ask, read off the record — and whether a rollback trigger fired.

Enterprise-readiness plan D9 (§8 rollback triggers, §9 observability): no new
infrastructure. It reads the day's conversations (read-only database session) and the
journal's `assist.agent.turn` lines once, scores every turn with
`tools.ask_turn_trace.findings`, and prints the day's numbers. Exit code 1 when a trigger
fires, so a timer or a deploy script can alert on it. Writes nothing, calls no model.

    set -a; . /root/.legalmind.env; set +a
    python3 -m tools.ask_daily_report [--date 2026-10-22] [--floor-rate 0.10] [--json]

Triggers (provisional until the owner's numbers, ruling O2):
- any cross-brand citation (T1) or any non-current citation (T3) — zero tolerance;
- a mid-conversation fixed reply (T18) — zero tolerance;
- floor rate above --floor-rate.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text

from tools import ask_turn_trace as trace

ZERO_TOLERANCE = ("T1 BRAND_MIX", "T1 WRONG_BRAND", "T3 NOT_CURRENT",
                  "T18 FIXED_REPLY_MID_CONVERSATION")


def journal_lines(day: date, unit: str) -> list[dict]:
    """The day's `assist.agent.turn` lines, with their timestamps (read only)."""
    since = datetime.combine(day, datetime.min.time()) - timedelta(hours=1)
    until = datetime.combine(day + timedelta(days=1), datetime.min.time())
    try:
        out = subprocess.run(
            ["journalctl", "-u", unit, "-o", "cat", "--no-pager",
             "--since", since.strftime("%Y-%m-%d %H:%M:%S"),
             "--until", until.strftime("%Y-%m-%d %H:%M:%S")],
            capture_output=True, text=True, timeout=120, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    lines = []
    for raw in out.splitlines():
        if not raw.startswith("{") or '"assist.agent.turn"' not in raw:
            continue
        try:
            line = json.loads(raw)
            line["_ts"] = datetime.fromisoformat(line["ts"]).replace(tzinfo=UTC)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        lines.append(line)
    return lines


def summarise(turns: list[trace.Turn], *, floor_rate: float) -> dict:
    found = Counter(f.split(":")[0] for t in turns for f in t.findings)
    logged = [t for t in turns if t.log]
    model = [t for t in logged if t.log and t.log.get("outcome") != "prerouted"]
    lat = sorted(int((t.log or {}).get("total_ms") or 0) for t in model)
    calls = [int((t.log or {}).get("calls") or 0) for t in model]
    tokens = [int((t.log or {}).get("prompt_tokens") or 0)
              + int((t.log or {}).get("output_tokens") or 0) for t in model]
    floors = sum(1 for t in model if (t.log or {}).get("outcome") == "floor")
    asked = done = 0
    for t in model:
        m = trace._POINTS.search(trace.flags_of(t.log or {}))
        if m:
            done, asked = done + int(m[1]), asked + int(m[2])
    triggers = [f"{k}: {found[k]}" for k in ZERO_TOLERANCE if found.get(k)]
    rate = floors / len(model) if model else 0.0
    if rate > floor_rate:
        triggers.append(f"floor rate {rate:.0%} > {floor_rate:.0%}")
    return {
        "turns": len(turns), "logged": len(logged), "model_turns": len(model),
        "floors": floors, "floor_rate": round(rate, 3),
        "points_answered": f"{done}/{asked}" if asked else "—",
        "latency_ms_p50": lat[len(lat) // 2] if lat else None,
        "latency_ms_p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None,
        "calls_per_turn": round(sum(calls) / len(calls), 2) if calls else None,
        "tokens_per_turn": sum(tokens) // len(tokens) if tokens else None,
        "findings": dict(found.most_common()), "triggers": triggers}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--floor-rate", type=float, default=0.10)
    ap.add_argument("--unit", default="legalmind-api")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    url = os.environ.get("LEGALMIND_DATABASE_URL")
    if not url:
        print("LEGALMIND_DATABASE_URL is not set", file=sys.stderr)
        return 2
    day = date.fromisoformat(a.date)
    engine = create_engine(url,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    turns: list[trace.Turn] = []
    lines = journal_lines(day, a.unit)
    with engine.connect() as c:
        ids = c.execute(text(
            "SELECT DISTINCT conversation_id FROM assist.messages "
            "WHERE created_at >= :d AND created_at < :n"),
            {"d": day, "n": day + timedelta(days=1)}).scalars().all()
        for cid in ids:
            got = [t for t in trace.turns_from(c, str(cid)) if t.created_at.date() == day]
            trace.match_logs(got, [x for x in lines if x.get("conversation_id") == str(cid)])
            turns += got
    for t in turns:
        t.findings = trace.findings(t)
    report = {"date": a.date, **summarise(turns, floor_rate=a.floor_rate)}
    print(json.dumps(report, indent=1) if a.json else "\n".join(
        f"{k}: {v}" for k, v in report.items()))
    return 1 if report["triggers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

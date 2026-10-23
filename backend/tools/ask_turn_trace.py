"""Why did this Ask turn answer the way it did? — one conversation, turn by turn.

Read-only: the database session is opened read only, the journal is only read, and no
model is called (enterprise-readiness plan §7A step 3, owner method 2026-10-22: "read the
logs, investigate why it failed"). Run on the server that holds the data:

    python3 -m tools.ask_turn_trace <conversation_id> [--json] [--unit legalmind-api]

Per turn it prints the message, how the reply was produced (outcome, rung, flags, calls,
tokens, stage times from `assist.agent.turn`), every evidence key the reply cited with
its source, brand and state, and FINDINGS — the plan's failure classes that can be read
off the record mechanically: a cited published policy of another brand (T1/T2), a
superseded record cited as current (T3), points left unanswered (T8), a fixed reply in a
conversation under way (T18), a floor or a timeout (T16), blocks the verifier dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text

from legalmind.assist.knowledge import published

#: A reply is matched to the `assist.agent.turn` line logged at most this long before
#: it was stored (the line is written as the turn ends, the reply right after).
MATCH_S = 300


@dataclass
class Cited:
    key: str
    source: str
    brand: str | None
    state: str


@dataclass
class Turn:
    ordinal: int
    message: str
    reply: str
    answer_state: str | None
    model: str | None
    created_at: datetime
    cited: list[Cited] = field(default_factory=list)
    log: dict | None = None
    findings: list[str] = field(default_factory=list)


def _one(text_: str, n: int) -> str:
    return re.sub(r"\s+", " ", text_ or "")[:n]


def brand_of(source_type: str | None) -> str | None:
    """The brand of a published policy's source type; None for every other source."""
    policy = published.BY_SOURCE_TYPE.get(source_type or "")
    return policy.brand if policy else None


def match_logs(turns: list[Turn], lines: list[dict]) -> None:
    """Each turn gets the latest `assist.agent.turn` line logged before its reply and
    within MATCH_S of it; a line is used once."""
    used: set[int] = set()
    for t in turns:
        best = None
        for i, line in enumerate(lines):
            ts = line.get("_ts")
            if i in used or ts is None or not (
                    t.created_at - timedelta(seconds=MATCH_S) <= ts <= t.created_at
                    + timedelta(seconds=5)):
                continue
            if best is None or ts > lines[best]["_ts"]:
                best = i
        if best is not None:
            used.add(best)
            t.log = lines[best]


_POINTS = re.compile(r"points:(\d+)/(\d+)")


def flags_of(log: dict) -> str:
    flags = log.get("flags", "")
    return " ".join(flags) if isinstance(flags, list) else str(flags)


def findings(t: Turn) -> list[str]:
    """The failure classes this turn shows on the record (plan §7)."""
    out = []
    brands = {c.brand for c in t.cited if c.brand}
    named = published.named_brand(t.message)
    if len(brands) > 1:
        out.append(f"T1 BRAND_MIX: cites published policies of {sorted(brands)}")
    elif named and brands and brands != {named}:
        out.append(f"T1 WRONG_BRAND: message names {named}, cites {sorted(brands)}")
    elif brands and not named:
        out.append(f"T1 BRAND_UNSTATED: cites only {sorted(brands)}; the message names "
                   "no brand (check the brand the reader meant)")
    # "historical" (a Constitution record shown as history, `AM-107`) and "draft" (an
    # unsigned document's own text) are labels the reader sees, not staleness
    stale = [c.key for c in t.cited
             if c.state.lower() not in ("current", "historical", "draft")]
    if stale:
        out.append(f"T3 NOT_CURRENT: cited {stale}")
    log = t.log or {}
    flags = flags_of(log)
    if (m := _POINTS.search(flags)) and int(m[1]) < int(m[2]):
        out.append(f"T8 POINTS_PARTIAL: {m[1]} of {m[2]} points answered")
    if log.get("outcome") == "prerouted" and t.ordinal > 0:
        out.append("T18 FIXED_REPLY_MID_CONVERSATION")
    if log.get("outcome") == "floor" or "floor" in flags:
        out.append(f"T16 FLOOR: {flags}")
    if re.search(r"timeout|hard_deadline", flags, re.I):
        out.append(f"T16 TIME: {flags}")
    if str(log.get("dropped", "0")) not in ("0", ""):
        out.append(f"VERIFIER_DROPPED: blocks {log.get('dropped')}")
    if t.log is None and t.answer_state:
        out.append("NO_TURN_LOG: no assist.agent.turn line matched (legacy path, or "
                   "the journal no longer holds it)")
    return out


def read_turns(url: str, conversation_id: str) -> list[Turn]:
    engine = create_engine(url,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    with engine.connect() as c:
        return turns_from(c, conversation_id)


def turns_from(c, conversation_id: str) -> list[Turn]:
    """The conversation's turns and what each reply cited, read on ``c`` (a connection or
    session) — shared with `tools.ask_conversation_eval`, which reads its own rolled-back
    replay through it."""
    rows = c.execute(text(
        "SELECT m.id, m.ordinal, m.role, m.content, m.created_at, a.answer_state, "
        "a.model_identity, a.id FROM assist.messages m "
        "LEFT JOIN assist.ai_answers a ON a.message_id = m.id "
        "WHERE m.conversation_id = :c ORDER BY m.ordinal"),
        {"c": conversation_id}).all()
    turns: list[Turn] = []
    pending = None
    for _mid, ordinal, role, content, created, state, model, answer_id in rows:
        if role == "USER":
            pending = (ordinal, content)
            continue
        if pending is None:
            continue
        t = Turn(pending[0], pending[1], content, state and str(state), model, created)
        if answer_id is not None:
            for key, crumb, stype, status in c.execute(text(
                    "SELECT DISTINCT e.evidence_key, coalesce(e.location, e.source_ref), "
                    "s.source_type, e.status "
                    "FROM assist.answer_evidence ae "
                    "JOIN assist.conversation_evidence e ON e.id = ae.ledger_id "
                    "LEFT JOIN assist.knowledge_items i ON i.id = e.knowledge_item_id "
                    "LEFT JOIN assist.knowledge_sources s ON s.id = i.source_id "
                    "WHERE ae.answer_id = :a ORDER BY e.evidence_key"),
                    {"a": answer_id}).all():
                t.cited.append(Cited(key, crumb or "", brand_of(stype), status or ""))
        turns.append(t)
        pending = None
    return turns


def read_logs(conversation_id: str, since: datetime, unit: str) -> list[dict]:
    """The conversation's `assist.agent.turn` lines from the journal (read only)."""
    try:
        out = subprocess.run(
            ["journalctl", "-u", unit, "-o", "cat", "--no-pager",
             "--since", since.strftime("%Y-%m-%d %H:%M:%S")],
            capture_output=True, text=True, timeout=60, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    lines = []
    for raw in out.splitlines():
        if not raw.startswith("{") or conversation_id not in raw:
            continue
        try:
            line = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if line.get("event") != "assist.agent.turn":
            continue
        try:   # the log's ts is UTC without a zone; the DB's created_at carries one
            line["_ts"] = datetime.fromisoformat(line["ts"]).replace(tzinfo=UTC)
        except (KeyError, ValueError):
            line["_ts"] = None
        lines.append(line)
    return lines


def render(turns: list[Turn]) -> str:
    out = []
    for t in turns:
        log = t.log or {}
        out.append(f"── turn {t.ordinal} · {t.created_at:%Y-%m-%d %H:%M:%S} · "
                   f"{t.answer_state} · model {t.model or '—'}")
        out.append(f"   asked: {_one(t.message, 300)}")
        out.append(f"   brand: named in message={published.named_brand(t.message)} · cited="
                   f"{sorted({c.brand for c in t.cited if c.brand}) or '—'}")
        if log:
            out.append(f"   path: outcome={log.get('outcome')} rung={log.get('rung')} "
                       f"flags={log.get('flags')} calls={log.get('calls')} "
                       f"tokens in/out={log.get('prompt_tokens')}/{log.get('output_tokens')}")
            out.append(f"   stages_ms: {log.get('stages_ms')}  tools: "
                       f"{[x[0] for x in log.get('tool_ms') or []]}")
            out.append(f"   checks failed (final): {log.get('checks_final') or '—'}  "
                       f"dropped: {log.get('dropped')}")
        for c in t.cited:
            out.append(f"   cited {c.key:<4} {c.state:<10} {c.brand or '':<10} {c.source[:90]}")
        out.append(f"   reply: {_one(t.reply, 300)}")
        for f in t.findings or ["no finding on the record"]:
            out.append(f"   ▶ {f}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("conversation_id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--unit", default="legalmind-api")
    a = ap.parse_args(argv)
    url = os.environ.get("LEGALMIND_DATABASE_URL")
    if not url:
        print("LEGALMIND_DATABASE_URL is not set", file=sys.stderr)
        return 2
    turns = read_turns(url, a.conversation_id)
    if turns:
        match_logs(turns, read_logs(a.conversation_id,
                                    min(t.created_at for t in turns) - timedelta(minutes=10),
                                    a.unit))
    for t in turns:
        t.findings = findings(t)
    if a.json:
        print(json.dumps([{**asdict(t), "log": {k: v for k, v in (t.log or {}).items()
                                               if k != "_ts"}} for t in turns],
                         default=str, indent=1))
    else:
        print(render(turns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

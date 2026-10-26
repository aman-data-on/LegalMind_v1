"""Replay the multi-turn Ask cases through the live path, score them, keep nothing.

Enterprise-readiness plan P0 (`docs/architecture/ask-agent/ENTERPRISE_READINESS_PLAN.md`
§6–§8). Each case in `tests/assist_eval/ask_conversations.json` is asked, turn by turn,
through `service.ask` — the path the API takes — as a real reader (their permissions,
resolved server-side), against the real corpus. Then it is scored mechanically.

NOTHING IS KEPT. Every case runs in its own transaction that is rolled back; `commit`
raises; the pre-egress commit (`service._release_connection`) is a no-op; the answer
caches are off so every turn is a fresh answer. It DOES call the model the corpus is
configured with (Gemini by default) — so it is a measurement run, not an iteration loop
(CLAUDE.md "Gemini cost guard"): it stops at --max-calls and reports calls, tokens and
latency per turn.

    set -a; . /root/.legalmind.env; set +a
    python3 -m tools.ask_conversation_eval --user <email> [--only C01,C03] \\
        [--models gemini,deepseek,bonsai] [--repeat 3] [--max-calls 200] [--out r.json]
    python3 -m tools.ask_conversation_eval --rescore r.json     # no database, no model

Every model Ask offers is held to the same cases and scored the same way, and the
report puts them on one page (owner, 2026-10-22). One answer is not a measurement:
--repeat runs each model again, because the same 16-point email was answered 15 of 16
on one run and 1 of 16 on the next (plan G25).

Scoring (per turn, from the case's `expect` and from `tools.ask_turn_trace.findings`):
route (model|fixed), answered (a floor fails), forbid_brand (no published policy of that brand cited),
all_points (points:x/y with x == y; brand_question_ok lets a first
answer ask which brand instead), require / forbid (case-insensitive regexes on the
reply). A `require` that encodes the plan's target behaviour is expected to FAIL on code
that does not have it yet — that failure is the baseline.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from legalmind.assist import service
from legalmind.assist.llm import generation
from legalmind.observability.logs import LOGGER_NAME
from legalmind.security.resolver import effective_permissions
from tools import ask_turn_trace as trace

CASES = Path(__file__).resolve().parents[1] / "tests" / "assist_eval" / "ask_conversations.json"


class _TurnLog(logging.Handler):
    """Collects the `assist.agent.turn` fields the live path logs, by conversation."""

    def __init__(self) -> None:
        super().__init__()
        self.by_conversation: dict[str, list[dict]] = {}

    def emit(self, record: logging.LogRecord) -> None:
        fields = getattr(record, "legalmind_fields", None) or {}
        if record.getMessage() == "assist.agent.turn" and fields.get("conversation_id"):
            self.by_conversation.setdefault(fields["conversation_id"], []).append(fields)


_COVERAGE = re.compile(r"lists (\d+) points; (each|\d+) (?:is|are) answered")


def _fixed_texts() -> tuple[str, ...]:
    """Every reply the pre-router writes in fixed words — how a fixed reply is known
    when no turn log was captured."""
    from legalmind.assist.agent import agent
    from legalmind.assist.query import capability, conversational
    manifest = capability.load()
    return (capability.brief(manifest), capability.render(manifest),
            conversational.SCOPE_REPLY, *conversational.REPLY.values(),
            "I don't have that agreement in this chat yet", agent.BRAND_QUESTION)


def observed(reply: str, log: dict | None) -> dict:
    """The turn's outcome and flags: from its log line, else read off the reply itself —
    a fixed reply is one of the fixed texts, and the points line is code's own words."""
    if log:
        return log
    out: dict = {"outcome": "answered"}
    if any(reply.startswith(t[:60]) for t in _fixed_texts()):
        out["outcome"] = "prerouted"
    if m := _COVERAGE.search(reply):
        done = m[1] if m[2] == "each" else m[2]
        out["flags"] = [f"points:{done}/{m[1]}"]
    return out


#: A sentence that leaves the thing open, denies it, or reports what the reader's
#: material says is not the reply asserting it (run 2026-10-22: five false FAILs —
#: "Whether that difference is acceptable is Legal's call", "the sources do not state
#: that … is acceptable", "your email states an instruction to confirm …").
_NOT_ASSERTED = re.compile(
    r"\b(?:whether|if|unless|not|no|never|cannot|can't|don't|doesn't|isn't|aren't|"
    r"without|instruction|asks?|asked|requests?|requested|wants?|states?|says?|"
    r"claims?|proposes?|proposed)\b", re.I)


def asserted(pattern: str, reply: str) -> bool:
    """Whether some sentence of the reply asserts ``pattern`` as its own statement."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", reply or ""):
        m = re.search(pattern, sentence, re.I)
        if m and not _NOT_ASSERTED.search(sentence[:m.start()] + " " + sentence[m.end():]):
            return True
    return False


def score(turn: trace.Turn, log: dict | None, expect: dict) -> list[str]:
    """What this turn got wrong against its case's expectations (empty = pass)."""
    fails = []
    log = observed(turn.reply, log)
    outcome = log.get("outcome", "answered")
    if expect.get("route") == "model" and outcome == "prerouted":
        fails.append("ROUTE: a fixed reply where the model should answer")
    if expect.get("route") == "fixed" and outcome != "prerouted":
        fails.append(f"ROUTE: {outcome}, expected a fixed reply")
    if expect.get("answered") and outcome == "floor":
        fails.append(f"FLOOR: {trace.flags_of(log)[:80]}")
    if (brand := expect.get("forbid_brand")) and any(c.brand == brand for c in turn.cited):
        fails.append(f"BRAND: cites a published {brand} policy "
                     f"{[c.key for c in turn.cited if c.brand == brand]}")
    from legalmind.assist.agent import agent
    if expect.get("all_points") and not (expect.get("brand_question_ok") and
                                         turn.reply.startswith(agent.BRAND_QUESTION[:40])):
        m = re.search(r"points:(\d+)/(\d+)", trace.flags_of(log or {}))
        if m is None:
            fails.append("POINTS: the list was not read as points")
        elif int(m[1]) < int(m[2]):
            fails.append(f"POINTS: {m[1]} of {m[2]} answered")
    for pattern in expect.get("forbid", []):
        if asserted(pattern, turn.reply):
            fails.append(f"FORBID: /{pattern}/")
    for pattern in expect.get("require", []):
        if not re.search(pattern, turn.reply, re.I | re.M):
            fails.append(f"REQUIRE: /{pattern}/")
    return fails


def copy_attachments(db, ids: list[str], conversation) -> None:
    """The reader's own attachments of a production conversation, copied into the
    replay's conversation (rows and chunks, new ids) — inside its rolled-back
    transaction, so nothing is kept."""
    for old in ids:
        new = uuid.uuid4()
        db.execute(text(
            "INSERT INTO assist.conversation_attachments (id, conversation_id, message_id, "
            "kind, filename, mime_type, byte_size, content_sha256, storage_key, status, "
            "failure_code, created_at, ready_at, expires_at, segments) "
            "SELECT :n, :c, NULL, kind, filename, mime_type, byte_size, content_sha256, "
            "storage_key, status, failure_code, now(), ready_at, expires_at, segments "
            "FROM assist.conversation_attachments WHERE id = :o"),
            {"n": new, "c": conversation, "o": old})
        db.execute(text(
            "INSERT INTO assist.attachment_chunks (id, attachment_id, ordinal, content, "
            "location, start_offset, end_offset, annotations, chunking_algorithm_version, "
            "created_at) SELECT gen_random_uuid(), :n, ordinal, content, location, "
            "start_offset, end_offset, annotations, chunking_algorithm_version, now() "
            "FROM assist.attachment_chunks WHERE attachment_id = :o"),
            {"n": new, "o": old})


#: What no turn of a real conversation may assert (T4) — scored only where asserted.
PRODUCTION_FORBID = [r"\b(?:is|are|would be) acceptable\b",
                     r"(?:standard|common|usual) (?:commercial|industry|market) practice",
                     r"\byou (?:should|can) sign\b"]


def production_cases(db) -> list[dict]:
    """Every production conversation, in order, as a replay case: its reader, its
    document, each USER message with the attachments that came with it, the reply the
    code of its day gave. Read at run time and never written to the repository — the
    words are real clients' (54.6; owner ruling O1)."""
    from legalmind.assist.agent import points
    cases = []
    # a conversation whose contract has since been deleted cannot be replayed as it was
    for cid, user, contract in db.execute(text(
            "SELECT v.id, v.user_id, v.contract_id FROM assist.conversations v "
            "WHERE v.contract_id IS NULL OR EXISTS "
            "(SELECT 1 FROM contracts c WHERE c.id = v.contract_id) "
            "ORDER BY v.created_at")).all():
        msgs = db.execute(text(
            "SELECT id, ordinal, role, content, created_at FROM assist.messages "
            "WHERE conversation_id = :c ORDER BY ordinal"), {"c": cid}).all()
        atts = db.execute(text(
            "SELECT id, message_id, created_at FROM assist.conversation_attachments "
            "WHERE conversation_id = :c ORDER BY created_at"), {"c": cid}).all()
        users = [m for m in msgs if m.role == "USER"]
        turns, given = [], set()
        for k, m in enumerate(users):
            mine = [str(a.id) for a in atts if str(a.id) not in given and (
                a.message_id == m.id or (a.message_id is None
                                         and a.created_at <= m.created_at))]
            given |= set(mine)
            reply = next((r.content for r in msgs if r.ordinal > m.ordinal
                          and r.role == "ASSISTANT"), "")
            expect: dict = {"forbid": PRODUCTION_FORBID, "answered": True}
            if k and len(m.content.split()) >= 4:
                expect["route"] = "model"
            if len(points.enumerate_points(m.content)) >= points.MIN_POINTS:
                expect["all_points"] = True
                # the first answer may ask which brand first (`AM-201`): the reader of
                # one such list named CloudPe only two turns later
                expect["brand_question_ok"] = not k
            turns.append({"message": m.content, "attachments": mine, "expect": expect,
                          "old_reply": reply})
        cases.append({"id": f"P-{str(cid)[:8]}", "plan": ["production"],
                      "severity": "High", "user_id": user, "contract_id": contract,
                      "turns": turns})
    return cases


def _refuse_commit(*_a, **_k):
    raise RuntimeError("commit refused: the conversation eval keeps nothing")


def run(cases: list[dict], *, user_email: str | None, url: str, max_calls: int,
        model: str = "gemini") -> dict:
    # every turn a fresh answer — for this run only, never for the importing process
    # (a module-level switch turned the caches off for a whole pytest session)
    saved = {k: os.environ.get(k) for k in ("LEGALMIND_ASK_CACHE_PUBLIC",
                                            "LEGALMIND_ASK_CACHE_USER")}
    os.environ.update(dict.fromkeys(saved, "off"))
    engine = create_engine(url, future=True)
    db = Session(engine, future=True)
    db.commit = _refuse_commit                       # type: ignore[method-assign]
    service._release_connection = lambda _db: None   # type: ignore[assignment]
    generation.BEFORE_EGRESS.set(None)
    handler = _TurnLog()
    logger = logging.getLogger(LOGGER_NAME)
    level = logger.level
    logger.setLevel(logging.INFO)    # unconfigured, the logger drops INFO (run 1 lost it)
    logger.addHandler(handler)
    reader = db.execute(text("SELECT id FROM users WHERE email = :e"),
                        {"e": user_email}).scalar_one() if user_email else None
    calls_used, results = 0, []
    try:
        for case in cases:
            if calls_used >= max_calls:
                results.append({"id": case["id"], "skipped": "max-calls reached"})
                continue
            # a production replay asks as its own reader, on its own document
            user = case.get("user_id") or reader
            if user is None:
                raise ValueError(f"{case['id']}: no reader (--user, or the case's own)")
            permissions = effective_permissions(db, user)
            contract = case.get("contract_id")
            version = db.execute(text(
                "SELECT id FROM document_versions WHERE contract_id = :c "
                "ORDER BY version_number DESC LIMIT 1"), {"c": contract}).scalar() \
                if contract else None
            conversation = service.create_conversation(db, user_id=user, contract_id=contract)
            turns_out = []
            for i, step in enumerate(case["turns"]):
                copy_attachments(db, step.get("attachments", []), conversation)
                started = time.monotonic()
                before = len(handler.by_conversation.get(str(conversation), []))
                error = None
                try:
                    service.ask(db, conversation_id=conversation, document_version_id=version,
                                question=step["message"], permissions=permissions,
                                request_id=f"eval-{case['id']}-{i}-{uuid.uuid4().hex[:6]}",
                                model=model)
                except Exception as exc:  # a crash is a result, recorded, not a stop
                    error = f"{type(exc).__name__}: {exc}"[:200]
                wall_ms = int((time.monotonic() - started) * 1000)
                turns = trace.turns_from(db, str(conversation))
                turn = turns[-1] if turns else None
                logs = handler.by_conversation.get(str(conversation), [])
                # the legacy path logs no agent turn: no line for this turn then
                log = logs[-1] if len(logs) > before else None
                if turn is None:
                    turns_out.append({"turn": i, "error": error or "no reply stored",
                                      "fails": ["NO_REPLY"]})
                    continue
                turn.log = log
                calls = int((log or {}).get("calls") or 0)
                calls_used += calls
                fails = score(turn, log, step.get("expect", {}))
                if error:
                    fails.append(f"ERROR: {error}")
                turns_out.append({
                    "turn": i, "outcome": observed(turn.reply, log).get("outcome"),
                    "flags": trace.flags_of(observed(turn.reply, log)), "calls": calls,
                    "logged": log is not None,
                    "tokens": int((log or {}).get("prompt_tokens") or 0)
                    + int((log or {}).get("output_tokens") or 0),
                    "latency_ms": ((log or {}).get("stages_ms") or {}).get("total", wall_ms),
                    "cited": [(c.key, c.brand, c.state) for c in turn.cited],
                    "findings": trace.findings(turn), "fails": fails,
                    # ids, numbers and check codes only (`turn_log`), never text
                    "log": log or {}, "reply": turn.reply,
                    **({"old_reply": step["old_reply"]} if "old_reply" in step else {})})
            db.rollback()                              # nothing of the case survives
            results.append({"id": case["id"], "plan": case.get("plan"),
                            "severity": case.get("severity"), "turns": turns_out,
                            "pass": all(not t["fails"] for t in turns_out)})
    finally:
        db.rollback()
        db.close()
        logger.removeHandler(handler)
        logger.setLevel(level)
        for k, val in saved.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
    return {"model": model, "calls_used": calls_used, "results": results}


def matrix(runs: list[dict]) -> str:
    """Every model on one page (owner, 2026-10-22: "treat every LLM we use the same"):
    case × model/repeat, then each model's latency, calls and tokens."""
    heads = [f"{r['model']}#{r.get('repeat', 1)}" for r in runs]
    ids = list(dict.fromkeys(c["id"] for r in runs for c in r["results"]))
    out = ["case  " + "  ".join(f"{h:<12}" for h in heads)]
    for cid in ids:
        cells = []
        for r in runs:
            c = next((x for x in r["results"] if x["id"] == cid), None)
            cells.append("—" if c is None or "turns" not in c
                         else "PASS" if c["pass"] else "FAIL")
        out.append(f"{cid:<5} " + "  ".join(f"{x:<12}" for x in cells))
    out.append("")
    for r in runs:
        done = [c for c in r["results"] if "turns" in c]
        turns = [t for c in done for t in c["turns"] if t.get("outcome") != "prerouted"]
        lat = sorted(t["latency_ms"] for t in turns if t.get("latency_ms"))
        calls = [t.get("calls", 0) for t in turns]
        tok = [t.get("tokens", 0) for t in turns if t.get("calls")]
        out.append(
            f"{r['model']}#{r.get('repeat', 1)}: passed {sum(c['pass'] for c in done)}/"
            f"{len(done)} · latency p50 {lat[len(lat) // 2] if lat else '—'} ms, p95 "
            f"{lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else '—'} ms · calls/turn "
            f"{round(sum(calls) / len(calls), 2) if calls else '—'} · tokens/turn "
            f"{sum(tok) // len(tok) if tok else '—'} · calls total {r['calls_used']}")
    return "\n".join(out)


def summary(report: dict) -> str:
    lines = [f"model {report.get('model')} · calls used: {report['calls_used']}"]
    done = [r for r in report["results"] if "turns" in r]
    lat = sorted(t["latency_ms"] for r in done for t in r["turns"]
                 if t.get("latency_ms") and t.get("outcome") != "prerouted")
    if lat:
        lines.append(f"latency ms p50 {lat[len(lat) // 2]} · p95 "
                     f"{lat[min(len(lat) - 1, int(0.95 * len(lat)))]} · max {lat[-1]}")
    tok = [t.get("tokens", 0) for r in done for t in r["turns"] if t.get("calls")]
    if tok:
        lines.append(f"tokens/turn mean {sum(tok) // len(tok)} · max {max(tok)}")
    lines.append(f"cases passed: {sum(r['pass'] for r in done)} of {len(done)}")
    for r in report["results"]:
        if "skipped" in r:
            lines.append(f"{r['id']}  SKIPPED ({r['skipped']})")
            continue
        lines.append(f"{r['id']}  {'PASS' if r['pass'] else 'FAIL'}  {r['severity']}  "
                     f"{','.join(r.get('plan') or [])}")
        for t in r["turns"]:
            for f in t["fails"]:
                lines.append(f"      turn {t['turn']}: {f}")
    return "\n".join(lines)


def rescore(report: dict, cases: list[dict]) -> dict:
    """Score a saved report again — no database, no model — after a scoring change."""
    by_id = {c["id"]: c for c in cases}
    for r in report["results"]:
        if "turns" not in r:
            continue
        for t in r["turns"]:
            if "reply" not in t:
                continue
            turn = trace.Turn(t["turn"], "", t["reply"], None, None, None)  # type: ignore[arg-type]
            turn.cited = [trace.Cited(k, "", b, s) for k, b, s in t["cited"]]
            log = t.get("log") or None          # the run's own record wins over a guess
            t["fails"] = score(turn, log, by_id[r["id"]]["turns"][t["turn"]].get("expect", {}))
            t["outcome"] = observed(t["reply"], log).get("outcome")
        r["pass"] = all(not t["fails"] for t in r["turns"])
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--rescore", default="", help="score a saved report again, no model")
    ap.add_argument("--user", default="", help="the reader whose permissions to use")
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--max-calls", type=int, default=200, help="per model and repeat")
    ap.add_argument("--models", default="gemini",
                    help="comma-separated: every model Ask offers is held to the same cases")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per model — one answer is not a measurement (G25)")
    ap.add_argument("--out", default="")
    ap.add_argument("--production", action="store_true",
                    help="replay every production conversation as its own reader")
    a = ap.parse_args(argv)
    cases = json.loads(CASES.read_text())["cases"]
    url = os.environ.get("LEGALMIND_DATABASE_URL")
    if a.production and url:
        with Session(create_engine(url, future=True)) as read:
            cases = production_cases(read)
    if a.rescore:
        saved = json.loads(Path(a.rescore).read_text())
        runs = [rescore(r, cases) for r in saved.get("runs", [saved])]
        Path(a.rescore).write_text(json.dumps({"runs": runs}, indent=1, default=str))
        print("\n\n".join(summary(r) for r in runs) + "\n\n" + matrix(runs))
        return 0
    if not a.user and not a.production:
        ap.error("--user is required for a run")
    if not url:
        print("LEGALMIND_DATABASE_URL is not set", file=sys.stderr)
        return 2
    if a.only:
        wanted = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    runs = []
    for model in [m.strip() for m in a.models.split(",") if m.strip()]:
        for n in range(1, a.repeat + 1):
            report = run(cases, user_email=a.user, url=url, max_calls=a.max_calls,
                         model=model)
            report["repeat"] = n
            runs.append(report)
            if a.out:            # written after every run: a long run is never all lost
                Path(a.out).write_text(json.dumps({"runs": runs}, indent=1, default=str))
    print("\n\n".join(summary(r) for r in runs) + "\n\n" + matrix(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

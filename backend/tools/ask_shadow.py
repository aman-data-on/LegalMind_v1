"""Phase 3 shadow runner: the agent beside the current pipeline, on real documents.

    python3 -m tools.ask_shadow --db <SCRATCH url> --scripts <private json> \
        --out /root/.legalmind/review/phase3 [--only G1,G4] [--cap 450]

Each script turn is asked twice, in two conversations holding the same document and
the same material: through `service.ask` (the shipped pipeline) and through
`agent.run_turn` (the shadow agent). SCRATCH ONLY — it writes conversations, messages,
attachments and ledger rows; the live database is refused.

The scripts reference private corpus documents, so they live OUTSIDE the repository
(D11), and so does everything this writes: `<out>/turns.json` (metrics and the texts,
for the owner's review) and `<out>/review.md` (20 turns). What may be committed is the
summary this prints: ids, counts, tokens and latencies — no document or answer text.

Script format (JSON list): {"id": "G1", "contract": <corpus file id or null>,
"user": "owner" | "stranger", "provider": "gemini" | "down", "turns": [{"say": str,
"paste": [{"file": id, "chars": n}], "upload_txt": {"file": id}, "inject": str}]}.
"""
from __future__ import annotations

import argparse
import email
import json
import os
import pathlib
import re
import statistics
import sys
import time
import uuid
from email import policy

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind.api.routers.assist import extract_material
from legalmind.assist import (
    agent,
    agent_verify,
    attachments,
    generation,
    guardrails,
    service,
    tools,
)
from legalmind.db import models as M
from legalmind.domain import enums as E

CORPUS = pathlib.Path("/root/.legalmind/test-corpus/raw")
PERMS = frozenset({"assist.ask", "legal_position.view", "configuration.view"})


class _CapReached(Exception):
    pass


class _Down:
    """G9: the provider is unreachable — every call fails, nothing egresses."""

    def turn(self, *a, **k):
        raise generation.GenerationUnavailable("simulated outage")


def _doc_text(db, file_id: str) -> str:
    path = next(CORPUS.glob(f"{file_id}.*"))
    if path.suffix == ".eml":
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        body = msg.get_body(preferencelist=("plain", "html"))
        return f"Subject: {msg['subject']}\n\n{body.get_content() if body else ''}"
    rows = db.execute(text(
        "SELECT e.content FROM document_evidence e JOIN document_versions v "
        "ON v.id = e.document_version_id WHERE v.original_filename LIKE :f "
        "ORDER BY e.start_offset NULLS LAST, e.id"), {"f": f"{file_id}.%"}).scalars().all()
    return "\n\n".join(rows)


def _version(db, file_id: str):
    return db.execute(text(
        "SELECT v.id, v.contract_id FROM document_versions v "
        "WHERE v.original_filename LIKE :f ORDER BY v.version_number DESC LIMIT 1"),
        {"f": f"{file_id}.%"}).first()


def _attach(db, conv, turn) -> None:
    for p in turn.get("paste") or []:
        body = _doc_text(db, p["file"])[: p.get("chars", 4000)]
        if turn.get("inject"):
            body += "\n\n" + turn["inject"]
        mime, ex = extract_material(body.encode(), attachments.PASTE, None, "text/plain")
        attachments.add(db, conversation_id=conv, data=body.encode(),
                        kind=attachments.PASTE, mime=mime, extracted=ex)
    if turn.get("upload_txt"):
        raw = _doc_text(db, turn["upload_txt"]["file"]).encode()
        mime, ex = extract_material(raw, attachments.FILE, "note.txt", "text/plain")
        attachments.add(db, conversation_id=conv, data=raw, kind=attachments.FILE,
                        mime=mime, extracted=ex, filename="note.txt")


def _support(text_: str, sources: list[str]) -> tuple[int, int]:
    """(supported, total) sentences: a sentence is supported when it shares at least half
    its content words with one cited source — the guardrail's own lexical floor."""
    sents = [s for s in guardrails._SENTENCES.split(text_ or "") if s.strip()]
    srcs = [guardrails._content_words(x) for x in sources]
    ok = 0
    for s in sents:
        words = guardrails._content_words(s)
        ok += bool(words) and any(len(words & src) >= 0.5 * len(words) for src in srcs)
    return ok, len(sents)


def run(db, scripts: list[dict], cap: int) -> list[dict]:
    rows = []
    real = generation.generate_raw, generation.generate_turn
    spent = {"n": 0}

    def capped(fn):
        # Counts every call at the one seam, with its tokens: `service.ask` sets its own
        # usage context, so per-side figures come from these totals' deltas.
        def wrapped(*a, **k):
            if spent["n"] >= cap:
                raise _CapReached()
            spent["n"] += 1
            r = fn(*a, **k)
            spent["prompt"] = spent.get("prompt", 0) + (r.prompt_tokens or 0)
            spent["output"] = spent.get("output", 0) + (r.output_tokens or 0)
            return r
        return wrapped
    generation.generate_raw, generation.generate_turn = (capped(real[0]),
                                                         capped(real[1]))
    os.environ["LEGALMIND_ASK_ATTACHMENTS"] = "on"
    try:
        for sc in scripts:
            contract_version = _version(db, sc["contract"]) if sc.get("contract") else None
            owner_id = (db.get(M.Contract, contract_version.contract_id).owner_id
                        if contract_version else None)
            if owner_id is None or sc.get("user") == "stranger":
                u = M.User(email=f"shadow-{uuid.uuid4().hex[:8]}@example.test",
                           name="shadow", status=E.UserStatus.ACTIVE)
                db.add(u)
                db.flush()
                user_id = u.id
            else:
                user_id = owner_id
            # A stranger (G10) asks with no document in scope: the document is not theirs.
            scope = (contract_version.contract_id
                     if contract_version is not None and user_id == owner_id else None)
            version_id = (contract_version.id if contract_version is not None
                          and scope is not None else None)
            cur = service.create_conversation(db, user_id=user_id, contract_id=scope)
            ag = service.create_conversation(db, user_id=user_id, contract_id=scope)
            provider = _Down() if sc.get("provider") == "down" else agent.GeminiProvider()
            for n, turn in enumerate(sc["turns"], 1):
                _attach(db, cur, turn)
                _attach(db, ag, turn)
                question = turn["say"]
                before = (spent["n"], spent.get("prompt", 0), spent.get("output", 0))
                t0 = time.monotonic()
                out = service.ask(db, conversation_id=cur, document_version_id=version_id,
                                  question=question, permissions=PERMS)
                cur_ms = int((time.monotonic() - t0) * 1000)
                usage = {"calls": spent["n"] - before[0],
                         "prompt_tokens": spent.get("prompt", 0) - before[1],
                         "output_tokens": spent.get("output", 0) - before[2]}
                service._append_turn(db, ag, "USER", question)
                ctx = tools.ToolContext.open(db, user_id=user_id, permissions=PERMS,
                                             conversation_id=ag)
                t = agent.run_turn(provider, ctx, question, request_id=f"shadow-{sc['id']}")
                reply = service._append_turn(db, ag, "ASSISTANT", t.text())
                answer = service._persist_answer(
                    db, reply, None, service.AssistAnswerState.ANSWERED, model=None,
                    prompt_version_id=None, latency_ms=t.stages_ms.get("total"))
                if t.registry is not None:
                    t.registry.persist(reply, answer, t.cited)
                agent.ConversationManager(db, ag).after_reply()
                agent._audit(db, t, ag, f"shadow-{sc['id']}")
                db.commit()
                cited_text = [t.registry.shown[k].record.text for k in t.cited
                              if t.registry and k in t.registry.shown]
                sourced = " ".join(b["text"] for b in t.blocks if b["kind"] == "sourced")
                cur_cited = [c.text for c in out.citations] + [
                    p.get("text", "") for p in (out.positions or [])]
                rows.append({
                    "script": sc["id"], "turn": n, "question": question,
                    "checks": turn.get("checks", []), "doc_selected": scope is not None,
                    "agent": {"text": t.text(), "outcome": t.outcome,
                              "blocks": t.blocks, "rung": t.rung, "dropped": t.dropped,
                              "violations_first": t.violations_first,
                              "violations_final": t.violations_final,
                              "shown_refs": ({k: v.record.source_ref
                                              for k, v in t.registry.shown.items()}
                                             if t.registry else {}),
                              "weak": t.weak,
                              "scopes": ({k: v.scope for k, v in t.registry.shown.items()}
                                         if t.registry else {}),
                              "kinds": [b["kind"] for b in t.blocks],
                              "assessment": t.assessment,
                              "calls": [vars(c) for c in t.calls],
                              "tool_execs": len(t.tool_execs),
                              "tools": [x[0] for x in t.tool_execs],
                              "searches": t.searches,
                              "cited": t.cited, "weak_cited": t.weak_cited,
                              "invalid_cites": t.invalid_cites,
                              "locations": {k: t.registry.shown[k].record.location
                                            for k in t.cited
                                            if t.registry and k in t.registry.shown},
                              "stages_ms": t.stages_ms, "flags": t.flags,
                              "support": _support(sourced, cited_text)},
                    "current": {"text": out.text, "state": out.answer_state.value,
                                "doc_chunks": [str(c.chunk_id) for c in out.citations],
                                "position_codes": [p_["standard_code"] for p_ in
                                                   (out.positions or [])],
                                "citations": len(out.citations)
                                + len(out.positions or []),
                                "calls": usage.get("calls", 0),
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "ms": cur_ms,
                                "support": _support(out.text, cur_cited)}})
                print(f"{sc['id']}.{n} agent {t.outcome} calls={len(t.calls)} "
                      f"tools={len(t.tool_execs)} {t.stages_ms.get('total')}ms | current "
                      f"{out.answer_state.value} calls={usage.get('calls', 0)} "
                      f"{cur_ms}ms | spent={spent['n']}", flush=True)
    except _CapReached:
        print(f"CALL CAP {cap} reached — remaining turns not run", flush=True)
    finally:
        generation.generate_raw, generation.generate_turn = real
    return rows


def summary(rows: list[dict]) -> dict:
    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))] if xs else None
    a = [r["agent"] for r in rows]
    c = [r["current"] for r in rows]
    calls = [len(x["calls"]) for x in a]
    per_call = [x for t in a for x in t["calls"]]
    dead = sum(not ({"sourced", "user_stated", "reasoning", "general", "draft", "clarify",
                     "prerouted"}
                    & set(x["kinds"])) for x in a)
    stages: dict[str, list[int]] = {}
    for x in a:
        for k, v in x["stages_ms"].items():
            stages.setdefault(k.split("_")[0], []).append(v)
    sup = lambda xs: (sum(x["support"][0] for x in xs),       # noqa: E731
                      sum(x["support"][1] for x in xs))
    return {
        "turns": len(rows),
        "agent": {"calls_mean": round(statistics.mean(calls), 2) if calls else None,
                  "calls_max": max(calls, default=0),
                  "tool_execs_max": max((x["tool_execs"] for x in a), default=0),
                  "over_budget_turns": sum(n > agent.MAX_CALLS for n in calls),
                  "outcomes": dict(__import__("collections").Counter(
                      x["outcome"] for x in a)),
                  "dead_ends": dead,
                  "cited": sum(len(x["cited"]) for x in a),
                  "weak_cited": sum(len(x["weak_cited"]) for x in a),
                  "invalid_cites": sum(len(x["invalid_cites"]) for x in a),
                  "claim_support_sentences": sup(a),
                  "p50_ms": pct([x["stages_ms"].get("total", 0) for x in a], .5),
                  "p95_ms": pct([x["stages_ms"].get("total", 0) for x in a], .95),
                  "stage_p50_p95_ms": {k: (pct(v, .5), pct(v, .95))
                                       for k, v in sorted(stages.items())},
                  "prompt_tokens_per_call_p50_p95": (
                      pct([x["prompt_tokens"] or 0 for x in per_call], .5),
                      pct([x["prompt_tokens"] or 0 for x in per_call], .95)),
                  "output_tokens_per_call_p50_p95": (
                      pct([x["output_tokens"] or 0 for x in per_call], .5),
                      pct([x["output_tokens"] or 0 for x in per_call], .95)),
                  "prompt_tokens": sum(x["prompt_tokens"] or 0 for x in per_call),
                  "output_tokens": sum(x["output_tokens"] or 0 for x in per_call)},
        "current": {"calls": sum(x["calls"] for x in c),
                    "refusals": sum(x["state"] != "ANSWERED" for x in c),
                    "citations": sum(x["citations"] for x in c),
                    "claim_support_sentences": sup(c),
                    "p50_ms": pct([x["ms"] for x in c], .5),
                    "p95_ms": pct([x["ms"] for x in c], .95),
                    "prompt_tokens": sum(x["prompt_tokens"] for x in c),
                    "output_tokens": sum(x["output_tokens"] for x in c)},
        "agent_citations": sum(len(x["cited"]) for x in a)}


_BLAME = ("try naming", "you must", "you need to", "please provide", "rephrase")


_WHOLE_EXCLUDED = re.compile(
    r"no (?:service )?credits? (?:would|will|is|shall) (?:be )?(?:due|payable|owed)|"
    r"not (?:be )?entitled to (?:any )?(?:service )?credits?|"
    r"(?:entire|whole) (?:outage|downtime) (?:is |would be )?excluded|"
    r"fully excluded from (?:credit|the availability)", re.I)


def regression(rows: list[dict]) -> list[dict]:
    """The owner's Phase 3 review P1–P11 as per-turn checks (Phase 4). Each is a rule
    about the turn's own evidence or the current pipeline's answer to the same turn —
    never a stored expected answer. P4 runs on every turn; the others where the
    scripts name them. A Phase 3 row lacks some fields; those checks read `n/a`."""
    def kinds(a):
        return [b["kind"] for b in a.get("blocks") or []] or a.get("kinds", [])

    def blocks(a):
        return a.get("blocks") or []

    def final(a, check) -> bool | None:
        """No `check` left after repair — None for a row with no verifier record.
        Lines read "block N: CHECK — detail" (`agent_verify.Violation.line`)."""
        v = a.get("violations_final")
        if v is None:
            return None
        return check not in {x.split(": ", 1)[1].split(" —", 1)[0] for x in v}
    out = []
    for r in rows:
        a, c = r["agent"], r["current"]
        res: dict[str, str] = {}
        for check in sorted(set(r.get("checks", [])) | {"P4"}):
            ok: bool | None
            if check == "P1":
                cited_d = [k for k in a["cited"] if k.startswith("D")]
                first = next((b for b in blocks(a) if b["kind"] == "sourced"), None)
                if not r.get("doc_selected", True):
                    ok = None
                elif blocks(a):
                    # The document first: its cited claim leads, or — when it does not
                    # address the question — the answer opens by saying so plainly.
                    lead = next((b for b in blocks(a) if b["kind"] in
                                 agent_verify.ANSWERING), None)
                    ok = (first is not None and bool(cited_d) and any(
                        k.startswith("D") for k in first["cites"])) or (
                        lead is not None and lead["kind"] != "sourced" and any(
                            agent_verify.about_document(x) == "absent"
                            for x in guardrails._SENTENCES.split(lead["text"])))
                else:
                    ok = bool(cited_d)
            elif check == "SWITCH":
                # owner 3.2 (C5.2): after the user names another document, the answer
                # cites that document — not the selected one's terms in its place
                scopes = a.get("scopes") or {}
                ok = None if not blocks(a) else any(
                    (scopes.get(k) or "").startswith("another document")
                    for k in a["cited"])
            elif check == "PARTIAL":
                # owner 3.2 (C5.4): an exclusion that covers part of an outage never
                # becomes the whole outage excluded
                ok = None if not blocks(a) else not _WHOLE_EXCLUDED.search(a["text"])
            elif check == "F12":
                # plan 1.15: an unsigned document is never labelled executed — no F12
                # left after repair, and no shown sentence (other than the reader's
                # attributed claim) calls it signed or executed
                ok = None if not blocks(a) else (final(a, "F12") is not False and not any(
                    agent_verify.calls_executed(b["text"]) for b in blocks(a)
                    if b["kind"] != "user_stated"))
            elif check in ("P2", "P9", "P10"):
                ok = final(a, {"P9": "V7"}.get(check, check))
            elif check == "P3":
                ok = all((b["kind"] == "sourced" and bool(b["cites"]))
                         or b["kind"] == "user_stated"
                         or (b["kind"] == "reasoning" and bool(final(a, "V7")))
                         for b in blocks(a)
                         # an assertion — a next step or a question asserts nothing
                         if b["kind"] in agent_verify.ANSWERING
                         and "data" in b["text"].lower() and ("loss" in b["text"].lower()
                                                             or "breach" in
                                                             b["text"].lower())
                         ) if blocks(a) else None
            elif check == "P4":
                per_block = [b["cites"] for b in blocks(a) if b.get("cites")]
                locs = a.get("locations", {})
                named = set(re.findall(r"\b[CPSHDU]\d{1,3}\b", a["text"]))
                ok = (not a.get("invalid_cites") and named <= set(a["cited"])
                      and all(len(x) == len(set(x)) and len(x) <= 2 for x in per_block)
                      and all(locs.get(k) for k in a["cited"] if k[0] in "CPDH")
                      ) if blocks(a) else (not a.get("invalid_cites")
                                           and len(a["cited"]) == len(set(a["cited"])))
            elif check == "P5":
                weak = set(a.get("weak_cited", []))
                if not agent._claim_made(r["question"]):
                    ok = a["assessment"] == "n/a"          # nothing asserted to assess
                else:
                    ok = a["assessment"] not in ("supported", "contradicted") or bool(
                        set(a["cited"]) - weak)
            elif check == "P6":
                shown = set((a.get("shown_refs") or {}).values())
                need = {f"POS:{code}" for code in c.get("position_codes", [])}
                ok = (need <= shown) if a.get("shown_refs") is not None else None
            elif check == "P7":
                ok = "Question:" not in a["text"] and kinds(a).count("clarify") <= 1 \
                    and not ("clarify" in kinds(a) and "sourced" in kinds(a)
                             and a["assessment"] != "undeterminable")
            elif check == "P8":
                ok = len(a["calls"]) == 0
            elif check == "P11":
                ok = (a["outcome"] in ("floor", "fallback") and not any(
                    w in a["text"].lower() for w in _BLAME) and bool(a["cited"]))
            else:
                ok = None
            res[check] = "n/a" if ok is None else ("pass" if ok else "FAIL")
        out.append({"turn": f"{r['script']}.{r['turn']}", **res})
    return out


def doc_turns(rows: list[dict], judged: dict | None = None) -> list[str]:
    """Phase 4 exit criterion: every turn with a selected document, the agent beside the
    current pipeline on the owner's four points. Mechanical evidence for points 1, 3 and
    4; point 2 (correct clause and figures) and every final mark come from the reviewer's
    `judged` file — PROVISIONAL, the owner decides."""
    judged = judged or {}
    hard = ("V1", "V4", "V5", "P2", "B5", "P10")
    lines = ["| Turn | Point | Agent (evidence) | Current (evidence) | Provisional judgment |",
             "|---|---|---|---|---|"]
    for r in rows:
        if not r.get("doc_selected"):
            continue
        a, c = r["agent"], r["current"]
        turn = f"{r['script']}.{r['turn']}"
        first = next((b for b in a.get("blocks", []) if b["kind"] == "sourced"), None)
        left = {x.split(": ", 1)[1].split(" —", 1)[0] for x in a.get("violations_final",
                                                                     [])}
        ev = {
            "1 primary source": (
                f"first claim cites {first['cites'] if first else '—'}; "
                f"D cited {[k for k in a['cited'] if k.startswith('D')] or '—'}",
                f"{len(c['doc_chunks'])} document citation(s)"),
            "2 clause and figures": (f"cited locations {a.get('locations') or '—'}",
                                     "see answer text"),
            "3 no unsupported authority": (
                f"left after repair: {sorted(left & set(hard)) or 'none'}; "
                f"dropped {a.get('dropped', 0)}", "shipped verifier passed"
                if c["state"] == "ANSWERED" else c["state"]),
            "4 no dead end": (f"{a['outcome']}, rung {a.get('rung')}", c["state"]),
        }
        for point, (agent_ev, cur_ev) in ev.items():
            mark = judged.get(turn, {}).get(point.split()[0], "to judge")
            lines.append(f"| {turn} | {point} | {agent_ev} | {cur_ev} | {mark} |")
    return lines


def write_review(rows: list[dict], out: pathlib.Path, n: int = 20) -> pathlib.Path:
    """The owner's review sample (brief C2): n turns, every script represented, each with
    the question, both answers, the evidence keys and clause locations cited, calls and
    latency. Written OUTSIDE the repository, mode 600 — it carries client text."""
    picked, seen = [], set()
    for r in rows:                        # one turn per script first, then the rest
        if r["script"] not in seen:
            picked.append(r)
            seen.add(r["script"])
    picked += [r for r in rows if r not in picked][: max(0, n - len(picked))]
    picked = sorted(picked[:n], key=rows.index)
    lines = ["# Ask agent — shadow review sample", "",
             "Each turn: the question, the SHADOW agent's answer (never shown to users), "
             "the CURRENT pipeline's answer, evidence keys and clause locations cited, "
             "model calls and latency.", ""]
    for r in picked:
        a, c = r["agent"], r["current"]
        lines += [f"## {r['script']} · turn {r['turn']}", "", f"**Question:** {r['question']}",
                  "", f"**Shadow agent** — {a['outcome']}, {len(a['calls'])} calls, "
                  f"{a['tool_execs']} tool executions, {a['stages_ms'].get('total')} ms, "
                  f"assessment `{a['assessment']}`",
                  f"cited {a['cited'] or '—'} · weak cited {a['weak_cited'] or '—'} · "
                  f"locations {a['locations'] or '—'}", "", a["text"] or "(empty)", "",
                  f"**Current pipeline** — {c['state']}, {c['calls']} calls, {c['ms']} ms, "
                  f"{c['citations']} citations", "", c["text"] or "(empty)", "", "---", ""]
    judged_path = out / "judgments.json"
    judged = json.loads(judged_path.read_text()) if judged_path.exists() else None
    lines = [*lines[:4], "## Selected-document turns — agent vs current (provisional)", "", *doc_turns(rows, judged), "", "---", "", *lines[4:]]
    path = out / "review.md"
    path.write_text("\n".join(lines))
    os.chmod(path, 0o600)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--scripts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--cap", type=int, default=450)
    ap.add_argument("--review-from", default="",
                    help="write review.md from an existing turns-*.json (no calls)")
    ap.add_argument("--regression-from", default="",
                    help="score P1-P11 on an existing turns-*.json (no calls)")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    if args.regression_from:
        rows = json.loads(pathlib.Path(args.regression_from).read_text())
        named = {(sc["id"], n): t.get("checks", [])
                 for sc in json.loads(pathlib.Path(args.scripts).read_text())
                 for n, t in enumerate(sc["turns"], 1)}
        for r in rows:                     # scored by the scripts' current checks
            r["checks"] = named.get((r["script"], r["turn"]), r.get("checks", []))
        for row in regression(rows):
            print(json.dumps(row))
        return 0
    if args.review_from:
        print(write_review(json.loads(pathlib.Path(args.review_from).read_text()), out))
        return 0
    if args.db.rsplit("/", 1)[-1] in {"legalmind_v1_dev", "legalmind"}:
        raise SystemExit("refusing the live database: this tool writes")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(out, 0o700)
    scripts = json.loads(pathlib.Path(args.scripts).read_text())
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    scripts = [s for s in scripts if not only or s["id"] in only]
    db = sessionmaker(bind=create_engine(args.db, future=True), future=True)()
    rows = run(db, scripts, args.cap)
    db.close()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for name, payload in ((f"turns-{stamp}.json", rows),
                          (f"summary-{stamp}.json", summary(rows))):
        p = out / name
        p.write_text(json.dumps(payload, indent=1, default=str))
        os.chmod(p, 0o600)
    write_review(rows, out)
    print(json.dumps(summary(rows), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

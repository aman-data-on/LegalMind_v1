"""Roadmap PHASE 10 — conversational generation over the evidence bundle, measured.

    python3 -m tools.eval_generation --db <scratch url> [--live] [--json out.json]

OFFLINE (default, zero Gemini): a stub model answers each bundle by restating every
excerpt's first sentence with its marker, plus the [A]/[M] lines — it exercises the
payload, the egress screen, the part states and every mechanical check, and measures
prompt size. --live makes ONE real call per answerable case through the single egress
seam (the Gemini cost guard: one controlled run, after offline passes).

Scored deterministically against labels that already exist (the PHASE 0 benchmark's
gold, `must_not`, `answer.distinguish`, `must_not_state_as_policy`, `refuse`):
  relevance      an answerable case is answered, and cites a gold source
  completeness   every kind the case must distinguish is cited; every answerable part
                 has one of its supporting excerpts cited
  faithfulness   share of sentences passing the checks (marker, figure in cited text)
  unsupported    sentences with no marker, or a figure their citation does not carry
  contradictions a must-not-state-as-policy figure said of the position, un-negated
  citations      precision of cited excerpts against gold; invalid markers
  cost           calls, prompt/output tokens, latency p50/p95; USD only when
                 LEGALMIND_GEMINI_USD_PER_M_IN/_OUT are set (no price is guessed)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legalmind.assist import answer, generation, guardrails
from legalmind.assist import query_plan as qp
from tools import rag_benchmark as rb

_FIRST = re.compile(r"^(.{20,300}?[.;:])(?:\s|$)", re.S)


_CONTRACT = re.compile(r"^\[(\d+)\] (.*?SAY AS: ([^·]+?) ·.*?)\n\s+TEXT: (.+)$", re.M)


def stub(question, block, *, environment, prior_questions=(), request_id=None):
    """A deterministic 'model': each excerpt's first sentence, cited — or, for a PHASE 12
    contract block, each contract verbatim under its SAY AS — then [A] and [M]."""
    out = []
    if block.startswith("APPROVED CLAIMS"):
        out = []
        for n, head, say, text in _CONTRACT.findall(block):
            frame = re.search(r"FRAME: (.+?) \(say so", head)
            scope = re.search(r"SCOPE: (.+?) agreements only", head)
            only = re.search(r"APPLIES ONLY TO: (.+?) \(say so\)", head)
            this = re.search(r"'THIS' REFERS TO: (.+?) \(name it\)", head)
            exc = re.search(r"SUBJECT TO THESE EXCEPTIONS: (.+?) \(say so\)", head, re.S)
            when = re.search(r"IN FORCE: (.+?) \(say so\)|(REPEALED) —", head)
            lead = " ".join(x for x in (
                f"For {scope.group(1)} agreements," if scope else "",
                f"for {only.group(1)}," if only else "", say.strip(),
                f"({frame.group(1).lower()})" if frame else "",
                f"(on {this.group(1)})" if this else "") if x)
            body = re.sub(r"(?<=[.!?])\s+", "; ", text.rstrip("."))  # one sentence
            if exc:
                body += "; subject to these exceptions: " + re.sub(
                    r"(?<=[.!?])\s+", "; ", exc.group(1).rstrip("."))
            if when:
                body += (f" (in force: {when.group(1).rstrip('.')})" if when.group(1)
                         else " (repealed — historical, not current law)")
            means = re.findall(r"'([^']+)' MEANS: (.+?) \(say so\)", head)
            if means:
                body += " (" + "; ".join(f"{a.lower()} being {m}" for a, m in means) + ")"
            out.append(f"{lead} states: {body} [{n}].")
        block = ""
    for m in re.finditer(r"^\[(\d+)\] [^\n]*\n(.+?)(?=\n\n\[\d+\] |\n\n\[A\]|\n\n\[M\]|"
                         r"\n\nPARTS|\Z)", block, re.S | re.M):
        # Skip the excerpt's header line ("Legal Constitution L1.10 · 13 …", "The … Act,
        # 2017 · Section 50 · …") — a heading is not a sentence any answer would write.
        lines = [x for x in m.group(2).split("\n") if x.strip()]
        if len(lines) > 1 and " · " in lines[0]:
            lines = lines[1:]
        body = " ".join(" ".join(lines).split()[:40])
        first = _FIRST.match(body)
        out.append(f"{(first.group(1) if first else body).rstrip('.;:')} [{m.group(1)}].")
    if "[A] " in block:
        out.append("That figure is what the reader was told, not a verified term [A].")
    if "[M] " in block:
        out.append("The signed agreement is not available, so its terms cannot be "
                   "confirmed [M].")
    prompt = generation.BUNDLE_PROMPT_TEMPLATE.format(bundle=block, question=question,
                                                      context="")
    return generation.GenerationResult(" ".join(out), "stub", "offline", "", 0,
                                       len(prompt) // 4, sum(len(x) for x in out) // 4)


def stub_repair(question, block, draft, failures, *, environment, prior_questions=(),
                request_id=None):
    """Offline repair: the stub's own answer again — never the network."""
    return stub(question, block, environment=environment)


def _sentences(text):
    return [s.strip() for s in guardrails._SENTENCES.split(text or "") if s.strip()]


def score(case, plan, bundle, ans) -> dict:
    gold = [r for slot in case["gold"] for r in slot]
    cited_n = {int(n) for n in re.findall(r"\[(\d{1,2})\]", ans.text)} if ans.generated \
        else set()
    cited = [ans.refs[n - 1] for n in cited_n if 1 <= n <= len(ans.refs)]
    kinds = {ans.kinds[n - 1] for n in cited_n if 1 <= n <= len(ans.kinds)}
    if ans.generated and "[A]" in ans.text:
        kinds.add(qp.USER_ASSERTION)
    if ans.generated and "[M]" in ans.text:
        kinds.add(qp.MISSING_DOCUMENT)
    want = case.get("answer", {}).get("distinguish", [])
    contradictions = []
    for s in _sentences(ans.text if ans.generated else ""):
        for phrase in case.get("answer", {}).get("must_not_state_as_policy", []):
            if phrase.lower() in s.lower() and "[A]" not in s \
                    and not (answer._NEGATION.search(s) or answer._ABSENT.search(s)):
                contradictions.append(s[:100])
    sents = _sentences(ans.text) if ans.generated else []
    hit = [r for r in cited if any(rb.ref_matches(g, r) for g in gold)]
    return {
        "id": case["id"], "golden": case.get("golden", False),
        "answerable_gold": bool(case["gold"]), "bundle_answerable": bundle.answerable,
        "must_refuse": bool(case.get("answer", {}).get("refuse")),
        "generated": ans.generated, "failures": ans.failures,
        "cites_gold": bool(hit), "cited": cited,
        "citation_precision": len(hit) / len(cited) if cited else None,
        "distinguish": {k: k in kinds for k in want},
        "parts_answered": [any(ans.refs.index(s.ref) + 1 in cited_n
                               for s in p.sources if s.supports and s.ref in ans.refs)
                           for p in bundle.parts if p.state in ("SUPPORTED",
                                                                "PARTIALLY_SUPPORTED")],
        "sentences": len(sents), "contradictions": contradictions,
        "latency_ms": ans.latency_ms, "prompt_tokens": ans.prompt_tokens,
        "output_tokens": ans.output_tokens, "text": ans.text, "draft": ans.draft,
        "model": ans.model, "calls": ans.calls, "verify_ms": ans.verify_ms,
        "prepare_ms": ans.prepare_ms,
        "first_draft": ans.first_draft,
    }


def replay(prior: dict):
    """A 'model' that returns what the live model said before — `--recheck` re-runs
    every check on stored drafts with zero Gemini calls (the cost guard)."""
    def generate(question, block, *, environment, prior_questions=(), request_id=None):
        r = prior[generate.case]
        return generation.GenerationResult(r["draft"] or "", r["model"] or "replay",
                                           "replay", "", r["latency_ms"] or 0,
                                           r["prompt_tokens"], r["output_tokens"])
    generate.case = ""
    return generate


def aggregate(rows, mode: str) -> dict:
    def frac(xs):
        xs = list(xs)
        return round(sum(xs) / len(xs), 4) if xs else None
    called = [r for r in rows if r["prompt_tokens"] is not None and r["model"] != "stub"]
    vms = sorted(r["verify_ms"] for r in rows if r.get("calls")) or [0]
    if mode == "offline-stub":
        called = [r for r in rows if r["prompt_tokens"] is not None]
    lat = sorted(r["latency_ms"] for r in called if r["latency_ms"]) or [0]
    fails = [f for r in rows for f in r["failures"]]
    pin, pout = (sum(r[k] or 0 for r in called) for k in ("prompt_tokens",
                                                            "output_tokens"))
    rate_in = os.environ.get("LEGALMIND_GEMINI_USD_PER_M_IN")
    rate_out = os.environ.get("LEGALMIND_GEMINI_USD_PER_M_OUT")
    answerable = [r for r in rows if r["answerable_gold"] and r["bundle_answerable"]]
    dist = [v for r in rows for v in r["distinguish"].values()]
    return {
        "mode": mode,
        "cases": len(rows),
        "gemini_calls": sum(r.get("calls") or 0 for r in called) if mode == "live" else 0,
        "repaired": sum(1 for r in rows if r.get("calls") == 2),
        "repaired_then_shown": sum(1 for r in rows if r.get("calls") == 2
                                   and r["generated"]),
        "verify_ms": {"p50": vms[len(vms) // 2], "p95": vms[int(len(vms) * .95)]},
        "prepare_ms": (lambda p: {"p50": p[len(p) // 2], "p95": p[int(len(p) * .95)]})(
            sorted(r.get("prepare_ms") or 0 for r in rows if r.get("calls")) or [0]),
        "answered_of_answerable_bundles": frac(r["generated"] for r in answerable),
        "relevance_cites_gold": frac(r["cites_gold"] for r in answerable),
        "completeness_distinguish": frac(dist),
        "completeness_parts": frac(x for r in answerable for x in r["parts_answered"]),
        "faithfulness_answers_passing_checks": frac(r["generated"] for r in called),
        "unsupported_sentences": sum(1 for f in fails
                                     if f.startswith(("no citation", "figure"))),
        "reader_figure_as_position": sum(1 for f in fails if f.startswith("a reader")),
        "verdicts": sum(1 for f in fails if f.startswith("compliance")),
        "contradictions_shown": sum(len(r["contradictions"]) for r in rows),
        "citation_precision": frac(r["citation_precision"] for r in answerable
                                   if r["citation_precision"] is not None),
        "invalid_markers": sum(1 for f in fails if "does not exist" in f),
        "refusals_correct": frac(not r["generated"] for r in rows if r["must_refuse"]),
        "failure_kinds": sorted({f.split(":")[0] for f in fails}),
        "latency_ms": {"p50": lat[len(lat) // 2], "p95": lat[int(len(lat) * .95)]},
        "tokens": {"prompt": pin, "output": pout,
                   "prompt_per_call": pin // max(1, len(called))},
        "usd": (round(pin / 1e6 * float(rate_in) + pout / 1e6 * float(rate_out), 4)
                if rate_in and rate_out else "rate not recorded — tokens are the cost"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--recheck", help="a previous --live JSON: re-check its drafts")
    ap.add_argument("--no-repair", action="store_true",
                    help="no corrective generation (measure the deterministic layer)")
    args = ap.parse_args()
    if args.no_repair:
        answer.REPAIR = False
    db = sessionmaker(bind=create_engine(
        args.db, connect_args={"options": "-c default_transaction_read_only=on"}))()
    replayed = None
    if args.recheck:
        replayed = replay({r["id"]: r for r in json.loads(
            pathlib.Path(args.recheck).read_text())["cases"] if r.get("draft")})
    rows = []
    for case in json.loads(rb.DATASET.read_text())["cases"]:
        if args.only and case["id"] not in args.only:
            continue
        built = rb.bundle_for(db, case)
        if built is None:
            continue
        plan, bundle = built
        # Offline and replay modes stub BOTH calls: a repair left on the real seam
        # would egress from an "offline" run whenever a credential is present.
        model = None if args.live else stub
        fixer = None if args.live else stub_repair
        if replayed is not None:
            replayed.case = case["id"]       # type: ignore[attr-defined]
            model = replayed
        ans = answer.respond(bundle, case["question"], environment="development",
                             prior_questions=(case["after"],) if case.get("after") else (),
                             generate=model, repair=fixer, db=db)
        rows.append(score(case, plan, bundle, ans))
        print(case["id"], "OK" if ans.generated else "--", ans.failures[:2], flush=True)
    mode = "live" if args.live else "recheck (zero calls)" if args.recheck else "offline-stub"
    out = {"summary": aggregate(rows, mode), "cases": rows}
    print(json.dumps(out["summary"], indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

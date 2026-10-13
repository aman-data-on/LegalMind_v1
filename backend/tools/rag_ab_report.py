"""Tables and the pre-registered gate verdicts for RAG_FRAMEWORK_AB_BENCHMARK.md.

    python3 -m tools.rag_ab_run report

Reads the private result files (LEGALMIND_AB_PRIVATE) and rewrites ONLY the block
between the `generated` markers of docs/00-project/RAG_FRAMEWORK_AB_BENCHMARK.md. The
narrative around it is written by hand from these numbers. IDs, refs and figures only:
no answer or document text (54.6).
"""
from __future__ import annotations

import json

from tools.rag_ab_run import PRIVATE, ROOT

REPORT = ROOT.parent / "docs" / "00-project" / "RAG_FRAMEWORK_AB_BENCHMARK.md"
START, END = "<!-- generated:start -->", "<!-- generated:end -->"


def _load(name):
    p = PRIVATE / name
    return json.loads(p.read_text()) if p.exists() else None


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def _diff(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = b - a
        return f"{d:+.3f}" if isinstance(d, float) else f"{d:+d}"
    return "—"


def table(systems, metrics, title):
    head = "| Metric | " + " | ".join(s for s, _ in systems) + " | " + " | ".join(
        f"{s} - A" for s, _ in systems[1:]) + " |"
    out = [f"**{title}**", "", head, "|" + "---|" * (1 + 2 * len(systems) - 1)]
    for m in metrics:
        vals = [r.get(m) if r else None for _, r in systems]
        out.append(f"| {m} | " + " | ".join(_fmt(v) for v in vals) + " | "
                   + " | ".join(_diff(vals[0], v) for v in vals[1:]) + " |")
    return "\n".join(out) + "\n"


RET_METRICS = ["cases", "slots", "recall@1", "recall@3", "recall@5", "recall@10", "mrr",
               "ndcg@5", "multi_source_complete", "wrong_source_cases", "false_admission",
               "must_refuse", "pool_recall@10", "pool_recall@50", "pool_mrr", "ms_p50",
               "ms_p95"]
ANS_METRICS = ["turns", "scored_answer_turns", "expert_review_turns", "errors",
               "answered_rate", "cites_gold", "slots_cited", "citation_precision",
               "false_refusals", "context_dependent_cites_gold", "must_refuse",
               "false_admissions", "social_or_scope_turns",
               "social_or_scope_answered_from_corpus", "cites_prior_ok",
               "wrong_source_cited", "wrong_source_shown", "contradictions",
               "verdict_language", "foreign_document_cited", "non_current_cited",
               "hard_negative_lead", "unsupported_figure_sentences", "sentences",
               "nli_supported_share", "latency_ms_p50", "latency_ms_p95", "gemini_calls",
               "gemini_calls_per_turn", "prompt_tokens", "output_tokens"]
SAFETY = ["wrong_source_cited", "wrong_source_shown", "false_admissions", "contradictions",
          "verdict_language", "foreign_document_cited", "non_current_cited",
          "social_or_scope_answered_from_corpus"]


def per_case_retrieval(ret):
    """case id -> satisfied-at-3 for each slot, from a retrieval result."""
    return {r["id"]: [s["rank"] is not None and s["rank"] <= 3 for s in r["slots"]]
            for r in ret["rows"]}


def wins(a, b, key="single"):
    pa, pb = per_case_retrieval(a), per_case_retrieval(b)
    aw, bw, both = [], [], []
    for cid, sa in pa.items():
        sb = pb.get(cid, [])
        if not sa:
            continue
        na, nb = sum(sa), sum(sb)
        if na > nb:
            aw.append(cid)
        elif nb > na:
            bw.append(cid)
        elif na < len(sa):
            both.append(cid)
    return aw, bw, both


def safety_events(ans):
    out = []
    for c in ans["conversations"]:
        for t in c["turns"]:
            ck = t.get("checks", {})
            for k in ("wrong_source_cited", "foreign_document_cited", "non_current_cited",
                      "contradictions", "verdicts"):
                if ck.get(k):
                    out.append((t["id"], k, len(ck[k]) if isinstance(ck[k], list) else 1))
            if ck.get("false_admission"):
                out.append((t["id"], "false_admission", 1))
            if ck.get("answered_from_corpus"):
                out.append((t["id"], f"{t['kind']}_answered_from_corpus", 1))
    return out


def answer_turns(ans):
    return {t["id"]: t for c in ans["conversations"] for t in c["turns"]
            if t["kind"] != "prior"}


def gates(ra, rb0, aa, ab0, rb1):
    """The pre-registered gates, mechanically. Returns rows (gate, system, verdict, why)."""
    rows = []

    def g(name, sys_, ok, why):
        rows.append((name, sys_, "INCONCLUSIVE" if ok is None else "PASS" if ok else "FAIL",
                     why))
    for sys_, rret, rans in (("B0", rb0, ab0), ("B1", rb1, None)):
        if rret is None:
            continue
        ma, mb = ra["metrics"], rret["metrics"]
        a1, b1 = ma["single_turn"], mb["single_turn"]
        if rans is not None and aa is not None:
            worse = [f"{s}.{k} {aa['metrics'][s][k]}→{rans['metrics'][s][k]}"
                     for s in ("single_turn", "multi_turn") for k in SAFETY
                     if (rans["metrics"][s][k] or 0) > (aa["metrics"][s][k] or 0)]
            g("G1 legal safety", sys_, not worse, "; ".join(worse) or "no count above A")
            ca, cb = aa["metrics"]["single_turn"], rans["metrics"]["single_turn"]
            ok = all(cb[k] is not None and ca[k] is not None and cb[k] >= ca[k] - .02
                     for k in ("cites_gold", "citation_precision"))
            g("G2 citation correctness", sys_, ok,
              f"cites_gold {ca['cites_gold']}→{cb['cites_gold']}, precision "
              f"{ca['citation_precision']}→{cb['citation_precision']}")
            ha, hb = aa["metrics"]["adversarial"], rans["metrics"]["adversarial"]
            g("G3 hard negatives", sys_,
              hb["wrong_source_cited"] <= ha["wrong_source_cited"]
              and hb["false_admissions"] <= ha["false_admissions"]
              and mb["adversarial"]["wrong_source_cases"] <= ma["adversarial"]["wrong_source_cases"]
              and mb["adversarial"]["false_admission"] <= ma["adversarial"]["false_admission"],
              f"answers wrong-source {ha['wrong_source_cited']}→{hb['wrong_source_cited']}, "
              f"false admission {ha['false_admissions']}→{hb['false_admissions']}; retrieval "
              f"wrong-source {ma['adversarial']['wrong_source_cases']}→"
              f"{mb['adversarial']['wrong_source_cases']}, false admission "
              f"{ma['adversarial']['false_admission']}→{mb['adversarial']['false_admission']}")
            # G5/G6 name no suite, so both the single-turn and the conversation suite
            # must pass — the conservative reading, stated in the report.
            l5, l6 = [], []
            for suite in ("single_turn", "multi_turn"):
                la, lb = aa["metrics"][suite], rans["metrics"][suite]
                ta = (la["prompt_tokens"] + la["output_tokens"]) / max(1, la["turns"])
                tb = (lb["prompt_tokens"] + lb["output_tokens"]) / max(1, lb["turns"])
                l5.append((lb["latency_ms_p95"] <= 1.2 * la["latency_ms_p95"],
                           f"{suite} p95 {la['latency_ms_p95']}→{lb['latency_ms_p95']} ms"))
                l6.append((lb["gemini_calls_per_turn"] <= 1.2 * la["gemini_calls_per_turn"]
                           and tb <= 1.2 * ta, f"{suite} calls/turn "
                           f"{la['gemini_calls_per_turn']}→{lb['gemini_calls_per_turn']}, "
                           f"tokens/turn {ta:.0f}→{tb:.0f}"))
            g("G5 latency", sys_, all(x for x, _ in l5), "; ".join(y for _, y in l5))
            g("G6 cost", sys_, all(x for x, _ in l6), "; ".join(y for _, y in l6))
            xa, xb = aa["metrics"]["multi_turn"], rans["metrics"]["multi_turn"]
            ok = (xb["context_dependent_cites_gold"] or 0) >= (
                xa["context_dependent_cites_gold"] or 0) - .02 and not any(
                (xb[k] or 0) > (xa[k] or 0) for k in SAFETY)
            g("G8 conversation", sys_, ok,
              f"context-dependent cites_gold {xa['context_dependent_cites_gold']}→"
              f"{xb['context_dependent_cites_gold']}")
        else:
            for name in ("G1 legal safety", "G2 citation correctness", "G5 latency",
                         "G6 cost", "G8 conversation"):
                g(name, sys_, None, "answer stage not run for this system (cost guard)")
            g("G3 hard negatives", sys_,
              mb["adversarial"]["wrong_source_cases"] <= ma["adversarial"]["wrong_source_cases"]
              and mb["adversarial"]["false_admission"] <= ma["adversarial"]["false_admission"],
              "retrieval stage only")
        da, db = ma["document"], mb["document"]
        ok = (b1["recall@3"] >= a1["recall@3"] - .01 and b1["mrr"] >= a1["mrr"] - .01
              and mb["no_document"]["recall@3"] >= .95 and db["recall@3"] >= da["recall@3"])
        g("G4 retrieval", sys_, ok,
          f"single-turn r@3 {a1['recall@3']}→{b1['recall@3']}, MRR {a1['mrr']}→{b1['mrr']}, "
          f"no-document r@3 {ma['no_document']['recall@3']}→{mb['no_document']['recall@3']}, "
          f"document r@3 {da['recall@3']}→{db['recall@3']}")
    return rows


def build() -> str:
    ra, rb0, rb1 = (_load(f"retrieval_{s}.json") for s in ("A", "B0", "B1"))
    from tools.rag_ab_run import answer_metrics
    aa, ab0 = (_load(f"benchmark_results_{s}.json") for s in ("A", "B0"))
    for res in (aa, ab0):
        if res:
            res["metrics"] = answer_metrics(res)        # the current scorer's suites
    parts = []
    for suite in ("no_document", "document", "single_turn", "adversarial", "manager",
                  "follow_ups_J"):
        parts.append(table([(s, r["metrics"][suite]) for s, r in
                                  (("A", ra), ("B0", rb0), ("B1", rb1)) if r],
                           RET_METRICS, f"Retrieval — {suite} (zero Gemini)"))
    for s, r in (("B0", rb0), ("B1", rb1)):
        if r and ra:
            aw, bw, both = wins(ra, r)
            parts.append(f"**Retrieval cases, A vs {s}** (gold satisfied at rank ≤ 3, per "
                         f"case): A wins {len(aw)} · {s} wins {len(bw)} · both short "
                         f"{len(both)}\n\n- A wins: {', '.join(aw) or '—'}\n- {s} wins: "
                         f"{', '.join(bw) or '—'}\n- both short: {', '.join(both) or '—'}\n")
    if aa and ab0:
        for suite in ("single_turn", "document", "multi_turn", "adversarial", "manager"):
            parts.append(table([("A", aa["metrics"][suite]),
                                      ("B0", ab0["metrics"][suite])], ANS_METRICS,
                               f"Answers — {suite} (live, model {aa['model']})"))
        ta, tb = answer_turns(aa), answer_turns(ab0)
        aw, bw, both = [], [], []
        for k, t in ta.items():
            ca, cb = t["checks"].get("cites_gold"), tb.get(k, {}).get("checks", {}).get(
                "cites_gold")
            if ca is None or t["expert_review"]:
                continue
            (aw if ca and not cb else bw if cb and not ca else both if not ca else []
             ).append(k)
        parts.append(f"**Answer turns, A vs B0** (cites a gold source): A wins {len(aw)} · "
                     f"B0 wins {len(bw)} · both fail {len(both)}\n\n- A wins: "
                     f"{', '.join(aw) or '—'}\n- B0 wins: {', '.join(bw) or '—'}\n"
                     f"- both fail: {', '.join(both) or '—'}\n")
        ea, eb = safety_events(aa), safety_events(ab0)
        parts.append("**Safety events** (turn · check · count)\n\n| A | B0 |\n|---|---|\n"
                     + "\n".join(f"| {' · '.join(map(str, x)) if x else ''} | "
                                 f"{' · '.join(map(str, y)) if y else ''} |"
                                 for x, y in _zip(ea, eb)) + "\n")
        if ab0.get("prep"):
            parts.append(f"B0 framework index build per process: {ab0['prep']}\n")
    if ra:
        rows = gates(ra, rb0, aa, ab0, rb1)
        parts.append("**Pre-registered gates** (RAG_FRAMEWORK_AB_CRITERIA.md; G7 assessed "
                     "in § Maintenance)\n\n| Gate | System | Verdict | Evidence |\n"
                     "|---|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} | {d} |"
                                                       for a, b, c, d in rows) + "\n")
    return "\n".join(parts)


def _zip(a, b):
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else None, b[i] if i < len(b) else None) for i in range(n)]


def main() -> int:
    body = build()
    doc = REPORT.read_text() if REPORT.exists() else f"{START}\n{END}\n"
    head, _, rest = doc.partition(START)
    _, _, tail = rest.partition(END)
    REPORT.write_text(f"{head}{START}\n\n{body}\n{END}{tail}")
    print(body)
    return 0

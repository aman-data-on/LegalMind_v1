"""Roadmap PHASE 11 — the claim verifier, measured. Zero Gemini.

    python3 -m tools.eval_verification --claims C --labels L0 L1 ... [--json out]

Against the PHASE 10 answers' own claims (549, from saved drafts — no new generation),
labelled independently (SUPPORTED · PARTIAL · UNSUPPORTED · CONTRADICTED · NON_FACTUAL,
supporting excerpts, kind errors), plus deterministic PERTURBATIONS of the supported
claims whose correct verdict is known by construction:
  negate      "may" → "may not", "is" → "is not", …      must be rejected
  overstate   "may" → "must", "should" → "must"          must be rejected
  figure      the first number+unit changed              must be rejected
  as_law      "Under Indian law, " prefixed to a company-position claim   rejected
  swap_cite   cited to an excerpt that does not support it — must be re-cited to
              a supporting excerpt, or rejected; kept on the wrong excerpt = false accept
Metrics: claim accuracy, false-accept / false-reject rates, citation precision and
recall (model's vs verifier's), latency.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from legalmind.assist.query import query_plan as qp
from legalmind.assist.retrieval import evidence as evidence_mod
from legalmind.assist.synthesis import answer
from legalmind.assist.verification import guardrails, verify

# Negation applies only to a claim carrying none already — "no early exit is not
# permitted" is a garbled double negative, not a clean contradiction (first run's flaw).
_HAS_NEGATION = re.compile(r"\b(?:not|no|never|none|nor|without|cannot)\b|n't\b", re.I)
_NEG = [(r"\bmay\b", "may not"), (r"\bmust\b", "must not"), (r"\bis\b", "is not"),
        (r"\bare\b", "are not"), (r"\bcan\b", "cannot"), (r"\bapplies\b", "does not apply"),
        (r"\bremain\b", "do not remain"), (r"\bpermits\b", "prohibits")]
_OVER = [(r"\bmay\b", "must"), (r"\bshould\b", "must"), (r"\bcan\b", "must"),
         (r"\bsome\b", "all")]


def _first(text, table):
    for pattern, repl in table:
        if re.search(pattern, text):
            return re.sub(pattern, repl, text, count=1)
    return None


def perturb(claim: dict, ex: dict) -> list[tuple[str, str]]:
    s = claim["text"]
    out = []
    for name, table in (("negate", _NEG), ("overstate", _OVER)):
        if name == "negate" and _HAS_NEGATION.search(s):
            continue
        head, _, tail = s.partition(",") if name == "negate" and s.count(",") > 2 \
            else (s, "", "")
        t = _first(head, table)
        if t:
            out.append((name, t + ("," + tail if tail else "")))
    m = re.search(r"\b(\d+)(\s*(?:days?|months?|years?|%|percent|weeks?))", s)
    if m:
        out.append(("figure", s[:m.start()] + str(int(m.group(1)) * 2 + 1)
                    + m.group(2) + s[m.end():]))
    kinds = {ex["excerpts"][n - 1]["kind"] for n in claim["gold"]}
    if kinds == {qp.COMPANY_POSITION} and not re.search(r"law|act\b", s, re.I):
        out.append(("as_law", "Under Indian law, " + s[0].lower() + s[1:]))
    wrong = [e["n"] for e in ex["excerpts"] if e["n"] not in claim["gold"]]
    if wrong:
        out.append(("swap_cite", answer._MARKER.sub(
            lambda mm: f"[{wrong[0]}]" if mm.group(1).isdigit() else mm.group(0), s)))
    return out


def run(answers, labels) -> dict:
    lab = {(r["case"], r["n"]): r for r in labels}
    rows, perturbed, lat = [], [], []
    for ex in answers:
        evidence = [e["text"] for e in ex["excerpts"]]
        kinds = [e["kind"] for e in ex["excerpts"]]
        auth = [ex["authority"].get(e["ref"], "") for e in ex["excerpts"]]
        qfig = tuple(guardrails.unstated_figures(
            f"{ex['question']} {ex['A'] or ''}", []))
        # The production pipeline is BOTH layers: PHASE 10's mechanical checks on each
        # sentence, then this verifier — so a claim is accepted only if both pass.
        payload = answer.Payload(evidence, kinds, [e["ref"] for e in ex["excerpts"]],
                                 ex["A"], ex["M"], "", (), qfig)
        empty = evidence_mod.Bundle((), (), (), False)

        def mechanical(text: str, payload=payload, empty=empty) -> bool:
            return not answer.check(text, payload, empty)
        t0 = time.perf_counter()
        # Timed as production runs it: the answer's own claims, in one check_answer.
        verify.check_answer("", evidence, kinds, auth, [c["text"] for c in ex["claims"]],
                            [answer.is_context(c["text"], qfig) for c in ex["claims"]])
        lat.append((time.perf_counter() - t0) * 1000)
        for c in ex["claims"]:
            g = lab[(ex["case"], c["n"])]
            j = verify.judge(c["text"], evidence, kinds, auth,
                             context=answer.is_context(c["text"], qfig))
            ok_gold = g["label"] in ("SUPPORTED", "NON_FACTUAL") and not g["kind_error"]
            semantic = j.verdict == "CONTEXT" or (j.verdict == "SUPPORTED"
                                                  and not j.kind_error)
            accepted = semantic and mechanical(c["text"])
            rows.append({"case": ex["case"], "n": c["n"], "gold": g["label"],
                         "kind_error_gold": g["kind_error"], "ok_gold": ok_gold,
                         "verdict": j.verdict, "kind_error": j.kind_error,
                         "accepted": accepted, "semantic": semantic,
                         "mechanical": mechanical(c["text"]), "cited": list(j.cited),
                         "assigned": list(j.citations), "supported_by": g["supported_by"],
                         "entail": round(j.entail, 3), "contra": round(j.contra, 3),
                         "reason": j.reason})
            if g["label"] == "SUPPORTED" and not g["kind_error"] and g["supported_by"] \
                    and j.verdict == "SUPPORTED":
                for name, text in perturb({"text": c["text"], "gold": g["supported_by"]},
                                          ex):
                    pj = verify.judge(text, evidence, kinds, auth,
                                      context=answer.is_context(text, qfig))
                    ok = (pj.verdict == "CONTEXT" or (pj.verdict == "SUPPORTED"
                                                      and not pj.kind_error))
                    if name == "swap_cite":
                        bad = ok and not set(pj.citations) & set(g["supported_by"])
                    else:
                        bad = ok and mechanical(text)
                    perturbed.append({"type": name, "false_accept": bad,
                                      "case": ex["case"], "n": c["n"],
                                      "text": text[:160]})
    return {"claims": rows, "perturbed": perturbed, "latency_ms": lat}


def summary(res) -> dict:
    def frac(xs):
        xs = list(xs)
        return round(sum(xs) / len(xs), 4) if xs else None
    rows, pert = res["claims"], res["perturbed"]
    bad = [r for r in rows if not r["ok_gold"]]
    ok = [r for r in rows if r["ok_gold"]]
    sup = [r for r in rows if r["gold"] == "SUPPORTED" and r["supported_by"]
           and r["cited"]]

    def prec(key):
        num = sum(len(set(r[key]) & set(r["supported_by"])) for r in sup if r[key])
        den = sum(len(r[key]) for r in sup if r[key])
        return round(num / den, 4) if den else None

    def rec(key):
        return frac(bool(set(r[key]) & set(r["supported_by"])) for r in sup)
    lat = sorted(res["latency_ms"]) or [0]
    by_answer: dict[str, list[dict]] = {}
    for r in rows:
        by_answer.setdefault(r["case"], []).append(r)
    passed = [a for a in by_answer.values() if all(r["accepted"] for r in a)]
    types = sorted({p["type"] for p in pert})
    return {
        "claims": len(rows), "gold_ok": len(ok), "gold_bad": len(bad),
        "accuracy": frac(r["accepted"] == r["ok_gold"] for r in rows),
        "false_accept_real": frac(r["accepted"] for r in bad),
        "false_accept_real_semantic_only": frac(r["semantic"] for r in bad),
        "false_reject_mechanical_only": frac(not r["mechanical"] for r in ok),
        "false_reject": frac(not r["accepted"] for r in ok),
        "false_reject_supported_only": frac(not r["accepted"] for r in ok
                                            if r["gold"] == "SUPPORTED"),
        "answers": len(by_answer),
        "answers_passing": frac(bool(all(r["accepted"] for r in a))
                                for a in by_answer.values()),
        "answers_clean_gold": frac(all(r["ok_gold"] for r in a)
                                   for a in by_answer.values()),
        "shown_answers_with_bad_claim": sum(1 for a in passed
                                            if not all(r["ok_gold"] for r in a)),
        "shown_bad_claims": sum(1 for a in passed for r in a if not r["ok_gold"]),
        "perturbations": len(pert),
        "false_accept_perturbed": frac(p["false_accept"] for p in pert),
        "false_accept_by_type": {t: frac(p["false_accept"] for p in pert
                                         if p["type"] == t) for t in types},
        "n_by_type": {t: sum(p["type"] == t for p in pert) for t in types},
        "citation_precision_model": prec("cited"),
        "citation_precision_verifier": prec("assigned"),
        "citation_recall_model": rec("cited"),
        "citation_recall_verifier": rec("assigned"),
        "latency_ms_per_answer": {"p50": round(lat[len(lat) // 2]),
                                  "p95": round(lat[int(len(lat) * .95)])},
        "model": f"{verify.config.nli_model_repo()}@{verify.config.nli_model_revision()}",
        "entail": verify.ENTAIL, "contra": verify.CONTRA,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", required=True)
    ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()
    answers = json.loads(pathlib.Path(args.claims).read_text())
    labels = [r for f in args.labels for r in json.loads(pathlib.Path(f).read_text())]
    res = run(answers, labels)
    out = {"summary": summary(res), **res}
    print(json.dumps(out["summary"], indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

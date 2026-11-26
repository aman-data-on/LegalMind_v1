"""Lawyer judgement P1 — "what it replaces in our paper", scored with ZERO model calls.

    python3 -m tools.our_paper_eval --doc <client.docx|pdf> --gold <gold.json>
        [--msa <our MSA file>] [--brand Leapswitch] [--on YYYY-MM-DD] [--json out.json]

Reads the client document with the production parser, finds its references into our
paper (`consistency.paper_references`), pins our documents as the review lane does —
the MSA from a file given here (the harness has no deal, so no signed paper or deal
template), each published policy from `legal-docs/published/<date>/<KEY>.html` in force
on the document's own date (`our_paper.pick_policy`, M2) — and resolves them
(`our_paper.resolve`). Reports, separately for NUMBERED and DESCRIBED references:
reference recall and precision (parsed vs the gold list), resolution recall and
precision (a RESOLVED row is right only when the gold says that pair is right), and
every false claim by name. The gold file lives with the case, outside the repo (rule
21; no client material here):

    {"references": [["3.1", "MSA", "17.2"], ["6.2", "SLA", "credits lapse"], ...],
     "wrong": [["5.2", "MSA", "7.3"]],    # pairs whose RESOLVED would be a false claim
     "fail_closed": {"2.1|AUP|5": "NO_STORED_COPY"}}   # the expected non-RESOLVED status
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sys
import uuid

from legalmind import config
from legalmind.analysis import consistency, our_paper
from legalmind.assist.knowledge import published
from legalmind.ingestion import parsing
from legalmind.mapping.engine import Clause


def clauses_of(path: pathlib.Path) -> list[Clause]:
    data = path.read_bytes()
    mime = ("application/pdf" if path.suffix.lower() == ".pdf" else
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    segments = parsing.parse(data, mime).segments
    return [Clause(evidence_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{path.name}-{i}"),
                   content=s.content, section_number=s.section_number,
                   section_title=s.section_title) for i, s in enumerate(segments)]


def msa_base(path: pathlib.Path) -> dict:
    return {"label": f"MSA file {path.name}", "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "units": our_paper.msa_units(clauses_of(path)), "paragraphs": []}


def policy_bases(brand: str, on: datetime.date) -> dict[str, dict]:
    """Each policy's saved snapshots as stored versions (each in force from its
    folder's date until the next snapshot that differs, `published.in_force`), pinned on `on`."""
    root = pathlib.Path(config.source_material_dir()) / "published"
    out = {}
    for doc in ("TOS", "SLA", "AUP"):
        policy = next(p for p in published.POLICIES
                      if p.key == f"{doc}-{brand.lower()}")
        periods: list[dict] = []
        for folder in sorted(root.iterdir()):
            page = folder / f"{policy.key}.html"
            if not page.exists():
                continue
            blocks = published.extract(page.read_text())
            sha = hashlib.sha256(published.policy_text(blocks).encode()).hexdigest()
            if periods and periods[-1]["sha256"] == sha:
                continue                    # unchanged: the same period runs on
            day = datetime.date.fromisoformat(folder.name)
            units, paragraphs = our_paper.policy_units(
                [(i.kind, i.clause, i.content) for i in published.items(policy, blocks)])
            periods.append({"source_id": sha, "started_on": day, "sha256": sha,
                            "label": f"{policy.name} as published on {day}",
                            "file": f"published/{folder.name}/{policy.key}.html",
                            "date": day.isoformat(), "units": units,
                            "paragraphs": paragraphs})
        got = published.in_force(periods, on)
        if got["pinned"] is None:
            out[doc] = {"unresolved": our_paper.NO_STORED_COPY, "hint": {
                "on": on.isoformat(), "earliest": got["earliest"] and
                got["earliest"].isoformat()}}
        else:
            out[doc] = {**got["pinned"], **({"newer": got["newer"]} if got["newer"]
                                             else {})}
    return out


def score(rows: list[dict], gold: dict) -> dict:
    def key(r: dict) -> tuple:
        return (r["source"], r["doc"], r["number"] or r["described"])
    want = {tuple(g) for g in gold["references"]}
    wrong = {tuple(g) for g in gold.get("wrong", [])}
    closed = gold.get("fail_closed", {})
    report: dict = {}
    for mode in ("NUMBERED", "DESCRIBED"):
        got = {key(r): r for r in rows if r["mode"] == mode}
        gold_mode = {g for g in want if (mode == "NUMBERED") == g[2][0].isdigit()}
        found = gold_mode & got.keys()
        resolvable = {g for g in gold_mode if "|".join(map(str, g)) not in closed}
        resolved = {k for k, r in got.items() if r["status"] == our_paper.RESOLVED}
        right = (resolved & resolvable) - wrong
        false = sorted(resolved - right)
        closed_right = sum(got[g]["status"] == closed["|".join(map(str, g))]
                           for g in gold_mode - resolvable if g in got)
        report[mode] = {
            "reference_recall": f"{len(found)}/{len(gold_mode)}",
            "reference_precision": f"{len(found)}/{len(got)}",
            "resolution_recall": f"{len(right)}/{len(resolvable)}",
            "resolution_precision": f"{len(right)}/{len(resolved)}",
            "fail_closed_as_expected": f"{closed_right}/{len(gold_mode - resolvable)}",
            "missed_references": sorted(gold_mode - got.keys()),
            "extra_references": sorted(got.keys() - gold_mode),
            "false_claims": [{"ref": list(k), "said": got[k].get("ours", {})
                              .get("quote", "")[:160]} for k in false],
            "not_resolved": sorted([*k, got[k]["status"]] for k in resolvable & got.keys()
                                   if k not in resolved)}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--doc", required=True, type=pathlib.Path)
    ap.add_argument("--gold", type=pathlib.Path)
    ap.add_argument("--msa", type=pathlib.Path,
                    default=pathlib.Path(config.source_material_dir()) / "MSA.pdf")
    ap.add_argument("--fingerprint", type=pathlib.Path, nargs="*", default=[])
    ap.add_argument("--brand", default="Leapswitch")
    ap.add_argument("--on", type=datetime.date.fromisoformat)
    ap.add_argument("--json", type=pathlib.Path)
    args = ap.parse_args(argv)
    clauses = clauses_of(args.doc)
    on = args.on or our_paper.document_date(clauses) or datetime.date.today()
    refs = consistency.paper_references(clauses)
    bases = {"MSA": msa_base(args.msa), **policy_bases(args.brand, on)}
    rows = our_paper.resolve(refs, bases)
    out = {"document_sha256": hashlib.sha256(args.doc.read_bytes()).hexdigest(),
           "on": on.isoformat(),
           "pins": {d: {k: v for k, v in b.items() if k in ("label", "sha256", "hint",
                                                            "unresolved")}
                    for d, b in bases.items()},
           "fingerprint": our_paper.fingerprint(
               refs, [bases["MSA"], *(msa_base(p) for p in args.fingerprint)]),
           "overrides": our_paper.overridden(rows), "rows": rows}
    if args.gold:
        out["score"] = score(rows, json.loads(args.gold.read_text()))
    text = json.dumps(out, indent=1, default=str)
    if args.json:
        args.json.write_text(text)
    print(json.dumps(out.get("score", {}), indent=1) if args.gold else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Measure the Finding-explanation pipeline against the live corpus — read-only.

`AM-49` r2 rejects a generated sentence mechanically whenever it strays, and
records FALLBACK. Measured 2026-09-11 on production: 44 ACCEPTED against 63
FALLBACK, a 41.1% acceptance rate, which makes the feature mostly not deliver.
This tool answers WHY, by classifying every rejection rather than by moving a
threshold — the floors are the guardrail and are not this tool's business.

It rebuilds each Finding's grounding material through the production
`explanations.gather`, calls the model through the single egress seam, and runs
the production `explanations.validate`. **It stores nothing**: no explanation
row is written or updated, so a run neither pollutes the cache nor changes what
a user sees. Identifiers and counts only in the output — never clause text
(locked 53.3).

Usage:  python3 -m tools.verify_explanation_quality [--limit N] [--json PATH]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist import explanations, generation
from legalmind.db import models as M

# The categories the phase brief names, mapped from the validator's own reasons.
_CATEGORIES = (
    ("insufficient source material", "insufficient source material"),
    ("model declared the material insufficient", "model refusal / thin evidence"),
    ("ungrounded words", "grounding overlap failure"),
    ("forbidden vocabulary", "forbidden vocabulary"),
    ("judgment vocabulary", "forbidden vocabulary"),
    ("unsupported number", "unsupported numbers"),
    ("more than", "prompt/format issue"),
    ("not exactly one sentence", "prompt/format issue"),
    ("length ", "prompt/format issue"),
    ("multi-line", "prompt/format issue"),
    ("empty reply", "prompt/format issue"),
)


def _validate_legacy(candidate: str, g) -> bool:
    """The SAME sentence judged by the pre-P1 comparison: raw surface forms on
    both sides, the frame vocabulary in raw form, and the flat set arithmetic
    that went with them.

    Every other check (length, one sentence, judgment and forbidden vocabulary,
    unsupported numbers) and both floors are the production ones, so the
    difference between this verdict and the production verdict is attributable to
    the comparison and to nothing else — which a second generation could never
    establish: measured 2026-09-11, the model re-answers about 10% of findings
    differently on an identical payload.
    """
    import re as _re

    from legalmind.assist import guardrails

    def legacy_words(text: str) -> set[str]:
        words = _re.findall(r"[A-Za-z][A-Za-z'-]+|\d[\d.,%]*", text.lower())
        return {w for w in words if w not in guardrails._STOPWORDS and len(w) > 1}

    def legacy_fraction(claim, source_words, ignore=frozenset()):
        words = {w for w in legacy_words(claim) if w not in ignore}
        if not words:
            return 1.0
        return len(words & source_words) / len(words)

    real = (guardrails._content_words, guardrails.grounded_fraction,
            explanations._FRAME_FORMS)
    guardrails._content_words = legacy_words
    guardrails.grounded_fraction = legacy_fraction
    explanations._FRAME_FORMS = explanations._FRAME_WORDS
    try:
        ok, _ = explanations.validate(candidate, g)
        return ok
    finally:
        (guardrails._content_words, guardrails.grounded_fraction,
         explanations._FRAME_FORMS) = real


def _category(reason: str | None) -> str:
    if not reason:
        return "accepted"
    for prefix, label in _CATEGORIES:
        if reason.startswith(prefix) or prefix in reason:
            return label
    return "other"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="0 = every finding")
    ap.add_argument("--json", default=None)
    ap.add_argument("--compare-legacy", action="store_true",
                    help="validate each generated sentence under BOTH the current "
                         "comparison and the pre-P1 raw-form one, so the validator's "
                         "effect is measured without the model's run-to-run variance")
    args = ap.parse_args(argv)

    if not generation.credential_present():
        print("SKIP: no generation credential configured", file=sys.stderr)
        return 0

    engine = create_engine(config.database_url())
    rows: list[dict] = []
    with Session(engine) as db:
        findings = db.execute(
            select(M.Finding).order_by(M.Finding.id)
        ).scalars().all()
        if args.limit:
            findings = findings[: args.limit]
        print(f"measuring {len(findings)} finding(s) — nothing is stored\n")
        for n, finding in enumerate(findings, start=1):
            g = explanations.gather(db, finding)
            if not g.sufficient():
                rows.append({"finding": str(finding.id), "accepted": False,
                             "reason": "insufficient source material",
                             "passages": len(g.passages)})
                continue
            passages = "\n".join(f"[{i}] {p}" for i, p in enumerate(g.passages, start=1)) \
                or "(none — the engine found no passage for this requirement)"
            prompt = explanations.PROMPT_TEMPLATE.format(
                title=g.title, description=g.description or "(none approved)",
                result=g.result_phrase, passages=passages,
                max_words=explanations._MAX_WORDS)
            try:
                result = generation.generate_raw(
                    prompt, prompt_version=explanations.PROMPT_VERSION,
                    environment=config.environment(), max_output_tokens=160)
            except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
                rows.append({"finding": str(finding.id), "accepted": False,
                             "reason": f"provider: {type(exc).__name__}",
                             "passages": len(g.passages)})
                continue
            ok, reason = explanations.validate(result.text, g)
            legacy_ok = None
            if args.compare_legacy:
                legacy_ok = _validate_legacy(result.text, g)
            # How far off was a grounding rejection? Recorded so a threshold
            # question can be answered with a distribution, never a guess.
            overlap = None
            if reason and reason.startswith("ungrounded words"):
                from legalmind.assist import guardrails
                claim = {w for w in guardrails._content_words(result.text)
                         if w not in explanations._FRAME_FORMS}
                overlap = round(len(claim & g.words()) / len(claim), 3) if claim else None
            rows.append({"finding": str(finding.id), "accepted": ok, "reason": reason,
                         "passages": len(g.passages), "overlap": overlap,
                         "legacy_accepted": legacy_ok,
                         "classification": str(finding.classification)})
            if n % 20 == 0:
                print(f"  ... {n}/{len(findings)}")
        db.rollback()          # belt and braces: this tool writes nothing

    accepted = sum(1 for r in rows if r["accepted"])
    total = len(rows)
    print(f"\n{'=' * 62}\nEXPLANATION QUALITY — {total} findings")
    print(f"{'=' * 62}")
    print(f"  accepted          {accepted}/{total} = {accepted / total:.3f}" if total else "  no findings")
    print(f"  fallback          {total - accepted}/{total}")
    print("\n  failures by category:")
    cats = collections.Counter(_category(r["reason"]) for r in rows if not r["accepted"])
    for label, n in cats.most_common():
        print(f"    {label:<34} {n:>4}")
    grounding = [r["overlap"] for r in rows if r.get("overlap") is not None]
    if grounding:
        grounding.sort()
        print(f"\n  grounding-rejected overlap distribution (floor "
              f"{explanations._GROUNDING_OVERLAP}):")
        print(f"    n={len(grounding)}  min={grounding[0]:.2f}  "
              f"median={grounding[len(grounding) // 2]:.2f}  max={grounding[-1]:.2f}")
    print("\n  by classification:")
    by_cls: dict = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        cls = r.get("classification") or "?"
        by_cls[cls][0] += 1
        by_cls[cls][1] += 1 if r["accepted"] else 0
    for cls, (n, ok) in sorted(by_cls.items()):
        print(f"    {cls:<46} {ok}/{n}")
    paired = [r for r in rows if r.get("legacy_accepted") is not None]
    if paired:
        both = sum(1 for r in paired if r["accepted"] and r["legacy_accepted"])
        gained = sum(1 for r in paired if r["accepted"] and not r["legacy_accepted"])
        lost = sum(1 for r in paired if not r["accepted"] and r["legacy_accepted"])
        neither = sum(1 for r in paired if not r["accepted"] and not r["legacy_accepted"])
        print(f"\n  SAME sentences under both comparisons (n={len(paired)}):")
        print(f"    accepted by both                  {both:>4}")
        print(f"    accepted only by the new one      {gained:>4}   <- the fix")
        print(f"    accepted only by the old one      {lost:>4}   <- must be 0")
        print(f"    rejected by both                  {neither:>4}")
        old_rate = (both + lost) / len(paired)
        new_rate = (both + gained) / len(paired)
        print(f"    acceptance  old {old_rate:.3f}  ->  new {new_rate:.3f}"
              f"  ({new_rate - old_rate:+.3f})")
    if args.json:
        with open(args.json, "w") as handle:
            json.dump({"total": total, "accepted": accepted,
                       "categories": dict(cats), "rows": rows}, handle, indent=1)
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

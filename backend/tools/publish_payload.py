"""Build the `POST /configuration/publish` payload, and refuse to build a wrong one.

WHY THIS EXISTS. `import_ratified_standards.py` ends by printing EVERY code it
touched — all 40. Pasting that list into a publish call fails outright, because
publishing a retired code raises `BusinessRuleRejected` (`AM-65`: reversing a
retirement is an owner decision, not a publish call), and one bad code fails the
whole request. The correct list is the 33 that are NOT retired.

A hand-kept list of 33 codes would drift from the directory the moment a standard
is added, retired or renamed — silently, and in the direction of publishing the
wrong set. So the list is DERIVED from the ratified files every time, and this
tool refuses rather than emits when the shape is not the approved one:

* exactly `--expect-active` codes carry no `retired` block (default 33);
* exactly `--expect-retired` carry one (default 7);
* no code is in both, and no code appears twice.

The counts are deliberate, not defensive noise. The owner approved publishing a
specific set; if the directory no longer matches it, that is a decision to be
re-taken, not a number for a script to follow.

Prints only codes and counts — no secrets, no positions, no clause text.

Usage:
    python3 -m tools.publish_payload                       # print a summary
    python3 -m tools.publish_payload -o /root/publish-33.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR

#: The approved operation's shape. Changing either number is a scope change.
#: 33 -> 37 on 2026-09-18: `AM-72` (AB-24) ratified four Constitution §31 Partner
#: Agreement positions when the owner resolved C-23.
EXPECT_ACTIVE = 37
EXPECT_RETIRED = 7


def split(standards_dir: Path) -> tuple[list[str], list[str]]:
    """Return (publishable, retired) requirement codes, sorted.

    A file is retired when it carries the `retired` block `AM-65` defines. That
    block — not the filename, not the basis string — is the single fact this
    reads, because it is the one the importer also acts on.
    """
    active: list[str] = []
    retired: list[str] = []
    for path in sorted(standards_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        code = payload["requirement_code"]
        (retired if payload.get("retired") else active).append(code)
    return sorted(active), sorted(retired)


def validate(active: list[str], retired: list[str],
             expect_active: int, expect_retired: int) -> list[str]:
    """Return the reasons this payload must not be sent. Empty means send it."""
    problems: list[str] = []
    both = sorted(set(active) & set(retired))
    if both:
        problems.append(f"codes marked both active and retired: {both}")
    for label, codes in (("active", active), ("retired", retired)):
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            problems.append(f"duplicate {label} codes: {dupes}")
    if len(active) != expect_active:
        problems.append(
            f"expected {expect_active} publishable standards, found {len(active)}")
    if len(retired) != expect_retired:
        problems.append(
            f"expected {expect_retired} retired standards, found {len(retired)}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", type=Path,
                    help="write the payload JSON here (default: print only)")
    ap.add_argument("--expect-active", type=int, default=EXPECT_ACTIVE)
    ap.add_argument("--expect-retired", type=int, default=EXPECT_RETIRED)
    args = ap.parse_args(argv)

    active, retired = split(RATIFIED_STANDARDS_DIR)
    problems = validate(active, retired, args.expect_active, args.expect_retired)
    if problems:
        print("REFUSING to emit a publish payload:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"publishable : {len(active)}")
    for code in active:
        print(f"    {code}")
    print(f"excluded (retired, never published): {len(retired)}")
    for code in retired:
        print(f"    {code}")

    if args.output:
        args.output.write_text(
            json.dumps({"requirement_codes": active}, indent=2) + "\n")
        args.output.chmod(0o600)
        print(f"\nwrote {args.output} ({len(active)} codes)")
    return 0


if __name__ == "__main__":                              # pragma: no cover
    raise SystemExit(main())

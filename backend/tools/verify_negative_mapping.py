"""Over-broad terminology check — the negative half of `verify_terminology`.

`verify_terminology` proves each Requirement's terminology CAN find the clause it
cites. That is necessary and not sufficient: terminology wide enough to find
anything finds everything, and a PRESENCE Requirement that maps a document with
no such clause produces a confident false `PRESENT` — worse than no mapping,
because a reviewer never looks.

This tool is the other direction. It runs the real ratified terminology over a
population that should map to NOTHING, and reports what does.

--------------------------------------------------------------------------
Why the statutes are the right negative population
--------------------------------------------------------------------------
The seven Indian statutes supplied on 2026-08-18 are **background law, never
contracts** (rule 7: a statute is not a Company Standard and not a Requirement
source). They are also the *hardest* available negative: the Indian Contract Act
1872 is saturated with contract vocabulary — offer, consideration, breach,
termination, arbitration — so terminology that survives it is genuinely keyed to
clause structure rather than to legal words in general.

--------------------------------------------------------------------------
What a hit means, and what it does not
--------------------------------------------------------------------------
A hit is a **signal to read**, not an automatic defect, and the tool deliberately
does not fail the build on one. Two different things produce hits:

* **A precision defect.** Before 2026-08-21, `ARBITRATION-MSA-001` carried the
  bare word `arbitration` as an `exact_phrase` at weight 5, so a footnote reading
  "Cf. the Arbitration Act, 1940" confirmed it. That is a real defect and it was
  fixed by demoting the term to an alias (decision #54).
* **A correct recognition in an inapplicable document.** Contract Act §28
  Exception 1 genuinely discusses agreements to refer disputes to arbitration.
  Terminology that recognises an arbitration clause *should* match it. The
  control against a statute reaching the evaluator is the **declared Document
  Type at upload** — "statute" is not one of locked Step 6's ten values — not the
  mapper, and suppressing it would need negative terms that also suppress
  genuine contract clauses (decision #56).

Telling those apart requires reading the signals, which is why the report prints
them. The number to watch is a hit whose score comes from ONE signal: that is the
shape of the defect, because it means a single term reached the threshold alone.

Absence of the documents is the normal case away from the owner's machine and
exits 0 with a SKIP, exactly as `verify_terminology` does (locked 54.6 keeps them
out of version control).

Usage:
    python3 -m tools.verify_negative_mapping
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from legalmind import config
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.ingestion.parsing import parse_pdf
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules

# Deterministic ids so two runs report identically (ENG-11 discipline applied to
# a tool; these ids never leave the process).
_NS = uuid.UUID("00000000-0000-0000-0000-00000000045f")

#: Background law, never contracts. Anything here mapping to a Requirement is a
#: finding to read — see the module docstring for how to read it.
NEGATIVE_SUBDIR = "Indian_Laws_and_Acts"


def _clauses(document: Path) -> list[Clause]:
    result = parse_pdf(document.read_bytes())
    return [
        Clause(
            evidence_id=uuid.uuid5(_NS, f"{document.name}:{i}"),
            content=seg.content,
            section_number=seg.section_number,
            section_title=seg.section_title,
            page_number=seg.page_number,
        )
        for i, seg in enumerate(result.segments)
    ]


def _rules(path: Path) -> MappingRules | None:
    payload = json.loads(path.read_text())
    config_block = payload.get("mapping_rules")
    return MappingRules.from_config(config_block) if config_block else None


def verify(standards_dir: Path, negative_dir: Path) -> tuple[list[str], int]:
    """Return (report lines, number of mappings found)."""
    lines: list[str] = []
    documents = sorted(negative_dir.glob("*.pdf"))
    if not documents:
        lines.append(
            f"SKIP  no negative documents at {negative_dir} "
            "(normal away from the owner's machine)")
        return lines, 0

    standards = sorted(standards_dir.glob("*.json"))
    hits = 0
    pairs = 0
    for document in documents:
        clauses = _clauses(document)
        for path in standards:
            rules = _rules(path)
            if rules is None:
                continue
            pairs += 1
            code = path.stem
            result = map_requirement(uuid.uuid5(_NS, code), rules, clauses)
            if result.state.value != "CONFIRMED":
                continue
            hits += 1
            lines.append(f"HIT   {document.name} -> {code}")
            # The signals are the point: a hit resting on ONE signal is the
            # shape of a precision defect, because a single term reached the
            # threshold alone.
            for line in result.explanation[2:]:
                lines.append(f"        {line}")

    lines.append("")
    lines.append(f"{len(documents)} negative document(s) x {len(standards)} "
                 f"Requirement(s) = {pairs} pair(s) · {hits} mapping(s)")
    if not hits:
        lines.append("CLEAN — no background-law document maps to any Requirement")
    else:
        lines.append("Read each hit: a single-signal hit is a precision defect; "
                     "a multi-signal hit on genuinely on-topic statutory text is "
                     "not (decision #56).")
    return lines, hits


def main() -> int:
    source_dir = Path(config.source_material_dir())
    lines, _hits = verify(RATIFIED_STANDARDS_DIR, source_dir / NEGATIVE_SUBDIR)
    for line in lines:
        print(line)
    # Deliberately always 0: a hit is a signal to read, not a build failure.
    # See the module docstring — some hits are correct behaviour.
    return 0


if __name__ == "__main__":
    sys.exit(main())

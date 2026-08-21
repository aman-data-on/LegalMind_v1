"""Verify the ratified terminology against the source documents themselves.

Every ratified Company Standard under ``backend/config/company_standards/`` was
extracted from a LeapSwitch document (manager's standing rule, 2026-08-19), and
since 2026-08-19 each file also carries the mapping and extraction terminology
that makes its Requirement publishable. This tool closes the loop the tests
cannot: it parses the REAL source document from ``LEGALMIND_SOURCE_MATERIAL_DIR``
(locked 54.6 keeps those files out of version control, so no test may embed
them), runs the locked mapping and extraction pipeline with the file's own
terminology, and requires the pipeline to reproduce the ratified position from
the very document it was ratified from:

* a PRESENCE Requirement must map ``CONFIRMED`` on its source document;
* a NUMERIC Requirement must extract exactly one position for its configured
  scope, and that position must equal the ratified ``preferred``/``unit``/
  ``basis`` — i.e. the document MATCHes the standard taken from it.

A failure means the terminology cannot find or read the very clause it cites —
defective configuration, reported loudly. Absence of the documents is the
normal case away from the owner's machine and exits 0 with a SKIP per file.

This is verification of configuration, not calibration: locked 35.10's
calibration against a *representative counterparty set* remains outstanding and
is not claimed here.

Usage:
    python3 -m tools.verify_terminology
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from legalmind import config
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.extraction.liability import (
    FINITE,
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.ingestion.parsing import parse_pdf
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules

# Deterministic ids so two runs report identically (ENG-11 discipline, applied
# to a tool: these ids never leave this process).
_NS = uuid.UUID("00000000-0000-0000-0000-00000000045e")


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


def _verify_numeric(payload: dict, confirmed: list[Clause]) -> list[str]:
    """Return failure strings; empty means the ratified position was reproduced."""
    cfg = payload["configuration"]
    facts = extract_liability_facts(
        confirmed, LiabilityExtractionConfig.from_config(cfg))
    scope = cfg.get("scope_key")
    positions = {
        (c.cap_status, c.cap_value, c.cap_unit, c.cap_basis)
        for c in facts.caps if c.scope == scope
    }
    expected = (FINITE, float(cfg["preferred"]), cfg["unit"], cfg["basis"])
    failures = []
    if not positions:
        failures.append(
            f"no position extracted for scope {scope!r} "
            f"(status {facts.extraction_status.value}; "
            f"diagnostics: {list(facts.extraction_diagnostics)})")
    elif positions != {expected}:
        failures.append(
            f"extracted {sorted(positions)} for scope {scope!r}, "
            f"ratified position is {expected}")
    return failures


def verify(standards_dir: Path, source_dir: Path) -> tuple[list[str], bool]:
    lines: list[str] = []
    ok = True
    for path in sorted(standards_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        code = payload["requirement_code"]
        mapping_config = payload.get("mapping_rules")
        source_file = payload.get("source_file")
        if not mapping_config or not source_file:
            lines.append(f"FAIL  {code}: no mapping_rules/source_file in the "
                         "ratified file")
            ok = False
            continue

        document = source_dir / source_file
        if not document.exists():
            lines.append(f"SKIP  {code}: {source_file} not present at "
                         f"{source_dir} (normal away from the owner's machine)")
            continue

        rules = MappingRules.from_config(mapping_config)
        result = map_requirement(uuid.uuid5(_NS, code), rules,
                                 _clauses(document))
        if result.state.value != "CONFIRMED":
            lines.append(
                f"FAIL  {code}: mapping state {result.state.value} on "
                f"{source_file} — the terminology cannot find the clause it "
                f"cites ({'; '.join(result.explanation)})")
            ok = False
            continue

        ev_type = payload.get("evaluator_type", "NUMERIC_COMPARISON")
        if ev_type == "PRESENCE":
            lines.append(f"PASS  {code}: CONFIRMED on {source_file} "
                         f"({len(result.candidates)} clause(s))")
            continue

        failures = _verify_numeric(payload, list(result.confirmed_clauses))
        if failures:
            lines.append(f"FAIL  {code}: " + "; ".join(failures))
            ok = False
        else:
            cfg = payload["configuration"]
            lines.append(
                f"PASS  {code}: {source_file} reproduces "
                f"{cfg['preferred']} {cfg['unit']} ({cfg['basis']}) from "
                f"{len(result.candidates)} confirmed clause(s)")
    return lines, ok


def main() -> int:
    source_dir = Path(config.source_material_dir())
    lines, ok = verify(RATIFIED_STANDARDS_DIR, source_dir)
    print("\n".join(lines))
    skips = sum(1 for line in lines if line.startswith("SKIP"))
    passes = sum(1 for line in lines if line.startswith("PASS"))
    fails = sum(1 for line in lines if line.startswith("FAIL"))
    print(f"\n{passes} PASS · {fails} FAIL · {skips} SKIP")
    return 1 if not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())

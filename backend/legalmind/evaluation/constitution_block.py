"""The `constitution` block of a Company Standard — AM-59 (AB-20, 2026-09-13).

Every ratified standard names the Legal Constitution section that states its
position, the Appendix B clause category, and the evidentiary BASIS of that
position in the Constitution's own vocabulary. It is how a Finding cites its
source (§23.5), how applicability finds a sibling position (AM-61), and how a
reader is told when a standard has no Constitution position behind it at all.

Configuration, not code: publish and the importer REFUSE a malformed block the
way they refuse an untyped standard, so analysis can read it as a plain dict.
"""
from __future__ import annotations

import re

#: L1.10 §6.3's three position labels plus §31's, plus the honest sixth: the
#: Constitution states no position and the standard traces to a LeapSwitch
#: document only (AM-43 r5 — reported to Counsel as a gap, not removed).
BASES: frozenset[str] = frozenset({
    "STAKEHOLDER_CONFIRMED",   # §§9-22: Stakeholder Confirmed / Counsel Validation Point
    "APPLICABLE_LAW",          # §12/§19 rows the Constitution marks Applicable Law
    "COMPANY_APPROVED",        # §31: "Company-approved"
    "LEGALMIND_RULE",          # §31 practice-based rule; never Acceptable by guess
    "NOT_ADOPTED",             # §31.6a: "NOT CURRENTLY ADOPTED" — never a current rule
    "DOCUMENT_ONLY",           # no Constitution position; source is a LeapSwitch clause
    "RETIRED",                 # AM-65: withdrawn from active review; history preserved
})

#: AM-65 (owner, 2026-09-14) — the exact words a retired standard must carry, so the
#: reason is in the file rather than only in a lock record.
RETIRED_MARKER = "RETIRED — NOT PRESENT IN CURRENT CONSTITUTION"

_SECTION = re.compile(r"^\d{1,2}(\.\d{1,2}[a-z]?)?$")


def is_retired(payload: dict | None) -> bool:
    """True when the standard file declares itself retired (AM-65).

    Read from the FILE, not from the database: the importer uses it to set
    `Requirement.status = DEPRECATED`, which is what actually keeps the standard
    out of every future configuration snapshot.
    """
    return isinstance((payload or {}).get("retired"), dict)


def retired_block_error(payload: dict | None) -> str | None:
    """None when a `retired` block is well-formed or absent; else the refusal."""
    block = (payload or {}).get("retired")
    if block is None:
        return None
    if not isinstance(block, dict):
        return "retired block is not an object"
    if block.get("marker") != RETIRED_MARKER:
        return f"retired.marker must read exactly {RETIRED_MARKER!r}"
    for field in ("date", "reason", "ruling"):
        if not isinstance(block.get(field), str) or not block[field].strip():
            return f"retired.{field} is required — a retirement without its reason is not a record"
    basis = ((payload or {}).get("configuration") or {}).get("constitution", {}).get("basis")
    if basis != "RETIRED":
        return "a retired standard must declare constitution.basis RETIRED"
    return None


def constitution_block_error(configuration: dict | None) -> str | None:
    """None when the block is well-formed (or absent — a pre-AM-59 snapshot);
    otherwise the sentence publish and the importer refuse with."""
    block = (configuration or {}).get("constitution")
    if block is None:
        return None
    if not isinstance(block, dict):
        return "constitution block is not an object"
    section = block.get("section")
    if section is not None and not (isinstance(section, str) and _SECTION.match(section)):
        return f"constitution.section {section!r} is not a Constitution section reference"
    if not isinstance(block.get("topic"), str) or not block["topic"].strip():
        return "constitution.topic must name the Appendix B clause category"
    if block.get("basis") not in BASES:
        return (f"constitution.basis {block.get('basis')!r} is not one of "
                + ", ".join(sorted(BASES)))
    if section is None and block.get("basis") not in ("DOCUMENT_ONLY", "RETIRED"):
        return "a standard with no Constitution section can only have basis DOCUMENT_ONLY"
    when = block.get("expected_when")
    if when is not None:
        codes = (when or {}).get("confirmed_any") if isinstance(when, dict) else None
        if (not isinstance(codes, list)
                or not all(isinstance(c, str) and c for c in codes)):
            return "constitution.expected_when.confirmed_any must list requirement codes"
    return None

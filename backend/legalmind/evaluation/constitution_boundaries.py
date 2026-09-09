"""Constitution-defined Unacceptable Positions — the two that are checkable.

AB-14 (`AM-43`) makes the Legal Constitution L1.5 the governing source of
company positions. Seven of its clause topics (Sections 9-16) each state an
explicit "Unacceptable Position" — the Constitution's own words for "this
clearly goes against an approved company requirement," distinct from an
ordinary deviation that a person can bring into line by editing the clause.

Only the two entries below are wired, because they are the only ones stated
as a condition this engine can check mechanically from a value it already
extracts (rules 7/21: never invent a threshold the Constitution did not
state). The other five Unacceptable Position paragraphs are qualitative —
Indemnification s.10 ("without specific approval"), SLA remedies s.11
("shorter than operationally feasible"), Data Protection s.12 ("no defined
... timeline at all"), Confidentiality directionality s.15 ("one-directional
... protecting only one party" — a mutuality fact this engine does not
extract), Payment/suspension s.16 ("materially less favorable"). A DEVIATION
against those Company Standards stays NEEDS REVIEW until Counsel gives a
checkable rule for it. Extending this table is a rule 6 change: name the
section, quote the Constitution's own words, and get the owner's yes.
"""
from __future__ import annotations

from typing import Any

ConstitutionProhibition = dict[str, str]

_LIABILITY_CODES = {"LIABILITY-MSA-001", "LIABILITY-TOS-001"}
_RETRIEVAL_CODES = {"DATA-RETRIEVAL-TOS-001"}

# Each paragraph has two limbs; only the FIRST is checked here (an unlimited
# cap; a window under 30 days). The citation shows the limb that fired, with
# the elision marked, so a reader is never told the unchecked limb applied.
_LIABILITY_QUOTE = "An uncapped/unlimited liability term […]"
_RETRIEVAL_QUOTE = "A post-termination data-export window shorter than 30 days […]"


def constitution_prohibition_for(requirement_code: str | None,
                                 actual_value: Any) -> ConstitutionProhibition | None:
    """The Constitution citation for this evaluated fact, or None.

    Deliberately narrow — matches only the exact condition the Constitution's
    own Unacceptable Position text names, for the two Company Standards whose
    evaluator already extracts that exact fact. Anything else (a requirement
    code not in either set, a value shape this function does not recognise)
    returns None, which the caller reads as NEEDS REVIEW rather than NOT
    ACCEPTED — the honest default when no rule is stated, per rule 15.
    """
    if not requirement_code or not isinstance(actual_value, dict):
        return None
    if requirement_code in _LIABILITY_CODES:
        if actual_value.get("cap_status") == "UNLIMITED":
            return {"section": "9", "quote": _LIABILITY_QUOTE}
        return None
    if requirement_code in _RETRIEVAL_CODES:
        value = actual_value.get("cap_value")
        unit = actual_value.get("cap_unit")
        if isinstance(value, (int, float)) and unit == "DAYS" and value < 30:
            return {"section": "13", "quote": _RETRIEVAL_QUOTE}
        return None
    return None

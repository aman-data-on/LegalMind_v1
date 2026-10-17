"""What the Constitution says about enforcing a clause's term — a note beside a Finding,
never a Finding (AM-159, 2026-10-17).

Each note is a verbatim sentence of the Legal Constitution with its section. Where the
Constitution states none (a restraint such as non-circumvention: no line of it names
Contract Act s.27), the note says only that Counsel confirms enforceability. Legal Mind
never asserts that a term is, or is not, enforceable (§29.1.1 item 5: "a Counsel
determination … never asserted by Legal Mind itself").
"""
from __future__ import annotations

COUNSEL = "Counsel to confirm enforceability"

#: requirement-code stem -> (section, the Constitution's own words)
_NOTES: dict[str, tuple[str | None, str]] = {
    "EARLY-TERM-RESTRICTION": ("29.1.1", "A stated contractual amount or term is not "
                               "automatically the legally recoverable or enforceable one "
                               "(Section 28.4.1)."),
    "LATE-FEE": ("28.6", "Subject to usury/penalty case law under Contract Act 1872"),
    "NON-SOLICIT": ("15", "Legal Counsel should verify and finalize the clause wording "
                    "and confirm the enforceability of the 2-year non-solicitation "
                    "clause under applicable law."),
    "NON-CIRCUMVENTION": (None, COUNSEL),
}


def note_for(requirement_code: str | None) -> dict[str, str | None] | None:
    """The enforceability note for a Requirement, or None when its topic has none."""
    if not requirement_code:
        return None
    stem = requirement_code.rsplit("-", 2)[0] if requirement_code.count("-") >= 2 \
        else requirement_code
    note = _NOTES.get(stem)
    return {"section": note[0], "text": note[1]} if note else None

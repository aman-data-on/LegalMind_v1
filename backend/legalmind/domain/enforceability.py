"""What the Constitution says about enforcing a clause's term — a note beside a Finding,
never a Finding (AM-159, 2026-10-17).

Each note is a verbatim sentence of the Legal Constitution with its section. Where the
Constitution states none (a restraint such as non-circumvention: no line of it names
Contract Act s.27), the note says only that Counsel confirms enforceability. Legal Mind
never asserts that a term is, or is not, enforceable (§29.1.1 item 5: "a Counsel
determination … never asserted by Legal Mind itself").

`AM-242` (AB-139, 2026-10-30): a note may also carry `law` — the provision of a SUPPLIED
statute (`legal-docs/Indian_Laws_and_Acts/`) that bears on the term, quoted verbatim with
its section, as background law beside the Constitution's words. Still a note for Counsel,
never a conclusion; no case law is quoted (none is supplied source material, rule 21).
"""
from __future__ import annotations

COUNSEL = "Counsel to confirm enforceability"

_ICA = "Indian Contract Act, 1872"
_DPDP_RULES = "Digital Personal Data Protection Rules, 2025"
_S74 = (
    _ICA, "74",
    "the party complaining of the breach is entitled, whether or not actual "
    "damage or loss is proved to have been caused thereby, to receive from the "
    "party who has broken the contract reasonable compensation not exceeding the "
    "amount so named")
_S74_INTEREST = (
    _ICA, "74, Explanation",
    "A stipulation for increased interest from the date of default may be a "
    "stipulation by way of penalty.")
_S27 = (
    _ICA, "27",
    "Every agreement by which any one is restrained from exercising a lawful "
    "profession, trade or business of any kind, is to that extent void.")
_S28 = (
    _ICA, "28(b)",
    "which extinguishes the rights of any party thereto, or discharges any party "
    "thereto, from any liability, under or in respect of any contract on the "
    "expiry of a specified period so as to restrict any party from enforcing his "
    "rights, is void to the extent.")
_DPDP_8_3 = (
    _DPDP_RULES, "8(3), in force under rule 1(4)",
    "a Data Fiduciary shall retain, in respect of any processing of personal data "
    "undertaken by it or on its behalf by a Data Processor, such personal data, "
    "associated traffic data and other logs of the processing for a minimum "
    "period of one year from the date of such processing, for the purposes as "
    "specified in the Seventh Schedule")

#: requirement-code stem -> (section, the Constitution's own words, the statute or None)
_NOTES: dict[str, tuple[str | None, str, tuple[str, str, str] | None]] = {
    "EARLY-TERM-RESTRICTION": ("29.1.1", "A stated contractual amount or term is not "
                               "automatically the legally recoverable or enforceable one "
                               "(Section 28.4.1).", _S74),
    "LATE-FEE": ("28.6", "Subject to usury/penalty case law under Contract Act 1872",
                 _S74_INTEREST),
    "LATE-INTEREST": (None, COUNSEL, _S74_INTEREST),
    "NON-SOLICIT": ("15", "Legal Counsel should verify and finalize the clause wording "
                    "and confirm the enforceability of the 2-year non-solicitation "
                    "clause under applicable law.", _S27),
    "NON-CIRCUMVENTION": (None, COUNSEL, _S27),
    "DISPUTE-WINDOW": (None, COUNSEL, _S28),
    "CLAIM-WINDOW": (None, COUNSEL, _S28),
    "DATA-PURGE": (None, COUNSEL, _DPDP_8_3),
    "DATA-RETRIEVAL": (None, COUNSEL, _DPDP_8_3),
}


def note_for(requirement_code: str | None) -> dict | None:
    """The enforceability note for a Requirement, or None when its topic has none."""
    if not requirement_code:
        return None
    stem = requirement_code.rsplit("-", 2)[0] if requirement_code.count("-") >= 2 \
        else requirement_code
    note = _NOTES.get(stem)
    if not note:
        return None
    law = note[2]
    return {"section": note[0], "text": note[1],
            **({"law": {"source": law[0], "section": law[1], "quote": law[2]}}
               if law else {})}

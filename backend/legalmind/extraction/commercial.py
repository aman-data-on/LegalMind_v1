"""The commercial facts a contract states: fee, committed term, their value (AM-152).

The business reader's question about a customer's redline is "how much money is at
stake". These are read from the document's own words, deterministically, each with the
clause it came from: the periodic fee ("Rs. 7,57,000.00 + … Per Month", "₹ 7,57,000.00
/mo") and the committed term ("Contract Agreement: 1 Year", "Contract Duration Annual",
"an initial term of 36 months"). The committed value is their product — arithmetic on
two cited figures, never a legal position, and never sent to a model (AM-30 t3). A
figure the words do not state is absent, never estimated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

_AMOUNT = r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
#: A fee per month: the amount, then within the same line (GST and the like may sit
#: between) "per month", "/mo", "/month" or "monthly".
_MONTHLY = re.compile(
    _AMOUNT + r"[^\n]{0,60}?(?:per\s+month|/\s*mo(?:nth)?\b|\bmonthly\b)", re.I)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "twelve": 12,
          "eighteen": 18, "twenty-four": 24, "thirty-six": 36}
#: A committed term the document states for the contract itself — as a heading value
#: ("Contract Agreement: 1 Year"), a definition ('"Initial Term" shall mean a period of 12
#: months') or a template's bracketed value ("The initial term is [one (1) year]").
_TERM = re.compile(
    r"(?:contract\s+(?:agreement|term|duration|period|tenure)|initial\s+term|committed\s+term"
    r"|minimum\s+(?:service|commitment)\s+(?:period|term)|lock-?\s?in\s+period"
    r"|service\s+period)"
    r"[\"\u201d\u2019']?\s*(?:shall\s+(?:be|mean)|means|is|of|:|-)?\s*(?:a\s+period\s+of\s+)?"
    r"\\?\[?\s*(\d{1,2}|" + "|".join(_WORDS) + r")\s*\(?\d*\)?\s*"
    r"(?:\\?\[[a-z]+\\?\]\s*)?(year|month)s?\b", re.I)
_ANNUAL = re.compile(r"contract\s+(?:duration|term|agreement)\s*:?\s*annual\b", re.I)
#: GST stated on top of the fee ("+ Rs. 1,36,260 (GST)", "plus GST", "exclusive of GST");
#: only then is the fee said to exclude it — never assumed (review, 2026-10-16).
_PLUS_GST = re.compile(r"\+[^\n+]{0,30}?\bgst\b|\bplus\s+gst\b|\bexclusive\s+of\s+gst\b"
                       r"|\bexcl(?:\.|uding)?\s+(?:of\s+)?gst\b", re.I)


@dataclass(frozen=True)
class CommercialFacts:
    fee_per_month: float | None = None
    fee_text: str | None = None
    fee_evidence: UUID | None = None
    term_months: int | None = None
    term_text: str | None = None
    term_evidence: UUID | None = None

    @property
    def excludes_gst(self) -> bool:
        """Whether the fee's own words put GST on top of it."""
        return bool(self.fee_text and _PLUS_GST.search(self.fee_text))

    @property
    def committed_value(self) -> float | None:
        """Fee × term, when the document states both — the money a fixed term commits."""
        if self.fee_per_month is None or self.term_months is None:
            return None
        return self.fee_per_month * self.term_months


def _number(text: str) -> float:
    return float(text.replace(",", ""))


def read(clauses) -> CommercialFacts:
    """The first monthly fee and the first committed term the document states, each
    with its evidence row. Order is the document's (ENG-11)."""
    fee = term = None
    for clause in clauses:
        content = clause.content or ""
        if fee is None and (m := _MONTHLY.search(content)):
            fee = (_number(m.group(1)), " ".join(m.group(0).split()), clause.evidence_id)
        if term is None:
            if (m := _TERM.search(content)):
                n = m.group(1).lower()
                count = _WORDS.get(n) or int(n)
                months = count * 12 if m.group(2).lower() == "year" else count
                term = (months, " ".join(m.group(0).split()), clause.evidence_id)
            elif (m := _ANNUAL.search(content)):
                term = (12, " ".join(m.group(0).split()), clause.evidence_id)
        if fee and term:
            break
    return CommercialFacts(
        fee_per_month=fee[0] if fee else None, fee_text=fee[1] if fee else None,
        fee_evidence=fee[2] if fee else None,
        term_months=term[0] if term else None, term_text=term[1] if term else None,
        term_evidence=term[2] if term else None)


def states_fixed_term(clauses) -> bool:
    """Whether the document commits to a term — Constitution §14's Scope of Application
    ("services supplied against a fixed-term commercial commitment")."""
    return read(clauses).term_months is not None


def rupees(amount: float) -> str:
    """₹ in the Indian grouping the documents use: 9084000 -> "₹90,84,000"."""
    whole = f"{amount:.0f}"
    head, tail = whole[:-3], whole[-3:]
    pairs = [head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1]
    return "₹" + ",".join([*pairs, tail])

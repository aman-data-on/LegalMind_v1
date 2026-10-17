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

_AMOUNT = (r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
           r"(?:\s*(lakhs?|lacs?|crores?|cr)\b)?")
_SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
          "crore": 1e7, "crores": 1e7, "cr": 1e7}
#: Words that make an amount something other than a monthly fee, before it or between it
#: and "per month": "Annual fee of Rs. 6,00,000 payable monthly", "Setup: Rs. 25,000
#: (one time). Recurring: …" — never read as the monthly figure (review, 2026-10-17).
_NOT_MONTHLY = re.compile(r"\b(?:annual\w*|annum|yearly|per\s+year|one[\s-]?time|set-?up|"
                          r"installation|deposit|advance\s+of)\b"
                          r"|(?<!\brs)(?<!\binr)\.\s", re.I)
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
    r"\\?\[?\s*(\d{1,2}|" + "|".join(_WORDS) + r")\s*\\?\]?\s*\(?\d*\)?\s*"
    r"(?:\\?\[[a-z]+\\?\]\s*)?(year|month)s?\b", re.I)
_ANNUAL = re.compile(r"contract\s+(?:duration|term|agreement)\s*:?\s*annual\b", re.I)
#: GST stated on top of the fee ("+ Rs. 1,36,260 (GST)", "plus GST", "exclusive of GST");
#: only then is the fee said to exclude it — never assumed (review, 2026-10-16).
_PLUS_GST = re.compile(r"\+[^\n+]{0,30}?\bgst\b|\bplus\s+gst\b|\bexclusive\s+of\s+gst\b"
                       r"|\bexcl(?:\.|uding)?\s+(?:of\s+)?gst\b", re.I)


#: A figure the parties have not agreed yet: a bracketed value ("[30]", "\\[one (1)
#: year\\]") or a blank ("_____ months"). Never read as a term (AM-156).
_PLACEHOLDER = re.compile(r"(?:\\?_){3,}")
#: A fee priced per unit — a monthly figure that is not the contract's value.
_PER_UNIT = re.compile(r"\b(?:per|each|for\s+each|for\s+every)\s+(?:server|gpu|node|unit|"
                       r"instance|vm|core|user|seat|rack|"
                       r"device|licen[cs]e)\b", re.I)
#: Fees the document leaves to another paper — said so, rather than "no fee stated".
_ELSEWHERE = re.compile(r"\b(?:fees?|charges?|pricing|prices?)\b[^.]{0,80}?\b(?:"
                        r"purchase\s+order|order\s+form|work\s+order|"
                        r"statement\s+of\s+work|annexure|schedule)", re.I)
#: A refund of prepaid fees on exit — a cash-flow line, never a figure (AM-156 R6).
_REFUND = re.compile(r"\brefund\w*\b[^.\n]{0,200}?\bpro[\s-]?rata\b|"
                     r"\bpro[\s-]?rata\b[^.\n]{0,200}?\brefund\w*\b", re.I)


@dataclass(frozen=True)
class CommercialFacts:
    fee_per_month: float | None = None
    fee_text: str | None = None
    fee_evidence: UUID | None = None
    term_months: int | None = None
    term_text: str | None = None
    term_evidence: UUID | None = None
    #: Why no committed value can be stated, in the reader's words — None when it can.
    missing: str | None = None
    #: Whether any agreed (not blank, not bracketed) term is stated — Constitution §14's
    #: scope, which two different terms do not remove (initial term + lock-in).
    term_stated: bool = False
    #: The document's own sentence on refunding prepaid fees, and its clause.
    refund_text: str | None = None
    refund_evidence: UUID | None = None

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


def _number(text: str, scale: str | None = None) -> float:
    return float(text.replace(",", "")) * _SCALE.get((scale or "").lower(), 1)


def _placeholder(text: str) -> bool:
    """A blank, or a bracket holding the only statement of the figure ("[30]", "\\[one
    (1) year\\]") — but not a word repeating a number already stated ("01 [ONE] Year")."""
    if _PLACEHOLDER.search(text):
        return True
    outside = re.sub(r"\\?\[[^\]]*(?:\\?\]|$)", " ", text)   # an unclosed one too
    return "[" in text and not re.search(r"\d", outside)


def _sentence(content: str, start: int, end: int) -> str:
    """The sentence holding ``content[start:end]``, whole."""
    lo = content.rfind(". ", 0, start)
    lo = lo + 2 if lo >= 0 else 0
    hi = content.find(". ", end)
    return " ".join(content[lo:hi + 1 if hi >= 0 else len(content)].split())


def read(clauses) -> CommercialFacts:
    """The monthly fee and the committed term the document states, each with its
    evidence row, in the document's order (ENG-11) — but a figure only when it is
    unambiguous (AM-156 R1): exactly one monthly rupee fee, not priced per unit, and
    one fixed term, neither bracketed nor blank. Otherwise ``missing`` says why, in the
    reader's words, and no value is stated: a figure is never estimated."""
    fees: list[tuple[float, str, UUID, bool, bool]] = []
    terms: list[tuple[int, str, UUID]] = []
    refund = elsewhere = None
    for clause in clauses:
        content = clause.content or ""
        if elsewhere is None and (m := _ELSEWHERE.search(content)):
            elsewhere = m.group(0)
        for m in _MONTHLY.finditer(content):
            # what precedes the amount and what lies between it and "per month": an
            # annual, one-time or set-up amount, or a second amount (other than the
            # GST beside the fee), is never the monthly fee — the figure is withheld
            gap = m.group(0)[m.end(2 if m.group(2) else 1) - m.start():]
            others = [a for a in re.finditer(_AMOUNT, gap, re.I)
                      if not re.search(r"\bgst\b", gap[a.end():a.end() + 12], re.I)]
            tail = content[m.end():m.end() + 40]
            before = content[max(0, m.start() - 30):m.start()]
            fees.append((_number(m.group(1), m.group(2)), " ".join(m.group(0).split()),
                         clause.evidence_id,
                         bool(_NOT_MONTHLY.search(before) or _NOT_MONTHLY.search(gap)
                              or others),
                         bool(_PER_UNIT.search(m.group(0) + tail))))
        if (m := _TERM.search(content)):
            n = m.group(1).lower()
            count = _WORDS.get(n) or int(n)
            months = count * 12 if m.group(2).lower() == "year" else count
            terms.append((months, " ".join(m.group(0).split()), clause.evidence_id))
        elif (m := _ANNUAL.search(content)):
            terms.append((12, " ".join(m.group(0).split()), clause.evidence_id))
        if refund is None and (m := _REFUND.search(content)):
            refund = (_sentence(content, m.start(), m.end()), clause.evidence_id)
    fee, term = (fees[0] if fees else None), (terms[0] if terms else None)
    missing = None
    if fee is None:
        missing = ("the fees are set out in another document (a purchase order, order "
                   "form or schedule) that is not part of this one" if elsewhere
                   else "the document states no monthly fee in rupees")
    elif len({f[0] for f in fees}) > 1:
        missing = "the document states more than one monthly fee"
    elif fee[3]:
        missing = "the fee wording is not a single monthly figure"
    elif fee[4]:
        missing = "the fee is priced per unit, not for the whole contract"
    elif _placeholder(fee[1]):
        missing = "the fee is left blank or in brackets"
    agreed = [t for t in terms if not _placeholder(t[1])]
    if term is not None and (_placeholder(term[1]) or len({t[0] for t in terms}) > 1):
        missing = missing or ("the term is left blank or in brackets"
                              if _placeholder(term[1])
                              else "the document states more than one term")
        term = None                         # no single agreed term: no value from it
    elif term is None:
        missing = missing or "the document states no fixed term"
    return CommercialFacts(
        fee_per_month=fee[0] if fee and not missing else None,
        fee_text=fee[1] if fee else None, fee_evidence=fee[2] if fee else None,
        term_months=term[0] if term else None, term_text=term[1] if term else None,
        term_evidence=term[2] if term else None, missing=missing,
        term_stated=bool(agreed),
        refund_text=refund[0] if refund else None,
        refund_evidence=refund[1] if refund else None)


def not_committed(facts: CommercialFacts, notice_days: float | None) -> float | None:
    """AM-156 R2 — what a customer who may leave on notice, owing nothing more, leaves
    uncommitted: the fee for the term less the fee for the notice period. Calendar
    days only; None when either figure is not stated."""
    if facts.committed_value is None or facts.fee_per_month is None:
        return None
    left = facts.committed_value - facts.fee_per_month * (notice_days or 0) / 30
    return left if left > 0 else None       # notice as long as the term leaves nothing


def states_fixed_term(clauses) -> bool:
    """Whether the document commits to a term — Constitution §14's Scope of Application
    ("services supplied against a fixed-term commercial commitment"). Any agreed term
    counts — an initial term beside a lock-in is still a commitment; only a blank or
    bracketed term is not (AM-156)."""
    return read(clauses).term_stated


def rupees(amount: float) -> str:
    """₹ in the Indian grouping the documents use: 9084000 -> "₹90,84,000"."""
    whole = f"{amount:.0f}"
    head, tail = whole[:-3], whole[-3:]
    pairs = [head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1]
    return "₹" + ",".join([*pairs, tail])

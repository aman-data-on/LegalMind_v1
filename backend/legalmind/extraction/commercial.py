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

from legalmind.extraction.liability import _NUMBER_WORD, parse_number

#: A rupee amount: a currency word standing alone ("servers 4" is not "rs 4"), and the
#: whole number ("Rs. 15000" is 15000, never "150" with the rest left over).
_AMOUNT = (r"(?:₹|(?<![a-z])(?:rs\.?|inr)(?![a-z]))\s*"
           r"(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?(?!,?\d)|\d+(?:\.\d+)?(?!,?\d))"
           r"(?:\s*(lakhs?|lacs?|l|crores?|cr|thousand|k|millions?|mn)\b)?")
_SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "crore": 1e7,
          "crores": 1e7, "cr": 1e7, "thousand": 1e3, "k": 1e3, "million": 1e6,
          "millions": 1e6, "mn": 1e6}
#: Words that make an amount something other than a monthly fee, before it or between it
#: and "per month": "Annual fee of Rs. 6,00,000 payable monthly", "Setup: Rs. 25,000
#: (one time). Recurring: …" — never read as the monthly figure (review, 2026-10-17).
_NOT_MONTHLY_WORDS = (r"\b(?:annual\w*|annum|yearly|per\s+year|one[\s-]?time|set-?up|"
                      r"installation|deposit|advance\s+of)\b")
_NOT_MONTHLY = re.compile(_NOT_MONTHLY_WORDS + r"|(?<!\brs)(?<!\binr)\.\s", re.I)
#: The cross-line window only withholds on those words — a sentence ending above the
#: amount ("4.1 Fees. The Customer shall pay …") says nothing about it (review r29).
_NOT_MONTHLY_ABOVE = re.compile(_NOT_MONTHLY_WORDS, re.I)
#: A fee per month: the amount, then within the same line (GST and the like may sit
#: between) "per month", "/mo", "/month" or "monthly".
_MONTHLY = re.compile(
    _AMOUNT + r"[^\n]{0,60}?(?:per\s+(?:calendar\s+)?month|per\s+mensem|/\s*mo(?:nth)?\b|"
    r"\bmonthly\b)", re.I)
#: A number in words, one to ninety-nine ("ten", "thirty-six") — the liability
#: extractor's own reading, never a second list (AM-54: a numeral, not terminology).
_WORDS = _NUMBER_WORD
#: A committed term the document states for the contract itself — as a heading value
#: ("Contract Agreement: 1 Year"), a definition ('"Initial Term" shall mean a period of 12
#: months') or a template's bracketed value ("The initial term is [one (1) year]").
_TERM = re.compile(
    r"(?:contract\s+(?:agreement|term|duration|period|tenure)|initial\s+term|committed\s+term"
    r"|minimum\s+(?:service|commitment)\s+(?:period|term)|lock-?\s?in\s+period"
    # "Service Period" as the contract's term, never an SLA's recurring measurement
    # window ("for each Service Period of one (1) month", "over a service period")
    r"|(?<!\beach\s)(?<!\bevery\s)(?<!\bper\s)(?<!\bover\sa\s)(?<!\bduring\sa\s)"
    r"service\s+period"
    # "This Agreement shall remain in force for a period of three (3) years"
    r"|(?:agreement|contract)\s+shall\s+(?:remain\s+in\s+(?:full\s+)?force(?:\s+and\s+"
    r"effect)?|continue(?:\s+in\s+force)?)\s+for)"
    r"[\"\u201d\u2019']?\s*(?:shall\s+(?:be|mean)|means|is|of|:|-)?\s*(?:a\s+period\s+of\s+)?"
    r"\\?\[?\s*(\d{1,3}(?!\d)|" + _WORDS + r")\s*\\?\]?\s*(?:\(\s*\d+\s*\)\s*)?"
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
#: AM-156 (final review, 2026-10-17) — an ALLOW-LIST, failing closed. An amount is the
#: contract's monthly fee only when its own line, sentence or table cell NAMES it as the
#: fee; anything that marks it as something else makes the figure ambiguous and withheld.
#: A blocklist of bad words never converged: contracts always found another wording.
_FEE_LABEL = re.compile(
    r"\b(?:fees?|charges?|costing|cost|price|pricing|rate|rental|rent|subscription|mrc|"
    r"recurring|tariff|consideration|pay(?:s|able|ment)?|billed|invoiced?)\b", re.I)
#: A charge on default, an adjustment, a quantity or a unit price: never the fee.
_NOT_THE_FEE = re.compile(
    r"\b(?:interest|late|overdue|penalt\w*|delay\w*|default|discount|rebate|credits?|"
    r"refund\w*|deposit|liabilit\w*|damages|indemn\w*|compensation|qty|quantity|"
    r"unit\s+price|per\s+(?!month|annum|year|cent|"
    r"calendar)\w+|(?:for\s+)?(?:each|every)\s+\w+|\d+\s*[x\u00d7])\b|\|\s*\d+\s*\|",
    re.I)
#: A unit price or a quantity in the amount's own words: the fee is per unit.
_PER_UNIT_WORD = re.compile(
    r"\bqty\b|\bquantity\b|\bunit\s+price\b|\bper\s+(?!month|annum|year|cent|calendar)\w+|"
    r"\b(?:each|every)\s+\w+|\d+\s*[x\u00d7]|\|\s*\d+\s*\|", re.I)
#: Fees the document leaves to another paper — said so, rather than "no fee stated".
_ELSEWHERE = re.compile(r"\b(?:fees?|charges?|pricing|prices?)\b[^.]{0,80}?\b(?:"
                        r"purchase\s+order|order\s+form|work\s+order|"
                        r"statement\s+of\s+work|annexure|schedule)", re.I)
#: A refund of prepaid fees on exit — a cash-flow line, never a figure (AM-156 R6).
_REFUND = re.compile(r"\brefund\w*\b[^.\n]{0,200}?\bpro[\s-]?rata\b|"
                     r"\bpro[\s-]?rata\b[^.\n]{0,200}?\brefund\w*\b", re.I)


#: AM-156 r29 — what makes a NAMED fee something other than the contract's whole monthly
#: fee: an exit or optional charge, a part of the term, a price that changes, a
#: multiplier or a slash-unit after the amount ("x 4", "/server/month"), or a sum spread
#: over the term ("Rs. 6,00,000 payable in 12 equal monthly instalments", r32).
_NOT_BASE = re.compile(
    r"\b(?:termination|cancell?ation|exit|early|unexpired|remaining|additional|optional|"
    r"add-?ons?|extra|excess|overage|usage|upgrades?|phase|escalat\w*|increas\w*|"
    r"revis\w*|thereafter|first\s+(?:\w+\s+){0,2}(?:months?|years?|quarters?)|"
    r"initial(?!\s+term)|waived?|year\s+\d|bi-?monthly|semi-?monthly|instal\w*|"
    r"install?ments?|equal|total|aggregate|for\s+(?:the|a|its)\s+(?:whole\s+|entire\s+)?"
    r"(?:term|period|tenure)|for\s+a\s+period\s+of|"
    r"fortnightly)\b"
    r"|[x\u00d7*]\s*\d|/\s*(?!mo(?:nth)?\b)[a-z]{2,}", re.I)
#: AM-156 r30 — the census is INVERTED: every rupee amount in the document counts against
#: the fee unless its own line positively makes it something else — an adjustment
#: (interest, a credit, a deposit …), a one-time charge, a liability figure, a tax line or
#: a total. A wording nobody listed can therefore only withhold, never add a figure. Any
#: second amount withholds, even at the same price, unless the document's own totals
#: confirm the fee; and a total that is not the fee withholds it (r31).
_NOT_A_FEE = re.compile(
    r"\b(?:interest|late|overdue|penalt\w*|delay\w*|default|credits?|"
    r"refund\w*|deposit|one[\s-]?time|set-?up|installation|liabilit\w*|damages|"
    r"indemn\w*)\b", re.I)
_TOTAL = re.compile(r"\b(?:sub-?\s?total|grand\s+total|total)\b", re.I)
#: A number before a period word ("10,000 per month", "1.5 lakh per month", "10000
#: rupees per month") — an amount, though its currency word was dropped (r31).
_BARE = re.compile(r"(?<![\w.,])(\d+(?:,\d{2,3})*(?:\.\d+)?)\s*(lakhs?|lacs?|l|crores?|"
                   r"cr|thousand|k|millions?|mn)?\b\s*(rupees|/-)?\s*(?=(?:per\b|"
                   r"p\.?\s?[maq]\.?(?!\w)|p/[mq]\b|a\s+month\b|(?:bi-?|semi-?)?monthly\b|"
                   r"quarterly\b|/\s*mo|every\s+(?:month|quarter)|each\s+month))", re.I)
#: The amount IS the tax ("+ Rs. 1,36,260 (GST)", "₹ 9,000 GST @18%") — not "(GST extra)".
_IS_TAX = re.compile(r"\s*\(?\s*(?:gst|[cis]gst|tax)\s*(?:\)|@|\d|$|[,;|])", re.I)
_TAX_ROW = re.compile(r"[\s|]*(?:tax|gst|[cis]gst)\b", re.I)
#: A fee in another currency: never converted, never left out.
_FOREIGN = re.compile(r"(?:\busd\b|\beur\b|\bgbp\b|[$\u20ac\u00a3])\s*\d", re.I)
#: The document lets the price change during the term — unless the change verb itself is
#: denied ("the fees shall not be increased", "no escalation"); "fixed for the first
#: twelve months and thereafter increased" is still a change (r31).
_CHANGE_VERB = (r"escalat\w*|increas\w*|revis\w*|hike\w*|enhanc\w*|uplift\w*|rais\w*|"
                r"adjust\w*|index\w*|cpi|step-?up\w*|chang\w*|modif\w*|var(?:y|ies|ied|"
                r"iation)|amend\w*|increment\w*|review\w*|go(?:es)?\s+up")
_PRICE_WORD = (r"fees?|charges?|prices?|pricing|rates?|tariffs?|rent(?:als?)?|mrc|"
               r"amounts?|cost(?:ing)?s?|subscriptions?|consideration")
_PRICED = re.compile(rf"\b(?:{_PRICE_WORD})\b", re.I)
_CHANGES = re.compile(rf"\b(?:{_CHANGE_VERB})\b", re.I)
#: Something taken off the price — a discount, a rebate, a waived or free period (r35).
_REDUCED = re.compile(r"\b(?:discount\w*|rebate\w*|waiv\w*|free\s+of\s+(?:charge|cost)|"
                      r"complimentary)\b", re.I)
_EXIT = re.compile(r"\b(?:terminat\w*|exit|lock-?\s?in|cancell?ation|unexpired)\b", re.I)
#: A price that follows a change of SCOPE ("if the resources are upgraded or downgraded …
#: the Service price will change accordingly", "an approved Change Request") is not a
#: change to the committed fee for the configuration stated (r34).
_SCOPE_CHANGE = re.compile(r"\b(?:upgrad\w*|downgrad\w*|change\s+requests?|additional\s+"
                           r"(?:resources|services)|scope)\b", re.I)
#: A stated price validity ("Pricing … is valid for a period of 1 year and may be subject
#: to change thereafter"): a change after it is outside a term no longer than it.
_VALID_FOR = re.compile(r"\b(?:valid|fixed|locked|firm)\s+(?:only\s+)?for\s+"
                        r"(?:the\s+first\s+|a\s+period\s+of\s+)?(\d{1,3}|"
                        + _WORDS + r")\s*(?:\(\s*\d+\s*\)\s*)?(year|month)s?\b",
                        re.I)
#: A price fixed only for a first period, or the then-prevailing rates after it ("Fees
#: are fixed only for the first year", "After the first year, … list prices shall apply").
_FIRST_PERIOD = re.compile(
    r"\b(?:for|after)\s+the\s+first\s+(?:(\d{1,3}|" + _WORDS
    + r")\s*(?:\(\s*\d+\s*\)\s*)?)?(year|month)s?\b", re.I)
_PREVAILING = re.compile(r"\b(?:then[\s-]?)?(?:prevailing|current|standard|list)\s+"
                         r"(?:rates?|prices?|pricing|tariffs?|charges)\b[^.]{0,30}?\bapply",
                         re.I)
_RISE = r"(?:increase|hike|escalation|uplift|increment|rise)"
_PCT_CHANGE = re.compile(rf"\d+(?:\.\d+)?\s*%\s+(?:[\w-]+\s+){{0,3}}?{_RISE}|"
                         rf"{_RISE}\w*\s+(?:of\s+|by\s+)?\d+(?:\.\d+)?\s*%", re.I)
#: A change verb denied right before it ("shall not be increased", "no escalation").
_DENIED = re.compile(r"\b(?:not|no|never|nor)\s+(?:\w+\s+){0,2}$", re.I)
#: A duration that goes on ("2 years 6 months", "1 year and 6 months") is not one figure.
_MORE_TERM = re.compile(
    r"\s*(?:\([^)]{0,30}\)\s*)?(?:,|;|and|plus|\+|&)?\s*(?:\d{1,3}|" + _WORDS
    + r")\s*(?:\(\s*\d+\s*\)\s*)?(?:year|month)s?\b", re.I)


#: AM-156 r34 — the SHAPE of a fee statement, the last gate. Six review rounds found a
#: new wording each time ("p.a., payable monthly", "@ Rs. 25,000/- per month each", "Rs.
#: 50 thousands"), so a figure is now stated only when its line has a plain shape: a
#: label and a colon (or "The Customer shall pay [a monthly fee of]"), the amount, at most
#: GST or "(Rupees … only)" before the period, and at most GST, "in advance", "[PREPAID]"
#: or the fee's own name after it. Anything else withholds; it can never add a figure.
_PERIOD_END = re.compile(r"(?:per\s+(?:calendar\s+)?month|per\s+mensem|/\s*mo(?:nth)?\b|"
                         r"\bmonthly\b)\s*$", re.I)
_LABEL = re.compile(
    r"\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:"
    r"[a-z][a-z()&/' .-]{0,60}?\s*[:\u2013-]"                       # "Service Costing:"
    r"|(?:the\s+)?(?:customer|client)\s+(?:shall|will|agrees\s+to)\s+pay\s+(?:(?:a|an|the)"
    r"\s+)?(?:monthly\s+|recurring\s+)?(?:(?:service|subscription|rental)\s+)?(?:fees?|"
    r"charges?|rental|subscription)?\s*(?:of)?"              # "… shall pay a fee of"
    r"|(?:[a-z]+\s+){0,3}[a-z]+"                              # "Charges INR …"
    r"|(?:\|\s*[a-z][a-z ()&/.-]*)+\|"                        # a table's label cells
    r")?\s*", re.I)
_GAP_OK = re.compile(
    r"\s+|/-|only|\(\s*rupees[^)]*\)|\+\s*(?:(?:rs\.?|inr|\u20b9)\s*[\d,]+(?:\.\d+)?\s*)?"
    r"\(?\s*gst\s*\)?|plus\s+(?:applicable\s+)?gst|\(?\s*(?:excl(?:\.|uding|usive\s+of)?|"
    r"incl(?:\.|uding|usive\s+of)?)\s*(?:of\s+)?(?:gst|taxes)\s*\)?", re.I)
_TAIL_OK = re.compile(
    r"[\s.,;|]+|\(\s*gst\s+is\s+\d+\s*%\s*\)|\[?\s*prepaid\s*\]?|\+\s*gst|"
    r"plus\s+(?:applicable\s+)?(?:gst|taxes)|\(?\s*(?:excl(?:\.|uding|usive\s+of)?|"
    r"incl(?:\.|uding|usive\s+of)?)\s*(?:of\s+)?(?:gst|taxes)\s*\)?|(?:payable\s+)?in\s+"
    r"advance|only|for\s+the\s+initial\s+term|\(\s*rupees[^)]*\)|(?:(?:monthly|recurring|"
    r"subscription|service|rental)\s+)*(?:fees?|charges?)|mrc", re.I)


def _plain(own: str, gap: str, tail: str) -> bool:
    """Whether a monthly amount is stated in a plain fee shape (r34): its own line's words
    before it form a label, and only allowed tokens stand between it and its period and
    after the period."""
    return bool(_LABEL.fullmatch(own) and not _GAP_OK.sub("", gap).strip()
                and not _TAIL_OK.sub("", tail).strip())


def _months(m: re.Match) -> int:
    """A "<number> year(s)/month(s)" match in months ("the first year" is one)."""
    count = int(parse_number(m.group(1) or "one") or 0)
    return count * 12 if m.group(2).lower() == "year" else count


def _consistent(fee: float, taxes: set[float], terms) -> set[float]:
    """The totals a document may state beside one monthly fee: the fee itself, the fee
    with its tax, and the fee over a stated term."""
    return {fee, *(fee + t for t in taxes), *(fee * t[0] for t in terms)}


_LINE_END = re.compile(r"\n|(?<!\brs)(?<!\binr)(?<!\bno)(?<!\bexcl)(?<!\bincl)"
                       r"(?<!\bapprox)\.\s", re.I)


def _line(content: str, start: int, end: int) -> tuple[str, str]:
    """The words before and after ``content[start:end]`` on its own line or sentence."""
    before = re.split(_LINE_END, content[max(0, start - 200):start])[-1]
    after = re.split(_LINE_END, content[end:end + 200] + " ")[0]
    return before, after


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


#: A bullet: a mark opening a line, or mid-line before anything but a lower-case word
#: ("for ● months" is a blank, as is "[●]"); "-" and "*" only where they open a line.
_BULLET = re.compile(r"(?:^|\n)[ \t]*[●•▪](?![^\[\]\n]{0,40}\])|"
                     r"[●•▪](?![^\[\]\n]{0,40}\])(?=[\s\u200b]*[^\sa-z\u200b])|\n\s*[-*]\s+")


#: a bullet that speaks of the item above it ("● Subject to revision every year",
#: "● Revised annually as per CPI": a change with no subject of its own)
_BACKREF = re.compile(rf"^\W*subject\s+to\b|^\W*(?:\w+\s+)?(?:{_CHANGE_VERB})\b|"
                      r"\b(?:it|its|them|they|these|those|such|the\s+same)\b", re.I)


def _pieces(content: str):
    """Each sentence; in a list, each bullet with the lines above the list and the latest
    line under a bullet that is not its first (a sub-heading). A bullet ends a sentence,
    so a price word in one bullet never pairs with a change word in another — unless the
    second speaks of the first ("● Fees: ₹10,000 ● Subject to revision every year"), and
    a heading's still does ("Pricing ● Revised annually"): a list read apart from its
    heading would state a fee that changes. A list whose bullets end in ";" or "." keeps
    its heading and its previous bullet across them. Linear: each piece is a bounded
    join, and a blank's "]" is looked for on its own line only."""
    kept = sub = previous = ""
    for part in re.split(r"(?<=[.;])\s+", content):
        head, *bullets = _BULLET.split(part)
        if bullets and not head.strip():
            head = kept                     # the list goes on past a ";"
        else:
            sub = previous = ""
        kept = head
        yield head
        for bullet in bullets:
            yield f"{head} {sub} {bullet}"
            if previous and _BACKREF.search(bullet):
                yield f"{previous} {bullet}"
            if (rest := bullet.partition("\n")[2]).strip():
                sub = rest
            previous = bullet


def read(clauses) -> CommercialFacts:
    """The monthly fee and the committed term the document states, each with its
    evidence row, in the document's order (ENG-11) — but a figure only when it is
    unambiguous (AM-156 R1): exactly one monthly rupee fee, not priced per unit, and
    one fixed term, neither bracketed nor blank. Otherwise ``missing`` says why, in the
    reader's words, and no value is stated: a figure is never estimated."""
    fees: list[tuple[float, str, UUID, bool, bool, bool, bool]] = []
    terms: list[tuple[int, str, UUID]] = []
    refund = elsewhere = None
    census: list[float] = []                # every amount that may be a fee
    totals: set[float] = set()              # the document's own totals …
    taxes: set[float] = set()               # … and tax amounts
    foreign = compound = False
    changes: list[int | None] = []          # each price change, after what validity
    reduced: list[str] = []                 # sentences that take something off the price
    for clause in clauses:
        content = clause.content or ""
        if elsewhere is None and (m := _ELSEWHERE.search(content)):
            elsewhere = m.group(0)
        # every change verb in a sentence naming a price, each read for its own denial;
        # one after a stated price validity counts only if that validity ends in the term
        for sentence in (" ".join(s.split()) for s in _pieces(content)):
            if _SCOPE_CHANGE.search(sentence):
                continue
            if _PCT_CHANGE.search(sentence):    # "a 5% year-on-year increase shall apply"
                changes.append(None)
            if not _PRICED.search(sentence):
                continue
            valid = _VALID_FOR.search(sentence)
            first = _FIRST_PERIOD.search(sentence)
            if first or (_PREVAILING.search(sentence) and not valid):
                changes.append(_months(first) if first else None)
            changes += [_months(valid) if valid and v.start() > valid.end() else None
                        for v in _CHANGES.finditer(sentence)
                        if not _DENIED.search(sentence[max(0, v.start() - 40):v.start()])]
            if valid:                       # "valid for 12 months only": a price after it
                changes.append(_months(valid))
            # a discount or a free period off the price, other than in the fee's own label
            # or an exit charge's waiver, changes what is paid (r35)
            if (_REDUCED.search(sentence) and not _EXIT.search(sentence)
                    and "|" not in sentence):     # a table's amounts are in the census
                reduced.append(sentence)
        amounts = [(_number(a.group(1), a.group(2)), a.start(), a.end())
                   for a in re.finditer(_AMOUNT, content, re.I)]
        amounts += [(_number(b.group(1), b.group(2)), b.start(), b.end())
                    for b in _BARE.finditer(content)    # not the digits of "Rs. 10,000"
                    # money, not a count ("servers 4 per month"): grouped, 4+ digits, a
                    # scale word or "rupees"
                    if ("," in b.group(1) or len(b.group(1).split(".")[0]) >= 4
                        or b.group(2) or b.group(3))
                    and not re.search(r"(?:₹|\brs\.?|\binr)\s*$",
                                     content[max(0, b.start() - 8):b.start()], re.I)]
        for value, start, end in amounts:
            before, after = _line(content, start, end)
            label = re.split(r"[,;]|\bsubject\s+to\b|\bprovided\b", after, flags=re.I)[0]
            if _TAX_ROW.match(before) or _IS_TAX.match(after):
                taxes.add(value)
            elif _NOT_A_FEE.search(before + " " + label):
                continue
            elif _TOTAL.search(before):
                totals.add(value)
            else:
                census.append(value)
        foreign = foreign or any(
            not _NOT_A_FEE.search(" ".join(_line(content, m.start(), m.end())))
            for m in _FOREIGN.finditer(content))
        for m in _MONTHLY.finditer(content):
            gap = m.group(0)[m.end(2 if m.group(2) else 1) - m.start():]
            others = [a for a in re.finditer(_AMOUNT, gap, re.I)
                      if not re.search(r"\bgst\b", gap[a.end():a.end() + 12], re.I)]
            # `window` crosses line wraps: an "annual" or "deposit" on the lines above can
            # only WITHHOLD. `own` is the amount's own line/sentence/cell: what names it.
            window = content[max(0, m.start() - 200):m.start()]
            own, tail = _line(content, m.start(), m.end())
            said = own + gap + tail
            fees.append((_number(m.group(1), m.group(2)), " ".join(m.group(0).split()),
                         clause.evidence_id,
                         bool(_NOT_MONTHLY_ABOVE.search(window)
                              or _NOT_MONTHLY.search(gap) or others
                              or _NOT_THE_FEE.search(said) or _NOT_BASE.search(said)),
                         bool(_PER_UNIT_WORD.search(said) or _PER_UNIT.search(said)),
                         bool(_FEE_LABEL.search(own + gap)),
                         _plain(own, _PERIOD_END.sub("", gap), tail)))
        found = False
        for m in _TERM.finditer(content):
            found = True
            if months := _months(m):        # a zero term ("Lock-in period: 0 months")
                terms.append((months, " ".join(m.group(0).split()), clause.evidence_id))
            compound = compound or bool(_MORE_TERM.match(content, m.end()))
        if not found and (m := _ANNUAL.search(content)):
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
        missing = "the document states more than one monthly amount"
    elif len(set(census) | {fee[0]}) > 1:
        missing = "the document states more than one amount that may be a fee or charge"
    elif totals - _consistent(fee[0], taxes, terms):
        missing = "the document's own total is not the fee"
    elif len(census) > 1 and fee[0] not in totals:
        # one amount stated more than once may be one fee restated or two items at one
        # price: only the document's own total tells them apart (r31)
        missing = ("the document states the amount more than once, and no total confirms "
                   "it is the whole fee")
    elif foreign:
        missing = "the document states a fee in another currency"
    elif any(v is None or not terms or v < terms[0][0] for v in changes):
        missing = "the fee may change during the term"
    elif any(fee[1] not in " ".join(r.split()) for r in reduced):
        missing = "the document takes a discount or a free period off the fee"
    elif fee[4]:
        missing = "the fee is priced per unit, not for the whole contract"
    elif fee[3]:
        missing = "the amount is not stated as a single monthly fee"
    elif not fee[5]:
        missing = "the document states a monthly amount but does not name it as the fee"
    elif not fee[6]:
        missing = "the fee is not stated as one plain monthly figure"
    elif _placeholder(fee[1]):
        missing = "the fee is left blank or in brackets"
    agreed = [t for t in terms if not _placeholder(t[1])]
    if term is not None and (_placeholder(term[1]) or len({t[0] for t in terms}) > 1
                             or compound):
        missing = missing or ("the term is left blank or in brackets"
                              if _placeholder(term[1])
                              else "the term is not stated as one figure" if compound
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

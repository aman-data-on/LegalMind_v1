"""Whose liability a cap limits — read from the cap sentence's own subject.

Moved from `api/angles.py` (2026-10-21) so the analysis reads the same fact the business
angle states: Constitution §9 names "a cap applying to only one party" an Unacceptable
Position, and a figure that matches says nothing about whom it binds. Deterministic: the
words decide, and when they do not say, None — never a guess.
"""
from __future__ import annotations

import re

#: A cap verb — the words before it are the sentence's subject. A carve-out after it
#: ("…, provided that such cap shall not apply to Leapswitch's liability …") is not, and
#: a negated one ("is not capped", "including but not limited to") states no cap (r29).
_CAP_VERB = re.compile(r"\b(?:exceed|capped|limited\s+to|restricted\s+to)\b|\bmaximum\s+"
                       r"(?:aggregate\s+)?liabilit\w*[^.;]{0,40}?\bshall\s+be\b", re.I)
_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
                 15: "fifteen", 18: "eighteen", 24: "twenty-four", 30: "thirty",
                 36: "thirty-six", 45: "forty-five", 60: "sixty", 90: "ninety"}
_UNIT_WORD = {"MONTHS": "month", "YEARS": "year", "DAYS": "day", "WORKING_DAYS": "day",
              "WEEKS": "week"}
_AMOUNT_WORDS = r"(?:(?:total|aggregate|maximum|entire|cumulative|overall)\s+)*liabilit"
#: The party a liability noun names — "Leapswitch's total liability", "the liability of
#: either Party". The LAST one before the cap verb is the cap's; a carve-out naming
#: "either party's obligations" earlier names no liability (r30).
_LIABLE = re.compile(
    r"\b(?:(?P<both>(?:each|either|neither)\s+party'?s?|both\s+parties'?|the\s+parties'|"
    r"each\s+of\s+the\s+parties'?)|(?P<ours>leapswitch|cloudpe|(?:service\s+)?provider|"
    r"supplier)'?s?|(?P<theirs>customer|client|partner)'?s?)\s+" + _AMOUNT_WORDS +
    r"|\bliabilit\w*\s+of\s+(?:the\s+)?(?:(?P<both2>each|either|both|neither)\s+part(?:y|ies)|"
    r"(?P<ours2>leapswitch|cloudpe|(?:service\s+)?provider|supplier)|"
    r"(?P<theirs2>customer|client|partner))\b", re.I)
#: The document types where the counterparty is a customer of LeapSwitch's services.
CUSTOMER_TYPES = frozenset({"MSA", "TOS", "SLA", "ORDER_FORM", "OTHER", "AMENDMENT", ""})
_OURS_WORD = r"(?:leapswitch|cloudpe|(?:service\s+)?provider|supplier)"
_THEIRS_WORD = r"(?:customer|client|partner)"


def sentences(text: str) -> list[str]:
    """A passage's sentences, with typographic apostrophes made plain ("Party’s")."""
    plain = (text or "").replace("\u2019", "'").replace("\u2018", "'")
    return re.split(r"(?<=[.;])\s+(?!\d)", plain)


def figure(actual: dict) -> re.Pattern | None:
    """The measured figure as a period in the document's words — "six (6) months",
    "12-month", and 24 months as "two (2) years" — never a bare number ("Clause 24")."""
    have, unit = actual.get("cap_value"), (actual.get("cap_unit") or "MONTHS").upper()
    if not isinstance(have, (int, float)) or have != int(have) or unit not in _UNIT_WORD:
        return None
    forms = [(int(have), _UNIT_WORD[unit])]
    if unit == "MONTHS" and have and have % 12 == 0:
        forms.append((int(have) // 12, "year"))
    if unit == "YEARS":
        forms.append((int(have) * 12, "month"))         # "twenty-four (24) months"
    return re.compile("|".join(
        rf"\b(?:{n}|{_NUMBER_WORDS.get(n, '_')})\b\)?[\s-]*(?:\(\s*\d+\s*\)[\s-]*)?"
        rf"(?:working\s+|calendar\s+)?{u}s?\b" for n, u in forms), re.I)


def cap_subjects(sentences: list[str]) -> list[tuple[str, str]]:
    """(sentence, subject) for each sentence that states a cap — "shall not exceed", "in
    no event … exceed", "limited to", "capped" — never a negated "limited"/"capped"
    ("is not capped", "shall not be limited to", "but not limited to")."""
    out = []
    for sentence in sentences:
        for m in _CAP_VERB.finditer(sentence):
            if (m.group(0).lower() == "exceed"
                    or not re.search(r"\bnot\s+(?:be\s+|been\s+)?$", sentence[:m.start()],
                                     re.I)):
                out.append((sentence, sentence[:m.start()]))
                break
    return out


def _party(m: re.Match, roles: bool) -> str | None:
    """The side a liability noun names. A role ("the Service Provider", "the Customer")
    is LeapSwitch's or the counterparty's only on a customer-service document; on a
    vendor or partner agreement LeapSwitch may be either, so only its name counts
    (r32)."""
    if m.group("both") or m.group("both2"):
        return "both"
    if ours := (m.group("ours") or m.group("ours2")):
        return "ours" if roles or re.match(r"leapswitch|cloudpe", ours, re.I) else None
    return "theirs" if roles else None


def cap_party(sentences: list[str], actual: dict, roles: bool) -> str | None:
    """Whose liability the measured cap limits — "both", "ours", "theirs" — from the
    last liability noun before the cap verb in the sentence that holds the measured
    figure (the only cap sentence, when none does); None when the words do not say.
    `roles`: a customer-service document, where "Provider"/"Customer" are sides."""
    measured_figure = figure(actual)
    caps = cap_subjects(sentences)
    measured = ([c for c in caps if measured_figure and measured_figure.search(c[0])]
                or (caps if len(caps) == 1 else []))
    whose = set()
    for _, subject in measured:
        sides = {_party(m, roles) for m in _LIABLE.finditer(subject)}
        # two parties' liability named before one cap, or the other side named anywhere
        # before it ("Leapswitch's liability, excluding the Customer's …", "of the
        # Customer and/or LeapSwitch"): the words do not say whose (r31, r32, r34)
        side = next(iter(sides)) if len(sides) == 1 else None
        other = {"theirs": _OURS_WORD, "ours": _THEIRS_WORD}.get(side or "")
        joint = other and re.search(rf"\b{other}\b", subject, re.I)
        whose.add(None if side is None or joint else side)
    return next(iter(whose)) if len(whose) == 1 else None

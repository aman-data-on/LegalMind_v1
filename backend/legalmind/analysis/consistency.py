"""What a careful reader notices across one document — observations, never Findings.

AM-159 (2026-10-17), lawyer-grade release 2, A5. Deterministic checks over the clauses the
review already read: a cross-reference that points nowhere or at the wrong clause, renewal
stated two ways, a clause made "subject to" another, the document's own precedence rule,
and a document that governs the provider's termination but gives no remedy for
non-payment. Each one is shown to the reader with its clauses; none produces a Finding, a
Classification or a Rule Outcome, and none is ever applied (locked F-6: "In-document
precedence language is detected, evidenced and reported — never applied"). Where the
Constitution states a basis, it is quoted verbatim with its section; where it states none,
the observation says so (§23.4).
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from legalmind.domain.client_profile import CIN
from legalmind.extraction.liability import parse_number
from legalmind.mapping.engine import Clause

#: the reader-facing kinds
CROSS_REFERENCE = "CROSS_REFERENCE"
RENEWAL_TWO_WAYS = "RENEWAL_TWO_WAYS"
SUBJECT_TO = "SUBJECT_TO"
PRECEDENCE = "PRECEDENCE"
NO_NONPAYMENT_REMEDY = "NO_NONPAYMENT_REMEDY"
NOTICE_TWO_WAYS = "NOTICE_TWO_WAYS"
OUR_DETAILS = "OUR_DETAILS"
UPTIME_TWO_WAYS = "UPTIME_TWO_WAYS"

_NUM = r"\d{1,3}(?:\.\d{1,3}){0,3}"
_HEAD = re.compile(rf"^\s*(?:Section|Clause|Article)?\s*({_NUM})\.?\s+(.*)$", re.S)
_INLINE_TITLE = re.compile(r"^([A-Z][\w ,&/'\u2019()\-]{1,110}?)\s*[:\u2013]\s+\S|"
                           r"^([A-Z][\w ,&/'\u2019\-]{1,60}?)\.\s+[A-Z]")
_NOISE = {"and", "or", "of", "the", "to", "for", "on", "in", "a", "an", "by", "with"}

# §13 Company Position; §31.2; §31.11 — the Constitution's own words
_NONPAYMENT_BASIS = {"section": "13", "quote": (
    "except for non-payment, security threats, or illegal use, which permit immediate "
    "suspension.")}
_SUBJECT_TO_BASIS = {"section": "31.2", "quote": (
    "This distinction should be checked on a document-by-document basis, since not every "
    "MSA structures the two clauses the same way.")}
_PO_BASIS = {"section": "31.11", "quote": (
    "Where a PO and the governing MSA conflict, the MSA prevails")}


def _index(clauses: list[Clause]) -> dict[str, dict[str, Any]]:
    """number -> {title, text, evidence_id}: a body row with no number of its own is read
    with the last numbered row before it."""
    idx: dict[str, dict[str, Any]] = {}
    current = None
    for clause in clauses:
        content = clause.content or ""
        number, title = clause.section_number, clause.section_title
        head = _HEAD.match(content.strip())
        if not number and head and len(head.group(2)) < 90 \
                and "\n" not in head.group(2).strip():
            number, title = head.group(1), head.group(2).strip(" .:")
        if number:
            number = number.rstrip(".")
            if not title:
                inline = _INLINE_TITLE.match(head.group(2) if head else content)
                title = (inline.group(1) or inline.group(2)) if inline else None
            current = number
            idx.setdefault(number, {"title": title, "text": "",
                                    "evidence_id": clause.evidence_id})
        if current:
            idx[current]["text"] += "\n" + content
    return idx


def _exists(idx: dict, n: str) -> bool:
    return n in idx or any(k.startswith(n + ".") for k in idx)


def _stems(text: str | None) -> set[str]:
    text = re.sub(r"\([^)]*\)", " ", text or "")
    return {w[:6] for w in re.findall(r"[a-z]+", text.lower())
            if w not in _NOISE and len(w) > 2}


def _heading(title: str | None) -> bool:
    """A real heading: short, and not a sentence the parser took as a title."""
    if not title:
        return False
    words = re.sub(r"\([^)]*\)", " ", title)       # "… Ownership (ONLY under …)"
    return len(words.split()) <= 8 and not words.rstrip().endswith((",", ";")) \
        and not re.search(r"\b(?:shall|will|may|must|is|are)\b", words)


def _numbered_well(idx: dict, n: str) -> bool:
    """A missing target is asserted only where the document's own numbering was read:
    top-level numbers 1..max present ≥ 80% (max ≥ 3), and for a sub-number its parent
    present with a sibling — a parse that lost numbers never reports them missing."""
    tops = {int(k.split(".")[0]) for k in idx if k.split(".")[0].isdigit()}
    if not tops or max(tops) < 3 or len(tops) / max(tops) < 0.8:
        return False
    if "." not in n:
        return int(n) > max(tops)
    parent = n.rsplit(".", 1)[0]
    return _exists(idx, parent) and any(k.rsplit(".", 1)[0] == parent
                                        for k in idx if "." in k)


def _observation(kind: str, numbers: list[str], idx: dict, text: str,
                 basis: dict | None = None) -> dict[str, Any]:
    ids: list[UUID] = [idx[n]["evidence_id"] for n in numbers if n in idx]
    return {"kind": kind, "clauses": numbers, "evidence_ids": [str(i) for i in ids],
            "text": text, "basis": basis}


# ---- D1: a cross-reference to no clause, or to the wrong one ------------------------
# a number with a letter ("Section 70B") or a range ("Sections 292–294") is a statute's
_REF = re.compile(rf"\b(?:Sections?|Clauses?|Articles?)\s+({_NUM})(?![\w\u2013-])"
                  rf"(?:\s+and\s+({_NUM})(?![\w\u2013-]))?"
                  rf"(?:\s*\(([A-Z][^)]{{2,60}})\))?(\s+of\s+(?:the\s+)?(?!this\b)\w+)?")
#: a statute named just before the reference ("IPC Sections …", "the IT Act, Section …")
_STATUTE_BEFORE = re.compile(r"\b(?:IPC|CrPC|Act|Code|Rules|Regulations)\W{0,3}$")
_LEAD = re.compile(r"(?:^|[^\w])([A-Za-z][A-Za-z ]{3,60}?)\s+(?:under|in|per|of|"
                   r"pursuant to|as described in|in accordance with)\s*$")


#: a definitions or interpretation clause, where a defined term is meant to point
_DEFINITIONS = {"defini", "interp", "meanin"}


def _named_heading(lead: str,
                   headings: dict[frozenset[str], str]) -> tuple[str, str] | None:
    """The words just before a reference that ARE another clause's heading — the longest
    trailing phrase of at most five words whose stems equal that heading's, with at least
    two content words ("termination for cause"), never the sentence's subject
    ("the Customer shall pay the fees")."""
    words = lead.split()
    for size in range(min(5, len(words)), 0, -1):
        phrase = " ".join(words[-size:])
        stems = frozenset(_stems(phrase))
        if len(stems) >= 2 and stems in headings:
            while words[-size].lower() in _NOISE:   # "for termination for cause"
                size -= 1
            return " ".join(words[-size:]), headings[stems]
    return None


def _cross_references(idx: dict) -> list[dict[str, Any]]:
    out = []
    headings: dict[frozenset[str], str] = {}
    for k, v in idx.items():                # computed once: every reference looks it up
        if _heading(v.get("title")):
            headings.setdefault(frozenset(_stems(v["title"])), k)
    for source, unit in idx.items():
        text = unit["text"]
        for m in _REF.finditer(text):
            before = text[max(0, m.start() - 12):m.start()]
            if m.group(4) or _STATUTE_BEFORE.search(before):
                continue                    # "… of the IT Act", "IPC Sections": a statute
            for n in filter(None, (m.group(1), m.group(2))):
                n = n.rstrip(".")
                if not _exists(idx, n):
                    if _numbered_well(idx, n):
                        out.append(_observation(
                            CROSS_REFERENCE, [source], idx,
                            f"Clause {source} refers to clause {n}, which this document "
                            "does not contain."))
                    continue
                target = _stems(idx.get(n, {}).get("title"))
                if m.group(3) and _stems(m.group(3)) & target:
                    continue                # "Section 4 (Payment Terms)": named right
                if not target or not _heading(idx[n].get("title")) \
                        or target & _DEFINITIONS:
                    # a defined term under the Definitions clause is pointed right
                    continue                # a "title" that is its first sentence
                lead = _LEAD.search(text[max(0, m.start() - 70):m.start()])
                for said in (m.group(3), lead.group(1) if lead else None):
                    hit = _named_heading(said or "", headings)
                    if hit and hit[1] != n and not _stems(hit[0]) & target:
                        out.append(_observation(
                            CROSS_REFERENCE, [source, n, hit[1]], idx,
                            f"Clause {source} refers to clause {n} for “{hit[0]}”, "
                            f"but clause {n} is headed “{idx[n]['title']}” — clause "
                            f"{hit[1]} is."))
                        break
    return out


# ---- D2: renewal stated two ways ----------------------------------------------------
_AUTO = re.compile(r"automatic\w*\s+(?:renew|commence|extend)|shall\s+(?:be\s+)?"
                   r"(?:auto[- ]?)?renew\w*\s+automatic|auto[- ]?renew", re.I)
_MUTUAL = re.compile(r"renew\w*[^.]{0,80}?\b(?:upon|subject to|by|with|on)\b[^.]{0,30}?"
                     r"\b(?:mutual\w*|both parties\W?|the parties\W?)\s*(?:written\s+)?"
                     r"(?:approval|consent|agreement)", re.I)
_NEGATED = re.compile(r"\b(?:not|no|never|neither|nor|without)\b", re.I)
#: the agreement governs a price, not the renewal itself
_PRICE = re.compile(r"\b(?:fees?|pric\w*|charges?|rates?|tariffs?)\b", re.I)


def _renewal(idx: dict) -> list[dict[str, Any]]:
    auto, mutual = [], []
    for n, unit in idx.items():
        for sentence in re.split(r"(?<=[.;])\s+", unit["text"]):
            if re.search(r"renew", sentence, re.I):
                said = _AUTO.search(sentence)
                if said and not _NEGATED.search(sentence[max(0, said.start() - 25):
                                                         said.start()]):
                    auto.append(n)              # not "shall not automatically renew"
                agreed = _MUTUAL.search(sentence)
                if agreed and not _PRICE.search(agreed.group(0)):
                    mutual.append(n)    # not "renewal pricing by mutual agreement"
    if not any(a != b for a in auto for b in mutual):
        return []                           # one clause stating both is one rule
    # every clause that says it, once (Step 2, 2026-10-21): a third statement is named too
    automatic = sorted(set(auto) - set(mutual)) or sorted(set(auto))
    consented = sorted(set(mutual))
    return [_observation(RENEWAL_TWO_WAYS, sorted({*auto, *mutual}), idx,
                         f"Renewal is stated two ways: {_clauses(automatic)} "
                         f"{_verb(automatic)} automatically; {_clauses(consented)} "
                         f"{_verb(consented)} only with both parties' agreement.")]


def _clauses(numbers: list[str]) -> str:
    return ("clause " if len(numbers) == 1 else "clauses ") + ", ".join(numbers)


def _verb(numbers: list[str]) -> str:
    return "renews" if len(numbers) == 1 else "renew"


# ---- Step 2 (2026-10-21): a convenience notice stated with two periods ---------------
_CONVENIENCE = re.compile(r"\b(?:convenience|without\s+cause|for\s+any\s+reason|"
                          r"at\s+any\s+time)\b", re.I)
_DAYS = re.compile(r"\b(\d{1,3}|[a-z]+(?:-[a-z]+)?)\s*(?:\(\s*\d{1,3}\s*\))?\s*"
                   r"((?:working|business|calendar)\s+)?days?\b", re.I)
_WHO = re.compile(r"\b(either\s+party|each\s+party|customer|client|leapswitch|cloudpe|"
                  r"(?:service\s+)?provider)\b[^.;]{0,40}?\bterminat", re.I)


_NON_RENEWAL = re.compile(r"non[- ]renewal|not\s+to\s+renew", re.I)


def _notice_days(sentence: str) -> str | None:
    """The one notice period a convenience exit states ("15 days", "30 working days")."""
    found = {f"{value:g} {(m.group(2) or '').lower()}days"
             for m in _DAYS.finditer(sentence)
             if (value := parse_number(m.group(1))) is not None}
    return next(iter(found)) if len(found) == 1 else None


def _notice(idx: dict) -> list[dict[str, Any]]:
    """Two clauses giving the same party different notice to leave for convenience. A
    customer's notice and the provider's are two rights, never one stated twice (MSA2
    §25.1/§25.2); "either party" overlaps both."""
    stated = []
    for n, unit in idx.items():
        for sentence in re.split(r"(?<=[.;])\s+", unit["text"]):
            days = _notice_days(sentence)
            if not days:
                continue
            if _EXIT.search(sentence) and _CONVENIENCE.search(sentence) \
                    and (who := _WHO.search(sentence)):
                side = " ".join(who.group(1).lower().split())
                stated.append(("to end the agreement", n,
                               "either" if side.endswith("party") else side, days))
            elif _NON_RENEWAL.search(sentence):
                stated.append(("not to renew", n, "either", days))
    out = []
    for kind in ("to end the agreement", "not to renew"):
        out += next(([_observation(
            NOTICE_TWO_WAYS, [c1, c2], idx,
            f"The notice {kind} is stated two ways: clause {c1} says {d1}; clause {c2} "
            f"says {d2}.")]
            for k1, c1, s1, d1 in stated for k2, c2, s2, d2 in stated
            if k1 == k2 == kind and c1 < c2 and d1 != d2
            and (s1 == s2 or "either" in (s1, s2))), [])
    return out


# ---- D3: a termination or term clause made subject to another -----------------------
_CHAIN = re.compile(rf"\b(subject to|notwithstanding)\s+(?:the\s+provisions\s+of\s+)?"
                    rf"(?:clause|section|article)\s+({_NUM})", re.I)
#: a convenience exit, made subject to a minimum term or lock-in (§14, §31.2)
_EXIT = re.compile(r"terminat\w*[^.]{0,120}?\b(?:convenience|notice|without\s+cause|"
                   r"for\s+any\s+reason|at\s+any\s+time)|(?:convenience|without\s+cause)[^.]{0,60}?"
                   r"terminat", re.I)
_COMMITMENT = re.compile(r"\bminimum\s+(?:service|commitment|term|period)|\block-?\s?in|"
                         r"\binitial\s+term\b|\bcommitted\s+term|\bservice\s+period\b|"
                         r"\bterm\s+of\s+[^.]{0,20}?\b(?:years?|months?)\b",
                         re.I)


def _subject_to(idx: dict) -> list[dict[str, Any]]:
    out = []
    for source, unit in idx.items():
        for m in _CHAIN.finditer(unit["text"]):
            target = m.group(2).rstrip(".")
            if not _exists(idx, target) or target == source:
                continue
            target_text = idx.get(target, {}).get("text", "")
            if not (_EXIT.search(unit["text"]) and _COMMITMENT.search(target_text)):
                continue                    # only an exit turning on the commitment
            out.append(_observation(
                SUBJECT_TO, [source, target], idx,
                f"Clause {source} applies {m.group(1).lower()} clause {target}: the two "
                "are read together.", _SUBJECT_TO_BASIS))
    return out


# ---- D4: the document's own precedence rule (information, never applied) ------------
_PRECEDES = re.compile(r"(?:conflict(?!s?[\s-]+of[\s-]+laws?)|inconsisten\w+)"
                       r"[^.]{0,160}?\b(?:shall\s+prevail|prevails?|(?:shall\s+)?take\s+"
                       r"precedence|shall\s+govern|shall\s+control)", re.I)


def _precedence(idx: dict) -> list[dict[str, Any]]:
    out = []
    for n, unit in idx.items():
        m = _PRECEDES.search(unit["text"])
        if m:
            words = " ".join(m.group(0).split())
            po = re.search(r"\b(?:purchase\s+order|po)\b", unit["text"], re.I)
            out.append(_observation(
                PRECEDENCE, [n], idx,
                f"Clause {n} states which document prevails in a conflict: “{words}”.",
                _PO_BASIS if po else None))
    return out


def precedence_quotes(units: list[tuple[str | None, str]]) -> list[str]:
    """The document's own words on which document prevails, from (clause, text) pairs —
    shown to the reader before asking them which document wins (`AM-230`). Never applied
    (locked F-6)."""
    out = []
    for clause, unit in units:
        if (m := _PRECEDES.search(unit)):
            words = " ".join(m.group(0).split())
            out.append(f"Clause {clause}: “{words}”" if clause else f"“{words}”")
    return out


# ---- D5: a provider-termination clause with no remedy for non-payment ----------------
#: OUR right to suspend or terminate: LeapSwitch (or either party) may / is entitled to /
#: reserves the right to …, or the Services may be suspended; never negated ("shall not
#: suspend"), never the customer's, never "upon termination the Customer shall pay"
_SUBJECT = (r"(?:either\s+party|(?:the\s+)?service\s+provider|leapswitch|"
            r"(?:the\s+)?provider|(?:the\s+)?company)")
_GAP = r"(?:(?!not\b|never\b)\w+\s+){0,4}?"
_ACT = r"(?:suspen|terminat|disconnect|deactivat|discontinu)\w*"
_OUR_REMEDY = re.compile(
    rf"{_SUBJECT}\s+(?:may|can|(?:is|shall\s+be)\s+entitled\s+to|(?:shall\s+)?ha(?:s|ve)"
    rf"\s+the\s+right\s+to|reserves?\s+the\s+right\s+to)\s+{_GAP}{_ACT}|"
    rf"entitles?\s+{_SUBJECT}\s+to\s+{_GAP}{_ACT}|"
    rf"\b(?:services?|account|agreement)\b(?:[^.;]{{0,60}}?\s)?(?:may|shall|will)\s+be\s+"
    rf"{_GAP}{_ACT}", re.I)
_NONPAY = re.compile(r"non[- ]?payment|overdue|unpaid|(?:fail\w*|default\w*)\s+"
                     r"(?:\w+\s+){0,3}(?:to\s+)?(?:make\s+)?pay|late\s+payment|"
                     r"payment\w*\s+(?:is|are)\s+not\s+(?:made|received)|"
                     r"not\s+(?:been\s+)?paid|(?:does|do|did)\s+not\s+pay|"
                     r"delay\w*\s+in\s+(?:the\s+)?payment|material\s+breach|"
                     r"outstanding\s+(?:amount|dues|invoice|fee|balance)", re.I)
#: a counterparty is the provider here, or the document governs no payment to us
_NOT_OUR_SERVICE = {"NDA", "VENDOR_AGREEMENT", "PARTNER_AGREEMENT",
                    "DISTRIBUTION_AGREEMENT"}
_PROVIDER_ENDS = re.compile(r"terminat\w+\s+by\s+(?:the\s+)?(?:service\s+provider|"
                            r"leapswitch|provider|company)|(?:service\s+provider|leapswitch|"
                            r"provider)\s+may\s+(?:only\s+)?terminat", re.I)


def _nonpayment(clauses: list[Clause], document_type: str | None) -> list[dict[str, Any]]:
    text = "\n".join(c.content or "" for c in clauses)
    if document_type in _NOT_OUR_SERVICE or not _PROVIDER_ENDS.search(text):
        return []                           # the document does not govern our exit
    if any(_OUR_REMEDY.search(s) and _NONPAY.search(s)
           for s in re.split(r"(?<=[.;])\s+", text)):
        return []
    return [{"kind": NO_NONPAYMENT_REMEDY, "clauses": [], "evidence_ids": [],
             "text": "This document states no right to suspend or terminate for "
                     "non-payment.", "basis": _NONPAYMENT_BASIS}]


# ---- AM-197: our own details as the Constitution records them (§4.1) ----------------
_INCORPORATION_BASIS = {"section": "4.1", "quote": (
    "Leapswitch Networks Pvt. Ltd. is a company incorporated under the Companies Act, "
    "2013")}
_OFFICE_BASIS = {"section": "4.1", "quote": (
    "registered office of record is Office 1104, 11th Floor, Gokhale Business Bay, "
    "Opposite City Pride, Kothrud, Pune 411038, Maharashtra, India")}
#: read forward from OUR name — "Pvt. Ltd." puts full stops inside the party block
_OUR_1956 = re.compile(r"\b(?:leapswitch|cloudpe)\b[^;]{0,200}?\bincorporated\s+under\s+"
                       r"the\s+companies\s+act,?\s*1956", re.I)
_OUR_OFFICE = re.compile(r"\b(?:leapswitch|cloudpe)\b[^;]{0,250}?\bregistered\s+office\s+"
                         r"(?:is\s+)?(?:at\s+)?(?P<at>[^(;]{5,160}?)"
                         r"(?=,?\s*bearing\b|\s*\(|;|$)", re.I)


def _our_details(clauses: list[Clause]) -> list[dict[str, Any]]:
    """Our incorporating statute or registered office stated otherwise than §4.1 — the
    first party block that names us, never the counterparty's."""
    out: list[dict[str, Any]] = []
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        ids = [str(clause.evidence_id)]
        if (not any(o["basis"] is _INCORPORATION_BASIS for o in out)
                and _OUR_1956.search(text)):
            out.append({"kind": OUR_DETAILS, "clauses": [], "evidence_ids": ids,
                        "text": "Our company is described as incorporated under the "
                                "Companies Act, 1956.", "basis": _INCORPORATION_BASIS})
        office = _OUR_OFFICE.search(text)
        if (office and "gokhale" not in office.group("at").lower()
                and not any(o["basis"] is _OFFICE_BASIS for o in out)):
            out.append({"kind": OUR_DETAILS, "clauses": [], "evidence_ids": ids,
                        "text": "Our registered office is given as "
                                f"{office.group('at').strip(' ,.')}.",
                        "basis": _OFFICE_BASIS})
    return out


# ---- AM-213: an uptime commitment stated two ways (§11) -------------------------------
_UPTIME_BASIS = {"section": "11", "quote": (
    "Leapswitch (Dedicated Server SLA): minimum uptime 99.9% (Dedicated Servers, Power "
    "(Single Power Servers), Public Network)")}
_TWO_WAYS = re.compile(r"\b(?:uptime|availability)\b[^.]{0,80}?\d{2,3}(?:\.\d+)?\s*%"
                       r"[^.]{0,60}?\bor\b[^.]{0,60}?\b(?:mins?|minutes?|hours?|hrs?)\b[^.]{0,60}?"
                       r"\bwhichever\s+is\s+(?:more|higher|greater|less|lower)\b", re.I)


def _uptime_two_ways(clauses: list[Clause]) -> list[dict[str, Any]]:
    """"99.9% or 60 mins in a month whichever is more" — a percentage and a time that are
    not the same commitment (60 minutes is 99.86% of a 30-day month), so the reader is
    told it can be read two ways; nothing is compared or chosen."""
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        if m := _TWO_WAYS.search(text):
            said = f"\u201c{m.group(0)}\u201d"
            return [{"kind": UPTIME_TWO_WAYS, "clauses": [], "evidence_ids":
                     [str(clause.evidence_id)], "basis": _UPTIME_BASIS,
                     "text": f"The uptime commitment is stated two ways: {said}."}]
    return []


# ---- AM-241 (AB-139, 2026-10-30): what a lawyer reads across the whole contract -------
OUR_ENTITY = "OUR_ENTITY"
NO_TERM_LENGTH = "NO_TERM_LENGTH"
BLANK_FIGURE = "BLANK_FIGURE"
NONPAYMENT_TWO_WAYS = "NONPAYMENT_TWO_WAYS"

_ENTITY_BASIS = {"section": "4.1", "quote": "Leapswitch Networks Pvt. Ltd."}
_OUR_NAME = re.compile(r"\b(?:leap\s?switch|cloudpe)"
                       r"(?:\s+(?!leap\s?switch\b|cloudpe\b)[A-Za-z]+){0,3}?\s+"
                       r"(?:private|pvt\.?)\s+(?:limited|ltd\.?)", re.I)


def _entity(name: str) -> str:
    name = re.sub(r"\bpvt\b\.?", "private", name.lower())
    name = re.sub(r"\bltd\b\.?", "limited", name).replace("leap switch", "leapswitch")
    return " ".join(name.split())


def _our_entity(clauses: list[Clause]) -> list[dict[str, Any]]:
    """Our company named as an entity the Constitution does not record (§4.1) — a
    signature block for "Leapswitch Data Services Private Limited" under a preamble for
    LeapSwitch Networks. CloudPe is a brand, never a company. A returned copy is read
    as we sent it too (the row's wording before the client's tracked changes): the
    client deleting our wrong name does not make it right in what we sent."""
    for clause in clauses:
        sent = (clause.marks or {}).get("original")
        for text, where in ((clause.content, ""), (sent, " in the version we sent")):
            for m in _OUR_NAME.finditer(" ".join((text or "").split())):
                if _entity(m.group(0)) != "leapswitch networks private limited":
                    return [{"kind": OUR_ENTITY, "clauses": [], "basis": _ENTITY_BASIS,
                             "evidence_ids": [str(clause.evidence_id)],
                             "text": f"Our company is named “{m.group(0)}”{where}, which "
                                     "is not the contracting entity."}]
    return []


#: the defined Term relied on ("the remainder of the Term"), and a length stated for it
_ON_TERM = re.compile(r"\b(?:remainder|expiry|expiration|end|balance)\s+of\s+the\s+"
                      r"(?:Initial\s+)?Term\b")
_LENGTH = re.compile(r"\b(?:term|tenure|in\s+force|valid|commit\w*|lock-?\s?in)\b"
                     r"[^.]{0,80}?"
                     r"\b(\d{1,3}|[a-z]+(?:-[a-z]+)?)\s*(?:\(\s*\d{1,3}\s*\))?\s*"
                     r"(?:months?|years?)\b", re.I)
_NOT_LENGTH = re.compile(r"renew|preceding|surviv|"
                         r"after\s+(?:the\s+)?(?:termination|expiry)", re.I)


def _term_length(idx: dict) -> list[dict[str, Any]]:
    """Clauses that run on "the Term" when no clause states how long it is. The order form
    may state it; the reader is told to read the two together."""
    relies = [n for n, unit in idx.items() if _ON_TERM.search(unit["text"])]
    if not relies:
        return []
    for unit in idx.values():
        for sentence in re.split(r"(?<=[.;])\s+", unit["text"]):
            m = _LENGTH.search(sentence)
            if (m and parse_number(m.group(1)) is not None
                    and not _NOT_LENGTH.search(sentence)):
                return []
    return [_observation(NO_TERM_LENGTH, relies, idx,
                         f"{_clauses(relies).capitalize()} "
                         f"{'relies' if len(relies) == 1 else 'rely'} on the Term, "
                         "but no clause states how long it is; if the order "
                         "form states it, read the two together.")]


#: "in the months preceding the claim": the number of the period left out
_BLANK = re.compile(r"\b(?:in|within|during|for|over)\s+the\s+"
                    r"(months?|days?|weeks?|years?)\s+(?:immediately\s+)?"
                    r"(?:preceding|prior|before|following|after)\b", re.I)


def _blank_figure(idx: dict) -> list[dict[str, Any]]:
    return [_observation(BLANK_FIGURE, [n], idx,
                         f"Clause {n} leaves the number of {m.group(1).lower()} blank: "
                         f"“{' '.join(m.group(0).split())}”.")
            for n, unit in idx.items() if (m := _BLANK.search(unit["text"]))]


_IMMEDIATE = re.compile(r"\bimmediate(?:ly)?\b|"
                        r"\bwithout\s+(?:any\s+)?(?:prior\s+)?notice\b", re.I)
_NONPAYMENT_NOTICE_BASIS = {"section": "16", "quote": (
    "Before suspending service for non-payment, the customer should receive appropriate "
    "written notice and a cure period")}


def _nonpayment_two_ways(idx: dict) -> list[dict[str, Any]]:
    """Our remedy for non-payment stated in several clauses with different notice — C-28
    stays open (§13 vs §16): the clauses are shown, none is chosen."""
    said: dict[str, str] = {}
    for n, unit in idx.items():
        for sentence in re.split(r"(?<=[.;])\s+", unit["text"]):
            # "material breach" alone is any breach (an address not notified, MSA
            # 20.3), never non-payment; "immediate written notice … within 15 days of
            # the Due Date" is immediate notice after a grace period (MSA 14.2)
            if _OUR_REMEDY.search(sentence) and any(
                    "material" not in m.group(0).lower()
                    for m in _NONPAY.finditer(sentence)):
                said.setdefault(n, "immediately" if _IMMEDIATE.search(sentence)
                                else _notice_days(sentence) or "no notice stated")
    if len(set(said.values())) < 2:
        return []
    parts = "; ".join(f"clause {n}: {d}" for n, d in said.items())
    return [_observation(NONPAYMENT_TWO_WAYS, list(said), idx,
                         f"Suspension or termination for non-payment is stated with "
                         f"different notice — {parts}.", _NONPAYMENT_NOTICE_BASIS)]


#: “Force Majeure” shall have the meaning set forth in Clause 8 — and clause 8 is Payment
_DEFINED_BY_REF = re.compile(rf"[\u201c\"\u2018']([A-Z][\w &/-]{{2,40}}?)"
                             rf"[\u201d\"\u2019']"
                             rf"\s+shall\s+have\s+the\s+"
                             rf"meaning\s+(?:set\s+(?:forth|out)|given|ascribed)\s+"
                             rf"(?:to\s+it\s+)?in\s+(?:Clause|Section|Article)\s+({_NUM})")


def _definition_targets(idx: dict) -> list[dict[str, Any]]:
    headings = {k: v["title"] for k, v in idx.items() if _heading(v.get("title"))}
    out = []
    for source, unit in idx.items():
        for m in _DEFINED_BY_REF.finditer(unit["text"]):
            term, n = m.group(1), m.group(2).rstrip(".")
            if n not in headings or _stems(term) & _stems(headings[n]):
                continue
            right = next((k for k, t in headings.items()
                          if _stems(term) <= _stems(t)), None)
            if right:
                out.append(_observation(
                    CROSS_REFERENCE, [source, n, right], idx,
                    f"Clause {source} defines “{term}” by clause {n}, which is headed "
                    f"“{headings[n]}” — clause {right} is."))
    return out


# ---- batch 8 R6 (AM-463): the commercial tables read against themselves -------------
# No threshold (a figure is compared at the precision the document prints it) and no
# legal vocabulary: qty, subtotal, tax and total are the table's own commercial words.
QUANTITY_TWO_WAYS = "QUANTITY_TWO_WAYS"
BLANK_FIELD = "BLANK_FIELD"
TOTALS_DIFFER = "TOTALS_DIFFER"
OUR_CIN = "OUR_CIN"

#: an item's own label, "( GPUN - 1 )" — letters then a number, in brackets
_ITEM = re.compile(r"\(\s*([A-Za-z]+(?:\s*-\s*|\s+)?\d+[A-Za-z0-9]*)\s*\)")
_AMOUNT = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_RATE = re.compile(r"\((\d+(?:\.\d+)?)\s*%\)")
#: a cell's "Label:" — one to four capitalised words — and what follows it
_LABEL = re.compile(r"(?<![\w(])([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3})\s*:")
_GLUE = r"[^\s.,;:()\[\]\"'\u2018\u2019\u201c\u201d]"
_PRINTED_CIN = re.compile(rf"(?P<pre>{_GLUE}?)(?P<cin>{CIN})(?P<post>{_GLUE}?)")
_US = re.compile(r"\b(?:leap\s?switch|cloudpe)\b", re.I)
_CIN_BASIS = {"section": "4.1", "quote": "Its CIN, U30007PN2010PTC137171"}
_OUR_CIN_NUMBER = re.search(CIN, _CIN_BASIS["quote"]).group(0)  # type: ignore[union-attr]


def _rows(clause: Clause) -> list[list[str]]:
    """A TABLE segment's rows as cells (`parsing.table_row`'s "| a | b |")."""
    return [[c.strip() for c in line.strip()[1:-1].split("|")]
            for line in (clause.content or "").split("\n")
            if line.startswith("| ") and line.rstrip().endswith("|")]


def _item(cells: list[str], skip: int = -1) -> str | None:
    """A row's item: its bracketed label ("GPUN-1"), else its first cell with words."""
    for k, cell in enumerate(cells):
        if k != skip and (m := _ITEM.search(cell)):
            return re.sub(r"\s*-\s*|\s+", "-", m.group(1)).upper()
    return next((c for k, c in enumerate(cells) if k != skip
                 and re.search(r"[A-Za-z]", c)), None)


def _figure(cell: str) -> tuple[Decimal, int] | None:
    """The first figure printed in a cell, with its decimal places."""
    m = _AMOUNT.search(cell)
    if m is None:
        return None
    raw = m.group(0).replace(",", "")
    return Decimal(raw), len(raw.partition(".")[2])


def _grouped(value: Decimal, places: int) -> str:
    """A rupee figure as Indian paper prints it: 66,98,400.00."""
    whole, _, frac = f"{abs(value):.{places}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    while len(head) > 2:
        head, tail = head[:-2], f"{head[-2:]},{tail}"
    return ("-" if value < 0 else "") + (f"{head},{tail}" if head else tail) \
        + (f".{frac}" if frac else "")


def _commercial(clause: Clause, kind: str, text: str) -> dict[str, Any]:
    return {"kind": kind, "clauses": [], "evidence_ids": [str(clause.evidence_id)],
            "text": text, "basis": None}


def _quantities(clauses: list[Clause]) -> list[dict[str, Any]]:
    """R6.1: one item given two different quantities (a "Qty" column) in the tables."""
    seen: dict[str, list[tuple[str, int, Clause]]] = defaultdict(list)
    for clause in clauses:
        col = None
        for cells in _rows(clause):
            head = [k for k, c in enumerate(cells) if c.lower() in ("qty", "quantity")]
            if head:
                col = head[0]
            elif col is not None and col < len(cells) and cells[col].isdigit() \
                    and (item := _item(cells, col)):
                seen[item].append((cells[col], int(cells[col]), clause))
    out = []
    for item, said in seen.items():
        first = said[0]
        other = next((s for s in said if s[1] != first[1]), None)
        if other is not None:
            out.append({**_commercial(
                first[2], QUANTITY_TWO_WAYS, f"The quantity of {item} is {first[0]} in "
                f"one table and {other[0]} in another."),
                        "evidence_ids": list(dict.fromkeys(
                            str(s[2].evidence_id) for s in (first, other)))})
    return out


def _blank_fields(clauses: list[Clause]) -> list[dict[str, Any]]:
    """R6.2: a "Label:" with nothing after it in a table cell, where the same label has a
    value elsewhere in the tables. No list of labels is kept."""
    fields: list[tuple[str, bool, str | None, Clause]] = []
    for clause in clauses:
        for cells in _rows(clause):
            for cell in cells:
                found = list(_LABEL.finditer(cell))
                for k, m in enumerate(found):
                    value = cell[m.end():found[k + 1].start() if k + 1 < len(found)
                                 else len(cell)]
                    fields.append((m.group(1), bool(re.search(r"\w", value)),
                                   _item([cell]) if _ITEM.search(cell) else None, clause))
    out: list[dict[str, Any]] = []
    for label, filled, item, clause in fields:
        other = next((f for f in fields if f[0] == label and f[1]), None)
        if filled or other is None or any(o["label"] == (label, item) for o in out):
            continue
        out.append({**_commercial(clause, BLANK_FIELD, f"{label} has no value"
                                  f"{f' for {item}' if item else ''}. It has one"
                                  f"{f' for {other[2]}' if other[2] else ' elsewhere'}."),
                    "label": (label, item)})
    return [{k: v for k, v in o.items() if k != "label"} for o in out]


#: the column a line's amount is read from: its header says amount, total or value
_AMOUNT_HEAD = re.compile(r"(?:line\s+)?(?:amount|total|value)\b", re.I)
_TAX_ROW = re.compile(r"(?:tax|gst|cgst|sgst|igst)\b", re.I)
#: a line that takes away (a discount, "Less:", a rebate, a minus sign): the lines are
#: then not a plain sum, so they are not summed
_TAKES_AWAY = re.compile(r"discount|\bless\b|rebate", re.I)
_MINUS = re.compile(r"[-\u2212]\s*(?:[^\d\s]{0,3}\s*)?\d")


def _totals(clauses: list[Clause]) -> list[dict[str, Any]]:
    """R6.3: in one table, each tax at its stated rate (CGST and SGST each), the line
    amounts — read from the column headed amount/total/value, else not checked; not
    summed when a line takes away (a discount, "Less:", a minus) — against the subtotal,
    and subtotal + every tax against the total (not checked beside a tax row with no
    stated rate: fail silent); each compared at
    the precision the stated figure is printed in (paise or rupees), rounded half up.
    A row missing: that check is not made."""
    out: list[dict[str, Any]] = []
    for clause in clauses:
        rows = _rows(clause)
        subtotal: tuple[Decimal, int] | None = None
        total: tuple[Decimal, int] | None = None
        taxes: list[tuple[Decimal, tuple[Decimal, int]]] = []   # (rate, stated)
        col: int | None = None
        lines: list[tuple[Decimal, int] | None] = []
        untaxed = adjusted = False     # a tax row with no rate; a line that takes away
        for cells in rows:
            first, amount = cells[0], _figure(cells[-1]) if len(cells) > 1 else None
            if re.match(r"sub\s?-?total", first, re.I):
                # its amount column when the table has one (round 3), else its last cell
                own = _figure(cells[col]) if col is not None and 0 < col < len(cells) \
                    else None
                subtotal = subtotal or own or amount
            elif amount and (r := _RATE.search(first)) and _TAX_ROW.match(first):
                taxes.append((Decimal(r.group(1)), amount))
            elif amount and _TAX_ROW.match(first):
                untaxed = True             # "Tax adjustment": the total is not checked
            elif amount and re.match(r"(?:grand\s+)?total\b", first, re.I):
                total = amount
            elif subtotal is None and not re.search(r"\d", " ".join(cells)):
                # a header row: the lines start after it, their amount in its column
                heads = [k for k, c in enumerate(cells) if _AMOUNT_HEAD.match(c.strip())]
                col, lines = (heads[-1] if heads else None), []
            elif subtotal is None:
                cell = cells[col] if col is not None and col < len(cells) else ""
                adjusted = adjusted or bool(_TAKES_AWAY.search(first)
                                            or _MINUS.search(cell))
                lines.append(_figure(cell) if cell else None)
        checks = []
        if subtotal is not None:
            for rate, tax in taxes:
                checks.append((subtotal[0] * rate / 100, tax,
                               f"The tax at {rate}% of {_grouped(*subtotal)} is "
                               "{computed}, but the table states {stated}"))
            if col is not None and lines and all(lines) and not adjusted:
                checks.append((sum((a[0] for a in lines if a), Decimal(0)), subtotal,
                               "The line amounts add up to {computed}, but the subtotal "
                               "states {stated}"))
            if taxes and total is not None and not untaxed:
                checks.append((subtotal[0] + sum(t[1][0] for t in taxes), total,
                               "The subtotal and tax add up to {computed}, but the total "
                               "states {stated}"))
        for computed, (stated, places), words in checks:
            at = computed.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
            if at != stated:
                out.append(_commercial(clause, TOTALS_DIFFER, words.format(
                    computed=_grouped(at, places), stated=_grouped(stated, places))
                    + f" (a difference of {_grouped(abs(at - stated), places)})."))
    return out


def _our_cin(clauses: list[Clause]) -> list[dict[str, Any]]:
    """R6.4: our CIN as printed. In prose, read forward from OUR name, a CIN with a
    character glued to it, or a CIN that is not the one §4.1 records; in a table, only
    a stray character on §4.1's own CIN (a table can hold both parties' details, so
    which other CIN is ours cannot be told). The value is quoted with its basis, never
    called wrong (its source is open for Legal, `AM-452` r3)."""
    out: list[dict[str, Any]] = []
    said: set[str] = set()
    for clause in clauses:
        text = " ".join((clause.content or "").split())
        table = text.startswith("| ")
        spans = [(m.end(), m.end() + 300) for m in _US.finditer(text)] if not table \
            else [(0, len(text))]
        for m in _PRINTED_CIN.finditer(text):
            if not any(a <= m.start() <= b and ";" not in text[a:m.start()]
                       for a, b in spans):
                continue
            stray = bool(m.group("pre") or m.group("post"))
            other = m.group("cin") != _OUR_CIN_NUMBER
            if (table and other) or not (stray or other) or m.group(0) in said:
                continue
            said.add(m.group(0))
            out.append({**_commercial(
                clause, OUR_CIN, f"Our CIN is printed with a stray character: "
                f"“{m.group(0)}”." if stray else f"Our CIN is printed as {m.group(0)}."),
                "basis": _CIN_BASIS})
    return out


def observe(clauses: list[Clause],
            document_type: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """The document's observations: `structural` ones a person weighs (renewal two ways,
    a subject-to chain, the precedence rule, a missing non-payment remedy) and
    `additional` points (cross-references) shown last."""
    idx = _index(clauses)
    return {"structural": [*_our_entity(clauses), *_term_length(idx), *_blank_figure(idx),
                           *_renewal(idx), *_notice(idx), *_nonpayment_two_ways(idx),
                           *_subject_to(idx), *_precedence(idx),
                           *_nonpayment(clauses, document_type),
                           *_our_details(clauses), *_uptime_two_ways(clauses),
                           *_our_cin(clauses), *_quantities(clauses),
                           *_blank_fields(clauses), *_totals(clauses)],
            "additional": [*_cross_references(idx), *_definition_targets(idx)]}


# ---- Lawyer judgement P1: a reference into OUR paper (MSA, TOS, SLA, AUP) ------------
# One parser, beside `_REF`: "MSA clause 17.2", "MSA clauses 17.2, 17.3 and 17.7",
# "despite MSA clause 8.4 (no set-off)", the inverted "section 13 of the Terms of
# Service", and DESCRIBED — an unnumbered passage named by its words ("the provision of
# the SLA under which credits lapse"). Observations only: never a Finding, a route, an
# effect or an answer; never read by `observe` (nothing it counts changes).
PAPER_DOCS = ("MSA", "TOS", "SLA", "AUP")
_DOC_NAMES = (r"(?P<doc>MSA|Master\s+Services?\s+Agreement|Terms\s+of\s+Service|TOS|"
              r"SLA|Service\s+Level\s+Agreement|AUP|Acceptable\s+Us(?:e|age)\s+Policy)")
_ONE = rf"{_NUM}(?:\([a-z]{{1,3}}\))?(?:\s*\([^()]{{3,80}}\))?"
_LIST = rf"{_ONE}(?:(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+){_ONE})*"
_UNIT = r"(?:clauses?|sections?|paragraphs?|§§?)"
_FORWARD = re.compile(rf"\b{_DOC_NAMES}\s+{_UNIT}\s*(?P<list>{_LIST})", re.I)
_INVERTED = re.compile(rf"\b{_UNIT}\s*(?P<list>{_LIST})\s+of\s+(?:the\s+)?"
                       rf"(?:(?!this\b)\w+\s+)?(?<!this\s)"
                       rf"{_DOC_NAMES}\b", re.I)
_EACH = re.compile(rf"(?P<n>{_NUM})(?:\((?P<sub>[a-z]{{1,3}})\))?"
                   r"(?:\s*\((?P<title>[^()]{3,80})\))?")
#: DESCRIBED: "the provision / statement / term of (or in) the SLA …" and the words
#: that name the passage. Each entry: what the client says, and what our passage says
#: (every pattern must match one paragraph of ours). Lexical aids, not positions.
_DESCRIBED_LEAD = re.compile(rf"\b(?:provision|statement|term|wording|sentence)s?\s+"
                             rf"(?:of|in)\s+(?:the\s+)?{_DOC_NAMES}\b", re.I)
DESCRIBED = (
    ("credits lapse", re.compile(r"\b(?:laps|nullif|forfeit|expir)\w*", re.I),
     (re.compile(r"\bcredit", re.I), re.compile(r"\b(?:laps|nullif|forfeit)\w*", re.I),
      re.compile(r"\b(?:terminat|expir)\w*", re.I))),
    ("exclusive remedy", re.compile(r"\b(?:exclusive|sole)\s+remed", re.I),
     (re.compile(r"\b(?:exclusive|sole)\s+remed", re.I),)),
)


def paper_doc(name: str) -> str:
    low = " ".join(name.lower().split())
    return ("MSA" if low.startswith(("msa", "master")) else
            "TOS" if low.startswith(("tos", "terms")) else
            "SLA" if low.startswith(("sla", "service level")) else "AUP")


# A verb binds to the reference's own clause, never to the sentence (round 2): each
# reference is masked as a token, the sentence split at ";", ":" and ", and/but/while",
# and the verb read only where the reference is its object ("replaces MSA clause 7.1",
# "despite MSA clause 8.4") or its subject ("MSA clause 15.3 is subject to this", "MSA
# clause 4.5 … does not apply"). Anything else names the clause: REFERS.
_T = "\x00"
_JOIN = r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+)"
_TOKEN = rf"{_T}\d+{_T}(?:\s*\([^()]*\))?"
_BEFORE = rf"(?:{_TOKEN}{_JOIN})*"
_AFTER = rf"(?:\s*\([^()]*\))?(?:{_JOIN}{_TOKEN})*"
_SPLIT = re.compile(r"[;:]|,\s+(?=(?:and|but|while|whereas)\b)", re.I)
#: a finite verb between a subject reference and "does not apply": the reference is
#: then not its subject ("MSA clause 9 remains in force; … does not apply")
_FINITE = re.compile(r"\b(?:is|are|was|were|shall|will|may|must|can|has|have|remains?|"
                     r"applies|apply|replaces?|includes?|survives?)\b", re.I)
#: what may come before a reference that opens its clause: a clause number, a conjunction
_OPENS = r"\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:(?:and|but|while|whereas)\s+)?"
_NOT_APPLY = r"\b(?:do|does|shall|will)\s+not\s+apply\b"


def _verb_in(segment: str, i: int, described: bool) -> str:
    t = re.escape(f"{_T}{i}{_T}")
    if re.search(rf"\b(?:despite|notwithstanding)\s+(?:the\s+provisions\s+of\s+)?"
                 rf"{_BEFORE}{t}", segment, re.I):
        return "DESPITE"
    if re.search(rf"\b(?:replac|supersed)\w*\s+(?:the\s+[\w' -]{{1,40}}?\s+in\s+)?"
                 rf"{_BEFORE}{t}", segment, re.I):
        return "REPLACES"
    for pattern, verb in (
            (r"\s+(?:is|are)\s+(?:hereby\s+)?(?:deleted\s+and\s+)?(?:replaced|superseded)\b",
             "REPLACES"),
            (r"\s+(?:is|are)\s+subject\s+to\b", "SUBJECT_TO"),
            (r"\s+includes?\b", "INCLUDES"),
            (r"\s+(?:shall\s+|will\s+)?survives?\b", "SURVIVES")):
        # the reference is the subject: it opens its clause ("MSA clause 15.3 is …"),
        # never "the right under MSA clause 13.2 includes …"
        if re.match(rf"{_OPENS}{_BEFORE}{t}{_AFTER}{pattern}", segment, re.I):
            return verb
    m = re.search(rf"{t}(.*?){_NOT_APPLY}", segment, re.I | re.S)
    if m and (described or not _FINITE.search(m.group(1))):
        return "DOES_NOT_APPLY"   # a described passage is the sentence's own subject
    return "REFERS"


def _verbs(sentence: str, spans: list[tuple[int, int]], described: set[int]
           ) -> dict[int, str]:
    masked = sentence
    for i, (a, b) in sorted(enumerate(spans), key=lambda x: -x[1][0]):
        masked = f"{masked[:a]}{_T}{i}{_T}{masked[b:]}"
    out: dict[int, str] = {}
    for segment in _SPLIT.split(masked):
        for m in re.finditer(rf"{_T}(\d+){_T}", segment):
            i = int(m.group(1))
            out[i] = _verb_in(segment, i, i in described)
    return out


def paper_references(clauses: list[Clause]) -> list[dict[str, Any]]:
    """Every reference this document makes into one of our documents, in order, one
    per (clause, document, number or described passage). Each: the client's clause and
    evidence, the document, the mode (NUMBERED / DESCRIBED), the number (and lettered
    sub-item), any title the client gave it, the verb and the client's sentence."""
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    units: list[tuple[str | None, dict[str, Any]]] = list(_index(clauses).items()) or [
        (None, {"text": "\n".join(c.content or "" for c in clauses),
                "evidence_id": None})]
    for source, unit in units:
        for sentence in re.split(r"(?<=[.;])\s+(?=[A-Z(])|\n", unit["text"]):
            found = [(m, m.group("list")) for m in _FORWARD.finditer(sentence)]
            found += [(m, m.group("list")) for m in _INVERTED.finditer(sentence)
                      if not any(f.start() <= m.start() < f.end() for f, _ in found)]
            found.sort(key=lambda f: f[0].start())
            lead = _DESCRIBED_LEAD.search(sentence)
            if lead and any(f.start() <= lead.start() < f.end() for f, _ in found):
                lead = None
            spans = [m.span() for m, _ in found] + ([lead.span()] if lead else [])
            verbs = _verbs(sentence, spans, {len(found)} if lead else set())
            for k, (m, listed) in enumerate(found):
                doc = paper_doc(m.group("doc"))
                for each in _EACH.finditer(listed):
                    key = (source, doc, each.group("n").rstrip("."))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"source": source, "evidence_id": unit["evidence_id"],
                                "doc": doc, "mode": "NUMBERED", "number": key[2],
                                "sub": each.group("sub"), "title": each.group("title"),
                                "verb": verbs.get(k, "REFERS"),
                                "quote": " ".join(sentence.split())})
            for name, said, _ours in DESCRIBED:
                if lead is None:
                    break
                key = (source, paper_doc(lead.group("doc")), name)
                if said.search(sentence[lead.end():]) and key not in seen:
                    seen.add(key)
                    out.append({"source": source, "evidence_id": unit["evidence_id"],
                                "doc": key[1], "mode": "DESCRIBED", "number": None,
                                "sub": None, "title": None, "described": name,
                                "verb": verbs.get(len(found), "REFERS"),
                                "quote": " ".join(sentence.split())})
    for r in out:
        r["evidence_id"] = None if r["evidence_id"] is None else str(r["evidence_id"])
    return out

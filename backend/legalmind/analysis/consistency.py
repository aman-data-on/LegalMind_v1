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
from typing import Any
from uuid import UUID

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


def observe(clauses: list[Clause],
            document_type: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """The document's observations: `structural` ones a person weighs (renewal two ways,
    a subject-to chain, the precedence rule, a missing non-payment remedy) and
    `additional` points (cross-references) shown last."""
    idx = _index(clauses)
    return {"structural": [*_renewal(idx), *_notice(idx), *_subject_to(idx),
                           *_precedence(idx), *_nonpayment(clauses, document_type),
                           *_our_details(clauses)],
            "additional": _cross_references(idx)}

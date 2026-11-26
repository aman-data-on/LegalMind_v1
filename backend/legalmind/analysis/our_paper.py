"""What a client's paper replaces in OUR paper — lawyer judgement, Phase 1 (`AM-476`).

Pure functions over (the client's references, our pinned documents): each reference
`consistency.paper_references` read is looked up in the version of our MSA, Terms of
Service, SLA or AUP pinned for this document, and shown with our own words beside the
client's. Read-only information: never a Finding, a Classification, a Rule Outcome, a
route, an effect, an answer or a Legal Decision (rules 10/13), and never read by
anything that makes one. No direction, effect or favour is stated (rule 7): the one
marker is a quoted fact — "Our text contains «AS IS»".

Fails closed (rule 15), each with its reason: the reference points nowhere in the
pinned document; the client's title for it does not fit ours; no MSA is pinned ("which
MSA?"); no stored copy of the policy is in force on the document's date; the brand is
unknown (never the other brand's text).
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from legalmind.analysis import consistency
from legalmind.extraction.liability import parse_number
from legalmind.mapping.engine import Clause

RESOLVED = "RESOLVED"
POINTS_NOWHERE = "POINTS_NOWHERE"
TITLE_MISMATCH = "TITLE_MISMATCH"
WHICH_MSA = "WHICH_MSA"
NO_STORED_COPY = "NO_STORED_COPY"
NO_BRAND = "NO_BRAND"
#: the verbs counted as "replaces or overrides" in the brief's one line
OVERRIDES = ("REPLACES", "DOES_NOT_APPLY", "DESPITE", "SUBJECT_TO")
#: the only marker: a phrase quoted from OUR text, never a statement of its effect
MARKERS = tuple(re.compile(p, re.I) for p in (
    r"\bas\s+is\b", r"\b(?:exclusive|sole)\s+remed\w*",
    r"\bno(?:n-?\s?|t\s+)refundable\b",
    r"\bwithout\s+(?:any\s+)?(?:deduction|set-?\s?off)(?:\s*(?:,|or)\s*set-?\s?off)?"))
#: a blank and up to three whole words after it ("________ months preceding the claim")
_BLANK = re.compile(r"_{3,}(?:[ \t]+[^\s.;_]+){0,3}|\[\s*[●•]?\s*\]")
QUOTE_CHARS = 1500
_WORD_NUMBER = re.compile(r"\b\d{1,4}\b|\b[a-z]+(?:-[a-z]+)?\b", re.I)


def msa_units(clauses: list[Clause]) -> dict[str, dict[str, Any]]:
    """Our MSA's numbered units, read as every document's are (`consistency._index`)."""
    return {n: {"title": u["title"], "text": " ".join(u["text"].split())}
            for n, u in consistency._index(clauses).items()}


_POLICY_HEAD = re.compile(rf"^\s*(?:Section\s+)?({consistency._NUM})\.?\s+(.+)$")


def policy_units(items: list[tuple[str, str | None, str]]
                 ) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """A stored policy's numbered sections ("13. Limitation of Liability" and every
    paragraph under it, unnumbered sub-headings included) and all its paragraphs (for a
    DESCRIBED reference) — from its `knowledge_items` (kind, clause, content) in order."""
    units: dict[str, dict[str, Any]] = {}
    paragraphs: list[str] = []
    current = None
    for kind, clause, content in items:
        head = _POLICY_HEAD.match(clause or "") if kind == "SECTION" else None
        if head:
            current = head.group(1).rstrip(".")
            units.setdefault(current, {"title": head.group(2).strip(), "text": ""})
        elif kind == "PARAGRAPH":
            paragraphs.append(" ".join(content.split()))
            if current:
                units[current]["text"] = f"{units[current]['text']} {content}".strip()
    for u in units.values():
        u["text"] = " ".join(u["text"].split())
    return units, paragraphs


def _unit(units: dict, number: str) -> dict[str, Any] | None:
    """Our unit by number; a top-level number gathers its sub-clauses in order."""
    parts = [u for n, u in units.items() if n == number or n.startswith(number + ".")]
    if not parts:
        return None
    first = units.get(number) or parts[0]
    return {"title": first["title"], "text": " ".join(p["text"] for p in parts).strip()}


def _numbers(text: str) -> set[float]:
    return {v for w in _WORD_NUMBER.findall(text) if (v := parse_number(w)) is not None}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower())) - {
        "clause", "section", "provision", "this", "that", "with", "from", "under"}


def _alike(a: str, b: str) -> bool:
    """One word family ("resale"/"resell", "modification"/"modify"): a shared six-letter
    stem, or two-thirds of the letters in order (`difflib`)."""
    return a[:6] == b[:6] or SequenceMatcher(None, a, b).ratio() >= 2 / 3


def title_fits(title: str, unit: dict[str, Any]) -> bool:
    """N2: the client's title is a summary, not our heading — it fits when one of its
    content words is in our heading or text (one word family), and (when it states
    numbers) one of its numbers is in our text. Words and numbers, never the string."""
    ours = f"{unit['title'] or ''} {unit['text']}"
    mine, theirs = _words(title), _words(ours)
    numbers = _numbers(title)
    return (not mine or any(_alike(a, b) for a in mine for b in theirs)) and \
        (not numbers or bool(numbers & _numbers(ours)))


def markers(text: str) -> list[str]:
    return [" ".join(m.group(0).split()) for p in MARKERS if (m := p.search(text))]


def _blank(text: str) -> str | None:
    m = _BLANK.search(text)
    return None if m is None else " ".join(m.group(0).split())


def _described(ref: dict, paragraphs: list[str]) -> str | None:
    ours = next(o for name, _s, o in consistency.DESCRIBED if name == ref["described"])
    return next((p for p in paragraphs if all(x.search(p) for x in ours)), None)


def _pin(base: dict) -> dict[str, Any]:
    return {k: base[k] for k in ("label", "file", "sha256", "date") if k in base}


def resolve(refs: list[dict], bases: dict[str, dict]) -> list[dict[str, Any]]:
    """Each reference with its status, the client's quote and — when found — our quote
    from the pinned document. `bases[doc]` is {label, file, sha256, date, units,
    paragraphs, newer?} or {"unresolved": WHICH_MSA | NO_STORED_COPY | NO_BRAND, ...}."""
    out = []
    for ref in refs:
        base = bases.get(ref["doc"]) or {"unresolved": NO_STORED_COPY}
        row: dict[str, Any] = {k: ref.get(k) for k in (
            "source", "evidence_id", "doc", "mode", "number", "sub", "title",
            "described", "verb")}
        row["client_quote"] = ref["quote"]
        if "unresolved" in base:
            row.update(status=base["unresolved"], hint=base.get("hint"))
            out.append(row)
            continue
        row["pin"] = _pin(base)
        unit: dict[str, Any] | None
        if ref["mode"] == "DESCRIBED":
            text = _described(ref, base["paragraphs"])
            unit = None if text is None else {"title": None, "text": text}
        else:
            unit = _unit(base["units"], ref["number"])
        if unit is None:
            row["status"] = POINTS_NOWHERE
            out.append(row)
            continue
        row["status"] = TITLE_MISMATCH if ref.get("title") and not title_fits(
            ref["title"], unit) else RESOLVED
        quote: str = unit["text"]
        row["ours"] = {"title": unit["title"], "quote": quote if len(quote) <= QUOTE_CHARS
                       else quote[:QUOTE_CHARS].rsplit(" ", 1)[0] + " …"}
        if found := markers(quote):
            row["markers"] = found
        if blank := _blank(quote):
            row["blank"] = blank
        newer = base.get("newer")
        if newer and ref["mode"] == "NUMBERED":
            later = _unit(newer["units"], ref["number"])
            if later is None or later["text"] != unit["text"]:
                row["changed_since"] = _pin(newer)
        elif newer and _described(ref, newer["paragraphs"]) != unit["text"]:
            row["changed_since"] = _pin(newer)
        out.append(row)
    return out


def fingerprint(refs: list[dict], candidates: list[dict]) -> list[dict[str, Any]]:
    """M1: how many of the client's titled MSA references fit each candidate MSA's
    clauses — a hint for Legal's pick, never a pick."""
    titled = [r for r in refs if r["doc"] == "MSA" and r.get("title")]
    if not titled:
        return []
    return [{**_pin(c), "fits": sum(bool((u := _unit(c["units"], r["number"]))
                                         and title_fits(r["title"], u)) for r in titled),
             "of": len(titled)} for c in candidates]


def overridden(rows: list[dict]) -> list[str]:
    """The brief's one line: our clauses (resolved) the client's paper replaces or
    overrides, each once, in order — "MSA 17.2", "TOS 13", "SLA (credits lapse)"."""
    said = [f"{r['doc']} {r['number'] or '(' + r['described'] + ')'}" for r in rows
            if r["status"] == RESOLVED and r["verb"] in OVERRIDES]
    return list(dict.fromkeys(said))


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december")
_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(" + "|".join(_MONTHS)
                   + r")\s*,?\s+(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b", re.I)
#: the document's own date is read from its opening rows only (a date deep in the text
#: is a deadline, not the document's)
_OPENING_ROWS = 8


#: the document's own date is anchored ("dated", "effective as of", "made on", "Draft …,")
_ANCHOR = re.compile(r"\b(?:dated|effective|made\s+on|entered\s+into|draft|as\s+of|"
                     r"signed\s+on|date\s*:)\b[^.;]{0,60}$", re.I)
#: …but not another document's date ("to the MSA dated …") or a deadline ("pay by …")
_NOT_OURS = re.compile(r"\b(?:(?:msa|agreement|contract|order|addendum|nda)\s+dated|"
                       r"pay\w*|due|by|before|no\s+later\s+than|until|within|"
                       r"deadline)\W+(?:on\s+)?(?:the\s+)?$", re.I)


def document_date(clauses: list[Clause]) -> date | None:
    """M2: the date the document gives itself on its opening rows — anchored ("dated",
    "effective as of", "made on", "Draft …,"), never another document's ("to the MSA
    dated …") nor a deadline ("pay by …"); else None (the caller then uses the upload
    date). A row of blanks ("____ day of ____") states none."""
    for clause in clauses[:_OPENING_ROWS]:
        text = clause.content or ""
        for m in _DATE.finditer(text):
            before = text[max(0, m.start() - 80):m.start()]
            if _NOT_OURS.search(before) or not _ANCHOR.search(before):
                continue
            try:
                return (date(int(m.group(3)), _MONTHS.index(m.group(2).lower()) + 1,
                             int(m.group(1))) if m.group(2) else
                        date(int(m.group(4)), int(m.group(5)), int(m.group(6))))
            except ValueError:
                continue
    return None

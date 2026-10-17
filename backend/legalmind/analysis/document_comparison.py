"""Diff-Talk — two documents side by side, clause by clause (owner, 2026-10-12).

Each side is either a document stored in LegalMind (any version the caller may read —
an uploaded MSA, NDA, PO, a client's contract) or one of the company's WEBSITE
documents (the CURRENT copy `AM-130`'s daily refresh keeps of the TOS, SLA, AUP and
Privacy Policy). The owner's instruction is a plain comparison: left against right,
no "approved" label on either side.

TEXT ONLY, like the version comparison (33.15/33.16): it says where the wording is the
same, changed, added or absent, never whether that is acceptable. No Finding,
Classification, Rule Outcome or Legal Decision is produced or quoted, and nothing is
written — the two documents are named in the request and nowhere else (AB-13 r3: no
document-to-document record).

WHY CLAUSES ARE PAIRED BY TEXT. Two documents number their clauses their own way, so
a shared number is not a shared clause. Both sides are cut at their top-level clause,
then paired by similarity, best pairs first. Below `PAIR_THRESHOLD` nothing is paired:
an unpaired clause is reported as being on one side only, never set beside an
unrelated one.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from difflib import SequenceMatcher
from functools import cache
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.knowledge import published
from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.domain import enums as E
from legalmind.mapping.service import body_rows

#: Similarity (see `_similarity`) two clauses need to be shown as one clause changed.
#: ponytail: lexical only, one global cut-off, measured on the Leapswitch and CloudPe
#: TOS/SLA/AUP/Privacy PDFs against the website. A clause rewritten in wholly new
#: words (CloudPe's SLA credit request, 0.27) stays "only left" + "only right" side
#: by side; the local embedding model (`AM-54`) is the upgrade if that matters.
PAIR_THRESHOLD = 0.4


class ComparisonNotPossible(Exception):
    """The comparison cannot be made as asked; the message says why."""


def _words(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def _norm(s: str) -> str:
    """Comparison text: spacing ignored and the clause's own leading number dropped
    — a clause renumbered word for word is unchanged (the reader still sees the
    number differ in the word diff)."""
    text = re.sub(r"^\W*\d+(?:\.\d+)*\.?\s*", "", (s or "").strip())
    # Spacing is the PDF's, not the wording: "Agreement.The" and "Agreement. The"
    # are the same words; a table's cell rules are its layout, not its words (the same
    # quote read as a table on one side and as lines on the other is unchanged).
    return re.sub(r"[\s|]+", "", _BLANK.sub(" ", _INVISIBLE.sub("", text)))


def _content(words: list[str]) -> set[str]:
    return {w for w in words if len(w) > 3}


# Words a heading match ignores: "AND" alone, or a recital's "B.", is no heading.
_TITLE_NOISE = {"and", "or", "of", "the", "to", "an", "in", "for", "on", "with", "by"}


def _title(unit: dict) -> str:
    return _title_words(unit.get("title") or "")


@cache    # cleared with `_score` after every comparison
def _title_words(title: str) -> str:
    return " ".join(w for w in _words(title)
                    if not w.isdigit() and len(w) > 1 and w not in _TITLE_NOISE)


def _similarity(a: dict, b: dict) -> float:
    """How alike two clauses are, 0..1+. The larger of word ORDER (a clause edited
    in place) and shared content WORDS (a clause the client rewrote in its own
    sentences), plus a bonus when both carry the same heading ("Late Fees" and
    "7. Late Fees") — a heading is the one thing a rewrite usually keeps. A marked-up
    clause is also read as it stood before the markup (`pair_text`, AM-146): the
    client rewrote both termination clauses of our MOU and, by their new words alone,
    each paired with the other (2026-10-17)."""
    return max(_score(x, _title(a), y, _title(b))
               for x in {a["text"], a.get("pair_text", a["text"])}
               for y in {b["text"], b.get("pair_text", b["text"])})


# Cleared after every comparison (`align`): keys hold whole clause texts, so a
# process-wide cache grew with every document ever compared (strict review,
# 2026-10-13). Unbounded WITHIN one comparison: a 4096 bound evicted the matrix
# every re-pair past ~64 clauses a side — 60 clauses took 10 s (review, 2026-10-14).
@cache
def _score(text_a: str, title_a: str, text_b: str, title_b: str) -> float:
    wa, wb = _words(text_a), _words(text_b)
    ca, cb = _content(wa), _content(wb)
    if not ca or not cb or not ca & cb:
        return 0.0
    shared = 2 * len(ca & cb) / (len(ca) + len(cb))
    # The quadratic matcher only when the cheap measure says it could matter.
    order = (SequenceMatcher(None, wa, wb, autojunk=False).ratio()
             if shared >= PAIR_THRESHOLD / 2 else 0.0)
    # By WORDS, never characters: as text, "b" is inside "arbitration" — which
    # paired a recital "B." with Governing Law (stress run, 2026-10-13).
    ta, tb = set(title_a.split()), set(title_b.split())
    same_heading = bool(ta and tb and (ta <= tb or tb <= ta))
    return max(order, shared * 0.9) + (0.3 if same_heading else 0.0)


def _pair(left: list[dict], right: list[dict]) -> dict[int, tuple[int, float]]:
    """Right index -> (left index, similarity); best pairs first, one each."""
    candidates = sorted(((s, i, j) for i, a in enumerate(left)
                         for j, b in enumerate(right)
                         if (s := _similarity(a, b)) >= PAIR_THRESHOLD),
                        reverse=True)
    pair: dict[int, tuple[int, float]] = {}
    taken: set[int] = set()
    for s, i, j in candidates:
        if i not in taken and j not in pair:
            pair[j] = (i, s)
            taken.add(i)
    return pair


def _join(units: list[dict], lo: int) -> list[dict]:
    """Units lo and lo+1 as one, named by the first in reading order."""
    a, b = units[lo], units[lo + 1]
    merged = {**a, "text": f'{a["text"]}\n{b["text"]}'}
    merged.pop("pair_text", None)
    if "evidence_ids" in a:
        merged["evidence_ids"] = a["evidence_ids"] + b["evidence_ids"]
    return [*units[:lo], merged, *units[lo + 2:]]


def _merge_once(left: list[dict], right: list[dict],
                pair: dict[int, tuple[int, float]]):
    """One unpaired clause folded into a paired neighbour, when that makes the pair
    MORE alike — the two sides cut the same text differently (a list numbered 1..7
    under one heading; headings the parser did not number). A clause genuinely added
    or absent only lowers the similarity, so it is never folded away. None when no
    fold improves anything."""
    by_left = {i: (j, s) for j, (i, s) in pair.items()}
    for j in range(len(right)):
        for n in (j - 1, j + 1):
            # A NUMBERED clause is the document's own clause, never a fragment
            # of its neighbour: a client's new "2. Non-Solicitation" folded into
            # "1. Liability" as CHANGED, with no ADDED row (review, 2026-10-14).
            if j not in pair and n in pair and right[j].get("ref") is None:
                lo = min(j, n)
                joined = _join(right, lo)[lo]
                if _improves(left[pair[n][0]], right[n], joined, pair[n][1], False):
                    return left, _join(right, lo)
    for i in range(len(left)):
        for n in (i - 1, i + 1):
            if i not in by_left and n in by_left and left[i].get("ref") is None:
                lo = min(i, n)
                joined = _join(left, lo)[lo]
                if _improves(right[by_left[n][0]], left[n], joined, by_left[n][1], True):
                    return _join(left, lo), right
    return None


def _order(a: str, b: str) -> float:
    return SequenceMatcher(None, _words(a), _words(b), autojunk=False).ratio()


def _improves(other: dict, alone: dict, joined: dict, was: float, on_left: bool) -> bool:
    """The fold makes the pair more alike AND keeps more of its word order — shared
    words alone rise whenever an added clause happens to reuse the vocabulary."""
    a, b = (joined, other) if on_left else (other, joined)
    return (_similarity(a, b) > was
            and _order(joined["text"], other["text"])
            > _order(alone["text"], other["text"]))


#: ponytail: folding re-pairs from scratch, so alignment grows steeply with clause
#: count (200 a side took seconds, 300 never finished — review, 2026-10-14). Real
#: contracts and the website documents hold tens of top-level clauses; past this the
#: comparison is refused rather than left to time out. Update the similarity matrix
#: per fold instead if documents this long ever need comparing.
MAX_CLAUSES = 150


def align(left: list[dict], right: list[dict]) -> list[dict]:
    if max(len(left), len(right)) > MAX_CLAUSES:
        raise ComparisonNotPossible(
            f"A document with more than {MAX_CLAUSES} clauses is too long to compare "
            "clause by clause.")
    try:
        left, right = _blocks(left), _blocks(right)
        split = _split_at_headings(left, right), _split_at_headings(right, left)
        if max(map(len, split)) <= MAX_CLAUSES:    # never refuses what was compared
            left, right = split
        rows = _align(left, right)
        for unit in (u for r in rows for u in (r["left"], r["right"]) if u):
            unit.pop("pair_text", None)    # for pairing only, never sent
        return rows
    finally:
        _score.cache_clear()
        _title_words.cache_clear()


def _squash(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def _table(line: str) -> bool:
    return line.startswith("| ")


def _blocks(units: list[dict]) -> list[dict]:
    """``units`` as the structural blocks a document comparison aligns (Litera,
    Draftable, Word's Compare all do this first): a TABLE that follows prose in a
    clause starts a block of its own, titled by its first cell — the client's proposal
    page sat inside "Dispute Resolution"; and a run of headings with nothing under them
    joins the block after it — a table's header row cut off at a page foot
    ("Description", "QTY", "Amount") read as three clauses the client added
    (2026-10-17). One lone heading stays a heading. View only."""
    out: list[dict] = []
    for unit in units:
        lines = unit["text"].splitlines()
        # Cut where a table starts after prose, never after it: what follows a table is
        # its footnote or its signature lines ("*99.95% for Power"), and anything new
        # below it is cut by its own heading.
        cuts = [k for k in range(2, len(lines))
                if _table(lines[k]) and not _table(lines[k - 1])
                and any(not _table(x) and x.strip() for x in lines[1:k])]
        if not cuts:
            out.append(unit)
            continue
        unit = {k: v for k, v in unit.items() if k != "pair_text"}
        for n, (lo, hi) in enumerate(zip([0, *cuts], [*cuts, len(lines)], strict=True)):
            cells = [c.strip() for c in lines[lo].strip("| ").split("|") if c.strip()]
            first = cells[0] if cells else lines[lo].strip()
            out.append({**unit, "text": "\n".join(lines[lo:hi]).strip(),
                        "id": f'{unit.get("id")}~{lo}', **({} if not n else {
                            "ref": None, "title": first[:120]})})
    merged: list[dict] = []
    held: list[dict] = []
    for unit in out:
        text = unit["text"].strip()
        if unit.get("ref") is None and len(text) <= 30 and len(text.split()) <= 3:
            held.append(unit)                 # a heading alone: wait for its block
            continue
        if len(held) == 1:
            # ONE lone heading is a heading ("Terms & Conditions:" over clause 1);
            # a header ROW is several cells in a run.
            merged += held
            held = []
        if held:
            ids = [e for h in held for e in h.get("evidence_ids", ())]
            unit = {**unit, "text": "\n".join([*(h["text"] for h in held), unit["text"]]),
                    **({"evidence_ids": ids + unit["evidence_ids"]}
                       if "evidence_ids" in unit else {})}
            held = []
        merged.append(unit)
    return merged + held


def _split_at_headings(units: list[dict], other: list[dict]) -> list[dict]:
    """`units` also cut at a line that is, word for word, a clause heading of `other`.

    The parser reads a bold heading as one only on a marked-up PDF (AM-146), so our
    clean MOU kept "Penalty Clause", "Confidentiality" and "Limitation of Liability"
    inside the clause above while the client's marked-up copy cut them out — eight
    clauses then showed as the client's alone (2026-10-17). A line on one side that
    the other side states as a heading is a heading on both. This view only: the
    parser and the evidence are untouched (rule 17)."""
    headings = {t for u in other if (t := _title(u))}
    # Spaces and punctuation aside too: a PDF wraps a narrow cell mid-word ("PROPOSA L"
    # for "PROPOSAL", the client's proposal heading against ours).
    squashed = {k for u in other if len(k := _squash(u.get("title") or "")) >= 4}
    out: list[dict] = []
    for unit in units:
        lines = unit["text"].splitlines()
        cuts = [k for k, line in enumerate(lines)
                if k and len(line) <= 80 and not line.startswith("| ")
                and (_title_words(line) in headings or _squash(line) in squashed)]
        if not cuts:
            out.append(unit)
            continue
        # Every piece a new id: a reader's choice kept against the whole clause must not
        # land on its first piece (AB-81 choices are keyed by clause id).
        unit = {k: v for k, v in unit.items() if k != "pair_text"}
        for n, (lo, hi) in enumerate(zip([0, *cuts], [*cuts, len(lines)], strict=True)):
            out.append({**unit, "text": "\n".join(lines[lo:hi]).strip(),
                        "id": f'{unit.get("id")}~{lo}', **({} if not n else {
                            "ref": None, "title": lines[lo].strip().rstrip(":")})})
    return out


def _align(left: list[dict], right: list[dict]) -> list[dict]:
    """Pair clauses by text; return rows in the RIGHT document's reading order, each
    left clause the right lacks placed where the left has it. A clause is a dict
    with at least `text`. Status: UNCHANGED · CHANGED · ADDED (right only) ·
    REMOVED (left only); `moved` marks a paired clause out of the left's order."""
    pair = _pair(left, right)
    # Re-pairs from scratch after every fold; `MAX_CLAUSES` bounds the cost.
    while (folded := _merge_once(left, right, pair)) is not None:
        left, right = folded
        pair = _pair(left, right)
    # Two openings are counterparts however differently they are worded: a
    # reader asks "how does their introduction differ from ours?", not to see
    # one row "missing" and another "added" (2026-10-12, CloudPe vs our SLA).
    if (left and right and 0 not in pair and all(i != 0 for i, _ in pair.values())
            and left[0].get("ref") is None and right[0].get("ref") is None):
        pair[0] = (0, 0.0)
    taken = {i for i, _ in pair.values()}
    in_order = _longest_increasing(
        [pair[j][0] for j in range(len(right)) if j in pair])
    rows: list[dict] = []
    emitted: set[int] = set()

    def absent_before(limit: int) -> None:
        for i in range(limit):
            if i not in taken and i not in emitted:
                emitted.add(i)
                rows.append({"status": "REMOVED", "moved": False,
                             "left": left[i], "right": None})

    for j, unit in enumerate(right):
        if j not in pair:
            rows.append({"status": "ADDED", "moved": False, "left": None,
                         "right": unit})
            continue
        i = pair[j][0]
        if i in in_order:
            absent_before(i)
        same = _norm(left[i]["text"]) == _norm(unit["text"])
        rows.append({"status": "UNCHANGED" if same else "CHANGED",
                     "moved": i not in in_order, "left": left[i], "right": unit})
    absent_before(len(left))
    return rows


def _longest_increasing(seq: list[int]) -> set[int]:
    """Values of one longest strictly increasing subsequence — the clauses that kept
    the source's order; every other paired clause was moved."""
    tails: list[int] = []          # index into seq of the smallest tail per length
    prev = [-1] * len(seq)
    for k, v in enumerate(seq):
        lo = bisect_left(tails, v, key=seq.__getitem__)
        prev[k] = tails[lo - 1] if lo else -1
        if lo == len(tails):
            tails.append(k)
        else:
            tails[lo] = k
    out, k = set(), tails[-1] if tails else -1
    while k != -1:
        out.add(seq[k])
        k = prev[k]
    return out


def _top(section: str | None) -> str | None:
    return re.split(r"[.\-(]", section)[0].strip() or section if section else None


def _starts_clause(row: M.DocumentEvidence, top: str | None, current: str | None) -> bool:
    """A new top-level number starts a clause — unless a letter is glued to it: a line
    wrapped at "Section 70B(6) of the IT Act" is a cross-reference the parser read as
    clause 70 (the parser itself is not retuned for this view)."""
    if top is None or top == current:
        return False
    number = re.escape(row.section_number or "")
    return not re.match(rf"^\W*(?:section|clause|article)?\s*{number}[A-Za-z]",
                        row.content or "", re.IGNORECASE)


#: Never words: icon-font glyphs a browser print leaves in the text (U+E90C after
#: "period."), joiners and soft hyphens — dropped. The stored evidence is untouched.
_INVISIBLE = re.compile("[\ue000-\uf8ff\u200c\u200d\u00ad]")
#: Blanks that do not look like one: a Google Docs export puts a zero-width space
#: where the space belongs ("4.\u200bThis") — a space, as `AM-45` r6 already reads it.
_BLANK = re.compile("[\u200b\u2060\ufeff\u00a0]")


_NUMBERING = re.compile(r"#(?:\.#)*\.")


def _running_lines(rows: list[M.DocumentEvidence]) -> set[str]:
    """Lines on 3+ pages, page numbers aside — a printed header or footer
    ("https://…/terms-of-service.php 1/9"), never clause text."""
    pages: dict[str, set] = {}
    for row in rows:
        for line in (row.content or "").splitlines():
            key = re.sub(r"\d+", "#", line.strip())
            # A printed header/footer carries a number (page, date, URL) or is long
            # ("Terms of Service - Leapswitch Networks Pvt. Ltd."). A short word on
            # its own line ("Agreement.") repeats across pages in real wording too —
            # counting it as a header deleted it from our MSA (2026-10-12).
            # Clause numbers ("4.", "4.1.") are never a header, though "#.#." repeats.
            if (key == "#" or len(key) >= 25 or ("#" in key and len(key) >= 3
                    and not _NUMBERING.fullmatch(key))):
                pages.setdefault(key, set()).add(row.page_number)
    return {k for k, p in pages.items() if len(p) >= 3}


def _clean(text: str, running: set[str]) -> str:
    lines = [ln for ln in _BLANK.sub(" ", _INVISIBLE.sub("", text)).splitlines()
             if re.sub(r"\d+", "#", ln.strip()) not in running]
    return "\n".join(lines)


#: A top-level clause line inside a row: "4." alone (its heading on the next line)
#: or "4. Scope of Services". "4.1." never matches — a sub-clause stays inside 4.
#: A markup tool's "[13.] Service Termination" is clause 13 too (AM-146).
_CLAUSE_LINE = re.compile(r"\s*(?:(\d{1,3})\.|\[(\d{1,3})\.\])(?:\s+(\S.*?))?\s*")


#: Parts that follow the numbered clauses and are no clause's: a schedule, annexure,
#: appendix or exhibit heading, and the signature block. Lumped into the last clause
#: they read as "21. General Provisions changed" when the client added a Schedule A
#: and renamed the signing entity (owner's MSA, 2026-10-12).
_PART_LINE = re.compile(
    r"\s*((?:SCHEDULE|ANNEXURE|ANNEX|APPENDIX|EXHIBIT)\b.*|IN WITNESS WHEREOF\b.*)",
    re.IGNORECASE)
_NO_MORE_CLAUSES = "100000"   # inside a part, its own "1." never starts a clause


def _part_title(line: str) -> str:
    line = line.strip()
    return "Signatures" if line.upper().startswith("IN WITNESS") else line[:120]


def _follows(number: str, current: str | None) -> bool:
    """`number` is the next clause after `current` (allowing a few skipped), so a
    list restarting at 1 inside clause 16, or a page number, never starts one."""
    at = int(current) if current and current.isdigit() else 0
    return at < int(number) <= at + 3


def version_clauses(rows: list[M.DocumentEvidence]) -> list[dict]:
    """Evidence rows grouped by top-level clause number (4, 4.1, 4.2 -> one clause 4).
    An unnumbered HEADING starts a clause of its own (paper that names its clauses
    without numbering them); any other unnumbered row continues the clause before
    it (a page break, a sub-paragraph). Text before the first is the opening text.

    The parser's numbering is not trusted alone: a Google Docs export hides a
    zero-width space after every number ("4.\u200b"), the parser then numbers
    nothing and keeps one row per PAGE (owner's MSA, 2026-10-12: 10 clauses wrongly
    reported missing). So each row is also split at its own top-level clause lines."""
    out: list[dict] = []
    running = _running_lines(rows)
    last = None              # the last NUMBERED clause, across unnumbered headings
    for row in rows:
        top = _top(row.section_number)
        heading = top is None and (row.evidence_metadata or {}).get("heading")
        if not out or heading or _starts_clause(row, top, out[-1]["ref"]):
            out.append({"ref": top,
                        "title": _INVISIBLE.sub("", row.section_title or "") or None
                        if top or heading else None,
                        "page": row.page_number, "evidence_ids": [], "parts": [],
                        # Stable across reloads (a choice is kept against it).
                        "id": str(row.id)})
        last = out[-1]["ref"] or last
        out[-1]["evidence_ids"].append(str(row.id))
        lines = _clean(row.content or "", running).splitlines()
        start = 0
        for k, line in enumerate(lines):
            part = _PART_LINE.fullmatch(line)
            # A heading is set in capitals; a wrapped line starting "Schedule 1 sets
            # out the fees" is wording. "IN WITNESS WHEREOF" is distinctive in any case.
            if part and (line.strip().isupper()
                         or line.strip().upper().startswith("IN WITNESS")):
                out[-1]["parts"].append("\n".join(lines[start:k]))
                out.append({"ref": None, "title": _part_title(line),
                            "id": f"{row.id}#{k}",
                            "page": row.page_number, "evidence_ids": [str(row.id)],
                            "parts": []})
                start, last = k, _NO_MORE_CLAUSES
                continue
            m = _CLAUSE_LINE.fullmatch(line)
            ref = (m.group(1) or m.group(2)) if m else None
            if m and ref and _follows(ref, last):
                out[-1]["parts"].append("\n".join(lines[start:k]))
                title = m.group(3) or next((ln.strip() for ln in lines[k + 1:]
                                            if ln.strip()), None)
                out.append({"ref": ref, "title": title, "page": row.page_number,
                            "id": f"{row.id}#{k}",
                            "evidence_ids": [str(row.id)], "parts": []})
                start, last = k, ref
        out[-1]["parts"].append("\n".join(lines[start:]))
    # A marked-up row's wording before the markup (AM-146), for pairing only — a
    # clause cut out of the middle of a row has no original of its own, and nor has the
    # clause it was cut from: the row's original holds both.
    before = {str(r.id): ((r.evidence_metadata or {}).get("revision") or {})
              .get("original") for r in rows}
    content = {str(r.id): r.content or "" for r in rows}
    shared = Counter(e for c in out for e in c["evidence_ids"])
    for c in out:
        c["text"] = "\n".join(c.pop("parts")).strip()
        if any(before[e] for e in c["evidence_ids"]) and \
                all(shared[e] == 1 for e in c["evidence_ids"]):
            c["pair_text"] = _clean("\n".join(before[e] or content[e]
                                              for e in c["evidence_ids"]), running)
    return [c for c in out if c["text"]]      # an empty opening is no clause


def website_clauses(items: Sequence[Any]) -> list[dict]:
    """The policy's records grouped under its top-level headings. The page title (h1)
    holds the opening text; deeper headings stay inside their clause as lines."""
    depth: dict[Any, int] = {}
    out: list[dict] = []
    for it in items:                                   # ordinal order: parents first
        depth[it.id] = depth.get(it.parent_id, -1) + 1
        if it.kind == "DOCUMENT":
            continue
        if it.kind == "SECTION" and depth[it.id] <= 2:
            number = re.match(r"\s*(\d+(?:\.\d+)*)\.?\s", it.clause or "")
            out.append({"ref": number.group(1) if number and depth[it.id] == 2 else None,
                        "id": str(it.id),
                        "title": it.clause, "parts": [] if depth[it.id] == 1
                        else [it.clause]})
            continue
        if not out:
            out.append({"ref": None, "title": None, "parts": [], "id": str(it.id)})
        out[-1]["parts"].append(_BLANK.sub(" ", _INVISIBLE.sub("", it.content)))
    for c in out:
        c["text"] = "\n".join(c.pop("parts")).strip()
    return [c for c in out if c["text"]]


def website_documents(db: DBSession) -> list[dict[str, Any]]:
    """The website documents that can be compared — those with a CURRENT copy."""
    current = {r.source_type: r for r in db.execute(text(
        f'SELECT source_type, title, version, effective_from FROM '
        f'"{config.assist_schema()}".knowledge_sources WHERE status = \'CURRENT\' '
        "AND source_type = ANY(:t)"), {"t": list(published.SOURCE_TYPES)})}
    return [{"key": p.key, "title": p.name, "url": p.url,
             "version": current[p.source_type].version,
             "effective_from": current[p.source_type].effective_from}
            for p in published.POLICIES if p.source_type in current]


def website_side(db: DBSession, key: str) -> dict[str, Any]:
    policy = next((p for p in published.POLICIES if p.key == key), None)
    doc = next((d for d in website_documents(db) if d["key"] == key), None)
    if policy is None or doc is None:
        raise ComparisonNotPossible(f"The website document {key} is not available.")
    schema = config.assist_schema()
    items = db.execute(text(
        f'SELECT i.id, i.parent_id, i.kind, i.clause, i.content '
        f'FROM "{schema}".knowledge_items i JOIN "{schema}".knowledge_sources s '
        "ON s.id = i.source_id WHERE s.source_type = :t AND s.status = 'CURRENT' "
        "ORDER BY i.ordinal"), {"t": policy.source_type}).all()
    return {"document": {"kind": "WEBSITE", **doc}, "clauses": website_clauses(items)}


def version_side(db: DBSession, contract: M.Contract,
                 version: M.DocumentVersion) -> dict[str, Any]:
    run_id = latest_completed_run_id(db, version.id)
    # Headers and footers are page furniture, not clauses (BR-4).
    evidence = body_rows(db.execute(
        select(M.DocumentEvidence)
        .where(M.DocumentEvidence.document_version_id == version.id,
               M.DocumentEvidence.processing_run_id == run_id)
        .order_by(M.DocumentEvidence.page_number.asc().nulls_last(),
                  M.DocumentEvidence.start_offset.asc().nulls_last(),
                  M.DocumentEvidence.id.asc())).scalars().all()) if run_id else []
    if not evidence:
        raise ComparisonNotPossible(
            f"{contract.name} has no extracted text to compare — an unreadable or "
            "still-processing document cannot be compared.")
    return {"document": {"kind": "DOCUMENT", "title": contract.name,
                         "contract_id": str(contract.id),
                         "document_version_id": str(version.id),
                         "version_number": version.version_number,
                         "filename": version.original_filename,
                         "unread_pages": _unread_pages(db, version, evidence)},
            "clauses": version_clauses(evidence)}


def _unread_pages(db: DBSession, version: M.DocumentVersion,
                  evidence: list[M.DocumentEvidence]) -> list[int]:
    """Pages with no readable text — named on screen, never silently skipped. Often a
    blank page (the owner's MSA, page 19: only its page number); sometimes a scan
    OCR could not read. Only asked when extraction was not COMPLETE."""
    if version.extraction_status == E.ExtractionStatus.COMPLETE:
        return []
    totals = [(r.run_metadata or {}).get("pages_total") for r in db.execute(
        select(M.DocumentProcessingRun)
        .where(M.DocumentProcessingRun.document_version_id == version.id)).scalars()]
    total = max((t for t in totals if isinstance(t, int)), default=0)
    read = {e.page_number for e in evidence}
    return [p for p in range(1, total + 1) if p not in read]


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    rows = align(left["clauses"], right["clauses"])
    return {
        "left": left["document"],
        "right": right["document"],
        "summary": {s: sum(r["status"] == s for r in rows)
                    for s in ("UNCHANGED", "CHANGED", "ADDED", "REMOVED")}
                   | {"MOVED": sum(r["moved"] for r in rows)},
        "clauses": rows,
    }


# --- The reader's choices (AB-81 / `AM-136`) ---------------------------------------

#: A side as stored: a document version id, or a website key — exactly one.
Side = tuple[UUID | None, str | None]
#: Column widths, kept in step with migration d3f7a1c9e5b2.
KEY_MAX, ROW_KEY_MAX = 64, 200
#: ponytail: a pair holds one row per difference, so tens; this only stops a client
#: filling the table. Raise it if a real comparison ever has more differences.
PAIR_MAX = 2000


def _pair_filter(left: Side, right: Side) -> ColumnElement[bool]:
    """`= value` or `IS NULL` per column — never IS NOT DISTINCT FROM, which no
    index serves — so the pair constraint's own index answers the read."""
    C = M.ComparisonChoice
    cols = ((C.right_version_id, right[0]), (C.right_key, right[1]),
            (C.left_version_id, left[0]), (C.left_key, left[1]))
    return and_(*(c.is_(None) if v is None else c == v for c, v in cols))


def read_choices(db: DBSession, left: Side, right: Side,
                 user_id: UUID) -> dict[str, dict]:
    """Every choice for this pair — one indexed query, the chooser's name joined."""
    C = M.ComparisonChoice
    rows = db.execute(
        select(C.row_key, C.choice, C.decided_by, C.updated_at, M.User.name)
        .join(M.User, M.User.id == C.decided_by)
        .where(_pair_filter(left, right))).all()
    return {r.row_key: {"choice": r.choice, "decided_by": r.name,
                        "decided_by_me": r.decided_by == user_id,
                        "updated_at": r.updated_at.isoformat()} for r in rows}


def write_choices(db: DBSession, left: Side, right: Side,
                  choices: dict[str, str], user_id: UUID) -> None:
    """One multi-row upsert: a choice replaces the pair's earlier one for that
    difference, and names who made it (r5). Refused past `PAIR_MAX` rows."""
    C = M.ComparisonChoice
    keys = db.scalars(select(C.row_key).where(_pair_filter(left, right))).all()
    if _counted(db, left, right, keys) + len(choices) > PAIR_MAX:
        raise ComparisonNotPossible("This comparison already holds too many choices.")
    stmt = insert(C).values([
        {"left_version_id": left[0], "left_key": left[1], "right_version_id": right[0],
         "right_key": right[1], "row_key": k, "choice": v, "decided_by": user_id}
        for k, v in choices.items()])
    db.execute(stmt.on_conflict_do_update(
        constraint="uq_comparison_choices_pair_row",
        set_={"choice": stmt.excluded.choice, "decided_by": stmt.excluded.decided_by,
              "updated_at": func.now()}))


def _counted(db: DBSession, left: Side, right: Side, keys: Sequence[str]) -> int:
    """The pair's rows that count against `PAIR_MAX`. A website side refreshed by
    `AM-130` has new clause ids, so a choice naming an id of an earlier copy
    matches no difference: kept, never shown and NEVER COUNTED (AB-81 r6)."""
    live = {n: _current_item_ids(db, side[1]) for n, side in ((1, left), (2, right))
            if side[1] is not None}
    parts = [[*k.split("|"), "", ""] for k in keys]     # status|left id|right id
    return sum(all(not p[n] or p[n] in want for n, want in live.items()) for p in parts)


def _current_item_ids(db: DBSession, key: str) -> set[str]:
    policy = next((p for p in published.POLICIES if p.key == key), None)
    if policy is None:
        return set()
    schema = config.assist_schema()
    return {str(i) for i in db.scalars(text(
        f'SELECT i.id FROM "{schema}".knowledge_items i '
        f'JOIN "{schema}".knowledge_sources s ON s.id = i.source_id '
        "WHERE s.source_type = :t AND s.status = 'CURRENT'"),
        {"t": policy.source_type})}

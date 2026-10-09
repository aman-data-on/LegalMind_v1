"""Domain C — the approved statute corpus (`AM-32` r6–r8, `AM-47`).

Three properties are locked consequences, not preferences:

**No statute without a provenance record** (r6). `ingest_statute` refuses a file whose
registry entry leaves any provenance field empty, and records the file's SHA-256 so the
row can be re-verified against the file. The quality caveat the owner's supply carries —
India Code re-verification pending (C-16 item 2) — is stated IN the record (`AM-47` r2),
never hidden by it. Rule 21: nothing is fetched; the owner supplies.

**Section-based chunking, cited Act + section** (r7). A chunk is one section of the Act
as the Act itself numbers it (`43A.`, `73.`, or a direction `(iv)` where the instrument
numbers that way); `section_number` is NOT NULL by schema, so a page-only citation cannot
exist. The arrangement-of-sections table and footnotes are not sections: a piece too
short to be a section body is dropped, and a numbered line that breaks the Act's
monotonic order (a footnote `1.` after `43A.`) is folded into the section it annotates.

**Background law only** (r7; source-material ruling 2026-08-18). Nothing here produces a
Requirement, a Company Standard, a Legal Rule, a threshold or an acceptance position,
and no statute chunk ever reaches the evaluator. Statute text MAY enter a generation
payload (r8) — it is public law — in its own evidence set, never merged with document
or position text (`AM-45` r2).
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.knowledge import authority
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P

STATUTE_CHUNKING_ALGORITHM_VERSION = "section-6"
# A section body shorter than this is an arrangement-of-sections entry or a footnote,
# not a section: dropped, never cited.
MIN_SECTION_CHARS = 150
MAX_SECTION_CHARS = 2000
# `total_sections` in the registry is the count of DISTINCT section numbers an Act
# yields, and it is a boundary check on the extraction, not an assertion about the
# chunker. Measured across the `section-1` -> `section-2` change (2026-09-20): the
# distinct-section count held for 15 of 17 Acts while the CHUNK count moved for 8, and
# the two that moved did so by one repealed stub each ("[...] Omitted by s. 255 and the
# Eleventh Schedule"). So an exact match would fail on stub churn and prove nothing,
# while a floor still catches the failure that matters — an extraction that breaks and
# yields 80 sections where the Act has 800.
SECTION_COUNT_FLOOR = 0.95

PROVENANCE_FIELDS = ("official_title", "act_number_year", "jurisdiction", "source",
                     "source_ref", "as_amended_date", "supplied_by", "supplied_at")

# The statuses a reader is served (`AM-125`). STAGED is a generation built beside the
# live one and not yet swapped in; STANDBY the generation swapped out, kept for a
# rollback; WITHDRAWN an Act refused on re-ingest (`AM-81` r3) or a retired generation.
# None of those three is read by search, the router or the refusal text.
LIVE_STATUSES = ("CURRENT", "REPEALED")


def _live_sql(column: str = "s.status") -> str:
    """SQL predicate: is this statute row served? The one definition every corpus-wide
    read uses — both search paths, `jurisdictions`, `available` and `holdings`."""
    return f"{column} IN {LIVE_STATUSES!r}"

# India Code PDFs prefix an inserted section with its footnote marker — `3[43A. …`
# — so an optional `\d{1,2}[` is admitted before the number; U+00A0/U+200B are
# blanks after the number (the same lesson as the document chunker).
# `\.` followed by blanks OR directly by a capital/quote/bracket: India Code's Contract
# Act body reads `73.Compensation for loss…` with no space (measured 2026-09-08 — §73
# had folded into §72 and the Constitution's own ss. 73–74 citation was unanswerable).
_SECTION_START = re.compile(
    r"^[ \t]*(?:\d{1,2}\[)?(?P<num>\d{1,3}[A-Z]{0,2})\."
    r"(?:[ \t\u00a0\u200b]+(?=\S)|(?=[A-Z\u201c\"\[(]))",
    re.MULTILINE)
_DIRECTION_START = re.compile(r"^[ \t]*\((?P<num>[ivxl]{1,5})\)[ \t]+(?=\S)",
                              re.MULTILINE)
_MARGINAL_END = re.compile("\\.\\s*[\u2014\u2013-]|\u2014|\n")
# `section-6`: a line that opens "(4) of section 35" after "…under sub-section" (or
# "section(s)", "clause") is a wrapped cross-reference, not sub-section (4). Taken as
# one, IT Act s. 2 restarted and was quarantined whole once its footnotes were cut. A
# lowercase-led item IS still a unit (Income-tax s. 10(23) reads "(23) any fund …").
_SUBSECTION = re.compile(r"(?<=\n)(?<!section\n)(?<!section \n)(?<!sections\n)"
                         r"(?<!sections \n)(?<!clause\n)(?<!clause \n)"
                         r"(?=[ \t]*\(\d{1,2}\)[ \t])")
# A section's own opening: "3. Appointment of officers.––The Board …" (heading, then a
# dash and the law). An arrangement entry or a footnote has no dash after its heading.
_SHORT_SECTION = re.compile(r"[ \t]*\d{1,3}[A-Z]{0,2}\.[ \t]+[A-Z][^.\n]*\.[ \t]*"
                            "[\u2014\u2013-]+[ \t]*[A-Z]")
_SECTION_IN_QUESTION = re.compile(
    r"\b(?:section|sec\.?|s\.)\s*(?P<num>\d{1,3}[A-Za-z]{0,2})\b", re.IGNORECASE)

# A SCHEDULE is a citable unit of the Act, and it is NOT a section: it carries no
# section number, so before `section-3` every Schedule folded into whichever section
# happened to be last. That is why the DPDP Act's penalty Schedule was cited as
# "s. 44(3) — Amendments to certain Acts" (measured live 2026-09-21), and why the
# Companies Act's seven Schedules sat inside s. 470.
#
# The heading must be the WHOLE line: the Companies Act, 1956 carries
# "347. APPLICATION OF SCHEDULE VIII TO CERTAIN MANAGING AGENTS", which is a section.
_SCHEDULE_START = re.compile(
    r"^[ \t]*(?:\d{1,2}\[)?(?:THE[ \t]+)?"
    r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH)?[ \t]*"
    r"SCHEDULE(?:[ \t]+[IVXL]+A?)?[ \t]*\.?[ \t]*$", re.MULTILINE)
# An arrangement-of-sections table lists the Schedules too, at the FRONT. A real
# Schedule follows the last section, so only a heading in the closing quarter counts.
SCHEDULE_TAIL_FRACTION = 0.75
# A Schedule sorts above every section number, so the monotonic fold neither swallows
# it nor lets it swallow a section.
_SCHEDULE_RANK = 10 ** 6
# India Code and Taxmann prints also set an inserted section's footnote marker as a
# bare superscript, with no bracket to separate it: `²66A.` extracts as `266A.`
# and `⁸60.` as `860.`. The number then reads far higher than any real
# section, and because the fold rule below absorbs a piece whose number falls BELOW the
# running one, a single glued digit swallowed the entire rest of the Act — 26 chunks of
# the IT Act under a non-existent "s. 266A", 349 of the CPC under "s. 860".
# The repair is bounded by the Act's OWN arrangement of sections (see
# `_repair_glued_markers`) and refuses itself when it would fire more than this many
# times, because that means the ceiling is wrong rather than the Act.
MAX_SECTION_NUMBER_REPAIRS = 5


class StatuteIngestRefused(Exception):
    """The file cannot be ingested as approved statute material."""


@dataclass(frozen=True)
class StatuteChunk:
    section_number: str
    sub_section: str | None
    marginal_note: str | None
    content: str
    char_start: int
    char_end: int


def _section_key(num: str) -> tuple[int, str]:
    if "SCHEDULE" in num.upper():
        return (_SCHEDULE_RANK, num.upper())
    digits = re.match(r"\d+", num)
    if not digits:
        return (0, num)
    return (int(digits.group()), num[len(digits.group()):])


_ROMAN = re.compile(r"^[IVXL]+A?$", re.IGNORECASE)


def _schedule_label(heading: str) -> str:
    """The Act's own name for a Schedule, as a citation renders it.

    Drops the footnote marker the print glues to the heading (`1[THE FIRST SCHEDULE`)
    and the trailing period, and capitalises for reading while leaving a roman numeral
    upper — "the First Schedule", "Schedule I", "Schedule IA".
    """
    words = re.sub(r"^\s*\d{1,2}\[", "", heading).strip().rstrip(".").split()
    return " ".join(w.upper() if _ROMAN.match(w) else w.capitalize() for w in words)


def _repair_glued_markers(numbered: list[tuple[int, str]],
                          ceiling: tuple[int, str] | None) -> list[tuple[int, str]]:
    """Strip a footnote marker glued to a section number, bounded by the Act itself.

    `ceiling` is the highest section number in the Act's own arrangement of sections.
    A body number above it cannot be a section number, so its leading digits are a
    marker: they are dropped one at a time and the first form that lands at or below
    the ceiling AND continues the sequence wins. Nothing else is touched.

    The whole pass refuses itself past `MAX_SECTION_NUMBER_REPAIRS`. A genuine glued
    marker is rare — one in the IT Act, two in the CPC. Hundreds means the ceiling is
    untrustworthy, which is the Taxmann Income-tax print, where an unguarded pass
    rewrote real sections 194C and 115VA to 94C and 15VA. Refusing leaves that Act
    exactly as it is today rather than corrupting it differently.
    """
    if not ceiling:
        return numbered
    out: list[tuple[int, str]] = []
    rewrites = 0
    running = (0, "")
    for position, num in numbered:
        fixed = num
        key = _section_key(num)
        if key[0] < _SCHEDULE_RANK and key > ceiling:
            lead = re.match(r"\d*", num)
            for cut in range(1, len(lead.group()) if lead else 0):
                candidate = _section_key(num[cut:])
                if candidate[0] and running < candidate <= ceiling:
                    fixed = num[cut:]
                    rewrites += 1
                    break
        key = _section_key(fixed)
        if key > running:
            running = key
        out.append((position, fixed))
    if rewrites > MAX_SECTION_NUMBER_REPAIRS:
        log_event("assist.statutes.repair_refused", rewrites=rewrites,
                  ceiling=ceiling[0], level=logging.WARNING)
        return numbered
    if rewrites:
        log_event("assist.statutes.repaired", rewrites=rewrites, level=logging.INFO)
    return out


def _marginal_note(body: str) -> str | None:
    m = _MARGINAL_END.search(body)
    note = body[: m.start()].strip() if m else body.strip()[:200]
    return note[:200] or None


def _windows(text: str) -> list[str]:
    """Cut text into pieces of at most MAX_SECTION_CHARS, at a blank where one exists.

    `section-4` (2026-09-24, roadmap PHASE 2): a single sub-section longer than the cap
    used to be kept whole — 26 CGST chunks over 2,000 characters, one CPC chunk of
    126,670 — so the cap was a packing target, not a bound. The pieces concatenate back
    to `text` exactly, so no character is lost and offsets stay true."""
    out = []
    while len(text) > MAX_SECTION_CHARS:
        cut = text.rfind(" ", MAX_SECTION_CHARS // 2, MAX_SECTION_CHARS)
        cut = cut if cut > 0 else MAX_SECTION_CHARS
        out.append(text[:cut])
        text = text[cut:]
    return [*out, text] if text else out


def _split_long(section: str) -> list[tuple[str | None, str]]:
    """Split an over-long section at its sub-section markers, greedily packed; every
    piece is then bounded by MAX_SECTION_CHARS (`_windows`)."""
    parts = [p for p in _SUBSECTION.split(section) if p.strip()]
    packed: list[tuple[str | None, str]] = []
    current = ""
    current_sub: str | None = None
    for part in parts or [section]:
        sub = re.match(r"[ \t]*(\(\d{1,2}\))", part)
        if current and len(current) + len(part) > MAX_SECTION_CHARS:
            packed.append((current_sub, current))
            current, current_sub = part, sub.group(1) if sub else None
        else:
            if not current:
                current_sub = sub.group(1) if sub else None
            current += part
    if current:
        packed.append((current_sub, current))
    return [(sub, piece) for sub, body in packed for piece in _windows(body)]


def _body_from(text: str, bounds: list, keys: list) -> int:
    """Where the body begins. India Code PDFs open with an ARRANGEMENT OF SECTIONS —
    one line per section, the same numbers — and footnotes carry numbers of their
    own, so the first "1." is not the Act's first section. The body starts at the
    first occurrence of the LOWEST section number whose piece is a body (long) and
    whose successor is a higher-numbered body: arrangement entries fail the second
    test (their successors are one-liners), footnotes come later. Everything before
    that point is front matter and is not a section."""
    def piece_len(i: int) -> int:
        return len(text[bounds[i][0]:bounds[i + 1][0]].strip())
    lowest = min(keys) if keys else None
    for i, key in enumerate(keys):
        if key == lowest and piece_len(i) >= MIN_SECTION_CHARS and i + 1 < len(keys) \
                and keys[i + 1] > key and piece_len(i + 1) >= MIN_SECTION_CHARS:
            return i
    return 0


_END_MATTER = re.compile(r"^[ \t]*STATEMENT OF OBJECTS AND REASONS[ \t]*$", re.MULTILINE)


def strip_end_matter(text: str) -> str:
    """`section-5` (2026-09-27): an India Code print closes with the Bill's STATEMENT
    OF OBJECTS AND REASONS — editorial matter, not law. It was stored under the last
    Schedule or section of eight Acts (the DPDP Schedule, IGST s. 25), where it could be
    cited as statute. Cut at that heading when it opens a line in the closing quarter;
    measured at 93.5–98.8% of every print that has one."""
    text = text or ""
    ends = [m.start() for m in _END_MATTER.finditer(text)
            if m.start() > len(text) * SCHEDULE_TAIL_FRACTION]
    return text[:ends[0]] if ends else text


# `section-6` (2026-10-08, owner D3, `AM-125`): an India Code page sets its amendment
# footnotes ("1. Subs. by Act 6 of 1899, s. 2, for …") as separate text blocks at its
# foot, after the law and before the page number. They were folded into the section
# above (638 of 5,011 chunks carried one), and the IGST Act's footnote "3. Ins. by Act
# 32 of 2018" was read as a section 3 holding s. 2's definitions. They are editorial
# matter, not law, and are cut at ingest the way `strip_end_matter` cuts the Statement
# of Objects and Reasons; the source PDF and its SHA-256 keep them recoverable.
#
# The pattern is deliberately NARROW. A broader one admitting "Section" dropped the
# real IT Act s. 9 ("9. Sections 6, 7 and 8 not to confer right …") and the integrity
# gate could not see it, because coverage is measured on the text left after the cut.
# So only a trailing block whose head is an amendment verb is a footnote, and every
# numbered item in a cut block must cite its source (an Act, an Order, a notification
# number, a section, "see"/"cf."/"ibid") and no line in it may open like law (a
# sub-section "(2) In …" or a section heading "11. Licence.—"), or the Act is refused.
# Measured: all 1,654 items cut from the 17 supplied Acts pass; ordinary statutory words
# ("seen", "notification", "inserted") are deliberately not anchors.
_FOOTNOTE_HEAD = re.compile(r"\d{1,3}\s*\.\s+(?:Subs\.|Ins\.|Omitted|Rep\.|The words|"
                            r"Added|Renumbered|Vide|Certain words|Words? )",
                            re.IGNORECASE)
_FOOTNOTE_ITEM = re.compile(r"(?m)^(?=\s*\d{1,3}\s*\.\s)")
_EDITORIAL = re.compile(r"(?i)\b(?:by Act|ibid|w\.\s?e\.\s?f|A\.\s?O\b|S\.\s?O\.|"
                        r"G\.\s?S\.\s?R|s\.\s*\d|struck down|see\b|cf\.|Order\b|"
                        r"Gazette\b)")
_READS_AS_LAW = re.compile(r"(?m)^[ \t]*(?:\(\d{1,2}\)[ \t]+[A-Z]|"
                           r"\d{1,3}[A-Z]{0,2}\.[ \t]+[A-Z][^.\n]*\.[ \t]*\u2014)")
# The read-time cleanup of page-foot notes the ingest cut cannot see (a footnote that
# sits mid-page, or inside a merged block). One definition; `claim_records` uses it.
FOOTNOTES = re.compile(r"(?mi)^\d{1,2}\.\s[^\n]*\b(?:subs\.|ins\.|rep\.|omitted|see|"
                       r"cf\.|w\.e\.f|by Act \d)[^\n]*(?:\n(?!\d{1,4}\s*$)[^\n]*)*?"
                       r"(?:\n\d{1,4}\s*$|\Z)")


@dataclass(frozen=True)
class Dropped:
    """What `strip_footnotes` cut from one Act — counted, so no cut is silent."""
    footnotes: int
    page_marks: int
    chars: int
    sha256: str


def strip_footnotes(pages: list[list[str]], *,
                    source: str = "") -> tuple[list[str], Dropped]:
    """Each page's text without its trailing footnote and page-mark blocks.

    `pages` holds each page's blocks in reading order. A page mark is the page's own
    number (measured: every bare trailing number in the corpus is its page index + 1)
    or the "IndiaCode" stamp. Refuses the Act if a cut block holds a numbered item with
    no editorial vocabulary: that is law, and losing it silently is the IT Act s. 9
    trap."""
    kept: list[str] = []
    cut: list[str] = []
    notes = marks = 0
    for number, blocks in enumerate(pages, start=1):
        i = len(blocks)
        while i and (blocks[i - 1] in (str(number), "IndiaCode")
                     or _FOOTNOTE_HEAD.match(blocks[i - 1])):
            i -= 1
        for block in blocks[i:]:
            if block in (str(number), "IndiaCode"):
                marks += 1
                continue
            notes += 1
            law = [item for item in _FOOTNOTE_ITEM.split(block)
                   if item.strip() and (not _EDITORIAL.search(item)
                                        or _READS_AS_LAW.search(item))]
            if law:
                raise StatuteIngestRefused(
                    f"{source}: page {number} — a page-foot block reads as law, not a "
                    f"footnote: {' '.join(law[0].split())[:80]!r}")
        cut += blocks[i:]
        kept.append("\n".join(blocks[:i]))
    joined = "\n".join(cut)
    return kept, Dropped(notes, marks, len(joined),
                         hashlib.sha256(joined.encode()).hexdigest())


def chunk_statute_text(text: str) -> list[StatuteChunk]:
    """Section-based chunks of an Act's text, in the Act's own order and numbering."""
    text = strip_end_matter(text)
    numbered = [(m.start(), m.group("num")) for m in _SECTION_START.finditer(text)]
    roman = len(numbered) < 2
    if roman:
        # An instrument that numbers its directions (i), (ii), ... — CERT-In's shape.
        numbered = [(m.start(), m.group("num"))
                    for m in _DIRECTION_START.finditer(text)]
        keyfn = lambda n: (0, n)  # noqa: E731 — roman order is the document's order
    else:
        keyfn = _section_key
    # A Schedule follows the Act's LAST section. `section-4`: the floor is where that
    # section's body begins, read from the Act's own arrangement (its ceiling) — the
    # DPDP Rules, 2025 carry seven Schedules over the last HALF of the text, so the
    # old "closing quarter" rule dropped the First to Fourth and folded them under
    # rule 23. With no arrangement to read, the closing quarter still applies.
    plain = [*sorted(numbered), (len(text), None)]
    plain_keys = [keyfn(num) for _, num in plain[:-1]]
    first = _body_from(text, plain, plain_keys)
    floor: float = len(text) * SCHEDULE_TAIL_FRACTION
    if not roman and first:
        top = max(plain_keys[:first])
        last = next((plain[i][0] for i in range(first, len(plain_keys))
                     if plain_keys[i] == top), None)
        if last is not None:
            floor = last
    elif not roman:
        # No arrangement (the DPDP Rules print has none): the Rules' own numbering
        # shows where they end — it climbs 1 → 23, then restarts at 1 inside the First
        # Schedule. The last section is the running maximum at that first restart.
        running, running_at = (0, ""), None
        for position, num in plain[:-1]:
            key = keyfn(num)
            if key[0] == 1 and running[0] > 1 and running_at is not None:
                floor = running_at
                break
            if key > running:
                running, running_at = key, position
    schedules = [] if roman else [
        (m.start(), _schedule_label(m.group()))
        for m in _SCHEDULE_START.finditer(text) if m.start() > floor]
    if schedules:
        # Inside a Schedule, `1.` and `2.` number its ENTRIES, not the Act's sections.
        numbered = [b for b in numbered if b[0] < schedules[0][0]]
    bounds = [*sorted(numbered + schedules), (len(text), None)]
    keys = [keyfn(num) for _, num in bounds[:-1]]
    body_from = _body_from(text, bounds, keys)

    # The Act's own arrangement of sections is everything before the body, so its
    # highest number is the ceiling a body number cannot exceed (`section-3`).
    ceiling = None
    if not roman and body_from:
        front = [k for k in keys[:body_from] if k[0] < _SCHEDULE_RANK]
        ceiling = max(front) if front else None
    numbered_body: list[tuple[int, str]] = [
        (position, num) for position, num in bounds[body_from:-1]
        if num is not None]
    ordered = [*_repair_glued_markers(numbered_body, ceiling), bounds[-1]]

    # Fold footnotes: a piece that is too short, or whose number falls below the
    # running section, belongs to the section before it. Two Schedules are never
    # compared by name — they run in document order, and "FOURTH" sorts below "THIRD".
    # `section-6`: a short piece is still a section when the Act's arrangement names
    # its number and it reads as one ("3. Appointment of officers.––The Board may …",
    # IGST s. 3, 130 characters — it had been read into s. 2's definitions).
    arranged = {num for _, num in bounds[:body_from]}
    sections: list[list] = []          # [num, start, end]
    for (s, num), (nxt, _) in pairwise(ordered):
        piece = text[s:nxt]
        both_schedules = sections and min(keyfn(num)[0], keyfn(sections[-1][0])[0]) \
            >= _SCHEDULE_RANK
        short = len(piece.strip()) < MIN_SECTION_CHARS and not (
            num in arranged and _SHORT_SECTION.match(piece)
            and not _FOOTNOTE_HEAD.match(piece.strip())
            and (not sections or keyfn(num) > keyfn(sections[-1][0])))
        if sections and (short or (
                not both_schedules and keyfn(num) < keyfn(sections[-1][0]))):
            sections[-1][2] = nxt
            continue
        if short:
            continue
        sections.append([num, s, nxt])

    chunks: list[StatuteChunk] = []
    for num, s, e in sections:
        body = text[s:e].strip()
        after_number = (_SECTION_START.match(body) or _DIRECTION_START.match(body)
                        or _SCHEDULE_START.match(body))
        note = _marginal_note(body[after_number.end():]) if after_number else None
        if len(body) <= MAX_SECTION_CHARS:
            chunks.append(StatuteChunk(num, None, note, body, s, e))
            continue
        offset = s
        for sub, part in _split_long(body):
            chunks.append(StatuteChunk(num, sub, note, part.strip(), offset,
                                       offset + len(part)))
            offset += len(part)
    return chunks


# Integrity gate (roadmap PHASE 2, §2 "No document becomes searchable until ingestion
# integrity checks pass"). A section failing a check is QUARANTINED — never written,
# so never searchable, never cited — and the Act is REFUSED when too much of it fails
# or its text is not covered. Thresholds measured on the 17-Act corpus, 2026-09-24:
# the largest genuine forward gap is 49 (Contract Act ss. 75 → 124, the Sale of Goods
# sections moved out in 1930); the CPC's First Schedule read as sections jumps 158 → 310.
NUMBERING_JUMP_LIMIT = 100
QUARANTINE_CEILING = 0.20
COVERAGE_FLOOR = 0.95


@dataclass(frozen=True)
class Integrity:
    kept: list[StatuteChunk]
    quarantined: dict[str, str]           # section → first failing check
    coverage: float
    refused: str | None


def check_integrity(chunks: list[StatuteChunk], text_length: int) -> Integrity:
    """Per-section checks, then per-Act ones. Deterministic; reads only the chunks.

    SUBSECTION_RESTART  a section's sub-sections run (2), (6), (2): several units were
                        folded under one number — the CPC's Orders under "s. 158"
    NUMBERING_JUMP      a forward gap over the limit: the parser left the Act's own
                        numbering, so the rest (Schedules excepted) is not trusted
    DUPLICATE_TEXT      the same text twice in one Act (a repeated-text explosion)
    OVERSIZED           a chunk over MAX_SECTION_CHARS (`_windows` makes this a bug)
    """
    bad: dict[str, str] = {}
    sections: dict[str, list[StatuteChunk]] = {}
    for c in chunks:
        sections.setdefault(c.section_number, []).append(c)
    for num, cs in sections.items():
        if _section_key(num)[0] >= _SCHEDULE_RANK:    # a Schedule has no sub-sections
            continue
        subs = [int(m.group()) for c in cs
                if c.sub_section and (m := re.search(r"\d+", c.sub_section))]
        if any(b < a for a, b in pairwise(subs)):
            bad[num] = "SUBSECTION_RESTART"
    numeric = [n for n in sections if 0 < _section_key(n)[0] < _SCHEDULE_RANK]
    for i, (a, b) in enumerate(pairwise(numeric)):
        if _section_key(b)[0] - _section_key(a)[0] > NUMBERING_JUMP_LIMIT:
            for n in numeric[i + 1:]:
                bad.setdefault(n, "NUMBERING_JUMP")
            break
    seen: set[str] = set()
    for c in chunks:
        if c.content in seen:
            bad.setdefault(c.section_number, "DUPLICATE_TEXT")
        seen.add(c.content)
        if len(c.content) > MAX_SECTION_CHARS:
            bad.setdefault(c.section_number, "OVERSIZED")
    kept = [c for c in chunks if c.section_number not in bad]
    covered, end = 0, 0
    for c in sorted(chunks, key=lambda c: c.char_start):
        covered += max(0, c.char_end - max(c.char_start, end))
        end = max(end, c.char_end)
    body = text_length - (chunks[0].char_start if chunks else 0)
    coverage = covered / body if body > 0 else 0.0
    refused = None
    # The ceiling counts SECTIONS — the unit a citation names. One folded blob of 500
    # chunks is one untrustworthy section, not proof the other 150 are wrong.
    if sections and len(bad) / len(sections) > QUARANTINE_CEILING:
        refused = (f"{len(bad)} of {len(sections)} sections fail integrity "
                   f"— over the {QUARANTINE_CEILING:.0%} ceiling")
    elif coverage < COVERAGE_FLOOR:
        refused = (f"chunks cover {coverage:.1%} of the Act's text, "
                   f"under {COVERAGE_FLOOR:.0%}")
    return Integrity(kept, bad, round(coverage, 4), refused)


def _page_blocks(page) -> list[str]:
    """One page's text blocks in READING order, not in PDF content-stream order.

    Gazette statutes are laid out in columns and the default extraction walks the
    content stream, which emits a whole column at a time. Measured on the DPDP Act's
    penalty Schedule (2026-09-20): a breach label and the penalty in the SAME table row
    came out 699 characters apart, so no chunk carried the pair and "the largest fine
    for failing to keep reasonable security safeguards" was unanswerable from the Act
    that states it. Sorting the page's text blocks into row-bands (y, then x) puts them
    113 characters apart, in the order a reader reads them.

    `get_text(sort=True)` reorders the same way but joins spans with no separator —
    measured on SLA-leapswitch.pdf it yielded `*99.95%forPower(Dual-poweredservers)`,
    which no lexical search can match. Sorting whole blocks leaves each block's own
    text, and its spacing, untouched.

    The 6-point band absorbs the baseline jitter of a justified line; blocks within one
    band are one visual row and are ordered left to right.

    Duplicated, deliberately, in `ingestion/parsing.py`: `tests/test_import_boundaries.py`
    confines `assist` to {db, domain, observability, security}, so this lane cannot
    import the ingestion parser. Four lines of geometry is the cheaper price.
    """
    blocks = [b for b in page.get_text("blocks") if b[6] == 0]   # 0 = text, 1 = image
    blocks.sort(key=lambda b: (round(b[1] / 6), b[0]))
    return [b[4].strip() for b in blocks if b[4].strip()]


_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")


def _pdf_text(path: Path) -> str:
    return _read_pdf(path)[0]


def _read_pdf(path: Path) -> tuple[str, Dropped]:
    """The instrument's text. A BILINGUAL Gazette print (the DPDP Rules, 2025: 23 Hindi
    pages, then 18 English) carries the same instrument twice, each numbered 1 → 23, so
    the fold rule filed the whole English half under "rule 23". Where both scripts hold
    whole pages, the English pages are the text chunked.
    ponytail: the Hindi version is then not indexed; index it as its own statute row
    if Hindi-language retrieval is ever asked for."""
    import pymupdf

    pages, dropped = strip_footnotes(
        [_page_blocks(page) for page in pymupdf.open(str(path)).pages()],
        source=path.name)
    return "\n".join(_prefer_latin(pages)), dropped


def _prefer_latin(pages: list[str]) -> list[str]:
    latin = [p for p in pages if len(_LATIN.findall(p)) >= len(_DEVANAGARI.findall(p))]
    return latin if latin else pages


def ingest_statute(db: DBSession, *, path: Path, provenance: dict,
                   stage: bool = False) -> dict:
    """Register one statute and (re)chunk it. Refuses without full provenance (r6).

    `stage` (`AM-125`, blue-green): the Act is written as a NEW row in status STAGED,
    beside the live one and invisible to every read (`_live_sql`), until `flip` swaps
    the generations. The live row and its chunks are never touched, so nothing that
    cites them is re-pointed or deleted."""
    missing = [f for f in PROVENANCE_FIELDS if not str(provenance.get(f) or "").strip()]
    if missing:
        raise StatuteIngestRefused(
            f"{path.name}: provenance incomplete — {', '.join(missing)} (AM-32 r6: a "
            "statute with no provenance record cannot be ingested)")
    if not path.exists():
        raise StatuteIngestRefused(
            f"{path.name}: file not present (rule 21 — supplied, never fetched)")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    declared = provenance.get("file_sha256")
    if declared and declared.lower() != sha:
        raise StatuteIngestRefused(
            f"{path.name}: SHA-256 differs from the registry entry")

    text, dropped = _read_pdf(path)
    full_text = strip_end_matter(text)
    chunks = chunk_statute_text(full_text)
    if not chunks:
        raise StatuteIngestRefused(
            f"{path.name}: no numbered sections found — a Domain C citation is Act + "
            "section, never a page alone (AM-32 r7)")
    sections = len({c.section_number for c in chunks})
    declared_sections = provenance.get("total_sections")
    if declared_sections and sections < declared_sections * SECTION_COUNT_FLOOR:
        raise StatuteIngestRefused(
            f"{path.name}: {sections} sections, registry declares {declared_sections} "
            f"— below the {SECTION_COUNT_FLOOR:.0%} floor, so the extraction lost part "
            "of the Act rather than merely re-drawing a boundary")
    integrity = check_integrity(chunks, len(full_text))
    if integrity.refused:
        raise StatuteIngestRefused(f"{path.name}: integrity — {integrity.refused}")
    chunks = integrity.kept

    schema = config.assist_schema()
    statute_id = _upsert_statute(db, schema, sha=sha, provenance=provenance, stage=stage)
    repointed = _replace_statute_chunks(db, schema, statute_id, chunks)
    embedded = _embed(db, statute_id)
    log_event("assist.statutes.ingested", statute_id=str(statute_id),
              chunks=len(chunks), embedded=embedded,
              quarantined=len(integrity.quarantined), staged=stage,
              footnotes_cut=dropped.footnotes, page_marks_cut=dropped.page_marks,
              cut_chars=dropped.chars, cut_sha256=dropped.sha256,
              citations_repointed=repointed)              # counts only (53.3)
    return {"statute_id": str(statute_id), "chunks": len(chunks), "sections": sections,
            "embedded": embedded, "file_sha256": sha,
            "citations_repointed": repointed, "coverage": integrity.coverage,
            "quarantined": integrity.quarantined, "dropped": dropped}


def _prior_rows(db: DBSession, schema: str, *, sha: str, provenance: dict,
                statuses: tuple[str, ...] = (*LIVE_STATUSES, "WITHDRAWN")) -> list:
    """The existing row(s) for this registry entry: the same file, the same title, or
    the file a replacement source declares it replaces (`replaces_file_sha256`,
    `AM-81` r2) — so a better copy of an Act re-chunks ITS row, citations re-pointed,
    rather than standing beside the one it supersedes.

    Only rows in `statuses` (`AM-125`): a STAGED or STANDBY generation of the same Act
    shares its title and file, and is never matched — so never updated, withdrawn or
    deleted — by an ingest of the other. A live row comes first; among WITHDRAWN rows
    (a refused Act, or a retired generation) the newest."""
    return list(db.execute(sql_text(
        f'SELECT id, status FROM "{schema}".statutes '
        'WHERE (file_sha256 IN (:sha, :replaces) OR official_title = :title) '
        "AND status = ANY(:st) ORDER BY status = 'WITHDRAWN', "
        "CASE WHEN status = 'WITHDRAWN' THEN created_at END DESC, created_at"),
        {"sha": sha, "title": provenance["official_title"], "st": list(statuses),
         "replaces": provenance.get("replaces_file_sha256") or sha}).all())


def withdraw_statute(db: DBSession, *, path: Path, provenance: dict,
                     stage: bool = False) -> int:
    """An Act REFUSED on re-ingest must not keep serving what it held before
    (`AM-81` r3): its existing row is marked WITHDRAWN, which both retrieval paths
    exclude. Nothing is deleted — citations recorded against it stay intact (rule 17).
    `stage`: a refused STAGE withdraws that Act's earlier STAGED row instead (and the
    live one is untouched), so `flip` finds the Act missing and refuses rather than
    swapping in a stale build. Returns the number of rows withdrawn."""
    schema = config.assist_schema()
    sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    ids = [r.id for r in _prior_rows(db, schema, sha=sha, provenance=provenance,
                                     statuses=("STAGED",) if stage else LIVE_STATUSES)]
    for statute_id in ids:
        db.execute(sql_text(f"UPDATE \"{schema}\".statutes SET status = 'WITHDRAWN' "
                            "WHERE id = :i"), {"i": statute_id})
    return len(ids)


def _upsert_statute(db: DBSession, schema: str, *, sha: str, provenance: dict,
                    stage: bool = False) -> UUID:
    """The statute row, KEPT across a re-ingest so its chunks can be reconciled.

    It used to be deleted and rewritten. That cascades through `statute_chunks` into
    `answer_citations` (migration `d7e2a9c41b58`), so every past answer silently lost
    the section it quoted — rule 17 forbids exactly that, and production carried 10
    such citations when this was written (2026-09-20).

    `stage`: a fresh STAGED row, every time. A previous STAGED row of the Act is
    WITHDRAWN, not re-chunked, so `_replace_statute_chunks` never deletes a chunk on
    the staging path (a new row has none).
    """
    fields = {"title": provenance["official_title"],
              "act": provenance["act_number_year"], "jur": provenance["jurisdiction"],
              "src": provenance["source"], "ref": provenance["source_ref"],
              "amended": provenance["as_amended_date"], "sha": sha,
              "by": provenance["supplied_by"], "at": provenance["supplied_at"],
              "status": "STAGED" if stage
              else authority.of_statute(provenance["official_title"])[1]}
    if stage:
        db.execute(sql_text(f"UPDATE \"{schema}\".statutes SET status = 'WITHDRAWN' "
                            "WHERE status = 'STAGED' AND official_title = :title"),
                   {"title": fields["title"]})
    prior = [] if stage else _prior_rows(db, schema, sha=sha, provenance=provenance)
    # A second LIVE row matching on the other key is a duplicate of the same Act; it has
    # no reconcilable identity of its own, so it goes as before. A WITHDRAWN row stays:
    # it may be a retired generation, and its chunks carry past answers' citations.
    for duplicate in prior[1:]:
        if duplicate.status in LIVE_STATUSES:
            db.execute(sql_text(f'DELETE FROM "{schema}".statutes WHERE id = :i'),
                       {"i": duplicate.id})
    if prior:
        db.execute(sql_text(f"""
            UPDATE "{schema}".statutes
               SET official_title = :title, act_number_year = :act, jurisdiction = :jur,
                   source = :src, source_ref = :ref, as_amended_date = :amended,
                   file_sha256 = :sha, supplied_by = :by, supplied_at = :at,
                   status = :status
             WHERE id = :id
        """), {**fields, "id": prior[0].id})
        return prior[0].id
    statute_id = uuid4()
    db.execute(sql_text(f"""
        INSERT INTO "{schema}".statutes
            (id, official_title, act_number_year, jurisdiction, source, source_ref,
             as_amended_date, file_sha256, supplied_by, supplied_at, status)
        VALUES (:id, :title, :act, :jur, :src, :ref, :amended, :sha, :by, :at, :status)
    """), {**fields, "id": statute_id})
    return statute_id


def _replace_statute_chunks(db: DBSession, schema: str, statute_id: UUID,
                            chunks: list[StatuteChunk]) -> int:
    """Re-chunk one statute WITHOUT invalidating the citations recorded against it.

    `store.replace_chunks` does this for documents by matching old text inside new,
    because a document chunk has no identity of its own. A statute chunk has one: the
    Act's own section numbering, which is what a Domain C citation names. So the match
    is the real key `(section_number, sub_section)` — a section keeps its row id, and
    the answer that cited s. 43A still points at s. 43A after a re-chunk.

    A section that no longer chunks out (renumbering, or a body that fell under
    MIN_SECTION_CHARS) hands its citations to the nearest surviving section in document
    order, which is the one its text now sits in, and only then is deleted.
    Returns the number of citations repointed.
    """
    old = db.execute(sql_text(f"""
        SELECT id, section_number, sub_section, content FROM "{schema}".statute_chunks
         WHERE statute_id = :s ORDER BY ordinal
    """), {"s": statute_id}).all()
    by_key = {(o.section_number, o.sub_section): o for o in old}
    # Park the old ordinals below zero so new ones are free under
    # uq_statute_chunks_statute_ordinal.
    db.execute(sql_text(f'UPDATE "{schema}".statute_chunks SET ordinal = -1 - ordinal '
                        'WHERE statute_id = :s'), {"s": statute_id})

    survivors: set = set()
    for ordinal, chunk in enumerate(chunks):
        keep = by_key.get((chunk.section_number, chunk.sub_section))
        if keep is None or keep.id in survivors:
            db.execute(sql_text(f"""
                INSERT INTO "{schema}".statute_chunks
                    (id, statute_id, section_number, sub_section, marginal_note,
                     ordinal, content, char_start, char_end, chunking_algorithm_version)
                VALUES (:id, :sid, :sec, :sub, :note, :ord, :content, :cs, :ce, :algo)
            """), {"id": uuid4(), "sid": statute_id, "sec": chunk.section_number,
                   "sub": chunk.sub_section, "note": chunk.marginal_note,
                   "ord": ordinal, "content": chunk.content, "cs": chunk.char_start,
                   "ce": chunk.char_end, "algo": STATUTE_CHUNKING_ALGORITHM_VERSION})
            continue
        db.execute(sql_text(f"""
            UPDATE "{schema}".statute_chunks
               SET marginal_note = :note, ordinal = :ord, content = :content,
                   char_start = :cs, char_end = :ce, chunking_algorithm_version = :algo
             WHERE id = :id
        """), {"id": keep.id, "note": chunk.marginal_note, "ord": ordinal,
               "content": chunk.content, "cs": chunk.char_start, "ce": chunk.char_end,
               "algo": STATUTE_CHUNKING_ALGORITHM_VERSION})
        if keep.content != chunk.content:
            # `_embed` inserts ON CONFLICT DO NOTHING, so a kept row would otherwise
            # keep the vector of text it no longer holds.
            db.execute(sql_text(f'DELETE FROM "{schema}".statute_chunk_embeddings '
                                'WHERE statute_chunk_id = :i'), {"i": keep.id})
        survivors.add(keep.id)

    # Where the old text WENT, preferred over where the old row SAT. `section-3`
    # renumbers (the IT Act's bogus "266A" blob becomes ss. 66A-87), so the section
    # key cannot match and document order alone sent a citation of s. 79's text to
    # s. 66 — a historical answer pointing at a section that does not contain what it
    # quoted, which is exactly what rule 17 forbids. Matching the old chunk's own text
    # inside a surviving one is what `store.replace_chunks` does for documents.
    doomed = {c.id for c in old if c.id not in survivors}
    remaining = {c.id: " ".join(c.content.split())
                 for c in db.execute(sql_text(
                     f'SELECT id, content FROM "{schema}".statute_chunks '
                     "WHERE statute_id = :s"), {"s": statute_id}).all()
                 if c.id not in doomed}

    def _successor(chunk) -> UUID | None:
        """A remaining chunk carrying a distinctive span of `chunk`'s own text.

        The probe starts AFTER the section number, because the number is the thing
        that changed: `3. Widgets.—Every keeper…` and `3A. Widgets.—Every keeper…`
        are the same section under two numberings and must still match.
        """
        body = (chunk.content or "").strip()
        opening = _SECTION_START.match(body) or _DIRECTION_START.match(body)
        probe = " ".join(body[opening.end():].split() if opening
                         else body.split())[:MIN_SECTION_CHARS]
        if len(probe) < 40:                     # too short to identify anything
            return None
        return next((cid for cid, text in remaining.items() if probe in text), None)

    repointed = 0
    for position, o in enumerate(old):
        if o.id in survivors:
            continue
        heir = _successor(o)
        heir = heir or next((k.id for k in old[position + 1:] if k.id in survivors), None)
        heir = heir or next((k.id for k in reversed(old[:position])
                             if k.id in survivors), None)
        if heir is not None:
            moved = db.execute(sql_text(f"""
                UPDATE "{schema}".answer_citations SET statute_chunk_id = :heir
                 WHERE statute_chunk_id = :old RETURNING id
            """), {"old": o.id, "heir": heir}).all()
            repointed += len(moved)
        db.execute(sql_text(f'DELETE FROM "{schema}".statute_chunks WHERE id = :i'),
                   {"i": o.id})
    return repointed


def breadcrumb(official_title: str, section_number: str,
               marginal_note: str | None) -> str:
    """Where a statute chunk sits: Act · section · marginal note. It heads the parent
    context `expand_section` hands to generation, and is never stored in or cited as
    the chunk's content. It is deliberately NOT embedded (measured 2026-09-24): over
    breadcrumb + text the MiniLM-calibrated gate opened on noise — "the current law on
    TDS for professional fees", which must refuse, drew six Companies Act and
    Arbitration Act units — for one rank gained on one question. The repeal
    annotation is provenance, not name, and stays out."""
    act = re.sub(r"\s*\((?:REPEALED|Rep\.).*$", "", official_title).split(" — ")[0]
    unit = section_number if "chedule" in section_number else f"Section {section_number}"
    return " · ".join(p for p in (act, unit, marginal_note) if p)


def _embed(db: DBSession, statute_id: UUID) -> int:
    """Vectors for the section chunks, best-effort — lexical retrieval works without.
    The Act's existing vectors are replaced, so a re-ingest never leaves a vector
    beside chunk text it no longer matches; vectors are derived and nothing cites
    them."""
    from legalmind.assist.knowledge import store

    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT id, content FROM "{schema}".statute_chunks
         WHERE statute_id = :s ORDER BY ordinal"""), {"s": statute_id}).all()
    db.execute(sql_text(f"""
        DELETE FROM "{schema}".statute_chunk_embeddings WHERE statute_chunk_id IN
          (SELECT id FROM "{schema}".statute_chunks WHERE statute_id = :s)"""),
        {"s": statute_id})
    return store.embed_into(db, table="statute_chunk_embeddings", fk="statute_chunk_id",
                            rows=[(r[0], r[1]) for r in rows])


def flip(db: DBSession, *, incoming: str, outgoing: str) -> int:
    """Swap generations (`AM-125`) in the caller's ONE transaction: the live rows become
    `outgoing` and the `incoming` rows take the status their title gives them
    (`authority.of_statute`, as ingestion writes it). `--swap` is STAGED in, STANDBY
    out; `--rollback` the exact reverse. Refuses unless the incoming generation holds
    exactly the live Acts. Statuses only: no chunk is touched, re-pointed or deleted,
    so every recorded citation keeps the text it quoted (rule 17)."""
    schema = config.assist_schema()

    def titles(where: str) -> Sequence:
        return db.execute(sql_text(
            f'SELECT id, official_title FROM "{schema}".statutes s '
            f"WHERE {where} ORDER BY official_title"), {"incoming": incoming}).all()
    live, waiting = titles(_live_sql()), titles("s.status = :incoming")
    if db.execute(sql_text(f'SELECT 1 FROM "{schema}".statutes WHERE status = :out '
                           "LIMIT 1"), {"out": outgoing}).first():
        raise StatuteIngestRefused(
            f"a {outgoing} generation is already waiting — roll it back or retire it "
            "first, or the generation it holds can no longer be restored")
    if [r.official_title for r in live] != [r.official_title for r in waiting]:
        raise StatuteIngestRefused(
            f"{len(waiting)} {incoming} statute row(s) against {len(live)} live — a "
            "generation is swapped whole or not at all")
    db.execute(sql_text(f'UPDATE "{schema}".statutes SET status = :out '
                        "WHERE id = ANY(:i)"),
               {"out": outgoing, "i": [r.id for r in live]})
    for r in waiting:
        db.execute(sql_text(f'UPDATE "{schema}".statutes SET status = :st WHERE id = :i'),
                   {"st": authority.of_statute(r.official_title)[1], "i": r.id})
    log_event("assist.statutes.flipped", incoming=incoming, outgoing=outgoing,
              statutes=len(waiting), level=logging.INFO)
    return len(waiting)


def retire(db: DBSession) -> int:
    """STANDBY -> WITHDRAWN once the rollback window closes (`AM-125`). Nothing is
    deleted: the retired chunks keep the citations of the answers that quoted them."""
    schema = config.assist_schema()
    return len(db.execute(sql_text(
        f"UPDATE \"{schema}\".statutes SET status = 'WITHDRAWN' WHERE status = 'STANDBY' "
        "RETURNING id")).all())


def jurisdictions(db: DBSession) -> frozenset[str]:
    """The jurisdictions the ratified corpus actually covers, from the corpus itself.

    The router refuses a question about a jurisdiction not in this set rather than
    answering it from another one's law. Reading it from the data instead of a list in
    code means ingesting an Act under a new jurisdiction changes what may be answered
    without an engineer editing a table.
    """
    schema = config.assist_schema()
    return frozenset(
        row[0] for row in db.execute(
            sql_text(f'SELECT DISTINCT jurisdiction FROM "{schema}".statutes '
                     f'WHERE {_live_sql("status")}'))
        if row[0])


def available(db: DBSession) -> bool:
    """A ratified corpus exists — the router's `statutes_available` input."""
    schema = config.assist_schema()
    return bool(db.execute(
        sql_text(f'SELECT 1 FROM "{schema}".statutes WHERE {_live_sql("status")} '
                 'LIMIT 1')).first())


def holdings(db: DBSession) -> list[str]:
    """The Acts the corpus holds — public information, used in the refusal (AM-46 r3)."""
    schema = config.assist_schema()
    return [r[0] for r in db.execute(sql_text(
        f'SELECT official_title FROM "{schema}".statutes WHERE {_live_sql("status")} '
        'ORDER BY official_title')).all()]


@dataclass(frozen=True)
class StatuteHit:
    statute_chunk_id: UUID
    official_title: str
    act_number_year: str
    section_number: str
    sub_section: str | None
    marginal_note: str | None
    content: str
    score: float

    @property
    def citation(self) -> str:
        """Act + the Act's own structural unit (`AM-32` r7), never a page alone.

        A Schedule carries no section number and is cited by its own name, so the
        "s." prefix is omitted for it — "…, the Schedule" reads as a lawyer writes
        it, where "…, s. THE SCHEDULE" does not. Presentation only: the stored unit
        is unchanged, and see `_SCHEDULE_START` for the representation decision.
        """
        sub = f" {self.sub_section}" if self.sub_section else ""
        if "schedule" in self.section_number.lower():
            return f"{self.official_title}, {self.section_number}{sub}"
        return f"{self.official_title}, s. {self.section_number}{sub}"


#: An agency's short name, expanded to the name the Act gives it: IT Act s. 70B says
#: "Indian Computer Emergency Response Team", never "CERT-In", and ranked 32nd for
#: "what does the IT Act say about CERT-In's role?" (golden O-04). Retrieval only —
#: the router's instrument vocabulary (`intent.ACT_ALIASES`) is untouched.
AGENCY_NAMES = {"cert-in": "indian computer emergency response team"}
_AGENCY = re.compile(r"\b(" + "|".join(map(re.escape, AGENCY_NAMES)) + r")\b", re.I)


def with_agency_names(question: str) -> str:
    """The reader's words with each agency's statutory name after its short one, for
    the cross-encoder, which scored s. 70B at -7.0 for "CERT-In's role" and at 4.4
    with the name spelled out. Never the question the gate or the reader sees."""
    return _AGENCY.sub(lambda m: f"{m.group(1)} ({AGENCY_NAMES[m.group(1).lower()]})",
                       question or "")


def expand_aliases(query: str) -> str:
    """Short names people type for Acts, expanded to the words the official title
    uses so the title match can see them. Names only — no law.

    The table lives in `intent.ACT_ALIASES`: the router needs the same short names to
    recognise that a question NAMES an instrument, and two copies would drift. The
    dependency runs from this module to that one, which imports nothing but `re`.
    """
    from legalmind.assist.query.intent import _ALIAS_SPACE, ACT_ALIASES

    lowered = f" {_ALIAS_SPACE.sub(' ', (query or '').lower())} "
    for short, full in (*ACT_ALIASES.items(), *AGENCY_NAMES.items()):
        if f" {short} " in lowered:
            lowered = lowered.replace(f" {short} ", f" {short} {full} ")
    return lowered.strip()


# --------------------------------------------------------------------------
# Repealed law — ONE definition, used by every path.
#
# `AM-71`'s rule is that a superseded source must be excluded from the LEXICAL
# and the VECTOR path, "both, or it returns through the one left unfiltered".
# The rule was written twice to satisfy that — once as a constant for the vector
# query and once as a literal in the lexical query — which is the same drift risk
# `AM-71` exists to prevent, one level down: an edit to one path silently leaves
# the other serving repealed law.
#
# So the marker and the predicate are defined once here. `_repealed_sql` takes the
# column expression because the lexical query reads it from a sub-select (bare
# `status`) and the vector query from the joined table (`s.status`); the POLICY is
# identical and there is exactly one place to change it.
#
# The label is the corpus's own: the registry title's "(REPEALED …)" marker, written
# to `statutes.status` at ingestion (`a7d3e9b1c5f2`, 2026-09-24). No repeal is
# inferred here and none may be — which Act is in force is law, not an engineering
# judgement (rule 7).
_REPEALED_MARKER = "REPEALED"


def _repealed_sql(column: str = "s.status") -> str:
    """SQL predicate: is this source's Act repealed? Reads the `status` column
    (`a7d3e9b1c5f2`), written at ingestion from the registry title's own marker."""
    return f"{column} = 'REPEALED'"


def search_statutes(db: DBSession, *, query: str, permissions: frozenset[str],
                    limit: int = 6, embed_query=None,
                    require_semantic: bool = False,
                    include_superseded: bool = False,
                    candidates: bool = False) -> list[StatuteHit]:
    """Lexical retrieval over the statute corpus, authorized inside the function.

    A section number named in the question ("section 43A") ranks its exact section
    first — that is what a statute question usually is — and the Act the question
    NAMES ranks before every other Act holding a section of that number (eighteen
    Acts in the corpus means eighteen section 138s; measured live 2026-09-08, the NI
    Act's was outranked by the CPC's until the title match was added). Otherwise the
    question's lexemes are OR-ed with a two-lexeme floor, as Domain A does.
    Deterministic order.

    ``require_semantic`` (2026-09-09) is set by the fallback path for a question that
    did not ask about the law: then two shared lexemes are not enough on their own —
    "termination", "notice" and "period" reach the Copyright Act's licence-termination
    section for a contract question — and the corpus counts as silent unless a gated
    vector neighbour vouches for the match. A statute-shaped question is never held
    to this: naming an Act or a section IS the relevance signal.
    """
    if P.ASSIST_ASK not in permissions:
        return []
    schema = config.assist_schema()
    wanted = [m.group("num").upper() for m in _SECTION_IN_QUESTION.finditer(query or "")]
    query = expand_aliases(query)
    quarantine = _QUARANTINE_CTE.format(schema=schema, cap=MAX_CHUNKS_PER_SECTION)
    not_suspect = _NOT_SUSPECT
    rows = db.execute(sql_text(f"""
      SELECT * FROM (
        WITH q AS (SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex),
        {quarantine}
        SELECT sc.id, s.official_title, s.act_number_year, s.status, sc.section_number,
               sc.sub_section, sc.marginal_note, sc.content, sc.ordinal,
               -- The section's title counts with its text: s. 27's says "restraint of
               -- trade" where its text says "restrained", which stems apart (E-03).
               coalesce(cardinality(m.hit), 0) AS matched,
               -- ...of which the Act's own title words: inside the Act a question
               -- names, "contract" matches nearly every section of the Contract Act
               -- and orders nothing (s. 27 ranked 42nd, E-03).
               (SELECT count(*) FROM unnest(m.hit) h WHERE h = ANY(tl.words))
                   AS title_matched,
               ts_rank(sc.content_tsv,
                       to_tsquery('english', (SELECT array_to_string(lex, ' | ') FROM q)))
                   AS score,
               (upper(sc.section_number) = ANY(:wanted)) AS exact_section,
               -- A RATIO, not a raw count (corrected 2026-09-09, live pre-deployment
               -- verification): a raw count let a long title that merely CONTAINS
               -- the named Act's words as a substring (CERT-In's title embeds
               -- "Information Technology Act, 2000") outrank the Act itself, because
               -- its long title racked up more incidental overlapping words. The
               -- ratio of matched to total non-stopword title lexemes favours the
               -- title the question actually names, whatever its length.
               --
               -- Only 'india'/'indian' are excluded (corrected the same pass): they
               -- are truly generic — nearly every title carries them, so they never
               -- discriminate. 'act' and 'rule' were excluded too until live testing
               -- showed "What is the DPDP Act?" tied the DPDP ACT against the DPDP
               -- RULES (their titles are otherwise near-identical) and the Rules won
               -- the tiebreak — exactly the word the question used to distinguish
               -- them was the word being thrown away. Keeping 'act'/'rule' as real
               -- lexemes fixes that pair without reopening the CERT-In case (its
               -- long title still loses on the ratio regardless of this word).
               (SELECT CASE WHEN count(*) = 0 THEN 0.0 ELSE
                    count(*) FILTER (WHERE t = ANY(q.lex))::float / count(*) END
                  -- The "(REPEALED ...)" annotation is provenance, not part of
                  -- the Act's name: counting its words as title lexemes sank the
                  -- ratio so far that naming the Act could not reach it, which
                  -- would have made the in-force exclusion absolute rather than
                  -- the "named Acts stay reachable" rule it is meant to be.
                  FROM q, unnest(tsvector_to_array(to_tsvector('english',
                       regexp_replace(s.official_title,
                                      ' \\({_REPEALED_MARKER}.*$', '')))) t
                 WHERE t NOT IN ('india', 'indian'))
                   AS act_match
          FROM "{schema}".statute_chunks sc
          JOIN "{schema}".statutes s ON s.id = sc.statute_id
          CROSS JOIN LATERAL (SELECT tsvector_to_array(to_tsvector('english',
                                     s.official_title)) AS words) tl
          CROSS JOIN LATERAL (SELECT array_agg(l) AS hit FROM q, unnest(
                  tsvector_to_array(sc.content_tsv || to_tsvector('english',
                                    coalesce(sc.marginal_note, '')))) l
                WHERE l = ANY(q.lex)) m
         WHERE (SELECT cardinality(lex) FROM q) > 0
           AND {not_suspect}
      ) ranked
      -- `act_match` was the PRIMARY key until 2026-09-21, and a FRACTIONAL title
      -- overlap was enough to win it, so one Act took every slot: "reasonable
      -- security ... personal data" matched the SPDI Rules' title at 0.36 and all ten
      -- hits came from the SPDI Rules, burying the DPDP Act's own penalty Schedule
      -- (measured: the Schedule ranked 13th). A MAJORITY match still sorts first —
      -- the question naming an Act is a real signal (AM-50 r3) — but below that the
      -- section's own text decides, and act_match is only a tiebreak.
      --
      -- A REPEALED Act sorts last among equals. The corpus deliberately holds the
      -- Companies Act, 1956 and the Income-tax Act, 1961 for history, and
      -- alphabetising `official_title` on a tie put "The Companies Act, 1956
      -- (REPEALED ...)" ahead of "The Companies Act, 2013" every time.
      -- Repealed law is not served as current law. It stays reachable the one way
      -- AM-71 keeps a superseded position reachable: when the question NAMES that
      -- Act, which `act_match >= 0.5` already means everywhere else in this query.
         WHERE NOT ({_repealed_sql('status')}) OR act_match >= 0.5
               OR {'TRUE' if include_superseded else 'FALSE'}
      --
      -- Among the Acts a question names, the one it names MORE fully goes first
      -- (2026-09-27): "the DPDP Act" also majority-matches the DPDP Rules' title, and
      -- "the Companies Act, 1956" the 2013 Act's, so the other instrument's sections
      -- shared the slots and took them (golden E-02 lost DPDP s. 8; H-04 the 1956 Act).
         ORDER BY (act_match >= 0.5) DESC, exact_section DESC,
                  (CASE WHEN act_match >= 0.5 THEN act_match END) DESC NULLS LAST,
                  -- Version before relevance: "the Companies Act" names the 1956 and
                  -- the 2013 Act alike, and once section titles counted, s. 293 of the
                  -- REPEALED 1956 Act ("powers of Board") outranked s. 179 (L-03).
                  ({_repealed_sql('status')}
                   AND {'FALSE' if include_superseded else 'TRUE'}) ASC,
                  matched - (CASE WHEN act_match >= 0.5 THEN title_matched ELSE 0 END)
                      DESC,
                  ({_repealed_sql('status')}) ASC, act_match DESC, score DESC,
                  official_title, ordinal
         LIMIT :limit
    """), {"q": query or "", "wanted": wanted or [""], "limit": limit * 6}).all()
    floor = 2 if len((query or "").split()) > 1 else 1
    # A question that names the Act ("What is the DPDP Act?") is answered from
    # that Act even when no section's text repeats the question's words: a
    # majority title-lexeme match alone admits its opening sections (AM-50 r3).
    hits = _one_per_section([
        StatuteHit(r.id, r.official_title, r.act_number_year, r.section_number,
                   r.sub_section, r.marginal_note, r.content, float(r.score))
        for r in rows
        if r.exact_section or r.matched >= floor or r.act_match >= 0.5])[:limit]
    # Vector increment (2026-09-09): a paraphrase that names no Act, section or
    # statutory word — "can a company process someone's personal data without
    # asking them?" — has no lexeme to match. The stored section vectors (`AM-32`'s
    # `statute_chunk_embeddings`, filled at ingestion) are consulted through the
    # same calibrated gate the document retrieval uses, and admitted neighbours
    # FILL the slots the lexical ranking left empty — they never displace an exact
    # section or a named Act, so the ranking `AM-47` locked stays lexical-first.
    named = any(r.exact_section or r.act_match >= 0.5 for r in rows)
    if named and candidates:
        # A candidate pool (PHASE 7) keeps the named Act's lexical order whole and
        # APPENDS the vector neighbours instead of filling only the empty slots: its job
        # is recall, and "restraint" does not stem to "restrained" (s. 27). Measured:
        # rank-fusing the two under the cap instead cost IT Act s. 70B its place.
        return _one_per_section([*hits, *_vector_neighbours(
            db, query, limit=limit, embed_query=embed_query,
            include_superseded=include_superseded, gated=False)])[:2 * limit]
    if named:
        # A named section or Act: lexical-first stands; vectors only fill the rest.
        if len(hits) < limit:
            hits = _one_per_section([*hits, *_vector_neighbours(
                db, query, limit=limit, embed_query=embed_query,
                include_superseded=include_superseded)])[:limit]
    else:
        # Nothing named: a two-lexeme OR match is a weak signal ("company" and
        # "person" reach the Companies Act for a question about personal data),
        # while a gated cosine is a strong one. Reciprocal rank fusion, the
        # vector side winning an exact tie.
        vector = (_vector_neighbours(db, query, limit=limit, embed_query=embed_query,
                                     include_superseded=include_superseded, gated=False)
                  if candidates else
                  _vector_neighbours(db, query, limit=limit, embed_query=embed_query,
                                     include_superseded=include_superseded))
        if require_semantic and not vector:
            log_event("assist.statutes.searched", hits=0, level=logging.DEBUG,
                      cause="no_semantic_evidence")
            return []
        from legalmind.assist.retrieval.calibration import RRF_K

        fused: dict = {}
        by_id: dict = {}
        for rank, h in enumerate(vector, start=1):
            key = h.statute_chunk_id
            fused[key] = fused.get(key, 0.0) + 1 / (RRF_K + rank)
            by_id.setdefault(h.statute_chunk_id, h)
        for rank, h in enumerate(hits, start=1):
            key = h.statute_chunk_id
            fused[key] = fused.get(key, 0.0) + 1 / (RRF_K + rank)
            by_id.setdefault(h.statute_chunk_id, h)
        order = list(fused)                      # insertion order = vector first on ties
        ranked = sorted(order, key=lambda i: (-fused[i], order.index(i)))
        hits = _one_per_section([by_id[i] for i in ranked])[:limit]
    log_event("assist.statutes.searched", hits=len(hits), level=logging.DEBUG)
    return hits


# `AM-71` is the precedent and the shape: a superseded position must be excluded
# from the LEXICAL and the VECTOR path, "both, or it returns through the one left
# unfiltered". The same is true of repealed law, and it matters more — a repealed
# section served as current law is a citation a lawyer would rely on without
# re-checking.
#
# The corpus DELIBERATELY holds repealed Acts (the Companies Act, 1956 as the
# historical incorporating statute, Constitution §4.1/§28.4.2), so this is a
# READ-side exclusion and nothing is deleted. History stays reachable exactly
# where AM-71 leaves it reachable: when the question names that Act.
#
# The label is the corpus's own, recorded in `official_title` at ingestion. No
# repeal is inferred here and none may be — which Act is in force is law, not an
# engineering judgement (rule 7).
# A section that holds a large fraction of an Act is not a section — it is the
# parser's failure to find the next boundary, and everything after that point is
# stored under one fabricated number. Serving that text as "s. 316" is the worst
# failure this system has, because a real statutory passage under a wrong section
# number is exactly the citation a reader would not re-check.
#
# 50 is not a guess: across the 21-Act corpus, 2,753 (Act, section) groups hold
# 1–43 chunks and the next six hold 66–195, so the threshold sits in an empty
# band. The quarantine is READ-side and deletes nothing — the fix is the parser
# (`_repair_glued_markers`), and this is what keeps a known-bad label off a
# citation until that lands.
MAX_CHUNKS_PER_SECTION = 50

_QUARANTINE_CTE = """
        suspect AS MATERIALIZED (
            SELECT statute_id, section_number
              FROM "{schema}".statute_chunks
             -- A Schedule is not a section and may be long (Companies Act, 2013
             -- Schedule III: 98 bounded chunks); folds are caught at ingestion now.
             WHERE section_number NOT ILIKE '%schedule%'
             GROUP BY 1, 2 HAVING count(*) > {cap}
        )"""

# ...and only a live Act is served by either path: never a WITHDRAWN one (refused on
# re-ingest, `AM-81` r3), nor a STAGED or STANDBY generation (`AM-125`).
_NOT_SUSPECT = f"""NOT EXISTS (SELECT 1 FROM suspect
                     WHERE suspect.statute_id = sc.statute_id
                       AND suspect.section_number = sc.section_number)
           AND {_live_sql()}"""





def _one_per_section(hits: list[StatuteHit]) -> list[StatuteHit]:
    """The best-ranked child per (Act, section) — roadmap §3: "duplicate child hits
    from one parent do not crowd out other sources". The parent is recovered at
    generation time by `expand_section`, so dropping a sibling loses no text."""
    seen: set[tuple[str, str]] = set()
    out = []
    for h in hits:
        key = (h.official_title, h.section_number)
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


_COMMENCEMENT = Path(__file__).resolve().parents[3] / "config/statutes/commencement.json"


@functools.cache
def _commencements() -> tuple[dict, ...]:
    return tuple(json.loads(_COMMENCEMENT.read_text())["entries"])


def commencement(official_title: str, section: str, sub_section: str | None = None, *,
                 today: date | None = None) -> str | None:
    """Roadmap §14 (`AM-104`): whether an enacted provision is NOT YET IN FORCE, as the
    ratified Constitution records it (`config/statutes/commencement.json`). DPDP s. 33
    was served as operative law while Constitution §28.2 records it commencing 13 May
    2027. With `sub_section` None, any not-yet-commenced part of the section counts;
    once the date passes, nothing is returned and the provision reads as enacted."""
    today = today or date.today()
    out = []
    for e in _commencements():
        starts = date.fromisoformat(e["commences"])
        if (e["act"] != official_title or e["section"] != section or starts <= today
                or (sub_section is not None
                    and e["sub_section"] not in (None, sub_section))):
            continue
        clause = f"clause ({e['clause']}) " if e.get("clause") else ""
        part = (f"sub-section ({e['sub_section']}) {clause}"
                if e["sub_section"] and sub_section is None else clause)
        # Labelled as the Constitution's stated date — the company's reading, never
        # the Act's own commencement (statutory text and commencement kept apart).
        out.append(f"{part}NOT YET IN FORCE — commences {starts.day} "
                   f"{starts.strftime('%B %Y')} (the date {e['cite']} states; the "
                   f"company's reading, not the Act's text)")
    return "; ".join(out) or None


def read_time_text(db: DBSession,
                   statute_chunk_id: UUID) -> tuple[str, str | None] | None:
    """(text, commencement) as the Ask agent shows one statute chunk and its ledger
    re-reads it (A-83's one read-time text): the chunk, headed "[Commencement: …]" when
    the Constitution records it NOT YET IN FORCE (`AM-104`) — the independent review of
    2026-10-06 found DPDP s. 33 and its Schedule reaching the agent as current law.

    A chunk that continues a section is read after the section's opening chunk, as a
    contract clause is read with the block it continues (`store.clause_text`): s. 74's
    second chunk — footnotes and illustrations — was found and shown alone, without the
    rule ("When a contract has been broken, if a sum is named…"), so it could not be
    cited (2026-10-07). 649 of 2,857 sections span more than one chunk."""
    schema = config.assist_schema()
    row = db.execute(sql_text(f"""
        SELECT s.official_title, c.section_number, c.sub_section, c.content, c.ordinal,
               h.content AS head, h.ordinal AS head_ordinal
          FROM "{schema}".statute_chunks c JOIN "{schema}".statutes s
            ON s.id = c.statute_id
          CROSS JOIN LATERAL (
              SELECT f.content, f.ordinal FROM "{schema}".statute_chunks f
               WHERE f.statute_id = c.statute_id AND f.section_number = c.section_number
               ORDER BY f.ordinal LIMIT 1) h
         WHERE c.id = :c"""), {"c": statute_chunk_id}).first()
    if row is None:
        return None
    body = row.content
    if row.ordinal != row.head_ordinal:
        gap = "\n" if row.ordinal == row.head_ordinal + 1 else "\n…\n"
        body = f"{row.head.rstrip()}{gap}{body}"
    status = commencement(row.official_title, row.section_number, row.sub_section)
    return (f"[Commencement: {status}]\n{body}" if status else body), status


def expand_section(db: DBSession, statute_chunk_id: UUID, *,
                   max_chars: int = 4000) -> str:
    """The parent of a retrieved chunk: its whole section (every sibling chunk, in the
    Act's order), windowed around the hit when the section is longer than
    `max_chars`. Headed by the breadcrumb, so the Act and section travel with it."""
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT s.official_title, sib.section_number, sib.marginal_note, sib.content,
               sib.id = :c AS hit
          FROM "{schema}".statute_chunks c
          JOIN "{schema}".statute_chunks sib ON sib.statute_id = c.statute_id
                                            AND sib.section_number = c.section_number
          JOIN "{schema}".statutes s ON s.id = c.statute_id
         WHERE c.id = :c ORDER BY sib.ordinal"""), {"c": statute_chunk_id}).all()
    if not rows:
        return ""
    at = next(n for n, r in enumerate(rows) if r.hit)
    lo = hi = at
    size = len(rows[at].content)
    while True:
        grew = False
        if hi + 1 < len(rows) and size + len(rows[hi + 1].content) <= max_chars:
            hi, size, grew = hi + 1, size + len(rows[hi + 1].content), True
        if lo > 0 and size + len(rows[lo - 1].content) <= max_chars:
            lo, size, grew = lo - 1, size + len(rows[lo - 1].content), True
        if not grew:
            break
    head = breadcrumb(rows[at].official_title, rows[at].section_number,
                      rows[at].marginal_note)
    status = commencement(rows[at].official_title, rows[at].section_number)
    if status:        # commencement is not in the statutory text: say it beside it
        head += f"\n[Commencement: {status}]"
    body = "\n".join(r.content for r in rows[lo:hi + 1])
    return head + "\n" + body + _schedule_cross_reference(
        db, statute_chunk_id, rows[at].section_number, body, max_chars - size)


def _schedule_cross_reference(db: DBSession, statute_chunk_id: UUID, section: str,
                              body: str, budget: int) -> str:
    """Roadmap §9 (cross-references preserved): a section that imposes "such monetary
    penalty specified in the Schedule" states no amount — DPDP s. 33's is in the
    Schedule headed "[See section 33 (1)]" (golden F-05). A Schedule of the same Act
    whose own header names this section back is appended, labelled, within the
    remaining budget. Both references must be explicit in the text; nothing is
    inferred."""
    if "schedule" in section.lower() or "schedule" not in body.lower() or budget <= 0:
        return ""
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT sib.section_number, sib.content
          FROM "{schema}".statute_chunks c
          JOIN "{schema}".statute_chunks sib ON sib.statute_id = c.statute_id
         WHERE c.id = :c AND sib.section_number ILIKE '%schedule%'
         ORDER BY sib.ordinal"""), {"c": statute_chunk_id}).all()
    back = re.compile(rf"\bsee\s+sections?\b[^\]]{{0,60}}?\b{re.escape(section)}\b",
                      re.IGNORECASE)
    named = {r.section_number for r in rows if back.search(r.content[:200])}
    out = ""
    for r in rows:
        if r.section_number in named and len(out) + len(r.content) <= budget:
            out += ("" if out else f"\n[Cross-reference: {r.section_number}]") \
                + "\n" + r.content
    return out


def _vector_neighbours(db: DBSession, query: str, *, limit: int,
                       embed_query=None,
                       include_superseded: bool = False,
                       gated: bool = True) -> list[StatuteHit]:
    """Gated nearest neighbours over `statute_chunk_embeddings`; [] without a model,
    without vectors, or when the calibrated gate stays shut."""
    from legalmind.assist.ingestion import embedding_runtime
    from legalmind.assist.knowledge import store
    from legalmind.assist.retrieval import calibration

    embed = embed_query or embedding_runtime.embed_query
    embedded = embed(query) if query and query.strip() else None
    if embedded is None:
        return []
    vector, _identity = embedded
    schema = config.assist_schema()
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    vtype = store.vector_type(db)
    literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    quarantine = _QUARANTINE_CTE.format(schema=schema, cap=MAX_CHUNKS_PER_SECTION)
    rows = db.execute(sql_text(f"""
        WITH{quarantine}
        SELECT sc.id, s.official_title, s.act_number_year, sc.section_number,
               sc.sub_section, sc.marginal_note, sc.content,
               1 - (se.embedding {op} CAST(:q AS {vtype})) AS cosine
          FROM "{schema}".statute_chunk_embeddings se
          JOIN "{schema}".statute_chunks sc ON sc.id = se.statute_chunk_id
          JOIN "{schema}".statutes s ON s.id = sc.statute_id
         WHERE (NOT ({_repealed_sql()}) OR {'TRUE' if include_superseded else 'FALSE'})
           AND {_NOT_SUSPECT}
         ORDER BY se.embedding {op} CAST(:q AS {vtype}), s.official_title, sc.ordinal
         LIMIT :lim
    """), {"q": literal, "lim": max(limit, calibration.RETRIEVAL_TOP_K)}).all()
    scores = [float(r.cosine) for r in rows]
    if gated and not calibration.gate_is_open(False, scores):
        return []
    return [StatuteHit(r.id, r.official_title, r.act_number_year, r.section_number,
                       r.sub_section, r.marginal_note, r.content, float(r.cosine))
            for r in rows
            if not gated or float(r.cosine) >= calibration.EVIDENCE_COSINE_FLOOR][:limit]

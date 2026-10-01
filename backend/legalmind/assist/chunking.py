"""Chunking — derived from committed Evidence, never re-parsed from raw text.

`AM-27` r4: a chunk *"is derived from an existing immutable Document Version and
references the Document Evidence row it came from. It carries no independent provenance
and creates no second source of truth for document content."*

That sentence decides the whole design. The ingestion parser has already done the hard
work: it segmented the document into paragraphs, detected the clause numbering the
document itself states (locked 34.12 — *preserved*, never generated), recorded page
numbers, kept byte offsets, and flagged OCR-derived text. A chunker that went back to
the raw bytes would re-derive all of that, worse, and would create the second source of
truth r4 forbids.

So chunking here is a **transformation of evidence rows**, and the only real decision is
what to do with a row too long to be a useful retrieval unit.

--------------------------------------------------------------------------
Deterministic, and deliberately so
--------------------------------------------------------------------------
Same evidence in, same chunks out — no clock, no randomness, no locale dependence.
This is not `ENG-11` determinism (the assist lane makes no such claim, and `AM-28` r1
bars it from that gate), but it is worth having anyway: re-indexing a document must not
silently produce different chunk boundaries, or a citation recorded against an earlier
run would point somewhere else.

--------------------------------------------------------------------------
What this does NOT do
--------------------------------------------------------------------------
No overlap between chunks. Overlap is a retrieval-quality tactic that duplicates text,
and its value depends on the retrieval strategy — which is unbuilt and unmeasured. It is
an A3/A4 question, and adding it now would be tuning against a hypothesis.

No parent/child hierarchy. Same reason: the two-tier retrieval strategy that would use
it does not exist yet.

No folding ACROSS evidence rows. When the parser emits a heading (`7.`, `TERM AND
TERMINATION`) as an evidence row of its own, the chunk holding §7.1 cannot absorb it:
`AM-27` r4 makes a chunk reference the one Document Evidence row it came from, and a chunk
spanning two rows would have two. Owner ruling 2026-09-10: r4 is not amended. Such a row
stays indexed — it carries the clause number a user asks with — and a hit on it is
REDIRECTED at query time to the clause that follows it (`store.search_hybrid`), where
before it was dropped. Page furniture (a running header repeated on every page) is the
one row shape excluded from the index outright (`_excluded_rows`).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise

# The chunker's own version, recorded on every row it writes. A change to the
# boundaries below must change this, because chunk ids recorded against an older
# algorithm would otherwise be silently reinterpreted.
# clause-aware-4 (2026-09-10): a bare clause number (`10.`) and an orphan list marker
# (`e.`) fold forward like a heading, a continuation tail folds back into the clause it
# completes, and page-furniture evidence rows are not indexed.
# clause-aware-5 (2026-09-30): a running header/footer and the page's own number are
# trimmed from a row's edges, and a dotted clause number opening a sentence mid-paragraph
# (`… agreement. 1.1.2 "Services" means …`) starts a chunk.
CHUNKING_ALGORITHM_VERSION = "clause-aware-5"

# An evidence row longer than this is split. The number is a retrieval-shape choice,
# not a legal one, and it is characters rather than tokens on purpose: counting tokens
# would mean a tokenizer, which is a dependency (rule 19) and a model-specific one at
# that — so the unit would change meaning the moment the model did.
#
# 2000 characters is roughly a long contract clause. It is deliberately generous:
# splitting is the lossy operation here, because a clause cut in half can strand a
# carve-out from the obligation it qualifies. Most evidence rows are paragraphs and
# fall well under it, so in practice this fires on the pathological rows only.
MAX_CHUNK_CHARS = 2000

# Below this, a trailing fragment is merged back rather than left as its own chunk. A
# 30-character chunk is not a retrievable idea, it is noise in the index.
MIN_TAIL_CHARS = 200

# A one-line piece under this length that does not end a sentence is a HEADING, not a
# clause, and it is merged into the piece that FOLLOWS it so the heading travels with
# the clause it introduces. A short one-line definition ending in a full stop
# (`1.13. "Agreement" means this document.`) is still a clause and still its own chunk.
# Measured live on 2026-09-08: 29% of the index (2,195 of 7,356 chunks) was under 60
# characters — `7. TERM AND TERMINATION`, `7.6. Effect of Termination:` — and those
# headings outranked the clauses beneath them on the very words a user asks with,
# so "termination notice period" retrieved four headings and refused. 80 matches
# `guardrails.evidence_is_sufficient`: text that cannot constitute evidence on its own
# should not be a retrieval unit on its own either.
MIN_CHUNK_CHARS = 80

# --------------------------------------------------------------------------
# Clause boundaries — the primary split, and why it is not length-driven
# --------------------------------------------------------------------------
# Measured on the real supplied documents (2026-08-25): PyMuPDF emits **no blank
# lines** for them — 59 single newlines and zero double newlines on a representative
# page — so `parsing.segment_paragraphs`, which splits on `\n\s*\n`, produces exactly
# ONE evidence row per page. Across six real documents that gave 99 page-fragment
# chunks with a median of ~1300 characters, and **2 of 59 evidence rows carried a
# section number**, because `detect_clause_number` only ever sees a page-sized
# segment's first line.
#
# The structure is not missing, though — it is regular and right there in the text:
# `1.13.`, `4.1.`, `4. SCOPE OF SERVICES`, each on its own line. So the chunker splits
# on those markers **whenever they appear, regardless of length**, rather than only
# when a row exceeds the cap. One chunk then corresponds to one clause, which is what
# `AM-27` r4's "derived text spans" is for and what a citation to "§17.2" needs.
#
# This reads structure the document itself states. It does not invent numbering —
# locked 34.12's rule that existing clause numbering is *preserved, never generated*
# applies here exactly as it does in the parser.
# `[ \t\u00a0\u200b]`: real documents put a zero-width space or an NBSP after the
# number (`17.\u200b LIMITATION OF LIABILITY`, measured live 2026-09-08). Treating only
# ASCII blanks as separators made the whole of §17 one 1,366-character chunk, and a
# question about the liability cap then failed grounding against it.
_BLANK = r"[ \t\u00a0\u200b]"
_CLAUSE_LINE = re.compile(
    rf"^{_BLANK}*(?P<num>\d{{1,3}}(?:\.\d{{1,3}})*)\.?(?={_BLANK}*$|{_BLANK}+\S)",
    re.MULTILINE)


# Sub-clauses the document runs together in one paragraph. Only a MULTI-level number
# opening a sentence counts — "7 days" or "99.9" is a quantity, not a clause — and not
# after an abbreviation that introduces a figure or a cross-reference ("Rs. 1.5",
# "Sec. 19.4 The …").
_INLINE_CLAUSE = re.compile(
    r"(?<=[.;:])[ \t]+(?=\d{1,3}(?:\.\d{1,3})+(?:\(\w{1,3}\))?\.?[ \t]+[\"“(A-Z])")
_NOT_A_SENTENCE_END = frozenset({"rs", "no", "nos", "inr", "usd", "approx", "v", "vs",
                                 "sec", "cl", "art", "para", "s", "ss", "r", "rr"})


def _clause_starts(text: str) -> list[int]:
    """Offsets where a numbered clause begins. Empty when the text has no numbering."""
    starts: list[int] = []
    for m in _CLAUSE_LINE.finditer(text):
        num = m.group("num")
        # A bare four-digit number is a year, a monetary amount or a stray page
        # artefact far more often than a clause. Requiring either a dot or at most
        # three digits keeps "2024." out while admitting "4." and "1.13.".
        if "." not in num and len(num) > 3:
            continue
        if m.start() == 0:
            continue          # already the start of this text; not a split point
        starts.append(m.start())
    for m in _INLINE_CLAUSE.finditer(text):
        word = re.findall(r"[A-Za-z]+", text[:m.start()][-12:])
        if not word or word[-1].lower() not in _NOT_A_SENTENCE_END:
            starts.append(m.end())
    return sorted(set(starts))


def leading_section_ref(text: str) -> str | None:
    """The clause number this text opens with, if it states one.

    Read from the content at query time rather than stored on the chunk row: it is a
    pure function of the text, so deriving it cannot drift, whereas a stored copy is
    exactly the "independent provenance" `AM-27` r4 forbids. A chunk that continues a
    clause from the previous page opens with no number and honestly returns None.
    """
    m = _CLAUSE_LINE.match(text)
    if not m:
        return None
    num = m.group("num")
    if "." not in num and len(num) > 3:
        return None
    return num


# Sentence-ish boundaries, used only to break a clause that is still over the cap.
_SUBCLAUSE = re.compile(r"(?<=\n)(?=\s*(?:\(\w{1,3}\)|\d{1,3}(?:\.\d{1,3})+\.?)(?:\s|$))")
# Both patterns are ZERO-WIDTH on purpose. A pattern that consumes the whitespace it
# splits on makes reassembly lossy: the pieces concatenate to "law.Each" instead of
# "law. Each", which breaks phrase search and reads as a typo in a citation. Keeping
# the separator with the following piece means concatenation is exactly lossless, and
# the per-chunk strip removes it only at the edges.
_SENTENCE = re.compile(r"(?<=[.;:])(?=\s+[A-Z(])")


@dataclass(frozen=True)
class Chunk:
    """One retrieval unit, traceable to the evidence row it came from.

    Deliberately carries no page number, section number, section title or source type.
    Those live on the evidence row and are reached by join — duplicating them here is
    the "independent provenance" `AM-27` r4 forbids, and a denormalized copy is how a
    derived store starts disagreeing with its source.
    """

    evidence_id: object
    ordinal: int
    content: str
    start_offset: int | None
    end_offset: int | None


def _split_long(text: str) -> list[str]:
    """Split an over-long segment at the best boundary available.

    Tries the document's own sub-clause markers first, then sentence ends, and only
    falls back to a hard character cut when the text offers no structure at all — a
    single unbroken block, which in practice means bad OCR.
    """
    for pattern in (_SUBCLAUSE, _SENTENCE):
        parts = [p for p in pattern.split(text) if p.strip()]
        if len(parts) > 1:
            merged = _accumulate(parts)
            # Only accept the split if it actually solved the problem. A clause with
            # one 3000-character sentence splits into pieces still over the cap, and
            # recursing on the next pattern is better than accepting that.
            if all(len(m) <= MAX_CHUNK_CHARS for m in merged):
                return merged
    # No usable structure: a hard cut, which is honest about being arbitrary.
    return [text[i:i + MAX_CHUNK_CHARS]
            for i in range(0, len(text), MAX_CHUNK_CHARS)]


def _accumulate(parts: list[str]) -> list[str]:
    """Greedily pack parts up to the cap, then fold a runt tail into its predecessor."""
    out: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{part}" if current else part
        if current and len(candidate) > MAX_CHUNK_CHARS:
            out.append(current)
            current = part
        else:
            current = candidate
    if current:
        out.append(current)
    if len(out) > 1 and len(out[-1]) < MIN_TAIL_CHARS:
        tail = out.pop()
        out[-1] = f"{out[-1]}{tail}"
    return out


# A line that is nothing but a clause number — `10`, `10.`, `4.3.1` — the shape the
# §10 / §10.1 / §10.2 extraction left behind: the number on its own line, its title on
# the next. Ending in a dot does not make it a sentence.
_BARE_NUMBER = re.compile(rf"^{_BLANK}*\d{{1,3}}(?:\.\d{{1,3}})*\.?{_BLANK}*$")
# An orphaned list marker — `e.`, `(a)`, `iv.`, `(iii)` — separated from its item.
_LIST_MARKER = re.compile(r"^\s*\(?(?:[a-zA-Z]|[ivxIVX]{1,4}|\d{1,2})[.)]\s*$")
# A bullet glyph opening a line: the item continues the list it sits in.
_BULLET = ("°", "•", "·", "▪", "○", "‣", "-", "\u2013", "\u2014", "*")
_TERMINAL = (".", ";", ":", ")", "\"", "\u201d", "'", "\u2019")


def _is_heading_line(line: str) -> bool:
    line = line.replace("\u200b", "").strip()
    if not line or len(line) >= MIN_CHUNK_CHARS:
        return False
    if _BARE_NUMBER.match(line) or _LIST_MARKER.match(line):
        return True
    if line.startswith(_BULLET):
        return False          # a list item, not a title — handled as a tail
    letters = [ch for ch in line if ch.isalpha()]
    # `8. ACCEPTABLE USER POLICY (AUP)` — an all-capitals line is a title whatever
    # it ends with; a sentence is not written in capitals.
    if letters and all(ch.isupper() for ch in letters):
        return True
    return not line.endswith((".", ";", ")"))


def _is_heading(piece: str) -> bool:
    """A clause title, a bare clause number, an orphan list marker, or up to three such
    lines together (`7.\\n\\nEffect of Termination:`) — never a sentence. Deterministic,
    and deliberately narrow: one line that ends a sentence is a clause, however short."""
    lines = [ln for ln in piece.splitlines() if ln.strip()]
    return 0 < len(lines) <= 3 and all(_is_heading_line(ln) for ln in lines)


def is_fragment(content: str) -> bool:
    """The single definition of "not a retrieval unit on its own" — shared with
    `store.is_fragment`, which applies it at query time to rows indexed before this
    version of the chunker."""
    return _is_heading(content)


def _is_tail(piece: str, previous: str) -> bool:
    """A short piece that COMPLETES the clause before it rather than starting one.

    The document's own structure has to say so: the piece opens in lower case, with a
    closing bracket or a bullet (`the shift)`, `° Denial of Service Attacks`), or the
    previous piece stopped mid-sentence — `...payment within` / `30 days of invoice.`,
    where the clause splitter took a number at the start of a line for a clause. A
    short piece after a piece that DID end its sentence is a clause of its own, however
    short — `1.10 "Term" means the period specified in Clause 5.` stays a chunk (owner,
    2026-09-10: short legal sentences are valid evidence).
    """
    if len(piece) >= MIN_CHUNK_CHARS:
        return False
    head = piece.lstrip("\u200b \t")
    if head[:1].islower() or head.startswith((")", ",", *_BULLET)):
        return True
    return not previous.rstrip().rstrip("\u200b").endswith(_TERMINAL)


def runs_on(previous: str, following: str, *, page_break: bool) -> bool:
    """D15: `previous` stops mid-sentence and `following` carries the rest of it.

    Across a page break, not ending the sentence is enough: the break is the page's,
    not the author's. Within a page the parser's row break IS a paragraph break, so the
    next block must visibly continue — lower case, a bracket, a bullet, or a comma
    before it (measured 2026-10-01: without this, 498 same-page boundaries between a
    label line and the next capitalised item were read as one sentence). A following
    block that opens a clause or a heading never continues anything."""
    head = following.lstrip("\u200b \t")
    tail = previous.rstrip().rstrip("\u200b")
    if not head or _CLAUSE_LINE.match(head) or _is_heading(following) \
            or tail.endswith(_TERMINAL):
        return False
    return page_break or tail.endswith(",") or head[:1].islower() \
        or head.startswith(("(", ")", ",", *_BULLET))


def _fold_fragments(pieces: list[str]) -> list[str]:
    """Merge a heading into the piece that follows it, and a tail into the piece before.

    A heading-shaped piece is carried forward and prepended to the next piece, so
    `7. TERM AND TERMINATION` becomes the first line of the chunk holding §7.1 rather
    than a chunk of its own; a bare `10.` travels the same way. A continuation tail is
    appended to its predecessor. A trailing heading with nothing after it folds back.
    Lossless: the pieces still concatenate to the original text, joined by the newline
    the split consumed nothing of.
    """
    out: list[str] = []
    carry = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        piece = f"{carry}\n{piece}" if carry else piece
        carry = ""
        if _is_heading(piece):
            carry = piece
            continue
        if out and _is_tail(piece, out[-1]):
            out[-1] = f"{out[-1]}\n{piece}"
            continue
        out.append(piece)
    if carry:
        if out:
            out[-1] = f"{out[-1]}\n{carry}"
        else:
            out.append(carry)
    return out


# A short row whose exact text recurs this many times in one document version is page
# furniture — a running header, a footer date, a brand line — not a clause.
FURNITURE_REPEATS = 3


def _excluded_rows(contents: list[str]) -> set[int]:
    """Indexes of evidence rows that must not become retrieval units: page furniture.

    A short row whose exact text recurs `FURNITURE_REPEATS` times or more across the
    version — a running header, a footer date, a brand line — belongs to no clause and
    is decided by the document's own repetition, nothing else. A heading-only row is
    deliberately NOT excluded here: it carries the clause number a user asks with
    ("what does 17.2 say?"), and `store.search_hybrid` redirects a hit on it to the
    clause it introduces. A short row that is a sentence is always kept.
    """
    short = Counter(c for c in contents if c and len(c) < MIN_CHUNK_CHARS)
    return {i for i, c in enumerate(contents)
            if c and len(c) < MIN_CHUNK_CHARS and short[c] >= FURNITURE_REPEATS}


# A web page printed to PDF, or any paper with a running header and footer, repeats a
# line on every page — usually fused into a clause row, where `_excluded_rows` never
# sees it. A running line sits at the TOP of a page's first row or the FOOT of its last
# row, on FURNITURE_REPEATS pages and at least FURNITURE_PAGE_SHARE of the document's
# pages; it and the page's own number ("3", "Page 3 of 9") are trimmed from those two
# edges only. What is left is one contiguous span of the row, so the integrity gate
# holds and the evidence is untouched (locked 34.12). Both tests are needed — measured
# 2026-09-30 on the supplied corpus: an Act's "Illustrations" sub-heading recurs on most
# pages (frequency alone took 65 of them) and ends a page now and then (position alone
# took 8). Headers alternating odd/even pages each sit on about half. A list marker or
# any other number is content. Below MIN_FURNITURE_PAGES no line is running text: in a
# two-to-four page contract a heading at the top of most pages is likelier content, and
# on the real corpus (2026-10-01) nothing was trimmed from the 11 such documents anyway.
_PAGE_NUMBER = re.compile(r"^(?:page\s+)?(\d{1,4})(?:\s+of\s+\d{1,4})?$", re.I)
EDGE_LINES = 3
FURNITURE_PAGE_SHARE = 0.4
MIN_FURNITURE_PAGES = 5


def _page_edges(rows: list) -> tuple[set[int], set[int]]:
    """Indexes of the first and of the last row on each page."""
    first: dict = {}
    last: dict = {}
    for index, row in enumerate(rows):
        page = getattr(row, "page_number", None)
        if page is not None:
            first.setdefault(page, index)
            last[page] = index
    return set(first.values()), set(last.values())


def _furniture_lines(rows: list, first: set[int], last: set[int]) -> set[str]:
    pages: dict[str, set] = {}
    for index, row in enumerate(rows):
        lines = [line.strip() for line in (row.content or "").split("\n")]
        edge = ((lines[:EDGE_LINES] if index in first else [])
                + (lines[-EDGE_LINES:] if index in last else []))
        for s in edge:
            if s and not _BARE_NUMBER.match(s) and not _LIST_MARKER.match(s):
                pages.setdefault(s, set()).add(row.page_number)
    total = len({getattr(row, "page_number", None) for row in rows} - {None})
    if total < MIN_FURNITURE_PAGES:
        return set()
    floor = max(FURNITURE_REPEATS, total * FURNITURE_PAGE_SHARE)
    return {s for s, seen in pages.items() if len(seen) >= floor}


def _trim_edges(content: str, page: int | None, furniture: set[str], *,
                top: bool, foot: bool) -> str:
    def edge(line: str) -> bool:
        s = line.strip()
        number = _PAGE_NUMBER.match(s)
        return not s or s in furniture or bool(number and number.group(1) == str(page))
    lines = content.split("\n")
    while top and lines and edge(lines[0]):
        lines.pop(0)
    while foot and lines and edge(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def _indexable(rows: list) -> list[tuple]:
    """(row, text) for every row that becomes retrieval units, furniture trimmed."""
    contents = [(row.content or "").strip() for row in rows]
    first, last = _page_edges(rows)
    excluded, furniture = _excluded_rows(contents), _furniture_lines(rows, first, last)
    out = []
    for index, (row, content) in enumerate(zip(rows, contents, strict=True)):
        if content and index not in excluded:
            text = _trim_edges(content, getattr(row, "page_number", None), furniture,
                               top=index in first, foot=index in last)
            if text:
                out.append((row, text))
    return out


# Integrity gate (roadmap PHASE 2 §2: "No document becomes searchable until ingestion
# integrity checks pass"). A folded heading (≤3 lines under MIN_CHUNK_CHARS) and a
# folded tail may legitimately sit on top of a capped piece.
OVERSIZE_CHARS = MAX_CHUNK_CHARS + 4 * MIN_CHUNK_CHARS
COVERAGE_FLOOR = 0.95


def _norm(text: str) -> str:
    return " ".join(text.replace("\u200b", " ").split())


def integrity_failures(rows: list, chunks: list[Chunk]) -> list[str]:
    """The checks a chunk set must pass before it is written. Empty means it passes.

    FABRICATED_TEXT  a chunk whose text is not in its own evidence row — a bad join,
                     a label the parser never read
    OVERSIZED        a chunk over the cap plus what folding may add
    REPEATED_TEXT    one clause-length text repeated like page furniture
    CONTENT_LOSS     the chunks cover under COVERAGE_FLOOR of the indexable text
    """
    by_id = {row.id: _norm(row.content or "") for row in rows}
    failures = []
    fabricated = sum(1 for c in chunks
                     if _norm(c.content) not in by_id.get(c.evidence_id, ""))
    if fabricated:
        failures.append(f"FABRICATED_TEXT: {fabricated} chunk(s) not in their evidence")
    oversized = sum(1 for c in chunks if len(c.content) > OVERSIZE_CHARS)
    if oversized:
        failures.append(f"OVERSIZED: {oversized} chunk(s) over {OVERSIZE_CHARS} chars")
    repeats = Counter(_norm(c.content) for c in chunks
                      if len(c.content) >= MIN_CHUNK_CHARS)
    exploded = [n for n in repeats.values() if n >= FURNITURE_REPEATS]
    if exploded:
        failures.append(f"REPEATED_TEXT: {len(exploded)} text(s) repeated "
                        f"{FURNITURE_REPEATS}+ times")
    indexable = sum(len(_norm(text)) for _, text in _indexable(rows))
    covered = sum(len(_norm(c.content)) for c in chunks)
    if indexable and covered / indexable < COVERAGE_FLOOR:
        failures.append(f"CONTENT_LOSS: chunks cover {covered / indexable:.1%}")
    return failures


def chunk_evidence(rows: list) -> list[Chunk]:
    """Turn committed evidence rows into chunks, in document order.

    ``rows`` are `DocumentEvidence` objects — passed in rather than queried here, so
    this function stays pure and testable without a database.

    Offsets are carried through where the split allows. When an evidence row is split,
    only the first piece can honestly claim the row's `start_offset`: the parser's
    offsets refer to positions in the extracted text, and the normalization applied
    between `original_content` and `content` means a character count into the
    normalized string is not an offset into the original. Rather than compute a
    plausible-looking offset that is subtly wrong, later pieces carry ``None`` — an
    absent offset is honest, a fabricated one corrupts a citation.
    """
    chunks: list[Chunk] = []
    ordinal = 0
    # A blank row, a page-furniture row, or a row that was only furniture is not a
    # retrieval unit (`_indexable`). Skipped rather than stored, so the index never
    # returns a hit with nothing a user could read in it. The evidence row itself is
    # untouched — the index is derived, it is not the record (`AM-27` r4).
    for row, content in _indexable(rows):
        # A trimmed edge moves the text off the row's recorded offsets.
        whole = (row.content or "").strip()
        starts_at_row, ends_at_row = whole.startswith(content), whole.endswith(content)
        # Clause boundaries first — structural, and applied whatever the length.
        starts = _clause_starts(content)
        if starts:
            bounds = [0, *starts, len(content)]
            clauses = [content[a:b] for a, b in pairwise(bounds)]
        else:
            clauses = [content]
        # Then the length cap, per clause, for the genuinely over-long ones.
        pieces: list[str] = []
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            pieces.extend([clause] if len(clause) <= MAX_CHUNK_CHARS
                          else _split_long(clause))
        pieces = _fold_fragments(pieces)
        for index, piece in enumerate(pieces):
            first = index == 0
            chunks.append(Chunk(
                evidence_id=row.id,
                ordinal=ordinal,
                content=piece,
                start_offset=row.start_offset if first and starts_at_row else None,
                end_offset=(row.end_offset if first and len(pieces) == 1 and ends_at_row
                            else None),
            ))
            ordinal += 1
    return chunks


# A blank a template leaves for a value — "____ months", "[●]", "[ ]", "[*]", a dotted
# leader on a signature line (Ask plan 1.14). Marked so a reader is told the term is
# not stated; the text is never filled, normalised or removed.
_BLANK_FIELD = re.compile(r"_{3,}|\.{4,}|…{2,}|\[\s*(?:[●•*]+|\s)\s*\]")


def blank_fields(content: str) -> list[tuple[int, int]]:
    """(start, end) of every blank field in the text, in order."""
    return [m.span() for m in _BLANK_FIELD.finditer(content)]

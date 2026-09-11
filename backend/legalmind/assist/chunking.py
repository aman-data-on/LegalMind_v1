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
CHUNKING_ALGORITHM_VERSION = "clause-aware-4"

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
    return starts


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
    contents = [(row.content or "").strip() for row in rows]
    excluded = _excluded_rows(contents)
    for index, row in enumerate(rows):
        content = contents[index]
        if not content or index in excluded:
            # A blank evidence row is not a retrieval unit, and neither is a row that
            # is only a heading or page furniture. Skipped rather than stored, so the
            # index never returns a hit with nothing a user could read in it. The
            # evidence row itself is untouched — the index is derived, it is not the
            # record (`AM-27` r4).
            continue
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
                start_offset=row.start_offset if first else None,
                end_offset=row.end_offset if first and len(pieces) == 1 else None,
            ))
            ordinal += 1
    return chunks

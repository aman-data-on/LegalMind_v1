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
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

# The chunker's own version, recorded on every row it writes. A change to the
# boundaries below must change this, because chunk ids recorded against an older
# algorithm would otherwise be silently reinterpreted.
CHUNKING_ALGORITHM_VERSION = "clause-aware-2"

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
_CLAUSE_LINE = re.compile(
    r"^[ \t]*(?P<num>\d{1,3}(?:\.\d{1,3})*)\.?(?=[ \t]*$|[ \t]+\S)",
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
    for row in rows:
        content = (row.content or "").strip()
        if not content:
            # A blank evidence row is not a retrieval unit. Skipped rather than stored
            # empty, so the index never returns a hit with nothing in it.
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
        for index, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
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

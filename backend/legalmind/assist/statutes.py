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

import hashlib
import logging
import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.observability.logs import log_event
from legalmind.security import permissions as P

STATUTE_CHUNKING_ALGORITHM_VERSION = "section-3"
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
_SUBSECTION = re.compile(r"(?<=\n)(?=[ \t]*\(\d{1,2}\)[ \t])")
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


def _split_long(section: str) -> list[tuple[str | None, str]]:
    """Split an over-long section at its sub-section markers, greedily packed."""
    parts = [p for p in _SUBSECTION.split(section) if p.strip()]
    if len(parts) <= 1:
        return [(None, section[i:i + MAX_SECTION_CHARS])
                for i in range(0, len(section), MAX_SECTION_CHARS)]
    out: list[tuple[str | None, str]] = []
    current = ""
    current_sub: str | None = None
    for part in parts:
        sub = re.match(r"[ \t]*(\(\d{1,2}\))", part)
        if current and len(current) + len(part) > MAX_SECTION_CHARS:
            out.append((current_sub, current))
            current, current_sub = part, sub.group(1) if sub else None
        else:
            if not current:
                current_sub = sub.group(1) if sub else None
            current += part
    if current:
        out.append((current_sub, current))
    return out


def chunk_statute_text(text: str) -> list[StatuteChunk]:
    """Section-based chunks of an Act's text, in the Act's own order and numbering."""
    text = text or ""
    numbered = [(m.start(), m.group("num")) for m in _SECTION_START.finditer(text)]
    roman = len(numbered) < 2
    if roman:
        # An instrument that numbers its directions (i), (ii), ... — CERT-In's shape.
        numbered = [(m.start(), m.group("num"))
                    for m in _DIRECTION_START.finditer(text)]
        keyfn = lambda n: (0, n)  # noqa: E731 — roman order is the document's order
    else:
        keyfn = _section_key
    schedules = [] if roman else [
        (m.start(), _schedule_label(m.group()))
        for m in _SCHEDULE_START.finditer(text)
        if m.start() > len(text) * SCHEDULE_TAIL_FRACTION]
    if schedules:
        # Inside a Schedule, `1.` and `2.` number its ENTRIES, not the Act's sections.
        numbered = [b for b in numbered if b[0] < schedules[0][0]]
    bounds = [*sorted(numbered + schedules), (len(text), None)]

    def _piece_len(i: int) -> int:
        return len(text[bounds[i][0]:bounds[i + 1][0]].strip())

    # Where the body begins. India Code PDFs open with an ARRANGEMENT OF SECTIONS —
    # one line per section, the same numbers — and footnotes carry numbers of their
    # own, so the first "1." is not the Act's first section. The body starts at the
    # first occurrence of the LOWEST section number whose piece is a body (long) and
    # whose successor is a higher-numbered body: arrangement entries fail the second
    # test (their successors are one-liners), footnotes come later. Everything before
    # that point is front matter and is not a section.
    keys = [keyfn(num) for _, num in bounds[:-1]]
    lowest = min(keys) if keys else None
    body_from = 0
    for i, key in enumerate(keys):
        if key == lowest and _piece_len(i) >= MIN_SECTION_CHARS and i + 1 < len(keys) \
                and keys[i + 1] > key and _piece_len(i + 1) >= MIN_SECTION_CHARS:
            body_from = i
            break

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
    # running section, belongs to the section before it.
    sections: list[list] = []          # [num, start, end]
    for (s, num), (nxt, _) in pairwise(ordered):
        piece = text[s:nxt]
        if sections and (len(piece.strip()) < MIN_SECTION_CHARS
                         or keyfn(num) < keyfn(sections[-1][0])):
            sections[-1][2] = nxt
            continue
        if len(piece.strip()) < MIN_SECTION_CHARS:
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


def _page_text(page) -> str:
    """One page in READING order, not in PDF content-stream order.

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
    return "\n".join(b[4].strip() for b in blocks if b[4].strip())


def _pdf_text(path: Path) -> str:
    import pymupdf

    doc = pymupdf.open(str(path))
    return "\n".join(_page_text(page) for page in doc.pages())


def ingest_statute(db: DBSession, *, path: Path, provenance: dict) -> dict:
    """Register one statute and (re)chunk it. Refuses without full provenance (r6)."""
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

    chunks = chunk_statute_text(_pdf_text(path))
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

    schema = config.assist_schema()
    statute_id = _upsert_statute(db, schema, sha=sha, provenance=provenance)
    repointed = _replace_statute_chunks(db, schema, statute_id, chunks)
    embedded = _embed(db, statute_id)
    log_event("assist.statutes.ingested", statute_id=str(statute_id),
              chunks=len(chunks), embedded=embedded,
              citations_repointed=repointed)              # counts only (53.3)
    return {"statute_id": str(statute_id), "chunks": len(chunks), "sections": sections,
            "embedded": embedded, "file_sha256": sha,
            "citations_repointed": repointed}


def _upsert_statute(db: DBSession, schema: str, *, sha: str, provenance: dict) -> UUID:
    """The statute row, KEPT across a re-ingest so its chunks can be reconciled.

    It used to be deleted and rewritten. That cascades through `statute_chunks` into
    `answer_citations` (migration `d7e2a9c41b58`), so every past answer silently lost
    the section it quoted — rule 17 forbids exactly that, and production carried 10
    such citations when this was written (2026-09-20).
    """
    fields = {"title": provenance["official_title"],
              "act": provenance["act_number_year"], "jur": provenance["jurisdiction"],
              "src": provenance["source"], "ref": provenance["source_ref"],
              "amended": provenance["as_amended_date"], "sha": sha,
              "by": provenance["supplied_by"], "at": provenance["supplied_at"]}
    prior = db.execute(sql_text(
        f'SELECT id FROM "{schema}".statutes WHERE file_sha256 = :sha '
        'OR official_title = :title ORDER BY created_at'), fields).scalars().all()
    # A second row matching on the other key is a duplicate of the same Act; it has no
    # reconcilable identity of its own, so it goes as before.
    for duplicate in prior[1:]:
        db.execute(sql_text(f'DELETE FROM "{schema}".statutes WHERE id = :i'),
                   {"i": duplicate})
    if prior:
        db.execute(sql_text(f"""
            UPDATE "{schema}".statutes
               SET official_title = :title, act_number_year = :act, jurisdiction = :jur,
                   source = :src, source_ref = :ref, as_amended_date = :amended,
                   file_sha256 = :sha, supplied_by = :by, supplied_at = :at
             WHERE id = :id
        """), {**fields, "id": prior[0]})
        return prior[0]
    statute_id = uuid4()
    db.execute(sql_text(f"""
        INSERT INTO "{schema}".statutes
            (id, official_title, act_number_year, jurisdiction, source, source_ref,
             as_amended_date, file_sha256, supplied_by, supplied_at)
        VALUES (:id, :title, :act, :jur, :src, :ref, :amended, :sha, :by, :at)
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


def _embed(db: DBSession, statute_id: UUID) -> int:
    """Best-effort vectors for the section chunks — lexical retrieval works without."""
    from legalmind.assist import calibration, embedding_runtime, store

    if not embedding_runtime.available():
        return 0
    schema = config.assist_schema()
    rows = db.execute(sql_text(f"""
        SELECT id, content FROM "{schema}".statute_chunks
         WHERE statute_id = :s ORDER BY ordinal"""), {"s": statute_id}).all()
    vectors = embedding_runtime.embed_texts([r[1] for r in rows]) if rows else None
    if not vectors:
        return 0
    identity = embedding_runtime.identity() or calibration.EMBEDDING_MODEL_REPO
    name, _, revision = identity.partition("@")
    model_id = store.register_embedding_model(
        db, name=name, version=revision or calibration.EMBEDDING_MODEL_REVISION,
        dimensions=calibration.EMBEDDING_DIMENSIONS,
        checksum=embedding_runtime.checksum_fragment() or "unrecorded")
    vtype = store.vector_type(db)
    written = 0
    for (chunk_id, _), vector in zip(rows, vectors, strict=True):
        literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
        db.execute(sql_text(f"""
            INSERT INTO "{schema}".statute_chunk_embeddings
                (id, statute_chunk_id, embedding_model_id, embedding)
            VALUES (:id, :c, :m, CAST(:v AS {vtype}))
            ON CONFLICT (statute_chunk_id, embedding_model_id) DO NOTHING
        """), {"id": uuid4(), "c": chunk_id, "m": model_id, "v": literal})
        written += 1
    return written


def available(db: DBSession) -> bool:
    """A ratified corpus exists — the router's `statutes_available` input."""
    schema = config.assist_schema()
    return bool(db.execute(
        sql_text(f'SELECT 1 FROM "{schema}".statutes LIMIT 1')).first())


def holdings(db: DBSession) -> list[str]:
    """The Acts the corpus holds — public information, used in the refusal (AM-46 r3)."""
    schema = config.assist_schema()
    return [r[0] for r in db.execute(sql_text(
        f'SELECT official_title FROM "{schema}".statutes ORDER BY official_title')).all()]


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


def expand_aliases(query: str) -> str:
    """Short names people type for Acts, expanded to the words the official title
    uses so the title match can see them. Names only — no law.

    The table lives in `intent.ACT_ALIASES`: the router needs the same short names to
    recognise that a question NAMES an instrument, and two copies would drift. The
    dependency runs from this module to that one, which imports nothing but `re`.
    """
    from legalmind.assist.intent import ACT_ALIASES

    lowered = f" {(query or '').lower()} "
    for short, full in ACT_ALIASES.items():
        if f" {short} " in lowered:
            lowered = lowered.replace(f" {short} ", f" {short} {full} ")
    return lowered.strip()


def search_statutes(db: DBSession, *, query: str, permissions: frozenset[str],
                    limit: int = 6, embed_query=None,
                    require_semantic: bool = False) -> list[StatuteHit]:
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
    rows = db.execute(sql_text(f"""
      SELECT * FROM (
        WITH q AS (SELECT tsvector_to_array(to_tsvector('english', :q)) AS lex)
        SELECT sc.id, s.official_title, s.act_number_year, sc.section_number,
               sc.sub_section, sc.marginal_note, sc.content, sc.ordinal,
               (SELECT count(*) FROM q, unnest(tsvector_to_array(sc.content_tsv)) l
                 WHERE l = ANY(q.lex)) AS matched,
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
                  FROM q, unnest(tsvector_to_array(to_tsvector('english',
                                                               s.official_title))) t
                 WHERE t NOT IN ('india', 'indian'))
                   AS act_match
          FROM "{schema}".statute_chunks sc
          JOIN "{schema}".statutes s ON s.id = sc.statute_id
         WHERE (SELECT cardinality(lex) FROM q) > 0
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
         ORDER BY (act_match >= 0.5) DESC, exact_section DESC, matched DESC,
                  (official_title LIKE '%REPEALED%') ASC, act_match DESC, score DESC,
                  official_title, ordinal
         LIMIT :limit
    """), {"q": query or "", "wanted": wanted or [""], "limit": limit * 6}).all()
    floor = 2 if len((query or "").split()) > 1 else 1
    # A question that names the Act ("What is the DPDP Act?") is answered from
    # that Act even when no section's text repeats the question's words: a
    # majority title-lexeme match alone admits its opening sections (AM-50 r3).
    hits = [StatuteHit(r.id, r.official_title, r.act_number_year, r.section_number,
                       r.sub_section, r.marginal_note, r.content, float(r.score))
            for r in rows
            if r.exact_section or r.matched >= floor or r.act_match >= 0.5][:limit]
    # Vector increment (2026-09-09): a paraphrase that names no Act, section or
    # statutory word — "can a company process someone's personal data without
    # asking them?" — has no lexeme to match. The stored section vectors (`AM-32`'s
    # `statute_chunk_embeddings`, filled at ingestion) are consulted through the
    # same calibrated gate the document retrieval uses, and admitted neighbours
    # FILL the slots the lexical ranking left empty — they never displace an exact
    # section or a named Act, so the ranking `AM-47` locked stays lexical-first.
    named = any(r.exact_section or r.act_match >= 0.5 for r in rows)
    if named:
        # A named section or Act: lexical-first stands; vectors only fill the rest.
        if len(hits) < limit:
            seen = {h.statute_chunk_id for h in hits}
            hits += [h for h in _vector_neighbours(db, query, limit=limit,
                                                   embed_query=embed_query)
                     if h.statute_chunk_id not in seen][:limit - len(hits)]
    else:
        # Nothing named: a two-lexeme OR match is a weak signal ("company" and
        # "person" reach the Companies Act for a question about personal data),
        # while a gated cosine is a strong one. Reciprocal rank fusion, the
        # vector side winning an exact tie.
        vector = _vector_neighbours(db, query, limit=limit, embed_query=embed_query)
        if require_semantic and not vector:
            log_event("assist.statutes.searched", hits=0, level=logging.DEBUG,
                      cause="no_semantic_evidence")
            return []
        from legalmind.assist.calibration import RRF_K

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
        hits = [by_id[i] for i in ranked][:limit]
    log_event("assist.statutes.searched", hits=len(hits), level=logging.DEBUG)
    return hits


def _vector_neighbours(db: DBSession, query: str, *, limit: int,
                       embed_query=None) -> list[StatuteHit]:
    """Gated nearest neighbours over `statute_chunk_embeddings`; [] without a model,
    without vectors, or when the calibrated gate stays shut."""
    from legalmind.assist import calibration, embedding_runtime, store

    embed = embed_query or embedding_runtime.embed_query
    embedded = embed(query) if query and query.strip() else None
    if embedded is None:
        return []
    vector, _identity = embedded
    schema = config.assist_schema()
    op = f'OPERATOR("{store.vector_schema(db)}".<=>)'
    vtype = store.vector_type(db)
    literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
    rows = db.execute(sql_text(f"""
        SELECT sc.id, s.official_title, s.act_number_year, sc.section_number,
               sc.sub_section, sc.marginal_note, sc.content,
               1 - (se.embedding {op} CAST(:q AS {vtype})) AS cosine
          FROM "{schema}".statute_chunk_embeddings se
          JOIN "{schema}".statute_chunks sc ON sc.id = se.statute_chunk_id
          JOIN "{schema}".statutes s ON s.id = sc.statute_id
         ORDER BY se.embedding {op} CAST(:q AS {vtype}), s.official_title, sc.ordinal
         LIMIT :lim
    """), {"q": literal, "lim": max(limit, calibration.RETRIEVAL_TOP_K)}).all()
    scores = [float(r.cosine) for r in rows]
    if not calibration.gate_is_open(False, scores):
        return []
    return [StatuteHit(r.id, r.official_title, r.act_number_year, r.section_number,
                       r.sub_section, r.marginal_note, r.content, float(r.cosine))
            for r in rows if float(r.cosine) >= calibration.EVIDENCE_COSINE_FLOOR][:limit]

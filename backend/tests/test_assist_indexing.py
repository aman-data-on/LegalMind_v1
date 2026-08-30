"""Chunking, indexing and lexical search — Gate section 5b unit A2.

Two halves, deliberately separate. The chunker is a pure function and is tested without
a database, which is what makes its determinism cheap to assert. Indexing and search run
against a really-ingested document, because the property that matters there is that the
chunks trace back to the evidence the *real* parser produced — not to a fixture that
happens to look like it.

Nothing here asserts a legal conclusion. Every document below is synthetic clause text
written for this test; per rule 21 no real contract, Company Standard or threshold
appears, and the assist lane produces no Finding to assert anyway (`AM-25` r1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from legalmind import config
from legalmind.assist import store
from legalmind.assist.chunking import (
    CHUNKING_ALGORITHM_VERSION,
    MAX_CHUNK_CHARS,
    chunk_evidence,
    leading_section_ref,
)
from legalmind.assist.indexing import index_document_version, index_safely
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import LocalFilesystemStorage
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_ingestion import build_docx


@dataclass
class FakeEvidence:
    """Stands in for a `DocumentEvidence` row in the pure-chunker tests."""

    id: uuid.UUID
    content: str
    start_offset: int | None = 0
    end_offset: int | None = 100


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(tmp_path / "objects")


PARAGRAPHS = [
    "1. Definitions",
    "In this Agreement, Affiliate means any entity controlling or controlled by a party.",
    "17.2 Limitation of Liability",
    "Neither party's aggregate liability shall exceed the fees paid in the twelve months "
    "preceding the claim, save for death or personal injury.",
    "18. Termination for Convenience",
    "Either party may terminate this Agreement on ninety days written notice.",
]


def _ingested(db, storage, user, paragraphs=None):
    contract = M.Contract(owner_id=user.id, name="Synthetic MSA",
                          contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    result = ingest_document(
        db, storage, contract_id=contract.id, uploaded_by=user.id,
        data=build_docx(paragraphs or PARAGRAPHS), filename="msa.docx",
        declared_mime=DOCX_MIME)
    return result.document_version


# ==========================================================================
# The chunker, as a pure function
# ==========================================================================
def test_a_short_evidence_row_becomes_exactly_one_chunk():
    rows = [FakeEvidence(uuid.uuid4(), "A short clause."),
            FakeEvidence(uuid.uuid4(), "Another short clause.")]
    chunks = chunk_evidence(rows)
    assert [c.content for c in chunks] == ["A short clause.", "Another short clause."]
    assert [c.ordinal for c in chunks] == [0, 1]


def test_chunking_is_deterministic():
    """Not `ENG-11` determinism — the assist lane makes no such claim (`AM-28` r1) —
    but re-indexing must not move chunk boundaries, or a citation recorded against an
    earlier run points somewhere else."""
    rows = [FakeEvidence(uuid.uuid4(), "Clause. " * 400)]
    runs = [[(c.ordinal, c.content) for c in chunk_evidence(rows)] for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_a_blank_evidence_row_produces_no_chunk():
    """A hit with nothing in it is worse than no hit."""
    rows = [FakeEvidence(uuid.uuid4(), "   \n  "),
            FakeEvidence(uuid.uuid4(), "Real content.")]
    chunks = chunk_evidence(rows)
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0, "ordinals stay contiguous across a skipped row"


def test_an_over_long_row_is_split_and_every_piece_is_within_the_cap():
    sentence = "The Provider shall maintain records of all processing activities. "
    rows = [FakeEvidence(uuid.uuid4(), sentence * 80)]
    chunks = chunk_evidence(rows)
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)


def test_a_split_row_reassembles_to_the_original_text():
    """Splitting may not lose or duplicate text.

    Joined with a space, because the split consumes the whitespace at each seam and
    the pieces are individually stripped. Whitespace is not the property under test:
    no word may vanish, and none may appear twice.
    """
    sentence = "Each party shall comply with applicable data protection law. "
    original = sentence * 80
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), original)])
    assert " ".join(c.content for c in chunks).split() == original.split()


def test_only_the_first_piece_of_a_split_row_claims_the_offset():
    """A fabricated offset corrupts a citation; an absent one is honest.

    The parser's offsets index the extracted text, and normalization between
    `original_content` and `content` means a character count into the normalized
    string is not an offset into the original. So later pieces carry None rather than
    a plausible-looking number.
    """
    rows = [FakeEvidence(uuid.uuid4(), "Sentence one. " * 300,
                         start_offset=500, end_offset=9000)]
    chunks = chunk_evidence(rows)
    assert len(chunks) > 1
    assert chunks[0].start_offset == 500
    assert chunks[0].end_offset is None, "a split row's first piece does not end where the row does"
    assert all(c.start_offset is None and c.end_offset is None for c in chunks[1:])


def test_an_unsplittable_block_still_gets_bounded_chunks():
    """Bad OCR produces text with no sentence or sub-clause structure at all.

    The fallback is a hard character cut, which is arbitrary — and preferable to
    emitting one enormous chunk that is useless as a retrieval unit.
    """
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), "x" * 7000)])
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHUNK_CHARS for c in chunks)


def test_every_chunk_names_the_evidence_row_it_came_from():
    """`AM-27` r4 — traceability is the point of the chunk, not a nicety."""
    a, b = uuid.uuid4(), uuid.uuid4()
    chunks = chunk_evidence([FakeEvidence(a, "First."), FakeEvidence(b, "Second.")])
    assert [c.evidence_id for c in chunks] == [a, b]


# ==========================================================================
# Indexing, against a really-ingested document
# ==========================================================================
def test_indexing_writes_chunks_traceable_to_real_evidence(db, storage, user):
    dv = _ingested(db, storage, user)
    result = index_document_version(db, dv.id)

    assert not result.skipped
    assert result.chunks_written > 0
    assert store.count_chunks(db, dv.id) == result.chunks_written

    schema = config.assist_schema()
    from sqlalchemy import text
    orphans = db.execute(text(f"""
        SELECT count(*) FROM "{schema}".chunks c
         LEFT JOIN document_evidence e ON e.id = c.evidence_id
         WHERE e.id IS NULL
    """)).scalar()
    assert orphans == 0, "every chunk must resolve to a real evidence row"

    versions = db.execute(text(
        f'SELECT DISTINCT chunking_algorithm_version FROM "{schema}".chunks'
    )).scalars().all()
    assert versions == [CHUNKING_ALGORITHM_VERSION]


def test_chunk_text_is_a_substring_of_its_evidence_row(db, storage, user):
    """The chunk is a derived view, not an independent record (`AM-27` r4).

    If a chunk's text is not found in the evidence it claims to come from, the chunker
    has invented or transformed content — and a citation to it would point at text the
    document does not contain.
    """
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)

    from sqlalchemy import text
    schema = config.assist_schema()
    bad = db.execute(text(f"""
        SELECT c.id FROM "{schema}".chunks c
          JOIN document_evidence e ON e.id = c.evidence_id
         WHERE position(c.content in e.content) = 0
    """)).scalars().all()
    assert bad == [], f"{len(bad)} chunk(s) are not substrings of their evidence"


def test_indexing_twice_is_a_no_op_rather_than_a_silent_reindex(db, storage, user):
    """Deliberately not idempotent-by-overwrite.

    Delete-and-reinsert would cascade to `answer_citations`, silently invalidating
    citations recorded against the removed chunks. So a second call reports what it
    found and changes nothing.
    """
    dv = _ingested(db, storage, user)
    first = index_document_version(db, dv.id)

    second = index_document_version(db, dv.id)
    assert second.skipped
    assert second.chunks_written == 0
    assert "already indexed" in (second.reason or "")
    assert store.count_chunks(db, dv.id) == first.chunks_written


def test_an_explicit_reindex_replaces_the_chunks(db, storage, user):
    dv = _ingested(db, storage, user)
    first = index_document_version(db, dv.id)
    again = index_document_version(db, dv.id, reindex=True)
    assert not again.skipped
    assert again.chunks_written == first.chunks_written
    assert store.count_chunks(db, dv.id) == first.chunks_written


def test_indexing_an_unknown_document_version_drops_cleanly(db):
    """Same posture as the analysis task's unknown Review: it means the enqueuing
    transaction never committed, so this is not an error to raise."""
    result = index_document_version(db, uuid.uuid4())
    assert result.skipped
    assert result.reason == "document version not found"


def test_index_safely_never_raises(db, monkeypatch):
    """An upload whose parsing succeeded must not be undone by a derived index.

    Evidence is authoritative and untouched; the only casualty is a rebuildable index.
    Letting this propagate would let the assist lane break the authoritative path,
    which is the inversion `AM-25` r1 and Step 38 rule 21 exist to prevent.
    """
    from legalmind.assist import indexing

    def boom(*args, **kwargs):
        raise RuntimeError("index backend exploded")

    monkeypatch.setattr(indexing, "chunk_evidence", boom)
    result = index_safely(db, uuid.uuid4())
    assert result.skipped
    assert result.chunks_written == 0


# ==========================================================================
# Lexical search
# ==========================================================================
def test_search_finds_a_clause_by_phrase(db, storage, user):
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)

    hits = store.search_chunks(db, document_version_id=dv.id,
                               query="aggregate liability")
    assert hits, "expected a hit for a phrase present in the document"
    assert any("aggregate liability" in h.content for h in hits)


def test_search_finds_a_clause_by_its_section_number(db, storage, user):
    """The case a stemmed full-text index alone handles badly.

    "17.2" is not a word, and this is why the trigram signal exists alongside
    `tsvector` — a lexical search over legal text that cannot find a section number is
    not much use.
    """
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)

    hits = store.search_chunks(db, document_version_id=dv.id, query="17.2")
    assert hits, "expected a hit for a section number stated in the document"


def test_search_reports_provenance_joined_from_the_evidence_row(db, storage, user):
    """`AM-27` r4 — the chunk stores no provenance, so a citation's page and section
    come from the authoritative evidence row on every query."""
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)

    hits = store.search_chunks(db, document_version_id=dv.id, query="Termination")
    assert hits
    assert all(h.source_type for h in hits), "source type must come through"
    assert any(h.section_number for h in hits), (
        "at least one hit should carry the section number the parser detected")


def test_search_never_returns_a_chunk_from_another_document(db, storage, user):
    """`AM-25` r6 — the scope is applied inside the query, not to the results.

    This is the property the whole retrieval-authorization design rests on. The
    signature takes one authorized `document_version_id` precisely so a caller cannot
    forget to scope it, and here two documents contain the same clause text: a search
    scoped to one must not see the other's chunk even though it matches.
    """
    mine = _ingested(db, storage, user)
    theirs = _ingested(db, storage, user)
    index_document_version(db, mine.id)
    index_document_version(db, theirs.id)

    hits = store.search_chunks(db, document_version_id=mine.id,
                               query="aggregate liability")
    assert hits
    from sqlalchemy import text
    schema = config.assist_schema()
    theirs_ids = set(db.execute(text(
        f'SELECT id FROM "{schema}".chunks WHERE document_version_id = :dv'
    ), {"dv": theirs.id}).scalars().all())
    assert not ({h.chunk_id for h in hits} & theirs_ids)


def test_an_empty_query_returns_nothing_rather_than_everything(db, storage, user):
    """Fail closed. An empty query matching the whole document would be a quiet
    disclosure of its contents rather than a search."""
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)
    assert store.search_chunks(db, document_version_id=dv.id, query="") == []
    assert store.search_chunks(db, document_version_id=dv.id, query="   ") == []


def test_a_query_matching_nothing_returns_no_hits(db, storage, user):
    """`AM-29`'s `NO_EVIDENCE_RETRIEVED` has to be reachable honestly."""
    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)
    assert store.search_chunks(
        db, document_version_id=dv.id,
        query="zzzznonexistentclausetermzzzz") == []


def test_the_retrieval_score_is_not_stored_on_the_chunk(db, assist_schema_name=None):
    """A score is a property of one query, not of the document.

    Storing it would make a per-question number look like a permanent attribute — and
    it is a *retrieval* score, never legal confidence (`AI-03` item 16).
    """
    from sqlalchemy import text
    schema = config.assist_schema()
    cols = set(db.execute(text("""
        SELECT column_name FROM information_schema.columns
         WHERE table_schema = :s AND table_name = 'chunks'
    """), {"s": schema}).scalars().all())
    assert not (cols & {"score", "rank", "retrieval_score", "similarity"})


# ==========================================================================
# The ingestion hook
# ==========================================================================
def test_uploading_a_document_indexes_it(api, db, seeded, user, storage):
    """End to end through the real endpoint, with no broker configured — so the
    dispatcher takes its inline fallback and the chunks exist by the time the
    response returns."""
    from tests.conftest import grant_role, sign_in

    grant_role(db, user, "USER")
    sign_in(api, db, user)
    created = api.post("/api/v1/contracts",
                       json={"name": "Upload indexes", "contract_type": "MSA"})
    assert created.status_code == 201
    contract_id = created.json()["data"]["id"]

    response = api.post(
        f"/api/v1/contracts/{contract_id}/document-versions",
        content=build_docx(PARAGRAPHS),
        headers={"content-type": DOCX_MIME, "x-filename": "msa.docx"})
    assert response.status_code == 201
    document_version_id = response.json()["data"]["document_version"]["id"]

    assert store.count_chunks(db, uuid.UUID(document_version_id)) > 0, (
        "the upload endpoint should have dispatched indexing inline")


# ==========================================================================
# Clause-boundary splitting — driven by what the real documents actually look like
# ==========================================================================
# Measured on the supplied documents on 2026-08-25: PyMuPDF emits **no blank lines**
# for them, so `parsing.segment_paragraphs` (which splits on `\n\s*\n`) produces one
# page-sized evidence row per page. Across six real documents that gave 99
# page-fragment chunks and **2 of 59 evidence rows carrying a section number**.
#
# Splitting on the clause markers the documents state — `1.13.`, `4.1.`,
# `4. SCOPE OF SERVICES`, each on its own line — took that to 341 chunks with a
# section on 300 of them. These tests pin the behaviour that produced it.
PAGE_SIZED_ROW = (
    "1.13.\n"
    "“Services” means any services provided by the Provider to the Customer.\n"
    "1.14.\n"
    "“Service Commencement Date” means the date of acceptance of the first order.\n"
    "1.15.\n"
    "“Service Credits” means the credits the Customer would be entitled to receive.\n"
)


def test_a_page_sized_row_splits_at_its_clause_markers():
    """The measured real-document case: one evidence row holding several clauses.

    Length-driven splitting alone left these as one chunk, because the row is under
    the character cap — so a page with three definitions in it produced a single
    retrieval unit conflating all three.
    """
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), PAGE_SIZED_ROW)])
    assert len(chunks) == 3, [c.content[:30] for c in chunks]
    assert [leading_section_ref(c.content) for c in chunks] == ["1.13", "1.14", "1.15"]


def test_clause_splitting_happens_regardless_of_length():
    """Not a length optimization. A short row with two clauses is still two chunks,
    because the unit that matters for a citation is the clause, not the page."""
    short = "5.\nThe first obligation.\n6.\nThe second obligation.\n"
    assert len(short) < MAX_CHUNK_CHARS
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), short)])
    assert len(chunks) == 2


def test_a_clause_number_with_a_title_on_the_same_line_is_recognised():
    """`4. SCOPE OF SERVICES` — the other real shape in these documents."""
    text = "3.\nPreceding text.\n4. SCOPE OF SERVICES\nThis Agreement shall govern.\n"
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), text)])
    refs = [leading_section_ref(c.content) for c in chunks]
    assert "4" in refs


def test_a_four_digit_number_is_not_mistaken_for_a_clause():
    """`2024.` is a year, a monetary amount or a page artefact far more often than a
    clause. Requiring a dot or at most three digits keeps it out — without which a
    contract mentioning a year would fragment at every occurrence."""
    text = "Payment is due in 2024.\n2024.\nThis line begins with a year, not a clause.\n"
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), text)])
    assert len(chunks) == 1
    assert leading_section_ref("2024.\nSomething") is None


def test_a_chunk_continuing_a_clause_across_a_page_has_no_section_of_its_own():
    """Honest absence rather than a guess.

    A page that opens mid-clause carries no number, and inventing one — inheriting the
    previous page's, say — would put a citation on text that does not state it.
    """
    text = "continuing text from the previous page without any marker.\n"
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), text)])
    assert len(chunks) == 1
    assert leading_section_ref(chunks[0].content) is None


def test_clause_splitting_loses_no_text():
    chunks = chunk_evidence([FakeEvidence(uuid.uuid4(), PAGE_SIZED_ROW)])
    assert " ".join(c.content for c in chunks).split() == PAGE_SIZED_ROW.split()


def test_the_section_reference_is_derived_and_not_stored(db, storage, user):
    """`AM-27` r4 — no independent provenance on the chunk row.

    The section a citation displays is either the evidence row's own `section_number`
    or the clause marker the chunk's text opens with. Neither is a stored copy, so
    neither can drift from the document.
    """
    from sqlalchemy import text as sql

    dv = _ingested(db, storage, user)
    index_document_version(db, dv.id)
    schema = config.assist_schema()
    cols = set(db.execute(sql("""
        SELECT column_name FROM information_schema.columns
         WHERE table_schema = :s AND table_name = 'chunks'
    """), {"s": schema}).scalars().all())
    assert not (cols & {"section_number", "section_ref", "section_title"})

    hits = store.search_chunks(db, document_version_id=dv.id, query="Limitation")
    assert hits
    assert any(h.section_ref for h in hits), (
        "a hit on a numbered clause should resolve a section reference")

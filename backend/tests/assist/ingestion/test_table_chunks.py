"""Tables through the chunker (N-TBLSPLIT, 2026-10-15) — pure, no database.

A table reaches the chunker as `parsing.table_row` lines (`| a | b |`), inline in the
clause that introduces it (PDF) or as its own TABLE row (DOCX). Before clause-aware-6
an over-long table was cut by the sentence splitter mid-row, and a short row looked
like a heading (short, no full stop) and was carried onto the NEXT clause.
"""

from __future__ import annotations

from types import SimpleNamespace

from legalmind.assist.ingestion import chunking
from legalmind.assist.ingestion.chunking import (
    MAX_CHUNK_CHARS,
    _norm,
    chunk_evidence,
    integrity_failures,
    is_fragment,
)


def _row(content, page=1):
    return SimpleNamespace(id="ev", content=content, page_number=page,
                           start_offset=0, end_offset=len(content))


def _coverage(rows, chunks):
    indexable = sum(len(_norm(text)) for _, text in chunking._indexable(rows))
    return sum(len(_norm(c.content)) for c in chunks) / indexable


def test_a_table_row_is_never_a_heading_or_a_fragment():
    for line in ("| a | b |", "| SLA | CREDIT |", "| < 99.9% | 5% |"):
        assert not chunking._is_heading_line(line)
        assert not is_fragment(line)


def test_a_short_row_after_a_clause_stays_with_that_clause_not_the_next():
    clause = "4.1 The Provider shall issue a service credit as set out below:"
    following = ("4.2 Service credits are the Customer's sole and exclusive remedy for "
                 "downtime under this Agreement.")
    out = chunking._fold_fragments([clause, "| UPTIME | CREDIT |", following])
    # Before: the capitalised row was a "heading" and opened clause 4.2's chunk.
    assert out[-1] == following
    assert "| UPTIME | CREDIT |" in out[0]


def test_a_heading_with_a_small_table_is_one_clean_chunk():
    content = "Issuance of Service Credits\n" + "\n".join(
        f"| < {99.9 - i / 10:.1f}% | {5 * (i + 1)}% of the monthly fee |"
        for i in range(6))
    rows = [_row(content)]
    chunks = chunk_evidence(rows)
    assert [c.content for c in chunks] == [content]
    assert integrity_failures(rows, chunks) == []


def test_a_long_table_splits_only_between_rows():
    header = "| Availability | Credit | Cap |"
    body = [f"| Below {99.9 - i / 100:.2f}% in month {i} | {i % 20 + 1}% of the monthly "
            f"fee for the affected service | 20% |" for i in range(60)]
    content = "\n".join([header, *body])
    assert len(content) > MAX_CHUNK_CHARS
    rows = [_row(content)]
    chunks = chunk_evidence(rows)
    assert len(chunks) > 1
    lines = set(content.split("\n"))
    for c in chunks:
        assert c.content.startswith("| ")                 # a row boundary, never mid-row
        assert set(c.content.split("\n")) <= lines        # whole rows only
    assert integrity_failures(rows, chunks) == []         # no FABRICATED_TEXT/OVERSIZED
    assert _coverage(rows, chunks) >= 0.95


def test_a_single_row_over_the_cap_is_still_bounded():
    giant = "| " + "word " * 600 + "|"
    content = "\n".join(["| Term | Meaning |", giant, "| Fee | Monthly |"])
    rows = [_row(content)]
    chunks = chunk_evidence(rows)
    assert all(len(c.content) <= chunking.OVERSIZE_CHARS for c in chunks)
    assert integrity_failures(rows, chunks) == []

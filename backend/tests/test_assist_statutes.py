"""Domain C — provenance-refusing ingestion, section chunking, Act + section retrieval."""
import os
from pathlib import Path

import pytest

from legalmind.assist import statutes
from legalmind.assist.statutes import (
    StatuteIngestRefused,
    chunk_statute_text,
    ingest_statute,
    search_statutes,
)
from legalmind.security import permissions as P

ASK = frozenset({P.ASSIST_ASK})

SYNTHETIC_ACT = (
    "THE SYNTHETIC WIDGETS ACT, 2099\nARRANGEMENT OF SECTIONS\n"
    "1. Short title.\n2. Definitions.\n3. Widget handling.\n"
    "THE SYNTHETIC WIDGETS ACT, 2099\n"
    "1. Short title.—This Act may be called the Synthetic Widgets Act, 2099. It extends to "
    "the whole of the test suite and to nowhere else whatsoever, and it commences on the day "
    "it is read by a test runner, which is a purely synthetic event of no legal character.\n"
    "2. Definitions.—In this Act, unless the context otherwise requires,—\n"
    "(1) \"widget\" means a synthetic thing used only in tests of this software and nothing "
    "that exists in the world; (2) \"handler\" means a person who handles a widget in a test.\n"
    "3. Widget handling.—(1) Every handler shall handle every widget with synthetic care.\n"
    "(2) A handler who fails to do so shall be liable to a synthetic penalty, which is not a "
    "penalty under any real law and creates no obligation on anyone anywhere at any time.\n"
    "1. Subs. by Act 1 of 2100, s. 7, for \"care\" (w.e.f. never) — a footnote-shaped line.\n"
)


def test_sections_are_chunked_by_the_acts_own_numbering():
    chunks = chunk_statute_text(SYNTHETIC_ACT)
    assert [c.section_number for c in chunks] == ["1", "2", "3"]
    assert chunks[0].marginal_note == "Short title"
    assert chunks[2].content.startswith("3. Widget handling")


def test_the_arrangement_table_and_footnotes_are_not_sections():
    chunks = chunk_statute_text(SYNTHETIC_ACT)
    assert all(len(c.content) >= statutes.MIN_SECTION_CHARS for c in chunks)
    # The trailing "1. Subs. by ..." footnote breaks monotonic order and folds into s. 3.
    assert "Subs. by Act 1 of 2100" in chunks[-1].content


def test_a_direction_numbered_in_roman_is_still_a_section():
    text = ("Directions are issued as follows:\n"
            + "".join(f"({r}) Every provider shall do the synthetic thing number {i}, "
                      "which is described here at sufficient length to be a body and not a "
                      "heading, and which binds nobody in the real world at all.\n"
                      for i, r in enumerate(["i", "ii", "iii"], start=1)))
    assert [c.section_number for c in chunk_statute_text(text)] == ["i", "ii", "iii"]


def test_chunking_loses_no_section_text():
    joined = " ".join(c.content for c in chunk_statute_text(SYNTHETIC_ACT))
    for phrase in ("synthetic care", "synthetic penalty", "purely synthetic event"):
        assert phrase in joined


def _provenance(**over):
    base = {"official_title": "The Synthetic Widgets Act, 2099",
            "act_number_year": "Act No. 0 of 2099", "jurisdiction": "TEST",
            "source": "synthetic test fixture", "source_ref": "none — synthetic",
            "as_amended_date": "n/a", "supplied_by": "test", "supplied_at": "2026-09-08T00:00:00Z"}
    base.update(over)
    return base


def _pdf(tmp_path, text=SYNTHETIC_ACT):
    import pymupdf
    path = tmp_path / "synthetic.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 60), text, fontsize=8)
    doc.save(str(path))
    return path


def test_ingestion_refuses_incomplete_provenance(db, tmp_path):
    with pytest.raises(StatuteIngestRefused, match="provenance incomplete"):
        ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(source_ref=""))


def test_ingestion_refuses_a_missing_file(db, tmp_path):
    with pytest.raises(StatuteIngestRefused, match="not present"):
        ingest_statute(db, path=tmp_path / "absent.pdf", provenance=_provenance())


def test_ingested_sections_are_found_by_section_number_and_cited_act_plus_section(db, tmp_path):
    report = ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    assert report["chunks"] == 3 and statutes.available(db)
    hits = search_statutes(db, query="What does section 3 say about widget handling?",
                           permissions=ASK)
    assert hits and hits[0].section_number == "3"
    assert hits[0].citation == "The Synthetic Widgets Act, 2099, s. 3"
    assert "synthetic care" in hits[0].content


def test_without_assist_ask_the_corpus_is_empty(db, tmp_path):
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    assert search_statutes(db, query="section 3 widget", permissions=frozenset()) == []


def test_reingestion_replaces_rather_than_accumulates(db, tmp_path):
    from sqlalchemy import text

    from legalmind import config
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    n = db.execute(text(f'SELECT count(*) FROM "{config.assist_schema()}".statutes')).scalar()
    assert n == 1 and statutes.holdings(db) == ["The Synthetic Widgets Act, 2099"]


REAL = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR",
                           "/root/Legalmind.v1/legal-docs")) / "Indian_Laws_and_Acts" / "IT_Act_2000.pdf"


@pytest.mark.skipif(not REAL.exists(), reason="supplied statute not present on this machine")
def test_the_supplied_it_act_yields_section_43a(db):
    report = ingest_statute(db, path=REAL, provenance=_provenance(
        official_title="The Information Technology Act, 2000", act_number_year="Act No. 21 of 2000"))
    assert report["chunks"] > 80
    hits = search_statutes(db, query="What does section 43A of the IT Act say?", permissions=ASK)
    assert hits and hits[0].section_number == "43A"
    assert "body corporate" in hits[0].content.lower()

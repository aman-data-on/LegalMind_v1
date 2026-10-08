"""`AM-125` — footnotes cut at ingest (`section-6`) and the blue-green statute re-ingest:
a STAGED generation is invisible, a swap and a rollback are status flips, and nothing a
past answer cites is ever re-pointed or deleted (rule 17)."""
import os
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist.knowledge import statutes
from legalmind.assist.knowledge.statutes import (
    StatuteIngestRefused,
    ingest_statute,
    search_statutes,
    strip_footnotes,
)
from tests.assist.knowledge.test_assist_statutes import (
    ASK,
    SYNTHETIC_ACT,
    _pdf,
    _present,
    _provenance,
)

DOCS = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR",
                           "/root/Legalmind.v1/legal-docs")) / "Indian_Laws_and_Acts"
S9 = "9. Sections 6, 7 and 8 not to confer right to insist document should be accepted"


# --- section-6: page-foot footnotes are cut, and every cut is accounted for ------------

def test_trailing_footnote_and_page_mark_blocks_are_cut_and_counted():
    note = "1. Subs. by Act 6 of 1899, s. 2, for “thing” (w.e.f. 1-1-1900)."
    pages, cut = strip_footnotes([["3. Widget handling.—Every handler shall.", note,
                                   "1", "IndiaCode"]])
    assert pages == ["3. Widget handling.—Every handler shall."]
    assert (cut.footnotes, cut.page_marks) == (1, 2)
    assert cut.chars == len("\n".join([note, "1", "IndiaCode"])) and len(cut.sha256) == 64


def test_a_trailing_section_is_never_read_as_a_footnote():
    """The prototype trap: a pattern admitting "Section" cut the real IT Act s. 9."""
    pages, cut = strip_footnotes([["8. Something.", S9 + " in electronic form.", "1"]])
    assert S9 in pages[0] and cut.footnotes == 0


def test_a_number_that_is_not_the_pages_own_is_not_a_page_mark():
    pages, cut = strip_footnotes([["Body.", "7"]])
    assert pages == ["Body.\n7"] and cut.page_marks == 0


def test_a_cut_block_holding_law_refuses_the_act():
    merged = "1. Subs. by Act 1 of 2000, s. 3.\n2. Every person shall keep a register."
    with pytest.raises(StatuteIngestRefused, match="reads as law"):
        strip_footnotes([["Body.", merged]], source="x.pdf")


@pytest.mark.parametrize("block", [
    "2. Omitted by Act 4 of 2005, s. 2.\n11. The Controller shall be seen to act and every person seeking a "
    "licence shall pay the fee.",
    "1. Subs. by Act 2 of 2000, s. 3.\n(2) In particular, the Central Government may, by "
    "notification, make rules.",
])
def test_ordinary_statutory_words_do_not_pass_a_cut_block_as_editorial(block):
    """"seen", "seeking" and "notification" are law's words too: a cut item must cite
    its source, and a line that opens like a sub-section refuses the Act."""
    with pytest.raises(StatuteIngestRefused, match="reads as law"):
        strip_footnotes([["Body.", block]], source="x.pdf")


def test_a_lowercase_led_sub_section_still_opens_its_own_unit():
    """Income-tax s. 10 numbers its clauses "(23) any income of …": rejecting every
    lowercase-led marker filed s. 10(23) under "(15)"."""
    body = ("10. Incomes not included.—(1) Any income " + "x " * 600 + "\n(2) any fund "
            + "y " * 600 + "\n(3) any scholarship " + "z " * 600)
    assert [sub for sub, _ in statutes._split_long(body)][-2:] == ["(2)", "(3)"]


def test_a_short_section_named_in_the_arrangement_is_its_own_section():
    """IGST s. 3 ("3. Appointment of officers.––The Board may appoint …") is 130
    characters: under MIN_SECTION_CHARS it had been read into s. 2's definitions."""
    act = SYNTHETIC_ACT.replace(
        "3. Widget handling.—(1)",
        "3A. Widget keepers.—The Board may appoint widget keepers.\n3. Widget handling.—(1)"
    ).replace("3. Widget handling.\nTHE", "3A. Widget keepers.\n3. Widget handling.\nTHE")
    by_section = {c.section_number: c.content for c in statutes.chunk_statute_text(act)}
    assert by_section["3A"].startswith("3A. Widget keepers.")
    assert "widget keepers" not in by_section["2"]


def test_a_wrapped_cross_reference_does_not_open_a_sub_section():
    """IT Act s. 2 reads "…under sub-section\\n(4) of section 35;" — taken as
    sub-section (4), the real (2) after it was a restart and the whole definitions
    section was quarantined once the footnotes no longer hid it."""
    body = ("2. Definitions.—(1) In this Act " + "x " * 600 + "issued under sub-section\n"
            "(4) of section 35;\n" + "y " * 600 + "\n(2) Any reference in this Act.")
    subs = [sub for sub, _ in statutes._split_long(body)]
    assert "(4)" not in subs and "(2)" in subs


@pytest.mark.skipif(not _present(DOCS / "IT_Act_2000_indiacode.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_real_it_act_keeps_section_9_and_section_2_and_loses_its_footnotes():
    text_, cut = statutes._read_pdf(DOCS / "IT_Act_2000_indiacode.pdf")
    chunks = statutes.check_integrity(statutes.chunk_statute_text(text_), len(text_))
    sections = {c.section_number for c in chunks.kept}
    assert {"2", "3", "3A", "4", "9"} <= sections and not chunks.quarantined
    assert S9 in " ".join(" ".join(c.content.split()) for c in chunks.kept)
    assert cut.footnotes >= 20
    assert "1. Subs. by Act 10 of 2009, s. 2, for “digital signature” (w.e.f. 27-10-2009)" \
        not in text_


@pytest.mark.skipif(not _present(DOCS / "IGST_Act_2017.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_igst_footnote_is_gone_and_the_real_section_3_is_section_3():
    """"3. Ins. by Act 32 of 2018 …" was parsed as s. 3 holding s. 2's definitions; the
    real s. 3 ("Appointment of officers") must be filed as 3, never under s. 2."""
    text_, _ = statutes._read_pdf(DOCS / "IGST_Act_2017.pdf")
    by_section: dict[str, str] = {}
    for c in statutes.chunk_statute_text(text_):
        by_section[c.section_number] = by_section.get(c.section_number, "") + c.content
    assert by_section["3"].startswith("3. Appointment of officers.")
    assert "may appoint such central tax officers" not in by_section["2"]
    assert not re.search(r"(?m)^\s*3\.\s+Ins\. by Act 32 of 2018", text_)


@pytest.mark.skipif(not _present(DOCS / "Income_Tax_Act_1961_indiacode.pdf"),
                    reason="supplied statute not present on this machine")
def test_income_tax_section_10_clauses_carry_their_own_labels():
    text_, _ = statutes._read_pdf(DOCS / "Income_Tax_Act_1961_indiacode.pdf")
    opening = {c.content[:5]: c.sub_section for c in statutes.chunk_statute_text(text_)
               if c.section_number == "10" and c.sub_section}
    assert opening["(16) "] == "(16)" and opening["(23) "] == "(23)"


# --- blue-green: STAGED invisible, swap/rollback are flips, nothing deleted -----------

def _schema():
    return config.assist_schema()


def _cite(db, user, chunk_id):
    s = _schema()
    conv = db.execute(text(f'INSERT INTO "{s}".conversations (id, user_id) VALUES (:i, :u) '
                           "RETURNING id"), {"i": uuid.uuid4(), "u": user.id}).scalar_one()
    msg = db.execute(text(f'INSERT INTO "{s}".messages (id, conversation_id, ordinal, role, '
                          "content) VALUES (:i, :c, 0, 'ASSISTANT', 'x') RETURNING id"),
                     {"i": uuid.uuid4(), "c": conv}).scalar_one()
    answer = db.execute(text(f'INSERT INTO "{s}".ai_answers (id, message_id, answer_state) '
                             "VALUES (:i, :m, 'ANSWERED') RETURNING id"),
                        {"i": uuid.uuid4(), "m": msg}).scalar_one()
    db.execute(text(f'INSERT INTO "{s}".answer_citations (id, answer_id, statute_chunk_id, '
                    "claim_ordinal) VALUES (:i, :a, :c, 0)"),
               {"i": uuid.uuid4(), "a": answer, "c": chunk_id})
    return answer


def _statuses(db):
    return sorted(db.execute(text(f'SELECT status FROM "{_schema()}".statutes')).scalars())


def _hit(db):
    hits = search_statutes(db, query="What does section 3 say about widget handling?",
                           permissions=ASK)
    return hits[0].content if hits else None


def test_a_staged_generation_is_invisible_and_swaps_and_rolls_back_whole(db, tmp_path, user):
    s = _schema()
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    green = db.execute(text(f'SELECT id FROM "{s}".statute_chunks '
                            "WHERE section_number = '3'")).scalar_one()
    answer = _cite(db, user, green)
    new_text = SYNTHETIC_ACT.replace("synthetic care", "synthetic care and diligence")
    ingest_statute(db, path=_pdf(tmp_path, new_text), provenance=_provenance(),
                   stage=True)

    assert _statuses(db) == ["CURRENT", "STAGED"]
    assert statutes.holdings(db) == ["The Synthetic Widgets Act, 2099"]   # not twice
    assert "diligence" not in _hit(db), "a STAGED chunk must never be served"

    assert statutes.flip(db, incoming="STAGED", outgoing="STANDBY") == 1
    assert _statuses(db) == ["CURRENT", "STANDBY"]
    assert "diligence" in _hit(db)

    assert statutes.flip(db, incoming="STANDBY", outgoing="STAGED") == 1
    assert _statuses(db) == ["CURRENT", "STAGED"]
    assert "diligence" not in _hit(db)

    statutes.flip(db, incoming="STAGED", outgoing="STANDBY")
    chunks = db.execute(text(f'SELECT count(*) FROM "{s}".statute_chunks')).scalar()
    assert statutes.retire(db) == 1
    assert _statuses(db) == ["CURRENT", "WITHDRAWN"]
    # A later in-place ingest reuses the LIVE row and leaves the retired one whole.
    ingest_statute(db, path=_pdf(tmp_path, new_text), provenance=_provenance())
    assert db.execute(text(f'SELECT count(*) FROM "{s}".statute_chunks')).scalar() == chunks
    cited = db.execute(text(f'SELECT statute_chunk_id FROM "{s}".answer_citations '
                            "WHERE answer_id = :a"), {"a": answer}).scalar_one()
    assert cited == green, "the past answer still cites the chunk it quoted"


def test_the_standby_window_is_never_touched_by_an_in_place_ingest(db, tmp_path):
    """During the rollback window an in-place ingest, or a refused one, acts on the LIVE
    row only: matching the older STANDBY row would re-chunk it and lose the rollback."""
    s = _schema()
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    assert _statuses(db) == ["STAGED"]
    assert not statutes.available(db) and statutes.jurisdictions(db) == frozenset()
    db.execute(text(f"UPDATE \"{s}\".statutes SET status = 'CURRENT'"))
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    statutes.flip(db, incoming="STAGED", outgoing="STANDBY")
    standby = (f'SELECT c.id, c.content FROM "{s}".statute_chunks c JOIN "{s}".statutes t '
               "ON t.id = c.statute_id WHERE t.status = 'STANDBY' ORDER BY c.id")
    before = db.execute(text(standby)).all()
    new_text = SYNTHETIC_ACT.replace("synthetic care", "synthetic care and diligence")
    ingest_statute(db, path=_pdf(tmp_path, new_text), provenance=_provenance())
    assert statutes.withdraw_statute(db, path=_pdf(tmp_path), provenance=_provenance()) == 1
    assert _statuses(db) == ["STANDBY", "WITHDRAWN"]
    assert db.execute(text(standby)).all() == before


def test_a_refused_restage_withdraws_the_stale_staged_build_so_the_swap_refuses(
        db, tmp_path):
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    # The tool's refusal branch for a STAGE (`tools.ingest_statutes._ingest`).
    assert statutes.withdraw_statute(db, path=_pdf(tmp_path), provenance=_provenance(),
                                     stage=True) == 1
    assert _statuses(db) == ["CURRENT", "WITHDRAWN"]
    with pytest.raises(StatuteIngestRefused, match="0 STAGED"):
        statutes.flip(db, incoming="STAGED", outgoing="STANDBY")


def test_a_second_swap_refuses_while_a_standby_generation_waits(db, tmp_path):
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    statutes.flip(db, incoming="STAGED", outgoing="STANDBY")
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    with pytest.raises(StatuteIngestRefused, match="already waiting"):
        statutes.flip(db, incoming="STAGED", outgoing="STANDBY")
    assert _statuses(db) == ["CURRENT", "STAGED", "STANDBY"]


def test_a_swap_refuses_unless_the_staged_generation_holds_every_live_act(db, tmp_path):
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    with pytest.raises(StatuteIngestRefused, match="0 STAGED"):
        statutes.flip(db, incoming="STAGED", outgoing="STANDBY")
    assert _statuses(db) == ["CURRENT"]


def test_restaging_withdraws_the_previous_staged_row_and_deletes_nothing(db, tmp_path):
    s = _schema()
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance())
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    before = db.execute(text(f'SELECT count(*) FROM "{s}".statute_chunks')).scalar()
    ingest_statute(db, path=_pdf(tmp_path), provenance=_provenance(), stage=True)
    assert _statuses(db) == ["CURRENT", "STAGED", "WITHDRAWN"]
    assert db.execute(text(f'SELECT count(*) FROM "{s}".statute_chunks')).scalar() == \
        before + 3


def test_the_benchmark_reports_recall_at_5_and_citation_accuracy():
    from tools import rag_benchmark as rb
    case = {"id": "X", "category": "E", "must_not": [],
            "gold": [["STAT:Indian Contract Act, 1872:74"]]}
    shown = [f"STAT:Indian Contract Act, 1872:{n}" for n in (1, 2, 3, 4, 74)]
    out = rb.aggregate([rb.score_case(case, shown, shown, {"STATUTES"}, bool, False)])
    assert (out["recall@3"], out["recall@5"], out["citation_accuracy"]) == (0.0, 1.0, 1.0)

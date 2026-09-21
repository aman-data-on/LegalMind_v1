"""`section-3`: Schedules are their own citable unit, and a footnote marker glued to a
section number no longer swallows the rest of the Act.

The mechanism is tested on synthetic text so it runs everywhere, including CI, which
has no source material. The named real-Act cases — the ones the defect was found in —
are tested against the supplied PDFs and skip where those are absent.
"""
import os
from pathlib import Path

import pytest

from legalmind.assist.statutes import (
    MAX_SECTION_NUMBER_REPAIRS,
    SCHEDULE_TAIL_FRACTION,
    _repair_glued_markers,
    chunk_statute_text,
)

BODY = ("This section exists only in the test suite and states nothing about the world, "
        "and it is long enough to clear the minimum body length that separates a real "
        "section from an arrangement entry or a footnote line in a statute print. ")


def _act(*, glued: str = "", schedule: str = "") -> str:
    """A synthetic Act shaped like an India Code print: arrangement, then the body."""
    arrangement = ("THE SYNTHETIC REPAIR ACT, 2099\nARRANGEMENT OF SECTIONS\n"
                   "1. Short title.\n2. Definitions.\n3. Duties.\n4. Penalties.\n"
                   "THE SCHEDULE.\n")
    body = "THE SYNTHETIC REPAIR ACT, 2099\n"
    for n in ("1. Short title", "2. Definitions", "3. Duties"):
        body += f"{n}.—{BODY}\n"
    body += f"{glued or '4'}. Penalties.—{BODY}\n"
    body += f"5. Appeals.—{BODY}\n6. Review.—{BODY}\n"
    return arrangement + body + schedule


# --- the glued footnote marker ----------------------------------------------------

def test_a_glued_footnote_marker_does_not_swallow_the_rest_of_the_act():
    """`²4.` extracts as `24.`, which is above every section this Act has. Before
    `section-3` the monotonic fold then absorbed ss. 5 and 6 into it."""
    chunks = chunk_statute_text(_act(glued="24"))
    assert [c.section_number for c in chunks] == ["1", "2", "3", "4", "5", "6"]


def test_the_repair_is_bounded_by_the_acts_own_arrangement():
    """A number at or below the ceiling is a real section and is left alone: the
    arrangement runs to 4, and s. 4 is not rewritten to anything."""
    assert [c.section_number for c in chunk_statute_text(_act())] == \
        ["1", "2", "3", "4", "5", "6"]


def test_a_handful_of_rewrites_is_applied():
    """Tested on the helper: in a whole-Act run a wrong rewrite is usually absorbed by
    the monotonic fold and leaves no trace in the output, so a test at that level
    cannot tell a refusal from a rewrite."""
    numbered = [(0, "1"), (10, "250"), (20, "3")]          # 250 -> 50, one rewrite
    assert [n for _, n in _repair_glued_markers(numbered, (90, ""))] == ["1", "50", "3"]


def test_the_repair_refuses_itself_when_it_would_fire_too_often():
    """The Taxmann Income-tax print: the arrangement is not detectable, the ceiling is
    wrong, and an unguarded pass rewrites 186 numbers including real ss. 194C and
    115VA. Past the budget the WHOLE pass is abandoned, never trimmed."""
    numbered = [(i * 10, f"1{i + 10}") for i in range(MAX_SECTION_NUMBER_REPAIRS + 2)]
    assert _repair_glued_markers(numbered, (90, "")) == numbered


def test_no_ceiling_means_no_repair():
    """An Act whose front matter yields no section number is left exactly as it is."""
    numbered = [(0, "1"), (10, "999")]
    assert _repair_glued_markers(numbered, None) == numbered


# --- Schedules ---------------------------------------------------------------------

def test_a_schedule_is_its_own_citable_unit_not_the_last_sections_tail():
    schedule = ("THE SCHEDULE\n"
                "1. Breach of a synthetic duty.—May extend to one synthetic rupee. "
                + BODY + "\n")
    chunks = chunk_statute_text(_act(schedule=schedule))
    numbers = [c.section_number for c in chunks]
    assert "The Schedule" in numbers
    body = next(c for c in chunks if c.section_number == "The Schedule").content
    assert "one synthetic rupee" in body


def test_a_schedule_entry_number_is_not_read_as_a_section():
    """Inside a Schedule, `1.` numbers an entry. It must not reopen section 1."""
    schedule = ("THE SCHEDULE\n"
                "1. First entry.—" + BODY + "\n2. Second entry.—" + BODY + "\n")
    chunks = chunk_statute_text(_act(schedule=schedule))
    after = [c.section_number for c in chunks[chunks.index(
        next(c for c in chunks if c.section_number == "The Schedule")):]]
    assert set(after) == {"The Schedule"}, after


def test_an_arrangement_of_sections_schedule_line_is_not_a_boundary():
    """`THE SCHEDULE.` appears in the front matter too. Only a heading in the closing
    quarter of the document is the Schedule itself."""
    chunks = chunk_statute_text(_act())
    assert "The Schedule" not in [c.section_number for c in chunks]
    assert SCHEDULE_TAIL_FRACTION < 1.0


def test_a_section_heading_that_merely_mentions_a_schedule_stays_a_section():
    """The Companies Act, 1956 carries `347. APPLICATION OF SCHEDULE VIII TO CERTAIN
    MANAGING AGENTS`. The heading must be the whole line to count."""
    act = _act(schedule="4. APPLICATION OF SCHEDULE VIII TO AGENTS.—" + BODY + "\n")
    assert "The Schedule" not in [c.section_number for c in chunk_statute_text(act)]


# --- the real Acts the defect was found in -----------------------------------------

def _present(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:                      # unreadable is indistinguishable from absent
        return False


DOCS = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR",
                           "/root/Legalmind.v1/legal-docs")) / "Indian_Laws_and_Acts"


def _sections(name: str) -> dict[str, int]:
    from legalmind.assist.statutes import _pdf_text
    counts: dict[str, int] = {}
    for c in chunk_statute_text(_pdf_text(DOCS / name)):
        counts[c.section_number] = counts.get(c.section_number, 0) + 1
    return counts


@pytest.mark.skipif(not _present(DOCS / "IT_Act_2000_indiacode.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_it_acts_intermediary_and_privacy_sections_are_addressable():
    """`²66A.` was read as `266A`, which is above every section of the Act, so
    ss. 66A-87 folded into one 26-chunk blob: s. 79 (intermediary liability) was cited
    as `s. 266A(3) - Punishment for sending offensive messages`."""
    counts = _sections("IT_Act_2000_indiacode.pdf")
    for section in ("43A", "66A", "70B", "72A", "79"):
        assert section in counts, f"IT Act s. {section} is not addressable"
    assert "266A" not in counts, "the glued footnote marker is back"
    assert max(counts.values()) <= 10, f"a blob has reappeared: {max(counts.values())}"


@pytest.mark.skipif(not _present(DOCS / "CPC_1908.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_cpcs_glued_section_numbers_are_repaired():
    """`⁸60.` -> `860.` (Property liable to attachment and sale in execution of a
    decree) and `³92.` -> `392.` (Public charities)."""
    counts = _sections("CPC_1908.pdf")
    assert "60" in counts and "92" in counts
    assert "860" not in counts and "392" not in counts


@pytest.mark.skipif(not _present(DOCS / "DPDP_Act_2023_indiacode.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_dpdp_penalty_schedule_is_cited_as_the_schedule():
    """It was cited as `s. 44(3) - Amendments to certain Acts`, which is a wrong
    citation on the Act's whole penalty table."""
    from legalmind.assist.statutes import _pdf_text
    chunks = chunk_statute_text(_pdf_text(DOCS / "DPDP_Act_2023_indiacode.pdf"))
    schedule = [c for c in chunks if c.section_number == "The Schedule"]
    assert schedule, "the DPDP Schedule is not its own unit"
    assert any("two hundred and fifty crore rupees" in " ".join(c.content.split())
               for c in schedule)


@pytest.mark.skipif(not _present(DOCS / "Income_Tax_Act_1961.pdf"),
                    reason="supplied statute not present on this machine")
def test_the_income_tax_print_is_left_exactly_as_it_was():
    """This publisher print defeats the chunker (26 of ~298 sections) and `section-3`
    does not pretend otherwise: it must not change the Act in either direction. The
    repair refuses itself here; separately the monotonic fold would have absorbed the
    bad rewrites anyway, so this asserts the OUTCOME, not the guard."""
    counts = _sections("Income_Tax_Act_1961.pdf")
    assert "94C" not in counts and "15VA" not in counts, "a corrupt rewrite landed"
    assert "659" in counts, "the Act must be left as the previous chunker left it"


# --- the ranking the repaired corpus was measured on (2026-09-21) ------------------

@pytest.mark.skipif(not _present(DOCS / "SPDI_Rules_2011.pdf")
                    or not _present(DOCS / "DPDP_Act_2023_indiacode.pdf"),
                    reason="supplied statutes not present on this machine")
def test_a_fractional_title_match_no_longer_takes_every_slot(db):
    """`act_match` was the PRIMARY sort key on a fractional overlap, so the Act whose
    TITLE happened to carry the question's words took all ten slots. "reasonable
    security ... personal data" matched the SPDI Rules' title at 0.36; every hit came
    from the SPDI Rules and the DPDP Act's own penalty Schedule ranked 13th."""
    from legalmind.assist.statutes import ingest_statute, search_statutes
    from legalmind.security import permissions as P
    from tests.test_assist_statutes import _provenance

    for name, title, act in (
            ("SPDI_Rules_2011.pdf",
             "The Information Technology (Reasonable Security Practices and Procedures "
             "and Sensitive Personal Data or Information) Rules, 2011", "G.S.R. 313(E)"),
            ("DPDP_Act_2023_indiacode.pdf",
             "The Digital Personal Data Protection Act, 2023", "Act No. 22 of 2023")):
        ingest_statute(db, path=DOCS / name,
                       provenance=_provenance(official_title=title, act_number_year=act))
    hits = search_statutes(
        db, permissions=frozenset({P.ASSIST_ASK}), limit=6,
        query="What is the largest fine for failing to put reasonable security "
              "safeguards around personal data?")
    assert hits, "nothing retrieved"
    assert len({h.official_title for h in hits}) > 1, \
        "one Act still holds every slot: " + hits[0].official_title
    assert any("two hundred and fifty crore rupees" in " ".join(h.content.split())
               for h in hits), "the DPDP penalty Schedule is still buried"


def test_a_repealed_act_sorts_last_among_equals(db, tmp_path):
    """The corpus holds the Companies Act, 1956 and the Income-tax Act, 1961 for
    history. Alphabetising `official_title` on a tie put "... 1956 (REPEALED ...)"
    ahead of "... 2013" every time, so the repealed Act answered first.

    Scored on the LEXICAL path alone (`embed_query` returns nothing), because that is
    the ordering this changed. When no Act is named the lexical hits are fused with
    the gated vector neighbours, and fusion can still float a repealed Act — with two
    byte-identical synthetic Acts their vectors are identical and the tie is arbitrary.
    The end-to-end evidence that this helps on real law is the Domain C probe.
    """
    import pymupdf

    from legalmind.assist.statutes import ingest_statute, search_statutes
    from legalmind.security import permissions as P
    from tests.test_assist_statutes import _provenance

    body = ("THE SYNTHETIC ESTATE ACT\nARRANGEMENT OF SECTIONS\n1. A.\n2. Widgets.\n"
            "THE SYNTHETIC ESTATE ACT\n1. A.—" + BODY + "\n"
            "2. Widgets.—Every keeper shall keep every synthetic widget in a "
            "synthetic cupboard, and this sentence exists only so the section clears "
            "the minimum body length used by the chunker in this test suite.\n")
    for title in ("The Synthetic Estate Act, 2013",
                  "The Synthetic Estate Act, 1956 (REPEALED)"):
        pdf = tmp_path / f"{title[-9:].strip('() ')}.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((40, 60), body, fontsize=8)
        doc.save(pdf)
        ingest_statute(db, path=pdf, provenance=_provenance(
            official_title=title, act_number_year="Act No. 1"))
    hits = search_statutes(db, query="synthetic widget cupboard keeper",
                           permissions=frozenset({P.ASSIST_ASK}), limit=4,
                           embed_query=lambda _q: None)
    assert hits, "nothing retrieved"
    assert "REPEALED" not in hits[0].official_title, \
        f"a repealed Act answered first: {hits[0].citation}"


def test_a_citation_follows_its_TEXT_when_a_section_is_renumbered(db, tmp_path):
    """`section-3` renumbers — the IT Act's bogus "266A" blob becomes ss. 66A-87 — so
    the `(section_number, sub_section)` key cannot match and the old row is retired.
    Document order alone sent a citation of s. 79's text to s. 66, a historical answer
    pointing at a section that does not contain what it quoted (rule 17). The heir is
    now the chunk that CARRIES the text, and document order is only the fallback.
    """
    import uuid as _uuid

    import pymupdf
    from sqlalchemy import text as sql_text

    from legalmind import config
    from legalmind.assist.statutes import ingest_statute
    from tests.test_assist_statutes import _provenance

    DISTINCT = ("Every synthetic keeper shall keep every synthetic widget inside a "
                "synthetic cupboard at all times, and this sentence is long enough to "
                "identify the section it belongs to wherever that section moves to.")

    def _write(number: str):
        body = (f"THE SYNTHETIC MOVING ACT\nARRANGEMENT OF SECTIONS\n1. A.\n2. B.\n"
                f"{number}. Widgets.\n"
                f"THE SYNTHETIC MOVING ACT\n1. A.—{BODY}\n2. B.—{BODY}\n"
                f"{number}. Widgets.—{DISTINCT}\n")
        pdf = tmp_path / f"moving-{number}.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((40, 60), body, fontsize=8)
        doc.save(pdf)
        return pdf

    prov = _provenance(official_title="The Synthetic Moving Act",
                       act_number_year="Act No. 2 of 2099")
    ingest_statute(db, path=_write("3"), provenance=prov)
    schema = config.assist_schema()
    chunk_id = db.execute(sql_text(
        f'SELECT id FROM "{schema}".statute_chunks WHERE section_number = \'3\'')).scalar_one()

    user_id = db.execute(sql_text("SELECT id FROM users LIMIT 1")).scalar()
    if user_id is None:
        user_id = _uuid.uuid4()
        db.execute(sql_text("INSERT INTO users (id, email, name, status, created_at, "
                            "updated_at) VALUES (:i, :e, 'x', 'ACTIVE', now(), now())"),
                   {"i": user_id, "e": f"move-{_uuid.uuid4().hex[:8]}@leapswitch.com"})
    conv = db.execute(sql_text(f'INSERT INTO "{schema}".conversations (id, user_id) '
                               "VALUES (:i, :u) RETURNING id"),
                      {"i": _uuid.uuid4(), "u": user_id}).scalar_one()
    msg = db.execute(sql_text(f'INSERT INTO "{schema}".messages (id, conversation_id, '
                              "ordinal, role, content) VALUES (:i, :c, 0, 'ASSISTANT', 'x') "
                              "RETURNING id"), {"i": _uuid.uuid4(), "c": conv}).scalar_one()
    answer = db.execute(sql_text(f'INSERT INTO "{schema}".ai_answers (id, message_id, '
                                 "answer_state) VALUES (:i, :m, 'ANSWERED') RETURNING id"),
                        {"i": _uuid.uuid4(), "m": msg}).scalar_one()
    db.execute(sql_text(f'INSERT INTO "{schema}".answer_citations (id, answer_id, '
                        "statute_chunk_id, claim_ordinal) VALUES (:i, :a, :c, 0)"),
               {"i": _uuid.uuid4(), "a": answer, "c": chunk_id})

    ingest_statute(db, path=_write("3A"), provenance=prov)       # the SAME text, renumbered

    landed = db.execute(sql_text(
        f'SELECT sc.section_number, sc.content FROM "{schema}".answer_citations ac '
        f'JOIN "{schema}".statute_chunks sc ON sc.id = ac.statute_chunk_id '
        "WHERE ac.answer_id = :a"), {"a": answer}).all()
    assert landed, "the citation was lost"
    assert landed[0].section_number == "3A", \
        f"citation followed document order to s. {landed[0].section_number}, not its text"
    assert DISTINCT[:60] in " ".join(landed[0].content.split())

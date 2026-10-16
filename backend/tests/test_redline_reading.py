"""Marked-up (redlined) PDFs — AM-146.

A real customer MOU, exported with its tracked changes shown, was read as plain text:
a struck "3" beside an inserted "5" became "53 years", the markup tool's "[13.]" label
glued clause 13 onto clause 12, and bold headings above short bullets were absorbed
into the section above. Each test rebuilds one of those on a synthetic PDF (54.6 keeps
real documents out of the repository): orange text, an underline drawn under an
insertion and a line drawn through a deletion, as Word and LibreOffice export them.
"""

from __future__ import annotations

import pytest

from legalmind.ingestion import parsing
from legalmind.ingestion.parsing import detect_clause_number, parse_pdf

pymupdf = pytest.importorskip("pymupdf")

ORANGE = (0.776, 0.573, 0.0)
BLACK = (0, 0, 0)
BLUE = (0.0, 0.3, 0.8)


class _Page:
    """Writes runs left to right on one line; marks a run struck or underlined."""

    def __init__(self, page):
        self.page = page

    def line(self, y: float, *runs: tuple[str, str]) -> None:
        x = 72.0
        for text, mark in runs:
            font = "hebo" if mark == "bold" else "helv"
            colour = ORANGE if mark in ("ins", "del") else BLUE if mark == "link" else BLACK
            self.page.insert_text((x, y), text, fontsize=10, fontname=font, color=colour)
            end = x + pymupdf.get_text_length(text, fontname=font, fontsize=10)
            if mark in ("ins", "link", "black_underline"):
                self.page.draw_line((x, y + 2), (end, y + 2), color=colour, width=0.5)
            elif mark == "del":
                self.page.draw_line((x, y - 3.5), (end, y - 3.5), color=colour, width=0.5)
            x = end


def _pdf(*pages: list[tuple]) -> bytes:
    doc = pymupdf.open()
    for lines in pages:
        page = _Page(doc.new_page())
        for y, runs in lines:
            page.line(y, *runs)
    return doc.tobytes()


def _read(data: bytes):
    return parse_pdf(data, ocr=False, docling=False).segments


def test_a_struck_figure_beside_an_inserted_one_is_two_versions_never_one_number():
    segments = _read(_pdf([
        (72, [("Confidentiality", "bold")]),
        (90, [("Confidentiality obligation continues for ", ""), ("5", "ins"),
              ("3", "del"), (" years after termination.", "")]),
    ]))
    clause = segments[-1]
    assert "continues for 5 years" in clause.content
    assert "53" not in clause.content
    revision = clause.metadata["revision"]
    assert "continues for 3 years" in revision["original"]
    assert revision["changes"] == [{"deleted": "3", "inserted": "5"}]


def test_a_deleted_sentence_and_its_replacement_read_as_the_proposed_text():
    segments = _read(_pdf([
        (72, [("13. Service Termination: ", ""),
              ("A 30-day prior notice period applies.", "del"), (" ", ""),
              ("The Customer may terminate on 15 days notice.", "ins")]),
    ]))
    clause = segments[0]
    assert "15 days notice" in clause.content and "30-day" not in clause.content
    assert "A 30-day prior notice period applies." in clause.metadata["revision"]["original"]
    assert "15 days" not in clause.metadata["revision"]["original"]


def test_a_wholly_deleted_bullet_leaves_the_proposed_text_and_stays_in_the_original():
    segments = _read(_pdf([
        (72, [("Termination", "bold")]),
        (90, [("- Services stop after termination", "")]),
        (104, [("- ", ""), ("Early termination charges may apply", "del")]),
        (118, [("- ", ""), ("Customer must give 30 days notice", "del")]),
        (132, [("- Outstanding dues must be cleared", "")]),
    ]))
    clause = segments[-1]
    assert "Early termination" not in clause.content
    assert clause.content.count("- ") == 2              # no bullet left standing empty
    original = clause.metadata["revision"]["original"]
    assert original.index("Early termination") < original.index("30 days notice")


def test_a_document_with_links_but_no_strikes_is_not_marked_up():
    data = _pdf([
        (72, [("1. Contact ", ""), ("corporate@example.com", "link"),
              (" for notices.", "")]),
        (90, [("Ref: ", ""), ("LS/OCT/2026/NK/0156", "black_underline")]),
    ])
    doc = pymupdf.open(stream=data, filetype="pdf")
    assert parsing._revision_colours(doc) == frozenset()
    assert not any("revision" in s.metadata for s in _read(data))


def test_an_unmarked_document_reads_exactly_as_without_the_redline_reader(monkeypatch):
    # The isolation the owner asked for: the gate is the ONLY way in. Bold headings
    # above short lines keep today's reading on a document with no tracked changes.
    data = _pdf([
        (72, [("Confidentiality", "bold")]),
        (90, [("- Both parties keep information confidential", "")]),
        (104, [("Governing Law", "bold")]),
        (118, [("- Governed by Indian law", "")]),
    ])
    with_gate = [(s.content, s.metadata) for s in _read(data)]
    monkeypatch.setattr(parsing, "_revision_colours", lambda doc: frozenset())
    assert with_gate == [(s.content, s.metadata) for s in _read(data)]
    assert len(with_gate) == 1                           # absorbed, exactly as before


def test_in_a_marked_up_document_a_bold_heading_above_short_bullets_starts_a_section():
    segments = _read(_pdf([
        (72, [("Confidentiality", "bold")]),
        (90, [("- Obligation continues for ", ""), ("5", "ins"), ("3", "del"),
              (" years", "")]),
        (104, [("Governing Law", "bold")]),
        (118, [("- Governed by Indian law", "")]),
        (132, [("Penalty Clause:", "bold")]),
        (146, [("Credits are paid monthly.", "")]),
    ]))
    titles = [s.section_title for s in segments]
    assert titles == ["Confidentiality", "Governing Law", "Penalty Clause"]
    assert all(s.metadata.get("heading") for s in segments)


def test_a_markup_tools_bracketed_number_is_the_clause_number():
    assert detect_clause_number("[13.] Service Termination: notice")[0] == "13"
    assert detect_clause_number("[4.2.] Payment")[0] == "4.2"
    assert detect_clause_number("[1] See the schedule")[0] is None      # a footnote
    assert detect_clause_number("[13.] the rest of a sentence")[0] is None


def test_a_bracketed_clause_number_no_longer_glues_onto_the_clause_above():
    segments = _read(_pdf([
        (72, [("12. Support is provided on tickets raised by the customer.", "")]),
        (90, [("[13.] Service Termination: ", ""),
              ("The Customer may terminate on 15 days notice.", "ins")]),
    ]))
    assert [s.section_number for s in segments] == ["12", "13"]
    assert "15 days" not in segments[0].content


def test_a_clause_running_onto_the_next_page_is_one_segment():
    segments = _read(_pdf(
        [(72, [("Penalty Clause:", "bold")]),
         (90, [("Credits are calculated on a pro-rata basis from the time", ""),
               (" of the ticket", "ins"), (" daily", "del")])],
        [(72, [("the Trouble Ticket is issued until resolution.", "")]),
         (90, [("Dispute Resolution:", "bold")]),
         (104, [("Courts at Pune have jurisdiction.", "")])],
    ))
    penalty = next(s for s in segments if s.section_title == "Penalty Clause")
    assert "from the time of the ticket\nthe Trouble Ticket is issued" in penalty.content
    assert (penalty.page_number, penalty.metadata["end_page"]) == (1, 2)
    assert any(s.section_title == "Dispute Resolution" for s in segments)


def test_a_capitalised_page_top_after_an_unpunctuated_line_is_not_a_continuation():
    # A signature block ends unpunctuated; "IN WITNESS WHEREOF" begins its own text.
    segments = _read(_pdf(
        [(72, [("Warm Regards", "")]), (90, [("Business Development Manager", ""),
                                            (" Ltd", "del")])],
        [(72, [("IN WITNESS WHEREOF the Parties have executed this Agreement.", "")])],
    ))
    assert segments[-1].page_number == 2
    assert "end_page" not in segments[0].metadata


def test_a_docx_tracked_change_keeps_its_original_beside_the_accepted_text():
    """The DOCX path read the accepted view already (A3) but threw the deleted text
    away; it is now recorded exactly as a PDF's is."""
    import docx
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    w = nsdecls("w")
    d = docx.Document()
    p = d.add_paragraph("Liability shall not exceed the total fees paid in the ")
    for xml in (f'<w:del {w} w:id="1" w:author="x"><w:r><w:delText>12</w:delText></w:r></w:del>',
                f'<w:ins {w} w:id="2" w:author="x"><w:r><w:t>6</w:t></w:r></w:ins>',
                f'<w:r {w}><w:t xml:space="preserve"> months.</w:t></w:r>'):
        p._p.append(parse_xml(xml))
    d.add_paragraph("Governing law is India.")
    import io
    buf = io.BytesIO()
    d.save(buf)
    segments = parsing.parse_docx(buf.getvalue()).segments
    clause, plain = segments[0], segments[1]
    assert "paid in the 6 months" in clause.content
    assert clause.metadata["revision"] == {
        "original": "Liability shall not exceed the total fees paid in the 12 months.",
        "changes": [{"deleted": "12", "inserted": "6"}]}
    assert "revision" not in plain.metadata

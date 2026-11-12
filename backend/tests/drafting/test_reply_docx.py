"""Prepare our reply — R6, `AM-251` r2: the client's DOCX with our answers as tracked
changes, read back by the repository's own parser as exactly those changes.

Every fixture is built in memory with python-docx and placeholder text — no real
document and no legal content enters the repository (locked 54.6, rule 21).
"""

from __future__ import annotations

import io
import os
import subprocess
import zipfile
from datetime import UTC, datetime

import docx
import pytest
from docx.oxml import parse_xml
from lxml import etree

from legalmind.drafting.reply_docx import ReplyEdit, ReplyError, apply_reply
from legalmind.ingestion.parsing import parse_docx

WHEN = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
#: a paragraph the client marked: "thirty (30)" deleted, "fifteen (15)" inserted
CLIENT_MARKED = (
    f'<w:p {_WNS}><w:r><w:t xml:space="preserve">Clause E payable in </w:t></w:r>'
    '<w:del w:id="901" w:author="Client" w:date="2026-10-01T00:00:00Z"><w:r>'
    '<w:delText>thirty (30)</w:delText></w:r></w:del>'
    '<w:ins w:id="902" w:author="Client" w:date="2026-10-01T00:00:00Z"><w:r>'
    '<w:t>fifteen (15)</w:t></w:r></w:ins>'
    '<w:r><w:t xml:space="preserve"> days.</w:t></w:r></w:p>')


def _doc(*texts: str, table: tuple[str, ...] = (), raw: tuple[str, ...] = ()) -> bytes:
    d = docx.Document()
    for text in texts:
        d.add_paragraph(text)
    if table:
        cells = d.add_table(rows=1, cols=len(table)).rows[0].cells
        for cell, text in zip(cells, table, strict=True):
            cell.paragraphs[0].text = text
    for xml in raw:
        d.element.body.insert(len(d.element.body) - 1, parse_xml(xml))
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def _xml(data: bytes) -> etree._Element:
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return etree.fromstring(package.read("word/document.xml"))


def _paragraphs(data: bytes) -> list[bytes]:
    return [etree.tostring(p) for p in _xml(data).iterfind(".//w:p", NS)]


def _changes(data: bytes) -> list[dict]:
    """Every tracked change the parser reads back, in document order."""
    return [c for s in parse_docx(data).segments
            for c in (s.metadata.get("revision") or {}).get("changes", ())]


def _ours(data: bytes) -> list[tuple[str, str]]:
    """Our changes in the XML: (kind, text) for each w:ins / w:del by us."""
    root = _xml(data)
    return [(el.tag.rsplit("}", 1)[1], "".join(el.itertext()))
            for el in root.iter(f"{{{NS['w']}}}ins", f"{{{NS['w']}}}del")
            if el.get(f"{{{NS['w']}}}author") == "LeapSwitch Legal"
            and el.getparent().tag != f"{{{NS['w']}}}rPr"]


def test_a_replacement_is_exactly_the_changed_words():
    before = _doc("Clause A text.", "Clause B is payable in thirty days.", "Clause C text.")
    after = apply_reply(before, [ReplyEdit("Clause B is payable in thirty days.",
                                           "Clause B is payable in sixty days.")], when=WHEN)
    assert _ours(after) == [("del", "thirty"), ("ins", "sixty")]
    assert _changes(after) == [{"deleted": "thirty", "inserted": "sixty"}]
    old, new = _paragraphs(before), _paragraphs(after)
    assert (old[0], old[2]) == (new[0], new[2])        # untouched: byte-identical XML
    change = _xml(after).find(".//w:del", NS)
    assert change.get(f"{{{NS['w']}}}date") == "2026-11-02T09:30:00Z"
    assert [p.text for p in docx.Document(io.BytesIO(after)).paragraphs] == [
        "Clause A text.", "Clause B is payable in  days.", "Clause C text."]  # w:ins skipped


def test_the_split_text_keeps_its_formatting():
    d = docx.Document()
    p = d.add_paragraph("Clause D ")
    p.add_run("has bold words here").bold = True
    buffer = io.BytesIO()
    d.save(buffer)
    after = apply_reply(buffer.getvalue(), [ReplyEdit(
        "Clause D has bold words here", "Clause D has bold terms here")], when=WHEN)
    root = _xml(after)
    for change in [*root.iterfind(".//w:ins", NS), *root.iterfind(".//w:del", NS)]:
        assert change.find("w:r/w:rPr/w:b", NS) is not None
    bold_runs = [r for r in root.iterfind(".//w:p/w:r", NS)
                 if r.find("w:rPr/w:b", NS) is not None]
    assert ["".join(r.itertext()) for r in bold_runs] == ["has bold ", " here"]
    assert _changes(after) == [{"deleted": "words", "inserted": "terms"}]


def test_a_paragraph_in_a_table():
    before = _doc("Clause A text.", table=("Cell one text", "Cell two old words"))
    after = apply_reply(before, [ReplyEdit("Cell two old words", "Cell two new words")],
                        when=WHEN)
    assert _ours(after) == [("del", "old"), ("ins", "new")]
    assert _changes(after) == [{"deleted": "old", "inserted": "new"}]


def test_delete_and_reinsert_a_paragraph():
    before = _doc("Clause A text.", "Clause B to remove.", "Clause C text.")
    after = apply_reply(before, [
        ReplyEdit("Clause B to remove.", None),
        ReplyEdit("Clause C text.", "Clause D restored.", insert_after_anchor=True),
    ], when=WHEN)
    assert _ours(after) == [("del", "Clause B to remove."), ("ins", "Clause D restored.")]
    root = _xml(after)
    marks = root.findall(".//w:pPr/w:rPr/*", NS)
    assert [m.tag.rsplit("}", 1)[1] for m in marks] == ["del", "ins"]  # paragraph marks
    assert _changes(after) == [{"deleted": "Clause B to remove.", "inserted": ""},
                               {"deleted": "", "inserted": "Clause D restored."}]
    assert [s.content for s in parse_docx(after).segments] == [
        "Clause A text.", "Clause C text.", "Clause D restored."]


def test_an_anchor_is_located_exactly_once_or_refused():
    before = _doc("Clause A same.", "Clause A same.", "Clause C text.")
    with pytest.raises(ReplyError) as ambiguous:
        apply_reply(before, [ReplyEdit("Clause A same.", "Clause A new.")], when=WHEN)
    assert ambiguous.value.code == "ANCHOR_AMBIGUOUS"
    with pytest.raises(ReplyError) as missing:
        apply_reply(before, [ReplyEdit("Clause Z", "x", index_hint=2)], when=WHEN)
    assert missing.value.code == "ANCHOR_NOT_FOUND"    # a hint never locates alone
    with pytest.raises(ReplyError) as twice:
        apply_reply(before, [ReplyEdit("Clause C text.", "a"),
                             ReplyEdit("Clause C text.", "b")], when=WHEN)
    assert twice.value.code == "CONFLICTING_EDITS"
    after = apply_reply(before, [ReplyEdit("Clause A same.", "Clause A new.",
                                           index_hint=1)], when=WHEN)
    old, new = _paragraphs(before), _paragraphs(after)
    assert old[0] == new[0] and old[1] != new[1]


def test_the_clients_tracked_changes_stay_and_ours_restore_our_wording():
    before = _doc("Clause A text.", raw=(CLIENT_MARKED,
                                         CLIENT_MARKED.replace("Clause E", "Clause F")
                                         .replace('"90', '"80')))
    after = apply_reply(before, [ReplyEdit("Clause E payable in fifteen (15) days.",
                                           "Clause E payable in thirty (30) days.")],
                        when=WHEN)
    root = _xml(after)
    theirs = [el for el in root.iter(f"{{{NS['w']}}}ins", f"{{{NS['w']}}}del")
              if el.get(f"{{{NS['w']}}}author") == "Client"]
    # theirs all kept: F's two, E's deletion, and E's insertion split in three where
    # our "thirty" and "30" are lifted out of it (a w:ins never nests)
    assert len(theirs) == 6
    assert _paragraphs(before)[-1] == _paragraphs(after)[-1]      # Clause F untouched
    segments = parse_docx(after).segments
    assert segments[1].content == "Clause E payable in thirty (30) days."
    assert segments[1].metadata["revision"]["original"] == (
        "Clause E payable in thirty (30) days.")
    ids = [el.get(f"{{{NS['w']}}}id") for el in root.iter(
        f"{{{NS['w']}}}ins", f"{{{NS['w']}}}del")]
    assert len(ids) == len(set(ids))
    # no w:ins nests in another
    assert not root.findall(".//w:ins//w:ins", NS)


def test_round_trip_reads_back_exactly_our_changes_and_is_deterministic():
    before = _doc("Clause A one two three.", "Clause B alpha beta.", "Clause C keep.",
                  "Clause D drop me.", table=("Cell X red", "Cell Y"))
    edits = [ReplyEdit("Clause A one two three.", "Clause A one 2 three four."),
             ReplyEdit("Clause B alpha beta.", "New start Clause B alpha beta."),
             ReplyEdit("Clause D drop me.", None),
             ReplyEdit("Clause C keep.", "Clause E back.", insert_after_anchor=True),
             ReplyEdit("Cell X red", "Cell X blue")]
    after = apply_reply(before, edits, when=WHEN)
    assert _changes(before) == []
    assert _changes(after) == [
        {"deleted": "two", "inserted": "2"},
        {"deleted": "", "inserted": "four"},
        {"deleted": "", "inserted": "New start"},
        {"deleted": "", "inserted": "Clause E back."},
        {"deleted": "Clause D drop me.", "inserted": ""},
        {"deleted": "red", "inserted": "blue"}]
    assert [s.content for s in parse_docx(after).segments] == [
        "Clause A one 2 three four.", "New start Clause B alpha beta.", "Clause C keep.",
        "Clause E back.", "| Cell X blue | Cell Y |"]
    again = apply_reply(before, edits, when=WHEN)
    with zipfile.ZipFile(io.BytesIO(after)) as a, zipfile.ZipFile(io.BytesIO(again)) as b:
        assert a.read("word/document.xml") == b.read("word/document.xml")
    docx.Document(io.BytesIO(after))                       # opens


@pytest.mark.skipif(not os.environ.get("LEGALMIND_SOFFICE"),
                    reason="LEGALMIND_SOFFICE is not set: no LibreOffice here")
def test_libreoffice_converts_the_reply(tmp_path):  # pragma: no cover
    after = apply_reply(_doc("Clause A old."), [ReplyEdit("Clause A old.", "Clause A new.")],
                        when=WHEN)
    (tmp_path / "reply.docx").write_bytes(after)
    subprocess.run([os.environ["LEGALMIND_SOFFICE"], "--headless", "--convert-to", "pdf", "--outdir",
                    str(tmp_path), str(tmp_path / "reply.docx")], check=True, timeout=120)
    assert (tmp_path / "reply.pdf").stat().st_size > 0

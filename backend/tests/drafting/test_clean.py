"""The clean copy: every revision accepted and every comment removed, in every story."""

import io
import re
import zipfile
from datetime import UTC, datetime

import docx
from docx.oxml import parse_xml
from lxml import etree

from legalmind.drafting import clean
from legalmind.drafting.reply_docx import ReplyEdit, ReplyNote, apply_reply
from legalmind.ingestion.parsing import parse_docx

WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'w:author="Client" w:date="2026-10-01T00:00:00Z"'
BODY = [
    # inserted and deleted runs, a deleted field code
    f'<w:p {WNS}><w:r><w:t xml:space="preserve">Run kept </w:t></w:r>'
    f'<w:del w:id="1" {A}><w:r><w:delText>run deleted</w:delText></w:r>'
    f'<w:r><w:delInstrText> PAGE </w:delInstrText></w:r></w:del>'
    f'<w:ins w:id="2" {A}><w:r><w:t>run inserted</w:t></w:r></w:ins></w:p>',
    # a move, with its range markers
    f'<w:p {WNS}><w:moveFromRangeStart w:id="3" w:name="m1" {A}/><w:moveFrom w:id="4" {A}>'
    f'<w:r><w:t>moved away</w:t></w:r></w:moveFrom><w:moveFromRangeEnd w:id="3"/>'
    f'<w:moveToRangeStart w:id="5" w:name="m1" {A}/><w:moveTo w:id="6" {A}><w:r>'
    f'<w:t>moved here</w:t></w:r></w:moveTo><w:moveToRangeEnd w:id="5"/></w:p>',
    # a deleted paragraph mark: this paragraph joins the next
    f'<w:p {WNS}><w:pPr><w:rPr><w:del w:id="7" {A}/></w:rPr></w:pPr>'
    f'<w:r><w:t xml:space="preserve">Joined first half </w:t></w:r></w:p>',
    f'<w:p {WNS}><w:r><w:t>and second half.</w:t></w:r></w:p>',
    # an inserted paragraph mark, property changes, numbering change, customXml markers
    f'<w:p {WNS}><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/>'
    f'<w:numberingChange w:id="8" {A} w:original="%1."/></w:numPr>'
    f'<w:rPr><w:ins w:id="9" {A}/></w:rPr><w:pPrChange w:id="10" {A}><w:pPr/></w:pPrChange>'
    f'</w:pPr><w:customXmlInsRangeStart w:id="11" {A}/><w:r><w:rPr><w:b/>'
    f'<w:rPrChange w:id="12" {A}><w:rPr/></w:rPrChange></w:rPr><w:t>Formatted.</w:t></w:r>'
    f'<w:customXmlInsRangeEnd w:id="11"/></w:p>',
    # a table: deleted row, inserted row, deleted cell, inserted cell, merged cell
    f'<w:tbl {WNS}><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblPrChange w:id="13" {A}>'
    f'<w:tblPr/></w:tblPrChange></w:tblPr><w:tblGrid><w:gridCol w:w="2000"/>'
    f'<w:gridCol w:w="2000"/><w:tblGridChange w:id="14"><w:tblGrid/></w:tblGridChange>'
    f'</w:tblGrid>'
    f'<w:tr><w:trPr><w:del w:id="15" {A}/></w:trPr><w:tc><w:p><w:r><w:t>row deleted</w:t>'
    f'</w:r></w:p></w:tc><w:tc><w:p/></w:tc></w:tr>'
    f'<w:tr><w:trPr><w:ins w:id="16" {A}/><w:trPrChange w:id="17" {A}><w:trPr/>'
    f'</w:trPrChange></w:trPr><w:tc><w:tcPr><w:cellIns w:id="18" {A}/></w:tcPr><w:p><w:r>'
    f'<w:t>row inserted</w:t></w:r></w:p></w:tc><w:tc><w:tcPr><w:cellDel w:id="19" {A}/>'
    f'</w:tcPr><w:p><w:r><w:t>cell deleted</w:t></w:r></w:p></w:tc></w:tr>'
    f'<w:tr><w:tc><w:tcPr><w:cellMerge w:id="20" {A} w:vMerge="rest"/>'
    f'<w:tcPrChange w:id="21" {A}><w:tcPr/></w:tcPrChange></w:tcPr><w:p><w:r>'
    f'<w:t>merged</w:t></w:r></w:p></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>',
]
FOOTNOTES = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes {WNS}>'
    f'<w:footnote w:id="1"><w:p><w:ins w:id="30" {A}><w:r><w:t>note inserted</w:t></w:r>'
    f'</w:ins><w:del w:id="31" {A}><w:r><w:delText>note deleted</w:delText></w:r></w:del>'
    f'</w:p></w:footnote></w:footnotes>')


def _tracked_docx() -> bytes:
    d = docx.Document()
    body = d.element.body
    for xml in BODY:
        body.insert(len(body) - 1, parse_xml(xml))
    header = d.sections[0].header.paragraphs[0]._p
    header.append(parse_xml(f'<w:ins {WNS} w:id="40" {A}><w:r><w:t>head inserted</w:t>'
                            f'</w:r></w:ins>'))
    header.append(parse_xml(f'<w:del {WNS} w:id="41" {A}><w:r><w:delText>head deleted'
                            f'</w:delText></w:r></w:del>'))
    d.settings.element.append(parse_xml(f'<w:trackRevisions {WNS}/>'))
    out = io.BytesIO()
    d.save(out)
    # a footnotes part (python-docx writes none) — related, typed and tracked
    src, dst = zipfile.ZipFile(io.BytesIO(out.getvalue())), io.BytesIO()
    with zipfile.ZipFile(dst, "w") as z:
        for name in src.namelist():
            data = src.read(name)
            if name == "[Content_Types].xml":
                data = data.replace(b"</Types>", b'<Override PartName="/word/footnotes.xml" '
                                    b'ContentType="application/vnd.openxmlformats-officedocument'
                                    b'.wordprocessingml.footnotes+xml"/></Types>')
            if name == "word/_rels/document.xml.rels":
                data = data.replace(b"</Relationships>", b'<Relationship Id="rIdFn" Type="'
                                    b'http://schemas.openxmlformats.org/officeDocument/2006/'
                                    b'relationships/footnotes" Target="footnotes.xml"/>'
                                    b'</Relationships>')
            z.writestr(name, data)
        z.writestr("word/footnotes.xml", FOOTNOTES)
    # and real tracked changes and a Word comment, written by our own reply writer
    return apply_reply(dst.getvalue(), [ReplyEdit("and second half.", "and our half.")],
                       when=datetime(2026, 11, 3, tzinfo=UTC),
                       notes=[ReplyNote("Run kept run inserted", "Placeholder comment.")])


def _all_xml(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    return "".join(z.read(n).decode() for n in z.namelist() if n.endswith((".xml", ".rels")))


def test_every_revision_kind_is_present_before():
    found = {m.split(": ")[1] for m in clean.has_markup(_tracked_docx())}
    assert {"ins", "del", "moveFrom", "moveTo", "delText", "delInstrText", "cellIns",
            "cellDel", "cellMerge", "rPrChange", "pPrChange", "tblPrChange", "trPrChange",
            "tcPrChange", "tblGridChange", "numberingChange", "customXmlInsRangeStart",
            "moveFromRangeStart", "commentRangeStart", "commentReference", "comments part",
            "trackRevisions"} <= found


def test_the_clean_copy_has_no_revision_or_comment_in_any_part():
    out = clean.clean(_tracked_docx())
    assert clean.has_markup(out) == []
    xml = _all_xml(out)
    for local in clean.MARKUP:
        assert not re.search(rf"<w:{local}[\s/>]", xml), local
    assert "trackRevisions" not in xml
    z = zipfile.ZipFile(io.BytesIO(out))
    assert not [n for n in z.namelist() if "comments" in n]
    for name in ("[Content_Types].xml", "word/_rels/document.xml.rels"):
        assert b"comments" not in z.read(name), name


def test_accepted_text_is_what_word_shows():
    out = clean.clean(_tracked_docx())
    texts = [s.content for s in parse_docx(out).segments]
    joined = "\n".join(texts)
    assert "Run kept run inserted" in texts
    assert "moved here" in texts and "moved away" not in joined
    assert "Joined first half and our half." in texts          # mark merged, our edit in
    assert "row deleted" not in joined and "cell deleted" not in joined
    assert "row inserted" in joined and "merged" in joined
    assert "head inserted" in joined and "head deleted" not in joined
    z = zipfile.ZipFile(io.BytesIO(out))
    notes = z.read("word/footnotes.xml").decode()
    assert "note inserted" in notes and "note deleted" not in notes
    root = etree.fromstring(z.read("word/document.xml"))
    merge = root.find(".//{*}vMerge")
    assert merge is not None and merge.get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "restart"


def test_a_clean_document_passes_through_unchanged_in_text(rendered):
    out = clean.clean(rendered[2])
    assert clean.has_markup(out) == []
    assert [s.content for s in parse_docx(out).segments] == [
        s.content for s in parse_docx(rendered[2]).segments]

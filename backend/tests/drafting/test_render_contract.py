"""The model → DOCX on the house shell: Word-native numbering, REF fields with correct
cached numbers, sections, content controls, embedded images, determinism."""

import io
import re
import zipfile

import docx
import pytest

from legalmind.drafting import library, preflight, render_contract
from legalmind.ingestion.parsing import parse_docx
from tests.drafting.conftest import build

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _part(data, name):
    return zipfile.ZipFile(io.BytesIO(data)).read(name).decode()


def test_the_parser_reads_back_the_model_numbers(rendered):
    model, _, data = rendered
    numbered = {s.content: s.section_number for s in parse_docx(data).segments
                if s.section_number}
    assert numbered["Clause A Heading"] == "2"
    assert numbered["Clause A.1.1.1.1 text (level five)."] == "2.1.1.1.1"
    assert numbered["Schedule A Paragraph Two"] == "2"           # restarted by w:num
    assert preflight._numbering(data, model) == []


def test_numbering_is_style_linked_and_restarts_by_override(rendered):
    numbering = _part(rendered[2], "word/numbering.xml")
    assert '<w:pStyle w:val="LMHeading1"/>' in numbering
    assert numbering.count("<w:startOverride w:val=\"1\"/>") >= 3   # 2 schedules + lists
    styles = _part(rendered[2], "word/styles.xml")
    assert re.search(r'w:styleId="LMHeading1".*?<w:numId w:val="1"/>', styles, re.S)


def test_ref_fields_carry_the_computed_number(rendered):
    model, _, data = rendered
    document = _part(data, "word/document.xml")
    refs = dict(re.findall(r'w:instr=" REF (_LM_\w+) \\w \\h "><w:r><w:t>([^<]+)<', document))
    assert refs["_LM_CLAUSE_A_1"] == model["numbers"]["CLAUSE_A_1"] == "2.1"
    assert refs["_LM_SCHEDULE_A_2"] == "2"
    assert '<w:bookmarkStart w:id="' in document and 'w:name="_LM_CLAUSE_A_1"' in document
    settings = _part(data, "word/settings.xml")
    assert "updateFields" not in settings
    assert 'w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="14"' in settings


def test_sections_content_controls_and_furniture(rendered):
    model, digest, data = rendered
    d = docx.Document(io.BytesIO(data))
    assert len(d.sections) == 3                                   # main + two schedules
    assert all(s._sectPr.find(f"{W}pgNumType") is not None for s in d.sections[1:])
    tags = [t.get(f"{W}val") for t in d.element.body.iter(f"{W}tag")]
    assert "lm:CLAUSE_A@1" in tags and "lm:execution" in tags and "lm:parties" in tags
    ids = [i.get(f"{W}val") for i in d.element.body.iter(f"{W}id")]
    assert len(ids) == len(set(ids))
    assert all(len(t) <= 64 for t in tags)
    assert d.element.body.find(f".//{W}sdtPr/{W}lock").get(f"{W}val") == "sdtContentLocked"
    footer = d.sections[1].footer._element.xml
    assert f"LM-TEST-v1-{digest[:8]}" in footer and 'w:instr=" PAGE "' in footer
    core = _part(data, "docProps/core.xml")
    assert "LegalMind" in core and "2001-01-01" in core


def test_logo_table_and_image_are_embedded_with_alt_text(rendered):
    _, _, data = rendered
    z = zipfile.ZipFile(io.BytesIO(data))
    assert sum(n.startswith("word/media/") for n in z.namelist()) == 2
    header = next(z.read(n).decode() for n in z.namelist() if n.startswith("word/header"))
    assert 'descr="Placeholder logo"' in header
    document = z.read("word/document.xml").decode()
    assert 'descr="Placeholder figure: three boxes joined by lines"' in document
    assert "<w:tblHeader/>" in document and "<w:cantSplit/>" in document
    assert 'TargetMode="External"' not in "".join(
        z.read(n).decode() for n in z.namelist() if n.endswith(".rels"))
    ids = re.findall(r'<wp:docPr id="(\d+)"', "".join(
        z.read(n).decode() for n in z.namelist() if n.endswith(".xml")))
    assert len(ids) == len(set(ids)) == 4             # a logo per section header + the figure


def test_same_model_same_bytes(placeholder, answers):
    a, b = build(*placeholder, answers), build(*placeholder, answers)
    assert a[1] == b[1] and a[2] == b[2]
    assert {i.date_time for i in zipfile.ZipFile(io.BytesIO(a[2])).infolist()} == {
        (1980, 1, 1, 0, 0, 0)}


def test_the_rendered_file_passes_preflight(rendered):
    model, _, data = rendered
    assert preflight.check(data, model=model) == []


def test_annexure_appended_unchanged(rendered):
    annex = docx.Document()
    annex.add_paragraph("Annexure placeholder paragraph.")
    annex.add_table(rows=1, cols=2).rows[0].cells[0].text = "Annexure cell"
    buf = io.BytesIO()
    annex.save(buf)
    out = render_contract.append_annexure(rendered[2], buf.getvalue(), "Annexure 1")
    texts = [s.content for s in parse_docx(out).segments]
    assert "Annexure placeholder paragraph." in texts and "Annexure 1" in texts


def test_annexure_with_images_is_refused_until_docxcompose(rendered):
    annex = docx.Document()
    annex.add_paragraph().add_run().add_picture(io.BytesIO(
        zipfile.ZipFile(io.BytesIO(rendered[2])).read("word/media/image1.png")))
    buf = io.BytesIO()
    annex.save(buf)
    with pytest.raises(render_contract.RenderError, match="docxcompose"):
        render_contract.append_annexure(rendered[2], buf.getvalue(), "Annexure 1")


def test_the_house_style_is_applied(rendered):
    """The approved MSA format's values (house.json) read back from the rendered file."""
    h = render_contract.house()
    d = docx.Document(io.BytesIO(rendered[2]))
    s, page = d.sections[0], h["page"]
    for side, mm in page["margin_mm"].items():
        assert abs(getattr(s, f"{side}_margin").mm - mm) < 0.1
    assert abs(s.header_distance.mm - page["header_mm"]) < 0.1
    assert round(s.page_width.mm) == page["width_mm"]
    normal = d.styles["Normal"]
    assert normal.font.name == h["font"] and normal.font.size.pt == h["font_size_pt"]
    fmt = normal.paragraph_format
    assert fmt.line_spacing == h["line_spacing"]
    assert [fmt.space_before.pt, fmt.space_after.pt] == h["spacing_pt"]["normal"]
    assert fmt.alignment == docx.enum.text.WD_ALIGN_PARAGRAPH.JUSTIFY
    heading = d.styles["LM Heading 1"]
    assert heading.font.bold and heading.font.all_caps
    assert [heading.paragraph_format.space_before.pt,
            heading.paragraph_format.space_after.pt] == h["spacing_pt"]["heading1"]
    # Round 6: no empty paragraph anywhere in the body; one ladder (no direct indents)
    body = d.element.body
    assert not [p for p in body.iter(f"{W}p") if not "".join(p.itertext()).strip()
                and p.getparent().tag != f"{W}tc" and p.find(f".//{W}drawing") is None
                and p.find(f"{W}pPr/{W}sectPr") is None]
    assert "lead_clauses" not in h
    numbering = _part(rendered[2], "word/numbering.xml")
    for i, (number, text) in enumerate(h["clause_ladder_twips"]):
        level = re.search(rf'<w:lvl w:ilvl="{i}">.*?</w:lvl>', numbering, re.S).group(0)
        assert f'w:left="{text}" w:hanging="{text - number}"' in level
        assert '<w:lvlJc w:val="right"/>' in level
    assert '<w:lvlText w:val="%1.%2.%3."/>' in numbering
    document = _part(rendered[2], "word/document.xml")
    assert f'w:fill="{h["table"]["header_fill"]}"' in document
    assert f'w:color="{h["table"]["border"]}"' in document


def test_front_matter_and_numbered_definitions_as_the_approved_format(placeholder,
                                                                      answers):
    """Synthetic words only: lettered parties with the incorporation after the bold name,
    a bold connector, the parties' closing sentence, a recitals label, the bold run-in
    of the operative words and of the execution lead, a numbered definition's term bold,
    and the paired By / Sign table."""
    template, clauses = placeholder
    layout = template["layout"]
    layout["parties"][0]["incorporation"] = ("a placeholder company, hereinafter "
                                             "referred to as “Party One”")
    layout.update(connector="AND", recitals_label="WHEREAS",
                  parties_close="Together referred to as the “Placeholder Parties”.",
                  operative="NOW THEREFORE, the placeholder parties agree:")
    layout["execution"]["lead"] = "IN WITNESS WHEREOF placeholder signatories sign."
    clauses[("DEFINITIONS", 1)]["body"] += [
        {"kind": "sub", "text": "“Placeholder Term Three” shall mean a placeholder."},
        {"kind": "sub", "title": "Placeholder Title:", "text": " placeholder words."}]
    body = clauses[("DEFINITIONS", 1)]["body"]           # the title survives an edit
    edited = library.parse_wording(library.wording(body, "1"), body)[-1]
    assert (edited["title"], edited["text"]) == ("Placeholder Title:", " placeholder words.")
    model, _, data = build(template, clauses, answers)
    d = docx.Document(io.BytesIO(data))
    paragraphs = [docx.text.paragraph.Paragraph(p, d) for p in d.element.body.iter(f"{W}p")]
    bold = {r.text for p in paragraphs for r in p.runs if r.bold}
    assert {"Placeholder Term Three", "Party One", "Placeholder Parties",
            "NOW THEREFORE,", "IN WITNESS WHEREOF"} <= bold
    assert next(p for p in paragraphs if p.text == "AND").style.font.bold
    assert {r.text for p in paragraphs for r in p.runs if r.underline} == {
        "Placeholder Title"}                          # never the colon (Round 6)
    texts = [p.text for p in paragraphs]
    assert "AND" in texts and "WHEREAS" in texts and "Parties" not in texts
    name = model["parties"][0]["name"][0]["t"]
    assert f"{name}, a placeholder company, hereinafter referred to as “Party One”" in texts
    table = docx.table.Table(list(d.element.body.iter(f"{W}tbl"))[-1], d)
    assert [c.text for c in table.rows[1].cells][::2] == ["By", "By"]
    assert table.rows[0].cells[0].text == "Signatory Details"
    labels = [r.cells[0].text for r in table.rows]
    assert {"Sign", "Name", "Signatory Email", "Date of sign"} <= set(labels)
    assert preflight._numbering(data, model) == []
    # the parser records the file's own weight, for the reading view (house_style too)
    read = {seg.content: seg.metadata for seg in parse_docx(data).segments}
    titled = read["Placeholder Title: placeholder words."]
    assert titled["style"] == "LM Heading 2" and titled["emphasis"] == [[0, 17, "u"]]
    party = read[f"{name}, a placeholder company, hereinafter referred to as “Party One”"]
    assert [name, "b"] == [f"{name}, a"[party["emphasis"][0][0]:party["emphasis"][0][1]],
                           party["emphasis"][0][2]]


def test_a_definition_with_its_short_form_in_brackets_bolds_both_terms():
    """MSA 1.17 (2026-11-04): “Service Level Agreement” (“SLA”) shall mean …"""
    runs = render_contract.emphasis([{"t": "“Service Level Agreement” (“SLA”) shall mean the SLA."}],
                    terms="defining")
    assert [r["t"] for r in runs if r.get("b")] == ["Service Level Agreement", "SLA"]

"""The clean copy — every tracked change accepted and every comment removed, in EVERY
story of the package (body, headers, footers, footnotes, endnotes; styles and numbering
too), as Word's "Accept All Changes" + "Delete All Comments" leaves it (ECMA-376 Part 1
§17.13; Microsoft Learn, "Accept all revisions").

Accepting:

* ``w:ins`` / ``w:moveTo`` — unwrapped (their runs stay); as a paragraph-mark or row
  marker (inside ``w:rPr`` / ``w:trPr``) the marker alone goes.
* ``w:del`` / ``w:moveFrom`` — removed with their content (``w:delText``,
  ``w:delInstrText``); a DELETED PARAGRAPH MARK (``w:pPr/w:rPr/w:del``) merges the
  paragraph's content into the next paragraph; a deleted row (``w:trPr/w:del``) goes
  with its row.
* ``w:cellIns`` accepted, ``w:cellDel`` removes its cell, ``w:cellMerge`` becomes the
  ``w:vMerge`` it proposed.
* every property change (``w:rPrChange`` ``w:pPrChange`` ``w:sectPrChange``
  ``w:tblPrChange`` ``w:tblPrExChange`` ``w:trPrChange`` ``w:tcPrChange``
  ``w:tblGridChange``) and ``w:numberingChange`` dropped — the current properties stand;
  move-range and customXml range markers removed.
* comments: ``w:commentRangeStart/End`` and the ``w:commentReference`` runs removed, the
  comments parts (comments, commentsExtended, commentsIds, commentsExtensible), their
  relationships and their content-type overrides removed. ``w:trackRevisions`` off.

`has_markup` is the test a clean copy must pass (preflight asserts it on the XML).
"""

from __future__ import annotations

import io
import re
import zipfile

from lxml import etree  # type: ignore[import-untyped]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_COMMENT_PARTS = re.compile(r"^word/comments(Extended|Ids|Extensible)?\.xml$")
_PROPERTY_CHANGES = ("rPrChange", "pPrChange", "sectPrChange", "tblPrChange",
                     "tblPrExChange", "trPrChange", "tcPrChange", "tblGridChange",
                     "numberingChange")
_MARKERS = ("moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart",
            "moveToRangeEnd",
            "customXmlInsRangeStart", "customXmlInsRangeEnd", "customXmlDelRangeStart",
            "customXmlDelRangeEnd", "customXmlMoveFromRangeStart",
            "customXmlMoveFromRangeEnd",
            "customXmlMoveToRangeStart", "customXmlMoveToRangeEnd", "commentRangeStart",
            "commentRangeEnd")
#: what follows w:vMerge in w:tcPr (ECMA-376 schema order)
_AFTER_VMERGE = {"tcBorders", "shd", "noWrap", "tcMar", "textDirection", "tcFitText",
                 "vAlign", "hideMark", "headers", "cellIns", "cellDel"}
#: every element a clean copy may not contain
MARKUP = ("ins", "del", "moveFrom", "moveTo", "delText", "delInstrText", "cellIns",
          "cellDel", "cellMerge", "commentReference", *_PROPERTY_CHANGES, *_MARKERS)


def _drop(el: etree._Element) -> None:
    el.getparent().remove(el)


def _unwrap(el: etree._Element) -> None:
    parent = el.getparent()
    i = parent.index(el)
    for child in reversed(list(el)):
        parent.insert(i, child)
    parent.remove(el)


def _all(root: etree._Element, *names: str) -> list[etree._Element]:
    return [el for name in names for el in root.iter(_W + name)]


def accept(root: etree._Element) -> None:
    """Accept every revision in one XML part, in place."""
    for el in _all(root, *_PROPERTY_CHANGES, *_MARKERS):
        _drop(el)
    for r in [ref.getparent() for ref in _all(root, "commentReference")]:
        _drop(r)
    for row_mark in [el for el in _all(root, "del") if el.getparent().tag == _W + "trPr"]:
        _drop(row_mark.getparent().getparent())             # the deleted row
    for mark in [el for el in _all(root, "del", "moveFrom") if el.getparent().tag ==
                 _W + "rPr" and el.getparent().getparent().tag == _W + "pPr"]:
        _merge_deleted_mark(mark)
    for el in _all(root, "del", "moveFrom"):
        if el.getparent() is not None:      # not inside content already removed
            _drop(el)
    for el in _all(root, "delText", "delInstrText"):
        _drop(el)
    for el in _all(root, "ins", "moveTo"):
        if el.getparent().tag in (_W + "rPr", _W + "trPr"):
            _drop(el)
        else:
            _unwrap(el)
    for el in _all(root, "cellIns"):
        _drop(el)
    for el in _all(root, "cellDel"):
        tc = el.getparent().getparent()
        _drop(tc)
    for el in _all(root, "cellMerge"):
        tcpr = el.getparent()
        _drop(el)
        for old in tcpr.findall(_W + "vMerge"):
            _drop(old)
        merge = etree.Element(_W + "vMerge")
        if el.get(_W + "vMerge") == "rest":
            merge.set(_W + "val", "restart")
        after = next((c for c in tcpr if etree.QName(c).localname in _AFTER_VMERGE), None)
        if after is not None:
            after.addprevious(merge)
        else:
            tcpr.append(merge)


def _merge_deleted_mark(mark: etree._Element) -> None:
    """A paragraph whose mark was deleted joins the paragraph after it."""
    p = mark.getparent().getparent().getparent()
    _drop(mark)
    after = p.getnext()
    if after is None or after.tag != _W + "p":
        return                       # the last paragraph of its story keeps its mark
    content = [c for c in p if c.tag != _W + "pPr"]
    anchor = after.find(_W + "pPr")
    for child in reversed(content):
        if anchor is not None:
            anchor.addnext(child)
        else:
            after.insert(0, child)
    _drop(p)


def has_markup(docx_bytes: bytes) -> list[str]:
    """Every revision or comment element left in any part, as ``part: tag`` — empty for
    a clean copy. Comment PARTS count too."""
    found = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        for name in z.namelist():
            if _COMMENT_PARTS.match(name):
                found.append(f"{name}: comments part")
                continue
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            root = etree.fromstring(z.read(name))
            tags = {etree.QName(el).localname for el in _all(root, *MARKUP)}
            if any(el.get(_W + "val") not in ("0", "false")
                   for el in root.iter(_W + "trackRevisions")):
                tags.add("trackRevisions")
            found += [f"{name}: {t}" for t in sorted(tags)]
    return found


def clean(docx_bytes: bytes) -> bytes:
    """The clean copy of a DOCX."""
    src = zipfile.ZipFile(io.BytesIO(docx_bytes))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            name = info.filename
            if _COMMENT_PARTS.match(name):
                continue
            data = src.read(name)
            if name == "[Content_Types].xml":
                data = re.sub(rb'<Override [^>]*PartName="/word/comments[A-Za-z]*\.xml"'
                              rb'[^>]*/>', b"", data)
            elif name == "word/_rels/document.xml.rels":
                data = re.sub(rb'<Relationship [^>]*Target="comments[A-Za-z]*\.xml"'
                              rb'[^>]*/>', b"", data)
            elif name.startswith("word/") and name.endswith(".xml"):
                root = etree.fromstring(data)
                accept(root)
                for el in root.iter(_W + "trackRevisions"):
                    _drop(el)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                      standalone=True)
            dst.writestr(info, data)
    return out.getvalue()

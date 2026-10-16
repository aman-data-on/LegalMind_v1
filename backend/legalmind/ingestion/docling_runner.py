"""Read one PDF's TABLES with Docling and write neutral JSON — run in Docling's OWN env.

    <docling python> -I docling_runner.py <in.pdf> <out.json> <artifacts_dir> <langs>

Standalone on purpose: stdlib and docling only, never a legalmind import. The API
never imports Docling (its models would share the API's memory limit);
`parsing._docling_read` runs this file as a separate process and falls back to the
standard parser on any failure. Offline: models come from ``artifacts_dir`` and the
caller sets HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE (AM-30 — Gemini is the only egress).

Tables only (2026-10-15): prose is always the standard parser's, so this writes no text.
Output: {"docling_version": str, "pages": {"<page_no>": [table, ...]}} where a table is
    {"bbox": [x0, y0, x1, y1], "rows": [[text, ...], ...],
     "cells": [{"text": str, "bbox": [x0, y0, x1, y1]}, ...]}
with every bbox in PyMuPDF's top-left page coordinates and ``cells`` each cell ONCE (a
label ``rows`` carries down a vertical span is one cell) — what the caller's character
and geometry checks read. A table with a cell Docling gave no box is not written: the
caller could not check it.
"""

import json
import sys
from importlib.metadata import version


def _rows(table) -> list[list[str]]:
    """The grid with a horizontally spanned cell's text ONCE (its first column, ''
    after), and a vertically spanned cell's text on every row it spans — the rule the
    PyMuPDF path (`parsing._table_rows`) and the DOCX path (`_docx_rows`) follow."""
    return [["" if j > cell.start_col_offset_idx else cell.text
             for j, cell in enumerate(row)] for row in table.data.grid]


def _box(bbox, height: float) -> list[float]:
    box = bbox.to_top_left_origin(height)
    return [round(v, 2) for v in (box.l, box.t, box.r, box.b)]


def main(src: str, out: str, artifacts: str, langs: str) -> None:
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        artifacts_path=artifacts, do_table_structure=True, do_ocr=True,
        ocr_options=TesseractCliOcrOptions(lang=langs.split("+"),
                                           force_full_page_ocr=False),
        accelerator_options=AcceleratorOptions(num_threads=2, device="cpu"))
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    doc = converter.convert(src).document

    pages: dict[str, list[dict]] = {}
    for table in doc.tables:
        cells = table.data.table_cells
        if not table.prov or any(cell.bbox is None for cell in cells):
            continue
        prov = table.prov[0]
        height = doc.pages[prov.page_no].size.height
        pages.setdefault(str(prov.page_no), []).append(
            {"bbox": _box(prov.bbox, height), "rows": _rows(table),
             "cells": [{"text": cell.text, "bbox": _box(cell.bbox, height)}
                       for cell in cells]})

    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"docling_version": version("docling"), "pages": pages}, fh,
                  ensure_ascii=False)


if __name__ == "__main__":
    main(*sys.argv[1:5])

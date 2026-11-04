"""A reading copy of our reply as PDF (R6, `AM-251` r1): the reply's text with every
tracked change accepted — the parser's own accepted view (`parse_docx`) — laid out by
the report's PyMuPDF Story path (`export_render`). The Word file is the reply; this is
labelled, at the top of the first page and on every page, as a copy to read.
"""

from __future__ import annotations

import io

from legalmind.api.export_render import _PDF_CSS, Block, _blocks_to_html
from legalmind.ingestion.parsing import parse_docx

_LABEL = "Reading copy · every tracked change shown accepted · the Word file is the reply"


def render_reply_pdf(docx_bytes: bytes) -> bytes:
    import pymupdf

    blocks = [Block("h1", "Reading copy of our reply"),
              Block("note", "This copy shows the text as it reads with every tracked "
                            "change accepted. The changes themselves are in the Word "
                            "file, which is the reply.")]
    for segment in parse_docx(docx_bytes).segments:
        blocks += [Block("p", line) for line in segment.content.split("\n")]
    # ponytail: the Story loop of `render_pdf`, without its "internal legal review"
    # frame — a reply goes to the client. Parametrize `render_pdf`'s frame to share it.
    story = pymupdf.Story(html=_blocks_to_html(blocks), user_css=_PDF_CSS)
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page_rect = pymupdf.paper_rect("a4")
    content_rect = page_rect + (36, 40, -36, -40)  # noqa: RUF005 — pymupdf inset
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()
    pdf = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    total = pdf.page_count
    for index in range(total):
        pdf[index].insert_text((36, 24), f"{_LABEL} · Page {index + 1} of {total}",
                               fontsize=7.5, color=(0.35, 0.35, 0.35))
    out = pdf.tobytes()
    pdf.close()
    return out

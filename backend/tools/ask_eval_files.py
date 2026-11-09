"""Synthetic chat files for the Ask conversation cases (lawyer batch 1, N01-N08).

Each is generated, never read from disk: company-neutral text written for the test, no
client or person named (54.6, rule 21). A case names a file by key in a turn's "files";
`tools.ask_conversation_eval` attaches it through the API's own path (`extract_material`
then `attachments.add`) before the turn is asked.
"""
from __future__ import annotations

import pymupdf

PNG_MIME = "image/png"
PDF_MIME = "application/pdf"
TEXT_MIME = "text/plain"

_CAP = ("17.2 Limitation of Liability. The aggregate liability of the Provider shall not "
        "exceed the fees paid by the Customer in the six (6) months preceding the claim.")


def _png_clause() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=300)
    page.insert_textbox(pymupdf.Rect(20, 20, 580, 280), _CAP, fontsize=13)
    return page.get_pixmap(dpi=150).tobytes("png")


def _logo_pdf() -> bytes:
    """Three pages of an order form with a logo on page 1 and a picture where a signature
    would be on page 3 — the text says nothing about being signed."""
    doc = pymupdf.open()
    tile = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    tile.clear_with(90)
    clauses = ["1. Order. The Customer orders dedicated servers for twelve (12) months.",
               "2. Fees. Fees are payable monthly in advance within twenty-one (21) days "
               "of the invoice date.",
               "3. Signatures. For the Provider: ____________  For the Customer: "
               "____________"]
    for text in clauses:
        page = doc.new_page(width=600, height=800)
        page.insert_textbox(pymupdf.Rect(40, 200, 560, 600), text, fontsize=12)
    doc[0].insert_image(pymupdf.Rect(40, 20, 190, 180), pixmap=tile)
    doc[2].insert_image(pymupdf.Rect(380, 640, 540, 780), pixmap=tile)
    return doc.tobytes()


def _pages18() -> bytes:
    """About 70k characters of a services agreement with no liability clause at all."""
    topics = ["Services", "Fees", "Term", "Support", "Change requests", "Notices",
              "Assignment", "Subcontracting", "Records", "Reporting", "Security",
              "Personnel", "Acceptance", "Delivery", "Invoices", "Taxes", "Audit",
              "Governing law"]
    return "\n\n".join(
        f"{n}. {t}. " + (f"The parties shall perform their obligations under this clause "
                         f"{n} in good faith and as set out in the order form. ") * 30
        for n, t in enumerate(topics, 1)).encode()


def _msa_favour() -> bytes:
    """Our side is the provider; the payment period (7 days) is shorter than our 21."""
    doc = pymupdf.open()
    text = (
        "MASTER SERVICES AGREEMENT\n"
        "This Agreement is made between Leapswitch Networks Private Limited (hereinafter "
        "\"Service Provider\") and Client A Limited (hereinafter \"Customer\").\n"
        "1. Services. The Service Provider shall provide the cloud services in the order "
        "form.\n"
        "2. Payment. Customer shall pay all undisputed invoices within seven (7) days of "
        "the invoice date.\n"
        "3. Governing Law. This Agreement is governed by the laws of India and the courts "
        "at Mumbai shall have exclusive jurisdiction.\n"
        "4. Limitation of Liability. The total liability of the Service Provider shall not "
        "exceed the fees paid in the three (3) months preceding the claim.\n")
    page = doc.new_page(width=600, height=800)
    page.insert_textbox(pymupdf.Rect(40, 40, 560, 780), text, fontsize=11)
    return doc.tobytes()


#: key -> (filename, mime, bytes factory)
FILES = {
    "png_clause": ("clause-screenshot.png", PNG_MIME, _png_clause),
    "logo_pdf": ("order-form.pdf", PDF_MIME, _logo_pdf),
    "pages18": ("services-agreement.txt", TEXT_MIME, _pages18),
    "msa_favour": ("client-a-msa.pdf", PDF_MIME, _msa_favour),
}


def attach(db, conversation_id, key: str):
    """Attach one synthetic file the way the API does."""
    from legalmind.api.routers.assist import extract_material
    from legalmind.assist.agent import attachments
    name, mime, make = FILES[key]
    data = make()
    mime, extracted = extract_material(data, attachments.FILE, name, mime)
    return attachments.add(db, conversation_id=conversation_id, data=data,
                           kind=attachments.FILE, mime=mime, extracted=extracted,
                           filename=name)

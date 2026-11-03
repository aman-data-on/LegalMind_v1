"""G-1 step 1 — is this paper a contract at all? (classify-then-route, first layer).

All text here is synthetic (rule 21 concerns real legal material). The real-document
evaluation — every file in legal-docs and every production upload — is recorded in
the G-1 session report. Refusing a real contract is the worse error, so the deals
below that carry no contract structure must never come out NOT_A_CONTRACT.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from legalmind.domain.paper_kind import (
    CONTRACT_OR_POLICY,
    NOT_A_CONTRACT,
    UNSURE,
    classify_paper,
)


def _paper(*texts: str, numbered: bool = False):
    return [SimpleNamespace(content=t, section_number=str(i + 1) if numbered else None)
            for i, t in enumerate(texts)]


RESUME = (
    "Priya Sharma", "priya.sharma@example.com | +91 98xxxxxx10 | linkedin.com/in/priya",
    "Career Objective",
    "Seeking a backend engineering role where I can build reliable services.",
    "Education", "B.Tech, Computer Engineering, Pune University, 2019. CGPA 8.4",
    "Work Experience",
    "Software Engineer, Acme Tech (2019 - 2024): built billing APIs in Python and Go.",
    "Skills", "Python, Go, PostgreSQL, Kubernetes, Terraform",
    "Hobbies", "Trekking, chess")

INVOICE = (
    "TAX INVOICE", "Invoice No: INV-2026-0412   Invoice Date: 02-11-2026",
    "Bill To: Example Traders Pvt Ltd, Pune   GSTIN: 27AAAAA0000A1Z5",
    "Description | HSN/SAC | Qty | Rate | Amount",
    "Dedicated server rental, October | 998315 | 1 | 12,000.00 | 12,000.00",
    "Sub-total 12,000.00   CGST 9% 1,080.00   SGST 9% 1,080.00",
    "Grand Total 14,160.00", "Amount in words: Fourteen thousand one hundred sixty only",
    "Amount Due: 14,160.00 by 15-11-2026")

SLIDES = (
    "Q3 Product Review", "Agenda", "Highlights", "Revenue up 18%", "Three new regions",
    "Roadmap", "Mobile app beta", "Self-serve onboarding", "Hiring plan", "Questions?",
    "Thank you for joining the quarterly review this afternoon")

EMAIL = (
    "From: rohan@example.com", "To: team@example.com", "Subject: Friday lunch",
    "Hi all,",
    "We are planning a team lunch this Friday at the usual place around one o'clock. "
    "Let me know by Thursday evening if you can make it so I can book a table.",
    "Thanks,", "Rohan")

#: Real-world deals with no contract structure (independent review, 2026-11-02).
DEALS = {
    "email accepting a quotation": (
        "From: buyer@x.com", "To: sales@leapswitch.com",
        "Subject: Acceptance of quotation Q-114", "Dear Team,",
        "We confirm acceptance of your quotation Q-114 for 4 dedicated servers at "
        "Rs 48,000 per month for a period of 12 months starting 1 December 2026. "
        "Payment will be made within 30 days of invoice. Please proceed with "
        "provisioning.", "Regards,", "Rahul"),
    "purchase order without its title": (
        "ABC Pvt Ltd", "GSTIN: 27AAACA1234B1Z5", "PO No: 4500123 Date: 01-11-2026",
        "Bill To: ABC Pvt Ltd Pune", "Ship To: Mumbai DC",
        "Item: Dedicated server rental, 12 months", "Sub-total: 5,76,000",
        "CGST 9%: 51,840", "SGST 9%: 51,840", "Grand Total: 6,79,680",
        "Terms: Payment within 45 days of invoice. Vendor will deliver within 7 days. "
        "Late delivery attracts 1% per week penalty, capped at 10%. This order is "
        "subject to our general terms."),
    "statement of work with CV-like headings": (
        "Statement of Work - Resource Augmentation", "Skills:", "Java, Spring",
        "Experience:", "5 years", "Projects", "Migration of billing",
        "The Vendor will provide two engineers on site for 6 months at Rs 1,50,000 per "
        "resource per month. The Client will pay within 30 days. Either side may end "
        "this with 30 days notice."),
    "engagement details with CV-like headings and no title": (
        "Resource Augmentation - Engagement Details", "Skills:", "Java, Spring",
        "Experience:", "5 years", "Projects", "Migration of billing",
        "The Vendor will provide two engineers on site for 6 months at Rs 1,50,000 per "
        "resource per month. The Client will pay within 30 days. Either side may end "
        "this with 30 days notice."),
    "colocation letter agreement": (
        "Dear Mr Shah,", "Re: Colocation of 2 racks",
        "Further to our discussions, we are pleased to offer colocation of 2 racks at "
        "our Mumbai facility at Rs 90,000 per rack per month, for a minimum period of "
        "24 months. Fees are payable quarterly in advance. Please sign and return a "
        "copy of this letter to confirm your acceptance.",
        "Thanks and regards,", "For LeapSwitch Networks", "Accepted: ____ "),
    "OCR'd service order in short lines": (
        "LeapSwitch Networks Pvt Ltd", "Service Order", "Customer: ____",
        "Service: Cloud VM", "Term: 12 months", "Fee: Rs 20,000/month", "Signature",
        "Date", "Stamp"),
    "rate card table": (
        "Item", "Qty", "Rate", "Amount", "VM 4 vCPU", "10", "2000", "20000",
        "Sub-total", "20000", "IGST 18%", "3600", "Grand total", "23600",
        "Valid for 12 months from acceptance"),
}


@pytest.mark.parametrize("texts", [RESUME, INVOICE], ids=["resume", "invoice"])
def test_a_resume_or_an_invoice_is_not_a_contract(texts):
    result = classify_paper(_paper(*texts))
    assert result.kind == NOT_A_CONTRACT, result.signals
    assert result.signals                                  # the audit says why


@pytest.mark.parametrize("texts", [SLIDES, EMAIL], ids=["slides", "email"])
def test_an_email_or_a_slide_shape_alone_never_refuses(texts):
    # OCR lines and table cells look like slides; deals are agreed by email
    assert classify_paper(_paper(*texts)).kind == UNSURE


@pytest.mark.parametrize("texts", DEALS.values(), ids=DEALS.keys())
def test_a_deal_without_contract_structure_is_never_refused(texts):
    result = classify_paper(_paper(*texts))
    assert result.kind != NOT_A_CONTRACT, result.signals


@pytest.mark.parametrize("title", [
    "MASTER SERVICES AGREEMENT", "Terms of Service", "Service Level Agreement",
    "Acceptable Use Policy", "Privacy Policy", "Data Processing Addendum",
    "Purchase Order", "Memorandum of Understanding"])
def test_a_recognised_legal_title_is_always_in_domain(title):
    # even when the body carries invoice-looking lines: the title decides
    assert classify_paper(_paper(title, *INVOICE[1:])).kind == CONTRACT_OR_POLICY


def test_contract_structure_without_a_title_is_a_contract():
    paper = _paper(
        "This agreement is entered into by and between Alpha Ltd and Beta Ltd.",
        "WHEREAS Alpha provides hosting services;",
        "The Customer shall pay all fees within thirty days of invoice.",
        "The Provider shall not disclose Confidential Information.",
        "This agreement shall be governed by the laws of India.", numbered=True)
    assert classify_paper(paper).kind == CONTRACT_OR_POLICY


@pytest.mark.parametrize("line", [
    "Disputes are subject to arbitration in Pune.",          # one legal signal
    "Supply will continue at Rs 12,000 per month."])        # one commitment
def test_one_legal_or_commitment_signal_keeps_an_invoice_out_of_refusal(line):
    assert classify_paper(_paper(*INVOICE, line)).kind == UNSURE


def test_no_extractable_text_is_unsure_not_refused():
    assert classify_paper(_paper("", "Page 1")).kind == UNSURE
    assert classify_paper([]).kind == UNSURE


def test_the_same_paper_classifies_the_same_way():
    assert classify_paper(_paper(*RESUME)) == classify_paper(_paper(*RESUME))

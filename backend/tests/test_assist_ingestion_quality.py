"""Ask plan Phase 1D (2026-09-30) — what the retrieval index keeps from real-world paper.

Synthetic fixtures only, one per failure shape the plan names: a flattened credit
table, a web page printed with running header and footer, sub-clauses run together in
one paragraph, a page number at a page break, blank fields, an unsigned copy. Nothing
here asserts a legal conclusion (rule 21); each test is about which text lands in which
chunk. The evidence row is never altered (locked 34.12) — trimming happens only in the
derived index, and every chunk stays a span of its own row (the integrity gate).
"""
import uuid
from types import SimpleNamespace

import pytest

from legalmind.assist.ingestion.chunking import (
    chunk_evidence,
    integrity_failures,
    leading_section_ref,
)
from tests.test_assist_ask import indexed_contract, storage  # noqa: F401  (fixtures)

HEADER = "Example Cloud | Products | Pricing | Support | Login"
FOOTER = "(c) 2026 Example Cloud Pvt Ltd. All rights reserved. | Privacy | Terms"


def _rows(*pages: list[str]):
    """Evidence rows in document order, each carrying the page it was read from."""
    return [SimpleNamespace(id=uuid.uuid4(), content=text, start_offset=0,
                            end_offset=len(text), page_number=n)
            for n, texts in enumerate(pages, 1) for text in texts]


def _chunks(rows):
    chunks = chunk_evidence(rows)
    assert integrity_failures(rows, chunks) == []
    return [c.content for c in chunks]


WEB_PAGE = _rows(
    [f"{HEADER}\n7.1 Support is available by ticket at all times.",
     f"7.3 Critical incidents are acknowledged within fifteen minutes.\n{FOOTER}\nPage 1 of 5"],
    [f"{HEADER}\n7.4 Scheduled maintenance is announced seven days ahead.\n{FOOTER}\nPage 2 of 5"],
    [f"{HEADER}\n8.1 Fees are payable monthly in advance.\n{FOOTER}\nPage 3 of 5"],
    [f"{HEADER}\n8.2 Late fees accrue at the agreed rate.\n{FOOTER}\nPage 4 of 5"],
    [f"{HEADER}\n9.1 Either party may terminate on notice.\n{FOOTER}\nPage 5 of 5"])


def test_a_running_header_and_footer_never_reach_a_chunk():
    chunks = _chunks(WEB_PAGE)
    assert not any(HEADER in c or FOOTER in c or "Page 2 of 5" in c for c in chunks)
    assert "7.4 Scheduled maintenance is announced seven days ahead." in chunks


@pytest.mark.parametrize("pages", [2, 3, 4])
def test_a_short_contract_keeps_a_heading_repeated_atop_every_page(pages):
    # The minimum-page guard: in a two-to-four page contract a line at the top of
    # every page is likelier a heading than running text, so nothing is trimmed.
    heading = "SCHEDULE A - SERVICE LEVELS"
    rows = _rows(*[[f"{heading}\n{n}.1 The service level for item {n} is as stated."]
                   for n in range(1, pages + 1)])
    assert sum(heading in c for c in _chunks(rows)) == pages


def test_a_line_repeated_on_one_page_only_is_kept():
    rows = _rows([f"Note: fees are in INR.\n{n}. Clause {n} applies to this Order."
                  for n in (1, 2, 3)])
    assert sum("Note: fees are in INR." in c for c in _chunks(rows)) == 3


def test_a_heading_recurring_mid_page_on_every_page_is_content():
    # Measured on a supplied Act: "Illustrations" ends an inner row on most pages.
    rows = _rows(*[[f"{HEADER}\n{n}. A promise is a proposal accepted.",
                    f"{n}.1 Every promise is an agreement.\nIllustrations",
                    f"(a) A proposes, B accepts.\n{FOOTER}"] for n in (1, 2, 3, 4, 5)])
    chunks = _chunks(rows)
    assert sum(c.endswith("Illustrations") for c in chunks) == 5
    assert not any(HEADER in c or FOOTER in c for c in chunks)


def test_the_page_number_at_a_page_break_is_dropped_and_nothing_else():
    rows = _rows(["12.1 The Customer shall pay each invoice within thirty (30)\n1"],
                 ["days of the invoice date.\n12.2 Disputed amounts are notified in writing."])
    chunks = _chunks(rows)
    assert chunks[0] == "12.1 The Customer shall pay each invoice within thirty (30)"


def test_a_number_that_is_not_this_pages_number_is_content():
    # A two-line table cell at the foot of page 1: "12" is a value, not page 12.
    rows = _rows(["Minimum term (months)\n12"], ["2. Fees are fixed."])
    assert _chunks(rows)[0] == "Minimum term (months)\n12"


def test_sub_clauses_run_together_in_one_paragraph_are_split_with_their_numbers():
    rows = _rows(['1.1 Definitions. 1.1.1 "Agreement" means this master services agreement. '
                  '1.1.2 "Services" means the hosting services described in the Order Form. '
                  "19.4 Termination for cause. (a) Either party may terminate on a material "
                  "breach not cured within thirty days; (b) the Customer may terminate on the "
                  "insolvency of the Provider."])
    refs = [leading_section_ref(c) for c in _chunks(rows)]
    assert refs == ["1.1", "1.1.1", "1.1.2", "19.4"]


@pytest.mark.parametrize("text", [
    "The fee is Rs. 1.5 Lakh per month, payable in advance.",
    "Refer to Sec. 19.4 The Customer shall comply with it.",
    "Uptime was 99.9. 2 Service Credits were issued that month.",
])
def test_a_decimal_or_a_cross_reference_is_not_a_clause_start(text):
    assert _chunks(_rows([text])) == [text]


def test_blank_fields_are_kept_exactly_as_written():
    text = ("3.1 This Agreement commences on [●] and continues for a term of ____ months. "
            "17.7 The aggregate liability of either party shall not exceed ________.")
    joined = " ".join(_chunks(_rows([text])))
    assert "[●]" in joined and "____ months" in joined and "exceed ________." in joined


# --- 1.15: nothing is executed unless a person declared it so ------------------------
@pytest.mark.parametrize("role, expected", [
    (None, "DRAFT_DOCUMENT"), ("COMPANY_DRAFT", "DRAFT_DOCUMENT"),
    ("CLIENT_MODIFIED", "DRAFT_DOCUMENT"), ("FINAL_SIGNED", "EXECUTED_DOCUMENT"),
])
def test_a_document_is_executed_only_when_declared_final_signed(db, indexed_contract,
                                                                  role, expected):
    from sqlalchemy import text

    from legalmind import config
    from legalmind.assist.retrieval import retrieval
    _, version = indexed_contract
    version.doc_metadata = {"version_role": role} if role else {}
    db.flush()
    hits = [SimpleNamespace(chunk_id=r.id, content=r.content, retrieval_score=1.0)
            for r in db.execute(text(f'SELECT id, content FROM "{config.assist_schema()}"'
                                     ".chunks WHERE document_version_id = :v"),
                                {"v": version.id})]
    candidates = retrieval._document_candidates(db, "DOCUMENT", hits, version.id)
    assert hits and {c.authority for c in candidates} == {expected}


# --- 1.14: blank fields are marked, never filled or removed ---------------------------
@pytest.mark.parametrize("text, blanks", [
    ("for a term of ____ months", ["____"]),
    ("commences on [●] and ends on [ ]", ["[●]", "[ ]"]),
    ("Signature: ............ Date: ________", ["............", "________"]),
    ("an amount of Rs. [*] per month", ["[*]"]),
    ("Section 17.2 applies; see clause 4.", []),
    ("a total of 1,000 units at 99.9%", []),
])
def test_blank_fields_are_found_where_they_are_written(text, blanks):
    from legalmind.assist.ingestion.chunking import blank_fields
    assert [text[s:e] for s, e in blank_fields(text)] == blanks

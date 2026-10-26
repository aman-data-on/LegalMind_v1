"""A signing block is never a term left blank (AM-186, owner 2026-10-26): an NDA's
"By: ____ / Name: ____ / Title: ____" read as two unfilled terms. Each line below is a
shape real signing blocks take; each term is a blank a contract really leaves."""
import pytest

from legalmind.analysis.reading import _has_blank

SIGNING = [
    "ACME SOFTWARE SOLUTIONS PRIVATE LIMITED. ___________",
    "By: By:________________",
    "Name: ________ Name:",
    "Title: _________ Title:",
    "Designation: _________",
    "For ACME PVT LTD\n_____________\nAuthorised Signatory",
    "Signature: ______  Date: ______",
    "Witness: ________ Place: ________",
    "Company Seal / Stamp: ________",
]
TERMS = [
    "Payment is due within ____ days of the invoice.",
    "Effective Date: ________",
    "Business Day means any day on which banks at ___________ are open.",
    "By: ______ The fee is ____ per month.",                  # a term beside a signature
    "The liability cap is [●] months of fees.",
    "Place of arbitration: ________",                          # a term, not a signing place
]


@pytest.mark.parametrize("line", SIGNING)
def test_a_signing_line_is_not_a_blank_term(line):
    assert not _has_blank(line)


@pytest.mark.parametrize("line", TERMS)
def test_a_term_left_blank_is_still_a_blank(line):
    assert _has_blank(line)

"""A heading over a short bullet list is a heading (AM-196, 2026-10-26): a customer
MOU's "Confidentiality" and "Limitation of Liability", each over bullets shorter than
the 60-character prose test, were read as one block with "Data Protection and Privacy",
so no clause could be told apart and the liability cap went to a person for the wrong
reason. A web page's menu — short lines under short lines — is still no heading."""
import pytest

from legalmind.ingestion.parsing import _is_unnumbered_heading


@pytest.mark.parametrize("line,following", [
    ("Confidentiality", "●\u200b Both parties must keep shared information confidential"),
    ("Limitation of Liability", "● No liability for indirect or consequential damages"),
    ("Payment Terms", "• Services billed in advance"),
    # a label every word of which is capitalised, over the prose it introduces
    ("Penalty Clause:", "If the Leapswitch Networks Pvt. Ltd. fails to provide Services in "
                        "accordance with the MOU, it shall credit the account."),
])
def test_a_heading_over_a_short_bullet_is_a_heading(line, following):
    assert _is_unnumbered_heading(line, following)


@pytest.mark.parametrize("line,following", [
    ("VPS", "Kubernetes"),                                   # a menu: short under short
    ("Storage", "● Careers"),                                # a one-word bullet is no body
    ("Confidentiality", "● Yes"),
    # a lead-in is the clause's own sentence, never its heading
    ("The Customer shall:", "pay every invoice within twenty-one days of the invoice "
                            "date without any deduction."),
    ("Customer shall comply with the following:", "All applicable laws and the AUP in "
                                                  "force from time to time."),
])
def test_a_menu_or_a_word_bullet_is_not_a_heading(line, following):
    assert not _is_unnumbered_heading(line, following)

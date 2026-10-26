"""Our own details on the paper are the Constitution's (AM-197, 2026-10-26): a customer
MOU described LeapSwitch as "incorporated under the Companies Act, 1956" with a
superseded registered office — §4.1 records the Companies Act, 2013 and Gokhale Business
Bay. An observation for the reader, never a Finding (AM-159)."""
from uuid import uuid4

import pytest

from legalmind.analysis.consistency import OUR_DETAILS, observe
from legalmind.mapping.engine import Clause

MOU_PARTY = ("A. Leapswitch Networks Private Limited, a company incorporated under the "
             "Companies Act, 1956 and having its registered office at 1/A2/22, Ajantha "
             "Avenue, Paud Road, Pune - 411038, bearing CIN U30007PN2010PTC137171")
CUSTOMER = ("B. ACME TECHNOLOGIES PRIVATE LIMITED, a company incorporated under the "
            "Companies Act, 1956 and having its registered office at 12 MG Road, "
            "Bangalore")


def _ours(*texts: str) -> list[dict]:
    clauses = [Clause(evidence_id=uuid4(), content=t) for t in texts]
    return [o for o in observe(clauses)["structural"] if o["kind"] == OUR_DETAILS]


def test_our_superseded_statute_and_office_are_said_with_section_4_1():
    said = _ours(MOU_PARTY, CUSTOMER)
    assert len(said) == 2
    assert {o["basis"]["section"] for o in said} == {"4.1"}
    assert any("1956" in o["text"] for o in said)
    assert any(o["text"] == "Our registered office is given as 1/A2/22, Ajantha Avenue, "
               "Paud Road, Pune - 411038." for o in said)


@pytest.mark.parametrize("text", [
    "Leapswitch Networks Pvt. Ltd., a company incorporated under the Companies Act, 2013, "
    "having its registered office at Office 1104, 11th Floor, Gokhale Business Bay, Kothrud, "
    "Pune 411038",
    CUSTOMER,                                     # the customer's details are theirs
])
def test_details_that_are_right_or_not_ours_are_not_raised(text):
    assert _ours(text) == []

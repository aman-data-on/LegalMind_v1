"""Three recognition gaps found by running five synthetic contracts (2026-09-15).

`AM-51`/`AM-60` made applicability content-first, but nothing exercised it on a
realistic four-page agreement. Five were generated (`tools/generate_test_contracts`)
and run through the live API. The engine's applicability was right — an
OTHER-labelled document scored identically to the same clauses labelled MSA —
but three recognition gaps showed up, all of them vocabulary rather than logic.

Each is pinned here at the level it actually failed, so a fix cannot regress and
the two that are NOT fixed cannot be mistaken for working.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from legalmind.extraction.liability import (
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause, map_requirement

STANDARDS = Path(__file__).resolve().parents[1] / "config" / "company_standards"
_NS = uuid.UUID("00000000-0000-0000-0000-00000000045e")


def extraction(code: str) -> dict:
    return json.loads((STANDARDS / f"{code}.json").read_text())["configuration"]


def facts(text: str, code: str, *, title: str):
    cfg = extraction(code)
    clause = Clause(evidence_id=uuid.uuid5(_NS, text[:40]), content=text,
                    section_number="1", section_title=title, page_number=1)
    result = extract_liability_facts(
        [clause], LiabilityExtractionConfig.from_config(cfg))
    return [(c.cap_status, c.cap_value, c.cap_unit, c.cap_basis)
            for c in result.caps]


# --------------------------------------------------------------------------
# FIXED — an uncapped liability term must reach the Constitution's §9 boundary.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("code", ["LIABILITY-MSA-001", "LIABILITY-TOS-001"])
@pytest.mark.parametrize("text", [
    "Each party accepts unlimited liability for any loss or damage arising out "
    "of or in connection with this Agreement.",
    "The liability of the Supplier under this Agreement is not capped and "
    "shall not be subject to any financial limit.",
    "The liability of the Supplier shall be unlimited.",
])
def test_an_uncapped_liability_term_is_recognised_as_unlimited(code, text):
    """Was ABSENT, which reads as "no cap clause present".

    The consequence was not cosmetic: `constitution_boundaries` §9 fires only on
    `cap_status == "UNLIMITED"`, so an agreement accepting unlimited liability —
    the exact term the Constitution calls Not Negotiable — was classified
    MISSING and surfaced as "Requires modification" instead of "Needs a
    decision". A prohibited term read as a drafting nit.
    """
    statuses = [f[0] for f in facts(text, code, title="Limitation of Liability")]
    assert "UNLIMITED" in statuses, f"{code}: {text[:40]!r} -> {statuses}"


# --------------------------------------------------------------------------
# FIXED — "following the termination" is ordinary drafting for a survival term.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("code,basis", [
    ("CONF-SURVIVAL-MSA-001", "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION"),
    ("CONF-SURVIVAL-NDA-001",
     "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION_OR_RELATIONSHIP_END"),
])
def test_survival_basis_is_read_from_following_the_termination(code, basis):
    """Was basis None -> UNABLE_TO_EVALUATE -> "Needs a decision".

    The VALUE extracted correctly (3 years); only the basis was unattributed,
    because the vocabulary held "after termination" and "post-termination" but
    not "following the termination". A clause exactly on the Constitution's
    number was therefore sent to a human as unreadable.
    """
    text = ("The obligations in this clause shall survive for a period of "
            "3 (3) years following the termination or expiry of this Agreement.")
    got = facts(text, code, title="Confidentiality")
    assert got, f"{code}: nothing extracted"
    assert got[0][1] == 3.0 and got[0][2] == "YEARS"
    assert got[0][3] == basis, f"{code}: basis was {got[0][3]}"


# --------------------------------------------------------------------------
# NOT FIXED — documented precision limitation, pinned so it cannot change
# silently in either direction.
# --------------------------------------------------------------------------
def test_a_billing_dispute_window_collides_with_the_payment_period():
    """PAYMENT-PERIOD-MSA-001 claims any "N days ... invoice" construction.

    Its `cap_phrases` hold "days of the invoice date", "days of invoice" AND
    "days of receipt of the invoice", and its only basis term is "invoice". So a
    billing-dispute window — ordinary drafting, present in most real agreements —
    is indistinguishable from the payment period. The evaluator then holds two
    values for one basis and classifies CONFLICT, which surfaces as "Needs a
    decision" on a payment term that is exactly on the Constitution's number.

    This is FAIL-CLOSED and therefore safe (rule 15): nothing is asserted as
    acceptable, the evidence is kept, and a person decides. It is recorded, not
    fixed, because narrowing the vocabulary trades this false alarm for missed
    payment clauses — a recall loss in the unsafe direction — and choosing that
    trade is an owner decision about ratified configuration, not a session's.
    """
    # Two SEPARATE clauses, which is how a contract is segmented — a payment
    # paragraph and a dispute paragraph, each numbered. Within one paragraph
    # only the first figure is taken; the conflict needs the two to be distinct
    # clauses, which in a real agreement they always are.
    clauses = [
        Clause(evidence_id=uuid.uuid5(_NS, "pay"), section_number="3.2",
               section_title="Payment", page_number=1,
               content="The Customer shall pay each undisputed invoice within "
                       "21 (21) days of the invoice date."),
        Clause(evidence_id=uuid.uuid5(_NS, "dispute"), section_number="3.3",
               section_title="Payment", page_number=1,
               content="If the Customer disputes an invoice in good faith it "
                       "shall notify the Supplier of the disputed invoice "
                       "within 15 (15) days of receipt of the invoice."),
    ]
    cfg = extraction("PAYMENT-PERIOD-MSA-001")
    result = extract_liability_facts(
        clauses, LiabilityExtractionConfig.from_config(cfg))
    got = [(c.cap_status, c.cap_value, c.cap_unit, c.cap_basis)
           for c in result.caps]
    values = sorted(f[1] for f in got if f[1] is not None)
    assert values == [15.0, 21.0], f"collision changed shape: {got}"
    assert all(f[3] == "INVOICE_PAYMENT_PERIOD" for f in got), got


# --------------------------------------------------------------------------
# FIXED — the MAPPER must see an uncapped clause before the extractor can.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("code", ["LIABILITY-MSA-001", "LIABILITY-TOS-001"])
def test_an_uncapped_liability_clause_is_mapped_at_all(code):
    """The full-set run caught what the extraction test could not.

    Widening `extraction.unlimited_phrases` fixed the extractor, and the unit
    test above passed — because it handed the clause straight to
    `extract_liability_facts`. The live pipeline maps first, and an uncapped
    clause scored **2 against a confirm threshold of 5**: the only thing it
    matched was the section heading. So the clause was never recognised as a
    liability clause, extraction never ran on it, and the Finding came back
    MISSING — "Requires modification" for an agreement accepting unlimited
    liability.

    An uncapped liability term was, in other words, invisible rather than
    merely misread. The mapping vocabulary needs the phrasings too.
    """
    from legalmind.mapping.rules import MappingRules
    cfg = json.loads((STANDARDS / f"{code}.json").read_text())
    rules = MappingRules.from_config(cfg["mapping_rules"])
    clause = Clause(
        evidence_id=uuid.uuid5(_NS, f"uncapped-{code}"),
        section_number="7", section_title="Limitation of Liability", page_number=1,
        content="Each party accepts unlimited liability for any loss or damage "
                "arising out of or in connection with this Agreement. The "
                "liability of the Supplier is not capped and shall not be "
                "subject to any financial limit.")
    result = map_requirement(uuid.uuid5(_NS, code), rules, [clause])
    assert result.state.value == "CONFIRMED", \
        f"{code}: {result.state.value} — {'; '.join(result.explanation)}"


@pytest.mark.parametrize("code", ["LIABILITY-MSA-001", "LIABILITY-TOS-001"])
def test_widening_the_mapper_did_not_make_it_promiscuous(code):
    """The other half: a clause about nothing in particular must still not map.

    Adding phrases to buy recall is only safe if precision holds, and a
    liability standard that confirms on an unrelated clause would put a cap
    finding on a document that states no cap at all.
    """
    from legalmind.mapping.rules import MappingRules
    cfg = json.loads((STANDARDS / f"{code}.json").read_text())
    rules = MappingRules.from_config(cfg["mapping_rules"])
    clause = Clause(
        evidence_id=uuid.uuid5(_NS, f"unrelated-{code}"),
        section_number="2", section_title="Scope of Services", page_number=1,
        content="The Supplier shall perform the Services with reasonable skill "
                "and care in accordance with industry standards, and shall "
                "allocate suitably qualified personnel.")
    result = map_requirement(uuid.uuid5(_NS, code), rules, [clause])
    assert result.state.value != "CONFIRMED", f"{code} confirmed on an unrelated clause"

"""Counterparty calibration — locked 35.10's direction, first pass 2026-08-20.

Locked 35.10 requires terminology and thresholds to be validated against a
representative contract set. The owner-approved pass of 2026-08-20 probed eight
public counterparty specimens (test-only authorization of 2026-08-18) and added
drafting-variant terminology to the two liability standards: counterparty paper
writes "will not exceed" / "not to exceed" / "is limited to" where LeapSwitch's
own documents write "shall not exceed".

These tests pin that calibration with SHORT CITED EXCERPTS (locked 54.6 permits
excerpts; the documents themselves stay outside the repository). Each excerpt is
quoted verbatim from a public web document and exercises the REAL ratified
configuration read from ``backend/config/company_standards/`` — so a terminology
regression that silently un-maps AWS, or a careless basis term that would let a
mis-read magnitude be compared, fails here rather than in production.

What is deliberately pinned as FAIL-CLOSED, not as a defect:

* a magnitude with an unrecognised basis is never compared (45B.4) — the GCP and
  Microsoft caps are measured against service-scoped bases, not total fees;
* composite formulas (greater-of / lesser-of / averages) never have one limb
  read as the cap — CtrlS's two-limb clause resolves to positions a human sees;
* the evaluator-layer conclusions for these shapes are corpus-pinned
  (CP-LIAB-01 for deviation-by-value under the approved rule, CP-LIAB-02/03 for
  basis refusal); this file pins the mapping/extraction layer that feeds them.
"""

from __future__ import annotations

import json
from uuid import uuid4

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.extraction.liability import (
    FINITE,
    UNKNOWN,
    UNLIMITED,
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules


def _ratified(code: str) -> tuple[MappingRules, LiabilityExtractionConfig]:
    payload = json.loads((RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())
    return (MappingRules.from_config(payload["mapping_rules"]),
            LiabilityExtractionConfig.from_config(payload["configuration"]))


def _clause(text: str) -> Clause:
    return Clause(evidence_id=uuid4(), content=text)


def _map_and_extract(code: str, text: str):
    rules, extraction = _ratified(code)
    clause = _clause(text)
    result = map_requirement(uuid4(), rules, [clause])
    facts = (extract_liability_facts(list(result.confirmed_clauses), extraction)
             if result.state.value == "CONFIRMED" else None)
    return result, facts


# AWS Customer Agreement §9.2 (aws.amazon.com/agreement, public web terms;
# test specimen only, owner authorization 2026-08-18).
AWS_9_2 = (
    "EXCEPT FOR PAYMENT OBLIGATIONS UNDER SECTION 7, THE AGGREGATE LIABILITY "
    "UNDER THIS AGREEMENT OF EITHER AWS OR YOU, AND ANY OF OUR RESPECTIVE "
    "AFFILIATES OR LICENSORS, WILL NOT EXCEED THE AMOUNTS PAID BY YOU TO AWS "
    "UNDER THIS AGREEMENT FOR THE SERVICES THAT GAVE RISE TO THE LIABILITY "
    "DURING THE 12 MONTHS BEFORE THE LIABILITY AROSE.")


def test_aws_will_not_exceed_maps_and_extracts_the_affected_services_cap():
    """'WILL not exceed' is the same cap concept as 'SHALL not exceed'.

    Before calibration this clause scored below the confirm threshold and the
    engine reported nothing at all; a reviewer would never have seen it. Against
    the MSA standard the extracted position (12 months, affected-services basis)
    is a genuine value deviation from the ratified 6 — the evaluator-layer
    consequence (DEVIATION → UNACCEPTABLE under the approved rule) is pinned by
    CP-LIAB-01's shape.
    """
    result, facts = _map_and_extract("LIABILITY-MSA-001", AWS_9_2)
    assert result.state.value == "CONFIRMED"
    assert facts is not None and len(facts.caps) == 1
    cap = facts.caps[0]
    assert cap.cap_status == FINITE
    assert cap.cap_value == 12.0
    assert cap.cap_unit == "MONTHS"
    # The clause's own restriction — the SAME basis concept as MSA 17.2, in
    # AWS's words. Comparable to the MSA standard, and deliberately NOT to the
    # TOS standard's FEES_PAID.
    assert cap.cap_basis == "FEES_PAID_FOR_AFFECTED_SERVICES"


def test_aws_basis_is_not_read_as_total_fees():
    """45B.4 — against the TOS standard the same clause must extract NO basis:
    'for the services that gave rise to the liability' is not 'total fees paid',
    and an unrecognised basis fails closed rather than being equated."""
    _, facts = _map_and_extract("LIABILITY-TOS-001", AWS_9_2)
    assert facts is not None and facts.caps[0].cap_basis is None


def test_google_is_limited_to_extracts_but_the_service_scoped_basis_fails_closed():
    """Google Cloud Platform TOS §12.2 (cloud.google.com/terms, public web
    terms; test specimen only). 'is limited to' is a cap statement; the basis
    ('Fees Customer paid for such Services') is service-scoped, so no configured
    basis term may match and the comparison must fail closed (45B.4)."""
    excerpt = (
        "Each party's total aggregate Liability for damages arising out of or "
        "relating to this Agreement is limited to the Fees Customer paid for "
        "such Services during the 12 month period before the event giving rise "
        "to Liability.")
    result, facts = _map_and_extract("LIABILITY-TOS-001", excerpt)
    assert result.state.value == "CONFIRMED"
    cap = facts.caps[0]
    assert (cap.cap_status, cap.cap_value, cap.cap_unit) == (FINITE, 12.0, "MONTHS")
    assert cap.cap_basis is None          # never equated with FEES_PAID


def test_ctrls_two_part_clause_yields_positions_a_human_must_resolve():
    """CtrlS MSA §12.1 (ctrls.in, public web terms; test specimen only) states
    an unlimited position for non-excludable liability AND a greater-of
    composite cap in one clause. Clause-level extraction reports the UNLIMITED
    it genuinely states; the composite must never have one limb read as a clean
    value. Same-scope distinct positions resolve to CONFLICT at the evaluator
    (45C.2) — evidence retained, a human decides. Nothing here is auto-accepted.
    """
    part_a = (
        "Either Party's liability arising out of any loss or damages for which "
        "limitation is expressly prohibited by Applicable Laws, shall be "
        "unlimited.")
    part_b = (
        "Subject to Clause 12.1(a), the maximum aggregate monetary liability of "
        "either Party under any theory of law shall not exceed the actual "
        "damages incurred up to the greater of: (i) an amount equal to six "
        "times the Fees payable by Customer for the Services in the first month "
        "of the Initial Term, or (ii) the total amount paid by Customer to the "
        "Service Provider for the Services that are the subject of the claim in "
        "the 12 months immediately preceding the event(s) that first gave rise "
        "to the claim.")
    rules, extraction = _ratified("LIABILITY-MSA-001")
    clauses = [_clause(part_a + " " + part_b)]
    result = map_requirement(uuid4(), rules, clauses)
    assert result.state.value == "CONFIRMED"
    facts = extract_liability_facts(list(result.confirmed_clauses), extraction)
    assert [c.cap_status for c in facts.caps] == [UNLIMITED]
    # UNLIMITED evaluates to DEVIATION before any magnitude or basis question,
    # and the approved rule's unlimited_outcome sends it to Legal (corpus-pinned
    # by STD-LIAB-03's carve-out shape).


def test_composite_lesser_of_formulas_stay_unread():
    """NxtGen T&C (nxtgen.com, public web terms; test specimen only): a
    lesser-of formula whose fee limb is written '6(six) months'. Reading the
    digits through the reversed parenthetical — or reading either limb alone —
    would flatten a two-limb formula into a confident single value (the exact
    45B.4/L-11 failure). UNKNOWN → UNABLE_TO_EVALUATE is the correct outcome.
    """
    excerpt = (
        "The total liability under or in connection with this agreement will "
        "be limited to the actual direct damages incurred but will not exceed "
        "the annual contract value or the fees paid by the customer in the "
        "last 6(six) months, whichever is less.")
    result, facts = _map_and_extract("LIABILITY-TOS-001", excerpt)
    assert result.state.value == "CONFIRMED"
    assert [c.cap_status for c in facts.caps] == [UNKNOWN]
    assert facts.caps[0].cap_value is None

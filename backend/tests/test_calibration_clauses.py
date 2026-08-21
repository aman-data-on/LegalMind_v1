"""Counterparty calibration for the non-liability Requirements — 2026-08-20.

The owner's tasking: every ratified Requirement must demonstrably work on real
counterparty documents, without waiting for a private document supply. Sources,
in order of preference, all authorized:

1. **Public web terms** (owner test-only exception, 2026-08-18): CtrlS MSA,
   ESDS SLA, Google Cloud SLAs, CloudPe SLA, NxtGen T&C.
2. **Public filings** (SEC EDGAR exhibits — real executed agreements):
   Xerox/Global Imaging Mutual NDA (EX-99.(D)(2), 2007-04-04) and the Castlight
   Health services agreement (EX-10.11, 2014-03-03).
3. **Synthetic real-pattern clauses** where no public specimen states a value —
   locked 54.6 expressly allows synthetic contract text for fixtures. Each such
   test is labelled SYNTHETIC, drafts in the register's standard pattern, and
   its expectation follows mechanically from the ratified position; nothing in
   it becomes a standard or a threshold (rules 7/21 untouched).

Every test runs the REAL ratified configuration from
``backend/config/company_standards/`` — mapping then extraction — so these are
regression pins on the calibrated terminology, not on copies of it. Fail-closed
outcomes (UNKNOWN word-form values, absent bases, unit mismatches surfaced to
the evaluator) are asserted as the CORRECT result where the drafting genuinely
does not state a machine-comparable value.
"""

from __future__ import annotations

import json
from uuid import uuid4

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.extraction.liability import (
    FINITE,
    UNKNOWN,
    LiabilityExtractionConfig,
    extract_liability_facts,
)
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules


def _run(code: str, text: str):
    payload = json.loads((RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())
    rules = MappingRules.from_config(payload["mapping_rules"])
    clause = Clause(evidence_id=uuid4(), content=text)
    result = map_requirement(uuid4(), rules, [clause])
    facts = None
    if (result.state.value == "CONFIRMED"
            and payload.get("evaluator_type") != "PRESENCE"):
        facts = extract_liability_facts(
            list(result.confirmed_clauses),
            LiabilityExtractionConfig.from_config(payload["configuration"]))
    return result, facts


def _single_cap(facts):
    assert facts is not None and len(facts.caps) == 1, facts
    return facts.caps[0]


# ======================================================================
# SLA — claim window (real public specimens; three different values)
# ======================================================================
def test_esds_fifteen_day_credit_request_window_is_read():
    """ESDS SLA §9.1 (esds.co.in, public web terms): a 15-day window in the
    mirrored digits-word convention — a genuine DEVIATION against 60."""
    result, facts = _run("CLAIM-WINDOW-SLA-001", (
        "To claim a service credit under this SLA, the Client must submit a "
        "written credit request within 15 (fifteen) calendar days of the end "
        "of the calendar month in which the alleged SLA breach occurred."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_status, cap.cap_value, cap.cap_unit) == (FINITE, 15.0, "DAYS")


def test_google_sixty_day_credit_notification_window_is_read():
    """Google Compute Engine SLA (cloud.google.com, public web terms): 60 days
    — the same value as the ratified standard, in Google's drafting."""
    result, facts = _run("CLAIM-WINDOW-SLA-001", (
        "Customer Must Request Financial Credit. In order to receive any of "
        "the Financial Credits described above, Customer must notify Google "
        "technical support within 60 days from the time Customer becomes "
        "eligible to receive a Financial Credit."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (60.0, "DAYS")


def test_a_word_form_claim_window_stays_unread():
    """CtrlS SLA 4.3 (ctrls.in, public web terms): 'a month prior to the date
    of claim' states no digits, so no value may be manufactured (44.24)."""
    result, facts = _run("CLAIM-WINDOW-SLA-001", (
        "Customer shall be eligible for Service Credit for only those "
        "Downtimes which has occurred a month prior to the date of claim and "
        "the maximum Service Credit is as mentioned in Clause 6.1."))
    if result.state.value == "CONFIRMED" and facts.caps:
        assert all(c.cap_status != FINITE for c in facts.caps)


# ======================================================================
# MSA — cure period, auto-renewal, force majeure (real public specimens)
# ======================================================================
def test_ctrls_ten_day_cure_period_is_read():
    """CtrlS MSA (ctrls.in, public web terms): 'fails to cure such breach
    within a period of ten (10) days (or such mutually agreeable period)' —
    a genuine DEVIATION against the ratified 30."""
    result, facts = _run("CURE-PERIOD-MSA-001", (
        "Customer is in breach of this Agreement and fails to cure such "
        "breach within a period of ten (10) days (or such mutually agreeable "
        "period) of Service Provider notifying the Customer of such breach."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_status, cap.cap_value, cap.cap_unit) == (FINITE, 10.0, "DAYS")
    assert cap.cap_basis == "BREACH_CURE_PERIOD"


def test_a_day_denominated_renewal_term_surfaces_the_unit_mismatch():
    """CtrlS MSA §1.23 (ctrls.in): 'automatic renewal period ... consecutive
    rolling 90 days terms'. DAYS is configured as a recognisable unit precisely
    so the evaluator refuses EXPLICITLY (unit differs, 45C.23) instead of
    reporting an unreadable clause."""
    result, facts = _run("AUTORENEW-MSA-001", (
        "Renewal Term means the automatic renewal period following expiry of "
        "the Initial Term, for consecutive rolling 90 days terms unless "
        "otherwise provided under the STA."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_status, cap.cap_value, cap.cap_unit) == (FINITE, 90.0, "DAYS")
    # The ratified unit is MONTHS; the evaluator's strict unit equality turns
    # this into UNABLE_TO_EVALUATE, never a silent 90-vs-6 comparison.


def test_the_generic_force_majeure_trigger_wording_is_read_by_the_msa_requirement():
    """Negotiated MSAs state the trigger as 'continues for more than N
    consecutive days' (the TOS drafting). The MSA requirement must read it too
    — a real negotiated 30-day trigger was visible only to the TOS requirement
    before this calibration. SYNTHETIC sentence in that standard pattern; the
    private executed document is not quoted (54.6)."""
    result, facts = _run("FORCE-MAJEURE-MSA-001", (
        "If a Force Majeure Event continues for more than thirty (30) "
        "consecutive days, either Party may terminate this Agreement upon "
        "written notice."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (30.0, "DAYS")


# ======================================================================
# NDA — survival, non-solicit, return/destruction (real public filings)
# ======================================================================
XEROX_SURVIVAL = (
    "Unless the Parties otherwise agree in writing, a Recipient's duty to "
    "protect Confidential Information expires two years from the Effective "
    "Date.")


def test_the_effective_date_survival_anchor_can_never_falsely_match():
    """Xerox/Global Imaging Mutual NDA §8 (SEC EDGAR EX-99.(D)(2), 2007): two
    years FROM THE EFFECTIVE DATE — same number as the ratified standard,
    different clock. The clause maps (Legal sees it), but the value is in words
    (UNKNOWN) and the effective-date anchor is deliberately absent from the
    basis terms, so '2 == 2' can never be asserted across different anchors —
    the exact 45B.4 trap the catalogue documents."""
    result, facts = _run("CONF-SURVIVAL-NDA-001", XEROX_SURVIVAL)
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert cap.cap_status == UNKNOWN
    assert cap.cap_basis is None


def test_xerox_non_solicit_maps_and_its_word_form_period_fails_closed():
    """Xerox/Global Imaging Mutual NDA §9 (SEC EDGAR): a one-year non-solicit
    written as 'a period ending one year from' — mapped, and the word-form
    value stays unread rather than guessed."""
    result, facts = _run("NON-SOLICIT-NDA-001", (
        "For a period ending one year from the date on which the Parties have "
        "terminated discussions concerning a Potential Transaction, each Party "
        "agrees not to, either directly or through others, solicit, initiate "
        "discussions with or attempt to solicit for employment any present "
        "officer or management employee of the other Party."))
    assert result.state.value == "CONFIRMED"
    if facts.caps:
        assert all(c.cap_status != FINITE for c in facts.caps)


def test_xerox_deliver_and_destroy_drafting_establishes_presence():
    """Xerox/Global Imaging Mutual NDA §7 (SEC EDGAR): return/destruction
    stated as 'deliver to the Discloser ... destroy all copies' — presence must
    be established from that drafting, not only from LeapSwitch's own."""
    result, _ = _run("RETURN-DESTRUCTION-NDA-001", (
        "Each Recipient will promptly deliver to the Discloser all "
        "Confidential Information furnished in tangible form and will destroy "
        "all copies, extracts or other reproductions thereof."))
    assert result.state.value == "CONFIRMED"


def test_nxtgen_thirty_day_termination_notice_is_read():
    """NxtGen T&C (nxtgen.com, public web terms): termination on thirty (30)
    days' notice in a third party's drafting."""
    result, facts = _run("TERM-NOTICE-NDA-001", (
        "This agreement may be terminated by either party by giving thirty "
        "(30) days prior written notice to the other party."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (30.0, "DAYS")


# ======================================================================
# Purge / retrieval / KYC / late fee (public filing + SYNTHETIC patterns)
# ======================================================================
def test_castlight_ninety_day_purge_window_is_read():
    """Castlight Health services agreement §7.4 (SEC EDGAR EX-10.11, 2014): a
    real 90-day purge obligation — a genuine DEVIATION against the ratified
    15 days."""
    result, facts = _run("DATA-PURGE-MSA-001", (
        "Castlight will, within ninety (90) days after written request by "
        "Customer, purge all Customer Data received from the Customer."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_status, cap.cap_value, cap.cap_unit) == (FINITE, 90.0, "DAYS")


def test_a_counterparty_retrieval_window_in_the_standard_pattern_is_read():
    """SYNTHETIC, standard industry pattern (no public specimen states a
    retrieval window in third-party drafting; LeapSwitch's own TOS remains the
    only real one). The expectation follows mechanically from the ratified
    position; the sentence asserts no one's legal position."""
    result, facts = _run("DATA-RETRIEVAL-TOS-001", (
        "Following termination, customer data will remain available for "
        "retrieval for 30 days, after which it may be permanently deleted."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (30.0, "DAYS")


def test_a_counterparty_kyc_retention_in_the_standard_pattern_is_read():
    """SYNTHETIC, standard industry pattern (KYC record retention is
    India-regulatory drafting; no third-party specimen in any public source
    found states a period — see the calibration record)."""
    result, facts = _run("KYC-RETENTION-TOS-001", (
        "All KYC records shall be maintained for a minimum period of three "
        "(3) years after cancellation of the subscriber's registration."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (3.0, "YEARS")


def test_a_late_fee_in_the_standard_pattern_is_read():
    """SYNTHETIC, standard industry pattern ('1.5% per month'). Microsoft's
    real late-fee drafting ('2% ... calculated and payable monthly') is
    non-contiguous and correctly fails closed to a human — pinned implicitly by
    it extracting UNKNOWN, not asserted here as a value."""
    result, facts = _run("LATE-FEE-TOS-001", (
        "Overdue invoices will be charged a late fee of 1.5% per month on the "
        "outstanding balance."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (1.5, "PERCENT_PER_MONTH")


def test_a_counterparty_confidentiality_survival_in_the_standard_pattern_is_read():
    """SYNTHETIC, standard industry pattern, POST-TERMINATION anchored — the
    one anchor the ratified MSA basis may compare (45B.4). No public MSA
    specimen states survival years (CtrlS carries only boilerplate survival)."""
    result, facts = _run("CONF-SURVIVAL-MSA-001", (
        "The obligations of confidentiality under this clause shall survive "
        "for a period of five (5) years post-termination of this Agreement."))
    assert result.state.value == "CONFIRMED"
    cap = _single_cap(facts)
    assert (cap.cap_value, cap.cap_unit) == (5.0, "YEARS")

"""Counterparty calibration for the 11 PRESENCE Requirements — 2026-08-21.

Locked 35.10 requires terminology to be validated against a representative
contract set. Real negotiated counterparty contracts are not yet available; the
owner directed (2026-08-21) that public sources be used until they arrive —
public web terms, public filings, published policies and statutes. This file
pins that pass.

Every excerpt below is quoted VERBATIM from a public document and is a TEST
SPECIMEN ONLY (owner authorization 2026-08-18, extended 2026-08-21). None is a
source of a Company Standard, a Legal Rule, a threshold or any configuration
value, and none enters the repository beyond the short excerpts here — locked
54.6 permits excerpts.

Each test exercises the REAL ratified configuration read from
``backend/config/company_standards/``, so a terminology regression that silently
un-maps a counterparty clause fails here rather than in production.

--------------------------------------------------------------------------
Why these Requirements are PRESENCE and what that means for the assertions
--------------------------------------------------------------------------
A PRESENCE Requirement asks only whether a provision EXISTS. So the assertion is
always the mapping state, never a value. The clause's CONTENT — how broad the
exclusion is, which party the indemnity runs to, which seat the arbitration
names — goes to Legal with the evidence. Categorical value comparison is a V2
evaluator (CLAUSE_CATALOGUE.md).

--------------------------------------------------------------------------
The safety property these tests also protect
--------------------------------------------------------------------------
With locked 35.8's default weights an alias or a keyword group scores 3 and
``confirm_threshold`` is 5. No single generic term can therefore confirm a
mapping on its own — two independent signals are always required. That is what
makes broad aliases like "trade secret" or "arbitration" safe to configure, and
``test_a_single_generic_term_cannot_confirm_alone`` pins it.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from legalmind.mapping.engine import Clause, map_requirement
from legalmind.mapping.rules import MappingRules
from legalmind.mapping.scoring import score_clause


def _rules(code: str) -> MappingRules:
    payload = json.loads((RATIFIED_STANDARDS_DIR / f"{code}.json").read_text())
    return MappingRules.from_config(payload["mapping_rules"])


def _state(code: str, text: str) -> str:
    result = map_requirement(uuid4(), _rules(code),
                             [Clause(evidence_id=uuid4(), content=text)])
    return result.state.value


def _score(code: str, text: str) -> int:
    """The raw signal score for one clause.

    Deliberately `score_clause` and not `map_requirement`: the latter exposes
    only candidates that already reached `confirm_threshold`, so reading a score
    from it can return nothing but ">= threshold" or 0. The tests below need the
    intermediate value — "recognised, but not enough to confirm" is exactly the
    band that keeps a broad alias safe.
    """
    return score_clause(_rules(code), content=text).score


# ==========================================================================
# Specimens — verbatim, public sources, test-only
# ==========================================================================

# AWS Customer Agreement (aws.amazon.com/agreement)
AWS_9_1 = (
    "NEITHER AWS NOR YOU WILL HAVE LIABILITY ARISING OUT OF OR RELATED TO THIS "
    "AGREEMENT FOR (A) INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR "
    "EXEMPLARY DAMAGES, INCLUDING LOST PROFITS, REVENUES, CUSTOMERS, "
    "OPPORTUNITIES OR GOODWILL")
AWS_9_2_CARVEOUT = (
    "EXCEPT THAT NOTHING IN THIS SECTION 9 WILL LIMIT (A) YOUR OBLIGATION TO "
    "PAY AWS FOR YOUR USE OF THE SERVICES PURSUANT TO SECTION 3")
AWS_11_15_E = (
    "none of the disclaimers or damage caps set forth in Section 9 will "
    "exclude or limit either party's liability for such party's gross "
    "negligence or willful misconduct")
AWS_7_1 = (
    "you will defend, indemnify, and hold harmless us, our affiliates and "
    "licensors, and each of their respective employees, officers, directors, "
    "and representatives from and against any Losses arising out of or "
    "relating to any third-party claim")
AWS_8 = (
    "THE SERVICES AND AWS CONTENT ARE PROVIDED \"AS IS.\" WE AND OUR "
    "AFFILIATES AND LICENSORS MAKE NO REPRESENTATIONS OR WARRANTIES OF ANY "
    "KIND, WHETHER EXPRESS, IMPLIED, STATUTORY OR OTHERWISE REGARDING THE "
    "SERVICES, AND DISCLAIM ALL WARRANTIES, INCLUDING ANY IMPLIED OR EXPRESS "
    "WARRANTIES OF MERCHANTABILITY, SATISFACTORY QUALITY, FITNESS FOR A "
    "PARTICULAR PURPOSE, NON-INFRINGEMENT, OR QUIET ENJOYMENT")
AWS_11_5 = (
    "Disputes will be resolved by binding arbitration, rather than in court, "
    "except that either party may elect to proceed in small claims court")

# DigitalOcean Terms of Service (digitalocean.com/legal)
DO_10_1 = (
    "in no event will we be liable to you for any indirect, incidental, "
    "special, consequential, or punitive damages, including loss of profits, "
    "data, use, goodwill, or other intangible losses")
DO_11 = (
    "you shall defend, indemnify, and hold harmless us and our employees, "
    "officers, directors, agents, contractors, and representatives from all "
    "liabilities, claims, and expenses")
DO_9_1 = (
    "The Websites and Services and all content and materials available "
    "through them are provided \"as is\" and on an \"as available\" basis.")
DO_13_1 = (
    "every dispute arising in connection with this TOS will be resolved by "
    "binding arbitration")
DO_6_3 = (
    "you agree to be billed on a recurring basis and to be automatically "
    "charged for the applicable fees until you cancel your account")
DO_2_1 = (
    "the Websites and Services are owned and/or provided by DigitalOcean. The "
    "names, logos, trademarks, service marks and other proprietary "
    "designations are protected by intellectual property and other laws")

# Hetzner Online Terms and Conditions (hetzner.com/legal)
HETZNER_USA_17 = (
    "IN NO EVENT SHALL WE BE LIABLE TO YOU FOR ANY DIRECT, INDIRECT, "
    "INCIDENTAL, SPECIAL, PUNITIVE, OR CONSEQUENTIAL DAMAGES WHATSOEVER")
HETZNER_10 = (
    "The statutory limitation period also applies to claims for damages in "
    "the event of willful and gross negligence as well as in the event of "
    "injury to life, limb and health")
HETZNER_USA_7 = (
    "The contracts will continue and automatically renew themselves until "
    "terminated by either party.")

# Public SEC EDGAR filings (sec.gov/Archives/edgar) — public by law
EDGAR_NDA_RESIDUALS = (
    "The receiving party's employees may use any Residuals for any purpose, "
    "provided that this paragraph does not grant or imply any license or "
    "other right to use any patent, trademark, copyright, mask work right or "
    "other intellectual property right. \"Residuals\" means information that "
    "is retained, as general knowledge and experience, in the unaided memory "
    "of the receiving party's employees who have had access to the disclosing "
    "party's Confidential Information.")
EDGAR_NDA_DESTROY = (
    "upon written request of the disclosing party, the receiving party shall "
    "take reasonable steps to instruct all persons involved in the "
    "Transaction to destroy all Confidential Information furnished to the "
    "receiving party by or on behalf of the disclosing party pursuant to this "
    "Agreement.")
EDGAR_TRADE_SECRET = (
    "Executive shall not directly or indirectly divulge or make use of any "
    "Trade Secrets (so long as the information remains a Trade Secret under "
    "the applicable state law) for the benefit of anyone other than the "
    "Company")
EDGAR_EARLY_TERMINATION = (
    "In the event that Tenant fails timely to give Tenant's Termination "
    "Notice or to pay the Early Termination Fee, Tenant shall have no right "
    "to terminate the term of the Lease pursuant to this Paragraph 6.")
EDGAR_NDA_GOVLAW = (
    "This Agreement shall be governed by and construed and enforced in "
    "accordance with the laws of the State of Delaware applicable to "
    "agreements made and to be performed within that state.")
EDGAR_NDA_COMPELLED = (
    "In the event that a receiving party or its Associates is or becomes "
    "legally compelled under applicable law, regulation or securities "
    "exchange listing agreement, or by a competent governmental, "
    "administrative or regulatory authority or in a proceeding before a "
    "court, arbitrator or administrative agency, to disclose any "
    "Confidential Information, such party shall provide prompt notice.")


# ==========================================================================
# The calibration itself — each was NOT CONFIRMED before 2026-08-21
# ==========================================================================

CONFIRMS = [
    # (requirement code, specimen label, text, what the calibration added)
    ("LIAB-EXCLUSIONS-MSA-001", "AWS 9.1", AWS_9_1,
     "'consequential OR EXEMPLARY damages' and 'LOST profits' — LeapSwitch's "
     "own 17.1 writes 'consequential, exemplary' and 'loss of profits'"),
    ("LIAB-EXCLUSIONS-MSA-001", "DigitalOcean 10.1", DO_10_1, "word order"),
    ("LIAB-EXCLUSIONS-MSA-001", "Hetzner USA 17", HETZNER_USA_17, "word order"),
    ("LIAB-CARVEOUTS-MSA-001", "AWS 9.2", AWS_9_2_CARVEOUT,
     "'nothing in this section ... will limit' — the carve-out written as a "
     "saving clause rather than as an exclusions list"),
    ("LIAB-CARVEOUTS-MSA-001", "AWS 11.15(e)", AWS_11_15_E, "'exclude or limit'"),
    ("LIAB-CARVEOUTS-MSA-001", "Hetzner 10", HETZNER_10,
     "'willful and gross negligence' plus 'injury to life' — civil-law drafting"),
    ("INDEMNITY-MSA-001", "AWS 7.1", AWS_7_1, "already mapped; pinned"),
    ("INDEMNITY-MSA-001", "DigitalOcean 11", DO_11, "already mapped; pinned"),
    ("RETURN-DESTRUCTION-MSA-001", "EDGAR NDA cl.10", EDGAR_NDA_DESTROY,
     "'destroy all Confidential Information' with no 'return' verb at all"),
    ("IP-OWNERSHIP-MSA-001", "DigitalOcean 2.1", DO_2_1,
     "'owned ... protected by intellectual property' — ownership asserted "
     "without the words 'right, title and interest'"),
    ("WARRANTY-DISCLAIMER-MSA-001", "AWS 8", AWS_8, "already mapped; pinned"),
    ("WARRANTY-DISCLAIMER-MSA-001", "DigitalOcean 9.1", DO_9_1,
     "bare 'as is'/'as available' with no merchantability list"),
    ("EARLY-TERM-RESTRICTION-MSA-001", "EDGAR early-termination",
     EDGAR_EARLY_TERMINATION,
     "'no right to terminate' + 'Early Termination Fee' as separate signals"),
    ("ARBITRATION-TOS-001", "AWS 11.5", AWS_11_5, "'binding arbitration'"),
    ("ARBITRATION-TOS-001", "DigitalOcean 13.1", DO_13_1, "'binding arbitration'"),
    ("AUTORENEW-TOS-001", "DigitalOcean 6.3", DO_6_3,
     "'recurring basis ... automatically charged' — renewal by billing conduct"),
    ("AUTORENEW-TOS-001", "Hetzner USA 7", HETZNER_USA_7, "'automatically renew'"),
    ("RESIDUALS-NDA-001", "EDGAR NDA cl.8", EDGAR_NDA_RESIDUALS,
     "already mapped via 'residuals' + 'unaided memory'; pinned"),
    ("TRADE-SECRET-CARVEOUT-NDA-001", "EDGAR trade secret", EDGAR_TRADE_SECRET,
     "'so long as the information remains a Trade Secret' — the same proviso "
     "with a different determiner"),

    # The five PRESENCE Requirements ratified 2026-08-19 that the 2026-08-20
    # counterparty pass never reached — it covered liability and the numeric
    # clauses only. All five failed on their first public specimen.
    ("GOVLAW-MSA-001", "EDGAR NDA cl.14", EDGAR_NDA_GOVLAW,
     "'governed by and construed AND ENFORCED in accordance with' — three "
     "words inserted into the middle of the configured exact phrase"),
    ("GOVLAW-TOS-001", "EDGAR NDA cl.14", EDGAR_NDA_GOVLAW, "as GOVLAW-MSA-001"),
    ("GOVLAW-NDA-001", "EDGAR NDA cl.14", EDGAR_NDA_GOVLAW, "as GOVLAW-MSA-001"),
    ("COMPELLED-DISCLOSURE-NDA-001", "EDGAR NDA cl.3", EDGAR_NDA_COMPELLED,
     "'legally compelled ... to disclose' where LeapSwitch's NDA writes "
     "'required by applicable law'"),
    ("RETURN-DESTRUCTION-NDA-001", "EDGAR NDA cl.10", EDGAR_NDA_DESTROY,
     "'destroy all Confidential Information' with no 'return' verb — the same "
     "gap the MSA counterpart had"),
]


@pytest.mark.parametrize(
    "code,label,text,added",
    CONFIRMS,
    ids=[f"{c}-{lbl}" for c, lbl, _t, _a in CONFIRMS])
def test_a_public_specimen_maps_to_its_requirement(code, label, text, added):
    """The clause type is recognised in a third party's words, not only ours."""
    assert _state(code, text) == "CONFIRMED", (
        f"{code} no longer maps {label}; the calibration of 2026-08-21 added: "
        f"{added}")


# ==========================================================================
# Deliberately NOT matched — recorded so absence is not read as a defect
# ==========================================================================

def test_aws_customer_content_carve_out_is_not_forced_to_map():
    """AWS 6.1 ("we obtain no rights ... to Your Content") is a CUSTOMER-content
    allocation, not the supplier IP-ownership clause IP-OWNERSHIP-MSA-001 is the
    position for. Making it map would need a term broad enough to fire on any
    sentence containing "rights", and an over-broad presence term produces a
    confident false PRESENT — worse than no mapping, because a reviewer would
    never look. Left unmapped deliberately; the same judgement the Xerox
    survival anchor received on 2026-08-20 (decision #42).
    """
    assert _state("IP-OWNERSHIP-MSA-001",
                  "we obtain no rights under this Agreement from you or your "
                  "licensors to Your Content") != "CONFIRMED"


def test_a_single_generic_term_cannot_confirm_alone():
    """The property that makes broad aliases safe to configure.

    An alias or keyword group scores 3 against `confirm_threshold` 5, so one
    generic word raises a clause to 3 and never to a mapping. If a future
    calibration promotes one of these to an `exact_phrase` (weight 5) it would
    confirm on a single word, and this test is what stops that happening
    silently.
    """
    for code, word in [("TRADE-SECRET-CARVEOUT-NDA-001", "trade secret"),
                       ("ARBITRATION-TOS-001", "arbitration"),
                       ("ARBITRATION-MSA-001", "arbitration"),
                       ("AUTORENEW-TOS-001", "renewal term"),
                       ("RESIDUALS-NDA-001", "residuals"),
                       ("GOVLAW-MSA-001", "governing law")]:
        text = f"This agreement mentions {word} once and says nothing further."
        score = _score(code, text)
        # Recognised — otherwise this test would pass for the wrong reason, on
        # terminology that matches nothing at all.
        assert score > 0, f"{code}: {word!r} is not recognised at all"
        assert score < 5, (
            f"{code}: the single term {word!r} now reaches the confirm "
            "threshold on its own — a one-word false PRESENT is reachable")
        assert _state(code, text) != "CONFIRMED"


def test_arbitration_msa_no_longer_confirms_on_a_bare_statutory_reference():
    """The precision fix of 2026-08-21 (owner-approved).

    `ARBITRATION-MSA-001` carried the bare word `arbitration` as an
    `exact_phrase` at weight 5, so a SINGLE mention confirmed the mapping. The
    2026-08-21 statute sweep caught it: a footnote in the Indian Contract Act
    1872 reading "Cf. the Arbitration Act, 1940" confirmed a Requirement about
    whether a contract contains an arbitration clause.

    Demoted to an alias (weight 3), so two independent signals are now needed.
    MSA 19.3-19.4 still confirms — it states both `arbitration` and
    `arbitrator` — which `tools/verify_terminology` checks against the real
    document.
    """
    footnote = ("Cf. the Arbitration Act, 1940 (10 of 1940) and the Companies "
                "Act, 1956 (1 of 1956), s. 389.")
    assert _state("ARBITRATION-MSA-001", footnote) != "CONFIRMED"
    assert _score("ARBITRATION-MSA-001", footnote) == 3

    # The real clause still maps, on two independent signals rather than one.
    real = ("such differences and disputes shall be referred, at the option of "
            "either Party, to arbitration by a single arbitrator")
    assert _state("ARBITRATION-MSA-001", real) == "CONFIRMED"

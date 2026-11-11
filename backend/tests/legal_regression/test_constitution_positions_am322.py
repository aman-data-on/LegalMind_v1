"""AM-322 (owner go, 2026-11-09): the Constitution positions that had no standard file —
§12 data residency, breach notification and sub-processors, §15's trade-secret survival
on an MSA, §31.14 assignment and change of control per family. Each is proved on wording
built from the Constitution's own words or our own published paper (a short cited excerpt,
54.6), never a client's. Absence is MISSING only inside the declared family (AM-51)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures

ROOT = Path(__file__).resolve().parents[3]
STANDARDS = ROOT / "backend" / "config" / "company_standards"
CANONICAL = ROOT / "docs" / "02-legal-domain" / "LEGAL_CONSTITUTION_L1.16.md"
NEW = ("DATA-RESIDENCY-MSA-001", "DATA-RESIDENCY-VENDOR_AGREEMENT-001",
       "BREACH-NOTIFICATION-MSA-001", "BREACH-NOTIFICATION-TOS-001",
       "SUB-PROCESSORS-MSA-001", "SUB-PROCESSORS-TOS-001",
       "TRADE-SECRET-CARVEOUT-MSA-001", "ASSIGNMENT-MSA-001",
       "ASSIGNMENT-VENDOR_AGREEMENT-001", "ASSIGNMENT-PARTNER_AGREEMENT-001",
       "ASSIGNMENT-DISTRIBUTION_AGREEMENT-001",
       "CHANGE-OF-CONTROL-TERMINATION-PARTNER_AGREEMENT-001",
       "CHANGE-OF-CONTROL-NOTICE-VENDOR_AGREEMENT-001",
       "CHANGE-OF-CONTROL-NOTICE-DISTRIBUTION_AGREEMENT-001")
FILLER = ["1. Services", "1.1 The Provider shall provide the Services described in the "
          "Order.", "2. Fees", "2.1 The fees are stated in the Order."]


@pytest.mark.parametrize("code", NEW)
def test_every_new_position_quotes_the_canonical_constitution_verbatim(code):
    text = CANONICAL.read_text().replace("\\&", "&")
    payload = json.loads((STANDARDS / f"{code}.json").read_text())
    cfg = payload["configuration"]
    for part in payload["source_quote"].split(" ... "):
        assert part in text, (code, part)
    if cfg.get("unacceptable_position"):
        assert cfg["unacceptable_position"] in text, code
    assert cfg["constitution"]["version"] == "L1.16"
    assert payload["legal_rule"]["configuration"] == {
        "deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE"}


def _one(build, db, code: str, kind: str, *clauses: str) -> str | None:
    review, _ = _review(build, db, [code], [*FILLER, *clauses], kind=kind)
    return _findings(db, review).get(code, {}).get("classification")


# ------------------------------------------------------------------- §12 data residency
# AM-322 r11: a §12 qualitative position is presence-only — absence is MISSING, a clause
# found is for a person (UNABLE_TO_EVALUATE), never MATCH (rule 15). Each list below is a
# verifier's attack that a word-reading rule once returned as Accepted.
def test_a_residency_commitment_found_is_read_by_a_person(build, db):
    assert _one(build, db, "DATA-RESIDENCY-MSA-001", "MSA", "3. Data Protection",
                "3.1 Data residency for India-designated services is maintained within "
                "India.") == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("clause", [
    "Customer may choose to host its data in data centres within India, the United "
    "States or Europe.",
    "Leapswitch may transfer customer data outside India to its sub-processors; backups "
    "are kept within India.",
    "Any dispute about data shall be resolved by courts within India.",
    "Data residency is within India, but Leapswitch may transfer data to other countries "
    "at its discretion.",
])
def test_on_topic_wording_without_the_residency_commitment_is_never_a_match(build, db,
                                                                            clause):
    assert _one(build, db, "DATA-RESIDENCY-MSA-001", "MSA", "3. Data", clause) \
        != "MATCH"


def test_an_msa_with_no_residency_commitment_is_missing_it(build, db):
    assert _one(build, db, "DATA-RESIDENCY-MSA-001", "MSA") == "MISSING"


def test_log_retention_within_india_is_not_a_residency_commitment(build, db):
    # §12 keeps system logs (a CERT-In duty) apart from where customer data resides
    assert _one(build, db, "DATA-RESIDENCY-MSA-001", "MSA",
                "3. Logs", "3.1 ICT system logs are kept for a rolling period within "
                "India.") == "MISSING"


def test_a_vendor_paper_is_held_to_the_same_residency_position(build, db):
    assert _one(build, db, "DATA-RESIDENCY-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT") \
        == "MISSING"


# --------------------------------------------------------------- §12 breach notification
OUR_TOS_BREACH = ("Breach Notification: Leapswitch will notify you without undue delay "
                  "upon becoming aware of a personal data breach affecting your "
                  "customer-hosted data.")


def test_our_published_breach_wording_is_read_by_a_person(build, db):
    # AM-322 r11: our own TOS too — found, not MISSING; a person confirms it
    assert _one(build, db, "BREACH-NOTIFICATION-TOS-001", "TOS", "4. Data Protection",
                OUR_TOS_BREACH) == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("heading,clause", [
    ("7. Termination", "7.1 If either party commits a material breach, the other shall "
     "notify it in writing and allow 72 hours to cure the breach, failing which it may "
     "give notification of termination."),
    ("Breach Notification", "Provider will notify Customer of a personal data breach at "
     "its discretion."),
    ("4. Data Protection", "4.1 The Provider will notify the Customer of a personal data "
     "breach affecting the Customer's data."),
])
def test_a_breach_clause_without_a_notification_timeline_is_never_a_match(build, db,
                                                                         heading, clause):
    # §12 Unacceptable: "no defined breach-notification timeline at all"
    assert _one(build, db, "BREACH-NOTIFICATION-MSA-001", "MSA", heading, clause) \
        != "MATCH"


def test_cert_in_reporting_alone_is_not_customer_breach_notification(build, db):
    # §12.3: statutory reporting to CERT-In and customer notification are separate
    assert _one(build, db, "BREACH-NOTIFICATION-MSA-001", "MSA", "4. Incident Reporting",
                "4.1 The Provider reports cyber security incidents to CERT-In within six "
                "(6) hours of detection.") == "MISSING"


# ------------------------------------------------------------------- §12 sub-processors
def test_sub_processors_disclosed_and_bound_are_read_by_a_person(build, db):
    assert _one(build, db, "SUB-PROCESSORS-MSA-001", "MSA", "4. Data Protection",
                "4.2 Sub-processors are disclosed to the Customer and bound to "
                "obligations no less protective than this Agreement.") \
        == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("clause", [
    "Provider may engage any sub-processors without notice to or consent of the Customer "
    "and shall have no liability for them.",
    # our published TOS lists them but does not say they are bound: a person decides
    "Sub-Processors: Leapswitch may engage sub-processors as listed in our Privacy "
    "Policy. We will notify you of any changes to sub-processors that directly affect "
    "the processing of your data.",
])
def test_sub_processors_not_both_disclosed_and_bound_are_never_a_match(build, db, clause):
    assert _one(build, db, "SUB-PROCESSORS-TOS-001", "TOS", "4. Data Protection",
                clause) == "UNABLE_TO_EVALUATE"


def test_an_msa_naming_no_sub_processors_is_missing_them(build, db):
    assert _one(build, db, "SUB-PROCESSORS-MSA-001", "MSA") == "MISSING"


def test_a_dpa_is_not_measured_until_the_owner_rules(build, db):
    # C-31: Constitution §12.2 vs AM-73 r1 / AM-244 — today's behaviour kept
    assert _one(build, db, "BREACH-NOTIFICATION-MSA-001", "DPA",
                "4. Data Protection", OUR_TOS_BREACH) is None


# --------------------------------------------------------- §15 trade secrets on an MSA
SURVIVAL = ("5.3 Obligations under this Clause shall survive for a period of three (3) "
            "years post-termination")


def test_an_msa_keeping_trade_secrets_while_they_remain_so_states_section_15(build, db):
    assert _one(build, db, "TRADE-SECRET-CARVEOUT-MSA-001", "MSA", "5. Confidentiality",
                SURVIVAL + ", provided that obligations relating to trade secrets shall "
                "survive for as long as such information remains a trade secret under "
                "applicable law.") == "MATCH"


def test_an_msa_where_trade_secrets_expire_with_the_three_years_is_missing_it(build, db):
    assert _one(build, db, "TRADE-SECRET-CARVEOUT-MSA-001", "MSA", "5. Confidentiality",
                SURVIVAL + ".") == "MISSING"


def test_protecting_only_labelled_trade_secrets_narrows_section_15(build, db):
    assert _one(build, db, "TRADE-SECRET-CARVEOUT-MSA-001", "MSA", "5. Confidentiality",
                SURVIVAL + "; information expressly identified as a trade secret remains "
                "protected for so long as it remains a trade secret.") == "DEVIATION"


# ------------------------------------------------------------- §31.14 assignment / control
def test_our_msa_assignment_to_affiliates_and_successors_states_the_position(build, db):
    assert _one(build, db, "ASSIGNMENT-MSA-001", "MSA", "21. Assignment",
                "21.1 Assignment: The Customer shall not assign this Agreement without the "
                "prior written consent of Leapswitch. Leapswitch may assign this "
                "Agreement to any of its Affiliates or successors on notice to the "
                "Customer.") == "MATCH"


def test_the_parties_successors_and_permitted_assigns_is_not_an_assignment_clause(build,
                                                                                  db):
    # breaks the standard if "assigns" + "successors" in the preamble confirmed it
    assert _one(build, db, "ASSIGNMENT-MSA-001", "MSA",
                "Leapswitch (which expression shall include its affiliates, successors and "
                "permitted assigns) of the FIRST PART.") != "MATCH"


@pytest.mark.parametrize("code,kind,clause", [
    ("ASSIGNMENT-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT",
     "9.1 Assignment: the Vendor may not assign this Agreement without the Company's "
     "consent; the Company may assign it to an affiliate or successor."),
    ("ASSIGNMENT-PARTNER_AGREEMENT-001", "PARTNER_AGREEMENT",
     "9.1 Assignment: the Partner may not assign the agreement without the Company's "
     "prior written consent; the Company may assign it to an affiliate or an acquirer "
     "with notice to the Partner."),
    ("ASSIGNMENT-DISTRIBUTION_AGREEMENT-001", "DISTRIBUTION_AGREEMENT",
     "9.1 Assignment: neither party may assign its rights without consent, and this "
     "Agreement binds each party's successor."),
    ("CHANGE-OF-CONTROL-TERMINATION-PARTNER_AGREEMENT-001", "PARTNER_AGREEMENT",
     "9.2 Either party may terminate this Agreement immediately if the other party "
     "undergoes a change of control that adversely affects its ability to perform, "
     "with notice of the reason."),
])
def test_each_family_states_its_own_section_31_14_position(build, db, code, kind, clause):
    assert _one(build, db, code, kind, "9. Assignment and Change of Control", clause) \
        == "MATCH"


@pytest.mark.parametrize("code,kind", [
    ("ASSIGNMENT-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT"),
    ("ASSIGNMENT-PARTNER_AGREEMENT-001", "PARTNER_AGREEMENT"),
    ("ASSIGNMENT-DISTRIBUTION_AGREEMENT-001", "DISTRIBUTION_AGREEMENT"),
    ("CHANGE-OF-CONTROL-TERMINATION-PARTNER_AGREEMENT-001", "PARTNER_AGREEMENT"),
])
def test_a_family_paper_silent_on_its_section_31_14_position_is_missing_it(build, db,
                                                                           code, kind):
    assert _one(build, db, code, kind) == "MISSING"


@pytest.mark.parametrize("code,kind", [
    ("CHANGE-OF-CONTROL-NOTICE-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT"),
    ("CHANGE-OF-CONTROL-NOTICE-DISTRIBUTION_AGREEMENT-001", "DISTRIBUTION_AGREEMENT"),
])
@pytest.mark.parametrize("days,result", [("thirty (30)", "MATCH"),
                                         ("sixty (60)", "DEVIATION")])  # told later
def test_a_change_of_control_notice_is_measured_against_thirty_days(build, db, code, kind,
                                                                    days, result):
    assert _one(build, db, code, kind, "10. Change of Control",
                f"10.1 The other party shall provide notice of a change of control "
                f"within {days} days.") == result


def test_a_privacy_policy_is_not_measured_against_section_12(build, db):
    # AM-73 r1: a published policy states no position of its own to measure
    assert _one(build, db, "BREACH-NOTIFICATION-MSA-001", "PRIVACY_POLICY",
                "13. Data Breach Notification", OUR_TOS_BREACH) is None


# ------------------------------------- AM-322 r10/r11: elements stated, then taken back
# Round-2 independent verifier (2026-11-09): each clause below states the §12 elements in
# the Constitution's own words and then negates, permits or conditions them — 17 came
# back Accepted. Every one is for a person (rule 15); none is a new position.
TAKEN_BACK = [
    # §12 data residency (Unacceptable: "no data-residency commitment")
    ("DATA-RESIDENCY-MSA-001", "MSA", "Data residency within India is not guaranteed."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "Customer data shall have data residency outside India."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "Provider makes no commitment as to data residency in India."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "Data residency: Customer data is hosted in India, Singapore or the United States at "
     "Provider's option."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "Data residency is in India except where Provider elects otherwise."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "For India-designated services, data residency is not limited to India."),
    ("DATA-RESIDENCY-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT",
     "The Vendor gives no data residency commitment for India-designated services."),
    # §12 breach notification (Unacceptable: no defined breach-notification timeline)
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Provider shall notify Customer of any personal data breach within 72 hours where "
     "Provider deems appropriate."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Provider is not required to notify Customer of a personal data breach without undue "
     "delay or within any number of hours."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Provider may, but shall not be obliged to, notify Customer of a personal data breach "
     "without undue delay."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Customer shall notify Provider of any personal data breach without undue delay and "
     "in any event within 24 hours. Provider gives no notification of a personal data "
     "breach."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Provider will notify Customer of a personal data breach without undue delay or at a "
     "time of its choosing, which may exceed 720 hours."),
    ("BREACH-NOTIFICATION-TOS-001", "TOS",
     "Breach Notification: we may notify you of a personal data breach without undue "
     "delay, or not at all."),
    # §12 sub-processors ("disclosed and bound to obligations no less protective")
    ("SUB-PROCESSORS-MSA-001", "MSA",
     "Provider shall not disclose its sub-processors and sub-processors shall not be bound "
     "by obligations no less protective than this Agreement."),
    ("SUB-PROCESSORS-MSA-001", "MSA",
     "Sub-processors are disclosed only on request, and are bound to obligations no less "
     "protective than this Agreement."),
    ("SUB-PROCESSORS-MSA-001", "MSA",
     "Provider need not disclose sub-processors; obligations no less protective than this "
     "Agreement apply only to Provider."),
    ("SUB-PROCESSORS-TOS-001", "TOS",
     "Sub-Processors: sub-processors may be disclosed at Leapswitch's discretion; "
     "obligations no less protective than these Terms are not assured."),
]


@pytest.mark.parametrize("code,kind,clause", TAKEN_BACK)
def test_elements_negated_permitted_or_conditioned_are_for_a_person(build, db, code, kind,
                                                                    clause):
    assert _one(build, db, code, kind, "4. Data Protection", clause) \
        == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("code,kind,clauses", [
    # each element present, but no ONE clause states them all
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     ("4. Data Protection", "4.1 The Provider will notify the Customer of a personal data "
      "breach.", "5. Support", "5.1 Support requests are answered without undue delay.")),
    ("SUB-PROCESSORS-MSA-001", "MSA",
     ("4. Data Protection", "4.1 Sub-processors are disclosed to the Customer.",
      "5. Security", "5.1 Each party applies safeguards no less protective than industry "
      "practice.")),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     ("4. Data Residency", "4.1 Data residency is as stated in the Order.",
      "5. Location", "5.1 The Provider's offices are in India.")),
])
def test_elements_split_across_clauses_stay_for_a_person(build, db, code, kind, clauses):
    assert _one(build, db, code, kind, *clauses) == "UNABLE_TO_EVALUATE"


def test_an_hours_figure_alone_is_not_the_customer_notice_timeline(build, db):
    # §12.3: the hours deadline is CERT-In's; none is assumed for the customer
    assert _one(build, db, "BREACH-NOTIFICATION-MSA-001", "MSA", "4. Data Protection",
                "4.1 Provider shall notify Customer of any personal data breach within 72 "
                "hours.") == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("code,kind,clause", [
    ("DATA-RESIDENCY-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT",
     "Data residency is maintained within India for all India-designated services."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Provider shall notify Customer of any Personal Data Breach affecting Customer's data "
     "without undue delay after becoming aware of it."),
    ("SUB-PROCESSORS-TOS-001", "TOS",
     "Sub-processors must be disclosed and bound to obligations no less protective than "
     "this policy."),
])
def test_even_the_constitutions_own_wording_is_read_by_a_person(build, db, code, kind,
                                                               clause):
    assert _one(build, db, code, kind, "4. Data Protection", clause) \
        == "UNABLE_TO_EVALUATE"


# ------------------------------------------ AM-322 r10/r11: the duty runs the wrong way
# r10 read these as "the duty on the other side"; r11 withdrew that reading (§12 does not
# say which party commits). Under r11 every one is found and read by a person.
@pytest.mark.parametrize("code,kind,clause", [
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Customer shall notify Provider of any personal data breach without undue delay."),
    ("BREACH-NOTIFICATION-TOS-001", "TOS",
     "You shall notify Leapswitch of any personal data breach without undue delay."),
    ("SUB-PROCESSORS-MSA-001", "MSA",
     "Customer shall disclose its sub-processors and bind them to obligations no less "
     "protective than this Agreement."),
    ("SUB-PROCESSORS-TOS-001", "TOS",
     "You shall disclose your sub-processors and bind them to obligations no less "
     "protective than these Terms."),
    ("DATA-RESIDENCY-MSA-001", "MSA",
     "Customer shall maintain data residency within India for all India-designated "
     "services."),
    ("DATA-RESIDENCY-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT",
     "LeapSwitch shall maintain data residency within India for India-designated "
     "services."),
])
def test_elements_on_the_other_side_are_for_a_person(build, db, code, kind, clause):
    assert _one(build, db, code, kind, "4. Data Protection", clause) \
        == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("code,kind,clause", [
    ("DATA-RESIDENCY-VENDOR_AGREEMENT-001", "VENDOR_AGREEMENT",
     "The Vendor shall maintain data residency within India for all India-designated "
     "services."),
    ("BREACH-NOTIFICATION-MSA-001", "MSA",
     "Each party shall notify the other of any personal data breach without undue delay."),
])
def test_the_providing_side_or_both_sides_are_read_by_a_person(build, db, code, kind,
                                                              clause):
    assert _one(build, db, code, kind, "4. Data Protection", clause) \
        == "UNABLE_TO_EVALUATE"


# ----------------------------------------------- AM-322 r11: the round-3 verifier's attacks
# 45 sentences (independent verifier, 2026-11-09); 41 beat r10's word lists. Qualifiers,
# negations and back-references off any list, unknown or shifted actors, and element words
# borrowed from the CERT-In duty (§12.3). Each is for a person — and so is sound wording.
DR, DRV = "DATA-RESIDENCY-MSA-001", "DATA-RESIDENCY-VENDOR_AGREEMENT-001"
BN, BNT = "BREACH-NOTIFICATION-MSA-001", "BREACH-NOTIFICATION-TOS-001"
SP, SPT = "SUB-PROCESSORS-MSA-001", "SUB-PROCESSORS-TOS-001"
SUBS = ('This Agreement is made between LeapSwitch Networks Private Limited (the '
        '"Provider") and Acme Retail Private Limited (the "Subscriber").')
VCO = ('This Agreement is made between LeapSwitch Networks Private Limited (the "Company") '
       'and Acme Cloud Private Limited (the "Vendor").')
DRS = "Data residency is maintained within India for all India-designated services"
BNS = "Provider shall notify Customer of any personal data breach without undue delay"
SPS = ("Sub-processors are disclosed to the Customer and bound to obligations no less "
       "protective than this Agreement")
ROUND_3 = [
    (DR, "MSA", [f"{DRS} save as otherwise agreed by Provider."]),
    (DR, "MSA", [f"{DRS} to the extent commercially practicable for Provider."]),
    (DR, "MSA", [f"{DRS}. This commitment shall not apply where Provider considers it "
                 "necessary."]),
    (DR, "MSA", [f"{DRS}; however, Provider reserves the right to relocate any data at any "
                 "time."]),
    (DR, "MSA", ["Nothing herein obliges Provider to maintain data residency within India "
                 "for India-designated services."]),
    (DR, "MSA", ["Provider disclaims any obligation to maintain data residency within India "
                 "for India-designated services."]),
    (DR, "MSA", [f"{DRS}, other than data Provider designates for global hosting."]),
    (DR, "MSA", [f"{DRS} until Provider gives notice otherwise."]),
    (DR, "MSA", [f"4.1 {DRS}.", "4.2 Clause 4.1 shall not apply to backups, replicas or "
                 "disaster-recovery copies."]),
    (DR, "MSA", [f"4.1 (a) {DRS} (b) the commitment in (a) lapses on renewal."]),
    (DR, "MSA", ["It is not the case that Provider does not maintain data residency within "
                 "India."]),
    (DR, "MSA", [SUBS, "The Subscriber shall maintain data residency within India for all "
                 "India-designated services."]),
    (DR, "MSA", ["Provider shall require Customer to maintain data residency within India "
                 "for all India-designated services."]),
    (DRV, "VENDOR_AGREEMENT", [VCO, "The Company shall maintain data residency within India "
                               "for all India-designated services."]),
    (DRV, "VENDOR_AGREEMENT", ["The Company shall maintain data residency within India for "
                               "all India-designated services."]),
    (DRV, "VENDOR_AGREEMENT", ["The Vendor shall host the platform, and LeapSwitch shall "
                               "maintain data residency within India for all "
                               "India-designated services."]),
    (DRV, "VENDOR_AGREEMENT", ["The Vendor shall ensure that LeapSwitch maintains data "
                               "residency within India for all India-designated services."]),
    (DRV, "VENDOR_AGREEMENT", ["The Vendor shall maintain data residency within India for "
                               "all India-designated services save as the Vendor otherwise "
                               "determines."]),
    (DRV, "VENDOR_AGREEMENT", ["Users of the Vendor platform shall maintain data residency "
                               "within India for all India-designated services."]),
    (BN, "MSA", [f"{BNS} to the extent permitted by Provider's internal policies."]),
    (BN, "MSA", [f"{BNS}. This clause shall not bind Provider in any respect."]),
    (BN, "MSA", [f"{BNS}; Customer hereby waives the foregoing obligation."]),
    (BN, "MSA", ["Nothing in this Agreement requires Provider to notify Customer of any "
                 "personal data breach without undue delay."]),
    (BN, "MSA", ["Provider disclaims any duty to notify Customer of any personal data breach "
                 "without undue delay."]),
    (BN, "MSA", ["Provider shall require Customer to notify Provider of any personal data "
                 "breach without undue delay."]),
    (BN, "MSA", [f"{BNS} save as Provider's insurers direct otherwise."]),
    (BN, "MSA", [SUBS, "The Subscriber shall notify the Provider of any personal data breach "
                 "without undue delay."]),
    # §12.3: "without undue delay" here is the CERT-In report, not the customer's notice
    (BN, "MSA", ["Provider shall notify Customer of the incident in writing; any personal "
                 "data breach is reported without undue delay to CERT-In."]),
    (BN, "MSA", [f"4.1 {BNS}.", "4.2 Clause 4.1 does not apply to data hosted on shared "
                 "infrastructure."]),
    (BN, "MSA", [f"{BNS}, where practicable."]),
    (BN, "MSA", [f"{BNS} only where Provider is legally compelled to do so."]),
    (BN, "MSA", ["Provider shall not fail to notify Customer of any personal data breach "
                 "without undue delay."]),
    (BNT, "TOS", ["We will notify you of any personal data breach without undue delay where "
                  "we consider it appropriate."]),
    (BNT, "TOS", ["You will notify us of any personal data breach without undue delay."]),
    (BNT, "TOS", ["Leapswitch's customers shall notify Leapswitch of any personal data "
                  "breach without undue delay."]),
    (BNT, "TOS", ["Users of the Services shall notify Leapswitch of any personal data breach "
                  "without undue delay."]),
    (SP, "MSA", [f"{SPS}, save as Provider otherwise determines."]),
    (SP, "MSA", [f"{SPS}. This clause is of no effect for Provider's affiliates."]),
    (SP, "MSA", [f"{SPS} to the extent Provider is able to negotiate such terms."]),
    (SP, "MSA", ["Sub-processors are disclosed to the Customer; Provider shall use "
                 "reasonable efforts to bind them to obligations no less protective than "
                 "this Agreement."]),
    (SP, "MSA", ["Provider disclaims any duty to ensure that sub-processors, which are "
                 "disclosed to the Customer, are bound by obligations no less protective "
                 "than this Agreement."]),
    (SP, "MSA", [SUBS, "The Subscriber shall disclose its sub-processors and bind them to "
                 "obligations no less protective than this Agreement."]),
    (SP, "MSA", ["Sub-processors other than Provider's affiliates are disclosed to the "
                 "Customer and bound to obligations no less protective than this "
                 "Agreement."]),
    (SPT, "TOS", ["Your sub-processors must be disclosed to Leapswitch and bound to "
                  "obligations no less protective than these Terms."]),
    (SPT, "TOS", ["Sub-processors are disclosed in our Privacy Policy and bound to "
                  "obligations no less protective than these Terms, save as we otherwise "
                  "decide."]),
]
SOUND = [  # the verifier's controls: sound wording, still a person's call
    (BN, "MSA", ["Provider shall notify Customer without undue delay if it becomes aware of "
                 "a personal data breach affecting Customer's data."]),
    (SP, "MSA", ["Provider may engage sub-processors provided that they are disclosed to the "
                 "Customer and bound to obligations no less protective than this "
                 "Agreement."]),
    (DR, "MSA", ["Customer's data residency is maintained within India for all "
                 "India-designated services."]),
    (SP, "MSA", ["Each sub-processor is disclosed in Annex 3 and bound by obligations no "
                 "less protective than this Agreement."]),
    (BNT, "TOS", ["We will notify you of any personal data breach without undue delay."]),
    (DRV, "VENDOR_AGREEMENT", [VCO, "The Vendor shall maintain data residency within India "
                               "for all India-designated services."]),
]


@pytest.mark.parametrize("code,kind,paragraphs", ROUND_3 + SOUND)
def test_a_section_12_clause_found_is_never_matched_by_its_words(build, db, code, kind,
                                                                 paragraphs):
    lead = paragraphs[:1] if paragraphs[0] in (SUBS, VCO) else []
    body = paragraphs[len(lead):]
    assert _one(build, db, code, kind, *lead, "4. Data Protection", *body) \
        == "UNABLE_TO_EVALUATE"


# ------------------------------------- AM-322 r12: the person is shown the whole section
def _cited(build, db, code: str, kind: str, *clauses: str) -> set:
    review, _ = _review(build, db, [code], [*FILLER, *clauses], kind=kind)
    return {s for s, _ in _findings(db, review)[code]["cited"]}


def test_a_split_residency_clause_cites_its_operative_sub_clause(build, db):
    assert "3.2" in _cited(build, db, "DATA-RESIDENCY-MSA-001", "MSA", "3. Data Residency",
                           "3.1 This clause sets out data residency.",
                           "3.2 Customer Data is stored only in India.", "4. Fees",
                           "4.1 Fees are stated in the Order.")


def test_a_split_breach_clause_cites_its_operative_sub_clause(build, db):
    cited = _cited(build, db, "BREACH-NOTIFICATION-TOS-001", "TOS", "10. Security",
                   "10.1 A personal data breach means a breach of security leading to "
                   "unauthorised access to personal data, notified without undue delay.",
                   "10.2 We will tell you without undue delay.", "11. Fees",
                   "11.1 Fees are stated in the Order.")
    assert "10.2" in cited and not {"11", "11.1"} & cited


# ------------------------------------- AM-322 r13: owner-approved finding terms (2026-11-11)
# Each term is quoted from our own paper (AM322-PROPOSED-TERMS R1, R2, B1, B2, S1, S2, S4).
# A term only FINDS a clause; under r11 what is found is a person's call, never MATCH.
@pytest.mark.parametrize("code,kind,heading,clause", [
    (DR, "MSA", "11. Data Protection", "11.5 Cross-Border Data Transfers: If Personal Data is "
     "transferred outside the jurisdiction in which it was originally collected (including "
     "cross-border transfers from India), Provider shall ensure such transfers are lawful."),
    (DR, "MSA", "11. Data Protection", "11.5 Personal Data transferred outside India is "
     "protected by standard contractual clauses."),
    (BN, "MSA", "Data Breach Notification", "Provider will tell Customer promptly."),
    (BN, "MSA", "4. Security", "4.1 Provider shall notify Customer of any data breach."),
    (SP, "MSA", "11. Data Protection", "11.4 Sharing with Affiliates, Business Partners and "
     "Third-Party Processors: Provider may disclose Personal Data to its affiliates."),
    (SP, "MSA", "18. Assignment", "18.2 Provider may upon notice to Customer engage a "
     "subcontractor to provide Services to Customer."),
    (SPT, "TOS", "21. General", "21.1 Third Party Service Providers: Leapswitch may use "
     "third-party service providers for rendering Services."),
])
def test_an_approved_finding_term_sends_the_clause_to_a_person(build, db, code, kind,
                                                              heading, clause):
    assert _one(build, db, code, kind, heading, clause) == "UNABLE_TO_EVALUATE"


@pytest.mark.parametrize("code,kind,clause", [
    # rejected or conditioned terms alone find nothing (R5, B2 without "notify", B3, S3)
    (DR, "MSA", "1.1 “Territory” means the territory of India."),
    (BN, "MSA", "9.1 LeapSwitch disclaims all liability for any security incident or data "
     "breach caused by Customer content."),
    (SP, "MSA", "13.1 The total liability of Provider, its employees, subcontractors or "
     "suppliers shall not exceed the fees paid."),
])
def test_a_rejected_term_alone_still_finds_nothing(build, db, code, kind, clause):
    assert _one(build, db, code, kind, "9. General", clause) == "MISSING"


_SRC = Path(os.environ.get("LEGALMIND_SOURCE_MATERIAL_DIR", ROOT / "legal-docs"))


def _real(build, db, name: str, codes: list[str]) -> dict:
    from legalmind.analysis.service import run_analysis
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    from legalmind.ingestion.service import ingest_document
    from tests.test_hard_test_fixes import _ratified
    for code in codes:
        _ratified(build, code)
    contract = M.Contract(owner_id=build.owner.id, name="MSA", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    result = ingest_document(db, build.storage, contract_id=contract.id,
                             uploaded_by=build.owner.id, data=(_SRC / name).read_bytes(),
                             filename=name, declared_mime="application/pdf")
    review = M.Review(contract_id=contract.id, document_version_id=result.document_version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    run_analysis(db, review)
    return _findings(db, review)


@pytest.mark.skipif(not (_SRC / "MSA.pdf").is_file(),
                    reason="source material is gitignored (54.6); present on the server only")
def test_our_msa_cross_border_and_third_party_processors_go_to_a_person(build, db):
    found = _real(build, db, "MSA.pdf", [DR, SP])
    assert found[DR]["classification"] == "UNABLE_TO_EVALUATE"
    assert "11.5" in {s for s, _ in found[DR]["cited"]}
    assert found[SP]["classification"] == "UNABLE_TO_EVALUATE"
    assert "11.4" in {s for s, _ in found[SP]["cited"]}


@pytest.mark.skipif(not (_SRC / "MSA-GRP-2026-07-30.pdf").is_file(),
                    reason="source material is gitignored (54.6); present on the server only")
def test_an_msa_engaging_a_subcontractor_goes_to_a_person(build, db):
    found = _real(build, db, "MSA-GRP-2026-07-30.pdf", [SP])[SP]
    assert found["classification"] == "UNABLE_TO_EVALUATE"
    assert "18.2" in {s for s, _ in found["cited"]}


def test_the_cited_section_stops_before_the_signature_block(build, db):
    cited = _cited(build, db, "DATA-RESIDENCY-MSA-001", "MSA", "3. Data Residency",
                   "3.1 This clause sets out data residency.",
                   "3.2 Customer Data is stored only in India.",
                   "IN WITNESS WHEREOF the Parties have executed this Agreement.",
                   "Date of sign")
    assert {"3.1", "3.2"} <= cited and None not in cited


@pytest.mark.parametrize("code,kind,clauses", [
    # AM-322 r15: a "Title Case:" label with its own sentence is the section's text
    (DR, "MSA", ("3. Data Protection", "3.1 This clause sets out data residency.",
                 "Storage Location: All Customer Data shall be stored only in India.")),
    (BNT, "TOS", ("10. Security", "10.1 A personal data breach means a breach of security "
                  "leading to unauthorised access to personal data.",
                  "Notice To You: We will tell you without undue delay.")),
])
def test_a_labelled_operative_sentence_stays_in_the_cited_section(build, db, code, kind,
                                                                  clauses):
    assert None in _cited(build, db, code, kind, *clauses, "11. Fees",
                          "11.1 Fees are stated in the Order.")


def test_the_take_back_is_cited_and_the_signature_block_is_not(build, db):
    # AM-322 r16 (verifier's probe): "Exceptions" is no end of section 6 — its take-back
    # is exactly what the person must read
    review, _ = _review(build, db, [SP], [*FILLER, "6. Sub-processors",
                        "6.1 Sub-processors are disclosed to the Customer and bound to "
                        "obligations no less protective than this Agreement.",
                        "Exceptions", "This clause does not apply to affiliates of Provider.",
                        "IN WITNESS WHEREOF the Parties have executed this Agreement.",
                        "By: ____"], kind="MSA")
    from sqlalchemy import select

    from legalmind.db import models as M
    finding = db.execute(select(M.Finding).where(M.Finding.review_id == review.id)).scalars()
    texts = {e.content for f in finding for e in db.execute(
        select(M.DocumentEvidence).join(
            M.FindingEvidence, M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
        .where(M.FindingEvidence.finding_id == f.id)).scalars()}
    joined = " ".join(texts)
    assert "does not apply to affiliates" in joined
    assert "IN WITNESS" not in joined and "By: ____" not in joined


@pytest.mark.parametrize("row,ends", [
    ("IN WITNESS WHEREOF the Parties have executed this Agreement.", True),
    ("20 IN WITNESS WHEREOF the Parties have executed this Agreement.", True),
    ("Signed by LeapSwitch Networks for and on behalf of the Provider", True),
    ("For and on behalf of the Customer", True),
    ("Name: ____", True),
    ("Signed by either party, a waiver of this clause is binding.", False),
    ("Exceptions", False),
    ("Storage Location: All Customer Data shall be stored only in India.", False),
])
def test_only_a_signature_block_ends_a_cited_section(row, ends):
    from legalmind.analysis.service import _ends_section
    assert _ends_section(row) is ends

"""AM-54 R&D evaluation — LIVE, against the real generation model.

A labelled corpus of materially different drafting styles (synonyms, reordered
sentences, equivalent unit expressions, cross-references, table rows,
sub-clauses, contextual wording) plus hard negatives (similar terminology,
different obligation) for 19 ratified standards across every finding type and
all three families. Each variant is analysed twice through `run_analysis`: with
the semantic stage and lexical-only. The report counts recognition TP/FN, false
positives, fail-safes, and — the gate — cases where the semantic stage changed a
result the lexical engine already had right.

Skipped unless LEGALMIND_RD_LIVE=1, a generation credential is configured and the
local embedding model is provisioned. Every clause below is synthetic (rule 21).
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from legalmind.analysis import semantic
from legalmind.analysis.service import run_analysis
from legalmind.assist import embedding_runtime, generation
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_analysis import build, build_docx, storage  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("LEGALMIND_RD_LIVE") != "1" or not generation.credential_present()
    or not embedding_runtime.available(),
    reason="live R&D: needs LEGALMIND_RD_LIVE=1, a generation credential and the embedding model")

STD = pathlib.Path(__file__).resolve().parents[1] / "config" / "company_standards"
REPORT = pathlib.Path(os.environ.get("LEGALMIND_RD_REPORT", "/tmp/am54-corpus-report.md"))

# (kind, paragraphs, expected classification or None = "fail-safe acceptable")
# Negatives: kind starts with "neg".
CORPUS: dict[str, list[tuple[str, list[str], str | None]]] = {
 "LIABILITY-MSA-001": [
  ("synonym", ["9. Cap on Damages", "Neither party's cumulative liability arising out of this Agreement, whatever the cause of action, may exceed the total fees paid by the Customer in the twelve months before the event giving rise to the claim."], "MATCH"),
  ("reordered", ["The total fees paid by the Customer during the twelve (12) months preceding the claim is the ceiling on each party's aggregate liability under this Agreement, however arising."], "MATCH"),
  ("units-year", ["9. Responsibility", "Each party's overall exposure under this Agreement is capped at one year of total fees paid by the Customer."], None),
  ("cross-reference", ["9.2 Subject to Section 9.3 (Exclusions), each party's liability in the aggregate is limited to the total amount paid by the Customer in the 12 months immediately before the claim."], "MATCH"),
  ("table", ["LIABILITY CAP | Total fees paid by Customer in the 12 (twelve) months preceding the claim | applies to all claims however arising"], "MATCH"),
  ("sub-clause", ["9.1 Liability.", "(a) Each party's aggregate liability under this Agreement is limited to (b) the total fees paid by the Customer (c) in the 12 months immediately preceding the event giving rise to the claim."], "MATCH"),
  ("contextual", ["Our responsibility to you for anything going wrong under this contract, and yours to us, is capped: the most either side pays the other is the total fees paid in the 12 months before the problem arose."], "MATCH"),
  ("genuine-difference", ["9. Cap on Damages", "Neither party's cumulative liability may be more than the total fees paid by the Customer in the six (6) months preceding the claim."], "DEVIATION"),
  ("neg-exclusions", ["9. Exclusion of Damages", "In no event shall either party be liable for indirect, incidental, consequential, special or punitive damages, or for loss of profits, revenue or data, however caused."], None),
  ("neg-fees", ["8. Fees", "The Customer shall pay the total fees set out in the Order Form within 30 days of invoice; fees paid are non-refundable."], None),
 ],
 "CURE-PERIOD-MSA-001": [
  ("synonym", ["15. Default", "If the Customer defaults on any obligation, Leapswitch may end this Agreement where the default is not remedied within 30 days after receipt of written notice describing it."], "MATCH"),
  ("reordered", ["Thirty (30) days after receipt of written notice of a breach, if the breach has still not been cured, the non-breaching party may terminate this Agreement."], "MATCH"),
  ("units-words", ["15.1 Either party may terminate for material breach that remains uncured thirty days after receipt of written notice of the breach."], "MATCH"),
  ("cross-reference", ["15.2 Without prejudice to Section 15.4, a party in breach shall have 30 days after receipt of written notice to cure it, failing which the other party may terminate."], "MATCH"),
  ("table", ["BREACH CURE PERIOD | 30 days after receipt of written notice | termination right thereafter"], "MATCH"),
  ("contextual", ["If one of us breaks this agreement, the other will say so in writing and the party at fault gets thirty days to fix it before the agreement can be ended."], None),
  ("genuine-difference", ["15. Default", "A breach not cured within 10 days after receipt of written notice entitles the other party to terminate."], "DEVIATION"),
  ("neg-payment-terms", ["8.2 Invoices are due 30 days after receipt; amounts unpaid after that date accrue interest."], None),
  ("neg-notice-of-claims", ["Claims under the warranty must be notified in writing within 30 days of discovery."], None),
 ],
 "FORCE-MAJEURE-MSA-001": [
  ("synonym", ["18. Events Beyond Control", "Should an event of force majeure prevent performance for more than 60 consecutive days, either party may end this Agreement on written notice."], "MATCH"),
  ("reordered", ["Either party may terminate this Agreement by written notice where performance has been prevented by a force majeure event for a period longer than sixty (60) days."], "MATCH"),
  ("cross-reference", ["18.3 If a Force Majeure Event (as defined in Section 18.1) continues beyond 60 days, either party may terminate the affected Order by notice."], "MATCH"),
  ("table", ["FORCE MAJEURE | performance suspended for the duration | termination right after 60 days' continuance"], "MATCH"),
  ("genuine-difference", ["Where a force majeure event persists for more than ninety (90) days, either party may terminate."], "DEVIATION"),
  ("neg-fm-definition", ["18.1 Force Majeure Event means any event beyond a party's reasonable control including act of God, war, epidemic, governmental action or failure of utilities."], None),
  ("neg-sla-outage", ["Service outages exceeding 60 minutes in a month entitle the Customer to a service credit under the SLA."], None),
 ],
 "CONF-SURVIVAL-MSA-001": [
  ("synonym", ["12.4 The confidentiality undertakings in this Section remain binding for three years after termination of this Agreement."], "MATCH"),
  ("reordered", ["For a period of three (3) years after termination, each party shall continue to keep the other's Confidential Information confidential."], "MATCH"),
  ("units-words", ["The duty of confidence in this clause continues for three years from the date of termination of the Agreement."], "MATCH"),
  ("table", ["CONFIDENTIALITY SURVIVAL | 3 (three) years after termination"], "MATCH"),
  ("genuine-difference", ["12.4 The confidentiality obligations shall continue for five years after termination."], "DEVIATION"),
  ("neg-survival-generic", ["21.11 Survival: Clauses on payment, indemnity and governing law survive termination of this Agreement."], None),
  ("neg-term-of-agreement", ["7.1 This Agreement has an initial term of three years from the Service Commencement Date."], None),
 ],
 "AUTORENEW-MSA-001": [
  ("synonym", ["7.3 Rollover. Unless either party gives notice of non-renewal, this Agreement rolls over for further terms of six months each on the same conditions."], None),
  ("reordered", ["On expiry of the Term this Agreement shall automatically renew for successive periods of 6 months, unless terminated in accordance with this Section."], "MATCH"),
  ("table", ["RENEWAL | automatic | successive periods of six (6) months"], None),
  ("neg-renewal-of-licence", ["The Customer must renew its software licences with the third-party vendor annually."], None),
  ("neg-price-review", ["Charges are reviewed every six months and may be revised on 30 days' notice."], None),
 ],
 "GOVLAW-MSA-001": [
  ("synonym", ["19. Applicable Law", "This Agreement is subject to the laws of the Republic of India."], "MATCH"),
  ("reordered", ["The laws of India, without regard to conflict-of-laws principles, apply to this Agreement and to any dispute arising from it."], "MATCH"),
  ("cross-reference", ["19.1 Subject to Section 19.2 (Arbitration), this Agreement and any non-contractual obligations are to be interpreted under Indian law."], "MATCH"),
  ("table", ["LAW/FORUM | India | exclusive courts of Mumbai"], "MATCH"),
  ("contextual", ["Indian law governs this agreement. If we end up in court, it will be a court in Mumbai."], "MATCH"),
  ("neg-compliance-with-laws", ["20.1 Each party shall comply with all applicable laws, rules and regulations in performing this Agreement, including data-protection laws."], None),
  ("neg-definition", ["1.3 'Applicable Laws' means any law, statute, rule, regulation, order or circular of any Governmental Authority."], None),
 ],
 "INDEMNITY-MSA-001": [
  ("synonym", ["11. Protection against Claims", "The Customer will make good and keep Leapswitch, its officers and staff free from any loss, claim or expense arising from the Customer's use of the Services or breach of this Agreement."], "MATCH"),
  ("reordered", ["Against all third-party claims, losses and costs arising from its content or its breach, the Customer shall compensate and protect Leapswitch and its affiliates."], "MATCH"),
  ("sub-clause", ["11.1 The Customer shall (a) take over the defence of, (b) compensate, and (c) shield Leapswitch and its directors from any claim brought by a third party in connection with the Customer's use of the Services."], "MATCH"),
  ("neg-insurance", ["The Customer shall maintain public liability insurance of not less than INR 1 crore for the term."], None),
  ("neg-limitation", ["Each party's liability is capped at the total fees paid in the 12 months before the claim."], None),
 ],
 "RETURN-DESTRUCTION-MSA-001": [
  ("synonym", ["12.3 On request, the recipient shall hand back or erase every document and copy that embodies the other party's Confidential Information."], "MATCH"),
  ("reordered", ["All materials embodying Confidential Information shall, at the disclosing party's option, be given back or wiped by the receiving party within thirty days of a written request."], "MATCH"),
  ("contextual", ["Once we part ways, each side gives back or deletes the other's confidential information within thirty days of being asked."], "MATCH"),
  ("neg-data-purge", ["7.7 Thirty days after termination Leapswitch will purge all Customer data from its production systems and backups."], None),
  ("neg-return-of-equipment", ["On termination the Customer shall return all Leapswitch-owned hardware in good condition within 14 days."], None),
 ],
 "WARRANTY-DISCLAIMER-MSA-001": [
  ("synonym", ["14. No Guarantees", "Leapswitch gives no assurance that information, data or third-party applications made available through the Services are reliable, accurate, complete or useful."], "MATCH"),
  ("contextual", ["The Services are provided as they are. We do not promise that anything you access through them will be accurate, complete, dependable or fit for what you need."], "MATCH"),
  ("neg-performance-warranty", ["12.1 Leapswitch warrants that the Services will be performed in a competent and workmanlike manner consistent with industry standards."], None),
  ("neg-customer-warranty", ["9.1 The Customer represents and warrants that it has the legal right to use all content it uploads."], None),
 ],
 "LIAB-EXCLUSIONS-MSA-001": [
  ("synonym", ["9.3 Leapswitch shall have no responsibility for any loss that is not a direct result of its breach, including loss of business, revenue, anticipated savings, goodwill or data."], "MATCH"),
  ("reordered", ["Loss of profit, loss of data and every other indirect or consequential loss are excluded from Leapswitch's liability under this Agreement."], "MATCH"),
  ("neg-cap", ["Leapswitch's aggregate liability shall not exceed the total fees paid in the 12 months preceding the claim."], None),
  ("neg-carveouts", ["The limitations in this Section do not apply to fraud, wilful misconduct or gross negligence."], None),
 ],
 "IP-OWNERSHIP-MSA-001": [
  ("synonym", ["13. Proprietary Rights", "Everything that makes up the Services — software, documentation, marks and know-how — belongs to Leapswitch and stays with Leapswitch; nothing in this Agreement passes ownership to the Customer."], "MATCH"),
  ("sub-clause", ["13.1 As between the parties, (a) Leapswitch retains all title to the platform, its code and improvements, and (b) the Customer acquires only the limited right to use the Services during the Term."], "MATCH"),
  ("neg-customer-data", ["The Customer retains ownership of all data it uploads to the Services."], None),
  ("neg-licence-grant", ["Leapswitch grants the Customer a non-exclusive, non-transferable licence to use the Services during the Term."], None),
 ],
 "LATE-FEE-TOS-001": [
  ("synonym", ["Payments not received by the due date carry interest at 2 percent per month until settled."], "MATCH"),
  ("reordered", ["Interest of 2% per month accrues on any amount that remains outstanding after its due date, to the extent permitted by law."], "MATCH"),
  ("table", ["OVERDUE INTEREST | 2 percent per month | from due date to settlement"], "MATCH"),
  ("genuine-difference", ["Overdue amounts bear interest at 1.5 percent per month."], "DEVIATION"),
  ("neg-suspension", ["Services may be suspended if any invoice remains unpaid for more than 15 days."], None),
  ("neg-taxes", ["All fees are exclusive of GST and other taxes, which the Customer shall pay in addition."], None),
 ],
 "DATA-RETRIEVAL-TOS-001": [
  ("synonym", ["16.4 After your account closes you can download your data free of charge for 30 days following termination; after that it is erased."], "MATCH"),
  ("reordered", ["For 30 days following termination, and without charge, the Customer may export its content, after which Leapswitch deletes it."], "MATCH"),
  ("genuine-difference", ["Data remains available for export for 7 days following termination."], "DEVIATION"),
  ("neg-return-of-confidential", ["On termination each party shall return or destroy the other's Confidential Information within 30 days of request."], None),
  ("neg-backups", ["Leapswitch keeps encrypted backups of customer data for 30 days on a rolling basis during the term."], None),
 ],
 "ARBITRATION-TOS-001": [
  ("synonym", ["Any disagreement under these Terms that cannot be settled informally is referred to a single neutral appointed jointly, whose award is final and binding on both sides."], "MATCH"),
  ("contextual", ["If we can't sort out a dispute between ourselves, one independent person chosen by both of us will decide it, and that decision is final."], "MATCH"),
  ("neg-courts", ["The courts at Mumbai shall have exclusive jurisdiction over disputes arising under these Terms."], None),
  ("neg-mediation", ["The parties shall first attempt to resolve any dispute by good-faith negotiation between senior executives within 30 days."], None),
 ],
 "TERM-NOTICE-NDA-001": [
  ("synonym", ["9.2 Either side may bring this Agreement to an end at any time by giving the other 30 days' written notice."], "MATCH"),
  ("reordered", ["On thirty (30) days' notice in writing to the other, either party may end this Agreement."], "MATCH"),
  ("genuine-difference", ["Either party may terminate this Agreement on 90 days' written notice."], "DEVIATION"),
  ("neg-notice-address", ["Notices under this Agreement shall be in writing and delivered to the addresses set out above."], None),
  ("neg-survival", ["The obligations in Sections 3 to 6 survive termination of this Agreement."], None),
 ],
 "NON-SOLICIT-NDA-001": [
  ("synonym", ["10. No Poaching", "For two years after this Agreement ends, the Receiving Party shall not, directly or through others, entice away any employee of the Disclosing Party."], "MATCH"),
  ("reordered", ["During the term and for a period of two (2) years thereafter, neither party will solicit for employment the other's personnel with whom it had contact."], "MATCH"),
  ("genuine-difference", ["For a period of one year after termination, the Receiving Party shall not solicit the Disclosing Party's employees."], "DEVIATION"),
  ("neg-non-compete", ["The Receiving Party shall not develop a competing product using the Confidential Information."], None),
  ("neg-marketing", ["Neither party shall use the other's name or marks in marketing without prior written consent."], None),
 ],
 "RESIDUALS-NDA-001": [
  ("synonym", ["11. Free Use of Recollections", "Personnel of the recipient may use, in the ordinary course of business, know-how that remains in their unaided recollection without deliberate memorisation."], "MATCH"),
  ("contextual", ["Nothing here stops the receiving side's staff from applying general skills, ideas and concepts they retain mentally after working with the disclosed material, provided no copy is kept."], "MATCH"),
  ("neg-exclusions", ["2. Confidential Information does not include information that is publicly available or was already known to the Receiving Party without restriction."], None),
  ("neg-use-restriction", ["4. The Receiving Party shall use Confidential Information solely for the Purpose and for no other reason."], None),
 ],
 "COMPELLED-DISCLOSURE-NDA-001": [
  ("synonym", ["5. Disclosure Required by Authority", "If a court, regulator or statute obliges the Receiving Party to reveal Confidential Information, it shall, where lawful, alert the Disclosing Party in writing beforehand so that a protective remedy can be sought."], "MATCH"),
  ("sub-clause", ["5.1 Where the Receiving Party is ordered to produce Confidential Information it shall (a) promptly notify the Disclosing Party in writing, (b) disclose only what is required, and (c) cooperate in seeking confidential treatment."], "MATCH"),
  ("neg-permitted-disclosure", ["The Receiving Party may disclose Confidential Information to its employees and advisers who need to know it for the Purpose."], None),
  ("neg-compliance", ["Each party shall comply with all laws applicable to it in performing this Agreement."], None),
 ],
 "TRADE-SECRET-CARVEOUT-NDA-001": [
  ("synonym", ["9.3 Where disclosed information amounts to a trade secret under applicable law, the duty of confidence lasts for as long as that information keeps that status."], "MATCH"),
  ("reordered", ["For as long as it continues to be protected as a trade secret, information so qualifying remains subject to the confidentiality obligations notwithstanding the expiry of the term in 9.2."], "MATCH"),
  ("neg-survival-general", ["Confidentiality obligations survive for three years after termination."], None),
  ("neg-definition", ["'Confidential Information' includes trade secrets, know-how, business plans and customer lists disclosed by either party."], None),
 ],
}


def _standard(code: str) -> dict:
    return json.loads((STD / f"{code}.json").read_text())


def _review(build, family: str, paragraphs: list[str]) -> M.Review:
    db = build.db
    contract = M.Contract(owner_id=build.owner.id, name=f"RD {family}", contract_type=family,
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    result = ingest_document(db, build.storage, contract_id=contract.id,
                             uploaded_by=build.owner.id, data=build_docx(paragraphs),
                             filename="rd.docx", declared_mime=DOCX_MIME)
    review = M.Review(contract_id=contract.id, document_version_id=result.document_version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    return review


ROWS: list[dict] = []
CALLS = {"n": 0}


@pytest.fixture(autouse=True)
def _count_calls(monkeypatch):
    real = generation.generate_raw

    def counting(*a, **k):
        CALLS["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(generation, "generate_raw", counting)


@pytest.mark.parametrize("code,kind,paragraphs,expected", [
    (code, kind, paragraphs, expected)
    for code, variants in CORPUS.items() for kind, paragraphs, expected in variants
], ids=[f"{code}:{kind}" for code, variants in CORPUS.items() for kind, _, _ in variants])
def test_variant(build, db, monkeypatch, code, kind, paragraphs, expected):
    payload = _standard(code)
    evaluator = E.EvaluatorType(payload.get("evaluator_type") or payload["evaluation_rules"]["evaluator"])
    rv = build.requirement(code, evaluator, mapping=payload["mapping_rules"],
                           standard=payload["configuration"],
                           legal_rule=payload["legal_rule"]["configuration"])
    rv.description = payload.get("description"); db.flush()
    family = payload["configuration"]["document_type"]

    semantic_run = run_analysis(db, _review(build, family, paragraphs))
    sem = semantic_run.outcomes[0] if semantic_run.outcomes else None

    monkeypatch.setattr(semantic, "build_index", lambda *a, **k: None)
    lexical_run = run_analysis(db, _review(build, family, paragraphs))
    lex = lexical_run.outcomes[0] if lexical_run.outcomes else None

    ROWS.append({
        "code": code, "kind": kind, "expected": expected,
        "sem_map": sem.mapping_state if sem else "n/a", "sem_cls": sem.classification if sem else "none",
        "lex_map": lex.mapping_state if lex else "n/a", "lex_cls": lex.classification if lex else "none",
        "semantic_used": any(d.startswith("semantic") for d in (sem.diagnostics if sem else [])),
    })


def test_zz_report():
    if not ROWS:
        pytest.skip("no rows")
    pos = [r for r in ROWS if not r["kind"].startswith("neg")]
    neg = [r for r in ROWS if r["kind"].startswith("neg")]
    tp = [r for r in pos if r["sem_map"] == "CONFIRMED"]
    fn_missing = [r for r in pos if r["sem_map"] == "NONE"]
    fn_review = [r for r in pos if r["sem_map"] == "UNRESOLVED"]
    # A negative the configured terms ALSO confirm is a lexical false positive
    # that predates AM-54 (a force-majeure definition carrying the alias and the
    # heading term); the gate here is on what the semantic stage INTRODUCED.
    fp = [r for r in neg if r["sem_map"] == "CONFIRMED" and r["lex_map"] != "CONFIRMED"]
    fp_lexical = [r for r in neg if r["sem_map"] == "CONFIRMED" and r["lex_map"] == "CONFIRMED"]
    neg_safe = [r for r in neg if r["sem_map"] == "UNRESOLVED"]
    cls_ok = [r for r in pos if r["expected"] and r["sem_cls"] == r["expected"]]
    cls_bad = [r for r in pos if r["expected"] and r["sem_cls"] not in (r["expected"], "UNABLE_TO_EVALUATE")]
    cls_safe = [r for r in pos if r["expected"] and r["sem_cls"] == "UNABLE_TO_EVALUATE"]
    lex_correct = [r for r in pos if r["expected"] and r["lex_cls"] == r["expected"]]
    changed_correct = [r for r in lex_correct if r["sem_cls"] != r["lex_cls"]]
    recovered = [r for r in pos if r["expected"] and r["lex_cls"] != r["expected"] and r["sem_cls"] == r["expected"]]
    lines = [
        "# AM-54 semantic recognition — live corpus report", "",
        f"variants: {len(ROWS)} ({len(pos)} positives, {len(neg)} negatives) across {len(CORPUS)} standards; model calls: {CALLS['n']}", "",
        f"RECOGNITION  TP {len(tp)}/{len(pos)} · FN→MISSING {len(fn_missing)} · FN→Needs review {len(fn_review)}",
        f"NEGATIVES    semantic FP {len(fp)}/{len(neg)} · lexical FP (pre-existing) {len(fp_lexical)} · fail-safe (Needs review) {len(neg_safe)} · correctly not mapped {len(neg) - len(fp) - len(fp_lexical) - len(neg_safe)}",
        f"CLASSIFICATION (positives with an expected result)  correct {len(cls_ok)} · fail-safe {len(cls_safe)} · WRONG {len(cls_bad)}",
        f"LEXICAL BASELINE  correct {len(lex_correct)} · recovered by semantic {len(recovered)} · CHANGED-A-CORRECT-RESULT {len(changed_correct)}", "",
        "| standard | variant | expected | lexical map/cls | semantic map/cls | note |", "|---|---|---|---|---|---|",
    ]
    for r in ROWS:
        note = ("FP" if r in fp else "lexical-FP" if r in fp_lexical else "WRONG" if r in cls_bad else "changed-correct" if r in changed_correct
                else "recovered" if r in recovered else "FN" if r in fn_missing else "fail-safe" if (r in fn_review or r in neg_safe or r in cls_safe) else "")
        lines.append(f"| {r['code']} | {r['kind']} | {r['expected'] or '—'} | {r['lex_map']}/{r['lex_cls']} | {r['sem_map']}/{r['sem_cls']} | {note} |")
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    assert fp == [], fp
    assert cls_bad == [], cls_bad
    assert changed_correct == [], changed_correct

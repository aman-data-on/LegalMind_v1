"""A controlled MIXED agreement — MSA payment/liability, NDA confidentiality, a
purchase-order clause, a tax clause, one intentionally absent expected position
(dispute resolution beside a governing-law clause) and one internal conflict
(two liability caps) — reviewed against the REAL 32 ratified standards.

Every paragraph is synthetic (rule 21). The deterministic tests run lexical-only
(the semantic stage is switched off by removing the index) so the assertions hold
without a model; `test_live_*` adds the grounded semantic stage and is skipped
unless LEGALMIND_RD_LIVE=1. The document is typed OTHER, then untyped, then MSA:
the label must not decide what is measured (AM-51, AM-60, AM-61).
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from legalmind.analysis import semantic
from legalmind.analysis.service import run_analysis
from legalmind.api.reporting import report_payload
from legalmind.assist import embedding_runtime, generation
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.test_analysis import build, storage  # noqa: F401

STD = pathlib.Path(__file__).resolve().parents[1] / "config" / "company_standards"

MIXED = [
    "MASTER SERVICES AND CONFIDENTIALITY AGREEMENT",
    "1. Definitions",
    "1.1 Capitalised terms have the meanings given in this Agreement and any Purchase Order.",
    "2. Term and Renewal",
    "2.1 This Agreement commences on the Effective Date for an Initial Term of one (1) year "
    "and shall automatically renew for successive periods of one (1) year each on the same "
    "terms and conditions, unless either Party gives written notice of non-renewal at least "
    "thirty (30) days prior to the expiry of the Initial Term or the then-current Renewal Term.",
    "3. Payment Terms and Taxes",
    "3.1 Customer shall pay all undisputed invoices within twenty-one (21) days of the invoice "
    "date. Any amount not paid when due shall accrue interest at two percent (2%) per month.",
    "3.2 All fees are exclusive of GST, which shall be billed separately in accordance with "
    "applicable Indian tax law. Where tax is required to be deducted at source under the "
    "Income Tax Act, Customer shall furnish the corresponding certificate.",
    "4. Purchase Orders",
    "4.1 Each Purchase Order shall state the products or services, quantity, price, applicable "
    "taxes and delivery dates, shall reference this Agreement, and becomes binding only upon "
    "written acceptance by the Supplier. Where a Purchase Order conflicts with this Agreement, "
    "this Agreement prevails.",
    "5. Confidentiality",
    "5.1 Each Party shall hold the other Party's Confidential Information in strict confidence "
    "and shall not disclose it to any third party without prior written consent.",
    "5.2 The obligations in this Clause 5 shall survive for a period of three (3) years after "
    "termination of this Agreement.",
    "5.3 Upon termination, each Party shall return or destroy all Confidential Information of "
    "the other Party in its possession.",
    "6. Limitation of Liability",
    "6.1 Each Party's aggregate liability arising out of this Agreement shall not exceed the "
    "total fees paid by Customer in the twelve (12) months preceding the claim.",
    "6.2 In no event shall either Party be liable for indirect, incidental or consequential "
    "damages, or for loss of profits, however caused.",
    "6.3 Notwithstanding Clause 6.1, the Supplier's aggregate liability shall not exceed the "
    "total fees paid by Customer in the six (6) months preceding the claim.",
    "7. Governing Law",
    "7.1 This Agreement shall be governed by and construed in accordance with the laws of India.",
]


def _load_all(build, db):
    codes = []
    for path in sorted(STD.glob("*.json")):
        payload = json.loads(path.read_text())
        if "retired" in payload:
            continue        # AM-65 — retired standards never reach a live snapshot
        evaluator = E.EvaluatorType(payload.get("evaluator_type")
                                    or payload["evaluation_rules"]["evaluator"])
        rv = build.requirement(payload["requirement_code"], evaluator,
                               mapping=payload["mapping_rules"],
                               standard=payload["configuration"],
                               legal_rule=payload["legal_rule"]["configuration"])
        rv.description = payload.get("description")
        codes.append(payload["requirement_code"])
    db.flush()
    return codes


def _review(build, db, contract_type):
    review = build.review(MIXED)
    contract = db.get(M.Contract, review.contract_id)
    contract.contract_type = contract_type
    db.flush()
    return review


def _run(build, db, monkeypatch, contract_type, *, semantic_stage=False):
    codes = _load_all(build, db)
    if not semantic_stage:
        monkeypatch.setattr(semantic, "build_index", lambda *a, **k: None)
    review = _review(build, db, contract_type)
    run = run_analysis(db, review)
    cls = {o.requirement_code: o.classification for o in run.outcomes}
    cov = {c["code"]: c for c in run.applicability}
    assert set(cov) == set(codes), "every pinned standard has an applicability record"
    report = report_payload(db, review)
    report["_cited_by"] = _cited_by(db, run)
    return run, cls, cov, report


def _cited_by(db, run):
    """clause section -> the requirement codes whose Finding cites it (diagnostic)."""
    from sqlalchemy import select
    out: dict[str, list[str]] = {}
    for o in run.outcomes:
        if o.finding_id is None:
            continue
        rows = db.execute(
            select(M.DocumentEvidence.section_number, M.DocumentEvidence.content)
            .join(M.FindingEvidence, M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
            .where(M.FindingEvidence.finding_id == o.finding_id)).all()
        for section, content in rows:
            out.setdefault(section or content[:40], []).append(o.requirement_code)
    return out


def _assert_content_first(cls, cov, run):
    # Recognised by CONTENT, whatever family the standard belongs to:
    assert cls["AUTORENEW-MSA-001"] == "MATCH"          # 30-day non-renewal notice (§31.15)
    assert cls["CONF-SURVIVAL-MSA-001"] == "MATCH"      # 3 years (§15)
    assert cls["LIAB-EXCLUSIONS-MSA-001"] == "MATCH"    # §9 exclusion present
    assert cls["LIABILITY-MSA-001"] == "CONFLICT"       # 12 vs 6 months, same scope (45C.2)
    assert cls["PAYMENT-PERIOD-MSA-001"] == "MATCH"     # 21 days (§16) — Constitution-approved standard
    assert cls["GST-EXCLUSIVE-MSA-001"] == "MATCH"      # fees exclusive of GST (§16)
    # One Constitution position, measured once:
    assert "LIABILITY-TOS-001" not in cls and cov["LIABILITY-TOS-001"]["outcome"] == "SAME_POSITION"
    govlaw = [c for c in cls if c.startswith("GOVLAW-")]
    assert len(govlaw) == 1 and cls[govlaw[0]] == "MATCH"
    # Intentionally absent but EXPECTED (governing law confirmed -> §22 dispute resolution):
    arb = [c for c in cls if c.startswith("ARBITRATION-")]
    assert len(arb) == 1 and cls[arb[0]] == "MISSING", (arb, cls)
    # Not expected here — no termination clause, no data window, no fixed-term exit — recorded:
    for code in ("DATA-RETRIEVAL-TOS-001", "KYC-RETENTION-TOS-001", "CLAIM-WINDOW-SLA-001"):
        assert cov[code]["outcome"] == "NOT_APPLICABLE", (code, cov[code])
        assert cov[code]["reason"]
    # Nothing is dropped silently: every outcome is APPLIED, SAME_POSITION or NOT_APPLICABLE
    assert {c["outcome"] for c in cov.values()} <= {"APPLIED", "SAME_POSITION", "NOT_APPLICABLE"}


def _assert_unmeasured_clauses_are_visible(report):
    # REC-02 / D-4b: an unmatched provision is recorded once per CLAUSE, at its anchor
    # row — the clause heading when the document has one — read by a person, never
    # judged.
    #
    # THIS LIST SHRINKS AS THE CONSTITUTION IS RATIFIED, and that is the point. §16's
    # payment and GST positions became measured when the owner ratified them through the
    # Constitution (2026-09-13). §31.11's Purchase Order positions followed on
    # 2026-09-18 (`AM-73`), so the PO clause is now MEASURED by CONTENTS-ORDER_FORM-001
    # instead of surfaced as unmeasured. Both assertions are therefore negative: a
    # clause leaving this list is coverage arriving, not a regression.
    excerpts = " ".join(r["excerpt"] for r in report["unmatched_provisions_detail"])
    assert "twenty-one (21) days of the invoice" not in excerpts, report["_cited_by"]
    assert "Each Purchase Order shall state" not in excerpts, report["_cited_by"]
    # The mechanism still works: something in this mixed agreement is still unmeasured
    # and still visible, so the negative assertions above are not passing vacuously.
    assert report["unmatched_provisions_detail"], report["_cited_by"]


def test_mixed_agreement_typed_other(build, db, monkeypatch):
    run, cls, cov, report = _run(build, db, monkeypatch, "OTHER")
    _assert_content_first(cls, cov, run)
    _assert_unmeasured_clauses_are_visible(report)
    assert cov["CURE-PERIOD-MSA-001"]["outcome"] == "NOT_APPLICABLE"
    assert "not the declared family (OTHER)" in cov["CURE-PERIOD-MSA-001"]["reason"]


def test_mixed_agreement_untyped(build, db, monkeypatch):
    run, cls, cov, report = _run(build, db, monkeypatch, None)
    _assert_content_first(cls, cov, run)
    assert run.detected_types == []
    assert "no type declared" in cov["CURE-PERIOD-MSA-001"]["reason"]


def test_mixed_agreement_typed_msa_measures_the_family_too(build, db, monkeypatch):
    run, cls, cov, report = _run(build, db, monkeypatch, "MSA")
    _assert_content_first(cls, cov, run)
    # The declared family adds its own standards — measured, fail-closed where the
    # words are ambiguous (a stray 'termination' scores below the threshold ->
    # UNRESOLVED -> UNABLE_TO_EVALUATE, never a guessed absence), and only its own:
    assert cls["CURE-PERIOD-MSA-001"] in ("MISSING", "UNABLE_TO_EVALUATE")
    assert cov["CURE-PERIOD-MSA-001"]["reason"].startswith("declared type MSA")
    assert cov["KYC-RETENTION-TOS-001"]["outcome"] == "NOT_APPLICABLE"


def test_the_label_does_not_change_what_content_recognises(build, db, monkeypatch):
    """Same document, three labels: the content-recognised verdicts are identical."""
    results = []
    for t in ("OTHER", None, "MSA"):
        monkeypatch.setattr(semantic, "build_index", lambda *a, **k: None)
        if not results:
            _load_all(build, db)
        review = _review(build, db, t)
        run = run_analysis(db, review)
        results.append({o.requirement_code: o.classification for o in run.outcomes
                        if o.requirement_code in ("AUTORENEW-MSA-001", "CONF-SURVIVAL-MSA-001",
                                                  "LIABILITY-MSA-001", "LIAB-EXCLUSIONS-MSA-001")})
    assert results[0] == results[1] == results[2], results


@pytest.mark.skipif(
    os.environ.get("LEGALMIND_RD_LIVE") != "1" or not generation.credential_present()
    or not embedding_runtime.available(),
    reason="live: needs LEGALMIND_RD_LIVE=1, a generation credential and the embedding model")
def test_live_mixed_agreement_with_the_semantic_stage(build, db, monkeypatch):
    run, cls, cov, report = _run(build, db, monkeypatch, "OTHER", semantic_stage=True)
    _assert_content_first(cls, cov, run)
    out = pathlib.Path(os.environ.get("LEGALMIND_RD_REPORT", "/tmp/mixed-live.json"))
    out.write_text(json.dumps({"classifications": cls, "applicability": cov,
                               "unmatched": report["unmatched_provisions_detail"]}, indent=1))

"""A cap under an unusual title is never "No clause on this point" (`AM-317` r5, audit
N8, rule 15): the configured words confirm a data-breach exclusion with no figure, while
"13. LIMITATION ON DAMAGES" — the standard's own configured alias — heads the real cap in
words the configured phrases do not read. The Finding is UNABLE_TO_EVALUATE on that clause
(Needs a decision), never MISSING. Synthetic wording only (rule 21); the standard is the
ratified file.
"""
from __future__ import annotations

from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from tests.legal_regression.test_legal_regression import _docx, _findings
from tests.test_analysis import DOCX_MIME, build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified

CAP = "LIABILITY-MSA-001"
BREACH = ["25.11 Limitation of Liability for Data Breaches",
          "Provider shall not be liable for data breaches unless caused by its gross "
          "negligence."]
DAMAGES = ("13.1 The total liability of Provider on all claims shall in no case go beyond "
           "the average fee paid over a three (3) month period.")


def _analysed(build, db, rows):
    _ratified(build, CAP)
    contract = M.Contract(owner_id=build.owner.id, name="Client paper", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    v = ingest_document(db, build.storage, contract_id=contract.id,
                        uploaded_by=build.owner.id, data=_docx(rows),
                        filename="contract.docx", declared_mime=DOCX_MIME).document_version
    review = M.Review(contract_id=contract.id, document_version_id=v.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    run_analysis(db, review)
    return _findings(db, review)[CAP]


def test_a_cap_under_an_unusual_title_needs_a_decision_never_missing(build, db):
    found = _analysed(build, db, ["13. LIMITATION ON DAMAGES", DAMAGES,
                                  "25. GENERAL", *BREACH])
    assert found["classification"] == "UNABLE_TO_EVALUATE"
    assert "13.1" in {s for s, _ in found["cited"]}


def test_a_paper_whose_words_point_at_nothing_else_is_still_missing(build, db):
    """The fail-closed reading needs a clause the configured words point at: with only
    the exclusion, nothing else is on the point and absence stands."""
    assert _analysed(build, db, ["25. GENERAL", *BREACH])["classification"] == "MISSING"

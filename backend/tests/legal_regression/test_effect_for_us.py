"""What a client change does for us, through the real pipeline (`AM-299`/`AM-301`, the
manager's example): our MSA's mutual 12-months-of-total-fees cap returned at six months
reads "Better for us" on the same basis AND on the affected-services basis, while the
engine's own Findings are unchanged (a DEVIATION and an UNABLE_TO_EVALUATE — never a
MATCH). Synthetic wording only (rule 21); the standard is the ratified file.
"""
from __future__ import annotations

import pytest

from legalmind.analysis import negotiation
from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from tests.legal_regression.test_legal_regression import CAP, _docx, _findings
from tests.test_analysis import DOCX_MIME, build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified

OURS = ("17.2 The total aggregate liability of each party shall not exceed the total fees "
        "paid by the Customer in the twelve (12) months preceding the claim.")
SAME_BASIS = OURS.replace("twelve (12)", "six (6)")
AFFECTED = ("17.2 The total aggregate liability of each party shall not exceed the total "
            "amount actually paid by the Customer to Leapswitch for the specific services "
            "giving rise to the claim during the six (6) month period preceding the claim.")
HIGHER = OURS.replace("twelve (12)", "eighteen (18)")
ONE_PARTY = ("17.2 Leapswitch's total aggregate liability shall not exceed the total fees "
             "paid by the Customer in the six (6) months preceding the claim.")


def _version(build, db, contract, sentence):
    v = ingest_document(db, build.storage, contract_id=contract.id,
                        uploaded_by=build.owner.id,
                        data=_docx(["17. Limitation of Liability", sentence]),
                        filename="contract.docx", declared_mime=DOCX_MIME).document_version
    review = M.Review(contract_id=contract.id, document_version_id=v.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review); db.flush()
    run_analysis(db, review)
    return v, review


def _returned(build, db, sentence, kind="MSA"):
    _ratified(build, CAP)
    contract = M.Contract(owner_id=build.owner.id, name="Negotiated MSA", contract_type=kind,
                          status=E.ContractStatus.ACTIVE)
    db.add(contract); db.flush()
    ours, _ = _version(build, db, contract, OURS)
    theirs, review = _version(build, db, contract, sentence)
    [change] = [c for c in negotiation.changes(db, contract, ours, theirs,
                                               legal_position=True)["changes"]
                if c["clause"]["number"] == "17.2"]
    return change, _findings(db, review)[CAP]["classification"]


def test_six_months_of_total_fees_is_better_for_us_and_still_a_deviation(build, db):
    change, cls = _returned(build, db, SAME_BASIS)
    assert cls == "DEVIATION"                      # the engine is untouched (rule 14)
    assert (change["effect_for_us"], change["route"]) == ("POSITIVE", "favour")


def test_six_months_of_affected_service_fees_is_better_for_us_never_a_match(build, db):
    """`AM-301`: affected-services fees ≤ total fees — the bases stay incomparable."""
    change, cls = _returned(build, db, AFFECTED)
    assert cls == "UNABLE_TO_EVALUATE"
    assert (change["effect_for_us"], change["route"]) == ("POSITIVE", "favour")


@pytest.mark.parametrize("sentence", [HIGHER, ONE_PARTY])
def test_a_higher_cap_or_a_one_party_cap_goes_to_legal(build, db, sentence):
    change, _ = _returned(build, db, sentence)
    assert (change["effect_for_us"], change["route"]) == ("NEGATIVE", "holder")


def test_a_lower_cap_on_a_vendors_paper_is_not_read_as_ours(build, db):
    """LeapSwitch is the customer there: a lower cap on the vendor is worse (`AM-239` r2)."""
    change, _ = _returned(build, db, SAME_BASIS, kind="VENDOR_AGREEMENT")
    assert change["effect_for_us"] == "NEGATIVE"

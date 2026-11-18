"""AB-213 D2 (`AM-406`): an OPTIONAL fill-in field the deal left empty stays cleanly blank
and never blocks the final contract; a required blank still does. STRUCTURAL placeholder,
synthetic text only (rule 21)."""

from __future__ import annotations

import uuid

from legalmind.api.routers import negotiation as N
from tests.conftest import sign_in
from tests.drafting.test_new_contract import (  # noqa: F401 — fixtures
    _start,
    count_is_blank,
    published,
    staff,
)

V1 = "/api/v1"


def test_an_unanswered_optional_blank_is_skipped_and_a_filled_one_is_not(
        db, api, count_is_blank, published, staff, answers):
    sign_in(api, db, staff)
    left = {k: v for k, v in answers.items() if k != "party_one_cin"}
    draft = _start(api, published, answers=left).json()["data"]
    cid = api.post(f"{V1}/drafts/{draft['id']}/create",
                   json={"expected_version": 0}).json()["data"]["contract_id"]
    assert N.optional_blanks(db, uuid.UUID(cid)) == {"NOWHERE"}
    done = api.post(f"{V1}/contracts/{cid}/blank-values",
                    json={"values": {"party_one_cin": "U9"}, "expected_version": 1})
    assert done.status_code == 201, done.text
    assert N.optional_blanks(db, uuid.UUID(cid)) == set()


def test_model_blanks_skips_only_the_optional_clause():
    model = {"body": [{"number": "17", "body": ["fees in the ___ months"]},
                      {"number": "18", "body": ["banks at ___ open"]}]}
    assert "2 blanks" in (N.model_blanks(model) or "")
    assert "1 blank is" in (N.model_blanks(model, {"17"}) or "")
    assert N.model_blanks(model, {"17", "18"}) is None
    assert N._skipped("17.7", {"17"}) and not N._skipped("171", {"17"})


def test_fill_in_fields_are_closed_while_the_contract_is_with_legal(
        db, api, count_is_blank, published, staff, answers):
    """AB-213 D10 (`AM-408` r2): sales cannot change the text Legal is reading."""
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    sign_in(api, db, staff)
    draft = _start(api, published, answers=answers).json()["data"]
    cid = api.post(f"{V1}/drafts/{draft['id']}/create",
                   json={"expected_version": 0}).json()["data"]["contract_id"]
    url = f"{V1}/contracts/{cid}/blank-values"
    assert api.get(url).json()["data"]["can_edit"] is True
    v1 = db.query(M.DocumentVersion).filter_by(contract_id=uuid.UUID(cid)).one()
    reviews = db.query(M.Review).filter_by(document_version_id=v1.id).all()
    if not reviews:
        snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=staff.id)
        db.add(snap)
        db.flush()
        reviews = [M.Review(contract_id=v1.contract_id, document_version_id=v1.id,
                            configuration_snapshot_id=snap.id, created_by=staff.id,
                            status=E.ReviewStatus.LEGAL_REVIEW)]
        db.add(reviews[0])
        db.flush()
    for review in reviews:                       # sent to Legal (an active assignment)
        review.status = E.ReviewStatus.PROCESSING          # Legal still reading it
        db.add(M.ReviewAssignment(review_id=review.id, user_id=staff.id,
                                  assigned_by=staff.id))
    db.flush()
    assert api.get(url).json()["data"]["can_edit"] is False
    refused = api.post(url, json={"values": {"party_one_cin": "U5"}, "expected_version": 1})
    assert refused.status_code == 409

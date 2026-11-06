"""Where every deal stands — `AM-260` (CLM R7, 2026-11-02): each path lands on its stage,
the stage reaches the contract list and detail, and the list filters and counts by it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.deal_stage import (
    NegotiationStage as S,
)
from legalmind.domain.deal_stage import (
    ReviewFacts,
    VersionFacts,
    derive_stage,
    stage_payload,
)
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_finding, make_review_for, make_user, sign_in
from tests.test_version_comparison import V1

T0 = datetime(2026, 10, 1, tzinfo=UTC)


def _at(days: int) -> datetime:
    return T0 + timedelta(days=days)


def _v(n, role=None, sent=None):
    return VersionFacts(n, _at(n), role, _at(sent) if sent is not None else None)


# ------------------------------------------------------------------ the pure derivation
def test_no_version_yet_is_drafting_since_the_contract_was_created():
    assert derive_stage(_at(0), []) == (S.DRAFTING, _at(0))


def test_our_draft_not_sent_is_drafting():
    assert derive_stage(_at(0), [_v(1, "COMPANY_DRAFT")]) == (S.DRAFTING, _at(1))


def test_a_draft_sent_for_review_is_internal_review():
    review = ReviewFacts(in_review_since=_at(2))
    assert derive_stage(_at(0), [_v(1, "COMPANY_DRAFT")], review) == (
        S.INTERNAL_REVIEW, _at(2))


def test_a_draft_legal_has_decided_is_ready_to_send():
    """Every point of our draft sent for review decided: the deal moves on, it does not
    sit With Legal on an assignment nobody releases."""
    review = ReviewFacts(in_review_since=_at(2), reply_cleared=True)
    assert derive_stage(_at(0), [_v(1, "COMPANY_DRAFT")], review) == (
        S.READY_TO_SEND, _at(1))
    assert derive_stage(_at(0), [_v(1, "COMPANY_DRAFT", sent=3)], review)[0] \
        is S.WITH_CLIENT


def test_a_sent_version_is_with_client_since_it_was_sent():
    assert derive_stage(_at(0), [_v(1, "COMPANY_DRAFT", sent=3)],
                        ReviewFacts(in_review_since=_at(2))) == (S.WITH_CLIENT, _at(3))


def test_the_clients_version_after_ours_is_our_turn():
    versions = [_v(1, "COMPANY_DRAFT", sent=1), _v(2, "CLIENT_MODIFIED")]
    assert derive_stage(_at(0), versions) == (S.CLIENT_RETURNED, _at(2))


def test_our_next_draft_after_a_return_is_drafting_again_then_with_client():
    versions = [_v(1, "COMPANY_DRAFT", sent=1), _v(2, "CLIENT_MODIFIED"),
                _v(3, "COMPANY_DRAFT")]
    assert derive_stage(_at(0), versions)[0] is S.DRAFTING
    versions[2] = _v(3, "COMPANY_DRAFT", sent=4)
    assert derive_stage(_at(0), versions) == (S.WITH_CLIENT, _at(4))


def test_our_prepared_reply_is_ready_to_send_until_marked_sent():
    """The reply (`reply_to`) waits on one act — Mark sent — so it is not "Drafting"."""
    reply = VersionFacts(3, _at(3), "COMPANY_DRAFT", None, reply_to=True)
    versions = [_v(1, "COMPANY_DRAFT", sent=1), _v(2, "CLIENT_MODIFIED"), reply]
    cleared = ReviewFacts(reply_cleared=True)
    assert derive_stage(_at(0), versions, cleared) == (S.READY_TO_SEND, _at(3))
    # sent to a reviewer first: Legal is looking at it before it goes
    assert derive_stage(_at(0), versions, ReviewFacts(in_review_since=_at(4)))[0] \
        is S.INTERNAL_REVIEW
    versions[2] = VersionFacts(3, _at(3), "COMPANY_DRAFT", _at(5), reply_to=True)
    assert derive_stage(_at(0), versions) == (S.WITH_CLIENT, _at(5))


def test_a_reply_with_an_undecided_point_is_never_ready_to_send():
    """`AM-293` r1: a reply whose Review is unfinished or holds an undecided point cannot
    leave, so it reads With Legal — and so does one whose review facts are not visible."""
    reply = VersionFacts(3, _at(3), "COMPANY_DRAFT", None, reply_to=True)
    versions = [_v(1, "COMPANY_DRAFT", sent=1), _v(2, "CLIENT_MODIFIED"), reply]
    assert derive_stage(_at(0), versions, ReviewFacts(reply_cleared=False)) == (
        S.INTERNAL_REVIEW, _at(3))
    assert derive_stage(_at(0), versions)[0] is S.INTERNAL_REVIEW


def test_only_the_latest_versions_sent_mark_counts():
    """v1 went out; our v2 has not — the deal is with us, not the client."""
    assert derive_stage(_at(0), [_v(1, sent=1), _v(2)])[0] is S.DRAFTING


def test_sign_as_is_or_after_our_changes_is_ready_to_sign():
    for outcome in ("SIGN_AS_IS", "SIGN_WITH_CHANGES"):
        review = ReviewFacts(outcome=outcome, outcome_at=_at(5))
        assert derive_stage(_at(0), [_v(1, "CLIENT_MODIFIED")], review) == (
            S.READY_TO_SIGN, _at(5))


def test_on_hold_is_its_own_stage_and_do_not_sign_falls_through():
    held = ReviewFacts(outcome="ON_HOLD", outcome_at=_at(5))
    assert derive_stage(_at(0), [_v(1)], held) == (S.ON_HOLD, _at(5))
    refused = ReviewFacts(outcome="DO_NOT_SIGN", outcome_at=_at(5))
    assert derive_stage(_at(0), [_v(1, "CLIENT_MODIFIED")], refused)[0] is S.CLIENT_RETURNED


def test_a_signed_copy_beats_everything():
    versions = [_v(1, "COMPANY_DRAFT", sent=1), _v(2, "FINAL_SIGNED"), _v(3)]
    review = ReviewFacts(outcome="ON_HOLD", outcome_at=_at(9))
    assert derive_stage(_at(0), versions, review) == (S.SIGNED, _at(2))


def test_days_in_stage_are_whole_days_and_never_negative():
    assert stage_payload(S.WITH_CLIENT, _at(0), _at(9) + timedelta(hours=5))["days"] == 9
    assert stage_payload(S.WITH_CLIENT, _at(3), _at(0))["days"] == 0


def test_the_vocabulary_is_its_own():
    """REC-06: never a value of `review_stage` or ContractStatus."""
    taken = {s.value for s in E.ContractStatus} | {
        "SUPERSEDED", "ANALYSING", "ANALYSIS_FAILED", "WAITING_FOR_CLARIFICATION",
        "REOPENED", "WITH_LEGAL", "NOT_SENT", "COMPLETE", "NO_ISSUES",
        "CONTRACT_DECISION_PENDING"}
    assert not taken & {s.value for s in S}


# ------------------------------------------------------------------ through the API
def _owner(api, db):
    user = make_user(db)
    grant_role(db, user, P.ROLE_USER)
    sign_in(api, db, user)
    return user


def _returned(db, owner):
    """v1 ours, sent; v2 the client's."""
    review = make_review_for(db, owner)
    v1 = db.get(M.DocumentVersion, review.document_version_id)
    v1.doc_metadata = {"version_role": "COMPANY_DRAFT"}
    v1.sent_at, v1.sent_by = datetime.now(UTC) - timedelta(days=3), owner.id
    db.add(M.DocumentVersion(
        contract_id=review.contract_id, version_number=2, original_filename="v2.pdf",
        mime_type="application/pdf", file_size_bytes=10, file_hash="h2", storage_key="k2",
        processing_status=E.ProcessingStatus.COMPLETED, uploaded_by=owner.id,
        doc_metadata={"version_role": "CLIENT_MODIFIED"}))
    db.flush()
    return review


def test_list_detail_filter_and_tiles_carry_the_stage(api, db, seeded):
    owner = _owner(api, db)
    returned = _returned(db, owner)
    drafting = make_review_for(db, owner)
    detail = api.get(f"{V1}/contracts/{returned.contract_id}").json()["data"]
    assert detail["negotiation_stage"]["stage"] == "CLIENT_RETURNED"
    assert detail["negotiation_stage"]["days"] == 0
    rows = api.get(f"{V1}/contracts").json()["data"]
    assert {r["id"]: r["negotiation_stage"]["stage"] for r in rows} == {
        str(returned.contract_id): "CLIENT_RETURNED",
        str(drafting.contract_id): "DRAFTING"}
    only = api.get(f"{V1}/contracts", params={"stage": "CLIENT_RETURNED"}).json()
    assert [r["id"] for r in only["data"]] == [str(returned.contract_id)]
    assert api.get(f"{V1}/contracts", params={"stage": "LOST"}).status_code == 422
    tiles = api.get(f"{V1}/contracts/summary").json()["data"]["stages"]
    assert tiles["CLIENT_RETURNED"] == 1 and tiles["DRAFTING"] == 1
    assert sum(tiles.values()) == 2


def test_sent_for_review_and_the_contract_decision_move_the_stage(
        api, db, seeded, requirement_version):
    owner = _owner(api, db)
    review = make_review_for(db, owner)
    finding = make_finding(db, review, requirement_version)       # one undecided point
    url = f"{V1}/contracts/{review.contract_id}"
    reviewer = make_user(db)
    db.add(M.ReviewAssignment(review_id=review.id, user_id=reviewer.id,
                              assigned_by=owner.id))
    db.flush()
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "INTERNAL_REVIEW"
    finding.status = E.FindingStatus.RESOLVED      # Legal decided it: the draft moves on
    db.flush()
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "READY_TO_SEND"
    finding.status = E.FindingStatus.DECISION_REQUIRED
    db.flush()
    db.add(M.ContractOutcomeRecord(review_id=review.id, outcome=E.ContractOutcome.SIGN_AS_IS,
                                   suggested=E.ContractOutcome.SIGN_AS_IS,
                                   justification="agreed", decided_by=reviewer.id,
                                   version_number=1))
    db.flush()
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "READY_TO_SIGN"
    review.reopened_at = datetime.now(UTC) + timedelta(seconds=1)   # AM-175
    db.flush()
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "INTERNAL_REVIEW"


def test_the_list_holds_a_reply_with_an_undecided_point_back_from_ready_to_send(
        api, db, seeded, requirement_version):
    """The reply the critic saw read "Ready to send" beside open points (`AM-293` r1)."""
    owner = _owner(api, db)
    review = make_review_for(db, owner)
    dv = db.get(M.DocumentVersion, review.document_version_id)
    dv.doc_metadata = {"version_role": "COMPANY_DRAFT", "reply_to": 1}
    db.flush()
    url = f"{V1}/contracts/{review.contract_id}"
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "READY_TO_SEND"
    finding = make_finding(db, review, requirement_version)
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "INTERNAL_REVIEW"
    finding.status = E.FindingStatus.RESOLVED
    review.status = E.ReviewStatus.PROCESSING          # unfinished fails closed too
    db.flush()
    assert api.get(url).json()["data"]["negotiation_stage"]["stage"] == "INTERNAL_REVIEW"


def test_out_of_scope_detail_stays_the_byte_identical_404(api, db, seeded):
    _owner(api, db)
    theirs = _returned(db, make_user(db))

    def body(path):
        r = api.get(path)
        assert r.status_code == 404
        payload = r.json()
        payload["error"]["request_id"] = "-"
        return str(sorted(payload.items()))

    assert body(f"{V1}/contracts/{theirs.contract_id}") == body(f"{V1}/contracts/{uuid.uuid4()}")

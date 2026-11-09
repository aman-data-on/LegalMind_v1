"""The deal cycle ends at the final clean copy — `AM-318` (owner, 2026-11-06).

Stamping and signing happen in another tool. A deal is Final once its latest version is
our final contract (an Annexure package, or a final copy) and Legal recorded Sign as is
on it. Every document here is synthetic; none names a client.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.deal_stage import NegotiationStage as S
from legalmind.domain.deal_stage import ReviewFacts, VersionFacts, derive_stage
from legalmind.drafting import clean
from legalmind.workflow import contract_outcome as CO
from legalmind.workflow.errors import InvalidTransition
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _ingest,
    _review,
    owner,
)
from tests.test_negotiation_reply import (
    OURS,
    THEIRS,
    _answer,
    _negotiated,
    _text,
    published,  # noqa: F401 — autouse fixture
)
from tests.test_version_comparison import V1

T0 = datetime(2026, 11, 1, tzinfo=UTC)
FINAL = f"{V1}/contracts/{{}}/final-copy"


def _at(d: int) -> datetime:
    return T0 + timedelta(days=d)


# ------------------------------------------------------------------ the pure stage
def test_a_final_contract_signed_as_is_is_final_even_once_recorded_as_sent():
    final = VersionFacts(3, _at(3), "COMPANY_DRAFT", _at(5), True, True)
    review = ReviewFacts(outcome="SIGN_AS_IS", outcome_at=_at(4))
    assert derive_stage(_at(0), [final], review) == (S.FINAL, _at(4))


def test_a_final_contract_awaiting_the_decision_is_with_legal():
    final = VersionFacts(3, _at(3), "COMPANY_DRAFT", None, True, True)
    assert derive_stage(_at(0), [final], ReviewFacts(reply_cleared=True)) == (
        S.INTERNAL_REVIEW, _at(3))


def test_sign_as_is_on_a_version_that_is_not_final_is_ready_for_the_final_contract():
    draft = VersionFacts(1, _at(1), "COMPANY_DRAFT")
    review = ReviewFacts(outcome="SIGN_AS_IS", outcome_at=_at(2))
    assert derive_stage(_at(0), [draft], review)[0] is S.READY_TO_SIGN


def test_a_legacy_signed_deal_stays_signed():
    signed = VersionFacts(4, _at(4), "FINAL_SIGNED")
    assert derive_stage(_at(0), [signed])[0] is S.SIGNED


# ------------------------------------------------------------------ the final copy
def test_the_client_accepted_our_draft_unchanged(api, db, owner, tmp_path):
    """B4: nothing to answer — the final copy is our version, clean."""
    c = _contract(db, owner)
    ours = _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert (dry["available"], dry["mode"], dry["agreed"]) == (True, "copy", [])
    r = api.post(FINAL.format(c.id))
    assert r.status_code == 201, r.text
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    assert v.version_number == 2 and v.doc_metadata["final_copy_of"] == str(ours.id)
    assert v.doc_metadata["version_role"] == "COMPANY_DRAFT"
    # a final copy is never a second final copy
    again = api.post(FINAL.format(c.id))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "FINAL_COPY_NOT_READY"


def test_a_counter_proposal_goes_to_the_client_before_the_final_copy(
        api, db, owner, tmp_path, monkeypatch):
    """Verifier item 1: answers that keep or propose our wording go back as our reply
    first (REPLY_FIRST); once the client accepts that reply, its final copy is clean —
    every tracked change accepted, no revision mark left."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    c, _, theirs = _negotiated(api, db, owner, tmp_path)
    assert api.get(FINAL.format(c.id)).json()["data"]["blockers"][0]["code"] == "CHANGES"
    for change in _changes(api, c)["changes"]:
        _answer(api, c, change, "accept_theirs" if change["clause"]["number"] == "4"
                else "keep_ours")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["REPLY_FIRST"]
    reply = api.post(f"{V1}/contracts/{c.id}/reply")
    assert reply.status_code == 201, reply.text
    after = api.get(FINAL.format(c.id)).json()["data"]
    assert after["available"] and len(after["agreed"]) == 5       # the round's answers
    r = api.post(FINAL.format(c.id))          # the client accepted our reply as it was
    assert r.status_code == 201, r.text
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    assert v.doc_metadata["final_copy_of"] == reply.json()["data"]["document_version"]["id"]
    from legalmind.api.storage import get_storage
    data = api.app.dependency_overrides.get(get_storage, get_storage)().get(v.storage_key)
    assert clean.has_markup(data) == []
    assert _text(data) == [*OURS[:3], THEIRS[2]]


def test_a_blank_left_to_fill_blocks_the_final_contract(api, db, owner, tmp_path):
    """Verifier item 4: a final contract never keeps a blank — a plain list says where."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx("1. Business Day means a day banks at ___________ are "
                                   "open.", *OURS[1:]), "ours.docx")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["BLANKS"]
    assert "clause 1 (" in dry["blockers"][0]["message"]
    assert api.post(FINAL.format(c.id)).status_code == 409


def test_a_client_pdf_with_answers_to_write_is_refused(api, db, owner):
    from tests.test_negotiation import _pair
    c = _contract(db, owner)
    _pair(db, c, "9. Liability is capped.", "9. Liability is uncapped.")
    _answer(api, c, _changes(api, c)["changes"][0], "keep_ours")
    dry = api.get(FINAL.format(c.id)).json()["data"]
    # a counter-proposal on the client's PDF: our reply first (which needs their Word file)
    assert dry["blockers"][0]["code"] in {"REPLY_FIRST", "NOT_READ"}


# ------------------------------------------------------------------ the decision
def test_a_final_copy_is_never_signed_after_our_changes(api, db, owner, tmp_path):
    """A2: on a final copy only Sign as is / Do not sign / On hold."""
    c = _contract(db, owner)
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    r = api.post(FINAL.format(c.id))
    v = db.get(M.DocumentVersion, uuid.UUID(r.json()["data"]["document_version"]["id"]))
    review = db.execute(select(M.Review).where(
        M.Review.document_version_id == v.id)).scalar() or _review(db, v, [])
    review.status = E.ReviewStatus.RESOLVED
    db.flush()
    assert CO.is_final_copy(db, review)
    with mock.patch.object(CO, "has_permission", return_value=True), \
            pytest.raises(InvalidTransition):
        CO.record(db, review, actor_id=owner.id, justification="x",
                  outcome=E.ContractOutcome.SIGN_WITH_CHANGES)

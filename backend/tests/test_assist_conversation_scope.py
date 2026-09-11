"""Attaching a document to a live conversation, and asking about a Finding (2026-09-11).

Two additions, both narrow, both tested here for what they must NOT do as much as for
what they do:

  - `POST /conversations/{id}/document` gives a document-less conversation a document
    and keeps every earlier turn. It is ONE-WAY: a conversation that already carries a
    contract is refused, because earlier turns cite `evidence_id`s from the first
    document's reading order and re-pointing would strand all of them.

  - `AskRequest.finding_id` seeds the RETRIEVAL query with the Finding's requirement and
    cited clause, so "why is this a deviation?" retrieves the clause instead of nothing.
    It never widens what the caller may read, and — the assertion that matters — the
    Finding's classification and the Company Standard value never reach the payload
    (`AM-30` t3, `AM-32` r4, unchanged by `AM-58`).
"""

from __future__ import annotations

import typing
import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import service
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    indexed_contract,
    storage,
)
from tests.test_assist_explanations import owner  # noqa: F401


def _scoped(db, conversation_id):
    schema = config.assist_schema()
    return db.execute(text(f'SELECT contract_id FROM "{schema}".conversations '
                           "WHERE id = :i"), {"i": conversation_id}).scalar()


# ==========================================================================
# Attaching a document to a conversation that has none
# ==========================================================================
def test_a_document_less_conversation_gains_a_document(db, user, indexed_contract):
    contract, _version = indexed_contract
    conversation_id = service.create_conversation(db, user_id=user.id, contract_id=None)
    assert _scoped(db, conversation_id) is None

    service.attach_contract(db, conversation_id=conversation_id,
                            contract_id=contract.id)

    assert _scoped(db, conversation_id) == contract.id


def test_the_earlier_turns_survive_the_attachment(db, user, indexed_contract):
    """The whole point: a reader asking about the organization's standards who then
    attaches the agreement keeps the thread instead of losing it to a new chat."""
    contract, _version = indexed_contract
    conversation_id = service.create_conversation(db, user_id=user.id, contract_id=None)
    schema = config.assist_schema()
    service._persist_turn(db, conversation_id, 0, "USER", "What do we require?")
    service._persist_turn(db, conversation_id, 1, "ASSISTANT", "The approved position…")

    service.attach_contract(db, conversation_id=conversation_id,
                            contract_id=contract.id)

    kept = db.execute(text(f'SELECT count(*) FROM "{schema}".messages '
                           "WHERE conversation_id = :c"), {"c": conversation_id}).scalar()
    assert kept == 2


def test_a_conversation_that_already_has_a_document_is_refused(db, user,
                                                               indexed_contract):
    """One-way. Re-pointing would leave every earlier citation aimed at a row that is
    no longer in the conversation's document."""
    contract, _version = indexed_contract
    conversation_id = service.create_conversation(db, user_id=user.id,
                                                  contract_id=contract.id)

    with pytest.raises(service.ConversationAlreadyScoped):
        service.attach_contract(db, conversation_id=conversation_id,
                                contract_id=contract.id)

    assert _scoped(db, conversation_id) == contract.id


# ==========================================================================
# The same two rules, through the API, with the full authorization chain
# ==========================================================================
def test_the_endpoint_attaches_and_then_refuses_a_second_document(api, db, seeded,
                                                                  storage):
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    from legalmind.ingestion.service import ingest_document
    from legalmind.ingestion.validation import DOCX_MIME
    from tests.conftest import grant_role, make_user, sign_in
    from tests.test_assist_ask import PARAGRAPHS
    from tests.test_ingestion import build_docx

    owner = make_user(db)
    grant_role(db, owner, "USER")
    sign_in(api, db, owner)
    contract = M.Contract(owner_id=owner.id, name="Attach MSA", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    ingest_document(db, storage, contract_id=contract.id, uploaded_by=owner.id,
                    data=build_docx(PARAGRAPHS), filename="msa.docx",
                    declared_mime=DOCX_MIME)
    db.commit()

    created = api.post("/api/v1/conversations", json={})
    assert created.status_code == 201, created.text
    conversation_id = created.json()["data"]["id"]

    attached = api.post(f"/api/v1/conversations/{conversation_id}/document",
                        json={"contract_id": str(contract.id)})
    assert attached.status_code == 200, attached.text
    assert attached.json()["data"]["contract_id"] == str(contract.id)

    again = api.post(f"/api/v1/conversations/{conversation_id}/document",
                     json={"contract_id": str(contract.id)})
    assert again.status_code == 422, again.text
    assert "start a new chat" in again.text


def test_attaching_a_contract_the_caller_cannot_read_is_not_found(api, db, seeded,
                                                                  storage):
    """`AM-25` r6/r7: out of scope is indistinguishable from nonexistent, and the
    attach route is not a new way to discover that a contract exists."""
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    from tests.conftest import grant_role, make_user, sign_in

    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    someone_else = make_user(db)
    hidden = M.Contract(owner_id=someone_else.id, name="Not yours",
                        contract_type="MSA", status=E.ContractStatus.ACTIVE)
    db.add(hidden)
    db.flush()
    db.commit()
    sign_in(api, db, stranger)

    created = api.post("/api/v1/conversations", json={})
    conversation_id = created.json()["data"]["id"]
    refused = api.post(f"/api/v1/conversations/{conversation_id}/document",
                       json={"contract_id": str(hidden.id)})
    assert refused.status_code == 404, refused.text


def test_attaching_to_someone_elses_conversation_is_not_found(api, db, seeded, storage):
    """`AB-12` r8: a conversation is visible to its creator only, and this route is
    held to the same rule as reading one."""
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    from tests.conftest import grant_role, make_user, sign_in

    first = make_user(db)
    grant_role(db, first, "USER")
    sign_in(api, db, first)
    conversation_id = api.post("/api/v1/conversations", json={}).json()["data"]["id"]

    second = make_user(db)
    grant_role(db, second, "USER")
    theirs = M.Contract(owner_id=second.id, name="Theirs", contract_type="MSA",
                        status=E.ContractStatus.ACTIVE)
    db.add(theirs)
    db.flush()
    db.commit()
    sign_in(api, db, second)

    refused = api.post(f"/api/v1/conversations/{conversation_id}/document",
                       json={"contract_id": str(theirs.id)})
    assert refused.status_code == 404, refused.text


# ==========================================================================
# Asking about a Finding — the cited rows are admitted, the payload is not widened
# ==========================================================================
def test_a_findings_cited_rows_are_found_by_id(db, owner):
    """"Why is this a deviation?" carries no retrievable content of its own. The
    Finding already knows which rows it is about, so they are fetched by id rather
    than re-found by text — measured 2026-09-11: seeding the QUERY with the clause's
    own words made it longer, lexical search ANDs every stemmed term, and the gate
    stayed shut on a clause sitting in the same document."""
    from tests.test_assist_explanations import PASSAGE, _finding, _requirement

    rv = _requirement(db, owner)
    finding = _finding(db, owner, rv, passages=(PASSAGE,))

    ids = service._finding_evidence_ids(db, finding.id)

    assert len(ids) == 1, "the one cited row, by id"


def test_the_cited_rows_resolve_to_chunks_inside_the_asked_version(db, owner):
    """`AM-25` r6: the chunk lookup is scoped to the one document version, so a
    Finding can never widen retrieval beyond the document being asked about."""
    from sqlalchemy import select

    from legalmind.assist import store
    from legalmind.db import models as M
    from tests.test_assist_explanations import PASSAGE, _finding, _requirement

    rv = _requirement(db, owner)
    finding = _finding(db, owner, rv, passages=(PASSAGE,))
    ids = service._finding_evidence_ids(db, finding.id)
    evidence = db.execute(select(M.DocumentEvidence)
                          .where(M.DocumentEvidence.id == ids[0])).scalar_one()

    # Asked about ANOTHER version: the cited row is not in it, so nothing comes back.
    other = uuid.uuid4()
    assert store.chunks_for_evidence(db, document_version_id=other,
                                     evidence_ids=ids) == []
    # Asked about its own version: whatever chunks exist are this document's.
    same = store.chunks_for_evidence(
        db, document_version_id=evidence.document_version_id, evidence_ids=ids)
    for hit in same:
        assert hit.evidence_id in ids


def test_a_finding_with_no_cited_rows_admits_nothing(db, owner):
    """Fail closed and quiet: a Finding whose Evaluation cited nothing (a MISSING
    clause is the ordinary case) degrades to an ordinary question, never an error."""
    from tests.test_assist_explanations import _finding, _requirement

    rv = _requirement(db, owner)
    finding = _finding(db, owner, rv)          # no passages
    assert service._finding_evidence_ids(db, finding.id) == []


def test_an_unknown_finding_admits_nothing_rather_than_failing(db, owner):
    """A stale id from a client is not a 500."""
    assert service._finding_evidence_ids(db, uuid.uuid4()) == []


def test_a_follow_up_inherits_the_finding_the_previous_turn_named(db, owner):
    """Flow 8's mechanism. "Is this acceptable?" carries no subject of its own —
    that is what makes it a follow-up — so dropping the Finding on the very next
    question made it retrieve nothing while the clause it meant was on screen.

    Recorded on the retrieval run, and read back the same way the answered VERSION
    already is. Only the most recent turn is consulted.
    """
    from legalmind.assist import service as svc

    conversation_id = svc.create_conversation(db, user_id=owner.id, contract_id=None)
    message_id = svc._persist_turn(db, conversation_id, 0, "USER", "What does clause 13 say?")

    class _Empty:
        hits: typing.ClassVar[list] = []
        gate_open = False
        lexical_hit = False
        vector_top_score = None
        vector_peak_gap = None
        strategy_version = "test"
        embedding_model = None

    finding_id = uuid.uuid4()
    svc._persist_retrieval(db, message_id, "q", _Empty(), document_version_id=None,
                           finding_id=finding_id)

    assert svc._inherited_finding(db, conversation_id) == finding_id


def test_a_conversation_that_never_named_a_finding_inherits_nothing(db, owner):
    from legalmind.assist import service as svc

    conversation_id = svc.create_conversation(db, user_id=owner.id, contract_id=None)
    assert svc._inherited_finding(db, conversation_id) is None

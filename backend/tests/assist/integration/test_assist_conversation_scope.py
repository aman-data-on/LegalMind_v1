"""A conversation's document scope, and asking about a Finding (2026-09-11).

  - A standalone Ask chat never gains a Contract Review document: the 2026-09-11 route
    that attached one (`POST /conversations/{id}/document`) was withdrawn 2026-10-08
    when Contract Review and Ask became separate workflows.

  - `AskRequest.finding_id` seeds the RETRIEVAL query with the Finding's requirement and
    cited clause, so "why is this a deviation?" retrieves the clause instead of nothing.
    It never widens what the caller may read, and — the assertion that matters — the
    Finding's classification and the Company Standard value never reach the payload
    (`AM-30` t3, `AM-32` r4, unchanged by `AM-58`).
"""

from __future__ import annotations

import typing
import uuid

from sqlalchemy import text

from legalmind import config
from legalmind.assist import service
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    indexed_contract,
    storage,
)
from tests.assist.synthesis.test_assist_explanations import owner  # noqa: F401


def _scoped(db, conversation_id):
    schema = config.assist_schema()
    return db.execute(text(f'SELECT contract_id FROM "{schema}".conversations '
                           "WHERE id = :i"), {"i": conversation_id}).scalar()


# ==========================================================================
# A standalone Ask chat never gains a Contract Review document (2026-10-08)
# ==========================================================================
def test_a_standalone_chat_cannot_be_given_a_contract(api, db, seeded, storage):
    """Workflow isolation: the route that turned an Ask chat into a contract's chat is
    withdrawn, so a direct call — not only the screen — finds nothing to call, and the
    chat stays document-less. A contract is discussed from its own Review."""
    from legalmind.db import models as M
    from legalmind.domain import enums as E
    from tests.conftest import grant_role, make_user, sign_in

    owner = make_user(db)
    grant_role(db, owner, "USER")
    contract = M.Contract(owner_id=owner.id, name="Mine", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    db.commit()
    sign_in(api, db, owner)
    conversation_id = api.post("/api/v1/conversations", json={}).json()["data"]["id"]

    refused = api.post(f"/api/v1/conversations/{conversation_id}/document",
                       json={"contract_id": str(contract.id)})
    assert refused.status_code in (404, 405), refused.text
    assert _scoped(db, uuid.UUID(conversation_id)) is None


# ==========================================================================
# Asking about a Finding — the cited rows are admitted, the payload is not widened
# ==========================================================================
def test_a_findings_cited_rows_are_found_by_id(db, owner):
    """"Why is this a deviation?" carries no retrievable content of its own. The
    Finding already knows which rows it is about, so they are fetched by id rather
    than re-found by text — measured 2026-09-11: seeding the QUERY with the clause's
    own words made it longer, lexical search ANDs every stemmed term, and the gate
    stayed shut on a clause sitting in the same document."""
    from tests.assist.synthesis.test_assist_explanations import (
        PASSAGE,
        _finding,
        _requirement,
    )

    rv = _requirement(db, owner)
    finding = _finding(db, owner, rv, passages=(PASSAGE,))

    ids = service._finding_evidence_ids(db, finding.id)

    assert len(ids) == 1, "the one cited row, by id"


def test_the_cited_rows_resolve_to_chunks_inside_the_asked_version(db, owner):
    """`AM-25` r6: the chunk lookup is scoped to the one document version, so a
    Finding can never widen retrieval beyond the document being asked about."""
    from sqlalchemy import select

    from legalmind.assist.knowledge import store
    from legalmind.db import models as M
    from tests.assist.synthesis.test_assist_explanations import (
        PASSAGE,
        _finding,
        _requirement,
    )

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
    from tests.assist.synthesis.test_assist_explanations import _finding, _requirement

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

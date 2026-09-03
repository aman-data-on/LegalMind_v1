"""Which document version a question is answered from — the 2026-09-02 defect.

The reported symptom was UI copy: a reader with version 1 open saw the Ask input
disabled and a button offering to "open the latest version". The cause was not
copy. `POST /conversations/{id}/messages` resolved its target as
`MAX(version_number)` over the conversation's contract and gave the caller no way
to say otherwise, so an answer read while version 1 was on screen came from
version 2 — including every citation's `evidence_id`, which belongs to exactly one
version's reading order and therefore could not be highlighted on the open page.

These tests pin the corrected contract:

  * a named version is honoured, and only within the conversation's own contract
  * omitting the field still means "the newest", so the change is additive
  * the answer and the replayed transcript both STATE the version they read,
    because a contract-scoped conversation can legitimately hold turns from more
    than one and the reader must never have to assume

Nothing about retrieval, the gate, the guardrails or the refusal wording is
touched here; `test_assist_ask.py` owns those and they are unchanged.
"""

from __future__ import annotations

import uuid

from legalmind.assist import embedding_runtime
from tests.test_assist_ask import (
    DOCX_MIME,
    PARAGRAPHS,
    _fake_generation,
    build_docx,
)

REVISED = [
    "17.2 Limitation of Liability",
    "Neither party's aggregate liability under this Agreement shall exceed the "
    "total fees paid in the twenty-four months immediately preceding the event "
    "giving rise to the claim.",
    "22. Termination for Convenience",
    "Either party may terminate this Agreement for convenience on thirty days "
    "prior written notice to the other party.",
]

ASK = '"prior written notice" termination for convenience'


def _two_version_contract(api, db, user, monkeypatch):
    """A contract with v1 and v2 indexed, plus a conversation on it.

    The two versions deliberately disagree on the notice period (ninety days in
    v1, thirty in v2), so an answer names which document it read.
    """
    from tests.conftest import grant_role, sign_in

    embedding_runtime.reset_for_tests()
    grant_role(db, user, "USER")
    sign_in(api, db, user)
    contract_id = api.post(
        "/api/v1/contracts",
        json={"name": "Versioned MSA", "contract_type": "MSA"},
    ).json()["data"]["id"]

    def upload(paragraphs, filename):
        response = api.post(f"/api/v1/contracts/{contract_id}/document-versions",
                            content=build_docx(paragraphs),
                            headers={"content-type": DOCX_MIME,
                                     "x-filename": filename})
        assert response.status_code == 201, response.text
        return response.json()["data"]["document_version"]

    v1 = upload(PARAGRAPHS, "msa-v1.docx")
    v2 = upload(REVISED, "msa-v2.docx")
    assert (v1["version_number"], v2["version_number"]) == (1, 2)

    conversation_id = api.post("/api/v1/conversations",
                               json={"contract_id": contract_id}).json()["data"]["id"]
    return contract_id, v1, v2, conversation_id


# =====================================================================
# The defect itself
# =====================================================================
def test_a_reader_on_version_1_is_answered_from_version_1(api, db, seeded, user, monkeypatch):
    """The whole point. Naming v1 answers from v1 even though v2 exists — the
    case that previously had no expressible form and so was disabled in the UI."""
    _, v1, v2, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    _fake_generation(monkeypatch, "Termination requires ninety days notice [1].")

    reply = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                     json={"question": ASK, "document_version_id": v1["id"]})
    assert reply.status_code == 201, reply.text
    payload = reply.json()["data"]

    assert payload["document_version_id"] == v1["id"]
    assert payload["version_number"] == 1
    assert payload["document_version_id"] != v2["id"]


def test_every_citation_belongs_to_the_version_that_was_asked_about(
        api, db, seeded, user, monkeypatch):
    """The reason the version matters at all: `evidence_id` is what the workspace
    highlights, and an evidence row belongs to one version. A citation from the
    other version cannot be pointed at on the open page."""
    _, v1, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    _fake_generation(monkeypatch, "Termination requires ninety days notice [1].")

    payload = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                       json={"question": ASK,
                             "document_version_id": v1["id"]}).json()["data"]
    assert payload["citations"]

    evidence = api.get(f"/api/v1/document-versions/{v1['id']}/evidence")
    rows = {row["id"] for row in evidence.json()["data"]}
    for citation in payload["citations"]:
        assert citation["evidence_id"] in rows, (
            "a citation must point at an evidence row of the version that was "
            "asked about, or the workspace cannot highlight it")


def test_omitting_the_version_still_means_the_newest(api, db, seeded, user, monkeypatch):
    """The field is additive: every caller that does not send it keeps exactly
    the behaviour it had before the field existed."""
    _, _, v2, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    _fake_generation(monkeypatch, "Termination requires thirty days notice [1].")

    payload = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                       json={"question": ASK}).json()["data"]
    assert payload["document_version_id"] == v2["id"]
    assert payload["version_number"] == 2


# =====================================================================
# The scope can only narrow — never widen
# =====================================================================
def test_a_version_from_another_contract_is_refused(api, db, seeded, user, monkeypatch):
    """A version the caller CAN read, but which is not part of this conversation's
    contract, is refused rather than answered. Answering it would let one
    conversation mix two documents' evidence, which is what AM-25 r6's
    single-scope retrieval exists to prevent."""
    _, _, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    other = api.post("/api/v1/contracts",
                     json={"name": "Someone else's subject",
                           "contract_type": "MSA"}).json()["data"]["id"]
    foreign = api.post(f"/api/v1/contracts/{other}/document-versions",
                       content=build_docx(REVISED),
                       headers={"content-type": DOCX_MIME,
                                "x-filename": "other.docx"}
                       ).json()["data"]["document_version"]["id"]

    refused = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                       json={"question": ASK, "document_version_id": foreign})
    assert refused.status_code == 422, refused.text


def test_another_users_version_is_byte_identical_404(api, db, seeded, user, monkeypatch):
    """Naming a version is not a way around the Guard: one belonging to a
    contract outside the caller's scope reads exactly like one that does not
    exist (`AM-25` r6/r7, `API-10`)."""
    import json as _json

    from tests.conftest import grant_role, make_user, sign_in

    embedding_runtime.reset_for_tests()
    other = make_user(db)
    grant_role(db, other, "USER")
    sign_in(api, db, other)
    theirs = api.post("/api/v1/contracts",
                      json={"name": "Theirs", "contract_type": "MSA"}).json()["data"]["id"]
    hidden = api.post(f"/api/v1/contracts/{theirs}/document-versions",
                      content=build_docx(PARAGRAPHS),
                      headers={"content-type": DOCX_MIME, "x-filename": "t.docx"}
                      ).json()["data"]["document_version"]["id"]

    _, _, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    stolen = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                      json={"question": ASK, "document_version_id": hidden})
    ghost = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                     json={"question": ASK, "document_version_id": str(uuid.uuid4())})
    assert stolen.status_code == 404 and ghost.status_code == 404

    bodies = []
    for response in (stolen, ghost):
        body = response.json()
        body["error"]["request_id"] = "-"
        bodies.append(_json.dumps(body, sort_keys=True))
    assert bodies[0] == bodies[1]


def test_a_malformed_version_id_is_rejected_not_ignored(api, db, seeded, user, monkeypatch):
    """Falling back to "the newest" on a malformed id would answer about a
    different document than the caller asked for — silently, which is the whole
    class of bug this change removes."""
    _, _, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    response = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                        json={"question": ASK, "document_version_id": "not-a-uuid"})
    assert response.status_code == 422


# =====================================================================
# Replay — a conversation may span versions, and must say so
# =====================================================================
def test_a_replayed_transcript_states_each_turns_version(api, db, seeded, user, monkeypatch):
    """One conversation, two turns, two versions. The reload reports the version
    per turn, so the workspace can tell a citation it can highlight from one it
    cannot — instead of pointing at nothing and announcing that it did."""
    _, v1, v2, conversation_id = _two_version_contract(api, db, user, monkeypatch)

    _fake_generation(monkeypatch, "Termination requires ninety days notice [1].")
    api.post(f"/api/v1/conversations/{conversation_id}/messages",
             json={"question": ASK, "document_version_id": v1["id"]})
    _fake_generation(monkeypatch, "Termination requires thirty days notice [1].")
    api.post(f"/api/v1/conversations/{conversation_id}/messages",
             json={"question": ASK, "document_version_id": v2["id"]})

    loaded = api.get(f"/api/v1/conversations/{conversation_id}").json()["data"]
    answers = [m for m in loaded["messages"] if m["role"] == "ASSISTANT"]
    assert [a["version_number"] for a in answers] == [1, 2]
    assert [a["document_version_id"] for a in answers] == [v1["id"], v2["id"]]

    # And a question turn carries no version — it is not answered from anything.
    questions = [m for m in loaded["messages"] if m["role"] == "USER"]
    assert all(q["document_version_id"] is None for q in questions)
    assert all(q["version_number"] is None for q in questions)


def test_an_evaluator_routed_turn_reports_no_version(api, db, seeded, user, monkeypatch):
    """A compliance-shaped question is routed, never retrieved (`AM-25` r4), so
    there is no version it was read from. Reporting one would be a fabrication."""
    _, v1, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    routed = api.post(f"/api/v1/conversations/{conversation_id}/messages",
                      json={"question": "does this document meet our standard?",
                            "document_version_id": v1["id"]}).json()["data"]
    assert routed["routed_to_evaluator"] is True

    loaded = api.get(f"/api/v1/conversations/{conversation_id}").json()["data"]
    answer = next(m for m in loaded["messages"] if m["role"] == "ASSISTANT")
    assert answer["document_version_id"] is None
    assert answer["version_number"] is None


def test_the_retrieval_run_records_the_document_scope(api, db, seeded, user, monkeypatch):
    """`AM-27` describes `retrieval_runs` as "query, filters, chunk ids, scores".
    The document scope is the filter this retrieval applies, and recording it
    there is what makes an answer's version a fact on the row rather than
    something a reader reconstructs from a chunk id. No new column."""
    from sqlalchemy import text

    from legalmind import config

    _, v1, _, conversation_id = _two_version_contract(api, db, user, monkeypatch)
    _fake_generation(monkeypatch, "Termination requires ninety days notice [1].")
    api.post(f"/api/v1/conversations/{conversation_id}/messages",
             json={"question": ASK, "document_version_id": v1["id"]})

    schema = config.assist_schema()
    scopes = db.execute(text(f"""
        SELECT r.filters->>'document_version_id'
          FROM "{schema}".retrieval_runs r
          JOIN "{schema}".messages m ON m.id = r.message_id
         WHERE m.conversation_id = :c
    """), {"c": conversation_id}).scalars().all()
    assert scopes == [v1["id"]]

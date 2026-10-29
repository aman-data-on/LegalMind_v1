"""`AM-226` r7/r8 (2026-10-28): a question carries the files it was sent with, derived from
the two timestamps (nothing new is stored), and the chat list is searched over every chat
of the caller's own — never anyone else's. No model: the generation seam is offline."""
import pytest

from tests.assist.agent.test_assist_attachments import _api_conversation
from tests.assist.integration.test_assist_ask import storage  # noqa: F401  (fixture)


@pytest.fixture
def quiet(monkeypatch):
    from tests.assist.integration.test_conversation_multi_source import go_offline
    go_offline(monkeypatch)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")


def _upload(api, conv, name, body):
    r = api.post(f"/api/v1/conversations/{conv}/attachments", content=body,
                 headers={"Content-Type": "text/plain", "X-Filename": name})
    assert r.status_code == 201, r.text


def _ask(api, conv, question):
    r = api.post(f"/api/v1/conversations/{conv}/messages", json={"question": question})
    assert r.status_code == 201, r.text


def test_each_question_carries_the_files_saved_before_it(api, db, seeded, user, quiet):
    conv = _api_conversation(api, db, user)
    _upload(api, conv, "renewal.txt", b"Clause 4. The term renews for twelve months.")
    _upload(api, conv, "notice.txt", b"Clause 9. Either party may end this on 30 days notice.")
    _ask(api, conv, "What do these say about renewal?")
    _ask(api, conv, "And the notice period?")                      # no file of its own
    _upload(api, conv, "fees.txt", b"Clause 6. Fees are payable monthly in advance.")
    _ask(api, conv, "When are fees due?")

    turns = api.get(f"/api/v1/conversations/{conv}").json()["data"]["messages"]
    asked = [t for t in turns if t["role"] == "USER"]
    assert [[a["filename"] for a in t.get("attachments", [])] for t in asked] == [
        ["renewal.txt", "notice.txt"], [], ["fees.txt"]]
    assert all("attachments" not in t for t in turns if t["role"] == "ASSISTANT")
    # The view the list already gives: names, sizes and status, never the content.
    assert set(asked[0]["attachments"][0]) == {
        "id", "kind", "filename", "mime_type", "byte_size", "status", "failure_code",
        "pages_unread", "created_at", "expires_at"}


def test_an_old_chats_files_never_pass_to_its_next_question(api, db, seeded, user, quiet):
    """Files saved before this link existed stay unlinked; a new question takes only its
    own (the condition on the previous question's time)."""
    from sqlalchemy import text

    from legalmind import config
    conv = _api_conversation(api, db, user)
    _upload(api, conv, "old.txt", b"Clause 2. The old agreement.")
    _ask(api, conv, "What does it say?")
    db.execute(text(f'UPDATE "{config.assist_schema()}".conversation_attachments '
                    "SET message_id = NULL WHERE conversation_id = :c"), {"c": conv})
    _upload(api, conv, "new.txt", b"Clause 3. The new schedule.")
    _ask(api, conv, "And the schedule?")
    asked = [t for t in api.get(f"/api/v1/conversations/{conv}").json()["data"]["messages"]
             if t["role"] == "USER"]
    assert [[a["filename"] for a in t.get("attachments", [])] for t in asked] == [[], ["new.txt"]]


def test_search_reads_every_chat_of_the_callers_and_takes_the_term_literally(
        api, db, seeded, user, quiet):
    conv = _api_conversation(api, db, user)
    _ask(api, conv, "What is the termination notice period?")
    other = api.post("/api/v1/conversations", json={}).json()["data"]["id"]
    _ask(api, other, "Who owns the data?")

    def found(term):
        r = api.get("/api/v1/conversations", params={"q": term, "has_document": "false"})
        assert r.status_code == 200, r.text
        return [c["id"] for c in r.json()["data"]]

    assert found("TERMINATION") == [conv]          # any question, case-insensitive
    assert found("owns") == [other]
    assert found("%") == [] and found("_") == []   # a wildcard is a character, not a pattern

    from tests.conftest import grant_role, make_user, sign_in
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    assert found("termination") == []              # never another reader's chats

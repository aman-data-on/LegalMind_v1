"""A chat's model choice is the CHAT's (`AM-122`, owner 2026-10-08).

Before this the choice lived in one browser tab, so a chat reopened elsewhere went
back to Gemini, and the dock — which has no picker — always asked with the default.
Pinned here: the choice is stored when made, read back on reopening, used by a turn
that names no model, replaced only by a turn that names another, refused BY NAME when
the server cannot serve it (never silently replaced, `AM-116` r4), and invisible to a
stranger. Fixed replies ("hi") make every ask here zero-model.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist.agent import agent, model_router
from tests.assist.agent.test_assist_agent import ranked  # noqa: F401  (fixture)
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures)
    indexed_contract,
    storage,
)
from tests.conftest import grant_role, make_user, sign_in


@pytest.fixture
def deepseek_on(monkeypatch):
    """DeepSeek configured (key + URL + the agent path), with no egress possible."""
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    monkeypatch.setenv("LEGALMIND_INDIEROUTER_API_KEY", "sk-test-key-not-real-0123456789")
    monkeypatch.setenv("LEGALMIND_INDIEROUTER_BASE_URL", "https://router.example/v1")

    def refuse(*_a, **_k):
        raise AssertionError("no provider may be called in this test")
    monkeypatch.setattr(agent.OpenAICompatProvider, "turn", refuse)
    monkeypatch.setattr(agent.GeminiProvider, "turn", refuse)


def _chat(api, db, user, body: dict | None = None):
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    return api.post("/api/v1/conversations", json=body or {})


def _stored(db, conv) -> str | None:
    return db.execute(text(f'SELECT model FROM "{config.assist_schema()}".conversations '
                           "WHERE id = :c"), {"c": conv}).scalar()


def _error(response) -> dict:
    return {k: v for k, v in response.json()["error"].items() if k != "request_id"}


def test_a_chat_opened_without_a_choice_has_none_and_asks_with_the_default(
        api, db, seeded, user, deepseek_on):
    created = _chat(api, db, user).json()["data"]
    assert created["model"] is None
    detail = api.get(f"/api/v1/conversations/{created['id']}").json()["data"]
    assert detail["model"] is None
    asked = api.post(f"/api/v1/conversations/{created['id']}/messages",
                     json={"question": "hi"}).json()["data"]
    assert asked["model"] == model_router.DEFAULT == "gemini"
    assert _stored(db, created["id"]) is None, "the default is never written as a choice"


def test_a_chosen_model_is_stored_and_shown_on_reopening(api, db, seeded, user, deepseek_on):
    conv = _chat(api, db, user).json()["data"]["id"]
    changed = api.patch(f"/api/v1/conversations/{conv}", json={"model": "deepseek"})
    assert changed.status_code == 200 and changed.json()["data"]["model"] == "deepseek"
    assert api.get(f"/api/v1/conversations/{conv}").json()["data"]["model"] == "deepseek"
    listed = api.get("/api/v1/conversations").json()["data"]
    assert [c["model"] for c in listed if c["id"] == conv] == ["deepseek"]
    # the choice survives a rename, and a rename survives the choice
    api.patch(f"/api/v1/conversations/{conv}", json={"title": "Cap review"})
    detail = api.get(f"/api/v1/conversations/{conv}").json()["data"]
    assert detail["model"] == "deepseek"
    assert [c["title"] for c in listed if c["id"] == conv] != ["Cap review"]  # list was before


def test_a_chat_may_be_opened_on_a_model(api, db, seeded, user, deepseek_on):
    created = _chat(api, db, user, {"model": "deepseek"}).json()["data"]
    assert created["model"] == "deepseek" and _stored(db, created["id"]) == "deepseek"


def test_a_turn_naming_no_model_goes_to_the_chats_own(api, db, seeded, user, deepseek_on):
    conv = _chat(api, db, user).json()["data"]["id"]
    api.patch(f"/api/v1/conversations/{conv}", json={"model": "deepseek"})
    asked = api.post(f"/api/v1/conversations/{conv}/messages", json={"question": "hi"})
    assert asked.status_code == 201 and asked.json()["data"]["model"] == "deepseek"


def test_a_turn_naming_a_model_makes_it_the_chats_until_another_is_named(
        api, db, seeded, user, deepseek_on):
    conv = _chat(api, db, user).json()["data"]["id"]
    first = api.post(f"/api/v1/conversations/{conv}/messages",
                     json={"question": "hi", "model": "deepseek"}).json()["data"]
    assert first["model"] == "deepseek" and _stored(db, conv) == "deepseek"
    again = api.post(f"/api/v1/conversations/{conv}/messages",
                     json={"question": "thanks"}).json()["data"]
    assert again["model"] == "deepseek"
    back = api.post(f"/api/v1/conversations/{conv}/messages",
                    json={"question": "hello", "model": "gemini"}).json()["data"]
    assert back["model"] == "gemini" and _stored(db, conv) == "gemini"


def test_a_stored_model_the_server_cannot_serve_is_refused_by_name_never_replaced(
        api, db, seeded, user, deepseek_on, monkeypatch):
    conv = _chat(api, db, user).json()["data"]["id"]
    api.patch(f"/api/v1/conversations/{conv}", json={"model": "deepseek"})
    monkeypatch.delenv("LEGALMIND_INDIEROUTER_API_KEY")
    refused = api.post(f"/api/v1/conversations/{conv}/messages", json={"question": "hi"})
    assert refused.status_code == 422
    assert _error(refused)["code"] == "MODEL_NOT_CONFIGURED"
    assert "DeepSeek" in _error(refused)["message"]
    assert _stored(db, conv) == "deepseek", "the choice is the reader's; it is not undone"
    turns = db.execute(text(f'SELECT count(*) FROM "{config.assist_schema()}".messages '
                            "WHERE conversation_id = :c"), {"c": conv}).scalar_one()
    assert turns == 0, "nothing was stored, and nothing was answered by Gemini instead"
    # and the picker may still be moved back by the reader
    assert api.patch(f"/api/v1/conversations/{conv}",
                     json={"model": "gemini"}).status_code == 200


@pytest.mark.parametrize("where", ["create", "patch", "ask"])
def test_an_unknown_model_is_refused_everywhere_and_nothing_is_stored(
        api, db, seeded, user, deepseek_on, where):
    if where == "create":
        reply = _chat(api, db, user, {"model": "gpt-9"})
        assert reply.status_code == 422
        return
    conv = _chat(api, db, user).json()["data"]["id"]
    if where == "patch":
        reply = api.patch(f"/api/v1/conversations/{conv}", json={"model": "gpt-9"})
    else:
        reply = api.post(f"/api/v1/conversations/{conv}/messages",
                         json={"question": "hi", "model": "gpt-9"})
    assert reply.status_code == 422
    assert _stored(db, conv) is None


def test_a_patch_that_changes_nothing_is_refused(api, db, seeded, user, deepseek_on):
    conv = _chat(api, db, user).json()["data"]["id"]
    assert api.patch(f"/api/v1/conversations/{conv}", json={}).status_code == 422


def test_a_stranger_cannot_set_a_chats_model_and_learns_nothing(api, db, seeded, user,
                                                               deepseek_on):
    conv = _chat(api, db, user).json()["data"]["id"]
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    theirs = api.patch(f"/api/v1/conversations/{conv}", json={"model": "deepseek"})
    absent = api.patch(f"/api/v1/conversations/{uuid.uuid4()}", json={"model": "deepseek"})
    assert theirs.status_code == absent.status_code == 404
    assert _error(theirs) == _error(absent)
    assert _stored(db, conv) is None


# ==========================================================================
# The footer's three honest cases (`AM-122`)
# ==========================================================================
def test_a_fixed_reply_has_no_model_and_no_time_live_and_on_reload(
        api, db, seeded, user, deepseek_on):
    """'Answered without a model · 4 ms' read as a mystery: nothing was timed, because
    nothing ran. A fixed reply stores no latency, so the footer can say 'instant'."""
    conv = _chat(api, db, user).json()["data"]["id"]
    live = api.post(f"/api/v1/conversations/{conv}/messages",
                    json={"question": "hi"}).json()["data"]
    assert live["answered_by"] is None and live["latency_ms"] is None
    replay = [m for m in api.get(f"/api/v1/conversations/{conv}").json()["data"]["messages"]
              if m["role"] == "ASSISTANT"][-1]
    assert replay["answered_by"] is None and replay["latency_ms"] is None


# ==========================================================================
# "ok" after an offer takes the offer up (`AM-122` r3) — the model is asked
# ==========================================================================
def test_an_acknowledgement_after_an_offering_reply_reaches_the_model(
        api, db, seeded, user, indexed_contract, ranked, monkeypatch):
    """A reader answered thirteen offers with "ok" and got the fixed line each time
    (2026-10-07). With the previous reply ending in an offer, "ok" is a turn for the
    model — with the thread, so it knows what was offered."""
    import json as _json

    from tests.assist.agent.test_assist_agent import Scripted, _turn
    contract, _ = indexed_contract
    final = _json.dumps({"blocks": [{"kind": "reasoning", "text": "Here are the exceptions."}],
                         "assessment": "n/a"})
    fake = Scripted(_turn(text_=""), final=final)
    monkeypatch.setattr(agent, "GeminiProvider", lambda: fake)
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    conv = api.post("/api/v1/conversations",
                    json={"contract_id": str(contract.id)}).json()["data"]["id"]
    from legalmind.assist import service
    service._persist_turn(db, uuid.UUID(conv), 0, "USER", "What is the cap?")
    service._persist_turn(db, uuid.UUID(conv), 1, "ASSISTANT",
                          "Twelve months of fees.\n\nShall I explain the exceptions next?")
    db.commit()
    live = api.post(f"/api/v1/conversations/{conv}/messages",
                    json={"question": "ok"}).json()["data"]
    assert fake.seen, "the acknowledgement was answered by the fixed line, not the model"
    assert live["answered_by"] is not None and "exceptions" in live["text"]
    # and after a reply that offers nothing, "ok" is still small talk: zero calls
    service._persist_turn(db, uuid.UUID(conv), 4, "USER", "Thanks.")
    service._persist_turn(db, uuid.UUID(conv), 5, "ASSISTANT", "The cap is twelve months.")
    db.commit()
    calls = len(fake.seen)
    plain = api.post(f"/api/v1/conversations/{conv}/messages",
                     json={"question": "ok"}).json()["data"]
    assert plain["answered_by"] is None and len(fake.seen) == calls

"""The Ask chat's own controls (`AM-116`, owner 2026-10-06): the model the reader
picks, a chat's name, and deleting a chat.

What must NOT happen is pinned as closely as what must: an id from the browser is
never trusted, a model that is not configured is refused by name and never answered
by Gemini instead, and nobody renames or deletes a chat that is not their own — a
stranger's attempt is the same 404 as an id that does not exist, and changes nothing.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import service
from legalmind.assist.agent import agent, model_router
from legalmind.assist.llm import generation
from legalmind.db import models as M
from legalmind.security import audit
from tests.conftest import grant_role, make_user, sign_in


@pytest.fixture
def no_egress(monkeypatch):
    """Any provider call fails the test: a refused model must spend nothing."""
    def refuse(*_a, **_k):
        raise AssertionError("a provider was called")
    monkeypatch.setattr(generation, "generate", refuse)
    monkeypatch.setattr(generation, "generate_turn", refuse)
    for m in model_router.MODELS.values():
        if m.id != model_router.DEFAULT:
            monkeypatch.delenv(m.key_env, raising=False)


def _chat(api, db, user) -> str:
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    return api.post("/api/v1/conversations", json={}).json()["data"]["id"]


def _count(db, table: str, conversation_id) -> int:
    return db.execute(text(f'SELECT count(*) FROM "{config.assist_schema()}".{table} '
                           "WHERE " + ("id" if table == "conversations"
                                       else "conversation_id") + " = :c"),
                      {"c": conversation_id}).scalar_one()


def _error(response) -> dict:
    return {k: v for k, v in response.json()["error"].items() if k != "request_id"}


# ==========================================================================
# The model registry and router
# ==========================================================================
def test_no_model_means_gemini_and_gemini_is_served_by_its_adapter():
    assert model_router.resolve(None).id == "gemini"
    assert isinstance(model_router.provider("gemini"), agent.GeminiProvider)


@pytest.mark.parametrize("model_id", ["deepseek", "qwen", "bonsai"])
def test_a_listed_model_without_an_adapter_is_refused_even_with_a_key(model_id,
                                                                      monkeypatch):
    """A key alone configures nothing: there is no adapter, so nothing is pretended."""
    monkeypatch.setenv(model_router.MODELS[model_id].key_env, "sk-real-looking-key")
    with pytest.raises(model_router.ModelNotConfigured):
        model_router.resolve(model_id)


def test_an_unlisted_id_is_refused_not_trusted():
    with pytest.raises(model_router.UnknownModel):
        model_router.resolve("gpt-something")


def test_an_adapter_serves_only_with_its_key_and_url_on_the_agent_path(monkeypatch):
    """Adapter + key + base URL make a model configured (`AM-117`) — and only where the
    agent routes by provider. On the older pipeline it would be answered by Gemini, so
    it is refused; without its URL it is refused; a key alone (Qwen) serves nothing."""
    sentinel = object()
    monkeypatch.setitem(model_router.ADAPTERS, "openai", lambda model: sentinel)
    monkeypatch.setenv("LEGALMIND_INDIEROUTER_API_KEY", "sk-real-looking-key")
    monkeypatch.setenv("LEGALMIND_INDIEROUTER_BASE_URL", "https://router.example/v1")
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    assert model_router.provider("deepseek") is sentinel
    assert model_router.egress_hosts() == ["router.example"]
    with pytest.raises(model_router.ModelNotConfigured):
        model_router.resolve("qwen")
    monkeypatch.delenv("LEGALMIND_INDIEROUTER_BASE_URL")
    with pytest.raises(model_router.ModelNotConfigured):
        model_router.resolve("deepseek")
    monkeypatch.setenv("LEGALMIND_INDIEROUTER_BASE_URL", "https://router.example/v1")
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "off")
    with pytest.raises(model_router.ModelNotConfigured):
        model_router.resolve("deepseek")


def test_the_model_list_says_which_models_are_configured(api, db, seeded, user,
                                                         no_egress):
    _chat(api, db, user)
    listed = api.get("/api/v1/ask/models").json()["data"]
    assert [m["id"] for m in listed] == ["gemini", "deepseek", "qwen", "bonsai"]
    assert {m["id"]: m["configured"] for m in listed} == {
        "gemini": True, "deepseek": False, "qwen": False, "bonsai": False}
    assert [m["id"] for m in listed if m["default"]] == ["gemini"]


def test_a_model_that_is_not_configured_is_refused_by_name_and_nothing_is_stored(
        api, db, seeded, user, no_egress):
    conv = _chat(api, db, user)
    reply = api.post(f"/api/v1/conversations/{conv}/messages",
                     json={"question": "What is our liability cap?", "model": "deepseek"})
    assert reply.status_code == 422
    assert reply.json()["error"]["code"] == "MODEL_NOT_CONFIGURED"
    assert "DeepSeek is not configured" in reply.json()["error"]["message"]
    assert _count(db, "messages", conv) == 0


def test_an_unknown_model_id_is_refused_and_nothing_is_stored(api, db, seeded, user,
                                                              no_egress):
    conv = _chat(api, db, user)
    reply = api.post(f"/api/v1/conversations/{conv}/messages",
                     json={"question": "What is our liability cap?", "model": "x" * 20})
    assert reply.status_code == 422
    assert reply.json()["error"]["code"] == "BUSINESS_RULE_REJECTED"
    assert _count(db, "messages", conv) == 0


def test_the_agent_is_handed_the_adapter_for_the_chosen_model(db, user, monkeypatch):
    """service → model_router → adapter: the provider the agent runs with is the one
    the router returns for the reader's model, not a hard-wired Gemini."""
    seen = []
    monkeypatch.setattr(model_router, "provider", lambda m: seen.append(m) or object())
    monkeypatch.setattr(agent, "run_turn", lambda provider, *a, **k: (_ for _ in ()).throw(
        RuntimeError("stop")))
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    with pytest.raises(RuntimeError, match="stop"):
        service._agent_answer(db, conv, user.id, "What is our cap?",
                              frozenset({"assist.ask"}), None, "gemini")
    assert seen == ["gemini"]


# ==========================================================================
# Renaming a chat
# ==========================================================================
def test_the_owner_renames_a_chat_and_the_list_carries_the_name(api, db, seeded, user):
    conv = _chat(api, db, user)
    reply = api.patch(f"/api/v1/conversations/{conv}", json={"title": "  Cap   review \t"})
    assert reply.status_code == 200
    assert reply.json()["data"]["title"] == "Cap review"
    listed = api.get("/api/v1/conversations").json()["data"]
    assert [c["title"] for c in listed if c["id"] == conv] == ["Cap review"]


@pytest.mark.parametrize("title", ["", "   ", "two\nlines", "bell\x07", "x" * 121])
def test_an_empty_or_invalid_name_is_refused_and_the_old_one_kept(api, db, seeded, user,
                                                                  title):
    conv = _chat(api, db, user)
    api.patch(f"/api/v1/conversations/{conv}", json={"title": "Kept"})
    reply = api.patch(f"/api/v1/conversations/{conv}", json={"title": title})
    assert reply.status_code == 422
    listed = api.get("/api/v1/conversations").json()["data"]
    assert [c["title"] for c in listed if c["id"] == conv] == ["Kept"]


def test_a_stranger_cannot_rename_a_chat_and_learns_nothing(api, db, seeded, user):
    conv = _chat(api, db, user)
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    theirs = api.patch(f"/api/v1/conversations/{conv}", json={"title": "Mine now"})
    absent = api.patch(f"/api/v1/conversations/{uuid.uuid4()}", json={"title": "Mine now"})
    assert theirs.status_code == absent.status_code == 404
    assert _error(theirs) == _error(absent)
    title = db.execute(text(f'SELECT title FROM "{config.assist_schema()}".conversations '
                            "WHERE id = :c"), {"c": conv}).scalar()
    assert title is None


# ==========================================================================
# Deleting a chat
# ==========================================================================
def test_the_owner_deletes_a_chat_with_everything_under_it(api, db, seeded, user):
    conv = _chat(api, db, user)
    service._persist_turn(db, uuid.UUID(conv), 0, "USER", "What is our cap?")
    service._persist_turn(db, uuid.UUID(conv), 1, "ASSISTANT", "Twelve months of fees.")
    db.commit()
    assert api.delete(f"/api/v1/conversations/{conv}").status_code == 204
    assert _count(db, "conversations", conv) == 0
    assert _count(db, "messages", conv) == 0
    assert conv not in [c["id"] for c in api.get("/api/v1/conversations").json()["data"]]
    assert api.get(f"/api/v1/conversations/{conv}").status_code == 404
    assert api.delete(f"/api/v1/conversations/{conv}").status_code == 404


def test_the_deletion_is_audited_with_counts_and_no_text(api, db, seeded, user):
    conv = _chat(api, db, user)
    api.patch(f"/api/v1/conversations/{conv}", json={"title": "Secret deal name"})
    service._persist_turn(db, uuid.UUID(conv), 0, "USER", "What about the secret deal?")
    db.commit()
    api.delete(f"/api/v1/conversations/{conv}")
    event = db.query(M.AuditEvent).filter_by(
        action=audit.ASSIST_CONVERSATION_DELETED, entity_id=uuid.UUID(conv)).one()
    assert event.actor_id == user.id
    assert "secret" not in str(event.before_state).lower()
    assert event.before_state["message_count"] == 1


def test_a_stranger_cannot_delete_a_chat_and_learns_nothing(api, db, seeded, user):
    conv = _chat(api, db, user)
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    theirs = api.delete(f"/api/v1/conversations/{conv}")
    absent = api.delete(f"/api/v1/conversations/{uuid.uuid4()}")
    assert theirs.status_code == absent.status_code == 404
    assert _error(theirs) == _error(absent)
    assert _count(db, "conversations", conv) == 1

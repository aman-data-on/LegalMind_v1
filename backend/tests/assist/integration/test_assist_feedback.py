"""Answer feedback (`AM-123`, owner D2c 2026-10-08): the reader's rating and the
implicit signals, logged for evaluation and never used to tune anything (`AM-26`).

Pinned as closely as what it records: only the answer's own reader can leave feedback,
and anyone else — or a user turn, or an id that does not exist — gets one identical 404;
the reason never reaches the audit trail or a log line; repeats are one row.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from legalmind import config
from legalmind.assist import feedback, service
from legalmind.assist.agent import agent
from legalmind.db import models as M
from legalmind.security import audit
from tests.assist.agent.test_assist_agent import ranked  # noqa: F401  (fixture)
from tests.assist.integration.test_assist_ask import (  # noqa: F401  (fixtures)
    indexed_contract,
    storage,
)
from tests.conftest import grant_role, make_user, sign_in
from tests.test_observability import captured  # noqa: F401  (fixture)
from tools import feedback_report

URL = "/api/v1/feedback"


def _answer(api, db, user, question="What is our liability cap?",
            sign=True) -> tuple[str, str, str]:
    """A signed-in reader's chat with one question and one answer: (chat, user turn,
    answer) ids."""
    if sign:
        grant_role(db, user, "USER")
        db.commit()
        sign_in(api, db, user)
    conv = api.post("/api/v1/conversations", json={}).json()["data"]["id"]
    asked = service._persist_turn(db, uuid.UUID(conv), 0, "USER", question)
    answer = service._persist_turn(db, uuid.UUID(conv), 1, "ASSISTANT", "Twelve months.")
    db.commit()
    return conv, str(asked), str(answer)


def _rows(db, message_id) -> list[tuple]:
    return db.execute(text(
        f'SELECT kind, rating, reason, query_type FROM "{config.assist_schema()}".'
        "answer_feedback WHERE message_id = :m ORDER BY kind"), {"m": message_id}).all()


def _error(response) -> dict:
    return {k: v for k, v in response.json()["error"].items() if k != "request_id"}


def test_a_rating_is_recorded_flips_in_place_and_returns_only_its_id(api, db, seeded,
                                                                      user):
    _, _, answer = _answer(api, db, user)
    up = api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "UP"})
    assert up.status_code == 201 and set(up.json()["data"]) == {"id"}
    down = api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN",
                               "reason": "  Missed   the carve-out "})
    assert down.json()["data"]["id"] == up.json()["data"]["id"]
    assert _rows(db, answer) == [("RATING", "DOWN", "Missed the carve-out", "ANSWER:NONE")]


def test_the_reason_never_reaches_the_audit_trail(api, db, seeded, user):
    _, _, answer = _answer(api, db, user)
    api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN",
                        "reason": "secret deal wording"})
    [event] = db.query(M.AuditEvent).filter_by(
        action=audit.ASSIST_FEEDBACK_RECORDED, entity_id=uuid.UUID(answer)).all()
    assert event.actor_id == user.id and event.after_state == {"kind": "RATING"}
    assert "secret" not in str(event.before_state) + str(event.after_state)


def test_an_implicit_signal_twice_is_one_row(api, db, seeded, user):
    _, _, answer = _answer(api, db, user)
    for _ in range(2):
        assert api.post(URL, json={"message_id": answer, "kind": "COPY"}).status_code == 201
    api.post(URL, json={"message_id": answer, "kind": "CITE_CLICK"})
    assert _rows(db, answer) == [("CITE_CLICK", None, None, "ANSWER:NONE"),
                                 ("COPY", None, None, "ANSWER:NONE")]


@pytest.mark.parametrize("body", [
    {"kind": "RATING"},                                      # a rating with no value
    {"kind": "COPY", "rating": "UP"},                        # a value on a signal
    {"kind": "COPY", "reason": "why"},                       # a reason with no rating
    {"kind": "REASK"},                                       # server-side only
    {"kind": "RATING", "rating": "MATCH"},                   # no legal-axis vocabulary
    {"kind": "RATING", "rating": "DOWN", "reason": "two\nlines"},
    {"kind": "RATING", "rating": "DOWN", "reason": "x" * 501},
])
def test_a_malformed_signal_is_refused_and_nothing_stored(api, db, seeded, user, body):
    _, _, answer = _answer(api, db, user)
    assert api.post(URL, json={"message_id": answer, **body}).status_code == 422
    assert _rows(db, answer) == []


def test_a_stranger_a_user_turn_and_an_unknown_id_are_one_identical_404(api, db, seeded,
                                                                         user):
    _, asked, answer = _answer(api, db, user)
    body = {"kind": "RATING", "rating": "DOWN"}
    own_user_turn = api.post(URL, json={"message_id": asked, **body})
    stranger = make_user(db)
    grant_role(db, stranger, "USER")
    db.commit()
    sign_in(api, db, stranger)
    theirs = api.post(URL, json={"message_id": answer, **body})
    fake = str(uuid.uuid4())
    absent = api.post(URL, json={"message_id": fake, **body})
    assert own_user_turn.status_code == theirs.status_code == absent.status_code == 404
    # the same body with the id swapped: nothing says which case it was
    assert (json.dumps(_error(theirs)).replace(answer, fake)
            == json.dumps(_error(absent)))
    assert json.dumps(_error(own_user_turn)).replace(asked, fake) == json.dumps(
        _error(absent))
    assert _rows(db, answer) == [] and _rows(db, asked) == []


def test_feedback_goes_with_its_chat(api, db, seeded, user):
    conv, _, answer = _answer(api, db, user)
    api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN",
                        "reason": "wrong"})
    assert api.delete(f"/api/v1/conversations/{conv}").status_code == 204
    assert _rows(db, answer) == []


def test_the_third_not_helpful_on_one_query_type_raises_the_alert(api, db, seeded, user,
                                                                   captured):
    alerts = []
    for n in range(3):
        _, _, answer = _answer(api, db, user, question=f"Summarise clause {n}",
                               sign=n == 0)
        api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN"})
        alerts.append([e for e in captured()
                       if e.get("event") == feedback.DOWN_CLUSTER_SIGNAL])
    assert [len(a) for a in alerts] == [0, 0, 1]
    [alert] = alerts[-1]
    assert alert["level"] == "WARNING"
    assert alert["query_type"] == "SUMMARY:NONE" and alert["count"] == 3
    assert feedback_report.flags(db) == [{"query_type": "SUMMARY:NONE", "count": 3}]


def test_the_same_vote_again_keeps_its_reason_and_does_not_alert_again(api, db, seeded,
                                                                       user, captured):
    for n in range(3):
        _, _, answer = _answer(api, db, user, question=f"Summarise clause {n}",
                               sign=n == 0)
        api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN",
                            "reason": "missed the carve-out"})
    for _ in range(2):        # the reader clicks the pressed "Not helpful" again
        api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN"})
    assert _rows(db, answer) == [("RATING", "DOWN", "missed the carve-out",
                                  "SUMMARY:NONE")]
    assert len([e for e in captured()
                if e.get("event") == feedback.DOWN_CLUSTER_SIGNAL]) == 1
    api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "UP"})
    assert _rows(db, answer)[0][1:3] == ("UP", None)     # a flip clears the reason


def test_a_not_helpful_older_than_the_window_is_not_counted(api, db, seeded, user):
    _, _, answer = _answer(api, db, user, question="Summarise clause 1")
    api.post(URL, json={"message_id": answer, "kind": "RATING", "rating": "DOWN"})
    assert feedback.down_count(db, "SUMMARY:NONE") == 1
    db.execute(text(f'UPDATE "{config.assist_schema()}".answer_feedback SET created_at '
                    "= now() - make_interval(days => :d + 1)"),
               {"d": feedback.DOWN_CLUSTER_DAYS})
    assert feedback.down_count(db, "SUMMARY:NONE") == 0


def test_the_corpus_version_is_the_live_corpus_stamp(api, db, seeded, user):
    """Not a code constant: the stamp `cache.corpus_version` moves on any re-ingest
    (see its docstring), so feedback before and after one stays apart."""
    from legalmind.assist.retrieval import cache
    _, _, answer = _answer(api, db, user)
    api.post(URL, json={"message_id": answer, "kind": "COPY"})
    stored = db.execute(text(f'SELECT corpus_version FROM "{config.assist_schema()}".'
                             "answer_feedback")).scalar()
    assert stored.endswith("|" + cache.corpus_version(db))


def test_the_same_question_again_is_a_reask_and_live_answers_name_their_prompt(
        api, db, seeded, user, indexed_contract, ranked, monkeypatch):
    from tests.assist.agent.test_assist_agent import SEARCH, Scripted, _turn
    contract, _ = indexed_contract
    final = json.dumps({"blocks": [{"kind": "sourced", "text": "Ninety days.",
                                    "cites": ["D1"]}], "assessment": "supported"})
    monkeypatch.setattr(agent, "GeminiProvider",
                        lambda: Scripted(_turn(calls=[SEARCH]), final=final))
    monkeypatch.setenv("LEGALMIND_ASK_AGENT_MODE", "on")
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    conv = api.post("/api/v1/conversations",
                    json={"contract_id": str(contract.id)}).json()["data"]["id"]
    ask = f"/api/v1/conversations/{conv}/messages"
    first = api.post(ask, json={"question": "What is the notice period?"}).json()["data"]
    api.post(ask, json={"question": "what is the  notice period"})
    assert _rows(db, first["message_id"]) == [("REASK", None, None, "ANSWER:DOCUMENTS")]
    code = db.execute(text(f"""
        SELECT pv.code FROM "{config.assist_schema()}".ai_answers a
          JOIN "{config.assist_schema()}".prompt_versions pv ON pv.id = a.prompt_version_id
         WHERE a.message_id = :m"""), {"m": first["message_id"]}).scalar()
    assert code == agent.PROMPT_VERSION


def test_the_monthly_export_refuses_any_path_inside_a_checkout(tmp_path):
    with pytest.raises(SystemExit, match="inside a git checkout"):
        feedback_report.write_cases([], feedback_report.Path(__file__).parent / "x.json")
    out = tmp_path / "2026-10.json"
    feedback_report.write_cases([{"question": "q"}], out)
    assert json.loads(out.read_text())["negative_examples_for_curation"] == [
        {"question": "q"}]
    assert out.stat().st_mode & 0o777 == 0o600
    out.chmod(0o644)                  # an existing, wider file is narrowed on overwrite
    feedback_report.write_cases([], out)
    assert out.stat().st_mode & 0o777 == 0o600

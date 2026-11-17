"""AB-209: keep approved words as written (`AM-390`), our signatory on the template
(`AM-391`), a blank in approved words made a fill-in field (`AM-392`). The STRUCTURAL
placeholder with synthetic text only (rule 21)."""

import uuid

import pytest

from legalmind.db import models as M
from legalmind.drafting import library, publish
from legalmind.drafting import model as model_
from tests.conftest import sign_in
from tests.drafting.test_templates_api import _url, lawyer, staff, template  # noqa: F401

UNDEFINED = "“Placeholder Partner” is used in quotes and never defined"


@pytest.fixture
def ready(db, api, template, lawyer, user, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    db.flush()
    sign_in(api, db, lawyer)
    return template


def _approve_rest(api, tv, but):
    for pin in library.pins(tv):
        if pin["clause_key"] != but:
            assert api.post(_url(tv, f"/clauses/{pin['clause_key']}/approve")
                            ).status_code == 200


def test_an_undefined_term_can_be_kept_as_written_and_the_template_publishes(
        db, api, ready, staff, lawyer):
    rep = api.post(_url(ready, "/clauses/CLAUSE_E/replace"), json={
        "text": "A “Placeholder Partner” may have placeholder terms.", "reason": "ours"})
    assert rep.status_code == 200, rep.text
    _approve_rest(api, ready, "CLAUSE_E")
    refused = api.post(_url(ready, "/publish"))
    assert f"PREFLIGHT UNDEFINED_TERM: {UNDEFINED}" in refused.json()["error"]["problems"]
    # only an approver, only a keepable code, never without a reason
    keep = {"code": "UNDEFINED_TERM", "detail": UNDEFINED, "reason": "Our MSA, as signed"}
    assert api.post(_url(ready, "/keep-as-written"),
                    json={**keep, "reason": ""}).status_code == 422
    assert api.post(_url(ready, "/keep-as-written"),
                    json={**keep, "code": "REF_NO_BOOKMARK"}).status_code == 409
    sign_in(api, db, staff)
    assert api.post(_url(ready, "/keep-as-written"), json=keep).status_code == 404
    sign_in(api, db, lawyer)
    ok = api.post(_url(ready, "/keep-as-written"), json=keep)
    assert ok.status_code == 200, ok.text
    assert [(k["code"], k["reason"], k["by"]) for k in ok.json()["data"]["kept"]] == [
        ("UNDEFINED_TERM", "Our MSA, as signed", lawyer.name)]
    assert api.get(_url(ready)).json()["data"]["kept"][0]["detail"] == UNDEFINED
    assert api.get(_url(ready, "/check")).json()["data"]["problems"] == []
    done = api.post(_url(ready, "/publish"))
    assert done.status_code == 200, done.text
    assert db.query(M.AuditEvent).filter_by(action=publish.TEXT_KEPT,
                                            entity_id=ready.id).count() == 1
    # published: nothing more is kept on this version
    assert api.post(_url(ready, "/keep-as-written"), json=keep).status_code == 409


def test_our_signatory_is_fixed_on_the_template(db, api, ready):
    bad = api.post(_url(ready, "/our-signatory"), json={
        "name": "Signer Placeholder", "designation": "Director", "email": "not-an-email"})
    assert bad.status_code == 409 and "email" in bad.json()["error"]["message"]
    ok = api.post(_url(ready, "/our-signatory"), json={
        "name": "Signer Placeholder", "designation": "Director",
        "email": "signer@example.test"})
    assert ok.status_code == 200, ok.text
    db.refresh(ready)
    fixed = {model_.role(v): v.get("locked_value") for v in ready.variables}
    assert (fixed["our_signatory_name"], fixed["our_signatory_email"]) == (
        "Signer Placeholder", "signer@example.test")
    assert not {"party_one_signatory", "party_one_email"} & set(
        ready.layout.get("check_values", {}))
    event = db.query(M.AuditEvent).filter_by(action="template.signatory_set",
                                             entity_id=ready.id).one()
    assert "Signer Placeholder" not in str(event.after_state)          # personal data
    _approve_rest(api, ready, None)
    assert api.get(_url(ready, "/check")).json()["data"]["problems"] == []


def test_a_blank_becomes_a_fill_in_field_and_the_words_never_change(db, api, ready):
    rep = api.post(_url(ready, "/clauses/CLAUSE_B/replace"), json={
        "text": "Placeholder days at ______ and ______ months.", "reason": "ours"})
    assert rep.status_code == 200, rep.text
    clause = next(c for c in api.get(_url(ready)).json()["data"]["clauses"]
                  if c["clause_key"] == "CLAUSE_B")
    assert [(b["n"], b["field"]) for b in clause["blanks"]] == [(1, None), (2, None)]
    assert api.post(_url(ready, "/blank-fields"), json={
        "where": "CLAUSE_B", "n": 3, "label": "Place"}).status_code == 409
    assert api.post(_url(ready, "/blank-fields"), json={
        "where": "CLAUSE_B", "n": 1, "label": "bad_label"}).status_code == 409
    # AM-394: an optional blank needs the value it takes when sales leaves it empty
    assert api.post(_url(ready, "/blank-fields"), json={
        "where": "CLAUSE_B", "n": 2, "label": "Months", "required": False}).status_code == 409
    for n, label, required in ((1, "Placeholder place", True),
                               (2, "Placeholder months", False)):
        made = api.post(_url(ready, "/blank-fields"), json={
            "where": "CLAUSE_B", "n": n, "label": label, "required": required,
            **({} if required else {"default": "Six"})})
        assert made.status_code == 200, made.text
    assert api.post(_url(ready, "/blank-fields"), json={
        "where": "CLAUSE_B", "n": 1, "label": "Again"}).status_code == 409
    clause = next(c for c in made.json()["data"]["clauses"]
                  if c["clause_key"] == "CLAUSE_B")
    assert [b["field"]["required"] for b in clause["blanks"]] == [True, False]
    _approve_rest(api, ready, "CLAUSE_B")
    assert api.get(_url(ready, "/check")).json()["data"]["problems"] == []
    db.refresh(ready)
    rows = publish.pinned_clauses(db, ready)
    hashes = {k: r.content_hash for k, r in rows.items()}
    clauses = {k: publish.clause_dict(r) for k, r in rows.items()}
    answers = dict(ready.layout["check_values"])
    filled = model_.resolve(publish.template_dict(ready), clauses,
                            {**answers, "blank_2": "Seven"})
    text = str(filled)
    assert "Check value" in text and "Seven" in text and "______" not in text
    left = str(model_.resolve(publish.template_dict(ready), clauses, answers))
    assert "Six" in left and "______" not in left     # unanswered: Legal's default
    with pytest.raises(model_.ModelError, match="blank_1"):
        model_.resolve(publish.template_dict(ready), clauses,
                       {k: v for k, v in answers.items() if k != "blank_1"})
    assert {k: r.content_hash for k, r in publish.pinned_clauses(db, ready).items()
            } == hashes


@pytest.mark.parametrize("text, out", [
    ("banks at ___________are open", "banks at Pune are open"),
    ("providing _______________ .", "providing Pune."),
    ("providing ____, and", "providing Pune, and"),
    ("at ____ and ____", "at Pune and ____"),
])
def test_a_filled_blank_reads_as_a_sentence(text, out):
    """AM-394: no glued word, no space before punctuation; an unfilled run stays."""
    tpl = {"variables": [{"key": "b", "blank": {"in": "C", "n": 1}}], "layout": {}}
    _, clauses = model_._fill_blanks(tpl, {("C", 1): {"clause_key": "C", "body": text}},
                                     {"b": "x"})
    assert clauses[("C", 1)]["body"].replace("{b}", "Pune") == out

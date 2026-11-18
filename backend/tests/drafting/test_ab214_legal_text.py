"""AB-214 `AM-412`/`AM-414`: Legal may add its own wording to Annexure 1 and Annexure 2 on
the template page — a DRAFT clause version, approved and published like any clause.
Optional: neither is needed for a final contract. The strings below are test stand-ins
that say so; nothing here is a legal text (rule 21).
"""

from __future__ import annotations

from sqlalchemy import select

from legalmind.db import models as M
from legalmind.drafting import library, publish, special_conditions
from legalmind.drafting import model as model_
from tests.conftest import sign_in
from tests.drafting.test_final_package_s3 import T, _imported
from tests.drafting.test_new_contract import staff  # noqa: F401 — fixtures
from tests.drafting.test_template_keep_signatory_blanks import ready  # noqa: F401
from tests.drafting.test_templates_api import _url, lawyer, template  # noqa: F401

WORDS = "[TEST STAND-IN — not legal text] first line\n\n[TEST STAND-IN] second line"
SENTENCE = "[TEST STAND-IN — not legal text] precedence sentence"


def _places(api, tv):
    return {p["which"]: p for p in api.get(_url(tv, "")).json()["data"]["legal_text"]}


def test_the_annexure_1_wording_starts_empty_and_goes_draft_approve(db, api, ready, lawyer):
    assert _places(api, ready) == {}                      # no annexure: no place
    assert api.post(_url(ready, "/annexure-1")).status_code == 200
    place = _places(api, ready)["annexure_1"]
    assert (place["supplied"], place["text"], place["editable"]) == (False, None, True)
    assert api.post(_url(ready, "/legal-text"), json={
        "which": "precedence", "text": SENTENCE}).status_code == 409   # no such place
    for bad in ("   ", model_.LEGAL_TO_SUPPLY, "words with a {field}"):   # the old stand-in too
        assert api.post(_url(ready, "/legal-text"), json={
            "which": "annexure_1", "text": bad}).status_code in (409, 422)
    made = api.post(_url(ready, "/legal-text"), json={"which": "annexure_1", "text": WORDS})
    assert made.status_code == 200, made.text
    place = {p["which"]: p for p in made.json()["data"]["legal_text"]}["annexure_1"]
    assert (place["supplied"], place["approved"]) == (True, False)
    assert place["text"] == WORDS.replace("\n\n", "\n")
    db.refresh(ready)
    pin = ready.annexures[-1]["clauses"][0]
    row = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == pin["clause_key"],
        M.ClauseVersion.version == pin["version"])).scalar_one()
    # a DRAFT like any clause, the form's tables untouched, Legal's lines first
    assert (row.status, row.version, row.source["kind"]) == ("DRAFT", 2, library.LEGAL_TEXT)
    assert [b["text"] for b in row.body[:2]] == WORDS.split("\n\n")      # printed when present
    assert [b["kind"] for b in row.body] == ["p", "p", "table", "table", "table"]
    assert library.label(row) == "Supplied by Legal — not approved yet"
    event = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == library.LEGAL_TEXT_SUPPLIED)).scalar_one()
    assert event.actor_id == lawyer.id
    assert event.after_state["content_hash"] == row.content_hash
    # with or without Legal's words, nothing here blocks a final contract (AM-414)
    clauses = {k: publish.clause_dict(r) for k, r in publish.pinned_clauses(db, ready).items()}
    m = model_.resolve(publish.template_dict(ready), clauses, ready.layout["check_values"])
    assert model_.legal_to_supply(m) == []
    assert api.post(_url(ready, f"/clauses/{pin['clause_key']}/approve")).status_code == 200
    assert _places(api, ready)["annexure_1"]["approved"] is True
    # the same words again are refused; nothing is written twice
    assert api.post(_url(ready, "/legal-text"), json={
        "which": "annexure_1", "text": WORDS}).status_code == 409


def test_only_the_clause_approver_may_supply_it(db, api, ready, staff):
    assert api.post(_url(ready, "/annexure-1")).status_code == 200
    sign_in(api, db, staff)
    r = api.post(_url(ready, "/legal-text"), json={"which": "annexure_1", "text": WORDS})
    assert r.status_code in (403, 404)
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == library.LEGAL_TEXT_SUPPLIED)).first() is None


def test_legals_annexure_2_sentence_is_optional_and_prints_when_approved(
        db, api, user, seeded, placeholder, lawyer):
    tv = _imported(db, user, placeholder)
    T.attach_special_conditions(db, tv, actor_id=user.id, precedence_into="frame",
                                frame_version=2, initials=False)
    sign_in(api, db, lawyer)
    place = _places(api, tv)["precedence"]
    assert (place["supplied"], place["text"]) == (False, None)
    made = api.post(_url(tv, "/legal-text"), json={"which": "precedence", "text": SENTENCE})
    assert made.status_code == 200, made.text
    db.refresh(tv)
    frame = tv.layout["special_conditions"]["frame"]
    row = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == frame["clause_key"],
        M.ClauseVersion.version == frame["version"])).scalar_one()
    said = special_conditions.roles(row.body)
    assert said["precedence"] == [SENTENCE] and row.status == "DRAFT"
    roles = [b.get("role") for b in row.body]
    assert roles.index("precedence") == max(
        i for i, r in enumerate(roles) if r == "opening") + 1
    # a draft frame is not approved yet — approval is the same step as any clause
    assert [m["code"] for m in special_conditions.readiness(db, tv)["missing"]] == [
        "FRAME_NOT_APPROVED"]
    assert api.post(_url(tv, f"/clauses/{frame['clause_key']}/approve")).status_code == 200
    db.refresh(tv)
    assert special_conditions.readiness(db, tv) == {"ready": True, "missing": []}
    # changing it replaces the sentence, never stacks a second one
    again = api.post(_url(tv, "/legal-text"), json={
        "which": "precedence", "text": SENTENCE + " (revised)"})
    assert again.status_code == 200
    db.refresh(tv)
    frame = tv.layout["special_conditions"]["frame"]
    row = db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == frame["clause_key"],
        M.ClauseVersion.version == frame["version"])).scalar_one()
    assert special_conditions.roles(row.body)["precedence"] == [SENTENCE + " (revised)"]


def test_an_annexure_title_is_printed_once(placeholder, answers):
    """`AM-413` r4: Annexure 1's one clause carries the annexure's own title — the final
    contract prints it once, not as a heading and again as clause 1."""
    from legalmind.drafting import render_contract as R
    from legalmind.ingestion.parsing import parse_docx
    from tests.drafting.test_final_package_s4 import _answers, _with_annexure_1

    template, clauses = _with_annexure_1(placeholder)
    annex = template["annexures"][-1]
    key = (annex["clauses"][0]["clause_key"], annex["clauses"][0]["version"])
    clauses = {**clauses, key: {**clauses[key], "title": annex["title"]}}
    m = model_.resolve(template, clauses, _answers(answers, ("VPS",)))
    docx = R.render(m, template["assets"], contract_ref="T", version_number=1,
                    model_hash=model_.model_hash(m))
    texts = [s.content for s in parse_docx(docx).segments]
    assert sum(annex["title"] in t for t in texts) == 1
    # the numbering check agrees with what is printed (the publish gate runs it)
    from legalmind.drafting import preflight
    assert list(preflight._numbering(docx, m)) == []

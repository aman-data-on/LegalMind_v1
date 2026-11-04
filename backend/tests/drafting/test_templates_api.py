"""S4 — the template API: clause-by-clause lawyer approval and the publish gate
(`AM-282`, `AM-283`). The STRUCTURAL placeholder only — synthetic text (rule 21)."""

import uuid

import pytest
from sqlalchemy import text

from legalmind.db import models as M
from legalmind.drafting import library
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tools import import_template as T

V1 = "/api/v1"


@pytest.fixture
def template(db, user, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    return db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.STRUCTURAL").one()


@pytest.fixture
def lawyer(db, seeded):
    person = make_user(db)
    grant_role(db, person, P.ROLE_LEGAL_DECISION_AUTHORITY)
    return person


@pytest.fixture
def staff(db, seeded):
    person = make_user(db)
    grant_role(db, person, P.ROLE_USER)
    return person


def _url(tv, tail=""):
    return f"{V1}/templates/{tv.id if hasattr(tv, 'id') else tv}{tail}"


def test_a_draft_is_invisible_to_anyone_but_an_approver(db, api, template, staff, lawyer):
    sign_in(api, db, staff)
    assert api.get(f"{V1}/templates").json()["data"] == []
    hidden, absent = api.get(_url(template)), api.get(_url(uuid.uuid4()))
    assert hidden.status_code == absent.status_code == 404
    assert hidden.json()["error"] == {**absent.json()["error"],
                                      "request_id": hidden.json()["error"]["request_id"]}
    assert api.post(_url(template, "/clauses/CLAUSE_A/approve")).status_code == 404
    sign_in(api, db, make_user(db))                     # no role at all
    assert api.get(f"{V1}/templates").status_code == 403
    sign_in(api, db, lawyer)
    listed = api.get(f"{V1}/templates").json()["data"]
    total = len(library.pins(template))
    assert [(t["status"], t["progress"]) for t in listed] == [
        ("DRAFT", f"0 of {total} clauses approved")]
    detail = api.get(_url(template)).json()["data"]
    assert detail["label"] == library.DRAFT_LABEL
    clause_a = next(c for c in detail["clauses"] if c["clause_key"] == "CLAUSE_A")
    assert clause_a["status"] == "DRAFT" and "count_value" in clause_a["variables"]
    assert clause_a["flags"] == [] and clause_a["approval"] is None


def test_each_action_writes_a_new_approved_version(db, api, template, lawyer):
    sign_in(api, db, lawyer)
    ok = api.post(_url(template, "/clauses/CLAUSE_A/approve"))
    assert ok.status_code == 200, ok.text
    v2 = db.query(M.ClauseVersion).filter_by(clause_key="CLAUSE_A", version=2).one()
    event = db.get(M.AuditEvent, uuid.UUID(v2.source["approval_ref"]))
    shown = next(c for c in api.get(_url(template)).json()["data"]["clauses"]
                 if c["clause_key"] == "CLAUSE_A")
    assert shown["approval"]["approved_by_name"] == lawyer.name
    assert (v2.status, v2.approved_by, v2.source["supplier"]) == (
        "APPROVED", lawyer.id, f"lawyer:{lawyer.id}")
    assert (event.action, event.entity_id, v2.source["sha256"]) == (
        "template.clause_approved", v2.id, v2.content_hash)
    assert db.query(M.ClauseVersion).filter_by(clause_key="CLAUSE_A", version=1
                                               ).one().status == "DRAFT"
    again = api.post(_url(template, "/clauses/CLAUSE_A/approve"))
    assert again.status_code == 409
    wording = "Our own wording for {count_value}.\n\nA second paragraph, kept as typed."
    rep = api.post(_url(template, "/clauses/CLAUSE_A/replace"),
                   json={"text": wording, "reason": "Lawyer's wording"})
    assert rep.status_code == 200 and rep.json()["data"]["version"] == 3
    v3 = db.query(M.ClauseVersion).filter_by(clause_key="CLAUSE_A", version=3).one()
    assert [b["text"] for b in v3.body] == wording.split("\n\n")
    db.refresh(template)
    assert {p["clause_key"]: p["version"] for p in template.clauses}["CLAUSE_A"] == 3
    with pytest.raises(Exception, match="frozen"), db.begin_nested():
        db.execute(text("UPDATE clause_versions SET title='x' WHERE id=:i"), {"i": v3.id})
    bad = api.post(_url(template, "/clauses/CLAUSE_B/replace"),
                   json={"text": "Uses {nobody_declared}.", "reason": "x"})
    assert bad.status_code == 409 and "nobody_declared" in bad.json()["error"]["message"]
    assert api.post(_url(template, "/clauses/CLAUSE_B/no-position"),
                    json={"reason": ""}).status_code == 422
    nop = api.post(_url(template, "/clauses/CLAUSE_B/no-position"),
                   json={"reason": "No company position"})
    assert nop.status_code == 200
    assert api.post(_url(template, "/clauses/NOT_PINNED/approve")).status_code == 404


def test_publish_is_refused_with_every_problem_named(db, api, template, lawyer):
    sign_in(api, db, lawyer)
    api.post(_url(template, "/clauses/CLAUSE_A/approve"))
    refused = api.post(_url(template, "/publish"))
    assert refused.status_code == 422
    error = refused.json()["error"]
    assert error["code"] == "PUBLISH_REFUSED"
    assert "CLAUSE_NOT_APPROVED: CLAUSE_B@1 is DRAFT" in error["problems"]
    assert not any("CLAUSE_A" in p for p in error["problems"])
    db.refresh(template)
    assert template.status == "DRAFT"
    assert db.query(M.AuditEvent).filter_by(action="template.publish_refused",
                                            entity_id=template.id).count() == 1


def test_publish_succeeds_once_every_clause_is_approved(db, api, template, lawyer, staff,
                                                        user, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(template):
        assert api.post(_url(template, f"/clauses/{pin['clause_key']}/approve")
                        ).status_code == 200
    done = api.post(_url(template, "/publish"))
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "PUBLISHED"
    assert api.post(_url(template, "/clauses/CLAUSE_A/no-position"),
                    json={"reason": "late"}).status_code == 409
    # a published template's clauses are fixed: its check is refused, never a 500
    assert api.get(_url(template, "/check")).status_code == 409
    sign_in(api, db, staff)
    assert [t["status"] for t in api.get(f"{V1}/templates").json()["data"]] == ["PUBLISHED"]
    assert "flags" not in api.get(_url(template)).json()["data"]
    assert api.post(_url(template, "/clauses/CLAUSE_A/approve")).status_code == 403
    assert api.post(_url(template, "/publish")).status_code == 403


def test_check_previews_the_gate_and_keeps_nothing(db, api, template, lawyer, staff, user,
                                                   monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    db.flush()
    sign_in(api, db, staff)
    assert api.get(_url(template, "/check")).status_code == 404
    sign_in(api, db, lawyer)
    before = (db.query(M.ClauseVersion).count(), db.query(M.AuditEvent).count())
    checked = api.get(_url(template, "/check"))
    assert checked.status_code == 200, checked.text
    assert checked.json()["data"] == {"publishable": True, "problems": [], "standards": []}
    db.expire_all()
    assert (db.query(M.ClauseVersion).count(), db.query(M.AuditEvent).count()) == before
    assert db.get(M.TemplateVersion, template.id).status == "DRAFT"


def test_only_a_hand_published_demo_label_is_shown_as_one():
    from legalmind.drafting.blank import demo_label
    demo = "DEMO — not approved by Legal"
    assert demo_label(M.TemplateVersion(source={"label": demo})) == demo
    assert demo_label(M.TemplateVersion(source={"label": "Reference text — not approved by Legal"})) is None
    assert demo_label(M.TemplateVersion(source=None)) is None


def test_a_finding_is_placed_on_the_clause_its_evidence_opens():
    from legalmind.api.routers.templates import _clause_of, _norm
    texts = {"A": _norm("The first clause speaks of {count_value} apples and pears."),
             "B": _norm("A second clause about something else entirely, here.")}
    assert _clause_of("A second clause about something else entirely, here.", texts) == "B"
    assert _clause_of("Nothing like any clause at all in this template.", texts) is None
    assert _clause_of("Short.", texts) is None


# -------------------------------------------- the lawyer's wording keeps its structure
NESTED = ("4.1 The {term:Placeholder Term One} applies to [Count value] items.\n"
          "4.1.1 A second-level point.\n"
          "4.1.1.1 A third-level point.\n"
          "(a) first listed thing;\n(b) second listed thing.\n"
          "4.2 Back at the second level.\n"
          "A closing paragraph with no number.")


def _a(db, template):
    return db.query(M.ClauseVersion).filter_by(clause_key="CLAUSE_A", version=1).one().body


def test_wording_nests_by_its_markers_and_keeps_every_word(db, template):
    body = library.parse_wording(NESTED, _a(db, template))
    one, two = body
    assert (one["key"], one["text"]) == ("CLAUSE_A_1", "The {term:Placeholder Term One} "
                                         "applies to {count_value} items.")
    deep = one["body"][0]["body"][0]
    assert deep["text"] == "A third-level point."
    assert deep["body"][0] == {"kind": "list",
                               "items": ["first listed thing;", "second listed thing."]}
    assert two["body"] == [{"kind": "p", "text": "A closing paragraph with no number."}]
    lines = library.outline(body, "4")
    assert [(x["number"], x["level"]) for x in lines] == [
        ("4.1", 2), ("4.1.1", 3), ("4.1.1.1", 4), ("(a)", 4), ("(b)", 4), ("4.2", 2),
        (None, 2)]
    typed = NESTED.replace("[Count value]", "{count_value}")
    assert library.wording(body, "4").split() == typed.split()     # flattened = as typed


def test_a_list_inside_a_list_item_is_refused_not_flattened(db, template):
    with pytest.raises(library.LibraryRefused, match="list inside a list item"):
        library.parse_wording("(a) outer\n(i) inner", [])
    assert library.parse_wording("(h) eighth\n(i) ninth", [])[0]["items"] == [
        "eighth", "ninth"]


def test_replaced_definitions_stay_defined_and_the_template_publishes(
        db, api, template, lawyer, user, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    db.flush()
    sign_in(api, db, lawyer)
    wording = ("In this agreement:\n\n"
               "\"Placeholder Term One\" means the first placeholder thing.\n\n"
               "The second placeholder thing, see {xref:CLAUSE_C_2} (together, the "
               "“Placeholder Term Two”).")
    rep = api.post(_url(template, "/clauses/DEFINITIONS/replace"),
                   json={"text": wording, "reason": "Our definitions"})
    assert rep.status_code == 200, rep.text
    assert [x["kind"] for x in rep.json()["data"]["outline"]] == ["p", "definition", "p"]
    row = db.query(M.ClauseVersion).filter_by(
        clause_key="DEFINITIONS", version=rep.json()["data"]["version"]).one()
    assert row.source["text"] == wording
    assert row.body[1] == {"kind": "definition", "term": "Placeholder Term One",
                           "text": "means the first placeholder thing."}
    for pin in library.pins(template):
        if pin["clause_key"] != "DEFINITIONS":
            assert api.post(_url(template, f"/clauses/{pin['clause_key']}/approve")
                            ).status_code == 200
    done = api.post(_url(template, "/publish"))
    assert done.status_code == 200, done.text


def test_a_dry_run_shows_the_numbering_and_writes_nothing(db, api, template, lawyer):
    sign_in(api, db, lawyer)
    before = (db.query(M.ClauseVersion).count(), db.query(M.AuditEvent).count())
    pins_before = list(template.clauses)
    dry = api.post(_url(template, "/clauses/CLAUSE_A/replace"),
                   json={"text": NESTED, "dry_run": True})
    assert dry.status_code == 200, dry.text
    got = dry.json()["data"]
    assert got["dry_run"] is True
    number = library.number_of(template, "CLAUSE_A")
    assert [x["number"] for x in got["outline"]][:3] == [
        f"{number}.1", f"{number}.1.1", f"{number}.1.1.1"]
    db.expire_all()
    assert (db.query(M.ClauseVersion).count(), db.query(M.AuditEvent).count()) == before
    assert db.get(M.TemplateVersion, template.id).clauses == pins_before
    assert api.post(_url(template, "/clauses/CLAUSE_A/replace"),
                    json={"text": NESTED}).status_code == 409      # recording needs a reason


def _bare(body):
    """Blocks without empty ``body`` lists (the importer writes them, the library not)."""
    return [{k: _bare(v) if k == "body" else v for k, v in b.items()
             if not (k == "body" and not v)} for b in body]


def test_the_offered_wording_reads_back_into_the_same_clause(db, api, template, lawyer):
    sign_in(api, db, lawyer)
    for c in api.get(_url(template)).json()["data"]["clauses"]:
        back = library.parse_wording(c["wording"], c["body"])
        assert library.wording(back, "1") == library.wording(c["body"], "1")
        if c["clause_key"] != "CLAUSE_C":       # its figure follows 3.2 as text: inside it
            assert _bare(back) == _bare(c["body"]), c["clause_key"]


def test_a_roman_list_runs_on():
    assert library.parse_wording("(i) one\n(ii) two\n(iii) three", [])[0]["items"] == [
        "one", "two", "three"]
    with pytest.raises(library.LibraryRefused, match="list inside a list item"):
        library.parse_wording("(i) one\n(ii) two\n(a) inner", [])


def test_a_clause_shows_every_version_and_what_the_published_template_uses(
        db, api, template, lawyer, staff, user, monkeypatch):
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(template):
        api.post(_url(template, f"/clauses/{pin['clause_key']}/approve"))
    assert api.post(_url(template, "/publish")).status_code == 200
    # a second version of the same template, drafted from the published one's pins
    v2 = M.TemplateVersion(
        template_key=template.template_key, version=2, doc_type=template.doc_type,
        brand=template.brand, layout=template.layout, clauses=template.clauses,
        variables=template.variables, annexures=template.annexures, assets=template.assets,
        source=template.source, content_hash=template.content_hash, created_by=user.id)
    db.add(v2)
    db.flush()
    assert api.post(_url(v2, "/clauses/CLAUSE_A/no-position"),
                    json={"reason": "Says nothing we hold"}).status_code == 200
    detail = api.get(_url(v2)).json()["data"]
    assert detail["published"] == {"id": str(template.id), "version": 1}
    a = next(c for c in detail["clauses"] if c["clause_key"] == "CLAUSE_A")
    b = next(c for c in detail["clauses"] if c["clause_key"] == "CLAUSE_B")
    assert (a["version"], a["published_version"]) == (3, 2)
    assert b["version"] == b["published_version"] == 2
    history = api.get(_url(v2, "/clauses/CLAUSE_A/versions"))
    assert history.status_code == 200, history.text
    rows = history.json()["data"]
    assert [(r["version"], r["decision"], r["in_this_template"], r["published"])
            for r in rows] == [(3, "NO_POSITION", True, False), (2, "APPROVE", False, True),
                               (1, None, False, False)]
    assert rows[0]["reason"] == "Says nothing we hold"
    assert rows[0]["approved_by_name"] == lawyer.name and rows[2]["approved_by_name"] is None
    assert api.get(_url(v2, "/clauses/NOT_A_CLAUSE/versions")).status_code == 404
    sign_in(api, db, staff)
    assert api.get(_url(v2, "/clauses/CLAUSE_A/versions")).status_code == 404

"""Import (JSON and reference DOCX), the freeze trigger, and the publish gate."""

import copy
import json
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from legalmind.db import models as M
from legalmind.drafting import publish
from legalmind.security.permissions import ROLE_LEGAL_DECISION_AUTHORITY
from tests.conftest import grant_role, make_user
from tests.drafting.conftest import PLACEHOLDER
from tools import import_template as T


# ---------------------------------------------------------------- import
def test_a_clause_without_a_source_is_refused(tmp_path):
    raw = json.loads(PLACEHOLDER.read_text())
    del raw["clause_versions"][1]["source"]
    path = tmp_path / "template.json"
    path.write_text(json.dumps(raw))
    for asset in raw["assets"].values():
        (tmp_path / asset["file"]).write_bytes((PLACEHOLDER.parent / asset["file"]).read_bytes())
    with pytest.raises(T.ImportRefused, match="CLAUSE_A@1: no recorded source"):
        T.load_json(path)


def test_a_declared_hash_that_differs_is_refused(placeholder):
    clause = copy.deepcopy(placeholder[1][("CLAUSE_A", 1)])
    clause["content_hash"] = "0" * 64
    with pytest.raises(T.ImportRefused, match="content_hash does not match"):
        T.check_clause(clause)


def test_a_condition_on_an_undeclared_field_is_refused(placeholder):
    template, clauses = placeholder
    template["clauses"][0]["when"] = {"==": [{"var": "nobody_declared_this"}, True]}
    with pytest.raises(T.ImportRefused, match="undeclared"):
        T.check_template(template, clauses)


def test_reference_docx_import_keeps_tables_images_and_flags_the_rest(tmp_path, rendered):
    path = tmp_path / "reference.docx"
    path.write_bytes(rendered[2])
    with pytest.raises(T.ImportRefused, match="no recorded source"):
        T.load_docx(path, template_key="REF.TEST", doc_type="OTHER", brand=None,
                    supplier="", approval_ref=None)
    template, clauses, flagged = T.load_docx(
        path, template_key="REF.TEST", doc_type="OTHER", brand=None,
        supplier="Placeholder supplier", approval_ref=None)
    titles = [c["title"] for c in clauses.values()]
    assert titles[:6] == ["Definitions", "Clause A Heading", "Clause B Heading",
                          "Clause C Heading", "Clause D Heading", "Clause E Heading"]
    clause_b = clauses[("CLAUSE_B_HEADING", 1)]["body"]
    assert any(b["kind"] == "table" and b["header"][0] == "Column One" for b in clause_b)
    clause_c = clauses[("CLAUSE_C_HEADING", 1)]["body"]
    kinds = [b["kind"] for b in clause_c] + [x["kind"] for b in clause_c for x in b.get("body", [])]
    assert "image" in kinds and template["assets"]       # kept where it stood (after 4.2)
    clause_a = clauses[("CLAUSE_A_HEADING", 1)]["body"]
    assert clause_a[0]["kind"] == "sub" and clause_a[0]["body"][0]["kind"] == "sub"
    assert any("before the first numbered clause" in f for f in flagged)
    assert all(c["source"]["sha256"] and c["source"]["supplier"] for c in clauses.values())


def test_import_writes_draft_rows_once(db, user, placeholder):
    template, clauses = placeholder
    lines = T.import_rows(db, template, clauses, actor_id=user.id)
    assert sum(line.startswith("DRAFT clause") for line in lines) == len(clauses)
    again = T.import_rows(db, template, clauses, actor_id=user.id)
    assert all(line.startswith("unchanged") for line in again)
    changed = copy.deepcopy(clauses)
    changed[("CLAUSE_A", 1)]["content_hash"] = "f" * 64
    with pytest.raises(T.ImportRefused, match="a new version is needed"):
        T.import_rows(db, template, changed, actor_id=user.id)


# ---------------------------------------------------------------- freeze
def _approve_all(db, user, template_key="PLACEHOLDER.STRUCTURAL"):
    db.execute(text("UPDATE clause_versions SET status='APPROVED', approved_by=:u, "
                    "approved_at=now() WHERE status='DRAFT'"), {"u": user.id})
    db.execute(text("UPDATE template_versions SET status='APPROVED', approved_by=:u, "
                    "approved_at=now() WHERE template_key=:k"), {"u": user.id, "k": template_key})
    db.expire_all()


@pytest.mark.parametrize("sql", [
    "UPDATE clause_versions SET title='changed' WHERE clause_key='CLAUSE_A'",
    "UPDATE clause_versions SET status='DRAFT' WHERE clause_key='CLAUSE_A'",
    "DELETE FROM clause_versions WHERE clause_key='CLAUSE_A'",
    "UPDATE template_versions SET clauses='[]'::jsonb",
    "UPDATE clause_versions SET status='RETIRED', title='changed' WHERE clause_key='CLAUSE_A'",
])
def test_an_approved_version_is_frozen(db, user, placeholder, sql):
    T.import_rows(db, *placeholder, actor_id=user.id)
    _approve_all(db, user)
    with pytest.raises(DBAPIError, match=r"frozen|may not move|cannot be deleted"), \
            db.begin_nested():
        db.execute(text(sql))


def test_a_draft_may_change_and_an_approved_one_may_retire(db, user, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    db.execute(text("UPDATE clause_versions SET title='Draft edit' WHERE clause_key='CLAUSE_A'"))
    _approve_all(db, user)
    db.execute(text("UPDATE clause_versions SET status='RETIRED' WHERE clause_key='CLAUSE_A'"))


def test_approval_needs_an_approver(db, user, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE clause_versions SET status='APPROVED' "
                        "WHERE clause_key='CLAUSE_A'"))


# ---------------------------------------------------------------- publish
@pytest.fixture
def holder(db, seeded):
    person = make_user(db)
    grant_role(db, person, ROLE_LEGAL_DECISION_AUTHORITY)
    return person


@pytest.fixture
def snapshot(db, user):
    snap = M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id)
    db.add(snap)
    db.flush()
    return snap


def _template_row(db):
    return db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.STRUCTURAL").one()


def test_publish_needs_the_permission(db, user, seeded, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    with pytest.raises(publish.PublishRefused, match="NOT_PERMITTED"):
        publish.publish_template(db, _template_row(db).id, actor_id=user.id)


def test_publish_refuses_an_unapproved_clause(db, user, holder, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    _approve_all(db, user)
    db.execute(text("UPDATE clause_versions SET status='RETIRED' WHERE clause_key='CLAUSE_D'"))
    db.expire_all()
    with pytest.raises(publish.PublishRefused) as exc:
        publish.publish_template(db, _template_row(db).id, actor_id=holder.id)
    assert exc.value.problems == ["CLAUSE_NOT_APPROVED: CLAUSE_D@1 is RETIRED"]


def test_publish_refuses_a_draft_template(db, user, holder, placeholder):
    T.import_rows(db, *placeholder, actor_id=user.id)
    with pytest.raises(publish.PublishRefused, match="TEMPLATE_NOT_APPROVED"):
        publish.publish_template(db, _template_row(db).id, actor_id=holder.id)


def test_publish_refuses_anything_but_match(db, user, holder, placeholder, snapshot,
                                            monkeypatch):
    T.import_rows(db, *placeholder, actor_id=user.id)
    _approve_all(db, user)
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    # AM-303: a deviation in our favour (the fourth field) passes; any other does not
    monkeypatch.setattr(publish, "_findings", lambda *a, **k: [
        ("REQ-A", "MATCH", "A", False), ("REQ-B", "DEVIATION", "B", False),
        ("REQ-C", "DEVIATION", "C", True)])
    with pytest.raises(publish.PublishRefused) as exc:
        publish.publish_template(db, _template_row(db).id, actor_id=holder.id)
    assert exc.value.problems == ["NOT_MATCH: REQ-B is DEVIATION"]
    assert _template_row(db).status == "APPROVED"


def test_publish_refuses_a_question_whose_label_reads_like_its_key(db, user, holder,
                                                                  placeholder):
    template, clauses = copy.deepcopy(placeholder)
    count = next(v for v in template["variables"] if v["key"] == "count_value")
    del count["label"]                                  # no author label, no role words
    signer = next(v for v in template["variables"] if v["key"] == "party_two_signatory")
    signer["label"] = "Party_two signatory"
    template["content_hash"] = T.template_hash(template, clauses)
    T.import_rows(db, template, clauses, actor_id=user.id)
    _approve_all(db, user)
    with pytest.raises(publish.PublishRefused) as exc:
        publish.publish_template(db, _template_row(db).id, actor_id=holder.id)
    assert [p.split(" has")[0] for p in exc.value.problems] == [
        "LABEL: party_two_signatory", "LABEL: count_value"]


def test_publish_runs_the_engine_and_rolls_it_back(db, user, holder, placeholder, snapshot):
    """With LEGALMIND_SOFFICE set, the PDF is preflighted too."""
    T.import_rows(db, *placeholder, actor_id=user.id)
    _approve_all(db, user)
    contracts = db.query(M.Contract).count()
    done = publish.publish_template(db, _template_row(db).id, actor_id=holder.id)
    row = _template_row(db)
    assert (row.status, row.checked_snapshot_id, row.published_by) == (
        "PUBLISHED", snapshot.id, holder.id)
    assert db.query(M.Contract).count() == contracts          # the check left nothing
    assert done.model_hash and done.pdf_checked == bool(os.environ.get("LEGALMIND_SOFFICE"))
    audit = db.query(M.AuditEvent).filter_by(action=publish.TEMPLATE_PUBLISHED).one()
    assert audit.after_state["snapshot_id"] == str(snapshot.id)


def test_one_published_version_per_key(db, user, holder, placeholder, snapshot, monkeypatch):
    T.import_rows(db, *placeholder, actor_id=user.id)
    template, clauses = copy.deepcopy(placeholder)
    template["version"] = 2
    template["content_hash"] = T.template_hash(template, clauses)
    T.import_rows(db, template, clauses, actor_id=user.id)
    _approve_all(db, user)
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    rows = sorted(db.query(M.TemplateVersion).all(), key=lambda r: r.version)
    publish.publish_template(db, rows[0].id, actor_id=holder.id)
    publish.publish_template(db, rows[1].id, actor_id=holder.id)
    db.expire_all()
    assert [r.status for r in sorted(db.query(M.TemplateVersion).all(),
                                     key=lambda r: r.version)] == ["RETIRED", "PUBLISHED"]

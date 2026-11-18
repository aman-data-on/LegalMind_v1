"""E2E fix batch C/D, drafting side (AB-211): Annexure 1 wired into a template from its
page (`AM-397`), the package page order, and a fill-in field filled after the client's
round (`AM-400`, B5). The STRUCTURAL placeholder with synthetic text only (rule 21): no
Annexure 1 wording is written anywhere — the clause carries the Legal-to-supply stand-in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from legalmind.api.routers import negotiation as N
from legalmind.db import models as M
from legalmind.drafting import model as model_
from legalmind.drafting import publish
from legalmind.drafting import render_contract as R
from legalmind.ingestion.parsing import parse_docx
from tests.conftest import sign_in
from tests.drafting.test_final_package_s3 import _entries, _test_frame, _with_frame
from tests.drafting.test_final_package_s4 import _answers, _with_annexure_1
from tests.drafting.test_new_contract import (  # noqa: F401 — fixtures
    _start,
    count_is_blank,
    published,
    staff,
)
from tests.drafting.test_template_keep_signatory_blanks import ready  # noqa: F401
from tests.drafting.test_templates_api import _url, lawyer, template  # noqa: F401

V1 = "/api/v1"


# ---------------------------------------------------------------- AM-397: the action
def test_the_template_page_adds_annexure_1_once_and_writes_no_wording(db, api, ready):
    """E1: the annexure, three Order form questions, the signature page last; a second
    call is 409. The clause carries the form's tables and no wording (`AM-414`)."""
    made = api.post(_url(ready, "/annexure-1"))
    assert made.status_code == 200, made.text
    db.refresh(ready)
    annex = [a for a in ready.annexures if a["key"] == "ANNEXURE_1"]
    assert len(annex) == 1 and annex[0]["title"] == "Annexure 1 — Service Order Form"
    asked = {v["key"]: v for v in ready.variables if v.get("group") == "Order form"}
    assert set(asked) == {"services", "fees", "initial_term_months"}
    assert asked["services"]["multi"] and "VPS" in asked["services"]["allowed"]
    assert ready.layout["execution"]["last"] is True
    row = db.query(M.ClauseVersion).filter_by(clause_key="ANNEX1.ORDER_FORM").one()
    assert row.status == "DRAFT"
    # AM-414: the form only — no wording of ours, and no stand-in either
    assert [b["kind"] for b in row.body] == ["table", "table", "table"]
    assert db.query(M.AuditEvent).filter_by(action="template.annexure_1_added").count() == 1
    again = api.post(_url(ready, "/annexure-1"))
    assert again.status_code == 409
    # filled: two services render two rows, and the stand-in blocks the final
    clauses = {k: publish.clause_dict(r) for k, r in publish.pinned_clauses(db, ready).items()}
    answers = {**ready.layout["check_values"], "services": ["VPS", "Dedicated Servers"],
               "fees": [{"service": "VPS", "quantity": 2, "monthly_fee": 900,
                         "one_time_fee": 0},
                        {"service": "Dedicated Servers", "quantity": 1,
                         "monthly_fee": 9000, "one_time_fee": 500}],
               "initial_term_months": 12}
    m = model_.resolve(publish.template_dict(ready), clauses, answers)
    sched = next(s for s in m["schedules"] if s["key"] == "ANNEXURE_1")
    tables = [b for b in sched["clauses"][0]["body"] if b["kind"] == "table"]
    assert [model_.text_of(r[0]) for r in tables[1]["rows"][1:]] == ["VPS",
                                                                     "Dedicated Servers"]
    assert model_.legal_to_supply(m) == []              # AM-414: nothing blocks the final


def test_a_sales_user_cannot_add_annexure_1(db, api, template, staff):
    sign_in(api, db, staff)
    assert api.post(_url(template, "/annexure-1")).status_code in (403, 404)


# ---------------------------------------------------------------- AM-397: page order
def test_the_final_reads_msa_then_annex_1_then_annex_2_then_the_signature_page(
        placeholder, answers):
    """E3: body → Annexure 1 → Annexure 2 → signatures, by the rendered text's order."""
    frame = _test_frame()
    template, clauses, cfg = _with_frame(placeholder, frame)
    template, clauses = _with_annexure_1((template, clauses))
    filled = _answers(answers, ("VPS",))
    base = model_.resolve(template, clauses, filled)
    m = model_.resolve(template, clauses, filled,
                       special={"frame": frame, "config": cfg, "entries": _entries(base)})
    docx = R.render(m, template["assets"], contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(m))
    texts = [s.content for s in parse_docx(docx).segments]

    def at(start: str) -> int:
        return next(i for i, t in enumerate(texts) if t.startswith(start))
    body = max(i for i, t in enumerate(texts) if t.startswith("Schedule B"))
    annex_1, annex_2 = at("Annexure 1 — Test"), at("Annexure 2 — Agreed Amendments")
    signature = at("| Signatory Details")
    assert body < annex_1 < annex_2 < signature


# ---------------------------------------------------------------- AM-400: B5
def test_a_field_filled_after_the_client_round_waits_for_the_final(
        db, api, count_is_blank, published, staff, answers):
    """B5: once our version left, a fill makes no new version: it is kept on our version,
    audited, read by the final contract's build and listed for the signing note; the
    final copy writes it into its own blank (`clean.fill_blanks`)."""
    sign_in(api, db, staff)
    draft = _start(api, published, answers=answers).json()["data"]
    cid = api.post(f"{V1}/drafts/{draft['id']}/create",
                   json={"expected_version": 0}).json()["data"]["contract_id"]
    v1 = db.query(M.DocumentVersion).filter_by(contract_id=uuid.UUID(cid)).one()
    v1.sent_at, v1.sent_by = datetime.now(UTC), staff.id
    db.flush()
    url = f"{V1}/contracts/{cid}/blank-values"
    listed = api.get(url).json()["data"]
    assert listed["can_edit"] and listed["applies_at_final"]
    done = api.post(url, json={"values": {"party_one_cin": "U9"}, "expected_version": 1})
    assert done.status_code == 201, done.text
    assert done.json()["data"]["applies_at_final"] is True
    assert db.query(M.DocumentVersion).filter_by(contract_id=uuid.UUID(cid)).count() == 1
    db.refresh(v1)
    [kept] = v1.doc_metadata["filled_since_sent"]
    assert (kept["key"], kept["label"], kept["value"]) == (
        "party_one_cin", listed["fields"][0]["label"], "U9")
    assert N.contract_fills(db, uuid.UUID(cid)) == [kept]
    made = db.query(M.ContractDraft).filter_by(document_version_id=v1.id).one()
    assert made.values.get("party_one_cin") != "U9"          # the record is untouched
    assert N.filled_values(db, made)["party_one_cin"] == "U9"
    basis = N._basis(db, made)
    assert "U9" in str(basis["base"]) and "U9" not in str(basis["plain"])
    assert N.model_blanks(basis["base"]) is None
    event = db.query(M.AuditEvent).filter_by(action="contract.blank_filled").one()
    assert event.after_state["applies_at_final"] is True


def test_a_final_copy_writes_a_later_fill_into_its_own_blank():
    """AM-400 r1: the blank the words before it lead up to takes the value; another
    blank stays (the check still blocks it); spacing reads as a sentence."""
    import io
    import zipfile

    import docx

    from legalmind.drafting import clean

    d = docx.Document()
    d.add_paragraph("fees paid by Customer in the __________ months preceding the claim.")
    d.add_paragraph("banks at ___________are open; another ______ stays.")
    raw = io.BytesIO()
    d.save(raw)
    made, unplaced = clean.fill_blanks(raw.getvalue(), [
        {"key": "a", "value": "six (6)", "before": "fees paid by Customer in the"},
        {"key": "b", "value": "Pune", "before": "banks at"},
        {"key": "c", "value": "x", "before": "nowhere in the text"}])
    assert unplaced == ["c"]
    with zipfile.ZipFile(io.BytesIO(made)) as z:
        text = z.read("word/document.xml").decode()
    assert "in the six (6) months preceding" in text
    assert "banks at Pune are open; another ______ stays." in text

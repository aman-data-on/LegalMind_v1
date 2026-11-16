"""Annexure 1 — Service Order Form engine (`FINAL-PACKAGE-SPEC` S4: d2, g5).

A ``choice`` with ``multi`` (services taken), a ``rows`` field (the fee lines), a table
filled from answers, clause 5.3 numbers by ``layout.delivery`` and `LEGAL_TO_SUPPLY`.
The Annexure 1 clause is Legal's (L3): every clause text here is TEST-ONLY and says so,
on the STRUCTURAL placeholder template. The service names come from the catalogue.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from legalmind.api.routers import negotiation as N
from legalmind.db import models as M
from legalmind.drafting import library
from legalmind.drafting import model as model_
from legalmind.drafting import render_contract as R
from legalmind.ingestion.parsing import parse_docx
from tests.conftest import sign_in
from tests.drafting.test_special_conditions import _imported, lawyer  # noqa: F401
from tools import import_template as T

V1 = "/api/v1"
CATALOGUE = json.loads(T.SERVICE_CATALOGUE.read_text(encoding="utf-8"))
#: the pre-S4 placeholder model hashes: a template without the new shapes is unchanged
HASH_FILLED = "4d2eb1664f8307a79e7d17f1cc5d9c0c8d8871e2cd69279cefe91ad0bec1e0ef"
HASH_BLANK = "8bad49dcaf20a2964608d5fe01856ef0ed1e67f6aff2fcbdf9c40d67ce772d74"
SOURCE = {"kind": "STRUCTURAL_PLACEHOLDER", "supplier": "test only"}


def _clause(key: str, title: str, body: list) -> dict:
    return T.check_clause({"clause_key": key, "version": 1, "title": title, "body": body,
                           "realises": [], "stance": None, "source": SOURCE})


def _with_annexure_1(placeholder) -> tuple[dict, dict]:
    """The placeholder plus a TEST-ONLY delivery clause (subs worded as the MSA's 5.3
    lines start) and a TEST-ONLY Annexure 1 whose tables fill from the answers."""
    template, clauses = copy.deepcopy(placeholder)
    delivery = _clause("TEST.DELIVERY", "Test delivery clause", [
        {"kind": "sub", "text": "Test lead, not Legal's text.", "body": [
            {"kind": "sub", "text": f"{CATALOGUE['delivery'][s]} test only."}
            for s in ("VPS", "Dedicated Servers", "CloudPe Instances")]}])
    annex = _clause("TEST.ANNEX1", "Test annexure clause", [
        {"kind": "p", "text": "TEST ONLY — not Legal's Annexure 1 text."},
        {"kind": "table", "header": ["Test service", "Test 5.3"], "rows_from": "services",
         "cells": ["{item}", "{delivery}"]},
        {"kind": "table", "header": ["Test service", "Test quantity"],
         "rows_from": "fees", "cells": ["{item.service}", "{item.quantity}"]}])
    for c in (delivery, annex):
        clauses[(c["clause_key"], 1)] = c
    template["clauses"].append({"clause_key": "TEST.DELIVERY", "version": 1})
    template["annexures"].append({"key": "ANNEXURE_1", "title": "Annexure 1 — Test",
                                  "clauses": [{"clause_key": "TEST.ANNEX1", "version": 1}]})
    template["variables"] += [
        {"key": "services", "label": "Services taken", "type": "choice", "multi": True,
         "class": "M", "allowed": CATALOGUE["services"]},
        {"key": "fees", "label": "Fee lines", "type": "rows", "class": "M", "columns": [
            {"key": "service", "label": "Service", "type": "choice",
             "allowed": CATALOGUE["services"]},
            {"key": "quantity", "label": "Quantity", "type": "int", "range": [1, 999]}]}]
    template["layout"]["delivery"] = {"clause": "TEST.DELIVERY",
                                      "lines": dict(CATALOGUE["delivery"])}
    template["layout"]["check_values"] = _answers(template["layout"]["check_values"])
    return template, clauses


def _answers(answers, services=("VPS",)) -> dict:
    return {**answers, "services": list(services),
            "fees": [{"service": s, "quantity": 2} for s in services]}


def _problems(template, clauses, answers) -> list[dict]:
    with pytest.raises(model_.ModelError) as exc:
        model_.resolve(template, clauses, answers)
    return exc.value.problems


# ---------------------------------------------------------------- the model (no DB)
def test_unchanged_without_the_new_shapes(placeholder, answers):
    t, c = placeholder
    assert model_.model_hash(model_.resolve(t, c, answers)) == HASH_FILLED
    assert model_.model_hash(model_.resolve(t, c, {}, blank=True)) == HASH_BLANK


@pytest.mark.parametrize(("services", "problem"), [
    ([], "must be one or more of the approved options"),
    ("VPS", "must be one or more of the approved options"),
    (["VPS", "VPS"], "names an option twice"),
    (["Web hosting"], "is not one of the approved options")])
def test_multi_choice(placeholder, answers, services, problem):
    t, c = _with_annexure_1(placeholder)
    got = _problems(t, c, {**_answers(answers), "services": services})
    assert {"field": "services", "problem": problem} in got


@pytest.mark.parametrize(("fees", "problem"), [
    ([], "must have 1 to 50 rows"),
    ([{"service": "VPS"}], "row 1 must give exactly: service, quantity"),
    ([{"service": "VPS", "quantity": "two"}], "row 1, Quantity, must be a whole number"),
    ([{"service": "Web", "quantity": 1}], "row 1, Service, is not one of the approved "
                                          "options"),
    ([{"service": "VPS", "quantity": 1}] * 51, "must have 1 to 50 rows")])
def test_rows_variable(placeholder, answers, fees, problem):
    t, c = _with_annexure_1(placeholder)
    assert {"field": "fees", "problem": problem} in _problems(
        t, c, {**_answers(answers), "fees": fees})


def _annex_rows(m: dict) -> list[list[str]]:
    annex = next(s for s in m["schedules"] if s["key"] == "ANNEXURE_1")
    return [[model_.text_of(cell) for cell in row]
            for b in annex["clauses"][0]["body"] if b["kind"] == "table"
            for row in b["rows"]]


def test_rows_fill_the_table_and_delivery_numbers(placeholder, answers):
    """g5: VPS, Dedicated and CloudPe point at their own 5.3 lines (here the test
    clause's), in the order chosen; the DOCX carries every row."""
    t, c = _with_annexure_1(placeholder)
    t["layout"]["execution"]["last"] = True
    chosen = ("CloudPe Instances", "VPS", "Dedicated Servers")
    m = model_.resolve(t, c, _answers(answers, chosen))
    n = m["numbers"]["TEST.DELIVERY"]
    assert _annex_rows(m) == [
        ["Test service", "Test 5.3"], ["CloudPe Instances", f"{n}.1.3"],
        ["VPS", f"{n}.1.1"], ["Dedicated Servers", f"{n}.1.2"],
        ["Test service", "Test quantity"], ["CloudPe Instances", "2"], ["VPS", "2"],
        ["Dedicated Servers", "2"]]
    assert model_.legal_to_supply(m) == []
    docx = R.render(m, t["assets"], contract_ref="T", version_number=1,
                    model_hash=model_.model_hash(m))
    texts = [s.content for s in parse_docx(docx).segments]
    assert f"| Dedicated Servers | {n}.1.2 |" in "\n".join(texts)
    # spec (a): the body, then Annexure 1, then the signature page last
    at = texts.index("Annexure 1 — Test")
    assert texts.index("Test delivery clause") < at < min(
        i for i, x in enumerate(texts) if "Signatory Details" in x)


def test_legal_to_supply(placeholder, answers):
    """g5: a service with no 5.3 line is a visible placeholder, named by
    `legal_to_supply`; nothing is written in its place (rule 21)."""
    t, c = _with_annexure_1(placeholder)
    m = model_.resolve(t, c, _answers(answers, ("Colocation", "VPS", "Kubernetes")))
    assert model_.legal_to_supply(m) == ["Colocation", "Kubernetes"]
    assert _annex_rows(m)[1] == ["Colocation", "[Legal to supply]"]
    assert N.legal_gap("Colocation") == ("Clause 5.3 has no delivery wording for "
                                       "Colocation. Legal supplies it; LegalMind never "
                                       "writes it.")


def test_a_delivery_line_no_sub_starts_with_is_refused(placeholder, answers):
    t, c = _with_annexure_1(placeholder)
    t["layout"]["delivery"]["lines"]["VPS"] = "Not a line:"
    got = _problems(t, c, _answers(answers))
    assert any("maps VPS to “Not a line:”, which 0 sub-clauses" in p["problem"]
               for p in got)


def test_blank_template_rows(placeholder):
    t, c = _with_annexure_1(placeholder)
    m = model_.resolve(t, c, {}, blank=True)
    rows = _annex_rows(m)
    assert rows[1] == ["[Test service]", "[Test 5.3]"]


def test_adding_annexure_1_leaves_the_body_unchanged(placeholder, answers):
    t0, c0 = placeholder
    t, c = _with_annexure_1(placeholder)
    before = model_.resolve(t0, c0, answers)["body"]
    after = model_.resolve(t, c, _answers(answers))["body"]
    assert after[:len(before)] == before


def test_catalogue_and_import_check(placeholder):
    assert CATALOGUE["services"] == ["VPS", "Dedicated Servers", "CloudPe Instances",
                                     "Bare Metal", "Colocation", "GPU Cloud",
                                     "Kubernetes"]
    assert set(CATALOGUE["delivery"]) == {"VPS", "Dedicated Servers",
                                          "CloudPe Instances"}
    t, c = _with_annexure_1(placeholder)
    T.check_template(t, c)
    t["layout"]["delivery"]["lines"]["Web hosting"] = "W"
    del t["variables"][-1]["columns"]
    with pytest.raises(T.ImportRefused) as exc:
        T.check_template(t, c)
    assert "delivery: Web hosting is not an option" in str(exc.value)
    assert "fees: a rows field with no columns" in str(exc.value)


# ---------------------------------------------------------------- DB: the final copy
def test_final_copy_blocks_on_legal_to_supply(db, api, user, seeded, placeholder,
                                              lawyer, monkeypatch, tmp_path):
    """g5 through the API: a contract made with Colocation cannot become Final."""
    from legalmind.api.storage import get_storage
    from legalmind.ingestion.storage import LocalFilesystemStorage
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    t, c = _with_annexure_1(placeholder)
    tv = _imported(db, user, (t, c))
    tv.layout = {**tv.layout, "execution": {**tv.layout["execution"], "last": True}}
    library._rehash(db, tv)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        assert api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve"
                        ).status_code == 200
    done = api.post(f"{V1}/templates/{tv.id}/publish")
    assert done.status_code == 200, done.text
    storage = LocalFilesystemStorage(tmp_path / "objects")
    api.app.dependency_overrides[get_storage] = lambda: storage
    try:
        draft = api.post(f"{V1}/drafts", json={
            "template_version_id": done.json()["data"]["id"],
            "answers": _answers(dict(t["layout"]["check_values"]),
                                ("VPS", "Colocation"))}).json()["data"]
        assert draft["problems"] == []
        made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
        assert made.status_code == 201, made.text
        contract = db.get(M.Contract, uuid.UUID(made.json()["data"]["contract_id"]))
        # the review of v1 is not this test's: its gate is passed by hand
        monkeypatch.setattr(N.negotiation, "review_open_points", lambda db, v: None)
        plan = N._final_plan(SimpleNamespace(db=db), contract, storage)
        assert [b["code"] for b in plan["blockers"]] == ["LEGAL_TO_SUPPLY"], plan
        assert "Colocation" in plan["blockers"][0]["message"]
    finally:
        api.app.dependency_overrides.pop(get_storage, None)

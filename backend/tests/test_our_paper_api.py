"""Lawyer judgement P1 (`AM-476`) through the API: which version of our paper a client's
references are read against, the fail-closed reasons, Legal's pick, the sales cap, and
M7 — the change list, routes, effects, answers, automatic acceptance, the brief and the
Findings are byte-identical with the feature on and off.

Every document and policy text is synthetic, a placeholder that states no position of
ours (rule 21), and names no client (54.6).
"""
from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
from sqlalchemy import select, text

from legalmind import config
from legalmind.analysis import negotiation, our_paper
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_deal_brief import _routing
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _docx,
    _ingest,
    _review,
    owner,
)
from tests.test_negotiation_reply import OURS, THEIRS, published  # noqa: F401
from tests.test_negotiation_wording import _lawyer, _send
from tests.test_prior_paper import _client, _signed
from tests.test_version_comparison import V1

#: our signed MSA with the client — placeholders
SIGNED_MSA = ["7. Term", "7.3 Placeholder renewal: six (6) months, thirty (30) days.",
              "8. Fees", "8.4 Placeholder payment without any deduction, set-off or "
              "counter claim.", "17. Liability", "17.7 Placeholder cap of the ________ "
              "months preceding the claim."]
#: the client's paper: our THEIRS plus a clause that reaches into our paper
REFERS = [*THEIRS, "6. This replaces MSA clauses 7.3 and 17.7, despite MSA clause 8.4 "
          "and MSA clause 9.9, and section 5 of the Terms of Service."]


def _get(api, c, **params):
    r = api.get(f"{V1}/contracts/{c.id}/our-paper", params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _deal(db, tmp_path, owner, cp, theirs=REFERS):
    c = _contract(db, owner, contract_type="ADDENDUM")
    c.counterparty_id = cp.id
    _ingest(db, tmp_path, c, _docx(*OURS), "ours.docx")
    return c, _ingest(db, tmp_path, c, _docx(*theirs), "theirs.docx")


def _rows(view):
    return {(r["doc"], r["number"]): r for r in view["rows"]}


def test_read_against_the_msa_signed_with_this_client(api, db, owner, tmp_path):
    cp = _client(db, owner)
    signed, v = _signed(db, tmp_path, owner, cp, paper=SIGNED_MSA)
    c, _ = _deal(db, tmp_path, owner, cp)
    c.issuing_entity = "LEAPSWITCH"
    view = _get(api, c)
    assert view["pins"]["MSA"]["how"] == "PRIOR_PAPER"
    # file and SHA-256 are Legal's detail; a sales reader gets the label and date
    assert {"file", "sha256"}.isdisjoint(view["pins"]["MSA"])
    assert v.file_hash not in json.dumps(view)
    rows = _rows(view)
    assert rows[("MSA", "7.3")]["status"] == our_paper.RESOLVED
    assert rows[("MSA", "7.3")]["verb"] == "REPLACES"
    assert rows[("MSA", "8.4")]["verb"] == "DESPITE"
    assert rows[("MSA", "8.4")]["markers"] == ["without any deduction, set-off"]
    assert rows[("MSA", "17.7")]["blank"].startswith("________")
    assert rows[("MSA", "9.9")]["status"] == our_paper.POINTS_NOWHERE
    # no stored Terms of Service in this database: never the live page, never a guess
    assert rows[("TOS", "5")]["status"] == our_paper.NO_STORED_COPY
    # round 2: sales receives the count, never the list
    assert "overrides" not in view and view["overrides_count"] == 3
    assert view["overrides_by_doc"] == {"MSA": 3}


def _policy(db, brand: str, day: date, words: str, current=True):
    schema = config.assist_schema()
    sid = uuid.uuid4()
    db.execute(text(f"""INSERT INTO "{schema}".knowledge_sources (id, source_type, title,
        version, status, authority, jurisdiction, effective_from, source_file, file_sha256)
        VALUES (:i, :t, :ti, :v, :s, 'APPROVED_COMPANY_DOCUMENT', 'IN', :d, 'test', :h)"""),
        {"i": sid, "t": f"PUBLISHED_TOS_{brand.upper()}", "ti": f"{brand} Terms of Service",
         "v": f"{day}-test", "s": "CURRENT" if current else "SUPERSEDED", "d": day,
         "h": uuid.uuid4().hex})
    db.execute(text(f"""INSERT INTO "{schema}".knowledge_source_periods (source_type,
        source_id, started_on) VALUES (:t, :i, :d)"""),
        {"t": f"PUBLISHED_TOS_{brand.upper()}", "i": sid, "d": day})
    for k, (kind, clause, content) in enumerate([
            ("SECTION", "5. Refunds", "5. Refunds"), ("PARAGRAPH", None, words)]):
        db.execute(text(f"""INSERT INTO "{schema}".knowledge_items (id, source_id, ordinal,
            kind, clause, content, authority, status, cross_references, line_start,
            line_end, breadcrumb) VALUES (:i, :s, :o, :k, :c, :ct,
            'APPROVED_COMPANY_DOCUMENT', 'CURRENT', '{{}}', :o, :o, 'b')"""),
            {"i": uuid.uuid4(), "s": sid, "o": k, "k": kind, "c": clause, "ct": words
             if kind == "PARAGRAPH" else content})
    return sid


def test_a_policy_is_the_stored_copy_of_the_contracts_brand_never_the_other(
        api, db, owner, tmp_path):
    cp = _client(db, owner)
    c, theirs = _deal(db, tmp_path, owner, cp)
    _policy(db, "Leapswitch", theirs.created_at.date(), "Placeholder words A.")
    c.issuing_entity = "LEAPSWITCH"
    db.flush()
    view = _get(api, c)
    row = _rows(view)[("TOS", "5")]
    assert row["status"] == our_paper.RESOLVED
    assert row["ours"]["quote"] == "Placeholder words A."
    assert view["pins"]["TOS"]["label"].startswith("Leapswitch Terms of Service as published on")
    c.issuing_entity = "CLOUDPE"                    # no CloudPe copy stored: unresolved
    db.flush()
    assert _rows(_get(api, c))[("TOS", "5")]["status"] == our_paper.NO_STORED_COPY


def test_which_msa_then_legals_pick(api, db, owner, tmp_path):
    cp = _client(db, owner)
    a, va = _signed(db, tmp_path, owner, cp, paper=SIGNED_MSA)
    b, vb = _signed(db, tmp_path, owner, cp, paper=SIGNED_MSA[:2])
    c, theirs = _deal(db, tmp_path, owner, cp)
    lawyer = _lawyer(db)
    for version in (theirs, va, vb):        # Legal reads all three (rule 18: R1.7)
        _send(db, _review(db, version, [(0, E.FindingClassification.MATCH,
                                         E.RuleOutcome.ACCEPTABLE)]), lawyer)
    view = _get(api, c)                     # two signed MSAs: never auto-picked
    assert view["pins"]["MSA"]["unresolved"] == our_paper.WHICH_MSA
    assert not view["can_pick"] and "hint" not in view["pins"]["MSA"]
    assert not any("hint" in r for r in view["rows"] if r["doc"] == "MSA")
    assert api.post(f"{V1}/contracts/{c.id}/our-paper/msa",
                    json={"contract_id": str(a.id)}).status_code == 403
    sign_in(api, db, lawyer)
    view = _get(api, c)
    assert view["can_pick"] and {x.get("contract_id") for x in
                                 view["pins"]["MSA"]["hint"]["choices"]} >= {
        str(a.id), str(b.id)}
    r = api.post(f"{V1}/contracts/{c.id}/our-paper/msa", json={"contract_id": str(c.id)})
    assert r.status_code == 422                     # not a signed MSA with this client
    r = api.post(f"{V1}/contracts/{c.id}/our-paper/msa", json={"contract_id": str(a.id)})
    assert r.status_code == 201, r.text
    view = _get(api, c)
    pin = view["pins"]["MSA"]
    assert pin["how"] == "LEGAL_PICK" and view["can_pick"]          # changeable
    assert pin["picked"]["by_you"] and pin["sha256"]                # Legal sees the SHA
    assert _rows(view)[("MSA", "7.3")]["status"] == our_paper.RESOLVED
    assert view["overrides"] == ["MSA 7.3", "MSA 17.7", "MSA 8.4"]
    # a re-pick is a new append-only record; the latest one is the pin
    assert api.post(f"{V1}/contracts/{c.id}/our-paper/msa",
                    json={"contract_id": str(b.id)}).status_code == 201
    view = _get(api, c)
    assert _rows(view)[("MSA", "8.4")]["status"] == our_paper.POINTS_NOWHERE   # b lacks it
    assert db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "our_paper.msa_picked")).scalars().all().__len__() == 2
    first = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == "our_paper.msa_picked").order_by(
        M.AuditEvent.timestamp)).scalars().first()
    assert first.actor_id == lawyer.id and first.after_state == {"contract_id": str(a.id)}


def test_sales_sees_five_rows_and_how_many_more_are_for_legal(api, db, owner, tmp_path):
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp, paper=SIGNED_MSA)
    many = [*THEIRS, "6. MSA clauses 1.1, 1.2, 1.3 and 1.4 apply. This replaces MSA "
            "clauses 7.3 and 8.4."]
    c, _ = _deal(db, tmp_path, owner, cp, theirs=many)
    view = _get(api, c)
    assert len(view["rows"]) == 5 and view["more_for_legal"] == 1
    assert {r["number"] for r in view["rows"]} >= {"7.3", "8.4"}  # the replaced first


def test_off_is_a_404_and_out_of_scope_is_the_one_404(api, db, owner, tmp_path,
                                                       monkeypatch):
    cp = _client(db, owner)
    c, _ = _deal(db, tmp_path, owner, cp)
    monkeypatch.setenv("LEGALMIND_OUR_PAPER", "off")
    assert api.get(f"{V1}/contracts/{c.id}/our-paper").status_code == 404
    monkeypatch.delenv("LEGALMIND_OUR_PAPER")
    stranger = make_user(db)
    grant_role(db, stranger, P.ROLE_USER)
    sign_in(api, db, stranger)
    a = api.get(f"{V1}/contracts/{c.id}/our-paper")
    b = api.get(f"{V1}/contracts/{uuid.uuid4()}/our-paper")
    assert a.status_code == b.status_code == 404
    assert {**a.json()["error"], "request_id": 0} == {**b.json()["error"], "request_id": 0}


def test_m7_nothing_that_decides_moves_with_the_feature_on_or_off(
        api, db, owner, tmp_path, monkeypatch):
    """Findings, the change list's routes, effects, answers and automatic acceptance, and
    the brief (its counts included) — the same bytes with the feature on and off, the
    our-paper view read in between."""
    monkeypatch.setattr(negotiation, "auto_rule", lambda db, review: True)
    cp = _client(db, owner)
    _signed(db, tmp_path, owner, cp, paper=SIGNED_MSA)
    c, theirs = _deal(db, tmp_path, owner, cp)
    review = _review(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.UNACCEPTABLE)])
    lawyer = _lawyer(db)
    _send(db, review, lawyer)

    def snapshot() -> str:
        out = []
        for who in (owner, lawyer):
            sign_in(api, db, who)
            out.append(_routing(_changes(api, c)))
            for path in (f"/contracts/{c.id}/brief", f"/reviews/{review.id}/findings",
                         f"/reviews/{review.id}/angles"):
                r = api.get(f"{V1}{path}")
                assert r.status_code == 200, (path, r.text)
                out.append(r.text)
        return json.dumps(out)

    monkeypatch.setenv("LEGALMIND_OUR_PAPER", "off")
    off = snapshot()
    monkeypatch.setenv("LEGALMIND_OUR_PAPER", "on")
    sign_in(api, db, lawyer)
    assert _get(api, c)["rows"]                   # the feature is on and has rows
    assert snapshot() == off


@pytest.mark.parametrize("question", ["Does this addendum meet our standard?",
                                      "Does the addendum meet our standards?"])
def test_ask_still_routes_meets_our_standard_to_the_evaluator(question):
    """M7 / `AM-25` r4: Ask's own router decides this question, and nothing in the assist
    lane can read the our-paper rows (`test_our_paper`, import scan)."""
    from legalmind.assist.query import intent
    assert intent.is_comparison_question(question)


def test_the_deals_template_is_pinned_when_no_msa_is_signed(api, db, owner, tmp_path,
                                                            monkeypatch):
    """M1 step 2: the MSA template the deal was drafted from (its rows stubbed: the
    rendering is `blank`'s own, tested there)."""
    from legalmind.api.routers import our_paper as route
    from legalmind.mapping.engine import Clause
    cp = _client(db, owner)
    c, theirs = _deal(db, tmp_path, owner, cp)
    tv = M.TemplateVersion(template_key="MSA.TEST", version=3, status="RETIRED",
                           doc_type="MSA", layout={"title": "Test MSA"}, clauses=[],
                           variables=[], annexures=[], assets={}, source={},
                           content_hash="c" * 64, created_by=owner.id)
    db.add(tv)
    db.flush()
    db.add(M.ContractDraft(contract_id=c.id, document_version_id=theirs.id,
                           template_version_id=tv.id, values={}, model_hash="m" * 64,
                           renderer_version="test", created_by=owner.id))
    db.flush()
    rows = [Clause(evidence_id=uuid.uuid4(), content=t, section_number=n)
            for n, t in (("7.3", "7.3 Placeholder renewal words."),)]
    monkeypatch.setattr(route.blank, "our_side", lambda db, v: (rows, set(), set()))
    view = _get(api, c)
    assert view["pins"]["MSA"]["how"] == "TEMPLATE"
    assert view["pins"]["MSA"]["label"] == "Test MSA — template version 3"
    assert _rows(view)[("MSA", "7.3")]["status"] == our_paper.RESOLVED

"""S5 (`FINAL-PACKAGE-SPEC` d3, g12): the client's paper converts to ours — our template
with the deal's answers, and only the points of theirs that were accepted, verbatim, as
Annexure 2 entries. Their defined terms or numbering block (Legal writes ours, L6); an
unanchored point needs a person's "add after". Every text here is synthetic structure
(the STRUCTURAL placeholder, TEST-ONLY frame) — no legal conclusion (rule 21)."""

from __future__ import annotations

import hashlib
import uuid

import pytest

from legalmind.api.routers import negotiation as N
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import model as model_
from legalmind.drafting import special_conditions as S
from tests.conftest import sign_in
from tests.drafting.test_final_package_s3 import _publish, _test_frame
from tests.drafting.test_special_conditions import _imported, lawyer  # noqa: F401
from tests.test_negotiation import owner  # noqa: F401
from tests.test_paper_rows import _paper, _point

V1 = "/api/v1"
THEIRS_TEXT = "Their own wording for this point, as their paper has it."


def _row(answer: str | None, text: str = f"14.2 {THEIRS_TEXT}", *,
         anchor: str | None = "CLAUSE_D", add_after: str | None = None,
         wording: str | None = None) -> dict:
    return {"row_key": f"N|THEIRS|PT-{uuid.uuid4().hex[:6]}|ev", "kind": "THEIRS",
            "answer": None if answer is None else {"answer": answer, "wording": wording},
            "after": {"text": text}, "clause": {"number": "14.2"},
            "anchor": {"left_key": f"clause:{anchor}" if anchor else None},
            "effect_for_us": "NEGATIVE",
            **({"add_after": add_after} if add_after else {})}


def _derive(placeholder, answers, rows, their_paper=()):
    base = model_.resolve(*placeholder, answers)
    units = [{"texts": [t], "number": None, "evidence_ids": []} for t in their_paper]
    return S.derive(rows, [], units, [], base, lambda _: None)


# ---------------------------------------------------------------- derive (no DB)
def test_theirs_accepted_becomes_a_replace_entry(placeholder, answers):
    """g12: an accepted THEIRS row anchored to our clause replaces it with their text,
    verbatim, their own number stripped."""
    got = _derive(placeholder, answers, [_row("accept_theirs")])
    assert got["blockers"] == []
    [e] = got["entries"]
    assert (e["op"], e["target"]["number"]) == ("replace", "5")
    assert hashlib.sha256(e["text"].encode()).hexdigest() == \
        hashlib.sha256(THEIRS_TEXT.encode()).hexdigest()


def test_foreign_defined_term_blocks(placeholder, answers):
    paper = ["1.1 “Service Provider” means the party that provides the services."]
    got = _derive(placeholder, answers,
                  [_row("accept_theirs", "The Service Provider keeps the records.")],
                  paper)
    assert [b["code"] for b in got["blockers"]] == ["UNDEFINED_TERM"]
    assert "Service Provider" in got["blockers"][0]["message"]
    assert got["entries"] == []
    # a term our contract defines passes
    ok = _derive(placeholder, answers,
                 [_row("accept_theirs", "Party One keeps the records.")], paper)
    assert ok["blockers"] == []


def test_foreign_numbering_blocks(placeholder, answers):
    got = _derive(placeholder, answers,
                  [_row("accept_theirs", "Subject to Clause 14, the records are kept.")])
    assert [b["code"] for b in got["blockers"]] == ["FOREIGN_XREF"]


def test_unanchored_needs_a_pick(placeholder, answers):
    got = _derive(placeholder, answers, [_row("accept_theirs", anchor=None)])
    assert [b["code"] for b in got["blockers"]] == ["ANCHOR_REQUIRED"]
    picked = _derive(placeholder, answers,
                     [_row("accept_theirs", anchor=None, add_after="CLAUSE_C_2")])
    [e] = picked["entries"]
    assert (e["op"], e["target"]["number"], e["new_number"]) == ("insert_after", "4.2",
                                                                "4.2A")


def test_an_anchor_wins_over_a_pick(placeholder, answers):
    got = _derive(placeholder, answers, [_row("accept_theirs", add_after="CLAUSE_C_2")])
    assert [(e["op"], e["target"]["number"]) for e in got["entries"]] == [("replace", "5")]


def test_an_accepted_point_with_no_text_blocks(placeholder, answers):
    got = _derive(placeholder, answers, [_row("accept_theirs", "14.2 ")])
    assert [b["code"] for b in got["blockers"]] == ["CANNOT_EXPRESS"]
    assert got["entries"] == []


def test_anchor_scoped_to_the_template(placeholder, answers):
    got = _derive(placeholder, answers, [_row("accept_theirs", anchor="OTHER.TEMPLATE")])
    assert [b["code"] for b in got["blockers"]] == ["ANCHOR_REQUIRED"]


def test_keep_ours_and_standard_carry_nothing(placeholder, answers):
    got = _derive(placeholder, answers, [_row("keep_ours"), _row("use_standard"),
                                         _row(None)])
    assert got == {**got, "entries": [], "blockers": []}


def test_our_wording_is_listed_verbatim(placeholder, answers):
    got = _derive(placeholder, answers,
                  [_row("write_wording", wording="Our approved wording for this.")])
    assert [(e["op"], e["text"]) for e in got["entries"]] == [
        ("replace", "Our approved wording for this.")]


# ---------------------------------------------------------------- the API (DB)
@pytest.fixture
def paper(db, api, user, seeded, placeholder, lawyer, owner, tmp_path,
          monkeypatch):
    """A client-paper deal with one point (Worse for us, read in clause 2 of theirs),
    our TEST-ONLY Annexure-2 template, and the owner's New-contract draft on it."""
    tv = _publish(db, api, user, placeholder, lawyer, _test_frame())
    sign_in(api, db, owner)
    c, version, _, evidence, review = _paper(db, tmp_path, owner)
    code = _point(db, review, E.FindingClassification.DEVIATION,
                  [("CONFIRMED", [evidence[1]])])
    draft = api.post(f"{V1}/drafts", json={
        "template_version_id": str(tv.id),
        "answers": dict(tv.layout["check_values"])}).json()["data"]
    return c, version, code, draft


def _answered(monkeypatch, answer: dict | None):
    """The holder's answer and Legal's decision are not this test's (AM-281/290 own
    them): the listed THEIRS row is given ``answer`` as accepted."""
    real = N._changes

    def changes(guard, contract, a, b, **kw):
        listed, before, after = real(guard, contract, a, b, **kw)
        for ch in listed["changes"]:
            ch.update(answer=answer, holder_accepted=True, waiting_for_approval=False)
        return listed, before, after
    monkeypatch.setattr(N, "_changes", changes)


def test_convert_preview_and_make(db, api, paper, monkeypatch):
    c, version, code, draft = paper
    url = f"{V1}/contracts/{c.id}/convert"
    body = {"draft_id": draft["id"]}
    open_ = api.post(f"{url}/preview", json=body).json()["data"]
    assert open_["available"] is False
    assert "PACKAGE_NOT_READY" in {b["code"] for b in open_["blockers"]}   # unanswered
    _answered(monkeypatch, {"answer": "accept_theirs", "version_number": 1})
    dry = api.post(f"{url}/preview", json=body).json()["data"]
    [anchor] = [b for b in dry["blockers"] if b["code"] == "ANCHOR_REQUIRED"]
    assert dry["choices"] and {"key", "number", "heading"} <= set(dry["choices"][0])
    body["add_after"] = {anchor["row_key"]: "CLAUSE_C_2"}
    dry = api.post(f"{url}/preview", json=body).json()["data"]
    assert dry["available"] is True, dry["blockers"]
    [e] = dry["entries"]
    assert (e["op"], e["new_number"], e["text"]) == ("insert_after", "4.2A",
                                                    "Beta clause text.")
    monkeypatch.setattr(N, "_trace", lambda guard, plan: [
        {"n": 1, "row_key": e["row_key"], "choice_id": str(uuid.uuid4()),
         "effect": "NEGATIVE", "decision_ids": [str(uuid.uuid4())], "target_key": "x",
         "op": e["op"], "text_sha256": "0" * 64}])
    stale = api.post(url, json={**body, "expected_entries_sha256": "0" * 64})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_PREVIEW"
    made = api.post(url, json={**body, "expected_entries_sha256": dry["entries_sha256"]})
    assert made.status_code == 201, made.text
    v = db.get(M.DocumentVersion, uuid.UUID(made.json()["data"]["document_version"]["id"]))
    assert v.doc_metadata["package_of"] == str(version.id)
    assert v.doc_metadata["converted_from"] == str(version.id)
    assert v.doc_metadata["special_conditions"]["entries"][0]["text"] == "Beta clause text."
    assert db.query(M.ContractDraft).filter_by(document_version_id=v.id).one()
    assert db.get(M.DraftAnswers, uuid.UUID(draft["id"])) is None       # consumed
    # converted once: the client's paper is answered
    again = api.post(f"{url}/preview", json=body).json()["data"]
    assert [b["code"] for b in again["blockers"]] == ["NOT_CLIENT_PAPER"]


def test_no_annexure_template(db, api, user, seeded, placeholder,
                                               lawyer, owner, tmp_path,
                                               monkeypatch):
    tv = _imported(db, user, placeholder)                      # no Annexure 2
    from datetime import UTC, datetime, timedelta

    from legalmind.drafting import library
    tv.layout = {**tv.layout, "execution": {**tv.layout["execution"], "last": True}}
    library._rehash(db, tv)
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id,
                                   created_at=datetime.now(UTC) - timedelta(days=1)))
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve")
    tid = api.post(f"{V1}/templates/{tv.id}/publish").json()["data"]["id"]
    sign_in(api, db, owner)
    c, *_ = _paper(db, tmp_path, owner)
    draft = api.post(f"{V1}/drafts", json={
        "template_version_id": tid,
        "answers": dict(placeholder[0]["layout"]["check_values"])}).json()["data"]
    _answered(monkeypatch, {"answer": "accept_theirs", "version_number": 1})
    dry = api.post(f"{V1}/contracts/{c.id}/convert/preview",
                   json={"draft_id": draft["id"]}).json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["NO_ANNEXURE"]

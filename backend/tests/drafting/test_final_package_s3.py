"""Annexure 2 on our MSA's shape — `FINAL-PACKAGE-SPEC` S3 (d, g 1–4 and 10).

The precedence sentence is the frame's own role (``precedence: "frame"``); the body is
never edited. The reference frame ``SC.FRAME@2`` ("Annexure 2 — Agreed Amendments") is
DRAFT and has NO precedence sentence: Legal supplies it (rules 7/21). Where a test needs
one, it uses a TEST-ONLY frame whose words say so ("TEST PRECEDENCE SENTENCE …"),
created and approved inside the test, never in config. The STRUCTURAL placeholder
template and synthetic text only.
"""

from __future__ import annotations

import copy
import io
import json
import re
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from sqlalchemy import select

from legalmind.db import models as M
from legalmind.drafting import effective, library, special_conditions
from legalmind.drafting import model as model_
from legalmind.drafting import render_contract as R
from legalmind.ingestion.parsing import parse_docx
from tests.conftest import sign_in
from tests.drafting.test_special_conditions import (  # noqa: F401 — fixtures
    _client_copy,
    _entries,
    _imported,
    _ingest,
    lawyer,
    negotiated,
    test_an_undecided_round_and_another_reader_are_refused,
)
from tools import import_template as T

V1 = "/api/v1"
#: the test-only frame: the reference frame @2's words plus a precedence role that says
#: it is a test — never Legal's text, never in config
TEST_PRECEDENCE = ("TEST PRECEDENCE SENTENCE for {sc:agreement}: not Legal's text, "
                   "used only by the tests.")


def _reference(version: int) -> dict:
    raw = json.loads(T.SPECIAL_REFERENCE.read_text(encoding="utf-8"))
    return next(c for c in raw["clause_versions"]
                if (c["clause_key"], c["version"]) == ("SC.FRAME", version))


def _test_frame() -> dict:
    frame = copy.deepcopy(_reference(2))
    frame.update(clause_key="TEST.FRAME", version=1,
                 title="Annexure 2 — Agreed Amendments (test)")
    at = next(i for i, b in enumerate(frame["body"]) if b["role"] == "opening")
    frame["body"].insert(at + 1, {"kind": "p", "role": "precedence",
                                  "text": TEST_PRECEDENCE})
    frame["source"] = {**frame["source"], "supplier": "test only"}
    return T.check_clause(frame)


# ---------------------------------------------------------------- the reference frame
def test_the_reference_frame_2_is_draft_text_with_no_precedence_sentence():
    """Rules 7/21: nothing in config says which document wins — Legal does (L1)."""
    frame = _reference(2)
    said = special_conditions.roles(frame["body"])
    assert said["title"] == ["Annexure 2 — Agreed Amendments"]
    assert "precedence" not in said
    assert not any(re.search(r"conflict|supersede|prevail", t, re.I)
                   for texts in said.values() for t in texts)
    assert frame["source"]["label"] == special_conditions.FOR_APPROVAL
    # @1 is untouched: earlier records rebuild against it
    assert _reference(1)["title"] == "Annexure A — Special Conditions"


# ---------------------------------------------------------------- the model (no DB)
def _with_frame(placeholder, frame: dict) -> tuple[dict, dict, dict]:
    template, clauses = copy.deepcopy(placeholder)
    clauses[(frame["clause_key"], frame["version"])] = frame
    cfg = {"frame": {"clause_key": frame["clause_key"], "version": frame["version"]},
           "precedence": special_conditions.IN_FRAME, "initials": False}
    template["layout"]["special_conditions"] = cfg
    template["layout"]["execution"]["last"] = True
    return template, clauses, cfg


def test_the_precedence_sentence_follows_the_opening(placeholder, answers):
    """d4: the frame's precedence role is printed right after the opening, in the
    annexure, and the annexure sits after the schedules with the signatures last."""
    frame = _test_frame()
    template, clauses, cfg = _with_frame(placeholder, frame)
    base = model_.resolve(template, clauses, answers)
    m = model_.resolve(template, clauses, answers,
                       special={"frame": frame, "config": cfg, "entries": _entries(base)})
    sc = m["special_conditions"]
    assert [model_.text_of(r) for r in sc["precedence_lines"]] == [
        "TEST PRECEDENCE SENTENCE for Placeholder: not Legal's text, used only by the "
        "tests."]
    docx = R.render(m, template["assets"], contract_ref="T", version_number=2,
                    model_hash=model_.model_hash(m))
    texts = [s.content for s in parse_docx(docx).segments]
    at = texts.index("Annexure 2 — Agreed Amendments")
    assert texts[at + 1].startswith("These Agreed Amendments form an integral part")
    assert texts[at + 2].startswith("TEST PRECEDENCE SENTENCE")
    assert max(i for i, t in enumerate(texts) if t.startswith("Schedule B")) < at
    # a frame without the role: no key, so the model (and its hash) is as before
    plain = _with_frame(placeholder, T.check_clause(_reference(2)))
    m2 = model_.resolve(plain[0], plain[1], answers, special={
        "frame": T.check_clause(_reference(2)), "config": plain[2],
        "entries": _entries(base)})
    assert "precedence_lines" not in m2["special_conditions"]


def test_sc_target_resolves(placeholder, answers):
    """(g)10: a lead naming 2.2 while the body numbers no such clause 9.9 is refused."""
    frame = _test_frame()
    template, clauses, cfg = _with_frame(placeholder, frame)
    base = model_.resolve(template, clauses, answers)
    entries = _entries(base)
    entries[0]["target"] = {**entries[0]["target"], "number": "9.9"}
    with pytest.raises(model_.ModelError, match="does not number so"):
        model_.resolve(template, clauses, answers,
                       special={"frame": frame, "config": cfg, "entries": entries})


# ---------------------------------------------------------------- DB: readiness
def test_readiness_without_and_with_the_precedence_role(db, api, user, seeded,
                                                        placeholder, lawyer):
    """PRECEDENCE_NOT_SUPPLIED while the frame has no precedence role; no body clause
    is pinned or versioned for it; with Legal's role in an approved frame it is ready."""
    tv = _imported(db, user, placeholder)
    clauses_before = copy.deepcopy(tv.clauses)
    T.attach_special_conditions(db, tv, actor_id=user.id, precedence_into="frame",
                                frame_version=2, initials=False)
    assert tv.clauses == clauses_before                          # the body untouched
    assert tv.layout["special_conditions"]["precedence"] == "frame"
    assert not db.execute(select(M.ClauseVersion).where(
        M.ClauseVersion.clause_key == "SC.PRECEDENCE")).scalars().all()
    assert [m["code"] for m in special_conditions.readiness(db, tv)["missing"]] == [
        "FRAME_NOT_APPROVED", "PRECEDENCE_NOT_SUPPLIED"]
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        assert api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve"
                        ).status_code == 200
    db.refresh(tv)
    missing = special_conditions.readiness(db, tv)["missing"]
    assert missing == [{"code": "PRECEDENCE_NOT_SUPPLIED",
                        "detail": special_conditions.PRECEDENCE_NOT_SUPPLIED}]
    # the role, in a frame Legal approved (here a test-only frame)
    frame = _test_frame()
    db.add(M.ClauseVersion(**{k: frame[k] for k in (
        "clause_key", "version", "title", "body", "realises", "stance", "source",
        "content_hash")}, status="DRAFT", created_by=user.id))
    tv.layout = {**tv.layout, "special_conditions": {
        **tv.layout["special_conditions"],
        "frame": {"clause_key": "TEST.FRAME", "version": 1}}}
    db.flush()
    assert api.post(f"{V1}/templates/{tv.id}/clauses/TEST.FRAME/approve"
                    ).status_code == 200
    assert special_conditions.readiness(db, tv) == {"ready": True, "missing": []}


# ---------------------------------------------------------------- DB: end to end
def _publish(db, api, user, placeholder, lawyer, frame: dict | None):
    tv = _imported(db, user, placeholder)
    T.attach_special_conditions(db, tv, actor_id=user.id, precedence_into="frame",
                                frame_version=2, initials=False)
    if frame is not None:
        db.add(M.ClauseVersion(**{k: frame[k] for k in (
            "clause_key", "version", "title", "body", "realises", "stance", "source",
            "content_hash")}, status="DRAFT", created_by=user.id))
        tv.layout = {**tv.layout, "special_conditions": {
            **tv.layout["special_conditions"],
            "frame": {"clause_key": frame["clause_key"], "version": frame["version"]}}}
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
    return db.get(M.TemplateVersion, uuid.UUID(done.json()["data"]["id"]))


@pytest.fixture
def sc_template(db, api, user, seeded, placeholder, lawyer, monkeypatch):
    """Overrides `test_special_conditions.sc_template` for this module: the placeholder
    with Annexure 2's shape — precedence in the frame (a test-only one, approved here),
    the signature page last."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    return _publish(db, api, user, placeholder, lawyer, _test_frame())


def _sdts(data: bytes) -> dict[str, str]:
    """Each body clause's content control, as XML, without the ids a later bookmark
    shifts (one w:id sequence) and the synthetic anchors an entry adds."""
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    out = {}
    for m in re.finditer(r'<w:sdt>.*?<w:tag w:val="(lm:[^"@]+@\d+)"/>.*?</w:sdt>', xml,
                         re.S):
        body = re.sub(r' w:id="\d+"|<w:id w:val="\d+"/>', "", m.group(0))
        body = re.sub(r'<w:bookmark(?:Start|End)[^>]*?(?:~[^"]*")?[^>]*/>', "", body)
        out[m.group(1)] = body
    return out


def test_the_msa_body_is_unchanged_and_entries_verbatim(db, api, negotiated):
    """(g)1, 2: every body clause's content control in the final contract reads as v1's,
    the base model rebuilds to v1's hash; an accepted client text is listed verbatim;
    the precedence sentence follows the opening; the effective contract applies."""
    contract, v1, v2, storage = negotiated
    url = f"{V1}/contracts/{contract.id}/package"
    dry = api.get(url).json()["data"]
    assert dry["available"] is True, dry["blockers"]
    assert dry["precedence"] == {"in_frame": True, "supplied": True}
    theirs = "Clause C.1 text with Placeholder Term Two, as the client asks."
    assert dry["entries"][0]["text"] == theirs                    # verbatim
    made = api.post(url, json={"expected_entries_sha256": dry["entries_sha256"]})
    assert made.status_code == 201, made.text
    v3 = db.get(M.DocumentVersion, uuid.UUID(made.json()["data"]["document_version"]["id"]))
    final, ours = storage.get(v3.storage_key), storage.get(v1.storage_key)
    before, after = _sdts(ours), _sdts(final)
    body = [k for k in before if k.startswith("lm:") and k != "lm:execution"
            and k != "lm:parties"]
    assert body and all(after[k] == before[k] for k in body), [
        k for k in body if after.get(k) != before[k]]
    draft = db.execute(select(M.ContractDraft).where(
        M.ContractDraft.document_version_id == v1.id)).scalar_one()
    from legalmind.api.routers.negotiation import _basis
    assert model_.model_hash(_basis(db, draft)["base"]) == draft.model_hash
    texts = [s.content for s in parse_docx(final).segments]
    at = texts.index("Annexure 2 — Agreed Amendments")
    assert texts[at + 2].startswith("TEST PRECEDENCE SENTENCE")
    assert theirs in texts[at:]
    # the signature page closes the file: nothing of the annexure after it
    assert min(i for i, t in enumerate(texts) if "Signatory Details" in t) > at
    clauses, status, reason = effective.effective_clauses(db, v3.id)
    assert status == effective.APPLIED, reason
    by = {c.section_number: c.content for c in clauses if c.section_number}
    assert by["4.1"] == theirs

    # effective: the client returns it with the precedence sentence changed — never read
    import docx as D
    from docx.oxml.ns import qn
    doc = D.Document(io.BytesIO(final))
    edited = 0
    for p in doc.element.body.iter(qn("w:p")):      # inside the locked control too
        ts = list(p.iter(qn("w:t")))
        if "".join(t.text or "" for t in ts).startswith("TEST PRECEDENCE SENTENCE"):
            ts[0].text = "TEST PRECEDENCE SENTENCE, edited by the client."
            for t in ts[1:]:
                t.text = ""
            edited += 1
    assert edited == 1
    out = io.BytesIO()
    doc.save(out)
    from pathlib import Path
    v4 = _ingest(db, Path(storage.root).parent, contract, out.getvalue(),
                 "CLIENT_MODIFIED")
    _, status, reason = effective.effective_clauses(db, v4.id)
    assert status == effective.NOT_APPLIED
    assert reason == "the frame's precedence sentence is absent or different"


def test_a_blank_in_an_entry_blocks_the_final_contract(db, api, negotiated):
    """AM-324 r5 closed: an entry's text with a blank left in it blocks the package."""
    contract = negotiated[0]
    rows = api.get(f"{V1}/contracts/{contract.id}/changes").json()["data"]["changes"]
    five = next(c for c in rows if c["clause"]["number"] == "5")
    r = api.post(f"{V1}/contracts/{contract.id}/changes/"
                 f"{quote(five['row_key'], safe='')}/answers",
                 json={"answer": "write_wording", "expected_version": 1,
                       "reason": "Our counter", "wording": "Clause D within ___ days."})
    assert r.status_code == 201, r.text
    dry = api.get(f"{V1}/contracts/{contract.id}/package").json()["data"]
    assert not dry["available"]
    blank = [b for b in dry["blockers"] if b["code"] == "BLANKS"]
    assert blank and blank[0]["message"].startswith("Entry 3 (clause 5) still has a "
                                                     "blank to fill (")


def test_a_deal_on_annexure_2_makes_its_final_contract_as_the_package(db, api,
                                                                     negotiated):
    """(f)8: on a template with Annexure 2, a returned and answered deal's final is the
    package, never a final copy of the body (USE_PACKAGE)."""
    contract = negotiated[0]
    dry = api.get(f"{V1}/contracts/{contract.id}/final-copy").json()["data"]
    assert [b["code"] for b in dry["blockers"]] == ["USE_PACKAGE"]
    assert "Annexure 2 — Agreed Amendments" in dry["blockers"][0]["message"]
    assert api.post(f"{V1}/contracts/{contract.id}/final-copy").status_code == 409


@pytest.fixture
def unsupplied(db, api, user, seeded, placeholder, lawyer, monkeypatch, tmp_path):
    """The reference frame @2 approved (inside the test) with no precedence sentence:
    a deal made from it, returned with one accepted change."""
    from legalmind.api.storage import get_storage
    from legalmind.ingestion.storage import LocalFilesystemStorage
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    tv = _publish(db, api, user, placeholder, lawyer, None)
    storage = LocalFilesystemStorage(tmp_path / "objects")
    api.app.dependency_overrides[get_storage] = lambda: storage
    draft = api.post(f"{V1}/drafts", json={"template_version_id": str(tv.id),
                                           "answers": dict(tv.layout["check_values"])}
                     ).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    contract = db.get(M.Contract, uuid.UUID(made.json()["data"]["contract_id"]))
    v1 = db.get(M.DocumentVersion, uuid.UUID(made.json()["data"]["document_version_id"]))
    _ingest(db, tmp_path, contract, _client_copy(storage.get(v1.storage_key)),
            "CLIENT_MODIFIED")
    yield contract
    api.app.dependency_overrides.pop(get_storage, None)


def test_precedence_blocker(db, api, unsupplied):
    """(g)4: no precedence sentence in the frame → the dry run names
    PRECEDENCE_NOT_SUPPLIED in plain words, and Prepare is refused (409)."""
    url = f"{V1}/contracts/{unsupplied.id}/package"
    dry = api.get(url).json()["data"]
    assert {"code": "PRECEDENCE_NOT_SUPPLIED",
            "message": special_conditions.PRECEDENCE_NOT_SUPPLIED,
            "detail": special_conditions.PRECEDENCE_NOT_SUPPLIED} in dry["blockers"]
    assert dry["precedence"] == {"in_frame": True, "supplied": False}
    made = api.post(url, json={"expected_entries_sha256": dry.get("entries_sha256")
                               or "0" * 64})
    assert made.status_code == 409
    assert made.json()["error"]["code"] == "PACKAGE_NOT_READY"


__all__ = ["test_an_undecided_round_and_another_reader_are_refused"]   # (g)3 keep ours

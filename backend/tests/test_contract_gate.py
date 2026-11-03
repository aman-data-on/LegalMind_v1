"""`AM-245` (owner, 2026-11-02, classify-then-route): a paper that is not a contract —
a resume, an invoice — never reaches mapping, `AM-54` recognition or an evaluator. The
reader is told, and the contract's owner may choose "Review anyway", audited. A real
contract and an UNSURE paper behave exactly as before. Synthetic non-legal text only.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from legalmind import config
from legalmind.analysis import service as analysis
from legalmind.api import temporary_review
from legalmind.assist import service
from legalmind.assist.agent import attachments
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.domain.paper_kind import CONTRACT_OR_POLICY, UNSURE, classify_paper
from legalmind.mapping.service import load_clauses
from legalmind.security import audit as A
from tests.assist.agent.test_assist_attachments import _add
from tests.conftest import bespoke_role, grant, grant_role, make_user, sign_in
from tests.test_analysis import (  # noqa: F401  (the fixtures, by name)
    DOCX_MIME,
    LEGAL_RULE,
    MAPPING,
    STANDARD,
    Builder,
    build,
    build_docx,
    storage,
)

RESUME = ["Priya Sharma", "priya.sharma@example.com | linkedin.com/in/priya",
          "Career Objective",
          "Seeking a backend engineering role where I can build reliable services.",
          "Education", "B.Tech, Computer Engineering, Pune University, 2019. CGPA 8.4",
          "Work Experience",
          "Software Engineer, Acme Tech (2019 - 2024): built billing APIs in Python.",
          "Skills", "Python, Go, PostgreSQL, Kubernetes", "Hobbies", "Trekking, chess"]
INVOICE = ["TAX INVOICE", "Invoice No: INV-2026-0412   Invoice Date: 02-11-2026",
           "Bill To: Example Traders Pvt Ltd, Pune   GSTIN: 27AAAAA0000A1Z5",
           "Dedicated server rental, October, quantity one, rate 12,000.00",
           "Sub-total 12,000.00   CGST 9% 1,080.00   SGST 9% 1,080.00",
           "Grand Total 14,160.00",
           "Amount in words: Fourteen thousand one hundred sixty only",
           "Amount Due: 14,160.00 by 15-11-2026"]
CONTRACT = ["This Agreement is entered into by and between the Provider and the Customer.",
            "WHEREAS the Customer wishes to obtain hosting services from the Provider.",
            "1. Limitation of Liability",
            "Liability shall not exceed 24 months of fees paid."]
UNSURE_PAPER = ["1. Limitation of Liability",
                "Liability shall not exceed 24 months of fees paid."]


def _case(db, storage, paragraphs):
    owner = make_user(db)
    grant_role(db, owner, "USER")
    builder = Builder(db, storage, owner)
    builder.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                        mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    return owner, builder.review(paragraphs)


def _no_egress(monkeypatch):
    def never(*_a, **_k):
        raise AssertionError("AM-54 recognition reached for a non-contract")
    monkeypatch.setattr(analysis, "_egress_for", never)
    monkeypatch.setattr(analysis.semantic, "build_index", never)


def _events(db, review, action):
    return db.execute(select(M.AuditEvent).where(
        M.AuditEvent.entity_id == review.id, M.AuditEvent.action == action)).scalars().all()


def _count(db, table, review):
    return db.execute(select(func.count()).select_from(table)
                      .where(table.review_id == review.id)).scalar_one()


@pytest.mark.parametrize("paper", [RESUME, INVOICE], ids=["resume", "invoice"])
def test_a_non_contract_is_never_analysed_and_says_so(api, db, storage, seeded,
                                                      monkeypatch, paper):
    owner, review = _case(db, storage, paper)
    sign_in(api, db, owner)
    _no_egress(monkeypatch)

    r = api.post(f"/api/v1/reviews/{review.id}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["not_a_contract"] is True and body["review_status"] == "DRAFT"
    assert body["paper_kind"]["kind"] == "NOT_A_CONTRACT" and body["paper_kind"]["signals"]
    assert _count(db, M.Finding, review) == 0
    assert db.execute(select(func.count()).select_from(M.Evaluation).join(
        M.Finding, M.Finding.id == M.Evaluation.finding_id).where(
        M.Finding.review_id == review.id)).scalar_one() == 0
    [event] = _events(db, review, A.ANALYSIS_NOT_A_CONTRACT)
    assert event.actor_id == owner.id
    assert event.after_state["signals"] == body["paper_kind"]["signals"]

    version = api.get(f"/api/v1/document-versions/{review.document_version_id}")
    assert version.json()["data"]["paper_kind"] == {
        "kind": "NOT_A_CONTRACT", "signals": body["paper_kind"]["signals"],
        "reviewed_anyway": False}


def test_review_anyway_runs_the_analysis_and_is_audited(api, db, storage, seeded):
    owner, review = _case(db, storage, RESUME)
    sign_in(api, db, owner)
    assert api.post(f"/api/v1/reviews/{review.id}/analyze").json()["data"]["not_a_contract"]

    r = api.post(f"/api/v1/reviews/{review.id}/analyze?review_anyway=true")
    assert r.status_code == 201, r.text
    assert "not_a_contract" not in r.json()["data"]
    db.refresh(review)
    assert review.status is not E.ReviewStatus.DRAFT       # analysed
    [event] = _events(db, review, A.ANALYSIS_REVIEW_ANYWAY)
    assert event.actor_id == owner.id
    assert event.after_state["override"] == {"by": str(owner.id)}
    assert event.after_state["kind"] == "NOT_A_CONTRACT" and event.after_state["signals"]
    version = api.get(f"/api/v1/document-versions/{review.document_version_id}")
    assert version.json()["data"]["paper_kind"]["reviewed_anyway"] is True
    # again, on the analysed Review: refused as already analysed, so no second override
    again = api.post(f"/api/v1/reviews/{review.id}/analyze?review_anyway=true")
    assert again.json()["data"]["already_analysed"] is True
    assert len(_events(db, review, A.ANALYSIS_REVIEW_ANYWAY)) == 1


@pytest.mark.parametrize("who,status", [("narrow", 403), ("stranger", 404)])
def test_review_anyway_needs_what_the_analysis_needs(api, db, storage, seeded, who, status):
    _, review = _case(db, storage, RESUME)
    user = make_user(db)
    if who == "narrow":     # visible as owner, but without review.create
        grant(db, user, bespoke_role(db, "VIEW_ONLY_REVIEWS", ["review.view"]))
        db.get(M.Contract, review.contract_id).owner_id = user.id
    else:
        grant_role(db, user, "USER")
    db.flush()
    sign_in(api, db, user)

    r = api.post(f"/api/v1/reviews/{review.id}/analyze?review_anyway=true")
    assert r.status_code == status
    assert _events(db, review, A.ANALYSIS_REVIEW_ANYWAY) == []
    db.refresh(review)
    assert review.status is E.ReviewStatus.DRAFT


@pytest.mark.parametrize("paper,kind", [(CONTRACT, CONTRACT_OR_POLICY),
                                        (UNSURE_PAPER, UNSURE)],
                         ids=["contract", "unsure"])
def test_a_contract_or_an_unsure_paper_is_analysed_as_before(api, db, storage, seeded,
                                                             paper, kind):
    owner, review = _case(db, storage, paper)
    assert classify_paper(load_clauses(db, review.document_version_id)).kind == kind
    sign_in(api, db, owner)

    body = api.post(f"/api/v1/reviews/{review.id}/analyze").json()["data"]
    assert body["findings_created"] == 1 and "not_a_contract" not in body
    assert _events(db, review, A.ANALYSIS_NOT_A_CONTRACT) == []
    version = api.get(f"/api/v1/document-versions/{review.document_version_id}")
    assert version.json()["data"]["paper_kind"]["kind"] == kind


def test_the_version_says_what_the_gate_will_say_before_any_review(api, db, storage,
                                                                   seeded):
    """The screen's pre-check: GET the version, read `paper_kind`, before creating a
    Review — computed at read time, nothing written."""
    owner, review = _case(db, storage, RESUME)
    sign_in(api, db, owner)
    before = db.execute(select(func.count()).select_from(M.AuditEvent)).scalar_one()
    got = api.get(f"/api/v1/document-versions/{review.document_version_id}")
    paper = got.json()["data"]["paper_kind"]
    assert paper["kind"] == "NOT_A_CONTRACT" and paper["signals"]
    assert paper["reviewed_anyway"] is False
    assert db.execute(select(func.count()).select_from(M.AuditEvent)).scalar_one() \
        == before


def test_a_queued_review_anyway_runs_though_the_worker_sees_no_override(
        api, db, storage, seeded, monkeypatch):
    """Review (2): the worker may run before the request commits its override, so the
    override travels in the job; and a gated job is never logged "already analysed"."""
    from legalmind.worker import tasks
    from tests.test_worker import BROKER, JoinedSession
    monkeypatch.setenv("LEGALMIND_BROKER_URL", BROKER)
    sent: list[dict] = []
    monkeypatch.setattr(tasks.analyse_review, "apply_async",
                        lambda **call: sent.append(call) or type("T", (), {"id": "t"}))
    monkeypatch.setattr(tasks, "_session", lambda: JoinedSession(db))
    owner, review = _case(db, storage, RESUME)
    sign_in(api, db, owner)

    r = api.post(f"/api/v1/reviews/{review.id}/analyze?review_anyway=true")
    assert r.status_code == 202, r.text
    kwargs = sent[0]["kwargs"]
    assert kwargs["review_anyway"] is True
    # the worker's view: no committed override on the reading
    run = analysis._reading_run(db, review.document_version_id)
    run.run_metadata = {k: v for k, v in (run.run_metadata or {}).items()
                        if k != "paper_kind"}
    db.flush()
    assert tasks.analyse_review.apply(kwargs=kwargs, throw=True).get()["analysed"]
    db.refresh(review)
    assert review.status is not E.ReviewStatus.DRAFT

    other = Builder(db, storage, owner).review(INVOICE)
    without = {**kwargs, "review_id": str(other.id)}
    without.pop("review_anyway")
    assert tasks.analyse_review.apply(kwargs=without, throw=True).get() == {
        "review_id": str(other.id), "analysed": False, "reason_code": "not_a_contract"}
    [event] = _events(db, other, A.ANALYSIS_NOT_A_CONTRACT)      # audited there too
    assert event.actor_id == owner.id and event.after_state["signals"]


def test_the_reading_records_its_kind_once(build, db):
    """Review (5): classified when the reading completes, on its run — the gate, the
    version's screen and the type suggestion read it there."""
    from legalmind.db.lookup import paper_kind_of
    review = build.review(RESUME)
    run = analysis._reading_run(db, review.document_version_id)
    recorded = run.run_metadata["paper_kind"]
    assert recorded["kind"] == "NOT_A_CONTRACT" and recorded["signals"]
    assert paper_kind_of(db, review.document_version_id) == recorded
    # a reading from before this was recorded is classified on read, unchanged
    run.run_metadata = {k: v for k, v in run.run_metadata.items() if k != "paper_kind"}
    db.flush()
    assert paper_kind_of(db, review.document_version_id)["kind"] == "NOT_A_CONTRACT"


def test_run_analysis_itself_refuses_a_non_contract(build, db, monkeypatch):
    """The worker's path: the gate sits in `assert_analysable`, which both modes run."""
    _no_egress(monkeypatch)
    review = build.review(INVOICE)
    with pytest.raises(analysis.NotAContract):
        analysis.run_analysis(db, review)
    assert review.status is E.ReviewStatus.DRAFT


# ---- Ask: a chat file -------------------------------------------------------------
def _resume_chat(db, owner, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = service.create_conversation(db, user_id=owner.id, contract_id=None)
    _add(db, conversation_id=conv, data=build_docx(RESUME), kind=attachments.FILE,
         filename="cv.docx", mime=DOCX_MIME)
    return conv


def test_a_resume_attachment_is_never_reviewed(build, db, monkeypatch):
    conv = _resume_chat(db, build.owner, monkeypatch)
    monkeypatch.setattr(temporary_review, "run_analysis", None)       # never runs
    reviewed = temporary_review.review_file(db, conversation_id=conv,
                                            user_id=build.owner.id, legal_position=True,
                                            request_id=None)
    assert reviewed is not None and reviewed.refused == service.NOT_A_CONTRACT
    assert reviewed.findings == []
    outcome = service.record_file_review(
        db, conversation_id=conv, question="review", filename=reviewed.filename,
        findings=[], refused=reviewed.refused, request_id=None)
    assert outcome.text == ("This does not look like a contract or one of our policies, "
                            "so nothing in cv.docx was reviewed against our positions.")
    assert outcome.routed_to_evaluator is False and outcome.comparison is None


@pytest.mark.parametrize("role", ["USER", "LEGAL_REVIEWER"])
def test_asking_for_a_review_of_a_resume_names_it_in_the_fixed_sentence(
        api, db, seeded, build, monkeypatch, role):
    user = make_user(db)
    grant_role(db, user, role)
    db.commit()
    sign_in(api, db, user)
    conv = _resume_chat(db, user, monkeypatch)
    db.commit()
    monkeypatch.setattr(temporary_review, "run_analysis", None)       # never runs
    r = api.post(f"/api/v1/conversations/{conv}/messages", json={
        "question": "Please review this contract as LeapSwitch's lawyer would: what "
                    "must change before we sign, what should we ask the other side, "
                    "and what is fine as it is?"})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["text"].startswith(service.unmeasured_text(service.NOT_A_CONTRACT,
                                                           "cv.docx"))


def test_a_resumes_records_are_never_set_beside_a_position(build, db, monkeypatch):
    """`no_position_refs` (Q-7) covers a non-contract too: an ordinary Ask answer drops
    any comparison block citing the resume's records; a contract's stay comparable."""
    conv = _resume_chat(db, build.owner, monkeypatch)
    _add(db, conversation_id=conv, data=build_docx(CONTRACT), kind=attachments.FILE,
         filename="msa.docx", mime=DOCX_MIME)
    rows = db.execute(text(
        f'SELECT a.filename, c.id FROM "{config.assist_schema()}".attachment_chunks c '
        f'JOIN "{config.assist_schema()}".conversation_attachments a '
        "ON a.id = c.attachment_id")).all()
    by_file = {name: {f"ATT:{i}" for n, i in rows if n == name} for name, _ in rows}
    assert by_file["cv.docx"] and by_file["msa.docx"]
    assert attachments.no_position_refs(db, conv) == by_file["cv.docx"]


# ---- Upload: the type suggestion (AM-50/AM-64) ------------------------------------
def test_a_resume_is_never_sent_to_be_typed(build, db, monkeypatch):
    from legalmind.assist.synthesis import type_suggestion

    def never(*_a, **_k):
        raise AssertionError("a non-contract's text reached the generation seam")
    monkeypatch.setattr(type_suggestion.generation, "generate_raw", never)
    review = build.review(RESUME)
    got = type_suggestion.suggest_document_type(
        db, document_version_id=review.document_version_id)
    assert got == type_suggestion.NOT_CONFIDENT
    [event] = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.entity_id == review.document_version_id,
        M.AuditEvent.action.in_([A.ASSIST_TYPE_SUGGESTION_CALLED,
                                 A.ASSIST_TYPE_SUGGESTION_SKIPPED]))).scalars().all()
    assert event.action == A.ASSIST_TYPE_SUGGESTION_SKIPPED   # never "called"
    assert event.after_state["kind"] == "NOT_A_CONTRACT" and event.after_state["signals"]


@pytest.mark.parametrize("paper", [CONTRACT, UNSURE_PAPER], ids=["contract", "unsure"])
def test_a_contract_or_an_unsure_paper_is_still_typed(build, db, monkeypatch, paper):
    from legalmind.assist.llm import generation
    from legalmind.assist.synthesis import type_suggestion
    sent = []

    def fake(prompt, *, prompt_version, **_k):
        sent.append(prompt)
        return generation.GenerationResult(
            text="TYPE: MSA\nREASON: named", model="fake@test",
            prompt_version=prompt_version, payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(type_suggestion.generation, "generate_raw", fake)
    review = build.review(paper)
    got = type_suggestion.suggest_document_type(
        db, document_version_id=review.document_version_id)
    assert got.suggested_type == "MSA" and len(sent) == 1
    assert "Limitation of Liability" in sent[0]

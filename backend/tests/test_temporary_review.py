"""`AM-143` (owner, 2026-10-15): a chat file is reviewed by the Dashboard's own contract-
review engine, and the result is temporary — never saved as a Contract.

"Dashboard aur Ask attachment dono mein same authoritative contract-review engine use
hona chahiye. Ask attachment ka result temporary rahe." The AI pairs a clause with a
standard; code computes the result; a person decides. Synthetic text only (rule 21).
"""
from __future__ import annotations

from sqlalchemy import func, select, text

from legalmind import config
from legalmind.analysis.service import run_analysis
from legalmind.api import temporary_review
from legalmind.assist import service
from legalmind.assist.agent import attachments
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.assist.agent.test_assist_attachments import _add
from tests.test_analysis import (  # noqa: F401  (the fixtures, by name)
    DOCX_MIME,
    LEGAL_RULE,
    MAPPING,
    STANDARD,
    build,
    build_docx,
    storage,
)

PARAGRAPHS = ["1. Limitation of Liability",
              "Liability shall not exceed 3 months of fees paid."]   # standard: 6
TABLES = (M.Contract, M.DocumentVersion, M.DocumentEvidence, M.Review, M.Finding,
          M.Evaluation, M.AuditEvent)


def _counts(db):
    return {t.__tablename__: db.execute(select(func.count()).select_from(t)).scalar_one()
            for t in TABLES}


def _file_chat(db, owner, monkeypatch):
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = service.create_conversation(db, user_id=owner.id, contract_id=None)
    _add(db, conversation_id=conv, data=build_docx(PARAGRAPHS), kind=attachments.FILE,
         filename="msa.docx", mime=DOCX_MIME)
    return conv


def test_a_chat_file_gets_the_dashboards_result_and_leaves_nothing_behind(build, db,
                                                                          monkeypatch):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    # The Dashboard: the same text uploaded as a document and analysed.
    dashboard = build.review(PARAGRAPHS)
    run_analysis(db, dashboard)
    expected = sorted(f.classification.value for f in db.execute(
        select(M.Finding).where(M.Finding.review_id == dashboard.id)).scalars())

    conv = _file_chat(db, build.owner, monkeypatch)
    before = _counts(db)
    reviewed = temporary_review.review_file(db, conversation_id=conv,
                                            user_id=build.owner.id, legal_position=True,
                                            request_id=None)

    assert reviewed is not None and reviewed.refused is None
    assert reviewed.filename == "msa.docx"
    # the same engine, the same answer
    assert sorted(f["classification"] for f in reviewed.findings) == expected == ["DEVIATION"]
    finding = reviewed.findings[0]
    assert finding["evaluations"][0]["expected_value"]           # the standard, shown
    assert finding["evidence"] and "shall not exceed" in finding["evidence"][0]["content"]
    # temporary: no Contract, Version, evidence, Review, Finding or audit row survives
    assert _counts(db) == before


def test_the_engines_model_calls_stay_audited_and_its_verdicts_go(build, db, monkeypatch):
    """The savepoint rollback must not erase an egress (`AM-30`); the recognition
    verdicts hold the file's words, so they go with it (A4-2)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from legalmind.security import audit as A

    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    conv = _file_chat(db, build.owner, monkeypatch)

    def analysed_with_one_model_call(db, review, **kw):     # what the egress seam writes
        db.execute(pg_insert(M.SemanticRecognitionCache).values(
            configuration_snapshot_id=review.configuration_snapshot_id,
            prompt_version="map-1", prompt_sha256="p" * 64, model="gemini",
            response_text="YES", payload_sha256="h" * 64))
        A.record(db, action=A.ASSIST_GENERATION_CALLED, entity_type="review",
                 entity_id=review.id, after={"purpose": "map-1", "model": "gemini",
                                             "payload_sha256": "h" * 64})
        return run_analysis(db, review, **kw)

    monkeypatch.setattr(temporary_review, "run_analysis", analysed_with_one_model_call)
    reviewed = temporary_review.review_file(db, conversation_id=conv,
                                            user_id=build.owner.id, legal_position=True,
                                            request_id=None)
    assert reviewed is not None and reviewed.findings
    calls = db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == A.ASSIST_GENERATION_CALLED)).scalars().all()
    assert [(c.entity_type, c.entity_id, c.after_state["payload_sha256"]) for c in calls] \
        == [("conversation", conv, "h" * 64)]
    assert db.execute(select(M.SemanticRecognitionCache.response_text).where(
        M.SemanticRecognitionCache.payload_sha256 == "h" * 64)).scalars().all() == []
    assert db.execute(select(func.count()).select_from(M.Review)).scalar_one() == 0


def test_the_standard_is_omitted_not_nulled_without_legal_position(build, db,
                                                                   monkeypatch):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    conv = _file_chat(db, build.owner, monkeypatch)
    reviewed = temporary_review.review_file(db, conversation_id=conv,
                                            user_id=build.owner.id, legal_position=False,
                                            request_id=None)
    assert reviewed is not None
    assert "expected_value" not in reviewed.findings[0]["evaluations"][0]   # SEC-07


def test_no_file_or_no_published_standards_falls_through(db, monkeypatch):
    from tests.conftest import make_user
    owner = make_user(db)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = service.create_conversation(db, user_id=owner.id, contract_id=None)
    assert temporary_review.review_file(db, conversation_id=conv, user_id=owner.id,
                                        legal_position=True, request_id=None) is None
    # a paste is the reader's text, not a document: it keeps the ordinary path
    _add(db, conversation_id=conv, data=b"Clause 4. Liability is capped at 6 months.",
         kind=attachments.PASTE)
    assert attachments.file_segments(db, conv) is None


def test_an_expired_file_loses_its_segments(build, db, monkeypatch):
    """The segments are the file's text: they expire with its chunks (A4-2)."""
    from sqlalchemy import text

    conv = _file_chat(db, build.owner, monkeypatch)
    [att] = attachments.list_for(db, conv)
    assert attachments.file_segments(db, conv) is not None
    attachments.purge_expired(db, now=att.expires_at)
    assert attachments.file_segments(db, conv) is None
    assert db.execute(text(
        f'SELECT segments FROM "{attachments._schema()}".conversation_attachments '
        "WHERE id = :id"), {"id": att.id}).scalar_one() is None


def test_which_questions_run_the_contract_review():
    for asked in ("Review this contract against our approved standards",
                  "Read the uploaded contract and compare it with our organization's "
                  "approved legal standards.",
                  "Which of these terms should we negotiate?",
                  "Is this ok to sign?",
                  "What are your points on this agreement?"):
        assert service.wants_temporary_review(asked), asked
    for asked in ("What is the termination notice period in this file?",
                  "Summarise this agreement",
                  # a clause typed in the question, or an earlier paste: not the file
                  "Any concerns with this clause: the supplier may terminate on 7 days "
                  "notice?",
                  "what are your thoughts on this?",
                  "any issues with it?",
                  "Does this agreement comply with the DPDP Act?",     # a statute: r3
                  # the reader's own asks are answered as points (#199)
                  "Please answer the points below:\n1. Notice period?\n2. Uptime?\n"
                  "3. Penalty?"):
        assert not service.wants_temporary_review(asked), asked


def test_the_ask_endpoint_answers_with_the_temporary_review(api, db, seeded, build,
                                                            monkeypatch):
    from tests.conftest import grant_role, make_user, sign_in
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    user = make_user(db)
    grant_role(db, user, "USER")
    db.commit()
    sign_in(api, db, user)
    conv = _file_chat(db, user, monkeypatch)
    db.commit()

    # `AM-236`: one file is reviewed as LeapSwitch's lawyer would, straight away — this
    # file names no parties, so "we provide the service" is assumed and said
    r = api.post(f"/api/v1/conversations/{conv}/messages",
                 json={"question": "Review this contract against our approved standards"})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["routed_to_evaluator"] is True
    review = body["payload"]
    assert review["kind"] == "deal_review" and review["single"] is True
    assert [f["name"] for f in review["files"]] == ["msa.docx"]
    assert [c["classification"] for row in review["rows"]
            for c in row["cells"].values()] == ["DEVIATION"]
    assert body["text"].startswith("msa.docx, reviewed against our positions: 1 point")
    assert "we provide the service, still being negotiated" in body["text"]
    assert review["answers"]["side_read"] is False                 # assumed, not read

    # a reopened chat shows the same review: it is stored with the turn (`AM-231`)
    replay = api.get(f"/api/v1/conversations/{conv}").json()["data"]["messages"]
    assert replay[-1]["routed_to_evaluator"] is True
    assert replay[-1]["payload"]["rows"] == review["rows"]


def test_an_account_without_review_access_is_told_so(api, db, seeded, build, monkeypatch):
    from tests.conftest import grant_role, make_user, sign_in
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    reviewer = make_user(db)
    grant_role(db, reviewer, "LEGAL_REVIEWER")       # assist.ask, no review.create
    db.commit()
    sign_in(api, db, reviewer)
    conv = _file_chat(db, reviewer, monkeypatch)
    db.commit()
    r = api.post(f"/api/v1/conversations/{conv}/messages",
                 json={"question": "Review this contract against our approved standards"})
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["text"] == service.TEMPORARY_REVIEW_NOT_PERMITTED_TEXT
    assert body["comparison"] is None
    assert body["routed_to_evaluator"] is False     # nothing was compared


def test_no_applicable_standard_is_still_a_result(build, db, monkeypatch):
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = service.create_conversation(db, user_id=build.owner.id, contract_id=None)
    _add(db, conversation_id=conv, kind=attachments.FILE, filename="law.docx",
         mime=DOCX_MIME, data=build_docx(["1. Governing Law",
                                          "This agreement is governed by Indian law."]))
    reviewed = temporary_review.review_file(db, conversation_id=conv,
                                            user_id=build.owner.id, legal_position=True,
                                            request_id=None)
    assert reviewed is not None and reviewed.findings == [] and reviewed.refused is None
    outcome = service.record_file_review(db, conversation_id=conv, question="review",
                                         filename="law.docx", findings=[], refused=None,
                                         request_id=None)
    assert outcome.routed_to_evaluator and outcome.comparison["findings"] == []


def test_a_partial_parse_is_never_reviewed_nor_replaced_by_an_older_file(
        build, db, monkeypatch):
    """`AM-143` r5: only a COMPLETE parse is reviewed — a partial one would let the
    engine report as MISSING what it never read. The newest file is the one asked
    about, so a partial newest file is declined rather than an older complete file
    reviewed in its place; its unread pages are still recorded for the model and the
    reader (F7, document-reading audit 2026-10-15)."""
    build.requirement("LIABILITY-001", E.EvaluatorType.NUMERIC_COMPARISON,
                      mapping=MAPPING, standard=STANDARD, legal_rule=LEGAL_RULE)
    monkeypatch.setenv("LEGALMIND_ASK_ATTACHMENTS", "on")
    conv = service.create_conversation(db, user_id=build.owner.id, contract_id=None)
    from legalmind.ingestion import parsing as P
    words = "1. Limitation of Liability. Liability shall not exceed 3 months of fees paid."
    seg = P.Segment(content=words, original_content=words, page_number=1,
                    source_type=E.EvidenceSourceType.NATIVE_TEXT)
    attachments.add(db, conversation_id=conv, data=b"whole", kind=attachments.FILE,
                    mime="application/pdf", filename="older.pdf", extracted=[seg])
    note = "page 2: no usable native text and OCR not run for this read; page not extracted"
    partial = attachments.add(db, conversation_id=conv, data=b"x", kind=attachments.FILE,
                              mime="application/pdf", filename="scan.pdf",
                              extracted=attachments.PartialText([seg], [2], [note]))
    db.execute(text(f'UPDATE "{config.assist_schema()}".conversation_attachments '
                    "SET created_at = created_at + interval '1 minute' WHERE id = :i"),
               {"i": partial.id})
    assert partial.status == attachments.READY and partial.pages_unread == [2]
    assert temporary_review.review_file(db, conversation_id=conv, user_id=build.owner.id,
                                        legal_position=True, request_id=None) is None
    # a file from before 2026-10-15 holds NULL — newest still wins, still not reviewed
    db.execute(text(f'UPDATE "{config.assist_schema()}".conversation_attachments '
                    "SET segments = NULL WHERE id = :i"), {"i": partial.id})
    assert temporary_review.review_file(db, conversation_id=conv, user_id=build.owner.id,
                                        legal_position=True, request_id=None) is None

"""Ask source routing — the owner's five scenarios (2026-09-10), one test each.

  A  the contract answers                → answer from the contract, cited
  B  the contract is silent, a Company Standard answers
                                         → "not in the document", then the standard, cited
  C  contract and Company Standard differ → both shown, attributed, never adjudicated
  D  a statutory question                → the statute corpus, cited Act + section
  E  nothing relevant anywhere           → only then "not found", naming every source

Nothing termination-specific: the same routing serves any clause. Retrieval over the
document is pinned so the tests are about the ROUTE (which sources, in which fields,
with which wording), not about the ranking, which `tools.verify_assist_quality`
measures against the real material. Generation is faked at the single seam.

Scenario C and `AM-45` r2: the two sources are SHOWN side by side — document answer in
`text`, position in `positions` with its standard code and, when a Review exists, the
evaluator's Finding for that standard. No sentence explains the difference: the position
never enters the payload (`AM-32` r4) and a generated comparison would be the verdict the
assistant may not utter (`AM-25` r4). The Finding IS the authoritative difference.
"""

from __future__ import annotations

from sqlalchemy import text

from legalmind import config
from legalmind.assist import generation, intent, service, store
from tests.test_assist_ask import (  # noqa: F401  (fixtures re-exported for pytest)
    USER_PERMS,
    _conversation,
    _ratified_positions,
    _synthetic_statute,
    indexed_contract,
    storage,
)


def _grounded_generation(monkeypatch):
    def fake(question, evidence, **kwargs):
        return generation.GenerationResult(
            text=evidence[0].split(".")[0].strip() + " [1].", model="fake",
            prompt_version="test", payload_sha256="0" * 64, latency_ms=1)
    monkeypatch.setattr(service.generation, "generate", fake)


def _pin_document(monkeypatch, db, version_id, *, open_, needle="terminate"):
    row = db.execute(text(
        f'SELECT id, evidence_id, content FROM "{config.assist_schema()}".chunks '
        'WHERE document_version_id = :d AND content ILIKE :n ORDER BY ordinal LIMIT 1'),
        {"d": version_id, "n": f"%{needle}%"}).first()
    hit = store.SearchHit(chunk_id=row[0], evidence_id=row[1], content=row[2],
                          page_number=1, section_number=None, section_title=None,
                          source_type="NATIVE_TEXT", retrieval_score=0.9)
    monkeypatch.setattr(service.store, "search_hybrid", lambda *a, **k: store.RetrievalOutcome(
        hits=[hit] if open_ else [], gate_open=open_, lexical_hit=open_,
        vector_top_score=None, vector_peak_gap=None, strategy_version="pinned",
        embedding_model=None))
    return row[2]


def test_A_the_contract_answers_and_is_cited(db, user, indexed_contract, monkeypatch):
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    clause = _pin_document(monkeypatch, db, version.id, open_=True)
    out = service.ask(db, conversation_id=_conversation(db, user, contract),
                      document_version_id=version.id, permissions=USER_PERMS,
                      question="What is the termination notice period?")
    assert out.answer_state.value == "ANSWERED"
    assert out.text.rstrip(" [1].") in clause
    assert out.citations and out.citations[0].evidence_id
    assert out.positions == [] and out.statutes is None
    assert out.domains == ("DOCUMENT", "POSITIONS")     # positions searched beside, empty


def test_B_the_contract_is_silent_and_the_company_standard_answers(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    _pin_document(monkeypatch, db, version.id, open_=False)
    out = service.ask(db, conversation_id=_conversation(db, user, contract),
                      document_version_id=version.id, permissions=USER_PERMS,
                      question="How must a handler treat every widget with care?")
    assert out.answer_state.value == "ANSWERED"
    assert out.text == service.POSITIONS_BESIDE_TEXT
    assert out.text.startswith("No answer was found in the selected document.")
    assert out.positions[0]["standard_code"] == "TESTPOS-MSA-001"
    assert out.positions[0]["source_clause"] == "9.9 Widget Handling"
    assert "Widgets shall be handled with care" in out.positions[0]["content"]
    assert out.citations == []
    assert out.domains == ("DOCUMENT", "POSITIONS")


def test_C_contract_and_company_standard_are_both_shown_and_never_adjudicated(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    clause = _pin_document(monkeypatch, db, version.id, open_=True)
    out = service.ask(db, conversation_id=_conversation(db, user, contract),
                      document_version_id=version.id, permissions=USER_PERMS,
                      question="How must a handler treat every widget with care?")
    assert out.answer_state.value == "ANSWERED"
    # The document's answer, in its own field, cited to the document …
    assert out.text.rstrip(" [1].") in clause and out.citations
    # … the organization's position beside it, verbatim, attributed to its standard …
    assert out.positions[0]["standard_code"] == "TESTPOS-MSA-001"
    assert "Widgets shall be handled with care" in out.positions[0]["content"]
    assert out.positions[0]["finding"] is None          # no Review yet: nothing to point at
    # … and no sentence anywhere judges one against the other.
    assert not intent.is_verdict_statement(out.text)
    assert "Widgets shall be handled" not in out.text
    assert out.domains == ("DOCUMENT", "POSITIONS")


def test_D_a_statutory_question_is_answered_from_the_statute_corpus(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _synthetic_statute(db, tmp_path)
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    _pin_document(monkeypatch, db, version.id, open_=False)
    out = service.ask(db, conversation_id=_conversation(db, user, contract),
                      document_version_id=version.id, permissions=USER_PERMS,
                      question="What does section 3 of the Synthetic Widgets Act say?")
    assert out.answer_state.value == "ANSWERED"
    assert out.text == service.STATUTES_BESIDE_TEXT
    assert out.statutes["answer_state"] == "ANSWERED"
    assert out.statutes["citations"][0]["citation"] == "The Synthetic Widgets Act, 2099, s. 3"
    assert out.citations == []
    assert out.domains == ("DOCUMENT", "POSITIONS", "STATUTES")


def test_E_nothing_relevant_anywhere_is_the_only_time_not_found_is_said(
        db, user, indexed_contract, tmp_path, monkeypatch):
    _ratified_positions(db, user, tmp_path)
    _synthetic_statute(db, tmp_path)
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    _pin_document(monkeypatch, db, version.id, open_=False)
    out = service.ask(db, conversation_id=_conversation(db, user, contract),
                      document_version_id=version.id, permissions=USER_PERMS,
                      question="Which colour must the quarterly invoices be printed in?")
    assert out.answer_state.value != "ANSWERED"
    assert out.positions == [] and (out.statutes is None or out.statutes.get("text") is None)
    assert out.text.startswith(
        "Information not found in the selected document or in the organization's "
        "approved positions or in the approved statute corpus.")
    assert out.domains == ("DOCUMENT", "POSITIONS", "STATUTES")


def test_the_document_is_never_the_only_source_for_a_caller_who_may_read_more(
        db, user, indexed_contract, tmp_path, monkeypatch):
    """The defect the phase re-audits: with a document open, a question the document
    does not answer still reaches every other authorized source — and for a caller
    who may read none of them, the refusal names the document alone."""
    _ratified_positions(db, user, tmp_path)
    contract, version = indexed_contract
    _grounded_generation(monkeypatch)
    _pin_document(monkeypatch, db, version.id, open_=False)
    question = "How must a handler treat every widget with care?"
    wide = service.ask(db, conversation_id=_conversation(db, user, contract),
                       document_version_id=version.id, permissions=USER_PERMS,
                       question=question)
    narrow = service.ask(db, conversation_id=_conversation(db, user, contract),
                         document_version_id=version.id,
                         permissions=frozenset({"assist.ask"}), question=question)
    assert wide.positions and wide.domains == ("DOCUMENT", "POSITIONS")
    assert narrow.positions == [] and narrow.domains == ("DOCUMENT",)
    assert narrow.text.startswith("Information not found in the selected document.")

"""An exit question answered through the whole agent turn (AM-167, 2026-10-19): the clause
the answer cites says leaving costs nothing and prepaid fees come back, and the first live
answer stated only the notice period, added "it would breach the contract" and offered to
continue. A scripted fake provider — no model call. Synthetic text only (rule 21)."""
from __future__ import annotations

import json

from legalmind.assist.agent import agent
from legalmind.assist.ingestion import indexing
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.validation import DOCX_MIME
from tests.assist.agent.test_assist_agent import Scripted, _ctx, _turn
from tests.assist.integration.test_assist_ask import storage  # noqa: F401
from tests.test_ingestion import build_docx

CLAUSE = ("13. Service Termination: The Customer may terminate the Services (i) by "
          "providing 15 days prior written notice; or (ii) immediately upon written notice "
          "if the Services fail the agreed SLA for 3 consecutive days. No lock-in, early "
          "termination charges, penalties or minimum commitment charges shall apply. Any "
          "prepaid fees for the unutilised period shall be refunded to the Customer on a "
          "pro-rata basis within 15 days of termination.")
SEARCH = {"name": "search_knowledge", "args": {"query": "terminate notice early termination"}}
FINAL = json.dumps({"analysis": "13 bears on notice.", "assessment": "n/a", "blocks": [
    {"kind": "sourced", "cites": ["D1"], "text": "The customer may terminate on 15 days' "
     "prior written notice, or immediately if the Services fail the agreed SLA for 3 "
     "consecutive days."},
    {"kind": "reasoning", "cites": [], "text": "If the customer gives no notice, it would "
     "breach the contract terms."},
    {"kind": "next_step", "cites": [], "text": "Would you like me to analyze the refund "
     "provisions?"}]})


def test_the_cost_of_leaving_is_in_the_answer_and_no_invented_breach_or_offer(
        db, user, storage):
    contract = M.Contract(owner_id=user.id, name="Exit", contract_type="OTHER",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                              data=build_docx([CLAUSE]), filename="m.docx",
                              declared_mime=DOCX_MIME).document_version
    indexing.index_document_version(db, version.id)
    p = Scripted(_turn(calls=[SEARCH]), final=FINAL)
    t = agent.run_turn(p, _ctx(db, user, contract), "customer can exist without give the notice")
    texts = [b["text"] for b in t.blocks]
    assert t.outcome == "answered", t.violations_final
    assert any("15 days" in x and "3 consecutive days" in x for x in texts)
    assert any(x.startswith("No lock-in, early termination charges") for x in texts)
    assert any("refunded to the Customer on a pro-rata basis" in x for x in texts)
    assert not any("breach" in x.lower() for x in texts)         # V18: nobody wrote it
    assert not any(b["kind"] == "next_step" and x.startswith("Would you like")
                   for b, x in zip(t.blocks, texts, strict=True))


def test_an_exit_question_reads_the_leaving_clauses_with_a_local_search(
        db, user, storage, monkeypatch):
    """The recall step is wired into the turn and asks for what leaving costs and for the
    clause a cited summary points to — local retrieval, never a model call."""
    contract = M.Contract(owner_id=user.id, name="Exit2", contract_type="OTHER",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                              data=build_docx([CLAUSE]), filename="m.docx",
                              declared_mime=DOCX_MIME).document_version
    indexing.index_document_version(db, version.id)
    seen: list[str] = []
    real = agent._exit_recall

    def spy(ctx, reg, blocks, shown):
        seen.append("recall")
        return real(ctx, reg, blocks, shown)
    monkeypatch.setattr(agent, "_exit_recall", spy)
    agent.run_turn(Scripted(_turn(calls=[SEARCH]), final=FINAL), _ctx(db, user, contract),
                   "can the customer cancel?")
    assert seen == ["recall"]
    agent.run_turn(Scripted(_turn(calls=[SEARCH]), final=FINAL), _ctx(db, user, contract),
                   "what is the liability cap?")
    assert seen == ["recall"]                          # not an exit question: not asked

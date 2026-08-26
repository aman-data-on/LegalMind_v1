"""The assist-lane conversation endpoints — AB-3/AB-4, additive to the locked 49.x API.

Three endpoints, all behind `assist.ask`, all following the house conventions: the
envelope, the Guard's visibility-then-permission ordering, byte-identical 404s for
anything out of scope, and CSRF on writes (inherited from the app middleware).

The confidentiality posture worth stating: a conversation is scoped to a contract the
requester can view, retrieval is scoped inside the SQL to that contract's document
version (`AM-25` r6), and a conversation belonging to someone else is `NotVisible` —
indistinguishable from one that does not exist (r7, `API-10`).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, text

from legalmind import config
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.schemas import AskRequest, ConversationCreate
from legalmind.assist import service
from legalmind.db import models as M
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["assist"])


def _latest_document_version(guard: Guard, contract_id: UUID) -> M.DocumentVersion:
    row = guard.db.execute(
        select(M.DocumentVersion)
        .where(M.DocumentVersion.contract_id == contract_id)
        .order_by(M.DocumentVersion.version_number.desc())
        .limit(1)).scalar_one_or_none()
    if row is None:
        raise BusinessRuleRejected(
            "the contract has no uploaded document to ask about")
    return row


def _visible_conversation(guard: Guard, conversation_id: UUID) -> dict:
    """Ownership check with the byte-identical-404 discipline.

    A conversation is visible to its creator only. `NotVisible` — not Forbidden —
    for anyone else, so existence never leaks (`AM-25` r7, `API-10`).
    """
    schema = config.assist_schema()
    row = guard.db.execute(text(f"""
        SELECT id, user_id, contract_id, created_at
          FROM "{schema}".conversations WHERE id = :i
    """), {"i": conversation_id}).first()
    if row is None or row[1] != guard.user_id:
        raise NotVisible("conversation", conversation_id)
    return {"id": row[0], "user_id": row[1], "contract_id": row[2],
            "created_at": row[3]}


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationCreate,
                        guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.ASSIST_ASK)
    contract_id = None
    if body.contract_id is not None:
        # Visibility before anything else: asking about a contract requires being
        # able to see it, resolved by the existing Guard chain.
        contract = guard.contract(UUID(body.contract_id), P.ASSIST_ASK)
        contract_id = contract.id
    conversation_id = service.create_conversation(
        guard.db, user_id=guard.user_id, contract_id=contract_id)
    return data({"id": str(conversation_id),
                 "contract_id": str(contract_id) if contract_id else None})


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID,
                     guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    schema = config.assist_schema()
    turns = guard.db.execute(text(f"""
        SELECT m.id, m.ordinal, m.role, m.content, a.answer_state
          FROM "{schema}".messages m
          LEFT JOIN "{schema}".ai_answers a ON a.message_id = m.id
         WHERE m.conversation_id = :c
         ORDER BY m.ordinal
    """), {"c": conversation_id}).all()
    return data({
        "id": str(conversation_id),
        "contract_id": (str(conversation["contract_id"])
                        if conversation["contract_id"] else None),
        "messages": [{"id": str(t[0]), "ordinal": t[1], "role": t[2],
                      "content": t[3], "answer_state": t[4]} for t in turns],
    })


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def ask(conversation_id: UUID, body: AskRequest,
        guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    if conversation["contract_id"] is None:
        # Domain C (general legal research) has no authorized corpus table yet
        # (C-15/C-16); a document-less conversation cannot retrieve anything, and
        # saying so plainly beats a refusal that looks like a search miss.
        raise BusinessRuleRejected(
            "this conversation has no contract attached; general legal research "
            "is not available yet")

    # The full existing authorization chain for the underlying document — the same
    # resolver every other document read goes through (AM-25 r6: server-side, before
    # retrieval).
    guard.contract(conversation["contract_id"], P.ASSIST_ASK)
    version = _latest_document_version(guard, conversation["contract_id"])

    if not (body.question or "").strip():
        raise BusinessRuleRejected("the question is empty")
    if len(body.question) > 2000:
        raise BusinessRuleRejected("the question exceeds 2000 characters")

    outcome = service.ask(guard.db, conversation_id=conversation_id,
                          document_version_id=version.id,
                          question=body.question, request_id=guard.request_id)
    return data({
        "conversation_id": str(outcome.conversation_id),
        "message_id": str(outcome.message_id),
        "answer_state": outcome.answer_state.value,
        "text": outcome.text,
        "routed_to_evaluator": outcome.routed_to_evaluator,
        "citations": [{
            "chunk_id": str(c.chunk_id),
            "page_number": c.page_number,
            "section_ref": c.section_ref,
            "excerpt": c.excerpt,
            # A retrieval score, labeled as exactly that — never confidence
            # (AI-03 item 16; rule 12).
            "retrieval_score": round(c.retrieval_score, 4),
        } for c in outcome.citations],
    })

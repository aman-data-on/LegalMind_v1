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

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text

from legalmind import config
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.pagination import Page, page_params
from legalmind.api.schemas import AskRequest, ConversationCreate
from legalmind.assist import service
from legalmind.assist.chunking import leading_section_ref
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


@router.get("/conversations")
def list_conversations(guard: Guard = Depends(get_guard),
                       page: Page = Depends(page_params),
                       contract_id: UUID | None = Query(None)) -> dict:
    """The caller's own conversations, newest first — 49.6 r4 applied to the assist
    lane: the list carries exactly what `GET /conversations/{id}` would return and
    nothing a GET would 404 on, so it cannot become the enumeration oracle `AM-25`
    r7 forbids. `contract_id` is the one allow-listed filter (49.6 r3): the workspace
    for a document shows that document's history and no other."""
    guard.permission(P.ASSIST_ASK)
    schema = config.assist_schema()
    where = "user_id = :u" + (" AND contract_id = :k" if contract_id else "")
    params: dict = {"u": guard.user_id}
    if contract_id:
        params["k"] = contract_id
    total = guard.db.execute(text(
        f'SELECT count(*) FROM "{schema}".conversations WHERE {where}'
    ), params).scalar_one()
    rows = guard.db.execute(text(f"""
        SELECT c.id, c.contract_id, c.created_at,
               (SELECT count(*) FROM "{schema}".messages m
                 WHERE m.conversation_id = c.id) AS turns,
               (SELECT m.content FROM "{schema}".messages m
                 WHERE m.conversation_id = c.id AND m.role = 'USER'
                 ORDER BY m.ordinal LIMIT 1) AS first_question
          FROM "{schema}".conversations c
         WHERE {where}
         ORDER BY c.created_at DESC, c.id DESC
         LIMIT :lim OFFSET :off
    """), {**params, "lim": page.page_size, "off": page.offset}).all()
    return paginated([{
        "id": str(r[0]),
        "contract_id": str(r[1]) if r[1] else None,
        "created_at": r[2].isoformat() if r[2] else None,
        "message_count": r[3],
        "first_question": r[4],
    } for r in rows], page=page.page, page_size=page.page_size, total=total)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID,
                     guard: Guard = Depends(get_guard)) -> dict:
    """A conversation with its turns — and, for every assistant turn, the SAME
    citation objects the live answer carried, so a reload renders exactly what was
    shown (`AM-25` r5: every answer traceable to its retrieved evidence, on every
    view of it, not only the first).

    Citations are rebuilt from `answer_citations` (the verified claim→chunk rows),
    the chunk's evidence row (page, section) and the retrieval run (the score for
    that chunk in THAT query — a property of the query, so it lives on the run, not
    the chunk). Refusals and routed turns have no citation rows and get `[]`.
    """
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    schema = config.assist_schema()
    turns = guard.db.execute(text(f"""
        SELECT m.id, m.ordinal, m.role, m.content, a.answer_state, a.id
          FROM "{schema}".messages m
          LEFT JOIN "{schema}".ai_answers a ON a.message_id = m.id
         WHERE m.conversation_id = :c
         ORDER BY m.ordinal
    """), {"c": conversation_id}).all()

    cited = guard.db.execute(text(f"""
        SELECT ac.answer_id, ac.claim_ordinal, ch.id, ch.content,
               e.page_number, e.section_number,
               (SELECT (h->>'score')::float
                  FROM jsonb_array_elements(r.results->'hits') h
                 WHERE h->>'chunk_id' = ch.id::text
                 LIMIT 1) AS score,
               e.id AS evidence_id
          FROM "{schema}".answer_citations ac
          JOIN "{schema}".ai_answers a ON a.id = ac.answer_id
          JOIN "{schema}".messages m ON m.id = a.message_id
          JOIN "{schema}".chunks ch ON ch.id = ac.chunk_id
          JOIN document_evidence e ON e.id = ch.evidence_id
          LEFT JOIN "{schema}".retrieval_runs r ON r.id = a.retrieval_run_id
         WHERE m.conversation_id = :c
         ORDER BY ac.claim_ordinal, ch.id
    """), {"c": conversation_id}).all()
    by_answer: dict = {}
    for row in cited:
        by_answer.setdefault(row[0], []).append({
            "chunk_id": str(row[2]),
            "evidence_id": str(row[7]),
            "page_number": row[4],
            "section_ref": row[5] or leading_section_ref(row[3]),
            "excerpt": row[3][:240],
            # A retrieval score, labeled as exactly that — never confidence
            # (AI-03 item 16; rule 12). None only if the run row is missing.
            "retrieval_score": round(row[6], 4) if row[6] is not None else None,
        })

    return data({
        "id": str(conversation_id),
        "contract_id": (str(conversation["contract_id"])
                        if conversation["contract_id"] else None),
        "messages": [{
            "id": str(t[0]), "ordinal": t[1], "role": t[2], "content": t[3],
            "answer_state": t[4],
            "routed_to_evaluator": (t[2] == "ASSISTANT"
                                    and t[3] == service.EVALUATOR_ROUTE_TEXT),
            "citations": by_answer.get(t[5], []),
        } for t in turns],
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
            "evidence_id": str(c.evidence_id),
            "page_number": c.page_number,
            "section_ref": c.section_ref,
            "excerpt": c.excerpt,
            # A retrieval score, labeled as exactly that — never confidence
            # (AI-03 item 16; rule 12).
            "retrieval_score": round(c.retrieval_score, 4),
        } for c in outcome.citations],
    })

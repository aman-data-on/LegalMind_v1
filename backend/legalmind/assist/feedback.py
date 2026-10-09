"""Answer feedback (`AM-123`, owner D2c 2026-10-08): the reader's own rating and the
implicit signals around an answer, logged for evaluation and for nothing else.

Nothing reads these rows to change an answer — no tuning, no retraining, no ranking
(`AM-26`). The answer's model, prompt version and cited records are reached by join
through `ai_answers` and the evidence ledger, never copied here. The free-text reason
lives in this table only: never in the audit trail, never in a log line (53.3).
"""
from __future__ import annotations

import logging
import uuid
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.query import presentation
from legalmind.assist.retrieval import cache
from legalmind.assist.retrieval.calibration import RETRIEVAL_STRATEGY_VERSION
from legalmind.observability.logs import log_event
from legalmind.security import audit

RATING, COPY, CITE_CLICK, QUICK_CLOSE, REASK = (
    "RATING", "COPY", "CITE_CLICK", "QUICK_CLOSE", "REASK")
UP, DOWN = "UP", "DOWN"

#: The owner's threshold (D2c): this many Not helpful ratings on one query type raise a
#: human alert. ponytail: a rolling 30-day window so one old cluster does not alert
#: forever; the owner named no window — change it here if they do.
DOWN_CLUSTER_MIN = 3
DOWN_CLUSTER_DAYS = 30
DOWN_CLUSTER_SIGNAL = "assist.feedback_down_cluster"


def corpus_version(db: DBSession) -> str:
    """How the answer was searched and over what: the retrieval strategy plus the
    corpus's live state (`cache.corpus_version` — moves on any re-ingest)."""
    return f"{RETRIEVAL_STRATEGY_VERSION}|{cache.corpus_version(db)}"


def _schema() -> str:
    return config.assist_schema()


def answer_conversation(db: DBSession, message_id: UUID) -> UUID | None:
    """The conversation of an ASSISTANT message, else None — a user turn is not an
    answer and is treated exactly like an id that does not exist."""
    return db.execute(text(
        f'SELECT conversation_id FROM "{_schema()}".messages '
        "WHERE id = :m AND role = 'ASSISTANT'"), {"m": message_id}).scalar()


def query_type(db: DBSession, message_id: UUID) -> str:
    """Deterministic, no model: the asked question's task (`presentation.read`) and the
    sorted domains the answer cited, e.g. ``summary:DOCUMENTS,POSITIONS``."""
    s = _schema()
    question = db.execute(text(f"""
        SELECT u.content FROM "{s}".messages a
          JOIN "{s}".messages u ON u.conversation_id = a.conversation_id
                               AND u.role = 'USER' AND u.ordinal < a.ordinal
         WHERE a.id = :m ORDER BY u.ordinal DESC LIMIT 1"""), {"m": message_id}).scalar()
    domains = db.execute(text(f"""
        SELECT DISTINCT ce.domain FROM "{s}".ai_answers an
          JOIN "{s}".answer_evidence ae ON ae.answer_id = an.id
          JOIN "{s}".conversation_evidence ce ON ce.id = ae.ledger_id
         WHERE an.message_id = :m ORDER BY ce.domain"""),
        {"m": message_id}).scalars().all()
    return f"{presentation.read(question or '').task}:{','.join(domains) or 'NONE'}"


def record(db: DBSession, *, message_id: UUID, user_id: UUID, kind: str,
           rating: str | None = None, reason: str | None = None,
           request_id: str | None = None) -> UUID:
    """Upsert one signal — a repeat is one row, a rating flips UP <-> DOWN in place —
    audit its kind only, and raise the down-cluster alert at the owner's threshold."""
    qtype, s = query_type(db, message_id), _schema()
    # The same rating again with no reason keeps the reason already sent; a flip clears
    # it. `prev` reads the row as it was before this statement, so the alert below fires
    # only when the row BECOMES Not helpful — never again for a repeat of the same vote.
    feedback_id, previous = db.execute(text(f"""
        WITH prev AS (SELECT rating FROM "{s}".answer_feedback
                       WHERE message_id = :m AND user_id = :u AND kind = :k)
        INSERT INTO "{s}".answer_feedback AS f
            (id, message_id, user_id, kind, rating, reason, query_type, corpus_version)
        VALUES (:i, :m, :u, :k, :r, :why, :q, :cv)
        ON CONFLICT (message_id, user_id, kind) DO UPDATE
           SET rating = EXCLUDED.rating, created_at = now(),
               reason = CASE WHEN EXCLUDED.rating = f.rating AND EXCLUDED.reason IS NULL
                             THEN f.reason ELSE EXCLUDED.reason END
        RETURNING id, (SELECT rating FROM prev)"""),
        {"i": uuid.uuid4(), "m": message_id, "u": user_id, "k": kind, "r": rating,
         "why": reason, "q": qtype, "cv": corpus_version(db)}).one()
    audit.record(db, action=audit.ASSIST_FEEDBACK_RECORDED, entity_type="message",
                 entity_id=message_id, actor_id=user_id, request_id=request_id,
                 after={"kind": kind})
    if rating == DOWN and previous != DOWN:
        count = down_count(db, qtype)
        if count >= DOWN_CLUSTER_MIN:
            log_event(DOWN_CLUSTER_SIGNAL, level=logging.WARNING, request_id=request_id,
                      query_type=qtype, count=count, window_days=DOWN_CLUSTER_DAYS)
    return feedback_id


def down_count(db: DBSession, qtype: str) -> int:
    return db.execute(text(f"""
        SELECT count(*) FROM "{_schema()}".answer_feedback
         WHERE kind = 'RATING' AND rating = 'DOWN' AND query_type = :q
           AND created_at > now() - make_interval(days => :d)"""),
        {"q": qtype, "d": DOWN_CLUSTER_DAYS}).scalar_one()


def _normalised(question: str) -> str:
    return " ".join((question or "").casefold().split()).rstrip(" ?.!")


def note_reask(db: DBSession, *, conversation_id: UUID, user_id: UUID, question: str,
               request_id: str | None = None) -> None:
    """The same question asked again in the same chat: a negative signal on the answer
    it followed. Read before the new turn is stored; nothing changes for the reader.

    ponytail: a retry after the client's own timeout (`ASK_TIMEOUT_MS`) also lands here,
    against an answer the reader never saw — accepted as noise (150 s timeouts are rare);
    a retry flag on `AskRequest` sent by the client's "Try again" removes it."""
    s = _schema()
    last = db.execute(text(f"""
        SELECT u.content, (SELECT a.id FROM "{s}".messages a
                            WHERE a.conversation_id = u.conversation_id
                              AND a.role = 'ASSISTANT' AND a.ordinal > u.ordinal
                            ORDER BY a.ordinal DESC LIMIT 1)
          FROM "{s}".messages u
         WHERE u.conversation_id = :c AND u.role = 'USER'
         ORDER BY u.ordinal DESC LIMIT 1"""), {"c": conversation_id}).first()
    if last and last[1] and _normalised(last[0]) == _normalised(question):
        record(db, message_id=last[1], user_id=user_id, kind=REASK, request_id=request_id)

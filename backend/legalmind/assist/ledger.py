"""The per-conversation evidence ledger — Ask plan 1.6–1.8, `AM-110` (audit A5-1…A5-3).

Every record an answer cited gets a code-assigned key in its conversation — `C3`, `P1`,
`S2`, `H1`, `D4`, `U1` — stored with its natural key (`source_ref`), authority, status
as seen, location and the SHA-256 of the exact text handed to the model. THE TEXT IS
NOT STORED: a re-fetch reads it live, under the caller's permissions at that moment, so
the ledger never becomes a second copy of the corpus and nothing deleted, expired or
withdrawn can resurface from it.

Recorded once per answered turn from what the answer actually cited (A5-2): the rows
`answer_citations` already holds — document, position and statute — plus the
Constitution and user-material refs that table has no column for (A5-3), passed in by
the path that cited them.

`refetch` states what is true NOW (decision A-16): `current` when the record is visible
and its text unchanged; `stale` when it is visible but changed or superseded — a new
document version, a retired standard, a repealed Act, a non-current Constitution item,
or a re-chunk that dropped the pointer; `unavailable` when it is no longer visible to
this caller, expired, or gone. Every domain's live permission rule runs again (A1 gap
4); nothing is trusted from write time. An unknown key and an invisible one return the
same `unavailable`, with no text.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist import authority, positions
from legalmind.security import permissions as P

CURRENT, STALE, UNAVAILABLE = "current", "stale", "unavailable"
_DOMAIN = {"C": "CONSTITUTION", "H": "CONSTITUTION", "P": "POSITIONS", "S": "STATUTES",
           "D": "DOCUMENTS", "U": "ATTACHMENTS"}
_POINTER = {"CONSTITUTION": "knowledge_item_id", "POSITIONS": "position_chunk_id",
            "STATUTES": "statute_chunk_id", "DOCUMENTS": "chunk_id",
            "ATTACHMENTS": "attachment_chunk_id"}


@dataclass(frozen=True)
class Record:
    """One cited record, as handed to the model."""
    source_class: str               # C P S H D U
    source_ref: str
    pointer: UUID | None
    text: str
    authority: str
    status: str
    location: str | None = None
    source_version: str | None = None


@dataclass(frozen=True)
class Fetched:
    key: str
    state: str                      # current · stale · unavailable
    text: str | None = None
    source_ref: str | None = None
    authority: str | None = None


def text_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _schema() -> str:
    return config.assist_schema()


def record_answer(db: DBSession, *, conversation_id: UUID, answer_id: UUID,
                  turn_message_id: UUID, extra: Iterable[Record] = ()) -> list[str]:
    """Ledger rows and `answer_evidence` links for one answer, in citation order; the
    keys, in that order. The same record cited again keeps its key."""
    keys: list[str] = []
    for ordinal, rec in enumerate([*_cited(db, answer_id), *extra]):
        ledger_id, key = _upsert(db, conversation_id, turn_message_id, rec)
        db.execute(text(f"""
            INSERT INTO "{_schema()}".answer_evidence
                (id, answer_id, ledger_id, claim_ordinal)
            VALUES (:i, :a, :l, :o) ON CONFLICT DO NOTHING"""),
            {"i": uuid4(), "a": answer_id, "l": ledger_id, "o": ordinal})
        keys.append(key)
    return keys


def keys_for_answer(db: DBSession, answer_id: UUID) -> list[str]:
    return list(db.execute(text(f"""
        SELECT e.evidence_key FROM "{_schema()}".answer_evidence ae
          JOIN "{_schema()}".conversation_evidence e ON e.id = ae.ledger_id
         WHERE ae.answer_id = :a ORDER BY ae.claim_ordinal"""),
        {"a": answer_id}).scalars())


def _cited(db: DBSession, answer_id: UUID) -> list[Record]:
    s = _schema()
    rows = db.execute(text(f"""
        SELECT ac.chunk_id, c.content, c.document_version_id, ev.section_number,
               ev.page_number, dv.metadata->>'version_role' AS role,
               ac.position_chunk_id, pc.content AS pos_text, pc.standard_code,
               pc.standard_version_id, pc.source_clause,
               ac.statute_chunk_id, sc.content AS stat_text, sc.section_number AS sec,
               st.official_title, st.status AS stat_status, st.file_sha256
          FROM "{s}".answer_citations ac
          LEFT JOIN "{s}".chunks c ON c.id = ac.chunk_id
          LEFT JOIN document_evidence ev ON ev.id = c.evidence_id
          LEFT JOIN document_versions dv ON dv.id = c.document_version_id
          LEFT JOIN "{s}".position_chunks pc ON pc.id = ac.position_chunk_id
          LEFT JOIN "{s}".statute_chunks sc ON sc.id = ac.statute_chunk_id
          LEFT JOIN "{s}".statutes st ON st.id = sc.statute_id
         WHERE ac.answer_id = :a ORDER BY ac.claim_ordinal"""), {"a": answer_id}).all()
    out = []
    for r in rows:
        if r.chunk_id is not None:
            label = authority.of_document(r.role) or "DRAFT_DOCUMENT"
            out.append(Record("D", f"DOC:{r.chunk_id}", r.chunk_id, r.content, label,
                              "executed" if label == "EXECUTED_DOCUMENT" else "draft",
                              r.section_number or (f"p.{r.page_number}" if r.page_number
                                                   else None),
                              str(r.document_version_id)))
        elif r.position_chunk_id is not None:
            out.append(Record("P", f"POS:{r.standard_code}@{r.standard_version_id}",
                              r.position_chunk_id, r.pos_text, "COMPANY_STANDARD",
                              "current", r.source_clause, str(r.standard_version_id)))
        elif r.statute_chunk_id is not None:
            title = r.official_title.removeprefix("The ")
            out.append(Record("S", f"STAT:{title}:{r.sec}", r.statute_chunk_id,
                              r.stat_text, "PRIMARY_LAW", (r.stat_status or "current")
                              .lower(), f"s. {r.sec}", r.file_sha256))
    return out


def _upsert(db: DBSession, conversation_id: UUID, turn_message_id: UUID,
            rec: Record) -> tuple[UUID, str]:
    s, digest = _schema(), text_hash(rec.text)
    found = db.execute(text(f"""
        SELECT id, evidence_key FROM "{s}".conversation_evidence
         WHERE conversation_id = :c AND source_ref = :r AND text_hash = :h"""),
        {"c": conversation_id, "r": rec.source_ref, "h": digest}).first()
    if found is not None:
        return found[0], found[1]
    n = db.execute(text(f"""
        SELECT count(*) FROM "{s}".conversation_evidence
         WHERE conversation_id = :c AND source_class = :k"""),
        {"c": conversation_id, "k": rec.source_class}).scalar_one()
    domain = _DOMAIN[rec.source_class]
    ledger_id, key = uuid4(), f"{rec.source_class}{n + 1}"
    db.execute(text(f"""
        INSERT INTO "{s}".conversation_evidence
            (id, conversation_id, evidence_key, source_class, domain, source_ref,
             {_POINTER[domain]}, authority, status, source_version, location, text_hash,
             fetched_at, turn_message_id)
        VALUES (:i, :c, :k, :cls, :d, :r, :p, :a, :st, :v, :loc, :h, :t, :m)"""),
        {"i": ledger_id, "c": conversation_id, "k": key, "cls": rec.source_class,
         "d": domain, "r": rec.source_ref[:255], "p": rec.pointer,
         "a": rec.authority[:32],
         "st": rec.status[:16], "v": (rec.source_version or None) and
         rec.source_version[:64], "loc": rec.location and rec.location[:128], "h": digest,
         "t": datetime.now(UTC), "m": turn_message_id})
    return ledger_id, key


def refetch(db: DBSession, *, conversation_id: UUID, keys: Iterable[str],
            permissions: frozenset[str], contract_id: UUID | None) -> list[Fetched]:
    """Records by key, read live under the caller's permissions NOW. `contract_id` is
    the conversation's contract as the router has just authorised it, or None."""
    s = _schema()
    rows = {r.evidence_key: r for r in db.execute(text(f"""
        SELECT * FROM "{s}".conversation_evidence
         WHERE conversation_id = :c AND evidence_key = ANY(:k)"""),
        {"c": conversation_id, "k": list(keys)}).all()}
    out = []
    for key in keys:
        row = rows.get(key)
        live = _live(db, row, conversation_id, permissions, contract_id) if row else None
        if row is None or live is None:
            out.append(Fetched(key, UNAVAILABLE))
            continue
        content, superseded = live
        state = STALE if superseded or text_hash(content) != row.text_hash else CURRENT
        out.append(Fetched(key, state, content, row.source_ref, row.authority))
    return out


def _live(db, row, conversation_id, permissions, contract_id) -> tuple[str, bool] | None:
    """(text, superseded) for a visible record, or None."""
    s = _schema()
    if P.ASSIST_ASK not in permissions:
        return None
    if row.domain == "ATTACHMENTS":
        hit = db.execute(text(f"""
            SELECT c.content FROM "{s}".attachment_chunks c
              JOIN "{s}".conversation_attachments a ON a.id = c.attachment_id
             WHERE c.id = :i AND a.conversation_id = :c AND a.status = 'READY'
               AND a.expires_at > now()"""),
            {"i": row.attachment_chunk_id, "c": conversation_id}).first()
        return (hit[0], False) if hit else None
    if row.domain == "DOCUMENTS":
        if contract_id is None:
            return None
        hit = db.execute(text(f"""
            SELECT c.content, EXISTS (SELECT 1 FROM document_versions n
                                       WHERE n.contract_id = dv.contract_id
                                         AND n.version_number > dv.version_number)
              FROM "{s}".chunks c
              JOIN document_versions dv ON dv.id = c.document_version_id
             WHERE c.id = :i AND dv.contract_id = :k"""),
            {"i": row.chunk_id, "k": contract_id}).first()
        return (hit[0], hit[1]) if hit else None
    if row.domain == "STATUTES":
        hit = db.execute(text(f"""
            SELECT c.content, st.status = 'REPEALED' FROM "{s}".statute_chunks c
              JOIN "{s}".statutes st ON st.id = c.statute_id WHERE c.id = :i"""),
            {"i": row.statute_chunk_id}).first()
        return (hit[0], bool(hit[1])) if hit else None
    if not positions.can_read(permissions):       # positions and the Constitution
        return None
    if row.domain == "POSITIONS":
        code = row.source_ref.removeprefix("POS:").split("@")[0]
        hit = db.execute(text(f"""
            SELECT pc.content, (r.status = 'DEPRECATED' OR pc.id IS DISTINCT FROM :i)
              FROM "{s}".position_chunks pc
              JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
              JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
              JOIN requirements r ON r.id = rv.requirement_id
             WHERE pc.id = :i OR (CAST(:i AS uuid) IS NULL AND pc.standard_code = :code)
             ORDER BY pc.ordinal LIMIT 1"""), {"i": row.position_chunk_id, "code": code}
        ).first()
        return (hit[0], bool(hit[1])) if hit else None
    hit = db.execute(text(f"""
        SELECT k.content, (k.status <> 'CURRENT' OR ks.status <> 'CURRENT'
                           OR k.id IS DISTINCT FROM :i)
          FROM "{s}".knowledge_items k JOIN "{s}".knowledge_sources ks
            ON ks.id = k.source_id
         WHERE k.id = :i OR (CAST(:i AS uuid) IS NULL AND k.section_path = :sec
                             AND ks.status = 'CURRENT')
         ORDER BY k.ordinal LIMIT 1"""),
        {"i": row.knowledge_item_id,
         "sec": row.source_ref.removeprefix("CONST:")}).first()
    return (hit[0], bool(hit[1])) if hit else None

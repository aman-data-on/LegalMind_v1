"""The one source-integrity gate on what leaves LegalMind for a client — source
integrity B1, `AM-273`/`AB-150` amendment (owner yes, 2026-11-26).

LegalMind sends no client mail (`AM-273` m3); text leaves by COPY (Ask "Copy email",
"Copy wording", the deal-review copy, the signing note) and by DOWNLOAD (the reply
DOCX/PDF, the final package and final copy, the contract as amended). Every one runs
`source_check` here:

* ``POST /outgoing/check`` — the copy buttons and Ask's paste-to-check box. The browser
  disables the copy on a block; a clipboard gate is a guard, not a control (the text
  can still be selected), so the server records every copy attempt (S5).
* `require_clear` — called by the download routes: a blocked file is refused 409
  SOURCE_CHECK_BLOCKED, server-side (rule 18).

Only a `legal.review` holder may override, with a reason, for ONE item and the exact
problems seen (their digest): an append-only audit row holding the policy versions'
hashes (rule 17). Never `legal.decision` — whether a quote is current is not a Legal
Decision (rule 13).
"""
from __future__ import annotations

import hashlib
import io
import json
from types import SimpleNamespace
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from legalmind import config
from legalmind.api.deps import Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected, SourceCheckBlocked
from legalmind.api.storage import get_storage
from legalmind.assist.knowledge import source_check
from legalmind.db import models as M
from legalmind.ingestion.storage import StorageBackend
from legalmind.security import audit
from legalmind.security import permissions as P

router = APIRouter(tags=["outgoing"])

#: the copy surfaces, and the client ones among them (the leak check, LEGAL-02/S6)
Surface = Literal["copy_email", "copy_wording", "deal_review", "signing_note",
                  "paste_check", "download"]
_CLIENT = {"copy_email", "copy_wording", "paste_check"}
#: internal copies only warn (critique M3 #3): Legal's own memo is not the client's
_WARN_ONLY = {"deal_review"}
#: the versions that leave as a file for the client, by their metadata mark
OUTGOING_MARKS = ("reply_to", "package_of", "final_copy_of", "copy_of")


class OutgoingCheckRequest(BaseModel):
    surface: Surface
    text: str | None = Field(default=None, max_length=60_000)
    conversation_id: UUID | None = None
    keys: list[str] = Field(default_factory=list, max_length=60)
    document_version_id: UUID | None = None
    override_reason: str | None = Field(default=None, max_length=1000)


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def version_text(storage: StorageBackend, version: M.DocumentVersion) -> str:
    """A Word version's text; "" for a PDF (the client's own paper, copied as is)."""
    return docx_text(storage.get(version.storage_key)) \
        if version.mime_type == DOCX_MIME else ""


def docx_text(raw: bytes) -> str:
    """Every paragraph and table row of a DOCX, a line each — what the client reads."""
    import docx

    doc = docx.Document(io.BytesIO(raw))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        lines += [" | ".join(c.text for c in row.cells) for row in table.rows]
    return "\n".join(line for line in lines if line.strip())


def _digest(item: str, problems: list[dict]) -> str:
    body = json.dumps([item, [{k: p.get(k) for k in ("code", "figure", "quote", "key",
                                                      "policy")} for p in problems]],
                      sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def _overridden(guard: Guard, entity_id: UUID, digest: str) -> bool:
    A = M.AuditEvent
    rows = guard.db.execute(select(A.after_state).where(
        A.action == audit.OUTGOING_OVERRIDDEN, A.entity_id == entity_id)).scalars()
    return any((r or {}).get("digest") == digest for r in rows)


def _version_problems(guard: Guard, storage: StorageBackend,
                      version: M.DocumentVersion) -> list[dict]:
    body = version_text(storage, version)
    return source_check.check_text(guard.db, body) if body else []


def is_outgoing(version: M.DocumentVersion) -> bool:
    meta = version.doc_metadata or {}
    return any(meta.get(k) for k in OUTGOING_MARKS)


def require_clear(guard: Guard, storage: StorageBackend,
                  version: M.DocumentVersion) -> None:
    """Refuse (409) a client file whose policy figures or quotes are not the version in
    force, unless Legal overrode exactly these problems on exactly this version."""
    if not is_outgoing(version):
        return
    problems = _version_problems(guard, storage, version)
    if any(p["blocks"] for p in problems) and not _overridden(
            guard, version.id, _digest(str(version.id), problems)):
        raise SourceCheckBlocked(problems)


def sent_record(guard: Guard, storage: StorageBackend,
                version: M.DocumentVersion) -> dict[str, Any]:
    """What went out (S5, decision 4): the policy versions in force and the figures
    checked — so Legal can later list who received a figure. Never the text."""
    versions = source_check.load(guard.db)
    body = version_text(storage, version)
    problems = source_check.check_text(guard.db, body, versions=versions)
    return {"policy_versions": source_check.in_force_hashes(guard.db, versions),
            "figures": source_check.policy_figures(body),
            "source_problems": [p["code"] for p in problems]}


def _cited(guard: Guard, conversation_id: UUID, keys: list[str],
           versions: list[source_check.Version]) -> list[SimpleNamespace]:
    """The answer's cited records as the gate needs them: the key, and a published
    policy's passage status — read from the ledger's own pointer, whatever the copier
    may read (a policy is public text; nothing but the status leaves)."""
    rows = guard.db.execute(text(f"""
        SELECT evidence_key, knowledge_item_id FROM "{config.assist_schema()}".
               conversation_evidence
         WHERE conversation_id = :c AND evidence_key = ANY(:k)"""),
        {"c": conversation_id, "k": keys}).all()
    return [SimpleNamespace(key=r[0], passage=source_check.passage_status(
        guard.db, r[1], versions=versions) if r[1] is not None else None)
        for r in sorted(rows, key=lambda r: keys.index(r[0]))]


@router.post("/outgoing/check")
def check_outgoing(body: OutgoingCheckRequest, guard: Guard = Depends(get_guard),
                   storage: StorageBackend = Depends(get_storage)) -> dict:
    """Check text (or a client file) before it leaves: ``problems`` in order, each with
    ``code``, ``blocks`` and ``message``; ``blocked`` when any blocks and no override.
    With ``override_reason`` a `legal.review` holder passes it, recorded; anyone else
    is refused 403. Every copy attempt is recorded; a paste-to-check is not."""
    db = guard.db
    versions = source_check.load(db)
    item: tuple[str, UUID | None]
    text_: str | None
    if body.document_version_id is not None:
        version = guard.document_version_readable(body.document_version_id,
                                                  P.DOCUMENT_DOWNLOAD)
        if not is_outgoing(version):
            raise BusinessRuleRejected("only a file prepared for the client is checked")
        problems = _version_problems(guard, storage, version)
        item, text_ = ("document_version", version.id), None
    else:
        if body.text is None or not body.text.strip():
            raise BusinessRuleRejected("nothing to check")
        text_ = body.text
        problems = source_check.check_text(db, text_, versions=versions)
        if body.surface in _CLIENT:
            problems += source_check.leak_problems(text_)
        if body.conversation_id is not None and body.keys:
            from legalmind.api.routers.assist import _visible_conversation
            guard.permission(P.ASSIST_ASK)
            conversation = _visible_conversation(guard, body.conversation_id)
            problems = source_check.cited_problems(
                db, _cited(guard, body.conversation_id, body.keys, versions),
                client=body.surface in _CLIENT, versions=versions) + problems
            item = ("conversation", conversation["id"])
        else:
            item = ("outgoing_text", None)
    if body.surface in _WARN_ONLY:
        problems = [{**p, "blocks": False} for p in problems]
    blocking = any(p["blocks"] for p in problems)
    digest = _digest(str(item[1] or hashlib.sha256((text_ or "").encode()).hexdigest()),
                     problems)
    record = {"surface": body.surface, "digest": digest,
              "policy_versions": source_check.in_force_hashes(db, versions),
              "problems": [p["code"] for p in problems], "blocked": blocking,
              "text_sha256": hashlib.sha256((text_ or "").encode()).hexdigest()
              if text_ is not None else None}
    overridden = False
    if body.override_reason is not None:
        reason = body.override_reason.strip()
        if not reason:
            raise BusinessRuleRejected("an override needs a reason")
        guard.permission(P.LEGAL_REVIEW)
        audit.record(db, action=audit.OUTGOING_OVERRIDDEN, entity_type=item[0],
                     entity_id=item[1], actor_id=guard.user_id,
                     request_id=guard.request_id, after={**record, "reason": reason})
        overridden = blocking
    elif body.surface != "paste_check":
        audit.record(db, action=audit.OUTGOING_CHECKED, entity_type=item[0],
                     entity_id=item[1], actor_id=guard.user_id,
                     request_id=guard.request_id, after=record)
    return data({"problems": problems, "blocked": blocking and not overridden,
                 "overridden": overridden,
                 "can_override": P.LEGAL_REVIEW in guard.permissions})

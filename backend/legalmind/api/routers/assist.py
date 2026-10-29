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

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select, text
from starlette.concurrency import run_in_threadpool

from legalmind import config
from legalmind.api import ratelimit, temporary_review
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data, paginated
from legalmind.api.errors import BusinessRuleRejected, ModelNotConfigured
from legalmind.api.pagination import Page, page_params
from legalmind.api.schemas import (
    AskRequest,
    ConversationCreate,
    ConversationUpdate,
    FeedbackRequest,
)
from legalmind.assist import feedback, service
from legalmind.assist.agent import attachments, ledger, model_router
from legalmind.assist.ingestion.chunking import leading_section_ref
from legalmind.assist.llm import breaker
from legalmind.assist.query import routing
from legalmind.assist.synthesis import explanations, obligations, type_suggestion
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.observability.logs import log_event
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract
from legalmind.security.errors import NotVisible

router = APIRouter(tags=["assist"], route_class=CommitBeforeResponse)

# In-process for a single worker; Redis-backed when LEGALMIND_RATELIMIT_BACKEND=redis
# (see ratelimit.limiter_from_env).
_limiter: ratelimit.RateLimiter = ratelimit.limiter_from_env()


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


def _asked_document_version(guard: Guard, contract_id: UUID,
                            requested: str | None) -> M.DocumentVersion:
    """The version a question is about: the one the caller names, else the newest.

    Why this exists (2026-09-02). Before it, the ask endpoint ALWAYS resolved the
    newest version of the conversation's contract. A reader with version 1 open
    therefore could not ask about what was on their screen — the answer, and the
    `evidence_id` in every citation, would have come from a different version's
    reading order, so the workspace's highlight gesture would point at a row that
    does not exist on the open page. The UI's only honest move was to disable the
    input and say "open the latest version", which is what the owner reported.

    The scope can only NARROW here, never widen. Two independent checks:
    `guard.document_version` runs the full 47.6 chain (visibility of the owning
    contract, then the permission), and the version is then required to belong to
    THIS conversation's contract — so a valid id from another contract the caller
    happens to be able to read is still refused rather than answered.

    Omitting the field keeps the previous behaviour exactly, which is what makes
    this an additive API change.
    """
    if requested is None:
        return _latest_document_version(guard, contract_id)
    try:
        version_id = UUID(requested)
    except ValueError as exc:
        raise BusinessRuleRejected(
            "document_version_id is not a valid identifier") from exc
    version = guard.document_version_readable(version_id, P.ASSIST_ASK)
    if version.contract_id != contract_id:
        # Not a 404: the caller can see this version, it simply is not part of the
        # conversation they are asking in. Answering across contracts would let one
        # conversation mix two documents' evidence, which is what AM-25 r6's
        # single-scope retrieval exists to prevent.
        raise BusinessRuleRejected(
            "the document version does not belong to this conversation's contract")
    return version


def _visible_conversation(guard: Guard, conversation_id: UUID) -> dict:
    """Ownership check with the byte-identical-404 discipline.

    A conversation is visible to its creator only. `NotVisible` — not Forbidden —
    for anyone else, so existence never leaks (`AM-25` r7, `API-10`).
    """
    schema = config.assist_schema()
    row = guard.db.execute(text(f"""
        SELECT id, user_id, contract_id, created_at, model, title
          FROM "{schema}".conversations WHERE id = :i
    """), {"i": conversation_id}).first()
    if row is None or row[1] != guard.user_id:
        raise NotVisible("conversation", conversation_id)
    return {"id": row[0], "user_id": row[1], "contract_id": row[2],
            "created_at": row[3], "model": row[4], "title": row[5]}


def _model(model_id: str | None) -> model_router.Model:
    """The reader's model from the server's own registry (`AM-116`): an unknown id is
    refused, a listed one that is not configured is refused BY NAME — the question is
    never answered by a different model than the one the reader picked."""
    try:
        return model_router.resolve(model_id)
    except model_router.UnknownModel as exc:
        raise BusinessRuleRejected("unknown model") from exc
    except model_router.ModelNotConfigured as exc:
        raise ModelNotConfigured(
            f"{exc} is not configured yet. Choose Gemini to ask this question.") from exc


@router.get("/ask/models")
def ask_models(guard: Guard = Depends(get_guard)) -> dict:
    """The composer's model list, each marked configured or not — so the screen never
    offers a model as working when the server would refuse it. ``paused`` (`AM-222`):
    the provider stopped serving us (credit or quota) and nothing has succeeded since;
    only a platform administrator is told why and since when."""
    guard.permission(P.ASSIST_ASK)
    paused = breaker.paused()
    admin = P.PLATFORM_MANAGE in guard.permissions
    order = list(model_router.MODELS.values())

    def stopped(m: model_router.Model) -> bool:
        """Paused, and no later model answers in its place (failover runs forward only,
        and only while `LEGALMIND_ASK_FAILOVER` is on, `AM-124`)."""
        later = order[order.index(m) + 1:]
        return m.label in paused and not (config.ask_failover() and any(
            n.id != model_router.DEFAULT and model_router.configured(n)
            and n.label not in paused for n in later))

    def row(m: model_router.Model) -> dict:
        out = {"id": m.id, "label": m.label, "default": m.id == model_router.DEFAULT,
               "configured": model_router.configured(m), "paused": stopped(m)}
        if admin and out["paused"]:
            kind, since = paused[m.label]
            out["paused_reason"] = {"kind": kind, "since": datetime.fromtimestamp(
                since, UTC).isoformat()}
        return out
    return data([row(m) for m in model_router.MODELS.values()])


@router.post("/document-versions/{document_version_id}/suggest-type")
def suggest_type(document_version_id: UUID,
                 guard: Guard = Depends(get_guard)) -> dict:
    """Assist-lane type suggestion (owner, 2026-08-31) — a proposal, never a write.

    The Guard resolves the version through its contract (47.6), the assist lane
    reads the opening evidence, and the response is only ever advice for the UI's
    pre-fill. The type itself is recorded exclusively by the human's own
    `PATCH /contracts/{id}` — Q9's substance (human-declared) survives intact.
    Every failure shape is the same honest `confident: false`, so the screen
    degrades to the plain empty select rather than erroring.
    """
    guard.permission(P.ASSIST_ASK)
    guard.document_version(document_version_id, P.ASSIST_ASK)
    _limiter.check(f"suggest_type:{guard.user_id}", ratelimit.SUGGEST_TYPE)
    suggestion = type_suggestion.suggest_document_type(
        guard.db, document_version_id=document_version_id,
        request_id=guard.request_id)
    return data({
        "suggested_type": suggestion.suggested_type,
        "confident": suggestion.confident,
        "reason": suggestion.reason,
    })


@router.post("/document-versions/{document_version_id}/extract-obligations")
def extract_obligations(document_version_id: UUID,
                        guard: Guard = Depends(get_guard)) -> dict:
    """Key Obligations extraction (owner, 2026-08-31) — descriptive facts about
    the document's own text, never a Finding or a judgment. Runs synchronously
    (the Ask precedent: one bounded generation call); idempotent-by-refusal —
    a version already extracted keeps its record, since the version is
    immutable and re-running buys nothing.

    Permission is `finding.view`: obligations are facts about text the caller
    can already read in full, not the organization's negotiating position, so
    LEGAL-02's stricter gate does not apply.
    """
    # Owner scope: the extraction writes a record that blocks re-reading the
    # version (`documents._reprocess_blockers`), so it is a write (AB-12).
    guard.document_version(document_version_id, P.FINDING_VIEW)
    _limiter.check(f"obligations:{guard.user_id}", ratelimit.SUGGEST_TYPE)
    result = obligations.extract_obligations(
        guard.db, document_version_id=document_version_id,
        request_id=guard.request_id)
    return data({"extracted": result.extracted,
                 "error_code": result.error_code})


@router.post("/findings/{finding_id}/explain")
def explain_finding(finding_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The grounded plain-English sentence under a Finding's status (owner,
    2026-09-09; `AM-49`). Language only: the deterministic result is read, never
    written. Cached against the Finding and a hash of its approved sources, so
    the wording is stable until a source changes; a rejected or unavailable
    generation returns FALLBACK/FAILED and the card shows the approved
    description instead.

    Permission is `finding.view` (the `AM-35` t5 reasoning): the sentence is
    built only from material the caller already sees — the requirement's
    approved description and the cited passages — never from a Company
    Standard value or a Rule Outcome, so LEGAL-02's stricter gate does not
    apply and the reply is identical for every caller who can see the Finding.
    """
    finding = guard.finding(finding_id, P.FINDING_VIEW)
    result = explanations.explain(
        guard.db, finding, request_id=guard.request_id,
        before_generation=lambda: _limiter.check(f"explain:{guard.user_id}",
                                                 ratelimit.EXPLAIN))
    return data({"status": result.status, "text": result.text,
                 "reason": result.reason, "prompt_version": result.prompt_version,
                 "passages": result.passages, "cached": result.cached})


@router.get("/document-versions/{document_version_id}/obligations")
def read_obligations(document_version_id: UUID,
                     guard: Guard = Depends(get_guard)) -> dict:
    guard.document_version_readable(document_version_id, P.FINDING_VIEW)
    return data(obligations.read_obligations(guard.db, document_version_id))


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationCreate,
                        guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.ASSIST_ASK)
    contract_id = None
    if body.contract_id is not None:
        # Visibility before anything else: asking about a contract requires being
        # able to READ it — owner or department scope (AB-12 r3). The
        # conversation itself belongs to the asker alone (r8).
        contract = guard.contract_readable(UUID(body.contract_id), P.ASSIST_ASK)
        contract_id = contract.id
    # The chat's model (`AM-122`): validated now, so a chat is never opened on a
    # model the server would refuse at the first question.
    model = _model(body.model).id if body.model is not None else None
    conversation_id = service.create_conversation(
        guard.db, user_id=guard.user_id, contract_id=contract_id, model=model)
    return data({"id": str(conversation_id),
                 "contract_id": str(contract_id) if contract_id else None,
                 "model": model})


def _chat_title(questions: list[str] | None) -> str | None:
    """The first question that is one — a chat opened with "hi" was titled "hi" in
    Recent chats for ever (`AM-109`). A chat that is only social keeps its first. The
    placeholder a pasted text leaves is no question: a chat that is only pasted text is
    "Pasted text", never "[Pasted text saved as an attachment]". A pasted email is named
    by its first sentence, never all of it (2026-10-13)."""
    from legalmind.assist.query import conversational
    given = [q for q in (questions or []) if (q or "").strip()]
    questions = [q for q in given
                 if q not in (attachments.MATERIAL_TURN, attachments.PASTE_REQUEST)]
    real = next((q for q in questions if conversational.kind(q) is None), None)
    title = (conversational.strip_social(real) if real else questions[0] if questions
             else "Pasted text" if given else None)
    if not title:
        return None
    first = re.split(r"(?<=[.?!])\s|\n", title.strip())[0]
    # "Clause 9." is a number's full stop, not a sentence (2026-10-13): a first
    # "sentence" of under three words gives way to the opening of the text itself.
    return (first if len(first.split()) >= 3 else title.strip())[:80]


@router.get("/conversations")
def list_conversations(guard: Guard = Depends(get_guard),
                       page: Page = Depends(page_params),
                       contract_id: UUID | None = Query(None),
                       has_document: bool | None = Query(None),
                       q: str | None = Query(None, max_length=200)) -> dict:
    """The caller's own conversations, newest first — 49.6 r4 applied to the assist
    lane: the list carries exactly what `GET /conversations/{id}` would return and
    nothing a GET would 404 on, so it cannot become the enumeration oracle `AM-25`
    r7 forbids. Two allow-listed filters (49.6 r3, extended by `AM-135` r2):
    `contract_id`, so a document's workspace shows that document's history and no
    other, and `has_document`, so the Ask page lists its own chats — those about no
    contract — while a chat about a contract is listed with it."""
    guard.permission(P.ASSIST_ASK)
    schema = config.assist_schema()
    clauses = ["user_id = :u"]
    params: dict[str, object] = {"u": guard.user_id}
    if contract_id:
        clauses.append("contract_id = :k")
        params["k"] = contract_id
    if has_document is not None:
        clauses.append(f"contract_id IS {'NOT ' if has_document else ''}NULL")
    if q and q.strip():
        # Search over EVERY chat of the caller's, not the page in hand (`AM-226` r8): the
        # name or any question, case-insensitive, the term taken literally. Still the
        # caller's own rows only — a third allow-listed filter, never an oracle.
        # Unqualified, as the clauses above are: the count and the page both use them.
        clauses.append(f"""(title ILIKE :q ESCAPE '\\' OR id IN (
            SELECT m.conversation_id FROM "{schema}".messages m
             WHERE m.role = 'USER' AND m.content ILIKE :q ESCAPE '\\'))""")
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{term}%"
    where = " AND ".join(clauses)
    total = guard.db.execute(text(
        f'SELECT count(*) FROM "{schema}".conversations WHERE {where}'
    ), params).scalar_one()
    rows = guard.db.execute(text(f"""
        SELECT c.id, c.contract_id, c.created_at,
               (SELECT count(*) FROM "{schema}".messages m
                 WHERE m.conversation_id = c.id) AS turns,
               (SELECT array_agg(f.content ORDER BY f.ordinal) FROM (
                    SELECT m.content, m.ordinal FROM "{schema}".messages m
                     WHERE m.conversation_id = c.id AND m.role = 'USER'
                     ORDER BY m.ordinal LIMIT 10) f) AS first_questions,
               c.title, c.model
          FROM "{schema}".conversations c
         WHERE {where}
         ORDER BY c.created_at DESC, c.id DESC
         LIMIT :lim OFFSET :off
    """), {**params, "lim": page.page_size, "off": page.offset}).all()
    # The document's NAME, served with the conversation (2026-09-04). Ask History
    # used to fetch `GET /contracts/{id}` once per row to label it, and that
    # endpoint is ownership-scoped and refuses a soft-deleted contract — so a row
    # about a document since deleted rendered a raw UUID prefix ("b91052d6"),
    # which is what the live audit found. The same one-query fix already applied
    # to `GET /reviews`; a conversation is the caller's own by construction
    # (`AM-25` r7), so naming the document it belongs to discloses nothing new.
    contract_ids = {r[1] for r in rows if r[1]}
    names = {} if not contract_ids else {
        c.id: c for c in guard.db.execute(
            select(M.Contract).where(M.Contract.id.in_(contract_ids))
        ).scalars().all()
    }
    return paginated([{
        "id": str(r[0]),
        "contract_id": str(r[1]) if r[1] else None,
        "created_at": r[2].isoformat() if r[2] else None,
        "message_count": r[3],
        "first_question": _chat_title(r[4]),
        # The reader's own name for the chat (`AM-116`); null until renamed.
        "title": r[5],
        # The chat's own model (`AM-122`); null until one is chosen.
        "model": r[6],
        "document_name": (names[r[1]].name if r[1] and r[1] in names else None),
        # Whether the workspace this row links to will open for THIS caller —
        # the same READ rule the workspace itself applies (`can_read_contract`).
        "document_accessible": bool(
            r[1] and r[1] in names
            and can_read_contract(guard.db, guard.user_id, names[r[1]])),
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
    # Each assistant turn also reports WHICH document version it was answered
    # from. A conversation is contract-scoped (AM-27: "an assist-lane session"),
    # so a contract that gains a revised version can hold turns answered from
    # more than one — and a replayed citation's `evidence_id` belongs to exactly
    # one version's reading order. Stating the version per turn is what lets the
    # workspace refuse to point at a row that is not on the open page, instead of
    # highlighting nothing and announcing that it did.
    #
    # Preferred source is the retrieval run's `filters` (written since
    # 2026-09-02). Rows written before that fall back to the version of the first
    # chunk the run actually hit — the same fact, recovered rather than guessed.
    turns = guard.db.execute(text(f"""
        SELECT m.id, m.ordinal, m.role, m.content, a.answer_state, a.id,
               v.id AS document_version_id, v.version_number,
               a.model_identity, a.latency_ms
          FROM "{schema}".messages m
          LEFT JOIN "{schema}".ai_answers a ON a.message_id = m.id
          LEFT JOIN "{schema}".retrieval_runs r ON r.id = a.retrieval_run_id
          LEFT JOIN document_versions v
                 ON v.id = COALESCE(
                      (r.filters->>'document_version_id')::uuid,
                      (SELECT ch.document_version_id FROM "{schema}".chunks ch
                        WHERE ch.id::text = (r.results->'hits'->0->>'chunk_id')))
         WHERE m.conversation_id = :c
         ORDER BY m.ordinal
    """), {"c": conversation_id}).all()

    # Authorization is re-checked HERE, not inherited from the turn that was
    # answered (P1, 2026-09-11; merged in Phase 0, 2026-09-17). A conversation is
    # creator-only, but owning the conversation is not the same right as reading
    # what it quoted: the grant that disclosed a Company Position, and the scope
    # that disclosed a clause, can both be withdrawn afterwards — by an
    # administrator removing `legal_position.view`, or by `contract.transfer`
    # moving the deal away. Measured before fixing: a caller whose position grant
    # had been revoked still received `standard_code`, `source_clause` and the
    # verbatim position text on reload, which is exactly the disclosure
    # `LEGAL-02` forbids. The live ask path already re-resolves permissions per
    # request (S-1) and checks `positions_permitted` twice; replay now applies
    # the same two tests. Withheld material is OMITTED, never nulled or emptied
    # in place (`SEC-07`, `API-10`), so a withheld citation is indistinguishable
    # from a turn that never had one. `AM-25` r5's traceability is preserved for
    # every caller who may still read the source — it was never a licence to
    # disclose past it.
    positions_readable = routing.positions_permitted(guard.permissions)
    contract_row = (guard.db.get(M.Contract, conversation["contract_id"])
                    if conversation["contract_id"] else None)
    document_readable = contract_row is not None and can_read_contract(
        guard.db, guard.user_id, contract_row)

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
    """), {"c": conversation_id}).all() if document_readable else []
    positioned = guard.db.execute(text(f"""
        SELECT ac.answer_id, pc.id, pc.standard_code, pc.document_type,
               pc.source_clause, pc.content, csv.version_number, r.status::text
          FROM "{schema}".answer_citations ac
          JOIN "{schema}".ai_answers a ON a.id = ac.answer_id
          JOIN "{schema}".messages m ON m.id = a.message_id
          JOIN "{schema}".position_chunks pc ON pc.id = ac.position_chunk_id
          JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
          JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
          JOIN requirements r ON r.id = rv.requirement_id
         WHERE m.conversation_id = :c
         ORDER BY ac.claim_ordinal
    """), {"c": conversation_id}).all() if positions_readable else []
    statuted = guard.db.execute(text(f"""
        SELECT ac.answer_id, sc.id, s.official_title, sc.section_number, sc.sub_section,
               sc.marginal_note, sc.content
          FROM "{schema}".answer_citations ac
          JOIN "{schema}".ai_answers a ON a.id = ac.answer_id
          JOIN "{schema}".messages m ON m.id = a.message_id
          JOIN "{schema}".statute_chunks sc ON sc.id = ac.statute_chunk_id
          JOIN "{schema}".statutes s ON s.id = sc.statute_id
         WHERE m.conversation_id = :c
         ORDER BY ac.claim_ordinal
    """), {"c": conversation_id}).all()
    statutes_by_answer: dict = {}
    for row in statuted:
        sub = f" {row[4]}" if row[4] else ""
        statutes_by_answer.setdefault(row[0], []).append({
            "statute_chunk_id": str(row[1]), "citation": f"{row[2]}, s. {row[3]}{sub}",
            "official_title": row[2], "section_number": row[3], "sub_section": row[4],
            "marginal_note": row[5], "excerpt": row[6][:240], "retrieval_score": None})
    positions_by_answer: dict = {}
    for row in positioned:
        positions_by_answer.setdefault(row[0], []).append({
            "position_chunk_id": str(row[1]), "standard_code": row[2],
            "document_type": row[3], "source_clause": row[4], "content": row[5],
            "standard_version": row[6], "ratification_status": row[7],
            # ponytail: `retrieval_score` stays None on replay for positions and
            # statutes while document scores are recovered from the run's JSONB.
            # Deliberate, not an oversight: `_persist_retrieval` records `hits` and
            # `statute_hits` but no `position_hits`, so the number was never written
            # and cannot be recovered — and the score is NEVER RENDERED (rule 12;
            # `ask-pane.test.tsx` asserts "retrieval score" and "confidence" appear
            # nowhere). Adding a JSONB key and a recovery join for a value no reader
            # sees is cost without a reader. Upgrade path if an audit ever needs it:
            # add `position_hits: [{position_chunk_id, score}]` in `_persist_retrieval`
            # and mirror the document subquery here.
            "retrieval_score": None})
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
    # The structured Sources list on replay: each answer's ledger keys in citation
    # order, every record re-read NOW under the caller's permissions (`AM-111` r3) —
    # the ledger holds no text (`AM-110` r4); an unreadable one is left out (SEC-07).
    keyed = guard.db.execute(text(f"""
        SELECT ae.answer_id, ce.evidence_key, min(ae.claim_ordinal) AS o
          FROM "{schema}".answer_evidence ae
          JOIN "{schema}".conversation_evidence ce ON ce.id = ae.ledger_id
         WHERE ce.conversation_id = :c
         GROUP BY ae.answer_id, ce.evidence_key ORDER BY ae.answer_id, o
    """), {"c": conversation_id}).all()
    fetched = {f.key: f for f in ledger.refetch(
        guard.db, conversation_id=conversation_id,
        keys=list(dict.fromkeys(k for _, k, _ in keyed)), permissions=guard.permissions,
        contract_id=conversation["contract_id"] if document_readable else None)
        if f.state != ledger.UNAVAILABLE} if keyed else {}
    sources_by_answer: dict = {}
    for answer_id, key, _ in keyed:
        if key in fetched:
            f = fetched[key]
            sources_by_answer.setdefault(answer_id, []).append(
                (key, f.text, f.location, f.source_ref, None, f.state))

    # `AM-149` on replay: a routed turn's quoted clause, recomputed from the question
    # before it against the contract's newest version (the one the pane opens on) —
    # only for a reader of the document; otherwise omitted, never emptied (SEC-07).
    topics: dict = {}
    asked = ""
    for t in turns:
        if t[2] == "USER":
            asked = t[3]
        else:
            topics[t[0]] = service.topic_requirements(asked)
    clauses: dict = {}
    if document_readable:
        newest = guard.db.execute(select(M.DocumentVersion.id).where(
            M.DocumentVersion.contract_id == conversation["contract_id"]).order_by(
            M.DocumentVersion.version_number.desc()).limit(1)).scalar()
        asked = ""
        for t in turns:
            if t[2] == "USER":
                asked = t[3]
            elif t[3] == service.EVALUATOR_ROUTE_TEXT and (
                    found := service.quoted_clause(guard.db, newest, asked)):
                clauses[t[0]] = found

    # The files each question was sent with (`AM-226` r7), linked when it was saved.
    sent_with: dict = {}
    linked: dict = {row[0]: row[1] for row in guard.db.execute(text(
        f'SELECT id, message_id FROM "{schema}".conversation_attachments '
        "WHERE conversation_id = :c AND message_id IS NOT NULL"),
        {"c": conversation_id})}
    for a in attachments.list_for(guard.db, conversation_id):
        if a.id in linked:
            sent_with.setdefault(linked[a.id], []).append(_attachment_view(a))

    return data({
        "id": str(conversation_id),
        "contract_id": (str(conversation["contract_id"])
                        if conversation["contract_id"] else None),
        # The chat's own model (`AM-122`): what the composer shows on reopening.
        "model": conversation["model"],
        "messages": [{
            "id": str(t[0]), "ordinal": t[1], "role": t[2], "content": t[3],
            "answer_state": t[4],
            **({"attachments": sent_with[t[0]]} if sent_with.get(t[0]) else {}),
            "routed_to_evaluator": (t[2] == "ASSISTANT" and t[3] in service.ROUTED_TEXTS),
            **({"clause": clauses[t[0]]} if t[0] in clauses else {}),
            "topic_requirements": topics.get(t[0], []),
            "positions": positions_by_answer.get(t[5], []),
            # `AM-76` r2/r4 on replay, by the same means as `routed_to_evaluator`
            # above: the three fallback sentences are the ones that POINT AT the
            # quote instead of being an answer, so the transcript opens it too. A
            # paraphrase is free text and can never collide with a constant.
            "quote_is_the_answer": t[2] == "ASSISTANT" and t[3] in (
                service.POSITIONS_ONLY_TEXT, service.POSITIONS_BESIDE_TEXT,
                service.POSITIONS_EXACT_TEXT),
            # Replayed statute citations; the generated statute text is the turn's
            # content when the statute corpus was the answering source.
            "statutes": ({"answer_state": t[4], "text": None,
                          "citations": statutes_by_answer[t[5]]}
                         if t[5] in statutes_by_answer else None),
            # None for a user turn, and for an assistant turn that never
            # retrieved (a compliance-shaped question routed to the evaluator).
            "document_version_id": str(t[6]) if t[6] else None,
            "version_number": t[7],
            "citations": by_answer.get(t[5], []),
            "sources": service.source_views(guard.db, sources_by_answer.get(t[5], [])),
            "answered_by": model_router.answered_by(t[8]),
            "latency_ms": t[9],
        } for t in turns],
    })


def _attachment_view(a: attachments.Attachment) -> dict:
    """Ids, type, size and status only — the name is the reader's own and is shown to
    them; content never leaves through this view."""
    return {"id": str(a.id), "kind": a.kind, "filename": a.filename,
            "mime_type": a.mime_type, "byte_size": a.byte_size,
            "status": ("UNAVAILABLE" if a.status == attachments.EXPIRED else a.status),
            "failure_code": a.failure_code, "pages_unread": a.pages_unread,
            "created_at": a.created_at.isoformat(),
            "expires_at": a.expires_at.isoformat()}


def extract_material(data: bytes, kind: str, filename: str | None,
                     declared_mime: str) -> tuple[str, list | str]:
    """(mime, segments or a failure code) with the upload path's own validation and
    parsers — magic-byte sniffing included (34.16). Here, not in the assist lane,
    because ingestion is the API's dependency and not assist's."""
    from legalmind.ingestion import parsing, validation
    attachments.check_size(data, kind)
    if kind == attachments.PASTE:
        mime = validation.TEXT_MIME
    else:
        try:
            mime = validation.validate_upload(data, filename or "",
                                              declared_mime).mime_type
        except validation.UploadRejected as exc:
            raise attachments.AttachmentRejected(exc.code) from None
    try:
        # Never Docling: a chat file is read while the reader waits (10-30 s a file).
        parsed = parsing.parse(data, mime, defer_ocr=True, docling=False)
        if parsed.needs_ocr:
            # F7: one scanned page used to fail the whole file, every native page lost.
            # A short file is OCR'd here; a longer one keeps its native pages and its
            # scanned ones are reported unread (critic #26) — never the whole file lost.
            inline = parsed.pages_total <= attachments.ATTACHMENT_OCR_MAX_PAGES
            parsed = (_ocr_within_bound(parsing, data, mime) if inline
                      else parsing.parse(data, mime, ocr=False, docling=False))
            if not inline and not parsed.segments:
                return mime, "OCR_REQUIRED"     # a long scan: nothing here to keep
    except parsing.ParseError:
        return mime, "EXTRACTION_FAILED"
    if parsed.status is E.ExtractionStatus.COMPLETE:
        return mime, parsed.segments
    return mime, attachments.PartialText(parsed.segments, parsed.pages_failed,
                                         parsed.diagnostics)


def _ocr_within_bound(parsing, data: bytes, mime: str):
    """The inline OCR read, cut off at ATTACHMENT_OCR_MAX_SECONDS: past it the text layer
    alone is read and the scanned pages are reported unread, so the request answers
    inside nginx's 300 s. ponytail: the abandoned read finishes in its own thread
    (tesseract's per-page timeout bounds it); move OCR to the worker if that bites."""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as Timeout
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(parsing.parse, data, mime, docling=False).result(
            timeout=attachments.ATTACHMENT_OCR_MAX_SECONDS)
    except Timeout:
        return parsing.parse(data, mime, ocr=False, docling=False)
    finally:
        pool.shutdown(wait=False)


def _add_material(guard: Guard, conversation_id: UUID, payload: bytes, kind: str,
                  filename: str | None = None, mime: str = "text/plain"):
    try:
        if (same := attachments.already_attached(guard.db, conversation_id, payload,
                                                 kind)) is not None:
            return same           # the same bytes again: never parsed or OCR'd twice
        mime, extracted = extract_material(payload, kind, filename, mime)
        return attachments.add(guard.db, conversation_id=conversation_id, data=payload,
                               kind=kind, mime=mime, extracted=extracted,
                               filename=filename)
    except attachments.AttachmentRejected as exc:
        raise BusinessRuleRejected(f"the attachment was refused: {exc.code}") from exc


def _attachments_on() -> None:
    if not config.ask_attachments_enabled():
        raise BusinessRuleRejected("chat attachments are not enabled")


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: UUID, body: ConversationUpdate,
                        guard: Guard = Depends(get_guard)) -> dict:
    """The reader's own name for a chat (`AM-116`) and its model (`AM-122`). The
    creator only — anyone else gets the byte-identical 404 (`_visible_conversation`).
    A model is stored only once the registry accepts it, so a chat can never be left
    pointing at a model the server would refuse — and never silently at another."""
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    changes = {}
    if body.title is not None:
        changes["title"] = body.title
    if body.model is not None:
        changes["model"] = _model(body.model).id
    guard.db.execute(text(
        f'UPDATE "{config.assist_schema()}".conversations SET '
        + ", ".join(f"{k} = :{k}" for k in changes) + " WHERE id = :i"),
        {**changes, "i": conversation_id})
    return data({"id": str(conversation_id),
                 "title": changes.get("title", conversation["title"]),
                 "model": changes.get("model", conversation["model"])})


@router.post("/feedback", status_code=201)
def record_feedback(body: FeedbackRequest, guard: Guard = Depends(get_guard)) -> dict:
    """The reader's signal on one of their own answers (`AM-123`) — evaluation data,
    never a tuning input (`AM-26`). An unknown id, a user turn and someone else's
    answer are the same byte-identical 404 (SEC-07, `API-10`); only the id returns."""
    guard.permission(P.ASSIST_ASK)
    _limiter.check(f"feedback:{guard.user_id}", ratelimit.ASK)
    conversation_id = feedback.answer_conversation(guard.db, body.message_id)
    try:
        if conversation_id is None:
            raise NotVisible("message", body.message_id)
        _visible_conversation(guard, conversation_id)
    except NotVisible:
        raise NotVisible("message", body.message_id) from None
    return data({"id": str(feedback.record(
        guard.db, message_id=body.message_id, user_id=guard.user_id, kind=body.kind,
        rating=body.rating, reason=body.reason, request_id=guard.request_id))})


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID,
                        guard: Guard = Depends(get_guard)) -> None:
    """Delete a chat permanently (`AM-116`). The creator only — anyone else gets the
    byte-identical 404, so a guessed id neither deletes nor confirms a chat.

    One row goes and its turns, answers, citations, ledger and material follow by the
    schema's own cascades; chat material keeps no raw bytes (A-15), so nothing is left
    in storage. The audit trail is untouched (rule 17): the egress rows already written
    stay, and this deletion is recorded with counts only — no title, no question."""
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    schema = config.assist_schema()
    turns = guard.db.execute(text(
        f'SELECT count(*) FROM "{schema}".messages WHERE conversation_id = :i'),
        {"i": conversation_id}).scalar_one()
    guard.db.execute(text(f'DELETE FROM "{schema}".conversations WHERE id = :i'),
                     {"i": conversation_id})
    audit.record(guard.db, action=audit.ASSIST_CONVERSATION_DELETED,
                 entity_type="conversation", entity_id=conversation_id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 before={"contract_id": str(conversation["contract_id"])
                         if conversation["contract_id"] else None,
                         "message_count": turns},
                 after=None)


@router.post("/conversations/{conversation_id}/attachments", status_code=201)
async def add_attachment(conversation_id: UUID, request: Request,
                         x_filename: str = Header(..., max_length=400),
                         guard: Guard = Depends(get_guard)) -> dict:
    """A file for THIS conversation only (plan 1.2, A4-1): `assist.ask` plus ownership,
    never a Contract, never on the Dashboard. The upload endpoint's shape — raw body,
    type in Content-Type, name in X-Filename — and its validation, sniffing included."""
    _attachments_on()
    # Database work off the event loop — see `upload_document_version` (2026-10-13).
    await run_in_threadpool(guard.permission, P.ASSIST_ASK)
    await run_in_threadpool(_visible_conversation, guard, conversation_id)
    # a file may now be OCR'd inline (F7): uploads share the Ask budget (2026-10-16)
    await run_in_threadpool(_limiter.check, f"attach:{guard.user_id}", ratelimit.ASK)
    limit = config.ask_attachment_limits()["max_bytes"]
    declared = request.headers.get("content-length")
    if declared is not None and int(declared) > limit:
        raise BusinessRuleRejected("the attachment was refused: FILE_TOO_LARGE")
    payload = await request.body()
    if not payload:
        raise BusinessRuleRejected("the request body is empty")
    from legalmind.api.routers.contracts import _decode_percent_encoded_filename
    return data(_attachment_view(await run_in_threadpool(
        _add_material, guard, conversation_id, payload, attachments.FILE,
        filename=_decode_percent_encoded_filename(x_filename),
        mime=request.headers.get("content-type", ""))))


@router.get("/conversations/{conversation_id}/attachments")
def list_attachments(conversation_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    _attachments_on()
    guard.permission(P.ASSIST_ASK)
    _visible_conversation(guard, conversation_id)
    return data([_attachment_view(a) for a in attachments.list_for(guard.db,
                                                                    conversation_id)])


def _replace_from(guard: Guard, conversation_id: UUID, edit_of: str) -> None:
    """Edit (`AM-134` r3): the reader's own question, and every turn after it, go — their
    answers, citations, evidence and feedback by the schema's cascades — so the edited
    question is asked in its place. Only a USER turn of THIS chat, which is the caller's
    own (`_visible_conversation`); anything else is the same 404 as a wrong chat. The
    egress audit already written stays (rule 17); this is recorded with counts only."""
    schema = config.assist_schema()
    try:
        message_id = UUID(edit_of)
    except ValueError:
        raise NotVisible("conversation", conversation_id) from None
    ordinal = guard.db.execute(text(
        f'SELECT ordinal FROM "{schema}".messages WHERE id = :m '
        "AND conversation_id = :c AND role = 'USER'"),
        {"m": message_id, "c": conversation_id}).scalar_one_or_none()
    if ordinal is None:
        raise NotVisible("conversation", conversation_id)
    where = 'WHERE conversation_id = :c AND ordinal >= :o'
    bounds = {"c": conversation_id, "o": ordinal}
    removed = guard.db.execute(text(
        f'SELECT count(*) FROM "{schema}".messages {where}'), bounds).scalar_one()
    guard.db.execute(text(f'DELETE FROM "{schema}".messages {where}'), bounds)
    audit.record(guard.db, action=audit.ASSIST_TURNS_REPLACED, entity_type="conversation",
                 entity_id=conversation_id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 before={"from_ordinal": ordinal, "message_count": removed}, after=None)


def _question_of(guard: Guard, answer_id: UUID) -> str | None:
    """The USER turn an answer follows — the question a reader may edit."""
    schema = config.assist_schema()
    found = guard.db.execute(text(
        f'SELECT q.id FROM "{schema}".messages q JOIN "{schema}".messages a '
        "ON a.conversation_id = q.conversation_id AND q.ordinal < a.ordinal "
        "WHERE a.id = :a AND q.role = 'USER' ORDER BY q.ordinal DESC LIMIT 1"),
        {"a": answer_id}).scalar_one_or_none()
    return str(found) if found else None


def _temporary_review(guard: Guard, conversation_id: UUID,
                      question: str) -> service.AskOutcome | None:
    """`AM-143` (owner, 2026-10-15): a question that weighs a chat FILE against our
    positions is answered by the Dashboard's own contract-review engine, run on the
    file and rolled back — temporary, never a Contract. The same permissions as a
    Dashboard review: running one needs `review.create`, reading it `finding.view`, and
    the standard's value `legal_position.view` (omitted, never nulled). None: not such a
    question, no such file, or no published standards — the ordinary path answers."""
    if not service.wants_temporary_review(question) \
            or attachments.file_segments(guard.db, conversation_id) is None:
        return None
    if not {P.REVIEW_CREATE, P.FINDING_VIEW} <= guard.permissions:
        return service.record_file_review(
            guard.db, conversation_id=conversation_id, question=question,
            filename=None, findings=None, refused=None, request_id=guard.request_id)
    reviewed = temporary_review.review_file(
        guard.db, conversation_id=conversation_id, user_id=guard.user_id,
        legal_position=guard.sees_legal_position, request_id=guard.request_id)
    if reviewed is None:
        return None
    return service.record_file_review(
        guard.db, conversation_id=conversation_id, question=question,
        filename=reviewed.filename, findings=reviewed.findings,
        refused=reviewed.refused, request_id=guard.request_id)


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def ask(conversation_id: UUID, body: AskRequest,
        guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.ASSIST_ASK)
    conversation = _visible_conversation(guard, conversation_id)
    version = None
    if conversation["contract_id"] is not None:
        # The full existing authorization chain for the underlying document — the
        # same READ resolver every other document read goes through (AM-25 r6:
        # server-side, before retrieval). A previous owner who kept the conversation
        # can still read it; they can no longer ask new questions about a contract
        # they lost scope on.
        guard.contract_readable(conversation["contract_id"], P.ASSIST_ASK)
        version = _asked_document_version(guard, conversation["contract_id"],
                                          body.document_version_id)
    elif body.document_version_id is not None:
        raise BusinessRuleRejected(
            "this conversation has no contract attached; document_version_id "
            "cannot be named")
    # A document-less conversation is legitimate since 2026-09-08: the router
    # (`assist.routing`) decides which authorized sources can answer, and a question
    # nothing can answer gets the route's one refusal wording, not an error.

    # The reader's model, validated before anything is stored or spent (`AM-116`):
    # the one named in this request, else the chat's own (`AM-122`), else the
    # default. A model named here becomes the chat's, so the next turn — from any
    # tab, device or client — stays on it; one the server cannot serve is refused
    # by name and changes nothing.
    model = _model(body.model or conversation["model"])
    if body.model is not None and model.id != conversation["model"]:
        guard.db.execute(text(
            f'UPDATE "{config.assist_schema()}".conversations SET model = :m '
            "WHERE id = :i"), {"m": model.id, "i": conversation_id})

    # The one paid egress path, and until 2026-09-11 the only endpoint with no budget.
    _limiter.check(f"ask:{guard.user_id}", ratelimit.ASK)

    if not (body.question or "").strip():
        raise BusinessRuleRejected("the question is empty")
    if body.edit_of is not None:
        _replace_from(guard, conversation_id, body.edit_of)
    question, saved = body.question, []
    if len(question) > attachments.QUESTION_MAX_CHARS or (
            config.ask_attachments_enabled() and attachments.carries_material(question)):
        if not config.ask_attachments_enabled():
            raise BusinessRuleRejected(
                f"the question exceeds {attachments.QUESTION_MAX_CHARS} characters")
        question, material = attachments.split_paste(question)
        saved = [_attachment_view(_add_material(
            guard, conversation_id, material.encode(), attachments.PASTE))]
        if not question:
            # No paragraph asks by our rules, so the model reads it all for what it asks
            # — "Quote the clause and cite the source." at the end of an email is a
            # request no rule listed (owner, 2026-10-13, `AM-138`). The
            # reader's own words when they fit; the text is their citable material.
            fits = len(body.question) <= attachments.QUESTION_MAX_CHARS
            question = body.question if fits else attachments.PASTE_REQUEST

    # A question asked about a Finding: resolved through the ordinary Guard, then
    # required to belong to THIS conversation's contract. Same narrowing discipline as
    # `_asked_document_version` — a Finding the caller can legitimately read, but from
    # another contract, is refused rather than used to seed this conversation.
    finding_id = None
    if body.finding_id is not None:
        try:
            finding_id = UUID(body.finding_id)
        except ValueError as exc:
            raise BusinessRuleRejected("finding_id is not a valid identifier") from exc
        finding = guard.finding(finding_id, P.FINDING_VIEW)
        owner = guard.db.execute(text("""
            SELECT v.contract_id FROM findings f
              JOIN reviews r ON r.id = f.review_id
              JOIN document_versions v ON v.id = r.document_version_id
             WHERE f.id = :f"""), {"f": finding.id}).scalar_one_or_none()
        if owner is None or owner != conversation["contract_id"]:
            raise BusinessRuleRejected(
                "the finding does not belong to this conversation's document")

    feedback.note_reask(guard.db, conversation_id=conversation_id, user_id=guard.user_id,
                        question=question, request_id=guard.request_id)
    log_event("assist.ask.model", request_id=guard.request_id,
              conversation_id=str(conversation_id), model=model.id,
              provider=model.provider)
    outcome = (_temporary_review(guard, conversation_id, question)
               if conversation["contract_id"] is None and not saved else None)
    if outcome is None:
        outcome = service.ask(guard.db, conversation_id=conversation_id,
                              document_version_id=version.id if version else None,
                              permissions=guard.permissions,
                              question=question, request_id=guard.request_id,
                              finding_id=finding_id, model=model.id)
    # what replay will show, from the same row: the model that answered and the time
    answered = guard.db.execute(text(
        f'SELECT model_identity, latency_ms FROM "{config.assist_schema()}".ai_answers '
        "WHERE message_id = :m"), {"m": outcome.message_id}).first()
    return data({
        "conversation_id": str(outcome.conversation_id),
        "message_id": str(outcome.message_id),
        # The question this answers, by its own id: what an edit names (`AM-134` r3).
        "question_message_id": _question_of(guard, outcome.message_id),
        "model": model.id,
        # Which version this answer is about — stated, never inferred by the
        # caller. A conversation may span versions (the table is contract-scoped),
        # so the answer says which one it read rather than leaving the reader to
        # assume it matched whatever was on screen.
        "document_version_id": str(version.id) if version else None,
        "version_number": version.version_number if version else None,
        "answer_state": outcome.answer_state.value,
        "text": outcome.text,
        # `AM-76` r2 — the reader asked for the source's own words, so the UI opens
        # the quote in `positions` rather than collapsing it behind a disclosure.
        "exact_text_requested": outcome.exact_text_requested,
        # ...and the wider case: the quote is the answer, asked for or fallen back to
        # (`AM-76` r4). The UI must show it OPEN, or the reader gets a standard code
        # where the text told them the wording was "quoted below".
        "quote_is_the_answer": outcome.quote_is_the_answer,
        "routed_to_evaluator": outcome.routed_to_evaluator,
        # the asked topic's standards: the review's findings shown under this answer
        # stay on that topic (AM-156)
        "topic_requirements": service.topic_requirements(question),
        "comparison": outcome.comparison,
        "positions": outcome.positions,
        "statutes": outcome.statutes,
        "domains": list(outcome.domains),
        "citations": [{
            "chunk_id": str(c.chunk_id),
            "evidence_id": str(c.evidence_id),
            "page_number": c.page_number,
            "section_ref": c.section_ref,
            "excerpt": c.excerpt,
            # The whole cited span, for the expandable evidence view. `excerpt`
            # stays for the collapsed one.
            "text": c.text,
            # A retrieval score, labeled as exactly that — never confidence
            # (AI-03 item 16; rule 12).
            "retrieval_score": round(c.retrieval_score, 4),
        } for c in outcome.citations],
        # What this answer actually did, in pipeline order, with what each stage
        # cost. Nothing is streamed — no token reaches a reader before mechanical
        # verification (`AM-25` r5, `AM-69`) — so this is a record of the work, and
        # the UI shows its own wording for the stages while the request is open.
        "progress": service.progress_sequence(outcome.timings),
        # Plan 1.1: a long paste was kept as the reader's material, and the reply
        # says so here rather than inside the verified answer text.
        "attachments_saved": saved,
        "sources": outcome.sources,
        "answered_by": model_router.answered_by(answered[0] if answered else None),
        "latency_ms": answered[1] if answered else None,
    })

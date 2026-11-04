"""Ask's two caches — `AM-126` (draft; owner spec D2a, 2026-10-08). `AM-27`'s closed set
of tables admits no cache table, so nothing here is in the database. Each process keeps
its own LRU; production has run TWO uvicorn workers since 2026-10-30, so with
``LEGALMIND_ASK_CACHE_BACKEND=redis`` every entry is also kept in Redis, where the other
worker finds it (2026-11-02: per-process only, each worker missed what the other had
cached). JSON in Redis, never pickle; Redis down → per-process, as before.

TIER 1 — PUBLIC, shared across users. Only the CONSTITUTION, POSITIONS and STATUTES
domains, never a document or the reader's material (`PUBLIC_DOMAINS`):

  * a domain search's candidates (`retrieval.candidates`), keyed on the exact query,
    the caller's permission set and `include_superseded` — authorization is decided
    BEFORE the lookup, by which domains are searched and under which permissions, so a
    result is never filtered after the fact (`AM-25` r6) — and on `corpus_version`, so
    a re-ingest, a retired standard or a new Constitution misses at once. EXACT query
    only — no paraphrase hit: MiniLM puts "section 73 …" at 0.947 from "section 74 …",
    "excluded" at 0.936 from "included" and "before termination" at 0.985 from "after"
    (2026-10-08), so no cosine threshold separates a paraphrase from its opposite.
  * a cross-encoder score, keyed on (reranker identity, query, sha256(text)): changed
    text simply misses (`rerank.scores_many`).

TIER 2 — PER USER: an answered first turn, as a POINTER to its reply message, never its
text (`AM-27` r6). A hit re-reads the reply, misses when the reply, its conversation or
any record it cited is gone or no longer readable under the caller's live permissions
(`ledger.refetch`), and is written as a fresh turn with its own answer, ledger and audit
rows (`replay`). Never across users; only a turn with no prior context, so a re-ask in
the same conversation — the owner's "give me a new answer" — always runs fresh; never a
reply rated Not helpful; never a turn that called `find_documents`, whose names of other
documents are not ledger records and so could not be re-checked on a replay.

`LEGALMIND_ASK_CACHE_PUBLIC` / `LEGALMIND_ASK_CACHE_USER`: `off` is the rollback.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any
from uuid import UUID

from sqlalchemy import text

from legalmind import config

PUBLIC_DOMAINS = frozenset({"CONSTITUTION", "POSITIONS", "STATUTES"})
PUBLIC_TTL_S = 30 * 86400
USER_TTL_S = 86400


#: clear of Celery's, the limiter's and the breaker's keys; the version moves whenever
#: an entry's shape changes (a Candidate field), so a deploy never decodes the old shape
_REDIS_PREFIX = "legalmind:askcache:v1:"
_REDIS_BACKOFF_S = 30.0
_redis_client: list = []
_redis_down_until = [0.0]


def _seal_key() -> bytes | None:
    """The HMAC key for entries in Redis, derived from the server's JWT secret (its own
    label, so neither use can stand in for the other). Redis is not a trust boundary — a
    search entry becomes evidence text — so an entry without a valid seal is a miss."""
    secret = os.environ.get("LEGALMIND_JWT_SECRET", "")
    return hashlib.sha256(b"legalmind-askcache|" + secret.encode()).digest() \
        if secret else None


def _seal(payload: str, key: bytes) -> str:
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest() + "." + payload


def _unseal(raw: bytes, key: bytes) -> Any:
    """The JSON value of a sealed entry, or None when the seal does not verify."""
    try:
        sig, _, payload = raw.decode().partition(".")
    except ValueError:                  # not UTF-8: not ours
        return None
    good = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return json.loads(payload) if hmac.compare_digest(sig, good) else None


def _redis(action: Callable, fallback=None):
    """One Redis call when the shared backend is on (and a seal key exists); fails open
    to ``fallback`` and stays off for `_REDIS_BACKOFF_S`, so a dead Redis costs one
    timeout, not one per lookup."""
    if (not config.ask_cache_shared() or _seal_key() is None
            or time.monotonic() < _redis_down_until[0]):
        return fallback
    try:
        if not _redis_client:
            import redis  # lazy: celery[redis] pulls it in
            url = (os.environ.get("LEGALMIND_RATELIMIT_REDIS_URL")
                   or os.environ.get("LEGALMIND_BROKER_URL") or "")   # as the limiter
            _redis_client.append(redis.Redis.from_url(
                url, socket_timeout=0.5, socket_connect_timeout=0.5))
        return action(_redis_client[0])
    except Exception as exc:            # redis.RedisError and socket failures
        _redis_down_until[0] = time.monotonic() + _REDIS_BACKOFF_S
        from legalmind.observability.logs import log_event
        log_event("assist.cache.redis_unavailable", level=logging.WARNING,
                  error=type(exc).__name__)
        return fallback


@dataclasses.dataclass(frozen=True)
class Shared:
    """How a Store's entries travel through Redis: its name, their lifetime there, and
    a JSON codec (``encode`` to JSON-able, ``decode`` back)."""
    name: str
    ttl_s: int
    encode: Callable[[Any], Any] = lambda v: v
    decode: Callable[[Any], Any] = lambda v: v


class Store:
    """A bounded, expiring LRU behind one lock; with ``shared``, Redis behind it."""

    def __init__(self, ttl_s: float, maxsize: int,
                 clock: Callable[[], float] = time.monotonic,
                 shared: Shared | None = None):
        self.ttl_s, self.maxsize, self.clock = ttl_s, maxsize, clock
        self.shared = shared
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def _rkey(self, key: Hashable) -> str:
        assert self.shared is not None
        return f"{_REDIS_PREFIX}{self.shared.name}:{_digest(key)}"

    def get(self, key: Hashable) -> Any:
        with self._lock:
            found = self._data.get(key)
            if found is not None and found[0] >= self.clock():
                self._data.move_to_end(key)
                self.hits += 1
                return found[1]
            self._data.pop(key, None)
        value = None
        if self.shared is not None:
            raw = _redis(lambda c: c.get(self._rkey(key)))
            try:
                got = None if raw is None else _unseal(raw, _seal_key() or b"")
                value = None if got is None else self.shared.decode(got)
            except (ValueError, TypeError, KeyError):   # a shape this code cannot read
                value = None
                _redis(lambda c: c.delete(self._rkey(key)))
        with self._lock:
            if value is None:
                self.misses += 1
                return None
            self.hits += 1
        self._put_local(key, value)
        return value

    def _put_local(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._data[key] = (self.clock() + self.ttl_s, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def put(self, key: Hashable, value: Any) -> None:
        self._put_local(key, value)
        if (shared := self.shared) is not None:     # encoded only when Redis is on
            _redis(lambda c: c.set(self._rkey(key), _seal(
                json.dumps(shared.encode(value), default=str), _seal_key() or b""),
                ex=shared.ttl_s))

    def pop(self, key: Hashable) -> None:
        with self._lock:
            self._data.pop(key, None)
        if self.shared is not None:
            _redis(lambda c: c.delete(self._rkey(key)))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self.hits = self.misses = 0


def _candidates(found: tuple) -> list[dict]:
    return [dataclasses.asdict(c) for c in found]


def _from_candidates(rows: list[dict]) -> tuple:
    from legalmind.assist.retrieval.retrieval import Candidate
    return tuple(Candidate(**{**r, "item_id": UUID(r["item_id"]),
                              "lanes": tuple(r["lanes"]),
                              "authorities": tuple(r["authorities"])}) for r in rows)


# ponytail: entries hold up to DEPTH candidates with their text (~50-100 KB each), so
# the bound is small; intern the texts if a larger one is ever wanted. In Redis (no
# maxmemory, noeviction, shared with Celery) a search lives one day, not thirty, so the
# shared copy stays a few MB at today's traffic; give it its own Redis db or a
# maxmemory policy if Ask traffic grows by an order of magnitude.
SEARCHES = Store(PUBLIC_TTL_S, 1024,
                 shared=Shared("search", 86400, _candidates, _from_candidates))
# ponytail: one Redis GET per score lookup; batch them (MGET in rerank._memoised) if the
# stage logs show it. A day in Redis, as searches: noeviction Redis is Celery's broker.
SCORES = Store(PUBLIC_TTL_S, 100_000,      # ~300 B an entry: ~30 MB at the bound
               shared=Shared("score", 86400))
ANSWERS = Store(USER_TTL_S, 4096,
                shared=Shared("answer", int(USER_TTL_S),
                              decode=lambda v: (UUID(v[0]), UUID(v[1]))))


def counts() -> dict[str, int]:
    """Process totals for the stage logs — numbers only."""
    return {"search_hit": SEARCHES.hits, "search_miss": SEARCHES.misses,
            "score_hit": SCORES.hits, "score_miss": SCORES.misses,
            "answer_hit": ANSWERS.hits, "answer_miss": ANSWERS.misses}


def reset_for_tests() -> None:
    for store_ in (SEARCHES, SCORES, ANSWERS):
        store_.clear()


def _digest(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()


def permission_key(permissions: frozenset[str]) -> str:
    return _digest(sorted(permissions))


def corpus_version(db) -> str:
    """The public corpus's state in one cheap query: each Act's file hash and status,
    the statute chunks' count, chunking versions and row versions, each knowledge
    source's version, status and file hash and its items' row versions, and each
    position chunk with its standard version, row version and its requirement's status
    — retiring a standard (`AM-71`) flips a status, never a chunk — plus the embedder
    and reranker in this process. A row version is Postgres's `xmin`, which every UPDATE
    moves: a statute re-ingest rewrites a kept section's text IN PLACE
    (`statutes._replace_statute_chunks`), same row count, same file, same label."""
    from legalmind.assist.ingestion import embedding_runtime
    from legalmind.assist.retrieval import rerank
    s = config.assist_schema()
    stamp = db.execute(text(f"""SELECT md5(concat_ws('|',
      (SELECT string_agg(concat_ws(':', id, file_sha256, status), ',' ORDER BY id)
         FROM "{s}".statutes),
      (SELECT concat_ws(':', count(*), sum(xmin::text::bigint),
                        string_agg(DISTINCT chunking_algorithm_version, ','))
         FROM "{s}".statute_chunks),
      (SELECT string_agg(concat_ws(':', id, version, status, file_sha256), ','
                         ORDER BY id) FROM "{s}".knowledge_sources),
      (SELECT concat_ws(':', count(*), sum(xmin::text::bigint))
         FROM "{s}".knowledge_items),
      (SELECT string_agg(concat_ws(':', pc.id, pc.standard_version_id, pc.xmin,
                                   pc.chunking_algorithm_version, r.status), ','
                         ORDER BY pc.id)
         FROM "{s}".position_chunks pc
         JOIN company_standard_versions csv ON csv.id = pc.standard_version_id
         JOIN requirement_versions rv ON rv.id = csv.requirement_version_id
         JOIN requirements r ON r.id = rv.requirement_id)))""")).scalar()
    return f"{stamp}:{embedding_runtime.identity()}:{rerank.identity()}"


def public_search(key: tuple, run: Callable[[], list]) -> list:
    """`run()`'s result for a PUBLIC domain search, from the cache when this exact key
    was searched within the TTL."""
    found = SEARCHES.get(key)
    if found is None:
        found = tuple(run())
        SEARCHES.put(key, found)
    return list(found)


# ------------------------------------------------------------------------- tier 2
def normalized(question: str) -> str:
    r"""Case and punctuation folded, letters, digits and combining marks kept: `\w` drops
    Devanagari matras, so "पहले नोटिस" and "पहला नोटिस" shared a key (2026-10-13)."""
    text = unicodedata.normalize("NFC", question or "").casefold()
    return " ".join("".join(ch if unicodedata.category(ch)[0] in "LNM" else " "
                            for ch in text).split())


def answer_key(db, ctx, question: str, user_message_id: UUID, *, model: str,
               prompt_version: str) -> str | None:
    """The per-user key, or None when the turn may not use the cache: a prior turn in
    this conversation (the answer depends on it, `AM-111` r1, and a re-ask must run
    fresh) or the flag off. Keyed on the user, the selected document's version (the one
    the reader has open — an answer about Version 1 is never replayed for Version 2),
    the conversation's attachments, the question, the public corpus, the model, the
    prompt version and the permission set."""
    if not config.ask_cache_user():
        return None
    s = config.assist_schema()
    prior = db.execute(text(f'SELECT 1 FROM "{s}".messages WHERE conversation_id = :c '
                            "AND id <> :m LIMIT 1"),
                       {"c": ctx.conversation_id, "m": user_message_id}).first()
    if prior is not None:
        return None
    from legalmind.assist.agent import tools
    version = tools.selected_version(ctx)
    material = sorted(str(i) for i in db.execute(text(
        f'SELECT id FROM "{s}".conversation_attachments WHERE conversation_id = :c'),
        {"c": ctx.conversation_id}).scalars())
    return _digest(str(ctx.user_id), str(ctx.contract_id), str(version), material,
                   normalized(question), corpus_version(db), model, prompt_version,
                   permission_key(ctx.permissions))


def remember(key: str | None, conversation_id: UUID, reply_id: UUID) -> None:
    if key is not None:
        ANSWERS.put(key, (conversation_id, reply_id))


def replay(db, ctx, key: str | None, *, request_id: str | None, started: float):
    """The earlier answer as a fresh turn of THIS conversation, or None (a miss). Its
    text is re-read from its message and must not be rated Not helpful (a retry after
    a bad answer wants a new one); every record it cited is re-read under the
    caller's permissions NOW and must be current, else the entry is dropped. The new
    turn gets its own ai_answers row, its own ledger rows under the SAME keys the text
    cites (copied from the earlier first turn, whose ledger began empty, as this one's
    does), its own answer links and an `assist.answer_replayed` audit event."""
    from legalmind.assist import service
    from legalmind.assist.agent import ledger
    from legalmind.assist.state import AssistAnswerState
    from legalmind.observability.logs import log_event
    from legalmind.security import audit
    pointer = ANSWERS.get(key) if key is not None else None
    if pointer is None:
        return None
    source_conversation, source_reply = pointer
    s = config.assist_schema()
    row = db.execute(text(f"""
        SELECT m.content, a.id, a.model_identity, a.prompt_version_id
          FROM "{s}".messages m
          JOIN "{s}".conversations c ON c.id = m.conversation_id
          JOIN "{s}".ai_answers a ON a.message_id = m.id
         WHERE m.id = :m AND m.role = 'ASSISTANT' AND c.user_id = :u
           AND a.answer_state = :st
           AND NOT EXISTS (SELECT 1 FROM "{s}".answer_feedback f WHERE f.message_id = m.id
                           AND f.kind = 'RATING' AND f.rating = 'DOWN')"""),
        {"m": source_reply, "u": ctx.user_id,
         "st": AssistAnswerState.ANSWERED.value}).first()
    cited = ledger.keys_for_answer(db, row[1]) if row is not None else []
    fetched = ledger.refetch(db, conversation_id=source_conversation, keys=cited,
                             permissions=ctx.permissions,
                             contract_id=ctx.contract_id) if row is not None else []
    if row is None or any(f.state != ledger.CURRENT for f in fetched):
        ANSWERS.pop(key)
        return None
    content, _, model_identity, prompt_version_id = row
    reply = service._append_turn(db, ctx.conversation_id, "ASSISTANT", content)
    cols = ("evidence_key, source_class, domain, source_ref, chunk_id, "
            "position_chunk_id, statute_chunk_id, knowledge_item_id, "
            "attachment_chunk_id, authority, status, source_version, location, "
            "text_hash")
    db.execute(text(f"""
        INSERT INTO "{s}".conversation_evidence
            (id, conversation_id, turn_message_id, fetched_at, {cols})
        SELECT gen_random_uuid(), :c, :m, now(), {cols}
          FROM "{s}".conversation_evidence
         WHERE conversation_id = :src AND turn_message_id = :src_m"""),
        {"c": ctx.conversation_id, "m": reply, "src": source_conversation,
         "src_m": source_reply})
    elapsed = int((time.monotonic() - started) * 1000)
    answer = service._persist_answer(db, reply, None, AssistAnswerState.ANSWERED,
                                     model=model_identity,
                                     prompt_version_id=prompt_version_id,
                                     latency_ms=elapsed)
    ledger.record_answer(db, conversation_id=ctx.conversation_id, answer_id=answer,
                         turn_message_id=reply, extra=[
                             ledger.Record(f.key[0], f.source_ref or "", None,
                                           f.text or "", f.authority or "", "current",
                                           f.location) for f in fetched])
    audit.record(db, action=audit.ASSIST_ANSWER_REPLAYED, entity_type="conversation",
                 entity_id=ctx.conversation_id, request_id=request_id,
                 after={"source_message_id": str(source_reply), "model": model_identity,
                        "evidence_chunks": len(fetched)})
    log_event("assist.agent.turn", request_id=request_id,
              conversation_id=str(ctx.conversation_id), cache="answer_hit",
              stages_ms={"total": elapsed}, cache_counts=counts())
    return service.AskOutcome(
        conversation_id=ctx.conversation_id, message_id=reply,
        answer_state=AssistAnswerState.ANSWERED, text=content,
        timings={"total": elapsed, "cache": elapsed},
        sources=service.source_views(db, [(f.key, f.text, f.location, f.source_ref,
                                           None, f.state) for f in fetched]))

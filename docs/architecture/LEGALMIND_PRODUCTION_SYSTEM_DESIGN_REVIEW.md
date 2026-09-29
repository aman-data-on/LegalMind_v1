# LegalMind — Production System Design Review

📁 **ANALYSIS.** Architecture discovery and planning only. **No implementation changes were made to produce this document.** §28, appended the same day, records what was then implemented, what was found not applicable, and what still needs the owner. Every claim below is tagged `CONFIRMED` (read directly from code/config/tests), `INFERRED` (reasoned from confirmed facts, not itself observed), or `NEEDS MEASUREMENT` (requires a load test, EXPLAIN, or production metric this review could not run). Nothing here amends a locked decision (rules 2–3); where a recommendation would touch one, the decision ID is named per rule 6.

**Author**: architecture review pass, 2026-09-29. **Method**: seven parallel evidence-gathering passes over the actual repository (`/root/Legalmind.v1`), backend `legalmind/`, `ops/`, `.github/workflows/`, `frontend/`, `backend/tests/`, `backend/alembic/`. Every fact below carries a `file:line` citation from that pass. Documentation was cross-checked against code, not taken on its own word, per the brief.

**Scope note on today's real load**: the owner is the only user of this system today (per multiple `CLAUDE.md` records: "i am the only one who work in this project"; the product itself serves an unspecified future number of department users). This review models growth scenarios not because 500–1000 concurrent users is an imminent requirement, but because several of the findings below (the transaction held open across the Gemini call, the in-process rate limiter, local-disk document storage) are **cheap to fix now and expensive to discover under load later** — that is the whole point of doing this before scale forces it.

---

## 1. Executive Summary

LegalMind runs today as **one process of each kind, on one host**: one `uvicorn` API process (`systemctl restart legalmind-api`, no committed unit file — see §4), one Celery worker unit (`--concurrency 2`), one PostgreSQL instance with the `pgvector` extension, one Redis instance (used solely as the Celery broker), and one `nginx` reverse proxy with a single hardcoded upstream. Docker Compose exists as a **development/staging reference**, not the production shape (`docker-compose.yml:1-11`); production is systemd-native (`ops/production/`).

The system's engineering discipline is real and shows in the code: authorization is centralized in one `Guard` object and enforced before every domain operation (§13.1), RAG retrieval authorization is baked into the SQL `WHERE` clause rather than applied as a post-filter (§13.3 — verified against the code, not just the doc's claim), confidential-field omission and the 404-vs-403 leak guard both run through single shared functions (§13.4–13.5), Gemini failures never propagate as an unhandled 500 (§10), and optimistic-concurrency conflicts on Legal Decisions are enforced by an actual database constraint, not just application logic (§9.6). This is a codebase that took security and correctness seriously from the start.

The gaps are concentrated in three places, and they share a common shape: **each one is invisible at today's single-user load and would surface only under concurrency or multi-instance scaling** — exactly the failure mode this review exists to find before it is expensive.

1. **A database transaction is held open for the full duration of every Gemini call** (§6.5, §9). The per-request DB session is not committed until after `generation.generate()` returns from its network round-trip. Under concurrent Ask traffic this consumes a pool connection for as long as Gemini takes — up to the full 60-second timeout on a slow response — against an **unconfigured default pool of only 5 connections + 10 overflow per process** (§6.3). This is the single largest correctness/scalability risk found in this review (P0).
2. **The API cannot run as more than one instance without breaking correctness**, not just performance, because three things assume a single process: the in-process rate limiter (§6.4, §13.9), the local-filesystem-only document storage with no object-storage backend despite the spec calling for one (§16.4), and per-process singleton model warm-up cost (§6.4). None of these are hard to fix; all three currently block horizontal scaling outright rather than merely degrading it.
3. **Observability has a real blind spot in the one place that matters most for diagnosing an Ask problem**: `legalmind/assist/retrieval.py` emits zero log events — no latency, no candidate counts, nothing (§12.1). There is no metrics backend, no tracing, and no alerting anywhere in the system (§12.2–12.4) — all three are explicitly deferred by a locked decision (53.6, "NOT YET SPECIFIED"), so this is a known, named gap rather than an oversight, but it means today "what happened to this request?" cannot be fully answered from logs alone.

Nothing found in this review requires Redis-beyond-the-broker, a message queue beyond what already exists, a second database, microservices, or a new RAG framework. The recommended path is: fix the transaction-scoping bug (cheap, high-value), extract the two or three things that block horizontal scaling into shared/external state (cheap), close the retrieval observability gap (cheap), and defer everything else behind named, measurable trigger conditions (§21, §24).

---

## 2. Current Architecture

```
                                    ┌─────────────────────────────┐
                                    │         Browser              │
                                    └──────────────┬───────────────┘
                                                    │ HTTPS
                                    ┌───────────────▼───────────────┐
                                    │  nginx (single host)           │  ops/production/nginx-legalmind.lsnw.io.conf
                                    │  - TLS termination              │  limit_req_zone: login 10r/m, api 120r/m
                                    │  - client_max_body_size 25M     │
                                    └──────┬─────────────────┬──────┘
                                           │                 │
                              proxy_pass   │                 │  proxy_pass
                          127.0.0.1:3000   │                 │  127.0.0.1:8000
                                    ┌──────▼──────┐   ┌──────▼─────────────────────┐
                                    │  Next.js 16  │   │   FastAPI (uvicorn)         │
                                    │  App Router  │   │   ONE process (count        │
                                    │  React 19    │   │   unconfirmed — no unit     │
                                    │  no SSR-DB   │   │   file in repo, §4)         │
                                    │  access      │   │                              │
                                    └─────────────┘   │  Sync `def` handlers          │
                                                       │  (13 of 14 in one router)     │
                                                       │  → Starlette threadpool        │
                                                       │  sync SQLAlchemy engine        │
                                                       │  unconfigured pool (5+10)      │
                                                       └──────┬──────────┬────────────┘
                                                              │          │
                                          ┌───────────────────┘          └────────────────┐
                                          │                                                 │
                                   ┌──────▼─────────┐                              ┌────────▼────────┐
                                   │  PostgreSQL 16   │                              │  Gemini Flash     │
                                   │  + pgvector       │                              │  (sole egress)     │
                                   │  50 tables         │                              │  urllib, no pool,   │
                                   │  (31 locked +       │                              │  no retry, no        │
                                   │   19 assist schema)  │                              │  circuit breaker,     │
                                   │  exact KNN, no ANN     │                              │  60s timeout           │
                                   │  index (deliberate,     │                              │  1–5 calls/Ask          │
                                   │  AM-25 r6/r7)             │                              │  possible (§10.6)         │
                                   └──────┬──────────────────┘                              └─────────────────────────┘
                                          │
                                   ┌──────▼──────────┐        ┌───────────────────────┐
                                   │  Redis (1 use)     │◄──────│  Celery worker (1 unit) │
                                   │  Celery broker only │      │  --concurrency 2          │
                                   │  no cache, no         │      │  analysis + indexing        │
                                   │  session store          │      │  queues                       │
                                   └────────────────────────┘      │  no broker → INLINE           │
                                                                    │  fallback in request (§16.2)    │
                                                                    └───────────────────────────────┘
                                          │
                                   ┌──────▼──────────────┐
                                   │  Local filesystem      │  /var/lib/legalmind/documents
                                   │  (LocalFilesystemStorage)│  NO S3 backend exists in code
                                   │  content-addressed        │  despite spec calling for one
                                   └───────────────────────────┘
```

**Document upload → retrieval flow** (§16):
```
Upload → validate_upload (magic-byte sniff, 25MB edge / 100MB app limit)
        → LocalFilesystemStorage.put (SHA-256 content-addressed key)
        → parsing.parse (sync, in-request)
        → OCR (if needed): ALWAYS a daemon thread inside the API process
            (never queued, even with a broker configured) — recovered via
            Postgres advisory lock + startup reconciliation pass
        → dispatch_indexing: queued via Celery IF a broker is configured;
            otherwise runs INLINE in the request (chunking always inline-safe,
            embedding inline is the documented-costly fallback)
        → index_document_version: chunk_evidence → embed via local ONNX
            MiniLM singleton → INSERT chunks + chunk_embeddings
```

**Ask question flow** (§10, canonical 10-stage shape per `ASK_TARGET_ARCHITECTURE.md` §0):
```
POST /conversations/{id}/messages
  → RequestContextMiddleware / RequestLoggingMiddleware / CsrfMiddleware
  → get_db (opens session) → get_principal → get_guard
  → guard.permission(ASSIST_ASK) + guard.contract_readable/document_version_readable
  → InProcessRateLimiter.check (120/hour/user, single-process only)
  → service.ask()
      1. persist user turn (DB insert)
      2. conversation context (DB select, up to 4 prior turns)
      3. query understanding (in-process, regex/lexical, no DB/model)
      4. routing/authority policy — permissions decide candidate domains
         BEFORE question shape is considered (AM-45 r1, code not prompt)
      5. query planning — OFF by default (config default), 0 cost when off
      6. retrieval: store.search_hybrid — lexical (2 queries) + exact-KNN
         vector (1 query) per domain, authorization baked into SQL WHERE
      7. rerank — OFF by default (config default)
      8. evidence sufficiency gate — character-count check, no model
      9. generation.generate_raw() — THE ONE EGRESS FUNCTION, urllib,
         DB SESSION STILL OPEN across this call (§6.5, §9 — P0 finding)
     10. verification — mechanical (legacy path) or local NLI model
         (multi-source/default path)
     11. persist retrieval run, answer, citations (DB inserts)
  → CommitBeforeResponse commits the transaction BEFORE the response is sent
  → response
```

---

## 3. Component Inventory

| Layer | Technology | Evidence |
|---|---|---|
| Frontend | Next.js 16.3.4, React 19.2.0, App Router | `frontend/package.json:26-29` |
| Frontend state | Plain `useState`/Context, no Redux/Zustand/SWR/React Query | `package.json` deps grep — none present |
| API | FastAPI, sync `def` handlers (13/14 in `assist.py` router are sync) | `api/routers/*.py` |
| ORM | SQLAlchemy, sync engine (`create_engine`, not async) | `db/session.py:17,37` |
| Database | PostgreSQL 16 + pgvector ≥0.8.0 | `docker-compose.yml`, `AUTO_MODE_DECISIONS.md` row 75 |
| Vector search | pgvector exact KNN (no ANN index, deliberate) | `c4a91f6e2d87_chunk_embeddings.py:24-28` |
| Queue/broker | Celery + Redis (broker only, no result backend, no cache use) | `worker/app.py:58,75` |
| Local ML models | ONNX runtime, CPU-only execution provider, 3 singleton models (embed, rerank, NLI) | `onnx_backend.py:52`, `embedding_runtime.py`, `rerank.py`, `verify.py` |
| External LLM | Google Gemini (`gemini-3.6-flash`), single egress function, blocking `urllib` | `assist/generation.py:71,637-641` |
| Document storage | Local filesystem only, content-addressed; no S3 backend implemented | `ingestion/storage.py:48`, `api/storage.py:13-20` |
| Reverse proxy | nginx, single upstream each for API/frontend, rate-limit zones | `ops/production/nginx-legalmind.lsnw.io.conf` |
| Process supervision | systemd (`legalmind-worker.service` committed; API/frontend units referenced but not in repo) | `ops/production/` |
| CI | GitHub Actions, 15 jobs | `.github/workflows/ci.yml` |
| Deployment | Manual (`sudo legalmind-deploy` or `ops/deploy.sh`), restart-in-place, `flock`-serialized | `ops/deploy.sh` |
| Backups | `pg_dump` local (14-day) + GPG-encrypted S3 upload (90-day), cron-driven (schedule not in repo) | `ops/production/backup.sh` |
| Logging | Structured JSON, custom formatter, `request_id` correlation | `observability/logs.py:136-154` |
| Metrics/tracing/alerting | **None** — explicitly deferred (locked 53.6) | `observability/metrics.py:1-5` |

---

## 4. Dependency Graph (runtime, request-time)

```
FastAPI route handler
  → api/deps.py (get_db, get_principal, get_guard)   [hard dependency: PostgreSQL]
  → security/authorization.py, security/resolver.py   [DB reads, no cache]
  → service layer (contracts/, evaluation/, workflow/, assist/)
       assist/service.py
         → assist/routing.py, understanding.py, planner.py  [in-process, +DB for statutes.available()]
         → assist/store.py, positions.py, statutes.py, constitution.py  [PostgreSQL + pgvector]
             → assist/embedding_runtime.py → onnx_backend.py  [CPU, singleton, no external call]
         → assist/rerank.py → onnx_backend.py  [CPU, singleton, OFF by default]
         → assist/generation.py  [ONLY module with network egress — Gemini]
         → assist/verify.py → onnx_backend.py  [CPU, singleton, multi-source path only]
       ingestion/service.py
         → ingestion/storage.py  [local filesystem — hard dependency, no S3]
         → ingestion/parsing.py  [sync, in-process]
         → worker/dispatch.py  [Celery via Redis IF configured, else inline; OCR always inline thread]
  → CommitBeforeResponse route class  [PostgreSQL, commits before response]
```

**Hard runtime dependencies, in order of what breaks the most if lost:**
1. **PostgreSQL** — every request touches it; no cache layer exists anywhere to survive its absence (§5). Total outage = total outage.
2. **Local filesystem at `LEGALMIND_STORAGE_ROOT`** — every document read/write. No fallback.
3. **Redis** — only the Celery broker. Its absence degrades (falls back to inline processing, §16.2) rather than fails outright, **except** that inline processing under load is itself a risk (§9, §16.2).
4. **Gemini** — the assist lane is explicitly designed to degrade gracefully without it (§10.4); the authoritative (non-AI) legal-analysis path never depends on it at all (`AI-01`, `AM-25`).
5. **ONNX local models** — embedding-model failure degrades retrieval to lexical-only (`embedding_runtime.py:8-13`); rerank and NLI-verification are both already optional/off-by-default in the legacy path, so their absence is a smaller blast radius.

---

## 5. State Management / Horizontal Scaling — `CONFIRMED`

**Direct answer to the brief's question**: *"If I start 10 LegalMind API instances behind a load balancer, will the application still behave correctly?"* **No — not without changes.** Three specific things break, all cheap to fix:

| # | What breaks | Evidence | Failure mode with N instances |
|---|---|---|---|
| 1 | `InProcessRateLimiter` | `api/ratelimit.py:58-82`, singleton in `auth.py:65`, `assist.py:44`, `reviews.py:41`, `export.py:48`; docstring: "Correct for a single process only" (`ratelimit.py:60-64`) | Effective rate limit multiplies by N — a user gets N× their configured budget, split across whichever instance the LB happens to route them to |
| 2 | `LocalFilesystemStorage` | `ingestion/storage.py:48`, `api/storage.py:13-20` unconditionally instantiates it; no S3 backend class exists anywhere in the codebase despite comments describing one as the production target (`storage.py:51-53`) | A document uploaded via instance A 404s when instance B (different host, or same host without a shared volume) tries to read it |
| 3 | Per-process singleton model warm-up | `api/app.py:58-86` (`_warm_embedding_model`), same pattern for rerank/NLI singletons | Not a correctness break — N instances each pay the ONNX load cost independently, multiplying startup cost/memory, not causing wrong answers |

**What is *not* a problem**, confirmed by the same research pass:

- **Conversation/Ask state is fully DB-backed.** No in-memory session or conversation cache exists anywhere in `legalmind/assist/*.py`. A second instance can serve the next message in a conversation correctly.
- **Worker horizontal scaling looks safe by design.** Celery's redelivery semantics (`task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker/app.py:84-89`), a `UNIQUE(review_id, requirement_version_id)` constraint making a genuine double-processing race collide and roll back (`db/models.py:577`), and indexing's own refuse-if-already-indexed check (`assist/indexing.py:60-69`) together mean **N Celery worker processes/hosts consuming the same queue is safe today**, in contrast to the API side.
- **The deploy lock (`/var/lock/legalmind-deploy.lock`, `ops/deploy.sh:39-44`) is a single-host deploy-script concern**, not an application-instance concern — it says nothing about whether N *running* API instances can coexist, only that two people can't run the deploy script at once on one host.
- **DB-level advisory locks (OCR path) are already cross-process safe by construction** — Postgres session locks work correctly regardless of how many processes hold them from.

**CURRENT STATE → PROBLEM → RECOMMENDED, for each of the three real blockers:**

### 5.1 In-process rate limiter
- **CURRENT**: `deque`-based sliding window, one dict per process. `KEEP the interface, REPLACE the backend.`
- **PROBLEM**: multiplies the effective limit by instance count; also resets on every deploy restart (a process restart clears the dict).
- **WHY IT MATTERS**: rate limiting exists specifically to bound Gemini spend and abuse (§10, §11) — a limiter that silently stops working the moment you add a second instance is a cost-control and abuse-control gap that won't show up in any test that runs against one process.
- **OPTIONS**:
  - **(a) Redis-backed sliding window** — Redis is already in the stack as the Celery broker; a `ZSET`-based sliding window (or Redis's own `INCR`+`EXPIRE` fixed-window) is a small, well-understood addition, not a new dependency (rule 19 is satisfied — it reuses infrastructure already approved and running).
  - (b) Move rate limiting to nginx entirely — already partially true (`limit_req_zone`, `nginx-legalmind.lsnw.io.conf:17-18`), but nginx's zones are IP-based, not user-based, and the app-level limiter is intentionally user-keyed (important for a shared-IP office network).
  - (c) Do nothing until a second instance is actually provisioned.
- **TRADE-OFFS**: (a) is the only option that preserves per-user semantics across instances; it adds one small Redis round-trip per rate-limited call (login, ask, export, analysis, suggest-type) — cheap relative to the DB/Gemini calls already on those paths.
- **RECOMMENDED**: (a), implemented behind the existing `RateLimiter` protocol (`ratelimit.py` already has this abstraction — `NullRateLimiter` and `InProcessRateLimiter` both implement it, so a `RedisRateLimiter` slots in without touching call sites).
- **IMPLEMENTATION PLAN**: new class in `api/ratelimit.py` implementing the existing protocol; a `LEGALMIND_REDIS_URL`-driven factory function; swap the four module-level singletons to use it when the env var is set, fall back to in-process otherwise (so single-instance dev/staging is unaffected).
- **VALIDATION TEST**: a test that starts two `InProcessRateLimiter`-equivalent instances of the new class against the same Redis, hammers the same user key from both, and asserts the combined count is capped at the configured limit (not 2×).
- **ROLLBACK**: the factory falls back to in-process when Redis is unset — reverting is deleting the new class and the factory branch, no data migration involved.
- **TRIGGER CONDITION** (§21, §24): do this **before** running more than one API instance, not before. At one instance it is already correct.

### 5.2 Local filesystem document storage
- **CURRENT**: single `LocalFilesystemStorage` implementation, no interface variance despite `StorageBackend` being named as an abstraction (`storage.py:48`).
- **PROBLEM**: blocks any multi-host API deployment outright (not a degradation — a 404 on a document uploaded to a sibling host).
- **WHY IT MATTERS**: this is the one item in this review that is explicitly a **locked target already** — "Production uses S3-compatible object storage (locked Step 39)" is stated in the code's own comments (`storage.py:51-53`, `config.py:43-44`) — so building the S3 backend is not a new architectural decision, it is finishing a specified one that was deferred.
- **OPTIONS**: (a) implement the S3-compatible `StorageBackend` now; (b) keep local storage and instead pin every API instance to a shared network filesystem (NFS/EFS-equivalent) mounted at `LEGALMIND_STORAGE_ROOT` on every host; (c) do nothing until multi-host is provisioned.
- **TRADE-OFFS**: (a) matches the already-locked target and is what `ops/production/s3_object.py` already proves is feasible in this codebase (it already implements S3 put/get/list/delete for **backups** — the same library, boto3, and largely the same shape of code would serve documents). (b) is a smaller code change but adds an infrastructure dependency (shared filesystem) that then becomes its own single point of failure and was never the locked target.
- **RECOMMENDED**: (a) — reuse `s3_object.py`'s boto3 patterns to implement a second `StorageBackend` for documents, gated by the same interface `LocalFilesystemStorage` already implements, selected by an env var (`LEGALMIND_STORAGE_BACKEND=local|s3`) so single-host deployments keep working unchanged.
- **IMPLEMENTATION PLAN**: `ingestion/storage.py` — add `S3Storage(StorageBackend)` implementing `put`/`get`/`delete` against the interface already defined; `api/storage.py:16-19`'s `get_storage()` branches on config instead of unconditionally constructing `LocalFilesystemStorage`.
- **VALIDATION TEST**: the existing storage-backend test suite (whatever exercises `LocalFilesystemStorage.put/get`) run a second time against a local S3-compatible test double (moto, or a real bucket in staging) with identical assertions — content-addressing and the `_suffix()` allow-list (`storage.py:96-98`) must behave identically.
- **ROLLBACK**: env var back to `local`; no schema change (storage keys are content hashes, not backend-specific paths, per `storage.py:60-73`, so the same key format works with either backend, which is a low-risk detail worth preserving).
- **TRIGGER CONDITION**: needed before *any* second API host, whether for horizontal scaling or for basic redundancy — this is a P1 even at low user counts, because a single host's disk is also a single point of failure for every document in the system today, unconnected to scaling.

### 5.3 Per-process model warm-up cost
- **CURRENT**: `KEEP.` Warm-up at startup (`api/app.py:58-86`) is the right design — it pays the ONNX load cost once, at deploy time, instead of on the first user's request.
- **PROBLEM**: N processes pay it N times — a cost/startup-time multiplier, not a correctness issue.
- **RECOMMENDED**: `MEASURE FIRST.` Only worth addressing (e.g. a shared model-serving process) if warm-up time or per-process memory (the 118MB-vs-2.5GB trade-off already made deliberately at `pyproject.toml:33-42`) becomes a measured problem at the instance count actually provisioned. Do not build a model-server split speculatively.

---

## 6. Database Architecture Review

### 6.1 Schema overview — `CONFIRMED`, `KEEP`

50 tables total: 31 in the locked schema (`db/models.py`), 19 in a separate `assist` schema built across 6 Alembic migrations, per `AM-27` r1's requirement that assist-lane tables never share a schema with locked ones. Every assist-lane migration carries a mechanical proof (`tests/test_locked_schema_columns.py`) that it touched no locked table/column/index/enum. **This schema separation is correctly maintained and is a genuine strength** — it makes the "RAG never decides anything in the authoritative path" rule (`AI-01`) a database-level fact, not just a code-review convention.

### 6.2 pgvector — `CONFIRMED`, `KEEP`

Exact KNN (`ORDER BY embedding <=> :q`), no ANN index, on all four vector tables (`chunks_embeddings`, `position_chunk_embeddings`, `statute_chunk_embeddings`, `knowledge_item_embeddings`). This was a **measured decision**, not a default: `AUTO_MODE_DECISIONS.md` row 110 records that exact search was verified to lose no recall and to be the right trade for retrieval that is always pre-scoped to one document version (a few hundred candidate rows at most) before the vector sort runs. The `document_version_id`/`section` filter columns that bound the candidate set **are** indexed (`b1e7c4d20f39_assist_schema.py:173-186`); only the embedding column itself has no ANN index, which is exactly the deliberate choice.

- **KEEP as-is.** `MEASURE FIRST` before ever adding an ANN index: the trigger condition is a corpus large enough that a single document's chunk count regularly exceeds what an exact scan handles in acceptable latency — nothing in the evidence gathered suggests that threshold has been approached. Revisit if/when statute or Constitution retrieval (which spans a much larger corpus than one document) starts showing exact-scan latency in the `assist.ask.trace` numbers already being logged (`service.py:907-931`).

### 6.3 Connection pool — `CONFIRMED`, **P0 finding, paired with §6.5**

- **CURRENT**: `create_engine(url, pool_pre_ping=True)` (`db/session.py:37`) — no `pool_size`, `max_overflow`, `pool_timeout`, or `pool_recycle` set anywhere in the codebase. SQLAlchemy's defaults apply: `pool_size=5`, `max_overflow=10` — **15 connections per process, maximum**, before a request blocks waiting for one.
- **EVIDENCE**: `session.py:24-38` (engine construction), confirmed by grep across `config.py` for any `pool_*` symbol — none exist.
- **PROBLEM**: combined with §6.5 (a transaction held open across the full Gemini round-trip), 15 connections is a small budget. A handful of concurrent Ask requests, each holding a connection for up to 60 seconds while waiting on Gemini, exhausts the pool; every *other* request of any kind (not just Ask) — contract reads, Review lookups, login — then queues behind it or times out.
- **WHY IT MATTERS**: this is the direct answer to the brief's question *"could one slow dependency take down the whole application?"* — **yes, today, this is exactly the mechanism by which it would happen.** A slow Gemini response doesn't just slow down Ask; it starves the connection pool for every other endpoint sharing the same process.
- **OPTIONS**:
  - (a) Fix §6.5 first (stop holding the transaction open across the Gemini call) — this is the root cause; fixing it makes the pool-sizing question much less urgent, because connections are held for milliseconds (DB work only) instead of up to 60 seconds (DB work + network wait).
  - (b) Increase pool size as a stopgap without fixing §6.5 — masks the symptom, does not fix the structural problem, and a large pool just moves the exhaustion point to Postgres's own `max_connections`.
  - (c) Both — fix §6.5 as the real fix, and set explicit `pool_size`/`max_overflow`/`pool_timeout` values (rather than silent SQLAlchemy defaults) so the budget is a deliberate, documented number instead of an accident of the library's defaults, and `pool_timeout` gives a clean, fast-failing error instead of an indefinite queue.
- **RECOMMENDED**: (c). Root-cause fix in §6.5, plus explicit pool configuration so the ceiling is a decision, not a default.
- **IMPLEMENTATION PLAN**: `db/session.py` — add `pool_size=`, `max_overflow=`, `pool_timeout=` reading from new env vars with the current SQLAlchemy defaults as the fallback (so behavior is unchanged until someone deliberately tunes it); document the numbers relative to Postgres's own `max_connections` and the number of processes (API + worker) that share the database.
- **VALIDATION TEST**: a test that opens `pool_size + max_overflow + 1` sessions concurrently and asserts the `pool_timeout`-th one raises a clean `TimeoutError` rather than hanging — this test does not exist today (confirmed absent, §17).
- **ROLLBACK**: env vars unset → SQLAlchemy defaults, i.e. today's exact behavior.

### 6.4 Transaction scoping across the Gemini call — `CONFIRMED`, **P0**

- **CURRENT**: `generation.generate()` is called from inside `assist/service.py` while the request's single `db` session (opened by `get_db`, `api/deps.py:53-80`) is still open and uncommitted. Confirmed at three call sites: `service.py:628-633` (`_answer_statutes`), `service.py:1220` and `:1425-1427` (document Q&A path). The session isn't committed until `CommitBeforeResponse` runs, after the route handler returns (`deps.py:120-125`) — i.e., after generation, verification, and all persistence steps have already happened in the same transaction.
- **PROBLEM**: the DB connection checked out for that request is held, unusable by anything else, for the full duration of the Gemini network call — which has no retry and a 60-second timeout (§10.1), and per §10.6 can happen 1–5 times in a single Ask request (rescue + main + statute + repair calls all compose).
- **WHY IT MATTERS**: this is the review's single highest-value fix. It is a small, mechanical, code-only change (no schema, no migration) that removes the mechanism by which a slow or stuck Gemini response degrades every other endpoint in the application, not just Ask.
- **OPTIONS**:
  - (a) Commit (or at least release) the DB session before calling `generation.generate()`, re-open a session for the subsequent persistence steps (retrieval-run, answer, citations, audit event). This is the textbook fix: never hold a DB transaction open across an external network call.
  - (b) Move the Gemini call outside the request entirely (fire the generation as a background job, poll or push the result) — much larger change, adds latency for the common case, not justified by the evidence (Ask is meant to be synchronous and Stage 9 already forbids streaming per `AM-25` r5 — this is a deliberate design, not an oversight to route around).
  - (c) Leave it as-is and rely solely on the pool-size/timeout fix in §6.3 to fail fast instead of hang. Treats the symptom, not the cause.
- **RECOMMENDED**: (a).
- **TRADE-OFFS of (a)**: splitting into two transactions means the user-turn insert and the final answer/citation inserts are no longer atomic with each other — if the process crashes between them, a user turn could exist with no answer. This is an acceptable trade (the existing `CommitBeforeResponse` mechanism already accepts a similar "answer was generated but the response socket write could fail" window, §9.6) and is the standard shape for any request that mixes DB work with a slow external call — no production system holds a DB transaction open across an LLM call for exactly this reason.
- **IMPLEMENTATION PLAN**: in `assist/service.py`, restructure `_ask` so that (1) all pre-generation DB reads happen and their results are held as plain Python values, (2) the session used for those reads is committed/released before `generation.generate_raw()` is called, (3) a fresh session (or the same one, re-begun) is used for the post-generation persistence block (`_persist_retrieval`, `_persist_answer`, `_persist_citations`, the audit-log `ASSIST_GENERATION_CALLED` write). The route-level `CommitBeforeResponse` mechanism is unaffected — it still commits whatever the final session holds before the response goes out.
- **VALIDATION TEST**: a test that starts N concurrent Ask requests (N > pool_size) against a Gemini test-double with an artificial delay, and asserts that requests to *other* endpoints (e.g. `GET /contracts`) made during that window complete quickly rather than queuing behind the Ask requests' held connections. This test does not exist today.
- **ROLLBACK**: this is a refactor of one function's session lifecycle, not a schema or data change — revert is a code revert.

### 6.5 Indexes — `CONFIRMED`, mostly `KEEP`, one `IMPROVE`

Indexes generally match query patterns: `contracts`, `reviews`, `findings`, `document_evidence` all have indexes on the columns their actual `WHERE` clauses filter on (`db/models.py:290-296,545-551,576-581,378-382`); the assist-schema tables mirror the `document_version_id`/`section` filters used in `store.py`/`positions.py`/`statutes.py` (`b1e7c4d20f39_assist_schema.py:173-186`).

**One gap**: `audit_events` has indexes on `actor_id`, `(entity_type, entity_id)`, and `timestamp` (`db/models.py:778-782`) but **no index on `action` alone**, while `GET /audit-events?action=...` (`api/routers/audit.py:59-60`) can be called with only that filter, forcing a sequential scan on what will become the largest table in the system (append-only, no retention policy — §6.7).

- **RECOMMENDED**: `IMPROVE.` Add an index on `audit_events.action` (or a composite `(action, timestamp)` if that's the common query shape) once §6.7's row-count question is answered — don't index a column speculatively; index it once the table's actual size makes a sequential scan on it measurably slow. `MEASURE FIRST`: current row count and whether `action`-only filtering is a route actually used in practice (it may be an admin/audit-review tool used rarely enough that a sequential scan is fine for years).

### 6.6 N+1 / repeated queries — `CONFIRMED`, minor, `IMPROVE` (low priority)

One real N+1 read: `evaluation/service.py:129-147` issues one `SELECT` per `evidence_ref` inside a loop to check `FindingEvidence` existence before insert, instead of a single batched `.in_()` check. Bounded by evidence-count-per-evaluation (typically single digits per the evidence gathered), so real-world impact is small. Several per-row `INSERT` loops for citations (`assist/service.py:540-547,582-588,596-602`) are the same shape — not correctness bugs, just an unbatched write pattern.

Everywhere else, the codebase consistently batches with `.in_()`/`ANY(:ids)` rather than looping (`api/serializers.py` actor/user/department lookups, `assist/store.py:747-768`'s explicit choice of `ANY(:ids)` "so asking for the rows by id cannot miss"). **This is a strength, not a gap** — the one N+1 found is small and isolated, not a systemic pattern.

- **RECOMMENDED**: `IMPROVE`, P3. Batch the `FindingEvidence` existence check in `evaluation/service.py` with a single `.in_()` query when someone is next in that file for another reason — not worth a standalone change given the bounded row counts involved.

### 6.7 Audit log growth — `CONFIRMED`, `MEASURE FIRST`

`audit_events` is enforced append-only by an actual database trigger (`legalmind_append_only()`, `80dccb65caf6_initial_locked_schema.py:420-437`) — UPDATE/DELETE both raise at the DB level, not just by application convention. No partitioning, retention, or archival strategy exists anywhere in the migrations or application code.

- **WHY IT MATTERS**: rule 17 requires the audit trail to stay reproducible and historical Reviews to stay reproducible — this is a hard constraint that rules out simple deletion-based retention. A table that only grows, with no partition boundary, eventually affects both storage and the sequential-scan risk in §6.5.
- **MEASURE FIRST**: current row-count growth rate (roughly, rows per Ask request × Ask volume + rows per Decision × Decision volume, per §6.7's per-operation counts already measured: 1 row per successful Gemini call, 1–2 rows per Legal Decision). At today's single-user volume this is a non-issue; it becomes worth planning for once volume projections are known (§24 gives the trigger condition).
- **RECOMMENDED path when the trigger fires**: time-based partitioning (e.g. by month) is the standard answer for an append-only, timestamp-queried table — it doesn't violate the append-only/no-delete rule (old partitions can be detached/archived to cold storage rather than deleted, preserving rule 17's reproducibility requirement) and directly improves query performance on the existing `timestamp` index. **Do not build this now** — it is real engineering effort for a problem that measured evidence doesn't yet show exists.

### 6.8 Pagination — `CONFIRMED`, `KEEP` with one documented exception

Standard offset/limit, clamped server-side to 100 (`api/pagination.py:20,37-43`), with a deterministic tiebreaker on `id` (locked 49.6). One documented, deliberate exception: `GET /contracts` with a `status` filter (a derived, non-column bucket) loads the full department/account-scoped result set into Python and paginates in memory (`contracts.py:189-197`) — bounded by the requester's own visible scope, not the whole table, so this is not an unbounded-result risk, just a non-SQL pagination path worth knowing about if that scope ever grows very large for a single department.

- **RECOMMENDED**: `KEEP`, `MEASURE FIRST` only if a single department's contract count grows large enough that the in-memory pagination step becomes visible in request latency.

### 6.9 Migration health — `CONFIRMED`, `KEEP`

17 revision files, single linear chain confirmed by cross-referencing every `down_revision` (one head, `b8e2f6a4d1c3`, never appears as anyone's parent). No `NOT NULL` column addition without a `server_default` was found in any migration — every risky pattern that could lock a large table during a deploy was checked and none exists. **This is a clean migration history.**

- **NEEDS MEASUREMENT**: actual `alembic heads` execution (this review inspected files, did not run the command) — low-risk to confirm, high-value if it ever silently diverges.

---

## 7. Cache Analysis — `CONFIRMED`: there is effectively no cache, and that is currently fine

**Direct finding**: nothing is cached across requests, anywhere in the system, except two narrow, deliberately-scoped exceptions:

1. A per-answer NLI pair memo (`assist/verify.py:112`) — explicitly cleared before and after every `check_answer()` call. Not a cross-request cache.
2. A `functools.cache` on a static local JSON config file read (`statutes.py:1098`, commencement dates) — caches parsing of a file that ships with the codebase, not runtime data.

Every retrieval-adjacent operation re-runs on every call: the embedding model re-embeds the identical query string independently for each domain searched within one Ask (document, positions, statutes, constitution each call `embedding_runtime.embed_query` separately, §10 evidence), retrieval issues fresh SQL every time, and Constitution/company-standard/statute chunks are read fresh from the DB on every call with no memoization.

**Why this is a defensible current state, not an oversight**: the brief's own instruction is "do NOT simply say 'add Redis' — determine what should and should NOT be cached," and applying that discipline here:

| Candidate | Cache? | Reasoning |
|---|---|---|
| Retrieval results (chunks for a query) | **NO** | Authorization is baked into the query itself (§13.3) — caching results keyed by query text alone would require re-deriving and re-checking authorization on every cache hit anyway to avoid leaking one user's retrieval into another's, which removes most of the benefit and adds real risk (rule 18's own warning: "never cache data in a way that can bypass authorization" applies directly here) |
| Embeddings of repeated identical questions | **MEASURE FIRST** | Lowest-risk cache candidate in the whole system — an embedding is a pure function of query text with no per-user authorization component. Worth measuring how often the *exact same question string* recurs before building this; if it's rare (likely, for natural-language questions), the cache buys little |
| Constitution / Company Standard / statute chunks | **MEASURE FIRST, likely yes eventually** | Read-heavy, rarely-changing, no per-user authorization variance (once a reader has the `positions.can_read` permission, the content is the same for everyone) — the best candidate in the system for a straightforward cache, but nothing in the evidence gathered shows this is currently a measured bottleneck |
| Conversation/answer content | **NO** | Mutates per-request, has per-user/per-department authorization, and caching an AI-generated answer risks serving a stale or wrongly-scoped answer — directly against rule 18 |
| Gemini responses | **NO, explicitly** | Even setting aside cost, two identical-looking questions can have different authorized evidence sets (different user, different document permissions) — caching the response would either leak or silently answer from the wrong evidence. The brief's own caution flag applies precisely here. |

**RECOMMENDED**: do not add a cache anywhere right now. If Constitution/statute/company-standard read latency is ever measured as a real contributor to Ask latency (nothing gathered in this review shows that it is — these reads are not logged with latency at all today, §12.1, which is itself worth fixing before deciding whether to cache them), the shape would be: key = `(source_id, content_hash)`, value = the chunk rows, TTL = none needed (invalidate on the publish/version-change event that already exists as a locked workflow step, since Company Standards are versioned and Reviews use configuration snapshots per rule 16), no per-user variance needed since these reads carry no confidential per-user data. This is a **MEASURE FIRST** item, not a recommendation to build now.

---

## 8. State Management — see §5 (Horizontal Scaling), which is the same question asked from a different angle. No additional findings.

---

## 9. Concurrency / Race Conditions

For each scenario in the brief, current behavior, risk, required guarantee, and fix:

| Scenario | Current behavior | Risk | Required guarantee | Fix |
|---|---|---|---|---|
| **Same user sends two questions quickly** | UI disables the composer while a request is pending (`AskWorkspace.tsx:747,763`, `AskDock.tsx:471,477`) — blocks the common case at the client | If a client bypasses the UI (direct API call, buggy retry) two concurrent inserts can compute the same next `ordinal` value (`service.py:214-219`, plain `SELECT max(ordinal)+1`, no lock) | The loser should get a clean, retryable error, not an unhandled crash | A `UniqueConstraint('conversation_id','ordinal')` **does exist** (`b1e7c4d20f39...py:284-285`) and would catch this — but no `try/except IntegrityError` wraps the insert anywhere in `service.py`/`deps.py` (confirmed absent), so the loser's request surfaces as an **unhandled 500**, not a clean 409. **P1**: wrap the turn-insert in a retry-on-`IntegrityError` (re-read the max ordinal, retry once) or return a typed 409 the way `DecisionControl`'s pattern already does (§9.6) |
| **Same conversation opened in two browser tabs** | Same mechanism as above — DB-level, not tab-aware | Same as above | Same as above | Same fix |
| **Retry while original request still running** | No idempotency key on the Ask POST | A naive client-side retry (e.g. a flaky network causing the client to resend) could append a duplicate user turn and trigger a second full set of Gemini calls — a real **cost** risk given §10.6's finding that one Ask can already cost 1–5 Gemini calls | A retried request with the same client-generated idempotency key should not re-trigger generation | **P2**: this is a real gap but lower priority than the P0/P1 items above — no evidence of it happening in practice was found (and the UI-level composer-disable mitigates the common accidental-double-click case), but it's worth an idempotency-key header on the Ask endpoint before opening the API to non-browser clients |
| **User switches chat during generation** | `AskWorkspace.tsx` explicitly guards this: captures `activeId`/`epoch` before the async call, checks staleness after, silently drops a late-arriving answer if the user navigated away (`AskWorkspace.tsx:337-339,390,405,468`) | **Confirmed correctly handled** in `AskWorkspace` | — | `KEEP` |
| — same, but in `AskDock` | **No equivalent staleness guard** — the pending response is appended to `turns` unconditionally when it arrives (`AskDock.tsx:277-283`), relying only on the disabled-composer to prevent overlap *within* one dock session | If the user navigates to a different document version while a dock question is pending, the late answer could be appended against the wrong document context | Same staleness check as `AskWorkspace` | **P2**: port the `stale()`/epoch pattern from `AskWorkspace` into `AskDock` — small, contained frontend fix |
| **Document deleted while Ask is running** | Not explicitly tested (§17); `document_version_id` scoping means a delete mid-retrieval would either find zero rows (if delete completes before the query) or succeed (if after) — no explicit handling found for the interleaved case | **NEEDS MEASUREMENT / NOT FOUND** — no test exercises this | A delete mid-Ask should produce a clean refusal, not a partial/confusing answer | Add a test; likely already safe by FK/scoping but unverified |
| **Document permissions change while Ask is running** | Permissions are re-resolved fresh from the DB on every request (`security/resolver.py:35-46`, explicitly no cross-request caching) — a permission change takes effect on the *next* request, not mid-flight of one already in progress | Low risk — a request already past its authorization check completes under the permissions it started with, which is standard and expected behavior for any web application | Standard "checked once at request start" semantics | `KEEP` — this is the normal, correct behavior, not a gap |
| **Constitution version / Company Standard unpublished during retrieval** | Reviews use configuration snapshots (rule 16, locked) — a Review's comparison is pinned to the snapshot taken when it started, so an unpublish mid-Review does not retroactively change results | **Confirmed correctly handled by the locked snapshot design** for the authoritative analysis path. For the *Ask* assist lane specifically, retrieval reads live Constitution/position rows on each call (§7) rather than a pinned snapshot — an unpublish between two Ask questions in the same conversation could change what the second question sees, which is arguably correct behavior (Ask should reflect current state) but is worth being explicit about, since it differs from the Review path's snapshot guarantee | Explicit documentation of which guarantee applies to which lane (Review = snapshot-pinned, Ask = live-read) | `KEEP` behavior; **P3**: add one sentence to `ASK_TARGET_ARCHITECTURE.md` making this distinction explicit if it isn't already, so it isn't mistaken for a bug later |
| **Two users update the same record (Legal Decision)** | Application-level version check (`workflow/decisions.py:98-102`) backed by a real `UNIQUE(evaluation_id, version_number)` constraint as the actual guarantee — a race that slips past the app check hits an `IntegrityError`, caught and re-raised as a typed `VersionConflict` → HTTP 409 (`decisions.py:113-121`) | **Confirmed correctly handled**, including a DB-level backstop, not just an application-level check | — | `KEEP` — this is the reference implementation the fix for the Ask-ordinal race (above) should follow |
| **Two workers process the same document** | Idempotent by refusal: indexing no-ops if chunks already exist (`assist/indexing.py:60-69`), analysis protected by `UNIQUE(review_id, requirement_version_id)` plus a no-op-if-already-analysed check (`tasks.py:155-163`) | **Confirmed correctly handled** | — | `KEEP` |
| **Duplicate ingestion (same file uploaded twice)** | **Not deduplicated** — a duplicate upload is flagged (`doc_metadata={"duplicate_of":...}`, `service.py:128`) but fully re-parsed, re-chunked, and re-embedded as an independent version, by explicit design ("the same source file may legitimately appear in several contracts," `storage.py:26-28`) | Not a bug — a deliberate design choice, since the same document can legitimately belong to two different contracts | Flag, don't block | `KEEP` — this is a considered decision, not an oversight |
| **Duplicate indexing** | Covered above (§9, indexing no-op) | — | — | `KEEP` |
| **Worker crashes mid-ingestion** | Tested with a real `SIGKILL` against a real worker: 23 of 24 Reviews recovered promptly (`test_worker.py:215-219`, docstring states this exact result) | The 1-in-24 gap in that test's own result | 100% recovery, or a documented reason why not | **P2, NEEDS MEASUREMENT**: find out what the 24th case was — was it a flake in the test itself, or a real edge case in the recovery mechanism? This is a test result already in the repository that appears not to have been fully chased down |
| **API crashes after DB write but before response** | `CommitBeforeResponse` (§2, §6.4) already narrows this window by committing before the response is sent rather than after — but a crash between the commit and the socket write is still possible, standard "at-least-once" semantics | Low — this is the normal, accepted risk profile for any web application; the commit-before-response fix already closed the *worse* version of this (client sees 200 for uncommitted work) | Standard at-least-once; not exactly-once | `KEEP` — already the best practical fix, exactly-once would require idempotency keys end-to-end which is disproportionate here |
| **Response succeeds but persistence fails** | The reverse of the above — `CommitBeforeResponse` means persistence is confirmed to have succeeded *before* the response is sent, so this specific ordering (response succeeds, persistence silently fails) is structurally excluded by the fix already in place | — | — | `KEEP` |

---

## 10. Failure / Recovery Design

### 10.1 Gemini — `CONFIRMED`, mixed KEEP/IMPROVE

| Aspect | Current | Assessment |
|---|---|---|
| Timeout | 60s (`generation.py:596,641`), no caller overrides it | `KEEP` — a request does return, it doesn't hang forever; 60s is on the long side for a *user-facing* wait but see §6.4, the real problem isn't the timeout length, it's that it happens with a DB connection still held |
| Retry | **None** on the Ask path — single attempt, immediate raise on any failure (`generation.py:643-662`). A different, unrelated lane (`analysis/service.py:368-398`) has one flat 1.5s-sleep retry, not used by Ask | `IMPROVE`, P2: a single bounded retry (one retry, short backoff) on transient errors (timeout, 5xx, connection reset) would likely reduce user-visible refusals without materially increasing worst-case latency or violating the cost guard's "no improvement means stop" principle — but this should be **measured** against real failure-rate data before building, per the Gemini cost guard's own instruction not to iterate against the live seam speculatively |
| Concurrency cap on Gemini calls | **None** — N concurrent Ask requests make N simultaneous Gemini calls, no semaphore | `IMPROVE`, P2: a bounded semaphore around `generate_raw()` would prevent a traffic spike from also spiking Gemini spend/rate-limit-429s simultaneously with everything else; low urgency at today's volume |
| Circuit breaker | **None found anywhere** | `IMPROVE`, P2: without one, every request independently retries against a fully-down provider for the full 60s, compounding §6.4's connection-pool problem. Fixing §6.4 (don't hold the DB connection) removes most of the *damage* a down Gemini can do; a circuit breaker would additionally remove the *latency* (fail fast after a few consecutive failures instead of 60s each). Sequence: fix §6.4 first (higher value, smaller change), then reassess whether a circuit breaker is still worth the added complexity |
| Error handling / graceful degradation | **Confirmed excellent.** Every failure mode (timeout, 429, 500, malformed/empty JSON) is caught inside `service.ask`/`answer.respond` and converted to a graceful degraded answer or a clean refusal — never an unhandled 500 to the user | `KEEP` — this is one of the strongest parts of the system |
| Idempotency / duplicate calls | Up to 4–5 Gemini calls possible in one Ask request (rescue + main + statute + repair + planner), confirmed via code trace and the system's own measured numbers ("Gemini calls per question 1.23 → 2.25" when the planner is on, `config.py:339-360`) | `MEASURE FIRST` / documentation gap: the module docstring's framing as "the single egress point" is true at the function level but can read as implying one call per request, which it is not. **P3**: correct the docstring's framing so a future reader doesn't assume 1:1 |
| Cost/token observability | `prompt_tokens`/`output_tokens`/`latency_ms`/`finish_reason` are logged (operational logs) but **not written to `audit_events`** — only `model`/`prompt_version`/`payload_sha256` reach the audit trail (`security/audit.py` call sites vs. `generation.py:668-672`) | `IMPROVE`, P3: this is a documentation-accuracy issue more than a functional gap (the data exists, just in logs rather than the audit table) — worth deciding deliberately whether token/cost data belongs in the audit trail (a compliance/legal record) or stays operational-only (a cost/ops record), rather than the current implicit split |
| Per-user/per-day cost cap | **None** — only the request-*count* rate limiter (120/hour/user) exists; no dollar or token ceiling | `IMPROVE`, P3, low urgency: worth a simple daily-spend alert threshold (log-based, using the already-computed `estimated_usd` in `assist.ask.trace`) before a hard cap — matches the Gemini cost guard's spirit without adding a new enforcement mechanism |
| Connection reuse | **None** — a fresh TCP+TLS connection is opened and torn down on every single Gemini call (`urllib.request.urlopen`, no `requests.Session`/`urllib3.PoolManager`) | `IMPROVE`, P2: switching to a pooled HTTP client (e.g. `httpx.Client` with connection reuse) would reduce per-call latency (TLS handshake avoided on repeat calls) at effectively zero risk — this is a pure win with no trade-off found, and worth doing alongside the §6.4 fix since both touch `generation.py` |

### 10.2 What happens if Gemini is unavailable for 5 minutes vs. 1 hour

**CONFIRMED behavior, both durations**: identical — every request independently times out after 60s, degrades gracefully to a refusal or fallback answer (§10.1), and the *next* request repeats the same 60s wait. There is no state that distinguishes "Gemini has been down for 5 minutes" from "Gemini has been down for 1 hour" — no circuit breaker means no memory of recent failures. This is functionally safe (no cascading failure, no data loss, no corrupted state) but **not efficient** — every single request during an extended outage pays the full 60s cost before degrading, which is the concrete cost of not having a circuit breaker (§10.1).

### 10.3 Other dependency failures — `CONFIRMED` / `NEEDS MEASUREMENT`

| Dependency down | Current behavior | Assessment |
|---|---|---|
| PostgreSQL unavailable | No fallback anywhere — every request needs it. `pool_pre_ping=True` means a dead connection is detected and replaced, but a fully unreachable DB fails every request | `KEEP` this as the accepted blast radius (there is no code path that should serve stale/cached data as if it were authoritative legal analysis — rule 18) — but **no test simulates this** (§17), which is worth closing so the *failure mode itself* (does it fail with a clean 503, or hang, or 500 with a leaking stack trace?) is verified rather than assumed |
| Redis unavailable | **Degrades, doesn't fail**: `configure_broker()` returning `None` routes both analysis and indexing dispatch to run inline in the request instead (`dispatch.py:72-85,126-179`) | `KEEP` the fallback existing; `IMPROVE`, P1: the fallback is explicitly documented as "not the locked deployment shape" and the production preflight is *supposed* to fail a deployment running this way — but only "no broker configured at startup" is tested, not "broker was up and went down mid-operation" (§17). A broker that drops mid-request would behave differently (an in-flight `apply_async` call failing) than one absent from the start — **NEEDS MEASUREMENT** to confirm this doesn't hang or error unexpectedly |
| Embedding model unavailable | Confirmed graceful: `_backend_failed` sticks for the process, falls back to lexical-only retrieval (`embedding_runtime.py:8-13,50-55`) | `KEEP` |
| Reranker/NLI model unavailable | Both are already optional in the legacy path (reranker off by default; NLI only used in the multi-source path with the legacy mechanical verifier as the always-available fallback) | `KEEP` |
| Worker crash | Tested, 23/24 recovery confirmed (§9) | `KEEP`, chase the 1/24 |
| Disk full | **NOT FOUND** — no explicit handling or test for the local filesystem storage running out of space | `IMPROVE`, P2, or moot once §5.2 (S3 storage) ships — a local-disk-full scenario becomes Amazon's/the object-store provider's problem to signal cleanly instead |
| Corrupted document / malformed PDF | Magic-byte validation at upload (`validation.py:49-89`) catches type mismatches; OCR has a 120s subprocess timeout (`parsing.py:832`) | `KEEP` — reasonable coverage; no page-count/decompression-bomb cap found, which `ops/production/README.md:60-70` documents as an explicitly accepted residual risk after evaluating and rejecting ClamAV (its own reasoning: a signature scanner doesn't address parser-exploitation risk, which is the real threat model here) — `KEEP` that documented decision, it was made deliberately, not missed |
| Migration failure | `alembic upgrade head` runs on every deploy; no `downgrade`-based rollback exists anywhere — the documented rollback path is `git checkout` + **restore from backup**, not a schema downgrade (`ops/production/README.md:405-408`) | `MEASURE FIRST` / **P2**: this means a bad migration's recovery time is bounded by backup-restore time, not by a fast `alembic downgrade`. Given the clean migration history (§6.9), this hasn't bitten yet, but it's worth deciding whether that's the permanent intended posture (restore-from-backup as the *only* migration rollback path) or worth adding `downgrade()` implementations to future migrations as a faster first line of defense |
| Deployment failure | `ops/deploy.sh` polls `/health` up to 20×1s after restart before considering the deploy complete; `flock`-serialized so two deploys can't race (`deploy.sh:39-44`) | `KEEP` — reasonable; see §16 for the restart-in-place outage window, which is a separate, already-documented, accepted trade-off |
| Process restart | `Restart=always` on the worker unit (`legalmind-worker.service:24`); API unit's restart policy is **NOT FOUND** in-repo (no committed unit file) | `IMPROVE`, P1: commit the `legalmind-api.service` (and frontend) unit files to the repo. Their absence means this review cannot verify the API process's own crash-restart policy, resource limits, or systemd hardening directives from source — only from a README's prose description. Given `ops/production/legalmind-worker.service` sets real hardening (`NoNewPrivileges`, `PrivateTmp`, `MemoryMax`, per README:42), the API unit almost certainly has equivalent settings **in production** — but "almost certainly, per a README" is exactly the gap rule 23 warns about (verify, don't assume) |

**Retry storms**: no retry loops exist anywhere on the Ask path (§10.1), so there is no retry-storm risk from the *application* today — the absence of retries is, in this one specific way, protective. If a retry is added per the §10.1 recommendation, it must be bounded (one retry, not a loop) to avoid introducing exactly this risk.

---

## 11. Security Architecture Review

Overall assessment: **this is the strongest area of the codebase**, and the evidence supports it rather than just the documentation's own claims about itself.

### 11.1 Authorization enforcement — `CONFIRMED`, `KEEP`

A single `Guard` object, dependency-injected via FastAPI's `Depends()`, is the enforcement boundary for every route touching a legal/document object. Route-by-route coverage was checked file by file: every router's route count matches its Guard/Principal dependency count, with the only exceptions being the three genuinely pre-authentication routes in `auth.py` (`/login`, `/oidc/start`, `/oidc/callback`) which touch no legal object and correctly have no Guard. **No route was found relying on authentication alone without an explicit object-level permission check.**

### 11.2 Department-scoped isolation — `CONFIRMED`, one real finding

Single-object reads share one function (`same_department()`/`contract_read_basis()`, `authorization.py:72-106`) — no drift risk there. **List/collection endpoints re-implement the department filter three separate times** (`contracts.py:89-112`, `counterparties.py:108-130,91-105`, `reviews.py:44-84`) — each an independent `M.User.department_id == guard.department_id` join.

- **PROBLEM**: three independent implementations of one locked rule is a drift risk — a future change to the rule (e.g. a department hierarchy) has to be applied in three places, and a mistake in any one is an information-disclosure bug (a list that shows a row a direct GET would correctly 404 on is the definition of an IDOR).
- **WHY THIS IS ALREADY PARTIALLY MITIGATED**: the code's own comments (`reviews.py:47-49`) show the team is aware and relies on a cross-check test asserting the list and the single-object check cannot disagree. This is a real, working mitigation — not a blind spot — but it is a test-enforced invariant standing in for a structural one.
- **OPTIONS**: (a) extract one shared `department_scoped(query, guard)` query-builder function used by all three list endpoints; (b) leave as-is, rely on the existing cross-check tests, add a fourth if a new list endpoint appears.
- **RECOMMENDED**: (a), P2. Not urgent (the cross-check tests are real protection), but a clear DRY win the next time any of these three files is touched for another reason — consistent with this project's own stated preference (rule: DRY always, grep for an existing helper before writing a new one).
- **IMPLEMENTATION PLAN**: a shared function in `security/authorization.py` alongside `same_department()`, taking a base query and returning it filtered; the three call sites swap their inline joins for a call to it.
- **VALIDATION TEST**: the existing cross-check tests continue to pass unchanged — they'd now be testing that the *same* function used by both paths, rather than two similar-but-independent ones, agree (a strictly stronger guarantee).

### 11.3 RAG retrieval authorization — `CONFIRMED`, `KEEP` — this claim was verified against the code, not just asserted

The documentation's claim (`AM-45` r1: "stages 3 and 7 are code, never a prompt") was checked directly against the SQL, not taken on faith. Confirmed: authorization is a `WHERE` clause inside the same query as the candidate search, on **both** the lexical and vector branches (`store.py:251-329,786-872`), with an explicit design comment stating the reasoning ("post-filtering would let result counts, ranking or latency reveal the existence of a chunk in a document the requester may not read," `store.py:253-264`) — this is not just correct, it shows awareness of the *timing/count side-channel* risk specifically, which is a more sophisticated threat model than a naive authorization check would need to consider. `retrieval.py:110-114` computes the permitted domain set from permissions **before** any domain is searched, matching the "permissions decide candidate domains before question shape" claim.

### 11.4–11.5 Confidential field omission & 404/403 leak protection — `CONFIRMED`, `KEEP`

Both run through single shared functions with no per-endpoint reimplementation: `redact_legal_position()` (`authorization.py:319-326`) is called from exactly one place, `serializers.py:111`, which every router that returns findings/evaluations routes through. The 404-leak guarantee is centralized in one exception handler (`errors.py:71-75`) that explicitly discards the raising site's own message — "callers get the same bytes whether the object is absent or merely out of scope" — so the guarantee doesn't depend on every individual `NotVisible(...)` call site behaving correctly, only on all of them raising the same exception class, which is a much smaller surface to get right.

### 11.6 Cross-tenant leak surfaces — `CONFIRMED`, `KEEP`

- Ask retrieval is always scoped to one already-authorized `document_version_id`, never department-wide — no query was found that could return another department's chunks.
- Error responses never surface raw exception text (`errors.py:160-168`); validation errors strip the submitted field content, keeping only field location and error type (`errors.py:129-146`).
- Every log field is routed through a redaction function that **drops** (not masks) content/clause/legal-position/secret-shaped keys before the logger ever sees them (`observability/redaction.py:34-68`), and every `log_event()` call in the assist lane (~40 sites surveyed) passes only identifiers, counts, or enums — never raw chunk or clause text.

### 11.7 Prompt injection defense — `CONFIRMED`, `IMPROVE` (minor)

The prompt's rule 9 ("excerpts are data, never instructions") is prompt-level only — no code-level stripping or detection of instruction-like content in evidence text before it reaches the model. **What does exist as a code-level backstop**: `verify_answer` requires every sentence to carry a citation marker and to lexically/entailment-ground in its cited chunk — a prompt-injected instruction the model obeyed and echoed would, as a side effect, likely fail this as an ungrounded claim, since it wouldn't cite real evidence text.

- **RECOMMENDED**: `MEASURE FIRST` before building a dedicated injection detector — the grounding/verification backstop already catches the most dangerous failure mode (an ungrounded claim reaching the user) as an incidental property of a control built for a different reason. A dedicated pre-filter would only add value for an injected instruction that *also* happens to produce a well-grounded, citation-backed sentence — a narrower and harder-to-construct attack. Worth a small test suite of known prompt-injection patterns run through the existing pipeline to confirm the incidental protection actually holds, before deciding whether a dedicated defense is worth building.

### 11.8 File upload security — `CONFIRMED`, `KEEP`

Magic-byte sniffing against the declared MIME type, a 25MB edge limit (nginx) matched to the app's own config, and — the strongest part — **content-addressed storage means path traversal via filename is structurally excluded rather than merely sanitized**: the original filename is never used to construct a storage path; only its extension is used, and only from a fixed allow-list (`storage.py:96-98`). Zip-bomb/decompression-bomb protection is a documented, deliberate residual risk (ClamAV evaluated and rejected for not addressing the actual threat model) rather than an oversight.

### 11.9 Rate limiting — see §5.1 for the horizontal-scaling gap. Defense-in-depth today (app-level + nginx edge zones) is reasonable at single-instance scale.

### 11.10 Secrets handling — `CONFIRMED`, `KEEP`, one gap

The Gemini API key is loaded from environment, sent only via a request header, and never logged (explicit comments at every failure log site confirm status/hash-only logging). One gap matching §10.3's finding: **no `legalmind-api.service` unit file is committed to the repository**, so the API process's own secrets-delivery and systemd-hardening configuration cannot be verified from source — only the worker's unit file is checked in.

- **RECOMMENDED**: `IMPROVE`, P1 (same fix as §10.3's process-restart-policy gap — one action closes both).

---

## 12. Observability Review

### 12.1 Logging — `CONFIRMED`, mixed

Structured JSON logging with a real correlation mechanism (`request_id` generated/validated per request, threaded explicitly as a parameter through most of the Ask pipeline — `service.py`, `planner.py`, `rescue.py`, `rerank.py`, `generation.py`, `answer.py` all accept and log it) is a solid foundation. 53.3-mandated redaction is structurally enforced (every field passes through `redact_fields()`, not an opt-in per call site).

**The gap**: `assist/retrieval.py` — the stage that does the actual candidate search across all domains — **has zero observability instrumentation**. No `log_event` import, no latency, no candidate counts, nothing. `verify.py` logs an unavailability warning but no per-request latency; `rerank.py` logs a reordering event without duration. Only `generation.py` (the Gemini call) computes and logs real latency numbers.

- **WHY IT MATTERS**: this is the direct answer to the brief's observability question — *"what happened to this request?" from one trace* — today, for the retrieval stage specifically, the answer is "nothing is recorded." If a slow Ask response is reported, the `request_id` ties together generation latency but not retrieval latency, which is very likely to be a real contributor (multiple domain searches, each with its own embedding call, per request).
- **RECOMMENDED**: `IMPROVE`, **P1**. Add a `timed()` context manager (the pattern already exists and is already used elsewhere — `analysis/service.py:171,271`, `api/app.py:80` — this is not a new pattern, just an unapplied one) around retrieval, rerank, and verify stages, logging `request_id`, stage name, and `duration_ms`, matching what `generation.py` already does. This is a small, contained, low-risk change with a clear payoff: it's the single cheapest fix in this review relative to its diagnostic value.
- **IMPLEMENTATION PLAN**: wrap the relevant calls in `service.py`'s stage orchestration (which already has a `_stage()` helper pattern visible for the statute-generation path, `service.py:629-633`) with `timed()`, logging into the same `_TRACE` contextvar structure already used for `assist.ask.trace`.
- **VALIDATION TEST**: assert `assist.ask.trace` (or a new per-stage log line) includes `retrieval_ms`, `rerank_ms`, `verify_ms` fields after this change, where today it only has `gemini_calls`/generation timing.
- **ROLLBACK**: pure logging addition, no behavior change, trivially revertible.

### 12.2–12.4 Metrics / Tracing / Alerting — `CONFIRMED absent`, and deliberately so

No metrics backend (Prometheus, StatsD, OpenTelemetry metrics), no distributed tracing, no alerting/dashboard configuration exists anywhere in the repository. This is not an oversight the code is silent about — `observability/metrics.py`'s own docstring states it "deliberately holds classification and naming, not a metrics backend" and explicitly cites locked decision 53.6 ("the monitoring stack" as "NOT YET SPECIFIED"). The module already defines signal names and an alertable-signal allowlist (`ANALYSIS_SIGNALS`, `ALERTABLE_SIGNALS`, `metrics.py:32-56`) — the naming/classification layer is built; only the backend that would consume it is missing, by a standing, named, locked decision.

- **RECOMMENDED**: `MEASURE FIRST` — this review does not recommend picking a metrics/tracing/alerting stack. That is squarely the kind of decision rule 4 and 53.6 reserve: "the behavior isn't specified, stop and ask." What this review *can* say: the naming layer (`metrics.py`) is already built in a way that would slot cleanly into whichever backend is eventually chosen (it already separates "what to measure" from "where it goes"), so **choosing a backend later does not require rearchitecting anything already built** — closing 53.6 is a decision to raise with the owner when observability at the current single-instance, single-user scale genuinely starts to hurt, not before.

### 12.5 Correlation, restated

One flat `request_id` per request is currently the only cross-cutting identifier, and it is a real, working mechanism, propagated through most (not all, per §12.1) of the pipeline. This is sufficient for "grep the logs for this request_id" debugging today; it would not by itself answer "trace this request across the API, worker, and Gemini call with timing at each hop" — that is what a tracing backend would add on top of the identifier that already exists. The identifier is the right foundation to build on when 53.6 is decided.

---

## 13. Performance Engineering — `MEASURE FIRST` throughout; no load-testing capability exists (§17) to measure with today

This section is honest about its own limits: **without a load-testing tool anywhere in the repository (confirmed absent, §17), every latency/throughput number below is inferred from code structure, not measured.** That distinction is preserved rather than blurred.

**Structural facts that bound performance, confirmed from code:**

- Nearly all route handlers are sync `def`, running in Starlette's threadpool rather than on the async event loop (only 1 of 14+ handlers surveyed is `async def`) — the practical concurrency ceiling per process is the threadpool size, not full async concurrency. Threadpool size itself is **not configured anywhere** in this repo (library default applies) — **NOT FOUND**.
- ONNX model sessions (embedding, rerank, NLI) have **no explicit `intra_op`/`inter_op` thread configuration** — ORT's own process-default threading applies, meaning three CPU-bound model sessions in one process compete for cores with no deliberate allocation between them.
- Per-request cost profile for a typical Ask (legacy path, answered case): **roughly 10–15 DB round-trips**, 1 embedding call per domain searched (typically 2–4 domains), 0–1 rerank calls (off by default), 0–1 batched NLI calls (multi-source path only), and **1–5 Gemini calls** depending on which fallback paths engage.

**RECOMMENDED performance budgets** (targets to measure against once load-testing exists, not measured numbers):

| Stage | Target (to validate, not yet measured) | Rationale |
|---|---|---|
| DB query (single) | < 50ms p95 | Standard OLTP expectation; indexes generally match query patterns (§6.5) so this should already hold |
| Embedding call (single query) | < 100ms p95 | Small model, CPU-bound, batched at 16 |
| Retrieval (one domain, full hybrid search) | < 200ms p95 | Currently **unmeasured** — this is exactly the gap §12.1 closes |
| Rerank (when on) | < 500ms p95 at depth 30 | Documented measurement already exists in code comments (15.2s→10.2s over 587 pairs from batching-order alone) — this is a stage that has already been tuned with real numbers, just not wired into per-request logging yet |
| Gemini call | < 3s p50, 60s hard ceiling | Provider-dependent, outside this system's control beyond the timeout/retry/circuit-breaker recommendations in §10.1 |
| Full Ask request (document path, answered) | < 5s p95 | Composite of the above; **the real number depends heavily on how many of the 1–5 possible Gemini calls actually fire**, which is itself worth measuring before setting a hard target |

- **Do not optimize speculatively.** Per the brief's own instruction: find the real bottlenecks first. The two structural things worth fixing regardless of measurement (because they're correctness/scalability issues, not just performance ones) are §6.4 (transaction scoping) and §5 (horizontal-scaling blockers) — both already covered above. Beyond those, this review recommends building the retrieval-stage logging (§12.1) *first*, then using the real numbers it produces to decide what, if anything, in this table actually needs work.

---

## 14. Frontend Architecture Review

### 14.1 API request patterns — `CONFIRMED`, `IMPROVE` (minor, low urgency)

No client-side caching or request deduplication library (no SWR/React Query) — a plain `fetch` wrapper is "the only data path" (`lib/api.ts:1-14`). `AbortController` is wired for the Ask endpoint's 150-second client-side timeout, not for cancel-on-unmount or cancel-on-rapid-navigation of ordinary GETs; several loading effects instead use a manual `cancelled` boolean flag to ignore stale responses after unmount — functionally similar to cancellation for the "don't apply a stale result" purpose, but doesn't actually cancel the in-flight network request (a smaller inefficiency, not a correctness bug).

- **RECOMMENDED**: `MEASURE FIRST`. No evidence gathered shows duplicate-request waste is currently a measured problem (no request-volume data exists to check against, §12). Not worth adopting a data-fetching library for its own sake — this is exactly the kind of "add a dependency because it's common" the brief warns against (§18). If a real duplicate-request pattern is ever observed, the fix is targeted (an `AbortController` on the specific hot path), not a library swap.

### 14.2 Conversation/document rendering — `CONFIRMED`, `IMPROVE` (P2, only if a real symptom appears)

No virtualization/windowing anywhere — both the conversation transcript and the document panel render every fetched row via a plain `.map()`. The document panel *does* fetch progressively from the server (100-row pages, fetched until the total is reached) — so the risk is specifically about *DOM* size at high turn/row counts, not network payload size.

- **Direct answer to the brief's question**: *"Can this application remain responsive after a user has 100+ conversations and very long chats/documents?"* — 100+ *conversations* is not a rendering risk (each conversation is loaded independently, and the conversations list itself is presumably paginated like other list endpoints, §6.8's pattern). A single *very long* chat (hundreds of turns) or a large document (thousands of evidence rows, even though fetched in pages) rendered entirely into the DOM at once **is** a plausible responsiveness risk, but this review found no test or measurement confirming it's a real problem at current usage, only that the structural risk exists.
- **RECOMMENDED**: `MEASURE FIRST`. Virtualization is real engineering effort and a real dependency addition (`react-window` or equivalent) — justified once a document or conversation of realistic size is actually shown to cause jank, not before. Given today's single-user usage, this is very unlikely to be the actual bottleneck anyone hits first.

### 14.3 Race conditions — `CONFIRMED`, one asymmetry worth closing

`AskWorkspace` correctly implements the classic "stale response" guard (captures `activeId`/`epoch` before the async call, checks staleness after, silently drops a late answer if the user navigated away). `AskDock` does not have the equivalent guard — see §9's table entry for the full write-up and recommendation (P2, small frontend fix, port the existing pattern).

### 14.4 DecisionControl / EscalateControl — `CONFIRMED`, one real asymmetry against CLAUDE.md's own description

`DecisionControl` implements both halves of the "bespoke no-optimistic-UI + 409-handling" description precisely: waits for server confirmation before any UI update, and on a 409 freezes the form with an explicit "Refresh to see the latest decision" recovery action. `EscalateControl` implements only the no-optimistic-UI half — it has **no explicit `isConflict`/409 handling**, falling through to a generic error banner instead.

- **WHY IT MATTERS**: CLAUDE.md describes both components as implementing this pattern; the code shows only one of the two actually does. A concurrent escalate-and-withdraw race (two department members acting on the same escalation) would surface as a generic error rather than the same clear "someone else already acted, here's what to do" recovery flow `DecisionControl` gives.
- **RECOMMENDED**: `IMPROVE`, **P1** (correctness/UX gap on a legal-workflow action, not just a style inconsistency — matches the severity class of the other P1 concurrency findings in §9). Port `DecisionControl`'s `isConflict` check and frozen-state recovery pattern into `EscalateControl` — the pattern already exists in the codebase, this is applying it a second place, not designing something new.
- **IMPLEMENTATION PLAN**: `EscalateControl.tsx` — add the same `outcome.kind === "conflict"` branch and frozen-form treatment `DecisionControl.tsx:51,97-100` already has, wired to `api.escalate`/`api.withdrawEscalation`'s existing `isConflict` check (`lib/api.ts:107`, already defined, just not consumed here).
- **VALIDATION TEST**: a test simulating a concurrent escalate/withdraw pair, asserting the loser sees the frozen-conflict UI rather than a generic error — the equivalent test presumably already exists for `DecisionControl` and can be mirrored.
- **ROLLBACK**: frontend-only, no data/schema involved, trivially revertible.

### 14.5 Bundle size — `CONFIRMED`, `KEEP` / `MEASURE FIRST`

No `next/dynamic` code splitting found; Next.js's own automatic route-based splitting still applies. No evidence gathered shows bundle size is currently a measured problem. `MEASURE FIRST` before adding manual splitting — this is speculative optimization territory without a number showing it's needed.

---

## 15. Document-Processing Architecture

Covered substantively in §5.2 (storage), §9 (concurrency/idempotency), §10.3 (corrupted-file handling), §16.2 (sync-vs-async dispatch). One additional point worth isolating:

**Document processing does not block normal user requests — with one caveat.** OCR always runs in a background daemon thread inside the API process, never inline in the request path (§2's flow diagram) — so a slow OCR job doesn't hold up the upload response. But indexing (chunking + embedding) **does** run inline, synchronously, in the request when no Celery broker is configured (`dispatch.py:126-179,148-151`) — and the code's own comment explicitly flags embedding-inline as "a way that embedding generation will not be [cheap]," implying this fallback, while functionally correct, is a real latency cost when it engages. Confirmed: production is *supposed* to run with a broker configured (the preflight tool is documented to fail a deployment that doesn't), and evidence from the workers research pass shows Redis + the worker unit are in fact installed and verified running in production as of 2026-09-14. So this specific risk is **currently closed in production**, but worth flagging as a deployment-configuration dependency rather than a structural guarantee — a misconfigured `LEGALMIND_BROKER_URL` on a future deployment would silently fall back to the slower, request-blocking path rather than failing loudly.

- **RECOMMENDED**: `IMPROVE`, P2: make the preflight check (already documented as existing) a hard startup failure in production mode, not just a deploy-time advisory, so this misconfiguration can't silently ship. **NEEDS MEASUREMENT**: confirm the preflight tool's actual current behavior (this review did not independently verify `deploy/preflight.py`'s enforcement strength, only that it's documented to check this).

---

## 16. Deployment / Operations Review

### 16.1 Current shape — `CONFIRMED`

Single host, systemd-managed: `legalmind-api` (uvicorn, unit file not in repo), `legalmind-worker` (Celery, unit file in repo, `--concurrency 2`), `legalmind-frontend`, `nginx`, Redis, PostgreSQL — all on one machine per `ops/production/README.md:11-16`. nginx has a single hardcoded upstream for each service (`proxy_pass http://127.0.0.1:8000` / `:3000`), no `upstream {}` block with multiple servers — confirming there is no load balancer in front of multiple instances today.

### 16.2 Zero-downtime — `CONFIRMED`, `KEEP` the current accepted trade-off

Every deploy restarts both the API and frontend processes in place (`systemctl restart`), causing a documented 2–3 second window where requests get `ECONNREFUSED` — masked with an `unavailable.html` page at the nginx layer, not eliminated. This is explicitly acknowledged in the repo's own operations documentation as an accepted trade-off, with the stated fix (a blue-green deployment rig) named but deliberately not built: "only its appearance is fixed here... a blue-green rig is the fix if that window ever becomes unacceptable" (`ops/production/README.md`).

- **RECOMMENDED**: `KEEP` as-is. This is a correctly-scoped, already-considered decision, not a gap this review is surfacing for the first time. `MEASURE FIRST` before building blue-green: the trigger condition is deploy frequency × the 2–3 second window's actual user impact — at today's deploy cadence and user count, a few-second window during a deploy is very unlikely to be the thing worth engineering effort. Worth revisiting once (a) deploys become frequent enough that cumulative downtime matters, or (b) a second API instance exists for other reasons (§5), at which point blue-green becomes close to free (route around the instance being restarted).

### 16.3 Migrations / rollback — see §10.3 for the full write-up (no `downgrade`-based rollback exists; restore-from-backup is the documented path).

### 16.4 Backups — `CONFIRMED`, mostly `KEEP`, one gap worth closing

Two-stage backup (local `pg_dump`, 14-day retention; GPG-encrypted upload to S3-compatible storage, 90-day retention), and — genuinely strong — a **full restore-and-verify run was actually performed and documented** (2026-09-14, into a scratch database, with a pass/fail table covering dump/verify, encryption, integrity, restore, and retention). This is real evidence of a tested recovery path, not just a backup script that's never been exercised.

- **The one gap, explicitly flagged by the same documentation**: the off-server upload/download leg specifically was **not** exercised end-to-end in that test ("credentials not yet supplied"). So the backup *creation* and *local restore* paths are proven; the *off-site retrieval* path — the one that matters most in a scenario where the primary host itself is lost — is not.
- **RECOMMENDED**: `IMPROVE`, **P1**. Re-run the restore test with the off-server leg included now that credentials exist (the same research pass found `s3_object.py` fully implemented and referenced as already in use for backups) — this closes the single most important untested link in an otherwise well-tested recovery chain.
- **Also NOT FOUND**: the backup schedule itself (cron entry / systemd timer) is not committed to the repository — it's documented in prose as configured manually on the host. `IMPROVE`, P2: commit a systemd timer unit (matching the pattern already used for the worker) so the schedule is version-controlled and auditable rather than tribal knowledge on one host.

### 16.5 CI/CD — `CONFIRMED`, `KEEP`

15 well-organized jobs covering lint/types, schema invariants, an authorization matrix (release-blocking), golden-corpus conformance, determinism, append-only-ledger integrity, frontend checks, browser/Playwright tests, post-migration reproducibility, independent verification, the full suite, dependency/container security scanning, and visual regression. This is a genuinely thorough gate. Deployment is confirmed fully manual (`sudo legalmind-deploy` or a direct `ops/deploy.sh` run) — CI never triggers a deploy, which is consistent with the project's own stated posture of one owner deciding when to ship.

### 16.6 Health checks — `CONFIRMED`, `KEEP` the design, `IMPROVE` the coverage

`/health` is deliberately contentless ("a probe must not become a reconnaissance endpoint") — a considered security decision, not an oversight. No separate `/ready` endpoint checking DB/model/broker availability exists. nginx does not reference `/health` at all; it's polled only by the deploy script itself.

- **RECOMMENDED**: `MEASURE FIRST` on adding a `/ready` endpoint — genuinely useful once there is a load balancer that needs to route around an unhealthy instance (§5's trigger condition), of limited value before that, since today there's exactly one instance and nothing to route around.

---

## 17. Testing / Load-Testing Strategy

### 17.1 What exists — `CONFIRMED`

~1768 backend test functions across 114 files, all DB-backed integration-style tests (no separate pure-unit tier — every test creates a real Postgres engine via fixtures). 37 frontend Vitest files, 33 Playwright e2e specs including a dedicated visual-regression suite. Separate RAG-quality benchmark scripts (`tools/benchmark_*.py`, `rag_benchmark.py`) measure retrieval/embedding/rerank **quality** (accuracy, relevance) as distinct from the pytest suite.

**Genuine failure-mode coverage found**: Gemini failure simulation (timeout, refusal, malformed response, all via monkeypatch), a real `SIGKILL`-against-a-real-worker crash-recovery test, a no-broker-configured inline-fallback test, and a concurrent-duplicate-request test using a real second DB connection holding an advisory lock to prove a 409 rather than a duplicate run.

### 17.2 What's missing — `CONFIRMED absent`

1. **No load/performance testing tool anywhere in the repository** — no locust, k6, artillery, or custom load script. This is itself the review's cleanest finding: the system has never been measured under concurrent load, which is exactly why every performance claim in §13 is labeled `MEASURE FIRST` rather than asserted as fact.
2. **No test simulates a live database outage mid-request** — only an unrelated audit-log-immutability trigger test and a log-redaction string test surfaced in the search for this.
3. **No test simulates Redis/broker going down mid-operation** — only the "not configured at startup" case is tested, not "was up, then dropped."
4. **No test specifically distinguishes a Gemini timeout from a generic failure** — the existing simulations cover generic exceptions/unavailability without a dedicated timeout-type assertion.

### 17.3 Test matrix — what to add, prioritized

| Category | Gap | Priority | Ties to |
|---|---|---|---|
| Load | Basic concurrent-Ask load test (even a simple asyncio/threading harness hitting a staging instance) proving/disproving the §6.4 connection-pool-exhaustion hypothesis | **P0** | §6.3, §6.4 — this is the validation test those fixes need |
| DB failure | Simulated DB unavailability mid-request, asserting a clean error rather than a hang or a leaking stack trace | P1 | §10.3 |
| Broker failure | Broker up-then-down mid-operation (not just absent-at-config-time) | P1 | §10.3 |
| Concurrency | The Ask-ordinal race (§9's first row) — two concurrent requests on one conversation, asserting a clean 409 rather than an unhandled 500 once that fix ships | P1 | §9 |
| Gemini | A dedicated timeout-type test, separate from the generic-failure tests already present | P2 | §10.1 |
| Frontend | `AskDock` staleness-guard test, once §14.3's fix ships | P2 | §9, §14.3 |
| Rate limiting | Two-instance rate-limit-sums-correctly test, once §5.1's Redis-backed limiter ships | (blocked on §5.1 shipping) | §5.1 |

**RECOMMENDED**: build the load-testing capability (item 1) **before**, or at latest alongside, the §6.4 transaction-scoping fix — it is the only way to actually confirm the fix worked rather than trusting code-reading alone. A minimal harness (even a simple concurrent-request script against a staging environment, not a full k6/locust adoption) is enough to validate the specific hypothesis in §6.3/§6.4; a fuller load-testing tool adoption can wait until there's a second scenario that needs it (rule 18's "only recommend infrastructure the workload and evidence justify" applies to test tooling too).

---

## 18. Architectural Trade-offs — what this review explicitly does NOT recommend, and why

Per the brief's own instruction not to reach for these by default:

| Not recommended now | Why not | Trigger condition that would change this |
|---|---|---|
| Redis for anything beyond the existing Celery broker | Nothing measured shows a caching need (§7); the one clear future candidate (Constitution/statute/company-standard chunk caching) has no latency data yet because retrieval isn't even logged (§12.1) — fix that first, then decide | A measured retrieval-latency contribution from these specific reads, once §12.1 ships |
| Kafka / a second message queue | Celery + Redis already handles the one background-job need (analysis, indexing) correctly, including crash recovery (§9) | A genuinely new workload shape (e.g. event streaming, fan-out to many consumers) that Celery's model doesn't fit — nothing in this review suggests one exists |
| Kubernetes / container orchestration | Single-host systemd deployment is working, well-tested (CI, backup/restore), and the actual blockers to running more than one instance (§5) are three small code fixes, not an orchestration problem | Once §5's three fixes ship AND a real second-instance need exists (redundancy or load) — orchestration is worth it for managing *many* instances, not for going from 1 to 2 |
| Microservice decomposition | Locked 38.26 already forbids this in V1 ("api and worker are the SAME IMAGE with different commands"); nothing in this review found a scaling or team-boundary problem that decomposition would solve — the RAG lane's schema separation (§6.1) already gives the main benefit (blast-radius isolation) without the operational cost of separate services | Would need an explicit locked-decision change (rule 6) — not something this review recommends raising |
| Read replicas | No evidence of read-heavy contention distinct from the write path; the actual measured-or-inferred bottleneck (§6.3/§6.4) is connection *pool sizing and lifecycle*, not read/write split | A measured read-query latency problem that pool-sizing/transaction-scoping fixes don't resolve |
| A separate vector database | pgvector's exact-KNN approach was explicitly measured and kept (§6.2) — this is already the "measure, don't assume" outcome the brief asks for, arrived at independently before this review | Corpus growth past what exact scan handles well (§6.2's own trigger condition) |
| Another RAG framework | Already assessed in a prior session (see repository memory on this exact question) — the custom pipeline's authorization-in-the-query, code-not-prompt routing, and single-egress-seam properties are not things an off-the-shelf framework provides, and are the properties the locked decisions actually require | None identified |
| A different/additional LLM model | Gemini Flash is a locked choice (`AM-30`) with a released gate (`AM-31`); nothing in this review touches model selection | Would need an explicit locked-decision change |

---

## 19. Current vs. Future Architecture

**A. Current**: single host, single instance of everything, systemd-supervised, no cache, no metrics/tracing, local disk storage, in-process rate limiting, a DB transaction held open across every Gemini call.

**B. Problems discovered** (this document, §5–§17): three horizontal-scaling blockers (§5), one high-severity connection-pool/transaction-scoping issue (§6.3–6.4), one observability blind spot on the highest-value stage to instrument (§12.1), one frontend concurrency-handling asymmetry on a legal-workflow control (§14.4), and several smaller, already-triaged items (P2/P3 throughout).

**C. Immediate fixes** (P0/P1, do now, all code-only, no infrastructure change): §6.4 (stop holding the DB transaction across Gemini calls), §6.3 (explicit pool sizing), §12.1 (retrieval-stage logging), §14.4 (EscalateControl 409 handling), §5.1+§5.2 (Redis-backed rate limiter + S3 storage backend, unblocking horizontal scaling), §16.4 (re-test the off-server backup leg), §9's ordinal-race fix, §10.3/§11.10 (commit the missing API systemd unit file).

**D. Near-term architecture** (after C ships, still single-instance): same shape as today, but with the P0/P1 fixes in place — a DB transaction that's held for milliseconds not up to 60 seconds, a rate limiter and storage backend that don't structurally block a second instance whenever one is actually needed, and retrieval-stage latency visible in logs.

**E. Future scaling architecture** (only once a trigger condition in §24 actually fires): 2+ API instances behind nginx's own `upstream {}` block (no new load balancer technology needed — nginx already does this), the now-external rate limiter and S3 storage making that safe, a `/ready` endpoint for the LB to route around an unhealthy instance, and — separately, gated on its own trigger — a metrics/tracing backend once 53.6 is decided.

**F. Trigger conditions** — see §24, consolidated in one place rather than scattered.

---

## 20. Recommended Target Architecture

No new component types. The target is the current architecture with the P0/P1 fixes applied and, only once triggered, a second API instance:

```
Browser → nginx (upstream {} with 2+ backends, once triggered)
            → Next.js (unchanged)
            → FastAPI × N  (N=1 today; N=2+ once §5's fixes ship AND triggered)
                → PostgreSQL (pool sized deliberately, §6.3; transactions
                  no longer held across Gemini calls, §6.4)
                → Redis (Celery broker, AND rate-limit state once §5.1 ships)
                → S3-compatible storage (once §5.2 ships; local disk
                  remains the single-instance/dev default)
                → Gemini (pooled HTTP client, §10.1; still the sole egress)
            → Celery worker × N (already safe to scale, §5 — no change needed)
```

Nothing here is a new technology. Rule 19 ("no new technologies, dependencies, or services without approval") is satisfied by construction — every component in this diagram already exists in the codebase or in `ops/production/s3_object.py`'s proven pattern.

---

## 21. Phased Implementation Roadmap

Each phase is independently shippable and independently valuable — none depends on a later phase to be worth doing.

### Phase 1 — P0: stop the connection-pool starvation risk
- **Objective**: a slow or down Gemini call can no longer degrade every other endpoint in the application.
- **Files**: `backend/legalmind/assist/service.py` (session-lifecycle restructure, §6.4), `backend/legalmind/db/session.py` (explicit pool config, §6.3).
- **Architecture change**: split the Ask request's DB session into a pre-generation and post-generation phase; make pool sizing an explicit, documented decision instead of a library default.
- **Migration**: none.
- **Test strategy**: new concurrent-load test proving other endpoints stay responsive while Ask requests wait on a slow Gemini test-double (§17.3, table row 1).
- **Performance measurement**: before/after connection-hold-duration for an Ask request.
- **Security validation**: none touched.
- **Rollback**: code revert, no data involved.
- **Risk**: low — mechanical refactor of session lifecycle, well-understood pattern.
- **Dependency**: none — can ship first, independently.

### Phase 2 — P1: close the retrieval observability gap
- **Objective**: `request_id` ties together every stage of an Ask request, not just generation.
- **Files**: `backend/legalmind/assist/retrieval.py`, `rerank.py`, `verify.py`, using the existing `timed()` helper.
- **Test strategy**: assert new latency fields appear in `assist.ask.trace`.
- **Risk**: near-zero — pure logging addition.
- **Dependency**: none, but delivers the most value if it ships before/alongside Phase 1's validation test, since it's how you'd measure the "before" state.

### Phase 3 — P1: unblock horizontal scaling
- **Objective**: a second API instance can be safely added when needed, without a structural correctness break.
- **Files**: `api/ratelimit.py` (Redis-backed limiter, §5.1), `ingestion/storage.py` + `api/storage.py` (S3 backend, §5.2).
- **Migration**: none (content-addressed keys are backend-agnostic).
- **Test strategy**: two-instance rate-limit-sums-correctly test; S3 backend parity test against the existing local-storage test suite.
- **Risk**: low-medium — S3 backend is new code, but follows an already-proven pattern in the same repo (`ops/production/s3_object.py`).
- **Dependency**: none — this phase is valuable even if a second instance is never provisioned, because it also removes local disk as a single point of failure for every document in the system (§5.2's framing).

### Phase 4 — P1: frontend/operational cleanup
- **Objective**: close the `EscalateControl` 409 gap (§14.4), the ordinal-race unhandled-500 (§9), the missing API systemd unit file (§10.3/§11.10), and the untested off-server backup leg (§16.4).
- **Files**: `frontend/src/components/workspace/EscalateControl.tsx`, `backend/legalmind/assist/service.py` (ordinal retry), `ops/production/legalmind-api.service` (new file), a re-run of the backup-restore test.
- **Risk**: low — each is small and independent; can ship as four small changes rather than one phase if preferred.
- **Dependency**: none.

### Phase 5 — P2/P3: everything else in this document
- Gemini connection pooling and a bounded single retry (§10.1), a shared department-scope query builder (§11.2), the `AskDock` staleness guard (§14.3, §9), a `/ready` endpoint (§16.6) — all independently small, all deferred behind the trigger conditions named where they appear above, none blocking any earlier phase.

---

## 22. Trigger-Based Scaling Plan (consolidated)

| Decision | Do NOT do this yet | Trigger condition |
|---|---|---|
| Add an ANN index to pgvector | It was measured and correctly rejected already (§6.2) | A single document's chunk count regularly large enough that exact-scan latency shows up in the (now-logged, post-Phase-2) retrieval trace |
| Partition/archive `audit_events` | No row-count evidence of a problem (§6.7) | Measured row-count growth and a measured sequential-scan cost on `action`-filtered queries |
| Add a Constitution/statute/company-standard chunk cache | No latency evidence yet (§7) | Retrieval-stage latency (now visible post-Phase-2) shows these specific reads as a real contributor |
| Run a second API instance | Blocked outright today (§5), and no load evidence justifies it yet | Phase 3 ships AND real concurrent-user load approaches what one instance's threadpool/pool can serve (measure via Phase-1's new load test) |
| Build a circuit breaker for Gemini | Fixing §6.4 removes most of the damage a down Gemini can do; a breaker only saves latency on top of that | Phase 1 ships AND Gemini outages are observed often enough that the remaining 60s-per-request cost during an outage is measurably painful |
| Choose a metrics/tracing/alerting backend | Locked 53.6, explicitly NOT YET SPECIFIED | An owner decision to close 53.6 — raise it once observability gaps (beyond Phase 2's logging fix) genuinely block operating the system, not before |
| Blue-green deployment | Current restart-in-place window is a documented, accepted trade-off (§16.2) | Deploy frequency × window impact becomes measurably painful, OR a second instance exists anyway (making it nearly free) |
| Virtualize conversation/document rendering | No measured jank (§14.2) | A real conversation or document size is shown to cause frontend responsiveness problems |
| A dedicated prompt-injection detector | The grounding/verification backstop already catches the dangerous case as a side effect (§11.7) | A test suite of known injection patterns shows the incidental protection actually fails for some pattern |

---

## 23. Risks and Rollback Strategy

Every fix recommended in §21 is:
- **Code-only, no schema/migration** except Phase 3's storage-backend addition, which is additive (a new class, a new config branch) and defaults to the current behavior (`local`) unless explicitly switched.
- **Independently revertible** — none of the phases depend on a prior phase's code remaining in place to function; each can be reverted on its own.
- **Backed by a validation test named in §21** before being considered done, per this project's own working-session discipline (implement → test → measure → fix → log).

**The one genuine risk worth naming explicitly**: Phase 1's session-lifecycle split (§6.4) changes the atomicity boundary of the Ask request — the user-turn insert and the final answer/citation inserts are no longer one transaction. If the process crashes between them, a user turn could exist with no answer attached. This is flagged, not hidden: it's an acceptable, standard trade-off (§6.4's own write-up explains why), but it is a real behavior change worth a specific test (a message with no corresponding answer should render sensibly in the conversation UI, not break it) rather than an assumed non-issue.

---

## 24. "What We May Still Be Missing" — the independent second pass

Working through the brief's own checklist, pretending the system already serves 10× today's traffic:

**"What would break first?"** The DB connection pool, via the mechanism in §6.3/§6.4 — a handful of concurrent Ask requests each holding a connection for up to 60 seconds while waiting on Gemini exhausts a 15-connection default pool, and every other endpoint (not just Ask) then queues or times out behind it. This is the review's single most important finding and is fixed in Phase 1.

**"How would I know it broke?"** Today: you would not know cleanly. There's no metrics backend, no alerting, and — until Phase 2 ships — no retrieval-stage latency logged at all. You would see it as "the whole app got slow," with no log data distinguishing "Gemini is slow" from "the DB pool is exhausted" from "retrieval is slow," because only generation latency is currently logged among the Ask stages. Phase 2 closes the diagnostic half of this; Phase 1 closes the causal half.

**"How would I recover?"** A `pool_timeout` (recommended in §6.3, not currently set) would at least fail fast with a clean error instead of hanging indefinitely — today, with no `pool_timeout` set, a request waiting for a pool connection under exhaustion has no explicit ceiling beyond whatever SQLAlchemy's own default resolves to, which this review did not independently verify (**NEEDS MEASUREMENT**: confirm SQLAlchemy's default `pool_timeout` behavior in this specific setup). Recovery today would be an operator restarting the API process — which, per §16.2, is already a well-tested, fast operation.

**"Could one bad request affect everyone?"** Yes, today — exactly via §6.3/§6.4's mechanism. This is the review's core finding, addressed by Phase 1.

**"Could one slow dependency take down the whole application?"** Yes, today, via the same mechanism — a slow Gemini response (up to 60s, no circuit breaker, no retry meaning no *additional* delay from retries but also no resilience) combined with the connection held across it is a slow-dependency-takes-down-everything pattern in its purest form. Phase 1 is the direct fix.

**"Could one user's data reach another user?"** No structural mechanism found for this — §11's review (authorization baked into every retrieval query, confidential-field omission and 404-leak protection both centralized in single shared functions, redaction applied to every log field) is the strongest part of this codebase and gives real confidence here, not just documentation confidence. The one drift risk found (§11.2, triplicated department-filter logic) is already caught by cross-check tests today, and the recommended fix (extract to one function) removes even the *possibility* of future drift rather than fixing an active leak.

**"Could repeated requests create uncontrolled cost?"** Partially, yes — §10.1's findings (no per-day cost cap, only a request-count limiter; up to 5 Gemini calls possible per single Ask; a retried request with no idempotency key could double-trigger generation, §9) are the relevant gaps. None are catastrophic (the request-count limiter does bound total volume, just not total *cost* per request), but this is a real, named gap rather than a solved problem — tracked as P2/P3 items across §9 and §10.1, not urgent at today's volume but worth closing before opening the system to non-browser API clients that wouldn't have the UI-level composer-disable mitigation.

**"Could deployment/migration cause data loss?"** No mechanism found for this specifically — the append-only audit trigger (§6.7) makes a whole class of data-loss impossible at the database level, migrations have a clean history with no risky patterns found (§6.9), and backups are tested end-to-end except the off-server leg (§16.4, flagged and prioritized). The main residual risk is a bad migration's *recovery time* being bounded by backup-restore speed rather than a fast schema downgrade (§10.3) — not data loss, but a longer-than-ideal recovery window.

**"Can the system scale horizontally?"** Not today, for three specific, small, already-identified reasons (§5). All three have concrete fixes in this roadmap (Phase 3). Once those ship, yes — the harder problems (conversation state, worker coordination, RAG retrieval correctness under concurrency) were already found to be safe by design, not blockers.

**"Can the system recover without manual database surgery?"** Mostly yes — worker crash recovery is tested and works (23/24, with the 24th worth chasing per §9's table), the deploy process is tested and fast, and backups are tested (mostly). The one place manual intervention is the *only* documented path is a bad migration (§10.3) — acceptable given the clean migration history, but worth knowing it's the one scenario where "recover without manual DB work" isn't currently true.

Nothing surfaced in this second pass that isn't already captured in §5–§17 and prioritized in §21 — the independent pass confirms the earlier findings rather than adding new ones, which is itself a useful signal that the review was thorough the first time through.

---

## 25. Immediate P0/P1/P2 Findings — consolidated list

**P0**
1. DB transaction held open across every Gemini call (§6.4) — the review's central finding.

**P1**
2. Unconfigured DB connection pool (§6.3, paired with #1).
3. `assist/retrieval.py` has zero observability instrumentation (§12.1).
4. Three things block horizontal scaling: in-process rate limiter, local-disk-only storage, (§5.1, §5.2).
5. `EscalateControl` lacks the 409-handling `DecisionControl` has (§14.4).
6. The Ask-conversation ordinal race surfaces as an unhandled 500 instead of a clean 409 (§9).
7. No `legalmind-api.service` unit file committed — process-restart policy and secrets-hardening unverifiable from source (§10.3, §11.10).
8. Off-server backup leg untested end-to-end (§16.4).

**P2** (real, not urgent, all named with a trigger or a "next time this file is touched" framing)
9. Triplicated department-scope query logic (§11.2) — mitigated by tests today.
10. `AskDock` missing the staleness guard `AskWorkspace` has (§9, §14.3).
11. No bounded retry / connection pooling / circuit breaker on the Gemini call (§10.1).
12. No idempotency key on the Ask endpoint (§9).
13. Chase the 1-in-24 worker-crash-recovery gap already visible in an existing test (§9).
14. Preflight's broker-fallback check should be a hard startup failure in production, not just advisory (§15).

**P3** (documentation/framing fixes, or genuinely speculative until measured)
15. `generation.py`'s docstring implies one call per request; code allows up to 5 (§10.1).
16. Token/cost data lives in logs, not `audit_events`, despite the module docstring's framing (§10.1).
17. No per-day Gemini cost cap, only a request-count limiter (§10.1).
18. `evaluation/service.py`'s one small N+1 read (§6.6).
19. No index on `audit_events.action` alone — defer until row-count data justifies it (§6.5).

---

## 26. Architectural Decisions That Should NOT Be Changed

Explicitly `KEEP`, with the review's confidence in each:

- **pgvector exact KNN, no ANN index** — a measured decision, verified correct (§6.2).
- **The assist/locked schema separation** — a real, database-enforced guarantee of `AI-01`, not just convention (§6.1).
- **RAG retrieval authorization baked into SQL** — verified against the code directly, not just the documentation's claim (§11.3).
- **Confidential-field omission and 404-leak protection, both centralized in single shared functions** — genuinely well-built (§11.4–11.5).
- **Graceful Gemini-failure degradation, never an unhandled 500** — one of the strongest parts of the system (§10.1).
- **`CommitBeforeResponse`'s commit-before-response ordering** — closes a real, measured race (11/60 and 3/60 failure rates cited in its own commit history) — this predates and is unrelated to the §6.4 finding, which is about *when in the request* the commit happens relative to the Gemini call, not *whether* it happens before or after the response (§2, §9).
- **`DecisionControl`'s no-optimistic-UI + DB-constraint-backed 409 handling** — the reference implementation the review recommends copying elsewhere (§9, §14.4), not changing.
- **No microservice decomposition, no new message queue, no second vector database, no new RAG framework, no new LLM** — all re-confirmed by this review as correct for the system's actual, evidenced needs (§18).
- **Restart-in-place deployment with a documented, accepted outage window** — a deliberate, already-considered trade-off, not an oversight (§16.2).
- **The deliberate absence of a metrics/tracing/alerting backend** — a named, locked-decision-backed deferral (53.6), not a gap this review found by surprise (§12.2–12.4).

---

## 27. Final Architecture Decision Summary

LegalMind's architecture is sound at its foundations — the authorization model, the RAG pipeline's code-not-prompt routing discipline, the audit trail's database-enforced append-only guarantee, and the graceful-degradation behavior around its one external dependency are all built the way a security- and correctness-conscious team builds them, and this review's evidence supports that assessment rather than just repeating the codebase's own claims about itself.

The gaps are concentrated, well-bounded, and cheap: one transaction-scoping bug that is the single highest-value fix available (§6.4), three small blockers standing between "works on one instance" and "works on N instances" (§5), one observability blind spot on exactly the stage most worth instrumenting (§12.1), and a handful of smaller, already-triaged items. None require new infrastructure, a new framework, or a locked-decision change. All are named with a concrete implementation plan, a validation test, and a rollback path in §21.

**Recommended immediate next step**: Phase 1 (§21) — the transaction-scoping and pool-sizing fix — paired with Phase 2's retrieval logging, since Phase 2 is how Phase 1's fix gets measured rather than assumed. Both are small, both are independently shippable, and together they close the finding this entire review considers most important.

**Sections 1–27 were written before any change was made.** §28 is the record of the execution pass that followed the same day.

---

## 28. Execution record — 2026-09-29 (branch `feat/production-hardening`, not deployed)

Every finding in §25 was taken in the order security → correctness → scaling blockers → observability → UX → ops → cleanup. Each row says what was done, or why nothing was, with the evidence. Nothing here amends a locked decision; two items need the owner and are listed last.

### 28.1 Implemented

| § | Finding | What changed | Proof |
|---|---|---|---|
| 6.4 (P0) | Transaction held across every Gemini call | `generation.BEFORE_EGRESS` — a context-variable hook invoked once in `generate_raw`, after every gate and screen and immediately before `urlopen`. `service.ask` sets it to `_release_connection(db)`, which commits; `session.commit()` returns the pooled connection (measured: `pool.checkedout()` 1 → 0). The multi-source path now closes its savepoint before generating — `answer.prepare` was split out of `respond` so every table read happens under the savepoint and nothing touches the database after it. The analysis lane never sets the hook. | `tests/test_ask_connection_release.py`: on BOTH paths, at the moment of the (faked) network call, `db.in_transaction()` and `db.in_nested_transaction()` are both False and no `assist.db.release_skipped` warning fires; a refused call never reaches the hook; outside the Ask service the seam commits nothing. |
| 6.4 atomicity | What is no longer atomic | The reader's USER turn (and the retrieval run) commit before the call; the answer, its citations and the audit row of the call stay one transaction, committed by `CommitBeforeResponse` as before. A crash mid-call leaves a question with no answer — the state a replayed conversation already lists as a question (`get_conversation` renders messages by role, `AskWorkspace.liveTurns` draws the same shape). Stated in `_release_connection`'s docstring. | Same test asserts `["USER", "ASSISTANT"]` after the call — the post-call writes landed in the session's next transaction. |
| 6.3 (P1) | Unconfigured pool | `config.db_pool()` → `LEGALMIND_DB_POOL_SIZE` / `_MAX_OVERFLOW` / `_POOL_TIMEOUT_S`, SQLAlchemy's defaults unchanged; `db/session.py` passes them to `create_engine`. | `mypy`/`ruff` clean; full suite (below). |
| 9 (P1) | Ordinal race → unhandled 500 | `service._append_turn`: read `max(ordinal)`, insert under a savepoint, on `IntegrityError` re-read once, on a second collision raise `ConversationConflict` (`SecurityError`, 409, `CONVERSATION_TURN_CONFLICT` — the existing handler maps it). Every production turn insert goes through it; `_persist_turn` stays the raw primitive the tests use. | Same test file: a stale ordinal is retried to `[0, 1]`; two stale reads raise 409; the session is still usable and no savepoint is left open. |
| 5.1 (P1) | In-process rate limiter blocks N processes | `RedisRateLimiter` behind the existing `RateLimiter` protocol: one sorted set per key (`legalmind:ratelimit:` prefix), `ZREMRANGEBYSCORE → ZADD → ZCARD → EXPIRE` in one `MULTI`, `ZREM` on overflow — a refused attempt is never recorded, exactly as in-process. `limiter_from_env()` selects it on `LEGALMIND_RATELIMIT_BACKEND=redis`, URL from `LEGALMIND_RATELIMIT_REDIS_URL` else the broker's. **Fails open** with a `ratelimit.redis_unavailable` warning (a spend bound, not an authorization control — the project already degrades rather than fails without the broker). `redis` 6.4.0 was already present via `celery[redis]`; no dependency added. Preflight reports the backend. | `tests/test_ratelimit_redis.py`: budget shared by two instances on one Redis; window expiry frees it; connection error → allowed + warning without the key in the log fields; factory defaults. |
| 5.2 (P1) | Local-disk-only documents | `S3Storage` beside `LocalFilesystemStorage`, the four Protocol methods, keys from a shared `_object_key()` so a key is backend-agnostic (rollback = env var). `get_storage()` branches on `LEGALMIND_STORAGE_BACKEND`; `s3` without `LEGALMIND_S3_BUCKET` raises — never a silent local fallback. Credentials only through boto3's chain (S-6). `legalmind.ingestion.storage` added to the egress register citing locked Step 39. | `tests/test_storage_s3.py`: both backends parametrised through the same assertions (key format, suffix allow-list, write-once, round-trip, discard); `get_storage` selection and refusal. `test_import_boundaries.py` names three modules. |
| 10.3 / 11.10 (P1) | API unit file not in the repository | `ops/production/legalmind-api.service`, `legalmind-frontend.service`, and both `*.service.d/10-hardening.conf` drop-ins — verbatim copies of `/etc/systemd/system` (the worker unit and the backup script were diffed: identical). | `diff` of the committed body against the installed unit: no difference. Confirms **one uvicorn process** (no `--workers`), `Restart=always`, `RestartSec=3`, and the hardening set the README attests. |

### 28.2 Not applicable, with evidence

| § | Finding | Why nothing changed |
|---|---|---|
| 12.1 (P1) | "Retrieval is not logged" | Overstated. `service._stage("retrieval")` wraps `store.search_hybrid` (legacy) and `retrieval.candidates` (multi-source); `positions`, `statutes`, `rescue`, `rerank`, `generation`, `verification`, `fallbacks` are stages too. `ask()` logs every one as `<stage>_ms` in `assist.ask.timings` and as `stages_ms` in `assist.ask.trace`, keyed by `request_id`; the multi-source trace also carries `retrievers`, `candidates`, `prepare_ms`, `verify_ms`. What `retrieval.py` lacks is its own `log_event` — a per-domain split of the retrieval stage. Deferred (P3): add it when one domain's share of that stage is the question. |
| 16.4 (P1) | Off-server backup leg untested | Stale. Credentials were supplied 2026-09-15; `/var/log/legalmind-backup.log` shows every 02:30 run since uploading, downloading, matching the SHA-256 and decrypting the object ("off-server ok … read back, decrypts", last on 2026-09-29). The local row already proves the decrypted bytes restore. `ops/production/README.md` corrected; the schedule is root's crontab (`30 2 * * *`), now quoted there. |
| 14.4 (P1) | `EscalateControl` lacks 409 handling | No 409 exists to handle. `POST /findings/{id}/escalate` is idempotent (`workflow/escalation.py:45-47` returns the existing escalation, 201); `DELETE …/escalate` on nothing active is a 200 no-op (`:64-66`); no `Conflict`/`VersionConflict` is raised anywhere on that path and `escalations` carries no unique constraint. The race the review described ends in success + refetch, not an error banner. Porting the conflict branch would be dead code. See 28.4 for the real gap it uncovered. |
| 9 (P2) | The "24th" Review in the crash test | Already explained in `test_worker.py:215-228`: nothing was lost — kombu's default visibility timeout (3600 s) made a redelivered message *look* stuck for an hour, and the test now pins `visibility_timeout > task_time_limit` and `< 3600`. Closed. |
| 10.1 (P2) | Retry, circuit breaker, concurrency cap on Gemini | Measured before building, per the cost guard: the API journal for the last 14 days holds **117 `assist.generation.completed` and 1 `assist.generation.failed` — HTTP 402**, a billing refusal that no retry or breaker would change. A 0.85 % failure rate with no transient error observed does not justify either; with one uvicorn process the effective concurrency ceiling on the call is the thread pool (anyio's default of 40). All three stay deferred behind the triggers in §22. |
| 6.5 (P3) | Index on `audit_events.action` | Measured: 3,411 rows, 2 MB; `EXPLAIN ANALYZE` of the `action`-filtered list is a 243-cost sequential scan. Not justified; revisit at the row count where that plan is measurably slow. |
| 9 / 14.3 (P2) | `AskDock` lacks `AskWorkspace`'s staleness guard | The identity the guard would key on cannot change under a pending submit: a contract switch remounts the dock (`dashboard/page.tsx:1598`, `<WorkspacePage key={contractId}>`), so a late answer resolves into an unmounted component and React drops it. A *version* switch does not reset the dock — by design: the transcript is contract-scoped, each turn records the version that answered it (`AskDock.tsx:154-156, 277-283`) and a turn from another version gets an "open Version N" affordance, pinned by `ask-dock.test.tsx:118-160`. Porting the guard keyed on the version would make a paid answer vanish from the log after a version click. Not a defect. |
| 15 (P2) | Preflight broker check as a hard failure | Already FAIL, not advisory: `preflight._analysis_worker` returns FAIL without a broker, `is_ready` requires PASS, and `ops/deploy.sh` refuses to finish unless `legalmind-worker` is active after the restart. What remains is the API *process* refusing to start on that misconfiguration — an operational policy (down vs. degraded) for the owner, 28.4. |

### 28.3 Deferred, unchanged from §22

Connection reuse for the Gemini client (P2 — a pooled client means `httpx`/`requests`, a dependency question under rule 19, and no latency figure yet says the handshake matters); an idempotency key on the Ask endpoint (P2 — an API contract change with no non-browser client to serve); the shared department-scope query builder (P2 — next time one of the three files is touched); the `evaluation/service.py` existence-check batch (P3); a per-day Gemini spend alert (P3); token/latency in `audit_events` versus logs (P3, and an owner question — is cost a compliance record or an operations record?).

### 28.4 Needs the owner

1. **`boto3` as a declared dependency.** `S3Storage` imports it lazily and it is installed on the host (system `python3-boto3`, the same package `ops/production/backup.sh` relies on), but `backend/pyproject.toml` does not declare it. Declaring it is a rule 19 approval. Until then `local` deployments never load it and `s3` ones need the package present.
2. **A partial unique index on `escalations(finding_id) WHERE withdrawn_at IS NULL`.** Two truly simultaneous escalates pass the application's check-then-insert and both insert; `withdraw` then withdraws one and the Finding stays escalated. Latent, not observed. The fix mirrors `workflow/decisions.py:115-119` (constraint + catch `IntegrityError` → return the existing row) and is a schema change on the locked tables, so it is not made here.
3. **Should the API refuse to start in production without a broker?** Today it runs degraded (inline analysis) and the deploy fails; a startup refusal is one line once the policy is chosen.
4. **Cost data's home** — `audit_events` (a legal record) or the operational log (where it is). Either is defensible; the split should be chosen, not inherited.

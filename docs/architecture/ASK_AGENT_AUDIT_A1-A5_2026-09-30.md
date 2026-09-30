# Ask agent — Phase 1A audit (A1–A5)

**Status:** 📁 ANALYSIS — read-only audit, decides nothing. **Date:** 2026-09-30.
**Code read:** `main` at `ee9dd10`. Line numbers refer to that commit.
**Plan:** [LegalMind Ask — Implementation Plan](LegalMind%20Ask%20—%20Implementation%20Plan%20(for%20the%20coding%20agent).md) §6 1A.

No code was changed for this audit. Where a claim below was re-checked directly against
the code after the first pass, it is marked ✔.

## Summary

| # | Question | Answer | Stop-and-ask? |
|---|---|---|---|
| A1 | Visibility enforced before ranking? | **Yes.** Document search is scoped in SQL to one pre-authorised version; the organisation-wide corpora (positions, Constitution, statutes) are gated by permission before any query runs. Nothing is filtered after ranking. | No. Gaps below matter for Phase 2 tools. |
| A2 | Version / status / authority / dates on records? | **Complete for Constitution and statutes, partial for positions, weak for documents.** Executed vs draft exists only as a declared JSONB key that retrieval never reads. No near-duplicate grouping. | **Yes** for 1.13 / 1.15 semantics (see question at the end). |
| A3 | Multi-source path reusable as a search tool? | **Mostly.** `plan → candidates → rerank → select → evidence.build` returns sources with quality signals and no generation, once the Gemini rescue call inside retrieval is made opt-in. | No for Phases 0–1. |
| A4 | How a chat attaches a document | One contract per conversation, set once. Uploading in Ask creates a real Contract. No conversation-scoped attachment exists. | **Yes** — conversation-scoped user material is a new concept and new schema. |
| A5 | Pinned evidence → ledger | Pinned evidence is not stored; it is recomputed from a Finding. Citations cover three chunk kinds, not the Constitution. Position IDs are not stable. | **Yes** — a ledger needs a new table and stable IDs first. |

---

## A1. Authorization inside retrieval candidate selection

**Finding.** Authorization is enforced before ranking, in two layers:

1. **Documents** are authorised in the router, then every candidate query is scoped in SQL
   to that one `document_version_id`.
2. **Positions, Constitution and statutes** are organisation-wide corpora. They are gated
   as a whole by the caller's permissions at the top of each search. Rows inside them are
   filtered only on status.

No department filter appears inside a retrieval query. None is needed, because document
retrieval never spans more than one already-authorised version.

**Evidence**

- Router order, [routers/assist.py](../../backend/legalmind/api/routers/assist.py):
  - `assist.ask` is checked at `:496`;
  - conversation ownership at `:497`, through `_visible_conversation` `:98-112`
    (`NotVisible` → 404);
  - contract read at `:505`, `guard.contract_readable`
    ([security/authorization.py:88-107](../../backend/legalmind/security/authorization.py#L88-L107):
    owner → `department.view` with same department → Legal scope).
- Version resolution:
  - `_asked_document_version` `:59-95` resolves the version;
  - a named version goes through `guard.document_version_readable`
    ([api/deps.py:299-315](../../backend/legalmind/api/deps.py#L299-L315)), which returns the
    same `NotVisible` for missing and unreadable.
- Document SQL scope:
  - lexical `WHERE c.document_version_id = :dv` ✔
    [store.py:320](../../backend/legalmind/assist/store.py#L320);
  - vector `:872`;
  - pinned rows `_version_chunks` `:762`;
  - outline `:728`.
- The multi-source document search calls the same function:
  `store.search_hybrid(..., candidates=True)` ✔
  [retrieval.py:156](../../backend/legalmind/assist/retrieval.py#L156).
- Positions: `positions.can_read` `:436-440`
  (`assist.ask` ∧ (`configuration.view` ∨ `legal_position.view`)).
  - Empty result at `:485`.
  - SQL excludes `DEPRECATED` only, at `:571` and `:717`.
- Constitution: `constitution.can_search` → `positions.can_read` `:356-358`.
  - Early return at `:306`.
  - SQL keeps `status='CURRENT' AND i.status <> 'UNRATIFIED'` only, at `:309-311`.
- Statutes: [statutes.py:870](../../backend/legalmind/assist/statutes.py#L870) requires
  `assist.ask` only.
  - `WITHDRAWN` and repealed rows are excluded in SQL at `:950`, `:1075` and `:1220`.
- Multi-source domain choice: `retrieval._authorized` `:110-114` admits the Constitution
  only on `positions.can_read`, and `:237` skips an unauthorised domain.

**Existing tests that already prove "no candidates, no existence leak"** (read and cited; the
suite run below covers them):

- `test_assist_authorization_boundaries.py`:
  - `test_2_retrieval_cannot_cross_a_document_version_boundary`
  - `test_2b_another_users_document_version_is_a_byte_identical_404`
  - `test_4_live_ask_stops_disclosing_a_position_the_moment_the_grant_is_gone` (with 4b, 4c)
  - `test_5_the_statute_corpus_needs_assist_ask_and_is_otherwise_an_empty_corpus`
  - `test_8_a_stranger_cannot_reach_another_owners_conversation`
  - `test_9_fallback_consults_only_domains_the_caller_may_read`
- `test_assist_ask_version_context.py`:
  - `test_another_users_version_is_byte_identical_404`
  - `test_a_version_from_another_contract_is_refused`
- `test_assist_ask.py`:
  - `test_someone_elses_conversation_is_byte_identical_404`
  - `test_a_department_user_without_the_grant_never_sees_a_position`
- `test_assist_conversation_scope.py::test_attaching_a_contract_the_caller_cannot_read_is_not_found`
- `test_positions.py`:
  - `test_without_a_position_permission_the_result_is_an_empty_corpus`
  - `test_the_vector_increment_respects_the_same_authorization`
  - `test_the_refusal_shape_is_byte_identical_to_a_genuine_miss`
- `test_assist_statutes.py::test_without_assist_ask_the_corpus_is_empty`
- `test_ask_multi_source_rollout.py::test_the_callers_own_permissions_scope_every_search`

**Gaps — none is a leak today, all matter for Phase 2 tools**

1. **No Ask test for department scope.** No test checks that a Department Lead can ask
   about a colleague's contract in their own department but not in another. Test 8 is
   headed "department isolation" but only exercises conversation ownership.
2. **The multi-source vector branch is not pinned.** It uses `candidates=True`, but
   `test_2` calls `search_hybrid` with `embed_query=None, candidates=False`. Pinning it
   needs the embedding model, which CI does not have.
3. **Four helpers take a raw ID and apply no scope or permission check:**
   - `store.expand_chunk` `:644`
   - `store.section_headings` `:679`
   - `constitution.expand` `:361`
   - `statutes.expand_section` `:1129`

   They are safe only because their IDs come from already-scoped results. **A tool that lets
   the model pass an ID must add a scope argument first** (plan task 2.3).
4. **Replayed statute citations are never re-checked.** Statutes need `assist.ask` alone,
   and the replay path (`routers/assist.py:414-424`) re-checks nothing.
5. **Position SQL excludes `DEPRECATED` but not `DRAFT`** requirements (`positions.py:571`).
6. **Retrieval searches one document version per question.** No query spans every
   document a user may read. A cross-document tool would need a new, authorised
   multi-version query.

---

## A2. Version, status, authority and date metadata

**Finding.** Metadata coverage varies by source:

- **Constitution and statutes:** full lifecycle metadata.
- **Positions:** status only.
- **Uploaded documents:** a human-declared `version_role` in JSONB that retrieval ignores.
- **Near-duplicates:** only exact duplicates (same file hash, same contract) are detected.

| Table | Relevant columns that exist |
|---|---|
| `contracts` (`models.py:265-296`) | `status` DRAFT/ACTIVE/SUPERSEDED (`enums.py:167`), `archived_at`, `counterparty_id` |
| `document_versions` (`:299-330`) | `version_number`, `file_hash` (not unique, `:300-302`), `processing_status`, `extraction_status`, `metadata` JSONB. Declared keys: `source`, `counterparty`, `effective_date`, `version_role` (`serializers.py:284`); `duplicate_of` is set at upload (`ingestion/service.py:128`) |
| `document_processing_runs` (`:333-356`) | `run_type`, `status` STARTED/COMPLETED/FAILED, `processor_version`, `started_at`/`completed_at`, `error_code` |
| `assist.chunks` (migration `b1e7c4d20f39:134-160`) | `document_version_id`, `evidence_id`, `ordinal`, offsets, `chunking_algorithm_version`. **No status or authority** |
| `requirements` / `requirement_versions` / `company_standard_versions` | `status` DRAFT/ACTIVE/DEPRECATED, `version_number`; the `configuration` JSONB carries `document_type` and `constitution {version, section, topic, basis}`. **No effective date** |
| `assist.position_chunks` (`d7e2a9c41b58:96-107`) | `standard_version_id`, `standard_code`, `document_type`, `source_clause` |
| `assist.knowledge_sources` (`f4c1e8a2b7d9:57-72`) | `version`, `status` (CHECK: CURRENT/SUPERSEDED/HISTORICAL/UNRATIFIED/REPEALED), `authority`, `jurisdiction`, `effective_from`, `effective_to`, `supersedes_id`, `file_sha256` |
| `assist.knowledge_items` (`:83-104`, `b8e2f6a4d1c3`) | `authority`, `status`, `section_path`, `kind`, `line_start`/`line_end`, `breadcrumb` |
| `assist.statutes` | `act_number_year`, `jurisdiction`, `as_amended_date` (text), `status` CURRENT/REPEALED/WITHDRAWN |
| Statute commencement | Not a column. Read from `config/statutes/commencement.json` by `statutes.commencement` (`:1103`) |

**Executed vs draft.**

- The only marker is `document_versions.metadata.version_role` ∈
  {`COMPANY_DRAFT`, `CLIENT_MODIFIED`, `FINAL_SIGNED`}
  ([domain/client_profile.py:67-71](../../backend/legalmind/domain/client_profile.py#L67-L71)).
  A person declares it; nothing infers it.
- `authority.of_document` (`authority.py:33-35`) maps that value to
  `EXECUTED_DOCUMENT`/`DRAFT_DOCUMENT`, but **nothing calls it**.
- Retrieval hard-codes the authority `"DOCUMENT"` for every document chunk ✔
  [retrieval.py:193](../../backend/legalmind/assist/retrieval.py#L193).

**Near-duplicates.** Detection is exact SHA-256 within one contract only
(`ingestion/service.py:62-77`). No version group, no similarity, no cross-contract link.

**Gaps**

- Plan 1.15 ("unsigned copies not labelled executed") needs `authority.of_document` wired into
  retrieval. That needs no schema: `version_role` exists. It does need a ruling on the
  default when `version_role` is absent (the plan says draft/unsigned).
- Plan 1.13 ("near-duplicates share a version group") has no home. It needs either a
  JSONB key on `document_versions.metadata` (the owner-Q2 `D-3` route, no migration) or a
  column.
- Positions have no effective date. The `DRAFT` requirement exclusion is missing (A1 gap 5).

---

## A3. The multi-source path

**Finding.** `LEGALMIND_ASK_MULTI_SOURCE` defaults to `on` (`config.py:445`), and
`_ask_path` sends every conversation to it (`service.py:1004-1011`). The branch runs at
`service.py:1213`, after the deterministic early exits. A failure returns `None`, and the
legacy path answers instead.

**Stages** (`service._ask_multi_source`, `service.py:1425-1569`):

1. `query_plan.plan` (`query_plan.py:172`). Deterministic, no model.
2. `retrieval.candidates(db, plan, route, permissions=, document_version_id=, pinned_evidence=)`
   (`retrieval.py:197-277`). Per-domain lexical + vector search, reciprocal-rank fusion, and
   an exact Constitution-section lookup.
3. `retrieval.rerank` (`:288-317`). Local cross-encoder, statutes and documents only.
4. `retrieval.select` (`:406-479`). Diverse evidence.
5. `evidence.build` (`evidence.py:162-222`). Parent context, relevance scoring, a
   per-source judgement (`_judge` `:125-159`), and a `Bundle` with `answerable` and
   `shown()`.
6. `answer.prepare` (`answer.py:918`). Claim contracts (`contracts.build`,
   `contracts.py:448`).
7. `answer.respond` (`answer.py:935-1026`). Up to two Gemini calls, plus the local NLI
   verifier.
8. Persist the answer and citations (`service.py:1527-1558`).

**Dependencies**

- A DB session under a savepoint (`:1472`), released before egress.
- Permissions, through `route` and `permissions` only.
- Local embedding, which degrades to lexical-only; a local reranker; a local NLI verifier.
- **Gemini in two places:**
  1. generation;
  2. **inside retrieval**: when the document gate is shut and nothing is pinned,
     `retrieval._search` calls `rescue.reconsider` ✔
     [retrieval.py:173-179](../../backend/legalmind/assist/retrieval.py#L173-L179). That call
     goes through the single egress seam (`generation.generate_raw`), which counts and logs
     it. But retrieval passes no `request_id`, so it can't be tied to the request, and it is
     not in the `calls` list the request's audit row records.

**Reuse as a read-only search tool.** Running stages 1–5 returns sources, `relevance`,
`supports`/`reason`, `status`, `authority` and `pool.document_gate`, with no generation. To
make them a clean tool, three things need separating:

1. **Make the rescue call opt-in**, or run with `LEGALMIND_EVIDENCE_RESCUE=off`, so a search
   makes no paid call.
2. **Lift `routing.plan(...)` out of `_ask`** (`service.py:1100-1103`). It is deterministic,
   so it can be called directly.
3. **Check the trace context variables** (`_stage`/`_trace`, set in `service.ask`). They are
   harmless when unset.

---

## A4. How a chat attaches a document today

**Finding.**

- A conversation holds at most one contract (`conversations.contract_id`), set once from
  `NULL`.
- Each question answers from one version of that contract.
- Uploading from Ask creates an ordinary Contract, owned by the uploader and shown on the
  Dashboard. Nothing ties it to the conversation.
- **No conversation-scoped attachment exists, and no status reaches the chat.**

**Evidence**

- **Question cap:** `question: str = Field(min_length=1, max_length=2000)` ✔
  [schemas.py:82](../../backend/legalmind/api/schemas.py#L82). A longer question is a
  Pydantic 422, re-checked at `routers/assist.py:521-522`.
- **Create:** `create_conversation` (`routers/assist.py:192-206`) checks the contract is
  readable.
- **Attach:** `attach_document` (`:209-248`) calls `service.attach_contract`
  (`service.py:438-472`), `UPDATE … WHERE contract_id IS NULL`. It is one-way and audited.
- **Version choice:** `_latest_document_version` takes the highest `version_number` and
  **does not check processing or index status** ✔
  [routers/assist.py:47-56](../../backend/legalmind/api/routers/assist.py#L47-L56).
- **Upload:** `POST /contracts/{id}/document-versions` (`routers/contracts.py:608-697`)
  requires `document.upload` and contract ownership.
  - Types: PDF, DOCX, text/plain, text/markdown, with magic-byte sniffing
    (`ingestion/validation.py:12-20`).
  - Size: 100 MB ceiling (`:27`), plus the deployment limit.
- **States:** `ProcessingStatus` PENDING/PROCESSING/COMPLETED/FAILED and `ExtractionStatus`
  COMPLETE/PARTIAL/AMBIGUOUS/FAILED (`enums.py:133-206`).
- **Visibility to Ask:** chunks become retrievable once `indexing.index_document_version`
  (`indexing.py:60-130`) writes `assist.chunks`.
  - It runs inline or on the `QUEUE_ASSIST` worker (`worker/dispatch.py:180-222`).
  - FAILED extractions are skipped, and an integrity failure refuses the index.
- **Frontend:** `AskWorkspace.tsx:351-369` calls `createContract` → `uploadDocument` →
  `attachDocument`.

**Gaps**

- A question asked while a document is still processing retrieves nothing and gives no
  signal (plan 1.2 status).
- Ask has no temporary "user material". A paste over 2000 characters is rejected (plan 1.1).
- Attaching requires `document.upload` and contract ownership. A conversation-only
  attachment would need its own authorization rule.

---

## A5. Pinned evidence and the per-answer record

**Finding.** "Pinned evidence" is not stored anywhere:

- For a question about a Finding, `_finding_evidence_ids` (`service.py:391-415`) reads that
  Finding's evidence at request time (limit 4).
- Only the `finding_id` is recorded, in `retrieval_runs.filters`.
- A per-conversation ledger with stable IDs needs a new table, and stable position and
  Constitution identities first.

**Evidence**

- **Legacy path:** writes `filters.finding_id` (`_persist_retrieval` `:532-533`).
- **Multi-source path:** writes none (`_persist_multi_source_run` `:1715-1721`), so a
  follow-up to a multi-source Finding answer cannot inherit it.
- **Inherited Finding:** `_inherited_finding` (`:380-388`) takes the latest run with any
  `finding_id`, although its docstring says "the immediately preceding turn".
- **`answer_citations`:**
  - Columns: `id`, `answer_id`, `chunk_id`, `position_chunk_id`, `statute_chunk_id`,
    `claim_ordinal`, `created_at`.
  - CHECK exactly one of the three (`d7e2a9c41b58:226-254`).
  - UNIQUE (`answer_id`, `claim_ordinal`, `chunk_id`) (`b1e7c4d20f39:391`).
  - Positions and statutes are told apart by ordinal offsets 1000+/2000+
    (`service.py:652`, `:666`).
- **No Constitution citation column.** Constitution references survive only as JSON in
  `retrieval_runs.results.constitution_cited` (`service.py:1711`, `:1728`).
- **The multi-source path saves citations from the wrong list.** It rebuilds them from the
  legacy `position_hits`/`statute_hits` (`:1530-1534`), not from the references the answer
  cited.
- **Position chunk IDs are not stable.** Re-chunking deletes by `standard_code` and inserts a
  fresh `uuid4` ✔
  [positions.py:381-398](../../backend/legalmind/assist/positions.py#L381-L398). The
  citation foreign key is `ON DELETE CASCADE`, so position citations are silently lost.
- **Constitution item IDs are regenerated** when the file's hash changes
  (`constitution.py:201-207`).
- **Document and statute chunk IDs are stable.** Their re-index preserves IDs and repoints
  citations (`store.replace_chunks`, `statutes._replace_statute_chunks`).

**What a ledger needs.**

- A table keyed by conversation, e.g. `assist.conversation_evidence` with `evidence_id`,
  `source_type`, `authority`, `status`, `version_id`, `location`, `text_hash`,
  `fetched_at`, `turn_id`, which `answer_citations` references.
- Existing tables can't hold it without overloading `retrieval_runs.results` JSONB, which
  has no foreign keys and no uniqueness.
- Stable position and Constitution identities come first (a content-hash identity is one
  option), or the ledger inherits the cascade loss.

---

## Found in passing — outside Phases 0–1, reported, not acted on

1. **v2.1 conflicts with locked decisions.** Several v2.1 target behaviours contradict
   decisions that are locked today. Each must be amended or recorded before Phase 3:
   - Sending earlier ASSISTANT answers to Gemini (v2.1 §4.2) conflicts with `AM-58` (prior
     USER questions only) and `AM-30` t2.
   - Uncited L4 general explanations conflict with `AM-25` r5, and the plan's D1–D4 records
     are still owed (plan §2).
   - D5 — pasted client material to Gemini — is outside `AM-30` t3 as written.
2. **Environment: `lmtest` credentials rotated.** The test role in the local-test-database
   note no longer authenticates. As a result:
   - The persistent Tier-2 gate database is unreadable to the current role.
   - A stale `lmtest`-owned test schema in `legalmind_v1_test` makes every DB-backed test
     there error at setup.

   The ops README recipe also needs `LEGALMIND_ENVIRONMENT` unset since decision 340, or
   analysis tests get a 503.

## The one owner question this audit raises

Plan tasks 1.1/1.2/1.5 (conversation attachments) and 1.6/1.7 (ledger) cannot be built
without new schema. See the phase report for the options.

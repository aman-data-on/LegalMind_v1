# Ask agent — design note: attachment and evidence-ledger tables

**Status:** ✅ APPROVED (owner D13/D14, 2026-09-30); locked as `AM-110` (AB-60). Migration `a9e4c2f7b1d3`, applied to scratch databases only (2026-10-01). Column names were adjusted to the repository's schema conventions (decision A-11): see the note at the end.
After approval, one Alembic revision will be written, run on a scratch database (upgrade →
downgrade → upgrade), and reviewed before it reaches staging. It never goes straight to
production.

**Owner constraints (2026-09-30):**
- new tables only;
- additive and reversible;
- no change to any existing table;
- covers audit A1 gap 4 and the A2 metadata gaps.

**Locks engaged.** Adding assist-schema tables extends `AM-27`'s authorized table set, as
`AM-32`, `AM-35` and `AM-49` did before. The migration therefore ships with its own lock record,
appended per rule 22, in the same change. Owner approval of this note is the approval that record
cites.

All tables live in `config.assist_schema()` (`assist` in production; a per-run schema in tests,
`F-4`). They follow the conventions of `assist.chunks` / `chunk_embeddings`:
- UUID keys;
- `timestamptz` columns;
- a generated `content_tsv`;
- embeddings in a sibling table with a schema-qualified `vector(384)`.

---

## 1. `conversation_attachments`: plan 1.1, 1.2, 1.5

One row per pasted block or uploaded file, scoped to one conversation.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `conversation_id` | uuid NOT NULL → `conversations(id)` ON DELETE CASCADE | Deleting the conversation deletes its material |
| `message_id` | uuid NULL → `messages(id)` ON DELETE SET NULL | The turn that brought it in |
| `kind` | varchar(8) CHECK IN (`PASTE`,`FILE`) | |
| `filename` | varchar(255) NULL | FILE only. Never logged |
| `mime_type` | varchar(100) NOT NULL | From the existing `ingestion/validation.py` sniffing |
| `byte_size` | bigint NOT NULL | |
| `content_sha256` | char(64) NOT NULL | Logged in traces instead of content |
| `storage_key` | varchar(512) NULL | Raw bytes go through the existing `ingestion.storage` backend, not a DB column |
| `status` | varchar(12) CHECK IN (`PROCESSING`,`READY`,`FAILED`,`EXPIRED`) | `unavailable` is computed at read time (expired, or no longer visible), not stored |
| `failure_code` | varchar(64) NULL | A code only (e.g. `UNSUPPORTED_TYPE`, `EXTRACTION_FAILED`). Never extracted text |
| `created_at` / `ready_at` | timestamptz | |
| `expires_at` | timestamptz NOT NULL | `created_at + LEGALMIND_ASK_ATTACHMENT_TTL_DAYS` (recommended 30) |

**Indexes and constraints.**
- `(conversation_id, created_at)` for listing.
- `(expires_at) WHERE status <> 'EXPIRED'` for the purge job.
- UNIQUE `(conversation_id, content_sha256)`: the same paste twice is one attachment.

## 2. `attachment_chunks` and `attachment_chunk_embeddings`: plan 1.3

These run parallel to `chunks` / `chunk_embeddings` because `chunks.document_version_id` is NOT
NULL, and existing tables stay untouched.

The search is **reused**, not rewritten. Attachment search runs `store.search_hybrid`'s
lexical + vector + RRF query shape over these tables. Whether that means parameterising the
table name in the existing SQL or a thin sibling query is decided at implementation, whichever
is the smaller diff. The document path must stay byte-identical on the golden benchmark.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `attachment_id` | uuid NOT NULL → `conversation_attachments(id)` ON DELETE CASCADE | |
| `ordinal` | int NOT NULL | UNIQUE with `attachment_id` |
| `content` | text NOT NULL | As written. Blank fields (`____`, `[●]`) are kept (plan 1.14) |
| `location` | varchar(64) NULL | Clause number, or `p.N` (plan 1.11) |
| `start_offset` / `end_offset` | bigint NULL | |
| `annotations` | jsonb NOT NULL DEFAULT `'{}'` | e.g. `{"blank_fields": [[s,e],…]}`. Marks only; the content is never altered |
| `chunking_algorithm_version` | varchar(64) NOT NULL | |
| `content_tsv` | tsvector GENERATED | GIN index, as in `chunks` |

`attachment_chunk_embeddings` has the same shape as `chunk_embeddings`, with the foreign key to
`attachment_chunks` and UNIQUE `(chunk_id, embedding_model_id)`.

## 3. `conversation_evidence`: the ledger (plan 1.6, 1.8; audit A5-1, A1 gap 4)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `conversation_id` | uuid NOT NULL → `conversations(id)` ON DELETE CASCADE | |
| `evidence_key` | varchar(8) NOT NULL | Code-assigned, e.g. `C3`, `U1`. UNIQUE with `conversation_id` |
| `source_class` | char(1) CHECK IN (`C`,`P`,`S`,`H`,`D`,`U`) | |
| `domain` | varchar(16) CHECK IN (`DOCUMENTS`,`POSITIONS`,`CONSTITUTION`,`STATUTES`,`ATTACHMENTS`) | **A1 gap 4.** Every re-fetch and replay runs this domain's *live* gate again. Nothing is trusted from write time |
| `source_ref` | varchar(255) NOT NULL | **Natural key (A5-1)**, which survives a re-chunk. Examples: `POS:<code>@v<n>`, `CONST:<section>@<source version>`, `STAT:<act>:<section>`, `DOC:<chunk id>`, `ATT:<chunk id>` |
| `chunk_id`, `position_chunk_id`, `statute_chunk_id`, `knowledge_item_id`, `attachment_chunk_id` | uuid NULL, each → its table ON DELETE **SET NULL** | A fast path only. A re-chunk nulls the pointer instead of deleting the row, and re-fetch falls back to `source_ref`. CHECK: at most one is set |
| `authority` | varchar(32) NOT NULL | e.g. `COMPANY_POSITION`, `HISTORICAL_EXCEPTION`, `LAW`, `EXECUTED_DOCUMENT`, `DRAFT_DOCUMENT`, `USER_MATERIAL` |
| `status` | varchar(16) NOT NULL | `current`, `historical`, `draft`, `executed`, `unsigned` or `superseded`, **as seen at fetch time**. Re-fetch recomputes it and reports `stale` or `unavailable` |
| `source_version` | varchar(64) NULL | Source version: standard version id, knowledge-source version, statute file hash, or document version id |
| `location` | varchar(128) NULL | e.g. `§14.3`, `cl. 17.2`, `s. 73` |
| `text_hash` | char(64) NOT NULL | SHA-256 of the exact text handed to the model |
| `fetched_at` | timestamptz NOT NULL | |
| `turn_message_id` | uuid NOT NULL → `messages(id)` ON DELETE CASCADE | The `turn_id` |

**Indexes and constraints.**
- UNIQUE `(conversation_id, evidence_id)`.
- UNIQUE `(conversation_id, source_ref, text_hash)`: the same record fetched twice keeps its ID.
- `(turn_message_id)`.

**Not stored:** the record's text. It is fetched live by `source_ref` under the caller's
permissions (plan 1.8). The ledger never becomes a second copy of the corpus, and deleted or
expired material cannot resurface from it.

## 4. `answer_evidence`: which IDs each answer cited (plan 1.7; audit A5-2, A5-3)

| Column | Type | Notes |
|---|---|---|
| `answer_id` | uuid NOT NULL → `ai_answers(id)` ON DELETE CASCADE | |
| `ledger_id` | uuid NOT NULL → `conversation_evidence(id)` ON DELETE CASCADE | |
| `claim_ordinal` | int NOT NULL | |

PK `(answer_id, ledger_id, claim_ordinal)`. This records **the refs the answer actually
cited**, closing A5-2, and covers the Constitution (A5-3). `answer_citations` is untouched and
keeps being written as today until a later, separate decision retires it.

## 5. `document_version_attributes`: A2-1 and A2-2 (plan 1.13, 1.15)

| Column | Type | Notes |
|---|---|---|
| `document_version_id` | uuid PK → `document_versions(id)` ON DELETE CASCADE | |
| `version_group` | uuid NOT NULL | Copies of one agreement share it. The first member's id seeds it |
| `normalized_text_sha256` | char(64) NOT NULL | Text after the plan 1.10/1.12 cleaning. Exact normalised match → same group |
| `similarity` | real NULL | To the group seed, when grouped by similarity. The threshold is a measured constant and is recorded with it |
| `algorithm_version` | varchar(64) NOT NULL | |
| `computed_at` | timestamptz NOT NULL | |

Index: `(version_group_id)`.

**No execution-status column.** A2-1's recommendation reads the existing declared
`metadata.version_role`, with absent read as unsigned, through `authority.of_document`. That is
a code change, not schema. Storing a derived copy would let the two disagree.

## Access checks

- Every read of §1–§4 joins through `conversations.user_id = :caller`. The router already
  establishes that ownership (`_visible_conversation`). A foreign or unknown id gives the same
  404 (A1, `AM-25` r7).
- Attachment search is scoped in SQL to the conversation's own attachments, **before ranking**
  (`AM-25` r6), never filtered afterwards.
- The permission to attach is `assist.ask` plus conversation ownership (A4-1). No new permission
  exists, so the permission catalogue is unchanged.
- The ledger re-fetch runs the live gate of `domain` every time (A1 gap 4).
- §5 is read only for a document version the router has already authorised.

## Retention and trace

- A purge job, in the existing worker, deletes storage bytes, chunks and embeddings for rows past
  `expires_at` and sets `status = EXPIRED`. The row itself is kept (ids and hashes only), so the
  audit trail stays whole (rule 17).
- Traces carry ids, hashes, sizes, statuses and latencies only. Never filename, content or
  extracted text (plan §3; `AM-30` t5).

## Rollback

- `downgrade()` drops the six tables in dependency order: `answer_evidence` →
  `conversation_evidence` → `attachment_chunk_embeddings` → `attachment_chunks` →
  `conversation_attachments`, then `document_version_attributes`.
- No existing table, column, constraint or enum changes, so downgrade loses only data this
  feature wrote. Storage bytes are removed by the purge job, not by downgrade. That order is
  deliberate: downgrade must not reach outside the database.
- Behaviour is flag-gated. With `LEGALMIND_ASK_ATTACHMENTS=off` (default until the owner turns
  it on), the API keeps the 2000-character rejection, and nothing reads or writes these tables.

## Open for the owner

1. Retention of 30 days (A4-2), and the limits in A4-3.
2. Whether `answer_citations` is ever retired in favour of `answer_evidence`. Not needed for
   Phase 1.

## Note: conformance changes at build time (A-11, 2026-10-01)

The repository's schema guards (`tests/test_assist_schema.py`) require every assist table
to have a UUID `id` primary key, and every `*_id` column to be a real foreign key. Three
changes make the design conform; none changes behaviour:

- `answer_evidence` and `document_version_attributes` each gain a UUID `id` primary key.
  Their former keys become UNIQUE constraints: (`answer_id`, `ledger_id`,
  `claim_ordinal`) and (`document_version_id`).
- `conversation_evidence.evidence_id` → `evidence_key`, and `version_id` →
  `source_version`. These hold a label and a version string, not references.
- `document_version_attributes.version_group_id` → `version_group`. No groups table
  exists.

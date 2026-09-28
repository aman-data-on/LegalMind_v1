# Multi-source Ask rollout runbook — roadmap PHASE 13

> 📁 **Operational.** Nothing in this runbook runs against production without the owner's
> explicit go-ahead. Every step below was rehearsed on 2026-09-26 against
> `legalmind_prod_rehearsal`, a local copy of production's full schema plus its public
> statute corpus (no contracts, documents, users or conversations were copied).

## What is being rolled out

> **`AM-106` (2026-09-28, owner): one Ask for every authorised reader.** The 10% canary
> was withdrawn. There is no percentage, no conversation hash and no cohort: every
> conversation, with or without a document, takes the verified path unless production is
> deliberately rolled back.
> **DEPLOYED 2026-09-28** — PR #123 merge `c9a2876`; the canary lines removed from `/root/.legalmind.env` (backup `/root/.legalmind/preserved/legalmind.env.before-am106-2026-09-28`); live check on production, writes rolled back: `flag` `on`, a no-document and a document question both `selected_path` `multi_source`, ANSWERED in one Gemini call each (9.3 s, 15.8 s), the document answer with 4 clause citations.

`LEGALMIND_ASK_MULTI_SOURCE` selects the Ask path (`config.ask_multi_source`):

| Value | Behaviour |
|---|---|
| `on` (**default**; the variable unset) | every conversation — with or without a document — uses the verified multi-source path (`service._ask_multi_source`) |
| `off` | **emergency rollback**: every conversation uses the previous path |
| `no_document` | **partial rollback**: document conversations use the previous path, document-free ones the verified path |
| any unreadable value | treated as `off` — the proven path, never a guess |

`LEGALMIND_ASK_MULTI_SOURCE_PERCENT` is **no longer read** (`AM-106` removed it and the
hash). A leftover line in the environment file changes nothing, but remove it so the file
says what production does. Every `assist.ask.trace` records `flag` beside `selected_path`
and the `path` that actually answered.

The verified path runs after every existing screen (general knowledge, capability, an
unmet prerequisite, the evaluator's compliance question) and answers only with a verified
generated answer. When it declines — nothing answerable, generation unavailable,
verification failing, or any error — the previous path answers or refuses exactly as it
does today. A declined turn shows in the trace as `selected_path` multi_source, `path`
legacy, with the reason in `fallback_kind`.

**The document lane** (`AM-106` r2–r4): a document question carries the CONTRACT lane,
the document takes two picks a round, its gate gets the Finding pin and the rescue judge
exactly as `service.retrieve_document` gives them, and its cited clauses come back as the
answer's `citations` (page, clause), numbered [1]..[d] and stored for history. Measured on
the 44 ratified document questions: gold clause shown 38 of 44 (previous path 41), not-found
questions admitting document text 0 of 10.

## Prerequisites — in this order

1. **Merge** the branch to `main` (the deploy ships `origin/main`).
2. **Back up** the production database (`pg_dump` of `legalmind_v1_dev`) and record the
   current Alembic head: `e9f2b6c4a173`.
3. **Migrate** — `python3 -m alembic upgrade head`, a straight chain:
   `e9f2b6c4a173 → f4c1e8a2b7d9` (knowledge_sources, knowledge_items) `→ a7d3e9b1c5f2`
   (statutes.status, repealed Acts marked) `→ b8e2f6a4d1c3` (breadcrumb, content_tsv,
   knowledge_item_embeddings). Rehearsed: upgrade, downgrade to `e9f2b6c4a173`, and upgrade
   again all clean. The rehearsal found and fixed a broken downgrade in `a7d3e9b1c5f2`.
4. **Ingest the Constitution** — `python3 -m tools.ingest_constitution` (12 s rehearsed).
   The canonical L1.10 file was corrected on 2026-09-27 (a §31.2 emphasis line still
   carried a counterparty name the `AM-59` redaction pass missed — replaced by the
   "[Customer A]" placeholder its own paragraph uses); the ingest is idempotent by file
   SHA-256, so this step also puts that correction into the records. Any environment
   whose `knowledge_sources` row predates it must be re-ingested before the flag is
   turned on, and `tests/test_constitution_redaction.py` is the check.
5. **Re-ingest the statutes under `AM-80`** — `python3 -m tools.ingest_statutes` (190 s
   rehearsed; re-points existing statute citations to the new chunks). Since `AM-104` the
   chunker is `section-5` (the Bill's Statement of Objects and Reasons is not stored as
   law): rehearsed 2026-09-28 at 17 Acts / **5,011** chunks, every row `section-5`. The
   live corpus is still `section-1`, so IT Act s. 70B reaches readers only after this step.
   `backend/config/statutes/commencement.json` ships with the code — no ingestion step.
6. **Provision** the entailment model `cross-encoder/nli-deberta-v3-small` at the pinned
   revision in the API's model directory; the reranker is already on in production.

## Verification — every number must match

After step 3:

```sql
SELECT version_num FROM alembic_version;                        -- b8e2f6a4d1c3
SELECT to_regclass('assist.knowledge_items'), to_regclass('assist.knowledge_sources'),
       to_regclass('assist.knowledge_item_embeddings');        -- all three exist
SELECT status, count(*) FROM assist.statutes GROUP BY 1;        -- CURRENT 15, REPEALED 2
```

After step 4 (the tool prints `items 701, embedded 404`):

```sql
SELECT count(*) FROM assist.knowledge_sources;                  -- 2
SELECT kind, count(*) FROM assist.knowledge_items GROUP BY 1;
  -- DOCUMENT 1 · SECTION 35 · SUBSECTION 76 · PROVISION 177 · PARAGRAPH 412 (= 701)
SELECT count(*) FROM assist.knowledge_item_embeddings;          -- 404
```

After step 5 (the tool reports 17 files, no `REFUSED` line, exit code 0):

```sql
SELECT count(*) FROM assist.statute_chunks;                     -- 5011 (AM-104)
SELECT chunking_algorithm_version, count(*) FROM assist.statute_chunks GROUP BY 1;
                                                               -- section-5 5011 only
SELECT count(*) FROM assist.statute_chunk_embeddings;           -- 5011
SELECT count(*) FROM assist.answer_citations c
  LEFT JOIN assist.statute_chunks s ON s.id = c.statute_chunk_id
 WHERE c.statute_chunk_id IS NOT NULL AND s.id IS NULL;         -- 0 (none orphaned)
```

Search health check — zero Gemini: the 76 benchmark questions' evidence bundles
(`tools.rag_benchmark.bundle_for`) on the migrated database select the same Constitution
and statute evidence as the validated corpus (`legalmind_rag_p2`). Rehearsed: 61 of 76
identical; the other 15 a strict superset, because the rehearsal copy holds no company
standards and the freed evidence slots filled with the next Constitution/statute units.

## Switching production to one Ask (`AM-106`)

The code ships with the verified path as the default, but production's environment file
still carries the 2026-09-28 canary lines (`LEGALMIND_ASK_MULTI_SOURCE=no_document`,
`LEGALMIND_ASK_MULTI_SOURCE_PERCENT=10`). With `AM-106` deployed and those lines left in
place, document-free conversations would ALL take the verified path (the share is no longer
read) and document conversations none. So the change is one step, done with the deploy:

1. Back up the environment file (`/root/.legalmind/preserved/`).
2. Delete both lines from `/root/.legalmind.env` (the default is `on`).
3. Deploy (`sudo legalmind-deploy`), which restarts the API with the new environment.
4. Verify in `assist.ask.trace`: `flag` `on`, and `selected_path` multi_source for both
   document and document-free conversations.

No migration and no ingestion are needed: `AM-106` changes code only.

(Earlier, `AM-94` introduced a canary with a share; the owner withdrew it on 2026-09-28.)

## Measured before the canary (2026-09-27, `AM-94`)

| | legacy (production today) | multi-source |
|---|---|---|
| Gemini calls per no-document question | 1 (statute answer or reading aid) | 1 (+1 corrective retry only when a sentence cites no contract) |
| Gemini p50 | ~1.7 s | ~2.7 s (`contract-answer-2`) |
| Local stages p50 / p95 (75 questions, zero Gemini) | — | candidates 0.2 / 0.4 s · rerank 0.8 / 1.1 s · bundle 0.4 / 0.45 s · contracts 0.1 / 0.6 s · verify 0.4 / 2.9 s |
| Answers judged better (6 questions, independent) | 1 | 5 |
| Bad sentences shown, run-9 replay (65 questions) | — | 16 / 421 kept + 92 repaired; false rejects 2 |
| Constitution text shown to readers | never | yes — redaction gate (`test_constitution_redaction.py`) |

Interpretation for the gate: the new path answers more questions (a false refusal on
H-03 becomes an answer), labels every layer, and is 40–85% shorter than its own
`AM-93` form; it is still several times slower end to end than legacy because it
retrieves broadly, verifies every sentence and writes a fuller answer. Watch
`stages_ms` and `gemini_ms` on the trace; widen the share only when the p95 stays
within what the product accepts.

## Rollback

* **Emergency, the whole Ask** — set `LEGALMIND_ASK_MULTI_SOURCE=off` in
  `/root/.legalmind.env` and `systemctl restart legalmind-api`. Every conversation returns
  to the previous path within seconds; no deploy and no data change.
* **Documents only** — `LEGALMIND_ASK_MULTI_SOURCE=no_document` and a restart: document
  conversations return to the previous path, document-free ones stay on the verified path.
* ⚠️ **Never "remove the line" to roll back.** Since `AM-106` the unset default is `on`:
  deleting the flag switches the verified path ON. Roll back only by setting `off` (or
  `no_document`) explicitly. The flag is read per request from the process environment,
  and systemd loads the file only at start, so a change applies once the API restarts —
  seconds, with requests in flight during the restart interrupted. Every answer records
  which path produced it (`retrieval_runs.filters.path`, `strategy_version`
  `multi-source-1`).
* **Schema/data** — not needed to restore the old path: the old path never reads the
  new tables. If the schema itself must go: `python3 -m alembic downgrade e9f2b6c4a173`
  (rehearsed clean). Statute re-ingestion is not undone by a downgrade; restore the
  pre-migration backup for that.

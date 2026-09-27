# Multi-source Ask rollout runbook — roadmap PHASE 13

> 📁 **Operational.** Nothing in this runbook runs against production without the owner's
> explicit go-ahead. Every step below was rehearsed on 2026-09-26 against
> `legalmind_prod_rehearsal`, a local copy of production's full schema plus its public
> statute corpus (no contracts, documents, users or conversations were copied).

## What is being rolled out

`LEGALMIND_ASK_MULTI_SOURCE` selects the Ask path (`config.ask_multi_source`):

| Value | Behaviour |
|---|---|
| `off` (default; any unknown value) | every conversation uses the existing path |
| `no_document` | a conversation with no document uses the validated PHASE 9–12 path (`service._ask_multi_source`); a document conversation uses the existing path |
| `on` | every conversation uses the new path. **Not approved** — the document lane has no benchmark |

`LEGALMIND_ASK_MULTI_SOURCE_PERCENT` (0–100, default 100) is the canary dial inside
whatever the flag admits: a conversation takes the new path when a SHA-256 of its id
falls below the share, so one reader's thread stays on one path for its whole life. A
value that cannot be read, or is out of range, admits nobody. Both values are recorded
on every `assist.ask.trace` (`flag`, `canary_percent`) beside `selected_path` and the
`path` that actually answered.

The new path runs after every existing screen and answers only with a verified
generated answer. When it declines (nothing answerable, generation unavailable,
verification failing, or any error), the existing path answers exactly as it does today.

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
   rehearsed; re-points existing statute citations to the new chunks).
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
SELECT count(*) FROM assist.statute_chunks;                     -- 5036
SELECT chunking_algorithm_version, count(*) FROM assist.statute_chunks GROUP BY 1;
                                                               -- section-4 5036 only
SELECT count(*) FROM assist.statute_chunk_embeddings;           -- 5036
SELECT count(*) FROM assist.answer_citations c
  LEFT JOIN assist.statute_chunks s ON s.id = c.statute_chunk_id
 WHERE c.statute_chunk_id IS NOT NULL AND s.id IS NULL;         -- 0 (none orphaned)
```

Search health check — zero Gemini: the 76 benchmark questions' evidence bundles
(`tools.rag_benchmark.bundle_for`) on the migrated database select the same Constitution
and statute evidence as the validated corpus (`legalmind_rag_p2`). Rehearsed: 61 of 76
identical; the other 15 a strict superset, because the rehearsal copy holds no company
standards and the freed evidence slots filled with the next Constitution/statute units.

## Canary

With the prerequisites verified, set `LEGALMIND_ASK_MULTI_SOURCE=no_document` and a
small `LEGALMIND_ASK_MULTI_SOURCE_PERCENT` (say 10) in `/root/.legalmind.env`, restart
the API (`systemctl restart legalmind-api`), and widen the share only on the trace
evidence. Watch `assist.ask.trace`: `selected_path` vs `path` (a legacy `path` under a
multi-source `selected_path` is a fallback, never a success), `fallback_kind`,
`generated`, `verification_failures`, `gemini_calls`, token counts, `latency_ms` and
`stages_ms`. Kill switch: the share to 0, or the flag to `off`, and a restart.

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

* **Answer path** — set `LEGALMIND_ASK_MULTI_SOURCE=off` (or remove it) in
  `/root/.legalmind.env` and `systemctl restart legalmind-api`. The flag is read per
  request from the process environment, and systemd loads the environment file only at
  start, so the change applies once the process restarts — seconds, with requests in
  flight during the restart interrupted. No deploy and no data change is needed; every
  answer records which path produced it (`retrieval_runs.filters.path`,
  `strategy_version` `multi-source-1`).
* **Schema/data** — not needed to restore the old path: the old path never reads the
  new tables. If the schema itself must go: `python3 -m alembic downgrade e9f2b6c4a173`
  (rehearsed clean). Statute re-ingestion is not undone by a downgrade; restore the
  pre-migration backup for that.

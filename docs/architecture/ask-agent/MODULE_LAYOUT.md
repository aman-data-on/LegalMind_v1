# Assist lane — module layout (2026-10-05)

📁 Record of a code move. It decides nothing and amends no lock. Owner request
(2026-10-05): organise the RAG/LLM code the way RAG projects are usually laid out, one
package per pipeline stage. Branch `feat/ask-agent-phase0-1` only; `main` is unchanged.

```
backend/legalmind/assist/
  ingestion/     evidence → searchable units, local embedding models
  knowledge/     the knowledge sources and their stores
  query/         understanding the question before retrieval
  retrieval/     candidates, reranking, the evidence bundle
  llm/           the ONE module permitted to reach the network (AM-30 t1)
  synthesis/     writing from evidence
  verification/  checking what was written against what was cited
  agent/         the Ask agent: loop, tools, ledger, material
  service.py     the ask flow (unchanged place)
  state.py       the sixth state axis, AM-29 (unchanged place)
```

| Old path (`legalmind/assist/…`) | New path |
|---|---|
| `chunking.py`, `indexing.py`, `embedding.py`, `embedding_runtime.py`, `onnx_backend.py`, `version_groups.py` | `ingestion/…` |
| `constitution.py`, `statutes.py`, `positions.py`, `authority.py`, `store.py` | `knowledge/…` |
| `understanding.py`, `intent.py`, `planner.py`, `query_plan.py`, `presentation.py`, `routing.py`, `conversational.py`, `capability.py` | `query/…` |
| `retrieval.py`, `rerank.py`, `evidence.py`, `calibration.py`, `rescue.py` | `retrieval/…` |
| `generation.py` | `llm/generation.py` |
| `answer.py`, `claim_records.py`, `contracts.py`, `explanations.py`, `obligations.py`, `type_suggestion.py` | `synthesis/…` |
| `verify.py`, `guardrails.py`, `agent_verify.py` | `verification/…` |
| `agent.py`, `tools.py`, `ledger.py`, `attachments.py` | `agent/…` |

**What did not change:** every module keeps its name and contents, so a call such as
`retrieval.candidates(...)` or `generation.generate_turn(...)` reads the same; only the
import line moves (`from legalmind.assist.llm import generation`). The Celery task name
`legalmind.assist.index_document_version` is a NAME, kept as it was, so queued tasks
still resolve. The import-boundary rules (`tests/test_import_boundaries.py`) resolve a
module wherever it sits in the package.

**Tests** follow the same stages, by each test's SUBJECT (not by what it imports — most
tests import `generation` only to stub it): `backend/tests/assist/<stage>/`, plus
`tests/assist/integration/` for the end-to-end Ask flow (`test_assist_ask`,
authorization, conversation memory and scope, multi-source rollout, load). Tests whose
subject is another package stay in `tests/` (API, import boundaries, the authoritative
lane's semantic recognition, deploy preflight). Collection is unchanged: the same 3281
test ids before and after the move. CI job 2 names three of them by path; updated.

**Older records** (`all_lock.md`, CHANGELOG, DAILY_CHANGED, the locked specifications)
name the old paths. They are history and are not edited (rule 22); use the table above.

**Not moved:** `backend/tools/` — several scripts are named by the locked deployment
specification, CI and the production systemd unit (`tools.purge_attachments`); moving
them would break those or require editing locked text.

# DAILY_CHANGED — LegalMind RAG Production programme log

Chronological implementation log for the master roadmap
[docs/LEGALMIND_RAG_PRODUCTION_ROADMAP.md](docs/LEGALMIND_RAG_PRODUCTION_ROADMAP.md).
Newest entry last. Branch `feat/legalmind-rag-production` (local only — no push/PR/merge).
Not the operations log ([docs/00-project/DAILY_CHANGES.md](docs/00-project/DAILY_CHANGES.md)),
not the decision record ([all_lock.md](all_lock.md)).

Every entry: what changed · how it was tested · what was measured · locks amended · commit.

---

## 2026-09-24 — Entry 0: baseline audit (read-only, no code changed)

Audit of the current repository against roadmap §1–§9, taken as the programme baseline.
Do not re-run it unless implementation evidence shows it is stale.

### Live system at baseline (`main` @ `30a1ce8`)

| Domain | Rows | Chunker (live) | Notes |
|---|---|---|---|
| A positions | 79 chunks, 1 per standard, 72 active | `positions-verbatim-2` | 54 from the Constitution; 25 quote MSA template / executed NDA / ToS paper |
| B documents | 3,391 chunks, 37 versions | `clause-aware-4` | flat, ≤2,000 chars, no breadcrumb, no parent |
| C statutes | 5,140 chunks, 17 Acts | **`section-1` live; code is `section-3`** | PR #110 parser fix merged, never re-ingested |

Postgres + pgvector 0.6.0 + pg_trgm; no ANN index (exact scan). Embedder MiniLM-L6-v2 (384,
truncation 512). Production flags: `LEGALMIND_RERANK=on`, `LEGALMIND_POSITION_SYNTHESIS=on`,
planner off, expansion off, rescue on.

### Step 1–9 findings

| # | Step | Finding |
|---|---|---|
| 1 | Source model | Constitution never indexed (`AM-43` r2). The §14 early-termination position is retrievable only as MSA-template cl. 7.2 text tagged `section "14"`; §14's own text, §28.4.1 (contract amount ≠ recoverable amount) and §31.2 historical exceptions are unreachable. No parent_id / section_path / effective dates / supersedes / cross-refs / authority level / historical-exception type. Repeal status is a title substring. `version_role` (FINAL_SIGNED…) exists but assist never reads it. |
| 2 | Ingestion | No gate before search (`index_safely` swallows errors; PARTIAL extraction indexed). No PDF tables. Live statutes corrupt: CPC "s.860", IT Act "s.266", Income-tax "s.659" fabricated; one chunk 128,684 chars, 21 > 20k; 127 duplicate (section, sub-section) groups. |
| 3 | Chunking | Flat by design (`chunking.py:33`); no hierarchy, breadcrumb or expansion. |
| 4 | Embeddings | MiniLM won the 2026-08-26 bake-off (smallest passing). bge-m3 / Qwen3 never measured. Gate constants are MiniLM-calibrated — any swap recalibrates the gate. |
| 5 | Storage | Postgres + pgvector is adequate at ~8.6k vectors. HNSW needs pgvector ≥ 0.8. |
| 6 | Understanding | Deterministic `QuestionUnderstanding` / `RoutePlan`; planner (≤3 rephrasings, not sub-questions) off. No decomposition, entities, section refs, language field. |
| 7 | Retrieval | FTS + trigram (no BM25) ∪ exact vector, RRF k=60. **"Top 3" = `POSITION_LIMIT=3`** and lexical discarded when vector returns anything. Documents 10, statutes 6. No clause-reference lookup for documents; no authority / effective-date filter; no diversity. |
| 8 | Rerank | Cross-encoder on documents only, after the gate, reorders ≤10; positions/statutes never reranked. |
| 9 | Evidence | Gemini gets unlabelled `[i] text`; one answer state; no bundle, no per-sub-question states, no company/contract/user/historical/law/missing distinction. |

Evaluation gaps: faithfulness and citation precision re-run the same verifier on answers that
already passed it (cannot fall below 1.0); no nDCG; no conversation set; no multi-hop,
exception or injection eval cases; one romanised Hinglish case; the 22-question readiness set
exists only in an old scratchpad. Observability: reranker scores, understanding, route and
rescue firing are not persisted; planner/rescue/reading-aid calls get no audit row.

### Legacy locks that conflict with the roadmap (to be amended when implementation reaches them)

| Lock | Conflicts with | Reached at |
|---|---|---|
| `AM-43` r2 — Constitution is not chunked, indexed or retrieved | §1 canonical Constitution + structured retrieval records | PHASE 1 |
| `AM-76` r6 / `AM-28` r2 — no model in the verifier | §11 semantic claim verification | PHASE 11 |
| `AM-58` r1–r2 — only ≤2 prior USER questions | §15 prior verified evidence as retrieval input | PHASE 6 |
| `AM-32` r1 / `AM-45` r2 — domains never merged | §9 multi-source evidence bundle (compatible if partitioned by source) | PHASE 9 |
| `AM-29` r2 — no reuse of legal-lane state names | §9 evidence states (`CONFLICTING`…) | PHASE 9 |
| `AM-26` r2 — smallest passing model | §4 bge-m3 "primary candidate" | PHASE 4 |

Material outside the roadmap's authority (rules 7/21): the "historical MSA says 30 days / no
penalty" variant needs real executed MSAs; only one is supplied. The Constitution's redacted
§31.2 record is the usable source until more is supplied.

---

## 2026-09-24 — Entry 1: PHASE 0 — golden benchmark + failure taxonomy

**Built**
* `backend/tests/assist_eval/rag_benchmark.json` — 76 cases, all 15 roadmap §17 categories
  (A–O, ≥3 each), 14 golden early-termination cases (GT-00 is the roadmap §0 question;
  GT-01…13 are the §17 variants: 6 vs 12 months, lock-in, remainder of term, early exit /
  terminate / cancel early, "we promised 6 months", signed MSA unavailable, historical
  30-day/no-penalty MSA, amount without the signed MSA, Hinglish). Gold = slots of real refs
  (`POS:` standard code · `CONST:` Constitution L1.10 section · `STAT:` Act + section), every
  one verified present in the supplied material on 2026-09-24; `must_not` = wrong-source
  traps; an `answer` block (distinctions, must-not-confirm, refuse) for PHASE 10+ scoring.
  Rule 21: no case authors a legal position; each cites its Constitution/statute source.
* `backend/tools/rag_benchmark.py` — replays the production no-document path of
  `service._ask` (route → primary Domain A/C with production limits → `_consult_fallbacks`),
  **zero Gemini**, **read-only connection**. Per slot: rank within its own domain list +
  failure code (SOURCE_NOT_INDEXED · SOURCE_MISSING · ROUTE_SHORT_CIRCUIT · ROUTE_MISSED ·
  RANK_CUTOFF · RETRIEVAL_MISS · RANK_LOW); per case WRONG_SOURCE / FALSE_ADMISSION.
  Reports Recall@3/@10, Hit@1, MRR, nDCG@5, multi-source completeness, per category and
  for the golden subset. Generation-stage codes named, scored from PHASE 10.
* `backend/tests/test_rag_benchmark.py` — dataset integrity + taxonomy logic (no DB/model; CI-safe).
* `backend/tests/assist_eval/rag_benchmark_baseline.json` — the recorded bar (refs/ranks only, no text).

**Tested** — 3/3 new tests pass; ruff + mypy clean. Two runs byte-identical (deterministic).

**Measured — BASELINE** (production corpus read-only; statutes `section-1`; production flags)

| | recall@3 | recall@10 | hit@1 | MRR | nDCG@5 | multi-source complete | wrong-source | false admission |
|---|---|---|---|---|---|---|---|---|
| all 76 (81 slots) | 0.494 | 0.519 | 0.435 | 0.439 | 0.564 | **0.000** | 0.053 | 0.200 (1/5) |
| golden 14 (18 slots) | 0.333 | 0.333 | 0.143 | 0.213 | 0.290 | **0.000** | 0.143 | — |

Failure codes over 81 slots: RETRIEVAL_MISS 14 · RANK_CUTOFF 11 · SOURCE_NOT_INDEXED 6 ·
ROUTE_MISSED 6 · SOURCE_MISSING 2 · RANK_LOW 2.

Weakest categories: H historical r@3 0.00 · J follow-ups 0.00 · K Hinglish 0.20 (4/5
RANK_CUTOFF — the gold is in the pool, `POSITION_LIMIT=3` cuts it) · G exceptions 0.25 ·
D multi-hop 0.375. Strongest: A exact wording 1.00, F numeric 0.83.

What the golden cases show: GT-00 retrieves the §14 standard at rank 2 **behind the
liability cap** (wrong source), cannot reach §31.2 (not indexed), and never consults
statutes (ROUTE_MISSED — a position hit suppresses the statute fallback). GT-08 ("we
promised 6 months") shows only the liability cap. GT-10 surfaces phantom statute sections
(A&C "s.87", Companies Act "s.470") — the `section-1` corruption, live.

Document half (existing `tools/probe_targeting.py`, gate DB, 64 answerable, no gate):
recall@10 0.641 · hit@1 0.438 · MRR 0.511 · gold@3 0.578 · evidence precision 0.142. The
0.891 in `baseline.json` counts gate-OPEN questions only — a different denominator, not a
regression (recorded 0.625 on 2026-09-18).

**Exit (PHASE 0)** — benchmark covers every roadmap category and the golden variants ✔ ·
deterministic, zero-cost scorer ✔ · every failing slot carries a stage code ✔ · baseline
recorded ✔ · retrieval measured separately from generation ✔.
**Deferred, named:** answer-level scoring (the `answer` block) → PHASE 10/12; the
tautological faithfulness/citation-precision metric in `verify_assist_quality` (re-runs the
same verifier) → PHASE 11/12.

**Locks amended** — none (PHASE 0 touches none).

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
**Commit:** `626005e`.

---

## 2026-09-24 — Entry 2: governance

Owner, in their own words: *"i want industry stnadard rag system for that if you need some
decion to change and update plz … i will give you ownership you do not have to ask me
update it and start phase 1"*. CLAUDE.md gains the master-roadmap section (conflicting locks
are amended by appended record, without asking per lock; rules 7/21/18, the audit trail and
the Gemini cost guard are NOT amendable this way) and a Start-here pointer; docs/README.md
indexes the roadmap and this log. Memory `legalmind-rag-roadmap-ownership`. **Commit:** `e65b42c`.

---

## 2026-09-24 — Entry 3: PHASE 1 — canonical knowledge/source model

**Lock amended — `AM-79` (AB-29)**, amending `AM-43` r2 (*"The Constitution … is not
chunked, indexed or retrieved"*) and the `AM-27`/`AM-32` assist-table lists (+2). Appended
to all_lock.md (19842 → 19921 lines; prior lines byte-identical — the diff is 79 additions,
0 deletions); registry row added and the `AM-43` row annotated; CLAUDE.md,
ARCHITECTURE_REFERENCE.md and CONFLICTS.md references annotated. Working documents
(CONSTITUTION_RECONCILIATION_2026-09-13.md, DOCUMENT_BUILDER_RND.md) left as records.
*Self-correction:* the first draft of the record stated pre-fix counts (672 items); corrected
before commit, so no committed line was changed.

**Built**
* Migration `f4c1e8a2b7d9` — `assist.knowledge_sources` (one row per canonical document
  version: type, title, version, status, authority, jurisdiction, effective_from/to,
  supersedes_id, source file, SHA-256) and `assist.knowledge_items` (hierarchy with real
  parent FK, the document's own `section_path`, clause, content, authority, status,
  cross_references, line span, FTS index). CHECK-constrained vocabularies, none shared with
  a legal axis.
* `legalmind/assist/constitution.py` — deterministic parser (every line → exactly one item;
  list items stay with their rule; tables are their own blocks) + `ingest` (idempotent by
  SHA-256; L1.10 CURRENT supersedes L1.5 SUPERSEDED) + `item_for_section` (a standard's
  pointer back to its section). `tools/ingest_constitution.py`; ops/README.md step.
* `legalmind/assist/authority.py` — the seven-class authority model mapped from metadata
  each domain already records (standard source_document, document version_role, statute
  repeal marker). Unknown execution status → None, never "executed".
* Authority read from the Constitution's own labels: "Historical exceptions/evidence:" and
  Evidence/⚠ notes naming a counterparty placeholder → HISTORICAL_EXCEPTION; §6, §28 and
  "Applicable Law / Legal Basis" → SECONDARY_REFERENCE; §31.6a → UNRATIFIED (wins over all).
  Two false-positive classes found and fixed while measuring: prose+table merged blocks
  tainting current summary tables (§27, §31.16, Appendix C/H), and §15.5's current guidance
  naming the reference NDA placeholder.

**Tested** — `tests/test_knowledge_source_model.py` (8: line coverage, no invented
numbers, historical ≠ policy, law-reading ≠ policy, §31.6a, standards + benchmark refs
resolve, one authority vocabulary, DB ingest + version chain + idempotency);
`test_assist_schema` updated. Full backend suite **2545 passed, 112 skipped (unchanged
count), 0 failed**; ruff + mypy clean.

**Measured (exit criteria)**

| Roadmap §1 exit criterion | Result |
|---|---|
| Original Constitution preserved | file untouched; SHA-256 recorded on its source row |
| Structured rules mapped back to source sections | 701 items (35 sections · 76 subsections · 177 provisions · 412 paragraphs); **0 non-blank lines lost**; **76/76** standards naming a section resolve; **11/11** benchmark Constitution refs resolve |
| Historical exceptions separated from current policy | **16** HISTORICAL_EXCEPTION items, all §31, **0** CURRENT; §31.2's "Established Company Position" CURRENT, its "Historical exceptions" HISTORICAL |
| Authority/version/status metadata available to retrieval | columns + FTS index on every item; 101 SECONDARY_REFERENCE; 9 UNRATIFIED (all §31.6a); version chain L1.10 → L1.5 |

Benchmark re-run: **byte-identical to the PHASE 0 baseline** — expected, as no retrieval
path reads the new tables until PHASE 3 (retrieval records) / PHASE 7 (retrieval). The
`SOURCE_NOT_INDEXED` slots (6) are now backed by stored, labelled items.

**Not done here, named:** statute status as a column (currently a title marker, mapped by
`authority.of_statute`) → PHASE 2 with the statute re-ingestion; L1.5 items (format differs)
→ when a historical-Constitution question needs them; production population
(`tools.ingest_constitution`) → at deploy, not on this branch.
**Commit:** `9cdfda9`.

---

## 2026-09-24 — Entry 4: PHASE 2 — ingestion and parser integrity

*(Resumed after a network interruption; the statute-predicate edits that had not run
were re-applied and verified before continuing.)*

**Lock amended — `AM-80` (AB-30)**, amending `AM-48` r5 (the corpus list) and adding
`statutes.status` to `AM-32`'s table. all_lock.md 19921 → 19999 lines, additions only;
registry row added, `AM-48` row annotated; CLAUDE.md counts updated.

**Built**
* **Statute integrity gate** — `statutes.check_integrity`, run inside `ingest_statute`
  before anything is written. Section quarantine: SUBSECTION_RESTART (units folded
  under one number), NUMBERING_JUMP (> 100, the parser left the Act's numbering),
  DUPLICATE_TEXT, OVERSIZED. Act refusal: > 20% of sections failing, or < 95% coverage.
  Thresholds measured on the 17 Acts (largest genuine gap 49; the CPC Schedule-as-
  sections jump 152). Two calibration fixes found by measuring: Schedules are exempt
  from the sub-section check, and the ceiling counts SECTIONS, not chunks.
* **`section-4`** — `_windows` bounds every statute chunk at 2,000 characters, lossless.
* **Bilingual prints** — `_prefer_latin`: the DPDP Rules 2025 file is 23 Hindi pages
  then 18 English; the English half had been folded under "rule 23". Only this file
  is affected (page-script scan of all 17).
* **`statutes.status`** — migration `a7d3e9b1c5f2`; `_repealed_sql` reads the column;
  `authority.of_statute` is the single derivation, used by ingestion.
* **Document integrity gate** — `chunking.integrity_failures` (FABRICATED_TEXT,
  OVERSIZED, REPEATED_TEXT, CONTENT_LOSS), enforced in `index_document_version`.
* Schedules exempt from the 50-chunk read-time quarantine (Companies Act 2013 Sch. III).
* ops/README.md: the re-ingest step for deploy.

**Tested** — 9 new tests (bounded/lossless windows, folded unit quarantined, numbering
jump spares Schedules, whole-Act refusal, duplicate and lost text, bilingual selection,
document gate pass/fail, a failing version is not searchable). `test_assist_answer_integrity`
repeal tests moved to the column (same intent: one predicate, both paths). Full suite
**2554 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Measured** — scratch DB `legalmind_rag_p2` built from the supplied files by the
current code (position corpus md5-identical to production), statutes before = the
production `section-1` corpus:

| Integrity (statutes) | before | after |
|---|---|---|
| chunks | 5,140 | 4,010 |
| sections with folded units | 30 | **0** |
| numbering jumps > 100 | 5 | **0** |
| chunks > 2,000 chars (max) | 806 (128,684) | **0 (2,000)** |
| sections > 50 chunks | 3 | 1 (Companies 2013 Schedule III — genuine) |
| searchable Acts | 17 | 16 (Income-tax 1961 refused) |

Quarantined: 28 sections across 8 Acts (CPC 10 incl. its folded Orders, Companies 1956 6,
Companies 2013 4, CGST 3, Copyright 2, IT Act 1, A&C 1, DPDP Rules 1). Documents: **37/37**
live versions pass the gate — no false positive.

| Benchmark (76 cases) | PHASE 0 | PHASE 2 |
|---|---|---|
| recall@3 / @10 | 0.494 / 0.519 | **0.506 / 0.531** |
| MRR / nDCG@5 | 0.439 / 0.564 | 0.446 / 0.580 |
| multi-source complete | 0.000 | **0.091** |
| wrong-source rate | 0.053 | **0.040** |
| SOURCE_MISSING | 2 | 1 |

Moved cases: L-03 Companies 2013 s.179 rank 5 → **1** and the repealed 1956 Act no longer
shown; E-02 DPDP s.8 now retrieved (rank 6); O-04 IT Act s.70B now exists (was
SOURCE_MISSING → RANK_CUTOFF); H-04 6 → 4; O-03 1 → 2 (still top-3). Golden subset
unchanged — expected: its failures are Domain A ranking and the unindexed Constitution,
which PHASES 3 and 7 address.

**Exit (roadmap §2)** — no statute section or document version becomes searchable
without passing integrity ✔ · fabricated labels, bad joins, oversized sections,
repeated text, content loss and repeal status all checked ✔ · measured before/after ✔.

**Not done, named:** the DPDP Rules' Hindi text and its Schedules (folded into rule 23,
quarantined) — a Gazette-specific Schedule parser; the Income-tax Act 1961 — needs a
clean official copy (rule 21); production re-ingest — at deploy (ops/README.md).
**Commit:** `aec345e`.

---

## 2026-09-24 — Entry 5: PHASE 2 closure — Income-tax Act, Gazette Schedules, withdrawal

Owner: *"close the remaining Phase 2 items yourself … Do NOT deploy yet"*.

**Lock amended — `AM-81` (AB-31)**, amending `AM-80` r5. all_lock.md 19999 → 20056,
additions only; registry row; CLAUDE.md counts.

**Income-tax Act, 1961 — obtained, verified, ingested (branch/scratch only).**
* India Code moved to `indiacode.gov.in` (a DSpace 7 app); the repository API located
  handle `123456789/620179` — the Act item holds ONE file, the original Gazette of
  14 September 1961, and no sectional text. Downloaded to
  `legal-docs/Indian_Laws_and_Acts/Income_Tax_Act_1961_indiacode.pdf` (new file; the
  2011 Taxmann print stays on disk). SHA-256 `f21154ca…`; India Code's declared MD5/size
  do not match the served bytes — recorded in the registry note, not reconciled.
* It passes integrity: 265 sections, 450 chunks, 5 quarantined, coverage 99.99%.
* **Limit, stated:** this is the Act AS ENACTED. The consolidated as-amended text
  (which carries ss. 194J/194C, cited by Constitution §6.1) is published only at
  `incometaxindia.gov.in`, which answered HTTP 403 (Akamai edge) to this host with and
  without browser headers; the Department of Revenue's Acts page links there. The
  title says "as enacted … later amendments NOT included". Scanned Gazette: the OCR
  text layer has character errors ("Cbllfitof"), which lexical retrieval will feel.
* No Markdown copy is added to the repository: locked 54.6 keeps source text out of
  it; the registry entry is the in-repo representation (provenance, handle, SHA).
* Registry `source` exceeded its 128-character column and failed at ingest — found by
  the rebuild; a column-length test now guards every entry.

**DPDP Rules Schedules — root cause and fix.** A Schedule counted only in the text's
closing quarter; the Rules' seven Schedules span the last half, so the First–Fourth
folded into rule 23. Now a Schedule counts after the body of the last section — the
arrangement's ceiling, or (no arrangement, as here) the running maximum at the first
numbering restart. A second latent bug surfaced while measuring: the footnote fold
compared two Schedules by NAME, and "FOURTH" < "THIRD", so later Schedules folded into
earlier ones (the Arbitration Act lost its Fourth–Seventh the same way). Fixed.

**Withdrawal.** A refused re-ingest used to leave the old chunks answering; now it marks
the row WITHDRAWN (excluded on both paths, nothing deleted). `replaces_file_sha256`
lets the India Code copy take over the old Income-tax row in production.

**Tested** — 6 new tests (Schedules without an arrangement + ordinal order; real DPDP
Rules 7 Schedules / rule 23 bounded / 0 quarantined; real India Code Income-tax passes
integrity; withdrawal stops serving; a replacement takes over its row; registry fits
the columns). Full suite **2560 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Measured** — scratch DB rebuilt from the current code:

| | production (section-1) | PHASE 2 first pass | **PHASE 2 closed** |
|---|---|---|---|
| searchable Acts | 17 | 16 | **17** |
| statute chunks | 5,140 | 4,010 | 5,036 |
| folded sections · jumps > 100 · chunks > 2,000 | 30 · 5 · 806 | 0 · 0 · 0 | **0 · 0 · 0** |
| Schedules as their own units | 0 | — | **46** |
| DPDP Rules quarantined | — | rule 23 (44 chunks) | **0** |

| Benchmark (76) | PHASE 0 | first pass | **closed** |
|---|---|---|---|
| recall@3 · recall@10 | 0.494 · 0.519 | 0.506 · 0.531 | **0.506 · 0.519** |
| MRR · nDCG@5 | 0.439 · 0.564 | 0.446 · 0.580 | 0.441 · 0.578 |
| multi-source complete | 0.000 | 0.091 | 0.000 |
| wrong-source rate | 0.053 | 0.040 | **0.040** |

Read honestly: E-02 (DPDP Act s.8) fell from rank 6 to 7 — past the statute limit of
6 — because the DPDP Rules' Second and Third Schedules are now REAL, correctly labelled
units that mention "Data Fiduciary"; O-03 moved 1 → 3 as the CPC's First Schedule became
its own unit. The first pass's E-02 gain was partly an artefact of those Schedules being
missing. This is a candidate-depth / ranking limit (PHASE 7 broad retrieval, PHASE 8
cross-domain rerank), not an integrity defect, and it is not tuned here.

**Exit (roadmap §2)** — met: every Act searchable passes integrity; no fabricated,
folded, oversized or duplicate section is stored; repeal and withdrawal are status
metadata; documents gated (37/37 pass). Production unchanged.
**Commit:** `962ed0b`.

---

## 2026-09-24 — Entry 6: PHASE 3 — hierarchical semantic chunking

**Lock amended — `AM-82` (AB-32)**: +1 assist table (`knowledge_item_embeddings`),
+`knowledge_items.breadcrumb`. all_lock.md 20056 → 20118, additions only; registry;
CLAUDE.md; ops/README.md; CHANGELOG.

**Built**
* **Constitution retrieval records** — migration `b8e2f6a4d1c3`. Children = PARAGRAPH
  items (rule + its list conditions). Breadcrumb from metadata only ("Legal Constitution
  L1.10 · 31. … · 31.2 Early Termination — MSA …" + an authority label for historical
  evidence / the company's reading of law), indexed and embedded, never content.
* `constitution.search` — hybrid (length-normalised lexical + vector, RRF), one child per
  parent, UNRATIFIED never returned, HISTORICAL carried with its status, Domain A
  authorization (`positions.can_read`, now the one predicate for both).
* **Parent restoration at read time** — `constitution.expand` (sibling paragraphs,
  non-current ones labelled), `statutes.expand_section` (whole section headed Act ·
  section · marginal note), `store.expand_chunk` (neighbours inside the same evidence
  row, so `AM-27` r4 holds). Not yet wired into generation (PHASE 8).
* **One chunk per (Act, section)** in `search_statutes`.
* **DRY** — `store.embed_into` replaces three copies of the embedding loop (positions,
  statutes, Constitution).
* Benchmark: a **Constitution lane**, scored apart from production.

**Measured, and two decisions the measurement made**
1. *Statute breadcrumb embedding — rejected.* Embedding "Act · Section · note" + text
   moved the MiniLM-calibrated gate: O-02 (must refuse, "current law on TDS for
   professional fees") drew six unrelated units → false admission 0.2 → 0.4, for one
   rank on O-03. Ablation (content-only re-embed) restored 0.2. The breadcrumb stays as
   the expansion header only. (`AM-82` r5.)
2. *Constitution lexical ranking.* Raw shared-word count let the §27 Counsel checklist
   TABLE outrank §14. Length-normalised `ts_rank` (norm 1) measured over the 41
   Constitution slots: with vectors MRR 0.798 → 0.822, r@3 0.878 → 0.902, r@10 equal;
   lexical-only MRR 0.445 → 0.645 (the no-model / CI path). Adopted, with 100 candidates.

**Dataset correction (disclosed):** 15 slots accepted only §14; §31.2 states the same
position in the Constitution's own words ("read together with Section 14") and is now
accepted beside it. Production numbers are unaffected (no production path reaches
Constitution refs yet); the Constitution lane rose 0.732 → 0.878 recall@3 from the
correction alone.

| Constitution lane (41 slots) | recall@3 | recall@6 | recall@10 | MRR |
|---|---|---|---|---|
| PHASE 2 (no retrieval path) | 0 | 0 | 0 | 0 |
| **PHASE 3** | **0.878** | **0.902** | **0.902** | **0.810** |

Golden: 13/14 reach their Constitution position at rank 1–2 — GT-00 [§14/§31.2 1, §31.2
historical 1, §28.4.1 2], GT-10 [1, 1], Hinglish GT-12 1. Miss: GT-02 ("6-month lock-in").

| Production (76) | PHASE 2 closed | PHASE 3 |
|---|---|---|
| recall@3 · MRR | 0.506 · 0.441 | 0.506 · 0.441 |
| wrong-source · false admission | 0.040 · 0.200 | 0.040 · 0.200 |

Production is unchanged in outcome by design: the Constitution is not routed until
PHASE 7, and one-per-section freed statute slots without moving a measured gold.

**Tested** — 7 new tests (breadcrumbs, search one-child-per-parent + authorization,
expansion labels history, statute collapse + section expansion, document expansion
within its evidence row). Full suite **2568 passed, 112 skipped (unchanged), 0 failed**;
CI-like run (no model, no source material) on the touched files 189 passed, 9 skipped;
ruff + mypy clean.

**Exit (roadmap §3)** — rules/exceptions/conditions stay connected (list items attached;
history labelled apart) ✔ · child retrieval identifies precise evidence (Constitution
r@3 0.878) ✔ · parent/context expansion available for all three corpora ✔ · duplicate
children of one parent do not crowd out others (Constitution + statutes) ✔.
**Named, not done:** document breadcrumb embeddings — they would move the calibrated
document gate, so they are measured in PHASE 4 with the embedding bake-off; wiring the
expansions into generation — PHASE 8.

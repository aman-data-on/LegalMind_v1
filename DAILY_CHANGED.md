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
**Commit:** `5748870`.

---

## 2026-09-24 — Entry 7: PHASE 4 — embedding benchmark + selection

**Lock amended — `AM-83` (AB-33)**, amending `AM-26` r2 ("smallest that passes") to the
roadmap §4 rule. all_lock.md 20118 → 20181, additions only; registry row + `AM-26`
annotation; CLAUDE.md; CHANGELOG; calibration.py provenance note.

**Built**
* `tools/benchmark_embedders.py` — per-domain vector ranking (Constitution, positions,
  statutes, documents), refs collapsed to the SOURCE, recall@1/3/10/30/50, MRR, nDCG@5,
  per category and difficulty, index time, query latency, peak RSS; read-only; block
  cache (resumable). Zero Gemini.
* `OnnxEmbeddingBackend` — `pooling` (mean / CLS / last token), `max_length`, empty KV
  cache for decoder exports (Qwen3), `verify_manifest` checks EVERY file incl. >2 GB
  external weights, streamed. `provision_model` streams, resumes (Range), `--onnx`/`--extra`.
* Models provisioned and pinned: `BAAI/bge-m3@5617a9f6…` (official ONNX, 2.27 GB weights),
  `onnx-community/Qwen3-Embedding-0.6B-ONNX@c25a394d…` (2.09 GB). Outside the repo.

**Incident** — the host rebooted mid-run (the first bge-m3 pass lost with `/tmp`). The
cache moved to `~/.legalmind/bench-cache`, blocks of 256 saved as they finish, the runner
detached (`setsid`); a reboot now costs one block.

**Measured** (full corpora; record `tests/assist_eval/embedder_benchmark_2026-09-24.json`)

| | MiniLM (384) | bge-m3 (1024) | Qwen3-0.6B (1024) |
|---|---|---|---|
| Constitution r@3 · r@30 | .927 · 1.0 | .951 · 1.0 | .927 · 1.0 |
| Positions MRR · r@30 | .616 · .895 | .742 · .895 | .793 · .895 |
| Statutes MRR · r@30 · r@50 | .255 · .667 · .667 | .478 · .722 · .833 | .485 · .778 · .778 |
| Documents MRR · r@10 · r@30 | .628 · .969 · 1.0 | .855 · 1.0 · 1.0 | .771 · .969 · 1.0 |
| Hinglish (K) MRR | .539 | .820 | .938 |
| **Gate kept at 12/13 refused** | **45/64** | 31/64 | 41/64 |
| query p50 · peak RSS | 2.8 ms · 1.3 GB | 44.7 ms · 4.5 GB | 99.3 ms · 13.8 GB |
| full re-embed | 4 min | 73 min | 115 min |

Gate re-swept for every model with three features (gap-to-mean, gap-to-second, z-score):
none lets bge-m3 or Qwen3 separate as well as MiniLM's current rule.

**Decision (roadmap §4 rule)** — the target workload after PHASES 7–8 is a 30–50 pool,
reranked, gated. At that depth the larger models add nothing on three of four domains;
their first-rank gain is what the reranker supplies; and they cost the gate 4–14
answerable questions. **MiniLM stays.** Qwen3 rejected on cost (13.8 GB on a 15 GB host).
bge-m3 recorded for the one measured gap — statute candidate recall (+3/18 at r@50) —
to be re-measured after PHASE 8 as a Domain C-only embedder with its own calibration.
No re-embedding, no schema change, production unchanged.

**Tested** — 2 new tests (every manifest file incl. external weights verified; pooling
modes normalised and distinct). Full suite **2570 passed, 112 skipped (unchanged),
0 failed**; ruff + mypy clean.

**Exit (roadmap §4)** — benchmarked on the actual corpora for every listed dimension
(recall@3/@10, Hit@1, MRR, nDCG@5, source-domain, Constitution / clause / statute,
paraphrase, Hinglish, latency, RAM, indexing time, re-index cost) ✔ · selection made by
the stated rule ✔ · no change without demonstrated workload gain ✔.
**Commit:** `41c1b95`. *Owner accepted PHASE 4: MiniLM is the production baseline, kept
reversible (identity is configuration; the backend loads mean/CLS/last-token models; the
bge-m3 and Qwen3 weights stay provisioned); bge-m3 is NOT rejected — re-test it for
statutes after PHASE 8 reranking.*

---

## 2026-09-24 — Entry 8: PHASE 5 — index and storage

**Lock recorded — `AM-84` (AB-34)**: Postgres stays; and the owner's rule that embedding
similarity produces candidates, never the answerability decision (target for PHASES
8–9; the current gate unchanged until then). all_lock.md 20181 → 20241, additions only;
registry; CLAUDE.md; CHANGELOG; ASK_TARGET_ARCHITECTURE stage 7 annotated.

**Built** — `tools/benchmark_storage.py` (read-only; query vectors precomputed so the
database is what is timed; TEMP-table growth test on the scratch DB only). Record:
`tests/assist_eval/storage_benchmark_2026-09-24.json`. Host now 6 CPUs.

**Measured** (scratch corpus; MiniLM 384-d; exact scan, no ANN)

| | p50 | p95 |
|---|---|---|
| Vector KNN statutes (5,036) k = 10 / 30 / 50 / 100 | 1.9 / 2.0 / 2.1 / 2.2 ms | ≤ 2.6 ms |
| Vector KNN Constitution · positions · one document, k = 50 | 0.6 · 0.5 · 0.8 ms | < 1.1 ms |
| Exact scan = numpy ground truth (top-50 overlap) | **1.0** on every domain | |
| FTS statutes · current-only filter · exact Act+section | 15.7 · 13.9 · 0.3 ms | 46 · 38 · 0.4 ms |
| Production hybrid @50: statutes · positions · Constitution · document | 150 · 3.3 · 9.4 · 6.9 ms | 199 · 5.0 · 12.7 · 20.0 ms |
| **One-statement fusion** (FTS + vector + status + exact ref, RRF @50) | **20.5 ms** | 43 ms |
| Concurrency 1 / 4 / 8 / 16 clients (statute KNN k = 50) | 405 / 1,065 / 1,047 / 809 q/s | 2.5 / 4.3 / 8.5 / 24 ms |
| Postgres RSS idle → 16 clients | 279 → 911 MB | |
| Growth ×10 (50,360) · ×40 (201,440) exact k = 50 | 27 · 106 ms | 28 · 118 ms |
| Assist corpus on disk | ~45 MB | |

**One optimisation tried and reverted.** The statute lexical path is 150 ms because it
scores every row (lexeme count, `ts_rank`, a per-row title ratio). A per-Act title CTE +
GIN-indexed candidate prefilter was built; the old and new functions were run over
157 questions × 2 depths: **0 differences, and no speedup** (138 → 148 ms) — legal
questions share common lexemes with ~65% of sections, so the prefilter keeps most rows.
No gain, so no change. The one-statement fusion (20 ms) shows the store is not the
limit; the lane design is PHASE 7's.

**Tested** — full suite **2570 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy
clean. Production and the production corpus untouched.

**Exit (roadmap §5)** — no measured need to migrate (latency, concurrency, memory,
features) ✔ · exact baseline established for any future ANN ✔ · lexical, metadata,
exact-reference and dense retrieval coexist in one store and one plan ✔.
**Commit:** `f8e00cc`. *Correction: Entry 8 says all_lock.md 20181 → 20241; it is 20240.*

---

## 2026-09-25 — Entry 9: PHASE 6 — query understanding + conversational rewriting

**Lock recorded — `AM-85` (AB-35)** — the plan's contract; amends nothing locked.
all_lock.md 20240 → 20287, additions only; registry; CLAUDE.md; CHANGELOG.

**Built**
* `legalmind/assist/query_plan.py` — the roadmap §6 Structured Query Plan, deterministic:
  composes `understanding.understand` + `planner.plan_lexical`; adds language (en / hi /
  hinglish), figures ("6 months"), claims (reported speech, promises — context, never
  evidence, never a sub-question), document_state (UNAVAILABLE on "cannot find", or when
  a contract is needed and `has_document=False`), lanes (COMPANY_POSITION · CONTRACT ·
  LAW · HISTORICAL_EXCEPTION · USER_ASSERTION · MISSING_DOCUMENT), sub-questions with
  their own lanes and queries.
* `planner._TERMS` — early-exit cue widened to every roadmap §6 phrasing and the golden
  variants; the canonical term is now §14's own words ("early exit fixed-term
  commitment"). It was "termination for convenience …", §13's topic.
* `tools/eval_query_plan.py` — scores against existing labels only (matrix, the
  benchmark's `answer.distinguish`), plus a retrieval check raw vs planned.

**Measured** (zero Gemini; record `tests/assist_eval/query_plan_eval_2026-09-25.json`)

| | result |
|---|---|
| Lane recall — company position · law · user assertion · missing doc · historical | 10/10 · 2/2 · 3/3 · 5/5 · 2/3 |
| Special-lane false positives (cases labelling none) | **0** |
| Convergence to §14 (5 roadmap phrasings + 13 golden variants) | **18/18** |
| Language: Hinglish recall · English precision | 5/5 · 1.0 |
| Golden figures | GT-00 [6, 12 months], GT-01/02/08 [6], GT-03 [12], GT-10 [30 days] |
| GT-00 decomposition | 4 sub-questions, the client's claim kept as context, state UNAVAILABLE |
| Constitution lane, raw → plan sub-queries | MRR 0.695 → **0.822** (r@3 0.927 equal) |
| Positions lane, raw → plan sub-queries | r@3 0.702 → **0.754**, MRR 0.613 → 0.657 |
| Existing understanding on the 76-case matrix | requested_fact 0.553 · authority 0.553 · temporal 1.0 · jurisdiction 1.0 |

The HISTORICAL miss is GT-00, which names no history; its §31.2 exceptions reach the
answer through retrieval. The matrix scores are the existing routing layer, recorded
as the baseline and not retuned: most gaps are DOCUMENT authority that comes from an
attached document rather than the words, and requested-fact label debates.

**Fixes found by measuring:** CONTRACT from whole-question signals (now per part, and
only when the reader points at an agreement — `document_target` reads "Contract Act"
and "contract value" alike); LAW on the bare word "compensation" (now enforceability
wording or an AMOUNT of a sum); a default COMPANY_POSITION lane for unplaced questions
(removed — "weather in Pune" has no lane); I-04 (contract needed, none attached).

**Tested** — `tests/test_query_plan.py` (5); `test_assist_planner` guard satisfied without
weakening it (a cue may carry no digit — quantifiers rewritten). Full suite **2575 passed,
112 skipped (unchanged), 0 failed**; ruff + mypy clean. Not wired into production yet.

**Exit (roadmap §6)** — deterministic extraction + structured plan with every listed
field ✔ · equivalent wording converges (18/18) ✔ · complex questions decompose into
focused sub-queries ✔ · simple queries stay deterministic and free ✔ · measured retrieval
gain from the plan ✔.
**Commit:** `eedba02`. *Correction: Entry 9 says all_lock.md 20240 → 20287; it is 20305.*

---

## 2026-09-25 — Entry 10: PHASE 7 — broad hybrid + metadata retrieval

**Lock recorded — `AM-86` (AB-36)** — amends nothing locked. all_lock.md 20305 → 20364
(counted from the file), additions only; registry; CLAUDE.md; CHANGELOG.

**Built**
* **Candidate mode** in `search_positions`, `search_statutes`, `store.search_hybrid`:
  lexical + dense fused, dense ungated (`AM-84` r4). Defaults untouched — the default
  calls pass exactly today's arguments (a first version passed `gated=` always and broke
  8 tests whose stubs replace `_vector_neighbours`; fixed by passing it only in candidate
  mode).
* `legalmind/assist/retrieval.py` — `candidates(db, plan, route, …)`: sub-questions +
  whole question × lane domains + the router's primary and fallback domains, depth 50,
  Constitution on the positions permission, exact Constitution-section reference, RRF per
  domain, dedupe by source. `select(pool, plan)`: 5–12 units, diversity-first per
  (sub-question, lane, domain); unplaced questions draw only from primary domains.
* `query_plan.plan(prior=…)` — a turn with no topic inherits the latest prior USER
  question's (roadmap §15; only the topic carries, never claims or figures; `AM-58`).
* `tools/rag_benchmark.py` — `pool` mode beside the unchanged production path; nDCG now
  counts each gold slot once (it could exceed 1).

**Dataset correction (disclosed):** six gold entries named `AM-65`'s RETIRED standards
(LIAB-CARVEOUTS, FORCE-MAJEURE ×2, RETURN-DESTRUCTION, COMPELLED-DISCLOSURE) — never
retrievable by design (`AM-71`); the PHASE 0 check tested chunk presence, not status.
Corrected from the Constitution's own text (§9's closed cap position for D-01/G-01/J-02;
no ratified source for C-05/G-04; D-03 keeps its survival slot) with the retired codes
as `must_not`; `test_no_gold_reference_is_a_retired_standard` guards it. Baseline
re-recorded.

**Measured by iteration** (each step measured, kept or fixed):

| step | pool recall | evidence recall | false admission |
|---|---|---|---|
| first pool | 0.852 | 0.630 | 0.20 |
| + router-domain fallback, topic inheritance | 0.936 | 0.705 | 0.20 |
| + fallback domains in the pool, statute vectors fused when an Act is named | 0.974 | 0.731 | **0.60** ✗ |
| + unplaced questions take evidence from PRIMARY domains only; named-Act vectors appended, not re-ranked (restored IT Act s.70B) | **0.987** | **0.705** | **0.20** |

| Final (76 cases, 78 slots) | production (unchanged) | PHASE 7 evidence | PHASE 7 pool |
|---|---|---|---|
| recall | 0.577 @10 · 0.564 @3 | 0.705 | **0.987** |
| golden (18 slots) | 0.333 | 0.778 | **1.000** |
| hit@1 · MRR | 0.508 · 0.497 | 0.657 · 0.628 | — |
| multi-source complete | 0.000 | 0.200 | — |
| wrong-source · false admission | 0.040 · 0.200 | 0.026 · 0.200 | — |

Production retrieval proven unchanged: the previous commit's benchmark, run in a
throwaway worktree on the same data, gives identical shown sources and slot ranks for all
76 cases. Pool miss: H-02 only (s. 194J not in the as-enacted 1961 text). In pool but not
in evidence: 22 (RANK_CUTOFF) — the reranker's job. Wrong sources left: J-01 (the
liability cap beside early termination), M-02 (an unanswerable question) — ranking and
sufficiency, PHASES 8–9.

**Tested** — `tests/test_retrieval_pool.py` (3), retired-gold guard (1). Full suite **2579
passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Exit (roadmap §7)** — gold present in the candidate pool for nearly every answerable
query (0.987; the one miss is absent from the corpus) ✔ · dense + lexical + metadata +
exact reference fused, deduplicated ✔ · top-3 dependency absent from the new path ✔ ·
diversity keeps a required statute from being displaced (test) ✔.
**Named:** production switches onto this path with PHASES 8–9 (flagged, `AM-28`-measured).

Commit: `d061e0c`.

## 2026-09-25 — Entry 11: PHASE 8 — reranking + parent/context reconstruction

**Lock recorded — `AM-87` (AB-37)** — amends nothing locked. all_lock.md 20364 → 20432
(counted from the file), additions only; registry; CLAUDE.md; CHANGELOG.

**Built**
* `rerank.scores()` — one scoring path shared by `reorder` and the pool rerank; None
  when the reranker cannot run (the caller keeps its order).
* `retrieval.rerank(pool, plan)` — cross-encoder over the top 30 of the STATUTES and
  DOCUMENT pools against the whole question; then version before relevance (a
  non-CURRENT source sorts behind current ones unless the question asks about the past —
  the repealed Companies Act 1956 s.291 had been promoted for L-03). Statute candidates
  now carry authority and status.
* `retrieval.select` — unrequested domains offer their best candidate in the first
  round only.
* `retrieval.with_context` + `constitution.expand` rewritten to the section level:
  a Constitution paragraph gets its whole SECTION/SUBSECTION (provision headings kept,
  non-current paragraphs labelled "historical evidence, not current policy", the law
  reading labelled "the company's reading of the law"), ≤ 4,000 chars windowed around
  the hit; statutes their section; documents their neighbours; the span always inside.
* `tools/rag_benchmark.py` — `pool_reranked` block (rerank latency, context stats);
  `tools/retest_statute_embedder.py` — the owner-ordered bge-m3 statute retest.

**Measured by iteration** (each variant measured; kept or rejected):

| variant | evidence recall | hit@1 | wrong-source | golden wrong | false adm. |
|---|---|---|---|---|---|
| PHASE 7 (no rerank) | 0.705 | 0.687 | 0.026 | 0 | 0.2 |
| rerank all domains, max over sub-questions | — | 0.582 | 0.066 | 0.143 ✗ | — |
| rerank all domains, whole question (d15, blends) | — | — | 0.066 ✗ | 0.143 ✗ | — |
| statutes + documents only, whole question, d30 | 0.756 | 0.702 | 0.026 | 0 | 0.2 ✔ |
| + every domain offered to unplaced questions | 0.782 | 0.731 | 0.040 ✗ | 0 | 0.6 ✗ |

The last row was built, measured and **reverted**: +2 of 78 slots is not worth tripling
false admission before a sufficiency gate exists; `AM-86` r3 stands. Depth (under the
broadened selection): d10/d20/d30 recall 0.756/0.769/0.782 at 0.35/0.7/1.06 s.

| Final (76 cases, 78 slots) | production (unchanged) | PHASE 7 evidence | PHASE 8 reranked |
|---|---|---|---|
| recall | 0.577 @10 | 0.705 | **0.756** |
| hit@1 · MRR · nDCG@5 | 0.508 · 0.497 · 0.551 | 0.687 · 0.645 · 0.576 | **0.702 · 0.690 · 0.604** |
| multi-source complete | 0.000 | 0.000 | **0.200** |
| wrong-source · false admission | 0.040 · 0.200 | 0.026 · 0.200 | 0.026 · 0.200 |
| golden recall · wrong-source | 0.333 · — | 0.778 · 0 | 0.778 · 0 |

Rerank p50 1,063 ms, p95 1,198 ms (CPU, 30 pairs). Context: 362 items, span inside 1.0,
p50 2,615 chars, max 4,191; GT-00/GT-10's §14 contexts carry the Applicable Law caveat.
Remaining: 18 RANK_CUTOFF (4 golden) — PHASE 9's bundle and sufficiency; SOURCE_MISSING
H-02 (not in the corpus).

**bge-m3 statute retest (owner instruction, PHASE 5)** — 18 statute slots, identical
lexical lane and rerank, cached vectors, zero Gemini: pool r@50 0.889 both; reranked r@1
0.278 vs 0.333, r@3 **0.611 vs 0.556**, r@6 0.722 vs 0.611, MRR 0.448 vs 0.465. No material
gain; MiniLM stays (`AM-83`). Result: `tests/assist_eval/statute_embedder_retest_2026-09-25.json`.

**Tested** — `tests/test_retrieval_pool.py` (+3: repealed source behind current, no
reranker keeps order, span never dropped from context), Constitution section-context
test (+1). Full suite **2583 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Exit (roadmap §8)** — reranking improves top-rank quality measurably (MRR 0.645 →
0.690, recall 0.705 → 0.756) without raising wrong-source ✔ · repealed/superseded sources
never outrank current ones (test) ✔ · every selected span has its parent context, span
inside (1.0) ✔ · latency measured (p95 1.2 s) ✔. **Named:** golden recall unchanged at
0.778 — its 4 misses are ranking inside the Constitution/positions, which the
cross-encoder was measured to harm; PHASE 9's evidence bundle takes them.

Commit: `9aabe1f`.

## 2026-09-25 — Entry 12: PHASE 9 — evidence bundle + authority/version/temporal controls

**Lock recorded — `AM-88` (AB-38)** — amends `AM-86` r3 and `AM-85` narrowly.
all_lock.md 20432 → 20512 (counted from the file), additions only; registry; CLAUDE.md;
CHANGELOG.

**Built**
* `legalmind/assist/evidence.py` — `build(db, plan, pool, selected) -> Bundle`: every
  unit judged (kind, parent context, relevance, reason); parts per sub-question with a
  state; `Assertion` (claim, figures, unstated by any company position, stated_by kinds);
  `missing_document`; `shown()` empty when nothing is answerable.
* Sufficiency per unit: UNRATIFIED never · non-CURRENT only for history/past questions ·
  cross-encoder (best of whole question and topic-carrying sub-queries) on the PARENT
  CONTEXT ≥ domain floor · named Constitution section passes · no reranker fails closed ·
  documents also need the calibrated gate (`Pool.document_gate`, the reader's own
  question only).
* `retrieval.kind_of`, `retrieval.named_sections`; kind-aware `select`, context-only
  lanes get a round.
* `query_plan`: a claim about signed paper opens HISTORICAL_EXCEPTION (Phase 6's one
  lane miss, GT-00).
* `tools/rag_benchmark.py` — `bundle` block (answerable kept, part states, reasons,
  golden representation, per-unit dump).

**Measured by iteration** (zero Gemini; each kept or fixed):

| step | recall | golden | wrong | false adm. | kept | precision |
|---|---|---|---|---|---|---|
| floors on whole question vs span | — | — | — | — | — | Constitution unusable: gold median −11 on the bare paragraph |
| + parent context scored (Constitution gold median −11 → −1.0) | 0.641 | 0.667 | 0 | 0 | 0.82 | 0.474 |
| + `shown()` bug fixed (a whole-question source outside every part was dropped — E-04) + best of sub-queries (Hinglish, follow-ups) | 0.692 | 0.778 | 0 | 0 | 0.91 | 0.429 |
| + statute floor −3 → −2 (plateau; same recall, precision up) | 0.692 | 0.778 | 0 | 0 | 0.91 | 0.447 |
| + kind-aware selection, context lanes, signed-claim → history | **0.718** | **0.889** | **0** | **0** | **0.925** | **0.457** |

Documents, held-out Tier-2 77: cosine gate 44/64 kept, 12/13 refused; cross-encoder
alone keeps 31 at 12 refused (worse); gate AND cross-encoder ≥ −6 keeps 43, refuses 12 —
chosen, so similarity never admits alone. Other floors are calibrated on the PHASE 0
benchmark (no held-out set for them; rule 21) — disclosed as a limitation.

| Final (76 cases, 78 slots) | production | PHASE 8 reranked | PHASE 9 bundle |
|---|---|---|---|
| recall | 0.577 @10 | 0.782 | 0.718 |
| golden recall · hit@1 | 0.333 · — | 0.889 · 0.786 | 0.889 · 0.857 |
| precision · mean shown | — | 0.267 · 5.0 | 0.457 · 2.7 |
| wrong-source · false admission | 0.040 · 0.200 | 0.026 · 0.200 | **0 · 0** |

(PHASE 8 reranked now includes kind-aware selection: golden 0.778 → 0.889, recall 0.756
→ 0.782, multi-source 0.2 → 0.3.) GT-00: parts all SUPPORTED; kinds COMPANY_POSITION
(§14), HISTORICAL_EXCEPTION, LAW (§28.4.1, the company's reading); signed MSA
UNAVAILABLE; "6 months" stated by no company position (stated only by LAW/history).
Admitted with empty gold: G-04, N-01, N-02 — ordinary positions retrieved; the answer
behaviour belongs to PHASES 10–11. Planner eval re-recorded (historical lane 2/3 → 3/3;
its slot counts also moved 41 → 44 / 57 → 54 because the PHASE 7 gold corrections
post-date the first record).

**Tested** — `tests/test_evidence_bundle.py` (6: repealed never answers a current
question; UNRATIFIED never supports; no reranker fails closed; a document needs its gate;
the golden kinds apart with the assertion recorded; irrelevant → INSUFFICIENT, nothing
shown), planner signed-claim test (1). Full suite **2590 passed, 112 skipped
(unchanged), 0 failed**; ruff + mypy clean.

**Exit (roadmap §9, §14)** — a structured bundle with authority, version, citation,
exact text, relevance and unresolved parts ✔ · the five states (four produced;
CONFLICTING named for PHASE 12) ✔ · the six distinctions kept apart ✔ · GT-00
represented exactly as §9 lists ✔ · a non-current source never answers a current
question (test) ✔ · similarity never decides answerability alone ✔ · wrong-source and
false admission 0 ✔. **Named:** recall in `shown` is 0.718 vs 0.782 before the filter —
the price of zero wrong sources; 21 RANK_CUTOFF remain.

Commit: `87a9dcc`.

## 2026-09-25 — Entry 13: PHASE 10 — conversational generation with Gemini

**Lock recorded — `AM-89` (AB-39)** — amends `AM-30` t2, `AM-30` t3 / `AM-32` r4 (as
amended by `AM-67`) and `AM-79` r6 narrowly. all_lock.md 20512 → 20604 (counted from the
file), additions only; registry; CLAUDE.md; CHANGELOG.

**Built**
* `legalmind/assist/answer.py` — `render` (supporting sources only, one excerpt per
  distinct parent context, each labelled by kind with a reader-facing citation; [A] =
  the question, the reader's assertions and the code's figure finding; [M] = the missing
  paper, the unanswered parts, and "nothing beyond the excerpts"; the part states),
  `respond` (no call for an unanswerable bundle; egress locator screen on every kind;
  one call; `check`; fallback), `check` (the mechanical checks, `AM-89` r4), `fallback`.
* `generation.generate_bundle_answer` + `BUNDLE_PROMPT_TEMPLATE` (`bundle-answer-5`)
  through the unchanged single seam.
* `guardrails._words` reads "eighteen per cent." / "twenty-four" as 18 / 24 percent
  (13–19 added to the number words) — shared, so every caller's figure check gains it.
* `tools/eval_generation.py` — offline stub, `--live`, and `--recheck` (re-runs every
  check on stored drafts with zero calls); `rag_benchmark.plan_case` / `bundle_for`
  shared.

**Offline first, zero calls:** stub over all 65 answerable bundles — the first stub run
found the figure check reading "§14"/"section 73" as figures (fixed: a figure is a
number WITH its unit, `AM-78`'s rule); then 100% pass, prompts ~2,000 tokens.

**Measured live (gemini-3.6-flash, `LEGALMIND_ENVIRONMENT=development`, scratch
corpus), diagnose → fix → retest:**

| run | prompt | calls | pass | invalid markers | verdicts | what the diagnosis found |
|---|---|---|---|---|---|---|
| 1 | answer-1 | 65 | 0.42 | 68 | 22 | [M] used for "cannot confirm" with no line to cite; verdict screen firing on the position's own "unacceptable"; "eighteen per cent." unread; drafts NOT stored (tool defect, fixed) |
| 2 | answer-2 | 65 | 0.71 | 21 | 1 | [M] still wanted when nothing was missing; "missing any policy for 6 months" not read as negation; "Pvt. Ltd." split as a sentence |
| 3 | answer-3 | 65 | 0.71 | 13 | 2 | no gain → Gemini stopped, re-checked offline: [A] cited when not listed (rule 4's own example); next-step verbs in other forms |
| 4 | answer-4 | 65 | 0.79 | 5 | 2 | "[4]" — the model citing prompt rule 4's own number |
| 5 | answer-5 targeted: 7 failing + 14 golden | 19 | 0.95 | 0 | 0 | GT-10 correctly stopped: current policy cited to a historical excerpt |

Between runs every check change was re-measured on the stored drafts with zero calls;
only a prompt/payload change got a new live run. The owner asked (mid-phase) whether 65
calls were needed: for diagnosis no — hence `--recheck` and the targeted run 5; for the
exit numbers the full set is kept, so the final figure combines run 4's 65 answers
(re-checked) with run 5's 19.

| Final (65 answerable, 11 refused before any call) | value |
|---|---|
| answered (generated and passing every check) | **0.984** |
| completeness — kinds the case must distinguish cited · parts answered | 0.913 · 0.986 |
| relevance — cites a gold source | 0.823 |
| citation precision (cited excerpts that are gold) | 0.502 |
| shown: unsupported sentences · reader figure as policy · verdicts · contradictions | **0 · 0 · 0 · 0** |
| refusals correct (must-refuse cases never generated) | 1.0 |
| latency p50 · p95 | 3.1 s · 4.1 s |
| tokens per call | ~2,000 prompt · ~320 output |
| all PHASE 10 Gemini use | 279 calls · 545,348 prompt · 83,446 output tokens |

Cost in USD is not stated: no price is recorded in the repository, and none is guessed
(`LEGALMIND_GEMINI_USD_PER_M_IN/_OUT` compute it when set). GT-00's answer: the §14
position; the company's reading of ss. 73–74 as a separate layer; the 6/12-month terms
of past contracts as negotiated exceptions, not current policy; "the company position
does not state 6 months [A]"; the missing signed MSA [M]; locate and verify it next.
The one contradiction the scorer first flagged (GT-03, "whether this equals 12 months
depends on the specific contract") was a conditional, not a policy statement — the
scorer now recognises the same absence forms as the check.

**Tested** — `tests/test_bundle_answer.py` (15: no call for an unanswerable bundle; the
payload labels kinds and keeps [A] apart with no internal id; a reader's figure as
policy / a bare fact on [A] / laundered by [A] never shown; unevidenced figures,
uncited sentences and dangling markers fail; section references are not figures; a
question figure may be named absent but never as a bound; "Pvt. Ltd." is not a break;
the position's own "unacceptable" is not a verdict but a claim judged against it is;
history never called policy; [M] present for an unanswered part; a dirty span refuses
egress before any call). Full suite **2605 passed, 112 skipped (unchanged), 0 failed**;
ruff + mypy clean.

**Exit (roadmap §10, §16)** — answers the question from the bundle only ✔ · combines
evidence and keeps the kinds apart (completeness 0.913) ✔ · user facts as context, never
evidence (0 shown) ✔ · missing information stated, never filled (0 unsupported figures
shown) ✔ · direct answer → distinction → known → missing → next step for complex
questions ✔ · no retrieval mechanics exposed ✔ · measured relevance, completeness,
faithfulness, unsupported claims, contradictions, citations, latency and tokens ✔.
**Named limitations:** the checks are mechanical (markers, figures, attribution,
negation, history wording, verdict) — a non-numeric unsupported paraphrase is caught only
by PHASE 11's semantic verification; citation precision 0.50 (answers cite neighbouring
sources the gold does not name); the final prompt was measured on 19 targeted cases, not
re-run on all 65; `CONFLICTING` still has no detector (PHASE 12).

Commit: `a10c7dc`.

## 2026-09-25 — Entry 14: PHASE 11 — semantic claim verification + citation verification

**Lock recorded — `AM-90` (AB-40)** — amends `AM-89` r3/r4 narrowly. all_lock.md
20604 → 20700 (counted from the file), additions only; registry; CLAUDE.md; CHANGELOG.

**Built**
* `legalmind/assist/verify.py` — `judge` per claim, `check_answer` per answer (stage 1
  batched for every claim in one model call; results memoised within the answer).
  Local NLI cross-encoder `cross-encoder/nli-deberta-v3-small@fa28048…` provisioned by
  `tools/provision_model` (checksums in its manifest); `config.nli_model_repo/revision`.
  Premises: the claim's best-overlapping sentences joined in document order, each framed
  with what its source is (company position / the company's reading of the law /
  historically, not current policy / the law / the contract); hard-wrapped statute lines
  rejoined; leading discourse words stripped. Stages: whole claim → single sentences,
  clauses and the cited sources together → other shown sources (re-citation). Checks on
  a kept claim: clause contradiction (≥ 0.9), verb-scoped negation and obligation shift
  (suffix-stemmed, aligned on the words after the verb), `guardrails`' existing
  polarity/modality (quantities off — `answer.check` owns figures), kind errors (law as
  the SUBJECT of a legal verb without an Act/law source; history as current policy;
  company position as the contract). Precision mode: an unsure entailment on a claim
  grounded ≥ 0.34 in its evidence is not an error.
* `answer.verify_answer` (mechanical, then semantic) and `answer.respond` with ONE
  corrective generation (`generation.generate_bundle_repair`, `bundle-repair-1`), then
  the fixed grounded answer. `answer.is_context`: signposts, [A]/[M]-only sentences,
  stated gaps, statements about the evidence set, a reader's figure named as absent.
  `Payload.authorities`; `Answer.calls/verify_ms/first_draft`.
* Prompt `bundle-answer-6` (a PHASE 10 behaviour corrected on the evidence): one fact per
  sentence, the excerpt's own words for obligations, conditions and exceptions.
* `onnx_backend.pair_logits` (raw per-label rows; `score` now uses it — one path).
* `tools/eval_verification.py` (claim-level: accuracy, false accept/reject, perturbation
  types, citation precision/recall, answer-level, production-shaped latency);
  `tools/eval_generation.py` records calls/repairs/verify time and stubs BOTH calls
  offline (a real-seam repair in "offline" mode was caught before any egress — no key in
  that environment — and fixed).

**Evaluation data (zero Gemini):** 2,220 claims in four sets, each labelled by separate
annotator subagents (not the verifier, not Gemini; development labels, not
owner-reviewed): dev 549 (PHASE 10 final answers — all tuning here), held-out 476
(PHASE 10 run 3), final 571 and final2 624 (PHASE 11 live runs 1 and 2). Deterministic
perturbations of supported claims give known-bad cases.

**Measured by iteration (dev → fix → dev; held-out for the report):**

| step | FR supported | corruptions accepted | note |
|---|---|---|---|
| 1-sentence windows, small NLI | 0.48 | 0.18 | attribution frames read as neutral |
| joined premises | 0.38 | 0.15 | |
| base NLI | 0.35 | 0.14 | 2× latency — rejected |
| kind-framed premises, discourse stripped | 0.27 | 0.11 | |
| label-scoped kinds, deontic check | 0.22 | 0.10 | |
| staged + clauses | 0.23 | 0.07 | |
| + lexical second route 0.6 | 0.11 | 0.08 | |
| + verb-scoped negation/obligation, suffix stem, fixes to 4 false-reject causes | 0.07 | 0.06 | |
| held-out, strict | 0.10 | 0.08 | answers passing 0.39 |
| **held-out, precision (shipped)** | **0.063** | **0.093** | answers passing 0.57 |
| large NLI (int8) | 0.036 | 0.195 | 10× latency — rejected |
| regex condition preservation | 0.21 | — | caught no more real errors — removed |
| reading-attribution rule | +0.03 | — | 3 claims caught — reverted |

Held-out (shipped): corruptions accepted — figure 0, law/position swap 0.024, negation
0.162 (about half the negation perturbations are garbled double negatives), overstatement
0.273, wrong citation 0.103; citation precision/recall 0.951/0.946.

**Live, full benchmark, labelled end to end:**

| | PHASE 10 | run 1 (strict) | run 2 (precision, shipped) |
|---|---|---|---|
| answers shown | 65 | 57 | 56 (15 after a repair) |
| bad claims shown | 23/549 (4.2%) | 20/482 (4.1%) | **16/519 (3.1%)** |
| shown answers with a bad claim | 17 | 15 | **12** |
| claim citations correct | 0.966 | 1.000 | **1.000** |
| clean answers that fell back | — | 7 | 5 |
| Gemini calls · prompt · output tokens | — | 93 · 208,017 · 29,285 | 89 · 196,212 · 30,181 |
| answer latency p50 · p95 (incl. repair) | — | 3.5 · 7.9 s | 3.8 · 8.7 s |
| verification p50 · p95 | — | 1.1 · 4.4 s | 1.1 · 4.5 s |

Run 1 showed the strict verifier did not reduce real bad claims (4.2% → 4.1%) and blocked
7 clean answers — the evidence that moved the design to precision mode.

**Does any Phase 10 behaviour need correction?** Yes, two, both done here: (1) the
reported "citation precision 0.50" was a metric artifact — it measured citations against
the benchmark's retrieval gold; claim by claim the model's citations were 0.966 correct,
and code now assigns them (1.000 shown); (2) the prompt now asks for one fact per
sentence in the excerpt's own terms (compound sentences and dropped conditions were the
verifier's main failure).

**Tested** — `tests/test_claim_verification.py` (13, entailment stubbed so decisions are
pinned independently of weights; CI has no model): supported paraphrase kept, re-citation,
unsupported, negation and obligation shifts, the three kind errors, no model fails
closed, code-assigned citation in the shown text, one retry then verified answer, second
failure → fixed answer, precision mode. `test_bundle_answer.py` isolates the mechanical
layer. Full suite **2618 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Exit (roadmap §11–§12)** — claims inspected, not words ✔ · paraphrase passes (held-out
FR 0.063) ✔ · invented figures, law/position swaps and wrong citations rejected or
corrected ✔ · citation assigned to the actual supporting source (1.000) ✔ · user
context vs evidence vs model claim kept apart ✔ · fail closed, never partial ✔ · full
benchmark re-tested live ✔ · bad claims shown reduced 4.2% → 3.1% ✔ (partly).
**Named limitations:** 16 bad claims still reached readers in 519 — 8 dropped
conditions, 7 kind errors (5 the company's reading of the law stated as bare fact), 1
unsupported; negation (0.16) and overstatement (0.27) corruptions still pass sometimes; 5
clean answers fell back; 9 of 65 answers are the fixed grounded answer; labels are
assistant-annotated. These are PHASE 12's multi-source-reasoning inputs.

Commit: `a5fe6c9`.

## 2026-09-26 — Entry 15: PHASE 12 — multi-source reasoning: claim contracts + evidence/conflict map (PARTIALLY MET)

**Lock recorded — `AM-91` (AB-41)** — amends `AM-89` r1–r3 and `AM-90` r4 narrowly.
all_lock.md 20700 → 20789 (counted from the file), additions only; registry; CLAUDE.md;
CHANGELOG. **Not declared complete** (owner instruction: only if the specific failure
modes materially improve — condition drops did not).

**Built**
* `legalmind/assist/contracts.py` — `statements` / `build` / `relations` / `render` /
  `check`: per-statement contracts (subject·action·object, modality, negation,
  conditions, exceptions, document-type scope, section scope, governing frame,
  CURRENT/HISTORICAL, kind from the statement's own label or heading), selected by the
  local reranker (best of the question and its parts, position headings boosted); the
  conflict map; the deterministic sentence checks.
* `generation.generate_contract_answer` (`contract-answer-1`); the repair accepts the
  template it repairs.
* `answer.contract_payload` / `contract_fallback` / `verbalise` / `repair_sentences`;
  `Payload.framed`; `Answer.prepare_ms`; near-verbatim restatements decided by the
  contract checks, not NLI; a restated frame is not a verdict.
* `guardrails`: a decimal with its unit ("99.9%") is a figure.
* `tools/eval_generation.py`: contract-aware stub, `--no-repair`, preparation latency.

**Measured by iteration** (every shown sentence labelled independently with ONE
error-type schema, applied identically to the PHASE 11 baseline answers — 624 + 635 +
651 + 640 + 667 sentences; per 1,000 shown sentences):

| | P11 | run 2 | run 3 | run 5 (final) |
|---|---|---|---|---|
| condition dropped | 38.5 | 103.4 | 73.4 | **36.6** |
| modality changed | 3.9 | 8.0 | 5.4 | **0** |
| reading stated as law | 9.6 | 0 | 0 | **0** |
| other kind | 23.1 | 15.9 | 16.3 | **14.6** |
| unsupported content | 3.9 | 5.3 | 8.2 | **11.0** |
| bad sentences | 7.3% | 13.0% | 9.5% | **5.7%** |
| answers shown | 56 | 40 | 39 | **54** |

What each iteration found (diagnosed on saved drafts with zero Gemini calls):
run 1 — the conflict map invented conflicts from shared words; purpose/entity/counsel
lines became claims; a section scope was demanded of every sentence; negation checked on
60-word notes; condition spans swallowed the main clause. Run 2 — sentence contracts lost
their governing heading ("Acceptable Position"), document-type and section scope, and
fragments lost their referent; "the company" counted as position attribution. Run 3 —
the header line was glued to the heading after it and discarded with it; standard titles
(the scope) were stripped; scope-list bullets and statute provisos split from their rule;
"This section governs …" merged into a claim hid the scope. Run 4 — 53% answered: strict
checks failed whole answers and Gemini repairs rescued 9/39 → deterministic sentence
repair (re-checked on run-4 drafts: 53% → 85.5% answered, zero calls), then modality
(plain restatement of shall/may) and grounding (≥ 0.65) checks. Run 5 — statute
sub-sections kept whole, Schedule model forms framed.

**Final (run 5):** answered 54/65; bad sentences 31/547 (5.7%) vs 38/519 (7.3%); answers
with a bad sentence 17/54 vs 26/56; citations correct 0.995; 11 fixed answers (7 clean);
latency p50 3.6 s / p95 7.6 s end to end, contracts built p50 0.15 s / p95 0.54 s,
verification p50 0.9 s; 77 Gemini calls. PHASE 12 total: 497 calls, 769,046 prompt +
198,155 output tokens over five full runs.

**Golden regression (mandatory):** 12 of 14 golden questions shown with zero bad
sentences (GT-09, GT-10 fall back to the fixed answer). GT-00: the current Constitution
position (§14 / EARLY-TERM-RESTRICTION-MSA-001), the company's reading of the law
(ss. 73–74, §28.4.1), the historical 6/12-month renewal terms, the client's assertion
[A] and the missing signed MSA [M] — separate, each named.

**Remaining failures, exactly:** 20 condition drops and 6 unsupported sentences in
shown answers — DPDP penalty entries without their "NOT YET IN FORCE (13 May 2027)"
status (4); §31.14 C's exceptions list and governing sub-headings (Change of
Ownership/Control; Partner & Distribution policy changes) lost (≈8); statute proviso
ranges (s.179 "clauses (d) to (f)"; s.1(4) spliced onto s.1(3)); "this position"
referents; a Purpose line read as a position; 8 other-kind misattributions. About half
are now in the VERBATIM replacement sentences — the contract text itself lacks context
that lives elsewhere in the source's structure.

**Tested** — `tests/test_claim_contracts.py` (12): per-statement kinds, drafting never a
claim, abbreviation and fragment handling, modality/negation/conditions/section scope
recorded, dropped condition, strengthened/weakened modality, lost negation, reading never
the law and always named, history never current and never blended, conflict map layers
vs conflicts (and scope), governing frame required, document-type scope required,
position never called the reading. Older layers pinned to their own paths. Full suite
**2630 passed, 112 skipped (unchanged), 0 failed**; ruff + mypy clean.

**Next:** build contracts from the structured Constitution records (`AM-79`/`AM-82`
knowledge_items: section path, heading, status, parent) rather than re-parsing flattened
context text — the remaining errors are all structure the records already hold.

Commit: `4efbe46`.

## 2026-09-26 — Entry 16: PHASE 12 — claim contracts from the structured source records (COMPLETE, `AM-92`)

**What changed.** Contracts for the Legal Constitution and statutes are now read from the
structured records rather than re-parsed context text (`assist/claim_records.py`). Each
claim carries, in the records' own words: its heading; its scope (the section's
"governs …" clause and the group's document types, narrowed by a lettered sub-part such
as "A. MSA / Customer", none on a historical deal); its in-force status ("NOT YET IN
FORCE — 13 May 2027", REPEALED); its group's exceptions list; what "this position", "the
Scope of Application above" and "the confirmed position" refer to; its local antecedents
("that sum" → "a sum payable on breach", "the contractual amount stated above" → "the
full committed-term value"); and its kind from the record's authority. A statute claim is
a whole sub-section with its provisos and items, footnotes removed, the Act named. Three
further contract checks hold a sentence to these; the repair appends only the records'
qualifiers. Gemini still only verbalises the contract. Production path unchanged.

**Measured.** Final full live run (run 9, 81 Gemini calls), every shown sentence labelled
independently with one schema, per 1,000 shown sentences, against run 7 (the records run
before the final fix) and `AM-91`'s run 5:

| | run 5 | run 7 | **run 9** |
|---|---|---|---|
| cross-reference / scope lost | 20.1 | 31.4 | **17.6** |
| source-kind misattribution | 14.6 | 3.9 | **6.6** |
| temporal / status lost | 7.3 | 2.0 | **2.2** |
| conditions dropped | 3.7 | 9.8 | **0** |
| exceptions / ranges lost | 9.1 | 2.0 | **2.2** |
| modality · negation | 0 · 0 | 2.0 · 2.0 | **0 · 0** |
| unsupported · contradicted | 11.0 · 0 | 9.8 · 2.0 | **6.6 · 2.2** |
| reader's assertion as fact | 0 | 2.0 | **0** |
| bad sentences · answers with one | 5.7% · 17 | 6.3% · 22 | **3.5% · 13** |
| citations correct | 0.995 | 0.989 | **0.997** |
| Gemini answers shown | 54/65 | 52/65 | **49/65** |
| fallbacks · false rejects | 11 · 7 | 13 · 5 | **16 · 6** |
| latency p50 / p95 | 3.6 / 7.6 s | 4.4 / 10.4 s | **4.0 / 10.8 s** |

Of the 16 fallbacks, 10 caught a real error; the 6 clean ones: GT-00 (output cap), A-03
(new record checks), L-02 (contract checks), H-03 (verdict screen), L-04 and N-02
(verifier). Golden: 11 of 14 shown, 8 with zero bad sentences; GT-00, GT-09, GT-11 fell
back to the fixed grounded answer.

**Final fix, proven before spend.** Run 7's saved answers re-checked offline (zero
Gemini): cross-reference shown 16 → 9, all other error types unchanged, false rejects
5 → 3. The 11 affected questions live (16 calls): 0 bad sentences shown (run 7: 11), 0
cross-reference/scope (run 7: 8), 0 unsupported, 0 false rejects, 6 of 11 shown (run 7:
8), every fallback a correct catch.

**Tested** — `tests/test_claim_records.py` (14) pins every case the owner named plus the
final fix. Full suite **2644 passed, 0 failed, 112 skipped**; ruff + mypy clean. Eval:
`backend/tests/assist_eval/contract_records_eval_2026-09-26.json`.

**Gemini.** Records continuation 254 calls (492,108 prompt + 142,701 output tokens);
PHASE 12 total 751 calls (1,261,154 + 340,856).

**Known limitations — recorded for PHASE 13, none attempted:** (1) output-cap truncation:
richer contracts lengthen answers, 4 of 65 hit the 900-token cap (0 in run 5); (2)
`[Illustrative clause:]` text in company-standard files (`POS:LIABILITY-MSA-001`)
presented as the position — all 3 source-kind errors shown; (3) A-03, one false reject
from the new record checks; (4) statute cross-reference reconstruction ("the period in
sub-section (1)", state amendments, Schedule items); (5) the PHASE 11 verifier's false
rejects.

Commit: `88c598f`.

## 2026-09-26 — Entry 17: Roadmap §13 — multi-source legal reasoning (`AM-93`)

**Requirement (roadmap §13, v1.0).** One answer may need the Constitution, the executed
MSA's availability, historical exception evidence, the law and the conversation — never
blended, each said as itself: the Constitution position, what the customer is claiming,
that the signed MSA is not available, that historical agreements are exceptions and not
current policy, that the amount cannot be confirmed until the executed MSA is verified.

**Already met (PHASE 9–12, reused):** kinds labelled apart, the reader's claim on [A],
the missing document on [M], the conflict map, contract checks against blending. Where
Gemini's answer was shown, the §13 labels were present every time.

**What was wrong, measured on the saved runs:** (1) the longest multi-source answers hit
the 900-token cap; the unfinished last sentence failed as "no citation" and the golden
answer fell back to a source dump (GT-00, GT-09, GT-11); (2) §31.15 holds a position
(30 days' notice) and historical deals, and read by the source's label the reader's
"30 day" was "stated by no company position" — told to Gemini, and H-03 rejected in all
three runs; (3) the history attribution counted against a verbatim restatement; (4)
nothing guaranteed [A]/[M]; (5) two antecedent gaps (§31.14 exceptions; a lead-in).

**Implemented:** finishReason recorded; a cut answer keeps its finished sentences; fixed
[A]/[M] sentences when needed; reader figures compared per claim kind; no sentence
speaking for a source it does not cite, source-kind checks on every sentence; two
record rules.

**Measured.** Zero-Gemini replay of run 9's saved answers: shown 49 → 53/65, bad sentences
16 → 16 (identical types), false rejects 6 → 3, §13 layered cases 8 → 10/11 (all 11 carry
the [A]/[M] they need), golden 11 → 13/14, none newly falling back. Live, 5 Gemini calls
(12,637 + 3,913 tokens): three real MAX_TOKENS cuts shown with the tail removed, [A]/[M]
3/3, H-03's 30 days stated as the company position, 50/56 sentences supported and none
unsupported or contradicted — and ONE blended GT-00 sentence, closed by the new check and
proven on that live text with zero calls.

**Tested** — `tests/test_multi_source_reasoning.py` (8) + 2 record tests. Full suite
**2654 passed, 0 failed, 112 skipped**; ruff + mypy clean. Eval:
`backend/tests/assist_eval/multi_source_eval_2026-09-26.json`.

**Remaining:** GT-09's Negotiable range and GT-11's s.143A scope (`AM-92`'s cross-reference
limitation) and the other `AM-92` limitations. The production Ask path still runs the
older generation — wiring this pipeline in is roadmap PHASE 13.

Commit: `dbb7e38`.

## 2026-09-27 — Entry 18: Roadmap PHASE 13A — the multi-source Ask path in production, canary-ready (`AM-94`)

**Wiring.** `LEGALMIND_ASK_MULTI_SOURCE` (off by default; `no_document` is the approved
scope; `on` is not) and `LEGALMIND_ASK_MULTI_SOURCE_PERCENT` (a per-conversation SHA-256
canary share, unreadable → 0). One branch point in `service._ask` after every existing
screen; `_ask_multi_source` runs the validated PHASE 9–12 path with the caller's live
permissions and answers only with a verified generated answer — otherwise legacy answers
exactly as today. Response contract unchanged; Constitution refs in
`retrieval_runs.results`; every egress audited. One `assist.ask.trace` per request
(ids, route, flag, share, selected vs answering path, fallback kind, counts, tokens,
finishes, versions, per-stage latency; no text). Rollback = flag off + API restart.

**Rehearsed, never applied to production:** migrations `e9f2b6c4a173 → f4c1e8a2b7d9 →
a7d3e9b1c5f2 → b8e2f6a4d1c3` up/down/up clean (the downgrade of `a7d3e9b1c5f2` named its
check constraint wrongly — fixed); Constitution ingest 701 items / 404 embeddings;
AM-80 statute re-ingest 17 Acts / 5036 chunks; evidence selection on the copy identical
(61/76) or a strict superset (15/76) of the validated corpus. Runbook:
`docs/09-implementation/MULTI_SOURCE_ROLLOUT_RUNBOOK.md`.

**Privacy.** A §31.2 emphasis line still carried a counterparty name the `AM-59`
redaction missed; replaced by the "[Customer A]" placeholder its own paragraph uses,
re-ingested, pinned by `tests/test_constitution_redaction.py` (SHA-256 of the name against
every word of the file and of every record). Legacy never showed Constitution text; the
new path does.

**Latency (zero Gemini, 75 questions, p50/p95 ms):** rerank 1095/3069 → 801/1071, bundle
381/1218 → 381/449, contracts 122/1077 → 98/599, verify 459/3329 → 432/2875 — length-
sorted cross-encoder/NLI batching, scores byte-identical. Live Gemini p50 2.7 s on the
`contract-answer-2` prompt (was 4.0–4.4 s).

**Evidence.** §31.2 holds a company position AND three historical exceptions; labelled
by its best-matching child it could never serve the history lane, so §31.15's renewal
deals were shown as the early-exit history. The Constitution search now reports every
authority a section's children hold and selection lets a section serve every lane it
holds (its label unchanged): GT-00 shows §31.2, gold coverage 53 → 54 / 73, every other
case byte-identical.

**Answer shape.** `contract-answer-2` shapes the answer to the question; a repair is the
smallest run of the record's own sentences that passes every check, one per contract,
joined without splitting "Cl. 5.1". Live, six questions (6 calls): 428 → 325, 405 → 291,
214 → 81, 2366 → 580 words. Independent judgement: the new answer better on 5 of 6
(direct answer first, layers labelled, the reader's figure never the policy, 40–85%
shorter, no irrelevant sections); O-03 worse — its gold sources are never retrieved
(`AM-92` statute residual) and the fixed answer now leads with a Schedule.

**False rejects.** "IN FORCE since …" no longer a qualifier; "subject to Cl. 5.1" no
longer truncated; an Act named once need not be renamed every sentence; a verbatim
excerpt carries its own modality; an inline "[Illustrative clause:]" is never a
position; a gap sentence may not call unconfirmed what a shown claim states. Zero-Gemini
replay of run 9 vs the `AM-93` baseline replay, after every fix: shown 53 → 53, bad
sentences 16 → 12 (three `[Illustrative clause:]` source-kind errors and one cross-
reference gone), answers with one 13 → 9, false rejects 3 → 3 (A-03's corrective-retry
draft fails the checks, as fail-closed intends). Contract building scores every (query,
sentence) pair in one batched call — GT-00: 50 calls → 1, contracts byte-identical.

**Tests.** Full suite **2694 passed, 0 failed, 112 skipped**; ruff + mypy clean. New:
`test_ask_multi_source_rollout.py` (32), `test_constitution_redaction.py` (3), and
section-kinds, minimal-repair, gap-guard, inline-drafting and Act-naming tests.

**Residuals, recorded:** `AM-92`'s statute cross-reference class (GT-09, GT-11, E-04's
paraphrased gap, O-03's Schedule-over-section retrieval); end-to-end latency of the new
path remains several times legacy's because Gemini writes a longer verified answer; the
document lane stays on legacy until it has its own benchmark.

Commit: `608cbb6`.

## 2026-09-27 — Entry 19: roadmap §7/§14/§15/§17 verified as behaviour (`AM-95`)

A live requirement matrix now tracks every roadmap section from requirement to
evidence (`docs/00-project/ROADMAP_REQUIREMENT_MATRIX.md`). Working it found five
defects, each traced to the phase that caused it:

* **§7/§8** — "section 74 of the Indian Contract Act" missed s. 74 even asked alone:
  search ranked it first, the cross-encoder (reading "section 74" in the question, not
  in the section) demoted it to tenth, and the judge's floor then rejected it. A named
  section of a named Act now survives both.
* **§14** — "section 194J of the Income-tax Act, 1961" (a section the supplied text
  predates) was answered from the CGST Act. A named Act now answers alone; H-02 refuses.
* **§15** — the roadmap's own follow-up example fell back to legacy: not anaphoric, so
  production never gave the planner the earlier question (the benchmark always did);
  and a three-turn chain lost its topic. The planner now sees every bounded earlier
  question; only the topic carries.
* **§15** — a changed topic ("section 74 …" after an early-exit question) inherited
  "early exit". A turn that names its own source never inherits.
* **§17 K** — Roman-Hindi questions retrieved the right sources and the English
  cross-encoder rejected them. The planner's English topic is also scored, for kinds the
  plan asked for only (an unscoped first version admitted the Copyright Act's
  licence-termination section to a data-retention question).

Zero-Gemini golden benchmark (79 cases, three new follow-up shapes): recall@3 0.728 →
0.778; A 0.83 → 1.0, J 0.86 → 1.0, K 0.2 → 0.6; wrong-source and false admission 0 both
sides; six cases changed, all up. Residuals recorded: F-03/F-04 planner vocabulary (the
fix would reopen AM-86 r3 for two cases and expose three must-refuse ones), K-03, K-05,
and a corpus with no second jurisdiction or not-yet-in-force statute to test beyond
record statuses.

Commit: `ed982ee`.

## 2026-09-27 — Entry 20: planner vocabulary and instrument recognition (`AM-96`)

Three golden misses had no planner topic: "KYC records" (no cue), "payment nahi kiya …
service band" (every question containing "service" was placed under SLA through the
canonical term "service level availability uptime"), and "reported to CERT-In?" (an
Act's short name before punctuation named no instrument). Each cue now points at the
topic its gold standard is configured with; "service" alone no longer counts; one shared
alias pattern tolerates punctuation. With retrieval now reaching the named Income-tax
Act, s. 199 answered "what did s. 194J say" — a section the text predates — so a named
section absent from the text is answered by no other section. Golden recall@3 0.778 →
0.815, F 0.5 → 0.83, K 0.6 → 0.8, wrong-source and false admission 0, H-02 refuses.
Suite 2708 passed.

## 2026-09-27 — Entry 21: evidence floor 8 and figures with their unit (`AM-97`)

A zero-Gemini sweep of the evidence floor showed 8 units reach recall@3 0.864 against
0.815 at 5, and 10 gains nothing more at a higher prompt size. Floor 8 alone let a
liability standard into two questions on other topics, so a standard whose configured
topic the question does not name is no longer evidence (`OFF_TOPIC`); wrong-source is
back to 0. The wider bundle then exposed a defect in the reader-figure check: it
compared the number alone, so any "6" in a shown section counted as the company stating
"6 months", and the answer stopped saying no position states it. Figures are now
compared with their unit. D-01, D-02, I-02 and K-05 close; false admission stays 0.

## 2026-09-27 — Entry 22: statutes ranked with their section title (`AM-98`)

The cross-encoder scored each statute on its best-matching chunk alone. For "what
compensation can we recover", s. 73 of the Contract Act matched on an illustration
about a ship's cargo and ranked below unrelated Acts. It now scores the chunk with the
section's own title, which ingestion already stores; the evidence is unchanged. The fix
first showed no gain because the candidate merge rebuilt each candidate and dropped the
title, and that merge now copies every field. Two reader phrasings of the liability cap
and a price rise now place their topics. Golden recall@3 0.864 → 0.901, the golden
questions reach 1.0, and wrong-source and false admission stay 0.

## 2026-09-27 — Entry 23: the more fully named Act ranks first (`AM-99`)

"What does the DPDP Act require of a data fiduciary?" names the DPDP Act, but it also
matches most of the DPDP Rules' title, so the statute search treated both as named and
let the Rules' sections take the slots on word count. DPDP s. 8 never reached the pool.
Among named instruments, the one the question names more fully now ranks first. The
Companies Act, 1956 question benefits the same way. Both the new and the legacy paths
improve, and wrong-source and false admission do not move. A second idea, ignoring an
Act's own title words inside it, helped s. 27 in the pool but changed no result, so it
was dropped.

## 2026-09-27 — Entry 24: the code's own restatement is always verifiable (`AM-100`)

Three live questions fell back to the legacy path. Regenerating them with every draft
captured showed a shared cause. When a draft sentence failed, the repair put the
approved claim's own words in its place, but for 20 of 553 claims that restatement
failed verification itself, so no repair could succeed. An exact restatement is now
trusted as source text, with every deterministic check still applied. A looser version
was tried first and rejected, because it let four known-bad draft sentences through.
Separately, an ellipsis in a ratified quote had cut "solicit" out of the non-solicitation
standard. Replaying 65 real answers: fallbacks 14 → 2, and every known-bad sentence is
judged exactly as before. All three live cases now answer on the new path.

## 2026-09-27 — Entry 25: "obligations" is not a "must" (`AM-101`)

The claim reader treated any word starting "obligat" as a binding modal, so "the vendor
should provide ... flow-down obligations" was recorded as mandatory, and a sentence
saying the position "requires" it passed. Only the verb forms bind now. With that false
reading gone, one more stored answer shows in full, and two of its DPDP s. 33 sentences
omit that the penalties commence only on 13 May 2027. The verifier cannot catch that,
because the corpus has no per-section commencement data. That needs the owner.

## 2026-09-27 — Entry 26: the Sources legend reads as a list (`AM-102`)

Checking the new answer as the interface shows it found two presentation faults. The
legend under an answer numbered claims, not sources, so one Constitution section could
appear three times. The legend was also one block starting with "Sources", which the
answer view renders as a single run-on paragraph. Each source now has one number, and
the legend is its own list, which the existing view already knows how to show. No
interface code changed. The status documents now record the whole roadmap effort.

## 2026-09-27 — Entry 27: tested in the real interface (`AM-103`)

The new Ask was run end to end on the branch: a scratch copy of the corpus, the branch
API and a production build of the interface, with a real browser. Asking about early
termination of a fixed-term deal worked, but it answered from §13 instead of §14,
because §14's best-matching paragraph was its legal note. A Constitution section on the
topic the question names may now answer for the company position. The same run showed
a restatement split inside a parenthesis. Records now split only between their own
sentences, never at an ellipsis or into an empty piece. Asked again, it answers from
§14 in one Gemini call and about 10 seconds.

## 2026-09-27 — Entry 28: the records brought up to date

A check of every record file found stale figures in three status documents. They said
fallbacks fell from 14 to 2 with 14 bad sentences, still listed K-05 as open, and quoted
category recall from before `AM-103`. They now carry the measured figures: fallbacks
14 → 1, 16 of 571 bad sentences with each judged exactly as before, and category recall
re-run at `AM-103`. They also stop calling the branch release-ready. A security review,
a fresh migration and rollback rehearsal, a trace check and CI are still owed. The
CLAUDE.md narrative now covers `AM-97` to `AM-103`, and HANDOFF.md points to the tracker.

## 2026-09-28 — Entry 29: the remaining misses fixed where they happen (`AM-104`)

Every remaining golden miss was traced stage by stage before anything was changed.

**Retrieval.** H-01 was a real defect: one Constitution section number could appear
several times in one search result, and each repeat added to its score, so four long
sections outranked §4.1. Each source now counts once per list. D-01 was searched under
the topic of the sentence before the question; a question part now keeps its own
topic. E-03: statute sections are now matched on their titles too, and inside an Act
the question names, that Act's own title words no longer decide the order (s. 27 moved
from 42nd to 4th). That briefly let the repealed 1956 Companies Act outrank the 2013
Act, so "current before repealed" now comes before the word count. O-04: "CERT-In" is
now spelled out as the name s. 70B uses, for search and for the reranker (32nd → 1st).
§70B was never missing from the supplied text; it is absent only from the live corpus,
which still runs the old parser.

**Statutes.** A section that says "penalty specified in the Schedule" now carries the
Schedule that names it back. The parser (`section-5`) drops the Bill's Statement of
Objects and Reasons, which eight Acts had stored as law. DPDP s. 33 and its Schedule
are shown as not yet in force until 13 May 2027, labelled as the date the Constitution
§28.2 states, not the Act's own commencement (`config/statutes/commencement.json`,
every quote checked against the Constitution file). Provisions the Constitution only
describes are not mapped to section numbers.

**Claims and verification.** 219 statute sections had lost their sub-section (1),
including s. 29A's twelve-month rule; 34 remain, all in-text references. The verifier
now catches a section number its claims do not name, a sentence that stops at "shall
not", and a status that was only the word "effective" in the statute. Checked on the
same claims: seven more bad sentences caught and no good one rejected. Three rendering
faults found in live answers are fixed ("G.S.R; 843(E)", "[2, A]", a footnote marker).

**Security review.** A Gemini call is now audited even when the new path fails
afterwards, and the trace carries a failure's kind, never quoted evidence.

**Measured.** Golden recall@3 0.926 → 0.951 (79 cases); 0.952 on the re-ingested corpus
with two new cases; wrong-source and false admission 0. Run-9 replay: bad sentences
shown 16 → 4 of 574. Live: 18 of 20 targeted questions answered in one call (27
evaluator calls, 71.3k prompt / 7.2k output tokens). Real browser through a
production-like proxy: upload, review, findings, Ask with follow-ups, history, phone
width, all clean. Migrations and ingestion rehearsed on a clone of the AM-94 copy.

**Not fixed, and why.** E-03 and the DPDP statute slot need the reranker to link a
non-solicit to restraint of trade and "maximum penalty" to the Schedule's amounts; a
wider evidence set fixes E-03 but adds 17% more evidence to every answer, so it was
not adopted. H-02's s. 194J is not in the accepted 1961 text. Four bad sentences are
generation faults no deterministic check can see.

## 2026-09-28 — Entry: the first CI run of the release PR (`AM-105`)

PR #121 ran CI for the first time and three jobs failed, none for a reason in the new
Ask. CI installed a new SQLAlchemy release, 2.1.1, because nothing pinned it, and its
typing broke 21 lines no one had touched; it is now pinned to the 2.0 line production
runs. Two conversation tests quietly relied on vector search, which CI does not have,
and a production model failure would have lost a follow-up's topic the same way. Now,
when no vectors are available, the topic phrase is also searched on its own. Doing
that always was tried and cost recall, so it runs only in the degraded mode. The
dashboard screenshot failed because the greeting says "Good morning" or "Good
afternoon" by time of day. Masking it failed, because the heading is as wide as its greeting, so that one screenshot now runs in a zone where it is afternoon. Retrieval with vectors is unchanged.

## 2026-09-28 — Entry: the new Ask engine is live as a canary

After the review and the three CI fixes, PR #121 was merged and deployed. A fresh
backup came first, checked both on the server and off it. The deploy moved the
database through three migrations. Then the Constitution was loaded, 701 records with
no redacted name among them, and the law library was rebuilt, 17 Acts with IT Act
s. 70B now present. On the live database, the search finds the right source exactly
as often as in testing. The new engine now answers 10% of conversations that have no
document attached. Three real questions all answered on it in one Gemini call each.
The DPDP penalties are correctly described as not yet in force. Switching it off is
one setting and a restart.

## 2026-09-28 — Entry: one Ask for every reader (`AM-106`)

The owner asked for the 10% canary to go: every authorised reader should get the new
Ask engine, with or without a document. The routing change itself is small. The flag now
defaults to on, the share and the conversation hash are gone, and "off" stays as the
emergency switch. The document lane had never been measured, so a benchmark was built on
the 44 approved document questions. At first the new engine showed the right clause for
only 18 of them. It planned document questions as company-policy questions, gave the
document one slot in eight, skipped the rescue check today's Ask runs on a weak search,
and let a web-trained relevance model veto clauses the document's own gate had accepted.
With each fixed at its stage it reaches 38, against 41 for today's path. It never admits
document text for a question the document does not answer. Document answers now carry
page and clause citations, which also come back when a conversation is reopened. Tested
through the real API and a real browser on a scratch copy; production is unchanged.

## 2026-09-28 — Entry: `AM-106` deployed

Owner "go". PR #123 merged through the ruleset (`c9a2876`, 15/15, 0 behind, 0 open threads). `LEGALMIND_ASK_MULTI_SOURCE=no_document` and `..._PERCENT=10` removed from `/root/.legalmind.env` (backup in `/root/.legalmind/preserved/`); `legalmind-deploy` shipped `c9a2876`, no migration. Checks: the API process carries no ASK flag, `config.ask_multi_source()` = `on`, `_ask_path` = `multi_source` with and without a document; `/health` 200, `/login` 200, no API errors in the journal. Two real questions through `service.ask` on the production DB, writes rolled back: no document → `multi_source`, ANSWERED, 1 Gemini call, 9.3 s; document → `multi_source`, ANSWERED, 1 Gemini call, 15.8 s, 4 clause citations. Rollback: add `LEGALMIND_ASK_MULTI_SOURCE=off`, restart `legalmind-api`.

## 2026-09-28 — Entry: the answer leads with the direct answer (`AM-107`)

The owner saw a production answer to "What does our Constitution say about early
termination? Please give the applicable company standard and cite the relevant
Constitution section." that had the right evidence but read as one long paragraph
mixing §31.2's fixed-term MSA rule, §13's non-fixed-term rules, a Distribution standard,
a historical Customer A note, the Contract Act reading and four sections.

**Root cause (production trace + zero-Gemini reproduction).** Retrieval and the evidence
bundle were right (§31.2 relevance 6.5, the top source) and verification passed. The
fault was claim selection (`contracts.build`): every shown source got up to three
claims, in source order, to a 12-claim cap, with no direct answer — Companies Act s. 466
(relevance -1.6) got as many as §31.2. And a claim from a structured record was the
record's whole paragraph, so a concise, correct sentence "dropped a condition" of a
different rule in it and was replaced by the paragraph — the verbatim blocks the reader
saw. 398 of 675 claims (59%) over 72 golden cases came from sources no gold slot names.

**Fix (`AM-107`).** One anchor per asked kind leads (evidence order unless another is
1.5 better; a named section leads; the statute leads the law lane); another document
family's rule never gives a claim (the Constitution's own §31.4 split); other sources
give one related claim, off-topic standards and unasked kinds only when close; each
claim carries a layer (primary / related / history / law) and an optional flag; a record
is claimed sentence by sentence; illustrations, provenance, pointers and notes to the
tool never pad; a failing optional sentence is dropped rather than pasted; the shown
answer is grouped direct answer → Also relevant → Historical context → Legal background
→ Sources under fixed server labels, rendered as headings. Prompt `contract-answer-4`.

**Measured.** Claims (72 cases, zero Gemini): primary from gold 44 → 52, gold slots
claimed 77 → 79/84, off-gold 398 → 168, claims per answer 9.4 → 5.2, must-not 0.
Retrieval unchanged (bundle recall@3 0.952, wrong-source 0, false admission 0).
Document lane: the right clause as the answer's first claim 8 → 22 of 44, among its claims 26 → 27, not-found questions claiming document text 0 → 0 (zero Gemini, rescue off, same bundle). Six owner scenarios through `service.ask` on production data,
writes rolled back: all verified on the new path in one Gemini call; the observed
question is two sentences on §31.2 + one related line + the past deals under their own
heading. 9 API scenarios on a scratch copy: all on the new path, document answers cite
page/clause. Real browser: the layers render as headings. Tests: `tests/test_answer_focus.py`
(14, all failing on main), frontend `ask-workspace.test.tsx`; full backend suite 2762 passed, 0 failed; CI shape (no embedding model) 198 assist tests passed.

## 2026-09-28/29 — Entry: the instruction shapes the answer (`AM-108`)

Owner brief (night): make Ask a production AI document assistant — document + instruction,
follow-ups, requested format and length — with the chat reading as a conversation, and
own the loop to deployment. Zero-Gemini probe on the scratch copy found the gaps: every
whole-document instruction refused (no topic → gate shut), "without comparing" went to the
evaluator, no format was read, the prompt forbade lists. Built `assist/presentation.py`
(task/form/count/short/simple/no-comparison/topic), the negated-comparison rule, document
tasks planned on the document, the outline for whole-document tasks, one claim per section,
prompt `contract-answer-5`, code-enforced form (bullet count, short retry, table rows
verified/repaired/dropped), layout for bullets and tables; frontend: no headline copy,
speaker hierarchy, collapsed passages, tables, and the chat grid held at viewport height
(pre-existing: `flex: 1` let an 8-turn chat grow the page to 3000px). One Gemini matrix
through the real API (9 cases) plus two browser flows at 1440/390 — all recorded with
screenshots in `docs/ASK_PRODUCT_COMPLETION_PLAN.md`. Regressions caught and fixed on the
way: the follow-up inherited the anchor's table instruction; "explain the liability clause"
hit the general-knowledge screen; the anchor "key risks" re-triggered the comparison; the
Gemini seam stub in `tools/eval_generation` needed the new kwarg. Benchmarks unchanged — retrieval bundle recall@3 0.952, hit@1 0.903, wrong-source 0, false admission 0; claims primary-from-gold 52/72, gold slots claimed 79/84, off-gold claims 168, 5.2 per answer; document lane (this run had the rescue judge live, so it is the AM-106 rescue-on figure) gold clause shown 38/44, as the first claim 29/44, not-found questions admitting document text 0/10.

## 2026-09-29 — Entry: Ask as a conversation (`AM-109`)

The owner handed over the whole Ask page. Two reported problems ("hi" gets a refusal, the
reader and the answer look alike) turned out to be symptoms of wider ones, found by
reading the code end to end and by using the page in a real browser on a scratch copy.

**Conversation.** Ask had no idea of small talk. "hi" was searched and refused, and a
mid-chat "thanks" was read as a follow-up and re-answered the last legal question.
Greetings, thanks, goodbyes and acknowledgements now get a fixed reply with no search and
no model call; "who are you" gets the capability list; a greeting in front of a real
question is dropped. A poem or weather request gets one clear sentence saying what Ask
is for; before, it inherited a topic from earlier turns and was answered from the
Constitution. Refusals now read "I couldn't find an answer in …, so I won't guess."

**Answers.** "and for NDAs?" after a liability question was answered with the NDA
survival period, because "NDA" was read as a topic; a document type is now a scope. Every
sentence repeated "The company position (Liability — …), for MSA agreements, states:";
the source is now named once per paragraph. A related Constitution section that said the
same thing as the standard is no longer repeated. A document liability answer pasted in
force majeure, compliance and indemnity; it now keeps to the asked clause, and a clause
is read with its heading, so "force majeure" finds clause 16.1.

**Page.** The reader's question sat on the page's own background colour; it is now a
blue bubble at full size. "Try again" did nothing; it now resends. An answer could land in
another chat after switching; it no longer can. The first answer re-fetched its own chat,
focus was lost after every send, answers were never announced to a screen reader, and a
chat opened with "hi" was titled "hi". All fixed, with a 150-second timeout added.

**Measured.** Retrieval unchanged (recall@3 0.953, no wrong source, no false admission);
document questions slightly better (right clause first 22 → 23 of 44); claim selection
unchanged except the new J-08 case. Backend 2843 and frontend 538 tests pass, plus 57
browser specs. About ten Gemini calls in all. Record:
`docs/00-project/ASK_SURFACE_REVIEW_2026-09-29.md`.


## 2026-09-29 — Entry: Ask second pass (`AM-109` addendum)

The owner asked for the rest of the review list to be finished: the document-side dock,
long conversations, accessibility, mobile, research, security, instructions, latency and
a final pass as a first-time user.

**Found and fixed.** The dock's "Try again" and timeout were missing; added, with focus
returning to its input. A 24-turn chat reloaded fast and kept its context, but the page
itself grew 5,000 px tall because hidden citation labels escaped the scroll area; the
scroll now stays inside the conversation. The only unlabelled tab stop was the hidden
file input. A first turn like "what about it?" with nothing before it was searched; it is
now asked what it means. The final pass asked the DPDP Act about breach notification and
got three definitions ("notification", "she") as the answer: a Definitions section now
leads only a question about meaning. The same answer repeated "(… NOT YET IN FORCE …)"
after every sentence and ended with a model sentence restating the question; both gone.
A company-standard answer whose explanation did not verify said "quoted below" with the
quotes folded shut; they now open. A background security review of every Ask change found
no P0/P1; its P2 (retry after a failed first question with a file) is fixed.

**Measured.** Answer focus unchanged (53 primary gold, 80/85 slots, 167 off-gold, 0
must-not). Latency over 20 live answers: p50 9.5 s, p95 33 s, generation 78% of it.
Backend 2858 passed / 112 skipped / 0 failed (one pre-existing test stub fixed for the heading lookup); frontend 542 passed; 61 browser specs. About 12 Gemini calls in this pass.
Record: `docs/00-project/ASK_SURFACE_REVIEW_2026-09-29.md` § Second pass.


## 2026-09-29 — Entry: `AM-109` DEPLOYED

PR #127 (`77db52a`, `90fbf84`, `2d8bfb5`) merged as `7f0f96c` and deployed with `sudo
legalmind-deploy`; no migration, no flag, no config change. CI 15/15 after adopting CI's
two Ask visual baselines (inspected expected vs actual: only the intended refusal wording,
question bubble, scope line and no-document opener changed). Production check, read-only:
API, frontend and worker active; API health 200; `/dashboard/ask` 200; no API errors after
the restart; the deployed code recognises "hi"/"thanks" and a no-subject first turn.


## 2026-10-06 — Entry: the Ask agent holds one real legal conversation (A-89…A-94)

Branch `feat/ask-conversation-colleague`, committed locally (owner: "commit all at once"),
not pushed, merged or deployed. The owner's 20-turn conversation was run through the live
agent with production flags (scratch DB) and every failure traced to its first concrete
blocker before anything changed; private record
`/root/.legalmind/diagnosis/conv-2026-10-06/FINDINGS.md`.

**Fixed in the owner's order:** (1) the statutes join `search_knowledge` through the shared
reranked candidate pool, admitted past the statute floor, and the first decision step
always searches (`toolConfig` `ANY`); (2) the case file — every earlier user message and
each reply's opening, within `AM-111` r1's budget; (3) P12 and a once-said caveat keep the
company standard apart from the customer's contract, and the five-step owed analysis runs
only when asked; (4) the verifier reads a table row as a unit and ranks premise rows by
rare words; (5) known · likely · unknown · review parts, plain words on request, no
repeats. Plus the owner's bold-key-phrase request (A-89).

**Measured.** Verifier held-out (zero Gemini): accuracy 0.885 → 0.889, false reject
0.096 → 0.091, corrupted accepted 0.097 → 0.092. Live conversation: turns citing an Act
0 → 10 of 19, "not entitled"/bare "Yes" 2 → 0, founding fact present at turn 20, p50 14.2 →
18.0 s, 2.8 → 3.3 calls a turn. Retrieval code of the shipped path unchanged (EVALS #59
stands). Gemini ≈ 200 calls today (diagnosis 106, fixes 97). Not fixed: the small NLI
model still reads "lawful, unless …" against "unlawful if …" as a contradiction; "one lakh"
and "one crore" are the same figure to the V2 check. Registered C-25.


## 2026-10-06 — Entry: independent and legal review; Constitution L1.11 (A-95…A-97, `AM-115`)

Same branch, owner instruction: review fixes 1–5 independently, resolve C-25 with a new
Constitution version, check regressions, review the result as a lawyer would, then commit,
push and open a PR (no merge, no deploy).

**Independent review (A-95).** A separate reviewer read `ca5315f` read-only and found nine
real defects — P12 never ran on cited claims; statute records lacked `AM-104`'s commencement
note; a figure equal to an Act's year passed V2; "explain simply" pushed content into unchecked
reasoning; unlabelled sentences fell under the wrong heading; P12/caveat ignored attached
material and non-English replies; "summarise" triggered the four parts; and smaller items.
All fixed, each with a test; plus lakh/crore amounts, open points in the case file, and
repeated boilerplate.

**Constitution L1.11 (A-96, `AM-115`, C-25).** §28.3 s. 70B(7) and s. 72A to the Act as
amended by the Jan Vishwas Act 2023 (w.e.f. 30 Nov 2023), a s. 43A note (DPDP s. 44(2)(a)
commencement not established — counsel), Appendix E. Golden retrieval benchmark on a scratch
copy before/after loading L1.11: identical, 0 of 82 cases changed.

**Lawyer-style review (A-97)** of the first full post-review run caught an in-force date
stated as the Act's, an indemnity-over-cap inference no source states, and the four parts on
every turn — fixed. Recorded validation (#65): Act cited 0 → 14 of 19 turns, standard-as-
contract statements 3 → 0, claims dropped 10 → 3, p50 18.8 s. Gemini ≈ 343 calls today.

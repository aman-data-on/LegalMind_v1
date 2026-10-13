# Contract report × current RAG — implementation trace (2026-09-29)

📁 **Working document.** Records what the upload → report path actually runs, which of the
RAG programme's improvements (roadmap PHASE 2–13) apply to it, what was measured, and what
changed. It decides nothing; verdict semantics are the locked evaluators' (`AI-01`, `AM-54`
r-terms, 45B.4). Branch `feat/report-speed`, not committed.

Method: imports and call paths read from code (citations below), then measured — zero
Gemini first (shortlist probe, NLI replay, furniture and embedding timings, read-only on
production), then one live confirmation per claim.

## 1. The report pipeline as it runs

| Stage | What runs (code) | RAG-lane component it uses |
|---|---|---|
| Upload | `POST /contracts/{id}/document-versions` (`api/routers/contracts.py`); magic-byte validation (`ingestion/validation.py`) | — |
| Parse / OCR | `ingestion/service.ingest_document` inline; OCR via `worker/dispatch.dispatch_ocr` | — |
| Ask index (side branch) | `assist/indexing.py` — chunks + embeddings, PHASE 2 integrity gate (`chunking.integrity_failures`) | used by Ask only |
| Clause extraction | `mapping/service.load_clauses` — evidence rows of the latest completed parse run | — |
| Standard matching | `analysis/service._map_item`: lexical rules (`mapping.engine`), then `semantic.build_index` (local embeddings) + cosine shortlist + `semantic.adjudicate` (Gemini, verbatim-span verified) | `embedding_runtime`, `generation.generate_raw` |
| Facts | `extraction/liability` deterministic; `semantic.extract_cap` (Gemini, value + unit verified in a verbatim span) | `generation.generate_raw` |
| Verdict | `evaluation.registry.evaluate` — NUMERIC_COMPARISON / PRESENCE, zero-tolerance Legal Rule | none (locked) |
| Evidence | `EvaluationEvidence` rows cited by each Evaluation | — |
| Explanation | `assist/explanations.py` (`AM-49`) — mechanical validation | `generation`, `guardrails` word screen |
| Report / UI | `api/reporting.report_payload`; `ReviewReportPage.tsx`; per-card explanation in `FindingsPane.tsx` | — |

`grep` over `analysis/ mapping/ extraction/ evaluation/ api/reporting.py assist/explanations.py`:
the only RAG-lane imports are `embedding_runtime`, `generation`, `guardrails`. No reference
to `knowledge_items`, `position_chunks`, `statute_chunks`, `chunks`, `search_hybrid`,
`rerank`, `verify`, `contracts`, `claim_records` or `evidence`.

## 2. Each roadmap improvement against the report path

| Phase | Improvement | Report path | Evidence |
|---|---|---|---|
| 1 | Canonical knowledge model (`AM-79`) | **Not applicable by lock** | `AM-79`: positions reach the evaluator only as ratified standard files; the report reads the Review's pinned configuration snapshot (rule 16) |
| 2 | Ingestion integrity | Parse + validation shared; chunk gate is Ask's | Page furniture: 88 rows in 24 production documents, **0** cited by any Evaluation, **0** of 362 unmatched-provision entries — no effect on a report |
| 3 | Hierarchical context (heading with the clause) | Not integrated — **measured, no gain** | Shortlist probe below: B1 = A (66/69), rank-1 43 → 40. Explanation payload with headings + 1,200-char passages: 30/69 → 29/69 accepted (live, production findings) |
| 4 | Embedding selection (`AM-83`, MiniLM) | **Used** — same `embedding_runtime` | `semantic.build_index` |
| 5 | Index/storage | In-memory exact cosine per document (≤~150 clauses); **anchor vectors now cached** per worker process (~0.8 s/run) | `semantic._ANCHOR_VECTORS` |
| 6 | Query understanding | **Not applicable** — no reader question | — |
| 7 | Hybrid lexical + vector | **Used** — lexical mapping rules first, vector shortlist where they are silent | `_map_item` |
| 8 | Cross-encoder rerank | Not integrated — **measured, no gain** | Among the 17 cases the semantic stage decides: A misses 1, B2 misses a different 1. Adds ~1 s CPU per requirement |
| 9 | Authority / version / temporal controls | **Used, stricter form** — ratified standards only, pinned snapshot, latest completed parse run; no statute in a report, so no temporal status to carry | `load_clauses`, snapshot pinning |
| 10 | Grounded generation | **Used** — the single egress seam, `AM-30` payload rules | `_egress_for`, `explanations._call` |
| 11 | Claim/citation verification | **Used** — every semantic confirmation and every extracted quantity must match a verbatim span; explanations mechanically validated. NLI **measured, no gain** | NLI over 27 accepted production explanations: 2 flagged (1 a false reject on an absence), requiring entailment would cut acceptance 39% → ~19% |
| 12 | Claim contracts / records | **Not applicable** — Ask answer composition; a Finding's sentence is one `AM-49` sentence | — |
| 13 | Rollout / observability | **Added** — `analysis.stage.map`, `analysis.stage.explain` timings | `analysis/service.py`, `worker/tasks.py` |

## 3. Accuracy

**Shortlist probe (zero Gemini).** 107 labelled variants (AM-54 R&D corpus, 19 ratified
standards) each placed inside a real 81-clause contract: does the clause reach the model?

| Mode | Positives shortlisted (69) | Ranked first | Negatives shortlisted (38) |
|---|---|---|---|
| A — today | 66 | 43 | 19 |
| B1 — clause + heading | 66 | 40 | 19 |
| B2 — reranked | 67 | 33 | 17 |
| B3 — both | 67 | 33 | 17 |

76 of 107 are decided lexically; of the 17 positives the semantic stage decides, A and B2
each miss one (different ones).

**Live corpus (report path, 124 Gemini calls).** Recognition 68/69; semantic false
positives 0/38; classification correct 49, **wrong 0**, fail-safe 17; the semantic stage
recovers 35 lexical misses and changes no correct result.

**Why the 17 fail-safes stay.** Each was traced: the clause is found, and for the numeric
standards the value is even read and verified ("2 percent per month", "30 days"), but the
evaluator also needs the *basis* and 45B.4 forbids assuming it — so it fails closed to a
person. That is verdict semantics, not retrieval.

**Concurrency is verdict-neutral.** With a deterministic stand-in for the model, sequential
and concurrent analysis of a real document give identical Findings, identical outcomes with
every diagnostic in order, and identical audit rows (47) in the same order.

## 4. Performance

| | A — before (production, n=5) | B — after (3 real documents) |
|---|---|---|
| Analysis | p50 117 s, p95/max 157 s | p50 24.7 s, max 28.1 s |
| Findings with their sentence | each card 12 s p95 / 33 s max on first view | all stored at p50 39.9 s, max 41.9 s after start |
| Gemini per report | ~43-53 recognition; ~40 explanations for an opened review, on view | 43 recognition; ~40 explanations right after analysis |
| Tokens per report | — | ~39k in / ~10k out, explanations included |

Live safety of concurrency: 138 calls six at a time in 42 s with no failure.

## 5. Second pass (owner, 2026-09-29) — reconciled, investigated, measured

**Verdict cache (PR #130, now on `main`).** The concurrent prefetch runs AFTER the cache:
a prompt the cache already holds for this snapshot and pinned model is never prefetched,
and a prefetched answer is written to the cache and audited exactly like a live one.
Four real documents analysed twice each: every repeat asked the model nothing (one SLA
prompt whose first attempt had failed — failures are never cached — was asked again) and
produced the same Findings in the same order. Tests: `test_semantic_recognition_cache.py`
(prefetch skips a cached prompt; a prefetched answer becomes the cache's),
`test_semantic_recognition.py` (a repeat analysis asks nothing and finds the same).

**The vendor governing-law MATCH — standards question, no code change.** Every ratified
governing-law standard is PRESENCE (`evaluation_rules.evaluator`), with the note
"presence is established by the mapping layer alone (45D)": GOVLAW-MSA/NDA/TOS say only
"governed by the laws of India"; the vendor standard names a Pune venue in its description
but was ratified PRESENCE. The PRESENCE evaluator has no value comparison. The Constitution
§22 / §31.1 does state Pune courts and arbitration seat. Making the venue count means
changing ratified standards and adding an evaluator behaviour — a standards decision, not
a comparison bug.

**The verified-number fail-safe — not safe, by 45B.4.** The basis is found only from the
standard's configured basis terms (`extraction.liability._find_basis`); none matching
leaves it unknown and the comparison fails closed ("an unrecognised basis fails closed
rather than being equated with the Company Standard's"). Taking the only configured basis
would equate "interest at 2 percent per month" with a "late fee", or "remedied" with
"cured" — exactly the equivalence 45B.4 forbids, and it would let the model's SAME verdict
decide it. The number is already verified; what is missing is a ratified basis term, which
is standards configuration (rule 21).

**Explanations after analysis vs on access.** Production since the layer went live: 10
reviews analysed, 4 opened, first view 10 s, 7 min, 19 min and 25 min after analysis (6
unopened, all a burst on 9 Sep). On access, a card waits 12 s p95 / 33 s max on first view;
after analysis, the sentences are stored before 3 of the 4 readers arrived. Cost ~40 short
calls per unopened review. Kept: after analysis (`LEGALMIND_EXPLAIN_AFTER_ANALYSIS=off`
reverts).

**Explanation acceptance — prompt, not AM-49.** The prompt never told the model the
validator's rule. `finding-explanation-2` states it (build from the approved wording and
the passages, only the listed linking words, a construction for an absent clause, the
length, no judgment words). On production's 69 explained Findings, validator unchanged:
v1 30/69 → v2 53/69 → **v3 (shipped) 65/69**. The last four are the validator working (the
contract's own "breach"/"liable" are judgment words it rejects; one over 35 words).
`test_the_prompt_permits_only_words_the_validator_accepts` keeps prompt and validator from
drifting.

**Benchmarks re-run on the combined code (provider degraded: ~6-8 s per call, 37 failures
in 293 calls on the document run).**

| | Morning (before second pass) | Combined code |
|---|---|---|
| Corpus recognition | 68/69 | 66/69 — the two misses re-run 3× each come out correct every time (transient provider failure: with no model, `AM-54` keeps the lexical result) |
| False matches (semantic) | 0/38 | 0/38 |
| Correct / fail-safe / wrong | 49 / 17 / 0 | 48 / 16 / 2 → 0 wrong on re-run |
| Explanations accepted (production's 69) | 30/69 | 65/69 |
| Four real documents, analysis | — | p50 177 s vs 654 s one-at-a-time under the same provider latency (3.7×); 24.7 s at normal latency (first pass) |
| Repeat analysis | — | 0 calls, same Findings in the same order, 4/4 documents |
| Tokens, four documents incl. explanations | — | 196k in / 36k out (~49k / 9k per report) |

## 6. Found, not changed (verdict semantics or legal policy)

- **`GOVERNING-LAW-DISPUTE-VENDOR_AGREEMENT-001` scored MATCH on an NDA choosing Bengaluru
  courts** although the standard's wording names a Pune venue: it is a PRESENCE requirement
  (any governing-law clause satisfies it) and applies by content across families (`AM-51`).
  The explanation said so ("rather than Pune") while the verdict said MATCH.
- **Basis for single-basis numeric standards** — see §3.
- **A provider outage asserts MISSING.** With no model reached, `AM-54` keeps the lexical
  result, and where the configured words are silent that is MISSING rather than Needs
  review — seen as two transient false MISSINGs today. Locked behaviour; recorded.

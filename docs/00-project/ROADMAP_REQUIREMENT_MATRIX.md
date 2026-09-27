# Roadmap requirement matrix — LegalMind Production RAG

> 📁 **Working document** (live). Tracks every section of
> [LEGALMIND_RAG_PRODUCTION_ROADMAP.md](../LEGALMIND_RAG_PRODUCTION_ROADMAP.md) (v1.0)
> from requirement to evidence. A row is ✅ only when implementation, a regression test
> AND a measurement exist. Update it in the same change that moves a row. It decides
> nothing; decisions stay in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md).

Status: ✅ met with evidence · 🟡 partly met / evidence thin · 🔴 defect open · ⬜ not started

Baseline: commit `608cbb6` (AM-94); last unit AM-98. Last updated 2026-09-27.

| § | Requirement | Implementation | Test | Benchmark / evidence | Status | Remaining issue |
|---|---|---|---|---|---|---|
| 1 | Canonical source model; history separate; authority/version/status on records | `assist/constitution.py`, `knowledge_items` (AM-79) | `test_knowledge_source_model.py` | PHASE 1 report | ✅ | — |
| 2 | Ingestion integrity; nothing searchable before it passes | `statutes.check_integrity` (AM-80) | `test_statute_integrity*` | 17/17 Acts, rehearsed on prod-like copy (AM-94 r6) | ✅ | — |
| 3 | Hierarchical chunking, parent restored | AM-82 | `test_constitution_retrieval*` | PHASE 3 report | ✅ | — |
| 4 | Embedding benchmarked, not assumed | AM-83 | `benchmark_embedders.py` | MiniLM kept on measurement | ✅ | — |
| 5 | Postgres unless evidence says otherwise | AM-84 | `benchmark_storage.py` | exact pgvector at measured depth | ✅ | — |
| 6 | Query understanding + decomposition | `query_plan.py` (AM-85), vocabulary + instrument recognition (AM-96) | `test_query_plan*`, `test_assist_planner.py` | F 0.5 → 0.83, K 0.6 → 0.8 | ✅ | K-05 |
| 7 | Broad hybrid retrieval, diversity, no top-3 dependency, exact reference | `retrieval.candidates/select` (AM-86), `exact_reference` (AM-95 r1) | `test_retrieval_pool.py` | pool recall 0.988; A-04 s. 74 now rank 1 | ✅ | — (F-03/F-04 closed by AM-96) |
| 8 | Rerank + parent context | `retrieval.rerank` (AM-87), length-sorted batching (AM-94 r8) | `test_retrieval_pool.py` | rerank p95 3.1 → 1.1 s; statute ranked with its title (AM-98) recall@3 0.864 → 0.901 | ✅ | — |
| 9 | Evidence bundle: part states, kinds apart | `evidence.py` (AM-88) | `test_evidence_bundle.py` | wrong-source 0, false admission 0; floor 8 + `OFF_TOPIC` (AM-97) recall@3 0.815 → 0.864 | ✅ | — |
| 10 | Grounded conversational generation | `generation.py`, `contract-answer-2` (AM-89/AM-94 r9) | `test_bundle_answer.py` | better on 5/6 judged | ✅ | O-03 (see §14) |
| 11 | Claim-level verification | `verify.py` (AM-90), contract checks (AM-91–93) | `test_claim_verification.py`, `test_claim_contracts.py` | run-9 replay: bad shown 16 → 12 | 🟡 | 12 bad sentences still shown in 65 (AM-92 cross-reference class) |
| 12 | Precise citations | markers assigned by code (AM-90), legend (AM-94 r3) | `test_ask_multi_source_rollout.py` | citation correctness 0.996 | ✅ | — |
| 13 | Multi-source reasoning, never blended | AM-91–93 | `test_multi_source_reasoning.py` | [A]/[M] 11/11 on layered cases | ✅ | — |
| 14 | Authority / jurisdiction / temporal behaviour | repealed status (AM-80), `wants_past`, `include_superseded`, `evidence._wrong_act` (a named section of a named Act is answered by that Act alone) | `test_evidence_bundle.py::…another_act` | H-04 historical → repealed Act; O-01/O-02 current → never repealed; H-02 no longer answered from CGST (75/76 byte-identical) | 🟡 | no NOT-YET-EFFECTIVE statute exists in the corpus to test "latest ≠ effective" beyond DPDP record status; no second jurisdiction supplied (wrong-jurisdiction proven only by router refusal) |
| 15 | Conversation intelligence | anchor (`_resolve_follow_up`) for the retrieval query; planner fed every bounded prior question; a turn naming its own source never inherits (AM-95 r3/r4) | `test_assist_conversation_memory.py`; `test_conversation_multi_source.py` (5) | golden J 7 cases, recall@3 1.0, wrong-context 0 | ✅ | AM-97 r3: a reader's figure is stated only with its unit (a bare 6 had hidden "6 months"). Earlier fix: the §15 example was not anaphoric so production never gave the planner the prior question (the benchmark always did) — it fell back to legacy; and a 3-turn chain lost the topic. Needs golden follow-up cases (§17) for a measurement |
| 16 | Evaluation per layer | `rag_benchmark.py` (retrieval + wrong-source/false-admission per stage and category), `eval_generation.py` (generation) | — | recall@3/10, hit@1, MRR, nDCG@5, wrong-source, false admission per stage | ✅ | conversation metrics are category J of the same tool; no separate tool needed |
| 17 | Permanent golden suite A–O | `tests/assist_eval/rag_benchmark.json` (79 cases) | benchmark tool | all 15 categories; K 0.2 → 1.0 (AM-95 r5, AM-96, AM-97) | 🟡 | B 0.8, E 0.75, G 0.67, H 0.5, O 0.67 recall@3 (AM-98); must-refuse is scored by empty gold + must_not, not a flag |
| 18 | Deployment discipline | flag + canary share + trace + rollback (AM-94) | `test_ask_multi_source_rollout.py` | rehearsed, never applied | 🟡 | production steps need owner authorisation; clean single-request latency not yet measured on idle host |
| 20 | Definition of done | — | — | — | 🟡 | follows from the rows above |

## Open work, in dependency order

1. ~~§15 — follow-up fallback~~ fixed and measured (J 1.0).
2. ~~§14 — `WRONG_ACT`~~ fixed; corpus limits recorded as residuals.
3. ~~§16/§17~~ follow-up cases added; ~~F-03/F-04/K-03~~ closed (AM-96). ~~K-05, D~~ closed (AM-97). ~~B-03, E-01, GT-11~~ closed (AM-98). Open, each traced to its stage (2026-09-27):
   - B-05 — rerank: the cross-encoder scores "raise our prices" irrelevant to "Prices may be changed"; synonym rewriting is query rewriting (off).
   - E-02, F-05 — statute part: DPDP s. 8 not in the pool; s. 33 in the pool but below the relevance floor, and the Schedule holding the figure is not in the pool.
   - E-03 — planner: the sub-question drops "two-year non-solicit" ("a restraint like that"), so s. 27 ranks 39th.
   - G-03 — selection: §13's matching paragraph is a legal-validation note, so the section is kind LAW only and never taken for the position lane. Changing that touches kind separation (§13), so it needs its own measured unit.
   - H-01 — selection: §4.1 is 9th in the Constitution pool, which is not cross-encoder ranked (AM-87).
   - O-04 — corpus: IT Act s. 70B is absent from the supplied text.
4. §11 — attack the remaining 12 shown bad sentences where the root cause is local.
5. §18 — idle-host latency measurement; runbook numbers refreshed.

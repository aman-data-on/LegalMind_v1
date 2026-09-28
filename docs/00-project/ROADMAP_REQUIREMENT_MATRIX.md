# Roadmap requirement matrix — LegalMind Production RAG

> 📁 **Working document** (live). Tracks every section of
> [LEGALMIND_RAG_PRODUCTION_ROADMAP.md](../LEGALMIND_RAG_PRODUCTION_ROADMAP.md) (v1.0)
> from requirement to evidence. A row is ✅ only when implementation, a regression test
> AND a measurement exist. Update it in the same change that moves a row. It decides
> nothing; decisions stay in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md).

Status: ✅ met with evidence · 🟡 partly met / evidence thin · 🔴 defect open · ⬜ not started

Baseline: commit `608cbb6` (AM-94); last unit AM-104. Last updated 2026-09-28.

| § | Requirement | Implementation | Test | Benchmark / evidence | Status | Remaining issue |
|---|---|---|---|---|---|---|
| 1 | Canonical source model; history separate; authority/version/status on records | `assist/constitution.py`, `knowledge_items` (AM-79) | `test_knowledge_source_model.py` | PHASE 1 report | ✅ | — |
| 2 | Ingestion integrity; nothing searchable before it passes | `statutes.check_integrity` (AM-80); `section-5` drops the Bill's Statement of Objects and Reasons (AM-104 r3) | `test_statute_integrity*`, `test_retrieval_misses_am104.py` | 17/17 Acts, 5,011 chunks rehearsed on a clone of the prod-like copy (AM-104); Copyright s. 79 recovered | ✅ | — |
| 3 | Hierarchical chunking, parent restored | AM-82 | `test_constitution_retrieval*` | PHASE 3 report | ✅ | — |
| 4 | Embedding benchmarked, not assumed | AM-83 | `benchmark_embedders.py` | MiniLM kept on measurement | ✅ | — |
| 5 | Postgres unless evidence says otherwise | AM-84 | `benchmark_storage.py` | exact pgvector at measured depth | ✅ | — |
| 6 | Query understanding + decomposition | `query_plan.py` (AM-85), vocabulary + instrument recognition (AM-96) | `test_query_plan*`, `test_assist_planner.py` | F 0.5 → 0.8, K 0.6 → 1.0 | ✅ | — (K-05 closed by AM-97) |
| 7 | Broad hybrid retrieval, diversity, no top-3 dependency, exact reference | `retrieval.candidates/select` (AM-86), `exact_reference` (AM-95 r1); once per list, section titles, named-Act title words, CERT-In (AM-104 r1) | `test_retrieval_pool.py`, `test_retrieval_misses_am104.py` | pool recall 0.988; H-01 §4.1 10th → 1st, E-03 s. 27 42nd → 4th, O-04 s. 70B 32nd → 1st; recall@3 0.926 → 0.951 | ✅ | — |
| 8 | Rerank + parent context | `retrieval.rerank` (AM-87), length-sorted batching (AM-94 r8) | `test_retrieval_pool.py` | rerank p95 3.1 → 1.1 s; statute ranked with its title (AM-98) recall@3 0.864 → 0.901 | ✅ | — |
| 9 | Evidence bundle: part states, kinds apart | `evidence.py` (AM-88); cited Schedule in its section's context (AM-104 r2) | `test_evidence_bundle.py` | wrong-source 0, false admission 0; recall@3 0.951 (79) / 0.952 (81, re-ingested corpus) | ✅ | E-03, F-05/O-05 statute slot: the local cross-encoder scores the right section below the floor (evidence 10 fixes E-03 at +17% evidence — not adopted) |
| 10 | Grounded conversational generation | `generation.py`, `contract-answer-2` (AM-89/AM-94 r9) | `test_bundle_answer.py` | better on 5/6 judged | ✅ | O-03 (see §14) |
| 11 | Claim-level verification | `verify.py` (AM-90), contract checks (AM-91–93), section/status/modal checks (AM-104 r6) | `test_claim_verification.py`, `test_claim_contracts.py`, `test_retrieval_misses_am104.py` | run-9 replay: bad sentences shown 16 → 4 of 574 (0.7%), answers with one 12 → 4, citation correctness 0.993; verifier isolated on identical claims: 7 new catches, 0 false rejects; fallbacks 2/65 (one is N-02's injection, now refused) | ✅ | 4 bad sentences are generation faults (garbled antecedent, dropped statute reference, spliced provisos) no deterministic check sees |
| 12 | Precise citations | markers assigned by code (AM-90), legend (AM-94 r3) | `test_ask_multi_source_rollout.py` | citation correctness 0.996; legend one number per source, rendered as a list (AM-102) | ✅ | — |
| 13 | Multi-source reasoning, never blended | AM-91–93 | `test_multi_source_reasoning.py` | [A]/[M] 11/11 on layered cases | ✅ | — |
| 14 | Authority / jurisdiction / temporal behaviour | repealed status (AM-80), `wants_past`, `include_superseded`, `_wrong_act`; commencement records from Constitution §28.2 (AM-104 r4) | `test_evidence_bundle.py::…another_act`, `test_retrieval_misses_am104.py` | DPDP s. 33/Schedule shown NOT YET IN FORCE until 13 May 2027 (live F-05, O-05, J-04), labelled as the Constitution's date | ✅ | tranche 3's described (unnumbered) obligations carry no record (rule 7); the Gazette notification is not in the supplied material; no second jurisdiction supplied |
| 15 | Conversation intelligence | anchor (`_resolve_follow_up`) for the retrieval query; planner fed every bounded prior question; a turn naming its own source never inherits (AM-95 r3/r4) | `test_assist_conversation_memory.py`; `test_conversation_multi_source.py` (5) | golden J 7 cases, recall@3 1.0, wrong-context 0 | ✅ | AM-97 r3: a reader's figure is stated only with its unit (a bare 6 had hidden "6 months"). Earlier fix: the §15 example was not anaphoric so production never gave the planner the prior question (the benchmark always did) — it fell back to legacy; and a 3-turn chain lost the topic. Needs golden follow-up cases (§17) for a measurement |
| 16 | Evaluation per layer | `rag_benchmark.py` (retrieval + wrong-source/false-admission per stage and category), `eval_generation.py` (generation) | — | recall@3/10, hit@1, MRR, nDCG@5, wrong-source, false admission per stage | ✅ | conversation metrics are category J of the same tool; no separate tool needed |
| 17 | Permanent golden suite A–O | `tests/assist_eval/rag_benchmark.json` (81 cases) | benchmark tool | O-05 (DPDP commencement) and O-06 (s. 70B) added; B-05 accepts §16, F-05's Schedule ref corrected (AM-104) | ✅ | misses left: E-03, F-05, O-05 statute slot (cross-encoder), H-02 (s. 194J not in the accepted text) |
| 18 | Deployment discipline | flag + canary share + trace + rollback (AM-94); egress audited on failure, trace failures as kinds (AM-104 r8) | `test_ask_multi_source_rollout.py` | migrations down/up twice + Constitution (701/404) and statute (5,011, `section-5`) ingestion rehearsed 2026-09-28 on a clone of the AM-94 prod-like copy; idle rerank p50/p95 866/1,084 ms; live generation p50 2.8 s; browser Ask 6–21 s per answer through a production-like proxy (host partly loaded); `assist.ask.trace` fields checked on real requests (path, fallback_kind, gemini_calls, latency, verify/gemini/prepare ms; no text) | 🟡 | a FRESH production snapshot for the rehearsal was not taken (dumping production needs owner authorisation); production steps need the owner |
| 20 | Definition of done | branch `feat/legalmind-rag-production`, main merged in locally (clean) | backend 2747 passed / 112 skipped / 0 failed; frontend 531 passed; ruff, mypy, tsc, forbidden-terms clean | golden recall@3 0.951 (79) / 0.952 (81), wrong-source 0, false admission 0; run-9 replay bad shown 0.7%, fallbacks 2/65; live 18/20 in one call; real browser upload → review → findings → Ask → history → 390 px clean; security review done (3 fixes, AM-104 r8); migration + ingestion rehearsed; trace fields checked | 🟡 | engineering and validation done for this branch; CI never run (needs a push). Remaining: the owner's release actions below, and the localized residuals (item 3 of Open work) |

## Open work, in dependency order

1. ~~§15, §14 `WRONG_ACT`, §16/§17 cases, §11 live fallbacks~~ done (AM-95–AM-103).
2. ~~H-01, D-01, O-04, B-05 (gold), F-05 context, DPDP commencement, s. 70B, "bare Section N"~~ done (AM-104). "Section 28" was a code defect (a status cut at the dot in "28.2.1"), not an ambiguity; s. 70B was always in the supplied text.
3. Residuals, each localized (2026-09-28): E-03 and the F-05/O-05 statute slot — the local cross-encoder; H-02 — source absent; 4 generation-only bad sentences; E-02 and H-01 can fall back live when a draft fails a strict check (safe: the legacy answer is shown).
4. §20 — CI (needs a push) and the owner's release actions below.

## Release actions that need the owner (2026-09-28)

1. Push `feat/legalmind-rag-production` and open the PR; CI must pass on the ruleset.
2. Merge after CI.
3. Production: back up the DB, apply migrations `e9f2b6c4a173` → `b8e2f6a4d1c3`, run `tools.ingest_constitution` and `tools.ingest_statutes` (the live corpus is still `section-1`: s. 70B and the `section-5` fixes arrive only with this re-ingest), then `tools.import_ratified_standards` if needed, restart the API.
4. Enable `LEGALMIND_ASK_MULTI_SOURCE=no_document` with a small `LEGALMIND_ASK_MULTI_SOURCE_PERCENT` canary, watch `assist.ask.trace` (path, fallback_kind, gemini_calls, verify_ms), widen. Rollback = the flag off.
5. Optional: authorise a fresh production snapshot for one more rehearsal; supply the DPDP commencement Gazette notification (G.S.R. 843(E)) if the statute record should cite it rather than the Constitution.

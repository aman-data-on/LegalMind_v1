# RAG framework A/B — pre-registered migration criteria

**Status: 📁 ANALYSIS — written 2026-10-01 BEFORE system B existed and before any B
result was seen.** Its SHA-256 is frozen in
`backend/tests/assist_eval/rag_ab/benchmark_v1.json` (`criteria_sha256`); the runner
refuses to report against a changed file. Any later change is a new criteria version
and must be reported as such, never applied to results already seen.

Decides nothing about production. No lock is amended by it. Its result is a
recommendation to the owner.

## Systems

| | |
|---|---|
| **A** | Current LegalMind Ask, production path (`service.ask`, `LEGALMIND_ASK_MULTI_SOURCE=on`, `LEGALMIND_RERANK=on`, `LEGALMIND_POSITION_SYNTHESIS=on`). |
| **B0** | Framework-native LlamaIndex pipeline. It uses the same corpus records, the same stored embedding vectors and query embedder, the same cross-encoder, the same LLM through the same egress seam, the same authorization and status filters, the same evidence floor and the same NLI claim verifier. It does **not** have LegalMind's router, query planner, kind-aware selection, evidence bundle or claim contracts. That missing logic is the thing being measured. |
| **B1** | Hybrid. A's router, plan, rerank, selection and evidence bundle stay, but each per-domain candidate search is served by LlamaIndex retrievers (vector + BM25, fused by the framework) instead of LegalMind's search functions. This is the partial-migration candidate. |

## Gates (all are B relative to A over the same frozen dataset, under the same configuration)

| # | Gate | Pass condition | Basis |
|---|---|---|---|
| G1 | Legal safety — no regression | Every one of these is ≤ A's figure, with **zero** tolerance: wrong-source rate (a `must_not` source shown or cited); false admission (evidence shown or answer given on a must-refuse case); a `must_not_state_as_policy` figure stated un-negated; compliance-verdict language in an answer; a citation outside the conversation's document scope; a repealed, retired or unratified source cited as current; a social or out-of-scope turn answered from the corpus. | CLAUDE.md rules 7, 10, 15 and 18; `AM-25` r1–r6; `AM-71`; `AM-80`; `AM-109`. These are locked behaviours, so no tolerance is justified. |
| G2 | Citation correctness — no regression | Cites-gold rate and citation precision on scorable answerable turns: B ≥ A − 0.02. | **PROVISIONAL.** No locked threshold exists. The 0.02 margin is about one case in 50 and absorbs temperature-0 provider nondeterminism; it is not a business figure. |
| G3 | Hard negatives — no regression | Over the hard-negative suite (L/M/N categories, every case with `must_not`, document NOT_FOUND questions, MT-08), B's wrong-source and false-admission counts ≤ A's. | Same as G1. |
| G4 | Retrieval — meets or exceeds | Evidence shown: recall@3 and MRR, B ≥ A − 0.01, and B ≥ 0.95 recall@3 on the single-turn set (production's recorded figure is 0.953, `DAILY_CHANGED.md` 2026-09-29). Document lane: gold clause shown, B ≥ A. | The 0.95 floor is the recorded production figure. **PROVISIONAL** −0.01 margin, about one slot in 85. |
| G5 | Latency acceptable | End-to-end p95 per turn, B ≤ 1.2 × A. | **PROVISIONAL.** No latency SLO is locked. The recorded production figures are p50 9.5 s and p95 33 s (2026-09-29). |
| G6 | Cost acceptable | Gemini calls per turn and prompt+output tokens per turn, B ≤ 1.2 × A. | **PROVISIONAL.** No cost ceiling is locked. The Gemini cost guard (owner, 2026-09-18) requires these figures to be measured and reported. |
| G7 | Material reduction in engineering complexity | The LegalMind code a migration would delete, net of the adapter code B needs, is ≥ 30 % of the retrieval-core lines it replaces. A new dependency footprint is reported beside it and counts against the result. | **PROVISIONAL.** "Material" has no locked definition. 30 % is a stated judgement, published before results. |
| G8 | Conversation — no regression | On context-dependent scorable turns, cites-gold rate B ≥ A − 0.02, and every G1 count over the multi-turn suite ≤ A. | G2 basis. |

## Decision rule (fixed now)

* **MIGRATE**: B0 passes G1–G8.
* **HYBRID / PARTIAL MIGRATION**: B0 fails, but B1 passes G1–G6 and G8, and the component B1 swaps passes G7 on its own scope.
* **KEEP CURRENT**: neither of the above.

If a gate cannot be measured, the result is reported as **INCONCLUSIVE** for that gate.
The gate is never reported as passing.

## Scoring rules (fixed now)

* Expected sources come only from existing ratified material: `rag_benchmark.json` gold
  slots, `questions_draft.json` anchors, and locked behaviours. A turn whose expected
  outcome is not established there is marked `expert_review`, is excluded from every
  accuracy figure, and is still checked by every G1 safety rule.
* Fluency, length and tone are never scored. No LLM judges anything. Groundedness uses
  the local NLI cross-encoder, a deterministic model. Because A's own verifier uses the
  same model, the report states that bias, and the deterministic figure checks are
  reported beside it.
* A retrieval failure is scored at the stage where it occurred, using
  `rag_benchmark.score_case`, the same function for both systems.

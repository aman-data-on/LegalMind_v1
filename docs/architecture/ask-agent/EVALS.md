# Ask agent — evaluation runs

| # | When (IST) | Commit | Benchmark | Corpus | Result | Gemini calls |
|---|---|---|---|---|---|---|
| 1 | 2026-09-30T12:55+05:30 | `ee9dd10` | `tools.rag_benchmark` | live DB, read-only | bundle recall@10 0.9529 · wrong-source 0 · false admission 0 | 0 |
| 2 | 2026-09-30T13:05+05:30 | Phase 0 working tree | `tools.rag_benchmark` | live DB, read-only | identical to #1 | 0 |
| 3 | 2026-09-30T17:40+05:30 | `b2a2795` | private document probe (`probe_targeting` on scratch corpus) | 15 supplied docs, clause-aware-4 | recall@10 0.6406 · hit@1 0.4375 · MRR 0.5107 | 0 |
| 4 | 2026-09-30T18:15+05:30 | pre-`80dfcf2` | private document probe | 15 supplied docs, clause-aware-5 | recall@10 0.6562 · hit@1 0.4375 · MRR 0.5126 | 0 |
| 5 | 2026-09-30T18:45+05:30 | pre-`80dfcf2` | `tools.rag_benchmark` | live DB, read-only | identical to #1 | 0 |
| 6 | 2026-09-30T20:10+05:30 | `6171352` + probe tool | `tools.probe_real_corpus --write-keys` | real corpus: 32 DOCX/PDF, 942 probes | recall@10 0.7258 · hit@1 0.6577 · MRR 0.6840 · false admission 0.0078. Misses 153: RETRIEVAL_MISS 97 (61 clause-number), GATE_CLOSED 35, RANK_CUTOFF 21 | 0 |
| 7 | 2026-10-01T10:30+05:30 | `31981d5` | `tools.probe_real_corpus --reuse` | same corpus and keys (0 drift) | recall@10 **0.8853** · hit@1 0.8082 · MRR 0.8381 · false admission 0.0078. Clause numbers recall@10 1.000; exact terms 0.8333. Misses 64, all exact-terms: GATE_CLOSED 36, RANK_CUTOFF 21, RETRIEVAL_MISS 7. **#6→#7 is the A-6 gold-definition correction, not a retrieval change** | 0 |
| 8 | 2026-10-01T11:05+05:30 | working tree | `tools.probe_real_corpus --reuse --write-keys` | same corpus; keys re-pinned (938) | recall@10 0.9657 · hit@1 0.8917 · MRR 0.9228 · false admission 0.026 (10/384). Misses 19 | 0 |
| 9 | 2026-10-01T11:12+05:30 | working tree | `tools.probe_real_corpus --reuse --write-keys` | same corpus, verbatim queries, 938 keys | recall@10 **0.9982** · hit@1 0.9242 · MRR 0.9544 · false admission 0.026 (10/384, all vector-gate, A-8). Clause numbers recall@10 1.000 / hit@1 0.9706; exact terms 0.9974 / 0.9036. Misses 1 (RETRIEVAL_MISS). **#7→#9 are probe corrections (A-7), not retrieval changes** | 0 |

No Gemini-backed evaluation has been run. Budget used: ₹0 of ~₹918.25.

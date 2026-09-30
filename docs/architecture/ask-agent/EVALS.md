# Ask agent — evaluation runs

| # | When (IST) | Commit | Benchmark | Corpus | Result | Gemini calls |
|---|---|---|---|---|---|---|
| 1 | 2026-09-30T12:55+05:30 | `ee9dd10` | `tools.rag_benchmark` | live DB, read-only | bundle recall@10 0.9529 · wrong-source 0 · false admission 0 | 0 |
| 2 | 2026-09-30T13:05+05:30 | Phase 0 working tree | `tools.rag_benchmark` | live DB, read-only | identical to #1 | 0 |
| 3 | 2026-09-30T17:40+05:30 | `b2a2795` | private document probe (`probe_targeting` on scratch corpus) | 15 supplied docs, clause-aware-4 | recall@10 0.6406 · hit@1 0.4375 · MRR 0.5107 | 0 |
| 4 | 2026-09-30T18:15+05:30 | pre-`80dfcf2` | private document probe | 15 supplied docs, clause-aware-5 | recall@10 0.6562 · hit@1 0.4375 · MRR 0.5126 | 0 |
| 5 | 2026-09-30T18:45+05:30 | pre-`80dfcf2` | `tools.rag_benchmark` | live DB, read-only | identical to #1 | 0 |

No Gemini-backed evaluation has been run. Budget used: ₹0 of ~₹918.25.

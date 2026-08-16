Source: all_lock.md lines 11249-11272 (Step 44, section 44.34). Canonical source: all_lock.md (Step 44 / Step 45A).

# Golden Test Corpus

**Status: LOCKED** — Step 44 is locked in the master specification. See [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

Cross-reference: see ../04-analysis-engine/ANALYSIS_ENGINE.md for the Step 44 lock (item 26: "A golden contract corpus is mandatory for evaluator validation and regression testing"). See REGRESSION_TESTING.md for how the corpus is used when the evaluator changes. See docs/04-analysis-engine/EDGE_CASES/LIABILITY.md for the worked liability examples this corpus is modeled on.

---

## 44.34 Golden test corpus

The Analysis Engine cannot be considered production-ready based only on unit tests.

We need a curated corpus.

Example:

```text
liability/
├── exact_match_6_months.pdf
├── acceptable_deviation_12_months.pdf
├── approval_required_24_months.pdf
├── unlimited_liability.pdf
├── missing_liability.pdf
├── ambiguous_liability.pdf
├── conflicting_liability.pdf
├── carveout_liability.pdf
└── multi_clause_liability.pdf
```

Each has expected results.

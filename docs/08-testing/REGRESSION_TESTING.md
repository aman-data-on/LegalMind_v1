Source: all_lock.md lines 11274-11300 (Step 44, section 44.35). Canonical source: all_lock.md (Step 44 / Step 45A).

# Regression Protection

**Status: LOCKED** — Step 44 is locked in the master specification. See [../00-project/LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

Cross-reference: see GOLDEN_CORPUS.md for the test corpus this process runs against. See docs/04-analysis-engine/ANALYSIS_ENGINE.md for the Step 44 lock (items 23-25 on engine versioning and reproducibility, which this process depends on).

---

## 44.35 Regression protection

Whenever the evaluator changes:

```text
Old test corpus
      ↓
New engine
      ↓
Compare results
```

If:

```text
Expected:
MATCH

Actual:
DEVIATION
```

the change must be investigated before release.

For a legal-analysis system, this is essential.

# Edge Cases — Indemnification

Canonical source: none yet.

## Status: NOT YET SPECIFIED

No indemnification-specific evaluator, requirement identity, company standard, fact schema, or edge-case set has been specified in the master specification (`all_lock.md`, Steps 1–45A).

Indemnification appears in the master specification **only** as an illustrative clause name in generic clause-list examples (e.g. Step 7's list of clause types). No legal rule, threshold, or evaluator behavior for indemnification has been decided.

**Do not invent indemnification rules, thresholds, or evaluator behavior.** They require an explicit specification step, following the same structure used for `LIABILITY-001` in [LIABILITY.md](LIABILITY.md):

1. Requirement identity
2. What the evaluator must determine
3. Structured fact schema
4. Company Standard
5. Legal Rule outcomes
6. Worked examples per outcome
7. Negative patterns and carve-outs
8. Conflict / ambiguity / missing / unable-to-evaluate handling
9. Explicit lock

The generic engine behavior that *would* apply to any requirement — mapping, fact extraction, conflict detection, explainability, fail-closed philosophy — is already locked and lives in [ANALYSIS_ENGINE.md](../ANALYSIS_ENGINE.md), [FACT_EXTRACTION.md](../FACT_EXTRACTION.md), and [CONFLICT_DETECTION.md](../CONFLICT_DETECTION.md).

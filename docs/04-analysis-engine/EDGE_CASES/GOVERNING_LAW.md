# Edge Cases — Governing Law

Canonical source: none yet.

## Status: NOT YET SPECIFIED

No governing-law-specific evaluator, requirement identity, company standard, fact schema, or edge-case set has been specified in the master specification (`all_lock.md`, Steps 1–45A).

Governing Law appears in the master specification **only** as an illustrative clause name in generic clause-list examples (e.g. Step 7's list of clause types). No legal rule, threshold, or evaluator behavior for governing law has been decided.

Note also that Legal/Regulatory References (DPDP Act, IT Act, GDPR, etc.) are a **separate concept** from a governing-law contract clause — see [DOCUMENT_MODEL.md](../../03-document-model/DOCUMENT_MODEL.md), Step 6. The regulatory reference workflow is itself listed as not yet locked.

**Do not invent governing-law rules, thresholds, or evaluator behavior.** They require an explicit specification step, following the same structure used for `LIABILITY-001` in [LIABILITY.md](LIABILITY.md):

1. Requirement identity
2. What the evaluator must determine
3. Structured fact schema
4. Company Standard
5. Legal Rule outcomes
6. Worked examples per outcome
7. Negative patterns and carve-outs
8. Conflict / ambiguity / missing / unable-to-evaluate handling
9. Explicit lock

The generic engine behavior that *would* apply to any requirement is already locked and lives in [ANALYSIS_ENGINE.md](../ANALYSIS_ENGINE.md), [FACT_EXTRACTION.md](../FACT_EXTRACTION.md), and [CONFLICT_DETECTION.md](../CONFLICT_DETECTION.md).

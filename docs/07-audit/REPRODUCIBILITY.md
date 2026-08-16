# Reproducibility

Canonical source: `all_lock.md` (Steps 9, 26, 29, 30, 33, 36.16, 44.36–44.37)

**Status: LOCKED**

Reproducibility is a hard requirement of LegalMind V1, not a nice-to-have. A Review that cannot be reproduced cannot be defended.

This document states the reproducibility *contract*. The mechanisms it depends on are canonical elsewhere:

* Configuration versioning and snapshots → [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md)
* Document/contract immutability and versioning → [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)
* Engine versioning and deterministic execution → [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md) and [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md)
* Audit events → [AUDIT_TRAIL.md](AUDIT_TRAIL.md)
* Regression protection against engine change → [REGRESSION_TESTING.md](../08-testing/REGRESSION_TESTING.md)

---

## The reproducibility contract

**Status: LOCKED**

A historical Review must remain reproducible and auditable. To achieve this, every Review records the exact context it used:

* Contract version / Document Version
* Comparison standard version
* Legal Position / Company Standard version
* Legal Rule version
* Mapping and evaluation rule versions
* Configuration snapshot
* Reviewer/creator
* Timestamp
* Review status
* Findings
* Evidence
* Escalations
* Decisions
* Audit history

---

## The four invariants reproducibility rests on

**Status: LOCKED**

1. **Document Versions are immutable.** A Document Version is never edited in place. A changed document is a new version.
2. **A Review points to exactly one Document Version.** Re-running analysis does not silently re-target the Review at newer content.
3. **Configuration is versioned and snapshotted at Review time.** Publishing a new standard or rule never mutates an existing Review's result.
4. **The audit trail is append-only.** History is added to, never rewritten.

---

## Existing Reviews never silently change

**Status: LOCKED** (Steps 9, 29, 30)

When a standard or legal rule is updated and published:

* All **new** comparisons use the new active version.
* All **existing** Reviews continue to reflect the configuration snapshot they were run against.

```text
MSA Standard
│
├── v1
│   Liability = 6 months
│   Status = Superseded
│
└── v2
    Liability = 12 months
    Status = Active
```

Draft versions must never silently affect comparisons. Only the active published version affects new comparisons.

---

## Re-review is explicit, not implicit

**Status: LOCKED** (Step 33)

Re-running analysis is an explicit, recorded action. Re-review does **not** create a new document version, and it does not erase the prior Review. The prior Review and its result remain retrievable.

---

## Engine versioning

**Status: LOCKED** (Step 44.36–44.37)

The analysis engine itself is versioned, and evaluation is deterministic: the same inputs, the same configuration snapshot, and the same engine version must produce the same result. Because engine changes can alter results, engine version is part of the reproducibility record, and engine changes are guarded by the golden corpus and regression testing.

---

## Evaluation must preserve the calculation

**Status: LOCKED** (Step 36.14)

It is not sufficient to store the outcome. The extracted facts, the standard compared against, the rule applied, and the reasoning path are retained so the conclusion can be re-derived and explained rather than merely re-asserted.

---

## Extraction diagnostics are persisted

**Status: LOCKED** (`REC-07`, 2026-08-16)

`extraction_diagnostics` is persisted as part of the evaluation/evidence record, for auditability and reproducibility — so a historical result can be explained, not merely reproduced.

Two hard constraints:

1. Diagnostics are **diagnostic metadata only**.
2. Diagnostics **cannot independently produce or alter a legal finding**.

This is consistent with 45B.17 (diagnostics must never become legal conclusions) and with the no-generic-confidence-score rule in [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md). Contract detail: [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md).

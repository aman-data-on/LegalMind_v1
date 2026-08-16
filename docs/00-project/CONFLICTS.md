# Conflicts & Ambiguities

Project rule: when two authoritative statements conflict, the conflict is reported, never silently resolved. This document exists so that no future session quietly picks a winner.

**C-01 through C-04 were reconciled by the project owner on 2026-08-16** (registry entries `REC-01`–`REC-06` in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md)). The analysis found that **none of the four was a true contradiction** — each was a supersession chain, a layer migration, a refinement, or different terminology for different stages. No historical locked text was modified.

**C-05 through C-08 remain open.** Do not resolve any open item without explicit approval.

| ID | Subject | Status |
|----|---------|--------|
| C-01 | Finding-type vocabularies | ✅ **RESOLVED** — supersession chain (`REC-01`, `REC-02`) |
| C-02 | Mapping-state vocabularies | ✅ **RESOLVED** — different stages (`REC-03`); one sub-item deferred |
| C-03 | Step 33 vs locked Step 26 | ✅ **RESOLVED** — refinement, no contradiction (`REC-04`) |
| C-04 | 45B field renames | ✅ **RESOLVED** — refinements + 2 defects fixed (`REC-05`) |
| C-05 | Stale 45A status block | ⏳ Open (clerical) |
| C-06 | Two "Step 29" sections | ⏳ Open (low) |
| C-07 | Superseded draft lists | ⏳ Informational |
| C-08 | Reviewer role authority | ⏳ Open (low) |

---

## C-01 — Three different locked Finding-type vocabularies

## ✅ RESOLVED 2026-08-16 — `REC-01`, `REC-02`

**Verdict: not a contradiction.** A supersession chain plus one layer migration and one scope narrowing:

* `ADDITIONAL` (18) → `EXTRA` (27) was a **pure rename** — the two definitions are near-verbatim.
* `UNMAPPED` (18) was a **layer migration**: Step 18 defines it as a *mapping* failure, formalized by Step 28 as mapping-state `UNRESOLVED` (axis 1).
* `CONFLICT`, `UNABLE_TO_EVALUATE` (27) and `AMBIGUOUS`, `UNRESOLVED` (36) were **additive**.
* `EXTRA`'s absence from Step 36 is **scope narrowing, not repeal** — Step 36's list is the outcome set of evaluating a *mapped Requirement*, and an unmatched provision has no Requirement to evaluate.

**Resolution:** the Step 36 seven-value set is canonical for Finding Classification (axis 2). `ADDITIONAL`/`EXTRA` become the document-level `UNMATCHED_PROVISION` observation, which is **not** a classification. Steps 18 and 27 remain locked and unmodified; their vocabularies are annotated as superseded and their behavioral rules remain fully in force.

→ [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) · [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md)

### Original finding (retained for the record)

**Severity: HIGH — affects the database enum, the API contract, and every evaluator.**

| Source | Locked vocabulary |
|--------|-------------------|
| Step 18 | `MATCH` / `DEVIATION` / `MISSING` / `ADDITIONAL` / `UNMAPPED` |
| Step 27 | `MATCH` / `DEVIATION` / `MISSING` / `CONFLICT` / `EXTRA` / `UNABLE_TO_EVALUATE` |
| Step 36 (and used by Steps 44, 45A, 45B) | `MATCH` / `DEVIATION` / `MISSING` / `CONFLICT` / `AMBIGUOUS` / `UNRESOLVED` / `UNABLE_TO_EVALUATE` |

All three are presented in the source as explicit locked decisions. `ADDITIONAL` and `EXTRA` appear to name the same concept under two names; `UNMAPPED` has no counterpart in the later sets; `CONFLICT`, `AMBIGUOUS` and `UNRESOLVED` are absent from the earliest set.

**Partial resolution present in the source:** Step 45A §17 acknowledges the earlier five-type model and states that Step 45 follows the later expanded model. This resolves the question *for the liability evaluator* but does not formally retire the Step 18 or Step 27 locks.

**To resolve:** an explicit decision retiring or superseding the Step 18 and Step 27 vocabularies, and a statement of what happens to `ADDITIONAL`/`EXTRA`/`UNMAPPED`.

Documented at: [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md), [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md).

---

## C-02 — Two different mapping-state vocabularies

## ✅ RESOLVED 2026-08-16 — `REC-03`

**Verdict: not a contradiction — different stages of the same layer.** Step 28 defines the **persisted** mapping state; Step 35's band names are **internal scoring-stage** labels, and its weights/thresholds are already explicitly provisional. Step 28's three values are canonical (axis 1).

> ⛔ **One sub-item deliberately left OPEN.** The scoring-band → mapping-state mapping (whether `CANDIDATE-REVIEW` corresponds to `AMBIGUOUS`, `UNRESOLVED`, or neither) is **NOT YET SPECIFIED** and was explicitly deferred by owner decision. The source never states it. **Do not infer or implement it.**

→ [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md)

### Original finding (retained for the record)

**Severity: MEDIUM**

| Source | Mapping states |
|--------|----------------|
| Step 28 (locked) | `CONFIRMED` / `AMBIGUOUS` / `UNRESOLVED` |
| Step 35 (locked) | `CANDIDATE` vs `CONFIRMED`; thresholds producing `CONFIRMED` / `CANDIDATE-REVIEW` / `NOT MAPPED`; plus `NO_CONFIDENT_MAPPING` |

No source text maps Step 28's `AMBIGUOUS` and `UNRESOLVED` onto Step 35's `CANDIDATE` / `NOT MAPPED` / `NO_CONFIDENT_MAPPING`.

**To resolve:** a single mapping-state enum, or an explicit statement that Step 28 describes mapping *outcomes* while Step 35 describes intermediate *scoring* states.

Documented at: [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md).

---

## C-03 — Step 33 is unlocked but Steps 34–35 depend on it

## ✅ RESOLVED 2026-08-16 — `REC-04`

**Verdict: not a contradiction — Step 33 is a refinement of locked Step 26.** A rule-by-rule comparison of Step 26's 17 locked rules against Step 33's 24 proposed rules found **no reversal**; Step 33 either restates or narrows Step 26 throughout (e.g. rule 14 "never points to a mutable 'latest'" sharpens Step 26 rule 3).

**Resolution:** Step 26 is the locked versioning decision. Step 33 is labelled PROVISIONAL elaboration. Three Step 33 rules have no Step 26 counterpart and **remain unlocked** — sequential version numbering, invalid/withdrawn-instead-of-delete, and the v1→v2→v3 predecessor chain. Do not implement those until Step 33 is explicitly locked.

→ [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)

### Original finding (retained for the record)

**Severity: MEDIUM**

Step 33 (Contract Versioning & Re-Review Workflow) closes with "Do not lock it yet until you confirm it looks right," and no subsequent lock for Step 33 appears in the master specification. Steps 34 and 35 are explicitly locked and use Step 33 concepts (notably "Document Version") throughout. Step 26 independently locks a document/contract versioning model that overlaps Step 33's subject matter.

**To resolve:** either lock Step 33, or state that Step 26's lock is the authoritative versioning decision and Step 33 is elaboration only.

Documented at: [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md).

---

## C-04 — Step 45B field renames vs Step 45A fact model

## ✅ RESOLVED 2026-08-16 — `REC-05`

**Verdict: refinements, not regressions — plus two genuine defects, now corrected.**

Ratified as improvements: `cap_status` replacing `cap_exists` + `cap_type` (a boolean plus a status enum is two sources of truth, and a boolean cannot express `UNKNOWN`), and `NOT_APPLICABLE` replacing `—` (required by 45B.26's no-arbitrary-NULL rule).

Two defects found and corrected in revision **R1**:

1. `rule_configuration` appeared in the 45B.9 tree but was missing from the 45B.11 complete input — restored.
2. `extraction_diagnostics` was dropped from the input when 45A's field became 45B's `extraction_status` enum, leaving the evaluator able to see *that* extraction was `PARTIAL` but not *why* — restored alongside the enum.

`extraction_diagnostics` persistence was subsequently resolved by `REC-07`: **persisted** with the evaluation/evidence record, as diagnostic metadata that cannot independently produce or alter a legal finding.

Still open: the **shape of `rule_configuration`** (named in 45B.9 but never specified).

**Step 45B remains UNLOCKED** pending final review.

→ [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) § REVISION R1

### Original finding (retained for the record)

**Severity: MEDIUM — Step 45B is not locked, so this is resolvable by editing 45B before locking it.**

| Step 45A §3 | Step 45B.4 / 45B.7 |
|-------------|--------------------|
| `cap_exists` | *(no counterpart)* |
| `cap_type` | `cap_status` |
| `extraction_diagnostics` | `extraction_status` |

The enum values (`FINITE` / `UNLIMITED` / `ABSENT` / `UNKNOWN`) are unchanged; the field names are not. Additionally, `rule_configuration` appears in the 45B.9 Legal Rule tree but is omitted from the 45B.11 complete input structure.

Also: Step 45A's evaluation matrix shows `—` for rule outcome on `MATCH`/`MISSING`/`CONFLICT`, while Step 45B fills these with an explicit `NOT_APPLICABLE` value.

**To resolve:** reconcile field names during the "one final check" the source recommends before locking 45B.

Documented at: [LIABILITY.md](../04-analysis-engine/EDGE_CASES/LIABILITY.md), [LIABILITY_EVALUATOR_CONTRACT.md](../04-analysis-engine/EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md).

---

## C-05 — Stale status block inside Step 45A

**Severity: LOW — clerical.**

The status block inside Step 45A still reads `Step 45A — LIABILITY-001 / 🔒 READY TO LOCK`. The file's final status block reads `Step 45A 🔒 LOCKED` / `Step 45B ⏳ REVIEW`. The final block is later and supersedes it, but both remain in the file.

---

## C-06 — Two "Step 29" sections

**Severity: LOW**

The master specification contains two Step 29 headings — one plain, one tagged "(LOCKED)" — with overlapping but not identical content (draft/publish workflow vs. formal configuration-control rules). They appear complementary rather than contradictory, but only one is explicitly locked.

Documented at: [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md).

---

## C-07 — Superseded draft lists retained in the source

**Severity: LOW — recorded so nobody re-adopts the earlier draft.**

These are *not* true conflicts; the later document explicitly supersedes the earlier draft, and the docs tree reflects that. Listed for traceability:

* Step 3's draft permission groups → superseded by Step 23's locked role matrix ([USER_ROLES.md](../01-product/USER_ROLES.md)).
* Step 22's "Recommended V1 Review Statuses" → superseded by Step 30's locked review lifecycle ([WORKFLOWS.md](../01-product/WORKFLOWS.md)).

---

## C-08 — Reviewer role authority undefined

**Severity: LOW**

Step 3 lists `Reviewer` as a proposed role, while Step 4 explicitly leaves open "whether Reviewer can approve anything or only review/escalate." Step 23's locked matrix names a `Legal Reviewer` role. Whether the Step 4 open question was closed by Step 23 is not stated in the source.

---

## Provenance note — the master specification changed during documentation

While this documentation structure was being built, `all_lock.md` grew from 12,481 lines to 13,510 lines: Step 45A's lock was confirmed and Step 45B (Evaluator Data Contract) was added. The docs tree reflects the 13,510-line state. Any future session should re-check the tail of `all_lock.md` against [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) before assuming the docs are current.

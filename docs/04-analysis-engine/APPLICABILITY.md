# Applicability — what a document is measured against, and why

> **Status: 📁 DERIVED — the rule as built.** Locked in `AM-51` (and its same-day r2 correction),
> `AM-61`, `AM-60`, `AM-65`; indexed in [LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).
> Where this file and a lock record disagree, the record wins and the discrepancy is reported
> (rule 5). Written 2026-09-14; the rule had no prose home outside the lock records.

Implementation: `backend/legalmind/analysis/service.py::applicable_by_content`.

---

## The question this answers

A document arrives. The configuration snapshot pins every ratified Company Standard. Which of them
is *this* document measured against — and, just as importantly, what happens to the rest?

Getting it wrong has two failure modes, and both have been observed in this system:

* **Too narrow** — a position the document plainly contains is never measured, so the reader sees
  nothing at all. Silent, and worse than a wrong verdict because the screen does not say the topic
  was looked at.
* **Too wide** — every standard is asserted MISSING because the document did not contain it. On a
  real mixed document this produced 24 findings, most of them false, from three ordinary
  boilerplate clauses (`AM-51` r2', 2026-09-09).

---

## The rule

**The document type is one optional signal, never a gate** (`AM-51`). Every pinned Requirement is
mapped first; applicability is decided from what the mapping found.

A Requirement **applies** when any of three declared signals holds:

| Signal | Meaning | Why it is safe |
|---|---|---|
| **CONFIRMED** | the document contains its clause — lexically, or recognised on a verbatim span (`AM-54`/`AM-60`) | Content wins whatever family the standard belongs to. One document may span several legal domains; an NDA that carries a liability cap is measured against the liability standard. |
| **DECLARED** | the standard's family is the document's declared type | The one fact a human, or a confident intake suggestion (`AM-50`), actually asserted about the KIND of paper. |
| **EXPECTED** | the standard's own `constitution.expected_when.confirmed_any` names a Constitution sibling the document confirms | Written per standard from the Constitution's structure and reviewed as configuration — never inferred across topics. |

A Requirement none of these reaches is **NOT_APPLICABLE**, and is **recorded with its reason**, not
dropped (`AM-61` r2). "Not applicable" and "missing" are different facts and the product says which.

Two further rules:

* **`not_applicable_to`** — a standard may exclude document types. The two liability standards list
  SLA, which is how the owner's 2026-08-20 ruling (service credits are a remedy, not a cap) stays in
  force.
* **Retired standards never apply at all.** A retired Requirement is `DEPRECATED` and never enters a
  snapshot (`AM-65`), so it cannot be confirmed, expected or asserted missing.

---

## What may be MISSING

**Absence is asserted only for a Requirement that applies.** A standard outside every applicable
route whose clause is absent is not missing — it was never this document's question.

Family **detection is the declared type only** (`AM-51` r2'). It is deliberately *not* inferred from
confirmed clauses, and the reason is measured: Governing Law and a liability cap appear in nearly
every commercial contract, so "two confirmed standards detect a family" detected every family from
one ordinary document and flooded it with MISSING findings.

Semantic recognition never establishes absence (`AM-54` r10). Where the configured words confirmed
nothing and the model did, a quantity the text then fails to yield is **uncertainty**, not absence.

For a numeric Requirement that applies, a mapping of NONE — no clause scored at all — is established
absence and evaluates **MISSING with zero evidence** (45C.15), the same shape `PRESENCE` has always
reported. Before `AM-61` r4 it produced an evidence-free `UNABLE_TO_EVALUATE` that the cardinality
rule then refused to persist, so the finding vanished entirely.

---

## One Constitution position, measured once

Standards are per document type (owner Q3=B): the type names the standard's **family**. That means
several standards can state the *same* Constitution position — three `GOVLAW-*` standards fire on a
single governing-law clause.

`AM-61` r3 de-duplicates the **measurement**, not the standards. Two applied standards with the same
signature — same Constitution section and same value/unit/basis/scope, or same presence expectation
and scope — are evaluated once: the declared family's copy if there is one, else the first by code
(ENG-11). The others are recorded `SAME_POSITION` naming the one measured.

Standards in one section with *different* bases stay two positions. The MSA and NDA
confidentiality-survival standards measure different things and both run.

---

## What the run records

Every pinned Requirement leaves the analysis with one record:

```json
{"code": "CURE-PERIOD-MSA-001", "section": "13",
 "outcome": "NOT_APPLICABLE",
 "reason": "not confirmed in the document; not the declared family (OTHER); no Constitution sibling it names is confirmed"}
```

`outcome` is `APPLIED`, `NOT_APPLICABLE` or `SAME_POSITION`, and the reason is the engine's own
words. The list is written into the `ANALYSIS_RUN_RECORDED` audit event and read back into the
review report's `coverage`, where the Report shows **what was measured and what was not**.

`NOT_APPLICABLE` is a **coverage outcome, not a classification**. No fifth `FindingClassification`
was added (45B.26) and it is never rendered as MISSING or as a Finding. A clause on a topic the
Constitution has no position about is an **unmatched provision** (REC-02) — listed on the report for
a person to read, never judged.

---

## Worked example — a mixed agreement, no declared type

A document containing confidentiality, payment, renewal, purchase-order and tax clauses, uploaded
with no type:

| Requirement | Outcome | Why |
|---|---|---|
| `LIABILITY-MSA-001` | APPLIED → CONFLICT | the document confirms two incompatible caps in one scope |
| `LIABILITY-TOS-001` | SAME_POSITION | states the same §9 position as the MSA standard, measured once |
| `GOVLAW-MSA-001` | APPLIED → MATCH | the governing-law clause is confirmed |
| `ARBITRATION-MSA-001` | APPLIED → MISSING | expected: the document confirms §22 through `GOVLAW-MSA-001`, and has no arbitration clause |
| `CURE-PERIOD-MSA-001` | NOT_APPLICABLE | not confirmed, no type declared, no sibling confirmed |
| purchase-order clause | — | no ratified standard exists; surfaces as an unmatched provision |

The same document under a declared type of `MSA` adds that family's absences, and **only** that
family's. The content-recognised verdicts are identical under `OTHER`, `MSA` and no type at all —
asserted by `backend/tests/test_mixed_agreement.py`.

---

## Known limitations

* **A document declares one type.** For a genuinely hybrid agreement, present clauses of every
  family are measured, but absence is asserted only inside the one declared family.
* **`not_applicable_to` tests the declared type only.** On an untyped document the SLA/liability
  exclusion rests on the configured negative pattern instead.
* **`AM-51` r5 is not implemented** — a type set after analysis does not re-run it (C-21, mooted in
  practice by `AM-64`: the reader never selects a type).
* **The de-duplicated position uses the kept copy's own mapping**, not a union of evidence across
  the copies.

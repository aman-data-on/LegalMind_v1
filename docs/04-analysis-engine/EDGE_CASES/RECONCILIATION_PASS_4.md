# Reconciliation Pass 4 — N-24 → N-18 → N-19 → N-26

**Status: ⏳ PROPOSAL — NOTHING LOCKED.** `all_lock.md` unmodified (13,941 lines, md5 `66591e62`). No locked decision changed. No legal requirement invented.

Prepared 2026-08-16. Executes the recommended sequence from [../EVALUATOR_EDGE_CASES.md](../EVALUATOR_EDGE_CASES.md) (Step 45D).

Related: [RECONCILIATION_PASS_3.md](RECONCILIATION_PASS_3.md) · [RECONCILIATION_PASS_2.md](RECONCILIATION_PASS_2.md) · [LIABILITY_EVALUATOR_CONTRACT.md](LIABILITY_EVALUATOR_CONTRACT.md)

---

# 1. N-24 — Does V1 require more than one Requirement evaluator?

## The question splits in two, and only one is a product decision

| | Question | Answerable from locked text? |
|---|---|---|
| **N-24a** | Does V1 support **multiple** Requirements? | **YES — derivable** |
| **N-24b** | **Which specific** Requirements must V1 ship with? | **No — owner decision** |

Everything downstream (N-18, N-19, N-26) depends only on **N-24a**. N-24b can remain open without blocking anything.

## N-24a — the locked corpus already answers this

I treated this as a product decision in Pass 3. On searching the locked text, it is not: **three locked decisions structurally presuppose multiple Requirements.**

### Evidence 1 — Step 8 / LEGAL-05 (LOCKED)

> **Comparison = complete alignment report.** LegalMind must not show only problems. The user should understand: What matches · What differs · What is missing · What conflicts · **Which clauses were reviewed** · Evidence supporting the result

with the locked example:

```text
CONTRACT COMPARISON

Overall alignment: 82%

✓ Payment Terms          Aligned
✓ Confidentiality        Aligned
⚠ Limitation of Liability  Deviation
❌ Data Protection        Missing
✓ Termination            Aligned
```

A single-Requirement V1 cannot satisfy this locked decision. "Which clauses were reviewed" would be one row; "overall alignment" would be 0% or 100%; "what matches" and "what differs" could never appear together. **The locked product decision is not implementable with one Requirement.**

### Evidence 2 — Step 20 (LOCKED)

> LegalMind V1 will maintain a centralized **Clause Library**.

Locked rule 4: "**Not every Clause** requires a Pre-approved Legal Rule." Locked rule 11: "Used Clause Library entries are not physically deleted; they may be **deprecated**."

A rule distinguishing which entries need Legal Rules, and a deprecation lifecycle for entries, both presuppose a population. A library of one needs neither.

### Evidence 3 — Step 7 (LOCKED)

Clause-level comparison is locked as operating over a set:

```text
├── Payment Terms
├── Termination
├── Confidentiality
├── Limitation of Liability
├── Indemnification
└── Governing Law
```

### Conclusion

**N-24a: V1 supports multiple Requirements. This is derived from locked Steps 7, 8 and 20 — not a new decision.**

Note the consequence for the earlier reasoning: **N-19 option 4 ("accept the coupling; V1 is magnitude-only") is effectively dead.** Step 8's own locked example includes `Data Protection → Missing` (a presence-type evaluation) and Step 7 names Governing Law (a permitted-value comparison). A magnitude-only V1 cannot produce the locked example.

## N-24b — remains OPEN, and is not blocking

Which Requirements ship in V1 is a legal/product decision requiring legal input. Nothing in this pass depends on it. It should be answered before implementation planning, not before 45B/45C/45D.

⚠ **Second-order consequence, reported not resolved:** if V1 requires multiple Requirements (N-24a) but only `LIABILITY-001` is specified, then **V1 is not currently specifiable end-to-end** — the locked Step 8 alignment report cannot be produced from one Requirement. This does not change any locked decision; it means the specification backlog is larger than the 45-series implies. Recorded as **N-27**.

---

# 2. N-26 — `MULTI_CLAUSE` and `CONFLICT_DETECTION` are a category error

Resolved **before** N-18, because it determines the vocabulary.

## The problem

36.12 lists `MULTI_CLAUSE` and `CONFLICT_DETECTION` among recommended *evaluator types* — as if a Requirement could select whether it handles multiple clauses or detects conflicts. But locked rules make both **universal engine behavior**:

| Behavior | Locked as universal |
|---|---|
| Multiple clauses per Requirement | Step 28 r2 — "One Requirement may be supported by multiple clauses"; 45D.4.1 |
| Conflict detection | Step 44.18 (Layer 7, part of the pipeline every evaluation traverses); Step 36.5; 45C.2; 45D.4.5 |

If `CONFLICT_DETECTION` were a selectable type, a Requirement could opt out of conflict detection — which would contradict 45C.22 (no silent precedence) and 45D.4.5. Conflict detection is a **layer**, not an evaluator.

## Proposed resolution

`MULTI_CLAUSE` and `CONFLICT_DETECTION` are **not** evaluator types. They are engine behaviors every evaluator inherits. They are removed from the proposed vocabulary below.

36.12 is a **recommendation**, not locked, so removing them amends nothing.

---

# 3. N-18 — Proposed `EVALUATOR_TYPE` vocabulary

## The gap

`EVALUATOR_TYPE` is `NOT NULL` in three locked tables (`requirement_versions` 42.7, `evaluation_rule_versions` 42.11, `evaluations` 42.15) and defined nowhere. The only candidate list (36.12) is explicitly a recommendation.

## Proposed vocabulary

Derived from 36.12, minus the two category errors (N-26):

```text
EVALUATOR_TYPE

NUMERIC_COMPARISON    A magnitude compared against a threshold.
                      Exercised by LIABILITY-001.

RANGE_COMPARISON      A magnitude compared against a bounded range.

ALLOWED_VALUES        A value compared against a permitted set.

EXACT_MATCH           A value compared for identity against a single
                      configured value.

BOOLEAN_PRESENT       Satisfied when a qualifying provision exists.

BOOLEAN_ABSENT        Satisfied when no qualifying provision exists.

TEXT_PATTERN          A provision compared against configured
                      deterministic patterns.
```

**Semantics are code, parameters are configuration** — the type selects a tested Python comparison algorithm (44.29: "comparison semantics" is Python-controlled); its thresholds, permitted values and patterns are configuration.

## Open questions inside this proposal — not resolved

| ID | Question |
|---|---|
| **N-28** | `EXACT_MATCH` is `ALLOWED_VALUES` with a set of one. Is the redundancy justified by clearer configuration, or should it be merged? Fewer types means less tested comparison code (ENG-10) |
| **N-29** | `RANGE_COMPARISON` may be `NUMERIC_COMPARISON` with two thresholds. Same question |
| **N-30** | Is `TEXT_PATTERN` an *evaluator* or a *mapping* concern? Step 35 already locks pattern matching in the mapping layer; a pattern-based **evaluation** may blur locked ENG-03 (Mapping ≠ Evaluation) |

**N-30 is the substantive one.** If `TEXT_PATTERN` evaluation means "does the clause text match a pattern," that is close to what mapping already does, and locked ENG-03 keeps those engines separate.

---

# 4. N-19 — Removing liability vocabulary from the shared schema

With N-24a settled (multiple Requirements, not all magnitude-type), the coupling must be removed.

## Proposed resolution — generalize the discriminator, per-Requirement vocabulary

| AM-8 as drafted | Proposed | Rationale |
|---|---|---|
| `cap_kind CAP_KIND NOT NULL`<br>`GENERAL \| EXCEPTION` | `evaluation_kind EVALUATION_KIND NOT NULL`<br>`PRIMARY \| EXCEPTION` | The general-position-plus-carve-out shape **is** structural — see N-25 below. Only the word "cap" was liability-specific |
| `scope SCOPE NOT NULL`<br>`AGGREGATE \| PER_CLAIM \| PER_EVENT \| CATEGORY \| UNKNOWN` | `scope_key VARCHAR NOT NULL` | The *values* are liability-of-damages concepts. A global enum cannot hold every Requirement's sub-scope vocabulary |
| `scope_label VARCHAR NULL` | unchanged | Display text |

### Why `scope_key` is a validated string, not an enum

Each Requirement defines its own sub-scope vocabulary. That vocabulary **already has a home**: `rule_configuration.comparable_scopes` (J-5), which declares per-Requirement which scopes exist and which are comparable. So `scope_key` is validated against the Requirement's configuration at evaluation time, not against a global database enum.

This does **not** violate 42.1 r10 — the relationship is not hidden in JSON; it is an explicit column validated against versioned configuration, and the configuration is itself snapshot-captured for reproducibility (AUD-04).

`UNKNOWN` remains a reserved `scope_key` value, preserving 45C.20's fail-closed behavior.

### `LIABILITY-001` under the generalized model

Unchanged in substance — only the field names and the validation source move:

```text
scope_key = "AGGREGATE"    evaluation_kind = PRIMARY
scope_key = "CATEGORY"     evaluation_kind = EXCEPTION   scope_label = "confidentiality breach"
```

The liability vocabulary (`AGGREGATE`, `PER_CLAIM`, `PER_EVENT`, `CATEGORY`) becomes `LIABILITY-001`'s configured `comparable_scopes` — exactly where 45A §6 defined it, rather than in a shared enum.

## N-25 revisited — does the general/exception split generalize?

Pass 3 flagged that the only evidence for `PRIMARY | EXCEPTION` being structural was liability. Re-examined:

A general position qualified by carve-outs is a **drafting pattern**, not a liability concept — a governing-law clause with a carved-out arbitration forum, a confidentiality obligation excluding publicly-available information. It appears wherever contracts state a rule and then except from it.

**Assessment: the split does generalize.** But this is judgment from contract-drafting practice, not derivation from locked LegalMind text — so it stays a proposal, not a derivation. **N-25 remains open**, narrowed to: *is `PRIMARY | EXCEPTION` sufficient, or do some Requirements need a third kind?*

---

# 5. Revised amendment set

**AM-8 is superseded by AM-8′.** Proposed, not applied.

| ID | Item | Change |
|----|------|--------|
| **AM-8′** | 42.15 `evaluations` | `scope_key VARCHAR NOT NULL`, `scope_label VARCHAR NULL`, `evaluation_kind EVALUATION_KIND NOT NULL`, `rule_outcome RULE_OUTCOME NOT NULL` — **replaces** AM-8's `scope`/`cap_kind` |
| **AM-16** | 42.7 / 42.11 / 42.15 | Define `EVALUATOR_TYPE` (7 values, N-18) |
| **AM-17** | 45B.4 / 45B.11 | `facts.caps[]` retains liability field names — **correct per 44.11**; only the *persisted* discriminators generalize |
| **AM-9′** | 45B | `caps[].cap_kind` → maps to `evaluation_kind` on persistence; `caps[].scope` → `scope_key` |

**The boundary this establishes (addresses N-20):**

```text
Requirement-specific   →  the evaluator's fact model and input contract   (44.11, 45B)
Shared / structural    →  Finding, Evaluation, classification, rule outcome,
                          scope discriminator, evidence, decision            (42.14–42.17)
```

Liability field names live in the 45B contract. The shared tables carry only structural discriminators.

---

# 6. 45D readiness after this pass

| Item | Status |
|---|---|
| **45D.4.1–45D.4.11** (structural contract) | **Ready to propose for lock** — each traceable to a locked rule; no longer blocked by N-19 |
| **45D.4.12** (reproducibility) | **Still blocked** — N-12 (Legal Rule version), N-13 (evaluator version) |
| **Requirement Specification Template** | **Unblocked** — R.3 now has a candidate vocabulary (N-18), subject to N-28/N-29/N-30 |
| **45D as a whole** | **Not lockable** — N-27, N-30 and the N-12/N-13 pair remain open |

---

# 7. Blockers after this pass

### Resolved

| ID | Resolution |
|----|-----------|
| **N-24a** | **Derived from locked Steps 7, 8, 20** — V1 supports multiple Requirements |
| **N-26** | `MULTI_CLAUSE` / `CONFLICT_DETECTION` are engine behaviors, not evaluator types |
| **N-19** | Generalized via AM-8′ — liability vocabulary removed from shared schema |
| **N-20** | Requirement-specific / shared boundary stated above |
| **N-25** | Narrowed — `PRIMARY \| EXCEPTION` assessed as generalizing; residual question recorded |

### Newly opened

| ID | Issue | Class |
|----|-------|-------|
| **N-27** | **V1 is not currently specifiable end-to-end.** Locked Step 8 requires a multi-Requirement alignment report; only `LIABILITY-001` is specified | **CRITICAL** |
| **N-28** | `EXACT_MATCH` vs `ALLOWED_VALUES` redundancy | MEDIUM |
| **N-29** | `RANGE_COMPARISON` vs `NUMERIC_COMPARISON` redundancy | MEDIUM |
| **N-30** | Is `TEXT_PATTERN` evaluation or mapping? May blur locked ENG-03 | HIGH |

### Carried forward, unchanged

**CRITICAL:** N-11 (Step 44 vs 36 on `UNRESOLVED`) · N-12 (Legal Rule version unpersisted) · N-13 (`evaluator_version` unpersisted) · B-6 (45B amendments unapproved) · B-8 (`evaluation_evidence`) · B-15 / OD-9 (authentication)

**HIGH:** N-14 · N-15 · N-8 · N-9 · B-9 · B-10 · N-21 (45D scope discrepancy) · N-23

**MEDIUM:** N-16 · N-17 · N-22 · B-11 · B-12 · B-14 · OD-1 – OD-15 (external audit, all open)

---

# 8. What still requires an owner decision

Nothing in this pass was decided unilaterally. Outstanding:

1. **N-24b** — which Requirements ship in V1. Legal/product input; not blocking.
2. **N-27** — given N-24a, does the specification backlog now include further Requirement specifications before V1 can be called complete? **This is the most consequential open question in the project.**
3. **N-18 vocabulary** — approve the 7 values, and rule on N-28/N-29/N-30.
4. **AM-8′** — approve the generalized discriminators before 45B is re-locked.
5. **N-11** — still the blocker for 45C and for AM-7.

**Recommended next:** N-27, then N-30, then N-11.

N-27 first because it is a scope question that changes what "done" means. If locked Step 8 genuinely requires a multi-Requirement report, then V1 needs several Requirement specifications that do not yet exist — and that reshapes the plan far more than any schema amendment. N-30 next because it is cheap and gates the evaluator vocabulary. N-11 remains the standing blocker for 45C.

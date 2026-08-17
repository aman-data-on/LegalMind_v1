# Reconciliation Pass 5 — N-31 verification & full cross-step audit

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ ANALYSIS — NOTHING LOCKED. 45D NOT LOCKED.** `all_lock.md` unmodified (13,941 lines, md5 `66591e62`). No locked decision changed. No evaluator or legal Requirement invented. V1 not expanded.

Prepared 2026-08-17. Related: [V1_SCOPE_AUDIT.md](V1_SCOPE_AUDIT.md) · [RECONCILIATION_PASS_4.md](RECONCILIATION_PASS_4.md) · [../EVALUATOR_EDGE_CASES.md](../EVALUATOR_EDGE_CASES.md) · [../../02-legal-domain/DECISION_STATE_MODEL.md](../../02-legal-domain/DECISION_STATE_MODEL.md)

---

# 1. N-31 verification against Steps 7, 8, 20, 28, 36, 44, 45A–45D

**Interpretation under test:** "Aligned" in Step 8's illustrative example denotes a comparison/alignment result where a qualifying provision is present and aligned — it does **not** imply that each illustrative row requires an independent value-comparison evaluator.

**This is an interpretation of an illustrative example. It grants no permission to alter locked Step 8, and creates no legal policy.**

## 1.1 Step-by-step check

| Step | Locked text tested | Result |
|---|---|---|
| **7** | Comparison is clause/requirement-level; outcomes `MATCH`/`DEVIATION`/`CONFLICT`/`MISSING`; "The detailed matching rules remain a later decision" | ✅ **No contradiction.** Step 7 explicitly defers matching rules. Presence-mode yields `MATCH`/`MISSING` from that set |
| **8** | Locked decision: complete alignment report — what matches, differs, is missing, conflicts; which clauses were reviewed; evidence | ✅ **No contradiction.** The locked decision constrains *what the report shows*, never *how each Requirement is compared*. Presence-mode supplies matches and missings |
| **20** | "The Company Standard is the organization's default/preferred position. A provision matching it is a `MATCH`." Rule 4: not every Clause requires a Pre-approved Legal Rule | ⚠ **Compatible, with a residual ambiguity** — see R-1. Rule 4 actively supports presence-mode: such a Requirement may have a Standard and no Legal Rule |
| **28** | Rule 5: "A required Requirement with no mapped provision **may** produce a `MISSING` Finding" | ✅ **Actively supports.** `MISSING` arises from mapping absence — no evaluator required |
| **36** | 36.2 "`MATCH` — Customer provision conforms to the Company Standard"; 36.11 "different legal requirements need different evaluation algorithms" | ✅ **Actively supports.** 36.11 is the locked rule that *requires* a second algorithm; presence-mode is one. 36.2 holds provided R-1 is resolved |
| **44** | 44.33 explainability: `Evidence → Fact → Standard → Rule → Result` | ✅ **Chain intact.** Evidence = the mapped clause; Fact = a qualifying provision exists; Standard = presence required; Rule = configured or `NOT_APPLICABLE`; Result = `MATCH` |
| **45A** | `LIABILITY-001` policy | ✅ **Unaffected.** Wholly liability-specific; presence-mode neither extends nor narrows it |
| **45B** | Evaluator data contract | ✅ **Unaffected as a contract** — 45B is `LIABILITY-001`-specific per locked 44.11. A presence evaluator needs its own small fact model |
| **45C** | Liability edge cases | ✅ **Unaffected.** Presence-mode inherits the structural rules, not the liability ones |
| **45D** | 45D.4.8 "Absence is not a position" | ✅ **Consistent** — absence yields `MISSING` and never manufactures a substantive position |

## 1.2 Verdict

**The interpretation contradicts no locked rule.** Two locked rules actively support it (Step 28 r5, Step 36.11) and one (Step 7) explicitly defers the matching rules that would otherwise govern.

## 1.3 Residual ambiguities — explicitly identified, not resolved

### R-1 · May a Company Standard express presence rather than a value?

Step 20 defines the Company Standard as "the organization's default/preferred **position**." Whether "a qualifying provision must exist" constitutes a position is **not locked**. Presence-mode `MATCH` depends on it: 36.2 requires conformance *to the Company Standard*, so a presence `MATCH` needs a presence Standard.

**Not resolved here.** If the answer is no, presence-mode cannot emit `MATCH` and can only contribute `MISSING` — which would leave Step 8's "Aligned" rows unproducible and reopen N-27. **This is now the load-bearing question, inherited from N-31.**

### R-2 · Is "Aligned" in the example equivalent to `MATCH`?

The example predates the locked classification vocabulary (Step 8 precedes Steps 18/27/36). "Aligned" appears nowhere in any locked enum. Treating it as `MATCH` is the natural reading but is an inference about illustrative text.

### R-3 · How is "Overall alignment" computed?

See N-33 below. The example shows "82%", and Step 9's **locked prose** lists "Overall alignment" as a report element — but no locked rule defines the calculation.

**None of R-1, R-2, R-3 is converted into legal policy by this pass.**

---

# 2. Fully resolved

| ID | Resolution | Basis |
|----|-----------|-------|
| **N-11** | Analytical `Classification.UNRESOLVED` and workflow unresolvedness are **distinct axes**. No amendment to 44.22 — its own closing sentence says "This is different from the analytical classification." AM-7 proceeds. Recorded via the existing axis-separation principle (REC-06) | 44.22, 36.7, REC-06 |
| **N-30** | `TEXT_PATTERN` removed from evaluator vocabulary. Mapping (35.4, 35.5, 35.10) and extraction (44.16) retain their locked pattern mechanisms. No duplicate created | 44.33, ENG-03 |
| **N-26** | `MULTI_CLAUSE`, `CONFLICT_DETECTION` are engine behaviors, not evaluator types | Step 28 r2, 44.18 |
| **N-27** | Minimum V1 coverage = `LIABILITY-001` + one generic presence-mode evaluator + configured Requirements. No additional legal-domain evaluator is compelled by any locked decision | Steps 8, 20, 21, 28, 29, 35.10, 36.11, 44.29 |
| **N-24a** | V1 supports multiple Requirements | Steps 7, 8, 20 |
| **N-19 / N-20** | Liability vocabulary removed from shared schema via AM-8′; Requirement-specific vs shared boundary stated | 44.11, 42.1 r10 |
| **N-25** | `PRIMARY \| EXCEPTION` assessed as generalizing | Contract-drafting practice; flagged as judgment |
| **N-31** | Verified above — no locked contradiction; three residual ambiguities recorded | §1 |

---

# 3. Open

| ID | Item | Class |
|----|------|-------|
| **R-1** | May a Company Standard express presence? **Load-bearing for N-27** | **CRITICAL** |
| **N-24b** | Which Requirements ship in V1 | OPEN by direction — do not invent |
| **N-18** | 6-value vocabulary — proceeds to detailed review, not locked | Pending audit completion |
| **N-28 / N-29** | `EXACT_MATCH` vs `ALLOWED_VALUES`; `RANGE_` vs `NUMERIC_` redundancy | MEDIUM |
| **R-2 / R-3** | "Aligned" ≡ `MATCH`?; alignment calculation | MEDIUM |
| **N-32** | Risk classification rules | HIGH |
| **N-33** | "Overall alignment" calculation | MEDIUM |
| **N-34** | Evidence cardinality for absent provisions | **HIGH — defect in the proposal** |

---

# 4. Genuine contradictions

## 4.1 In locked text

**None newly found in this pass.** Two apparent ones were tested and dissolved:

* **Step 9 "High-level risk" vs 36.10 "No generic risk score."** 36.10's wording is precise: it forbids `Risk = 83%` or `Low/Medium/High` **"as the primary V1 legal output."** Step 27 r12 permits risk that is "configuration-driven and not hard-coded solely from Finding type." A configuration-driven, secondary risk indicator satisfies both. **Not a contradiction — but see N-32, the rules are unspecified.**
* **Step 44.22 vs Step 36.7** — dissolved in §2 (N-11).

## 4.2 In the proposal set (mine, not locked)

### N-34 · Evidence cardinality contradiction — **must be corrected before 45B re-lock**

My own evaluator audit (Pass 3 §5) specified `evidence_refs[]` as **"≥1"** for every Evaluation. That is wrong, and presence-mode exposes it:

| Case | Locked source | Evidence available |
|---|---|---|
| Provision exists but carries no qualifying value → `MISSING` | 45C.14 | **Yes** — "The evidence showing the liability provision should still be retained" |
| No qualifying provision at all → `MISSING` | 45C.15 | **None exists** |

Combined with **EV-MIN** (every Finding has ≥1 Evaluation), a wholly-absent Requirement yields an Evaluation with **zero** evidence references. My "≥1" constraint would make locked 45C.15 unrepresentable.

**No locked rule is violated** — 45B.18 and 45C.25 require evidence *that exists* to survive; none existed. **The defect is in the proposal.**

**Correction (proposed):** `evidence_refs[]` is required and non-empty **for every Evaluation whose classification is based on an identified provision**; it is permitted to be empty **only** where the classification is `MISSING` arising from established absence. Never empty for `MATCH`, `DEVIATION`, `CONFLICT`, or `AMBIGUOUS`.

---

# 5. Implementation blockers

| ID | Blocker | Class |
|----|---------|-------|
| **R-1** | Presence-type Company Standard permitted? Gates the entire N-27 resolution | **CRITICAL** |
| **N-12** | Legal Rule version not persisted — Step 32 audit question 4 unanswerable | **CRITICAL** |
| **N-13** | `evaluator_version` not persisted — locked 45B.10 | **CRITICAL** |
| **B-6** | 45B amendments (AM-1, AM-8′, AM-9′–AM-17) unapproved | **CRITICAL** |
| **B-8** | `evaluation_evidence` junction | **CRITICAL** |
| **B-15 / OD-9** | Authentication unspecified | **CRITICAL** (independent) |
| **N-34** | Evidence cardinality correction | HIGH |
| **N-32** | Risk classification rules — locked report element, `all_lock.md`'s own "Not Yet Locked" list | HIGH |
| **N-14 / N-15** | `extraction_diagnostics` unpersisted; `justification NOT NULL` | HIGH |
| **N-1 / N-3** | Decision versioning; canonical decision schema | HIGH (resolved as proposals, unapproved) |
| **N-8 / N-9 / B-9 / B-10** | Widen-only rule; EV-MIN mechanism; approval and escalation levels | HIGH |
| **N-33** | "Overall alignment" calculation | MEDIUM |
| **N-16 / N-17 / N-21 / N-22 / N-23** | Std version per Evaluation; 45C.22 narrowing; 45D scope discrepancy; template; untested types | MEDIUM |
| **B-11 / B-12 / B-14** | Mapping bands; `UNMATCHED_PROVISION`; Step 33 | MEDIUM |
| **OD-1 – OD-15** | External-audit security decisions | Mixed |

---

# 6. Final minimum V1 evaluator scope

**Subject to R-1.**

```text
REQUIRED

1. LIABILITY-001                  NUMERIC_COMPARISON
   Status: specified (45A 🔒, 45B 🔒 pending amendment)

2. One generic presence-mode evaluator      BOOLEAN_PRESENT
   Status: NOT SPECIFIED — the single remaining evaluator specification
   Needs no Requirement-specific fact extraction; presence is
   established by the locked mapping layer (Step 28 r5, 35.10)

3. A configured set of Requirements
   Status: CONFIGURATION, not specification (Steps 21, 29, 35.10)

NOT REQUIRED — no locked decision compels any of these
   Payment Terms · Termination · Confidentiality · Indemnification
   Governing Law · Data Protection · Notice Period
   All appear in illustrative examples only.
```

**Evaluator vocabulary under review (6 values, not locked):**
`NUMERIC_COMPARISON` · `RANGE_COMPARISON` · `ALLOWED_VALUES` · `EXACT_MATCH` · `BOOLEAN_PRESENT` · `BOOLEAN_ABSENT`

Of these, V1 exercises **two**: `NUMERIC_COMPARISON` and `BOOLEAN_PRESENT`. The other four are vocabulary for configured future Requirements and require no V1 specification.

---

# 7. What 45D must specify before it can lock

| # | Item | Status |
|---|------|--------|
| 1 | **45D.4.1 – 45D.4.11** structural evaluator contract | Drafted; ready subject to N-34 correction |
| 2 | **45D.4.12** reproducibility | **Blocked** — N-12, N-13 |
| 3 | **Evidence cardinality rule** | **Missing** — N-34 correction must be written in |
| 4 | **`EVALUATOR_TYPE` vocabulary** | 6 values, pending detailed review (N-18, N-28, N-29) |
| 5 | **Requirement Specification Template** (R.1–R.17) | Drafted; R.3 depends on item 4 |
| 6 | **Requirement-specific vs shared boundary** | Drafted (N-20) |
| 7 | **Presence-mode evaluator specification** | **Not written** — the one remaining evaluator spec |
| 8 | **Scope-key rule for single-scope Requirements** | **Missing** — AM-8′ makes `scope_key NOT NULL`; a presence Requirement has one scope and needs a defined value |

Items 3, 7 and 8 are new work identified by this pass.

---

# 8. What moves out of 45D

"Step 46" does not exist in `all_lock.md`; this is a proposed boundary, not a step definition.

| Moves out | Destination | Why |
|---|---|---|
| Liability golden test cases | Golden-corpus step | Displaced by the 45D scope change (N-21); still blocked by B-6/B-8/N-12/N-13 |
| Presence-mode golden cases | Golden-corpus step | Follows item 7 above |
| **Risk classification rules (N-32)** | Its own step | Locked report element; listed in `all_lock.md`'s own "Not Yet Locked". **Not an evaluator concern** — 36.10 keeps it out of the legal output path |
| **"Overall alignment" calculation (N-33)** | Reporting step | Step 9 report element, not an evaluator concern |
| Which Requirements ship (N-24b) | Product/legal decision | Deliberately OPEN |
| Schema repairs N-12, N-13, N-14, N-15, N-1, N-3, B-8 | Schema reconciliation | Cross-cutting; blocks 45B re-lock, not 45D's content |
| Security, API, frontend, observability, testing, deployment | Independent track | OD-1 – OD-15 |

---

# 9. New findings this pass

| ID | Finding | Class |
|----|---------|-------|
| **R-1** | Whether a Company Standard may express presence rather than a value — inherited from N-31 and now load-bearing for N-27 | **CRITICAL** |
| **N-32** | **Risk classification rules unspecified.** "High-level risk" is a locked Step 9 report element and Step 1 lists risk classification as a V1 capability, but rules are in `all_lock.md`'s own "Not Yet Locked" list. 36.10 constrains it (never the primary legal output) and Step 27 r12 requires it be configuration-driven — but nothing defines it | HIGH |
| **N-33** | **"Overall alignment" calculation unspecified.** Locked Step 9 report element; "82%" appears only in an illustrative example | MEDIUM |
| **N-34** | **Evidence-cardinality contradiction in the proposal** — "≥1 evidence_refs" would make locked 45C.15 unrepresentable | HIGH |
| **R-2 / R-3** | "Aligned" ≡ `MATCH`?; alignment calculation | MEDIUM |

### Second-order dependency check

**N-34 affects:** the 45B output contract, 45D.4.10, `evaluation_evidence` (B-8) cardinality, golden cases 9 and 11, and the reviewer UI's evidence panel (must render an evidence-free `MISSING`). **Does not affect** J-3 decisions, N-1 versioning, the roll-up derivation, or authorization.

**R-1 affects:** N-27's entire resolution, the presence-mode evaluator specification, Step 8 report producibility, and the `company_standard` block in the 45B-derived contract (A-2 added `scope`; a presence Standard may need a *kind*). **This is the widest-reaching open item in the current set.**

---

# 10. Presented for review

| ID | Question | My position |
|----|----------|-------------|
| **R-1** | May a Company Standard express "a qualifying provision must be present" rather than a value? | **Presented, not recommended.** It determines whether presence-mode can emit `MATCH`, and therefore whether N-27's resolution holds. Step 20 r4 (not every Clause needs a Legal Rule) leans permissive, but "position" is undefined. **This is a legal-domain question** |
| **N-34** | Evidence cardinality correction | Recommend adopting §4.2's wording |
| **N-32** | Where do risk classification rules belong? | Recommend a dedicated step, outside the evaluator track |
| **N-33** | Alignment calculation | Recommend the reporting step |

**R-1 first.** Everything approved in this round about V1 scope rests on it, and unlike the others it cannot be settled by reading the locked corpus — the corpus does not address it.

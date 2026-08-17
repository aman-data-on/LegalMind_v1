# Step 45D — Cross-Evaluator Edge Cases

**Status: 🔒 LOCKED (2026-08-17).** Lock record in [`all_lock.md`](../../all_lock.md) under "Step 45D — LOCK RECORD". **No legal requirement invented** — 45D specifies evaluator-agnostic behavior only.

Prepared 2026-08-16. Related: [EDGE_CASES/LIABILITY.md](EDGE_CASES/LIABILITY.md) (45A 🔒) · [EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md](EDGE_CASES/LIABILITY_EVALUATOR_CONTRACT.md) (45B 🔒) · [EDGE_CASES/LIABILITY_EDGE_CASES.md](EDGE_CASES/LIABILITY_EDGE_CASES.md) (45C 🔒) · [EDGE_CASES/RECONCILIATION_PASS_3.md](EDGE_CASES/RECONCILIATION_PASS_3.md) · [ANALYSIS_ENGINE.md](ANALYSIS_ENGINE.md)

---

# 45D.0 — Scope, resolved

`all_lock.md` (45C.26) originally anticipated 45D as "Liability Golden Test Cases." 45D was redefined as **Cross-Evaluator Edge Cases**, and the golden-test work became **Step 45E — Golden Corpus**, covering liability and presence together. Resolved as F-7; see [../00-project/DECISION_FINALIZATION.md](../00-project/DECISION_FINALIZATION.md).

---

# 45D.1 Purpose and hard scope boundary

## What 45D is

Step 45D specifies the **evaluator-agnostic** behavior every Requirement evaluator must exhibit — the structural contract that `LIABILITY-001` happened to be the first instance of. Its inputs are Steps 44, 45A, 45B and 45C, generalized.

## What 45D is NOT

**45D specifies no new legal requirement.** Termination, Indemnification, Governing Law and every other Requirement remain **NOT YET SPECIFIED**, exactly as recorded in the docs tree. Nothing here creates a legal rule, threshold, tolerance, carve-out, or Company Standard for any of them.

This is a hard constraint, not a stylistic choice:

* [CLAUDE.md](../../CLAUDE.md) rule 7 — never invent legal requirements.
* Step 37's V1 scope freeze lists *capabilities* but **never enumerates which Requirements V1 must support**. No locked decision obliges LegalMind to specify any legal-domain Requirement beyond `LIABILITY-001`, and none authorizes inventing one. Which Requirements ship is configuration (N-24b, open by direction).

Where this document needs a non-liability example to test whether a contract generalizes, it uses an explicitly labelled **structural probe** — an abstract shape used to test the *contract*, carrying no legal content and asserting no rule.

---

# 45D.2 The structural / domain distinction

Every edge case falls into exactly one class. The discriminating test:

> **Does correct handling depend on the legal content of a specific Requirement?**
> **No →** structural. Belongs to the engine, applies to every evaluator, specifiable now.
> **Yes →** domain. Belongs to that Requirement's own specification step, and must not be written here.

| | Structural | Domain |
|---|---|---|
| Owner | Analysis engine (Steps 44, 45D) | Per-Requirement step (45A-style) |
| Example | "Multiple values may map to one Requirement and must not be silently reduced to one" | "Six months is the Company Standard" |
| Example | "A value whose unit cannot be established fails closed" | "Months and currency are the permitted units" |
| Specifiable today | **Yes** | **No — requires legal input** |

---

# 45D.3 Generalization audit of 45C

Every 45C rule classified. This is the substantive work of 45D: separating what LegalMind learned about *evaluation* from what it decided about *liability*.

| 45C | Subject | Class | Generalized form (structural) or reason it is domain |
|---|---|---|---|
| 45C.1 | Multiple caps | **STRUCTURAL** | A Requirement may be governed by multiple provisions covering different sub-scopes; differing values across different scopes are not, by themselves, a conflict |
| 45C.2 | Same scope, different caps | **STRUCTURAL** | Two provisions governing the *same* scope with incompatible values produce `CONFLICT` unless deterministic precedence resolves it; all evidence retained |
| 45C.3 | General + carve-out | **STRUCTURAL** | A general position and its exceptions are represented and evaluated separately; an exception is not a conflict |
| 45C.4 | Unlimited carve-out | **STRUCTURAL** | An exception's position applies **only** to that exception's scope and never generalizes to the whole provision |
| 45C.5 | Per-claim vs aggregate | **MIXED** | *Structural:* values in incomparable scopes must not be compared. *Domain:* which scopes exist, and which are comparable, is per-Requirement |
| 45C.6 | Per-event vs aggregate | **MIXED** | Same as 45C.5 |
| 45C.7 | Different bases | **MIXED** | *Structural:* incomparable measurement bases must not be silently equated. *Domain:* the basis vocabulary |
| 45C.8 | Fixed amount vs fee-based | **MIXED** | *Structural:* no conversion without a configured rule and its required inputs → `UNABLE_TO_EVALUATE`. *Domain:* which conversions are permitted |
| 45C.9 | Percentage cap | **MIXED** | Same as 45C.8 |
| 45C.10 | Cross-reference | **STRUCTURAL** | Resolve only when deterministic; never invent the referent; unresolvable → fail closed |
| 45C.11 | Conflicting cross-references | **STRUCTURAL** | Competing chains for the same scope → `CONFLICT`; both chains traceable |
| 45C.12 | Negative wording | **STRUCTURAL** | Requirement-adjacent vocabulary must not cause a false-positive extraction; negative and exception patterns are first-class |
| 45C.13 | Ambiguous wording | **STRUCTURAL** | Language that does not establish a determinate position is never resolved into one |
| 45C.14 | Provision exists, no qualifying value | **STRUCTURAL** | A present-but-non-qualifying provision → `MISSING` where the Requirement demands the value, **with the provision's evidence retained** |
| 45C.15 | Wholly absent | **STRUCTURAL** | Absence → `MISSING`; absence never manufactures a substantive position |
| 45C.16 | Referencing clause | **STRUCTURAL** | A provision that merely references another does not create a second evaluation |
| 45C.17 | Repeated identical provision | **STRUCTURAL** | Materially identical applicable provisions → one evaluation, multiple evidence references |
| 45C.18 | OCR corruption | **STRUCTURAL** | Normalize only when deterministic; otherwise fail closed |
| 45C.19 | Missing unit | **MIXED** | *Structural:* a bare quantity without its qualifier is insufficient. *Domain:* the unit vocabulary |
| 45C.20 | Missing scope | **MIXED** | *Structural:* where scope is necessary for comparison and undeterminable → fail closed. *Domain:* whether scope is necessary |
| 45C.21 | Decision matrix | **DOMAIN** | Thresholds and outcomes are liability-specific |
| 45C.22 | No silent precedence | **STRUCTURAL** | **Universal.** No positional, ordinal or source-based precedence heuristic, ever |
| 45C.23 | No conversion without evidence | **STRUCTURAL** | **Universal** |
| 45C.24 | Scope first | **STRUCTURAL** | **Universal:** establish what a value applies to before treating it as the legal position |
| 45C.25 | Evidence survives every branch | **STRUCTURAL** | **Universal** |

**Result: 15 fully structural, 6 mixed, 1 fully domain.** The great majority of 45C describes the engine, not liability — which is why 45D can be specified now while Termination cannot.

---

# 45D.4 The structural evaluator contract

**Status: 🔒 LOCKED.** Every Requirement evaluator must satisfy these. `LIABILITY-001` already does; each is traceable to a locked rule.

### 45D.4.1 — Multiplicity
A Requirement may be governed by more than one provision. The evaluator produces one Evaluation Result per distinct governed scope. Multiple provisions covering the same scope are one Evaluation with multiple evidence references, or `CONFLICT` where incompatible. *(45C.1, 45C.2, 45C.16, 45C.17; A-4)*

### 45D.4.2 — Scope precedes value
No extracted value may be treated as a legal position before what it applies to is established. Where a Requirement's comparison is scope-sensitive and scope is undeterminable, the evaluator fails closed. *(45C.24, 45C.20)*

### 45D.4.3 — General position and exceptions are separate
An exception's position applies only within the exception's own scope, never to the general position. Exceptions are never discarded. *(45C.3, 45C.4; 45A r16)*

### 45D.4.4 — No silent commensurability
Values expressed in different units, bases or scopes are not equated unless a configured deterministic conversion rule and its required inputs both exist. Otherwise `UNABLE_TO_EVALUATE`. *(45C.7–45C.9, 45C.23)*

### 45D.4.5 — No silent precedence
No positional, ordinal, source-based or confidence-based heuristic may resolve competing provisions. Only explicitly configured deterministic precedence applies. Otherwise `CONFLICT`. *(45C.22, B-5/D-5.1–D-5.3)*

### 45D.4.6 — Deterministic cross-reference only
Cross-references are preserved always and resolved only when deterministic. The engine never infers a referent's content. *(45C.10, 45C.11; Step 28 r3–r4)*

### 45D.4.7 — Negative and exception patterns are first-class
Requirement-adjacent vocabulary must not produce a false-positive extraction. *(45C.12; 44.16)*

### 45D.4.8 — Absence is not a position
Absence yields `MISSING`; it never manufactures a substantive legal position. A present-but-non-qualifying provision still yields its evidence. *(45C.14, 45C.15)*

### 45D.4.9 — Fail closed on unreliable input
Extraction failure, unresolvable ambiguity or unreliable evidence yields `UNABLE_TO_EVALUATE` or the appropriate uncertainty state — never a guess. *(45C.18, 45C.19, 45B.7; ENG-09)*

### 45D.4.10 — Evidence survives every branch *(revised — N-34 approved)*
Every outcome, including failures, retains its supporting evidence at the scope granularity that produced it.

**Cardinality rule:** evidence references are preserved **whenever evidence exists**. `MATCH`, `DEVIATION`, `CONFLICT` and `AMBIGUOUS` evaluations must not carry empty evidence references where supporting evidence exists. `MISSING` arising from **established absence** may legitimately carry **zero** references. **No synthetic evidence may be created solely to satisfy a database or API cardinality rule.**

This supersedes the "≥1 evidence_refs" constraint stated in earlier passes, which would have made locked 45C.15 unrepresentable. Note the distinction 45C.14 vs 45C.15: a provision that exists but carries no qualifying value yields `MISSING` **with** evidence; a wholly absent provision yields `MISSING` **without**.

*(45C.14, 45C.15, 45C.25, 45B.18, EV-MIN; requires `evaluation_evidence` permitting zero rows — B-8, N-37)*

### 45D.4.11 — The evaluator produces no Legal Decision
Universal and already locked. *(36.15, 45A r18, 45B.14)*

### 45D.4.12 — Reproducibility
Every Evaluation retains its evaluator version, configuration versions, extracted facts and evidence. *(45B.10, ENG-11 — **currently unrepresentable, N-12/N-13**)*

---

# 45D.4bis Approved decisions incorporated

Owner-approved 2026-08-17. Recorded here; **not locked**.

| ID | Decision | Effect on 45D |
|----|----------|---------------|
| **R-1** | A Company Standard may express that a qualifying provision must exist. Present → `MATCH`; absent → `MISSING`; absence may legitimately carry zero evidence. Not a general legal-policy rule | Enables the presence evaluator; requires `standard_kind` (AM-18) |
| **N-34** | Evidence cardinality corrected — see 45D.4.10 above | Corrects a defect in earlier passes |
| **N-11** | Analytical classification and workflow status are distinct axes; no amendment to 44.22; AM-7 proceeds | Recorded in [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) terms |
| **N-30** | `TEXT_PATTERN` removed from the evaluator vocabulary; mapping and extraction retain their locked pattern mechanisms | Vocabulary reduces to 6 (45D.5) |
| **N-27** | V1 minimum coverage = `LIABILITY-001` + one generic presence-mode evaluator + configured Requirements | Scope settled |
| **N-24b** | Which Requirements ship in V1 stays **OPEN**; no legal Requirement invented from examples | No change |
| **N-32** | Risk classification stays **out** of the evaluator specification | Moved out of 45D |
| **N-33** | Overall alignment is a reporting/aggregation concern | Moved out of 45D |

**Presence-mode evaluator specification: [EDGE_CASES/PRESENCE_EVALUATOR.md](EDGE_CASES/PRESENCE_EVALUATOR.md).**

---

# 45D.5 The evaluator-type taxonomy — a locked enum with no definition

## The gap

`EVALUATOR_TYPE` is declared **`NOT NULL`** in **three locked tables**:

```text
requirement_versions.evaluator_type        EVALUATOR_TYPE NOT NULL   (42.7)
evaluation_rule_versions.evaluator_type    EVALUATOR_TYPE NOT NULL   (42.11)
evaluations.evaluator_type                 EVALUATOR_TYPE NOT NULL   (42.15)
```

**Its values are defined nowhere in `all_lock.md`.** The only candidate vocabulary is 36.12, which is explicitly a *recommendation* — "I recommend supporting a controlled set of evaluator types, **such as**":

```text
EXACT_MATCH · ALLOWED_VALUES · NUMERIC_COMPARISON · RANGE_COMPARISON
BOOLEAN_PRESENT · BOOLEAN_ABSENT · TEXT_PATTERN · MULTI_CLAUSE · CONFLICT_DETECTION
```

This is the same species of defect as `FINDING_STATUS` (J-4) and the missing `evaluator_version` column (N-13): **a locked schema referencing an undefined vocabulary.** Recorded as **N-18**.

## Why it matters specifically for 45D

Of the nine recommended types, **`LIABILITY-001` exercises exactly one** — `NUMERIC_COMPARISON` (45A §5, 45B.15, 36.13). Eight have never been exercised by any specification. Every structural conclusion in 45A–45C was therefore derived from a single evaluator type, and 45D is the first opportunity to ask whether those conclusions generalize. Recorded as **N-23**.

---

# 45D.6 Liability semantics leaking into the shared schema

**This is the most consequential finding in 45D.**

## The problem

Amendment **AM-8** (from the J-series) proposes adding to the **shared** `evaluations` table:

```text
evaluations.scope        SCOPE NOT NULL         ← AGGREGATE | PER_CLAIM | PER_EVENT | CATEGORY | UNKNOWN
evaluations.scope_label  VARCHAR NULL
evaluations.cap_kind     CAP_KIND NOT NULL      ← GENERAL | EXCEPTION
```

`evaluations` is **not** a liability table. It holds the output of *every* evaluator for *every* Requirement. But:

* **`cap_kind`** names a *cap*. Only requirements that limit a quantity have caps.
* **`SCOPE`**'s values — `AGGREGATE`, `PER_CLAIM`, `PER_EVENT` — are liability-of-damages concepts. They come from 45A §6, a liability-specific enumeration.

Making both `NOT NULL` on the shared table forces **every future evaluator to supply liability-shaped values it has no meaning for.**

## Structural probe

*The following is a probe of the contract's generality. It carries no legal content and specifies no Requirement.*

Consider any Requirement evaluated by `ALLOWED_VALUES` — a permitted-set comparison rather than a magnitude comparison. Such an evaluator produces a value drawn from a set. It has:

* no cap, therefore no `cap_kind`;
* no aggregate/per-claim distinction, therefore no `SCOPE` value.

Under AM-8 as drafted, its Evaluation rows could not be written without inventing placeholder values — precisely the "arbitrary NULL semantics" that locked **45B.26** forbids, in enum form.

The same probe applied to `BOOLEAN_PRESENT` (does a qualifying provision exist at all?) gives the same result.

## Why this happened

Locked **44.11** states fact extraction *should* be Requirement-specific, and 45B is correctly a **`LIABILITY-001`-specific** contract. The error is not in 45B. It is that the J-series carried liability-specific field names outward into the **shared persistence layer** while generalizing cardinality. Cardinality (A-4) generalizes; vocabulary (A-1, A-3) does not.

## Options — none selected

| # | Option | Note |
|---|---|---|
| 1 | **Generalize the names.** `cap_kind` → `evaluation_kind` (`PRIMARY` \| `EXCEPTION`); `scope` → a Requirement-defined discriminator | The general/exception split does appear structural (45D.4.3); the liability *scope values* do not |
| 2 | **Make them nullable** and applicable only to magnitude-type evaluators | Collides with 45B.26's no-arbitrary-NULL rule unless "not applicable" is made explicit |
| 3 | **Move them out of `evaluations`** into a per-evaluator detail table or the existing `result` JSONB | JSONB collides with 42.1 r10 (no hiding core relationships); a detail table adds a join |
| 4 | **Accept the coupling** and declare V1 supports only magnitude-type evaluators | Honest and cheap, but forecloses `ALLOWED_VALUES`/`BOOLEAN_*` Requirements without a further amendment |

Recorded as **N-19**. **This should be resolved before 45B is re-locked**, because AM-8 is part of that re-lock.

---

# 45D.7 Requirement Specification Template

**Status: PROPOSED.** Derived by observing what 45A/45B/45C actually contain — process, not legal content. No future Requirement may be considered specified until every section is answered or explicitly marked NOT APPLICABLE.

```text
R.1   Requirement identity          code, name, document types, required/optional
R.2   What the evaluator determines the question, in one sentence
R.3   Evaluator type                from the EVALUATOR_TYPE vocabulary (blocked by N-18)
R.4   Structured fact model         requirement-specific fields, types, allowed values (44.11)
R.5   Sub-scopes                    do multiple governed scopes exist? are they comparable?
R.6   Units / bases / measures      vocabulary, and which are mutually comparable
R.7   Exceptions and carve-outs     may an exception carry its own position?
R.8   Company Standard              the organization's position, and its scope
R.9   Legal Rule outcomes           thresholds → ACCEPTABLE / APPROVAL_REQUIRED / UNACCEPTABLE
R.10  rule_configuration            scope_required, comparable_scopes, comparable_bases,
                                    exception_handling, precedence_rules, conversion_rules (J-5)
R.11  Positive / negative / exception patterns
R.12  Cross-reference behavior      what may be deterministically resolved
R.13  Worked example per outcome    every classification and rule outcome (45B.19–45B.25 style)
R.14  Conflict conditions           what constitutes same-scope incompatibility
R.15  Ambiguity and failure         what yields AMBIGUOUS / UNRESOLVED / UNABLE_TO_EVALUATE
R.16  Golden corpus cases           fixtures asserting per-scope output and the roll-up
R.17  Explicit lock statement
```

**Structural conformance is assumed, not restated:** every Requirement inherits 45D.4.1–45D.4.12 automatically. A Requirement specification that restates them is duplicating; one that *contradicts* them is a defect.

Recorded as **N-22** — no such template exists today; 45A/45B/45C's structure is implicit and was reconstructed here.

---

# 45D.8 Gaps, ambiguities and conflicts

| ID | Finding | Severity |
|----|---------|----------|
| **N-18** | **`EVALUATOR_TYPE` is `NOT NULL` in three locked tables and defined nowhere.** Only candidate vocabulary (36.12) is explicitly a recommendation | **CRITICAL** |
| **N-19** | **Liability vocabulary leaking into shared `evaluations`** via AM-8's `scope` / `cap_kind`. Blocks any non-magnitude evaluator. Must be settled before 45B re-lock | **CRITICAL** |
| **N-20** | The boundary between *Requirement-specific facts* (44.11, correctly liability-shaped in 45B) and *shared persistence* (42.15) is nowhere stated. N-19 is its first symptom; without the boundary, the next evaluator repeats it | HIGH |
| **N-21** | **45D scope discrepancy** — `all_lock.md` says 45D is Liability Golden Test Cases; the instruction says Other Evaluator Edge Cases | HIGH |
| **N-22** | No Requirement Specification Template exists; 45A–45C's structure is implicit | MEDIUM |
| **N-23** | Only `NUMERIC_COMPARISON` has ever been exercised. Eight recommended evaluator types are untested by any specification | HIGH |
| **N-24** | **Step 37's scope freeze never enumerates which Requirements V1 must support.** Whether `LIABILITY-001` alone satisfies V1 is undecided — this governs whether any further evaluator is needed at all | HIGH |
| **N-25** | 45D.4.3 asserts the general/exception split is structural, but the only evidence is liability. If it is in fact domain-specific, option 1 in 45D.6 is wrong | MEDIUM |
| **N-26** | `MULTI_CLAUSE` and `CONFLICT_DETECTION` appear in 36.12 as *evaluator types*, yet 45D.4.1 and 45D.4.5 treat multi-provision handling and conflict detection as **universal structural behavior** | **RESOLVED** — engine behaviors, not types |
| **N-35** | **An `OPTIONAL` Requirement with no mapped provision has no specified classification.** Step 28 r5 covers only "A **required** Requirement" | **HIGH — new** |
| **N-36** | **Composite Requirements** — may one Requirement carry both a presence Standard and value criteria, and does it then produce two Evaluations? | **HIGH — new** |
| **N-37** | `evaluation_evidence` must permit **zero** rows per Evaluation, or locked 45C.15 becomes unrepresentable | **MEDIUM — new** |
| **AM-18** | `company_standard_versions.standard_kind` (`PRESENCE \| VALUE`) — minimal representation of approved R-1; amends locked 42.8 | **Amendment, unapproved** |

### Second-order dependency check (per the standing audit rule)

**N-19 depends on:** AM-8, 42.15, 45B.4/45B.11, D-1.2 roll-up (unaffected — classification is evaluator-agnostic), golden cases 2/3/4/12, and the reviewer UI's scope column. **It does not affect** J-3 (decisions are scope-agnostic), N-1 (decision versioning), or the authorization traversal.

**N-18 depends on:** three locked tables, the Requirement Specification Template (R.3), Step 47's permission catalogue (unaffected), and every future evaluator specification.

---

# 45D.9 External reference material

Per the accepted classification (REFERENCE MATERIAL → AUDITED → AVAILABLE FOR FUTURE ADAPTATION), the four MoS documents were checked for relevance to 45D.

**Result: no applicable material.** The external project has no evaluator, no deterministic analysis engine, and no equivalent of Requirements, Findings or Evaluations. Its contributions are confined to Steps 47/49/52/53/55 as recorded in [EXTERNAL_REFERENCE_AUDIT.md](../00-project/EXTERNAL_REFERENCE_AUDIT.md).

One methodological observation transfers: the external documents' *Known Gaps* discipline is the same practice as 45D.8 — and the external project's inert `pending` status (conflict C-EXT-11) is the same defect class as **N-18** and J-4, namely vocabulary declared but never defined. That is now the **third** instance in LegalMind, which suggests a systematic sweep for undefined enums rather than discovery one per pass.

---

# 45D.10 What 45D does not specify

* **No new legal Requirement.** Termination, Indemnification and Governing Law remain NOT YET SPECIFIED. Their stub documents are unchanged.
* **No evaluator-type vocabulary** — blocked by N-18, which is a decision, not a derivation.
* **No resolution of N-19** — four options presented, none selected.
* **No golden test cases** — displaced by the 45D scope change (N-21) and still blocked by B-6/B-8/N-11/N-12/N-13.
* **No amendment to 45B** — N-19 argues AM-8 needs revision, but 45B is locked and any change follows the approval process.

---

# 45D.11 Lock readiness

| Question | Answer |
|---|---|
| Is 45D ready to lock? | **No.** N-18 and N-19 are both CRITICAL and both sit inside 45D's own subject matter |
| Can 45D.4 (structural contract) lock independently? | **Partially.** 45D.4.1–45D.4.11 are traceable to locked rules and could lock. 45D.4.12 cannot — it asserts reproducibility that N-12/N-13 make unrepresentable |
| Can the Requirement Template lock? | **Not usefully** — R.3 references the undefined `EVALUATOR_TYPE` |
| Does 45D unblock a second evaluator? | **No.** N-24 must first establish whether V1 needs one |
| Recommended sequence | N-24 (does V1 need more than one evaluator?) → N-18 (evaluator-type vocabulary) → N-19 (shared-schema coupling, before 45B re-lock) → N-26 → then 45D.4 and the template |

**N-24 first** — deliberately ahead of the technical items. If V1 requires only `LIABILITY-001`, N-19 collapses to option 4 and N-18 needs only one value. The scope question governs the cost of every other answer in this document.

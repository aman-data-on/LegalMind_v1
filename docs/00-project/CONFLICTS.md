# Conflicts & Ambiguities

Project rule: when two authoritative statements conflict, the conflict is reported, never silently resolved. This document exists so that no future session quietly picks a winner.

**C-01 through C-04 were reconciled by the project owner on 2026-08-16** (registry entries `REC-01`–`REC-06` in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md)). The analysis found that **none of the four was a true contradiction** — each was a supersession chain, a layer migration, a refinement, or different terminology for different stages. No historical locked text was modified.

**C-05 – C-08, C-10 and C-12 remain open.** **C-11 was resolved on 2026-08-17** by `REC-08` (CI/CD tooling is GitHub Actions). Do not resolve any open item without explicit approval.

**All N-series and J-series items are closed as of 2026-08-17** — resolved through Reconciliation Passes 2–6 and Amendment Batch AB-1. See [DECISION_FINALIZATION.md](DECISION_FINALIZATION.md) for the classification of every item. The remaining open decisions are the security/authorization track (OD-1 – OD-15) and the Requirement configuration catalogue (N-24b), neither of which blocks the evaluator track.

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
| C-09 | `backend/` source code vs "no implementation exists" | ✅ **RESOLVED** — authorized retroactively (`IMPL-01`, AB-2) |
| C-10 | `roles` seed list (42.2) vs the canonical role matrix (Step 23) | ⏳ Open (MEDIUM) |
| C-11 | Step 39 stack table names GitHub Actions for CI/CD vs locked 55.6 listing CI/CD tooling NOT YET SPECIFIED | ✅ **RESOLVED** — GitHub Actions is the V1 choice (`REC-08`) |
| C-12 | Step 39 stack table names Playwright for testing vs locked 54.7 listing test framework selection NOT YET SPECIFIED | ⏳ Open (LOW) — **blocks nothing**; both readings permit Playwright |

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

~~**Step 45B remains UNLOCKED** pending final review.~~ **Superseded:** Step 45B was re-locked on 2026-08-17 incorporating Amendment Batch AB-1. See [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) §K and `all_lock.md` "Step 45B — RE-LOCK RECORD". The shape of `rule_configuration` remains `NOT YET SPECIFIED`.

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

## C-09 — Application source code exists while the project asserts no implementation

## ✅ RESOLVED 2026-08-17 — `IMPL-01`, Amendment Batch AB-2

**Verdict: authorized retroactively, and the record says so.** The owner authorized implementation on 2026-08-17; the lock record states plainly that the work preceded the authorization and that nothing is backdated. The two additive tables were ratified separately as **AM-22** (`review_assignments`) and **AM-23** (`escalations`), with ownership resolved by **AM-24** (`created_by` is the owner; transfer deferred to V2).

The three technical findings the review surfaced — `F-1` EV-MIN delete path, `F-3` mapping state not persisted, `F-4` non-deterministic suite — are **not closed by this resolution**. They are tracked in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state.

### Original finding (retained for the record)

**Severity: HIGH — a process conflict, not a specification conflict. Recorded 2026-08-17; scope re-verified the same day.**

> **Updated.** First recorded as a five-file skeleton. On re-verification it is a **substantial implementation**: 58 Python modules, **8,717 lines**, three Alembic migrations, 13 test files, and a `.pytest_cache` showing the suite has been run. `backend/README.md` reports **six of ten build steps complete** — schema, security, ingestion, mapping, evaluation, workflow — with the API layer next.

The work is **specification-disciplined**, not ad-hoc: it cites locked decisions throughout, implements EV-MIN as a deferred constraint trigger, enforces append-only audit and decisions by database trigger, keeps mapping weights as configuration rather than code, structurally prevents the `PRESENCE` evaluator from reading clause text, declines to implement Step 35's deferred band vocabulary, and records its own limitations rather than working around them.

Two additive tables were created that no locked table represents — `review_assignments` (Step 24 r5/r6/r16/r17) and `escalations` (Steps 4, 22, Step 24 r5). `backend/README.md` states no locked table was amended. **This has not been independently verified against Step 42 and is not ratified by any lock record.**

**The conflict:**

| Source | Statement |
|---|---|
| [CLAUDE.md](../../CLAUDE.md) | "No implementation exists, and implementation must not begin without explicit approval." Do not, without explicit approval: "write application code, database migrations… install dependencies or select additional technologies… generate scaffolding 'to get started'" |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | "**No implementation has begun. No application code, database migration, API endpoint, frontend component, or infrastructure exists in this repository.**" |
| [IMPLEMENTATION_READINESS_GATE.md](../09-implementation/IMPLEMENTATION_READINESS_GATE.md) | "Implementation **may** be authorized… This document reports readiness; it does not grant it." |
| Working tree | `backend/` exists, with declared dependencies and a database layer |

No approval to begin implementation appears in `all_lock.md`; a search for one returns nothing.

**Not resolved here.** Three readings are possible and only the owner can choose:

1. Implementation **was** approved outside the repository record — then `IMPLEMENTATION_STATUS.md` and `CLAUDE.md` are stale and the approval belongs in `all_lock.md`.
2. It is unauthorized scaffolding — then it should be removed, and the "no scaffolding" rule reaffirmed.
3. It is a private local experiment, deliberately untracked — then it should be git-ignored and explicitly labelled as non-authoritative.

**Until this is decided:** do not treat `backend/` as specifying anything — code is not a specification, and a behavior appearing there does not make it decided. In particular, `review_assignments` and `escalations` are **unratified additive tables**, and the second-person-approval co-signature mechanism is an implementation choice where Step 31 r15 specifies a requirement but no mechanism.

**Resolved sub-item:** the repository had **no `.gitignore`**, leaving 70 `.pyc` files and a `.pytest_cache` one `git add -A` away from being committed. A `.gitignore` was added on 2026-08-17 covering Python, Node, secrets, editor and OS artefacts — and, per Step 54, contract file types so real counterparty documents cannot be committed by accident. This is repository hygiene and decides nothing about C-09 itself.

---

## C-10 — The `roles` seed list does not match the canonical role matrix

**Severity: MEDIUM — two locked steps, two role vocabularies. Recorded 2026-08-17 during architecture-reference verification.**

| Source | Status | Roles |
|---|---|---|
| **Step 23** (`ROLE-06`) | LOCKED — "supersedes the Step 3 draft groups" | `User` · `Legal Reviewer` · `Legal Admin` · `Super Admin` |
| **Step 42.2** (`DATA-04`), `all_lock.md` lines 7421–7427 and 8342–8348 | LOCKED | `USER` · `ADMIN` · `SUPER_ADMIN` |

The schema's seed list **omits `Legal Reviewer` and `Legal Admin`** and introduces `ADMIN`, which does not appear in the canonical matrix. The list is introduced as "Initial roles" — not labelled `RECOMMENDED`, unlike the `users.status` values immediately above it, which *are* ("Recommended statuses").

**Why it matters:** Step 47 locks the permission catalogue and states "**Default grants follow Step 23's locked role summary.**" A team seeding `roles` from 42.2 would produce a role set the Step 47 default grants cannot be mapped onto, and `ADMIN` would have no defined legal authority boundary — precisely the area `ROLE-05` and `SEC-02` guard.

**Not resolved here.** Two readings are available:

1. 42.2's list is illustrative seed data that Step 23 supersedes — then the schema document should say so, as it does for `users.status`.
2. `ADMIN` is a distinct system role separate from the Legal roles — then its relationship to `Legal Admin`, and its `legal.*` boundary, need stating.

**Until decided:** treat **Step 23 / `ROLE-06` as the canonical role matrix** — it is the later locked decision on the subject and the one Step 47 explicitly builds on — and do not seed `ADMIN` without a decision. Report rather than assume.

Documented at: [USER_ROLES.md](../01-product/USER_ROLES.md), [DATABASE_MIGRATIONS.md](../09-implementation/DATABASE_MIGRATIONS.md) §42.2, [STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md).

---

## C-11 — Is CI/CD tooling locked by Step 39, or NOT YET SPECIFIED by Step 55?

## ✅ RESOLVED 2026-08-17 — `REC-08`

**Verdict: the Step 39 stack table governs.** The project owner explicitly confirmed on 2026-08-17 that **GitHub Actions is the approved CI/CD tooling for LegalMind V1**, and that the Step 39 row is the intended tooling decision.

Step 55.6's inclusion of "CI/CD tooling" in its NOT YET SPECIFIED list is **superseded for that one line item only**. The 55.6 text stays exactly where it is and is annotated as superseded in [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) §55.6; `all_lock.md` was appended, never rewritten.

**Consequence.** `.github/workflows/ci.yml` is an authorized use of the locked Step 39 stack — `IMPL-01` permits the Step 39 stack — and is therefore **not** an unratified implementation choice and **not** a Pending-ratification item. The workflow is retained unchanged.

**Deliberately still open.** `REC-08` is narrow. Every other item in 55.6's list remains locked as NOT YET SPECIFIED: hosting platform, container orchestration, object-storage provider, monitoring stack, disaster-recovery objectives. `REC-08` confers no authority over any of them and authorizes no technology beyond GitHub Actions.

Lock record: [`all_lock.md`](../../all_lock.md) under "Reconciliation Decision REC-08 — CI/CD tooling" · Registry: [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) §R.

### Original finding (retained for the record)

**Severity: LOW — two locked records, opposite answers. Recorded 2026-08-17 while correcting a false "No CI pipeline" claim in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).**

| Source | Status | Says |
|---|---|---|
| **Step 39** technology stack table, `all_lock.md` line 6049 | LOCKED (stack table only) | `CI/CD` → **GitHub Actions** — "Straightforward automated testing/deployment" |
| **Step 55.6** production blockers, `all_lock.md` line 14871 and [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) §55.6 | LOCKED | "**NOT YET SPECIFIED:** hosting platform, container orchestration, **CI/CD tooling**, object-storage provider, monitoring stack, disaster-recovery objectives. None is determined by a locked decision; each is an operational choice at deployment time." |

**Why it matters:** `.github/workflows/ci.yml` exists and `main` is protected on one of its jobs. Under the first reading it is an authorized use of the locked Step 39 stack — `IMPL-01` forbids "any technology, dependency or service **beyond the Step 39 stack**", and GitHub Actions is inside it. Under the second reading it is an implementation choice made where the specification is silent, which `IMPL-01` condition 4 leaves unratified and which therefore belongs under **Pending ratification** in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). The two readings put the same file in two different governance categories.

Note that the "a later Step document beats an older topic document" heuristic in [CLAUDE.md](../../CLAUDE.md) does **not** settle this: both sources are Step-numbered lock records, not a Step versus an older topic document.

**Not resolved here.** Two readings are available:

1. Step 39's table is the locked stack and names GitHub Actions, so the tooling *is* chosen; 55.6's list is about *deployment-time* operational choices (hosting, orchestration, DR) and sweeps CI/CD in by association.
2. Step 55 is the later locked decision on deployment and deliberately reopens CI/CD as an operational choice, superseding the Step 39 table's row for this one line item.

**Until decided:** the workflow stays as it is — it is relied on by branch protection and by the release-blocking check, and removing it would reduce enforcement. Do not record the tooling question as settled in either direction, and do not cite this conflict as authority for adding any *other* technology.

Documented at: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state, [STEP_55_DEPLOYMENT.md](../09-implementation/STEP_55_DEPLOYMENT.md) §55.6, [BACKEND_ARCHITECTURE.md](../05-architecture/BACKEND_ARCHITECTURE.md) (stack table).

---

## C-12 — Is the test framework locked by Step 39, or NOT YET SPECIFIED by Step 54?

**Severity: LOW. Recorded 2026-08-17 while adding the browser-workflow suite. Not resolved. It blocks nothing — see "Why it does not block" below.**

The same shape as **C-11**, one document over.

| Source | Status | Says |
|---|---|---|
| **Step 39** technology stack table, `all_lock.md` line 6047 | LOCKED (stack table only) | `Testing` → **Pytest + Playwright** — "Backend/domain + real browser workflow testing"; `Frontend testing` → **Vitest** |
| **Step 54.7**, `all_lock.md` line ~14832 and [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md) §54.7 | LOCKED | "**NOT YET SPECIFIED:** coverage targets, **test framework selection**, CI topology — implementation-phase choices, **none determined by a locked decision.**" |

Step 54's closing clause is the sharper half: it does not merely omit the choice, it asserts that *no locked decision determines it* — while a locked table names two frameworks and a third.

**Why `REC-08` does not settle it.** `REC-08` resolved C-11 in favour of the Step 39 row, but its own text limits the supersession to "that one line item only". Extending it to test frameworks would be exactly the kind of quiet generalization rule 5 forbids.

**Why it does not block.** Both readings permit the framework actually used:

1. Step 39 governs → Playwright is the locked browser tier, and building it is building what is locked.
2. Step 54.7 governs → framework selection is an implementation-phase choice, and Playwright is *still* inside the Step 39 stack, so `IMPL-01`'s bar on "any technology, dependency or service **beyond the Step 39 stack**" is not crossed either way.

Pytest and Vitest have been in use on identical reasoning since the first unit. Whichever way this is ruled, **no code changes** — which is why it is registered rather than escalated.

**Two consequences observed, not decided.** Locked 54.1's six tiers contain no browser tier, and 54.7's release gate does not list one. So `frontend/e2e/` is documented as **supporting**, is not described as a locked tier, and is not part of the release gate; CI job 10 says so in its own comment. Coverage targets remain unset.

**Until decided:** do not describe the browser suite as a locked tier or a release gate, and do not cite this conflict as authority for adding any other framework.

Documented at: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) § Build state, [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md) §54.7, [`frontend/playwright.config.ts`](../../frontend/playwright.config.ts).

---

## Provenance note — the master specification changed during documentation

While this documentation structure was being built, `all_lock.md` grew from 12,481 lines to 13,510 lines: Step 45A's lock was confirmed and Step 45B (Evaluator Data Contract) was added. It has since grown to **14,885 lines** — AB-1, the 45B re-lock, Steps 45C/45D, and Steps 47, 49 and 52–55. Growth has been append-only throughout; no historical locked text has been modified.

Any future session should re-check the tail of `all_lock.md` against [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) before assuming the docs are current.

# CLAUDE.md — Working rules for LegalMind

Read this before doing anything in this repository.

**LegalMind is a specification-first project. The V1 specification is complete and implementation is now authorized** — `IMPL-01`, locked 2026-08-17. Specification-first still governs everything: `IMPL-01` authorizes **building what is already locked** and confers no authority to decide what is not. See [What implementation authorization does and does not cover](#what-implementation-authorization-does-and-does-not-cover).

---

## Start here

| | |
|---|---|
| **Where do I find X?** | [docs/README.md](docs/README.md) — the documentation index |
| **How the system works end to end** | [docs/00-project/ARCHITECTURE_REFERENCE.md](docs/00-project/ARCHITECTURE_REFERENCE.md) |
| Project overview | [docs/00-project/PROJECT_OVERVIEW.md](docs/00-project/PROJECT_OVERVIEW.md) |
| Every explicitly locked decision | [docs/00-project/LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) |
| Current step and what is not yet decided | [docs/00-project/IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) |
| Known conflicts — do not resolve these yourself | [docs/00-project/CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| Terminology and the distinctions that matter | [docs/00-project/GLOSSARY.md](docs/00-project/GLOSSARY.md) |
| How to propose a change, and what needs approval | [CONTRIBUTING.md](CONTRIBUTING.md) |
| The authoritative historical record | [all_lock.md](all_lock.md) |

Reuse what is already decided. The registry, the status document and the conflicts register exist so that you do not re-derive settled questions from `all_lock.md` — read them first, and go to `all_lock.md` for the exact locked text when you need it.

**`all_lock.md` is authoritative.** The `docs/` tree is the organized implementation reference derived from it. If they disagree, `all_lock.md` wins — and you must report the discrepancy rather than quietly following either one.

### Three traps in this repository

**1. A later Step document beats an older topic document.** Where both exist, the Step-numbered one is authoritative and the older one survives only as a record of what was true earlier. Four older files still read `NOT YET SPECIFIED` / `RECOMMENDED` for areas that are now locked — check the successor before concluding anything is undecided:

| Older file says "not specified" | Actually locked by |
|---|---|
| [AUTHENTICATION.md](docs/06-security/AUTHENTICATION.md) | [STEP_47_SECURITY_SPECIFICATION.md](docs/06-security/STEP_47_SECURITY_SPECIFICATION.md) |
| [FRONTEND_ARCHITECTURE.md](docs/05-architecture/FRONTEND_ARCHITECTURE.md) | [STEP_52_FRONTEND_ARCHITECTURE.md](docs/05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) |
| [TEST_STRATEGY.md](docs/08-testing/TEST_STRATEGY.md) | [STEP_54_TESTING_STRATEGY.md](docs/08-testing/STEP_54_TESTING_STRATEGY.md) |
| [DEPLOYMENT.md](docs/09-implementation/DEPLOYMENT.md) | [STEP_55_DEPLOYMENT.md](docs/09-implementation/STEP_55_DEPLOYMENT.md) |

**2. Working documents are not specifications.** The reconciliation passes, scope audits, decision-finalization and external-reference audit files record *how* conclusions were reached. Their internal status lines describe the state at the time of writing and are now stale — several still say "45D NOT LOCKED" when 45D is locked. They carry a 📁 banner. Never implement from them; take the outcome from [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md).

**3. Decision IDs are the fastest way in.** Every locked decision has a stable ID; search the registry by prefix rather than reading `all_lock.md` end to end: `PROD` `ROLE` `LEGAL` `FIND` `DOC` `ENG` `AI` `ARCH` `DATA` `AUD` `LIABILITY` (Steps 1–45B) · `REC` (reconciliation) · `AM` (Amendment Batches AB-1 `AM-1`–`AM-21` and AB-2 `AM-22`–`AM-24`) · `SEC` (Step 47) · `API` `FE` `OBS` `TEST` `DEP` (Steps 49, 52–55) · `IMPL` (implementation authorization). Open items use `OD-*` (open decisions), `C-*` (conflicts), `F-*` (engineering resolutions).

⚠️ **`F-*` is overloaded.** [DECISION_FINALIZATION.md](docs/00-project/DECISION_FINALIZATION.md) §1 uses `F-1`–`F-12` for *engineering resolutions* (`F-3` = escalation recorded at Finding level, cited by `AM-23`), while [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state uses `F-1`/`F-3`/`F-4` for *code-review findings* (`F-3` = Mapping State not persisted). Two different `F-3`. Always name the document you mean; do not merge the two series without an owner decision.

---

## The twenty-three rules

### Specification discipline

1. **LegalMind is specification-first.** Decisions are made in the specification, then implemented — never the reverse.
2. **Locked decisions are authoritative.** A decision marked LOCKED in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) is settled.
3. **Never silently modify a locked decision.** Not to fix a bug, not to make code cleaner, not because a better design occurred to you.
4. **Do not implement features without an approved specification.** If the behavior isn't specified, stop and ask — don't fill the gap with a reasonable-sounding default.
5. **When you discover a contradiction, stop and report it.** Do not pick the version you prefer, do not merge the two, do not assume the later one wins. Add it to [CONFLICTS.md](docs/00-project/CONFLICTS.md) and surface it.
6. **Before changing a locked decision, name it explicitly and request approval.** Say which decision ID, what it currently says, what you propose, and why. Wait for a yes.
7. **Never invent legal requirements.** No rule, threshold, tolerance, carve-out, or evaluator behavior that isn't in the specification. Inventing a plausible legal rule is worse than leaving a gap, because it looks authoritative.
8. **Never claim an unspecified decision is finalized.** "NOT YET SPECIFIED" is a valid, useful state. Preserve it.

### The legal-analysis model

9. **Legal analysis is deterministic in V1.** Same inputs + same configuration snapshot + same engine version → same result.
10. **V1 uses no LLM, RAG, embeddings, or vector database in the authoritative analysis path.** This is locked (`AI-01`) and is not a temporary simplification pending better tooling. Classical NLP (e.g. spaCy) is permitted in an assist-only role.
11. **Evidence traceability is mandatory.** Every finding and every extracted fact traces back to source evidence, and evidence must survive the evaluator.
12. **Findings must be explainable.** Every Finding reconstructs as Evidence → Fact → Standard → Rule → Result. No generic risk score. No "AI confidence" percentage.
13. **Legal Decisions are separate from Company Standards.** A Company Standard is what the organization wants; a Legal Rule is how far it will tolerate departing from that; a Legal Decision is an authorized human's ruling on a specific case. The engine produces Findings — it never produces Legal Decisions.
14. **RESOLVED ≠ MATCH.** A resolved workflow state must never be recorded as a MATCH finding. Likewise `DEVIATION` does not mean "unacceptable."
15. **Fail closed.** Insufficient extraction or evidence produces `UNABLE_TO_EVALUATE` — never a guess, never a silently resolved ambiguity, never a discarded carve-out.

### System guarantees

16. **Configuration is versioned, and Reviews use configuration snapshots.** Publishing new configuration never mutates an existing Review. Drafts never affect comparisons.
17. **Auditability and reproducibility are mandatory.** The audit trail is append-only. Historical Reviews stay reproducible.
18. **Security and ownership checks are server-side.** Authentication → Authorization → Business Operation → Database. Knowing an object's ID is never sufficient for access. The UI never implements legal evaluation logic and never talks to the database directly, and UI permission gating is presentation only.
    **Authentication never confers Legal Decision authority** (`SEC-01`), and no super-role bypass may ever reach `legal.decision` or `legal.approve_customization` (`SEC-02`, `ROLE-05`). Internal legal positions are permission-controlled and must not leak to ordinary users or counterparties (`LEGAL-02`); confidential fields are **omitted, not nulled**, and out-of-scope objects return a byte-identical 404 rather than disclosing existence (`SEC-07`, `API-10`).
19. **Do not make architectural changes for convenience.** The domain boundaries in [SYSTEM_ARCHITECTURE.md](docs/05-architecture/SYSTEM_ARCHITECTURE.md) are locked. No new technologies, dependencies, or services without approval.
20. **Treat `docs/` as the implementation specification.** Reference it rather than re-deriving decisions, and keep it in sync when the specification advances.

### Legal source material

21. **Ask for real legal source material — never manufacture it.** If implementation or validation requires real legal documents, representative contracts, company standards, or other legal source material that is not already in the repository, **stop and ask the owner for it explicitly before proceeding.** Do not invent legal content, and do not promote an arbitrary or illustrative example into production truth.

    This applies to golden-corpus fixtures, Company Standard and Legal Rule configuration, Requirement catalogues, mapping aliases and keyword groups, Step 35 threshold calibration, seed and demo data, and any test whose expected output asserts a legal conclusion.

    The worked examples throughout the specification — 6-month liability caps, Termination, Indemnification, Governing Law — are **illustrations of behavior, not the organization's legal positions**. Rule 7 forbids inventing a legal requirement; this rule closes the adjacent gap, where invented material arrives as *data* rather than as specification. Missing source material is a blocker to be raised, never a gap to be filled.

### The master record

22. **`all_lock.md` is append-only.** Never edit, reflow, reorder, reformat or delete a single existing line of it — not to fix a typo, not to correct a stale status block, not to apply an approved amendment. Every approved change is **appended** as a new lock record; superseded text stays exactly where it is and is annotated as superseded elsewhere. Twelve documents assert that prior line counts are byte-identical, and reproducibility of historical Reviews depends on that being true. The same discipline applies to every locked specification in `docs/`: supersede with a banner, never overwrite.


### Session continuity

23. **Completed work is completed, whoever did it.** Recorded work stays done regardless of whether *this* session performed it — a previous Claude session, another terminal, another process or another agent all count. **Never treat "this session did not do it" as "it has not been done."** That inference has been the single largest source of wasted effort in this project.

    **Before starting, read the state.** The repository itself, [CLAUDE.md](CLAUDE.md), [HANDOFF.md](HANDOFF.md), [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), [CHANGELOG.md](CHANGELOG.md), the tail of [all_lock.md](all_lock.md), and the tests and fixtures touching your task. These records are continuity evidence — use them, then verify only what the task actually requires.

    **Before making a change, check whether it is already made.** Grep for the symbol, open the file, run the test. If something looks incomplete, verify the real state of the code and the suite before rebuilding it. Do not recreate, re-implement, re-test or re-audit merely because you did not watch it happen.

    **Do not re-ask for decisions or material already supplied.** Keep these five states distinct and never collapse them:

    | State | Meaning |
    |---|---|
    | **Already decided** | An owner ruling exists. Do not reopen it or ask again. |
    | **Already implemented** | Code, config or fixtures exist and pass. Verify, do not rebuild. |
    | **Material supplied** | The documents exist — see [Source material](#source-material) below. **Look before asking.** |
    | **Genuinely missing material** | Verified absent from every known location. |
    | **Genuinely pending decision** | No ruling exists anywhere in the records. |

    **Assume concurrency.** Other terminals or agents may be working now. Inspect the filesystem and `git status` before modifying anything, and do not duplicate what is already present.

---

## Source material

**Owner ruling, 2026-08-18: the six documents below are the ONLY source material for this project.** Nothing else on this machine is v1 source material, whatever it may look like. In particular `/root/LegalMind/` is a **different project** — do not read from it except under the narrow test authorization below, and never treat anything in it as v1 source material.

**Test-only exception — owner authorization, 2026-08-18.** Public web terms of third-party providers may be used as **golden-corpus test inputs**, cited by the `CP-LIAB-*` fixtures. They are test specimens ONLY: never a source of a Company Standard, a Legal Rule, a threshold or any configuration value, and they never become v1 source material. The six documents below remain the project's source material, and nothing else on this machine may be used to fill `LEGALMIND_SOURCE_MATERIAL_DIR`.

| # | Document | Notes |
|---|---|---|
| D1 | CloudPe Terms of Service (5 Feb 2026) | published page; no liability cap |
| D2 | Leapswitch Networks Terms of Service (26 Feb 2026) | **§13 is the ratified Company Standard's source** — 12 months of total fees |
| D3 | CloudPe Service Level Agreement (eff. 1 Oct 2024) | service credits, no liability cap |
| D4 | Leapswitch Service Level Agreement (dedicated server) | service credits, no liability cap |
| D5 | Executed NDA, 17 June 2026 | **real counterparty** — never name it or its signatories |
| D6 | Leapswitch Master Services Agreement v2 (July 2025) | unexecuted template; §17.2 and §17.7 contradict |

**A second Leapswitch/CloudPe tranche arrived 2026-08-19** — six further documents at the same path: an **executed** Master Services Agreement with a real customer (28 July 2026), a second draft round of the MSA template, and both Acceptable Usage Policies and Privacy Policies.

⚠️ The executed MSA **names a real counterparty**. Treat it exactly like `NDA.pdf` — never name that counterparty or its signatories in the repository.

⚠️ Its cap is a **new formula** and must not be flattened into the ratified standard: §13 "Limitation on **Damages**" caps at *"the average price or fee paid for Services over a three (3) month period in the period of one (1) year"*, excluding death or bodily injury. An **average** is not a total, so under the 2026-08-18 basis ruling it is not comparable to `FEES_PAID` and fails closed.

⚠️ Both AUPs are saturated with *"includes but is not limited to"* in the **enumerative** sense. Neither caps or excludes liability. A detector hunting "not limited" would misread them — this is the `L-29a/b` trap in live material.

**Seven Indian statutes were also supplied** (2026-08-18): Contract Act 1872 · IT Act 2000 · SPDI Rules 2011 · Companies Act 2013 · CERT-In Directions 2022 · DPDP Act 2023 · IT Rules 2021. They are present on disk in `Indian_Laws_and_Acts/`.

⚠️ **A statute is NOT a Legal Rule and NOT a Company Standard.** Rule 7's trap in a new form: the Contract Act does not state what liability cap the organization will accept, and the DPDP Act does not create a Requirement. Statutes are **background law** — cite them in an explanation, never load them as configuration, and derive no Requirement, threshold or acceptance position from them. They are not counterparty contracts either, so they exercise the liability evaluator not at all and close none of the blocked 45E cases.

**Where they live.** `LEGALMIND_SOURCE_MATERIAL_DIR`, default `/root/Legalmind.v1/legal-docs/ (gitignored)` (locked 54.6 keeps them out of the repository). **All six are present as of 2026-08-18** under the filenames above, and `legalmind.ingestion.parsing` reads each as `COMPLETE`. `test_source_material.py` verifies presence, that the path is outside the working tree, and that no copy has entered the repository.

Locked **54.6** governs: no document, and no clause text beyond short cited excerpts, enters this repository.

⚠️ **A second tranche is still outstanding and must be requested, not substituted.** These six are all Leapswitch-issued, so they state the organization's own position and cannot exercise the deviation paths. See [SOURCE_MATERIAL_INTAKE.md](docs/00-project/SOURCE_MATERIAL_INTAKE.md) §8.5 for the seven patterns with no specimen. **Do not satisfy that request from any other directory on this machine.**

---

## Preserve the examples

The specification is full of worked examples — MATCH vs DEVIATION, RESOLVED ≠ MATCH, APPROVAL_REQUIRED, contract customization, evidence traceability, configuration snapshots, liability evaluation, multiple clauses, conflicting provisions. **These are deliberate.** They exist to show intended behavior precisely where prose is ambiguous.

Never delete an example to make a document shorter. Never "clean up" example values. When you add a specification, add worked examples in the same style.

---

## Document status labels

Every specification document declares its state. Never mix states without labeling them.

| Label | Meaning |
|-------|---------|
| 🔒 `LOCKED` | Settled. Requires explicit approval to change. |
| `PROVISIONAL` / `RECOMMENDED` | Proposed but not settled. Do not build on it as if it were final. |
| ⏳ `UNDER REVIEW` / `IN PROGRESS` | Actively being decided right now. |
| `PLANNED` / `NOT YET SPECIFIED` | Nothing has been decided. Do not invent it. |
| 📁 `ANALYSIS` / `PROPOSAL` | Working document. Records reasoning, decides nothing. Its status lines may be stale. |

Lifecycle state — specified · locked · implemented · tested · verified · blocked · production-ready — is tracked separately in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which is the only document that may assert build state. It is a documentation convention and must never share a field or enum with one of the five legal-domain state axes.

---

## What implementation authorization does and does not cover

`IMPL-01` (🔒 2026-08-17) authorizes implementation of the locked V1 specification, in the [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5 sequence. Its §6 standing constraints do **not** relax, and rules 1–22 above are unchanged.

**Authorized:** application code, database migrations, API endpoints, frontend components and test harnesses that realize a locked decision.

**Still requires explicit approval — `IMPL-01` grants none of it:**

* deciding anything marked `NOT YET SPECIFIED`
* resolving any open conflict (C-05–C-08, C-10, C-12) or open decision (`OD-*`)
* amending any locked decision
* adding any table, column or enum not covered by a lock record or an approved amendment batch
* authoring `NORMATIVE` golden-corpus fixtures — these need real representative contracts and the organization's real Company Standards, which **must be supplied, never manufactured** (rule 21)
* any technology, dependency or service beyond the Step 39 stack

**The code is not a specification.** A behavior appearing in the implementation does not make it decided. Where the code makes a choice the specification does not fix, that choice is an implementation detail recorded as such — it is not thereby locked. Conformance is verified against the locked corpus, never asserted by the implementation.

Documents under [docs/09-implementation/](docs/09-implementation/) still describe a *target*, not built work. **[IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) is the only document that may assert build state** — read its Build state table rather than inferring progress from the presence of code.

---

## Current state

**The V1 specification is complete.** Steps 1–45D, 47, 49 and 52–55, `REC-01`–`REC-09`, Amendment Batches AB-1 and AB-2, and `IMPL-01` are locked. `all_lock.md` is **15,358 lines**. Step 45E — Golden Corpus — is IN PROGRESS (64 fixtures specified; **28 authored — 16 `STRUCTURAL`, 9 `DOCUMENT_SUPPORTED`, 3 `STANDARD_DERIVED`**, the latter two built from the contracts supplied on 2026-08-18; **0 `NORMATIVE`**). Per-case status for all 64: `backend/tests/corpus_coverage.json`.

### The V1 configuration state — read before touching the evaluator or the corpus

**Company Standards are PER DOCUMENT TYPE (owner Q3=B, 2026-08-19). The ONE Legal Rule is the zero-tolerance blanket — approved and wired 2026-08-20.**

* **Two ratified standards**, one per document type, each in exactly one place under [backend/config/company_standards/](backend/config/company_standards/), referenced by fixtures via `company_standard_ref` — **never copy the values into a fixture.** They are *configuration*: no `all_lock.md` entry, no locked decision amended.

  | Code | Type | Position | Source |
  |---|---|---|---|
  | `LIABILITY-MSA-001` | MSA | **6 months of affected-service fees** | `MSA.pdf` §17.2 (owner, 2026-08-19) |
  | `LIABILITY-TOS-001` | TOS | **12 months of total fees** | `TOS-leapswitch.pdf` §13 (ratified 2026-08-18, re-scoped to TOS 2026-08-19 — **value unchanged**) |

* **Document Type scoping is enforced end to end** (locked Step 6 + Step 28; implementation 2026-08-19): every Company Standard declares `document_type` (publish refuses otherwise); the uploader declares a Contract's type from Step 6's ten values (`legalmind/domain/document_types.py` — owner Q9: declared, never inferred); and analysis evaluates only the Requirements whose type matches, refusing with `ANALYSIS_FAILED` when the Contract's type is undeclared. **An NDA therefore produces no liability Finding at all** — the applicability question, not a `MISSING`. Storage is the Company Standard JSONB per owner Q2 (the `D-3` route); the concept-vs-schema divergence is registered as **C-13**, open and blocking nothing.
* **The Legal Rule is decided, and it is ZERO TOLERANCE (manager ruling, recorded 2026-08-19).** *"Whatever is stated in our approved LeapSwitch legal documents is the final position. We do not provide/customize anything beyond those approved legal-document positions."* Therefore: MATCH → `ACCEPTABLE`; **any** DEVIATION → `UNACCEPTABLE` → Legal Decision required; **nothing that differs is ever auto-approved**. There is no `acceptable_max`, no `approval_required_above`, no tolerance band — not because none was chosen, but because **the policy is that none exists**. Never ask for thresholds again, and never infer one.
* **Wiring status: APPROVED AND WIRED (owner approval 2026-08-20).** Every ratified standard file carries `legal_rule.configuration = {"deviation_outcome": "UNACCEPTABLE", "unlimited_outcome": "UNACCEPTABLE"}` — the ONLY approved Legal Rule; the import tool refuses any other. Both evaluators read it (numeric `_rule_outcome_for`/`_unlimited_outcome`; presence `_deviation_outcome`), an unrecognised value fails closed to `NOT_APPLICABLE` and a human, and the corpus loader admits the rule only verbatim and only on `STANDARD_DERIVED`. The threshold keys stay forbidden everywhere — no tolerance band exists BY POLICY. Routing is doubly safe: D-3.5(a) sends `UNACCEPTABLE` to a human, and `UNRULED_DEVIATION_REQUIRES_DECISION` still catches any unruled path.
* **SLA scope is RULED (owner, 2026-08-20, closing L-13): service credits are a remedy, not a liability cap.** Liability is not applicable to the SLA document type, credit percentages are never read as caps, and no SLA-typed liability standard may be created from them. Pinned by `test_an_sla_is_never_measured_against_a_liability_requirement`.
* **Un-ruled deviations are routed to a human.** `UNRULED_DEVIATION_REQUIRES_DECISION` in [backend/legalmind/evaluation/workflow.py](backend/legalmind/evaluation/workflow.py) widens locked D-3.5 so `DEVIATION` + `NOT_APPLICABLE` yields `DECISION_REQUIRED` rather than `OPEN`. F-4 permits widening and forbids narrowing; this only widens. Consequence: in V1 essentially every deviation needs a Legal Decision.
* **`NOT_APPLICABLE` is the fail-closed state, not a placeholder** — locked Step 20 r4, *"the deviation stands and a human decides"*. **Do not add a fifth `RuleOutcome` value** (45B.26); `NOT_YET_SPECIFIED` was requested and deliberately declined.
* Keep `classification` (what a provision **is**) and `rule_outcome` (what Legal should **do**) strictly separate. `load_fixture` enforces the tier rules and `test_no_fixture_asserts_an_acceptance_policy` enforces them across the corpus.
* **A LeapSwitch outbound liability limitation must never be converted into a counterparty acceptance policy** without explicit owner approval. In particular MSA §17.2's six months is *not* a standard, and its basis ("fees for the specific Services giving rise to the claim") is **not** comparable to the ratified `FEES_PAID` — 45B.4 forbids assuming otherwise, so a six-month affected-services cap fails closed rather than deviating.

**Owner rulings of 2026-08-18/19 are settled. Do not reopen them and do not ask about them.**

| Ruling | Where it lives |
|---|---|
| Company Standards are **per document type** (Q3=B, 2026-08-19): MSA = 6 months affected-service fees, TOS = 12 months total fees | the two files under [backend/config/company_standards/](backend/config/company_standards/) |
| **Liability is not applicable to NDAs** (Q4=A) — an NDA produces no liability Finding | the document-type filter in `legalmind/analysis/service.py` |
| Document Type is **declared by the uploader** from Step 6's ten values, never inferred (Q9=A) | `legalmind/domain/document_types.py` |
| Type storage is **JSONB, no schema change** (Q2=A) | Company Standard `configuration.document_type`; C-13 registered |
| **Legal Rule = ZERO TOLERANCE** (manager, recorded 2026-08-19; **owner approved & wired 2026-08-20**): MATCH → `ACCEPTABLE`, any DEVIATION → `UNACCEPTABLE` → Legal Decision; no thresholds, no tolerance bands, no auto-approval of any deviation. Supersedes every earlier "no Legal Rule exists" statement | this table; memory `legalmind-zero-tolerance-legal-rule`; routing already enforced by D-3.5(a) + `UNRULED_DEVIATION_REQUIRES_DECISION` |
| `FEES_PAID` and `FEES_PAID_FOR_AFFECTED_SERVICES` stay **distinct** — never add either to `comparable_bases` or a conversion rule | same config file, `_owner_rulings` |
| Requirement catalogue: **SUPERSEDED 2026-08-19** — the owner instructed full-document review; **15 Requirements** across MSA/TOS/SLA, every position extracted from a LeapSwitch document | [docs/00-project/CLAUSE_CATALOGUE.md](docs/00-project/CLAUSE_CATALOGUE.md) + `backend/config/company_standards/` |
| MSA §17.2 and §17.7 govern **one scope and contradict** → `CONFLICT` | fixture `DOC-LIAB-04` |
| Source documents live at `legal-docs/` inside the project, **gitignored, never tracked** (re-ruled 2026-08-19; 54.6 = version control) | `/root/Legalmind.v1/legal-docs/ (gitignored)README.md` |

**The locked build sequence is complete and the project is in stabilization.** Every unit of the Gate §5 sequence is implemented; unit 10 (golden corpus) is the one unit still `PARTIAL`, and what remains of it awaits an approved Legal Rule and a second document tranche. Read [HANDOFF.md](HANDOFF.md) first — it is the single entry point for review, and names every open decision and every input still required from the owner.

**Implementation is authorized and underway.** For what is built, what is merely tested, and what blocks the VERIFIED state, read [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) — never `backend/README.md` or the code itself.

Two evaluators are specified: `LIABILITY-001` (`NUMERIC_COMPARISON`) and the generic `PRESENCE` evaluator. **No specific legal Requirement beyond `LIABILITY-001` is required by any locked decision** — Termination, Indemnification, Governing Law and the rest appear only in illustrative examples and are configuration, not specification — see [docs/04-analysis-engine/EDGE_CASES/](docs/04-analysis-engine/EDGE_CASES/).

**Before naming any state value, read [docs/02-legal-domain/DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md).** It is the canonical cross-layer reference for all five controlled state vocabularies. Mapping State, Finding Classification, Rule Outcome, Legal Decision, and Review Lifecycle are five separate axes and must never share a status field or enum — `AMBIGUOUS` in particular means three different things on three different layers.

Conflicts C-01–C-04 were reconciled on 2026-08-16 (`REC-01`–`REC-07`); **C-09** was resolved on 2026-08-17 by `IMPL-01` and AB-2, and **C-11** by `REC-08` (CI/CD tooling is GitHub Actions). **`REC-09`** (2026-08-17) defines Step 24 r6's "explicit Legal scope" and resolves finding **`F-6`** — before it, a Legal Reviewer could reach no Review at all. **Six remain open** in [CONFLICTS.md](docs/00-project/CONFLICTS.md): C-05–C-08 (low), **C-10 (MEDIUM)**, and **C-12** (low; Step 39 names Playwright while 54.7 lists framework selection as NOT YET SPECIFIED — registered, and blocking nothing). `REC-01`–`REC-07` are recorded in `all_lock.md` under "Post-Step-44 Cross-Document Reconciliation Decisions"; `REC-08` and `REC-09` each carry their own lock record appended after AB-2.

The security track's `OD-1`–`OD-15` are open decisions, of which `OD-9` (authentication) was closed by Step 47. The rest are tracked in [EXTERNAL_REFERENCE_AUDIT.md](docs/00-project/EXTERNAL_REFERENCE_AUDIT.md) §16 — do not resolve one yourself.

---

## Working a session

1. **Re-check [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) against the tail of [all_lock.md](all_lock.md).** The master specification grows as steps are locked and the docs tree can lag behind it. `all_lock.md` is currently **15,358 lines**; if it is longer, the docs may be stale and you should say so.
2. **Look the question up before deriving it.** Registry → status → conflicts → glossary → the specification. Re-deriving a settled question from `all_lock.md` wastes the session and risks a different answer than the one that is locked.
3. **Check what already exists before building or asking** — rule 23. Read the status, handoff and changelog records first; verify with a grep or a test run; and look in [Source material](#source-material) before requesting a document.
4. **Ask when blocked; do not proceed on an assumption.** Stop and request a decision when the behavior is unspecified (rule 4), a locked decision would have to change (rule 6), two sources contradict (rule 5), or real legal source material is missing (rule 21). Deliver everything that does not depend on the answer, and state plainly what you left out and why.
5. **Keep the record in sync.** A specification change lands as one synchronized operation — `all_lock.md` appended, plus the registry, status, conflicts and every affected specification. Record repository changes in [CHANGELOG.md](CHANGELOG.md) and decisions in `all_lock.md` and the registry; the two are not interchangeable. When you add a document, add it to [docs/README.md](docs/README.md) in the same change.
6. **Say what you actually did.** Report a discrepancy you found even when it is inconvenient, and never describe work as complete when part of it was skipped or blocked.

**Approval is required for:** beginning implementation · changing any locked decision · resolving an open conflict or `OD-*` · adding a technology, dependency or service · altering a domain boundary · changing a golden-corpus expectation. [CONTRIBUTING.md](CONTRIBUTING.md) has the procedure and the six kinds of change.

Once implementation is authorized, the constraints in [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §6 do not relax, and the recommended build sequence is in §5.

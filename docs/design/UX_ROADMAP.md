# UX_ROADMAP.md — Implementation Sequence

**Status: `PROPOSAL` — awaiting explicit approval before Phase 1 begins. Governed by [../../DESIGN.md](../../DESIGN.md).**

**Read this before starting any page work.** This roadmap governs a **retrofit**, not a build. Every page listed already exists, is permission-gated correctly, and is covered by tests — see [UX_AUDIT.md](UX_AUDIT.md) §1.2. The work ahead is applying a deliberately-chosen visual and component system to a correct, already-implemented information architecture, and improving specific interaction gaps identified in the audit — never re-deriving what pages should exist or what data they should show.

**The rule for every phase below: one milestone at a time, explicit approval before the next.** Completing a page is not implicit approval for the next page.

---

## Phase 0 — Discovery (this phase, complete)

Delivered: repository and existing-frontend inspection, the five-axis domain model and role/permission model as they constrain UI, a current-state UX audit ([UX_AUDIT.md](UX_AUDIT.md)), a persistent design-governance document ([../../DESIGN.md](../../DESIGN.md)), three explored interaction directions for the core review workflow with a recommendation ([DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) DD-1), and this roadmap. No code, styling, dependency, or route changes were made.

---

## Phase 1 — Design Foundation (before any page is touched)

**Goal:** make the visual and component decisions once, reviewed once, so every subsequent page consumes settled tokens and primitives instead of inventing its own.

Deliverables (each needs sign-off before Phase 2):
1. **Token set**: color (mapped explicitly onto the five state axes + two emphasis levels — see `DESIGN.md` § Visual principles), type scale, spacing scale, radius/border convention. Extends, does not replace, the existing `--ink`/`--muted`/`--line`/`--surface`/`--attention`/`--error` variables where they're already correct.
2. **Component primitives**, built to close the concrete gaps §1.3 of the audit identified: `Badge` (namespaced per state axis, never unified across axes), `Table` (real semantics, reusable across the six list pages), a shared pagination pattern, `Card`, form field primitives (label/error association for accessibility).
3. **No new dependency without approval** (rule 19) — these are built as plain React/CSS components consistent with the existing "no framework" decision, unless Phase 1 review explicitly decides otherwise and that decision is logged in `DESIGN_DECISIONS.md`.
4. **Accessibility floor verification tooling decision** — pick how the [DESIGN.md](../../DESIGN.md) § Accessibility principles get checked (automated audit in CI, manual checklist, or both) before it's needed on a real page.

**Dependency reason this comes first:** every page below consumes these tokens/primitives; building a page before this phase means redoing that page's styling once the system exists.

---

## Phase 2 — Application Shell

**Goal:** `Chrome.tsx`, global nav, and the shared states (`Loading`, `EmptyState`, `ErrorBanner`, `AccessRestricted`, `Pager`) get the Phase 1 system applied first, since every other page renders inside them.

**Dependency reason:** every page inherits the shell and the shared state components; restyling the shell after pages exist means every page shifts twice.

---

## Phase 3 onward — Individual pages, in sequence

Ordered by UX/technical dependency — which pages establish a pattern others need, and which are lowest-risk to prove the foundation against before the highest-stakes screen.

### 3.1 — `/login` — ✅ APPROVED (owner, 2026-08-21)

Delivered as DD-2 (behavior/hierarchy) + DD-3 ("The Reading" visual identity) + the DD-3 copy-pass addendum, all in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md). The next milestone (3.2 — `/contracts`) requires its own explicit approval before work begins.

- **Purpose:** authenticate.
- **Target user:** any user, unauthenticated.
- **Primary task:** sign in.
- **Major UX challenge:** none structurally — its value here is as a cheap, standalone proving ground for typography, form-field, button, and error-banner primitives before they meet a data-dense screen.
- **Dependencies:** Phase 1 tokens/primitives only — no `Chrome`, no permission model.
- **Reusable components required:** form field, button, `ErrorBanner`.
- **Important states:** idle, submitting (`busy`), error (identical wording for bad credentials vs. disabled account — S-7 must not regress).
- **Responsive considerations:** trivial (single narrow form); useful smoke test for the type scale at small widths.
- **Accessibility considerations:** label/error association, focus on first field, error announced to assistive tech.
- **Why here:** lowest risk, no dependencies, validates the foundation cheaply before the shell-wrapped pages.

### 3.2 — `/contracts` — DELIVERED 2026-08-21, awaiting owner review

Delivered under DD-5's finish standard and its theme resolution (light workspace + deep-navy identity topbar): the shell topbar restyled app-wide (navy, serif wordmark, accent-vivid active underline), serif page titles, `.table-card` finish (header band, row hover, status pills, date-only formatting), `.form-row` create card with `.field` primitives and the first light-surface `.btn--primary` (`--accent`). Logic, API calls, and permission gating untouched; validated by typecheck, 58/58 Vitest, build, and mocked-API screenshots at 1440/375 including the empty state.

### 3.2 (original spec) — `/contracts`

- **Purpose:** list and create contracts.
- **Target user:** User role (own contracts), Legal/Admin (scoped).
- **Primary task:** find or start a contract.
- **Major UX challenge:** first real use of `Table`/`Pager`/status `Badge` at genuine data density.
- **Dependencies:** Phase 2 shell; Phase 1 `Table`, `Pager`, `Badge`, `Card`.
- **Reusable components required:** `Table`, `Pager`, `Badge` (contract status), create form.
- **Important states:** loading, empty (with a real call to action), paginated, create-form validation/error.
- **Responsive considerations:** first real table-overflow decision (horizontal scroll vs. column priority) — set the pattern here, don't re-decide it per page.
- **Accessibility considerations:** real `<table>` semantics; create form field/error association.
- **Why here:** proves `Table`/`Pager`/`Badge` at low stakes (contract status has only three values) before Findings/Evaluations, which are far higher-stakes uses of the same primitives.

### 3.3 + 3.4 — DELIVERED 2026-08-21 (batched; owner: "go with the roadmap"), awaiting review

`/contracts/[contractId]`: back-link + serif title + type/status pill meta row, finished upload card (`.form-row`/`.field`), reviews `.table-card` with lifecycle pills, start-review card with labeled id fields. `/reviews`: filter card with labeled select, `.table-card` with lifecycle pills (neutral; `ANALYSIS_FAILED` error-tinted, `CANCELLED` muted), date-only display, and the filtered-empty vs true-empty distinction this roadmap flagged. Logic/API untouched. Validated: typecheck, 58/58 Vitest, build, and a REAL end-to-end browser pass (login as test user → create contract → upload the structural fixture → screenshots of list/detail/uploaded/reviews/filtered-empty).

### 3.3 (original spec) — `/contracts/[contractId]`

- **Purpose:** contract detail — document versions, upload, reviews, start a review.
- **Target user:** User (own), Legal/Admin (scoped).
- **Primary task:** upload a document version and start its review, or check prior versions/reviews.
- **Major UX challenge:** the upload flow's diagnostics/duplicate-detection messaging is currently ephemeral (lost on reload) — worth a deliberate, non-legal-content UX improvement here (persist per-document-version diagnostics), flagged in the audit.
- **Dependencies:** 3.2's `Table`/`Badge`; Phase 1 file-upload/status affordances (new primitive).
- **Reusable components required:** `Table` (versions, reviews), `Badge` (processing/extraction status), upload control.
- **Important states:** upload busy, duplicate detected, extraction diagnostics, empty reviews list.
- **Responsive considerations:** same table pattern as 3.2.
- **Accessibility considerations:** upload progress/result announced; file input has a real accessible label.
- **Why here:** extends 3.2's patterns immediately, and is a prerequisite step (upload → review) before the review-detail screen makes sense to design against real data.

### 3.4 — `/reviews`

- **Purpose:** list reviews (own + Legal-assigned), filter by status.
- **Target user:** User, Legal Reviewer/Admin.
- **Primary task:** find a review to open.
- **Major UX challenge:** none new — deliberately placed here as a second, near-zero-cost proof of the `Table`/`Pager`/`Badge`/filter pattern (9-value status enum) before the highest-complexity screen.
- **Dependencies:** 3.2's patterns directly.
- **Reusable components required:** `Table`, `Pager`, `Badge` (review lifecycle status), filter control.
- **Important states:** loading, empty, paginated, filtered-empty ("no reviews match this filter" vs. "no reviews at all" — currently not distinguished; worth fixing here).
- **Responsive considerations:** same table pattern.
- **Accessibility considerations:** filter control keyboard-operable, result count announced on filter change.
- **Why here:** cheapest possible dry run of a *filtered* list before the review-detail screen's much higher-stakes filtering (by classification / needs-decision).

### 3.5 — `/reviews/[reviewId]` — the core screen

- **Purpose:** inspect Findings → Evaluations → Evidence and record Legal Decisions.
- **Target user:** all roles, each seeing a structurally different view (confidentiality omission).
- **Primary task:** for a User — understand what was found; for Legal — decide what needs deciding.
- **Major UX challenge:** the whole reason Phase 0 explored three interaction directions ([DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) DD-1) — this is where the scalability finding and the escalation-vs-decision visual-distinction finding both land, and where the DD-1 direction (once approved) is actually built.
- **Dependencies:** every primitive built so far (`Table`/`Badge`/`Pager`/disclosure), plus new ones specific to this screen: attention treatment, evidence disclosure, decision form with explicit conflict state, decision history.
- **Reusable components required:** `FindingCard`/list-row (per DD-1's outcome), `EvaluationRow`, `EvidenceList`, `DecisionPanel`, `DecisionHistory`, `Badge` (three separate axes: classification, rule outcome, decision).
- **Important states:** loading (per-section, ideally announced), empty-with-analyse-CTA, analysis queued/polling (with the audit's flagged retry gap addressed), per-Evaluation attention, decision idle/submitting/recorded/conflict/error, escalated.
- **Responsive considerations:** if DD-1's hybrid (split-pane) direction is approved, this is where single-pane collapse behavior must be explicitly designed, not improvised.
- **Accessibility considerations:** disclosure widgets, live-region announcements for serial loading, focus management when moving between list and detail (if split-pane).
- **Why here:** deliberately not first — it is the highest-complexity, highest-stakes screen, and every primitive it needs has been proven at lower stakes on 3.2–3.4 first.

### 3.6 — `/reviews/[reviewId]/report`

- **Purpose:** aggregate picture of one Review — coverage, counts, alignment ratio.
- **Target user:** User, Legal.
- **Primary task:** get the summary without opening every Finding.
- **Major UX challenge:** presenting real counts without inventing a risk/severity rollup (see `DESIGN.md` Anti-patterns).
- **Dependencies:** 3.5's classification/status vocabulary and `Badge` set, reused directly.
- **Reusable components required:** `Badge`, simple count/ratio display (no chart unless one earns its place — most of these numbers are better as labeled figures than a chart).
- **Important states:** loading, error; no meaningful empty state (a Review always has a report once analysed).
- **Responsive considerations:** low — mostly text/numbers.
- **Accessibility considerations:** numeric summaries need clear text labels, not color-only meaning.
- **Why here:** directly depends on 3.5's finalized classification/status badge set; sequencing it earlier would mean redoing it once 3.5 lands.

### 3.7 — `/configuration`

- **Purpose:** Legal Admin manages Requirements, Company Standards, Legal Rule versions; draft → publish.
- **Target user:** Legal Admin only.
- **Primary task:** draft a new Requirement/Standard version, publish a configuration snapshot.
- **Major UX challenge:** JSON-textarea editing has no structural validation before submit (audit finding). A **presentation-only** improvement (syntax highlighting, bracket matching, JSON-shape validation) is legitimate here without violating rule 21/7 — it never authors or suggests legal content, only catches malformed structure before the network round-trip.
- **Dependencies:** `Table`/`Card`/`Badge` from earlier phases; a new (structural-only) JSON-editing affordance.
- **Reusable components required:** `Table` (requirement list, versions), form primitives, the new JSON editor affordance.
- **Important states:** loading, empty (with the existing explanatory copy about V1 shipping no default Requirements), per-card lazy detail loading, publish result summary, malformed-JSON caught client-side before submit.
- **Responsive considerations:** low priority — admin-only, low-traffic, desk-bound by nature.
- **Accessibility considerations:** editor affordance must remain keyboard-operable if a richer JSON widget is introduced.
- **Why here:** independent of the Review/Finding chain, lower traffic, safe to sequence after the core workflow rather than before it.

### 3.8 — `/audit`

- **Purpose:** read-only, append-only audit trail.
- **Target user:** Super Admin.
- **Primary task:** investigate an action.
- **Major UX challenge:** none structural — straightforward table-and-filter screen; the one real design question is presenting `before_state`/`after_state` diffs legibly when present.
- **Dependencies:** `Table`/`Pager`/filter pattern from 3.2/3.4, reused directly.
- **Reusable components required:** `Table`, `Pager`, filter controls, a before/after state display (new, small primitive).
- **Important states:** loading, empty, paginated, filtered.
- **Responsive considerations:** table-overflow pattern already settled by 3.2.
- **Accessibility considerations:** diff display must convey change through text, not only color.
- **Why here:** low risk, fully reuses established list-page patterns; no reason to sequence earlier.

### 3.9 — `/admin`

- **Purpose:** user and role administration.
- **Target user:** Super Admin.
- **Primary task:** create a user, grant/revoke a role.
- **Major UX challenge:** making `Role.confers_legal_authority` visually unmistakable when granting a role — this is the one place a UI mistake could look like it grants legal authority when the underlying permission grant is what actually matters (server-authoritative either way, but the UI should not mislead an admin about what they're granting).
- **Dependencies:** `Table`, form primitives, a `Badge`/flag for "confers legal authority."
- **Reusable components required:** `Table` (users, roles), grant/revoke form, legal-authority flag treatment.
- **Important states:** loading×2 (users/roles independently), empty, per-row grant/revoke busy/error.
- **Responsive considerations:** low priority, admin-only.
- **Accessibility considerations:** the legal-authority flag must not rely on color alone (ties to `DESIGN.md` § Accessibility).
- **Why here:** independent, low-traffic, safe to sequence last among the built screens.

### Deferred — report export

Not sequenced. `POST /reviews/{id}/export` does not exist and export formats are `NOT YET SPECIFIED` (49.12). Do not design this screen until that backend/spec gap is closed by an owner decision — designing ahead of an unspecified format would mean inventing behavior (rule 4).

---

## First milestone recommendation

**Phase 1 (Design Foundation) + Phase 2 (Application Shell) together are the actual first milestone** — not a page, but the prerequisite every page consumes. Within that milestone, `/login` (§3.1) is the first *page* actually touched, because it is the cheapest possible real-world test of the new type/form/button/error primitives, with zero permission-model or data-density complexity to confound the review.

**Do not start with `/reviews/[reviewId]`,** despite it being the product's most important screen — it is precisely because it's the most important and highest-risk screen that it should be attempted only after every primitive it needs has been proven on lower-stakes pages (3.2–3.4), and only after DD-1's interaction-model question has an explicit answer.

**Stop condition, restated:** this roadmap is a proposal. No page in Phase 3, and no primitive in Phase 1, gets implemented until this roadmap and DD-1 are explicitly approved, and even then, one milestone at a time with review before the next.

# UX_AUDIT.md — Current-State UX Audit (Phase 0)

**Status: `ANALYSIS` — a point-in-time record of what exists and what was found. Decides nothing by itself; outcomes that require a decision are recorded in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) or the [UX_ROADMAP.md](UX_ROADMAP.md).**

Governed by [../../DESIGN.md](../../DESIGN.md). Produced 2026-08-21 as part of the Phase 0 design-governance discovery pass, per repository rule 23: this audits and builds on the frontend that already exists — it does not propose rebuilding it.

---

## 1. Existing UI/UX architecture

### 1.1 Stack and constraints already settled

Next.js 16 / React 19 / TypeScript, no component library, no CSS framework, no client-state library, one plain stylesheet (`frontend/src/app/globals.css`). This was a **deliberate non-decision**, documented in `frontend/README.md`: adding one without approval would "quietly make it the project's answer to a question the owner has not decided" (Step 52.6). All data access goes through `frontend/src/lib/api.ts` — no page talks to the database or derives legal state client-side.

### 1.2 Page inventory (as built)

| Route | Purpose | Permission gate |
|---|---|---|
| `/` | Redirects to `/contracts` | none |
| `/login` | Password-fallback sign-in | none (public) |
| `/contracts` | List + create contracts | `CONTRACT_VIEW` (page), `CONTRACT_CREATE` (form) |
| `/contracts/[contractId]` | Contract detail: document versions, upload, reviews, start review | `CONTRACT_VIEW`; `DOCUMENT_UPLOAD`, `REVIEW_CREATE`, `DOCUMENT_DOWNLOAD` on controls |
| `/reviews` | List reviews (own + Legal-assigned), status filter | `REVIEW_VIEW` |
| `/reviews/[reviewId]` | **The core screen** — Review status, Findings → Evaluations, evidence, decisions, escalation, run-analysis | `REVIEW_VIEW` (page), `FINDING_VIEW` (inner), `REVIEW_CREATE` (analyse control) |
| `/reviews/[reviewId]/report` | Aggregate report: coverage, classification/status counts, alignment ratio, unmatched provisions | `REPORT_VIEW` |
| `/configuration` | Requirements / Company Standards admin: draft, version, publish | `CONFIGURATION_VIEW` (page), `CONFIGURATION_DRAFT`/`CONFIGURATION_PUBLISH` (controls) |
| `/audit` | Read-only append-only audit trail, filterable | `AUDIT_VIEW` |
| `/admin` | Users & roles administration | `USER_MANAGE` and/or `ROLE_MANAGE` |

The only locked (52.6) screen **not** built is report export — correctly deferred, because export formats are `NOT YET SPECIFIED` (49.12). This is not a gap in this audit's scope; it is a documented, deliberate absence.

### 1.3 Component inventory (as built)

`Chrome` (shell/nav/sign-out) → wraps every route but bare `/login`. `AccessRestricted` + `PermissionGate` (whole-section vs. per-control gating). `Feedback.tsx` (`ErrorBanner`, `Loading`, `EmptyState`, `Pager` — reused on every page). `FindingCard` → `EvaluationRow` (× N) → `EvidenceList`, and `EvaluationRow` → `DecisionPanel` → `DecisionHistory` — the only nested-composition chain in the app, and the one that carries the product's central relationship (Finding → Evaluation → Evidence/Decision).

**No shared `<Badge>`, `<Table>`, `<Modal>`, `<Tabs>`, or `<Toast>` component exists.** Status/classification/outcome/tag rendering is inline `className` string interpolation, repeated across four files. Six pages hand-roll `<table>` markup with no shared abstraction. This is the concrete, low-risk place a component library or set of primitives should start.

### 1.4 Permission and confidentiality model as implemented

`GET /auth/session` returns a flat effective-permission array; `session.tsx`'s `can(permission)` decides what renders. Confidential fields (`rule_outcome`, thresholds, `rule_configuration`) are omitted from the API response entirely for callers without `legal_position.view` — `EvaluationRow` renders by presence-testing each field, never by permission-testing, so the omission is structural, not a UI mask. This is verified by Playwright (`confidentiality.spec.ts`) and Vitest (`confidentiality.test.tsx`) and must be preserved exactly by any redesign.

### 1.5 Existing informal visual conventions

CSS variables: `--ink`, `--muted`, `--line`, `--surface`, `--page`, `--attention`/`--attention-bg`, `--error`/`--error-bg` — the entire token set today. `.card` (bordered surface), `form.inline`, and a badge/status/outcome/tag family that is *intentionally* namespaced per state axis rather than unified. Only two emphasis colors exist app-wide (amber = attention/needs-decision, red = error/conflict); green and purple appear only inside the classification badge palette. No dark mode, no responsive breakpoints, no motion. DOM class names double as Playwright/Vitest selectors (`.decision__conflict`, `li.evaluation`, `[data-scope]`, etc.) — any visual redesign must update these in lockstep with the test suites, not as an afterthought.

---

## 2. UX problems (audited against the ten dimensions)

| Dimension | Finding |
|---|---|
| **Information Architecture** | Sound. Contract → Document Version → Review → Finding → Evaluation is a faithful, linear reflection of the domain model; no invented groupings. |
| **Navigation** | Minimal but functional — top nav filtered by permission. No breadcrumb pattern; the report page has one hand-written "back to findings" link and nothing else models the Contract → Review → Report chain visually. |
| **Visual Hierarchy** | Currently flat — everything is roughly the same weight because there is, by design, almost no type/spacing scale yet. The one locked exception (`.evaluation--attention`) works, but nothing else in the hierarchy is visually reinforced. |
| **Interaction** | Efficient in principle (direct drill-down, no unnecessary modals) but has real friction: JSON-textarea configuration editing with no structural validation before submit; a 60-second analysis-poll timeout with no manual retry button; no keyboard-driven triage across Findings/Evaluations. |
| **Cognitive Load** | The Review screen loads Review → Findings → (per Finding) Evaluations → Evidence serially, each with its own "Loading…" line — for a dense Review this can read as a slow trickle rather than one page settling. Escalation controls (Finding-level) and Decision controls (Evaluation-level) currently look like the same kind of button despite being different kinds of authority — the single UX finding most worth fixing early. |
| **Legal Comprehension** | Strong at the data level — a Finding never renders `classification` without its Evaluations, evidence is always shown or explicitly stated absent, OCR-sourced evidence is labelled. Weak at the visual level — nothing yet distinguishes "this needs a decision" from "this is fine" beyond one border-color rule. |
| **Trust** | High — evidence is always reachable, decisions require server confirmation before rendering (no optimism), decision history shows superseded entries rather than hiding them. This is the area least in need of redesign; a visual system should protect it, not "modernize" it away. |
| **Permission Awareness** | Correct and deliberately conservative — controls vanish rather than disable, whole sections show `AccessRestricted` rather than partial/broken content. One rough edge: a brand-new user with zero granted permissions lands on `/contracts` and sees only `AccessRestricted` with no explanation of who to contact — likely acceptable (accounts are administrator-provisioned) but worth a documented decision rather than an accident. |
| **State Management** | Loading/empty/error states exist everywhere but are visually uniform to the point of being hard to tell apart at a glance (`<p className="hint">Loading …</p>` for all of them). No skeleton/shimmer states — acceptable per Anti-patterns in `DESIGN.md`, but the plain-text loading state should still be made visually distinct per state (loading vs. empty vs. error) rather than relying on the reader parsing the sentence. |
| **Scalability** | This is the audit's most material finding. The current expandable-list pattern for Findings (`FindingCard` per Finding, all rendered) has no tested upper bound. The product must explicitly support "hundreds of Findings" per Review (per this task's own brief) and there is currently no virtualization, no default "needs decision" filter view, and no persistent list-context while inspecting one Finding's detail. This directly motivates the interaction-model exploration in [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md). |
| **Accessibility** | Untested territory — no target declared, no automated a11y check in the test suite today. Markup is plain semantic HTML in most places (a reasonable starting point), but disclosure widgets, live-region loading announcements, and focus management on drill-down navigation have not been verified. |
| **Responsive behavior** | No breakpoints exist. Tables would overflow uncontrolled on a narrow viewport today. Given the primary usage context (desk-bound legal review of dense tabular data), this is a real but lower-urgency gap — see Responsive principles in `DESIGN.md`. |

---

## 3. User workflow map

Only workflows attested by the locked product/security specification are listed — none invented.

| Workflow | Role | Entry point | Goal | Required info | Primary action | Decision points | Permission boundary | Success | Failure |
|---|---|---|---|---|---|---|---|---|---|
| Upload & start review | User | `/contracts/[id]` | Get a counterparty document analyzed | Contract, document file | Upload document version → create Review | Which document version to review | `DOCUMENT_UPLOAD`, `REVIEW_CREATE` | Review created, moves to `PROCESSING` | Upload rejected (diagnostics shown), duplicate detected |
| Run analysis | User / Legal | `/reviews/[id]` | Produce Findings for a processed Review | Review in an analysable status | Trigger "Analyse" | Whether to re-trigger (blocked if already analysed) | `REVIEW_CREATE` | Findings appear | `ANALYSIS_FAILED` shown distinctly from `UNABLE_TO_EVALUATE` |
| Browse findings & evidence | User / Legal | `/reviews/[id]` | Understand what was found and why | Findings, Evaluations, Evidence | Expand a Finding, read evidence | Whether to escalate | `FINDING_VIEW`, `EVALUATION_VIEW` | User understands classification and evidence | Empty evidence correctly shown as absence, not error |
| Escalate a finding | User | `/reviews/[id]` | Ask Legal to look at something | The Finding in question, a reason | Submit escalation | None (request, not a ruling) | `REVIEW_VIEW` (any viewer may request) | Finding visible to Legal even post-resolution | No approve control ever appears for this actor |
| Legal review & decision | Legal Reviewer/Admin (explicit grant) | `/reviews/[id]` | Rule on a flagged Evaluation | Evaluation, its rule outcome, evidence, applicable rule | Submit a Legal Decision with justification | Which of 5 decision types; `APPROVE_CUSTOMIZATION` needs the extra grant | `LEGAL_DECISION` (+ `LEGAL_APPROVE_CUSTOMIZATION`) | Decision recorded, current in history | 409 version conflict shown, not silently resolved |
| View a report | User / Legal | `/reviews/[id]/report` | Get an aggregate picture of one Review | Coverage, classification/status counts, alignment ratio | Read | None | `REPORT_VIEW` | Accurate counts, no invented risk score | — |
| Manage legal configuration | Legal Admin | `/configuration` | Draft/publish Requirements, Company Standards, Legal Rules | Existing Requirement catalogue | Draft new version → publish snapshot | What to change; publishing is irreversible for that snapshot | `CONFIGURATION_DRAFT`, `CONFIGURATION_PUBLISH` | New snapshot published, existing Reviews unaffected | Malformed JSON caught before submit (currently weak — see §2) |
| Review audit trail | Super Admin | `/audit` | Investigate who did what, when | Action, entity type, before/after state | Filter and read | None (read-only) | `AUDIT_VIEW` | Complete, append-only record | — |
| Manage users & roles | Super Admin | `/admin` | Grant/revoke access | Users, roles, `confers_legal_authority` flag | Create user, grant/revoke role | Whether a role grants legal authority | `USER_MANAGE`, `ROLE_MANAGE` | Access reflects intended authority | Super Admin still cannot self-grant legal decision authority as a side effect |

---

## 4. Page inventory (categorized)

### Foundation
- Application shell / global navigation (`Chrome.tsx`)
- Authentication (`/login`)
- Shared states: loading, empty, error, access-restricted (`Feedback.tsx`, `AccessRestricted.tsx`)

### Core workflow
- Contract list + create (`/contracts`)
- Contract detail: upload, document versions, start review (`/contracts/[contractId]`)
- Review list (`/reviews`)
- Review detail: Findings → Evaluations → Evidence → Decisions, escalation (`/reviews/[reviewId]`)
- Report (`/reviews/[reviewId]/report`)

### Administration
- Legal configuration: Requirements, Company Standards, Legal Rules (`/configuration`)
- Audit trail (`/audit`)
- User & role management (`/admin`)

### Deferred, out of scope for this roadmap
- Report export — backend endpoint not implemented; formats `NOT YET SPECIFIED` (49.12). Do not design this until that gap is closed by an owner decision.

# DESIGN_DECISIONS.md — Design Decision Log

**Status: `ANALYSIS` for DD-1 (proposed, not yet approved). Governed by [../../DESIGN.md](../../DESIGN.md) § Design decision governance.**

This log records major, hard-to-reverse UI/UX decisions as they are made — one entry per decision, appended over time. A superseded entry is marked superseded in place, with a pointer to what replaced it; entries are never deleted or silently rewritten, in the same spirit as `all_lock.md`.

Each entry should be reviewed against the twelve questions in `CLAUDE.md`'s companion task brief (is this solving a real problem? is the hierarchy obvious? does it scale? etc.) before being proposed.

---

## DD-1 — Interaction model for the Findings review workflow

**Status:** `DECIDED` (owner approved the roadmap carrying this recommendation, 2026-08-21) and **realized in Phase 3.5** (2026-08-22) as direction C's essence — the needs-decision/all-findings view — layered on the preserved DOM; direction B's split-pane rail remains an open follow-up if finding volumes outgrow the single-page list. *(This status line was corrected on 2026-08-22 — it stale-read "PROPOSAL" after implementation had landed; flagged by the code review.)*

**Scope:** the `/reviews/[reviewId]` screen — the product's most important and highest-traffic workflow, where a user or Legal Reviewer inspects Findings, their nested Evaluations, evidence, and (for authorized users) records Legal Decisions.

**Why this needs a decision at all:** the [UX_AUDIT.md](UX_AUDIT.md) §2 Scalability finding is real — the current pattern renders every Finding as an expanded card with no default filter and no persistent list-context. The product brief requires this to work at "hundreds of Findings." That is a genuine, non-cosmetic UX problem worth solving deliberately rather than letting density grow until it breaks.

**Constraints every direction must satisfy (non-negotiable, from `CLAUDE.md` and Step 52.5):**
- A Finding is always expandable to its full set of Evaluations — never a single collapsed verdict.
- Decision controls attach to the Evaluation, never the Finding.
- `RESOLVED ≠ MATCH` stays visible.
- An Evaluation needing a decision (`requires_decision`) must be distinguishable by scanning.
- No optimistic UI for a Legal Decision; a 409 conflict must be shown, not absorbed.
- Confidential omission (no `legal_position.view`) must remain structural, not a client-side mask.

### Direction A — Expandable List (refine what exists today)

**Concept:** Findings render as a vertical list of cards; each expands to reveal its Evaluations; each Evaluation expands to Evidence and, where authorized, a Decision panel. This is the shape already implemented — Direction A is "keep the model, invest the visual-design budget in hierarchy and attention treatment only."

**Core interaction:** scroll and expand/collapse; no separate navigation state.

**Information hierarchy:** flat list, ordered by however the API returns Findings (currently creation order); attention is a per-card visual treatment.

**Navigation model:** single scrolling page; no persistent selection state.

**Strengths:** zero structural rework; fully compatible with the existing Playwright/Vitest suite's DOM assumptions; simplest to ship first; genuinely fine for a Review with a handful of Findings (the common case today, since the golden corpus and current usage are both small).

**Weaknesses:** does not solve the scalability finding — a Review with hundreds of Findings becomes a very long page with no way to jump straight to what needs a decision without scanning past everything else; no durable sense of "where am I in the queue" while reading one Finding's detail; re-finding a specific Finding after navigating away means re-scrolling.

**Scalability:** poor beyond roughly dozens of Findings without an added filter/jump mechanism bolted on top (which begins to reinvent Direction B piecemeal).

**Cognitive load:** low per-item, but rises with total Review size since there's no way to bound what's on screen.

**Implementation implications:** lowest cost; no routing changes; existing components (`FindingCard`, `EvaluationRow`, `EvidenceList`, `DecisionPanel`, `DecisionHistory`) are reused directly, just restyled.

### Direction B — Split-pane Workbench (master-detail)

**Concept:** a filterable, sortable list of Findings in a left rail (compact row: requirement code, classification badge, attention flag) and a full detail pane on the right for whichever Finding is selected — the familiar shape of a triage tool (issue tracker, ticket queue), justified here not by imitation but by the actual need: a reviewer moving through many Findings without losing their place.

**Core interaction:** select a row → full detail renders in place; keyboard next/previous moves through the filtered list without a page navigation.

**Information hierarchy:** list rail carries only the state axes needed to triage (classification, attention); detail pane carries the full Evidence → Fact → Standard → Rule → Result chain for the selected Finding.

**Navigation model:** two-pane, URL-addressable selection (so a specific Finding is still linkable/shareable), collapsing to a single pane on narrow viewports (list first, detail as a drill-in).

**Strengths:** genuinely solves the scalability problem — list stays bounded and scannable regardless of Review size; persistent context while inspecting detail; natural home for filters (by classification, by "needs decision"); keyboard-friendly triage.

**Weaknesses:** materially more implementation cost (two synchronized panes, selection state, responsive collapse behavior to define); risks reading as a generic "inbox" pattern if the detail pane doesn't keep the evidence chain as the visual star; narrow-viewport behavior needs its own explicit design.

**Scalability:** good — this is the direction's whole reason for existing.

**Cognitive load:** lower than A at scale (bounded list, one Finding's detail at a time); slightly higher up front (two regions to learn instead of one linear page).

**Implementation implications:** `EvaluationRow`/`EvidenceList`/`DecisionPanel`/`DecisionHistory` are reused inside the detail pane largely as-is; `FindingCard` is effectively replaced by a compact list-row component plus a detail-pane wrapper; needs new routing/selection state and a defined mobile/narrow collapse.

### Direction C — Decision Queue (task-first, attention-led)

**Concept:** the default view surfaces only the Evaluations that currently `requires_decision`, one focused decision at a time (or a short worklist), with the clause's evidence, the Company Standard, and the applicable Legal Rule shown together as the reason a decision is needed — directly realizing the brief's suggested relationship (Finding → Actual Clause → Expected Standard → Difference → Evidence → Decision). A separate, clearly-labeled "All Findings" view remains for browsing every classification, including MATCH, for completeness and audit.

**Core interaction:** work the queue; each decision advances to the next item; the full-findings view is one click away, never hidden.

**Information hierarchy:** the queue view leads with exactly the fields needed to decide; nothing else competes for attention on that screen.

**Navigation model:** a queue (primary) plus a full list (secondary) — two distinct, purpose-built views of the same underlying Evaluations rather than one view trying to serve both jobs.

**Strengths:** directly optimizes for the actual V1 bottleneck task — per [DESIGN.md](../../DESIGN.md) § Legal-specific UX principles, the zero-tolerance rule means most deviations need a decision today, so a queue that can't be missed is a strong error-prevention win; lowest cognitive load per decision; the clearest realization of "innovation must improve decision-making," not novelty for its own sake.

**Weaknesses:** an ordinary User (not Legal) mostly wants to browse everything, not decide anything — the queue framing serves Legal Reviewers well and User-role browsing less well unless the "All Findings" view is given equal navigational weight, not treated as an afterthought; could understate the full picture of a Review if the queue is mistaken for the whole Review.

**Scalability:** excellent for the decision task specifically (queue length is bounded by what actually needs deciding, typically far smaller than total Finding count); the secondary full-list view still needs Direction A or B's scalability answer underneath it.

**Cognitive load:** lowest per decision; requires care so it doesn't feel like it's hiding information from a browsing (non-deciding) user.

**Implementation implications:** highest conceptual departure from what exists; needs a new "queue" query/view (likely just a `requires_decision=true` filter over the existing findings endpoint — no new backend concept), a dedicated queue UI, and the existing components reused inside each queue item's detail; the "All Findings" view still needs an answer to the Direction A/B scalability question underneath it.

### Recommendation

**Adopt a hybrid: Direction B's structural navigation (bounded list + persistent detail pane, so the product scales past today's small Reviews) with Direction C's default framing (the list rail defaults to "needs a decision," not alphabetical/creation order, and the queue is the primary entry point for a Legal Reviewer) — while keeping an explicit, equally-weighted toggle to the full, unfiltered Finding list so no user ever mistakes the queue for the whole Review.**

Reasoning: Direction A is the lowest-risk choice but does not solve the audit's central scalability finding and would need bolted-on filtering to survive contact with a large Review anyway — at that point it has quietly become a worse version of B. Direction C alone best matches the *current* legal-policy reality (almost everything needs a decision) but risks under-serving the ordinary User's simpler "browse what was found" need, and still needs a scalable list underneath it. The hybrid keeps Direction C's genuine innovation — a task-first queue that embodies the Evidence → Fact → Standard → Rule → Result → Decision chain as one continuous act — without sacrificing Direction B's answer to scale, and without removing the complete, honest view of every Finding that legal auditability requires.

This is a proposal, not a decision: it changes a screen already covered by a locked structural spec (52.5) and an existing Playwright/Vitest suite, so it should be named explicitly and approved (per `CLAUDE.md` rule 6 in spirit, even though 52.5's structural guarantees — not its exact layout — are what's actually locked) before Phase 3 implementation reaches this screen. See [UX_ROADMAP.md](UX_ROADMAP.md) for where this lands in the build sequence.

---

## DD-2 — `/login` layout direction: restrained single-column, task-first hierarchy

**Status:** `IMPLEMENTED` (2026-08-21, Phase 3.1 of [UX_ROADMAP.md](UX_ROADMAP.md)).

**Scope:** the `/login` page only — but it sets the precedent for how a "single focused task" page carries the design system.

**Directions considered:**

- **A — Centered authentication card** (vertically/horizontally centered panel on the page background): the conventional SaaS shape. Rejected: vertical centering adds no information and moves the form further from the top of the tab order's natural reading position; it also reads as generic-SaaS, which [../../DESIGN.md](../../DESIGN.md) § Design philosophy explicitly avoids where the convention isn't earning its place.
- **B — Split workspace** (brand/positioning panel beside the form): rejected outright — LegalMind is an internal tool with no marketing job to do on its own login page; a positioning panel would be pure decoration (Anti-patterns: "visual decoration without functional purpose").
- **C — Restrained top-anchored column** (chosen): keep the existing `.shell--bare` narrow column, top-anchored like a document, and spend the effort on hierarchy: a small, quiet wordmark → the task heading ("Sign in") → the one piece of load-bearing context (SSO-fallback note) → the form → the provisioning note. No new layout machinery at all.

**Why C:** the user is a repeat internal user who wants the credential fields immediately; every element on the page already existed and is real information — the design problem was *order and weight*, not missing or excess content. C is also the cheapest to build and the most honest validation of the Phase 1 foundation, which was the milestone's actual purpose.

**Hierarchy decision worth recording:** the page's `<h1>` is now **"Sign in" (the task), not "LegalMind" (the product)** — the wordmark is a small-caps muted label above it (`.login__brand`). A screen reader announces the page's purpose rather than its brand, and the visual weight follows the same order. **Precedent:** on any focused-task page, the task is the heading; the product name is chrome.

**Also decided here, deliberately:**
- The submit button is the page's first `.btn--primary` — establishing "exactly one primary action per screen" in practice.
- Authentication failure styles **no field as individually invalid** — S-7 returns one indistinguishable answer for unknown account / wrong credential / disabled account, and per-field error styling would visually contradict that guarantee. `.field--invalid` remains reserved for client-detectable structural invalidity only.
- `autoFocus` on the email field: a login page has exactly one purpose; focusing its first field removes one keystroke/click for every session with no downside on a page with nothing else to read first. (Not a general precedent — on content pages autofocus steals the reading position and should not be copied.)
- A `.visually-hidden` live region announces "Signing in…" — the pattern for announcing a busy state that has no dedicated visible element; documented in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

---

## DD-3 — `/login` visual identity: "The Reading" (supersedes DD-2's composition; DD-2's behavioral decisions stand)

**Status:** `IMPLEMENTED` (2026-08-21). Owner-directed creative pass: the DD-2 result was functionally right but visually generic; the brief asked for a purpose-built legal-tech identity with meaningful motion.

**What survives from DD-2 unchanged:** task-first hierarchy (h1 = "Sign in"), one `.btn--primary` per screen, no per-field invalid styling on auth failure (S-7), `autoFocus`, the `.visually-hidden` busy announcement, and all authentication behavior.

**Concepts explored:**
- **A — "The Reading"** (chosen): an asymmetric split. The left field is a deep-ink environment rendering an *abstracted contract being read* — serif clause numbers (§1…§5) down a margin, redaction-like text bars, two rows carrying the product's real evidence-excerpt left-border idiom (`.evidence__text`), a slow luminance scan travelling the page every 26s while clause numbers sequentially brighten as it passes, and the locked explanation chain (Evidence → Fact → Standard → Rule → Result) as small-caps microcopy at the base. The sign-in panel sits right, calm and dominant.
- **B — "Evidence Chain" diagram as hero:** conceptually pure but reads as a marketing slide once static; absorbed into A as the chain microcopy instead.
- **C — "Comparison field"** (ambient cells classifying match/deviation): **disqualified by our own governance** — it would spend state-axis colors (attention amber, match green) decoratively, which DESIGN.md § Visual principles forbids. The chosen environment speaks only in deep-surface neutrals.

**Why A:** the motion *is* the product — a deterministic system reading a document — so removing the animation would materially weaken the meaning, not just the polish (the brief's own test). The environment uses only material from LegalMind's real world: § numbering, the evidence-excerpt mark, the locked chain. Remove the wordmark and it is still unmistakably a legal-document-analysis product, not a generic SaaS.

**System extensions made (tokens, not one-offs):** `--ink-deep`/`--on-deep`/`--on-deep-muted`/`--on-deep-faint` (a generic deep-surface voice, available to future environment moments — deliberately not named `--login-*`); `--font-display` (Georgia system-serif stack — no dependency, rule 19 intact) for identity and single-task headings only; `--ease-out-soft`.

**Motion hierarchy as implemented:** background scan 26s loop + staggered clause attention (ambient) · doc layer and chain fade in once (identity) · panel content staggered 0.5s entrance (form) · error banner immediate 0.2s fade, deliberately exempt from the entrance stagger (feedback — a stagger delay left it invisible-but-present, caught and fixed in browser review) · focus/hover instant. All ambience is `aria-hidden`; `prefers-reduced-motion` removes the scan and every animation while preserving the full static composition.

**Composition note for reuse:** the deep-ink environment + white panel split is `/login`'s identity moment, not a template — content pages stay on the light shell. `Chrome`'s login branch now emits `shell--login` (full-viewport); `shell--bare` remains for loading/signed-out states.

**Addendum — copy directive (owner, 2026-08-21).** Every visible message must pass "does the user need this right now?" Removed under that test: the SSO-fallback paragraph (describes a mechanism the page does not offer — when OIDC ships it returns as a real control, not prose), the second sentence of the admin note (redundant restatement), and the explanation-chain microcopy (product messaging at the field's base; the environment now carries identity through composition alone). Kept: wordmark (orientation), "Sign in", labels, button, error banner, and one recovery line — "Accounts are created by an administrator." — the only next action available to a user without credentials on a page with no signup or reset flow. **Standing rule for future pages:** interface copy is limited to what the user needs for the task in front of them; product/legal/positioning prose is not used to fill space.

---

## DD-4 — `/login` visual identity: owner-supplied deep-navy workspace (supersedes DD-3's composition)

**Status:** `IMPLEMENTED` (2026-08-21). The owner supplied a concrete design (a Claude Design canvas export) and directed the page be redesigned to match it. DD-3's "Reading" composition is superseded; DD-2's behavioral decisions and the DD-3 copy addendum stand.

**What was implemented from the mock, faithfully:** full-viewport deep-navy environment (`oklch` palette) with floating document geometry — two drifting triangles (12s/14s), two static triangles, a hairline ring, a pulsing radial glow; a top bar with the serif wordmark; a centered glass card (`backdrop-filter`, 14px radius, deep shadow) with entrance animation; dark inputs with placeholders and a border+glow focus treatment; a Show/Hide password reveal (presentation-only, `aria-pressed`, accessible name); a vivid full-width submit (`--accent-vivid`) with an inline spinner while submitting; the error banner restyled to a dark red-tinted treatment (wording untouched — S-7); the admin note as the page footer.

**Deliberately NOT carried over from the mock — each names a capability the product does not have, and the owner's own creative brief forbade adding such controls:** "Forgot password?" (no reset flow exists), "Sign in with SSO" (OIDC routes unimplemented — a dead button), the Google account chip (no Google auth; also renders an identity the page cannot know pre-auth), "Request access" and "Learn what LegalMind does" links (no such flows; contradicts administrator-provisioned accounts), the mock's client-side email-format error messages (native validation + the server's single S-7 message remain the only feedback), and the marketing tagline as `h1` ("Smart legal review, built in." fails the standing copy rule; the task heading "Sign in" stays). Any of these can be added on explicit owner instruction, but they will be non-functional until their capability exists.

**Typography substitution:** the mock loads Source Serif 4 + Public Sans from Google Fonts. A runtime CDN font is a new dependency (rule 19) and leaks page loads to a third party from a confidential legal tool, so the closest system-resident faces are used: `--font-display` (Georgia stack) for wordmark/heading, the existing sans stack for UI. If the exact faces are wanted, `next/font` bundling is a one-line approval away.

**Token changes:** deep-surface family retinted from neutral to the mock's navy (`--ink-deep` etc. now `oklch`), plus `--surface-deep`, `--line-deep`, `--input-deep`, `--accent-vivid`. Consumed only by `/login`.

**Test lockstep:** the reveal control's accessible name ("Show password") made Playwright's substring `getByLabel("Password")` ambiguous; `auth.setup.ts` and `session.spec.ts` now pass `{ exact: true }` — selector disambiguation only, no behavioral change to what the specs assert.

**Motion:** ambience (floats, glow) slow and `aria-hidden`; card entrance one-time 0.55s; error fade immediate; spinner is feedback. Under `prefers-reduced-motion` every animation is removed and the spinner is hidden entirely (the button label carries the busy state).

**Addendum (owner, 2026-08-21) — three mock elements restored on explicit instruction:** the header link ("New here? Learn what LegalMind does", placeholder `#` — no product page exists), the card footer line ("Not a customer yet? Request access", placeholder `#` — no request flow exists), and a **"Sign in with Google"** control. The Google control is an `<a>` to the locked 49.2 OIDC entry route (`GET /api/v1/auth/oidc/start` → redirect to the identity provider): the backend does not implement the route yet, so clicking it fails today by owner acceptance, and it starts working with zero frontend changes the moment the OIDC backend (with Google as IdP) ships. It is generic — never "Sign in as <name>" — because the page cannot know the user before authentication. A follow-up owner instruction the same day also restored the mock's tagline as the card heading ("Smart legal review, built in." replaces "Sign in" as the `h1`) and enlarged the header wordmark (1.5rem) and header link (1rem). Still absent, not asked for: "Forgot password?", the generic "Sign in with SSO" outline button, and the "Login" label (the submit stays "Sign in").

---

## DD-5 — Standing quality bar: polished finish is mandatory on every page

**Status:** `DECIDED` (owner directive, 2026-08-21).

The owner's correction, recorded verbatim in spirit: *"no marketing copy" does not mean anything goes — whatever is built must show a proper finish.* The DD-4 `/login` page is the reference for that finish level: cohesive background theme, deliberate fonts and text sizes, exact alignment, polished controls. The Phase-3.1 first pass at `/login` (functionally correct but visually bare) is the named mistake that must not repeat on any later page.

**Application to Phase 3 pages going forward:** every page milestone is judged on finish as a first-class acceptance criterion, alongside correctness — not as an optional polish pass afterward. Copy stays disciplined (DD-3 addendum); execution must be at DD-4's level.

**Theme question — RESOLVED (owner: "go with your recommendation", 2026-08-21):** content pages keep a **light workspace** (dense legal tables and evidence text stay maximally legible), while the **application shell's top bar adopts the deep-navy identity** so the family look from `/login` carries through every page. Primary action color on light surfaces is `--accent` (#1b4f9c — same hue family as `--accent-vivid`, but ~7:1 contrast with white text, where the vivid blue would fail AA on small button text); `--accent-vivid` stays the primary on deep surfaces. Deep-navy full-page environments remain identity moments, not the content default.

---

## DD-6 — Full R&D pass: all prior identity/IA decisions cancelled and superseded

**Status:** `DECIDED` (owner directive, 2026-08-27: *"Cancel all previous UI/UX decisions (start
fresh based on research)... give you ONE prompt."*). Authoritative document:
[UI_UX_MASTER_PROMPT.md](UI_UX_MASTER_PROMPT.md).

**Superseded by this entry:**
- **`DD-1`** (Findings-review interaction model) — was left `DECIDED`-in-part/proposal-in-part (the
  B+C hybrid was recommended but its exact structure never finalized). The master prompt §3
  finalizes it: bounded list defaulting to `requires_decision`, persistent detail pane,
  equally-weighted "All Findings" toggle, URL-addressable selection, keyboard next/previous. This
  is substantially DD-1's own recommendation, ratified rather than reinvented — the hybrid was
  sound; what was missing was a decision, not a better idea.
- **`DD-2`/`DD-3`/`DD-4`** (`/login` visual identity, three successive treatments) — superseded in
  full. The deep-navy glass/floating-geometry environment is retired: it was a one-page "identity
  moment" that never extended to the rest of the product (`DD-5` itself named this gap), and it
  violated this document's own anti-pattern list (glassmorphism, gradients, decorative motion) on
  the one page that most needed to set the standard, not break it. `/login` is rebuilt inside the
  single system in the master prompt §3–4 — task-first heading, one persistent dark shell bar
  shared with every other page, no page-specific spectacle.
- **`DD-5`** (standing finish bar + light-content/dark-shell split) — the finish-bar *standard*
  (every page must look finished, not just be correct) is **kept** and restated in the master
  prompt's own governing intent; the light-content/dark-shell *split specifically* is generalized
  correctly rather than superseded — the master prompt keeps exactly one dark surface (the
  persistent shell), which is what DD-5 was reaching for before the login environment complicated
  it.

**Not touched by this entry — these are locked product behavior, not UI/UX decisions, and no
"cancel all previous UI/UX decisions" instruction reaches them:** every rule in `CLAUDE.md` 1–23,
`52.1`–`52.7`, `LEGAL-02`/`SEC-07` confidentiality rendering, the five-axis state model plus the
assist lane's sixth axis, S-7's undifferentiated-auth-failure styling, no-optimistic-UI on Legal
Decisions, and every anti-pattern in [DESIGN.md](../../DESIGN.md) that derives from a locked rule
rather than a stylistic preference. `DESIGN.md`'s principles sections are retained near-verbatim in
spirit by the master prompt for the same reason.

**New, not present in any prior entry:** the two-register system (Authority vs. Inquiry, §4.1) for
how the legal-review workflow and the new AI assist surface coexist without being visually
confusable; the shared evidence-viewer decision (§3) unifying citation display across both paths;
the explicit rejection of three generic AI-chat conventions (token streaming, thumbs-up/down
feedback, and — kept, not rejected — AI-content labeling) against this product's specific
constraints (§0).

---

## DD-7 — Product UX roadmap ratifies the workspace plan; IA and landing decided

**Status:** `PROPOSED` (2026-08-27, awaiting owner review of
[PRODUCT_UX_ROADMAP.md](PRODUCT_UX_ROADMAP.md), which this entry indexes).

**Decided here:**

1. **The Review workspace adopts [WORKSPACE_UI_PLAN.md](WORKSPACE_UI_PLAN.md)'s
   three-pane composition** (document · findings · ask, cross-pane highlight as the
   signature) — **superseding the master prompt §3's own sketch** (findings list +
   detail pane + ask drawer). Reason: the vision's anchor object is the document, and
   the highlight gesture makes the evidence chain one act; the master prompt's "shared
   evidence viewer" idea *is* this mechanism, generalized. The master prompt remains
   authority for the visual system (§4) and everything else.
2. **Landing surface = Documents** (no dashboard): no cross-document KPI exists that a
   user acts on; every action starts from a document. Reviews-queue nav bias for
   LEGAL_REVIEWER, same app.
3. **No Settings/Profile screens in V1** — nothing real backs them (administrator-
   provisioned accounts, no user preferences); building them would fake capability.
4. **Positions live under a Legal nav area**, not global nav — verified: ordinary
   users hold no `configuration.view`, and LEGAL-02 makes advertising the section to
   them a disclosure.
5. **Admin is a separate control plane** — verified: SUPER_ADMIN holds only
   user/role/audit/platform permissions and cannot open a contract; "user UI + admin
   menu" is structurally false here.
6. **Font conflict flagged, not resolved** *(→ resolved by DD-8, owner approval
   2026-08-31)*: master prompt §4.3 (IBM Plex/Source Serif
   via Google Fonts) vs DD-4's no-runtime-CDN ruling. Implementation stays on the
   system stack until the owner approves `next/font` bundling (rule 19 line-item);
   the type *roles* (mono = precise values, italic serif = verbatim quotes) apply
   meanwhile with system faces.

**Build-first decision:** the document pane + highlight mechanism as a thin vertical
slice — the signature interaction and the one unproven technical risk
(offsets → rendered DOM spans). Full reasoning: PRODUCT_UX_ROADMAP.md §G.

---

## DD-8 — Master-prompt typefaces bundled via `next/font` (closes DD-7 §6)

**Status:** `DECIDED AND IMPLEMENTED` (owner approval, 2026-08-31: *"approve the font
bundling"* — the explicit rule-19 line-item DD-7 §6 required).

**What was decided:** the UI_UX_MASTER_PROMPT §4.3 faces are now real: **IBM Plex Sans**
(all UI chrome — weights 400/500/600, the only weights the stylesheet uses), **IBM Plex
Mono** (machine-tracked values — same weights), and **Source Serif 4** (verbatim quoted
document text, normal + italic). No other face anywhere, per §4.3.

**How, and why this satisfies DD-4's concern:** `next/font/google` downloads the font
files at **build time** and serves them from the application's own origin
(`.next/static/media`, verified: 33 woff2 files, zero built-asset references to
`fonts.googleapis.com`/`fonts.gstatic.com`). No page load ever reaches a third-party
host — the runtime-CDN leak DD-4 ruled out never occurs. `display: swap` keeps first
paint on the fallback stacks, which remain in every role token (`--ws-sans`/`--ws-mono`/
`--ws-serif`), so a failed font file degrades to exactly the previous system rendering.

**Scope:** the new application only — the variables are mounted by the `/workspace`
route-group layout (a `display: contents` carrier, no layout participation). Legacy
screens keep their system stacks untouched until their retirement pass.

**Build note:** the production build now requires egress to Google Fonts **at build
time only** (CI and the frontend image build both have it; the runtime `data` network
rules are unaffected). Expected: visual-baseline diffs on every new-UI screen — re-cut
from CI per the standing rule (owner, 2026-08-30).

---

## DD-9 — The reference-matched workspace (owner directive, 2026-09-01)

**Status:** `DECIDED AND IMPLEMENTED` (owner, in session, with a reference
screenshot: *"I want exactly like the image I attached"* — an explicit UX-review
request, which is what lifts the 2026-08-31 freeze for this pass).

**What was decided:**

1. **Cards on a grey canvas.** The workspace surface moves from flat bordered
   panes to white rounded cards (`--ws-radius-card: 10px`, one soft shadow
   token) on a `#f2f4f8` canvas. The accent brightens to `#2563eb`
   (hover `#1d4ed8`); the shell deepens to `#0d1220` with a blue active-nav
   treatment and an avatar chip.
2. **The three-bucket status mapping — supersedes the "equal weight within an
   axis" rendering rule** for the workspace's summary surfaces. The owner chose
   the reference's traffic light: green = `MATCH`, red = `MISSING`, amber =
   every other classification ("needs review" — DEVIATION, CONFLICT,
   UNABLE_TO_EVALUATE, AMBIGUOUS, UNRESOLVED, and any future value, which fails
   toward amber, never toward calm). PRESENTATION grouping only: the exact
   classification value always renders beside the color (chips, donut legend),
   the five-axis vocabularies are untouched, and rule 12 stands — counts and
   count-shares only, never a score, never confidence. Markers are icons with
   accessible names, never color alone.
3. **Layout = clauses card | document card | side card.** The document region
   splits into a Clauses card (search, status markers, legend, pages footer)
   and a Document card under a toolbar (find-in-document, page navigation
   tracked by intersection, zoom 85–150%, fullscreen). The side card carries
   two tabs — **AI Analysis** (default: stat tiles, segmented bar, three-bucket
   donut with per-classification legend and count-share percentages, Key
   Risks, Key Obligations two-up) and **Findings** (the full pane, decisions
   and escalation intact); `?finding=`/`?classification=` deep links open the
   Findings tab directly.
4. **The Ask bar becomes a floating card** with the sparkle mark, prefill
   suggestion chips (editable drafts — nothing sends itself), a circular send,
   the history toggle, and an honesty note. Header gains back-arrow, Download
   (the existing export, relocated), and Share (copy the deep-linkable URL).

**Deliberate omissions from the literal reference (no fake controls):**
"Compare" (no comparison capability exists), "Add custom clause" (clauses come
from the document, not the user), and Key Risks' "View suggestion" (clause
suggestions would state an organizational legal position — AM-25 forbids it
outside ratified sources). A notification bell is omitted for the same reason.

**Expected:** visual-baseline diffs on every workspace screen — re-cut from CI
per the standing rule (owner, 2026-08-30).

---

## DD-10 — The Documents index, owner-supplied reference (2026-09-01)

**Owner instruction:** a reference screenshot and a React file, "need to upgrade the
document page according to above code and image".

**Followed exactly:** the layout. A fixed 420px intake card beside a flexible
five-step explainer strip; icon-left stat tiles with the count beneath the label;
the toolbar, table and a footer inside one card so the column header stays visible
above an empty table; the footer's formats/size line and help link.

**Not followed, and why — the reference's copy described a different product.**
This is the substantive part of DD-10 and it is a rule-4/rule-12 matter, not taste:

| Reference said | Why it could not ship | What it says now |
|---|---|---|
| "AI extracts text and key clauses" | `AI-01`, reaffirmed by `AM-25`: no LLM, RAG, embedding or vector database in the AUTHORITATIVE path. Extraction is deterministic | "Clause text located, every span kept as evidence" |
| "Contract type & relevant standards identified" · "We'll automatically detect the contract type" | Owner Q9 (2026-08-19): type is **declared** by the uploader, never inferred. `AM-34` permits a suggestion the human must confirm | "Confirm type — yours to declare, a suggestion pre-fills the field" |
| "Get risks, deviations & actionable insights" | Rule 12: a Finding reconstructs as Evidence → Fact → Standard → Rule → Result. "Risk" and "insight" are the vocabulary of a product that returns a score | "Each result traces back to the clause it came from" |
| (the page lede, already in the tree) "our AI will automatically detect the type … identify risks" | All three of the above at once | "Upload a contract, confirm its type … same document, same configuration, same result" |

The determinism is the stronger claim anyway, and it is the true one.

**Also not copied:** the reference's palette (`#276df3`, `#16a052`, `#df8100`,
`#dfe5ee`) and its `Inter` stack. Every value resolves through the existing
`--ws-*` tokens, which are within a few points of the reference's own — copying
them in would have created a second, silently-diverging palette for one page. Type
stays on DD-8's self-hosted IBM Plex, which is a recorded owner-approved decision.

**Also not copied:** the unicode glyphs (`▤ ◎ ▥ ◇ 🔒 →`). `icons.tsx`'s house rule
is no emoji, and platform fonts render those at different weights and baselines,
which is visible in a row of five marks that must look equal.

**One addition beyond the reference.** Four of the five steps are things the system
does; one is a thing the reader does. Step 3 carries an accent ring — the only
ornament in the row — because it encodes something true rather than decorating the
sequence. (The reference tinted steps 3 and 5 with no meaning attached.) The status
hues are *not* used for it: `--ws-ok/warn/bad` are reserved for state.

**Verified by rendering, not by inspection.** Screenshots at 1600/980/600/380px:
no page-level horizontal scroll at any width, the table scrolls inside its own
container, and all five step labels sit on one line so the row shares a baseline.
Two defects were found this way and fixed — a two-line label that dropped its own
step's detail text out of alignment, and a **pre-existing** `.ws-shell__user`
overflow that clipped the "Sign out" control off-screen below ~720px.

Pinned by `frontend/src/__tests__/documents-pipeline.test.tsx` (10 tests), which
asserts the copy prohibitions above against the rendered markup — the tree-wide
`check:terms` script cannot see rendered text.

---

## DD-11 — Upload is a disclosure, not a modal (2026-09-01)

**The conflict, reported rather than resolved.** Redesigning the Dashboard, the
owner was offered three shapes for the upload trigger and chose "modal from
header button". [DESIGN.md](../../DESIGN.md) lists, among the things this product
does not do:

> Modals for anything that isn't a genuine interruption (a destructive
> confirmation, a truly blocking choice). Most of this product's "detail" needs
> are drill-down navigation, not modal overlays.

CLAUDE.md's UI/UX precedence is explicit that where a design skill's default
conflicts with a recorded DD decision, the DD decision wins **and the conflict is
reported** — rule 5, not silently resolved in either direction. So the conflict
was surfaced to the owner in the plan rather than either quietly building the
overlay or quietly dropping the request.

**What shipped.** An inline disclosure panel. A primary `+ Upload Contract`
button in the page header (`aria-expanded` / `aria-controls`) toggles a panel
that is absent from the DOM when closed and expands in place beneath the button
when open. No backdrop, no scroll lock, no focus trap.

**Why this satisfies the actual requirement.** What the owner was solving for was
space: an always-visible upload card occupied a large block of the fold whether
or not anyone was uploading. A disclosure collapses to zero height, which is the
same saving an overlay would have delivered — the overlay was a means, not the
end. The panel also keeps the upload flow in the page's own scroll and reading
order, which matters because the flow is multi-step (upload → extract → suggest
type → **human confirms the type** → analyze) and the confirm step is a real
decision the reader may want to leave and return to.

`UploadContract.tsx` is untouched. Its state machine, its API calls and owner
Q9's human-declared type are exactly as they were; only the container changed.

**Where a modal *is* used, and why that is consistent.** Two places, both of
which DESIGN.md names outright: the delete confirmation (a destructive
confirmation) and the edit-details form (a small blocking choice the user
summoned, dismissed by Escape or Cancel, restoring focus to the control that
opened it — the same pattern `KeyboardShortcutsHelp` established).

**If the owner still wants an overlay for upload**, that is theirs to decide;
this entry is superseded in place when they do, with the reasoning above
recorded as what was traded away.

---

## DD-12 — Two-tone wordmark, and the contrast audit it triggered (2026-09-02)

**Owner instruction, 2026-09-02:** *"Change the logo so that 'Legal' is white and 'Mind' is
brand blue (#0055AA). … Audit all text on the dashboard. Ensure every text element is fully
visible against its background."*

Presentation only. No locked decision is amended; `LOCKED_DECISIONS.md` is untouched.

### 1. The wordmark

`LegalMind` is now two spans inside the one link — `.ws-shell__word-a` (`#fff`) and
`.ws-shell__word-b` (`var(--ws-brand-on-dark)`). Two implementation notes that are easy to
get wrong:

* **No whitespace between the spans.** JSX renders a newline between sibling elements as a
  text node, which would produce "Legal Mind". Verified in a real browser:
  `textContent === "LegalMind"`.
* **The accessible name is unchanged.** Both spans are plain text in one link, so it is still
  announced "LegalMind, link" — splitting for colour does not split it for a screen reader.

`--ws-brand` is a **new token, deliberately not `--ws-accent`.** The accent is functional
(links, focus, primary action); the brand is identity. Merging them would mean that restyling
one silently restyles the other.

### 2. ⚠️ The brand blue does not meet contrast on the dark shell — and that is recorded, not fixed

`#0055AA` measures **7.29:1 on white** and **2.56:1 on the shell's `#0d1220`**. It is a deep
blue built for light surfaces; the top bar is near-black.

It ships **exactly as specified**, for two reasons: the owner named the hex, and WCAG SC 1.4.3
explicitly exempts logotypes from contrast requirements — so this is a legibility observation,
not a violation. But it is the dimmest text in the top bar, and that sits in tension with the
same instruction's second half.

The swap is therefore **one line**: set `--ws-brand-on-dark` to `#007af3` (4.52:1, AA) or
`#005fbe` (3.01:1, AA-large). Both are the same hue with lightness lifted — no new colour.
`--ws-brand` stays `#0055AA` for light surfaces either way.

### 3. The audit found five real failures, and they were not the logo

Measured every foreground/background pair the stylesheet actually declares in one rule — not
a theoretical matrix. The status colours were painted as **text on their own `-soft` tint**,
at 10–11px, and failed the 4.5:1 small-text minimum:

| Token | Was | On its `-soft` tint | Now | Now |
|---|---|---|---|---|
| `--ws-warn` | `#d97706` | **2.90:1** ❌ | `#a85c05` | 4.55:1 ✅ |
| `--ws-ok` | `#16a34a` | **2.98:1** ❌ | `#11803a` | 4.55:1 ✅ |
| `--ws-bad` | `#dc2626` | **4.23:1** ❌ | `#d52222` | 4.51:1 ✅ |
| `--ws-decision` | `#15803d` | **4.39:1** ❌ | `#157e3c` | 4.50:1 ✅ |
| `--ws-outcome` | `#b45309` | **4.47:1** ❌ | `#b35209` | 4.53:1 ✅ |

The worst of these was the `Needs Review` pill — the single most important status on the
dashboard was its least readable text.

**Only lightness moved.** Hue and saturation are untouched, so DD-9's owner-approved traffic
light still reads as the same three colours, and each value is the *minimum* darkening that
clears the line. Nothing regressed: on white, amber went 3.19→5.00 and green 3.30→5.03; as
bar-segment and legend-dot fills there is no text to affect; and the one white-on-red button
improved 4.83→5.15.

**Not changed, and why:** `--ws-ink-300` measures 2.20:1 on white but is used as a text colour
only for decorative icons that sit beside the text naming the same thing (the stat-tile plate,
the file glyph before a document name, the pending-step dot). SC 1.4.11 exempts a graphic whose
information is available in adjacent text. Changing it would dull a deliberate hierarchy for no
accessibility gain.

### 4. Verification

Contrast computed from the stylesheet's own declared pairs, then confirmed against
`getComputedStyle` in a headless browser; the deployed bundle was re-fetched from
`https://legalmind.lsnw.io` and checked to carry the new token values.

⚠️ **The 15 visual baselines will fail once.** These are colour changes on pinned screenshots.
Per the standing rule, baselines are cut in CI only — let job 15 fail, then adopt its
`*-actual.png`. Do not run `design-qa --update-snapshots` locally.

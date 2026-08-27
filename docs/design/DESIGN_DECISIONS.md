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

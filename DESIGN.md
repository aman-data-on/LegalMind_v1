# DESIGN.md — LegalMind UI/UX Operating Manual

**Status: `IN PROGRESS` (Phase 0 — Discovery). This document governs presentation-layer decisions only. It locks nothing in `all_lock.md` and amends no entry in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md).**

This document exists because [STEP_52_FRONTEND_ARCHITECTURE.md](docs/05-architecture/STEP_52_FRONTEND_ARCHITECTURE.md) §52.6 explicitly leaves visual design, component library, accessibility target, and internationalization `NOT YET SPECIFIED` and calls each "an implementation-phase choice." This is that choice being made deliberately, in the open, instead of accreting ad hoc. It does not touch [CLAUDE.md](CLAUDE.md), which remains the authority on everything else in this repository.

**What this document is not:** it is not a specification of legal behavior, not a Company Standard, not a Legal Rule, and not an amendment to any locked decision. Where this document is silent or in tension with `CLAUDE.md` rules 1–23, `CLAUDE.md` wins.

**What already exists:** the frontend (`frontend/`) is not a blank slate. All ten Step 52.6 screens except report export are implemented, permission-gated, and covered by 53 Vitest tests and a Playwright browser suite that pins down real security- and correctness-critical DOM behavior (confidentiality omission, no-optimistic-decision-UI, 409 conflict surfacing, byte-identical 404s). Deliberately, **no CSS framework, component library, or client-state library was added** — `frontend/src/app/globals.css` is one plain stylesheet. This document governs how that gap gets filled, not whether the existing information architecture is correct. **The IA is correct and locked-adjacent (52.5); the visual and component layer is what's open.**

---

## Design philosophy

LegalMind is not a marketing surface and not a generic SaaS dashboard. It is a document where a Legal Reviewer's attention is the scarcest resource in the system, and every screen exists to get that attention to the right evidence, in the right order, with the right authority boundary enforced. The product's own philosophy — deterministic, explainable, versioned, auditable, reproducible — is a design brief, not just a backend constraint:

- **Deterministic** → the UI never implies a probability, a confidence score, or a "the AI thinks" hedge. A classification is a classification, not a suggestion.
- **Explainable** → every screen that shows a conclusion must make the chain that produced it (Evidence → Fact → Standard → Rule → Result) reachable in the same view or one click away — never buried in a different page.
- **Versioned / Auditable / Reproducible** → the UI treats history as a first-class citizen, not an afterthought behind a "view audit log" link. Superseded decisions, prior document versions, and configuration snapshots are shown, not hidden.
- **Permission-controlled** → what a screen shows is a direct, honest function of who is looking. There is no single "the UI" — there are as many structurally distinct views as there are permission boundaries, and the design system must make each one look intentional, not like a degraded version of the "real" screen.

**The product's actual signature is not a visual flourish — it is the evidence chain itself.** LegalMind's version of a memorable, distinctive interface is making Evidence → Fact → Standard → Rule → Result feel like one continuous act of inspection rather than five disconnected lookups. Every visual design decision should be judged against whether it strengthens or dilutes that chain.

The tone throughout is: **evidence, clarity, confidence in the mechanical sense (traceability), and control** — never confidence in the statistical sense, and never urgency theater (no red for its own sake, no gamified progress bars, no "AI is thinking" shimmer).

---

## UX principles

1. **Show the chain, not the verdict.** A classification, status, or outcome badge is never presented without a path to the evidence and reasoning behind it, visible in the same view.
2. **Never let a summary substitute for its parts.** A Finding's derived `classification` is a summary label, not a conclusion — the Evaluations underneath it are the actual legal content and must always be reachable, never collapsed away permanently.
3. **Design for the decision-maker's actual task, not a generic CRUD view.** A Legal Reviewer's job in most of V1 is triage across many Evaluations that require a decision (because no Legal Rule tolerance currently exists — see [Legal-specific UX principles](#legal-specific-ux-principles)). Optimize the primary path for that reality, not for an idealized "browse everything equally" experience.
4. **Absence is information.** An empty evidence list, an omitted confidential field, a `NOT_APPLICABLE` rule outcome, and a zero-Finding Review are all valid, meaningful states — never rendered as errors, never rendered as visually identical to "still loading."
5. **Every action states what happens, in the interface's own voice.** A button's label survives unchanged into its result ("Escalate" → "Escalated", never "Submit" → "Success").
6. **Speed for the expert, clarity for the occasional user.** The primary persona is a repeat, professional user (Legal Reviewer, Legal Admin) who will use this daily — density and keyboard efficiency are not at odds with clarity here, they support it. Don't dumb down density in the name of approachability for a workflow whose whole audience is trained legal/ops staff.

---

## Information hierarchy principles

- **Structural state before decorative state.** The five state axes (Mapping State, Finding Classification, Rule Outcome, Legal Decision, Review Lifecycle — see [DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md)) are the primary hierarchy of every legal-content screen. Visual weight follows axis importance to the *current task*, not to how "positive" or "negative" a word sounds.
- **Never let two axes share a visual channel.** If classification and rule outcome are both shown as colored pills using the same color scale, a reader will conflate them within a week. Each axis gets its own token namespace, exactly mirroring the existing informal convention (`.badge` / `.status` / `.outcome` / `.tag`) — ratify that separation, don't collapse it into one generic `<Badge variant>`.
- **Attention is a first-class hierarchy level, not a color.** An Evaluation that `requires_decision` (rule outcome `APPROVAL_REQUIRED`/`UNACCEPTABLE`, Tier-1 classification, escalated, or an un-ruled `DEVIATION`) must be findable by scanning, not by reading. This is already a locked behavioral requirement (52.5); the design system's job is to make it also a *visual* one that survives a redesign.
- **Tier-1 classifications are not a severity ranking.** `UNABLE_TO_EVALUATE`, `CONFLICT`, `AMBIGUOUS`, and `UNRESOLVED` all route to the same place (human review) and are legally equivalent. Do not style them as if one is "worse" than another — that would invent a severity model the specification does not contain (rule 7).
- **The whole is reachable from the part, and the part from the whole.** A Finding screen shows enough of the Review it belongs to (status, contract, document version) to orient without navigating away; a Review screen surfaces enough of its Findings' aggregate state to know whether attention is needed before opening any of them.

---

## Interaction principles

- **No optimistic UI for anything that is a legal act.** A Legal Decision renders only after the server confirms it. A 409 version conflict is a legitimate, expected outcome — surface it plainly, never retry silently, never overwrite what's on screen with what the user just typed.
- **Permission-aware, not permission-apologetic.** A control the user cannot invoke is not shown, greyed out, or shown-then-disabled with a tooltip explaining why — it is simply absent, exactly as confidential fields are simply absent (52.3/52.4). Do not add a "you don't have permission" affordance that itself discloses the existence of the withheld capability, except at the whole-section level (`AccessRestricted`), which is the one place that disclosure is already sanctioned.
- **Escalation is a request; Decision is an act.** These must never look like the same kind of control. A Legal Decision changes what the record says the organization ruled; an escalation only asks that a human look. Visually and verbally distinguish request-for-attention controls from authority-exercising controls everywhere they appear together (this directly addresses a gap found in the Phase 0 audit — see [UX_AUDIT.md](docs/design/UX_AUDIT.md)).
- **History is inspected, not just logged.** Superseded Decisions, prior Document Versions, and old configuration snapshots should be a scroll or a click away from their current counterpart, in context — not exiled to a separate audit page that requires re-establishing context from scratch.
- **Filtering and pagination are a means, not a feature.** Every list screen needs consistent, predictable filter/sort/page controls — but a Legal Reviewer's actual need is usually "show me what needs a decision," not "browse everything alphabetically." Default views should bias toward the task, with an explicit, undoable way to see everything.
- **Keyboard access for repeat, professional use.** A user who reviews fifty Evaluations a day should not be forced to use a mouse for every one. This does not need a complete command palette on day one, but layout and markup choices should not preclude it later (see [Accessibility principles](#accessibility-principles)).

---

## Visual principles

**Finish standard (owner directive, 2026-08-21 — non-negotiable).** "No marketing copy" and "restraint" are rules about *content*, never an excuse for visual flatness. Every delivered page must look **finished**: a cohesive background theme, deliberate typography (scale, weights, family pairing), consistent alignment and spacing rhythm, polished controls (real button treatments, focus/hover states, considered input styling), and a composition that was clearly designed rather than defaulted. The `/login` page as delivered under DD-4 ([docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md)) is the current reference for this finish level — theme, font handling, text sizes, and alignment. A page that is behaviorally correct but visually bare is **not done**; the Phase-3.1 first pass at `/login` made exactly that mistake and it must not repeat on any subsequent page. Restraint disciplines *what* is on the page; finish governs *how well* what remains is executed — both are mandatory, and neither substitutes for the other.

This section is deliberately about *principles*, not tokens. Exact color hexes, a type scale, and spacing units are Phase 1 (Design Foundation) work, done once, reviewed once, and then treated as settled — not decided implicitly page by page. Until Phase 1 is approved, no page implementation should introduce new ad hoc visual tokens.

- **Typography carries hierarchy; color carries state.** Reach for weight, size, and spacing before reaching for a new color. Color is reserved for the five state axes and for the two existing emphasis semantics (attention, error) — it should stay a scarce, meaningful resource, not a decoration applied per-page.
- **Density is a feature of this product, not a defect to hide.** Legal review is inherently information-dense (long clause names, long evidence excerpts, many nested Evaluations). Don't import oversized hero sections, excess whitespace, or card-in-card-in-card nesting to make the product "feel lighter" — that adds scrolling and hides the evidence the user came for.
- **Surfaces should be flat and legible, not decorative.** Borders and subtle surface changes (already present via `--line`/`--surface`) are sufficient to separate regions. No glassmorphism, no gradients, no drop shadows deep enough to imply floating panels unless a real overlay (e.g., a modal that must interrupt) requires one.
- **One accent language for state, not brand.** LegalMind has no marketing "brand palette" job to do here — there is no logo-driven purple/blue "AI" aesthetic to protect and no reason to invent one. The palette's entire job is to make the five state axes and two emphasis levels distinguishable and calm at once.
- **Numbering and sequence markers are used only where the content is actually sequential.** Decision history, document versions, and configuration snapshot order are genuinely sequential — number them. Findings, Evaluations, and audit entries are not inherently ordered by importance — don't impose 01/02/03 styling on a set that isn't a sequence.

---

## Legal-specific UX principles

- **`RESOLVED ≠ MATCH`, visibly.** A resolved Finding must keep showing its original classification badge. Resolving a workflow state must never read, at a glance, as "this was fine."
- **`DEVIATION` is not "wrong."** A deviation is a factual comparison result. Whether it's tolerable is a separate axis (Rule Outcome), decided separately, and shown separately. Never merge the two into one "problem/no problem" signal.
- **In V1, almost every deviation currently requires a human decision.** The zero-tolerance Legal Rule ruling (manager, 2026-08-19; MATCH → `ACCEPTABLE`, any DEVIATION → `UNACCEPTABLE`, no tolerance band) plus the `UNRULED_DEVIATION_REQUIRES_DECISION` widening means the UI should not imply that automatic acceptance is the common case. Design the primary Legal Reviewer workflow around "there is usually a decision queue," not around a rare-exception mental model.
- **`NOT_APPLICABLE` is a real, correct answer — not a placeholder or a loading state.** Style it as a deliberate, calm "no rule exists" state, not as missing data.
- **Never invent a severity, confidence, or risk score.** No numeric "risk %," no traffic-light rollup that doesn't map to an actual locked field. If a screen wants a single glance-able signal, it must be built from real fields (`requires_decision`, `escalated`, rule outcome) — never a synthesized metric (rule 7, rule 12).
- **Confidential omission looks like absence, never like a lock.** No padlock icon, no "restricted" chip, no greyed placeholder where a `rule_outcome` or threshold would be for a caller without `legal_position.view`. The section is simply shorter for that caller. This is a security property, not just a style choice — get it wrong and the UI discloses that an internal legal position exists (LEGAL-02).
- **A Finding is a set of Evaluations, never a single verdict.** Any summary view (a report, a dashboard tile, a list row) must be honest about being a summary and must lead to the full set on request.
- **Decision authority is visually distinct from decision-adjacent activity.** Escalating, viewing, and commenting are not decisions. Only the Evaluation-level Decision control, gated on `legal.decision` (and additionally `legal.approve_customization` for that decision type), represents an authorized ruling — and it should be the only control on the page that looks like it changes the legal record.

---

## Accessibility principles

Accessibility target is formally `NOT YET SPECIFIED` (52.6) — this section states the floor that should hold regardless of what target is later chosen (e.g., WCAG 2.1 AA), so that choosing a target later is a matter of *verifying*, not *retrofitting*.

- Every interactive control is reachable and operable by keyboard alone; visible focus is never suppressed.
- Every status/classification/outcome/tag conveys meaning through text (or an accessible name), never through color alone.
- Form errors are associated with their field programmatically, not only by adjacent placement.
- Disclosure widgets (evidence lists, decision history) use real semantic disclosure patterns, not divs with click handlers.
- Tables used for list data use real table semantics (headers, scope) — not styled divs — since screen-reader users need row/column relationships for dense data.
- Motion, if introduced later, respects `prefers-reduced-motion`; nothing here needs animation to be usable today, and none should be added that isn't functional (see Anti-patterns).
- Loading states are announced to assistive technology (e.g., `aria-live`), not only shown visually — a serial "Loading Findings… Loading Evidence…" sequence is currently silent to a screen-reader user.

---

## Responsive principles

Dense, tabular legal data does not compress gracefully to a phone screen, and this product's primary usage context is a desk, not a phone. Responsive principles here are about **viewport range, not device fiction**:

- Design and test for a realistic desktop/laptop range first (the actual usage context for a Legal Reviewer's workday); tablet-width support is a secondary tier; phone-width support is explicitly not a V1 requirement unless the roadmap decides otherwise.
- Never let a responsive collapse silently drop a column that carries state (e.g., collapsing a table so the attention flag disappears on a narrower viewport is a correctness regression, not just a layout one).
- Prefer horizontal scroll inside a bounded container over destructive column-hiding for genuinely wide data (long evidence excerpts, long clause text) — the reader should know data still exists, not lose it.
- A split-pane or master-detail layout (if adopted — see [DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md)) must define its single-pane collapse behavior explicitly, not leave it as an afterthought.

---

## Anti-patterns

Do not do these, in LegalMind, without a documented, explicit decision overriding this section:

- Generic dashboard "stat cards" with a big number and a small label, unless the number is a real field with a defined meaning (no synthesized KPIs).
- Sidebar + header + card-grid layout adopted because it's conventional rather than because it solves this product's actual navigation problem (a mostly-linear Contract → Review → Finding → Evaluation drill-down, not a multi-domain dashboard).
- Rounded-everything, heavy shadows, glassmorphism, or gradient surfaces.
- Purple/blue "AI product" aesthetics, sparkle icons, or any visual implication that a result is AI-generated, probabilistic, or a suggestion — V1 uses no LLM/RAG/embeddings in the authoritative path (`AI-01`), and the UI must never imply otherwise.
- Confidence percentages, risk scores, or traffic-light rollups not backed by a real field.
- A lock icon, greyed placeholder, or "restricted" label standing in for an omitted confidential field.
- A single merged "status" badge that mixes two of the five state axes.
- Decorative animation (shimmer, bouncing icons, celebratory confetti on "resolved") — resolving a Finding is not an achievement to celebrate, and shimmer loading states can imply content that then contradicts a valid empty/absent state.
- Modals for anything that isn't a genuine interruption (a destructive confirmation, a truly blocking choice). Most of this product's "detail" needs are drill-down navigation, not modal overlays.
- Treating escalation and decision controls as visually interchangeable "action buttons."
- Client-side computation, caching, or re-derivation of any classification, rule outcome, or `requires_decision` value — every such value is rendered exactly as received (52.7), and a "smarter" client-side rollup is a spec violation, not a UX improvement.

---

## Design decision governance

Major, hard-to-reverse design decisions (an interaction model for a core workflow, a component-library adoption, an accessibility target, a responsive breakpoint strategy) are recorded in [docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) as they are made, in the same append-oriented spirit as `all_lock.md` — a superseded decision is marked superseded in place, with a pointer to what replaced it and why, rather than deleted or silently reworked.

A decision belongs in that log, not just in a PR description, when a future contributor could plausibly re-litigate it from scratch without knowing it was already decided. Smaller, page-local implementation choices that follow directly from the principles in this document do not need their own log entry.

Nothing in this document authorizes changing the frontend's structural guarantees (52.1–52.7), the five-axis state model, or any permission/confidentiality rule — those are `CLAUDE.md`/locked-specification territory. This document governs only how correct, already-specified behavior is *presented*.

---

## Where the rest of this lives

- Current-state audit (page inventory, component inventory, UX problems, workflow map): [docs/design/UX_AUDIT.md](docs/design/UX_AUDIT.md)
- Explored interaction directions for the core review workflow, and the recorded decision: [docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md)
- Phase sequencing and page-by-page implementation roadmap: [docs/design/UX_ROADMAP.md](docs/design/UX_ROADMAP.md)
- The concrete tokens and primitives, as implemented in Phase 1 + Phase 2: [docs/design/DESIGN_SYSTEM.md](docs/design/DESIGN_SYSTEM.md)

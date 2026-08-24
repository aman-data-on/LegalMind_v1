# DESIGN_SYSTEM.md — Design Foundation (Phase 1 + Phase 2, as implemented)

**Status: `IMPLEMENTED` for the tokens and primitives listed below; `PROPOSAL` for anything marked not-yet-adopted. Governed by [../../DESIGN.md](../../DESIGN.md).**

> Status words in `docs/design/` describe *design-workstream progress only*. [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md) remains the sole authority on build state; nothing here asserts a lifecycle state in that document's sense.

This is the concrete answer to Step 52.6's `NOT YET SPECIFIED` visual design/component question, as actually built in `frontend/src/app/globals.css`. It documents what exists so Phase 3 page work consumes a settled vocabulary instead of re-deriving it. **Nothing in this document changed a page's markup, behavior, or any of the frontend's 58 Vitest tests, the Playwright suite's assumptions, or the production build — all were re-verified after this pass (`npm run typecheck`, `npm test`, `npm run build`).**

The approach throughout was a **retrofit, not a redesign**: existing CSS rules were substituted for tokens. **Correction (code review, 2026-08-22):** five values were snapped to the nearest scale step rather than kept byte-exact — `label` 0.9rem→1rem, `th` 0.8rem→0.78rem, `.finding__note`/`.evidence__location` 0.82rem→0.78rem, `.pager` 0.88rem→0.9375rem. These sub-pixel-to-1.6px shifts shipped inside the owner-reviewed finish passes; the earlier claim of exactness was wrong and is corrected here rather than silently rewritten. Net new, genuinely additive behavior was added in exactly three narrowly-scoped places, each tied to a specific finding in [UX_AUDIT.md](UX_AUDIT.md), never a general redesign:

1. `.hint` / `.empty` were made visually distinct (previously identical in weight and size — audit §2 "State Management").
2. `Loading` states (`Feedback.tsx` and `Chrome.tsx`'s own inline loading text) now carry `role="status" aria-live="polite"` (audit §2 "Accessibility").
3. `form.inline` and the shell (`.topbar`, `.content`) now have defined behavior below 640px, where none existed before (audit §2 "Responsive behavior").

No new dependency, CSS framework, or component library was added (rule 19; Step 52.6). No page's `.tsx` file was edited except the two one-line accessibility attributes above.

---

## Tokens (`:root` in `globals.css`)

### Color — base palette (unchanged values)

| Token | Value | Use |
|---|---|---|
| `--ink` | `#1a1c1f` | Primary text, headings |
| `--muted` | `#5b6169` | Secondary text, hints, captions |
| `--line` | `#d8dce1` | Borders, dividers |
| `--surface` | `#ffffff` | Card/panel backgrounds |
| `--page` | `#f6f7f9` | Page background |
| `--attention` / `--attention-bg` | `#8a4b00` / `#fff6e8` | The one locked emphasis (52.5): needs-decision, escalated, `APPROVAL_REQUIRED`/`UNACCEPTABLE` |
| `--error` / `--error-bg` | `#8a1414` / `#fdeeee` | Errors, decision conflicts |

### Color — newly named (values unchanged, now explicit)

| Token | Value | Use |
|---|---|---|
| `--success` / `--success-bg` | `#1f6b2f` / `#eef7ee` | `MATCH` classification only |
| `--indeterminate` / `--indeterminate-bg` | `#5a3d8a` / `#f3eefb` | `CONFLICT`/`AMBIGUOUS`/`UNRESOLVED`/`UNABLE_TO_EVALUATE` (Tier 1) — one color for the cluster, since [DESIGN.md](../../DESIGN.md) forbids styling Tier 1 as a severity ranking |
| `--accent` | `#1b4f9c` | The one non-state accent (links, focus ring, primary actions) |

**Governance rule, restated from DESIGN.md:** these map 1:1 onto the five state axes and two emphasis levels — never onto anything else. `ACCEPTABLE`/`NOT_APPLICABLE` rule outcomes and `MATCH`-adjacent neutral states intentionally get **no** special color (the plain badge/pill border only) — that calm treatment already existed and is preserved, not extended with a new "positive" green everywhere.

### Typography

| Token | Value | Maps to (unchanged) |
|---|---|---|
| `--text-xs` | `0.78rem` | table headers, badges |
| `--text-sm` | `0.86rem` | hints, captions, secondary metadata |
| `--text-base` | `0.9375rem` | body |
| `--text-md` | `1rem` | `h3`, labels |
| `--text-lg` | `1.1rem` | `h2` |
| `--text-xl` | `1.35rem` | `h1` |
| `--weight-regular` / `--weight-medium` / `--weight-semibold` | `400` / `550` / `650` | body / emphasis / headings, brand |

One system font stack (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`) — unchanged. No second (display) typeface has been introduced; LegalMind's information density argues against a decorative display face competing with the evidence text itself (see DESIGN.md § Visual principles).

### Spacing

| Token | Value |
|---|---|
| `--space-1` … `--space-6` | `0.25rem, 0.5rem, 0.65rem, 1rem, 1.5rem, 2rem` |

Chosen to exactly cover the recurring values already present in the stylesheet (0.65rem in particular exists solely because `.evaluations` already used it). A value that doesn't land on the scale (e.g. the topbar's `0.75rem`, `.shell--bare`'s `3rem`) is left as a literal rather than forced onto the nearest token — see the file's own comments at each such spot.

### Radius / border

| Token | Value | Use |
|---|---|---|
| `--radius-xs` | `3px` | badge/status/outcome/tag pills |
| `--radius-sm` | `4px` | buttons, inputs, small cards |
| `--radius-md` | `6px` | `.card`, `.finding`, `.access-restricted` |
| `--radius-lg` | `10px` | reserved — not yet used; for a future genuine overlay only |

Border color is `--line` throughout, unchanged.

### Focus

`--focus-ring: 0 0 0 3px rgba(27, 79, 156, 0.35)` — applied via `:focus-visible` (not `:focus`, so a mouse click never draws it) to every interactive element: `button`, `a`, `input`, `select`, `textarea`, `[tabindex]`. No element had a defined focus style before; this adds visibility, it replaces nothing.

### Deep surface + display voice (added in DD-3)

| Token | Value | Use |
|---|---|---|
| `--ink-deep` / `--surface-deep` / `--line-deep` / `--input-deep` / `--on-deep` / `--on-deep-muted` / `--on-deep-faint` | `oklch` navy family (retinted in DD-4 from the DD-3 neutrals — see `globals.css` `:root` for exact values) | The "environment" voice — deep ground for identity moments (used by `/login`). Generic names on purpose; never a decorative home for state-axis colors. |
| `--accent-vivid` | `oklch(0.58 0.16 258)` | The one vivid action color, used only on deep surfaces (DD-4 submit button). |
| `--font-display` | `Georgia, "Iowan Old Style", "Times New Roman", Times, serif` | Identity and single-task headings only (wordmark, `/login`'s "Sign in"). Body text stays on the sans stack. System-resident — no font downloaded, no dependency. |
| ~~`--ease-out-soft`~~ | — | Removed 2026-08-22 (code review): defined but consumed by no rule — the DD-4 entrance uses the mock's own bezier. Motion rules stand: ambience slow and `aria-hidden`, entrances one-time, feedback immediate, everything removed under `prefers-reduced-motion`. |

### Breakpoints (documented values, not CSS custom properties — media queries can't consume a `var()`)

`--breakpoint-sm: 640px`, `--breakpoint-md: 960px`. Only `640px` is used by a real rule so far (see Responsive, below). `960px` is named for Phase 3's use, not yet consumed.

---

## Component primitives

### Badge / status / outcome / tag (existing family, now token-backed)

Unchanged structure, unchanged which classification/status/outcome maps to which color — only the hex literals became tokens. **The four namespaces stay separate on purpose** (`.badge` = Finding/Evaluation classification, `.status` = workflow status, `.outcome` = Rule Outcome, `.tag` = decision-history current/superseded) — this is the existing informal convention, ratified rather than collapsed, per DESIGN.md's "never let two axes share a visual channel."

No `<Badge>` React component was introduced. The codebase's existing, consistent pattern is a plain element with a computed `className` (`` `badge badge--${value.toLowerCase()}` ``) — introducing a wrapper component now, before any page adopts it, would be unused code and would start to look like the component-library decision Step 52.6 leaves open. If Phase 3 finds the repeated string-interpolation pattern worth abstracting once several pages are being touched, that is a candidate for its own `DESIGN_DECISIONS.md` entry then — not pre-built speculatively here.

### Button hierarchy (new, opt-in — not yet applied to any existing `<button>`)

| Class | Intent |
|---|---|
| `.btn--primary` | The action that most changes the record on this screen (e.g. recording a Legal Decision) |
| `.btn--secondary` | A normal action; visually close to the current unstyled default, made explicit |
| `.btn--danger` | A genuinely destructive or authority-reducing action (e.g. revoking a role) |
| `.btn--ghost` | A tertiary, low-emphasis action — equivalent to the existing `button.link` |
| `.btn--sm` | Size modifier, composes with any of the above |

Verified before adding: no existing page uses any of these class names today, so introducing them changed nothing rendered. Which existing button on which page becomes `.btn--primary` vs. stays on the bare `button` rule is a **Phase 3, page-by-page decision** — this document only names the vocabulary.

### Form primitives (new, opt-in)

`.field` / `.field__label` / `.field__hint` / `.field__error` / `.field--invalid` — an alternative, explicitly-associated label/hint/error wrapper. The existing bare `label`/`input` rules are untouched and every current form keeps rendering exactly as before; this is available for a form Phase 3 revisits.

### Table principles

No `<Table>` component — real `<table>`/`<th>`/`<td>` markup stays the pattern, for the same reason as Badge above. One new utility, `.table-wrap { overflow-x: auto; }`, is defined and documented but **not yet added to any page's markup** — Phase 3 wraps a page's table in it when that page is revisited, which directly resolves the audit's "tables would overflow uncontrolled on a narrow viewport" finding without editing every page today.

### Pagination

No new component — `Pager` in `Feedback.tsx` already exists and is reused by every list page; only its CSS (`.pager`) was touched (token substitution + `flex-wrap: wrap` so it doesn't overflow on a narrow viewport). No `.tsx` change.

### `.visually-hidden` (added in Phase 3.1)

Screen-reader-only content — for a `role="status" aria-live="polite"` announcement of a busy state that has no useful visible element of its own (a button label change alone is not reliably announced). First used by `/login`'s "Signing in…" announcement; reuse it anywhere a state change needs announcing without adding visible UI. Never use it to hide a confidential field's placeholder — 52.4 forbids any withheld-field marker, visible or not.

### Loading / empty / error states

`Loading` (`Feedback.tsx`) and `Chrome.tsx`'s own inline loading text now carry `role="status" aria-live="polite"`. `.hint` (loading, transient) and `.empty` (a settled, bounded fact — now a dashed-border box) are now visually distinct from each other; `.banner--error` (`ErrorBanner`) was already distinct and is untouched.

---

## Application Shell (Phase 2)

`Chrome.tsx`'s structure, permission-filtering logic, and identity/sign-out behavior are **unchanged** — only `.shell`, `.shell--bare`, `.topbar`, `.topbar__brand`, `.topbar__nav`, `.topbar__identity`, `.content`, `.footer` were retrofitted (token substitution, same rule as Phase 1) plus one new behavior:

```css
@media (max-width: 640px) {
  .content { padding: var(--space-4); }
  .topbar { gap: var(--space-3); }
  .topbar__identity { margin-left: auto; }
}
```

`.topbar` and `.topbar__nav` also gained `flex-wrap: wrap`, so the five permission-filtered nav links (and identity block) wrap to additional lines below ~640px instead of overflowing — no hamburger menu or JS-driven mobile nav was introduced. Per [DESIGN.md](../../DESIGN.md) § Responsive principles, phone-width is explicitly not a V1 requirement; if narrow-viewport usage becomes a real requirement later, a dedicated mobile-nav pattern is a candidate for its own `DESIGN_DECISIONS.md` entry, not something to invent speculatively now.

---

## What Phase 3 inherits

A page revisited in Phase 3 can now reach for: the full token set above; `.btn--*` for buttons; `.field*` for forms; `.table-wrap` for wide tables; the existing `Pager`/`Loading`/`EmptyState`/`ErrorBanner`/`AccessRestricted` components, now token-backed and (for `Loading`) accessible; and the existing badge/status/outcome/tag family, unchanged in meaning. No page has been touched yet — that is [UX_ROADMAP.md](UX_ROADMAP.md) §3, starting with `/login`.

# SHADCN ADOPTION REPORT

**Status:** 📁 `ANALYSIS`, step 1 of §5 **IMPLEMENTED 2026-09-10.** History, for anyone reading
this cold: the first pass built a dependency-free `Dialog.tsx` instead of Radix, on the belief
that Radix's `Portal` was incompatible with this project's Node-only Vitest environment for all
six dialogs. That belief was checked more precisely on request — it was true for exactly one of
the six (`KeyboardShortcutsHelp`, which has a `renderToStaticMarkup` unit test; the other five
have zero Vitest coverage and are validated only by Playwright in a real browser, where Portal is
unproblematic) — and the **final, current state re-implements `Dialog.tsx` on top of
`@radix-ui/react-dialog`** for those five, while `KeyboardShortcutsHelp` keeps its own plain
implementation. See the two addenda at the end of this document for the full sequence, including
a real structural bug (uncentered dialog) the first Radix attempt introduced and how it was
verified and fixed. `@radix-ui/react-dialog` is the one dependency now installed; Tailwind/shadcn
CLI remain unused — see §5 on why Radix-direct doesn't require either.
**Date:** 2026-09-10. **Governed by:** [DESIGN.md](../../DESIGN.md) and [CLAUDE.md](../../CLAUDE.md)
§ "UI and UX work" (shadcn/ui + Tailwind approved for incremental adoption, owner 2026-09-10).
This document locks nothing in `all_lock.md` and amends no entry in
[LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md).

---

## 0. What this covers

A full scan of the frontend's current component/CSS architecture, cross-referenced against
shadcn/ui's model, to answer: what should stay as-is, what would genuinely improve, what must
never be touched, and in what order to move — without a big-bang rewrite. No code changed.

---

## 1. Current architecture, as measured

| Area | Finding |
|---|---|
| Dependencies | `next` 16.3.4, `react`/`react-dom` 19.2.0, `lucide-react` only. Zero UI/CSS-framework deps, zero client-state lib. |
| Stylesheets | `app/globals.css` — 833 lines, shared tokens + primitives. `app/dashboard/workspace.css` — **3,976 lines**, workspace/client-screen specific. ~4,800 lines of hand-written CSS total. |
| Design tokens | CSS custom properties: `--surface`, `--line`, `--accent`, `--attention`/`--attention-bg`, `--error`/`--error-bg`, `--success-bg`, `--indeterminate-bg`, `--space-*`, `--text-*`, `--radius-*`, `--weight-*`. Consistently reused, not ad hoc per screen. |
| Buttons | One system: `.btn` + `.btn--primary/--secondary/--danger/--sm`, `.btn-icon`. A documented decision rule (comment at globals.css:312) maps action semantics → variant. Consistent everywhere it was checked. |
| Forms | `Field()` primitive (`components/Primitives.tsx`) binds label↔control; `.field`, `.field__hint`, `.field__error`, `.field--invalid`. No custom `<select>`/`<input>` skinning beyond focus rings — native controls, styled minimally. |
| Tables | `.table-card` (`TableCard()` primitive) — bordered, horizontally-scrolling, one shape used across Dashboard, Client Directory, Admin, Audit. |
| Badges/state | `StatePill` (`Primitives.tsx`) — **the one component that must never be treated as a generic shadcn `Badge`.** Four CSS namespaces (`badge`/`status`/`outcome`/`tag`) map 1:1 to the five legal-domain state axes; this separation is a correctness property (RESOLVED≠MATCH), not decoration. |
| Dialogs | **Hand-rolled, and duplicated.** `app/dashboard/page.tsx` implements the *same* dialog shape four separate times (lines ~1081, 1286, 1352, 1418 — each its own `dialogRef`, its own focus-restore `useEffect`, its own `if (e.key === "Escape") onClose()`), plus one more instance in `WorkspacePage.tsx` (`ws-modal__box`), one in `KeyboardShortcuts.tsx`, one non-modal variant in `AskDock.tsx` (`aria-modal="false"`, deliberately no focus trap), and one inline annotation popover in `DocumentPane.tsx`. All correct individually, but the four in `page.tsx` are near-identical copy-paste. |
| Tabs | Hand-rolled, and *already correctly accessible*: `WorkspaceLayout.tsx` and `ClientWorkspace.tsx` both implement real `role="tablist"`/`role="tab"`/`role="tabpanel"` with roving `tabIndex` and arrow-key navigation (`querySelectorAll('[role="tab"]')[next]?.focus()`). This is not a gap — it's already doing what Radix's `Tabs` primitive does. |
| Tooltips | None found as a distinct component; hints are shown via `.hint`/`title` attributes, not a floating tooltip primitive. |
| Alerts | `.banner`/`.banner--error` (globals.css) — plain, no dismiss animation, no variant beyond error. |
| Navigation | `.topbar`, `.topbar__nav` — flat, not a nav framework. |
| Responsive | Real breakpoints, not tokens-only: **32 `@media` rules** across the two stylesheets (640/720/760/899/900/1080/1100/1200/1400/1439/1499/1500px, plus `min-height`+`min-width` combos and 4 `prefers-reduced-motion` guards). This is a mature, tuned responsive system, not a placeholder. |
| Accessibility | 412 `aria-*`/`role=` attributes across `.tsx` files. `:focus-visible` (not `:focus`) used deliberately throughout, with a documented rationale (globals.css:245) for why mouse clicks shouldn't show a ring. Roving tabindex on tabs, `aria-modal`, `role="dialog"`, labelled dialogs — this is already a real accessibility investment, not a green field. |
| Existing shadcn usage | None. No `components.json`, no `components/ui/`, no Tailwind config anywhere in the repo. |

**Read on this:** the frontend is not an unstyled or accessibility-poor baseline that shadcn would
be rescuing. It is a deliberately hand-built, internally consistent, already-accessible system.
shadcn's value here is narrower than "add accessibility" — it's **de-duplication** (the four
copy-pasted dialogs) and **velocity on genuinely new surfaces**, not a rescue of a broken system.

---

## 2. What must never be touched

These are legal-correctness or security properties expressed as CSS/components, not styling
choices. A shadcn migration that touches any of them is out of scope regardless of how it looks:

| Component | Why |
|---|---|
| `StatePill` / `AXIS_CLASS` (`Primitives.tsx`) | RESOLVED≠MATCH depends on classification/status/outcome/tag rendering as visibly separate kinds of thing (DESIGN.md information-hierarchy rule). A shadcn `Badge` variant scale invites collapsing them into one channel. |
| `AccessRestricted.tsx` and all confidential-omission logic | `SEC-07`/`LEGAL-02`: an omitted field must look like *absence*, never disabled/greyed/padlocked. Radix's default disabled/tooltip pattern is the wrong shape by construction. |
| `DecisionControl.tsx`, `EscalateControl.tsx` | No-optimistic-UI + 409-conflict surfacing is bespoke business logic (a Legal Decision renders only after server confirmation); not a component-library concern. |
| `.table-card` density | DESIGN.md explicitly rejects card-in-card nesting and "lighter/airier" layouts for this product; shadcn's default `Card`+`Table` spacing trends the wrong direction for a document-dense legal review tool. |
| `WorkspaceLayout.tsx` / `ClientWorkspace.tsx` tabs | Already correct, already accessible, already tested. Nothing to fix. |

---

## 3. Where shadcn would genuinely help

Ranked by ratio of (duplication or missing-capability) to (risk of touching legal-sensitive code):

1. **Dialog consolidation — highest value, lowest risk.** The four `page.tsx` modals + `WorkspacePage.tsx`'s `ws-modal__box` + `KeyboardShortcuts.tsx` share one shape (focus-restore on open/close, Escape-to-close, `role="dialog"`/`aria-modal="true"`) implemented six separate times. A single Radix `Dialog` primitive, restyled to the existing `.ws-modal__box` visual treatment, removes five of those six hand-rolled implementations with **zero visual change** and less code to maintain. `AskDock.tsx`'s non-modal dialog (`aria-modal="false"`, deliberately no focus trap) should **not** be converted — that's a deliberate, documented deviation, not a bug.
2. **Tooltip primitive.** Currently absent; `.hint`/`title` is a weaker affordance. A Radix `Tooltip`, styled minimally, is additive — doesn't replace anything broken, just adds a capability the CSS system doesn't have yet.
3. **Form input primitives (Select, Checkbox) — only if/when a genuinely new form surface needs one.** Current native `<select>`/`<input>` + `.field` is fine as-is; don't convert existing forms (`ClientForm.tsx`, `UploadToClient.tsx`) just because a Radix `Select` exists. Reach for it on the next *new* form that needs a combobox/multi-select the native element can't do well.
4. **Popover/menu.** The row-action menu in `page.tsx` (`menuToggleRef`, arrow-key nav, Tab/Escape dismiss, lines ~223–245) is another hand-rolled implementation of what Radix's `DropdownMenu` does. Same profile as #1 — real but lower total duplication (one instance, not six).

**Not worth it anywhere found:** Tabs (already correct), Badge/state pills (forbidden, see §2), Table/Card (forbidden, see §2), a full alert/toast system (`.banner` is small and sufficient; no evidence of a need for stacked/auto-dismissing toasts).

---

## 4. Regression risks

- **CSS bleed.** Tailwind's Preflight reset changes base element styling (margins, `box-sizing`,
  `button` appearance) globally unless scoped/disabled. With 4,800 lines of existing CSS tuned
  against the current reset, an unscoped Preflight is the single highest-risk step in this whole
  effort — must be verified pixel-by-pixel on at least the login page and one workspace screen
  before merging.
- **Build pipeline.** `frontend/scripts/guard-build-target.mjs` (prebuild) and
  `frontend/scripts/deploy-frontend.sh` currently assume a plain Next.js build. Adding
  `postcss.config.*`/`tailwind.config.*` needs a real `npm run build` + `npm run deploy` dry run,
  not just `tsc --noEmit` passing.
- **Concurrency.** At time of writing, `git status` shows large uncommitted diffs in
  `workspace/WorkspacePage.tsx`, `workspace/icons.tsx`, `workspace/model.ts`,
  `dashboard/workspace.css`, and a new uncommitted `components/clients/` tree (Client Profiles
  feature), plus a second worktree (`readme-fallback-test` on branch
  `chore/readme-and-fallback-test`). None of those files should be touched by this work until
  that session's changes land.
- **Test selectors.** Vitest/Playwright suites assert on current DOM shape (e.g. `role="dialog"`
  attributes, specific class names). Converting a dialog to Radix must preserve the same
  `role`/`aria-*` output and ideally the same outer class name, or update the corresponding tests
  in the same change — never leave them silently stale.

---

## 5. Recommended order (incremental — each step independently shippable and revertible)

1. Add Tailwind + shadcn CLI config with Preflight **disabled or scoped** so no existing class is
   affected; verify with a visual diff on 2–3 representative screens before proceeding.
2. Consolidate the six hand-rolled dialogs into one Radix-based `Dialog` primitive, restyled to
   the current `.ws-modal__box` look. Update the affected tests in the same PR.
3. Add a `Tooltip` primitive (additive, no existing code touched).
4. Convert the `page.tsx` row-action menu to Radix `DropdownMenu`.
5. Only then, if a new form surface needs it, add `Select`/`Combobox` — do not retrofit existing
   forms.
6. Never proceed to tabs, badges, or table density (§2).

---

## 6. Files this touches when implementation starts

**Will change:** `frontend/package.json`, new `tailwind.config.*` / `postcss.config.*` /
`components.json`, `frontend/src/app/globals.css` (token bridging only), the dialog call sites in
`app/dashboard/page.tsx`, `components/workspace/WorkspacePage.tsx`, `components/KeyboardShortcuts.tsx`.

**Must not change:** `components/Primitives.tsx`, `components/AccessRestricted.tsx`,
`components/workspace/DecisionControl.tsx`, `components/workspace/EscalateControl.tsx`,
`components/workspace/WorkspaceLayout.tsx` tabs, `components/clients/ClientWorkspace.tsx` tabs,
`.table-card` styling, `components/workspace/AskDock.tsx`'s non-modal dialog, and everything
currently uncommitted by the other active session (see §4).

---

## 7. Owner decisions still open

None block starting step 1–3 above. One judgment call to make *at* step 1, not guessed here:
whether Tailwind's Preflight is disabled entirely or scoped to a `components/ui/` subtree —
decide after seeing the actual visual diff, not in the abstract.

---

## Addendum (2026-09-10) — step 1 implemented, and it isn't shadcn

⚠️ **Superseded by the "Final implementation" section below.** This addendum's claim that Radix
would break "for six call sites" was checked more precisely on request and found imprecise: it's
true for exactly one of the six. Left in place, not rewritten, per this project's own append-only
discipline for superseded reasoning — read it as the first-pass belief, not the final answer.

Starting the actual migration surfaced something the desk audit above missed: `vitest.config.ts`
locks the frontend's test environment to `"node"` and asserts components purely via
`react-dom/server`'s `renderToStaticMarkup` — a deliberate Step 39 choice, documented in that
file's own header comment, specifically to avoid adding a DOM testing library (jsdom + RTL).

Radix's `Dialog` (which is what shadcn's `dialog.tsx` wraps) renders its content through
`ReactDOM.createPortal` and depends on `useLayoutEffect`/refs against a real DOM. It cannot
render meaningfully — or, in the "closed" case the existing `KeyboardShortcutsHelp` test asserts
(`renders nothing while closed` → `renderToStaticMarkup` must return `""`), reliably at all —
inside that Node-only test strategy without adding jsdom, which is itself a separate rule-19
dependency decision this task didn't need to make.

This is exactly the §3/§F distinction the audit called for, just discovered one level deeper than
the desk review could see: **shadcn's `Dialog` would have made this worse**, not better — it
would have forced a parallel test setup for six call sites that already work, to fix
duplication that doesn't require it. Ranking still holds (dialog consolidation was the right
*first* target); the *tool* was wrong.

**What was built instead:** `frontend/src/components/Dialog.tsx` — a plain `useDialogFocus` hook
plus a `<Dialog>` wrapper, same markup and class names as before (`ws-modal`/`ws-modal__box`,
`role="dialog"`, `aria-modal`, `aria-labelledby`, Escape-to-close, scrim-click with an opt-out for
the one form dialog that needs it). All six call sites now use it:
`EditContractDialog`/`ArchiveContractDialog`/`DeleteContractDialog`/`TransferContractDialog` in
`app/dashboard/page.tsx`, `CompanyDocuments` in `workspace/WorkspacePage.tsx`, and
`KeyboardShortcutsHelp`. Zero new dependencies. `AskDock`'s deliberately non-modal dialog is
untouched. All 368 Vitest tests, `tsc --noEmit`, and `check:terms` pass unchanged.

**Consequence for §5 steps 2–5 (tooltip, dropdown menu, future Select/Combobox):** re-check each
one against this same test-environment constraint before reaching for the Radix/shadcn version.
A `Tooltip` or `DropdownMenu` that only needs to *render* (not hold live DOM focus/portal state)
may fare better under `renderToStaticMarkup` than `Dialog` did — verify with a throwaway render
before committing to either path, rather than assuming shadcn is available by default.

## Closing call (2026-09-10) — steps 2–5 are not being started

Re-checked each remaining candidate against the actual, current codebase (not the abstract case)
before touching anything further:

- **Tooltip** — zero consumers. Every hint in the codebase today is a native `title` attribute
  (`ClientDocuments.tsx`, `UploadToClient.tsx`, and others) and works. Building a `Tooltip`
  component with no call site is speculative scaffolding, not consolidation — skipped.
- **Row-action dropdown menu** (`page.tsx`'s `⋯` menu) — exists in exactly **one** place, already
  correctly accessible (arrow-key nav, Tab/Escape dismiss, focus management). One instance means
  there is nothing to de-duplicate, and a Radix `DropdownMenu` carries the same
  portal/`renderToStaticMarkup` risk `Dialog` did, for no net benefit — skipped.
- **Select/Combobox** — checked every form currently in the tree, including the in-progress
  Client Profiles work (`ClientDirectory`, `ClientForm`, `ClientDocuments`, `UploadToClient`, all
  four `page.tsx` dialogs): all native `<select>`, all working, no multi-select/combobox need
  anywhere — skipped.

**Adoption stays approved** (CLAUDE.md § UI and UX work) for the next case that actually clears
rung 1 of the ladder — real duplication, or a new surface a native element genuinely can't cover
— but none exists right now. Manufacturing a shadcn call site to use it would be exactly the
"shadcn because it's available" anti-pattern the owner's original instruction ruled out. No
further action pending a new concrete trigger; re-derive from the current code at that time
rather than resuming this list by default.

---

## Final implementation (2026-09-10) — Dialog rewritten on `@radix-ui/react-dialog`

The owner, after reviewing the first-pass reasoning above, asked for the exact claim to be
verified rather than assumed, and then approved a specific hybrid: Radix for the dialogs that
actually clear it, keep it simple for the one that doesn't.

**What verification found (empirical, not assumed):**

- Installed `react`, `react-dom`, `@radix-ui/react-dialog` in an isolated scratch directory
  (outside the repo) and reproduced this project's exact Vitest posture
  (`renderToStaticMarkup`, plain Node, `typeof document === "undefined"` confirmed).
  `Dialog.Portal` renders `""` for both open and closed states — silent, not a crash. Removing
  only `Portal` (same `Root`/`Overlay`/`Content`) renders correct markup. **Portal is the entire
  failure surface**; nothing else about Radix's Dialog has a problem there.
- Checked which test layer actually exercises each of the six dialogs. Result:
  `EditContractDialog`/`ArchiveContractDialog`/`DeleteContractDialog`/`TransferContractDialog`/
  `CompanyDocuments` have **zero** Vitest unit tests — they are validated exclusively by
  Playwright in a real Chromium browser (`dashboard-list.spec.ts`, `declared-metadata.spec.ts`),
  where Portal is completely normal (all are `"use client"`; Next SSRs once, then hydrates and
  the portal mounts, the same as any production Radix/shadcn app). Only `KeyboardShortcutsHelp`
  has a Vitest test that asserts on `renderToStaticMarkup` output directly — and that dialog's
  rendered behaviour is *also* already covered by `e2e/keyboard.spec.ts` in a real browser.
- So the true blocker was one component's one unit test, not a project-wide constraint.

**What shipped:** `components/Dialog.tsx` now wraps `RadixDialog.Root`/`Portal`/`Overlay`/
`Content`, used by the five dialogs above (call-site signatures unchanged — no other file needed
to change). `KeyboardShortcutsHelp` reverted to its own small, self-contained plain
implementation (the same shape as before consolidation), since it's the one exception with a
real reason to stay off Radix; that reasoning is now in its own file's header comment, not just
here.

**A real bug found and fixed during implementation, not by a test:** the first attempt rendered
`Dialog.Overlay` and `Dialog.Content` as siblings (Radix's own documented pattern) — but this
project's `.ws-modal` CSS centres its child via flexbox, so with nothing to apply that flexbox to,
the dialog rendered at `left: 0`, uncentered. Confirmed via a computed-style check in a real
browser (Playwright's `getBoundingClientRect`/`getComputedStyle` — the existing role/text-based
Playwright assertions did not catch this, since they don't inspect layout or paint). Fixed by
nesting `Content` inside `Overlay`, matching the original hand-rolled markup's parent/child
structure exactly; re-verified centred, opaque, and inside `.ws` afterward.

**A second real bug, caught by the same discipline, before it shipped:** Radix's `Dialog.Portal`
defaults to `document.body`. This project's `--ws-*` design tokens (`--ws-surface`,
`--ws-z-dialog`, `--ws-radius-card`, …) are scoped to `.ws`, not `:root` — the exact reason
`dashboard/page.tsx`'s row-action menu already needed a custom `menuPortalTarget()` fix on
2026-09-03 (portaling into `.ws` instead of `document.body`, after the default silently produced
a transparent, unz-indexed menu that Playwright's assertions also didn't catch). `Dialog.tsx`'s
Portal now targets `document.querySelector(".ws") ?? document.body`, the same fallback pattern.
Verified via computed style in a real browser: opaque `rgb(255, 255, 255)` background, correct
`z-index: 30`, centred at `left: 400` in a 1280px viewport (this test was a throwaway Playwright
spec, deleted after verification — not part of the committed suite, since it duplicated no
regression the existing suite doesn't already need covered by design changes, not test additions).

**Also verified in the same real-browser pass:** `dismissOnScrimClick={false}` on
`EditContractDialog` correctly blocks a scrim click while Escape still closes it;
`ArchiveContractDialog` (default `dismissOnScrimClick={true}`) correctly closes on a scrim click;
Delete and Transfer dialogs open and close cleanly. Screenshots taken and inspected, not just
asserted on. All 368 Vitest tests, `tsc --noEmit`, `check:terms`, and the 11 relevant Playwright
specs (`dashboard-list.spec.ts`, `declared-metadata.spec.ts`, `keyboard.spec.ts`) pass.

**Dependency added:** `@radix-ui/react-dialog` — the single package this required, no Tailwind,
no shadcn CLI. `AskDock`'s deliberately non-modal dialog remains untouched, as do all protected
surfaces in §2/§7 of this report.

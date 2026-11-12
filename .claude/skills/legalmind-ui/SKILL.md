---
name: legalmind-ui
description: LegalMind's UI and copy rules — type scale, spacing, colour roles, status chips, components, legal-text reading, the plain-language vocabulary for salespeople, and the pre-merge UI checklist. Use for ANY frontend task in LegalMind — a page, component, CSS/Tailwind change (even one line), layout, typography, colour, icon, empty/loading/error state, dialog, toast, table, chip, or any user-facing text, label, button, error or status wording in frontend/ or lib/labels.ts.
---

# LegalMind UI

Long form with measurements and sources (local research notes, outside the repo):
`/root/legalmind-clm-local/audit/ux-sales/DESIGN-FOUNDATION.md` and `PLAIN-LANGUAGE.md`. This file
is what you follow while building. The tokens live in ONE place: `frontend/src/app/globals.css`
`:root` (`--t-*` type, `--c-*` colour roles, `--s-*` space, `--r-*` radius). Every older name
(`--ws-text-*`, `--ws-ink-*`, `--text-*`, `--space-*`, `--radius-*`) is an alias of those — change
a value there, never at a call site.

**Order of authority:**
1. CLAUDE.md rules 1–23, rule 18 above all: the UI decides nothing legal and computes no status.
2. `.claude/rules/ui-ux.md`.
3. This skill.
4. DESIGN.md / DD-n, as reference only.

**Never change the behaviour of:**
- `StatePill` / `AXIS_CLASS`: separate axes, RESOLVED ≠ MATCH;
- `AccessRestricted` and any omission-as-absence;
- `DecisionControl` / `EscalateControl`: no optimistic UI, 409 handling.

They may only inherit the tokens below.

Also load `frontend-design:frontend-design` and `ui-ux-pro-max:ui-ux-pro-max` before writing markup,
and `dataviz` for any chart, meter or KPI tile.

## 1. Type: one scale, Plex Sans / Source Serif 4 / Plex Mono, weights 400·500·600 only

| Role | Token | px | Weight |
|---|---|---|---|
| Page title (one `h1`) | `--t-page` | 24/32 (no smaller on a phone) | 600 |
| Section `h2` | `--t-section` | 18/26 | 600 |
| Card / point title `h3` | `--t-subsection` | 16/24 | 600 |
| Sentences: summary, explanation, empty state, dialog | `--t-body` | 15/24 | 400 |
| Table/list rows, buttons, inputs | `--t-dense` | 14/20 | 400 (buttons 500) |
| Metadata, helper, counts | `--t-caption` | 13/18, muted | 400 |
| Chip label, table header | `--t-label` | 12/16 | 500 |
| Contract text | `--t-legal` | 17/28 Source Serif 4, max 68ch | 400 (the file's own bold: 700, a loaded face) |
| Clause quote in a panel | `--t-body` | 15/24 Source Serif 4 | 400 |
| IDs/money in tables | `--t-caption` | 13/18 Plex Mono, tabular-nums | 400 |

- **Nothing under 12 px.**
- No 550/650/700: they are not loaded and render as 600.
- No UPPERCASE and no letter-spacing on labels.
- Mono never for dates, times or statuses.
- Headings in DOM order: `h1` → `h2` → `h3`.

## 2. Space and shape

- Spacing comes only from tokens 4·8·12·16·24·32·48·64 (`--s-1..8`, `--ws-s1..s8`). `2px` is for borders and
  focus only. No 6, 7, 10 or 14 px.
- Rhythm: 4 label↔value · 8 between inline items · 12 inside a row · 16 card padding/gap · 24
  between sections · 32–48 between regions.
- Radius: 4 for inputs · 8 for buttons, chips and cards · 12 for dialogs · 999 for avatars and
  count bubbles only.
- Page max 80rem. Gutter 24, and 16 below 960.
- At 390 px and 320 px: no horizontal page scroll. A filter row that doesn't fit becomes one
  "Filter" menu.
- Touch targets: 24×24 minimum, 44 on phone layouts.

## 3. Colour: tokens only, no raw hex in components

- **Text:** `#0e1420`. Secondary `#2b3444`. Muted `#5b6478` (never on `#dfe3eb`).
- **Lines:** decorative `#e4e7ee`; control edges `#808899` (WCAG 1.4.11 needs 3:1).
- **Action:** `#2563eb`, hover `#1d4ed8`, tint `#eff4ff`. Links, the primary button, focus and
  selection only.
- **System error:** `#d52222`. Use it only when something failed (upload, save, analysis), never
  for a legal status.
- **The point statuses.** Same hue and icon on every screen; always word + icon + colour. Render
  them only with `<StatusChip>` (`components/StatusChip.tsx`), fed the server's `user_status` /
  `in_our_favour` — never a hand-rolled chip, never a status computed in the UI:

  | Status | Colour | Lucide icon |
  |---|---|---|
  | Matches | green `#11803a` / `#e9f7ee` | `circle-check` |
  | Change needed | orange `#c2410c` / `#fff3ea` | `pencil-line` |
  | Missing | orange `#c2410c` / `#fff3ea` | `file-plus` (**never red**) |
  | Needs a decision | indigo `#4f46e5` / `#eef2ff` | `scale` |
  | In our favour (server's flag) | teal `#0f766e` / `#e6f6f4` | `circle-arrow-up` |

- **Decided** is a neutral second line beside the status chip, never a replacement for it.
- **Effect for us** (better / no real change / worse) is neutral ink with an arrow icon, never a
  status hue.
- Nothing visual may suggest confidence: no %, score, meter, gradient or "risk level".

## 4. Components

- **Buttons**
  - Primary: filled, at most ONE per view, the action the status line names.
  - Secondary: white with a `#808899` border. Tertiary: a text link.
  - Height 36 (40 on phone), text 14/500, radius 8.
  - A label is 1–3 words starting with a verb, kept the same through the whole flow. No "→".
  - Icon-only buttons are allowed only for ⋯, close and zoom, with `aria-label` and a tooltip.
  - The same action has the same level on every page.
- **Status chip**: non-interactive, 12/16 500, radius 8, tint + hue + icon, an adjective (not a
  verb). Filters are segmented controls or selects, never look-alike chips. Hide zero-count
  filters.
- **Card**: white, 1px `#e4e7ee`, radius 8, padding 16, no shadow, never a card inside a card. A
  list is one card with dividers.
- **Table**:
  - Rows 40 (48 when a row has two lines), 14/20 text, sentence-case 12/16 muted headers.
  - Numbers right-aligned. "Open" plus ⋯ at the row end.
  - Never truncate status. Truncated names get a tooltip with the full name.
  - On the phone, a stacked list with no label/value grid.
- **Shared components — use these, never a local copy:** `StatusChip`; `ErrorState`,
  `LoadingState`, `EmptyState` (`components/Feedback.tsx`); `toast` / `toastFailure`
  (`components/Toast.tsx`); `FilePicker`; `PreviewPanel` (the exact PDF, downloads inside).
- **Empty state**: one centred block in the pane that would hold the content: icon, one line of
  what is true, one line of what to do, and the primary button. The other panes collapse.
- **Loading**: fixed-height skeleton rows (no shimmer). A spinner and verb inside the pressed
  button. Long jobs name the real step ("step 2 of 4"), never a fake %. `aria-live="polite"`.
- **Error**: `ErrorState`, inline at the top of the region. Title = what failed (no full stop),
  body = 1–2 sentences with the fix, one "Try again". Never beside a loading indicator (loading
  only while `data === null && !error`). The support reference prints only when there is one. Field errors sit under the field and are linked by
  `aria-describedby`.
- **Dialog**: only for a destructive confirm, recording a decision, or a preview. 480–640 wide.
  Cancel, then a primary named by its verb. Focus is trapped and returned. Esc closes. Full-height
  sheet at 390.
- **Toast**: `toast("Sent to Legal")` confirms the reader's own action (5 s, paused on hover or
  focus). `toastFailure("X could not be loaded")` reports a background failure with no region of
  its own (it stays until dismissed) — the replacement for `.catch(() => undefined)`. A failure in
  a region the reader is looking at stays inline. Never the only record.
- **Preview before download**: every generated file (reply, final contract, report) opens a
  preview first, with the Download button inside it.

## 5. Legal text

- Measure 60–75ch: `max-inline-size: 68ch`. Size 17/28 serif. 0.75em between paragraphs and
  1.25em between clauses. A hanging muted clause number.
- **No markup in display text**: no `**`, `##`, `\-`, `\[` or `.docx`. Strip it once in the shared
  display path, never per screen.
- Redlines use `<ins>`/`<del>`:

  | Change | How it looks |
  |---|---|
  | Added | Green tint + underline |
  | Removed | Red tint + line-through + muted text |
  | Formatting only | No highlight; a caption "Only the formatting changed" |
  | Whole clause added or the client's own clause | A normal-text block with a 3px green left rule and the header "The client added this clause". Never underline a whole clause |

## 6. Words (Sales sees these; lawyers see them too, plus a "Legal details" disclosure)

- **Point status, exactly:** Matches · Change needed · Missing · Needs a decision. Plus "Decided"
  as a second line, never instead of the status.
- **Who has it:** Your turn · Yours to answer · With Legal · Not sent to Legal · Waiting for the
  client.
- **Actions:**
  - on a change: Keep our wording · Accept their wording · Use our standard wording · Write new
    wording;
  - escalating: Ask Legal (one point) · Send to Legal (whole contract);
  - the reply: Answer changes → Prepare reply → Send reply;
  - the final contract: Prepare final contract · Check again.
- **One noun per thing:** point (never finding, issue or requirement) · change (the client's edit)
  · our standard (never Company Standard, position, playbook or rule) · the client · Compare (not
  Diff-Talk) · Clients.
- **A point is three lines:**
  - **What it says**: the client's clause, plain, 20 words or fewer, exact numbers.
  - **What we need**: our standard. Omit the whole line if the reader may not see positions; never
    show it as "hidden".
  - **What to do**: one verb-first action by one actor, consistent with the status.
- **Never shown to Sales:**
  - codes, IDs and enums (`[A-Z]{2,}[-_][A-Z0-9_-]+`, `AM-`, `AB-`, UUIDs, "Ref …");
  - `§`, "Section 31", "Constitution";
  - engine terms: requirement, evaluation, classification, deviation, finding, analysis, extraction,
    superseded, fallback, escalate;
  - legalese in our own copy: shall, hereinafter, notwithstanding;
  - confidence words: likely, probably, AI, score, %;
  - urgency theatre.
- **Style:**
  - Grade 8 or lower, sentences of 20 words or fewer, sentence case, "you" / "we" / "the client".
  - Errors say what happened and the fix, with no apology. Empty states say what is true and the
    next step.
  - Counts: "1 point", "3 points", "No points".
- All user-facing strings live in `lib/labels.ts` (or the area's single copy map), never inline in
  JSX. Server sentences pass through `withoutSectionRefs` before a Sales user sees them.

## 7. Pre-merge UI checklist (run every item; paste the evidence in the PR)

- [ ] **Screenshots** of every state at **1440×900 and 390×844**, as **sales** and **lawyer**
  (`local-stack` skill; never the deploy tree). States: full, empty, loading (throttled), error
  (API down / 500), no-access, long names, 1 vs many items.
- [ ] **No horizontal page scroll** at 390 and 320 (`document.documentElement.scrollWidth ===
  innerWidth`). Nothing is clipped without an affordance.
- [ ] **Type audit**: no computed `font-size` under 12px; only weights 400/500/600; no
  `text-transform: uppercase`. Exactly one `h1`, in heading order.
- [ ] **Tokens only**: the diff adds no raw hex, no off-scale px (allowed: 4/8/12/16/24/32/48/64
  and 2 for borders), and no new radius.
- [ ] **Contrast**: text ≥ 4.5:1 (≥ 3:1 for 24px+ or 18.66px bold); icons and control edges ≥ 3:1.
  Measured, not eyeballed.
- [ ] **Status**: each of the four words has the same hue and icon as on every other screen. A
  decided point still shows its status. No colour-only meaning.
- [ ] **No codes or jargon**: the rendered page text (as sales), run through
  `grep -E '[A-Z]{2,}[-_][A-Z0-9_]|AM-[0-9]|§|Constitution|requirement|evaluat|deviation|classification|\*\*|##|\.docx|Ref [A-Z0-9]{6}'`,
  returns nothing.
- [ ] **Plain words**: every new or changed string comes from `labels.ts` and matches the
  vocabulary. Flesch-Kincaid ≤ 8 on strings over 10 words. No confidence or urgency words.
- [ ] **Confidential omission**: as sales (without `legal_position.view`), "What we need" and every
  position is absent from the DOM, not hidden, greyed or locked.
- [ ] **One primary button per view**, labelled with the same verb as the toast or result it
  produces.
- [ ] **Preview before download** for every generated file.
- [ ] **Empty / loading / error states** follow §4. Loading is announced (`aria-live`). The error
  names the fix.
- [ ] **Keyboard**: everything is reachable by Tab with a visible focus ring. Dialogs trap focus,
  return it, and close on Esc. Shortcut hints are not shown to Sales.
- [ ] **Targets** ≥ 24×24 (≥ 44 on phone). Icon-only buttons have an `aria-label`.
- [ ] **WCAG 1.4.12**: with line-height 1.5, paragraph spacing 2em, letter spacing 0.12em and word
  spacing 0.16em injected, nothing overlaps or clips.
- [ ] **ruff / mypy** are not relevant here. Instead run `tsc`, `eslint` and the touched component
  tests. Visual baselines are CI-cut only: never run `--update-snapshots` locally.
- [ ] A **separate critic agent** reviewed the screenshots against this skill, and its findings
  were fixed or answered.
- [ ] Every item of the **never-do list** (§8) checked.

## 8. Never do — the agent-built-app tells (builder follows, verifier checks)

From the 2026-11-09 research (`AGENT-BUILT-APP-MISTAKES.md`, local notes). Referenced from the
`team-delivery` skill, so every UI batch runs it.

```text
NEVER DO (agent-built-app tells) — builder follows, verifier checks
1  No emoji as icons or bullets; Lucide only.        check: grep -P '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' in .tsx outside comments = 0
2  No decorative gradients, glow, glass, blur.       check: new linear/radial-gradient or backdrop-filter only for skeleton/mask/modal scrim
3  No literal colours, sizes or radii in CSS.        check: diff adds no #hex, no px font-size, no px border-radius outside :root tokens
4  No text under 12px; no ALL-CAPS labels/headers.   check: live probe min font-size >= 12px; no text-transform:uppercase on labels
5  Max 6 type sizes per page, from --ws-text-*.      check: probe distinct computed font-sizes <= 6
6  No raw machine text to a reader: no ** ## \- \[ , JSON, UUIDs, enum codes, model or vendor names.
                                                     check: page innerText has no /\*\*|^#{1,6} |\\[-\[\]]|[0-9a-f]{8}-[0-9a-f]{4}/
7  No overlap or overflow at 1440 and 390.           check: screenshots of both widths; scrollWidth <= innerWidth; no clipped pills
8  No generic copy ("How can I help you today?", "Welcome!", "Powered by AI").
                                                     check: every heading/empty state names this page's task and next step
9  Em dash and middle dot: max 1 per screen of UI copy; use a full stop or a label.
                                                     check: probe counts in UI chrome (document text excluded)
10 One name per thing: the nav word is used everywhere (Contracts, not documents).
                                                     check: grep the page's nouns against the nav labels
11 No silent failure: never .catch(() => undefined) / .catch(() => {}) on a user action or a visible load.
                                                     check: grep the diff = 0; each failure shows a plain message + retry
12 Every component ships empty, loading, error, no-access and full states.
                                                     check: one screenshot per state per persona
13 No control without an accessible name, at every width.
                                                     check: probe unnamed button/a/input = 0 at 1440 and 390
14 No outline:none without a :focus-visible ring.     check: Tab through the page; every stop shows a ring
15 No clickable div/span; use button or a.           check: grep '<(div|span|li)[^>]*onClick' = 0 (aria-hidden scrims excepted)
16 No dead or fake control: no empty handler, href="#", or button whose claim the API does not perform.
                                                     check: click every new control against the local API and see the result
17 No card-in-card, no chip and badge pile, no status dot without a defined state.
                                                     check: critic agent names each pill/dot and the state it means
18 No new helper before grepping for one (formatDate, shortDate and relativeTime already exist).
                                                     check: diff adds no function whose name or behaviour exists in lib/ or model.ts
19 No component file over 600 lines growing further; split by section first.
                                                     check: wc -l on touched .tsx; no touched file grows past 600 (existing ones must not grow)
20 No confidence, probability, "the AI thinks" or urgency theatre (rule 12).
                                                     check: npm run check:terms passes
21 No client-side legal logic or permission decisions; the UI only presents (rule 18).
                                                     check: no new permission/outcome computation in frontend/src
22 No secrets or NEXT_PUBLIC_ values; no tokens in localStorage.
                                                     check: grep NEXT_PUBLIC_ and localStorage in the diff
23 No "done" without evidence: the command output and the screenshots, checked by a fresh verifier.
                                                     check: the report links outputs and shots; the verifier re-ran them
24 Removing one default must not add the next one (no swapping purple for teal); follow the page plan.
                                                     check: critic compares against the plan, not against "less AI-looking"
```


# Diff-Talk: design plan

**IMPLEMENTED 2026-10-13** (branch `feat/legalmind-diff-talk`, not committed); the as-built record and its four deliberate differences from this plan are in §16. The owner asked for one solid plan before any
more UI changes: *"first make solid plan for everything how you present in this page"*.

This plan replaces piecemeal fixes. It is built **once**, in the order of §14, and shown
to the owner **once** at the end, with screenshots across every width in §13.

**DESIGN.md is not binding for this page** (owner, 2026-10-13: *"do not think design.md is
a final or you need to follow"*). The plan is designed from the reader's needs.
**Every device is supported**, phone included.

Nothing here touches the backend, the data, the URL model or the rules:
- 33.16: no verdict words;
- colours show wording only.

---

## 1. Who uses it, and for what

**Reader.** LeapSwitch sales and legal staff:
- mostly at a desk, on a laptop or a large screen;
- sometimes on a tablet or phone, for a quick check before a client call.

**Five jobs, in order:**

| # | Job | The page must answer |
|---|---|---|
| 1 | Pick the two documents | "Which is ours, which is theirs?" |
| 2 | See how far apart they are | "A few edits, or a different contract?" |
| 3 | Understand each difference | "What exactly did they change here?" — in seconds |
| 4 | Decide each one | "Keep ours, accept theirs, add it, leave it out" |
| 5 | Hand off | "Send my choices to Legal" |

**Success measures** (checked in §13):
- one difference understood in **≤ 5 s**;
- the choice reachable **without scrolling** on a laptop, for a typical clause;
- the 29-difference TOS pair fully decided in **under 5 minutes**.

---

## 2. Six principles: every decision below follows from these

1. **A difference is information, not an error.**
   - The page chrome stays neutral: no red edges, no red labels.
   - Red and green appear **only on the words** that differ (owner rule: colours for wording only).
2. **Show the change, not the whole clause.**
   - A reader opens a 40-line clause to find the 6 words that moved.
   - Lead with the changed sentences; the full clause is one tap away.
3. **The presentation follows the size of the change.**
   - A small edit, a total rewrite and a missing clause are three different reading tasks.
   - They get three display modes (§4), not one.
4. **One focus at a time.**
   - The current difference is unmistakable.
   - A decided difference folds to one line, so what remains is what is left to do.
5. **One structure on every width; only the arrangement changes.**
   - No separate "mobile design": the same regions, stacked differently (§5).
6. **Flat.**
   - At most one container level around content.
   - Columns are separated by space and a hairline, never by boxes.

---

## 3. Page anatomy: six regions

```
A  Page header      "Diff-Talk" (+ one line in setup only)
B  Pair bar         Ours: <name> · Client: <name>, each with Change
C  Review toolbar   filters (All · Changed · Added · Missing) · decided count · ↑ ↓ · Copy for Legal
D  Changes index    the list of differences, with each one's state
E  Comparison       the difference blocks
F  Action bar       phone only: ↑ · this block's choice · ↓
```

**B and C form one bar on wide screens**, and are pinned to the top.

**A shrinks to the title alone once a review is open.** Its explanation lives in setup, where
it is needed.

---

## 4. The difference block: the heart of the page

### 4.1 Anatomy (desktop)

```
│▌ 2  Terms of Service   ⟲ Wording changed · 2 of 5 sentences   [ Keep ours | Accept theirs ] │
│    OURS (p. 1)                           │ CLIENT (p. 1)                                    │
│    …payable within ░fifteen░ days…       │ …payable within ▓forty-five▓ days…               │
│    ⋯ 3 unchanged sentences ⋯             │ ⋯ 3 unchanged sentences ⋯                         │
│    Show the full clause (34 lines)                                                           │
─────────────────────────────────────────────────── hairline ─────────────────────────────────
```

- **Header line.** It holds:
  - the number;
  - the title, in title case;
  - the **kind tag**: neutral grey with an icon — `⟲ Wording changed`, `＋ Added by the client`, `− Missing from the client's`;
  - the size of the change ("2 of 5 sentences");
  - the **choice**, right-aligned.

  The choice is always in view with the heading, never 40 lines below.
- **Column headings "Ours / Client"** appear once per block, small, with the page number.

  On the desktop they are also pinned at the top of the comparison, so a long block never loses them.
- **No box around each text column.** Space and one vertical hairline separate the columns.
- **Current block:** a 3 px accent bar on the left (`--accent`, blue). Never red.
- **Blocks are separated by a hairline and spacing**, not by cards.

### 4.2 Three display modes (chosen by the data, not the reader)

| Mode | When | Shows |
|---|---|---|
| **Edited** | Paired, and at most half the sentences differ | Only the changed sentences, with word marks, each with one unchanged sentence of context. The rest folds to "⋯ n unchanged sentences ⋯", which can be opened. |
| **Rewritten** | Paired, and more than half the sentences differ | Both texts in full, **no word marks** (a page of marks is noise). The tag reads "Rewritten — read both". |
| **One-sided** | Added or missing | The text on its own side. The other side shows one muted line: "Not in our document" or "Not in the client's contract". |

The thresholds use what the page already computes (`changedSentences`). No backend change.

### 4.3 How words are marked

- **Ours:** the words that differ get a soft red tint and a solid bottom rule.
- **Client:** the same, in green.
- **No strikethrough.** Side by side, nothing is "deleted"; a strike would make our text hard to read.
- **Neighbouring marked words merge into one run**, spaces included. The current word-by-word blocks with gaps look choppy.
- **Screen readers hear** "ours only: …" and "client only: …". Colour is never the only signal.
- **Contrast:** marked text stays at least 4.5 : 1 on its tint.

### 4.4 Long text

- A block's text is clamped at **12 lines**, with a soft fade and "Show the full clause (n lines)".
- In **Edited** mode the clamp rarely triggers, because unchanged sentences are folded first.

### 4.5 The choice, and what a decided block becomes

- **Choice words by kind** (unchanged from today):
  - Changed: Keep ours / Accept theirs;
  - Added: Leave it out / Add it;
  - Missing: Keep ours / Leave it out.
- **Control:** a native radio pair, styled as a segmented control, at least **44 px** tall.
- **After a click:**
  - the block **folds to one line** — `✓ 2  Terms of Service — Accept theirs   Change`;
  - the page moves to the next undecided block.
- **A keyboard choice does not move**, as today.
- **"Change" reopens the block.** Nothing is lost.

---

## 5. Layout by width

The layout follows the space available, not the device.

| Width | Changes index (D) | Comparison (E) | Bars |
|---|---|---|---|
| **≥ 1280** | A fixed column on the left (280 px), scrolls on its own | Two columns, Ours \| Client | B + C in one pinned row |
| **1024–1279** | A column (240 px); titles may wrap to two lines | Two columns | One row; Copy for Legal shows its icon only, with its label kept for screen readers |
| **768–1023** (tablet) | Hidden; a **"29 changes" button** in the toolbar opens a side panel | Two columns, narrower margins | Two rows: B, then C |
| **< 768** (phone) | A **bottom sheet** from the "29 changes" button | **One column:** "Ours" stacked above "Client", each labelled, in that order always | B collapses to one line ("Ours TOS ⇄ Client TOS ▾", tap for details); C becomes F at the bottom |
| Phone landscape, 200 % zoom | Same as phone | Same as phone | Bars shrink to 44 px |

### Desktop (≥ 1280)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Ours  Leapswitch TOS · website, 9 Oct  Change │ Client  CloudPe TOS · v1  Change │ 3/29 decided │ ↑ ↓ │ Copy for Legal │
├──────────────────────┬───────────────────────────────────────────────────────────────────────┤
│ All 29 Chg 8 Add 4   │            OURS                  │            CLIENT                  │
│ Missing 17           ├──────────────────────────────────┴────────────────────────────────────┤
│ ✓ 1 Opening text     │ ✓ 1  Opening text — Leave it out                         Change       │
│ ▌2 Terms of Service  │ ▌2  Terms of Service  ⟲ Wording changed   [Keep ours|Accept theirs]   │
│ ○ 3 Copyright        │     …within ░fifteen░ days…       │ …within ▓forty-five▓ days…        │
│ ○ 4 Use              │ ───────────────────────────────────────────────────────────────────  │
│ …                    │ ○ 3  Copyright  ＋ Added by the client       [Leave it out|Add it]     │
│ 12 the same ▸ show   │     Not in our document           │ Copyright The information…        │
└──────────────────────┴───────────────────────────────────────────────────────────────────────┘
```

### Tablet (768–1023)

```
┌ Ours Leapswitch TOS  Change · Client CloudPe TOS  Change ─────────────────┐
│ [≡ 29 changes]  3/29 decided              ↑ ↓   Copy for Legal           │
├───────────────────────────────────────────────────────────────────────────┤
│ ▌2 Terms of Service  ⟲ Wording changed          [Keep ours|Accept theirs] │
│   OURS                            │ CLIENT                                │
│   …within ░fifteen░ days…         │ …within ▓forty-five▓ days…            │
└───────────────────────────────────────────────────────────────────────────┘
```

### Phone (< 768)

```
┌ Diff-Talk ─────────────────────┐
│ Ours TOS ⇄ Client TOS       ▾  │   ← one line; tap shows both names + Change
├────────────────────────────────┤
│ ▌2 Terms of Service            │
│ ⟲ Wording changed · 2 of 5     │
│ OURS · p. 1                    │
│ …within ░fifteen░ days…        │
│ CLIENT · p. 1                  │
│ …within ▓forty-five▓ days…     │
│ ⋯ 3 unchanged sentences ⋯      │
├────────────────────────────────┤
│ ↑ │ Keep ours │ Accept theirs │ ↓ │   ← action bar (F): thumb zone, 56 px
│ 3 of 29 decided · ≡ Changes    │
└────────────────────────────────┘
```

**On a phone the choice lives in the action bar**, for the current block. In a two-thumb
grip the bottom of the screen is the easy reach.

Pinned chrome on the phone:
- the top line is 44 px;
- the action bar is 56 px plus one small line;
- **≤ 14 % of an 844 px screen** in total (today about 17 %).

---

## 6. The changes index (D)

- **Rows.** Each row has:
  - the number;
  - the title (up to two lines, then an ellipsis with the full title on hover or focus);
  - a kind icon;
  - a **state glyph**: ○ undecided, or ✓ with the choice word ("✓ Accept theirs").

  "Not decided" is **not** printed 29 times. Absence of a tick says it.
- **Current row:** a 3 px accent bar and a light tint. The list scrolls to keep it in view.
- **Filters:** one segmented row — `All 29 · Changed 8 · Added 4 · Missing 17`.
  - The counts are the summary, so there is no separate summary strip.
  - They use neutral colours.
- **Footer:** "12 read the same ▸ show". The unchanged clauses stay hidden by default, as today.
- **Phone:** the same list in a bottom sheet, opening at 70 % height. Tapping a row closes the sheet on that block.

---

## 7. Pair bar (B) and setup

- **Pair bar.** Both documents are drawn **identically**: a label chip (Ours / Client), the name, one meta line, and Change.
  - Today ours is a link and theirs is plain text.
  - The name opens the document in a new tab, for both sides.
  - The bare "vs" is dropped; the order and the chips say it.
  - Raw upload names are cut with an ellipsis, with the full name on hover.
- **Setup** keeps the two numbered slots (it works). Three small fixes:
  - the footnote is left-aligned like everything else;
  - the floating Ask button is hidden on Diff-Talk, in setup as well as in review;
  - on a phone the slots stay stacked.

---

## 8. Visual language (existing tokens only)

| Element | Token / rule |
|---|---|
| Page background | `--surface` (existing workspace background) |
| Hairlines | `--line` |
| Current block, focus | `--accent` |
| Kind tags | neutral text colour + icon, no fill colour |
| Word marks | `--ws-diff-line` / `--ws-diff-word` (red for ours, green for client), tint plus a 2 px bottom rule |
| "Needs attention" | not used: no difference is urgent |
| Contract text | the house serif, 16 px / 1.6, at most about 68 characters per line |
| Interface text | the house sans, 13–14 px |
| Spacing | the `--ws-s*` scale: 8 within a block, 16 between parts, 24 between blocks |
| Progress | "3 of 29 decided", text plus a thin neutral bar. No colours or celebration: it is a count, not a game. |

---

## 9. Every state the page can be in

| State | What the reader sees |
|---|---|
| Loading | A skeleton in the real layout (bar, index rows, two text columns), never a spinner alone |
| Identical documents | "These two read the same, clause by clause." The unchanged list stays reachable. |
| Some pages unreadable | One quiet banner under the pair bar: "Pages 19, 22 of <name> have no readable text" |
| No differences in a filter | "No added clauses." with a one-click way back to All |
| All decided | The decided count turns into "All 29 decided", and Copy for Legal becomes the primary button. No confetti. |
| Comparison refused / not found / error | The current plain messages, placed where the comparison would be, with the way out (Change, Back) |
| Very large (200+ differences) | Rendering stays lazy (`content-visibility`); the index is a plain list, so it stays fast |

---

## 10. Interaction

- **J / K** move to the next / previous difference, as today.
- **New:** in a focused block, **1 / 2** choose the left / right option.

  The keys are shown in a "Keyboard" help line on desktop only.
- **Clicking a choice** folds the block and moves on. **Keyboard** choices stay put.
- **Change** on a folded block reopens it. Choices stay in the browser, as today.
- **Back and Forward** follow the URL, as today.
- **Motion.** One 150 ms fold or expand; nothing else animates.

  Reduced motion turns it off.

---

## 11. Accessibility (built in, not checked after)

- Touch targets are **≥ 44 px**, with ≥ 8 px between them.
- Focus is always visible. The pinned bars never cover a focused element: `scroll-margin` already handles this.
- Landmarks: the pair bar is a `header`, the index a `nav` named "Changes", the comparison `main`.
- Each block is a `section` named by its title.
- The choice is a real radio group, announced as "Terms of Service, your choice".
- Marks are announced as "ours only / client only". Colour is never the only signal.
- The page reflows at **200 % zoom** with no sideways scroll.
- Movement and choices are announced through one polite live region, as today.

---

## 12. What does not change

- The backend, the alignment, the API and the data.
- Choices are stored per pair in the browser. Server saving awaits the owner.
- The URL model: a comparison is a link, and Back undoes a step.
- No verdict words anywhere (33.16).
- Colours mark wording only.

---

## 13. Test matrix: run once, at the end, before the owner sees anything

| Widths | Pairs | Checks |
|---|---|---|
| 320 · 390 · 430 · 768 · 1024 · 1280 · 1440 · 1920 · phone landscape 844×390 · 200 % zoom at 1280 | e2e synthetic pair · our TOS vs the client's TOS (29 differences) · MSA template vs the Feb draft (4 changed) · a document against itself | No sideways scroll · pinned chrome ≤ 14 % (phone) · choice visible with its heading · ≥ 44 px targets · contrast ≥ 4.5 : 1 on tints · counts agree (index = filters = blocks) · screen-reader names · keyboard-only walk-through · the "5 minutes for 29" timing · no page errors |

The `e2e/diff-talk.spec.ts` selectors are updated in the same pass.

Before and after screenshots of every width are attached to the owner review.

---

## 14. Build order: one pass, one review

1. **Flat block and tokens.** Remove the card nesting and the red chrome; add the neutral kind tags, the accent current bar and the hairlines.
2. **Display modes:** Edited, Rewritten and One-sided; merged word marks; the 12-line clamp.
3. **Choice in the header, and folding of decided blocks.**
4. **Index and toolbar:** state glyphs, one filter row, pinned column headings, the symmetric pair bar.
5. **Width tiers:** tablet side panel, phone stacking, phone action bar, bottom sheet.
6. **All states** (§9) and the setup fixes (§7).
7. **The test matrix** (§13) and the spec update. Then **one** owner review with screenshots.

There is an optional desktop-only checkpoint after step 3, only if the owner wants one.

---

## 15. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| a | **Decided blocks fold to one line.** | Yes. What is left on screen is what is left to do. |
| b | **Edited mode shows the changed sentences first** (with context), the full clause on tap. | Yes. A reader can always open the whole clause in one tap; nothing is hidden without a visible way to open it. |

---

## 16. As built (2026-10-13)

Owner: *"do not ask me for choices do what is the best"*. §15's two recommendations
were taken: decided blocks fold, and Edited mode shows the changed sentences first.

**Four differences from the plan, each found by testing:**

1. **The phone's choice stays in its block** (below the text), not in the bottom bar.
   - "Current" on a phone follows the scroll, so a bar choice could land on the wrong difference.
   - The bottom bar keeps ↑, the position with the list, Copy and ↓.
2. **"Rewritten" is measured by shared words, not sentences.**
   - The rule: under half the words in common.
   - By sentences, a one-sentence clause with one word changed counted as 100 % rewritten.
3. **Filters are four equal cells**, the count over its word. A pill row wrapped in the 18.5 rem list.
4. **A jump holds "current" until the reader scrolls** (wheel, touch, scroll keys, a pointer press).
   - It replaces the timed guard.
   - Jumping to the last difference, which a page cannot bring to the top, reverted "current" to the one above.

**Also done:**
- On phone, the long-text cut applies to each side separately (13 rem), so ours never hides the client's.
- Pins are released on a short screen (≤ 520 px tall, a phone held sideways).
- Hover styles apply only where hover exists.
- Block titles are `h2` (the page went h1 → h3).
- The split viewer's 28 px marker column is zeroed through its `<col>`, so all three modes start on the same line under the pinned headings.

**Measured:**
- No sideways scroll at 320 · 390 · 768 · 1024 · 1280 · 1440 and 844×390.
- No control under 30 px.
- No page errors.
- Diff-Talk e2e 12/12, vitest 614/614, `npm run lint` clean, real-browser QA 33/33.

### Added after a user check: Full documents (2026-10-13)

Owner: *"think like user — are you able to check both docs side by side as diff?"* The honest answer was **no**:
- the page showed only the differences;
- its "show the same clauses" checkbox put same-wording clauses under **Ours only**, with the Client column empty — which reads as the client having nothing there.

**Fix:** one switch in the pinned bar, **Changes only | Full documents**. It replaces the checkbox.
- Full documents shows every clause in reading order, **both sides filled**:
  - same wording appears on both sides, unmarked;
  - changed clauses appear in full, with their words marked;
  - added or missing clauses show the empty side, labelled.
- Rows stay aligned, so the two documents scroll together.
- Nothing is folded or cut, and the choices work as in Changes only.
- **On a phone** a same-wording clause is shown once, labelled "Same wording", not printed twice.
- The pinned bar is now two rows at every width (the documents, then the controls), so the names are not cut.

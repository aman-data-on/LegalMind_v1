# CLM R&D — 08 · Phase 1 UI design pass (Changes, header, Contracts, To-do, bell)

`PROPOSAL` — 2026-11-02. Presentation only, in `/root/legalmind-worktrees/clm-p1` (uncommitted). It locks nothing,
amends no decision, and touches no backend code. Read with [03](03-ux-information-architecture.md) §3.7, §6.6, §9 and
[07](07-PHASE1-REQUIREMENTS.md) R1–R10.

**Knowledge base read first:** DESIGN.md, docs/design/* (DESIGN_SYSTEM, DESIGN_DECISIONS DD-1…DD-26, UI_PATTERNS,
UX audits, roadmaps, master prompt, shadcn/Tailwind reports), 03 and 07 here, CLAUDE.md § UI and UX work,
`workspace.css` tokens. DESIGN.md is reference, not binding (owner, 2026-10-13); the departures are listed at the end.

## Problems → decisions

| # | Problem (seen on screen) | Decision | KB basis |
|---|---|---|---|
| 1 | `/contracts/{id}/changes` (the address To-do, the bell and "File into contract" link to) opened the **Document** tab; only `?tab=changes` worked. | The workspace reads the tab from the path (`contractTabFromPath`), and switching tabs rewrites the path (`contractHref`). `?tab=changes` still works. | 07 R7, `AM-263` |
| 2 | "Needs a holder" / "Ask someone with the right" — jargon to a salesperson. | One vocabulary: **Needs Legal**, **Yours to answer**, **Deal owner answers**, **In our favour**, **Ask Legal**. "Legal Decision" stays, since it is the record's own term. The route reasons are rewritten in plain words ("None of our standards covers this clause, so Legal decides"). | 03 §6.6 ("Ask Legal to accept theirs"); frontend-design: name by what users understand |
| 3 | 82 rows, three lines each, with **"Changed without tracking" on every row**. It was pure noise, because the banner already said all 82 were untracked. "Wording changed" was also on every row. | The row is two lines: where it is, then only what is different about it. The kind shows only when it is not a wording change, and the legend says so. The **Untracked** tag shows only when some rows are tracked. The tag says **Needs Legal** / **In our favour** while a row is open, and ✓ **Kept ours** / **Accepted theirs** once answered. Open rows are in full ink and answered rows are quieter, so the list reads as "what is left" with no colour and no counter. | DESIGN.md density; "no urgency theatre"; ux "chip collection reflow" |
| 4 | Groups were a bare "1", "2" with no counts and could not be collapsed. | Each top-level clause has a **sticky, collapsible heading** (a real button, `aria-expanded`) showing its number, its heading where the document has one, and "*n* open" or "done". A group opens on its own when j/k moves into it. | 03 §9.2 keyboard; DESIGN.md "real semantic disclosure" |
| 5 | The filters wrapped onto three lines inside a 240 px column, and the default was "All". | The filters move into **one toolbar row** above the grid, with the progress count ("**0** of 82 answered · 82 still to answer") and **Prepare our reply** on the right, as in 03 §6.6. The default is **Yours to answer** when there is any, otherwise **All**. | DESIGN.md "default views bias toward the task" |
| 6 | "Yours to answer" said 82 for the owner while To-do said 20: holder rows counted as the owner's. | `matches("mine")` covers the owner's own routes, plus a holder change once Legal has accepted it, and for a holder the changes only Legal decides. It now equals To-do (20 for owner@, 62 for counsel@). | 07 R8; one number per fact |
| 7 | The answer card had no hierarchy: who answers and why was hidden inside "Explain this", the reason field had only a placeholder for a label, and the two "Decide" controls were unnamed. | Order: **where → who answers and why** (a ruled strip) → **the answer given** (✓ Kept ours — Owner, 2 Nov, "reason") → the review's words → **Your answer / Change your answer** (visible label "Reason (optional, one line)") → **Ask Legal** or **Your Legal Decision**, one named block per finding (status word · requirement code), with `DecisionControl`/`EscalateControl` placed unchanged → history (only when there is more than one entry) → Explain this. The route reason is no longer repeated in Explain this. | 03 §3.7 provenance; DESIGN.md "Escalation is a request; Decision is an act" |
| 8 | The holder's accept button wrapped onto two lines: "Accept theirs (recorded as your answer — no standard measures this)". | The fact moves to a sentence above the field, and the button reads **Accept theirs**. | frontend-design: a CTA says exactly what happens |
| 9 | Manual rows (AB-151) appeared as an inline `role=alert` block under the bar. | A real **confirmation dialog** (the existing `Dialog`): "*n* answers can't be written into the client's file", a list, **Cancel** / **Prepare the reply without them**. This is a genuine blocking choice, which is the one case where DESIGN.md allows a modal. | DESIGN.md anti-patterns (modals only for genuine interruptions) |
| 10 | "Download Word" and "Download PDF" link buttons sat off their text baseline, and "Marked sent" was a bare word. | Icon buttons **Word** and **PDF**. **Mark sent** is the primary action at that point. Once sent it reads "✓ Sent 2 Nov". | DESIGN.md: an action's label survives into its result |
| 11 | The header showed **"Draft"** (declared status) next to **"Client returned"** (deal stage), which read as a contradiction. The stage also said **"0 days"**. | When the server sends a stage, the stage is the header's status. The declared status shows beside it only when it is not `DRAFT`. "0 days" now reads **today**. | 07 R7; deal-stage vocabulary kept separate from the five axes |
| 12 | Contracts list: "Client returned 0 da…" overflowed into the Status column. | The stage badge shows without days, and the age sits under it in small muted text. Stage pills that hold deals read in full ink, and empty ones stay quiet. | DESIGN.md: never drop a column that carries state |
| 13 | To-do: the time and the action were misaligned, and the action was a bare link. | A three-column row (what and which contract · since · action). The action is a real secondary button. It stacks at ≤640 px. | — |
| 14 | Bell: the empty state was one run-on sentence, and there was no way on to To-do. | "No notifications" plus one sentence of what will appear, and an **Open your to-do** footer. The unread dot is unchanged (no red counter). | 07 R9; no urgency theatre |
| 15 | Phone (390 px): the Changes grid overlapped itself. | Below 1100 px: one scrolling column, the list capped at 42vh, then the card. The card **carries the changed passage itself** (a keyboard-focusable region, capped at 36vh), so the passage column is not repeated and nothing is lost. 44 px targets on coarse pointers. | 03 §9.1; DESIGN.md split-pane collapse must be defined |
| 16 | Collaborators: a long header button label, loose dialog spacing, and a 16 px field label. | Icon button "Add colleague" / "*n* colleagues", with the full phrase as its accessible name. Tighter intro and empty row. The add field is separated by a rule. | — |
| 17 | File into contract: the select had no visible label. | A visible "File into" label. | ux: visible labels |

**Not touched, by rule:** `StatePill`/`AXIS_CLASS`, `AccessRestricted`, `DecisionControl`, `EscalateControl` (placed
only). Controls a reader may not use stay absent. Positions stay absent when omitted. Nothing on these screens shows a
probability or confidence.

## Departures from DESIGN.md / DD records

- **Phone width** is designed here, although DESIGN.md says "not a V1 requirement". 03 §9.1 and the brief require it.
- A **modal** for the manual-rows confirmation. DESIGN.md allows a modal only for a genuine blocking choice, and this is one.
- The Changes list carries **no colour at all for state**. Open vs answered is shown by weight, which is stricter than DD-12.

## Screenshots

Scripts: `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/ui-pass/shots.mjs`.
Before: `…/ui-pass/before/` (the same code before this pass, built on :3499). After: `…/ui-pass/after/`. File names are
`{owner|counsel}-{d=1440|m=390}-{surface}.png`. Key pairs:

| Surface | Before | After |
|---|---|---|
| Changes, owner | before/owner-d-changesB.png | after/owner-d-changesB.png |
| Changes, holder, measured change | before/counsel-d-changesB.png | after/counsel-d-changesB-measured.png |
| `/changes` path | before/owner-d-changesA-path.png (Document tab) | after/owner-d-changesA-path.png |
| Empty filter, focus | before/owner-d-changesA-jj.png | after/counsel-d-changesB-empty.png, -focus.png |
| Phone | before/owner-m-changesB.png | after/owner-m-changesB.png, after/counsel-m-changesB-card.png |
| Contracts list | before/owner-d-contracts.png | after/owner-d-contracts.png |
| To-do | before/owner-d-todo.png | after/owner-d-todo.png, after/counsel-m-todo.png |
| Bell | before/counsel-d-bell.png | after/counsel-d-bell.png |
| Colleagues | before/owner-d-collab.png | after/owner-d-collab.png |

## Still open

- **Server:** To-do's `changes_to_answer` counts owner-route rows only, and leaves out `favour` rows. The Changes filter includes them, so the two differ when a favour row exists.
- **Server:** a holder row on a prepared reply still offers "Change your answer".
- Not seen in a browser: the manual-rows dialog and "File into contract". Triggering them writes to the shared scratch DB, so I left them alone.
- Existing, out of scope: the "Send for review…" select collapses to a bare chevron at 390 px, and the stat-card hero on Contracts.

---

## Pass 2 (owner feedback, 2026-11-02)

Owner, on the reply contract's Document tab: *"on the drafting page I see nothing, and everything does not look well
organized"*, then *"the doc is not well aligned … does not follow the standard of spacing, alignment … in a contract"*.
KB re-read first (as for pass 1). Built in `/root/legalmind-worktrees/clm-p1`, uncommitted.

### Problems → decisions

| # | Problem | Decision | Where |
|---|---|---|---|
| 1 | The reply (v3) said "not analysed yet". It was prepared by a script, and only the browser's `chainAnalysis` ever reviewed a reply. | `prepare_reply` opens the Review on the newest snapshot through `reviews.open_review` (taken out of `POST /reviews`, so there is one implementation) and runs `dispatch_analysis`, the same function `/analyze` uses: inline without a broker, and with one queued **after the commit** (`after_commit=True`), so no worker can read the Review before it exists. The browser no longer chains a second analysis after the reply. Key Obligations is unchanged and still runs when the panel opens. It fails on every version locally because there is no generation key (`GenerationRefused`, also on v2), so the reply is not the cause. | `api/routers/reviews.py`, `negotiation.py`, `worker/dispatch.py` |
| 2 | The Document tab did not say that this version is our reply. | A notice above the workspace: "Version 3 is our reply to the client's version 2 — *N* of our changes are in it as tracked changes; *M* to restore by hand in Word (clauses)", then **Download Word** · **Download PDF**, and "Sent to the client on *date*" once sent. The counts are saved on the version when the reply is prepared (`reply_tracked`, `reply_by_hand`) and sent as `document_version.reply`. They are omitted for an older reply. The scratch v3 was backfilled from its own `document.reply_prepared` audit event. | `ReplyNotice`, `serializers.py` |
| 3 | After the reply, the stage read "Drafting". | New stage **READY_TO_SEND** ("Ready to send"): the latest version is our reply (`reply_to`) and is not sent. Internal review wins over it, because Legal is looking at it. Marked "our turn" like Client returned. The vocabulary stays the deal's own and shares nothing with the five axes. | `domain/deal_stage.py`, `StageBadge` |
| 4 | Four columns at 2000 px (Contents · document · Summary · a second Ask column) and a floating Ask over the Changes card. | **One Ask surface**: Ask is the third tab of the side column at every width. This is DD-17 §4 / `AM-57` r4 (docked, one column). It withdraws the 2026-10-08 seventh pass's ≥1680 px Ask column, since the owner's latest ruling wins (the design tie-break). The width goes to the document. The global floating Ask is hidden on the contract record, which already has Ask in its row and in the top menu, as Diff-Talk does. | `WorkspaceLayout`, CSS |
| 5 | Underlined text links beside a version select, wrapping onto two rows. | One record header on both tabs. **Row 1:** title · type · stage · declared chips, then Colleagues · Share · ⋯ · **the stage's primary action** (Ready to send → **Mark sent**; Client returned → **Answer changes**, and on Changes that tab's own "Prepare our reply"; otherwise **Upload new version**). **Row 2:** Document \| Changes *n* as underline tabs · a **version switcher that names each version's role** ("3 · Our reply to v2", "2 · Client's", "1 · Ours", "Signed") · Send for review · View report. Under ⋯: Upload new version (when it is not the primary action), Compare versions, Compare in Diff-Talk. Mark sent is shown only when `can_send`, a new presentation flag on the changes list, which is the `mark_sent` check and outlives the round. That fixes the old bar, which hid the reply's files and Mark sent as soon as the round closed. | `WorkspacePage`, `ClientMenu` (exported, reused) |
| 6 | "Changed / Removed / Added" boxes broke the reading. | Changes are marked in the text, Word-style: the new words are underlined, the replaced words are struck just before them (drawn from `data-del` by CSS, not text), and there is a 2 px change bar in the margin. A change is placed inline only when its words can be found in order and without guessing. Otherwise it goes on one quiet "Also changed: removed ';'" line at the text's indent. A **Hide changes / Show changes** toggle in the document toolbar is remembered per browser. | `reading.ts`, `DocumentPane.RowText` |
| 7 | The sheet was justified with rivers, numbers sat flush with the text, and there was no hierarchy. | Contract typesetting, derived from the row text and the parser's `section_number` only (rule 17: the `<p>`'s text content is still exactly the evidence string, so selection, highlight and annotation offsets are unchanged). Numbers **hang in a gutter** and wrapped lines align with the text. 1 and 1.1 sit flush, (a) is under 1.1's text, (i)/i. is under (a)'s text, and 4.3.1 is one step in. "(i)" after "(h)" is a letter. A heading's list number (AM-185) is drawn in the gutter. Text is **left-aligned**, 74ch measure, 1.55 leading, 0.55 em paragraph space, headings with 1.5 em before and 0.5 em after (`break-after: avoid`). "AND"/"BETWEEN" are centred. "WHEREAS," is a bold label, with lettered recitals hung. Defined terms are in weight. At phone width the steps shrink to 60%. | `reading.ts`, CSS |
| — | Audit: Changes rows that only repeated their group ("3" under "3"). | The row says its passage's first words instead (`rowLabel`). | `ChangesPane` |
| — | Audit: at 390 px two tab rows both said "Document". | The narrow region tab is **Text**. Phone header buttons are icon-only, with their words kept as the accessible name. On a phone the notice is its title with **Word**/**PDF**, plus "Sent on" once sent. | |

**Not touched:** `StatePill`/`AXIS_CLASS`, `AccessRestricted`, `DecisionControl`, `EscalateControl`. No probability or
confidence anywhere. A control the reader may not use is absent: counsel sees no Mark sent and the notice says "Not
yet sent to the client".

**Departures recorded:** the 2026-10-08 ≥1680 px Ask column is withdrawn (above). DD-17's "Ask, open, is the side
column" now holds at every width. The reading view leaves DD-14's justified paragraphs for left-aligned text.

### Screenshots

Before is the coordinator's unchanged build on :3399 (read only). After is this pass on :3599/:8499. The folder is
`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/ui-pass-2/` and the names are
`{before|after}/{owner|counsel}-{1440|2000|390}-{drafting|returned}-{document|changes}.png`. The crops are
`{before|after}/crops/crop-{reply|client}-{parties|definitions|nested}-{1440|2000|390}.png`.

| Surface | Before | After |
|---|---|---|
| Reply, Document, 2000 px (four columns → three, notice, Mark sent) | before/owner-2000-drafting-document.png | after/owner-2000-drafting-document.png |
| Reply, Document, 1440 px | before/owner-1440-drafting-document.png | after/owner-1440-drafting-document.png |
| Client returned, header | before/owner-1440-returned-document.png | after/owner-1440-returned-document.png |
| Changes tab | before/owner-1440-returned-changes.png | after/owner-1440-returned-changes.png |
| Counsel (no Mark sent) | before/counsel-1440-drafting-document.png | after/counsel-1440-drafting-document.png |
| Phone | before/owner-390-drafting-document.png | after/owner-390-drafting-document.png |
| Parties / recitals | before/crops/crop-client-parties-1440.png | after/crops/crop-client-parties-1440.png |
| Definitions | before/crops/crop-reply-definitions-1440.png | after/crops/crop-reply-definitions-1440.png |
| Nested clause 4.3 → i. → 4.3.1 | before/crops/crop-reply-nested-1440.png | after/crops/crop-reply-nested-1440.png |

### Still open

- On a phone the Contents card still sits above the text in the Document region. The floating Ask launcher covers the
  document toolbar's right end. This existed before this pass and needs its own small pass.
- Key Obligations cannot be shown locally without a generation key. It also re-attempts extraction on every open, and
  a failed run is recorded each time (there are 18 FAILED runs on two versions).
- Changes tab: the passage column of the Changes tab still uses the older inline marks (for example
  "SERVICESSERVICES:"). Letter-case-only changes read as doubled words, so a case-only rule would help.

---

## S1 — plain language and person homes (2026-11-03)

Slice S1 of the approved plan (`read-all-the-concept-floating-papert.md`). Built in `/root/legalmind-worktrees/clm-p1`,
uncommitted. Presentation only. It locks nothing, and the vocabulary-per-person lock records are still S0's job. KB re-read
first (DESIGN.md, docs/design/*, 03, this file, DECISION_STATE_MODEL). `ui-ux-pro-max` and `frontend-design` were loaded.

### Decisions

| # | Decision | Where |
|---|---|---|
| 1 | **One label map.** `lib/labels.ts` gains `answeredWords` (Kept ours · Accepted theirs · Our standard · Our wording · Waiting for the client · Not applicable here), `POINT_WHO` (Yours to answer · With Legal · Waiting for approval), `DECISION_COPY`, `ASK_LEGAL_COPY`, `stageWords(code, viewer)` and `withoutSectionRefs`. `StageBadge.STAGE_LABEL` is derived from it. `findingLanguage.ts` keeps the reader words (AM-184) and gains `pointAnswer`. | labels.ts, findingLanguage.ts, StageBadge |
| 2 | **Jargon out.** Constitution → "our standards" (the § stays only in Legal details). Escalate for authorized review → **Ask Legal** ("You asked Legal to look at this. Asking is not an approval — Legal decides", which keeps ROLE-04's meaning). Justification (required) → **Reason**. The 409 message → "Someone answered this a moment ago — refresh to see it". "Recorded as version N" → "Your decision is recorded". "someone with legal authority" → "Legal". Client returned → **Client replied**. Internal review → **With Legal** for the owner and **Your review** for the lawyer. Needs Legal → **With Legal**. snapshot → "Our standards, version …". "one signal… never a gate" and "Never shown as Acceptable" are removed. "not approval to sign" → "Legal's review is done — signing is still your decision". Changes now show requirement codes as titles. `DecisionControl`/`EscalateControl`: only their strings changed. Markup, classes and the 409 and no-optimistic behaviour are untouched. | — |
| 3 | **Two lines per point, never merged.** Finding card, Summary open points and Changes rows. Line 1 is the reader word (the chip, unchanged). Line 2 says who answers it, or what was answered, in weight only and with no hue. A decided point keeps "Change needed" on line 1, so a decision never reads "Matches" (rule 14). The "Escalated" chip and the decided chip are folded into line 2. | FindingsPane, Angles, ChangesPane |
| 4 | **Legal details** is rendered only for `legal_position.view` **and** `legal.review` holders (`showsLegalDetails`). It holds the reasoning chain, the classification, the rule outcome, the § citation, the finding state, the engine record, codes and the evaluator. For anyone else these are absent, not greyed. Rule 11 and AM-19 still hold: every reader gets **Where it says this** (the quoted passages plus "Checked by NUMERIC-COMPARISON-v1 · n passages"). In the Summary, the tiles and "What was decided" moved into a Legal details fold. | FindingsPane, AnalysisPanel, CaseContext |
| 5 | **Person homes, from permissions** (`personaFor`). `legal.decision` → **For my review** (To-do decide and answer-the-changes items, then **Waiting for my approval**). `department.view` → **Team contracts** (the default scope is the department). Anyone else → **My contracts**. A second approver is the `second_approval` To-do items, not a permission. **New contract** is the one primary action, and it opens the existing upload. The greeting hero and the four stat cards are removed. | dashboard/page.tsx, TodoViews (`HomeQueue`, `TodoRow`), todo/page.tsx, model.ts |
| 6 | **The header has 5 items:** title · client · stage (worded for this reader) · "Owned by …" (+ colleagues) · one primary action. Share ("Copy link", with a status line) and View report move under ⋯. Type, declared status and effective date move to quiet facts on the bar. The source shows in the version label. | WorkspacePage |
| 7 | **Summary** is "What needs attention" (stage, contract decision, open points, with § refs stripped) and "Key terms" (money, obligations). | AnalysisPanel |

### Screenshots

The folder is `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/s1/{before,after}/`. Names are
`{owner|counsel}-{1440|390}-{contracts|todo|a-summary|a-findings|a-changes|b-…}.png`. Open states are in `after/*-1440-{menu,finding-open,summary-panel}.png`.
Before was built from the unchanged tree on :3698. After was built on :3699. Both use API :8399.

### Still open

- The visual baselines (`ws-documents.png`) will change. Adopt CI's (memory: never update them locally).
- The e2e specs were updated but not run here.
- Server-built Ask/report text still says "Constitution §…" (the report and the counter-proposal label). The Standards screen still says "snapshot". These are outside S1's surfaces.
- "Contracts with Legal" for the lawyer comes from the To-do only. The list has no default Legal filter yet.
- ObligationsPanel keeps its own all-caps "KEY OBLIGATIONS" title under "Key terms".

---

## S2 — Changes page (2026-11-03)

Slice S2 of the approved plan (flow 3, *Lawyer reviews*). One page: the Changes tab and the components it owns
(`ChangesPane.tsx`, new `ChangeComposer.tsx`, `changes.css`, `lib/changes.ts`, the changes/answers/reply client calls).
Built in `/root/legalmind-worktrees/clm-p1`, uncommitted. Presentation only, on locks `AM-284` (wording, notes), `AM-285` r3
(internal note omitted), `AM-291` (two lines, the action names) and `AM-293` (download gate). `frontend-design` and
`ui-ux-pro-max` loaded; KB re-read (DESIGN.md, DESIGN_SYSTEM, DD records, UI_PATTERNS, this file).

### Plan (written before building)

**Tokens — the existing workspace set, no new hue.** `--ws-ink-900` text · `--ws-ink-500` secondary · `--ws-ink-100`
rules · `--ws-paper` insets · `--ws-surface` cards · `--ws-accent` (actions, focus, the client's underline). Two notes
are told apart by *shape and words*, never a new colour: **Note to client** is a Word-comment balloon (accent-soft
ground, accent left rule — "this goes out"); **Internal note** is an inset on paper with a dashed rule ("this stays
in"). Each says so in its label.

**Type roles.** Source Serif (`--ws-serif`) for every contract word — the passage, their text, the wording editor, the
preview — and Plex Sans for everything that is ours (labels, actions, lines 1–2). Serif = what the contract says;
sans = what LegalMind says. Plex Mono only inside `<kbd>`.

**Each change, two lines, never merged (`AM-291` r1).** Line 1: the reader word against our standard (the review's
word, or nothing when the clause matches). Line 2: who answers it, or what was answered (Yours to answer · With Legal ·
Waiting for approval → Kept ours · Accepted theirs · Our standard · Our wording). Weight, not colour, carries open vs done.

```
LIST ROW                          CARD HEAD
┌───────────────────────────┐     ┌─────────────────────────────────────────┐
│ 7.2 Limitation of liabil… │     │ 7.2 Limitation of liability             │
│ Change needed             │ L1  │ Change needed · Limitation of liability │ L1 (review's word + point)
│ With Legal                │ L2  │ With Legal — our standard covers it     │ L2 (who answers + why)
└───────────────────────────┘     └─────────────────────────────────────────┘
```

**Answer card — holder (`can_write_wording` / `can_decide`).** One choice, then its panel — the four actions as a
radio group (arrow keys come free), so every answer carries the same notes:

```
 Your answer
 (•) Keep ours   ( ) Accept theirs   ( ) Use our standard   ( ) Write our wording
 ┌ panel for the choice ──────────────────────────────────────────────┐
 │ Write our wording                                                  │
 │  Their text (serif, read-only)  │ Your wording (serif textarea,    │
 │                                 │ prefilled with their text)       │
 │  How the client will see it: their text → yours, Word-style marks  │  ← the one memorable element
 │  Reason (required)                                                 │
 │  ┃ Note to client — goes into the reply as a comment they see      │  balloon
 │  ┆ Internal note — only Legal sees this; never sent                │  dashed inset
 │                                          [ Record our wording ]    │
 └────────────────────────────────────────────────────────────────────┘
```

Accept theirs on a measured point is a Legal Decision: its panel places `DecisionControl` per open finding, named
(word · point), and only after an effective acceptance does "Accept theirs" record. Use our standard says what it
inserts — our published clause for the point, verbatim — or, on the client's paper with no anchored clause, says that
none is published yet (and the action is absent there). Waiting for approval, after our wording on a measured point:

```
 Our wording · Waiting for approval
 ┃ Your wording is recorded as a Legal Decision. It takes effect when a second person
 ┃ with the right approves it — on your own contract, or where our standard asks for two.
 ┃ The reply cannot be prepared until then.            [their → our wording, marked]
```

**Answer card — Sales (owner route).** Keep ours · Accept theirs (or Accept on a favour row), a one-line reason, and
on a Legal row only Keep ours + **Ask Legal** (one named block per point). No wording, no internal note: absent.

**Client paper first (kind THEIRS).** Row line 1 "Their clause"; actions Accept theirs · Use our standard (only with an
anchored clause) · Write our wording. Keep ours is absent (`AM-294` r2).

**Prepare our reply.** Disabled is not enough: when blocked, a list under the bar — "Still open before the reply" —
each entry a link that selects that change (unanswered · waiting for Legal · waiting for approval). After the reply,
a download refused by `AM-293` (409 REPLY_UNDECIDED) lists its open points, each linking to the point on the reply.

**Keyboard.** j / k move through the list. After an answer the card says what was recorded and focus moves to the next
change still open in the list (or stays on the recorded line when none is left).

**Review against the brief — what was cut or changed.** Cut: the "Wording changed" chip on the card head (most rows; the
legend says so), the tracked/untracked meta when every change is untracked (the banner says it), the route strip as a
separate box (its words are line 2's sub-text now), two unnamed "Ask Legal" links (named per point). Changed from the
first sketch: the two-pane diff editor was a side-by-side at every width — at the card's 400–540 px it is stacked (their
text above, yours below) with the preview under both; a side-by-side diff in a side column would have been the generic
"diff tool" default and unreadable at that width. The notes' distinction was going to be two tints; tints alone fail
the colour-only rule, so it is shape + label.

---

## S1b — the rest of the plain words, one count, the owner's button (2026-11-03)

Follow-up to S1, built in `/root/legalmind-worktrees/clm-p1`, uncommitted. It applies `AM-291` (r2, r3, r5) and
locks nothing new. The KB was re-read as S1 did, and `ui-ux-pro-max` and `frontend-design` were loaded. The pages were
done one at a time (owner rule, 2026-11-03).

### Page 1: Contracts home

```
For my review / My contracts / Team contracts          [+ New contract]
[queue rows (holder only)]
[stage chips] [search] [filters]                       | Recent activity
[contracts table]                                      |
(the five-step strip is gone)
```

- **Removed:** `Pipeline.tsx`, its test, its mount and its CSS ("Upload · Extract · Confirm type · Evaluate ·
  Findings", "Stored once, never altered"). The strip showed only on an empty shelf, which is every reviewer's shelf.
- **Changed:** a reviewer whose own shelf is empty now reads "No contracts of your own — the points waiting for you are
  above". There is no second upload button there, because the header already has "New contract".
- **What makes the page clear:** the first thing a person sees is their own work, not how the system works inside.

### Page 2: Contract Summary tab

```
What needs attention
  Not sent to Legal yet
  [=====          ]  15 points need Legal — 0 decided so far
  Next: Owner sends it to Legal.
  [Send to Legal]           owner, not sent  (focuses the header's "Send to Legal…" picker)
  [With Legal — 15 points]  owner, sent
  [Review the points to decide 15]   legal.decision holder
Open points (16)
  Not ready to sign: 1 point must change and Legal must look at 14 more.
  1 point differs in our favour and can stay. Also check 4 things in the contract.
```

- **One count.** The definitions are in comments in `StageLine` and `angles.recommendation`. "Need Legal" means
  `review_progress.required`. Must change + Legal must look at = required (1 + 14 = 15). Open points = required + the
  points the approved rule accepts in our favour (16). The document's own observations (4) are counted separately and
  are no longer added into the points (the old "read 19 points" was 15 − 1 + 4 − 1 mixed together). Nothing is hidden.
- **Server wording (`angles.py`).**
  - Actions: "Ask them to use our wording" · "Legal decides — we have no approved wording for this" ·
    "Must change before signing — not negotiable" · "Our standards don't cover this — Legal decides" ·
    "Legal must read clause N before we rely on it".
  - Case steps: "Must change — not negotiable" · "Ask them to change the wording" · "Ask Legal to look at this".
  - The recommendation has no § in it. The §s are kept in code comments and in Legal details.
- **Report (`export_render.py`).** "Review status" · "Standards version" · "Standards checked … of our standards found
  something" · "Results, as recorded". A quoted source reads "Our standards — …". The § labels are listed once, in the
  audit appendix ("Where our standards say it").
- `NOT_SENT` now reads "Not sent to Legal yet". The header picker reads "Send to Legal…".

### Page 3: Contents index

- **The cause:** the parser gave rows such as `2` / "TERMS GOVERNING PROVISION OF SERVICES:" a `section_number` but no
  `section_title`. `clauseOf` returned `title: ""`, so only the number showed.
- **The fix:** `ownHeading` takes the title from the row's own first line, without the number and without a trailing
  colon. This is presentation only (`AM-57` r3). `isTitleLine` now accepts a trailing ":". There is a test in
  `clause-index.test.ts`.

### Page 4: Standards screen

- **Copy:** "Publish snapshot" → "Publish a new version"; "configuration snapshot" → "a new version of our standards";
  "Snapshot <id>" → "Version <id>". `StandardForm` was changed the same way.
- **Evaluator name:** CATEGORICAL showed as the raw enum, and now reads "One of a fixed list". This is not on a
  screenshot, because the build after it was blocked (see Still open).

### Screenshots

- **Before:** S1's after set, `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/s1/after/`.
- **After:** `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/s1b/after/`, as
  `{owner|counsel}-{1440|390}-{contracts|a-summary|b-summary|a-contents|b-contents|standards}.png` and
  `owner-1440-send-to-legal-focus.png`.
- **How they were made:** build :3799 → API :8399.

### Still open

- API :8399 was started before the `angles.py` change and does not reload. The screenshots therefore still show the OLD
  recommendation and action text. The new text is verified by the tests (406 passed). Restart :8399 to see it. I could
  not start my own API (permission denied).
- At 390px the Contents list has no height (same in S1's shots). This is a mobile layout defect that predates S1b.
- The header stage chip ("Client replied") and the Summary stage ("Not sent to Legal yet") are still two vocabularies on
  one screen. Under `AM-291` r4, `review_stage` belongs in Legal details.
- The e2e specs (`workspace.spec.ts` "Review the points to decide", review-workflow, configuration, reviews) were
  updated but not run.

### Built

| # | Decision | Where |
|---|---|---|
| 1 | `actionsFor(change, list)` — the actions a reader has, from the server's flags only (`can_answer`, `can_decide`, `can_write_wording`, route, `holder_accepted`, kind, `anchor`). Sales: Keep ours · Accept theirs on their own rows; Keep ours + Ask Legal on Legal's. Lawyer: all four as one radio group. Client paper: no Keep ours; Use our standard only with an anchored clause, else "No standard clause is published for this point yet." | `lib/changes.ts`, `ChangeComposer.tsx` |
| 2 | Card head = where · line 1 (review word · point) · line 2 (`whoLine`: who answers / what was answered, with the route reason only for a reader who does not answer it). List rows use the same `whoLine`; "Yours to answer" goes unsaid there. | `ChangesPane.tsx` |
| 3 | Write our wording: their text against ours, a serif editor prefilled with theirs, **How the client will see it** (live word-diff theirs → yours), reason required, the two notes, "Record our wording". Measured points say the wording is recorded as a Legal Decision. | `ChangeComposer.tsx`, `changes.css` |
| 4 | Accept theirs on a measured point places `DecisionControl` per open point (unchanged; Acceptable points skipped — the before-shot offered Decide on a "Matches our standard" point). Points are named only when there are several. | `ChangeComposer.tsx` |
| 5 | Waiting for approval: line 2, a clock on the row, and a ruled note saying a second person must approve (own contract, or the standard asks for two) and that the reply waits. The recorded wording, note to client and internal note (only when its key arrives) are shown with the answer. | `GivenAnswer` |
| 6 | After an answer focus moves to the next open change in the view (announced); a waiting answer keeps focus on its record. | `ChangesPane.replace` |
| 7 | Prepare our reply: while anything is open the button is absent and "*n* still open before the reply" opens a popover listing the changes by why (waiting for approval · waiting for Legal · not answered), each selecting its change. Downloads are fetched; an `AM-293` refusal lists the reply's open points, each linking to `?finding=`. | `ReplyBar`, `ReplyDownloads`, `GateList`, `api.replyFile`, `ApiError.gate` |
| 8 | Paper-first: the tab opens for a single client version; legend and `from: null` handled. | `useClientChanges`, legend |

Screenshots: `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/s2ui/{before,after}/{owner|counsel}-{1440|390}-{list,card,editor,waiting,blocked}.png`
(scripts `before.mjs`, `after.mjs` beside them). The API on :8399 runs older code, so the after-shots inject
`can_write_wording` and the lawyer's `can_answer` into its real GET and answer every write with a mock — nothing was
written to the scratch DB.

### Still open

- **Server:** "Use our standard" cannot show the clause text it will insert — no endpoint or list field serves the
  realising clause's text (the list carries only `anchor.clause_version_id` on paper-first rows). The panel says what
  it inserts in words; add the text to the row (e.g. `anchor.text`) and the card shows it.
- **Server:** who must approve and why is not in the answer response; the waiting note gives the two rules (`AM-289`,
  `requires_second_person`) rather than naming the case.
- Sales gets no "Note to client" (YAGNI for the owner route); the server accepts one if wanted.
- Not run in a browser against the new API: `waiting_for_approval`, `REPLY_UNDECIDED` downloads, paper-first rows
  (vitest-covered).

---

## Page 1 — Contracts home (critic round) (2026-11-03)

Built in `/root/legalmind-worktrees/clm-p1`, uncommitted. An independent critic reviewed the live home (12 findings);
each was checked against the page before it was fixed. `frontend-design` and `ui-ux-pro-max` were loaded; DESIGN.md,
docs/design/*, S1/S1b and the approved plan's "Target experience" re-read. Presentation only, plus one server fix
(`deal_stage.py`, below). Locks nothing.

### Plan (written before building)

**Tokens** — existing ones only: ground `--ws-paper` #f2f4f8 · surface `--ws-surface` #fff · text `--ws-ink-900` #0e1420 ·
meta `--ws-ink-500` #5b6478 · rules `--ws-ink-100` #e4e7ee · action `--ws-accent` #2563eb, its soft tint
`--ws-accent-soft` #eff4ff for a row that is this reader's turn and nothing else. **One face**: IBM Plex Sans for the
H1 and every heading (the global serif H1 is overridden here), tabular figures for counts and dates, no mono.
Sentence case everywhere; no tracked capitals.

**The one memorable element** — the turn band. The page's first sentence is what this person does next, written as
the action: *"Client replied — answer their changes"*, with the contract, client, version and upload date beneath and
one named button. A single 3px ink rule runs down the band's left edge (the deal-stage "our turn" idiom: weight and a
rule, never a verdict hue). Everything else on the page is quiet.

Owner (and Lead), 1440:

```
My contracts                                                        [+ New contract]

Your turn  2
┃ Client replied — answer their changes                  3 days   [Answer the changes]
┃ Client A MSA · Acme · v2, 2 Nov 2026
┃ Ready to send — send it to the client                  today    [Open the reply]
┃ Client A MSA · v3, 2 Nov 2026

All contracts  2                                  [Search by name ________] [Filter]
(All 2) (Client replied 1) (With Legal 1)          only stages that hold a deal
Contract                      Stage               Against our standard   Updated
Client A MSA                  Client replied 3d   17 differ              2 Nov 2026  Open ⋯
MSA · v2 · Acme
```

Counsel (`legal.decision`), 1440 — the queue is the page:

```
For my review                                                       [+ New contract]
┃ 15 points await your decision.                         20 h     [Decide]
┃ Client A MSA · Acme · v2, 2 Nov 2026 · Your review
Waiting for my approval  1            (only when something waits)
▸ All contracts                       (closed disclosure — the repository)
```

390: the H1, a full-width New contract, queue rows stacked (sentence, contract line, button); the list's search and
one **Filter** button on one line; stage chips in one horizontal scroller; each contract a two-line block; 96px of
bottom padding so the floating Ask never covers the last row.

**Cut** — Recent Activity (it listed only my own uploads, never other people's work); the Status filter and its
second vocabulary (Draft · Analyzing · Needs attention · No issues) with the client-side two-bucket merge behind it;
Last analyzed, Added and Type columns (type and version move to the name's second line); the four unlabelled coloured
counts and the status pill (one count, in words); ALL-CAPS headers; mono dates; the amber left bar on every
"needs attention" row; "View all"; the decorative icon-in-circle; zero-count chips; the duplicate "For my review" H2;
the empty table header; the "or ask anything" search placeholder (search searches names only).

**Review against the brief** — the first draft kept the chips above the search as the page's lead. That is the
generic dashboard shape (filters first, work second); it was moved under "All contracts" so the turn band leads.

### Findings → decisions

| # | Finding | Decision |
|---|---|---|
| H1 | Owner has no "your turn" queue | Fixed. "Your turn" band from the server's To-do (client replied + changes to answer, merged per contract; Legal answered) and the contracts at Ready to send, each with one named action. |
| H2 | Numbers disagree | Fixed. One count per row, in words: "17 differ" / "All match" (non-Acceptable points). The queue keeps the server's own sentence ("15 points await your decision"). Chips show only stages holding a deal this reader can see; hidden when all are 0. |
| H3 | Two contracts read identical | Fixed. Every queue and table row carries client (linked company, else the declared counterparty), version and upload date, and stage. |
| H4 | "Ready to send" with open points | Fixed at the source. `derive_stage` returns READY_TO_SEND only when the reply's Review finished with nothing undecided (`ReviewFacts.reply_cleared`, fed by `api/routers/contracts.py` `negotiation_stages` from the `AM-293` sets); otherwise With Legal — also without `review.view` (fails closed). Two tests added (pure + through the API). API :8399 was not restarted, so the after-shots still show the old stage. |
| H5 | Lawyer page half empty | Fixed. The queue is the page; the list sits in a closed "All contracts" disclosure; heading semantics corrected (no duplicate H2, empty states are paragraphs). |
| M6 | Row layout breaks at 1440 | Fixed. Four columns with min widths; Last analyzed dropped; action reads "Open". |
| M7 | Template tells | Fixed. Sentence case, body face with tabular figures, tint only on this reader's turn rows, no card-kit side panel, no "View all ›". |
| M8 | Mobile | Fixed on this page: one Filter button, a one-line chip scroller, bottom padding for Ask. **Not done:** the clipped top nav ("Asl") is the shared shell on every page — it belongs to its own pass, not this one. |
| M9 | Search mixes search and Ask; two status vocabularies; activity | Fixed. "Search by contract name"; the stage is the only status; activity panel removed. |
| L10 | 13 types listed | Fixed. The type filter lists only types seen on this person's contracts. |
| L11 | Serif H1, title case, small targets | Fixed. One face, sentence case, contract links and actions ≥ 24px (44px on touch). |
| L12 | Empty filter state | Fixed. One line and a Clear button; no table header, no icon. |

### Built

`dashboard/page.tsx` (list view rewritten: Status filter, two-bucket merge, Recent Activity, four columns and the
old empty states removed), `TodoViews.tsx` (`HomeQueue`: turn band, contract facts per row), `model.ts`
(`TURN_KINDS`, `contractFacts`, `differCount`, `shortDate`; `homeSections` unchanged so the To-do page is unchanged),
`workspace.css` (a new scoped block: `.ws-home`, `.ws-hq*`, `.ws-hometable*` — `.ws-turn` was avoided because the Ask
transcript already uses it), `person-home.test.ts`, `styled-classes.test.ts` (untouched list), backend
`deal_stage.py`, `contracts.py`, `test_deal_stage.py`.

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page1-home/{before,after}/`
— `{owner|counsel}-{1440|1920|390}[-full|-filter|-all-open].png`, `*-tab{n}.png` (keyboard), `*-empty-filter.png`.
Before = the critic's shots of :3399. After = own build on :3599 → API :8399.

### Still open

- The top nav clips at 390 ("Asl"): shared shell, every page — its own pass.
- The client name shows only for a linked company or a declared counterparty; the e2e seed has neither.
- "17 differ" counts points that differ from our standard, decided or not — the list row carries no undecided count.
  A server field (`open_points`) would let the row say "n to decide" exactly as the queue does.
- e2e specs (`dashboard-list.spec.ts`, journey) not run; the search box keeps the name "Search contracts".

---

## Page 2 — Contract page (critic round) (2026-11-03)

Built in `/root/legalmind-worktrees/clm-p1`, uncommitted. The Contract page's **Document** tab: header, version
switcher, Contents, reading view, side panel (Summary · Points · Ask), the point cards and Legal details. An
independent critic reviewed the live page (11 findings + the lawyer's empty "All contracts"); each was checked on
screen and against the API before it was fixed. `frontend-design` and `ui-ux-pro-max` were loaded; DESIGN.md,
docs/design/*, the passes above and the approved plan re-read. `AM-291` (one vocabulary, the reader word apart from
the answer, engine detail only in Legal details) and `AM-293` (nothing undecided offered as sendable) govern. Locks
nothing. The Changes tab (`ChangesPane`, `ChangeComposer`, `changes.css`) is page 3 and is not touched.

### Plan (written before building)

**Tokens** — existing ones only, nothing new: ground `--ws-paper` #f2f4f8 · sheet/surface `--ws-surface` #fff · text
`--ws-ink-900` #0e1420 · secondary `--ws-ink-700` #2b3444 · meta `--ws-ink-500` #5b6478 · rules `--ws-ink-100`
#e4e7ee · action `--ws-accent` #2563eb (one filled button per person, nothing else filled). Status tones stay
`--ws-tone-*` and appear only on the reader word. Type: **Source Serif 4** for the contract and every quote from it,
**IBM Plex Sans** for everything LegalMind says; no mono on any reader-facing line, no tracked capitals, sentence
case everywhere.

**The one memorable element — the reading column.** White sheets on grey, Source Serif 16/24.8 at ~60 characters,
hanging clause numbers. It is kept exactly and given more room: the in-text "The analysis of this clause:" strip and
the mono footer come off the sheet, headings keep their own words and gain weight. Everything around the column is
quiet so the contract reads as the contract.

Owner (deal owner), 1440 — contract A (client replied, nothing sent to Legal):

```
←  Client A MSA (e2e)                                              [⋯]  [Answer changes]
   Client replied today   Owned by you   [Add colleague]
   Document | Changes 82    Version [2 (client's, latest) ▾]  [Send to Legal… ▾]
┌ Contents ───────┐ ┌──────── reading column (serif, 60ch) ────────┐ ┌ Summary | Points | Ask ┐
│ Search          │ │ MASTER SERVICES AGREEMENT                    │ │ What needs attention  H2│
│ 1 Definitions…! │ │ This Master Services Agreement is entered…  │ │ Client replied          │
│ 2 Terms govern…│ │                                              │ │ 15 points need Legal —  │
│ 12 Performanc…!│ │ 5. TERM                                      │ │ not sent yet  [▬▬▬▬▬]   │
│ 13 not in this │ │ 5.1 The Term for the Services shall…         │ │ 82 changes to answer    │
│    document    │ │                                              │ │ (162 marks) Open Changes│
│ 14 Termination!│ │                                              │ │ Open points (15)        │
│ ─ key ─        │ │                                              │ │ Liability  Needs a dec. │
│ ✓ Matches ...  │ │                                              │ │ Needs Legal — not sent… p18│
└─────────────────┘ └──────────────────────────────────────────────┘ └────────────────────────┘
```

Counsel (`legal.decision`), 1440 — the same contract; the stage word is theirs ("Your review" once it is sent),
line 2 of every point is the act ("Yours to decide"), and the one filled button in the side panel is gone — the
header keeps the one primary action, the Summary offers "Decide the 15 open points" as a secondary button:

```
←  Client A MSA (e2e)                                              [⋯]  [Answer changes]
   Client replied today   Owned by Owner
   Document | Changes 82    Version [2 (client's, latest) ▾]
                                                    │ What needs attention          │
                                                    │ 15 open points — yours to     │
                                                    │ decide   [Decide the 15 points]│
                                                    │ Liability      Needs a decision│
                                                    │ Yours to decide       page 18 │
                                                    │ ▸ Legal details (review stage,│
                                                    │   recommendation, tallies)    │
```

A point card (Points tab), both people:

```
Auto-renewal                                       [Needs a decision]
Needs Legal — not sent yet            (holder: Yours to decide)
The contract states this more than once, differently (clause 5.3) …
“(g) ‘Renewal Term’ shall mean rolling periods …”   Clause 5.3, page 2
Our standard  30 days                                (position holders only)
[ Decide … ]                                          (holder: DecisionControl, unchanged, placed here)
View in document   Ask about this   Ask Legal
▸ Where it says this  /  ▸ Legal details (holder)
```

Phone, 390 (both people):

```
[Menu] LegalMind               🔔 (O)          52px — the nav is a menu, not a clipped strip
← Client A MSA (e2e)                 [⋯]
Client replied today · Owned by you            one line
Document | Changes 82        [Answer changes]
[Version 2 ▾] [Send to Legal… ▾]               one row
Contract | Summary | Points        [Contents]  Contents opens as a sheet
(the sheet, the column at full width)
```

**Cut** — the Summary's review-stage line ("Not sent to Legal yet") as a second status (it moves to Legal details);
"Ready to send" + "Mark sent" + "Download it, send it" while anything is open (the banner shows only at Ready to
send or once sent); the Summary's second filled button; the recommendation sentence for the owner (AM-156 r5's
action sentence is engine detail, r6); the "Must change — not negotiable" / "Ask Legal to look at this" line on
the owner's points; "To decide" (→ Open); "24 total"; "By analysis:"; the type text "MSA" and the middot version
label; the stage chip's one-sided border; the in-text analysis strip; the mono footer; "Numbering restarts";
ALL-CAPS card labels; empty card lines; "§5.3 · page 5" (→ "Clause 5.3, page 5"); the passage quoted a second
time in "Where it says this" when the card already quotes it; the 70px gap above "What needs attention".

**Review against the brief** — the first draft put the stage, the count and both sets of buttons in one hero card
in the side panel. That is the SaaS-card default (a big status tile with a CTA) and repeated the header; it was
cut back to a heading, two lines and a secondary button, so the header's one action is the only filled one. The
first draft also kept the Contents legend's own sentences; it now reads the four reader words the points use.

### Findings → decisions

| # | Finding | Decision |
|---|---|---|
| H1 | Header "Ready to send" + Mark sent + "Download it, send it" while 17 points open; Summary "Not sent to Legal yet" | Fixed. API :8399 confirmed: contract B is now `INTERNAL_REVIEW` (With Legal / "Your review"), so Mark sent is not offered. The reply banner shows only at Ready to send or once sent (`AM-293`). The Summary's first line is the header's own stage word; the review stage moved into Legal details. |
| H2 | "With Legal" before anything was sent; the lawyer told "Ask Legal to look at this" | Fixed. Line 2 reads "Needs Legal — not sent yet" until the owner sends, "With Legal" after, "Yours to decide" for a `legal.decision` holder. The action sentence is a Legal detail (`AM-291` r6); for Legal it reads "Read it and decide"; the holder's Decide sits on the card. |
| H3 | Phone: Contents zero height, ~380px of chrome, nested tabs, nav clipped | Fixed. The shell nav is a Menu button below 560px (shared shell). Contents is a sheet from a "Contents" button in the document toolbar. Status and owner on one line; Send to Legal, ⋯ and the one action on the next; Document · Changes and the version share a row; sub-tabs Contract · Summary · Points. Content starts at 187–238px (was ~380). Departure: the version and Send to Legal are not inside ⋯ — a select is not a menu item; they share rows instead. Ask stays the floating launcher, not a tab. |
| H4 | Counts and vocabularies disagree | Fixed. Summary "N open points" = "Open points (N)" = the Points tab's "Open N" (the server's `to_decide`; contract A 15, B 17). "To decide" → "Open"; "N total" and "By analysis:" gone. "82 changes from the client to answer (162 marks)" with an "Open Changes" link. The Contents key reads Matches our standard · Decided · Open point · Missing. "Company standard" → "Our standard". "Findings" → "Points" everywhere on the page. |
| M5 | Summary points six lines, contradictory | Fixed. Line 1: the point, the review's word, the place on the right; line 2: who has it. The gap, recommendation and standards' quotes are on the card and in Legal details. Only real links are links. |
| M6 | "§5.3 · page 5", passage quoted twice | Fixed. "Clause 5.3, page 5" on the card, in "Where it says this" and (server, `angles._where`) on the Summary; "Where it says this" lists only the passages the card does not already quote. |
| M7 | Engine wording and template styling on cards | Fixed: sentence-case labels, no mono, the vacuous "Requirement" step dropped, Decide placed above the disclosure, mono footer and in-text "analysis of this clause" strip removed, the contract side's "2 separate limits stated" replaced by the case's gap line. Kept: the standard's own detail ("30 days — non renewal notice"). |
| M8 | 70px gap, two blue primaries, detached dropdown | Fixed. "What needs attention" is the panel's H2 at the top; the Summary's button is secondary; Send to Legal sits beside ⋯ and the one action. `DecisionControl`'s own Decide button is unchanged (not ours to restyle). |
| M9 | Contents swallows body text, repeated eyebrows, clause 13 silent | Fixed. One line with an ellipsis (full words in the title), a declared part once, no "Numbering restarts", and "13 — no heading found" where a top-level number is skipped. |
| L10 | Headings, colon, selection band, table | Fixed: a numbered row whose own line is a title ("14" / "TERMINATION:") now reads as a heading. The colon is kept — it is the document's text (rule 17). A cited passage is a margin rule and a text tint, not a list-selection band. The Hardware SLA annexure is not a table in the source DOCX (4 tables, none there), so nothing was flattened. |
| L11 | Chip border, stray "MSA", middot version | Fixed. The stage is words (no chip, no one-sided rule); type text removed; options read "2 (client's, latest)". |
| P1 | The lawyer's "All contracts" shows "You own no contracts" | Fixed in the server. `GET /contracts?scope=legal` (needs `legal.review`): own + assigned + created + a Review in Legal scope — the same branches as `contract_read_basis`, in SQL; no global read. The lawyer's home uses it. Test `test_legal_lists_what_it_may_read_and_nothing_else`. |

### Built

Frontend: `WorkspacePage.tsx` (header, banner gate, version wording, Send to Legal placement), `AnalysisPanel.tsx`
(`AttentionLine`, Legal details: stage + recommendation), `Angles.tsx` (two-line points, folds), `FindingsPane.tsx`
(Open, Points, card face, quote once, Decide placement), `DocumentPane.tsx` (Contents line/gaps/key, phone sheet,
strip and footer removed), `WorkspaceLayout.tsx` (Points, Contract · Summary · Points), `WorkspaceShell.tsx` +
`icons.tsx` (phone menu), `findingLanguage.ts` (`pointAnswer(sent)`, `clauseAndPage`, chain), `model.ts` (numbered
title rows as headings), `lib/labels.ts`, `lib/api.ts`, `app/dashboard/page.tsx` (legal scope), `workspace.css`
(one scoped "Page 2" block). Tests: `contract-page.test.tsx` (new) and updated angles, finding-card,
finding-language, findings-filter, decide-and-case; e2e selectors updated (not run). Backend: `api/angles.py`
(`_where`), `api/routers/contracts.py` (`scope=legal`), `tests/test_negotiation_wording.py`.

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page2-contract/{before,after}/`
— before = the critic's shots of :3399; after = own build on :3599 → API :8399, as
`{owner|counsel}-{1440|1920|390}-{a|b}-{01-landing,02-summary,02-points,03-card,04-details,05-clause|05-contract,06-contents,07-menu}.png`.

### Still open

- API :8399 runs the code from before this pass: `scope=legal` (the lawyer's home list) and "Clause 5.3, page 5" on
  the Summary rows need a restart of :8399 to show. Tests cover both.
- The heading row's gutter number ("14") is not drawn for a heading whose number the parser kept apart.
- e2e specs updated for "Points", "Open", "Contract", "Our standard" but not run.

---

## Page 3 — Changes page (critic round) (2026-11-03)

Built in `/root/legalmind-worktrees/clm-p1`, uncommitted. The Changes tab (`ChangesPane.tsx`, `ChangeComposer.tsx`,
`changes.css`, `lib/changes.ts`, `lib/api.ts`) and one server route (`api/routers/negotiation.py`). An independent
critic reviewed the live page (3 high, 3 medium, 1 low + page 2's heading note); each was checked against the
screenshots and the client A rows before it was planned. `frontend-design` and `ui-ux-pro-max` loaded; DESIGN.md,
docs/design/*, S2, Page 1 and Page 2 above re-read. Governs: `AM-284` (wording typed by a person, notes),
`AM-285` r3 (internal note omitted for a non-holder), `AM-291` (two lines, the action names), `AM-293`,
`AM-294`. Locks nothing.

### Plan (written before building)

**Tokens** — existing ones only, no new hue: sheet `--ws-surface` #fff on `--ws-paper` #f2f4f8 · text `--ws-ink-900`
#0e1420 · secondary `--ws-ink-700` #2b3444 · meta `--ws-ink-500` #5b6478 · rules `--ws-ink-100` #e4e7ee · action and
the client's underline `--ws-accent` #2563eb, its tint `--ws-accent-soft` #eff4ff for the selected row and the
note that goes to the client. Removed text stays `--ws-ink-500` struck (verdict-neutral, `AM-255`). Type: **Source
Serif 4** for every word of the contract (passages, both blocks of a replaced clause, the editor, the preview);
**IBM Plex Sans** for everything LegalMind says, sentence case. Mono only inside `<kbd>` — the row tags and the
passage tags leave `.ws-chip` (mono 10.5px) for a sans tag.

**The one memorable element — the redline that reads.** A change is drawn the way a lawyer reads it, by how much
changed (Word "simple markup" / a clause compare):

```
SMALL EDIT (< 40% of the words changed): one paragraph, words marked in place
  …the Companies Act, ~~1956/2013,~~ __2013__, having its registered office…

PUNCTUATION / CAPITALS INSIDE A WORD: only the characters marked
  SERVICES__:__          (not ~~SERVICES~~ __SERVICES:__)
  INTERPRETATION__:__    capitals changed, said in words to a screen reader, dotted underline

REWRITTEN (≥ 40%): a replaced block — ours struck above, theirs below, each named
  ┌ Ours · version 1 ───────────────────────────────────────────┐
  │ ~~Each Party ("Indemnifying Party") agrees to indemnify …~~   │  ink-500, struck
  └──────────────────────────────────────────────────────────────┘
  ┌ The client's · version 2 ───────────────────────────────────┐
  │ Each Party (the "Indemnifying Party") agrees to indemnify,   │  ink-900, accent rule left
  │ defend, and hold harmless the other Party, its affiliates …  │
  └──────────────────────────────────────────────────────────────┘
```

The same function draws the passage column, the card on a phone, the "How the client will see it" preview and an
answer's recorded wording — one treatment everywhere.

**Formatting only.** A row the server routed `FORMATTING_ONLY` is tagged "Formatting only" (not "Wording
changed"), and all of them sit in ONE closed group at the top of the list with one action:

```
▸ Formatting only — headings' capitals and punctuation     19 open
  [ Keep ours on all 19 ]        (the deal owner's, and anyone who may answer)
     → confirm: "Keep ours on 19 formatting changes?"  the clause list · [Cancel] [Keep ours on all 19]
```

Server: `POST /contracts/{id}/changes/formatting/keep-ours` with the row keys the reader saw — every key must be an
unanswered `FORMATTING_ONLY` row, or the whole request is refused (409, nothing written); written in ONE
`write_choices` call with `expected = 0` per row, so it is all or none, never a partial result to explain.

**Counts by who answers (per person).**

```
Deal owner:  Yours to answer 19 · With Legal 62 · Answered 1 · All 82
Legal:       Yours to answer 62 · Deal owner's 19 · Answered 1 · All 82
```

A Legal reader on a deal-owner row reads line 2 "The deal owner answers" and keeps the answer controls (they may
answer it), never "Yours to answer". The owner's Legal row has ONE way to hand it over — the per-point Ask Legal
control — and no separate "Ask Legal" heading repeating it.

**Write our wording opens wide.** Choosing it opens an editor over the list and the passage (the card stays
beside it, so the choice and line 1/2 stay in view); on a phone it is a full screen. Footer pinned, always visible:

```
┌ Write our wording · 11 Indemnification ─────────────────────────────────────── [Back to the choices] ┐
│ The client's version 2 (serif, read-only)     │ Our wording (starts as theirs — edit it)            │
│                                               │ [ serif textarea, grows with the pane            ]  │
│ How the client will see it                                                                          │
│ their text → our wording, the redline above    ┌ Comment to the client ┐ ← the note, as the balloon │
│                                                └ they will get          ┘                            │
│ Sent to the client  [ note ________________ ]   🔒 Only Legal sees this — never sent [ note ____ ] │
├─────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Reason (required) [________________________]  Kept in this change's history in LegalMind;           │
│                                               never sent to the client.     [ Record our wording ]  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**The two notes.** "Sent to the client" — the accent balloon, and in the wording editor the note also appears in the
preview as the comment the client receives. "Only Legal sees this — never sent" — a dashed inset with a lock, and the
field is absent for a reader without `legal_position.view`. Under Reason: who reads it.

**Phone (390).** List first, filters one scrollable row; tapping a row opens the detail screen (the passage, the
card, the actions) with "Back to the list" at its top; the editor is a full screen over it.

```
[Yours 19][With Legal 62][Answered 1][All 82] →        one row, scrolls
1 of 82 answered · 81 open before the reply ▸
▸ Formatting only            19 open
  [Keep ours on all 19]
▾ 11 Indemnification
  11 Indemnification: Each Party (the…     ← first words
  Change needed  ·  With Legal              two lines
   (tap)
← Back to the list
11 Indemnification
Change needed · Indemnity
With Legal — one of our approved positions covers it
[replaced block: ours / theirs]
Your answer  [Keep ours]  Reason …  Ask Legal
```

**Smaller.** Rows with only a number ("1.2") read the clause's first words. The "still open before the reply"
popover lists only what blocks the reply, grouped by who must act (Waiting on Legal · Waiting on the deal owner),
each a link. A skip link "Skip to the list of changes" is the pane's first focusable element. Heading changes
match the reading view's bold headings: a heading's case/colon change is drawn as the heading (bold), only the
changed characters marked.

**Cut** — the "Wording changed" tag on every passage (the legend says it); `.ws-chip` mono tags on this page; the
"Ask Legal" heading over the Ask Legal control; the card's duplicate passage on desktop; the stacked
list-then-card layout on a phone; formatting rows scattered through 19 clause groups.

**Not changed (rule)** — `DecisionControl`'s "LEGAL DECISION" label is mono capitals in its own stylesheet;
`DecisionControl`, `EscalateControl`, `StatePill` and `AXIS_CLASS` are never restyled here, so it stays.

**Review against the brief.** First draft put the wording editor in a modal dialog centred on the page. That is the
generic form-modal default and hides the client's passage and the card's line 1/2 behind a scrim; it was changed
to an editor that takes the list and passage columns and leaves the card in view. First draft also coloured the two
redline blocks red/green (the Diff-Talk tokens); that reads as a verdict on the client's text (`AM-255`) — changed to
ink weight, strike and the accent rule, same as the word marks.

### Findings → decisions

| # | Finding | Decision |
|---|---|---|
| H1 | Rewritten clauses unreadable, word-interleaved (passage and "How the client will see it") | Fixed. `redline()` in `lib/changes.ts`: at ≥ 40% changed words (clauses of 8+ words) the change is a replaced block — "Ours, version 1" struck above, "The client's, version 2" below with the accent rule; smaller edits stay word-level. One `DiffText` draws the passage, the phone card, the editor's reference, the preview and a recorded wording. |
| H2 | Punctuation-only changes as doubled words, tagged "Wording changed" | Fixed. A removed/added pair whose letters and digits match is diffed by character: "SERVICES" + inserted ":"; a capitals change is a dotted underline said as "capitals changed". Rows the server routes `FORMATTING_ONLY` are tagged "Formatting only", sit in ONE closed group first, and carry "Keep ours on all N" → one confirmation listing the clauses. Server: `POST /contracts/{id}/changes/formatting/keep-ours` — every key must be an unanswered formatting-only row or the whole request is refused (422 for a legal row, 409 for one a colleague answered); written in ONE `write_choices` call, so all or none. Test `test_keep_ours_on_every_formatting_change_is_one_write_all_or_none`. |
| H3 | Wording editor buried in a 641px card | Fixed. "Write our wording" opens an editor over the list and passage columns (a portal into the pane's slot, so the composer's state stays in the card); full screen below 1100px. Client's text against ours beside the editor, the preview with the note drawn as the comment balloon, and a pinned footer with Reason + who reads it + "Record our wording" (in view at 1440/1920/390, measured). Esc / "Back to the choices" closes it. A second answer starts from the recorded wording. |
| M4 | Legal's "Yours to answer 81" counts 19 formatting rows | Fixed. Filters per person: Legal "Yours to answer 62 · Deal owner's 20"; owner "Yours to answer 20 · With Legal 62". Line 2 on a deal-owner row reads "Deal owner answers" for Legal. The owner's Legal row has one Ask Legal control; the "Ask Legal" heading over it is gone. The header's "Send to Legal…" (whole contract) is page 2's and stays. |
| M5 | The two notes look alike | Fixed. "Sent to the client — a comment on this change in our reply" (accent balloon, and shown in the preview as the comment the client gets); "🔒 Only Legal sees this — never sent" (dashed inset, absent without `legal_position.view`). Under Reason: "Kept with this answer in LegalMind, for everyone on this contract. Never sent to the client." |
| M6 | Phone: a tap shows nothing | Fixed. Below 760px the list and the detail are two screens; a tap opens the detail at its top with focus on "Back to the list"; filters are one scrolling row; the editor is full screen. |
| L7 | Bare numbers, mono tags, all-caps "LEGAL DECISION", the open popover, skip link | Fixed: a bare number reads its first words ("1.2 INTERPRETATION: (a) The headings…"), also as the card's title; tags are sans, sentence case (`.cx-tag`, not `.ws-chip`); the popover lists only what blocks the reply, grouped by who acts (Waiting for a second approval · Legal decides · The deal owner answers) and no longer overflows a phone; "Skip to the list of changes" is the pane's first stop. **Rejected:** "LEGAL DECISION" is `DecisionControl`'s own label — never restyled here (rule). |
| P2 | Case/colon handling must match the reading view's bold headings | Fixed. A one-line heading change is drawn bold, only the changed characters marked. |

### Built

`frontend/src/lib/changes.ts` (`wordDiff` with character refinement and a `case` mark, `redline`, `formattingOnly`, `isHeading`,
the `owner` filter, per-person `mine`, `whoLine` for Legal, `replyBlockers.withLegal/withOwner`),
`ChangesPane.tsx` (`filtersFor`, skip link, formatting group + `KeepAllFormatting` dialog, phone list/detail, editor slot,
`rowLabel`, grouped popover, one Ask Legal), `ChangeComposer.tsx` (`DiffText` replaced block, `Notes`, `Reason` with its
readers, the wide editor), `changes.css` (one "Page 3" block), `lib/api.ts` (`keepOursOnFormatting`). Tests:
`changes-pane.test.tsx` (+4: colon-only, replaced block, bare number, counts by who answers), `reading-layout.test.tsx`
(row label now "3 SERVICES:"). Backend: `api/routers/negotiation.py` (the bulk route), `api/schemas.py`
(`FormattingKeepOurs`), `api/permission_map.py`, `tests/test_negotiation.py`; `docs/api/openapi.json` regenerated.

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page3-changes/{before,after,after2}/` — before = the critic's shots of contract A on :3399; after = own build on
:3599 → own API :8599 (same scratch DB, worktree code with the new route) on a contract of my own ("Page 3 MSA (e2e)",
`5dc7254f…`, msa-A-r2 → r3), as `{counsel|owner}-{1440|1920|390}-{01-landing,02-formatting,03-rewritten,04-editor,
05-bulk-confirm,05-recorded,06-bulk-done,04-open}.png`; `after2/owner-390-04-open.png` is the popover after its fix.

### Still open

- :8399 does not have the bulk route until it is restarted; the screenshots used a private API on :8599.
- The editor's "How the client will see it" sits below the two columns and needs a scroll at 1440 (the footer stays).
- A Legal reader who is also the contract's owner reads their own formatting rows as "Deal owner answers".
- e2e specs not run; `DecisionControl`'s mono capitals label stays (not ours to restyle).

---

## Page 4 — Template approval (2026-11-03)

Slice S4 of the approved plan. The corporate lawyer (`legal.approve_customization`) turns an imported reference NDA /
MSA (DRAFT, "Reference text — not approved by Legal") into a published template, clause by clause. Built in
`/root/legalmind-worktrees/clm-p1`, uncommitted. Governs: `AM-282` (in-app approval by a named lawyer is the recorded
source; DRAFT text lives only in the database), `AM-283` (approve and publish need `legal.approve_customization`),
`AM-287` (brands). `frontend-design` and `ui-ux-pro-max` loaded; DESIGN.md, docs/design/*, S1–S2 and Pages 1–3 re-read.
Locks nothing. Industry reference: Ironclad / Juro clause-library governance (a clause list with states, the clause,
the playbook position beside it, an approval trail, publish behind a gate).

### What the server already gives, and the one field added

`GET /templates` (status, "12 of 18 clauses approved") and `GET /templates/{id}` (clauses, `{slots}`, flags, approval)
did not say **which clauses fail our standards** — that was only known by running the publish gate, which stops at
the first failing step. Added in `api/routers/templates.py` only: `GET /templates/{id}/check` runs the gate's own
steps on the text **as it stands** (every clause taken as approved, rendered, preflighted, read by the engine with
recognition off) inside a savepoint that is always rolled back — nothing is approved, recorded or kept. It returns
`problems` (preflight: undefined terms, slots…) and `standards` (every non-Match Finding: description, the engine's
word, the clauses its PRIMARY evidence is read from, and the position for `legal_position.view` only). Also
`approval.approved_by_name`. Nothing is invented: on the scratch DB it reproduces the gate exactly (NDA: definition,
mutuality, survival, venue, non-solicit; MSA: liability CONFLICT, data-loss, purge, venue, dispute window, 4 Missing,
4 undefined terms).

### Plan (written before building)

**Tokens** — existing only: `--ws-paper` ground, `--ws-surface` sheet, `--ws-ink-900/700/500/100`, `--ws-accent`
for the one filled action and focus, `--ws-accent-soft` for the selected clause. No verdict hue: a failing clause is
said in words on line 2 and carried by a 2px ink rule, not red. **Type:** Source Serif 4 for every word of the
template (the clause, its number, the editor), IBM Plex Sans for everything LegalMind says. No mono, no tracked
capitals, no middot meta; sentence case. A fill-in field is a sans chip inside the serif — **[Counterparty name]** —
so it reads as "not contract words yet".

**Two lines per clause, never merged** (as Pages 1–3). Line 1: number and heading. Line 2: what it needs —
"Fails our standard: <the standard in plain words>" · "Check this clause: <the import's own note>" · "Not approved yet"
→ "Approved by Priya, 3 Nov" / "Our wording, approved" / "No position, approved". Weight carries open vs done.

**The one memorable element — the signature line.** Each clause sheet ends the way a contract ends: a ruled line.
Before approval it reads, under the rule, *Reference text — not approved by Legal*. Approving writes the lawyer's name
and date onto that line (*Approved by Priya Shah, 3 November 2026*) — a single, short transition, the only motion on
the page. Everything else stays quiet so the clause reads as a clause.

Template list (1440):

```
Templates                                                     (no primary action — templates are imported)
LeapSwitch NDA                    Draft — not approved          0 of 15 clauses approved     [Review]
NON-DISCLOSURE AGREEMENT (serif)  5 standards not met before publishing
LeapSwitch MSA                    Draft — not approved          0 of 21 clauses approved     [Review]
LEAPSWITCH MASTER SERVICES …      12 standards not met · 4 terms never defined
CloudPe NDA                       Ready to publish              15 of 15 clauses approved    [Publish]
LeapSwitch NDA                    Published, version 1          —                            [Open]
```

Clause review (1440 / 1920 — three columns; the side column widens, the sheet keeps its 64ch measure):

```
← Templates   LeapSwitch NDA   Draft — not approved   3 of 15 approved           [Before publishing (5)]
┌ Clauses ───────────────────┐ ┌ sheet ───────────────────────────────┐ ┌ Our standard ──────────────┐
│ Fails our standard  5      │ │ 1   Confidential Information         │ │ Fails our standard          │
│ ┃1 Confidential Information│ │     For the purposes of this         │ │ Confidential information    │
│ ┃  Fails our standard: …   │ │     Agreement, "Confidential …"      │ │ covers what is marked …     │
│ ┃9 Term and Survival       │ │     … [Counterparty name] …          │ │ Could not be checked        │
│ Check this clause  1       │ │                                      │ │ Our position (holders only) │
│  0 Front matter            │ │ ──────────────────────────────────── │ │ "A two-part test: …"        │
│ The rest  9                │ │ Reference text — not approved by     │ │                             │
│  2 Exclusions              │ │ Legal                                │ │ [Approve as it stands]      │
│    Not approved yet        │ └──────────────────────────────────────┘ │ Replace with our wording    │
│ j / k  next · previous     │                                          │ No position                 │
└────────────────────────────┘                                          └─────────────────────────────┘
```

Replace with our wording opens in the side column: the reference text prefilled in a serif editor, "Reason
(required)", **Record our wording**; the fields the template knows are listed so the lawyer can type `{field}`.
No position: one reason field, **Record no position**. Approve on a clause that fails a standard says so first in one
sentence above the button ("The engine reads this clause as not meeting our standard. Approving it as it stands
keeps that.") — no modal; approving is reversible only by a new version, which the side column says.

Before publishing (the publish state, in the centre, chosen from the header or the list's top):

```
Before publishing LeapSwitch MSA
  Not met by the text as it stands  9         each → the clause it sits in
    Limitation of liability — Says it twice, differently            17 Limitation of liability
  Not in this template  4                     no clause to approve — needs our wording somewhere
    Change of control is notified …
  Terms used but never defined  4             "Controlled by" · "Controlling" …
  Clauses not approved yet  18                → the first one
  [Publish]   only when every clause is approved AND the check finds nothing; otherwise absent
  A refusal from the server is listed in the same words, never a toast.
```

Phone (390): one column. The list first (groups collapsible, "Before publishing" at the top); tapping a clause opens
it as its own screen — "Back to the clauses", the sheet, then our standard and the actions in a bar at the foot of the
screen (44px targets). The editor is the screen.

**Absence.** No Templates nav item, no home section, and a 404-identical page for anyone without
`legal.approve_customization` (owner, counsel without it). Positions are absent without `legal_position.view`.

**Review against the brief.** First draft put a progress bar and a big "3/15" tile in the header — the SaaS stat
tile; cut to the server's own sentence. First draft coloured failing clauses red; that is a verdict hue on our own
reference text and fails the colour-only rule — changed to words + an ink rule. First draft made Publish a separate
route with a stepper; a stepper for a one-step act is template chrome — it is a view of the same page. A standard the
engine reads across most of the template (mutuality: 12 of 15 clauses) is not pinned on 12 clauses — it is listed under
Before publishing as "Read across the whole template", so "Fails our standard" stays a short, true list.

### Self-critique → fixes (after the first screenshots)

| # | Seen | Fix |
|---|---|---|
| 1 | Every page blank for 7 s while a check ran — the check's request held the reader's session row locked, so their other requests queued behind it (and four checks ran one after another). | The check commits the request's own transaction before its savepoint; four checks now run side by side (13 s total, the template's own GET in 2 s while they run). |
| 2 | MSA headings in capitals in the list and the links ("LIMITATION OF LIABILITY"). | `displayTitle`: sentence case where LegalMind names a clause; the sheet keeps the document's own letters. |
| 3 | "Before publishing" left the third column empty. | The publish sheet takes the side column's room (`data-wide`). |
| 4 | A cross-reference read "[clause …]" (it pointed at a sub-clause key). | `clauseNumbers` numbers every keyed sub-clause as the renderer does; a resolved reference is plain text ("2.1"), only an unresolvable one is a chip. |
| 5 | The replace editor dropped defined terms; replacing Definitions made two terms undefined (the check showed it at once). | The prefill keeps “Term” in the text, and the help says the wording is kept as plain paragraphs (sub-clauses, definitions and tables lose their form) — a server limit, below. |
| 6 | Table headings in mono capitals (a global `th` rule). | Serif, sentence case, inside the sheet. |
| 7 | Phone: the actions 1,400 px below the fold under a long clause, and a sticky bar that covered "Fails our standard". | The side panels join the screen's column; a compact action bar (Approve, Replace, No position) sticks to the foot; the "approving keeps this" sentence moved under the standard. |
| 8 | The Ask launcher covered the side column's buttons. | Hidden on this page (Ask has no part in approving a template). |

### Built

Backend (`api/routers/templates.py` only, plus its `permission_map.py` line): `GET /templates/{id}/check`,
`approval.approved_by_name`. Tests `test_check_previews_the_gate_and_keeps_nothing`,
`test_a_finding_is_placed_on_the_clause_its_evidence_opens`; openapi regenerated. Frontend: `lib/templates.ts`,
`components/templates/{TemplateApproval,TemplateClause,TemplateList}.tsx`, `templates.css`,
`app/dashboard/templates/{page,layout,NotHere}.tsx`, `[id]/page.tsx`; nav item in `model.ts`; `<TemplatesToApprove/>`
appended to `HomeQueue`; `api.ts` (six template calls, `ApiError.problems`). Test `template-approval.test.tsx` (9).

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page4-templates/after/` —
`counsel-{1440|1920|390}-{01-home,02-list,03-nda-landing,04-nda-jj,05-msa-landing,06-msa-publish}.png`,
`counsel-390-03b/03c-nda-clause*.png`, `owner-{1440|390}-{01-home,02-templates,03-nda}.png` (absence), and the write
flow on the placeholder copy `counsel-1440-1{0..7}-*.png`, `counsel-{1440|390}-1{4,5}-*.png`. Own API :8599 on a copy
of the scratch DB (`legalmind_clm_p4`, migrated to head); the real reference templates in `legalmind_clm_e2e` were not
touched.

### Still open

- **Server:** "replace" stores the lawyer's wording as plain paragraphs (`library._body`), so a replaced clause loses
  its numbered sub-clauses, defined terms and tables — replacing Definitions makes its terms undefined and the gate
  then refuses. A structured replace (or Markdown-like markers for sub-clauses and definitions) is needed before the
  lawyer can rewrite structured clauses.
- **Server wording:** two standards' descriptions still say "where the Constitution places them".
- A standard whose evidence spans more than 3 clauses is shown as "across the whole template" (`SPREAD`, a fixed count).
- "Ready to publish" + Publish could not be shown on live data: every scratch template fails the gate (the placeholder
  is OTHER-typed synthetic text). The success path is covered by `test_publish_succeeds_once_every_clause_is_approved`
  and the refusal list by vitest.
- The check costs 4–8 s per template (render, LibreOffice, engine); the list runs one per draft.

---

## Page 5 — New contract (2026-11-03)

Slice S5 of the approved plan, flow 1 *Sales creates*: a salesperson (or the lawyer) makes our NDA or MSA for a client
from a **published** template in about two minutes. Built in `/root/legalmind-worktrees/clm-p1`, uncommitted.
Governs: `AM-282` r4 / `AM-283` (only a published template is used for a client), `AM-286` (the client's legal
details, typed by a person, format checks only), `AM-287` (brand per contract; no CloudPe MSA — the Constitution's
own words), `AM-293` (nothing undecided is sent; the created v1 is reviewed like any upload), `AM-295` (a draft has a
version: every save sends `expected_version`, 409 when stale; 30-day life). `frontend-design` and `ui-ux-pro-max`
loaded; DESIGN.md, docs/design/*, S1–S2 and Pages 1–4 re-read. Presentation only, no backend change. Locks nothing.
Industry reference: Juro / Ironclad "self-serve templates" — a questionnaire beside the document it fills, the
wording fixed, anything outside the playbook routed to Legal.

### What the server already gives

`GET /templates/published?doc_type=&brand=` (questions: key, label, type, group, class M · O · C · AO, help,
allowed, range, when, locked_value; annexures with their `when`), `POST /drafts` (pre-fills from the client's
profile and their last contract from the same template: `prefilled[]`), `GET/PATCH /drafts/{id}` (`expected_version`,
409 when stale), `GET /drafts/{id}/preview` (the resolved model; a filled run is `{t, var}`; a field not answered is
listed in `missing` and stood in), `POST /drafts/{id}/create` (contract + v1 + Review; 422 `DRAFT_INVALID` with
`problems[{field, problem}]`, 409 `TEMPLATE_NOT_PUBLISHED`). Client Profiles: search and create with the ten legal
fields (422 names a bad CIN/LLPIN, PAN or GSTIN by field). Nothing is added.

### Plan (written before building)

**Tokens** — existing ones only: ground `--ws-paper` #f2f4f8 · preview well `--ws-viewer` #dfe3eb · sheet and form
`--ws-surface` #fff · text `--ws-ink-900` #0e1420 · secondary `--ws-ink-700` #2b3444 · meta `--ws-ink-500` #5b6478 ·
rules `--ws-ink-100` #e4e7ee · the one filled action and focus `--ws-accent` #2563eb · a filled value in the preview
`--ws-accent-soft` #eff4ff with a 1px `--ws-accent` underline. No verdict hue anywhere: this page decides nothing.
**Type:** Source Serif 4 for every word of the contract (the preview: title, parties, clauses, schedules, signature
block), set exactly as Page 4's clause sheet (`.tpl-sheet`, hanging numbers in a 2.6em gutter, nested levels one step
in); IBM Plex Sans for everything LegalMind says. A field not answered yet is Page 4's sans chip inside the serif —
**[Party two name]** — so it never reads as contract words. No mono, no tracked capitals, no middot meta, sentence
case; two lines per item where an item has a second fact.

**The one memorable element — the locked document filling as you type.** The right side is the contract itself, on
its sheet, with its wording fixed (there is no editor anywhere on the page; the only inputs are the template's
questions). Every value a person gives appears in the sheet the moment it is typed — locally, before the save
returns — on a soft accent ground; a field not yet answered stands in the sentence as its named chip. Each value
and each chip is a button: it takes you to its question. The one motion on the page: a value that has just changed
settles from a deeper tint to the resting tint (0.6 s, none under reduced motion). Structure (a clause or a
schedule its condition adds) arrives with the saved preview, a moment later.

Step 1 — what and who (1440; one centred column, no preview yet — there is no template until both are chosen):

```
←  Contracts
New contract
1 What and who   2 Details   3 Review and create            (a real sequence: numbers earn their place)

What are you making?
( NDA                     )  ( MSA                         )
  Non-disclosure agreement     Master services agreement

Which company is it from?
( LeapSwitch              )  ( CloudPe                     )
                               MSA: "No CloudPe MSA; CloudPe services are governed by the published
                               CloudPe Terms of Service." — said as text, no option offered

Who is it with?
[ Search your clients ________________ ]
  Acme Private Limited                     ← a two-line result: name, then registered office / CIN
  Pune, U72900MH2010PTC123456
  + Add a new client                       → the inline form (below)

                                                            [Continue to details]
```

Adding a client inline (same column; the ten legal fields, each optional except the name, grouped as a lawyer
reads a parties block):

```
New client
Company name (required)      [__________________]
Registered name              [__________________]   Entity type  [Private limited company___]
CIN or LLPIN  [_____________]  PAN [__________]  GSTIN [_______________]
  "This is not a CIN (e.g. U72900MH2010PTC123456) or an LLPIN (e.g. AAB-1234)."   ← the API's field, under it
Registered office            [__________________]
Notice address               [__________________]   Notice email [____________]
Who signs for them           [__________________]   Their designation [_________]
Their authority to sign      [__________________]   (board resolution, letter of authority)
Typed by you — LegalMind never fills these in.                       [Cancel]  [Add client]
```

No published template (step 1, in place of Continue — plain explanation, never a disabled button):

```
Our LeapSwitch NDA template is being approved by Legal.
You can upload a contract instead, or come back when it is published.     [Upload a contract]
(for legal.approve_customization holders only:)  Open Templates
```

Step 2 — details beside the live contract (1440 / 1920; the form keeps 30rem, the sheet keeps its measure and the
well takes the rest):

```
←  Contracts   New contract   LeapSwitch NDA for Acme Private Limited          Saved          [Review and create]
1 What and who   2 Details   3 Review and create
┌ form 30rem ─────────────────────┐ ┌ well ───────────────────────────────────────────────────────────┐
│ Filled from Acme's profile: 4    │ │  The wording is fixed by our template. Only your answers change. │
│                                  │ │ ┌ sheet (serif) ────────────────────────────────────────────┐  │
│ Parties                          │ │ │            NON-DISCLOSURE AGREEMENT                         │  │
│ Who signs for us   Required      │ │ │ This Agreement is made on ‹4 November 2026› between          │  │
│ [Priya Shah__________]           │ │ │ LeapSwitch Networks Pvt Ltd, … and ‹Acme Private Limited›,   │  │
│ Our company name                 │ │ │ having its registered office at [Counterparty registered    │  │
│ LeapSwitch Networks Pvt Ltd      │ │ │ office] …                                                    │  │
│ Fixed by our template            │ │ │ 1   Definitions                                              │  │
│                                  │ │ │ 2   Term                                                      │  │
│ Deal                             │ │ │     2.1 This Agreement continues for ‹2› years …              │  │
│ Effective date     Required      │ │ │ …                                                            │  │
│ [04/11/2026]                     │ │ │ Signed for Acme Private Limited                              │  │
│ Term (years)       Required      │ │ │ [Counterparty signatory name], [Counterparty signatory …]   │  │
│ [2] between 1 and 3              │ │ └──────────────────────────────────────────────────────────────┘ │
│ Option             Required      │ └─────────────────────────────────────────────────────────────────┘
│ (•) Option 1  ( ) Option 2       │   ‹…› = a value you gave (click → its question); […] = not answered yet
│ Include clause D   Required      │
│ ( ) Yes  ( ) No                  │
│   Clause D value  (appears when "Include clause D" is Yes)
└──────────────────────────────────┘
```

Groups are the template's own (`group`, in the template's order — "Our company", "Client", "Deal" on the NDA);
only questions whose `when` holds are asked; a question with `allowed` is a set of choices (radios up to four, a
select beyond), never free text; `range` is said beside a number ("between 1 and 12") and set as min/max;
`locked_value` is shown as text with "Fixed by our template", never an input. Required is said in words beside the
label; an optional field reads "Optional". Help text under the label. The save: every change saved 0.6 s after
typing stops (`PATCH` with `expected_version`); the header reads *Saving…* → *Saved*; a 409 replaces it with a
banner across the form:

```
┃ These answers were changed in another tab or window. Reload them to carry on — what you typed here
┃ since the last save is not kept.                                                 [Reload the answers]
```

Step 3 — review and create (the form column becomes the review; the sheet stays):

```
Review and create
Still to fill in  2                       each a link to its question (step 2)
  Effective date — required
  Who signs for them — required
Name in LegalMind   [LeapSwitch NDA — Acme Private Limited]   (optional; the server's default if left as is)
When you create it, our review reads it against our standards, as it does any contract. Anything outside our
standard goes to Legal before it can be sent; the rest is ready to send.
                                                                       [Create the contract]
(after Create: "Creating the contract and starting our review…" then → the contract page, whose header shows
 its stage once the review finishes — Ready to send, or With Legal)
```

A 422 `DRAFT_INVALID` lists each problem by its question's label in the same "Still to fill in" list (preflight
problems — our own rendering — read "Our template could not be filled in: …, tell Legal"); a 409
`TEMPLATE_NOT_PUBLISHED` reads "Legal replaced this template while you worked. Start again from the published
version — your answers stay in this draft until then." with **Start again**.

Phone (390): the step line is one row; steps 2 and 3 have two views, **Details** and **Contract**, switched by a
two-part toggle under the header; tapping a value in the contract switches to Details at its question. The one
action (Review and create / Create the contract) sits in a bar fixed to the foot of the screen, 44px targets, and
the page keeps 96px of bottom padding so nothing hides under it.

```
←  Contracts                    Saved
New contract
1 What and who  2 Details  3 Review
[ Details | Contract ]
Parties
Who signs for us   Required
[____________________]
…
┌──────────────────────────────────┐
│        [Review and create]        │  fixed foot bar
└──────────────────────────────────┘
```

**Entry.** Contracts home's **New contract** opens a small chooser: *Create from our template* ("Our NDA or MSA,
filled in with the client's details") and *Upload a contract* ("The client's paper, or a contract signed
elsewhere" → the existing upload dialog, unchanged). Two-line items, no icons-in-circles. Route `/contracts/new`;
the draft's id is kept in the address (`?draft=`), so a reload or the back button resumes the same draft.

**Cut** — a stepper with progress bar or percentages; a "fields completed 7/12" counter (the review list says what
is left in words); any rich-text editor or contenteditable on the sheet; a field for the counterparty name in the
form when the client was chosen and the template pre-fills it from the profile (it is still shown and changeable —
it is the client's legal name, not ours to fix); a CloudPe MSA option shown disabled; toasts for save state.

**Review against the brief.** The first draft put the form in a wizard of six screens (Parties, Deal, Legal, …) with
the preview behind a "Preview" button — the generic multi-step-form default, and it hides the one thing that makes
this page worth having: seeing the contract become ours as you type. Changed to one details screen beside the live
sheet, the template's groups as headings in one column. The first draft also tinted missing fields amber in the
sheet; amber is the "needs attention" hue elsewhere and reads as a verdict on the client — changed to Page 4's named
chip in the accent family, the same "not contract words yet" idiom the lawyer saw when approving the template.
The first draft made the sheet's values plain underlined links; a link reads "goes somewhere else" — they are
buttons that move focus to the question, with the accent ground so a filled value is seen at a glance.

### Self-critique → fixes (after the first screenshots)

| # | Seen | Fix |
|---|---|---|
| 1 | Step 1's radios sat in the middle of each choice (the absolute-positioned input lost to the label's grid). | The choice is a two-column grid: the radio, then the two lines. |
| 2 | "Option 1" wrapped inside its choice. | Choices do not wrap their words; the row of choices wraps instead. |
| 3 | The 409 banner was at the top of a form already scrolled down — only the red "Saved elsewhere — reload" in the header showed it. | The banner sticks to the top of the form column. |
| 4 | The floating Ask launcher covered the sheet (desktop) and the action bar (phone). | Hidden on this page, as on Page 4. |
| 5 | Deep numbers ("2.1.1.1.1") ran into their text in the 2.6em gutter. | The gutter widens with the number's length. |
| 6 | In the new-client form, a help line pushed one input of a row below its neighbour. | Help goes under the input; a 422 moves focus to the first field it names. |
| 7 | A rebuild left the old `next-server` running, so the page loaded the old build's chunk names and drew unstyled. | Not a page fault. The rebuild script now stops the process on my port, not only the `npx` parent. |

### Built

Frontend only, no backend change: `app/contracts/new/page.tsx` (absent for anyone without `contract.create` +
`document.upload`, shown as the unknown-address page), `components/newcontract/{NewContract,ContractPreview,
QuestionField,ClientPicker,NewContractChooser}.tsx`, `newcontract.css`, `lib/newContract.ts` (a condition evaluator
that mirrors `drafting/conditions.py`, visible questions, answers as the server takes them, what is still missing,
plain words), `lib/api.ts` (six draft calls, and `ApiError.fieldProblems` for `DRAFT_INVALID`),
`app/dashboard/page.tsx` (New contract opens the chooser). The preview reuses Page 4's `.tpl-sheet` typesetting, not
`reading.ts`: that module lays out evidence rows by parsing numbers out of their text, and the preview's model
already has its numbers and levels. Tests: `new-contract.test.tsx` (14), `styled-classes.test.ts` (reads
`newcontract.css`).

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page5-new-contract/final/`
— `owner-{1440|1920|390}-{00-chooser,01-step1-empty,02-msa-no-template,03-cloudpe-nda-no-template,04-step1-client,
05-client-validation,06-client-chosen,07-details-empty,08-live-filling,09-conditional-shown,10-details-filled,
10b-sheet,11-value-jumps-to-question,12-autosave-conflict,13-review-missing,14-review-ready,15-after-create,
16-after-review}.png`. Own API :8599 on `legalmind_clm_p5`, a copy of `legalmind_clm_e2e`; own build on :3599.

### Still open

- **The placeholder could not be published through the S4 gate.** Every clause was approved through the API, and
  then `POST /templates/{id}/publish` refused: the engine reads the placeholder's text as MSA-family and finds six
  MSA standards MISSING. So, in the copy `legalmind_clm_p5` only, the row was moved DRAFT → APPROVED → PUBLISHED by
  SQL and relabelled NDA / LEAPSWITCH so the page has something to draw. The real reference templates were not
  touched. The shots therefore show "Placeholder Agreement" text under a "LeapSwitch NDA" label. A real published
  NDA is needed to see real questions, groups and help text, and the client pre-fill (the placeholder's keys are
  not `counterparty_*`, so `prefilled` was empty).
- The server's labels are made from the keys ("Party one cin"). Better words need a `label` on each template
  variable, which the lawyer or the importer has to supply.
- A clause or schedule added by a condition appears only with the saved preview, about 0.6–1 s after the answer.
  Values themselves appear as they are typed.
- e2e spec not written. Vitest covers the logic and the markup.

---

## Page 5 — critic round (2026-11-03)

An independent critic read the first build's screenshots and listed 14 findings. Each was checked against the page,
the code and the scratch database before changing anything; all were real, with the two corrections noted below.
Built in `/root/legalmind-worktrees/clm-p1`, uncommitted. `frontend-design` and `ui-ux-pro-max` loaded again. Bar:
Juro smartfields / Ironclad launch forms / SpotDraft questionnaires for intake beside a live preview; Carbon /
Atlassian / Fluent form order (label above, help under the label, field, inline message, Required in words); WCAG 2.2
AA. Locks nothing; `AM-286`/`AM-287`/`AM-293`/`AM-295` unchanged. No legal wording written: every new string is a
form label, help or LegalMind's own sentence; the CloudPe/LeapSwitch lines quote the Constitution's §5 entity table.

### Plan (written before changing anything)

The page's job is unchanged — the locked sheet filling as you type stays the one memorable element. What the critic
found is that the questionnaire spoke in keys, mixed our side with the client's, hid the client profile it had,
and told the person about Legal only after Create. The fix is in words, order and one read-only check; no new
token, no new hue (the check's box uses the ink rule, never a verdict colour).

| # | Finding | Verified | After |
|---|---|---|---|
| H1 | Raw-key labels | Yes: the placeholder had no `label`; `drafts.label` made "Party two cin" from the key | `model.ROLE_TEXT`: label + help by a variable's **role** (`role`, else its key — the importer's keys are roles): "Client's legal name", "Client's CIN or LLPIN", "Who signs for the client", "Their designation", "Who signs for us", "Effective date", … The importer writes them into every variable it makes; the placeholder declares `role`/`label`/`help` (synthetic). **Publish gate**: `LABEL: <key> has no label a person can read` when no author or role words exist or the label has an underscore (`model.key_like`). Groups by role: Client first, Deal, Our company last. |
| H2 | Our side mixed in | Yes | "Our company" folds to one line: the entity our template fixes (serif) and "Signed by Priya Shah, Director" / "Who signs for us is not chosen yet", with **Change** / **Choose who signs** opening the fields; fixed values stay text. A jump to one of them opens it. |
| H3 | Legal routing only after Create | Yes | `GET /drafts/{id}/check` runs the publish gate's own engine step (`publish.engine_findings`: recognition off, no model, savepoint always rolled back) on the draft as rendered now; ~1 s. Review lists "These 8 points will go to Legal before the contract can be sent" by requirement title and what the check saw ("not in this contract"), with a spinner while it reads — never blocking Create ("You can create it without waiting"). Per answer: a number outside the template's range says so inline. **Correction:** the critic asked for "Goes to Legal" on out-of-range values, but `model.validate` *refuses* them (Create would 422), so the words say what is true: "Our template allows a number between 1 and 12. A different number needs Legal: ask them, or upload the contract for review instead." **The placeholder's 8 Missing points are template QA, not a page fault**: it was relabelled NDA by SQL in the scratch copy and has no NDA clauses, so every NDA standard is MISSING. |
| H4 | Profile not reaching the draft | Yes: `CLIENT_FIELDS` mapped 6 fields by exact key; the placeholder's keys are `party_two_*` | All ten `AM-286` fields mapped by role (the profile now wins over the last contract's value). Each question carries `profile_field`; a field equal to the profile says **From the client profile**; a changed one says "Differs from the client profile" with **Also update the client profile** (PATCH, the existing route). The top note counts them. |
| H5 | 390 collisions; 180 s | Yes / harness | Recitals get a 2.8em gutter; every table scrolls in its own focusable region; the phone gutter narrows (`--ws-s3`, sheet 14px). **The 180 s was the screenshot script**, not the product: on a phone the contract page opens on its Contract tab and the script waited for text on the hidden Summary tab. With the tab opened: review shown 6.5 s after Create. |
| M6 | No answer summary | Yes | "Your answers" grouped Client / Deal / Our company, each with **Edit** (jumps to its first question); optional unanswered rows left out. |
| M7 | Missing items read as labels | Yes | "Who signs for the client: required", line 2 its group, styled as a link. |
| M8 | mm/dd/yyyy | Yes (Chrome follows the OS locale) | A text field read day-first (`10/11/2026`, `-` or `.` too, ISO accepted), help "Day, month, year, for example 10/11/2026", the date in words beside it; a half-typed date is never sent and says "Not a date yet". |
| M9 | Two conflict signals | Yes | The header save word is empty on a conflict; the banner says it once; Review and create / Create are disabled until reloaded. |
| M10 | Client form | Yes | Name and CIN first (full width, hint up front: "21 characters, for example …"), the rest under **More details**; PAN/GSTIN hints up front; a 422 on a hidden field opens More details. |
| M11 | Execution squeezed | Yes | A column no row fills is left out; name columns keep 7rem; the table uses the sheet's full measure at desktop and scrolls on a phone. |
| L12 | "Wording is fixed" said three times | Yes | Once, above the sheet. Step 1's line is "Our template, filled in with the client's details." |
| L13 | CloudPe line | Yes | From Constitution §5: "A brand operated by Leapswitch Networks Pvt. Ltd., for VPS, GPU Cloud and Kubernetes"; LeapSwitch: "Leapswitch Networks Pvt. Ltd., for Bare Metal, Colocation and hosting". |
| L14 | Chips | Yes | They read the new labels ("[Who signs for the client]"). |

One deliberate departure: "Who signs for **us**", not "for LeapSwitch" — the same template role serves the CloudPe NDA,
and the Constitution makes Leapswitch Networks the signing entity for both brands.

### Self-critique → fixes (after the first screenshots)

| # | Seen | Fix |
|---|---|---|
| 1 | The execution table scrolled at 1440 ("Signatur") — the 64ch measure minus its indent. | No indent for the execution table, 0.88em, tighter cells; min-width only on a phone. |
| 2 | The folded line read "Who signs for us and Their designation: required"; its button wrapped. | "Who signs for us is not chosen yet"; the button does not wrap. |
| 3 | Opening "Our company" repeated the entity under the line that names it. | The entity field is not repeated inside. |
| 4 | Label-to-help gap was 14px, help-to-field 6px (a global `label` margin). | The form's grid gap alone spaces them. |
| 5 | In the new-client grid the CIN help pushed its input below the name's. | Name and CIN each take a full row. |
| 6 | The check fired while Create ran and returned 404 once the draft was consumed. | No check while creating. |
| 7 | The placeholder's count help repeated "Between 1 and 12". | Help removed. |

### Built

Backend: `drafting/model.py` (`ROLE_TEXT`, `role`, `label`, `help_text`, `key_like`), `drafting/publish.py` (LABEL
gate; `latest_snapshot`, `engine_findings`; findings carry the requirement name), `api/routers/drafts.py` (questions
with role, group, help, `profile_field`; ten-field prefill by role; `GET /drafts/{id}/check`),
`api/permission_map.py`, `tools/import_template.py` (labels and help written), `config/templates/placeholder/
template.json` (roles, labels, groups; synthetic), `docs/api/openapi.json`. Tests: `test_new_contract.py` (+3: words
and profile field, the check with a stubbed engine, the real check rolled back; prefill of all ten by role),
`test_template_library.py` (+1: the LABEL gate). Frontend: `QuestionField.tsx`, `NewContract.tsx`, `ContractPreview.tsx`,
`ClientPicker.tsx`, `newcontract.css`, `lib/newContract.ts`, `lib/api.ts`; `new-contract.test.tsx` (+4).

Checks: backend `tests/drafting` + `test_api_contract.py` 252 passed, 4 skipped; ruff clean; mypy clean (244 files);
openapi `--check` OK. Frontend tsc clean; vitest 771/771; eslint: no finding in the touched files (the baseline's
51 errors elsewhere unchanged). Scratch DB `legalmind_clm_p5`'s placeholder row received the new variables by SQL.

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page5b-new-contract/final/` —
`owner-{1440|1920|390}-*.png`, every step and state, including `04b-add-client-form`, `07b-prefilled-from-profile`,
`07c-date-half-typed`, `07d-outside-range`, `07e-differs-from-profile`, `07f-our-company-folded`, `14a-review-checking`,
`14-review-ready`, `14b-phone-execution`, `14c-phone-recitals`. End to end (scripted typing): start → Create 21 s,
Create → contract page 5 s (was 10–11 s), → review shown 6.5 s at every width (390 was "not shown in 180 s").

### Still open

- A real published NDA is still needed to see real questions; the placeholder stands in.
- The early check reads with recognition off (as the gate does); the Review made at Create may differ where the
  semantic step recognises a clause the words alone do not. The page says the check is early, never the record.
- e2e spec not written.

---

## Page 4 — critic round (2026-11-03)

An independent critic read the first build's screenshots and listed 13 findings. All 13 were verified against the
page and the code before changing anything; each was real. Built in `/root/legalmind-worktrees/clm-p1`,
uncommitted. Locks nothing; `AM-282`/`AM-283` unchanged (approve, replace, no position and publish stay the
approver's; DRAFT text stays in the database). `frontend-design` and `ui-ux-pro-max` loaded again.

### Plan (written before changing anything)

The page's job is unchanged: the lawyer turns reference text into approved text, clause by clause, and the gate
decides when it is publishable. What the critic found is that the page let the lawyer do the wrong thing in one
click (approve a clause the gate will refuse), mixed two kinds of problem under one heading, counted the same
problems three different ways, and gave the "replace" path a raw box with no idea of how the words would be
numbered. The fix is in the words and the order of actions, not in new chrome: no new tokens, no new hue, the
serif sheet and its signature line stay the one memorable element.

| # | Finding | Before | After |
|---|---|---|---|
| H1 | Approve was the primary action on a failing clause | "Approve as it stands" filled, first | On a clause that differs: **Replace with our wording** is primary; Approve is secondary and asks in place: "Approve anyway? This clause differs from our standard on liability. The template can't be published until the clause is replaced." Approve anyway / Cancel, focus moves to the question. A clause that only couldn't be checked keeps Approve primary (it is a reading, not a difference), with the same in-place question. |
| H2 | Phone: the sticky bar offered Approve 1,400 px above the standard | bar = three buttons | The bar's first line names the standard ("Differs: Liability, and 1 more"), a link to the panel; the same primary swap. |
| H3 | "Fails our standard" held "Could not be checked" items | one group | Two groups, each with one sentence why: **Differs from our standard** ("…not meeting one of our standards. Replace them with our wording.") and **Couldn't be checked, read it yourself** ("…found the clause but could not measure it… Read it and decide."). Same split in the side panel (dashed rule for the second) and in Before publishing. |
| H4 | Replace was a raw textarea with `{xref:…}` and no numbering | plain text prefill, no preview | Prefilled with the server's `wording` (numbers and markers). A cross-reference reads `{clause 4.2}` in the editor and is turned back into its key before the server reads it. The centre becomes a live serif preview from the dry run (`…/replace` `dry_run`, 400 ms debounce) — numbered exactly as it will be, new or changed lines marked with an accent rule, reference lines no longer present listed under a disclosure. Under the editor, before Record: "N lines new or changed, M removed" and what changes in form ("7 numbered sub-clauses will become plain paragraphs"), on an ink rule. A dry-run refusal (e.g. an unknown field) shows under the editor and disables Record. |
| M5 | Publish summary counts did not match the rows | counted `problems`, rendered `problemLines` | One function, `stopCount` = standards + rendered problem lines. |
| M6 | List said 12, detail said 8 | different units | The same number everywhere: list "21 clauses to approve. 16 problems stop publishing.", header **Before publishing (16)**, publish sheet "16 problems stop publishing", groups summing to 16. Clause-list group counts stay clause counts, under clause headings. |
| M7 | List line 2 restated the standard's full text | "Fails our standard: The provider is not liable for loss, deletion…" | A few words from the Constitution topic the server now returns: "Differs: Liability", "Says it twice, differently: Liability", "Couldn't be checked: Data protection & privacy", "Approved, still differs: …". |
| M8 | Publish rows were not actionable | a clause title link | Each row names its action: "Replace in Limitation of liability" (opens the editor on that clause), "Read Definitions" for one that couldn't be checked, "Replace in Definitions" for a term used but never defined (the clause that uses it). |
| M9 | No governance trail | name and date only | The signature line keeps "Approved by …, date" and adds the reason. **History of this clause** (side panel, opened on demand) lists every version: how it was decided, by whom, when, the reason, and which version this template and the published one use. **Changes since version N** (list, when a published version exists) lists each clause whose version differs, with its decision and reason. |
| M10 | "Draft — not approved" with every clause approved | | "All clauses approved. 6 problems stop publishing". |
| L11 | "The rest" | | **Nothing to fix** ("The check finds nothing here. Approve each as it stands.") and **Approved**. |
| L12 | "← Templates", em dashes, unresolved chip | | "All templates"; "Back to the clauses"; em dashes removed from what LegalMind says (the server's DRAFT label is kept verbatim). The unresolved chip did not reproduce on any template after `clauseNumbers` numbers keyed sub-clauses (round 1); left as it is. |
| L13 | j/k not announced; hint contrast | | `aria-keyshortcuts="j k"` on the clause list; hint in `--ws-ink-700`. |

**Review against the brief.** First draft put a structure warning in the preview sheet AND under the editor — the
same sentence twice; cut to the one next to Record, where the decision is made. First draft of the confirm read
"Approve anyway? Differs: Liability." — a label, not a sentence; rewritten as the standard mid-sentence. A coloured
"changed" highlight was considered for the preview and rejected for a 3px accent rule on the accent-soft ground:
the accent family already means "LegalMind's mark inside the contract" (the field chip), which is what a change
mark is.

### Server (`api/routers/templates.py` only, plus its `permission_map.py` line)

- `GET /templates/{id}/check`: each standard also carries `topic` (the Constitution topic of the pinned standard —
  a label, never a position value).
- `GET /templates/{id}`: for approvers, each clause's `published_version` and the template's `published`
  ({id, version} of the PUBLISHED version of the same key, or null).
- `GET /templates/{id}/clauses/{key}/versions` (`legal.approve_customization`; anyone else 404, as every DRAFT
  read): every `clause_versions` row of that key, newest first — decision, reason, approver's name, dates,
  `in_this_template`, `published`, `wording`. Test
  `test_a_clause_shows_every_version_and_what_the_published_template_uses`; openapi regenerated.

### Built (frontend)

`lib/templates.ts` (groups, `unchecked`, `topicWords`, `shortWhy`, `stopCount`, `toEditor`/`fromEditor`,
`structureChanges`, `outlineDiff`, `changedSincePublished`; types), `lib/api.ts` (`previewClause`,
`clauseVersions`), `components/templates/{TemplateApproval,TemplateClause,TemplateList}.tsx`, `templates.css`.
`template-approval.test.tsx` 12 tests (was 9).

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/page4b-templates/` —
`counsel-{1440|1920|390}-{02-list,03-msa-landing,04-msa-liability,05-msa-confirm,06-msa-replace,
07-msa-replace-edited,08-msa-unchecked,09-msa-publish,10-nda-landing}.png`, the placeholder write flow
`counsel-1440-{20..24}-*.png` (replace with a cross-reference, all approved, history), `counsel-1440-30-ph2-changes.png`
(changes since version 1), `owner-{1440|390}-{02-templates,03-nda}.png` (still "Page not found"). Own API :8599 on
`legalmind_clm_p4b`, a dump of `legalmind_clm_e2e` plus the placeholder imported; `legalmind_clm_e2e` untouched.
Before: `…/page4-templates/after-r1/`.

### Still open

- **"Changes since" was shown on a state made by SQL.** The placeholder cannot pass the gate (the engine reads it
  as MSA-family; six standards MISSING), so in `legalmind_clm_p4b` only it was moved APPROVED → PUBLISHED by SQL
  and a version 2 DRAFT inserted beside it. There is no in-app way yet to start a new version of a published
  template; when there is, this view is where the lawyer reviews it.
- The editor is a textarea: a cross-reference is readable (`{clause 4.2}`) but not a chip there; only the preview
  shows it as contract text. A rich editor would be a new dependency.
- `topic` is coarse — four MSA standards share "Liability" — so two different standards on one clause can read
  alike on line 2 ("Differs: Liability, and 1 more"). A short per-standard label in the standard file would fix it.
- The header and list keep the last count while the check reruns after an action (4–8 s).

---

## Cross-page consistency (2026-11-03)

An independent review read the five pages side by side (4 high, 5 medium, 3 low). Built in
`/root/legalmind-worktrees/clm-p1`, uncommitted; shared foundations first, then each page moved
onto them one at a time and screenshotted (owner + counsel, 1440 / 390) before the next.
`frontend-design` and `ui-ux-pro-max` loaded. Bar: Juro / Ironclad / SpotDraft journeys (one
next step per record), IBM Carbon / Atlassian / Fluent page-header anatomy and action
hierarchy, WCAG 2.2 AA. Recorded as `AM-296` (AB-155, extends `AM-291` and `AM-264`).

### Shared foundations

| Foundation | Where | What it fixes |
|---|---|---|
| `counts` on contract detail, list and each To-do item — `changes_total · changes_left · changes_left_for_me · points_open · points_for_me`, absent never 0 | `api/routers/negotiation.py` `deal_counts`, `client_version`, `_mine`, `_reader`; `contracts.py`; `todo.py` | H1, H2, M5 |
| Two-noun words: `changesWords` ("19 of 82 changes yours"), `pointsWords`, `stageLine` | `lib/labels.ts` | H1, H2 |
| `ACTION` — one label per action, sentence case | `lib/labels.ts` | M6 |
| `nextStep` / `taskAction` / `runStep` / `useStep` — one primary per person per stage, the owning pane does the act | `lib/nextStep.ts` | H3, M9 |
| `PageHeader` — back in words · title · meta · secondary · one primary | `components/page/PageHeader.tsx` | M8 |
| `PointStatus` — four marks, one icon each | `components/workspace/PointStatus.tsx` | M7 |
| `relativeTime` — one spelled-out format | `components/workspace/model.ts` | L10 |
| `oneTaskPerContract`, `TaskList`, `useTasks` — home queue = To-do | `model.ts`, `TodoViews.tsx` | M5 |
| `fetchPdf` / `usePdfDownload` — every PDF button (200 · 202 poll with Retry-After · 503 PDF_NOT_MADE · 409 unchanged · ~2 min cap) | `lib/pdfDownload.ts` | coordinator's PDF note |

### Findings → decisions

| # | Before | After |
|---|---|---|
| H1 | "19 left", "Changes 82", "82 changes… 15 open points", "1 of 82 answered", "15 differ" | Changes tab badge = left for me (19 owner / 62 lawyer / none when 0); queue "19 of 82 changes are yours to answer."; list column "19 of 82 changes yours · 15 open points"; Summary the same two lines. |
| H2 | v3: every change answered, Summary "82 changes to answer" | Stage chip and Summary from the same counts: owner "With Legal, 17 points", lawyer "Legal deciding 17 points", "All 82 changes answered". Stage derivation unchanged (`deal_stage.py` was already right; the page read the wrong number). Departure: a comma, not the brief's spaced em dash (a template tell). |
| H3 | Lawyer: "Decide" on home, "Answer changes" on the contract, a side-panel button | Header primary from `nextStep`: lawyer "Decide 17 points" on every tab and on home/To-do; owner "Answer changes" → "Prepare our reply" → "Send our reply"; "Send to Legal" when nobody in Legal has it. The Summary's own Decide button and the Changes bar's filled Prepare button are gone (the bar listens for the header's step). |
| H4 | "Reference text — not approved" / "Draft, not approved yet"; "16 problems" vs clause-group counts; "Checking…" without end | One word, "Draft"; one sentence from the check, `blockers` ("21 clauses to approve. 16 problems stop publishing.") on the list, the home and the template header; the header's button "See the 16 problems". **Spinner:** reproduced on :3399 as counsel — the three checks run in parallel and take 4–10 s, nothing ever says done or failed, and a template with no clauses waited for ever (`view` needed a clause). Now `within()` (60 s) + a run counter: the check always finishes (result, or "did not finish" + Run again); a template with no clauses opens on Before publishing. The clause sheet keeps the server's DRAFT watermark verbatim. |
| M5 | Home 3, To-do 5; one contract twice | Server: one item per contract (`changes_to_answer` replaces `client_returned`; a return whose open changes are all Legal's is not the owner's; `reply_ready` added). Client: `oneTaskPerContract`; both pages render `TaskList`. Owner now 2 = 2, lawyer 4 = 4. Rows carry client, type, "Version 2, uploaded 3 Nov 2026, 14:45" and "Ref F68CC2". |
| M6 | Answer the changes / Open the changes / Answer changes / Open Changes | `ACTION` map; "Open the changes" and "Open Changes" removed. |
| M7 | Legend "Matches · Decided · Open point · Missing" vs filters "Open · Decided · Acceptable · Requires modification · Needs a decision · Missing" | One set: Matches our standard (circle-check) · Open point (alert) · Decided (check, ink) · Missing (file-minus) — legend, Points filters and Changes rows. "Open point" = neither matching nor decided (equals the server's to_decide under zero tolerance); "Missing" is a kind, so it can overlap. The card's reader word stays line 1. |
| M8 | Icon-only ←, vague "Before publishing" primary, wrapping header, native select, narrower Templates, /dashboard/templates | `PageHeader` everywhere; "← Contracts" / "← Templates" in words; title ellipsis, actions nowrap; "Send to Legal" a button opening a radio picker (Esc closes, focus on the first person); `.lm-page` 80rem for Contracts, To-do, Templates, New contract; `/templates` + redirects. |
| M9 | A contract from our template opened on "Upload new version" | Upload moved to ⋯; Drafting with open points → "Send to Legal"; nothing open → "Send to client" (download Word/PDF, then "I have sent it" — LegalMind sends nothing itself). |
| L10 | "4 h ago", "1 day", "3 d ago" | "4 hours ago", "yesterday", "3 days ago", then the date. |
| L11 | Mono client chip, "A · B · C" strings, accent bar on every card | Client as words (a link when linked); facts as separate parts; the queue's and template cards' left rule removed (kept only where it means "differs" in the clause list and "our turn" on the stage chip). |
| L12 | Phone: Ask pill over content | Both Ask launchers a 48px icon circle below 760px (word kept as the accessible name), less reserved space. **Not done:** the three tab layers (Document·Changes, Contract·Summary·Points) and the version select stay — merging them is a layout change of its own. |

### Consistency after

| | Home | To-do | Contract | Changes | Templates | New contract |
|---|---|---|---|---|---|---|
| Owner, client A v2 | 19 of 82 changes yours · Answer changes | same row | Client replied · tab 19 · Answer changes | Yours to answer 19 · Answer changes | — | — |
| Owner, client A v3 | All 82 answered · 17 open points | — | With Legal, 17 points · Send to Legal | 82 of 82 answered | — | — |
| Lawyer, client A v3 | 17 points await · Decide 17 points | same | Legal deciding 17 points · Decide 17 points | same header | — | — |
| Template | Draft · 21 clauses to approve. 16 problems… | — | — | — | same sentence | — |
| Header | PageHeader | PageHeader | PageHeader wide | same | PageHeader | PageHeader |

### Built

Backend: `api/routers/negotiation.py`, `contracts.py`, `todo.py`; `tests/test_todo.py` (+5). Frontend: the
foundations above; `app/dashboard/page.tsx`, `app/todo/page.tsx`, `app/templates/*` (moved), `next.config.ts`,
`WorkspacePage.tsx` (`RecordHeader`, `SendToLegal`), `AnalysisPanel.tsx`, `ChangesPane.tsx` (`SendOut`,
`ReplyDownloads` via the PDF helper), `WorkspaceLayout.tsx`, `FindingsPane.tsx`, `DocumentPane.tsx`,
`StageBadge.tsx`, `TodoViews.tsx`, `TemplateList.tsx`, `TemplateApproval.tsx`, `NewContract.tsx`, CSS blocks in
`workspace.css` / `templates.css` / `newcontract.css`. Tests: `cross-page.test.tsx`, `pdf-download.test.ts`
(new), `contract-page`, `person-home`, `findings-filter`, `template-approval`, `changes-pane`, `deal-stage`,
`styled-classes` updated.

Checks: backend 290 passed (todo, deal stage, negotiation ×4, api contract, collaborators, archive, rbac,
notifications); ruff + mypy clean; openapi `--check` OK (no schema change). Frontend tsc clean; vitest 781/781;
eslint 51 errors / 4 warnings — the baseline, none in a touched line.

### Screenshots

`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/crosspage-fix/` —
`before/` (the critic's), `after/p1-home`, `p2-contract`, `p4-templates`, `p5-new` (each page as it moved),
`after/final/{owner|counsel}-{1440|390}-{home,todo,c1,c2,ch1,ch2,templates,tpl,newc}.png`. Own API :8599 on
`legalmind_clm_e2e` (reads only), own build `.next-clm-x` on :3599.

### Still open

- `DecisionControl`'s own "Decide" buttons on the point cards stay filled (not ours to restyle), so the
  Points tab shows more than one filled button for the lawyer.
- The template's side panel keeps "Replace with our wording" filled: it is the clause's act, not the page's.
- "Send to client" for a contract made from our template was verified in code and unit tests only — the e2e
  database holds no template-made contract.
- Phone tab layers (L12) and e2e specs (not run).
- `deal_counts` builds one change list per contract in a live round (~0.4 s each); a stored tally if the list
  grows slow.

---

## Signing — "Record signing" → "Mark signed" (flow 5 "Final", AM-292 / AM-297, 2026-11-03)

### Plan

- **Where.** At *Ready to sign* the header's one primary step is **Record signing** (`nextStep`,
  `ACTION.recordSigning`) for whoever may answer on the deal. It opens a right-hand **sheet** (Radix
  `Dialog`, `lm-sign` overlay variant), not a new page: the contract stays visible behind it, and the
  person can close and come back — the record is saved as they go.
- **Three sections, in the order they happen**, each with one plain status word and a tick ("Recorded" /
  "Needed", colour never alone): **Stamp duty** (e-stamp certificate · stamp paper · not stamped yet, as
  choice rows with a one-line hint; reference, state, duty as typed, date; "not stamped" needs the
  explicit acknowledgement) · **Who signed** (for us / for the client: name, designation, authority —
  board resolution or authority letter — its reference and date, signed on, paper or e-signed; seal and
  witnesses under a closed "optional" disclosure; the client's row pre-filled from the client profile
  and the template answers) · **Signed copy** (upload; the server compares it with the agreed version).
- **Why stamping matters** is said once, in plain words, with no rate, article or advice: an unstamped
  contract is valid but not admitted as evidence until duty and penalty are paid; stamping is done
  before or at signing; LegalMind records, it does not work out the duty.
- **The one memorable element** is the comparison verdict: a green band "Signed copy matches the agreed
  version (version N)", or an amber band listing each difference by clause with the agreed and signed
  wording around the first changed word (serif, the diff colours of Diff-Talk). A `legal.decision`
  holder sees "Accept these differences" with a required reason; anyone else is told to upload the
  right copy or ask Legal.
- **Footer**: the server's blockers verbatim under "Before it can be marked signed:", then **Save** and
  **Mark signed** (the only filled button; disabled while anything blocks).
- **After signing**: the stage reads *Signed*, the header shows "Signed on <date>" and a quiet "Signing
  record" button; the same sheet shows the read-only summary (stamp, who signed with authority, how the
  copy compared, and "Download the signed copy").

### Before / after

| | Before | After |
|---|---|---|
| Header at Ready to sign | no primary step — the deal stopped at the decision | **Record signing** primary |
| Stamp duty | not recorded anywhere | method, reference, state, duty as typed, date — or the recorded "not stamped yet" acknowledgement |
| Signatory authority | free text on the client profile only | per party: name, designation, board resolution / authority letter + reference + date, signed on, how |
| Signed copy | declared "Final signed" by hand, never compared | uploaded in the flow, compared with the agreed version; differences block unless a holder accepts with a reason |
| FINAL_SIGNED | any owner could declare it | only "Mark signed" sets it; the declaration is refused (409) |
| After signing | "Signed" badge | "Signed on <date>", the signing record and the download; the record is final; delete refused (archive stays) |

Screenshots (owner and counsel, 1440 and 390):
`/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/signing/` —
`01` header at Ready to sign · `02` the sheet filled · `03` a copy that differs (owner) · `04/05` counsel
sees the difference and the accept box · `06` accepted · `07` ready · `08/09` signed header · `10` the
signing record. Own API :8599 on the DB copy `legalmind_clm_sign` (the agreed version's 17 points set
decided and a Sign-after-our-changes decision inserted by SQL for the screenshot only), own build
`.next-clm-sign` on :3599.

### Still open

- The header's "Signed on" date is the stage's `since` (the signed copy's upload), not the record's
  `signed_at`; the same day in practice.
- The signed copy is not reviewed, so its Summary tab says "not analysed yet"; a signed copy needs no
  review of its own, and the panel could say so.
- A filed historical contract that was already signed elsewhere cannot be declared Final signed any more
  — it must go through Record signing, which needs a Sign-as-is decision. Owner question: a "file an
  already-signed contract" path (no decision gate, still the stamp and authority record)?
- E-sign provider integration stays out of scope (AM-274: provider not named); "E-signed" is recorded only.

---

## Polish batch (2026-11-03)

Four items, one at a time (built, screenshotted, checked, then the next), in
`/root/legalmind-worktrees/clm-p1`, uncommitted. `frontend-design` and `ui-ux-pro-max` loaded; bar:
Material / iOS navigation bars for the phone row, Carbon / Atlassian pinned action footers, WCAG 2.2
AA (44px+ targets, real tab semantics, focus kept visible). Reused `PageHeader`, `ACTION`,
`nextStep`, `PointStatus`; no state axis, `StatePill`, `DecisionControl` or `EscalateControl` touched.

| # | Before | After |
|---|---|---|
| 1 Contract page, phone (<900px) | Three tab rows (Document·Changes, Contract·Summary·Points) and the version select stacked before any content; the document scrolled inside a fixed-height card, empty space under it; a floating Ask circle over the text; the ⋯ menu opened off the left edge | **One bottom bar**: Contract · Summary · Points · Changes (badge = changes left for me) · Ask (opens its sheet; the floating launcher is gone). The version moved into ⋯ as a radio group ("Version 2 (client's, latest)" ✓). The page scrolls, not the card; the document's toolbar sticks under the shell; the page counter watches the viewport. ⋯ opens rightwards. Desktop unchanged (1440 shot). Summary kept as a fifth tab: dropping it would lose the stage view on a phone (bottom-nav limit 5 holds). |
| 2 Generated contracts | Gutters grew per level (0.39in → 1.2in), so 2.1.1.1.1's text began at 2.8in | One ladder in `house.json` `clause_ladder_twips`: 1 and 1.1 hang at the margin in a 0.5in gutter; levels 3–5 step in 0.5in each with one 0.75in gutter (2.1.1.1.1 fits; its text at 2.25in of a 6.3in measure); `(a)`/`(A)` hang 1/3in under the clause text (`list_twips`). `reading.ts` uses the same ladder in em at 11pt, and now also hangs a list number the text does not carry (a generated contract's 2.1.1 used to lose its number in the reading view). Sample: `/root/legalmind-clm-local/s3-samples/placeholder-contract-v2.pdf` (+ `.docx`). |
| 3 Template Replace editor | "N numbered sub-clauses will become plain paragraphs" under a 14-row editor and the reason, below the fold at 1440 and 1920 | The structure summary, Record and Back are a **pinned footer** (`.tpl-form__foot`, sticky to the side column's foot, or the screen's on a phone); the summary scrolls itself past 32vh. |
| 4 Signing record | "Board resolution Board resolution of 1 Oct 2026" (kind label + a client-profile reference that already names it); "· signed …" as a dot string | `authorityWords` says the kind and the date once (not repeated when the reference states them); `signedWords` is its own line ("Signed on paper on 2 Nov 2026", "E-signed", "Signed on …"). |

Checks: frontend tsc clean, vitest 792/792 (+4: ladder to level five, list numbers in the gutter,
authority / signed words), eslint baseline unchanged (51, none new), forbidden terms clean; backend
`tests/drafting` 113 passed / 1 skipped (numbering round-trip and preflight included), ruff + mypy clean.

Screenshots: `/tmp/claude-0/-root-Legalmind-v1/7d6f47a9-ed19-4884-8f81-719fbd5c0bac/scratchpad/polish/`
`before/` and `after/` — `1-contract-390`, `-menu`, `-scrolled`, `1-points-390`, `1-changes-390(-scrolled)`,
`1-ask-390`, `1-contract-1440`; `2-pdf-p1-1`; `3-replace-{1440,1920,390}`; `4-signing-record-{1440,390}`.
Own API :8599 (`legalmind_clm_e2e` for 1–3; for 4 a throw-away copy of `legalmind_clm_sign` migrated to
head — the copy lacked `executions.origin` from AM-298 — dropped afterwards), own build `.next-clm-pol`
on :3599, both stopped and removed.

### Still open

- The template approval's preview sheet (`PreviewSheet`, `.tpl-para`) keeps its own 2.6em step; moving it
  onto the same ladder is a small follow-up.
- The generated-contract reading view was verified by unit test only: no DB copy in reach holds a
  contract made from a template.
- The contract header still says "Signed 49 minutes ago" beside "Signed on 3 Nov 2026" (the page
  header, not the drawer).
- Phone, 760–899px: the bottom bar also applies (it is the narrow layout's breakpoint); not
  screenshotted at tablet width.

## MSA house style (from the approved format) (2026-11-04)

Measured from the owner-supplied approved MSA (`legalmind-clm-fixtures/approved/msa-approved-2025-07.docx`,
a Google Docs export: almost everything is direct formatting, the styles part is unused). Values only, no
contract text. Implemented in `backend/config/templates/house/house.json` → `render_contract.house_shell`;
the reading view mirrors the ladder (`frontend/.../workspace/reading.ts`, 1em = 240 twips at 12pt).

| Property | Approved format | House value |
|---|---|---|
| Page | A4 portrait, 11906 × 16838 tw | 210 × 297 mm |
| Margins | top/bottom/left 1440 tw, right 1286.5 tw; header/footer 708 tw | 25.4 / 25.4 / 25.4 / 22.7 mm; 12.5 / 12.5 mm |
| Body font | Times New Roman 12pt (53 016 of 53 058 characters), black | Times New Roman 12 (LibreOffice: Liberation Serif, metric-compatible) |
| Line spacing | single (`line=240 auto`) on every paragraph | 1.0 |
| Alignment | justified (207 of 244 text paragraphs); title centred | Normal justified; title centred; table cells left |
| Paragraph spacing | clauses 0/0 (144 paragraphs); front matter and definitions 6/6 pt (40); 12/12 (20, scattered); 50 empty paragraphs separate main clauses | normal 0/0 · front, recitals, plain headings, definitions 6/6 · level-1 heading 12 before, 0 after |
| Title | bold, centred, 12pt, typed in capitals | bold, centred, 12pt, all-caps |
| Level-1 heading | bold capitals, number not bold, keep with next | bold, all-caps, keep with next; numbers `w:b=0` |
| Sub-headings | not bold; some underlined (run formatting) | not bold |
| Numbering (main list) | `1.` / `1.1.` / `1.1.1.` / `1.1.1.1.` / `1.1.1.1.1.`, decimal, trailing dot, `lvlJc=right`, tab; ind left 720/1440/2160/2880/3600, hanging 360 | `clause_ladder_twips` [[360,720],[1080,1440],[1800,2160],[2520,2880],[3240,3600]], `number_suffix` ".", right-aligned |
| Definitions list (first pages) | separate list: 360/360, 792/432, 1224/504, left-aligned | not reproduced (one ladder for the whole contract) |
| Defined terms | “**Term**” — term bold, quotes plain | same (`definition` blocks) |
| Parties / recitals | `A.` `B.` upper-letter, ind 567 hanging 567 (number at margin, text 1cm); party names bold; "WHEREAS" bold label | `party_twips` [567,567], `%1.` upper-letter, restarted for parties and for recitals |
| Sub-lists | lower-letter `a.` / roman `i.` defined but unused; items are decimal level 3 | `(a)` hung 0.5in under its clause's text (`list_twips` [0,720]) |
| Signature table | 4 columns 1380/3255/1410/3120 tw (9165), borders single 4/8pt `BFBFBF`, header row spanning, fill `E7E6E6`, centred bold; cell margins 0 top/bottom, 108 left/right; rows ≥ 1139 tw | borders/fill/margins as measured; execution rows ≥ 1139 tw; our column-per-field layout kept |
| Header | three empty paragraphs (tabs 4513 c / 9026 r) — no logo, no text | `header_label` false (logo only when the template has one) |
| Footer | `PAGE` field only, right-aligned, Calibri 11 | document ID left, "Page X of Y" right (tab at the text width), 11pt |
| Sections | one main section + two continuous, page numbers start 1, no schedules | unchanged (a schedule is its own section, numbers restart) |
| Settings | defaultTabStop 720, compatibilityMode 15 | compatibilityMode 15, `doNotExpandShiftReturn` |

Side-by-side (reference left, generated MSA template right, 110 dpi):
`/root/legalmind-clm-local/msa-template/side-by-side-p1.png` … `-p3.png`.

### Round 2 (2026-11-04) — measured in the PDFs with PyMuPDF word boxes

- **Two ladders, as the approved file has.** Clauses 1–2 (Definitions, Interpretation) sit on their own list
  (`1.1.` number at 6.4 mm, text 14 mm; `1.1.1.` 12.7 / 25.4 mm; clause 1's text 10 mm, clause 2's 6.4 mm),
  clauses 3+ on the main one (`3.1.` 11–13 / 25 mm; `3.1.1.` 20–22 / 38 mm). `house.json` `lead_clauses`
  carries the first; generated numbers and text land within 1 mm of the reference at every level, except
  two-digit `1.10.`–`1.18.` (reference pushes their text to 25 mm, a tab overflow; ours keeps 14 mm).
- **Vertical rhythm** matches to 0.2 pt: 13.8 pt lines, 6 pt between front/definition paragraphs, a blank
  line (`front_gap_pt` 19.8) between front blocks, before clause 1 and before clause 2. Top margin set to the
  file's *effective* 34.3 mm (its header carries three empty lines over a 25.4 mm margin).
- **Front matter:** lettered parties with the bold name and its incorporation sentence, a bold "AND",
  the "Party/Parties" sentence, "WHEREAS", lettered recitals, a bold "NOW THEREFORE," run-in; quoted defined
  terms bold in the front matter; a numbered definition's opening term bold.
- **Execution:** the paired "By / Sign" table (Signatory Details header, By, Sign, Name, Designation,
  Signatory Email, Date of sign), with the "IN WITNESS WHEREOF" lead above it.
- **Footer:** page number right-aligned, Calibri 11 (as the file); the document ID at left in 8 pt.

### Round 6: cleaned (owner, 2026-11-04)

The approved file's look stays: font, margins, numbering style, headings and signature table. Its inconsistencies are
no longer copied.
- **One ladder** for the whole document. `lead_clauses` is removed, so clauses 1–2 sit where 3+ do: level-1 numbers
  right-aligned at 0.25in with text at 0.5in, level 2 at 1in, level 3 at 1.5in. Every level-1 number ends at the same
  x on every page (PDF: 90 pt on all 21).
- **Spacing by style, no empty paragraphs:** clause, sub-clause, definition and front-matter paragraphs 0/6 pt; a
  level-1 heading 12/6 pt. The file's blank-line gaps (before the parties, WHEREAS, NOW THEREFORE, clause 1 and the
  execution block) are now 12 pt before. Table cells, header and footer 0/0. The definitions and clause 2 follow the
  same rhythm as every other clause.
- **Keep-with-next** on headings and on title-only run-in lines. Widow and orphan control on.
- **Run-in titles:** only the title's words are underlined, never the colon or the trailing space.
- **Reading view** (`reading.ts`, `workspace.css`): one ladder; half a line after each paragraph, a line before each
  clause heading.
- Before/after: `/root/legalmind-clm-local/msa-for-management/compare/` (pages 1, 2, 5, 15; contact sheet).

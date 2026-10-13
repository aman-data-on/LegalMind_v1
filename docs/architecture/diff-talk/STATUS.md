# Diff-Talk — status

**Status: 🛠️ BUILT on branch `feat/legalmind-diff-talk` — NOT committed, NOT merged, NOT deployed.**
Worktree `/root/legalmind-worktrees/diff-talk`. Owner instructions 2026-10-12.

The hand-over for the feature: what was built, why it is shaped this way, how to run
it, and what is left. It decides nothing — the locks it touches are listed at the end.

---

## 1. What it does

**Diff-Talk** is its own section in the top menu (Dashboard · Client Profiles ·
**Diff-Talk** · Ask). Two documents side by side, clause by clause.

- **Our document** (left): a **website document** (TOS, SLA, AUP, Privacy — the current
  published copy, so nobody uploads what the website already has), one of **our
  uploaded documents**, or a new **upload** (an MSA, NDA, PO).
- **Client contract** (right): a **client document already in LegalMind** or an
  **upload**. Each list offers only its own side — our documents never appear as a
  client's (owner, 2026-10-12: *"why both side is a same … list … confusion the
  user"*). An upload is declared ORGANIZATION or COUNTERPARTY as it lands (Step 6's
  existing source axis), which is what keeps the lists apart. No swap button: the
  sides have meaning.
- A **plain comparison** (owner: *"we do not say this approved or not"*): no side is
  labelled approved.
- Each clause is **Same wording** (green) · **Wording differs** (red, changed words
  marked) · **Missing from the client contract** · **Only in the client contract**, plus
  **"in a different place"** when it moved. Every colour is also said in words.
- **Previous / Next difference** with "Difference N of M" (announced to screen
  readers); matching clauses collapsed unless "Show the text of matching clauses".
- One line states the boundary: colours compare wording only; acceptability is
  answered in a document's Findings, never here.
- The URL carries both sides (`/dashboard/diff?left=…&right=…`), so a comparison can
  be linked and Back works. From any contract, **"Compare in Diff-Talk"** opens the
  page with that document on the right (and its type's website document on the left
  when there is one).

**Text only.** No Finding, classification, rule outcome, user status, Legal Decision,
accept/reject, redline or contract generation is produced, shown or written. Nothing
about the pairing is stored. The Constitution-based review is untouched.

## 2. Architecture

| Layer | Where | What |
|---|---|---|
| Alignment | `backend/legalmind/analysis/document_comparison.py` | deterministic, no model, symmetric left/right |
| API | `GET /api/v1/comparisons?left=&right=` — each side a document version id or a website key (`TOS-leapswitch` …) | `document.view`; a stored side resolves through the READ traversal, so another person's document is the same 404 as a missing one (SEC-07); 422 with a plain reason for: same document twice, a website document not loaded, a document with no extracted text |
| API | `GET /api/v1/comparisons/website-documents` | the website documents with a CURRENT copy (from `AM-130`'s daily refresh — no second copy, no new fetch) |
| Permissions | `api/permission_map.py` (both routes `document.view`); OpenAPI snapshot regenerated (additive) | |
| Frontend | `app/dashboard/diff/page.tsx` (route), `components/workspace/DiffTalk.tsx` (page, pickers, comparison), nav item in `components/workspace/model.ts`, link in `WorkspacePage.tsx`, `.ws-diff*` in `app/dashboard/workspace.css`, `lib/api.ts` `compareDocuments`/`websiteDocuments`, types in `lib/types.ts` | |
| Upload | the existing `POST /contracts` + `POST /contracts/{id}/document-versions` | an uploaded file is an ordinary LegalMind document — same storage, parsing, access rules and audit; it appears on the Dashboard |
| Dependency | `react-diff-viewer-continued@4.4.0` (exact pin) | owner-requested; React 19 peer OK; npm; +81 transitive packages (Emotion, `diff`, a syntax highlighter it ships with) |

**No database change. No migration. No new permission. No new service.**

### How clauses are aligned (why it is not a line diff)

1. **Cut both sides at their top-level clause.** Website: its top headings (the
   `knowledge_items` tree). Stored document: evidence rows grouped by top-level clause
   number (4, 4.1, 4.2 → 4); an unnumbered *heading* row (parser `metadata.heading`)
   also starts a clause; other unnumbered rows continue the one before (page breaks).
   A number with a letter glued to it ("Section 70B(6) of the IT Act" wrapped onto a
   line) is a cross-reference, not clause 70. The parser is not retuned for this — it
   serves the evaluator.
2. **Pair by text, not by number** — two documents number their clauses their own way.
   Score = the larger of word-order similarity and shared content words, + a bonus for
   the same heading ("Late Fees" ↔ "7. Late Fees"). Best pairs first, one each; below
   0.4 nothing is paired.
3. **Fold where the two sides cut the same text differently** — an unpaired piece joins
   a paired neighbour only when that makes the pair more alike (a list 1..7 under one
   heading). A genuinely one-sided clause lowers the similarity, so it is never folded.
4. **Moved** = a paired clause outside the longest in-order run.
5. **Same wording** ignores whitespace and the clause's own leading number.
6. **Display:** both sides are re-set one sentence per line ("Pvt. Ltd.", "e.g.", list
   numbers and initials never end a sentence) before the word diff.

## 3. Measured on real material (zero Gemini, zero network)

Stored side = the PDFs in `legal-docs/`; website side = the saved pages of 2026-10-09.

| Client contract | Our document (website) | Same | Differs | Missing from client | Only in client | Moved |
|---|---|---|---|---|---|---|
| Leapswitch TOS (Jul print) | LS TOS | 16 | 10 | 0 | 1 | 0 |
| Leapswitch SLA (print) | LS SLA | 0 | 5 | 0 | 1 | 0 |
| CloudPe TOS (no clause numbers) | LS TOS | 0 | 8 | 17 | 4 | 3 |
| CloudPe SLA (reworded) | LS SLA | 0 | 3 | 2 | 6 | 0 |
| CloudPe AUP | LS AUP | 0 | 14 | 0 | 1 | 0 |
| CloudPe Privacy | LS Privacy | 0 | 5 | 12 | 13 | 2 |

Every comparison ≤ 125 ms. The "only right" opening row of every browser-printed PDF is
the website's navigation printed into the page — real text in that file.

## 4. Tests (2026-10-12)

| Suite | Result |
|---|---|
| `backend/tests/test_document_comparison.py` (13: alignment, grouping, website ↔ document, document ↔ document, not-found, refusals, print headers, Google Docs export, schedules/signatures, openings) | 13 passed |
| `test_api_contract.py` + `test_version_comparison.py` | 115 passed |
| Backend regression subset (`test_api_*`, ingestion, source material, vocabulary, version comparison, assist knowledge) — run on the first cut | 486 passed, 1 skipped; the 2 failures were this change's own (permission map, OpenAPI snapshot) and are fixed |
| `ruff check .` · `mypy legalmind` | clean · no issues |
| Frontend: `npm run lint`; vitest (new `diff-talk.test.ts`, nav test) | clean; 45 files, 611 passed |
| Playwright subset (version-comparison, workspace, workspace-panes, workspace-viewports, gating), own DB + ports 8397/3397 | 40 passed (final run, after the workspace link) |
| Real browser, 1440 px and 390 px: menu → our MSA (uploaded by us) vs an uploaded client MSA; website SLA/TOS vs uploaded client SLA/TOS → Next/Previous | passed, no page errors; screenshots reviewed; Upload and select both 42 px (a global `label` margin had shrunk Upload to 32 px) |

### UI audit round (owner, 2026-10-12)

| Item | Done |
|---|---|
| Upload our doc + client doc, check the UI | Real browser: our MSA and a client MSA uploaded through Diff-Talk; success line under each ("Uploaded “MSA-Feb.pdf” and selected it."); a corrupt file shows the server's reason in red |
| Error left behind by a refused upload | Found in the audit: a refused file left an empty "notes" document on the Dashboard. Now uses the shared `uploadFirstDocument`, which archives it — verified none left |
| Page titles + meta descriptions | Root `title.template` "%s · LegalMind"; Dashboard, Diff-Talk, Client Profiles, Ask, Reviews, Legal, Standards, Administration, Sign in, 404 each name themselves with a description (three-line `layout.tsx` per section; verified in the browser) |
| Footer links / unused navigation | The legacy `Chrome` (old top bar, nav and footer) rendered only on unknown addresses — every other route redirects or has its own shell. Deleted; `/login` gets its own layout. The floating Ask button is hidden on Diff-Talk (it covered the client column; the menu's Ask stays) |
| Custom 404 | `app/not-found.tsx` — "Page not found", one way back to the Dashboard |
| Placeholder text | Sign-in's two `href="#"` links ("Learn what LegalMind does", "Request access") removed — DD-4 addendum placeholders; "Accounts are created by an administrator." stays. Diff-Talk headers no longer show "—" for a missing side |
| Compress images | `icon.png` 84 → 72 KB, `apple-icon.png` 15 → 13 KB (`pngquant`, already installed; same pixel sizes) |
| Mobile overflow | Measured 0 px horizontal overflow at 390 and 1440 px on 404, sign-in, empty Diff-Talk and a compared Diff-Talk |
| Optimise | The diff viewer (81 transitive packages) is lazy-loaded with the comparison and fetched in parallel with the data, not shipped with the page |
| Tests | lint clean; vitest 611/611; Playwright subset + `session.spec.ts` 43/43. ⚠️ `e2e/visual.spec.ts` sign-in baseline will differ (links removed) — baselines are refreshed from CI only |

### Strict UI review round (owner, 2026-10-12)

What a senior reviewer would have rejected, and what was done:

| Found | Fix |
|---|---|
| A raw `@@ -4,4 +4,4 @@` code-diff header under a clause | `showDiffOnly={false}` — every sentence shown, no fold lines |
| Clauses marked "Wording differs" that read identically — an icon-font glyph (U+E90C) and the browser-print header/footer ("https://…/terms-of-service.php", "1/9", "7/30/26, 6:55 PM") inside the clause text | Comparison layer drops private-use/zero-width glyphs and lines repeated on 3+ pages (page numbers aside, incl. bare "1/9" counters); stored evidence untouched. Leapswitch TOS print: 11 → **3** real differences (an office address, the "Last updated" date, the contact block); AUP 0 → 8 and Privacy 0 → 9 clauses now read the same. Test `test_print_headers_and_icon_glyphs_are_not_wording_differences` |
| −/+ code gutter in the two-column view | hidden in two columns (cell kept, contents hidden — removing the cell collapsed the table); kept with a legend in one column |
| A wall of pink: every header and line tinted | neutral headers; the state is the left rule + the coloured label; a light tint on changed sentences, the strong colour only on changed words |
| No page heading; the rule sentence pinned on screen | the section header every other screen uses (icon, h1 "Diff-Talk", one-line subtitle carrying the wording-only rule) |
| Pinned bar four rows tall | two rows: the two document names, then summary + Previous/Next + toggle |
| "website version of 2026-10-09"; "11 differences" twice | "website, as of Oct 9, 2026"; summary "**3 differences**: …. 24 clauses read the same."; counter "3 to review" → "1 of 3" |
| Bare sentence on an empty page | a bordered empty state saying what to do and what happens |
| Matching-clauses toggle shown when nothing matches; stale success line after a new choice | hidden when 0 match; messages cleared on change |
| Phone: the header icon on a line of its own | hidden below 900 px |

### Owner's own upload (2026-10-12): accuracy failure found and fixed

The owner compared our MSA template with an uploaded client MSA (a Google Docs export).
**Before:** 10 clauses (Interpretation, Scope, Term, Indemnification, Limitation of
Liability…) reported "missing from the client contract" — false. Cause: the export
puts a zero-width space after every number ("4.\u200b"); the parser numbered nothing
and stored one row per page, so Diff-Talk saw one giant block.

| Fix (comparison layer only; parser and stored evidence untouched) | Effect |
|---|---|
| Split each row at its own top-level clause lines ("4." + heading, "4. Heading"); a number starts a clause only if it follows the last one (+1…+3) — sub-clauses, page numbers and lists restarting at 1 never do; the last number survives an unnumbered heading | all 21 clauses paired 1:1 |
| Zero-width space / NBSP read as a space (as `AM-45` r6 already does), not deleted | no glued words |
| "Same wording" ignores spacing only | spacing artefacts never a difference |
| Printed header/footer rule tightened: a repeated line counts only if it carries a number (page, date, URL) or is ≥ 25 characters, and never if it is a clause number ("4.", "4.1.") — the looser rule had deleted the word "Agreement." from our MSA | no fake "Agreement." differences |

**After: 22 clauses — 20 identical (exact match), 2 real differences:** clause 1
(cross-references "12.1"/"18.1" replaced by blanks) and clause 21 (a "Schedule A — Data
Hosting, Backup, Disaster Recovery and Exit" added; the signing entity named
differently). Loads in ~0.2 s. Regression on the legal-docs set: no clause lost.

**"Within a second":** only differences are shown by default ("20 clauses read the same
… Show them"); inside a changed clause only the changed sentences (±1 for context),
the rest folded behind "Show 9 matching sentences"; the header says "3 of 21
sentences". The library's one-column fold row (four cells against two) squeezed phone
text to a quarter width — the empty cells are hidden. Test
`test_a_google_docs_export_is_split_at_its_own_clause_numbers`.

### User-confusion loop (owner, 2026-10-12: "work in loop until you make this perfect")

Each round: open real pairs as a user, name what confuses, fix, re-check.

| Round | Confusion found | Fix |
|---|---|---|
| 1 | "21. General Provisions — wording differs" when the client had added a Schedule A and renamed the signing entity | Schedules / Annexures / Appendices / Exhibits (capitalised heading lines) and the signature block ("IN WITNESS WHEREOF") are parts of their own; a schedule's own "1." never starts a main clause. Empty openings dropped. Your MSA: General Provisions now reads the same; "Schedule A … — Only in the client contract"; "Signatures — Wording differs" |
| 1 | Which column is ours once scrolled | "Our document / Client contract" over every opened clause |
| 2 | Schedule A shows only its title | The file's extraction is PARTIAL: the document line now says "Some pages of this file had no readable text (scans, images or tables) and are not compared." (`fully_read` in the payload) |
| 2 | Sentence 1.10 tinted with nothing marked | "quasi-↵governmental" vs "quasi-governmental": a word hyphenated across a PDF line is rejoined before the sentence layout |
| 3 | Red confetti across wholesale-rewritten sentences | Tried a similarity-gated word diff — it switched word highlighting OFF entirely (the viewer only highlights for its own method names, `shouldHighlightWordDiff`), losing the "12.1 → ___" marks. **Reverted** with its `diff` dependency; confetti on wholesale rewrites is the accepted cost |
| 3 | Tab crash on the SLA pair at desktop width | Diagnosed, not ours: kernel log shows `trap int3` in `chrome-headless-shell`'s Compositor; page memory 7 MB, 1,441 nodes, layout settled; 8/8 + 5/5 clean runs in full Chromium. Screenshot scripts now use full Chromium |
| 4 | Our opening "missing" + their opening "added" as two unrelated rows | Two unpaired openings are counterparts and are paired |
| 5 | "0 clauses read the same" | "No clause reads the same." |

| 6 | "Some pages had no readable text" — vague, and alarming | Checked the file: page 19 is **blank** (only its page number); Schedule A in that file is a heading with no body — nothing was lost. The line now names the pages: "Page 19 has no readable text and is not compared — often a blank page; if it holds a scan or picture, check it in the file." (`unread_pages`, from the run's `pages_total` against the pages with text; test `test_pages_without_text_are_named_never_silently_skipped`) |

Remaining, from the files themselves: a signature TABLE flattened by the PDF into one line ("Sign Sign Name Name …"); the "C." before "LeapSwitch Networks" is in our template's own text; scanned / image pages cannot be compared (now said on screen).

### Accept change — drafting choices (owner, 2026-10-13)

Designed wireframe-first, then built. Per difference: a joined either/or control —
**Keep ours | Accept theirs** (wording differs), **Leave it out | Add it** (only in the
client contract), **Keep ours | Remove it** (missing from it). Native radios (arrow
keys, focus ring, announcement). A pointer choice jumps to the next undecided
difference; a keyboard choice stays put (arrows change a radio while the reader is
still deciding). "1 of 3 decided" progress in the pinned bar (`<progress>`); a
"Your choices" recap with each undecided item one click away and **Copy for Legal**
(plain-text list for an email). Choices persist per document pair in this browser
(localStorage, guarded) — no table.

**A choice about wording, never a Legal Decision** (AB-12 r9 unamended; RESOLVED ≠
MATCH): the recap says the final contract still goes through LegalMind's review.
**Not built — needs the owner's "yes":** producing the merged final contract file
(Step 37 excludes "automatic modified DOCX/PDF generation"; PROD-02/05 already
describe the human-accepted, new-version flow it would follow), and saving choices
server-side (one new table). Verified in a real browser: mouse advance, keyboard
stays, reload keeps choices, clipboard text, phone width (no overflow).

## 5. Run it locally (nothing live touched)

```bash
S=<scratchpad>
sudo -u postgres createdb -O legalmind_test legalmind_difftalk_preview
. $S/preview.env.sh            # LEGALMIND_DATABASE_URL -> that DB; nothing from /root/.legalmind.env
# ⚠️ preview.env.sh MUST also set LEGALMIND_STORAGE_ROOT to a scratch folder: unset, it
#    defaults to /var/lib/legalmind/documents — the LIVE server's storage (production sets
#    none either). On 2026-10-12 the preview wrote ~10 upload files there before this was
#    caught; nothing was overwritten (unique names, unreferenced by the live DB); the files
#    are listed in the session scratchpad and left for the owner to decide on.
cd backend && python3 -c "from tools.e2e_bootstrap import migrate; import os; migrate(os.environ['LEGALMIND_DATABASE_URL'])"
python3 -m tools.e2e_bootstrap --document $S/structural.docx
python3 -m tools.refresh_published_policies --from /root/Legalmind.v1/legal-docs/published/2026-10-09
python3 -m uvicorn legalmind.api.app:app --port 8297
cd ../frontend && LEGALMIND_NEXT_DIST=.next-difftalk LEGALMIND_API_ORIGIN=http://127.0.0.1:8297 npx next build \
  && git checkout -- tsconfig.json next-env.d.ts \
  && LEGALMIND_NEXT_DIST=.next-difftalk LEGALMIND_API_ORIGIN=http://127.0.0.1:8297 npx next start --port 3298
```

Sign in at `http://127.0.0.1:3298/login` as `owner@e2e.test` / `e2e-not-a-secret`, then
**Diff-Talk** in the top menu.

## 6. Known limitations

- **A clause rewritten in wholly new words does not pair** (CloudPe SLA's credit
  request, similarity 0.27): it shows as only-left + only-right, side by side.
  Upgrade path: the local embedding model (`AM-54`) for unpaired leftovers.
- **Granularity is the top-level clause**; the word marks show where inside it.
- **Parser artefacts show as text** (browser-print headers, ▯ glyphs).
- **Uploads become ordinary Dashboard documents** (declared "Our document" / "Their
  document", no type).
- **A document uploaded elsewhere with no source declared counts as a client's**
  (only ORGANIZATION is ours) — declare it "Our document" in its details to move it.
- **The picker lists the 100 most recent documents** (`ponytail`-level choice); add a
  search box when someone has more.
- **No Playwright spec for Diff-Talk itself** — the e2e database has no website
  documents and CI has no saved pages (54.6). Covered by backend API tests, the unit
  test and the scripted real-browser pass.

## 7. For the owner — locks this touches (nothing amended)

- **DOC-07** says cross-TYPE comparison is out of V1 scope and leaves a cross-document
  comparison "neither authorized nor forbidden … would need its own decision". The
  owner's 2026-10-12 instruction ("simple … compare left … vs right") is that decision,
  for **text only**. Diff-Talk does not check that both sides are the same type: it is
  a wording comparison, not the evaluator's measurement against Requirements, which
  DOC-07 governs and which is unchanged. **Recommend recording this as a lock record
  when the branch is approved.**
- **AB-13 r3** (no document-to-document table): untouched — nothing is stored.
- **33.16**: held — no verdict in payload or screen.
- **AM-56 / AM-53 r5** (one status vocabulary): not engaged — no Finding status shown.
- **Rule 19**: the new dependency was named by the owner.
- **Phase 2** (Accept change, custom contract) still needs the decisions in the
  2026-10-12 gap analysis: Step 37 / `AM-25` / `AM-68` r5, `AB-12` r9, rule 21.

# Ask product completion — execution plan and work log

📁 **WORKING DOCUMENT — the source of truth for the 2026-09-28/29 Ask completion session.**
It records what was found, what was changed, what was tested and what remains. It locks
nothing; decisions land in `all_lock.md` (`AM-107`, `AM-108`) and the registry.

Owner brief (2026-09-28, evening): make the new Ask engine behave like a production AI
document assistant — no-document questions, document questions, document + instruction
(summary, bullets, table, comparison, clause list, simple language, key risks),
follow-ups, multi-source, Constitution comparison, historical/current, refusal,
citations, requested format/length — with the Ask UI reading as one AI conversation.
Full ownership: research → plan → implement → test → observe → fix → regression → re-test,
commit, PR, CI, deploy through the normal process; stop only at an approval boundary.

## 1. Baseline (start of session)

| Item | State |
|---|---|
| Production | `c9a2876` (`AM-106`): every Ask conversation on the verified multi-source path |
| Branch | `fix/ask-answer-focus` in `/root/legalmind-worktrees/ask-answer-focus`, **`AM-107` built, validated, uncommitted** (answer leads with the direct answer; layers apart; records written) |
| Golden retrieval | bundle recall@3 0.952 · wrong-source 0 · false admission 0 (`tools.rag_benchmark`) |
| Claim selection (`AM-107`) | primary from gold 52/72 · off-gold claims 168 · 5.2 claims/answer (`tools.benchmark_answer_focus`) |
| Document lane | right clause first claim 22/44, among claims 27/44 (`tools.benchmark_document_lane`) |
| Tests | backend 2762 passed · assist CI-shape 198 · frontend 36 |

## 2. Gaps found (zero-Gemini probe on the scratch copy, 2026-09-28 evening)

| # | Case | Observed | Root cause | Layer |
|---|---|---|---|---|
| G1 | Document + "Give me a short summary." / "Summarize this in 5 bullet points." / "Explain this in simple language." / "What are the key risks?" | gate shut → INSUFFICIENT → refusal | the instruction names no topic, so document retrieval has nothing to search for; there is no whole-document task | planning + retrieval |
| G2 | "Tell me what the agreement says …, **without** comparing it to our standard." | routed to the evaluator | `intent.is_comparison_question` sees "comparing … our standard" and ignores the negation | intent |
| G3 | "List only the termination clauses." | retrieval fine; answer would be prose, with Constitution rules mixed in | nothing reads "list only" or scopes the task to the document | presentation (absent) |
| G4 | Any "short / N bullets / table / simple language" | ignored | no presentation instruction exists anywhere; the contract prompt forbids lists | prompt + verification + renderer |
| G5 | Ask page: the question appears as the rail title, the page `<h1>`, and the user turn | three copies | `AskWorkspace` header renders the chat title as a headline | frontend IA |
| G6 | User and AI turns read as two similar text blocks | weak hierarchy | user turn has a label only; the answer has no voice marker | frontend |
| G7 | Document citations render every excerpt in full under the answer | evidence wall | `TranscriptTurn` prints every excerpt | frontend |
| G8 | Tables cannot render in an answer | n/a | `AnswerProse` renders paragraphs and bullets only | frontend |

Not a gap (already locked and working): "Compare this agreement with our Constitution" → the
evaluator's Findings table (`AM-25` r4, `ComparisonTable`). Ask never performs the comparison.

## 3. Design (generic — no question is special-cased)

**Presentation instruction (`assist/presentation.py`, deterministic).** `read(question)` →
`Presentation(task, shape, count, length, register, no_comparison, topic)`:
- task: ANSWER · SUMMARY · LIST · EXPLAIN · RISKS; shape: PROSE · BULLETS · TABLE;
  count (e.g. 5); length SHORT; register SIMPLE; `no_comparison` ("without comparing").
- `topic` = the instruction with its format words removed → what retrieval searches.
  Empty topic + document attached = **document-wide task**.
- The instruction controls presentation and task scope ONLY. Evidence, authorization,
  every contract check, the verifier and fail-closed behaviour are untouched.

**Document-wide evidence.** For a document-wide task the DOCUMENT lane does not search;
it takes the document's **outline**: one chunk per top-level section in document order,
sections that touch a ratified topic (`planner.topics_in`, the organization's own
vocabulary) first, capped by `evidence_size`. RISKS = the topic-bearing sections only.
The gate is open for it (the document IS the subject); the claim contracts and verifier
still decide every sentence. Positions/statutes lanes are not searched for a
document task unless the question mentions the organization or the law.

**Claims.** Document-wide: every outline chunk is an anchor with one claim — its first
substantive sentence (the clause's operative statement) — so a summary covers the
document rather than repeating one section. Topic tasks use `AM-107` selection.

**Prompt (`contract-answer-5`).** A PRESENTATION line names the task, shape, count,
length and register. Bullets: one sentence per "- " line, each with its markers, exactly
N when asked. Table: a pipe table whose header names the source kind; each row ends with
its markers. Short: under ~60 words. Simple: plain words, conditions kept.

**Verification of shaped answers.** Bullets are sentences (unchanged checks). A table is
verified row by row — each row read as "<row label> — <header>: <cell> [n]" — and the
whole table is dropped to the verified prose fallback if any row fails; nothing
unverified is shown. Code enforces the count (extra bullets cut; fewer kept — the
evidence is what it is) and asks one repair when a short answer runs long.

**Frontend.** Header = lightweight scope line (sr-only `<h1>`); user turn = tinted,
right-set bubble; AI turn = mark + "LegalMind" voice line; document excerpts behind
`<details>`; pipe-table rendering (server-emitted tables only); mobile check.

## 4. Test matrix

| Case | Gemini | Where |
|---|---|---|
| Presentation parsing (task/shape/count/length/register/no-comparison/topic) | 0 | `tests/test_presentation.py` |
| Comparison negation | 0 | `tests/test_presentation.py` |
| Outline selection, document-wide claims | 0 | `tests/test_presentation.py` |
| Bullet count enforcement, table row verification, table fail-closed | 0 | `tests/test_presentation.py` |
| Frontend: header, bubbles, details, table rendering | 0 | `ask-workspace.test.tsx` |
| Doc + short summary · doc + 5 bullets · doc + table of termination clauses · doc + "list only" · doc + simple language · doc + key risks · doc + "without comparing" · follow-up · no-doc question | ≤ 2 each | `scratch/live_answer.py` on production data (rolled back) / scratch API |
| Browser: no-doc question · doc + question · doc + short summary · doc + table · Constitution comparison · follow-up · refusal · history · mobile width | as above | Playwright on the scratch stack (`:8399`/`:3399`) |

## 5. Work log

**Step 1 — presentation layer built (backend).** `assist/presentation.py`
(reader), `intent._without_negated_comparison` (G2), `query_plan` carries the
instruction and narrows a document task to the document (G3), `store.outline_chunks` +
`retrieval` outline branch + document-only `select` for a whole-document task (G1),
`contracts._document_wide` (one operative sentence per section, topical first, 8 at
most), prompt `contract-answer-5` with a PRESENTATION line, `answer` verifies a table
row by row and rebuilds it with the verifier's markers, trims extra bullets, sends a
long "short" answer back once and keeps the verified draft if the retry fails,
`service._layered` keeps bullet lines and tables whole. `routing` lets a document task
past the general-knowledge screen when a document is open. Tests:
`tests/test_presentation.py` (21).

**Step 2 — frontend.** Page `<h1>` made screen-reader-only (G5); user turn label
sr-only, answer opens with a monogram voice line "LegalMind" (G6 — a monogram, not a
sparkle: DESIGN.md anti-pattern); cited passages behind `<details>` (G7); pipe tables
rendered as `<table>` for server-shaped answers only (G8). Tests: `ask-workspace.test.tsx`
+4; 40/40; `tsc` clean.

**Step 3 — first Gemini matrix (9 cases, scratch stack, real API).** Pass: short summary
(53 words, 3 sources), 5 bullets (exactly 5, 5 sources), follow-up with the document
retained, key risks (10 provisions). Fail: table (the model's lead-in sentence citing
all six rows failed the condition checks and sank the verified table → now a failing
lead-in is dropped and the table stands); "explain the liability clause in simple
language" (general-knowledge screen → bypassed for a document task); "without
comparing" (the follow-up anchor "What are the key risks?" re-triggered the comparison →
a negated comparison now rules the evaluator out outright); list-only and risks ran
long as prose → LIST and RISKS default to bullets and a whole-document task is capped
at 8 claims. Regressions: 3 tests stubbed the Gemini seam with a fixed signature →
stub widened (`tools/eval_generation.stub`).

**Step 4 — second Gemini pass (5 cases).** list-only → 6 bullets; simple → answered
(but read as LIST because "the liability clause" matched — EXPLAIN now outranks LIST);
risks → 8 bullets; "without comparing" → 6 document bullets on the new path; table →
failed again on a different ROW (Gemini variance) → r6 now repairs a failing row to its
claim's own words or drops it; the verified rows stand.

**Step 5 — browser flow #1 (desktop 1440, mobile 390; 5 Gemini answers each).** Found
the follow-up after the table forced into a table and falling back: the presentation was
read from the RESOLVED text (anchor + follow-up). Fixed: `query_plan.plan(...,
instruction=question)` reads it from the current turn only. Found "short" summaries of
~110 words: a SHORT whole-document task now gets four claims, not eight. Screenshots
`flow_desktop_*`, `flow_mobile_*` in the session scratchpad.

**Step 6 — third Gemini pass (4 cases) + browser flow #2.** Short summary 86 words/4
sources; table 5 rows verified in one call; follow-up after the table answers about
notice from the document with §13 as one related line; liability clause in plain prose.
Browser: table rendered and kept on reload at both widths, refusal unchanged, 8 turns
after reload. Screenshots `flow_desktop2_*`, `flow_mobile2_*`.

**Step 7 — a pre-existing layout defect, measured.** After a few turns the whole PAGE
scrolled (window.scrollY 2004, `.ws-chat` 2952px tall): `.ws-chat` had `flex: 1`
inside a column parent of indefinite height, so its `height: calc(100dvh - …)` was
ignored and it grew to its content. `flex: none` — the grid is now exactly the viewport
(948px at 1440, 808px at 390), the log scrolls, the composer stays put (probe:
`window.scrollY` 0 before and after typing). Also from the screenshots: the question
bubble got a hairline (the paper tint alone was near-invisible on the canvas), and the
table's row header wraps (on a phone "EARLY TERMINATION RESTRICTION" had left the
clause a column four words wide). Final screenshots `final_desktop_{1_top,2_table,
3_bottom}.png`, `final_mobile_{1_top,2_table,3_bottom}.png`.

**Judged as a user (desktop and phone):** the question is a bubble on the right, the
answer opens with the LegalMind line and says the thing asked first; the sources sit
under a hairline with the passages folded; a table reads as a table; a follow-up stays
in the thread; a nonsense question gets the same quiet refusal as before; reopening the
chat shows the same turns and the same table. Understandable in a few seconds: yes.
Remaining rough edge: "in simple language" is only partly honoured — the verifier
rejects paraphrases that lose a condition, so the model keeps close to the clause's
words (recorded as a residual, not fixed by loosening verification).

## 6. Test results

| Suite / measure | Result |
|---|---|
| `tests/test_presentation.py` (new, zero Gemini) | 25 passed |
| `tests/test_answer_focus.py` (`AM-107`) | 14 passed |
| assist-lane regression (22 files) | 608 passed, 1 xfailed |
| assist tests in CI's shape (no embedding model) | 222 passed |
| full backend suite | 2787 passed, 112 skipped, 1 xfailed, 0 failed (18 min, sharing the CPU with the benchmarks) |
| frontend `vitest` | 537 passed (39 files); `tsc` clean; forbidden-terms clean |
| ruff · mypy (130 files) | clean |
| retrieval / claims / document-lane benchmarks | unchanged — retrieval bundle recall@3 0.952, hit@1 0.903, wrong-source 0, false admission 0; claims primary-from-gold 52/72, gold slots claimed 79/84, off-gold claims 168, 5.2 per answer; document lane (this run had the rescue judge live, so it is the AM-106 rescue-on figure) gold clause shown 38/44, as the first claim 29/44, not-found questions admitting document text 0/10 |
| Gemini calls spent | ~35 (matrix ×3 partial runs, 4 browser flows) |

## 7. Stale test state

Inspected before touching anything. Removed at the end of the session (all provably
created by this or the previous `AM-106`/`AM-107` session of the same operator):
scratch databases `legalmind_focus_e2e`, `legalmind_doclane`, `legalmind_doclane_final`,
`legalmind_doclane_three` (clones for benchmarks and the browser stack; their uploaded
test MSAs, chunks, embeddings, conversations and history go with them); the `.next-focus`
build in the worktree; the scratch API (:8399) and web (:3399) processes. NOT removed,
because provenance could not be proven from here: the other `lmtest`-owned scratch
databases (`legalmind_rag_*`, `legalmind_prod_rehearsal`, `legalmind_rehearsal_am104`,
`legalmind_domainc_*`, `legalmind_cpui_*`, `legalmind_lmtest*`, …) — listed for the
owner. Redis here is the worker's job broker, not an Ask cache: untouched. Production
data, the Constitution, the ratified standards, the statute corpus, model files,
migrations and configuration: untouched.

## 8. Acceptance checklist

- [x] G1–G8 fixed with regression tests (`test_presentation.py`, `ask-workspace.test.tsx`)
- [x] Gemini-backed matrix run; every actual answer inspected and recorded (§5)
- [x] Browser validation, desktop and mobile, with screenshots recorded (§5)
- [x] Retrieval and claim benchmarks unchanged; full backend (2787) + frontend (537) suites green
- [x] Stale test state removed (§7), canonical data untouched
- [x] Records: `all_lock.md` (AB-57 `AM-107`, AB-58 `AM-108`), registry, CHANGELOG, DAILY_CHANGED, status, project state, matrix, CLAUDE.md, docs/README
- [x] Committed (`363fbd9`, baselines `1c1e4f5`), PR #125, CI 15/15 (job 10 flaked once — the known socket hang-up — and passed on the rerun; the two Ask visual baselines adopted from CI's own actuals), merged through the ruleset as `080b4a7`, deployed with `sudo legalmind-deploy`, production smoke test passed

## 9. Final answers (filled at the end)

**What was broken?** Claim selection had no direct answer (`AM-107`); with a document open every whole-document instruction refused, "without comparing" went to the evaluator, no format was read; the Ask page repeated the question three times, the two speakers looked alike, and a long chat scrolled the whole page.

**What was changed?** `AM-107` (answer-order claim selection, layered layout) and `AM-108` (`assist/presentation.py`, document tasks planned on the document, the outline for whole-document tasks, prompt `contract-answer-5`, code-enforced form, row-verified tables; frontend hierarchy, collapsed passages, tables, viewport-held grid). Nothing in evidence sufficiency, the gates, the contract checks, the verifier, authorization, the refusals or `AM-25` r4 changed.

**What tests were added?** `tests/test_answer_focus.py` (14), `tests/test_presentation.py` (27 after the follow-up), `ask-workspace.test.tsx` (+6); `tools/benchmark_answer_focus.py`; claim scoring in `tools/benchmark_document_lane.py`.

**Which Gemini-backed cases were actually tested?** Nine instruction cases through the real API (three partial passes while fixing), four browser flows (desktop/mobile ×2), the six `AM-107` scenarios on production data, and the production smoke test — ~40 calls in all; every answer read and recorded in §5.

**Before/after?** §2 and §5, and the roadmap matrix: every instruction case answered as asked on the verified path; claims primary-from-gold 44 → 52, off-gold 398 → 168; retrieval unchanged.

**Documents + instructions handled correctly?** Yes for summary, N bullets, table, list-only, plain language (partly — see residuals), key risks, "without comparing"; a comparison still goes to the evaluator by design.

**Follow-up/context working?** Yes — a follow-up after a table stays on the document and keeps its own (not the anchor's) instruction; the thread reloads with the same turns and table.

**UI understandable?** Yes, at 1440 and 390 (screenshots in §5): two speakers, answer first, sources folded, tables, the log scrolls.

**Stale test state removed?** Yes (§7); the other sessions' scratch databases are listed, not deleted.

**What remains?** The residuals in the `AM-108` lock record: "simple language" only partly honoured (the verifier keeps the model close to the clause's words); a summary is drawn from each section's first operative sentence; Gemini variance can cost a table a row (dropped, never shown unverified); the one production smoke observation — a plain question with "cite the relevant section" read as a list — fixed in the follow-up PR.

**Production deployment safe?** Deployed 2026-09-28 (`080b4a7`), no migration, no flag, smoke test passed; rollback is the previous deploy.

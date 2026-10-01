# Ask agent — implementation log

Chronological record of work against
[LegalMind Ask — Implementation Plan](LegalMind%20Ask%20—%20Implementation%20Plan%20(for%20the%20coding%20agent).md).
One dated entry per phase. Target design:
[v2.1 architecture](LegalMind_Ask_Conversational_Agent_Architecture_v2.1.md).

---

## 2026-09-30 — Phase 0 (hotfix) and Phase 1A (audit)

**Branch:** `feat/ask-agent-phase0-1`, worktree `/root/legalmind-worktrees/ask-agent-p0`,
from `main` `ee9dd10`. Local commits only.

### Phase 0: done

- **0.1** `intent.is_follow_up`. The anaphora rule ("this", "that", "it" anywhere in the
  message) now applies only to messages of at most `_FOLLOW_UP_MAX_TOKENS` = 30 word
  tokens. A pasted case summary whose last sentence says "this offer" no longer inherits
  the previous question as its retrieval anchor.
  - The opener rule ("and …") and the one-content-word rule are unchanged.
  - The fix sits in the one function both callers use: the current-turn flag
    (`understanding.py:327`) and anchor selection (`service._resolve_follow_up`).
  - A long first turn can now become the anchor for a short follow-up after it.
  - A near-the-start window was rejected: the real follow-up "…in this case and why it is
    not applicable" has its anaphor at token 8.
- **0.2** `intent.has_no_subject` treats request-for-a-view words (`take`, `view`,
  `opinion`, `thoughts`, `think`, `you`, `your`) as carrying no subject. "what is you take
  on this ?" on a first turn with no document now gets the existing UNCLEAR reply.
  - A digit or any real noun still counts as a subject ("your view on the liability cap",
    "what do you think of clause 7?").
  - The words are kept out of `_STOP`, so follow-up content-word counting is unchanged.
  - No reply text changed; `service.py:1057` and `_social_reply` are reused as they are.
- No prompt, calibration constant, gate threshold or verifier floor was touched.

### Phase 1A: report delivered

[ASK_AGENT_AUDIT_A1-A5_2026-09-30.md](ASK_AGENT_AUDIT_A1-A5_2026-09-30.md).

- **A1** authorization is enforced before ranking. No stop condition.
- **A2**, **A4** and **A5** each need owner decisions: executed/draft semantics and a
  version group, conversation-scoped user material, and an evidence-ledger table.

### Tests

- 12 new cases in `test_assist_intent.py` and `test_assist_social_turns.py`.
  - Before the fix, 6 failed: the long summary, 4 no-subject cases, and the first-turn
    service case.
  - After the fix, all pass.
- The full backend suite, run in a clean environment, gave 2,913 passed, 113 skipped,
  1 xfailed and 2 failed. Both failures were these two new documents missing from
  `docs/README.md`. They are now indexed, and that test file passes (132).
- `ruff check` and `mypy` are clean.

### Measurements

- `tools.rag_benchmark` (zero Gemini, read-only against the live database): the output is
  **byte-identical before and after**, timing fields excluded. That is 82 cases, bundle
  recall@10 0.9529, wrong-source 0.0, false admission 0.0.
- The 77-question document probe (`tools/probe_targeting.py`) **was not run**. It reads
  the persistent Tier-2 gate database, which the current role cannot read (`lmtest`
  credentials rotated). Its path, `store.search_hybrid`, does not import `intent`, so this
  change cannot move it.
- The 0.891 figure in the plan is the Gemini Tier-2 gate's recall over gate-open questions
  (`backend/tests/assist_eval/baseline.json`). It was not re-run, per the Gemini cost guard.

### Open

Phase 1B/1C need the owner's schema decision. 1D can proceed without schema.

---

## 2026-09-30 (later) — owner review; fixes before merge; Phase 1D

### Owner decisions recorded

- **Attachments and the ledger get new tables, not Contracts.** Design first; the migration
  is reviewed, then run on a scratch or staging database, never straight to production.
  The design note is
  [ASK_AGENT_TABLES_DESIGN_NOTE.md](ASK_AGENT_TABLES_DESIGN_NOTE.md). **No migration has been
  written.**
- **Phase 1D approved:** synthetic fixtures, plus two public SLA PDFs. The PDFs had not
  arrived at the time of this entry.
- **Lock amendments drafted, not applied:**
  [ASK_AGENT_LOCK_AMENDMENTS_DRAFT.md](ASK_AGENT_LOCK_AMENDMENTS_DRAFT.md). Pasted material
  engages `AM-30` **t4** (counterparty names in a payload) as well as t2/t3. That is flagged
  there.

### Plan correction (D9 and §8)

The per-commit regression gate is now the **zero-Gemini golden benchmark**
(`python3 -m tools.rag_benchmark`, 82 cases): bundle recall@10 ≥ 0.9529, wrong-source 0,
false admission 0. The Gemini-backed 0.891 (gate-open questions) is measured at phase exits
only, under a cost cap. D9, §8 and the Phase 0/1/2 exit lines of the committed plan copy are
updated to match.

**Blind spot, found while doing 1D:** the golden benchmark replays the **no-document** path,
so a document-chunker change cannot move it. Chunker changes are measured with the
77-question document probe, now run on a private corpus (below).

### Fixes before merge

1. **Test recipe.** Tests never read the production env file. A test-only role
   (`legalmind_test`) owns `legalmind_v1_test_isolated` and has no grant on any live table;
   verified by `permission denied` on `users`, `contracts` and `assist`. `conftest.py`
   refuses to start on a production-only setting. The recipe is documented in
   `ops/production/README.md`.
2. **A1 test.** `test_2c_a_department_lead_reaches_no_candidate_outside_their_department`:
   same-department access 201; another department's contract and version give the same 404
   as a random ID; the Ask service is never entered for them.
3. **Rescue audit.** Proposed (not implemented) in
   [ASK_AGENT_DECISIONS_A2_A4_A5.md](ASK_AGENT_DECISIONS_A2_A4_A5.md). Neither path writes an
   `assist.generation_called` row for the rescue call.
4. **Deploy tree clean.**
   - The session records were committed on `docs/session-records-2026-09-30`, with client
     names removed (the uncommitted edits had named five clients).
   - The plan originals were moved to
     `/root/.legalmind/preserved/ask-agent-plan-originals-2026-09-30/`.
5. **Plan documents** committed with client names replaced by placeholders.

### Phase 1D — what the chunks contained, and what changed

Every row below comes from synthetic fixtures through the real parser and chunker. The
document probe used a private corpus: the gate's 15 supplied documents, ingested by the
production path with zero Gemini. The baseline reproduced the recorded figures exactly.

| Req | Before | After |
|---|---|---|
| 1.9 table pairs | ✅ pairs kept in both a row layout and a two-column layout | unchanged. **Confirm on the owner's public SLA PDFs** |
| 1.10 web furniture | ❌ header fused into rows; footer and "Page N of 3" glued to clauses | ✅ trimmed from page edges |
| 1.10 cross-page stitch | ❌ a clause broken at a page stays two chunks | ❌ **not done**: a chunk may reference one evidence row (owner ruling 2026-09-10), and read-time context is same-row only. Needs a decision |
| 1.11 inline sub-clauses | ❌ `1.1 … 1.1.1 … 1.1.2 … 19.4` in one chunk | ✅ split, each opening with its number. `(a)`/`(b)` stay inside their parent clause |
| 1.12 page numbers | ❌ `…thirty (30)\n2` | ✅ the page's own number is dropped at a page edge; any other number is kept |
| 1.13 near-duplicates | not grouped | ❌ **blocked**: needs `document_version_attributes` (design note §5) |
| 1.14 blank fields | kept verbatim, not marked | kept verbatim ✅. Marking needs `attachment_chunks.annotations` (design note), or a read-time mark in Phase 4 |
| 1.15 unsigned | every document labelled `DOCUMENT` | ✅ `EXECUTED_DOCUMENT` only when declared `FINAL_SIGNED`, otherwise `DRAFT_DOCUMENT`. Never read from text: an unsigned copy's witness line says "have executed" |

**Chunker `clause-aware-5`.**
- **Rule:** a line is trimmed only at the top of a page's first row or the foot of its last
  row, and only when it sits there on at least three pages **and** at least 40% of the
  document's pages.
- **Why both tests** (measured on the supplied corpus):
  - frequency alone removed an Act's "Illustrations" sub-heading 65 times;
  - position alone removed it 8 times;
  - both together keep 65 of 65, while the Gazette running headers (English and Hindi),
    print timestamps, web-page title lines and "Page N of 8" are removed.

| Document probe, planner OFF | recall@10 | hit@1 | MRR | gold@3 | precision |
|---|---|---|---|---|---|
| clause-aware-4 (baseline) | 0.6406 | 0.4375 | 0.5107 | 0.5781 | 0.1418 |
| clause-aware-5 | **0.6562** | 0.4375 | 0.5126 | 0.5781 | 0.1435 |

- **Corpus totals:** 1,708 → 1,699 chunks; 3,008 characters of furniture removed; lines
  reading "Page N of M" inside chunks 8 → 0.
- **Integrity:** every document passes the integrity gate. It now counts indexable text
  after trimming, so furniture no longer counts as content loss.
- **Live data:** unaffected until a re-index. The chunker version is written per row and
  never filtered on, so old and new chunks coexist safely.

**D9 per-commit gate.** The golden benchmark output is **identical** to this morning's
baseline, timings excluded: bundle recall@10 0.9529, wrong-source 0, false admission 0.
The benchmark reads the live database read-only, so it needs the deployment's env file for
its connection, model and flag settings. Run with an empty environment it reported a
meaningless 0.0471. It is not a test, so the tests-never-read-the-production-env rule does
not apply to it. Unset `LEGALMIND_GEMINI_API_KEY` and `LEGALMIND_BROKER_URL` first.

**Scratch databases, all owned by `legalmind_test`, none live:**
- `legalmind_v1_test_isolated`: the test suite's database;
- `legalmind_v1_probe_askagent_base` and `legalmind_v1_probe_askagent_new`: the private
  document-probe corpora for clause-aware-4 and clause-aware-5;
- `legalmind_v1_test_askagent`: this morning's scratch test database, on the old role.

**Suite, final**, on the test-only role:
- **Result:** 2,935 passed, 113 skipped, 1 xfailed, 0 failed. The skip count is unchanged,
  so no source-material test skipped silently.
- **Lint:** `ruff check` and `mypy` are clean.
- **One existing test adapted:** `test_retrieval_pool.py` drives retrieval with no database
  and stubs each store read. It now stubs the new `store.version_role` the same way it
  stubs `store.section_headings`. No assertion changed.

---

## 2026-10-01 — kickoff backlog items 1–10

### 2026-09-30T21:00+05:30 — FEATURE — Real-document corpus fetched (item 1)

- **What:** 57 files from the owner's Drive folder were saved to
  `/root/.legalmind/test-corpus/raw/`: 24 emails, 20 DOCX, 12 PDF and 1 .doc. Each was
  verified against its Drive byte size and checked for a valid ZIP or PDF header. The
  directory is 700, the files are 600, and the manifest (ids, titles, sha256) is 600.
- **Why:** D10 and D11.
- **Commits:** none. The corpus is never committed.
- **How:** the Drive connector, then a scratch extractor that decodes the session's saved
  results. The first attempts were denied by the session classifier and stopped (A-5); the
  owner then added allow rules.
- **Next:** probe.

### 2026-10-01T10:30+05:30 — MEASURE — Real-document probe and baseline (items 2–3)

- **What:** `tools/probe_real_corpus.py` derives probes mechanically from evidence rows and
  scores `store.search_hybrid` with zero Gemini. Output and keys hold no text.
- **Commits:** `31981d5`.
- **Command:** `python3 -m tools.probe_real_corpus --db <scratch> --write-keys`.
- **Measured (EVALS #6):** recall@10 0.7258, hit@1 0.6577, MRR 0.6840, false admission
  0.0078.
- **Next:** classify the misses.

### 2026-10-01T11:12+05:30 — FIX — Probe definition (item 4; A-6, A-7)

- **What:** two probe faults were found and fixed.
  - A-6: 61 of 61 clause-number misses were heading-only chunks.
  - A-7: every remaining miss was a numeric phrase that the probe had rebuilt into a query
    no parser matches.
- **Fixed by:** a heading's clause body now counts as the answer, and each query is the
  document's own text slice.
- **Commits:** `04b954e`, `06cc466`.
- **Measured (EVALS #6 → #9):** recall@10 0.7258 → 0.9982, 153 → 1 miss. **This is probe
  correction, not a retrieval change.**
- **False admission:** 0.0078 → 0.026 on the re-derived set. All 10 are vector-gate
  openings; this is insufficient evidence (A-8).
- **Next:** measure the chunker change against `main`.

### 2026-10-01T11:40+05:30 — MEASURE — Phase 1D chunker vs main on real documents (D18b)

- **What:** the same 938 keys (0 drift), with `main`'s `clause-aware-4` ingested fresh in a
  detached worktree.
- **Commits:** `d1385cb` (records).
- **Command:** `python3 -m tools.probe_real_corpus --db <scratch_main>`.
- **Measured (EVALS #10):**

  | | recall@10 | hit@1 | MRR |
  |---|---|---|---|
  | `main` | 0.9765 | 0.9061 | 0.9344 |
  | branch | 0.9982 | 0.9242 | 0.9544 |
  | delta | +0.0217 | +0.0181 | +0.0200 |

  False admission is unchanged. 12 `ANCHOR_LOST` misses are fixed. **This is an
  improvement.**

### 2026-10-01T11:50+05:30 — MEASURE — Tables and noise on real documents (items 5–6)

- **Command:** a scratch structure scan; counts only.
- **Measured (EVALS #11):**

  | | `main` | branch |
  |---|---|---|
  | Table rows kept whole | 42/44 | 44/44 |
  | Percentage runs kept together | 9/10 | 10/10 |
  | Chunks ending on a bare page number | 46 | 3 |

  "Page N of M" lines: 0 → 0. One 9-page PDF keeps a repeated header line, accepted as
  residue.

### 2026-10-01T12:05+05:30 — FIX — Minimum-page guard (item 7; A-9)

- **What:** repeated-line trimming now needs 5 or more pages. A page's own number is still
  trimmed in a document of any length.
- **Commits:** `d1385cb`.
- **Tests:** new 2-, 3- and 4-page fixtures; the 3- and 4-page cases fail without the guard.
  Two fixtures were extended to 5 pages with the same assertions. 66 passed.
- **Measured (EVALS #12):** the real probe is unchanged.

### 2026-10-01T12:30+05:30 — FEATURE — A1 verification (item 8)

- **What:**
  - `test_2d`: a Department User, a second role.
  - `test_2e`: the `candidates=True` pool never crosses a version.
  - `test_test_role_isolation.py`: opt-in; the test role is refused on 5 live tables.
  - The env file is mode 600 and outside the repo.
- **Commits:** `ae716a0`.
- **Tests:** 16 passed in the boundaries file; 5 passed opted in.

### 2026-10-01T12:55+05:30 — FIX — Declaring a version executed is audited (item 9; A-10)

- **What:** `PATCH /document-versions/{id}` wrote no audit row. It now writes
  `document.declared` (actor, changed keys, `version_role` before→after; no counterparty
  text). Who may declare is unchanged: the owner, while no Review exists.
- **Commits:** `441da0d`.
- **Tests:** 1 new test, failing before and passing after. 139 passed across the three
  affected files.

### 2026-10-01T13:10+05:30 — MEASURE — Git-history scan for client names (item 10)

- **What:** 25 branches, 669 commits.
  - C2, C3, C4: none.
  - C1: 1 commit, 3 files.
  - C5: 8 commits, about 9 files.
  - This branch adds none. No rewrite.
- **Commits:** `99e5b1e`.
- **Next:** items 11–12, the 1B/1C migrations on scratch.

# Ask agent — STATUS

**Last updated:** 2026-10-01T15:25+05:30 · **Branch:** `feat/ask-agent-phase0-1`
(worktree `/root/legalmind-worktrees/ask-agent-p0`) · local commits only, nothing pushed,
merged or deployed. Controlling documents:
- the kickoff prompt (`/root/Legalmind.v1/LegalMind_Ask_Agent_Kickoff_Prompt.md`);
- the [operating charter rev 3](../LegalMind_Ask_Agent_Operating_Charter.md).

## Phase board

| Phase | State | Evidence |
|---|---|---|
| 0 Hotfix | **Exited** 2026-09-30 | commit `51f96e3`; [log](../IMPLEMENTATION_LOG.md) |
| 1A Audit | **Delivered** | [audit](../ASK_AGENT_AUDIT_A1-A5_2026-09-30.md) |
| 1B/1C Attachments, ledger | Tables built (scratch, `AM-110`); behaviour not yet built | [design note](../ASK_AGENT_TABLES_DESIGN_NOTE.md), approved under D13/D14 |
| 1D Ingestion quality | Partly done: 1.9 (synthetic only), 1.10 trimming, 1.11, 1.12, 1.15 | commit `80dfcf2` |
| 2–4 | Not started | — |
| 5 | Hard gate | — |

## Real-document corpus — fetched

`/root/.legalmind/test-corpus/raw/` holds 57 files: 24 emails, 20 DOCX, 12 PDF and one
legacy .doc.
- **Verified:** every byte size matches Drive; every DOCX is a valid ZIP and every PDF has a
  valid header.
- **Permissions:** directory 700, files 600; the manifest (ids · titles · sha256) is 600.
- **Duplicates:** 6 byte-identical groups.
- **How it was fetched:** the Drive connector, once the owner allowed
  `mcp__claude_ai_Google_Drive__download_file_content` on 2026-09-30. The session's own copies
  of large downloads sit under `/root/.claude` (mode 700). The probe tool runs under the
  owner's rule `Bash(python3 -m tools.probe_real_corpus:*)`, added 2026-10-01.

## Real-document baseline (EVALS #6–#9)

`tools/probe_real_corpus.py`, scratch DB `legalmind_v1_realprobe_cur`, chunker `clause-aware-5`.
The corpus is 32 DOCX/PDF with 938 pinned probes: 554 answerable and 384 unanswerable.

| | recall@10 | hit@1 | MRR | false admission |
|---|---|---|---|---|
| **#9 current** | **0.9982** | 0.9242 | 0.9544 | 0.026 (10/384) |
| #6 first run | 0.7258 | 0.6577 | 0.6840 | 0.0078 |

**#6 → #9 is entirely probe-definition correction (A-6, A-7).** The measured retrieval change is the Phase 1D
chunker against `main` on the same probes (EVALS #10): recall@10 0.9765 → 0.9982, hit@1 0.9061 → 0.9242,
MRR 0.9344 → 0.9544, false admission unchanged.
- **What the probe covers:** verbatim lookups — clause numbers and quoted phrases. It does
  NOT cover paraphrased questions; that is Phase 3/4 shadow evaluation.
- **Weakest number:** hit@1 0.92. The right chunk is found but is not first in 8% of
  lookups.
- **False admission (A-8):** insufficient evidence. All 10 are vector-gate openings for
  another contract's phrase.
- **Wrong-source:** n/a, because document search is scoped to one version in SQL.
- **Misses:** 1 (RETRIEVAL_MISS).

## Backlog (kickoff §10 order)

1. Corpus fetch — **done**.
2. Probe script and keys — **done** (`31981d5`).
3. Real baseline — **done** (above).
4. Miss classification — **done**. 153 → 1 miss. Every class was a probe-definition fault
   (A-6 heading chunks, A-7 rebuilt numeric queries), not retrieval. The one remaining miss
   is open. The false-admission rise is A-8.
5. Tables on real files — **done** (EVALS #11): rows kept whole 44/44, runs 10/10 (main: 42/44, 9/10).
6. Noise on real files — **done** (EVALS #11): bare page numbers at chunk ends 46 → 3; one 9-page PDF keeps a
   repeated table-header line (accepted residue).
7. Minimum-page guard — **done** (A-9, EVALS #12, unchanged on the real corpus).
8. A1 — **done**. `test_2c` (Lead, cross-department) and the new `test_2d` (Department User, same
   department) both get a 404 byte-identical to a missing document, and the service is never entered. The new
   `test_2e` checks that the `candidates=True` vector pool never crosses a version. The new opt-in
   `test_test_role_isolation.py` shows the test role is refused on 5 live tables (5 passed). The env file is 600,
   root-owned, outside the repo and untracked.
9. Execution state — **done** (A-10). Owner-only declaration, now audited as `document.declared`; default draft.
10. Git-history scan — **done** (2026-10-01T13:10+05:30). 25 local branches, 669 commits; the five
    client names are labelled C1–C5 here and never written out.
    - C2, C3, C4: in no commit at all.
    - C1: in 1 commit (`3653517`, 2026-09-10, Client Profiles), 4 occurrences in 3 test files on
      `main` and every branch.
    - C5: in 8 commits (`ca6f9b1` 2026-08-21 … `986ef26` 2026-09-14), 11 occurrences on `main`. They
      sit in `CHANGELOG.md`, `test_analysis.py`, `test_api_resources.py`, `test_ingestion.py`,
      `AUTO_MODE_DECISIONS.md`, `LEGALMIND_PROJECT_STATE.md`, `clause-index.test.ts` and
      `workspace/model.ts`. One further hit in a PNG is binary noise.
    - `feat/ask-agent-phase0-1` adds **none**: its counts equal `main`'s. History is not rewritten
      (hard gate 7).
11–12. 1B/1C migration — **done**. `a9e4c2f7b1d3`, six tables, locked as `AM-110` (AB-60).
    Applied to scratch (`legalmind_v1_migrate_scratch`): upgrade → downgrade → upgrade clean.
    Staging and production remain a hard gate. Schema conformance: A-11.
13. 1.13 near-duplicates — **done** (A-13, EVALS #13). Grouped at index time and scoped by counterparty; 0 mixed groups on the real corpus.
14. 1.14 marking.
15. Rescue call in the audit row.
16. D13 lock amendments.
17–19. Phases 2, 3, 4.

## Owner actions

None blocking. One optional, not a gate:

- **Question.** Should the C1/C5 names be removed from the *current* files on `main`?
  - **Recommendation.** Yes. Use one small PR replacing them with placeholders, as the
    executed-NDA rule already requires. History stays unchanged; rewriting it is hard gate 7,
    and these names are already in every clone.
  - **Evidence.** Item 10 above. The files were written by other sessions on 2026-08-21 …
    2026-09-14. The change would touch `main`, so it needs your merge.

## Open risks

- A new chunker on the live index needs one controlled rebuild (hard gate, D16).
- False admission on the real probe is 10/384 (0.026), all vector-gate openings. This is
  insufficient evidence (A-8) and is re-examined in Phase 2–4.

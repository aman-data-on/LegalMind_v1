# Ask agent — STATUS

**Last updated:** 2026-10-01T10:40+05:30 · **Branch:** `feat/ask-agent-phase0-1`
(worktree `/root/legalmind-worktrees/ask-agent-p0`) · local commits only, nothing pushed,
merged or deployed. Controlling documents:
- the kickoff prompt (`/root/Legalmind.v1/LegalMind_Ask_Agent_Kickoff_Prompt.md`);
- the [operating charter rev 3](../LegalMind_Ask_Agent_Operating_Charter.md).

## Phase board

| Phase | State | Evidence |
|---|---|---|
| 0 Hotfix | **Exited** 2026-09-30 | commit `51f96e3`; [log](../IMPLEMENTATION_LOG.md) |
| 1A Audit | **Delivered** | [audit](../ASK_AGENT_AUDIT_A1-A5_2026-09-30.md) |
| 1B/1C Attachments, ledger | Designed, **not built** | [design note](../ASK_AGENT_TABLES_DESIGN_NOTE.md), approved under D13/D14 |
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

## Real-document baseline (EVALS #6, #7)

`tools/probe_real_corpus.py`, scratch DB `legalmind_v1_realprobe_cur`, chunker
`clause-aware-5`. The corpus is 32 DOCX/PDF with 942 pinned probes: 558 answerable and 384
unanswerable.

| | recall@10 | hit@1 | MRR | false admission |
|---|---|---|---|---|
| #7 overall | 0.8853 | 0.8082 | 0.8381 | 0.0078 (3/384) |
| #7 clause numbers | 1.0000 | 0.9713 | 0.9813 | — |
| #7 exact terms | 0.8333 | 0.7344 | 0.7733 | — |

- **Wrong-source** is n/a: document search is scoped to one version in SQL.
- **#6 → #7 is a probe-definition correction (decision A-6), not a retrieval change.**
- **Misses: 64, all exact-terms.**
  - GATE_CLOSED 36: the largest class, and next to investigate.
  - RANK_CUTOFF 21.
  - RETRIEVAL_MISS 7.

## Backlog (kickoff §10 order)

1. Corpus fetch — **done**.
2. Probe script and keys — **done** (`31981d5`).
3. Real baseline — **done** (above).
4. Miss classification — **in progress**. All 64 misses are exact-terms. Fix the largest
   class (GATE_CLOSED) first.
5. Tables on real SLA and contract files.
6. Header, footer and page-marker noise on real documents.
7. Minimum-page guard for repeating headings, with 2–4 page fixtures.
8. A1: second role, search-candidate selection, env file 600, test role vs live tables.
9. Execution state: who declares "executed", audit, draft default.
10. Git-history scan for client names (no rewrite).
11–12. 1B/1C migrations, built and applied on scratch.
13. 1.13 near-duplicates.
14. 1.14 marking.
15. Rescue call in the audit row.
16. D13 lock amendments.
17–19. Phases 2, 3, 4.

## Owner actions

None.

## Open risks

- A new chunker on the live index needs one controlled rebuild (hard gate, D16).
- The unanswerable probe set has 3 false admissions. These are measured, not yet investigated.

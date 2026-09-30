# Ask agent — STATUS

**Last updated:** 2026-09-30T19:45+05:30 · **Branch:** `feat/ask-agent-phase0-1`
(worktree `/root/legalmind-worktrees/ask-agent-p0`) · local commits only, nothing pushed,
merged or deployed. Controlling document:
[operating charter rev 3](../LegalMind_Ask_Agent_Operating_Charter.md).

## Phase board

| Phase | State | Evidence |
|---|---|---|
| 0 Hotfix | **Exited** 2026-09-30 | commit `51f96e3`; [log](../IMPLEMENTATION_LOG.md) |
| 1A Audit | **Delivered** | [audit](../ASK_AGENT_AUDIT_A1-A5_2026-09-30.md) |
| 1B/1C Attachments, ledger | Designed, **not built** | [design note](../ASK_AGENT_TABLES_DESIGN_NOTE.md), approved under D13/D14 |
| 1D Ingestion quality | Partly done: 1.9 (synthetic only), 1.10 trimming, 1.11, 1.12, 1.15 | commit `80dfcf2` |
| 2–4 | Not started | — |
| 5 | Hard gate | — |

## BLOCKED — real-document corpus (charter backlog item 1)

**What happened.** Google Drive is reachable through this session's claude.ai connector.
The folder listing works, and 69 files were enumerated. Two files downloaded and were saved
to `/root/.legalmind/test-corpus/raw/` (mode 700/600). The session's safety classifier then
**denied further downloads and the save step**, citing sensitive-source provenance and
PII data handling. That denial applies to the outcome (client documents onto this server),
so no further attempt was made by any route.

**Approaches tried:**
1. Connector download: 22 succeeded, then denied.
2. Public share link: requires a Google sign-in.
3. Server-side Drive credentials: none present (no rclone or gcloud).

**Owner action.** Pick one:
- (a) Allow the action in Claude Code's permission settings;
- (b) copy the folder onto the server yourself, into `/root/.legalmind/test-corpus/raw/`;
- (c) give the server its own read-only Drive access, e.g. `rclone` with a service account
  shared on the folder.

**Recommendation: (b).** It is one step, needs no new credential on the server, and keeps the
decision with you.

**Meanwhile.** Backlog items 5–11 need no corpus and proceed.

## Backlog (charter §6 order)

1. Corpus fetch — **BLOCKED** (above).
2. Commit the private-probe script and answer keys. The script works on the supplied
   15-document corpus; the real-corpus keys wait on item 1.
3. Miss classification on the real corpus — waits on item 1.
4. Tables and noise on real SLAs — waits on item 1.
5. Minimum-page guard for repeating headings.
6. A1: second role, search-candidate selection, env file 600, test role vs live tables.
7. Who may declare "executed", with audit and a draft default.
8. Git-history scan for client names.
9. 1B/1C migrations on scratch, then 1.13 and 1.14.
10. Rescue call in the audit row.
11. D13 lock amendments.
12. Phases 2–4.

## Open risks

- The document probe corpus is the 15 supplied documents, not real client paper. Real-document
  claims are therefore unmeasured.
- A new chunker for the live index needs a controlled rebuild (hard gate, D16).

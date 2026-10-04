# Ask agent — STATUS

**Last updated:** 2026-10-04T13:47+05:30
(worktree `/root/legalmind-worktrees/ask-agent-p0`) · local commits only, nothing pushed,
merged or deployed. Controlling documents:
- the kickoff prompt (`/root/Legalmind.v1/LegalMind_Ask_Agent_Kickoff_Prompt.md`);
- the [operating charter rev 3](../LegalMind_Ask_Agent_Operating_Charter.md).

## Phase board

| Phase | State | Evidence |
|---|---|---|
| 0 Hotfix | **Exited** 2026-09-30 | commit `51f96e3`; [log](../IMPLEMENTATION_LOG.md) |
| 1A Audit | **Delivered** | [audit](../ASK_AGENT_AUDIT_A1-A5_2026-09-30.md) |
| 1B/1C Attachments, ledger | **Built** behind `LEGALMIND_ASK_ATTACHMENTS` (off): long paste, files with status, search, user-material labelling, TTL; ledger keys per answer, re-fetch `current`/`stale`/`unavailable` (A-15–A-18, `AM-114`) | [design note](../ASK_AGENT_TABLES_DESIGN_NOTE.md); `assist/attachments.py`, `assist/ledger.py` |
| 1D Ingestion quality | Done: 1.9–1.15, D15 cross-page read-time expansion (A-14, EVALS #15) | commits `80dfcf2` … D15 |
| **1 exit** | **MET** 2026-10-01, two caveats | [PHASE1_EXIT.md](PHASE1_EXIT.md) |
| **2 Tool layer** | **Accepted** by the owner (2026-10-03) | [PHASE2_EXIT.md](PHASE2_EXIT.md) |
| **3 Agent loop (shadow)** | **Accepted** by the owner (2026-10-03, with review P1–P11 carried into Phase 4) | [PHASE3_EXIT.md](PHASE3_EXIT.md); exit commit `9e7ef25` |
| **4 Verifier, ladder, floor** | **Exit report written — NOT complete.** Owner's acceptance spec *Real Conversation Tests v2* (2026-10-04, private) run on conversations 1, 3, 4, 5 (2 and 6 held out): Musts met on 7/22 turns (bar 90 %), 2 Must-not violations (C5.2, C5.4), worse than the current pipeline on 4 turns (all conversation 5), 6 items pending missing sources. G2.1, G5, G13.2 fixed and confirmed live; F12 passes; retrieval gates unchanged. **Waiting for the owner:** cross-document reach, the intended data-loss position, which document D3 is, F1–F3, English-only verified claims; and "commit" (nothing committed) | [PHASE4_EXIT.md](PHASE4_EXIT.md) (addendum); private `/root/.legalmind/review/phase4/spec_v2/` |
| 5 | Hard gate | — |

## Phase 4 plan (owner review of Phase 3, 2026-10-03; started from `e1a2840`)

**Scope.** Roadmap 4.1–4.6 (verifier V1–V8, one repair call, ladder L1–L4, deterministic floor,
renderer, adversarial set) and the owner's Phase 3 review P1–P11, each a regression case under
G1–G12 with its root cause fixed, before/after per issue, and the same 20-turn evaluation on
both paths. **New exit criterion:** on every selected-document turn the agent is no worse than
the current pipeline on four points (document primary, right clause and figures, no unsupported
authority, no dead end) — judged provisionally per turn, final call the owner's. Local only.

## Phase 3 plan (owner brief 2026-10-03; started from `e9731c9`)

**Scope.** A Gemini provider adapter (chat, tool call, structured output) on the existing
single egress seam; the agent loop (≤ 3 decision steps over the Phase 2 tools, then one
tool-free final call with the v2.1 §5.6 schema); per-turn budget enforcement (5 calls,
8 tool executions, 25 s soft / 40 s hard); a conversation manager (thread window with
prior replies labelled, deterministic rolling summary off the request path, pinned
evidence re-fetched through `get_evidence`); the system contract (Appendix A, adapted);
`ASK_AGENT_MODE = off | shadow | on` (default off; only off/shadow used); a shadow runner.
No user ever sees agent output.

**Exit criteria (brief §D).** G1–G11 run in shadow on real documents; no turn > 5 calls or
> 8 tool executions, average calls/turn reported; p50/p95 per turn and per stage; tokens
per call; no client text in committed files or traces (checked); shadow unreachable by
users (checked); comparison with the current pipeline on the same turns; owner review
sample at `/root/.legalmind/review/phase3/`; ruff, mypy, full suite clean AT the exit
commit; golden, frozen set and both probes not below Phase 2.

**Carry-forwards.** A1 generation baseline (branch 20, then `main` 77 — reported, not an
exit criterion). A2 record integrity: clock-only timestamps with a check, lint/types/suite
at the exit commit, default-mode equivalence of the gate tool. A3 probe reporting (the
earlier probe is the quality measure; the new one a tripwire; distinct-probe column). A4
retrieval quality: classify misses on the frozen set and the earlier probe, fix the
largest class that needs no calibration change, measure on every gate.

**Locks.** `AM-111` (prior replies as labelled context) and `AM-112` (labelled general
answers, no bare refusal) were already appended as AB-61 on 2026-10-01 for agent mode; no
new amendment is expected unless the build finds one.

**Test, evaluation and budget plan.** Unit tests with a scripted fake provider: budget caps,
tool-free last call, budget-exhaustion answer, prompt order, no duplicate thread or
attachment content, latest question never lost, user material only in data blocks, the
flag (`off` path byte-identical; `shadow` never returned). Then live: smallest evidence
first (one script), then G1–G11 in shadow and through the current pipeline on a scratch
copy holding the real corpus. Ceilings 1,000 calls/day, 450/run; estimated ~3 calls/turn ×
~35 turns + ~50 current-pipeline calls ≈ 160 per full run; A1 ≈ 130 more. Every run's
calls, tokens and estimated cost go to EVALS.

## Phase 2 plan (owner brief 2026-10-01; started from `ecd1814`)

**Scope.** Seven read-only tools in `backend/legalmind/assist/tools.py` — `search_knowledge`,
`get_company_position`, `search_statutes`, `get_evidence`, `list_attachments`,
`search_attachment`, `ask_user` — wrapping the existing retrieval, positions, statutes,
Constitution, ledger and attachment code. No API endpoint, no Ask wiring; tests only until
Phase 3. Production untouched.

**Exit criteria.**
1. Tool tests 100% pass: authorization (missing / malformed / nonexistent / unauthorized /
   authorized ID, cross-user, bypass through arguments and filters — identical responses),
   schema (unknown args, `k > 8`, bad filters, query length), read-only (no writes, no
   egress), `get_evidence` (current / stale / unavailable / missing / unauthorized / invalid).
2. Frozen 77-question set, hashed: branch ≥ `main` on recall@10, hit@1, MRR; ≤ on
   wrong-source and false admission (zero model calls). Both probes reported.
3. p50/p95 latency per tool in EVALS.
4. Full suite, ruff, mypy green; frontend checks green for A5.
5. Carry-forwards A1, A3, A4, A5, A6 complete. A2 reported with calls used/remaining.

**Phase 1 caveats carried forward.** Generated half: 20 unmeasured questions, and `main`'s
generation baseline (A2 — 100 calls/day; today's budget was spent by the Phase 1 exception,
so A2 starts 2026-10-02). Baseline comparability (A1). Probe interpretation (A3). The
80 → 75 denominator (A4). Attachment-status UI (A5, exception approved). Purge timer on
scratch (A6).

**Implementation, test and evidence plan.**
- A `ToolContext` built server-side (user, live permissions, owned conversation); the model
  supplies arguments only, through strict Pydantic models (`extra="forbid"`).
- Every ID argument resolves in ONE query that joins authorization; any failure is the
  same `NOT_FOUND` result. Schema violations are `INVALID_ARGUMENT`.
- Each tool runs inside a savepoint that is always rolled back; tests detect writes from
  Postgres's per-transaction counters (`pg_stat_xact_user_tables`) and trap the single
  Gemini seam.
- Ledger keys stay assigned at answer time (a tool that assigned them would write); tools
  return natural references.
- Regression: `verify_assist_quality` retrieval half, rescue off, no key, on `main` and the
  branch (same harness). Probes: `probe_targeting` (earlier, 77-question anchors) and
  `probe_real_corpus` (new). Latency on scratch `legalmind_v1_phase2`.

## Retrieval gate — required on EVERY retrieval change (owner, 2026-10-01)

Report all of these, on `main` and the branch, on the frozen **q77-v1** set
(sha256 `c06162de…f970a8b92`, pinned by `tests/test_frozen_question_set.py`):
1. `verify_assist_quality` retrieval half with **`LEGALMIND_EVIDENCE_RESCUE=off LEGALMIND_RERANK=on`**, no key (zero calls) — recall@10, hit@1, MRR, wrongly answered. The flags are part of the measurement: without rerank, hit@1 reads 0.438 instead of 0.484 (EVALS #37).
2. **Earlier probe** `tools/probe_targeting.py` — the 64 owner-ratified questions.
3. **New probe** `tools/probe_real_corpus.py` — the 938 pinned real-corpus keys.
4. Golden `tools.rag_benchmark` — wrong-source and false admission.
A measurement worktree of `main` lives at `/root/legalmind-worktrees/main-baseline` (detached, untracked harness copies only).

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

**Items 1–10 at a glance** (owner request, 2026-10-01). None blocked, none pending.

| # | Item | State | Commit(s) |
|---|---|---|---|
| 1 | Fetch real documents from Drive | done — 57 files, outside git (D11) | records `6171352`, `04b954e` (no corpus file is committed) |
| 2 | Probe script and expected-answer keys | done | `31981d5`, re-pinned `06cc466` |
| 3 | Real-document baseline | done — EVALS #6–#9 | `04b954e`, `06cc466` |
| 4 | Classify every probe miss | done — 153 → 1 (A-6, A-7) | `04b954e`, `06cc466` |
| 5 | Tables on real SLA/contract files | done — EVALS #11 | `d1385cb` |
| 6 | Web/header/footer/page-marker noise | done — EVALS #11 | `80dfcf2`, `d1385cb` |
| 7 | Minimum-page guard, 2–4 page fixtures | done — A-9, EVALS #12 | `d1385cb` |
| 8 | Verify A1 | done — tests 2c, 2d, 2e | `4115617`, `ae716a0` |
| 9 | Execution-state behaviour | done — A-10 | `441da0d` |
| 10 | Git-history scan for client names | done — branch adds none | `99e5b1e`, log `8c5c58c` |


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
14. 1.14 marking — **done** (EVALS #14). `chunking.blank_fields` marks `____`, `[●]`, `[ ]`, `[*]` and dotted leaders,
    and 144/144 real blanks are kept verbatim. Marks are stored on attachment chunks (`annotations`) once 1B ingestion
    is built, and attached to document hits in Phase 2 tool results (no column on `assist.chunks`).
15. Rescue call audited — **done**. `rescue.CALLS` collects each judge call made inside a request, and `service.ask`
    writes one `assist.generation_called` row each (prompt version, payload hash, excerpts judged, request id) on both
    paths. 2 new tests, failing before.
16. D13 lock amendments — **done**. `all_lock.md` AB-61 `AM-111`–`AM-113` (agent mode only), with registry rows and
    CLAUDE.md's count (22339 lines). Appended only; prior lines byte-identical. Plan §2's "record D1–D4" is met by `AM-112`.
D15. Cross-page clauses — **done** (A-14, EVALS #15). `store.continuation` brings the next block in as labelled
    `[continued on page N]` context and keeps its id on `Evidence.continuation`; the indexed unit stays one block. Citing
    both blocks lands with the ledger (1B/1C) and the verifier (Phase 4), which decide when an answer rests on both.
1B/1C. Attachments and ledger — **built** (A-15–A-18). Lock `AM-114` (AB-62) appended on the owner's confirmation
    2026-10-01: user material may reach Gemini on the normal path while the flag is on. UI for attachment status is not
    built (UI freeze; the API returns status).
**Phase 1 exit — MET** ([report](PHASE1_EXIT.md)): Tier-2 recall@10 0.922, wrongly answered 0/13, live G1/G4 pass, 115 calls (A-19).
17–19. Phases 2, 3, 4. **Next:** Phase 2, the tool layer.

## Owner actions

None blocking. One optional, not a gate:

- **Question.** Should the C1/C5 names be removed from the *current* files on `main`?
  - **Recommendation.** Yes. Use one small PR replacing them with placeholders, as the
    executed-NDA rule already requires. History stays unchanged; rewriting it is hard gate 7,
    and these names are already in every clone.
  - **Evidence.** Item 10 above. The files were written by other sessions on 2026-08-21 …
    2026-09-14. The change would touch `main`, so it needs your merge.

## Pre-Phase-5 items (owner decides before Phase 5)

- **Attachment-status display in the UI.** The UI is frozen. The API returns each attachment's status
  (`PROCESSING`/`READY`/`FAILED` with a code/`UNAVAILABLE`) and the long-paste reply says the text was saved; the screen
  does not yet show it. The owner decides the UI exception before Phase 5 (owner, 2026-10-01).
- **Retention timer install.** `ops/production/legalmind-attachment-purge.{service,timer}` (daily) are written, not
  installed; the purge also runs on every new attachment. Install with the flag turn-on (a production change).

## Open risks

- A new chunker on the live index needs one controlled rebuild (hard gate, D16).
- False admission on the real probe is 10/384 (0.026), all vector-gate openings. This is
  insufficient evidence (A-8) and is re-examined in Phase 2–4.

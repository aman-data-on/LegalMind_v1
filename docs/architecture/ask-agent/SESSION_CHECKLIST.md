# Ask agent — session checklist

The end-of-session ritual. A box is ticked only with its evidence beside it; one that
cannot be ticked carries an **Exception** note. Current state: [STATUS.md](STATUS.md). The
session's narrative: [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

---

## Session 2026-10-07-LD — latency diagnosis (diagnosis only)

### Before measuring
- [x] Prior records read first: RG handoff, STATUS, EVALS, the live DF branch's handoff and raw per-stage files, 176 captures, 31 run files, scratch answer rows, the production log — evidence: SESSION_HANDOFF.md § Latency diagnosis §1 (P1–P16, each with its source)
- [x] Own worktree and branch from `origin/main` `0aee166`, after `git worktree list`; the live DF session's API (`:8378`) and capture folder left untouched — evidence: `rag/latency-diagnosis-20261007` in `/root/legalmind-worktrees/latency-diagnosis`
- [x] Scratch database only; every profiled turn rolled back; no provider key in the profiler's environment — evidence: `/root/.legalmind/latency/env.sh` (refuses another DB, unsets the keys); `profile_turn.py` asserts there is no key

### Measurement
- [x] Phase A on all three paths: Gemini and DeepSeek read the document whole, Bonsai runs lean — evidence: §2 Phase A; `profile_full2.log` and `profile_full3.log`, memo cleared each rep
- [x] Phase B on all three models: first token, generation, cached and reasoning tokens, cold vs warm — evidence: §2 Phase B; `raw_calls.jsonl`, 16 calls, all HTTP 200
- [x] Phase C on all three: verify (live reused + replay), sources, persist, UI paint — evidence: §2 Phase C; `profile_service.py` and `ui_paint.mjs` outputs
- [x] E1–E10 each run, reused, or marked NOT RUN with its reason — evidence: §3 (E2 by arithmetic only)
- [x] Layer attribution, bottleneck per model, the 23-lever reducibility table, the ranked fix list — evidence: §4–§7
- [x] Every metric not measured is named with its reason — evidence: §8
- **Exception:** completion is (b) partial. The gaps are listed in §8 and in the completion line.

### Discipline
- [x] No fix implemented: no prompt, retrieval, model, chunking, cache, streaming or UI change, and no code committed — evidence: `git diff origin/main --stat` on the branch lists three records files
- [x] Gemini cost guard: the zero-model profiler and capture mining came first; live calls were made only for metrics the app does not expose; call count and tokens are reported — evidence: §10 (Gemini: 6 calls, 181,730 prompt tokens)
- [x] No client text in any committed file; the profiler's private logs are mode 600 in a mode-700 folder — evidence: `/root/.legalmind/latency/`
- [x] Local commit only, records staged by path; no push, merge or deploy — evidence: `git log origin/main..HEAD`

### Follow-up (owner: "ok go ahead", "ok go")
- [x] Fix #1 merged through the gate — evidence: PR #148 → `08564b3`; CI 17/18 (job 14 = the pre-existing `npm audit`); the ruleset requires only job 3, which passed; 0 behind; no `--admin`
- [x] Deployed and verified — evidence: `sudo legalmind-deploy` → `08564b3`; no migration; api/worker/frontend active; 0 API errors since 23:10:58 IST; build `YW163Q2NH1oMCu0Cs6Woi` contains the new paste wording
- [x] Attachment purge timer installed, as AM-121's deploy step requires — evidence: `systemctl list-timers` shows the next run at 03:30 IST; a manual run printed "purged 0 expired attachment(s)", Result=success

---

## Session 2026-10-07-DF — six known defects (D1–D6)

### Before code
- [x] STATUS.md and SESSION_HANDOFF.md read first; fix order written before code — evidence: SESSION_HANDOFF.md § Fix order (written before any code)
- [x] Own worktree and branch from `origin/main` `0aee166` — evidence: `rag/defect-fixes-20261007` in `/root/legalmind-worktrees/defect-fixes`
- [x] Scratch databases only — evidence: `legalmind_rag_ground` (API, `env.sh` refuses any other name), `legalmind_rag_ground_e2e` (Playwright); in-process measurements rolled back
- [x] UI skills applied to the composer/data-path change (loaded this session; no new visual design) — evidence: session transcript

### The six defects
- [x] D1 — every asked point answered or named, with the count — evidence: live 17/17 Gemini and DeepSeek (before: 4 and 6); final-code recheck 16/17 + point 6 named; `test_assist_points.py`
- [x] D2 — the floor says why; grounded sentences no longer cut — evidence: `test_settle_keeps_the_standard_a_differing_clause_is_compared_with` and `test_the_floor_says_why_never_only_that_it_could_not` (fail on old code); Bonsai T6 floor → full answer; "(D4)" keys and "Annexure-2" false rejections fixed with failing-first tests
- [x] D3 — a 5,000-character paste is the chat's material — evidence: 5,590-character message → 201, PASTE READY 5,542 bytes, answered from its clause 13.1; `test_attachments_are_on_unless_switched_off`; e2e "a long paste is kept whole" — **Exception:** the live (production) check needs a deploy, the owner's step
- [x] D4 — a clause named on page 22 of the 28-page agreement is found and cited — evidence: sweep numbers 53/81 → 81/81, headings 25/57 → 53/57; Bonsai live: 24.9 cited (54.9 s), "Enforcement and Penalties" (p. 22) cited first (65.2 s); `test_d4_*` (fails on old code)
- [x] D5 — TTFT and total measured before and after on all three models — evidence: SESSION_HANDOFF.md § D5 table; DeepSeek's done step 7.6–11.2 s → 2.6–3.6 s, parallel searches 5.5 s → 2.8 s; `test_a_decision_writing_prose_is_stopped…`, `test_one_steps_searches_run_in_parallel…` — **Exception:** token streaming to readers not done (blocker 1)
- [x] D6 — "does clause 17.2 of A conflict with clause 13 of B?" cites both by name — evidence: Gemini 26.3 s, DeepSeek 41.5 s, Bonsai 82.8 s, Sources `your file "TOS-leapswitch.pdf"`; `test_d6_*`, `test_d4_each_named_number…`; e2e "A second document joins the same chat as named material (D6)"
- [x] Blockers logged under "Blockers — needs human decision" — evidence: SESSION_HANDOFF.md (streaming to readers; Bonsai on long lists)

### Regression baseline
- [x] Agreement read, clause named, standard compared, sources per sentence — evidence: SESSION_HANDOFF.md § Regression baseline (T4–T6, three models) — **Exception:** no statute cited in these runs; pre-existing (the same search on `main` returns the same s. 74 fragment), logged
- [x] T4/T5/T6 answered on Gemini, DeepSeek and Bonsai — evidence: `runs/df-final-*.json` (private)
- [x] Footer shows model + time; Sources carry the record's text — evidence: 9 of 9 answers via `GET /conversations/{id}`; `test_an_agent_answer_names_its_model_time_and_sources_live_and_on_reload`
- [x] Ungrounded sentences removed, not guessed — evidence: verifier suite; D4 replay shows V4-failing statements dropped
- [x] "my agreement" with none attached asks for it — evidence: T3 on all three models, 0 model calls

### Tests
- [x] Backend, the whole suite as CI job 13 runs it (no keys, no local models): 3,229 passed, 167 skipped, 1 xfailed, 0 failed — evidence: pytest output on the final code, 2026-10-07 (3,216 at the last merge)
- [x] `tests/assist` under CI conditions: 1,660 passed, 32 skipped — evidence: pytest output after D6
- [x] ruff and mypy — evidence: "All checks passed!", "no issues found in 148 source files"
- [x] Frontend typecheck + forbidden terms (`npm run lint`), Vitest 560/560 — evidence: npm output, 2026-10-07
- [x] Playwright, Ask specs (5 files): 34/34 against `next dev` and the private e2e DB — evidence: output, 2026-10-07; `next dev`'s edits to `tsconfig.json`/`next-env.d.ts` reverted
- [x] CI guards 6–8 run locally — evidence: `all_lock.md` 82 added / 0 removed, prefix byte-identical to `origin/main`; no corpus file changed; no contract file types added
- [x] No `next build`, no deploy, no visual-baseline update — evidence: commands in this session's transcript

### Records and git
- [x] `AM-121` (AB-69) appended; LOCKED_DECISIONS row; CHANGELOG entry — evidence: `c6812a6`
- [x] STATUS.md and SESSION_HANDOFF.md updated after each fix — evidence: the D1–D6 commits each carry their record
- [x] No new .md file — evidence: `git diff --diff-filter=A --name-only origin/main` lists no .md
- [x] Local commits only, staged by path; no push, merge or deploy — evidence: `git log origin/main..HEAD`

## Session 2026-10-07-RG — grounding and behaviour

### Before code
- [x] CLAUDE.md, DESIGN.md and the status records read; UI skills loaded (`ui-ux-pro-max`, `frontend-design`) — evidence: session transcript, before the first edit
- [x] Plan written to SESSION_HANDOFF.md before any code — evidence: SESSION_HANDOFF.md § Plan
- [x] Own worktree and branch, `git worktree list` checked — evidence: `rag/grounding-and-behavior-20261007` in `/root/legalmind-worktrees/rag-ground`
- [x] Scratch databases only — evidence: `legalmind_rag_ground` (API), `legalmind_rag_ground_e2e` (Playwright); `env.sh` refuses any other DB name

### Grounding and behaviour
- [x] P0 fixed: no confident legal answer without Attachment, Pasted-Text or Evidence Context — evidence: T3 in a fresh chat on Gemini, DeepSeek and Bonsai, fixed reply with 0 calls; `test_assist_short_inputs.py`
- [x] Behaviour A ("hi", "thanks", "how can you help me?") — evidence: T9–T12 live, 0 calls; the brief is ≤ 320 characters (`test_assist_capability_route.py`)
- [x] Behaviour B (one clarifying question) — evidence: T13 live; `test_a_vague_intent_gets_one_clarifying_question…`
- [x] Behaviour C (bare paste → acknowledgement + offer) — evidence: T8 live (attachments on), `test_a_bare_paste_is_acknowledged_with_no_model_call` (attachments off)
- [x] Behaviour D (agreement + standard cited; missing grounding said) — evidence: T4–T6 on Gemini and DeepSeek cite the clause and the standard; T3 says what is missing
- [x] Behaviour E (consistency) — evidence: T9 and T12 return identical text on all three models
- [x] Behaviour F (proactive ≤ 20 %) — evidence: 2 of 13 changes, SESSION_HANDOFF.md § Proactive fixes
- [x] Owner's loop rules 1–7 — evidence: `_should_stop` `agent.py:906`, `MAX_DECISIONS` 6, the 3-line record in SESSION_HANDOFF.md

### Multi-model test
- [x] One e-mail and one counterparty document, from the private corpus — evidence: Drive ids in SESSION_HANDOFF.md, files mode 600 under `/root/.legalmind/test-corpus/raw/`
- [x] The same questions to every model, one chat each, re-checked in the same chat — evidence: `runs/*-before.json`, `*-after*.json` (private), conversation ids in SESSION_HANDOFF.md
- [x] Scored 1–5 on grounding, brevity, accuracy, tone and failure honesty — evidence: SESSION_HANDOFF.md § Behavioural test results
- [x] Bonsai answers through the agent — evidence: round 3, live T4 70 s, T5 74 s, T6 78 s with real answers (lean profile, streamed); it had returned 520 on the full context
- [x] Answer shows its model and time; Sources open to their record — evidence: real browser (DeepSeek, Bonsai), `test_an_agent_answer_names_its_model_time_and_sources_live_and_on_reload`, vitest
- [x] Qwen — removed from the model list on the owner's word that IndieRouter withdrew it (`AM-120`); evidence: "qwen" is refused as unknown, `test_an_adapter_serves_only_with_its_key_and_url_on_the_agent_path`
- [x] Independent review of round 3 — evidence: 8 findings, 7 fixed with tests, 1 logged (Next session)

### Tests
- [x] Backend: `tests/assist` + source material: 1,673 passed, 4 skipped; after the last commit, verification + agent 344 passed — evidence: pytest output, 2026-10-07
- [x] ruff and mypy — evidence: "All checks passed!", "no issues found in 147 source files"
- [x] Frontend typecheck + forbidden terms (`npm run lint`) and vitest 557/557 — evidence: npm output, 2026-10-07
- [x] Playwright, Ask specs (5 files) — evidence: 32/34 → two defects fixed (`af3a586`) → 33/33 plus the workspace spec 11/11, against `next dev` (no `next build`) and a private e2e DB
- [x] No `next build`, no deploy, no visual-baseline update — evidence: commands run are listed in this session's transcript

### Records and git
- [x] `all_lock.md` appended only (22,542 → 22,673 lines; the prefix is byte-identical at each append) — evidence: `cmp` against the pre-append copy
- [x] LOCKED_DECISIONS rows for `AM-117` and `AM-118` — evidence: `docs/00-project/LOCKED_DECISIONS.md`
- [x] STATUS.md, SESSION_HANDOFF.md and this file updated; the three CLAUDE.md records updated — evidence: the records commit
- [x] Local commits only, staged by path; no push, merge, rebase, tag or deploy — evidence: `git log fix/ask-chat-micro..HEAD`
- [x] SESSION_HANDOFF.md "Next session — pick up here" holds only genuine leftovers — evidence: re-read at session end

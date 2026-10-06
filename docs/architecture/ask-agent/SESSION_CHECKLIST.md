# Ask agent — session checklist

The end-of-session ritual. A box is ticked only with its evidence beside it; one that
cannot be ticked carries an **Exception** note. Current state: [STATUS.md](STATUS.md). The
session's narrative: [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

---

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
- [ ] Bonsai answers through the agent — **Exception:** the endpoint returns 520 on the agent's ~45k-token context (a gateway limit at about 50 s); small prompts work. Logged under Blockers; external.

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

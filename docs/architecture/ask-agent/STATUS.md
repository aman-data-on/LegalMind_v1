# Ask agent — STATUS

**Last updated:** 2026-10-07 23:10 IST (`AM-121` merged as `08564b3` and deployed); before that 2026-10-07 evening (branch `rag/defect-fixes-20261007`, worktree
`/root/legalmind-worktrees/defect-fixes`); earlier 2026-10-07 (branch
`rag/grounding-and-behavior-20261007`, worktree `/root/legalmind-worktrees/rag-ground`);
before that 2026-10-05T19:38+05:30
(worktree `/root/legalmind-worktrees/ask-agent-p0`) · local commits only, nothing pushed,
merged or deployed. Controlling documents:
- the kickoff prompt (`/root/Legalmind.v1/LegalMind_Ask_Agent_Kickoff_Prompt.md`);
- the [operating charter rev 3](../LegalMind_Ask_Agent_Operating_Charter.md).

## ▶ Start here — where the last session stopped (2026-10-06T11:17+05:30)

> **2026-10-08 00:04 IST — LIVE: latency batch 2 (`8335373`, PR #151).**
> - Production logs one `assist.agent.turn` line per question: stages, each call's latency and
>   tokens (cached and reasoning), and tool timings.
> - The reranker and NLI verifier warm at startup; verified in the log: embedding 579.51 ms,
>   reranker 315.74 ms, verifier 2,396.24 ms, all `warmed: true`.
> - A Gemini decision step is cut at 400 characters of discarded prose.
> - 0 API errors; build `ETT1PJWX4qa_KC5TfM9J9`. Rollback: revert `8335373` and redeploy.

> **2026-10-07 23:10 IST — LIVE: `AM-121` (D1–D6).** PR #148 was merged as `08564b3` (owner: "ok go
> ahead", after the latency diagnosis ranked its D5 changes first) and deployed with
> `sudo legalmind-deploy`.
> - No migration.
> - api, worker and frontend are active; `/health` and `/login` return 200.
> - 0 API errors since the restart.
> - Build `EGQorxD-i0UngJDCo5-al` is live and carries the new paste wording (the second of
>   two deploys of `08564b3`, at 23:10:54; the first built `YW163Q2NH1oMCu0Cs6Woi`).
> - Attachments are ON (unset in production, so the code default applies).
> - `legalmind-attachment-purge.timer` is installed and enabled; its manual run purged 0 and succeeded.
> - Latency report: SESSION_HANDOFF.md § Session 2026-10-07-LD.
>
> Rollback: `LEGALMIND_ASK_ATTACHMENTS=off` + restart, `LEGALMIND_ASK_AGENT_MODE=off` + restart,
> or revert `08564b3` and redeploy.

> **2026-10-07 (evening) — defect fixes D1–D6, branch `rag/defect-fixes-20261007` (local, not
> pushed):**
> - **D1 FIXED:** every asked point is answered or named (Gemini and DeepSeek 17/17 on the
>   real e-mail).
> - **D2 FIXED:** the floor says why, and the cite trim no longer strips standards.
> - **D3 FIXED (code):** a paste over 2,000 characters becomes the chat's material, like a
>   file (attachments default on, `AM-121`); verified locally on a 5,590-character paste.
> - **D4 FIXED:** a clause named by number or heading is in a searched document's evidence
>   whatever its rank (28-page MSA: numbers 53/81 → 81/81, headings 25/57 → 53/57); live on
>   Bonsai, page-22 clause found and cited.
> - **D5 partly FIXED:** DeepSeek's discarded "done" step is cut (7.6–11.2 s → 2.6–3.6 s),
>   a step's searches run in parallel (5.5 s → 2.8 s), a repair starts only with time to
>   finish; DeepSeek T4 went from the floor to answered. Streaming tokens to the reader is
>   blocked by the verify-before-show rule (owner decision).
> - **D6 FIXED:** a second agreement joins the same chat as a named file; every claim and
>   Sources line names it. "Does clause 17.2 of the MSA conflict with clause 13 of the ToS
>   I attached?" cites both on Gemini, DeepSeek and Bonsai. No API change.
> - **Regression baseline, final code:** T3 asks for the agreement and T4–T6 are answered
>   from it on all three models; footer and Sources text on all 9 answers. No statute was
>   cited in these runs: a pre-existing statute-record gap (Contract Act s. 74), identical
>   on `main`.
> - `AM-121` (AB-69) appended. Blockers for the owner: streaming tokens to readers;
>   Bonsai on long lists.
> - Details, measurements and blockers: SESSION_HANDOFF.md § Session 2026-10-07-DF.

> **2026-10-07 15:23 IST — LIVE:** PR #145 was merged as `f60d655` (owner: "go ahead push
> and merge") and deployed with `sudo legalmind-deploy`. It carries `AM-116`–`AM-120`.
> Verified read-only after the deploy:
> - the Alembic version moved, `a9e4c2f7b1d3` → `f4b8d2a6c1e9`, and the
>   `conversations.title` column exists;
> - api, worker and frontend are active; `/health` and `/login` return 200;
> - 0 API errors since the restart;
> - build `kMbIIyWTH5kttcpRjPQNq` carries the answer footer and the Sources buttons, and
>   no Qwen;
> - production serves gemini · deepseek · bonsai (egress api.indierouter.ai,
>   inference-api.lsnw.io).
>
> Rollback: `LEGALMIND_ASK_AGENT_MODE=off` and a restart, or revert `f60d655` and redeploy.
>
> Before the deploy, an uncommitted top-bar change in the deploy tree (from another of the
> owner's sessions) was parked, with the owner's choice: branch `wip/topbar-account-menu`
> `d24c2b5`, patch at `/root/.legalmind/preserved/topbar-account-menu-2026-10-07.patch`.

> **2026-10-07 — grounding and behaviour, three models (branch `rag/grounding-and-behavior-20261007`,
> on `fix/ask-chat-micro`; local commits only, NOT pushed, merged or deployed).**
> - DeepSeek (IndieRouter) and Bonsai (company endpoint) answer through the one egress seam
>   (`AM-117`).
> - Short, vague and ungrounded inputs get fixed words with no model call (`AM-118`):
>   - "hi" is one line;
>   - "how can you help me?" gets a three-sentence brief, its limit included;
>   - a question about the reader's own agreement, with none in the chat, asks for it
>     (was: a confident answer from our standard, P0);
>   - a vague intent gets one clarifying question;
>   - a bare paste is acknowledged.
> - The decision loop stops on time, then "done", a question asked, or a round of nothing new.
>   `MAX_DECISIONS` 6 is a safety net.
> - DeepSeek no longer falls to the floor: decision steps send `reasoning_effort` "none" and
>   are cut at 768 tokens.
> - The verifier scores claims in two batched NLI calls, so DeepSeek T7 went 75 → 42.8 s.
> - The floor never quotes another agreement family's position, and the local reranker picks
>   its quote.
> - Scores per model and turn, blockers and next steps: [SESSION_HANDOFF.md](SESSION_HANDOFF.md);
>   evidence per box: [SESSION_CHECKLIST.md](SESSION_CHECKLIST.md).
> - Tests: backend assist 1,673 passed; frontend 557; Ask e2e 34/34; ruff, mypy, tsc clean.
> - **Blocked:** the Bonsai endpoint cannot take the agent's ~45k-token context (520 at ~50 s).
> - **Review (same day):** a typed situation was being read as a paste, and the brief lacked
>   its limit; both fixed. Stack: `AM-116` → micro → this; neither parent is on GitHub.
> - **Round 3 (same day, `AM-119`):**
>   - Bonsai now answers (lean profile, streamed: 70–78 s live).
>   - Each answer shows its model and time.
>   - The Sources list opens each record in a dialog.
>   - Qwen is removed from the model list (`AM-120`): IndieRouter withdrew it.

> **2026-10-06 17:22 IST — LIVE: PR #143 merged as `b21cf94` (owner: "yes go ahead") and
> deployed with `sudo legalmind-deploy`; the Constitution re-ingested in production
> (`tools.ingest_constitution` → `changed: True, items 701, embedded 404`): L1.11 CURRENT
> `5b4e645ba0bd`, L1.10 SUPERSEDED (effective_to 2026-10-06, 701 items kept). Verified
> read-only: the current CERT-In entry says ₹1 crore and none says ₹1 lakh; api/worker/
> frontend active, `/health` 200, `/login` 200, 0 API errors since the restart; frontend
> build `204L9NQsS6VVyQCFPwvCx` carries the new section labels; the agent's search on the
> production DB returns IT Act s. 43A / s. 70B and DPDP's Schedule marked "not yet in force".
> Branch deleted. Rollback: revert `b21cf94` + redeploy; Constitution per ops/README.md
> § `AM-115`. (Below: the record as it stood at review.)**
> Branch `feat/ask-conversation-colleague`, commits `ca5315f` (fixes 1–5) and
> `31b35f3` (review, L1.11, validation). Tests at `31b35f3`: backend 3,206 passed · 119 skipped · 1 xfailed · 0 failed;
> frontend 547 passed; ruff, mypy, tsc clean. The owner's one-conversation test (20 turns, data deletion → cap →
> personal data → DPDP / IT Act → what to tell the customer) was diagnosed on the live agent
> (private FINDINGS `/root/.legalmind/diagnosis/conv-2026-10-06/`), fixed 1→5 (A-89…A-94),
> reviewed independently (A-95: nine findings, all fixed with tests), reviewed as a lawyer
> would (A-97) and validated end to end (EVALS #65: Act cited 0 → 14 of 19 turns, standard-as-
> contract statements 3 → 0, p50 18.8 s). **Constitution L1.11** (`AM-115`, A-96) resolves
> C-25: s. 70B(7) ₹1 crore and s. 72A ₹25 lakh as amended in 2023, a s. 43A note for counsel.
> **Pre-merge verification (A-98, EVALS #66) — clean after one fix.** (1) CI job 14 is the
> `main` baseline: `main`'s last run of it (run 37425459508, `7d12ea5`) failed on the same two
> advisories (Next.js GHSA-vcvr-r3jv-pc5j 16.2.0–16.3.5; source-map-js GHSA-68fv-2mgg-jv7q
> 1.0.0–1.2.1); later `main` runs skipped it (docs-only); this PR changes no dependency file;
> the ruleset requires only job 3. (2) "Lawful, unless": no new false deletion or acceptance —
> the s. 28/s. 23 rejections are identical under the pre-branch rules. (3) Indemnity and fixed
> wording clean; one P12 false flag on a denied protection fixed. (4) L1.11 at the PR head =
> the validated file (SHA-256 `5b4e645ba0bd…`); production read-only: L1.10 CURRENT `d53c0a6e`,
> 701 items, head `a9e4c2f7b1d3` — the rehearsed starting state.
> **On deploy:** run `python3 -m tools.ingest_constitution` with the API's environment right
> after the deploy (ops/README.md § `AM-115`) — `deploy.sh` does not; without it production
> keeps serving L1.10's figures. **Open for the owner:** merge + deploy; counsel
> items (DPDP s. 44(2)(a) commencement; s. 70B(8) complainant wording).

> **2026-10-06 12:42 IST — LIVE.** PR #140 merged (`7d12ea5`) and deployed with the
> Alembic fix PR #141 (`7b6fbd3`); migration `a9e4c2f7b1d3` applied (verified with
> `alembic current`); `LEGALMIND_ASK_AGENT_MODE=on` in production — **owner A-88, on for
> everyone**. Rollback: set it `off` in `/root/.legalmind.env` + `systemctl restart
> legalmind-api`. Attachments OFF. **Next (owner, new session):** re-run Real Conversation
> Tests v2 on production behaviour (C3 sends client material — ask first). Everything
> below this box describes the state before the merge.

**Next session:** read this box, then the A-82…A-87 rows of DECISIONS.md. Do not redo
anything listed as done.

**State:** branch `feat/ask-agent-phase0-1` (tag `demo-best` = `07bb58a`, the last code
commit), 0 behind `main`. **2026-10-06: owner approved push + PR for CI — NOT merge, NOT
deploy.** Before the push: the four retrieval gates re-run, identical to #49 (EVALS #59);
IMPLEMENTATION_STATUS / LEGALMIND_PROJECT_STATE / CHANGELOG synced (`197c019`). Check the
PR's CI result first.

**PR #140** (https://github.com/aman-data-on/LegalMind_v1/pull/140) — opened for CI only,
title says not for merge. First CI run: 14 pass, 2 fail:
- job 13 (whole suite): 6 tests needed the local models CI does not have (true since
  Phase 1; the branch had never run CI). Fixed in `6f7929f` by the suite's own
  conventions (material gate planted open in the attachment tests' fixture; two
  model-measuring cases skipped without the model). No assertion changed.
- job 14 (dependency scan): `npm audit` flags Next.js GHSA-vcvr-r3jv-pc5j and
  source-map-js GHSA-68fv-2mgg-jv7q. The branch does not touch `frontend/package*.json`,
  so `main` has the same finding — a separate dependency-bump PR, owner's call.
Re-run CI result: check `gh pr checks 140`.

**Owner, 2026-10-06: keep PR #140 open, NOT live** (no merge, no deploy, no migration).
**`main`'s records do not know this branch yet** — IMPLEMENTATION_STATUS,
LEGALMIND_PROJECT_STATE and CHANGELOG were updated ON THE BRANCH (`197c019`); the deploy
tree reads `main`. Read this file, not `main`'s, for the agent's state.

**Other worktrees, left untouched by owner choice (2026-10-06) — not this programme's:**
| Worktree / branch | State |
|---|---|
| `report-speed` / `feat/report-speed` | 16 uncommitted files incl. `assist/` + `analysis/` — needs the new import paths if it lands |
| `rag-framework-ab` / `bench/rag-framework-ab` | 12 uncommitted files + `tests/assist_eval/rag_ab/` |
| `no-auto-commit` / `docs/no-commit-without-owner` | uncommitted AGENTS.md / CLAUDE.md edits |
| `session-records-0930` / `docs/session-records-2026-09-30` | 1 commit not pushed (`001c306`) |
| `main-baseline` (detached `main`) | measurement worktree; 2 untracked tool harnesses | Full suite
green: 3172 passed · 119 skipped · 1 xfailed; ruff and mypy clean.

**Done on 2026-10-05 (in order):**
- A-82 answer style (answer first, no clause dumps, no internal fallback text); floor = one
  plain line + ≤2 ranked clauses; one retry on 500/503/429.
- A-83 Constitution hits read as whole sections; one read-time text for tool + ledger
  (re-fetched clauses no longer "stale"); verifier negation and number/blank fixes.
- A-84 planner cues word-bounded (`nda` inside "standard").
- RAG-stage layout: `assist/{ingestion,knowledge,query,retrieval,llm,synthesis,verification,agent}/`,
  tests in `tests/assist/<stage>/` — map in [MODULE_LAYOUT.md](MODULE_LAYOUT.md).
- A-85 the reader's own material always reaches the model (per-attachment, newest first).
- A-86 the owner's data-loss question answers across the provisions in the real chat
  (verifier lead-in/blank readings, reasoning order, internal `analysis` field, LOW thinking
  on the answer call, A1/A2 completeness repairs).
- A-87 rolling summary stateless (read from `assist.messages`; `_SUMMARIES` and
  `after_reply` removed); pinned header "EVIDENCE CITED ACROSS PREVIOUS TURNS"; payload
  measured as built once per turn with ~94% served from Gemini's implicit cache.

**Demo instance (running):** `backend/tools/demo_start.sh` → http://127.0.0.1:3299, login
`aman.singh@leapswitch.com` (password in `/root/.legalmind/demo/login.txt`), scratch DB
`legalmind_v1_demo`, the owner's paid key (key line only from `/root/.legalmind.env`).
Restart the API after code changes. Private records: `/root/.legalmind/diagnosis/`
(live-r*.json captures), `/root/.legalmind/demo/runs/`.

**Measured cost of the agent:** 2–4 Gemini calls and 70k–165k input tokens per turn on
the MSA; p50 ~20 s, max 26 s (legacy: 1–2 calls, ~2k tokens, p50 3.4 s).

**Open — owner decisions (hard gates):**
1. Re-run the owner's Real Conversation Tests v2 (last run FAIL 10/25, before all of
   today's fixes) — about 80–100 paid calls; holdouts C2/C6 only when the owner says.
2. Production migration `a9e4c2f7b1d3` (six attachment/ledger tables) — branch only.
3. Turning agent mode on in production (code forces `shadow` there, A-81).
4. Merge to `main` — only after CI is green and the §13a ruleset check; owner's call.
5. Keep or remove the "Searched in this turn: …" line (A-74, shows raw search queries).

**Open — engineering:** latency above the 20 s target; the other-document switch
(`find_documents`) unmeasured live; Devanagari claims and flattened tables fail closed;
`feat/report-speed` holds uncommitted assist edits that will need the new import paths.

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
| **4 Verifier, ladder, floor** | **FAIL against Real Conversation Tests v2 — NOT complete.** Final run (C1/C3/C4/C5 + F1–F3, 25 turns; 2 and 6 held out): Musts on 10/25 turns (40 %, bar 90 %), Must-not violations 0, worse than the current pipeline on 0 (better 19, equal 6), F1–F3 pass, 5 pending missing-source items listed. Done this round: controlled cross-document retrieval (A-65), D3 compared (A-66), root causes of the four regressions (A-67, A-70), multilingual plan (A-68), Must-not classification (A-69). Remaining: agent-behaviour misses per turn in PHASE4_EXIT addendum 2 | [PHASE4_EXIT.md](PHASE4_EXIT.md) (addendum 2); private `/root/.legalmind/review/phase4/acceptance/` |
| 5 | Hard gate | — |

## Demo mission (owner, 2026-10-04 23:00 IST → demo 09:00 IST 5 Oct)

Mission prompt: owner message of 2026-10-04 ("Make LegalMind Ask demo-ready"). Next session:
"Read STATUS.md and the mission prompt, and continue the loop from where you stopped."

**Free-key data rule (invariant 5):** only company-owned or public material through the free
key — the Constitution and standards, the MSA template (`MSA.pdf`), a partner-agreement
template, the public Leapswitch and CloudPe SLAs, synthetic messages. **Excluded:** C3 (bank
SLA and memo — client material). **The partner agreement exists only as client copies**: the
demo uses a template made by stripping every client-identifying field from one copy (A-76).

### Knowledge-gap list (zero model calls, 2026-10-04 23:15)

(a) exists in the knowledge base and reaches the model's context · (b) exists but does not
reach it · (c) exists in no document. Measured on this evening's captured contexts (current
code); C4.5, C5.4, C5.5, F2, F3 from the last full run. **27 a · 14 b · 2 c.**

| Turn | Needed information | Class |
|---|---|---|
| C1.1 | 17.2 six-month cap | **a** |
| C1.1 | 17.7 blank period | **b** |
| C1.1 | 17.1 exclusion | **a** |
| C1.1 | 17.3 customer-only exceptions | **a** |
| C1.1 | company MSA 12-month position | **a** |
| C1.1 | intended data-loss position | **c** |
| C1.2 | 17.1 exclusion | **a** |
| C1.2 | 17.3 customer-only exceptions | **a** |
| C1.2 | intended data-loss position (provider-side error) | **c** |
| C1.3 | 17.2 covers negligence | **a** |
| C1.3 | 17.3 customer-only exceptions | **a** |
| C1.4 | backup add-on terms | **b** |
| C1.5 | SLA credit remedy in the MSA | **a** |
| C1.5 | restoration obligation | **b** |
| C1.6 | 17.1 exclusion | **b** |
| C1.6 | 17.2 six-month cap | **a** |
| C4.1 | tier table (Gold benefits) | **a** |
| C4.1 | 3.2 rates 'listed above' | **b** |
| C4.2 | 4.2 one-time affiliate 10% | **a** |
| C4.3 | 13.2 cap with averaging | **a** |
| C4.3 | MSA template 17.2 (another document) | **b** |
| C4.3 | company MSA 12-month position | **a** |
| C4.4 | 8.2 30 days | **a** |
| C4.4 | 8.3 for cause | **b** |
| C4.4 | 8.6 no compensation | **a** |
| C4.5 | 3.3 refers to 9.2 | **a** |
| C4.5 | 9.2 is 'No Agency' | **b** |
| C5.1 | bands, below 95% = 100% | **a** |
| C5.1 | cap at the monthly bill | **b** |
| C5.1 | eligibility conditions | **b** |
| C5.2 | CloudPe below 95% = 20% | **b** |
| C5.3 | CloudPe 60 calendar days | **b** |
| C5.3 | credit note, not cash | **b** |
| C5.3 | void on termination | **b** |
| C5.4 | emergency maintenance <= 3 hours | **a** |
| C5.5 | company SLA standard 10/25/50 | **a** |
| C5.5 | company 30-day claim window | **a** |
| C5.5 | CloudPe bands to compare | **a** |
| F1.1 | 17.2 six months | **a** |
| F1.1 | company MSA 12-month position | **a** |
| F2.1 | early exit: fees for the remainder of the Term | **a** |
| F3.1 | 17.2 six months | **a** |
| F3.1 | 17.7 blank period | **a** |

**(c) — missing:** the *intended data-loss position* (C1.1, C1.2). Owner 2.2: a reasoning
example only — not to be ingested; answers say the company position on data loss is not
in the sources. **(b) is the work:** 14 items exist but never reach the model — the
diagnosis's root cause 1.

### Loop log

| # | Hypothesis | Change | Result | Kept | Calls |
|---|---|---|---|---|---|
| 1 | Needed clauses never reach the model (retrieval/context) | Backlog 1, 2, 4: whole selected document ≤240k chars (A-77), earlier answers' cites carried forward (A-79), seed heuristics removed (A-78) | zero-model coverage 27/41 → **37/41** (0.659 → 0.902); remaining 4 need the model's own search of another document (C4.3, C5.2, C5.3 ×2) | kept | 0 |
| 2 | Verifier deletes true claims (verification) | Backlog 5: B5 only for corpus-wide semantic-only hits (A-80) | unit-tested; D4 3/3 critical on the free key | kept | 7 |
| 3 | A clause split mid-sentence is judged by its half (context) | whole-document read joins a continuation chunk to the record it continues | D1.2's 17.1 data-loss claim no longer V3/V4 by construction; unit-tested | kept | 0 |
| 4 | An open question to counsel reads as an attribution (verification) | V12 exempts "legal review … whether …" without a stated consequence | D1.2's legal-review sentence kept; misattribution still caught; unit-tested | kept | 0 |
| 5 | The floor quotes the title page (orchestration) | floor ranks by the question's stemmed words; a quote carries its rule, not only its heading | browser, model unavailable: 17.7 and 17.2 quoted with the six-month rule in 0.7 s | kept | 0 |
| 6 | Two calls per turn halve the quota (orchestration) | Backlog 7: the decision call carries the final rules (`ANSWER_NOW`); a tool-free reply in the final structure is the answer | unit-tested; **never measured live** (no quota) — **reverted** (`7db1935`) under the keep-only-if-measured rule | reverted | 0 |
| 7 | The Key Obligations panel spends demo quota (orchestration) | `LEGALMIND_OBLIGATIONS_EXTRACTION=off` in the demo instance only (default on) | opening a document spends no request | kept | 0 |
| — | **Free-key quota: 20 requests/day/model on gemini-3.6-flash, exhausted 2026-10-04 ~23:40 IST** after D4 (7 calls) and D1/D3 (10). Resets ~05:30 IST. One D1–D5 run needs ~45 calls, so two verified runs cannot fit. Owner notified; zero-model work continues | — | — | — | — |

| 8 | The floor stops at a record's first sentence (orchestration) | a floor quote adds the record's sentence that best matches the question, verbatim, after " … " | floor-only, all 19 demo turns, zero calls: critical-pass 1 → **2/19** (D2.2 now quotes 4.2's 10%; D3.1 gains the 100 % band and 95 %); nothing regressed | kept | 0 |
| — | **05:38 IST: the free key served nothing.** The quota showed exhausted again ("retry in 23h51m") and the planned D4 run got 0 requests. Production uses a different key (checked by hash), so the key is spent elsewhere or the window is rolling. Without another key the demo shows the floor only | — | — | — | 0 |

| 9 | The answer reads like a search tool, and the floor dumps clauses (generation, orchestration) | Owner rule A-82: prompt `ask-agent-14` (answer first, how clauses connect, no clause wording unless asked, one offer); verifier drops silent; floor = one line + ≤2 IDF-ranked passages; one retry on 500/503/429-per-minute | browser, second free key: the cap question answered conversationally (6 months under 17.2; 17.7 blank; differs from the 12-month standard; an offer to explain the exceptions) in 19.8 s after two 503s recovered; the floor now quotes only 17.2 under one plain line | kept | ~8 |

| 10 | The agent reads the Constitution as isolated paragraphs (context) | A-83: a Constitution hit is read as its numbered section; one record per section | zero-model probe (10 new questions, holdouts excluded): needed items 15/20 → **20/20**; context per question ~6.4k → ~17k chars | kept | 0 |
| 11 | Cross-references carry the rest of the answer (context) | follow each hit's `cross_references`, query-filtered, at most 2 | no needed item gained; picks were noise (§12, §26.1, §31.14) even when strict | **reverted** | 0 |
| 12 | Joined clauses re-fetched later read "stale" (continuity) | `store.clause_text` / `ledger._read_time_text`: one read-time text for tool and ledger | regression test fails before, passes after (whole and ranked modes, and a Constitution section) | kept | 0 |
| 13 | The verifier deletes true claims (verification) | negation "in no event", clause-scoped subject negation, normalised lexical share, P10 company exemption | replay of captured final answers: false drops 7 → 1; true drops kept 2/2 | kept | 0 |

| 14 | Company-standard questions are searched as confidentiality (intent) | A-84: word-bounded planner cues; "SLA credit" cue | "what does our company standard say about SLA credits?" → SLA topic (was Confidentiality) | kept | 0 |

| 15 | Is the main problem solved? (context) | zero-model replay of the 10 A-75 diagnosis turns: does the A-75 oracle evidence reach today's context? | 55/58 oracle items present. Missing: the other-document switch (C5.3, model-dependent) and one non-critical position (C5.1) | — | 0 |
| 16 | The reader's own material disappears when it is large (context) | A-85: inline material per attachment, newest first, 120k budget | C3.2/C3.5: the pasted e-mail and memo (and the 56k upload) are back in context; regression test | kept | 0 |

| 17 | The owner's data-loss question answers from one clause (verification → generation) | A-86: blank and lead-in readings in the verifier; reasoning order + internal analysis + LOW thinking on the answer call; A1/A2 completeness repairs | real chat ×2: answer first; exclusion joined to the cap; 17.2, 17.7, 17.1/17.6, 9.10, 17.3 (Customer-only); open points; legal review once. Cost: some turns 3→4 calls, p95 ~22 s | kept | ~45 |

### Plan for the 05:30 IST quota reset (20 requests, the demo's own day)

The demo at 09:00 spends the same day's 20 requests. Unless the owner supplies a paid
key: (1) one D4 run on the iteration-6 commit, about 3 to 5 requests, to check the
one-call path holds quality and to give D4 its second pass; keep it or revert it with
git and move `demo-best`. (2) Leave the remaining ~15 for the live demo, about 8 to 10
turns. No other model runs.

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

- **Business finding — which version of one client's MSA was signed (owner, 2026-10-04;
  A-66).** The client's two DOCX copies (dated 4 and 5 August, byte-identical) follow the
  company TEMPLATE terms: no Minimum Service Period, early exit costs the remaining Term's
  fees, liability capped at six months of fees for the specific Services. The PDF dated
  30 July carries NEGOTIATED terms: a 6-month Minimum Service Period with compensation for
  its balance (5.1), a 90-day convenience exit (14.3), a 12-month Initial Term, and liability
  at the average monthly fee over three months (13.1). The evidence does not show which
  version was executed — **Legal and commercial to confirm**. (The client is not named here:
  no real counterparty is named in the repository; the private comparison is
  `/root/.legalmind/review/phase4/d3_comparison.json`.)

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

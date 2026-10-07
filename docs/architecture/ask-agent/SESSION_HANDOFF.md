# Ask agent — session handoff

Per-session log. Current state lives in [STATUS.md](STATUS.md); the end-of-session ritual in
[SESSION_CHECKLIST.md](SESSION_CHECKLIST.md). No client name, client text or key appears
here: fixtures are named by their private Drive id (`/root/.legalmind/test-corpus/raw/`,
mode 700/600, owner rulings D10/D11).

---

## Session 2026-10-07-DF — six known defects (D1–D6)

**Branch** `rag/defect-fixes-20261007` (worktree `/root/legalmind-worktrees/defect-fixes`),
from `main` `0aee166`. Local commits only: no push, merge or deploy.

**Regression baseline (must not break):**
- the agreement is read, the clause named, the standard compared, the law cited, and
  every sentence sourced;
- T4/T5/T6 (cap enforceable, convenience, indemnity survival) pass on all three models;
- a source click shows the clause, and the footer shows model + time;
- ungrounded sentences are removed;
- "my agreement" with no attachment asks for it.

### Fix order (written before any code)

1. **D1 [P0] — every requested point answered.**
   - A deterministic detector enumerates the numbered points in the reader's material
     (this email: "1. Title — request" … "17.").
   - Each point is searched on its own (local retrieval, no model cost).
   - The answer is asked for block by block, tagged with its point number.
   - After verification, code counts requested vs answered. Missing points get one
     continuation call; any still missing are listed by name, never dropped.
   - The reply states "N of N points".
2. **D2 [P0] — the fallback explains itself.**
   - Every floor is logged with its reason and the verifier's codes (codes and block
     indices only: no answer text in logs, per the log policy).
   - The reader is told why: the model did not finish in time; its answer could not be
     read; or which kind of check each draft statement failed.
   - Rejected sentences are never shown: an unverified claim reaching a reader is what
     `AM-25` r5 forbids.
   - The recorded floor cases are replayed to find real false positives.
3. **D3 [P1] — a long paste is accepted.**
   - Root cause: `LEGALMIND_ASK_ATTACHMENTS` is off in production, so the router refuses
     text over 2,000 characters.
   - The default becomes on, amending `AM-114`'s "default off". The owner's instruction is
     the approval, and the data boundary already approves sending material.
   - The paste then becomes the chat's material, exactly like an uploaded file.
   - The composer's counter is reworded.
   - Live verification needs a deploy, so it is the owner's step.
4. **D4 [P1] — a named clause is always in context.**
   - Clause numbers ("clause 13.1", "section 22") and clause topics named in the question
     are resolved against the selected document's own clause rows.
   - Those rows are forced into the turn's evidence even when ranking would miss them:
     the lean (Bonsai) path and documents over 240k characters are searched, not read
     whole.
5. **D5 [P2] — latency.**
   - Measure stage timings per model, before and after.
   - Make the safe speedups: the per-point searches of D1 run in parallel.
   - **Not done, by rule:** streaming tokens to the reader. The stage-9 invariant
     (`AM-25` r5, `AM-69`, CLAUDE.md) says nothing reaches a reader before verification;
     the owner must decide that. A progress-event stream would be an API contract
     change, so it is logged as a blocker.
   - Bonsai's reasoning is already off (`enable_thinking: false`, measured).
6. **D6 [P2] — two agreements in one chat.**
   - With a document already selected, a further file goes to the existing
     `POST /conversations/{id}/attachments` (no new API) instead of starting a new chat.
   - Material records carry their file name, so citations name the document.
   - The UI shows one chip per attachment.
   - The capability manifest's "one document per conversation" limit (L3) is updated.

Gemini cost guard: deterministic tests and offline replays first; one live check per
model per fix.

### Results (filled as each fix lands)

**D1 [P0] — FIXED** (`8d7a41b`, then the page fixes).
- Root cause: nothing counted. The model chose which points to answer, and the verifier's
  cite trim then stripped standards (see D2).
- Fix: `agent/points.py` reads the numbered list from the reader's own material, newest
  first (re-pasting the same text reuses its saved row). Each point is searched on its
  own, in parallel on read-only sessions. The answer is asked for point by point.
- After the checks, code counts. A point with no substantive block (a restatement does
  not count) is asked again, then named. The reply opens with the count and gives each
  point under its heading.
- Verified live on the real 17-point e-mail:

  | Model | Points named | Agreement clause cited | Standard (P/C) cited | Statute cited | Time |
  |---|---|---|---|---|---|
  | Gemini | **17/17** | 7 | 12 | 0 | 45 s |
  | DeepSeek | **17/17** | 7 | 15 | 1 | 81 s |
  | Bonsai | 0, all 17 **named** as not answered | — | — | — | 112 s |

  Before the fix, Gemini named 4 and DeepSeek 6.
- **Law per point:** cited only where the approved statute corpus bears. The calibrated
  statute gate finds nothing for business wording ("auto-renewal", "pricing
  protection"), and it is not loosened (wrong-source risk). One point (data retention)
  is offered the DPDP Rules.
- **Bonsai:** two attempts (pages of 4, then 2) both time out at about 20 tokens/s. Under
  the anti-loop rule this is now a **blocker**: the endpoint is too slow for long
  lists. The reply names every point and suggests Gemini or DeepSeek, or two points at a
  time.

**D2 [P0] — FIXED.**
- **Root cause 1:** `settle`'s cite trim kept a further cite only if the block then had
  no violation, V14 included. V14 means "the position and the agreement state different
  figures" (state both), so the trim stripped the standard from every "departs from our
  standard" claim, and some of those claims were then dropped.
  - Fix: the trim judges as the final check does (`SETTLE_IGNORED`).
  - Same 17-point answer: clause cites 5 → 8, standard cites 8 → 11.
  - Test: `test_settle_keeps_the_standard_a_differing_clause_is_compared_with`, which
    fails on the old code.
- **Root cause 2:** the floor said only "I couldn't write a full explanation".
  - Fix: `agent_verify.floor_reason` now says why: the model did not finish in time or
    could not be reached; its answer could not be read; or, statement by statement,
    which check failed on which source. The statement itself is never shown: an
    unchecked claim does not reach a reader (`AM-25` r5).
  - The failure flags now carry the cause ("TimeoutError", "HTTP 520").
  - Every floor is logged as `assist.agent.floor` with its kind and check codes; never
    text, per the log policy.
- **Verified live:**
  - Bonsai T6 is a full answer (58.6 s), where it had been the floor.
  - Bonsai T7 reads "Bonsai did not finish its answer within the time limit", with all
    17 points named.

## Session 2026-10-07-RG — grounding and behaviour

**Branch:** `rag/grounding-and-behavior-20261007`, worktree
`/root/legalmind-worktrees/rag-ground`, based on `fix/ask-chat-micro` `18ad160`, which
carries `AM-116` `990cf39` (the model router this session needs). Local commits only: no
push, merge, rebase, tag or deploy, and no `npm run deploy`, no bare `next build`, no
visual-baseline update.

### Goal

Make Ask answer only from Attachment Context (an uploaded agreement, or pasted text) plus
Evidence Context (Constitution, statutes, standards), behave like a senior assistant on
short, vague and ungrounded inputs, and prove both end to end on Gemini, DeepSeek and
Bonsai.

### Plan (written before any code)

1. **Environment, production untouched.**
   - Scratch DB `legalmind_rag_ground`: a `pg_dump` of `legalmind_v1_demo` (it is in use by
     the demo, so it is copied, never altered). That gives the branch head `f4b8d2a6c1e9`,
     the Constitution with L1.11 current, and 79 standards. Statute tables are replaced
     with the `section-5` set production serves (`AM-104`), taken from
     `legalmind_ab_bench`. Old conversations are truncated.
   - API from this worktree on its own port: agent mode on, attachments on (the designed
     paste path), production's rerank and position-synthesis flags. Only the needed key
     lines are read from `/root/.legalmind.env`.
2. **Trace the 11-step chain in code and in a live trace:** upload → attach → paste →
   request → proxy → retrieval → prompt assembly → system prompt → LLM call → render →
   failure UX. Evidence for every row is a file:line, a request trace or a captured
   payload (private, IDs only in this file).
3. **Fixture (owner D10):**
   - Email: Drive `1qTS1TkK4Vfk2Vf5w20quyGJD-gpYB9_0`, a counterparty's 17 review points on
     our MSA (early termination, auto-renewal, retention, suspension, liability carve-outs,
     mutual indemnity, payment).
   - Agreement: Drive `1k_mgdJyyUE0sAJ3vOlLQysW_nHXruh0-`, an executed MSA on our paper. Its
     damages cap is an AVERAGE of fees (the CLAUDE.md trap), which must not be read as the
     12-month total standard.
   - The two come from different counterparties; the questions test grounding per source,
     and no answer may merge them.
4. **The conversation (identical for every model):**
   1. normal: our early-termination position;
   2. scenario: a customer wants a capped early exit on 60 days' notice;
   3. ungrounded: "Is my liability cap enforceable?", with no document;
   4. attach the agreement, then the three sales questions: the cap; termination for
      convenience; indemnity survival;
   5. paste the email with a question;
   6. paste a clause with no question;
   7. "hi", "thanks", "how can you help me?", "hi" again;
   8. vague: "I want to talk about a dispute."

   One chat per model (the comparison needs the same history). A re-check after a fix
   goes back to the same chat.
5. **Score** each reply 1–5 on grounding, brevity, accuracy, tone and failure honesty.
   Rank defects: P0 = no grounding reaches the model, or a confident answer without
   grounding; P1 = partial or wrong grounding; P2 = degraded grounding or a behaviour gap.
6. **Fix minimal, root cause, with tests.**
   - Known before the live run (code evidence):
     - (a) the fixed "hi" reply re-introduces the product (`conversational.py`);
     - (b) "how can you help me?" is not recognised as a capability question and reaches
       the model;
     - (c) a pasted clause under 2,000 characters is not treated as material at all;
     - (d) with attachments off, as in production, a paste over 2,000 characters is
       refused.
   - Wording changes to the fixed replies append an `AM-109` amendment.
7. **Providers.**
   - One OpenAI-compatible adapter in the egress module, so every gate, payload screen,
     audit row and token count applies to it.
   - Registry: DeepSeek via IndieRouter, Bonsai via the company endpoint.
   - An appended `AM-30` amendment per `AM-116` r5. IndieRouter's no-training terms are
     recorded as unconfirmed; Bonsai is on the company's own domain.
8. **Gemini cost guard:**
   - deterministic checks first;
   - one live pass per model;
   - a re-run only of the turns a fix touches.
9. **Before stopping:**
   - tests: backend pytest (agent + touched modules), vitest, tsc and lint, plus a
     Playwright run where the CI stack is not needed;
   - commits;
   - update STATUS.md, this file and SESSION_CHECKLIST.md, and the three CLAUDE.md
     records.

### What was fixed

Every item: root cause, the change, file:line, commit. Records: `AM-117` (AB-65), `AM-118`
(AB-66), both appended to `all_lock.md`.

| # | Rank | Defect (evidence) | Root cause | Fix · where · commit |
|---|---|---|---|---|
| 1 | **P0** | "Is my liability cap enforceable?" with no agreement in the chat got a confident answer from the company standard, as if the standard were the reader's cap (Gemini T3) | nothing told a question about the reader's OWN paper from one about ours | a fixed reply says what to attach or paste · `query/conversational.py:177,191`, `service.py` `preroute` · `7ebf84a` (`AM-118` r3). Re-checked: T3 in a fresh chat on all three models, 0 calls |
| 2 | P1 | a bare clause paste was analysed unasked (T8) | a paste under the 2,000-character cap was never material | `agent/attachments.py:139` `carries_material` + `api/routers/assist.py` (attachments on → saved, `MATERIAL_SAVED`); with attachments off, `service.py:317-321` → `MATERIAL_READ`, 0 calls · `7ebf84a` (r5, r6) |
| 3 | P1 | "hi" re-introduced the product (T9, T12) | the fixed wording | `query/conversational.py:156` · `7ebf84a` (r1) |
| 4 | P1 | "how can you help me?" reached the model: 4 calls, 12 s (T11) | the agent's pre-router never ran the capability route | the manifest's `brief` · `query/capability.py:76,91`, `config/capability_manifest.json`, `preroute` · `7ebf84a` (r2) |
| 5 | P1 | a vague "I want to talk … about a dispute" got the dispute clause dumped (T13) | no clarifying rule | one fixed question · `query/conversational.py:211` · `7ebf84a` (r4) |
| 6 | P1 | the loop was controlled by a count (3) alone (owner's 7 rules) | no stop rule | `MAX_DECISIONS` 6 as a net; one `_should_stop` (time, then asked / done / repeat) · `agent/agent.py:49,906,990,1035` · `7ebf84a` (r7) |
| 7 | P1 | DeepSeek ended T2 and T4–T7 on the floor at 28–40 s | reasoning tokens count against `max_tokens`: a decision spent all 2,048 thinking and returned no tool call; a "done" decision then wrote 400–1,500 tokens of discarded prose; a LOW answer ran past its time | `reasoning_effort` from Gemini's thinking level; OpenAI-compatible providers think at MINIMAL and cut a decision at 768 tokens · `llm/generation.py:886`, `agent/agent.py:441,489` · `0108624`, `bf72fec` |
| 8 | P1 | DeepSeek T7 took 75 s against `HARD_S` 40 s: 36 s AFTER the model answered | the verifier judged claim by claim — 118 NLI calls of 1–5 pairs | `verify.warm` scores stage 1, then stage 2 for the claims stage 1 did not entail, in two calls; `judge` reads the memo; pair builders shared (`_claim`, `_stage2`) · `verification/verify.py:287,307,319`, `agent_verify.verify` · `51614b1`. Replay: 41 → 31.7 s, 118 → 20 calls, identical verdicts; live T7 75 → 42.8 s, T4 41.8 → 27.5 s |
| 9 | P1 | the floor quoted a Partner Agreement position as "the clause that answers this most directly" in an MSA chat (Bonsai T2) | P2b held the model's answer to the conversation's kinds of agreement, not the floor | one predicate for both · `verification/agent_verify.py:450` (`_other_family`), `floor`, `ladder` · `dd83fb3` |
| 10 | P2 | the floor chose by shared words: force majeure for an early exit, "(f) violates applicable laws" for the liability cap | lexical ranking only | the local cross-encoder (`rerank.scores`, on in production) orders the candidates; a second quote must clear logit 0 · `agent_verify.py:1170` · `40c35d1`. Live Bonsai floors now quote 14.3, 13.1, 15.2 |
| 11 | P2 | e2e 32/34: a refused paste came back trimmed; a model option said only "DeepSeek" to a screen reader | the restore used the trimmed text; a Radix option is named by its `ItemText` alone | `components/workspace/AskWorkspace.tsx` `submit`, `ModelPicker.tsx` (visually hidden status) · `af3a586` |

The providers themselves: `48aa1e2` (`AM-117`: DeepSeek via IndieRouter, Bonsai on the
company endpoint, through the one egress seam).

#### Decision loop (owner, 2026-10-07) — the three lines asked for

- **Problem:** the loop stopped only on a fixed count (3 decisions). A bare paste reached the model, which analysed it unasked, and repeated searches spent calls the final answer needed.
- **Change:** `MAX_DECISIONS` is now 6, as a safety net only. One `_should_stop()` ends the loop on `soft_deadline`, `budget` (the `HARD_S` − `FINAL_RESERVE_S` reserve, or the call cap), `asked`, `model_done`, or `repeat` (a round that returned only chunks already shown). A bare paste is acknowledged with zero model calls (`MATERIAL_READ`).
- **Where:** `backend/legalmind/assist/agent/agent.py:49`, `:906` (`_should_stop`), `:990`, `:1035`; `backend/legalmind/assist/service.py:317-321`; `backend/legalmind/assist/agent/attachments.py:51`. Tests: `tests/assist/agent/test_assist_agent.py`.

### Behavioural test results

One conversation per model, the same 13 inputs, re-checked in the SAME chat after each fix
(Gemini `188b1b2b`, DeepSeek `c1fd2bb1`, Bonsai `080c07e0`; T3's fix in a fresh no-document
chat, because the original chats hold the agreement by then). Fixture: Drive
`1qTS1TkK4Vfk2Vf5w20quyGJD-gpYB9_0` (the e-mail, 17 points) and `1k_mgdJyyUE0sAJ3vOlLQysW_nHXruh0-`
(the executed MSA). Scores 1–5 as **G**rounding · **B**revity · **A**ccuracy · **T**one ·
**F**ailure honesty, on the final reply.

| Input | Expected | Gemini | DeepSeek | Bonsai |
|---|---|---|---|---|
| T1 our early-termination position | the MSA standard, cited | 5·4·5·4·5 — no early exit, remaining fees [P1]; 13 s | 5·3·5·4·5 — the standard, then the attached 14.3 (asked after the attach); 33 s (was: answered) | 2·4·3·3·4 — floor (endpoint), the liability standard quoted first |
| T2 capped exit on 60 days? | "no — needs approval", from the standard | 5·4·5·5·5 — no, commercial approval + legal review [C3, P1] | 3·3·3·4·3 — answers from the attached agreement's 5.1/14.3, never says whether we can agree; 46 s (was: floor) | 3·4·3·4·4 — floor quotes 14.3 (was: a Partner Agreement position — fixed #9, #10) |
| T3 my cap enforceable? (no agreement) | say the grounding is missing | 5·5·5·5·5 — fixed reply, 0 calls (was 1·3·1·4·1: confident, from our standard) | 5·5·5·5·5 (was: floor quoting standards) | 5·5·5·5·5 |
| T4 this agreement's cap enforceable? | the 13.1 cap + the law + the standard, kept apart | 5·3·5·4·4 — 3-month average cap, 13.2 exclusions, ss. 73/74; 28 s | 5·3·5·4·5 — not determinable, a counsel point; 3-month average vs the 12-month standard; 27.5 s (was: floor) | 4·4·3·4·4 — floor quotes 13.1 (was: an unlawful-content clause — fixed #10) |
| T5 terminate for convenience? | 14.3, 90 days, 5.1 | 5·4·4·4·4 — 90 days; puts "we" under the customer's 5.1 limit; 25 s | 5·3·5·4·5 — both parties, customer subject to 5.1; 42 s (was: floor) | 4·5·4·3·4 — floor quotes 14.3 |
| T6 indemnity survives? | 15.2 accrued; no express survival | 5·4·5·4·5; 18 s | 5·4·5·4·4; 40 s (was: answered) | 4·5·4·3·4 — floor quotes 15.2 (was: 12.4 — fixed #10) |
| T7 e-mail + "which conflict with our standards?" | every conflicting point, against the standards | 4·4·3·4·3 — four conflicts; indemnity / liability / auto-renewal left out, unsaid; 29 s | 4·3·4·4·4 — six conflicts named with clauses; 42.8 s (was: floor, then 75 s — fixed #8) | 2·4·2·3·4 — floor quotes one agreement clause; a 17-point comparison has no one-passage answer |
| T8 bare clause paste | short acknowledgement + offer | 5·5·5·5·5 — saved, "what would you like to know?", 0 calls (was: a full analysis) | same | same |
| T9 / T12 "hi" twice | one short line, identical | 5·5·5·5·5 — "Hello. What can I help you with today?" both times, 0 calls | same | same |
| T10 "thanks" | short acknowledgement | 5·5·5·5·5 | same | same |
| T11 "how can you help me?" | ≤ 2–3 lines | 5·5·5·5·5 — the three-sentence brief (what it does, its limit, how to start), 0 calls (was: 4 model calls, 12 s) | same | same |
| T13 vague dispute | ONE clarifying question | 5·5·5·5·5 — "payment, termination, a breach, or something else?" (was: the dispute clause dumped) | same | same |

T8–T13 are answered before any model call, so they are identical for every model by
construction. Bonsai's T1–T7 are floors because its endpoint cannot take the agent's
context (Blockers). Model use (captured, private): Gemini 47 calls over both passes,
1.87 M prompt tokens (mostly cached) and 19.7 k output — the after-pass 10 calls; DeepSeek
63 calls; Bonsai 15 attempts, all failed at the endpoint; plus about 18 direct replays to
diagnose (DeepSeek, Bonsai — none to Gemini).

### Proactive fixes applied

Two of thirteen changes (15 %, under the 20 % cap):
- the `Endpoint` key is excluded from its `repr`, because captured call arguments printed it (`0108624`);
- the NLI memo is bounded at 4,096 entries (the agent path never cleared it, so it grew
  for the life of the process) and read once per call, so a concurrent clear cannot lose a
  pair (`51614b1`).

### Assumptions logged

- T2's DeepSeek and Bonsai re-runs came after the agreement was attached in the same chat,
  so they answer from it. That follows the one-chat rule, but it is not like-for-like with
  Gemini's T2, which was asked before the attach.
- `reasoning_effort` is sent to every OpenAI-compatible provider. DeepSeek honours it;
  Bonsai accepts it and ignores it (probe, 2026-10-07).

### Blockers — needs human decision or external setup

1. **`LEGALMIND_ASK_ATTACHMENTS` is off in production.** A paste over 2,000 characters is
   refused, and a bare paste under the cap is acknowledged but not saved. Turning it on is a
   production configuration change for the owner.
2. **IndieRouter's no-training terms are not confirmed** (`AM-117` r5).
3. **Security housekeeping:**
   - rotate the IndieRouter and Bonsai keys pasted into the chat;
   - the production DB password was visible in a process command line (seen 2026-10-06).

*Resolved in round 3:*
- Qwen is removed from the model list (`AM-120`): the owner reports IndieRouter withdrew
  it, which agrees with its "Unknown model" answer for the key.
- Bonsai now answers (see below).
- Agent answers' sources are now structured and can be opened (it had needed an
  API-contract change, made on the owner's request).

### Next session — pick up here

- **T7 coverage of a many-point e-mail.** Gemini named 4 conflicting points and DeepSeek 6.
  Gemini's first draft said indemnity, liability and auto-renewal also conflict, and its
  repair dropped that line. Fixing this needs an answer-contract change ("one block per
  conflicting point") plus a Gemini measurement run, so it was not done blind (cost guard).
- **DeepSeek T7 is still 42.8 s.** About 24 s of that is local NLI over 530 pairs (~45 ms a
  pair on 6 CPUs). What remains is fewer stage-2 pairs or a smaller NLI model, and both
  need measuring.
- **A source cited across turns can lose its dialog on reload** (independent review #7,
  predates round 3). The registry re-adopts a pinned key with the current text, and
  `ledger._upsert` then mints a new key by text hash, so reload finds the record under
  that new key. The fix belongs in the ledger's key identity.
- **"Open in the document" for another document's clause** is not offered, live or on
  reload: replay can only re-read the conversation's own contract.
- **Owner:** review the branch, then decide on push / PR / merge / deploy.

### Review before the GitHub step (2026-10-07, owner: "again review your work")

The whole diff against `fix/ask-chat-micro` was re-read and the CI guards were run
locally.

**Defects found and fixed in the review:**
1. **A typed situation was read as a bare paste.** 80 typed words ending "Let me know our
   position on this" were acknowledged and never answered. A last sentence that asks the
   assistant for something now makes the message a question · `agent/attachments.py`
   `_ASKS` · test `test_a_long_typed_situation_that_asks_is_a_question_not_a_paste`.
2. **The capability brief listed only strengths.** `AM-68` r5 requires the capability
   answer to state its limits, and the brief dropped them. It now carries L1 ("I do not
   decide whether a document is acceptable or advise whether to sign; a person decides"),
   and `brief()` accepts limit ids as evidence.
3. **The floor asked the reranker with no question words.** It no longer calls the
   reranker on an empty question.

**Checked and sound:**
- A tool call cut at 768 tokens parses to `{}`, which the tool layer refuses.
- `my …` does not swallow "my company's".
- "Add files" matches the UI's own wording.
- The configured hosts match the `AM-117` record.
- No counterparty name and no key prefix appears anywhere in the diff.
- CI job 6 locally: 0 lines removed, main's 22,469-line prefix identical.
- Job 7: no corpus fixture changed.
- Job 8: no contract file type added.

**Risks carried forward:**
- **The rollback path.** `preroute` runs only on the agent path, which production serves
  to everyone. With `LEGALMIND_ASK_AGENT_MODE=off` (the rollback) the old pipeline answers,
  without the `AM-118` own-agreement reply.
- **Gemini cost.** `MAX_DECISIONS` 6 permits more Gemini decisions per turn than 3 did;
  `SOFT_S` and the repeat stop bound it. Measured: T7 used 6 calls (was 4), T4 used 4
  (unchanged).
- **The stack.** It carries `AM-116`'s migration `f4b8d2a6c1e9` (`conversations.title`).
  A deploy must confirm the Alembic version moved (the 2026-10-06 silent rollback).
- **Private harness data.** `/root/.legalmind/rag-ground/captures/` (mode 700/600) holds
  real document text and, from before `0108624`, the provider keys inside the captured
  `Endpoint` repr. Delete it when the comparison is no longer needed.

**Tests after the review:**
- backend `tests/assist` + source material + import boundaries: 1,701 passed, 4 skipped
  (6:29). A first attempt stalled at ~30%, with Postgres at 90% CPU on one position query
  while the e2e run shared the server; the re-run was clean;
- ruff and mypy clean (147 files);
- Ask e2e in ONE pass: 34/34;
- frontend vitest 557/557, lint clean.

### Round 3 (2026-10-07) — Bonsai, Qwen, who answered and how long, sources you can open

Owner: fix Bonsai, find out why Qwen is not configured, show the model and the time
under each answer, and (their manager) list the sources structurally, each opening to
show where it came from. Researched first (two code maps, one per side); then built,
reviewed by an independent reviewer (8 findings, 7 fixed, 1 logged above), and measured
live.

| Item | Root cause (measured) | Change | Evidence |
|---|---|---|---|
| **Bonsai** | ~700 prompt and ~18–26 output tokens/s; the gateway closes a request silent for 50 s; it reasons unless told not to | lean profile (`AM-119` r3): agreement searched not read whole, material capped (and searched), no decision step, the repair only with time to finish, a 110 s budget; streamed inside `_send` (`AM-119` r4); `enable_thinking: false` | live T4 70 s, T5 74 s, T6 78 s, all real answers; before, every turn ended on the floor |
| **Qwen** | IndieRouter: "Unknown model: qwen3.8-flash-next" for the key | none possible: recorded (`AM-119` r5) | blocker 1 |
| **Model and time** | the answer row stored them; nothing returned them | `answered_by` + `latency_ms` live and on reload, from the same row; the footer "Answered by DeepSeek (deepseek-v4.1-flash) · 41.3 s"; a fixed reply says no model was used | real browser, DeepSeek and Bonsai |
| **Sources** | the agent returned `citations: []`, with a text legend only | `sources` per legend key; each legend entry is a button opening a dialog with the record's own words and "Open in the document"; reload re-reads under current permissions | real browser: dialog opens, Escape closes, focus returns |

**Fixes from the independent review:**
- the footer names only the model whose words are shown (the floor names none, and the
  rescue judge is never named);
- a stream that is empty or reports an error fails, and `[DONE]` ends it;
- a stream's per-read wait is at most 50 s, its deadline holds over the whole stream, and
  a retry gets only the time left;
- lean searches the reader's attachments;
- another document's clause is not offered as a source;
- the dock offers no link (its document is already open);
- a marker's jump lands visibly.

**Tests (final code):**
- backend `tests/assist` + source material + import boundaries: 1,709 passed, 4 skipped; without models (as CI): 1,645 passed, 32 skipped, 0 failed; ruff and mypy clean;
- frontend vitest 560/560, lint clean;
- Ask e2e 34/34 in one pass;
- live: DeepSeek and Bonsai in their own chats, in a real browser through nginx (`next
  dev`'s proxy drops requests after ~30 s, a local limit only).

### Final review before merging (2026-10-07)

An independent review of the whole branch against `main` found one defect, now fixed. It
found no permission leak, no egress outside `_send`, no migration problem, no API break,
and no CI failure.
- **HIGH, fixed:** with attachments off (as in production), "I don't have that agreement"
  also answered questions that gave their own text: a quoted clause, a stated figure
  ("my cap of 3 months' fees"), a drafting request, or a clause pasted in an earlier turn.
  The neighbouring vague-intent rule caught "a claim under the DPDP Act".
  - `their_document_topic` now steps aside for a quote, a colon followed by text, a
    figure, a drafting verb, or more than 20 words.
  - A paste in the thread counts as material.
  - `vague_intent` asks only when nothing but generic words remain.
  - Tests: the reviewer's inputs.
- **Low, fixed:** a test name that gave the wrong reason.

Whole backend suite, run as CI job 13 runs it (no keys, no models): 3,216 passed, 167
skipped, 1 xfailed, 0 failed. ruff and mypy clean.

### Git

**Merged and deployed 2026-10-07:**
- PR #145 merged as `f60d655` (09:44 UTC) and deployed at 15:23 IST; migration verified
  (see STATUS.md).
- Branches `rag/grounding-and-behavior-20261007`, `fix/ask-chat-micro` and
  `feat/ask-chat-controls` deleted, together with their worktrees.
- The parked top-bar change is on `wip/topbar-account-menu` `d24c2b5`.

As it stood before the merge:

Branch `rag/grounding-and-behavior-20261007` (worktree
`/root/legalmind-worktrees/rag-ground`), on `fix/ask-chat-micro` `18ad160`, on
`feat/ask-chat-controls` `990cf39` (`AM-116`). **Neither parent is on GitHub**, so a PR
from this branch to `main` carries all of them (12 commits); `origin/main` has not moved
since the base (0 commits behind). Local commits only. Review: `git log --oneline fix/ask-chat-micro..rag/grounding-and-behavior-20261007`
and `git diff fix/ask-chat-micro..rag/grounding-and-behavior-20261007 --stat`.

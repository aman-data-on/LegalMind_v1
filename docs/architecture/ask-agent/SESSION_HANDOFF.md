# Ask agent — session handoff

Per-session log. Current state lives in [STATUS.md](STATUS.md); the end-of-session ritual in
[SESSION_CHECKLIST.md](SESSION_CHECKLIST.md). No client name, client text or key appears
here: fixtures are named by their private Drive id (`/root/.legalmind/test-corpus/raw/`,
mode 700/600, owner rulings D10/D11).

---

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
| T11 "how can you help me?" | ≤ 2–3 lines | 5·5·5·5·5 — the two-sentence brief, 0 calls (was: 4 model calls, 12 s) | same | same |
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

1. **Bonsai cannot serve the agent.** A 16k-token prompt takes about 28 s, and the agent's
   ~45k-token context returns HTTP 520 at about 50 s (the endpoint's gateway limit); small
   prompts work (1 s). This needs a faster deployment, or an owner decision on a smaller
   per-provider context. Until then every Bonsai turn ends on the (now relevant) floor.
2. **Agent answers' citations are not navigable.** `_agent_answer` returns `citations: []`;
   the Sources legend is text. Making them navigable means a key-to-evidence field on the
   answer, which is an API contract change.
3. **`LEGALMIND_ASK_ATTACHMENTS` is off in production.** A paste over 2,000 characters is
   refused, and a bare paste under the cap is acknowledged but not saved. Turning it on is a
   production configuration change for the owner.
4. **IndieRouter's no-training terms are not confirmed** (`AM-117` r5). Qwen is not on the key.
5. **Security housekeeping:**
   - rotate the IndieRouter and Bonsai keys pasted into the chat;
   - the production DB password was visible in a process command line (seen 2026-10-06).

### Next session — pick up here

- **T7 coverage of a many-point e-mail.** Gemini named 4 conflicting points and DeepSeek 6.
  Gemini's first draft said indemnity, liability and auto-renewal also conflict, and its
  repair dropped that line. Fixing this needs an answer-contract change ("one block per
  conflicting point") plus a Gemini measurement run, so it was not done blind (cost guard).
- **DeepSeek T7 is still 42.8 s.** About 24 s of that is local NLI over 530 pairs (~45 ms a
  pair on 6 CPUs). What remains is fewer stage-2 pairs or a smaller NLI model, and both
  need measuring.
- **Owner:** review the branch, then decide on push / PR / merge / deploy.

### Git

Branch `rag/grounding-and-behavior-20261007` (worktree
`/root/legalmind-worktrees/rag-ground`), on `fix/ask-chat-micro` `18ad160`. Local commits
only. Review: `git log --oneline fix/ask-chat-micro..rag/grounding-and-behavior-20261007`
and `git diff fix/ask-chat-micro..rag/grounding-and-behavior-20261007 --stat`.

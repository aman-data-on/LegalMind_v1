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

#### Decision loop (owner, 2026-10-07)

- **Problem:** the loop stopped only on a fixed count (3 decisions). A bare paste reached the model, which analysed it unasked, and repeated searches spent calls the final answer needed.
- **Change:** `MAX_DECISIONS` is now 6, as a safety net only. One `_should_stop()` ends the loop on `soft_deadline`, `budget` (the `HARD_S` − `FINAL_RESERVE_S` reserve, or the call cap), `asked`, `model_done`, or `repeat` (a round that returned only chunks already shown). A bare paste is acknowledged with zero model calls (`MATERIAL_READ`).
- **Where:** `backend/legalmind/assist/agent/agent.py:49`, `:901` (`_should_stop`), `:985`, `:1030`; `backend/legalmind/assist/service.py:317-321`; `backend/legalmind/assist/agent/attachments.py:51`. Tests: `tests/assist/agent/test_assist_agent.py`.

### Behavioural test results

_(model × input × expected × actual × scores)_

### Proactive fixes applied

_(count, justification, share of changes; cap 20 %)_

### Pending · next session first · blockers · git

_(filled at the end)_

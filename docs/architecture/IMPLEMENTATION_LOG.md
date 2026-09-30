# Ask agent — implementation log

Chronological record of work against
[LegalMind Ask — Implementation Plan](LegalMind%20Ask%20—%20Implementation%20Plan%20(for%20the%20coding%20agent).md).
One dated entry per phase. Target design:
[v2.1 architecture](LegalMind_Ask_Conversational_Agent_Architecture_v2.1.md.md).

---

## 2026-09-30 — Phase 0 (hotfix) and Phase 1A (audit)

**Branch:** `feat/ask-agent-phase0-1`, worktree `/root/legalmind-worktrees/ask-agent-p0`,
from `main` `ee9dd10`. Local commits only.

### Phase 0: done

- **0.1** `intent.is_follow_up`. The anaphora rule ("this", "that", "it" anywhere in the
  message) now applies only to messages of at most `_FOLLOW_UP_MAX_TOKENS` = 30 word
  tokens. A pasted case summary whose last sentence says "this offer" no longer inherits
  the previous question as its retrieval anchor.
  - The opener rule ("and …") and the one-content-word rule are unchanged.
  - The fix sits in the one function both callers use: the current-turn flag
    (`understanding.py:327`) and anchor selection (`service._resolve_follow_up`).
  - A long first turn can now become the anchor for a short follow-up after it.
  - A near-the-start window was rejected: the real follow-up "…in this case and why it is
    not applicable" has its anaphor at token 8.
- **0.2** `intent.has_no_subject` treats request-for-a-view words (`take`, `view`,
  `opinion`, `thoughts`, `think`, `you`, `your`) as carrying no subject. "what is you take
  on this ?" on a first turn with no document now gets the existing UNCLEAR reply.
  - A digit or any real noun still counts as a subject ("your view on the liability cap",
    "what do you think of clause 7?").
  - The words are kept out of `_STOP`, so follow-up content-word counting is unchanged.
  - No reply text changed; `service.py:1057` and `_social_reply` are reused as they are.
- No prompt, calibration constant, gate threshold or verifier floor was touched.

### Phase 1A: report delivered

[ASK_AGENT_AUDIT_A1-A5_2026-09-30.md](ASK_AGENT_AUDIT_A1-A5_2026-09-30.md).

- **A1** authorization is enforced before ranking. No stop condition.
- **A2**, **A4** and **A5** each need owner decisions: executed/draft semantics and a
  version group, conversation-scoped user material, and an evidence-ledger table.

### Tests

- 12 new cases in `test_assist_intent.py` and `test_assist_social_turns.py`.
  - Before the fix, 6 failed: the long summary, 4 no-subject cases, and the first-turn
    service case.
  - After the fix, all pass.
- The full backend suite, run in a clean environment, gave 2,913 passed, 113 skipped,
  1 xfailed and 2 failed. Both failures were these two new documents missing from
  `docs/README.md`. They are now indexed, and that test file passes (132).
- `ruff check` and `mypy` are clean.

### Measurements

- `tools.rag_benchmark` (zero Gemini, read-only against the live database): the output is
  **byte-identical before and after**, timing fields excluded. That is 82 cases, bundle
  recall@10 0.9529, wrong-source 0.0, false admission 0.0.
- The 77-question document probe (`tools/probe_targeting.py`) **was not run**. It reads
  the persistent Tier-2 gate database, which the current role cannot read (`lmtest`
  credentials rotated). Its path, `store.search_hybrid`, does not import `intent`, so this
  change cannot move it.
- The 0.891 figure in the plan is the Gemini Tier-2 gate's recall over gate-open questions
  (`backend/tests/assist_eval/baseline.json`). It was not re-run, per the Gemini cost guard.

### Open

Phase 1B/1C need the owner's schema decision. 1D can proceed without schema.

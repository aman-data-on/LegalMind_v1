---
name: team-delivery
description: The LegalMind delivery loop for any non-trivial feature, fix batch, audit or UI page — research with official sources, a written spec with acceptance checks, build, then the same researcher re-checks; plus the role checklist and the agent brief template. Use when planning or delegating work, briefing a subagent, running a fix batch, or before calling a task done.
---

# Team delivery

Work as a complete product team. One person may play several roles; no role is skipped.

## Roles — what each one checks

| Role | Checks before "done" |
|---|---|
| Product manager | Who is the user, what job, what "done" looks like as acceptance checks; nothing the user would miss mid-journey |
| Legal-domain expert | No invented legal content (rules 7/21); RESOLVED ≠ MATCH; fail closed; positions only from ratified standards; statutes are background only |
| UX/UI designer | `.claude/rules/ui-ux.md` and the **`legalmind-ui`** skill (tokens, shared components, plain words): all states, phone, WCAG 2.2 AA, no confidence/probability language; its **never-do list** (§8) on every UI change |
| Full-stack engineer | Smallest change that fixes the class of failure; reuse existing helpers (grep first); DRY |
| QA / test engineer | One runnable check per behaviour; the commands in CLAUDE.md § Checks; skip counts; CI-shaped run for Ask |
| Security reviewer | Rule 18: auth → authz → op → DB inside every query; 404 not 403 out of scope; omit, never null, confidential fields; no secrets or client names in the repo |
| DevOps / release | Own worktree, no commit/push/deploy without the owner, migrations new-not-edited, OpenAPI snapshot, deploy notes |
| Technical writer | CHANGELOG, PROJECT_STATE, IMPLEMENTATION_STATUS, ENTERPRISE_TRACKER, docs/README.md; lock records via `lock-amendment` |

## The loop

1. **Research** (researcher agent): read the code and the records first (rule 23), then official
   or primary sources (vendor docs, standards, real products for UX, statutes from India Code).
   Output: findings ranked worst-first, each with evidence (file:line, URL) and a **Check** — the
   exact observation that proves it fixed.
2. **Spec**: write it to a file (scratchpad or the task's `audit/`/`docs/` folder) — scope, out of
   scope, acceptance checks, locks touched (as proposed amendments, never silently), owner
   questions (product/legal/security/external only).
3. **Build** (builder agent or you): fix in batches of ~5–6 findings; run the checks; report
   deviations from the spec explicitly.
4. **Re-check** (the SAME researcher, fresh context — `.claude/agents/independent-verifier.md`):
   verify each finding's Check against the built result, not against the builder's summary.
   Anything failing goes back to step 3.
5. **Record and report**: records updated; report what changed, what was verified (commands +
   results), what was skipped and why, and what needs the owner. Then wait for "commit".

UI pages add a separate critic agent after each page (`.claude/rules/ui-ux.md` § method). A UI
brief names the `legalmind-ui` skill and its never-do list (§8) as acceptance checks; the
verifier runs every check line of that list against the built result.

## Brief template (a subagent knows only what you write)

```text
Goal: <one sentence, the user outcome>
Context: <what is already known/ruled out; files and docs to read — paths, not pasted content>
Boundaries:
- Work only in <worktree path> on <branch>. Do not edit /root/Legalmind.v1 or other worktrees.
- No commit, push, PR, merge or deploy. No hooks/settings changes.
- DB <name> and ports <api>/<ui> only (skill local-stack); never --recreate another DB.
- all_lock.md append-only; no real client/counterparty names anywhere; no invented legal content.
- Paid models: none unless stated, with the estimated cost.
Acceptance checks: <numbered, each observable — a command and its expected output, a screenshot state>
Deliver: <file path for the report>; list every deviation from this brief and every check not run.
```

## Before saying "done"

- Every acceptance check run and its output seen (not inferred).
- Tried before claiming "can't" — one real probe, exact error reported.
- UI work: every item of `legalmind-ui` §7 (pre-merge checklist) and §8 (never-do list) run, with
  the evidence.
- `git status` in your worktree shows only your files; nothing committed without the owner.
- The final reply ends with a status line ("still working on X" / "waiting for next phase").

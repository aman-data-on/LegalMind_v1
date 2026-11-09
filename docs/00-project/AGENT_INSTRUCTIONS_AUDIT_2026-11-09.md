# Agent instructions audit — 2026-11-09

**Status: 📁 ANALYSIS + the record of the restructure it led to.** Decides nothing legal and
amends no lock. It reorganises the guidance agents load; every rule and decision ID that was in
`CLAUDE.md` is still reachable (verified by script, §4). The pre-restructure file is kept
verbatim at [archive/CLAUDE_MD_2026-11-09.md](archive/CLAUDE_MD_2026-11-09.md).

Official sources used (fetched 2026-11-09):

| Ref | Source | What it says that matters here |
|---|---|---|
| **[MEM]** | <https://code.claude.com/docs/en/memory> | "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence"; "if two instructions contradict each other, Claude may pick one arbitrarily"; imports "don't reduce its context cost"; `.claude/rules/*.md` with `paths:` load only when a matching file is read/edited; with both `CLAUDE.md` and `AGENTS.md` present Claude reads **`CLAUDE.md` only** unless it `@imports` `AGENTS.md`; auto memory loads "first 200 lines or 25KB"; `/doctor prompt-audit` |
| **[BP]** | <https://code.claude.com/docs/en/best-practices> | Keep CLAUDE.md to: exact test/typecheck/lint commands, misleading places, decisions not in the repo, things corrected twice. "Put team procedures in skills". "If something has to happen every time, make it a hook, a deny rule, or a managed setting. CLAUDE.md is for guidelines". "adding IMPORTANT probably won't fix it". Give Claude a check to run; review with a fresh subagent. Keep the enforced set small |
| **[SK]** | <https://code.claude.com/docs/en/skills> | `.claude/skills/<name>/SKILL.md`; `description` is always in context, body loads on invocation ("Put the key use case first", 1,536-char cap); `disable-model-invocation: true` for side-effect workflows; SKILL.md under 500 lines |
| **[SA]** | <https://code.claude.com/docs/en/sub-agents> | `.claude/agents/*.md` with `name`, `description`, `tools`, `model`; a reviewer given read-only tools is enforced by the harness |
| **[HK]** | <https://code.claude.com/docs/en/hooks-guide> | `PreToolUse` command hook reads `tool_input` JSON on stdin; exit 2 blocks and stderr goes back to Claude; deny rules hold in every permission mode |

---

## 1. Findings

Each: **where · evidence · why it hurts · fix · where the content goes.**
Line numbers are in the old `CLAUDE.md` (= the archive copy, offset +2).

### A. Size and shape

1. **CLAUDE.md is 665 lines / ~13.5k words, 3.3× the target.** · whole file · [MEM] "target under 200 lines … reduce adherence". Every unrelated task pays for UI, Ask, git-incident and config history. · **Fix:** new `CLAUDE.md` ≤ 200 lines holding only what every session needs; path-scoped detail to `.claude/rules/`; procedures to `.claude/skills/`. · **Moves:** see target map §2.
2. **"Current state" (L335–423) is a changelog, loaded every session.** · L337 is one ~2,000-word paragraph listing AB-3 → AB-25 and L1.5 → L1.15. · [BP] CLAUDE.md is for what Claude can't work out; this is history already in `all_lock.md`, [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) and `CHANGELOG.md`. It is also where the stale facts below hide. · **Fix:** drop from CLAUDE.md; the registry is the lookup. · **Moves:** verbatim in the archive; IDs are in LOCKED_DECISIONS.md (checked, §4).
3. **Narrative incidents inside rules** (2026-09-02 branch cleanup L533–537, 2026-09-04 reset L548–558, Ask Phase 1 Gemini spend L451–458). · [BP] "Keep CLAUDE.md short". The lesson is one line; the story is history. · **Fix:** keep the rule, drop the story. · **Moves:** the 09-04 story to [AGENTS.md](../../AGENTS.md) § Shared working tree; the others stay in the archive.

### B. Contradictions inside CLAUDE.md ([MEM]: "Claude may pick one arbitrarily")

4. **MSA liability position stated two ways.** · L379–383 table: `LIABILITY-MSA-001` = **12 months total fees** (reconciled `AM-43` r4); L401 owner-rulings table: "MSA = **6 months** affected-service fees". · An agent touching the evaluator could load the superseded value. · **Fix:** one statement — 12 months total fees (verified: `backend/config/company_standards/LIABILITY-MSA-001.json`); the 6-month note is labelled as the pre-`AM-43` history. · **Moves:** `.claude/rules/legal-engine-config.md`.
5. **"Two ratified standards" (L379) vs "78 active ratified Company Standards" (L407).** · `ls backend/config/company_standards/*.json` = 85 files, 7 `DEPRECATED` (`AM-65`) → 78 active. · **Fix:** say "78 active (85 files, 7 retired) — count before quoting". · **Moves:** legal-engine-config rule.
6. **"Two evaluators are specified" (L415).** · `backend/legalmind/evaluation/registry.py:3` "Exactly three evaluator types exist in V1: AM-16's two, and CATEGORICAL" (`AM-148`). · **Fix:** three evaluators. · **Moves:** legal-engine-config rule.
7. **Ask stage map says stage 6 "has never been built" and stages 2/4 "ship OFF" (L351–355).** · [ASK_TARGET_ARCHITECTURE.md](ASK_TARGET_ARCHITECTURE.md) §0 row 6: reranker "MERGED and ENABLED in production"; `AM-84`–`AM-87` (planner, broad retrieval, rerank) and the multi-source path `AM-94`/`AM-106` are live. · An Ask agent would rebuild or avoid a live stage. · **Fix:** name the stages; point to §0 and the roadmap for state; assert no state in the rule. · **Moves:** `.claude/rules/ask-rag.md`.
8. **Git: "commit straight to `main` / do not create a branch" (L518–537) vs AGENTS.md §1 "always a task branch"** — the body still says the opposite of its own banner. Also L570 struck-through "commit as soon as verified". · **Fix:** CLAUDE.md states only the current rule (task branch in your own worktree; no commit/push/PR/merge/deploy without the owner; CLM delegation of 2026-11-04). · **Moves:** CLAUDE.md § Git; detail in AGENTS.md.
9. **"Read HANDOFF.md first" (L411)** but HANDOFF.md is a point-in-time pack dated 2026-08-18 that itself says it is not current. · **Fix:** session start reads PROJECT_STATE → CHANGELOG → IMPLEMENTATION_STATUS (the greeting protocol); HANDOFF.md only as history.
10. **"Six remain open" conflicts (L419), listing C-12/13/14/17/19/28.** · [CONFLICTS.md](CONFLICTS.md) table: C-12, C-13, C-14, C-17, C-19, C-22, C-24, C-28 open = **8**. · **Fix:** point to CONFLICTS.md; never restate the count.
11. **"Approval is required for: beginning implementation" (L475)** vs `IMPL-01` authorised it on 2026-08-17 (L3). · **Fix:** drop "beginning implementation" from the list.
12. **The `IMPL-01` section's list "rules 1–22 above are unchanged" (L316)** — there are 23 rules. · **Fix:** "rules 1–23".
13. **"Product over locks" (memory, owner 2026-11-02) and the RAG-roadmap ownership (owner 2026-09-24) both amend rule 6's "ask first", but CLAUDE.md states only the RAG one.** · **Fix:** rule 6 in CLAUDE.md names both owner delegations and their shared exclusions (legal content, authorization, audit trail, zero-tolerance policy, cost guard).

13a. **"The ONLY approved Legal Rule" (L387) is stale.** · `AM-239` (2026-10-30, AB-139) added a second approved rule form (`favourable_outcome: ACCEPTABLE`) and amends `AM-33` r3 (LOCKED_DECISIONS.md rows `AM-33`, `AM-239`). An agent editing a standard would refuse or strip a valid favour form. · **Fix:** state both forms. · **Moves:** legal-engine-config rule.
13b. **UI section ranks DESIGN.md/DD-* as binding #2 (L281–287)** vs owner 2026-10-13 "DESIGN.md is not final … no need to follow" and 2026-10-28 "no restriction if you want to follow other design guidance". · **Fix:** DESIGN.md/DD are reference; CLAUDE.md rules, the three prohibitions and the never-touch list bind. · **Moves:** ui-ux rule.
13c. **RAG programme git line (L70–72)** names branch `feat/legalmind-rag-production` / worktree `rag-production` — merged and deployed 2026-09-28 (PR #121), worktree gone. · **Fix:** new Ask work on a fresh task branch. · **Moves:** ask-rag rule.
13d. **Cost guard names Gemini only (L425–460)**; since `AM-225`/`AM-249` other paid providers exist and an eval run drained the Together balance (memory, 2026-10-29). · **Fix:** the guard covers every paid model, with a cost estimate before any paid run. · **Moves:** ask-rag rule.

### C. Contradictions between files

14. **AGENTS.md §7 recommends `git stash push -u` and a backup branch with `git add -A` + commit** to "preserve" unknown work · contradicts CLAUDE.md "never stash files you did not modify", "never `git add -A`" and the no-commit rule. · **Fix:** §7 says stop and report; use your own worktree.
15. **AGENTS.md §8 "Commit checkpoints regularly"** and **§20 checklist "Branch is pushed"** contradict §13 (owner 2026-09-29: no commit/push without the owner). · **Fix:** reword both to "when the owner has said commit/push".
16. **AGENTS.md intro "add a table beyond `AM-27`'s nine"** — `AM-32`, `AM-110` and later batches added assist tables. · **Fix:** "a table not covered by a lock record".
17. **AGENTS.md "Where this supersedes CLAUDE.md"** paragraph describes the old CLAUDE.md section that no longer exists. · **Fix:** replace with one line: CLAUDE.md and AGENTS.md now agree.
18. **AGENTS.md is invisible to Claude Code.** · [MEM]: with a `CLAUDE.md` present, Claude reads `CLAUDE.md` only unless it `@imports` `AGENTS.md`. AGENTS.md is 880 lines; importing it would put CLAUDE.md far over budget ("imports … don't reduce its context cost"). · **Decision:** do **not** import. CLAUDE.md carries the git essentials (≈15 lines) and links AGENTS.md as the git/multi-agent reference; other vendors' agents still find AGENTS.md first.
19. **CLAUDE_WORKING_RULES.md** says "32 files" of standards and "Nine are open" conflicts. · **Fix:** point to the directory and CONFLICTS.md instead of counts.
20. **IMPLEMENTATION_STATUS.md L9 "Last synchronized against all_lock.md at 19,374 lines"** vs 27,678 today. · Not fixed here: that file is the only one allowed to assert build state and the sync is a records task. **Left for the owner/records session.**
21. **CONTRIBUTING.md § "Before implementation begins"** still describes the pre-`IMPL-01` world. Not fixed (locked-process doc; flagged).

### D. Memory (auto memory, outside the repo)

22. **"UI frozen 2026-08-31"** and **"Backend first, UI later" (2026-08-26)** vs later **"Enterprise-grade UI" (10-28)**, **"One page at a time" (11-03)**, **"DESIGN.md not binding" (10-13)**, **"Product over locks" (11-02)**. · **Fix:** both older files marked *superseded* with the later memory named (owner decisions kept, never deleted).
23. **"Concurrent agent in repo" recommends `git stash` to get a baseline** vs the shared-tree rule. · **Fix:** superseded note — get the baseline from a clean worktree at `origin/main` instead.
24. **Four "Pending 2026-10-xx/11-02" lists** read like live to-do lists. · **Fix:** each marked "historical snapshot — verify against ENTERPRISE_TRACKER/IMPLEMENTATION_STATUS before acting".
25. **MEMORY.md** 106 lines / 17.3 KB — inside the 200-line / 25 KB load window [MEM]; every file indexed, no dead links. Index lines updated for the superseded entries.

### E. Procedures re-explained in every brief → skills ([BP] "Put team procedures in skills")

26. **Local stack** (scratch DB, API on a spare port with a copied env, `LEGALMIND_NEXT_DIST`/`LEGALMIND_API_ORIGIN` build, Playwright via node with `--no-sandbox` because the MCP can't run Chromium as root, ports never to touch, never `--recreate` a curated e2e DB, `pkill -f` kills your shell). Spread across 4 memory files. → `.claude/skills/local-stack/`.
27. **The team loop** (researcher with official sources → written spec with acceptance checks → builder → the same researcher re-checks; batches of 5–6; separate critic for UI). Re-typed in every brief. → `.claude/skills/team-delivery/` + read-only `.claude/agents/independent-verifier.md` ([SA]).
28. **Lock amendment** (scan AM/AB IDs across main, every worktree incl. code comments, remote branches; append; registry; DAILY_CHANGED/CHANGELOG; no client names; prefix byte-identical). → `.claude/skills/lock-amendment/` with `disable-model-invocation: false` (it writes only records, never ships).
29. **"Try once before claiming you can't"** (memory 2026-11-09). → one line in CLAUDE.md § How we work.

### F. Zero-exception rules that belong in hooks/deny rules ([BP], [HK]) — **proposed only**

30. `all_lock.md` append-only · no `git add -A`/`.` · no commit/push/merge without the owner (CLM delegation excepted) · no `--update-snapshots` · no e2e `--recreate` on curated DBs · no bare `next build` in the deploy tree · no `reset --hard`/`checkout -- .`/`clean`/`stash` · never write to production ports. → [PROPOSED_HOOKS_2026-11-09.md](PROPOSED_HOOKS_2026-11-09.md). Not enabled: hooks in `.claude/settings.json` would bind every session in this repo the moment the file lands on `main`.

---

## 2. Target map

| Content (old CLAUDE.md) | New home | Loads |
|---|---|---|
| What LegalMind is, greeting protocol, team loop, check commands, rules 1–23, git essentials, traps, index | `CLAUDE.md` | every session |
| UI/UX section (L232–296) + UI memories (one page at a time, critic, enterprise bar) | `.claude/rules/ui-ux.md` | `frontend/**` |
| RAG roadmap (L44–77), ten stages (L341–373), Gemini cost guard (L425–460) | `.claude/rules/ask-rag.md` | `backend/legalmind/assist/**`, Ask tools/tests, roadmap |
| V1 configuration state (L375–417), Source material (L189–222), Preserve the examples (L224–230) | `.claude/rules/legal-engine-config.md` | `backend/config/**`, `analysis/**`, `evaluation/**`, `ingestion/**`, `tests/corpus/**` |
| Status labels (L298–312), IMPL-01 scope (L314–333), Working a session (L462–475), three traps detail, all_lock discipline | `.claude/rules/records-and-locks.md` | `all_lock.md`, `docs/**`, `CHANGELOG.md`, `CONTRIBUTING.md` |
| Testing (L477–516) | `.claude/rules/testing.md` | `backend/tests/**`, `frontend/e2e/**`, test files, `.github/workflows/**` |
| Shared working tree (L539–665) | `AGENTS.md` § Shared working tree (+ essentials in CLAUDE.md) | on demand (linked) |
| Current state history (L335–339, L411–423) | archive + LOCKED_DECISIONS.md | on demand |
| Local stack, team delivery, lock amendment | `.claude/skills/*/SKILL.md` | description always; body on demand |
| Independent review | `.claude/agents/independent-verifier.md` | on delegation |
| Hooks/deny rules | `PROPOSED_HOOKS_2026-11-09.md` | proposal only |

## 3. Left for the owner

* Enable the proposed hooks/deny rules (or a subset) — see the proposal's recommended first five.
* Sync IMPLEMENTATION_STATUS.md's `all_lock.md` line count (finding 20) and CONTRIBUTING.md's pre-`IMPL-01` section (finding 21) in a records session.
* `frontend/AGENTS.md` is regenerated by `next dev`; left untouched.

## 4. Verification (2026-11-09)

| Check | Result |
|---|---|
| New `CLAUDE.md` length | **141 lines** (was 665); largest rule 125 lines, largest skill 95 |
| Rules 1–23 present in CLAUDE.md | all 23, each with its decision IDs |
| Decision-ID coverage: IDs in the old CLAUDE.md vs new CLAUDE.md + `.claude/` + AGENTS.md + LOCKED_DECISIONS.md + CONFLICTS.md + CLAUSE_CATALOGUE.md | 266 IDs; 257 reachable. Not in those files: `AB-47`, `AB-54`, `AB-55`, `AB-56` (batch numbers present in `all_lock.md` but never given a registry row — a registry gap for a records session), `A-01`, `D-04` (benchmark question ids, in IMPLEMENTATION_STATUS.md), `DD-5` (DESIGN_DECISIONS.md), `F-12` (DECISION_FINALIZATION.md), `QA-100` (a tester-pass number). All remain in the archive |
| Relative links in every new/edited file | all resolve (the archive's links are root-relative by design, as in the original) |
| Every `paths:` glob matches at least one tracked file | yes |
| `tests/test_documentation_index.py` | 176 passed |
| Proposed hook scripts self-test | 36/36 (`guard-bash.sh`), 5/5 (`guard-all-lock.py`) |


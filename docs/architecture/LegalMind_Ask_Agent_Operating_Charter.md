# LegalMind Ask — Agent Operating Charter

**Date:** 2026-09-30 (rev 3: D10, D12, D19 updated; provider gate removed; phase-based model budget)
**Owner:** LegalMind product owner
**Applies to:** the coding agent working on Ask LegalMind
**Read with:** the Implementation Plan and Architecture v2.1 in `docs/architecture/`. Where this charter and the plan disagree, this charter wins.

---

## 1. Mission

Make Ask LegalMind behave like a real chat agent for managers: it reads what they paste or attach, remembers the thread, searches company sources and contracts, reasons over them, and answers in natural language. No dead ends. No invented authority. No invented numbers.

You own this outcome, not a task list. The owner has said what he wants. You decide how, you find what he has not noticed, and you keep going until the definition of done in section 3 is met or a hard gate in section 5 stops you.

---

## 2. How you are expected to work

Work as a senior engineer who is accountable for production quality:

- **Decide, then record.** For any decision inside section 4 or not covered by a hard gate, pick the option a strong reviewer would pick, record it in the decision log (section 7), and continue. Do not wait for approval.
- **Measure, do not assert.** Every claim of improvement has a before and after number from a named run. "No regression" is reported as that, not as improvement.
- **Find root causes.** When a test or probe fails, classify why before fixing. Fix the class, not the instance.
- **Look beyond the brief.** Actively look for problems the owner did not list: retrieval misses, security gaps, audit gaps, cost, latency, Hinglish quality, confusing UI text, dead code you introduced, docs that now contradict the code. Fix them when they serve the mission and pass the gates. Log each as a `PROACTIVE` entry.
- **Review your own work.** Before each commit, reread the diff as a strict reviewer. Before each phase exit, try to break what you built (bad input, wrong-source questions, injection, empty results, timeouts).
- **Never weaken a check to pass.** Do not delete tests, loosen assertions, lower thresholds or skip cases unless a decision entry explains why and what replaces the protection.
- **When stuck,** try up to three distinct approaches. If still blocked, record what you tried and why it failed, move to the next backlog item, and return later.

---

## 3. Definition of done

Done means all of the following, measured and recorded:

1. Implementation Plan phases 0–4 meet their exit criteria, with Phase 3 and 4 running in **shadow mode**.
2. All ten manager behaviours in the Implementation Plan section 4 pass in shadow, on real documents.
3. Acceptance metrics in the Implementation Plan section 8 are met, with the gate corrections in section 4 of this charter.
4. Document retrieval on the real-document probe has a recorded baseline, a miss analysis, and improvements that are measured, not assumed.
5. `STATUS.md` shows every phase, open risk and pending owner action accurately.
6. A final handoff report exists (section 8).

Turning agent mode on for real users is Phase 5 and is a hard gate. You prepare it. You do not do it.

---

## 4. Decisions (owner, 2026-09-30)

These add to or replace earlier decisions D1–D9 in the Implementation Plan.

| ID | Decision | Reason |
|---|---|---|
| D10 | **Real documents are approved for testing.** Use the documents in the shared Drive folder `legal docs from clients` and the other company contracts, SLAs and emails in Drive for the probe corpus, ingestion tests and shadow evaluation. Fetch them yourself from Drive using the access available on the server. Do not wait for the owner to provide them | Synthetic fixtures cannot show real table layouts, web-print noise, broken cross-references or party-name issues. The goal is behaviour on real documents |
| D11 | **Handling real documents.** Keep them outside the repo, in `/root/.legalmind/test-corpus/` (mode 700, files 600). Use only the scratch test database. Never commit them or excerpts of them. Commit scripts, expected-answer keys and metrics only. Logs and reports contain IDs, hashes and clause numbers, not client text | The documents are already processed by LegalMind. The risk is copies spreading, not reading |
| D12 | **Party names and client material may go to the model provider.** Pseudonymisation is not required. Provider terms are not a blocker for any phase, including Phase 5. Gemini is the default. Another provider may be added behind the provider adapter when measurements justify it. Record the provider, model and version of every call in the audit row. Draft the amendment to `AM-30 t4` accordingly | Owner decision. A contract cannot be analysed without its parties. The audit record of each call keeps egress visible |
| D13 | **Locked-decision amendments are approved by the owner:** `AM-58` / `AM-30 t2` (earlier answers in context), `AM-25 r5` (labelled uncited general answers), `AM-30 t3` (client material to Gemini), `AM-30 t4` (party names). Write them in the project's format, marked approved by the owner on 2026-09-30, in the same change that relies on them | Behaviour and decision log must not contradict each other |
| D14 | **Migrations:** write the new tables (attachments, evidence ledger, and any metadata gaps from A2) as additive, reversible migrations. Apply freely to the scratch test database. Applying to staging or production is a hard gate | Speed on scratch, safety on shared data |
| D15 | **Cross-page clauses (1.10):** implement read-time neighbour expansion. The index entry stays tied to one stored block; when a chunk ends mid-sentence, the next block is included as context and both are cited | Keeps the 2026-09-10 one-block ruling and fixes split clauses |
| D16 | **Re-indexing** is allowed on scratch copies at any time. Re-indexing the live index is a hard gate. Batch chunker changes so the live index is rebuilt once, with the old index kept for rollback | One controlled rebuild, reversible |
| D17 | **Phases:** you may move from Phase 1 through Phase 4 without waiting, as each phase meets its exit criteria and the phase report is written. Phase 5 is a hard gate | The owner does not want to approve every step |
| D18 | **Regression gates:** (a) zero-Gemini golden benchmark on every commit, no change to recall@10, wrong-source or false-admission; (b) private-corpus document probe on every ingestion or retrieval change, no drop in recall@10, hit@1 or MRR; (c) the Gemini-backed figure only at phase exits, inside the budget | The golden benchmark cannot see chunker changes. The probe can |
| D19 | **Model budget for evaluation**, read from config: `ASK_EVAL_MODEL_DAILY_CALL_CAP` (all providers combined) and `ASK_EVAL_MODEL_RUN_CALL_CAP` (one evaluation run). Phases 0–2: 100 calls per day. Phases 3–4: 1,000 calls per day, 450 per full run. Spend on the highest-value runs first (phase-exit checks, then the chats most likely to fail). Run the cheap subset (failing and changed cases) while tuning, and the full set only at checkpoints. When the cap limits a phase, do not stop: finish zero-model work, record in `STATUS.md` how many calls the phase needs, and continue the next day. Record calls used per run in `EVALS.md` | A full run of about 130 turns at about 3 calls per turn is about 400 calls. 1,000 per day allows two full runs plus tuning. The cap paces model-backed runs and never blocks progress |
| D20 | **Remote git:** you may push your feature branches to the remote for backup. You may not merge to `main`, rebase shared branches, or rewrite history | Work is safe from loss; main stays reviewed |

---

## 5. Hard gates (stop and ask)

Provider terms, document availability and the model budget are not hard gates. Stop only for these. For each, write the question in `STATUS.md` under *Owner actions*, state your recommendation, and continue with other backlog work while you wait.

1. Any write to the production or staging database, including migrations.
2. Re-indexing the live index.
3. Deploying, restarting production services, or changing production config.
4. Merging to `main`, rewriting git history, or force-pushing.
5. Turning agent mode on for any real user (`ASK_AGENT_MODE = on`).
6. Deleting or overwriting data you did not create.
7. Changing a locked decision other than those listed in D13.
8. Anything that exposes secrets or client documents outside the paths in D11 and the model calls allowed by D12.

---

## 6. Current backlog (start here, in this order)

1. Fetch the real documents from Drive into the test corpus (D10, D11). If Drive access fails, record the error and the exact access you need in *Owner actions*, and continue with items that do not need the documents.
2. Commit the private-corpus probe script and its expected-answer keys. Rebuild the baseline on the real corpus.
3. Classify every probe miss by cause (chunking, cross-page split, table, embedding, wording, metadata). Report counts. Fix the largest class first.
4. Verify 1.9 (tables) and 1.10 (web navigation noise, cross-page joining) on the real SLA and contract files.
5. Minimum-page guard for the repeating-heading rule, with 2–4 page contract fixtures.
6. Confirm the A1 test covers search candidate selection and a second role. Confirm the test env file is mode 600 outside the repo. Add a test that the test role cannot read live tables.
7. Define who may declare a document executed, audit that action, and default to draft.
8. Scan the full git history of every local branch for client names. Record the result. Do not rewrite history (hard gate 4).
9. Migrations and build of 1B / 1C on scratch (D14). Then 1.13 near-duplicates and 1.14 marking.
10. Rescue Gemini call recorded in the request's audit row.
11. Lock amendments (D13).
12. Phase 2, 3, 4 per the plan (D17).

Add items you discover. Keep the backlog in `STATUS.md`, not in your head.

---

## 7. Documentation (mandatory)

Extend the existing files instead of creating parallel ones. All times are IST, ISO 8601 (`2026-09-30T18:40+05:30`).

| File | What | When |
|---|---|---|
| `docs/architecture/ask-agent/STATUS.md` | Phase board, backlog, blocked items, open risks, owner actions with your recommendation, last updated time | After every work session and every phase exit. It must let a new session resume without asking anything |
| `docs/architecture/IMPLEMENTATION_LOG.md` | Timestamped entries: what you did, why, commits, results, next step. Tag entries `FIX`, `FEATURE`, `PROACTIVE`, `MEASURE`, `BLOCKED` | Every meaningful step |
| `docs/architecture/ask-agent/DECISIONS.md` | One entry per decision you make: ID, date and time, context, options considered, choice, reason, reversibility, owner-approved or agent-decided | Every decision |
| `docs/architecture/ask-agent/EVALS.md` | One row per measured run: date and time, commit, benchmark or probe, corpus version, metrics, notes | Every run |

Entry format for the log:

```text
### 2026-09-30T18:40+05:30 — FIX — Minimum-page guard for repeating headings
What: added page-count guard to header/footer detection in chunking.py.
Why: 40% page-share rule could strip a real heading in a 2–4 page contract.
Commits: <sha>
Tests: 6 new, failing before, passing after. Full suite: <n> passed, 0 failed.
Measured: probe recall@10 0.6562 → 0.6562 (no regression). EVALS row 14.
Next: classify probe misses.
```

Rules:

- Never claim a test passed unless you ran it. Include the command in the log.
- Record failures and dead ends too. They save the next session time.
- No client text in any document. Clause numbers and IDs only.

---

## 8. Reports

- **Phase exit report** (in `IMPLEMENTATION_LOG.md` and summarised in `STATUS.md`): summary, files changed and why, tests, measurements before and after, decisions made, proactive changes, risks, next phase.
- **Owner summary** at each phase exit, in plain language, five lines or fewer, then the owner actions list.
- **Final handoff** when section 3 is met: what was built, what was measured, what is still weak, what Phase 5 needs, and your recommendation for go or no-go.

---

## 9. Engineering rules

Unchanged from the Implementation Plan section 3: reuse existing utilities, smallest correct change, match the codebase, no secrets in code, validate input, parameterised queries, no personal data or client text in logs, never swallow errors, run lint, format and the full test suite before each phase exit.
# Ask agent — Phase 1 exit report (2026-10-01)

Branch `feat/ask-agent-phase0-1`, worktree `/root/legalmind-worktrees/ask-agent-p0`. Local
commits only; nothing pushed, merged or deployed. Everything new is behind
`LEGALMIND_ASK_ATTACHMENTS` (default **off**).

## Owner summary

1. **Completed:** audit A1–A5; long paste → attachment; `.txt`/`.md`/`.pdf`/`.docx` chat
   files with status; material searched and labelled as the reader's; 30-day retention
   that actually runs; evidence ledger with keys per answer and live re-fetch
   (`current`/`stale`/`unavailable`); ingestion 1.9–1.15; cross-page clauses (D15). Locks
   `AM-110` (tables) and `AM-114` (material to Gemini on the normal path, flag on).
2. **Measured:** Tier-2 recall@10 **0.922** (bar 0.891), wrongly answered **0/13**;
   golden benchmark unchanged (0.9529, wrong-source 0, false admission 0); real-corpus
   probe unchanged (recall@10 0.9982); live G1 and G4 **pass**; full suite green.
3. **Phase exit status:** **MET**, with two recorded caveats (below).
4. **Remaining weakness:** the generated half of the Tier-2 gate measured 57 of 77
   questions (the call cap stopped it), faithfulness 0.864; and one live answer
   attributed the customer's request to "you" — an attribution check is Phase 4 (V6).
5. **Next phase:** Phase 2 — the tool layer (`search_knowledge`, `get_evidence`, …)
   wrapping today's retrieval under the caller's permissions, zero Gemini until its exit.

## Exit criteria

| Criterion (plan §6) | Result | Evidence |
|---|---|---|
| Audit report delivered and reviewed | met | `ASK_AGENT_AUDIT_A1-A5_2026-09-30.md`; owner decisions A2/A4/A5 |
| Long paste accepted, saved, used in the answer (G1, current path) | met | live G1 PASS (EVALS #21); tests `test_on_a_long_paste_…`, `test_a_question_about_pasted_material_…` |
| `.txt` upload shows status and can be asked about (G4) | met | live G4 PASS; `test_on_a_long_paste_is_saved_and_a_text_file_shows_its_status` |
| Ledger IDs exist and are stored for each answer | met | `test_an_answer_stores_its_ledger_keys_…`; every answered turn, every path |
| Ingestion 1.9–1.15 | met | EVALS #10–#15, #19 on the private real corpus (32 documents) — measured corpus-wide, not mapped one by one to the test pack's D1–D5 labels |
| Existing tests pass | met | full suite, see STATUS |
| Golden benchmark meets the D9 per-commit gate | met | EVALS #17 |
| Tier-2 gate ≥ 0.891, under a cost cap | met (retrieval); generated half partial | EVALS #20: recall@10 0.922; 57/77 generated within the 109-call cap |

## Caveats, stated plainly

- **Generated half partial.** Faithfulness and citation precision (0.864) cover 57 of 77
  questions; the remaining 20 were not measured, by design of the cap. A full generated
  run needs about 140 calls (33 rescue + ~1.4 per question).
- **Baseline not comparable.** The gate tool reports the dataset hash differs from the
  recorded baseline. Re-baselining is a deliberate, reviewable act and was not done here.

## Defects found and fixed during the exit

| Found by | Defect | Fix |
|---|---|---|
| full suite | assist lane imported `ingestion` (locked layering) | parsing moved to the API layer (A-18) |
| full suite | two new routes missing from the permission map / OpenAPI snapshot | mapped (`assist.ask`), snapshot regenerated |
| owner check | nothing ran the 30-day purge | purge on every new attachment + daily timer (not installed) |
| live G1 | pasted text said as "The contract" | own claim kind `MATERIAL` (A-17) |
| live G1 | a self-repeating paste cited one sentence six times | identical text stored once (A-21) |
| live G1 | a two-part question lost its second clause; the answer claimed it was absent | later parts anchor on their own clause (A-20; document-lane benchmark identical) |
| D15 scan | a table-of-contents line read as a run-on | excluded (EVALS #19) |

## Owner actions

1. **Decide the UI exception for attachment status** before Phase 5 (UI frozen; the API
   returns status today).
2. **When turning `LEGALMIND_ASK_ATTACHMENTS` on in production:** install
   `ops/production/legalmind-attachment-purge.{service,timer}` in the same change, and
   apply migration `a9e4c2f7b1d3` first (both are hard gates).
3. **Optional:** approve a one-off budget for the 20 unmeasured generated questions
   (about 30 calls), or accept the 57-question measurement.
4. **Optional:** decide whether to re-baseline the Tier-2 gate on the current dataset.

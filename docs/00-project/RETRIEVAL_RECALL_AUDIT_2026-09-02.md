# Retrieval Recall Audit (E1) — 2026-09-02

**Status:** 📁 ANALYSIS — records the owner-authorized E1 investigation ("D1 APPROVED —
proceed with E1", 2026-09-02). Decides nothing. Any outcome lands in `all_lock.md`,
`LOCKED_DECISIONS.md`, `CHANGELOG.md` and code — never here.

**Scope granted:** investigate and fix the hybrid retrieval *fusion*, under ten
constraints, of which #2, #3 and #5 forbid touching `COSINE_FLOOR`, `PEAK_MARGIN` and
the refusal thresholds, and #10 requires measuring rather than predicting the result.

> **Verdict up front: fusion is not the cause, and E1 as scoped is a no-op.**
> The authorized change recovers **0.000** recall. The entire gap is one calibration
> constant applied at two points, both of which the same instruction placed out of
> scope. **No production code, threshold, gate or model was changed.** The remedy needs
> an owner calibration decision, which is what this document is for.

All numbers below are measured on the owner-ratified evaluation set (decision #126) —
unchanged, per constraint #6 — 64 answerable questions plus 13 unanswerable, `top_k = 10`.
The harness lives outside the repository (investigation only) and recomputes the real
`gate_is_open` from the real vector scores for every variant, so no variant is compared
against a differently-gated baseline.

---

## A · Root cause of the 0.438 hybrid recall

**`COSINE_FLOOR = 0.50` is applied at two separate points in the answer path, and
together they account for the whole gap. Reciprocal rank fusion accounts for none of it.**

| # | Where | Code | Effect |
|---|---|---|---|
| 1 | the **refusal decision** | `calibration.gate_is_open()` — requires vector top `>= COSINE_FLOOR` **and** peak separation `>= PEAK_MARGIN` | closes the gate; `search_hybrid` then returns `hits=[]` |
| 2 | the **per-hit evidence filter** | `store.search_hybrid` — `if float(r[7]) >= COSINE_FLOOR` prunes individual vector candidates | drops correct chunks from the evidence list *after* the decision to answer |

A third, contributing condition makes point 1 rest entirely on the vector score:

**The lexical branch is inert on this corpus — 1/64 = 0.016 alone.** It contributes no
unique recall. Consequently `gate_is_open`'s `if lexical_hit: return True` short-circuit
effectively never fires, and the gate decision rests wholly on the vector top score
clearing the floor by the margin.

**Why this is a calibration mismatch rather than a bug.** MiniLM's cosine scores are
compressed on this corpus — the architecture record measures answerable median **0.539**
against unanswerable **0.416**. A 0.50 floor therefore cuts through the *middle* of the
answerable distribution, not below it. A correct chunk sitting at 0.45 is ordinary for
this model. The floor was calibrated as a *refusal* control and behaves correctly as one;
its cost is that the same number also governs what may be *shown* as evidence.

---

## B · Diagnostic evidence

### B.1 The decisive measurement — the 2×2 over both applications

|  | per-hit floor **ON** | per-hit floor **OFF** |
|---|---|---|
| gate **ON** | **0.438 — SHIPPED** | 0.625 |
| gate **OFF** | 0.453 | **0.938 — the vector ceiling** |

Three readings, only the first of which was anticipated:

1. **Fusion loses nothing — proved, not inferred.** The bottom-right cell is 60/64,
   *bit-identical* to the vector branch measured alone. With neither threshold applied,
   RRF over lexical + vector reproduces the `AM-26` r2 ceiling exactly. No correct chunk
   is displaced out of the top 10 by fusion, by the lexical branch, or by truncation.
2. **The two applications are super-additive, so neither alone is a fix.** Floor only
   **+0.188**; gate only **+0.016**; both **+0.500**. They are not independent causes to
   be added, because they are one constant read twice: when the gate closes on vector
   grounds the top score is already below 0.50, so the per-hit filter has emptied the
   vector branch regardless. Relax either alone and the other still blocks.
3. **`hit@1` is 0.281 in every cell.** Neither threshold, and no fusion variant tested,
   changes which chunk ranks first — further evidence that ranking is not the problem.

`gate OFF` is a **measurement construct** used to attribute the loss. It is not a
proposal. Refusing correctly is a safety property, not a defect.

### B.2 Branch isolation, identical candidates, top-10

| branch | recall@10 |
|---|---|
| lexical alone | 1/64 = **0.016** |
| vector alone | 60/64 = **0.938** |
| RRF of both, no thresholds | 60/64 = **0.938** |
| shipped `search_hybrid` | 28/64 = **0.438** |

### B.3 Per-question inspection of the losses (TODO 1)

For every lost question, the fusion-specific diagnostics were empty: **zero fusion
displacements**, and `lexRank = None` for all 13 examined — the lexical branch had not
retrieved the chunk at all, so it had no rank with which to outrank anything.

---

## C · Experiments performed

All measured on identical cached candidates so differences are attributable to the
manipulated variable alone.

| # | Experiment | TODO | Outcome |
|---|---|---|---|
| 1 | per-question loss diagnostics: vector rank, lexical rank, RRF score, fused rank | 1 | no displacement; lexical absent |
| 2 | branch isolation (lexical / vector / fused) | 1 | §B.2 |
| 3 | deeper candidate pools, final `limit` preserved | 2 | §D |
| 4 | vector branch weighting | 3 | §E |
| 5 | lexical candidate cap, including full exclusion | 4 | §F |
| 6 | the 2×2 over both `COSINE_FLOOR` applications | — | §B.1 |
| 7 | full `AM-28` Tier-2 gate re-run after every repo edit | 6 | §J–§M |

---

## D · Candidate-pool results (TODO 2)

The observation in the instruction was correct as a reading of the code — both branches
retrieve `limit` candidates and the fused result is truncated back to `limit` — but it is
not the cause. Deeper pools barely move recall and **make refusal behaviour worse**.

| depth | recall@10 | retained | wrongly answered | correct refusals |
|---|---|---|---|---|
| 10 (shipped) | 0.438 | 41 | 1 | 12 |
| 50, floor ON | 0.453 | 42 | **2** | 11 |
| 20, floor OFF, `w_vec=5` | 0.641 | 42 | **2** | 11 |
| 50, floor OFF, `w_vec=5` | 0.641 | 42 | **2** | 11 |

**+0.016 recall for one additional wrongly-answered unanswerable question.** Depth widens
the candidate list enough for a marginal chunk to clear the gate on a question that should
be refused. Rejected: it trades a locked safety property for noise.

---

## E · Fusion-weight results (TODO 3)

| `w_vec` | floor OFF, depth 10 | recall@10 | hit@1 | retained | wrong | refusals |
|---|---|---|---|---|---|---|
| 1 (shipped) | | 0.625 | 0.281 | 41 | 1 | 12 |
| 2 | | 0.625 | 0.281 | 41 | 1 | 12 |
| 5 | | 0.625 | 0.281 | 41 | 1 | 12 |
| 20 | | 0.625 | 0.281 | 41 | 1 | 12 |

**Weighting changes nothing, at any weight, on any metric.** Expected once §B.2 is known:
weighting re-ranks *between* branches, and the lexical branch has nothing to down-weight.
No weight was selected. Nothing was overfitted to individual questions because nothing
moved.

---

## F · Lexical-floor results (TODO 4)

| `lex_cap` | floor OFF, depth 10 | recall@10 | hit@1 | retained | wrong | refusals |
|---|---|---|---|---|---|---|
| unbounded (shipped) | | 0.625 | 0.281 | 41 | 1 | 12 |
| 5 | | 0.625 | 0.281 | 41 | 1 | 12 |
| 3 | | 0.625 | 0.281 | 41 | 1 | 12 |
| 0 — lexical excluded entirely | | 0.625 | 0.281 | 41 | 1 | 12 |

**A lexical quality floor is neither harmful nor useful, and was correctly not added
automatically** (TODO 4's own caution). Removing the lexical branch *outright* changes no
metric, which is the strongest available statement that lexical candidates are not
crowding out vector evidence.

One consequence worth recording for a future decision: since the branch is inert here,
`search_hybrid`'s hybrid character is currently *nominal* on this corpus. That is a
property of these 12 documents and this question set, not a reason to remove a locked
component — a lexical branch earns its place on exact-wording and citation-style queries
that this evaluation set may under-represent.

---

## G · Final selected implementation

**None. No production file was changed.**

The smallest evidence-supported change that materially restores retrieval quality is a
change to `COSINE_FLOOR`'s two applications. Constraints #2, #3 and #5 forbid it. TODO 5
asks for the least-complex *evidence-supported* solution; the evidence supports no
in-scope solution, so the honest output of TODO 5 is a decision request, not a patch.
Constraint #10 forbids claiming success from an expected number, and there is no
authorized change whose measured result is anything but 0.000.

Two repository files were changed, both records rather than behaviour:

| File | Change |
|---|---|
| `backend/tests/test_assist_retrieval_fusion.py` | root cause corrected twice (§P.2); xfail preserved and still strict |
| `frontend/e2e/visual.spec.ts-snapshots/workspace-chromium-linux.png` | stale baseline adopted from CI after the verified workspace redesign |

### G.1 For the owner's decision — what the measurement does and does not license

The two applications of `COSINE_FLOOR` serve **different purposes**, and only one of them
is a refusal control:

* **Application 1, the gate** — decides *whether to answer*. This is a genuine
  recall/refusal trade. Relaxing it means answering questions the system currently
  declines, and it is worth only **+0.016** alone. **No case is made for changing it.**
* **Application 2, the per-hit filter** — decides *what evidence may be shown*, and runs
  **after** the decision to answer is already made. `gate_is_open` reads the **raw**
  vector scores and is untouched by it, so relaxing it alters no refusal.

Measured for application 2 alone: recall **0.438 → 0.625**, with `retained` 41,
`wrongly answered` 1, `correct refusals` 12 and `hit@1` 0.281 **all unchanged**.

**The honest limit of that measurement, stated plainly:** those four are *retrieval and
refusal* metrics. **Faithfulness, citation precision and user-visible wrong answers were
NOT re-measured with the filter relaxed**, and they plausibly could move — a longer
evidence list changes what generation sees, and admitting chunks at 0.35–0.50 admits
weaker evidence into the prompt. So this is **not** a zero-cost change, and it must not be
presented as one. It is a candidate whose safety cost is **unmeasured**, and measuring it
requires the full Tier-2 gate run that only an authorized change justifies.

Whether separating one constant into two named constants is a *weakening of a refusal
threshold* (constraint #2/#5) or a *disambiguation of two distinct uses* is a decision for
the owner. An audit should not settle that by choosing the reading that lets it ship a fix.

---

## H–M · Before vs after

No implementation was selected, so every quantity is unchanged **by construction**, not
by luck. Re-measured after the two record-only edits to confirm exactly that.

| | Before | After | Source |
|---|---|---|---|
| **H** · recall@10 | 0.438 | 0.438 | `AM-28` gate |
| **I** · hit@1 | 0.281 | 0.281 | harness |
| **J** · faithfulness | 1.0 | 1.0 | `AM-28` gate, 71 claims over 27 answers |
| **K** · citation precision | 1.0 | 1.0 | `AM-28` gate |
| **L** · user-visible wrong answers | 0/13 | 0/13 | `AM-28` gate |
| **M** · refusal behaviour | retained 41 · wrongly answered 1 · correct refusals 12 | identical | `AM-28` gate |

`AM-28` verdict: **SHIPPABLE** — all four quantities it names measured and held.

---

## N · Tests and checks passed

| Check | Result |
|---|---|
| backend suite | **1093 passed, 1 skipped, 1 xfailed** |
| `ruff` (`legalmind`, `tests`, `tools`) | clean for this work |
| `mypy legalmind` | no issues, 103 source files |
| `AM-28` Tier-2 gate | SHIPPABLE, every threshold held |
| CI job 1 · lint and type check | pass |
| CI job 10 · Playwright browser workflows | pass |
| CI job 11 · post-migration reproducibility | pass |
| CI job 12 · invariants without their tests | pass |
| CI job 13 · whole suite (release gate) | pass |
| CI job 15 · design QA | forbidden terms clean; one stale visual baseline, corrected (§P.3) |

**Ask path verified end to end, as TODO 9 requires** — `AskBar` → `askIntent` →
`api.ts` → `routers/assist.py:270` → `service.ask` → `store.search_hybrid` (`service.py:228`)
→ evidence gate → `generation.generate` (`:248`) → `guardrails.verify_answer` (`:279`) →
`_persist_citations` (`:296`). Intact; the `AM-28` faithfulness and citation figures above
are produced through this path, not a test double.

---

## O · Did the strict xfail XPASS?

**No — it still xfails, which is the correct outcome.** Shipped recall is 0.438 against
the 0.938 basis; the regression it pins is real and unfixed. It was **not** deleted,
weakened, or made non-strict (TODO 7). It will XPASS and fail the run the moment recall
reaches the calibrated basis, which is the prompt to re-run the Tier-2 gate and
re-baseline.

Two guard tests were added beside it, and they **pass**, pinning the *diagnosis* so a
future reader cannot re-derive "it must be fusion" from the headline numbers — the mistake
this file already made once:

* `test_fusion_reproduces_the_vector_ceiling_when_no_threshold_is_applied`
* `test_neither_threshold_application_is_a_fix_on_its_own`

---

## P · Was a re-baseline performed?

**No.** TODO 8 permits one only after an implementation is accepted and proven. None was.
`AM-26`'s original 60/64 vector result stands untouched and historically visible, and no
calibration record was rewritten.

### P.1 What was corrected instead

The record itself was wrong and is now fixed. Both corrections are in the git history with
their measurements, not silently amended.

### P.2 Two published root causes retracted — both mine

| Claim | Published in | Status |
|---|---|---|
| "RRF fusion displaces correct chunks" | commit `612c148` + the xfail docstring | **WRONG.** Measured displacement: **0**. |
| "the refusal gate is worth +0.312 on its own" | commit `23fb976` | **WRONG.** Measured: **+0.016**. |

**How each error happened**, because the method matters more than the number:

1. The fusion claim came from an "ungated" arm that read `search_hybrid`'s *returned
   hits* — which are empty whenever the gate closes. Every refused question therefore
   scored as a retrieval miss, and the residual looked like fusion. Measuring the raw
   vector branch separates refusal from retrieval.
2. The +0.312 came from assigning each lost question to whichever check fired *first*.
   That measures blame order, not recoverability. The 2×2 measures recoverability
   directly, and it is what should be trusted.

Corrected in commits `23fb976` and `ef06eb2`.

### P.3 One unrelated defect found and fixed en route

CI job 15 failed on `workspace.png` (38,563 px, 4%). Forbidden terms were clean and every
other baseline matched. Verified before adopting rather than adopted to turn CI green: the
diff is entirely the intended workspace redesign — framed document pane, relocated zoom
controls, bounded scrolling right rail. One apparent absence was checked and cleared:
`KEY OBLIGATIONS` no longer appears in the shot, but `AnalysisPanel.tsx:81` still renders
`ObligationsPanel` unconditionally — the rail now scrolls internally, so the section sits
below the fold of a viewport-only screenshot. A scroll position, not a removal. Baseline
taken from the CI artifact, never a local `--update-snapshots` run.

---

## Q · Remaining blockers

| # | Blocker | Owner action |
|---|---|---|
| 1 | **`COSINE_FLOOR`'s dual role.** Recovering the 0.5 recall gap requires changing it. Whether relaxing only the *per-hit evidence filter* (§G.1) counts as weakening a refusal threshold is a locked-calibration question this audit must not decide. | Decide. If relaxing the filter is authorized, the safety cost is **unmeasured** and a full Tier-2 gate run must gate the change. |
| 2 | **`C-17`** — `AM-30` t10 versus 47.1.3's mandatory IdP egress. Open from the prior audit. | Decide. |
| 3 | **Two secrets were pasted into chat** and must be rotated: the Google OAuth client secret and the Gemini API key. | Rotate. |
| 4 | The evaluation set may under-represent exact-wording queries, on which the lexical branch would earn its keep (§F). Not a defect and blocking nothing. | Note only. |

**Not reported as fixed.** Recall did not increase, because nothing was changed. Per
constraint #10, the measured result of the authorized change is **+0.000**, and that is
the finding.

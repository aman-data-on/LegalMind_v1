# The assist lane — retrieval, generation and the guardrails around them

> **Status: 📁 DERIVED — the assistive lane as built.** It decides nothing. Every rule it describes
> is locked in `all_lock.md` (`AM-25`–`AM-32`, `AM-44`–`AM-49`, `AM-54`, `AM-58`, `AM-60`) and
> indexed in [LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md); where this file and a lock
> record disagree, the record wins and the discrepancy is reported (rule 5). Build state is
> [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md)'s alone.

Written 2026-09-14 because the lane had no prose home: it was specified only inside lock records
and readable only by reading the code.

---

## 1. What the lane may and may not do

`AM-25` put an assistive lane in V1 scope on nine terms. The load-bearing ones:

* It **never** produces a Finding, Evaluation, Classification, Rule Outcome, Mapping State, Legal
  Decision or Lifecycle transition, and never writes to a legal or configuration table.
* It **never** states an organizational legal position that is not already in a ratified Company
  Standard, a published Legal Rule or an approved template.
* It **never** answers *"does this document meet our standard?"* — that question routes to the
  evaluator and returns the evaluator's own Finding.
* It makes **no determinism claim** (`AM-28`) and is never admitted to the authoritative lane's
  determinism guarantee.

One narrow exception runs the other way: since `AM-54`/`AM-60` the *authoritative* lane may use the
embedding model and the same egress seam for **recognition** — which clause addresses which
Requirement, and what quantity it states — on a verbatim span. That is described in
[APPLICABILITY.md](../04-analysis-engine/APPLICABILITY.md) and in `AM-54`, not here.

---

## 2. Three domains, never merged

`AM-32` fixes three retrieval domains. They are searched in a fixed order and their results are
never blended into one list:

| Domain | Corpus | Permission | Output |
|---|---|---|---|
| **DOCUMENT** | chunks of the uploaded document's own evidence rows | `assist.ask` + document scope | cited answer |
| **A — POSITIONS** | ratified Company Standards, chunked verbatim | `assist.ask` AND (`configuration.view` OR `legal_position.view`) — `AM-44` | **extractive only**: quoted verbatim with its standard code and source clause, never sent to the model |
| **C — STATUTES** | the Indian statute corpus, chunked by section | `assist.ask` | quoted section |

Routing (`AM-45`) is by **question shape**, computed deterministically with no model: token stems
decide whether a question is a comparison, a statute question, a verdict statement or a follow-up.
There is no source selector in the UI and never will be. A question the router sends to the
evaluator returns the evaluator's route text, not generated prose.

Every non-answer — closed gate, insufficient evidence, refused generation, unavailable provider,
failed verification, verdict statement — converges on the same fallback consultation of every other
authorized source before any refusal, and every refusal uses one wording per candidate set.

---

## 3. Retrieval, and the two floors

Both branches run and are fused; neither alone decides.

* **Lexical** — Postgres full-text. The document branch's calibrated AND-match is the signal that
  opens the gate; a broader OR-match supplies further candidates *after* the gate, as evidence only.
* **Vector** — pgvector cosine over chunk embeddings from a **local, self-hosted** model
  (`AM-26`): `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, pinned by revision. No
  embedding leaves the machine.
* **Fusion** — reciprocal rank fusion, `calibration.RRF_K = 60`, one constant for all three domains.
  Scores shown to callers stay branch-native: an RRF sum is a rank artefact and would read as
  meaning.

Two separate constants, deliberately (separated 2026-09-02 — "two responsibilities, two constants"):

| Constant | Value | Responsibility |
|---|---|---|
| `COSINE_FLOOR` | 0.50 | the **refusal gate** — may this question be answered at all |
| `PEAK_MARGIN` | 0.059 | the gate's peak test: top score against the mean of the rest |
| `EVIDENCE_COSINE_FLOOR` | 0.50 | the **per-hit prune** — may this chunk be cited |
| `RETRIEVAL_TOP_K` | 10 | candidates per branch |

Every measured value lives in `backend/legalmind/assist/calibration.py`, whose docstring records
that *"nothing in this module is a preference"*. The floors are a safety control: weakening one to
improve recall is a decision with a recorded cost, not a tuning knob.

**Known limitation, measured and recorded**: at these settings recall@10 is **0.891** against a
measured vector ceiling of 0.938. Of 64 answerable questions **3** are refused for want of
evidence and **0** are misrouted to the deterministic evaluator (**7** were, until
`is_comparison_question` was rebuilt on 2026-09-16 around a position REFERENCE rather than a
co-occurring organization-flavoured word). Nothing
that has been answered has been wrong (faithfulness 1.0, citation precision 1.0, 0 wrong answers
reaching a user; 1 of 13 unanswerable questions opens the retrieval gate and none survives to a
reader).

> Re-measured 2026-09-16, and the figure below it is not comparable to the 0.625 this
> paragraph carried before. That number came from a gate that called `store.search_hybrid`
> and stopped — no routing, no evidence rescue, no sufficiency screen — so it measured a
> pipeline that had not shipped since the rescue landed. Through the production path the
> same dataset reads **0.797**; with the rescue unreachable it reads **0.547**. The three
> steps move it in both directions, which is why the old number was not a worse measurement
> of the same quantity but a measurement of something else. The **7** evaluator-routed
> questions were a defect in `is_comparison_question`, not a retrieval miss; fixed the same
> day, taking recall to **0.891** (0.906 on a second run of the identical build — the rescue judge picks which chunks reopen the gate, so this line is not
> deterministic; every blocking quantity was identical in both) with the
> wrongly-answered rate unmoved. See the CHANGELOG
> entries for 2026-09-16.

> Corrected 2026-09-15. This paragraph read *"0.438 … 23 of 64"* — the figures from the
> 2026-09-02 audit — and was written on 2026-09-14, the same day the number moved. Recall
> reached 0.625 on 2026-09-10 via chunk hygiene and the heading redirect, and
> `assist_eval/baseline.json` has recorded `recall_at_10 0.625` / `false_refusals 21` since
> 2026-09-14, with `test_assist_retrieval_fusion.py` pinning `SHIPPED_RECALL_AT_10 = 0.625`.
> The audit's *recommendation* — relax `EVIDENCE_COSINE_FLOOR` alone — was never taken; the
> gain arrived by a different route. **Its diagnosis of the remaining 0.625 → 0.938 gap has
> not been re-measured since the pipeline changed, so the floors may no longer be the whole
> story.** Note also that faithfulness 1.0 is scored on the 33 answers that reach generation,
> not on the 64 answerable questions: the 21 false refusals never reach the model, so the
> figure describes the answerable half only. The full analysis
is [RETRIEVAL_RECALL_AUDIT_2026-09-02.md](../00-project/RETRIEVAL_RECALL_AUDIT_2026-09-02.md); the
2×2 is pinned by `tests/test_assist_retrieval_fusion.py`, whose third test is `xfail(strict=True)`
so that closing the gap **fails the run** and forces a re-baseline.

**Chunking** is `clause-aware-4`: it reads committed evidence rows, never re-parses raw text (one
source of truth — `AM-27` r4), splits on clause markers wherever they appear, folds headings and
orphan fragments into the clause they belong to, and excludes repeated page furniture. Re-indexing
preserves citations by matching successors on containment.

---

## 4. Generation — one seam, screened, hashed

Every call to a generative model in the entire system goes through
`assist/generation.py::generate_raw`. There is no second path, and
`tests/test_import_boundaries.py` asserts that exactly two modules may reach the network at all:
this one (`AM-30`) and the OIDC client (C-17).

In order, `generate_raw`:

1. checks the environment gate,
2. resolves the credential (a placeholder is a **failure**, not an absence),
3. refuses a floating model alias — the model is pinned (`AM-30` t7),
4. **screens the payload** for forbidden keys — `acceptable_max`, `approval_required_above`,
   `rule_outcome`, `deviation_outcome`, `unlimited_outcome`, `legal_rule`, `rule_configuration`,
   `credential_hash` — so no company position, rule or outcome can reach a provider (`AM-30` t3),
5. POSTs at temperature 0,
6. records `ASSIST_GENERATION_CALLED` on the audit trail with the model, the prompt version and the
   **payload SHA-256** — the hash, never the payload (`AM-30` t5).

Conversation context is bounded (`AM-58`): up to two prior **questions** of the same conversation,
labelled as context, never an earlier answer — an answer is not evidence, and letting generated text
ground a later claim is how a system starts believing itself.

---

## 5. Hallucination prevention

Two independent layers, and the first imports no model and no prompt — *"a guardrail that a prompt
change can affect is not a guardrail"* (`AM-28` r2), asserted by an import-boundary test.

**Before generation**: evidence must total at least 80 characters, or the model is never called.

**After generation**, `guardrails.verify_answer` applies four deterministic checks:

1. the model's own "NOT FOUND" passes through as `EVIDENCE_INSUFFICIENT` and is **never rewritten
   into an answer**;
2. every sentence carries a `[n]` citation marker;
3. every marker resolves to a chunk that exists;
4. every claim overlaps its cited chunk in content words above the grounding threshold.

Any failure becomes `CLAIM_UNSUPPORTED` and the user gets the standard refusal. A fifth screen sits
above: a grounded, verified answer that nonetheless states a **compliance verdict** is refused,
because that question belongs to the evaluator.

Finding explanations (`AM-49`) are validated even harder: one sentence, length-bounded, no judgment
language, no forbidden vocabulary, **no digit that is not in the source**, and a high grounding
overlap. A rejected explanation is not an error — the card falls back to the standard's own approved
description. A provider failure is *not stored*, so the next visit retries.

---

## 6. What is recorded, and how an answer is traced

| Table | Records |
|---|---|
| `prompt_versions` | the prompt code and its template text |
| `ai_answers` | model identity, prompt version, answer state, latency — **no confidence column**, deliberately (`AI-03` item 16) |
| `retrieval_runs` | query, filters, hit ids and scores, the gate's own inputs, embedding model, strategy version — ids and scores only, never text |
| `answer_citations` | one row per grounded claim→chunk link; the row's existence *is* the verification, so there is no `verified` flag |
| `chunks` | the chunking algorithm version that produced them |
| `audit_events` | `ASSIST_GENERATION_CALLED` with model, prompt version and payload hash |

So a stored answer traces to the exact prompt text, model, retrieval strategy and chunker that
produced it. Nullability is load-bearing: an answer refused for insufficient evidence has a null
model identity, because *the model was never called* and a default would fabricate a call.

Version constants: `grounded-answer-2` (Ask), `finding-explanation-1`, `obligation-extraction-1`,
`type-suggestion-1`, `semantic-mapping-1` and `semantic-cap-1` (recognition), `clause-aware-4`
(chunking), `section-1` (statutes), and the retrieval strategy version stamped on every run.

---

## 7. How it is measured

| Harness | Measures | Gate |
|---|---|---|
| `tools/verify_assist_quality.py` | the Tier-2 release gate over 77 ratified questions: wrongly answered, correct refusals, recall@10, hit@1, faithfulness, citation precision | **blocks** on a rise in wrongly-answered or a fall in faithfulness; refuses to compare across a changed dataset **or a changed pipeline identity** |
| `tools/benchmark_retrieval.py` | probes derived mechanically from real documents — never authored | reports |
| `tests/test_rd_semantic_corpus.py` | 104+ drafting variants over 19 standards, semantic vs lexical-only, four declared-type modes | 0 semantic false positives, 0 wrong, 0 changed-correct |
| `tools/calibrate_historical.py` | the published configuration against real signed counterparty paper | reports; never writes |

Two evaluation families are **deliberately not measured** rather than faked: paraphrase similarity
and legal phrasing need human-written questions, and inventing them would bias the result toward the
conclusion.

# Ask — target architecture

**Status: APPROVED PROPOSAL (owner, 2026-09-16), implemented phase by phase.** Phase 0 shipped 2026-09-17; Phase 1 (query planning + targeted retrieval) in progress; the reranker phase is held until Phase 1 passes its gates. Decisions it proposes (`AM-74`, `AM-75`) are proposals only — see [AB21_PROPOSED_AMENDMENTS.md](AB21_PROPOSED_AMENDMENTS.md). This document decides nothing; it records the design the owner approved and the measurements it rests on.


---

## 0. The owner's canonical stage map (recorded 2026-09-17)

The owner restated the target as a ten-stage pipeline. It is the same design this
document already describes — recorded here verbatim so every session names the stages
the same way, with the shipped state of each beside it.

```
USER QUESTION
   ↓
 1 CONVERSATION CONTEXT      active document / clause / previous turns
   ↓
 2 QUERY UNDERSTANDING — Gemini    intent + subject + topic + parties + legal concept
   ↓
 3 KNOWLEDGE ROUTER + AUTHORITY POLICY
      DOCUMENT  |  COMPANY STANDARD  |  GENERAL LAW
   ↓
 4 QUERY PLANNER             targeted queries + terminology expansion + decomposition
   ↓
 5 AUTHORIZED TARGETED RETRIEVAL   hybrid lexical + vector + metadata filtering
   ↓
 6 RERANKER                  most relevant evidence
   ↓
 7 EVIDENCE SUFFICIENCY / GATE     "do we have enough reliable evidence?"
   ↓
 8 GEMINI GROUNDED GENERATION      direct answer + explanation + citations
   ↓
 9 ANSWER VERIFICATION       grounding + citation correctness + unsupported-claim check
   ↓
10 RESPONSE                  simple answer + source/citation + expandable evidence
```

| Stage | Where it lives | State (2026-09-17) |
|---|---|---|
| 1 Conversation context | `service.ask()` step 1; ≤4 prior USER turns loaded, ≤2 sent | **SHIPPED** — bounded by `AM-58`; the prior ASSISTANT answer is never admitted (r2). Re-admitting the prior turn's *cited chunk ids* is proposed `AM-74`, owner decision |
| 2 Query understanding | `assist/planner.py`, `query-plan-1` | **MERGED, ships OFF** (`LEGALMIND_QUERY_PLANNER`). Phase 1 rebuilt 2026-09-18 so the provider is reached only for a question a lexical table cannot place: planning p50 **4,788 ms → 0 ms**, planner calls **1.00 → 0.18** per question (44 of 77 placed by table, 19 need no plan, 14 escalate). Still OFF: no targeting gain is demonstrable on this corpus — see stage 4 |
| 3 Knowledge router + authority policy | `assist/routing.py` `plan()`; `AM-45` r1 | **SHIPPED** — permissions decide candidate domains first, then question shape. Domains are never merged into one body of text (`AM-32` r1 / `AM-45` r2). Gemini may pick *within* authorized domains, never add one **Knowledge-domain classification rebuilt 2026-09-21 (FROZEN at `1a7ce69`).** `is_statute_question` was one flat regex matched anywhere — it fired on the English VERB "act" and recognised 2 of 23 statute questions. It is now a relation over seven deterministic signals (names_instrument · jurisdiction · rule_framing · legal_actor, against document_target · position_target · first_person), mirroring `is_comparison_question`'s 2026-09-16 rebuild; `RoutePlan.statute_signals` records which fired and the routed event logs them — never shown to a reader. Measured on a 91-case labelled matrix: precision **1.000** held, recall **0.333 → 0.889**, false STATUTE **0**. Still no model in the router (`AM-45` r1). |
| 4 Query planner | same module as stage 2; `LEGALMIND_QUERY_EXPANSION` | **MERGED, OFF, and measured harmful** — reformulations ≤3. Aiming (the topic) is **exactly neutral** for a document question by construction: the topic narrows Domain A only. Widening (extra fused vector passes) is worse on 4 of 5 targeting metrics in a deterministic probe, the third independent confirmation. The lexical-query injection point is closed: that query is the gate's calibrated input. **The corpus cannot test the one mechanism that could gain** — Domain A needs position-shaped questions (owner input, rule 21). Measure with `tools/probe_targeting.py`, not the Tier-2 gate, whose targeting numbers are scored only over gate-opened questions and so move with the nondeterministic rescue judge |
| 5 Authorized targeted retrieval | `store.search_hybrid`, `positions.search_positions`, `statutes.search_statutes` | **SHIPPED, single-query.** Authorization lives **inside** every query (`AM-25` r6); retired standards excluded from both lexical and vector paths (`AM-71`). Multi-query union + Domain A `constitution.topic` filter are Phase 1, built behind the flag. **Domain C ranking corrected 2026-09-21:** a FRACTIONAL `act_match` no longer sorts first, so one Act whose title merely carries the question's words cannot take every slot (a majority match still wins — `AM-50` r3); a REPEALED Act sorts last among equals. Measured on the repaired corpus: recall@6 0.700 → 0.800, hit@3 0.500 → 0.650, citation correctness 13/14 → 16/16, named-Act and exact-section unchanged |
| 6 Reranker | `backend/legalmind/assist/rerank.py` | **MERGED and ENABLED in production** (`LEGALMIND_RERANK=on`, verified in the running process 2026-09-17) — `ms-marco-MiniLM-L-6-v2`, pinned + checksummed, CPU-only. Measured: hit@1 0.609→0.734, MRR 0.709→0.796, recall 0.891→0.906, +205 ms, wrongly-answered and faithfulness unchanged. It runs AFTER the gate and **reorders only** — never membership, never the decision to answer (see §2 stage 6) |
| 7 Evidence sufficiency / gate | `assist/calibration.py`, `gate_is_open`, `evidence_is_sufficient`, `assist/rescue.py` | **SHIPPED, and UNCHANGED after Phase 2 (2026-09-18)** — deterministic, calibrated, and the safety control: it decides on the caller's original question, which is why a rephrasing alone can never turn a refusal into an answer. **Seven features have now failed to separate a false refusal from a correct one** (threshold sweep · second similarity feature · alternative embedding model · rerank floor · lexical match on the planner's canonical term, which was actively harmful · `gap_second` · `ratio`/`margin3`). N-13, which should be refused, carries the highest top cosine in the set (0.570) — above Q-61, which should be answered (0.554). And the headroom is nearly gone: the raw gate refuses 21 of 64 answerable, the **rescue judge already recovers 18**, leaving 3, one of which is a retrieval miss no gate change reaches. Test an idea with `tools/probe_gate.py` (zero Gemini) before spending a gate run |
| 8 Grounded generation | `assist/generation.py`, `grounded-answer-2` | **SHIPPED** — the one permitted egress (`AM-30`). Payload = question + chunk spans + prompt + ≤2 prior USER questions. No Legal Rule, threshold, Finding, company position or counterparty name ever enters it; `AM-67` adds published standard clause text as a reading aid; since `AM-76` (AB-26) that aid IS the answer and the quote is shown on request or on a verification failure |
| 9 Answer verification | `assist/guardrails.py` `verify_answer`, `intent.is_verdict_statement` | **SHIPPED, fail-closed** — an answer that cannot be verified is not shown (`AM-25` r5), and a screen that cannot evaluate an input fails closed (`AM-69`). This is why token streaming is impossible by design: perceived speed must come from progress states |
| 10 Response | `assist/service.py`, `AskDock.tsx` / `AskWorkspace.tsx` | **SHIPPED** — one verified block, citations renumbered to the displayed list (Phase 0, PR #68), expandable evidence. SSE progress states and marker links are Phase 3 |

**What the stage map does not change.** Gemini never routes to or away from the
evaluator, never opens the gate, never states a position absent from a ratified
standard, never says whether anything complies, and is never cited. Stages 3 and 7 are
code, not prompts. The map is a naming convention and a design record — it locks
nothing and amends no decision (rules 1, 2, 4).

---

## Context

The owner wants Ask to feel like a premium AI assistant: understand the question, know what it is *about*, use the conversation, pick the right source, retrieve narrowly, reason over evidence, answer point-by-point with citations — while Gemini never becomes the legal authority.

Today's pipeline is **shape → raw string → blind scan → similarity gate → generate → verify**. It has no representation of what a question is about. "What is the termination notice period?" and "what is the liability cap?" run the identical unconstrained scan over the same candidates, differing only by embedding distance. Measured consequences (all through the corrected Tier-2 gate, 77 ratified questions):

- shipped recall@10 **0.891** against a **0.938** vector ceiling; the remaining 3 false refusals are ranking failures, not retrieval misses
- the gate, not retrieval, was the binding constraint: 15 of 21 refused questions already had the gold chunk retrieved — the evidence rescue exists to pay an LLM call to re-read what the ranker already had
- every candidate-depth / fusion-weight / lexical-cap lever was measured at **0.000** gain, because RRF returns exactly what the vector branch returns
- **a reranker has never been built** — and `AM-25`'s permitted list ("hybrid retrieval **with reranking**") and `AM-26`'s stack table ("Reranking model | local, self-hosted, open-weight, cross-encoder") already authorise one

Two audit findings from this review that no earlier record noticed: `AM-25` r5 makes **token streaming impossible by design** (nothing may be shown before mechanical verification) — so "feels fast" must come from streamed progress states, not streamed tokens; and prose citation markers `[n]` and the rendered citation list `[n]` **diverge** whenever the model skips an evidence chunk (`service.py:912-923` collapses to `sorted(cited_indexes)`, `AskDock.tsx:540` renumbers by list index).

---

## 1. Current → target

| | Current | Target |
|---|---|---|
| **Intent** | Deterministic stem/word predicates: comparison, capability, general-knowledge, statute, follow-up. **Shape only — no topic.** | Same deterministic screens stay **first and authoritative for every safety route**. Added *after* them, on the retrieval path only: a Gemini **Query Plan** (topic · subject · party · source preference · ≤3 retrieval queries). Advisory, fail-closed to today's path. |
| **Retrieval query** | The question verbatim; follow-up = `f"{anchor} {question}"` | Original **+ ≤3 planner reformulations**, each embedded locally; follow-ups resolved to a self-contained query by the planner from the same two prior USER questions `AM-58` already permits |
| **Scope** | Broad: `WHERE document_version_id = :dv`, every chunk a candidate | Domain A **filtered inside the query** by the Constitution Appendix-B `topic` the standard already carries (14 topics over 40 standards). Document retrieval stays whole-document but **multi-query + reranked**; no hard topic filter on documents (no reliable tagging → false refusals). |
| **Expansion / reformulation** | None (`grep` returns zero hits) | Planner reformulations; statute alias expansion already exists and is reused |
| **Metadata filtering** | None | Domain A: `constitution.topic` (query-time join, no migration). Document: `section_hint` → lexical boost via existing `leading_section_ref`. Statutes: planner Act/section hint → existing named-Act ranking |
| **Hybrid + rerank** | Lexical (AND strict + OR floor + trigram) ∪ vector, RRF k=60. **No reranker.** | Same hybrid, union across queries, then a **local cross-encoder over ≤30 candidates → top-10**. Already authorised; selected per `AM-26` r2 (smallest that passes), pinned per r4/r5. |
| **Gate** | `lexical_hit OR (cos ≥ 0.50 AND gap ≥ 0.059)` on raw scores; rescue LLM reopens shut gates | Calibrated gate **unchanged** as the safety control. A second, deterministic, calibrated opener: `rerank_top ≥ RERANK_FLOOR`. Rescue demoted to last resort or retired **by measurement**. Recall@10 becomes deterministic again. |
| **Generation** | `grounded-answer-2`, one blocking call; positions extractive only (AM-67 approved but **off**) | `grounded-answer-3`: answer-shape steering from the plan (lead with the answer, 1–4 cited points). **AM-67 enabled** — the reading aid, which since `AM-76` (AB-26) replaces the quote as the default answer rather than sitting beside it. Same `generate_raw` seam, same payload categories. |
| **Verification** | `verify_answer` (4 checks, fail-closed) + `is_verdict_statement` | **Unchanged.** Plus the citation renumbering fix. |
| **Conversation** | 2 prior USER questions in payload; anchor concatenation | Planner-resolved follow-ups. **Proposed `AM-74`**: re-admit the prior turn's *cited chunk ids* as candidates (never the answer text). |
| **Fast paths** | capability · general-knowledge · comparison → evaluator · Finding-pinned evidence | Same four, all before the planner (zero added latency). Comparison handoff enriched with `AM-49` explanations — already authorised. |
| **UI** | Single blocking POST; skeleton "Looking this up…"; static citation list; markers as literal text | **SSE progress states** (deterministic, no internal names); answer delivered as one verified block; markers become links; suggested follow-ups derived deterministically from the plan's topic |
| **Observability** | `latency_ms` = provider call only; no stage timings | `logs.timed()` (exists, unused in assist) on every stage; per-stage p50/p95 in the gate output; Gemini calls and tokens per question |

---

## 2. Request flow, step by step

```
POST /conversations/{id}/messages                      api/routers/assist.py  (unchanged)
  Guard: assist.ask → conversation ownership → contract_readable → version → rate limit

service.ask()
  1  persist USER turn; load ≤4 prior USER questions            (unchanged, AM-58 r1/r7)
  2  DETERMINISTIC SCREENS — code, never prompt (AM-28 r2, AM-45 r3, AM-68 r1)
       general_knowledge → canned text, return                  (unchanged)
       capability        → rendered manifest, return            (unchanged, AM-68 r3)
       routing.plan()    → authorized candidate domains from PERMISSIONS first,
                           then shape (AM-45 r1)
       comparison        → evaluator handoff, return            (AM-25 r4; see §2.4)
  3  QUERY PLAN  ── NEW ──  generation.generate_raw("query-plan-1")
       in : question + the same ≤2 prior USER questions AM-58 already admits
       out: {intent, topic∈Appendix-B|null, subject, party∈{ORG,COUNTERPARTY,EITHER,NONE},
             source_preference∈{DOCUMENT,POSITIONS,STATUTES,ANY}, queries[≤3], section_hint}
       may: pick WITHIN the authorized domains; add reformulations; narrow Domain A by topic
       may NOT: add a domain; touch the comparison decision; open the gate; be cited
       on any failure → plan = None → steps 4–6 run exactly as today
       recorded on retrieval_runs.filters.plan (no chunk text)
  4  TARGETED RETRIEVAL  (authorization still INSIDE every query — AM-25 r6)
       Domain A   positions.search_positions(topic=plan.topic) — query-time join on
                  company_standard_versions.configuration->'constitution'->>'topic';
                  empty → re-run unfiltered. r.status <> 'DEPRECATED' stands (AM-71).
       DOCUMENT   store.search_hybrid(queries=[question, *plan.queries]) — one lexical pass
                  on the question, one vector pass per query (local embeddings), union,
                  fragments redirected, RRF across branches → ≤30 candidates
       STATUTES   statutes.search_statutes(query=plan.queries[0] or question) — existing
                  alias/named-Act ranking
  5  GATE      gate_is_open(lexical_hit, raw_cosines)            (unchanged, calibrated)
               else rescue.reconsider()                          (still in place; see below)
               then evidence_is_sufficient()                     (unchanged)
  6  RERANK    local cross-encoder REORDERS what the gate admitted (`assist/rerank.py`)
               ⚠️ AS BUILT, stages 5 and 6 run in THIS order — the reverse of the diagram
               above — and the reranker never gates. `RERANK_FLOOR` was MEASURED AND
               REJECTED (PR #74, 2026-09-17): a rerank floor cannot reopen a shut gate,
               because the top rerank score on the 20 answerable questions the gate
               wrongly refuses (median −3.12) overlaps the 13 genuinely unanswerable
               ones (median −2.30, i.e. HIGHER) almost entirely. The fourth independent
               feature to fail that separation, after the 35-point threshold sweep, the
               IDF-weighted overlap and the embedding-model swap. So the gate and the
               rescue each keep exactly the inputs they were calibrated on, and gate
               recovery remains the rescue judge's problem. See `service.retrieve_document`,
               whose docstring carries the same ordering and reason.
  7  PERSIST retrieval_runs after reconsideration                (fixed in #64)
  8  GENERATE  generation.generate(question, top-k, prior_questions, answer_shape=plan.intent)
               "grounded-answer-3"; payload = question + chunk spans + prompt + prior questions
               — the categories AM-30 t2 (as amended by AM-58/AM-67) already permits
  9  VERIFY    guardrails.verify_answer → intent.is_verdict_statement   (unchanged, AM-25 r5)
               renumber prose markers to the displayed list AFTER verification (display only)
 10  FALL-THROUGH _positions_or_refusal — positions (with AM-67 aid) → statutes → refusal
               (unchanged order, AM-50 r2, AM-46 wording)
 11  RESPOND   one verified block. Progress states streamed over SSE during 3–9:
               "reading your document" · "checking N passages" · "verifying citations" —
               deterministic strings, no domain names the caller is not already entitled to see
```

### 2.1 "What is the termination period of LeapSwitch?"
`mentions_organization` fires (`leapswitch` stem) → POSITIONS primary, DOCUMENT if attached. Plan: `topic=Termination & Suspension, party=ORGANIZATION, source_preference=POSITIONS, queries=["termination notice period", "notice required to terminate", "term and termination"]`. Domain A filtered to the **5** Termination standards (not 40) → the notice-period standard retrieved, and since `AM-76` its `AM-67` synthesis returned as the answer (the quote collapsed behind "Show exact wording"): *"The organisation's standard requires … [1]."* Document evidence, if any, in its own section (`AM-45` r2). **Today:** unfiltered 40-chunk scan where "period" vs "notice" mismatch can surface the wrong standard; no synthesis.

### 2.2 "How much time do we get to fix a breach?"
No position reference → not a comparison (fixed in #65). Plan: `topic=Termination & Suspension, subject="cure period after breach", queries=["cure period breach notice", "remedy breach within days", "material breach not cured"]`. Multi-query union → reranker ranks the §7.2 cure clause first → gate opens on rerank score even where a single-query cosine sat at 0.47 → *"30 days from written notice [1]."* **Today:** single query, cosine below floor, gate shut, rescue LLM call, maybe reopened.

### 2.3 "What standards do we require for liability?"
POSITIONS. Plan `topic=Liability` → **4** standards → each quoted + a synthesised point list ("Cap: 12 months of total fees [1]. Carve-outs: … [2].") **Today:** OR-lexeme match on "standards require liability" with a 2-lexeme floor over 40 chunks; extractive only.

### 2.4 Uploaded MSA + "Does this comply with our termination standard?"
`is_comparison_question` → **True** (position reference "our termination standard" + `compl`-family signal). Deterministic; the planner never runs. Handoff (`AM-45` r4) enriched, all already authorised: Findings of the latest Review **filtered to the Termination topic** (deterministic — the position noun is already extracted by `_position_reference`), each with its `AM-49` grounded explanation (cached, `finding.view`), the ratified position quoted (`AM-44`), "Open the Findings". Gemini decides nothing. **Today:** counts by classification + a link.

### 2.5 "What can LegalMind do?"
`is_capability_question` → rendered manifest (`AM-68` r3), zero retrieval, zero model calls. **Unchanged.** Manifest content is owner-approved configuration.

---

## 3. Division of labour

**Gemini does — understand, plan, reformulate, synthesise, explain:**
- Query Plan (new): what the question is about, which authorised source it points at, how to phrase retrieval
- Grounded answer generation over document / statute chunks (existing `generate`)
- Domain A reading aid as the default answer (`AM-67` as amended by `AM-76`; approved, enable)
- Finding explanation sentence (`AM-49`, existing)
- Evidence rescue as last resort (existing, expected to shrink to ~0)

**Gemini never does:** route to or away from the evaluator; open the gate on its own say-so; state a position absent from a ratified standard (`AM-25` r3); say whether anything complies (`AM-25` r4, `is_verdict_statement`); be cited; see a Legal Rule, threshold, Finding or counterparty name (`AM-30` t3/t4).

**RAG does — find and rank:**
- Local embeddings for every query variant (`AM-30` t1: embedding never egresses)
- Hybrid lexical + vector per domain, authorisation inside each query (`AM-25` r6)
- Domain A topic filter; statute alias/named-Act ranking
- Local cross-encoder rerank
- RRF fusion, fragment redirect

**Deterministic systems do — decide and verify:**
- Every safety route: comparison → evaluator, capability, general-knowledge (code, `AM-28` r2 spirit)
- The refusal gate and the new rerank opener, both calibrated constants with provenance (`calibration.py` discipline)
- `evidence_is_sufficient`, `verify_answer` (grounding overlap, fail-closed on unreadable claims — `AM-69` r2), `is_verdict_statement`
- Findings, classifications, statuses — the evaluator, read never produced (`AM-25` r1/r2)
- Refusal wording per candidate set (`AM-46`)
- Audit: hash-only per call (`AM-30` t5), retrieval run after reconsideration (`AM-27`)

---

## 4. Decisions that stay unchanged — and are assets, not obstacles

| Decision | Why it stays |
|---|---|
| `AM-25` r1–r9 | The lane's identity. r5 in particular is why streaming is *progress states*, not tokens — and why the product can be trusted. |
| `AM-25` r4 / `AM-45` r3 / `AM-68` r1 | Safety routing is code. The planner runs *after* and cannot influence it. Considered and rejected: letting the planner flag a "possible comparison" as a fail-closed widening — it would make a guardrail prompt-dependent (`AM-28` r2). |
| `AM-30` t1–t10 as amended | The planner's payload — question + ≤2 prior USER questions + a template — is a **subset** of what t2 (via `AM-58` r1) already permits. New *purpose*, same as the rescue was; a new `prompt_version`, hash-audited under t5. **No new category of data leaves.** |
| `AM-26` r2/r4/r5 | Govern the reranker's selection exactly as they governed the embedder's. |
| `AM-32` r1 / `AM-45` r2 | Domains never merged. A premium *presentation* juxtaposes sections; it does not need one body of text. Merging is exactly where legal authority would leak. |
| `AM-32` r4 as amended by `AM-67` | Already the reading-aid design. Enable, don't re-decide. |
| `AM-67` r7 | Prerequisite met: position corpus re-chunked 2026-09-15, 0 locators (`test_the_real_corpus_chunks_into_the_database_carrying_no_locator`). |
| `AM-68` r3 | Manifest rendered, never generated. Right call. |
| `AM-71` | Retired standards excluded read-side in both paths; the topic filter composes with it. |
| `AM-46` r1/r3, `AM-29` | Refusal wording per candidate set. (r2 is the one optional amendment — §5.) |
| `AM-27` r4 | No metadata duplicated onto `chunks`; the topic filter joins, it does not denormalise. |
| `AM-28` gate | Every phase re-baselines through `verify_assist_quality`, which now measures the production path. |

---

## 5. Locked decisions that need attention

### 5.1 Housekeeping — required regardless of this proposal (rule 5)

**`AM-45` r3** describes the enforcement mechanism as *"a deterministic two-signal stem classifier (an organization reference AND a distinct comparison verb or outcome noun)"*. PR #65 (2026-09-16, `be8d97c`) replaced that mechanism with a position-*reference* relation plus two further shapes. The **rule** (`AM-25` r4) is unchanged and the classifier is still deterministic and still code — but the parenthetical no longer describes the shipped screen. Append a clarifying record on the `AM-69` pattern ("implemented ahead of this record, recorded rather than backdated"). No behaviour change; the record is brought current.

Also found: `prompt_versions` never registers `position-reading-aid-1` (`AM-67` answers carry `prompt_version_id = NULL`); the registry's byte-identical line-count chain stops after AB-16 (`all_lock.md` is 19,374 lines, registry says 17,842). Both are record hygiene, not decisions.

### 5.2 Proposed `AM-74` — a prior turn's *evidence* may be re-admitted as candidates

| | |
|---|---|
| **Amends** | `AM-58` r1's closing sentence: *"Nothing else about the conversation is admitted."* |
| **Does not amend** | `AM-58` r2 (*never an earlier answer*), r3–r7; `AM-30` t2–t5 |
| **Why** | `AM-58`'s own recorded cost: *"a follow-up referring to something only the previous answer contains ('is the 30 days you mentioned business days?') still resolves through the previous question, not the answer, and may therefore miss."* This is the single largest gap between Ask and a premium assistant on multi-turn use. |
| **Replacement** | The chunk ids cited by the immediately preceding ASSISTANT turn **of the same conversation and same document version** are re-admitted as retrieval *candidates* (re-read from `answer_citations` → `chunks` by id, inside the same authorised scope), ranked with everything else. The answer text is never read, never sent, never cited — r2's rationale ("text that was itself generated grounding a later claim") is untouched. |
| **Risk / trade-off** | Low. Same document, same authorisation, chunk text that already egressed for that conversation. Cost: a stale anchor could keep an off-topic chunk in the candidate pool — the reranker and gate still decide. |

### 5.3 Proposed `AM-75` — a refusal may name the *subject* the caller's own document lacks (optional, defer)

| | |
|---|---|
| **Amends** | `AM-46` r2: *"No wording depends on whether a particular chunk, standard, statute or document exists."* |
| **Why** | *"Information not found in the selected document"* is honest but reads like a keyword box. *"The selected document does not appear to address the cure period"* is what a premium assistant says. |
| **Replacement** | Only when the caller is authorised for the document AND the planner produced a `subject`: the refusal may name that subject. Positions and statutes keep the exact `AM-46` wording. |
| **Oracle analysis** | Reveals that the caller's *own readable document* lacks a topic — information the caller can obtain by reading it. Nothing outside scope. Authorization exclusions remain byte-identical because the subject is never named for a domain the caller cannot read. |
| **Risk / trade-off** | The wording now depends on model output (the subject phrase). Mitigation: the subject is screened by `_forbidden_payload_check`-style rules and length-capped before display, or replaced by the plan's `topic` (a 14-item fixed vocabulary — deterministic). **Recommend deferring** until Phase 2 measurement shows how often refusals still occur. |

### 5.4 Explicitly NOT proposed

- **Token streaming** — blocked by `AM-25` r5 and correctly so. Progress-state streaming delivers the perceived speed without showing an unverified claim.
- **Cross-domain synthesis into one text** — `AM-32` r1 / `AM-45` r2. Presentation, not merging.
- **Embedding model change (`AM-73`)** — deferred; the reranker is the cheaper lever and re-embedding the corpus is a full migration.
- **Generated general-knowledge answers (`AM-72`)** — not approved; not needed for any of the five examples.
- **Multi-document conversations (`OD-A`)** — schema-level product decision, separate.
- **Relaxing `COSINE_FLOOR` / `PEAK_MARGIN`** — measured 35 combinations, every one trades a correct refusal.

---

## 6. Migration plan

Each phase ships behind a flag, re-baselines through `tools/verify_assist_quality.py`, and has an exit gate. `AM-28`: wrongly-answered and faithfulness may not worsen at any phase.

| Phase | What | Decision needed | Exit gate |
|---|---|---|---|
| **0 — enable what is approved** (~1 day) | Set `LEGALMIND_POSITION_SYNTHESIS=on` in production (`AM-67` r7 prerequisite met). Register `position-reading-aid-1` in `prompt_versions`. Add `logs.timed()` around every assist stage; persist end-to-end latency. Fix citation renumbering. Append the `AM-45` r3 clarifying record. | None | Gate SHIPPABLE; per-stage p50/p95 visible; `AM-67` synthesis verified on the 8 position questions |
| **1 — understand and target** (~3 days) | `assist/planner.py` (`query-plan-1`, fail-closed, advisory, `LEGALMIND_QUERY_PLANNER`). `store.search_hybrid(queries=[...])` multi-query union. `positions.search_positions(topic=)` query-time join. `grounded-answer-3` answer shape. Plan recorded on `retrieval_runs.filters.plan`. | None — payload categories unchanged | wrongly-answered ≤ 1/13 · faithfulness 1.0 · false refusals ≤ 3 · **MRR and gold-in-top-3 up** · Domain A candidates per position question ≤ 6 |
| **2 — rerank and re-gate** (~3–4 days) | Bake-off (`AM-26` r2 smallest-up: `ms-marco-MiniLM-L-6-v2` 22M → `L-12-v2` 33M → stop at first pass) on the 77 set via the existing `benchmark_retrieval` pattern. Provision with SHA-256 manifest (`tools/provision_model.py` pattern, r5). ONNX CPU, in-process like the embedder. `RERANK_FLOOR` calibrated so wrongly-answered does not rise; provenance in `calibration.py`. Rescue demoted to last resort; retire if it fires <1% on the 77. | The **pin record** (which model, SHA) — an `AM-26` r4 measurement obligation, not a new authorisation | recall@10 **deterministic** run-to-run · ≥ 0.90 · wrongly-answered ≤ 1/13 · rescue calls → ~0 · p95 end-to-end ≤ 6 s |
| **3 — feel** (~3 days) | **DONE 2026-09-18.** Prose markers → references (#78). **grounded-answer-3**: rule 6 open with the answer (no describing the excerpts, no restating the question), rule 7 plain prose (line-leading hyphens kept, asterisk emphasis and headings out). Diagnosed by reading 77 real answers out of the gate database, 0 Gemini calls. The retrieval preamble was **costing answers**, not just ugly — "Based on the provided excerpts," injects `based`/`provided`/`excerpts` into the claim sentence and the grounding check fails it; the identical fact passes unprefaced. Measured: answers 55→56, retained 61→62, false refusals 3→2, faithfulness and citation precision 1.0 either way, output tokens down, retrieval byte-identical. **SSE progress states: NOT BUILT, by owner goal + risk** — `AM-25` r5 forbids streaming the answer so it buys three strings on a 2.25 s wait, while the router's `CommitBeforeResponse` (which exists because a pre-commit `201` measurably lost rows) would need the audit trail committed mid-stream. A faked client-side timer was rejected: DESIGN.md forbids implying knowledge the client lacks. **Suggested follow-ups: still NOT DONE** — their specified source is `plan.topic` and the planner ships off (rule 4). Citation density deliberately unchanged: those repeated markers are per-claim attribution, which rules 11/12 require |
| **4 — conversation** | `AM-74` if approved: prior-turn cited chunks as candidates. Conversation eval set. | **`AM-74`** owner decision | Follow-up resolves to gold section on the scripted dialogues |
| **5 — refusal wording** | `AM-75` if approved and if Phase 2 shows refusals still frequent. | **`AM-75`** owner decision | — |

Rollback at every phase is the flag (`LEGALMIND_QUERY_PLANNER=off`, `LEGALMIND_RERANKER=off`, `LEGALMIND_POSITION_SYNTHESIS=off`) — a restart, no deploy — and the baseline's `pipeline` block records each so a flag-off run can never be compared against a flag-on bar (the drift check that already exists).

---

## 7. How we objectively test "smarter"

All through the **production path** (`verify_assist_quality`, corrected 2026-09-16), same 77 ratified questions, same anchors. New metrics are additive; nothing existing is redefined.

| # | Metric | Why it measures "smarter" | Blocking? |
|---|---|---|---|
| 7.1 | wrongly-answered (13 unanswerable) · user-visible wrong · faithfulness · citation precision | `AM-28`'s gate. The premium feel is worth nothing if it answers what it should refuse. | **Yes** |
| 7.2 | **MRR of the gold chunk** and **gold-in-top-3** — the dataset already carries `section` per question | "Targeted" means the right passage is *first*, not merely present in ten. Today hit@1 is 0.609. | Report; regression flagged |
| 7.3 | **Evidence precision** — share of chunks sent to generation that are from the gold section | Fewer, better chunks to the model = less to mis-cite, lower cost, faster | Report |
| 7.4 | **Domain A candidates per position question** (today: up to 40) | Direct measure of targeting on the organisation's positions | Report |
| 7.5 | **Routing matrix** — 7 false comparisons (0), 16 pinned + 14 unseen genuine (all), capability, general-knowledge | Existing tests; guarantees the planner never moved a safety route | **Yes** (tests) |
| 7.6 | **Blind pairwise preference** — 20 questions, before/after answers, randomised, owner-rated | The only subjective measure, kept small and explicit. Target ≥ 70% preference. | Phase 3 exit |
| 7.7 | **Answer-shape checks** (deterministic): every sentence cited; first sentence contains a content word from the gold chunk (leads with the answer); ≤ 6 sentences; no verdict | Point-to-point without a human rater | Report |
| 7.8 | **Conversation eval** — ~15 scripted 2–3-turn dialogues derived from existing ratified questions ("…and how long is the cure period?" after 2.2); scored on follow-up gold section | Multi-turn understanding | Phase 4 |
| 7.9 | **Determinism of recall@10** across two runs of the same build | Today it moves by one question because the rescue is a model call; Phase 2 should make it exact | Phase 2 exit |
| 7.10 | **Latency p50/p95 per stage** and **Gemini calls + tokens per question** | Premium ≠ slow or expensive | p95 ≤ 6 s; calls ≤ 2 per question |

**Latency budget (p50, target):** planner 300–500 ms (~150 output tokens, Flash, `thinkingLevel: MINIMAL`) · 4 local embeddings ~80 ms · SQL ~50 ms · rerank 30 pairs ~150 ms · generation 1.5–3 s · verify <10 ms → **~2.5–4.5 s** vs today's ~2–3 s plus a 500 ms rescue on ~30% of questions. Progress states cover the difference perceptually. **Cost:** +1 Flash call per retrieval question (~1e-4 USD), −rescue calls, fewer chunks per generation.

---

## 8. Risks and trade-offs, stated plainly

- **Planner adds a model call to the critical path.** Mitigated: fail-closed to today's path on any error/timeout (2 s cap); flag rollback; skipped entirely on all four fast paths.
- **Multi-query widens the candidate pool** — a reformulation could pull in a topical-but-wrong chunk. Mitigated: the reranker and the unchanged gate still decide; evidence precision (7.3) is measured.
- **A reranker is a new model in production**: provisioning, memory (~90 MB ONNX), cold start. Mitigated: same runtime pattern as the embedder (in-process ONNX, SHA manifest, lazy load); add a startup warm-up for both (none exists today — first request pays verification + session build).
- **`RERANK_FLOOR` was not built.** It is struck from this proposal: measured and rejected on the evidence recorded at stage 6 above (PR #74). Nothing in the shipped pipeline changes what may reach generation — the reranker reorders admitted evidence and nothing else, so `COSINE_FLOOR` and `PEAK_MARGIN` remain the only gate features.
- **`AM-74`/`AM-75` are owner decisions**, not engineering. Everything in Phases 0–3 ships without them.
- **The 14-topic taxonomy is the Constitution's, not a retrieval ontology.** It targets positions well; it is deliberately *not* used to hard-filter documents.

---

## 9. Files (for the eventual implementation — none touched now)

New: `backend/legalmind/assist/planner.py` · `backend/legalmind/assist/rerank.py` (+ `onnx_backend` extension) · `backend/tools/benchmark_rerank.py` · `docs/00-project/ASK_TARGET_ARCHITECTURE.md`

Modified: `service.py` (plan step, multi-query call, renumbering, timings, SSE generator) · `store.py` (`search_hybrid(queries=...)`, candidate union) · `positions.py` (`topic=` join) · `calibration.py` (`RERANK_FLOOR`, `RERANK_MODEL_*`, strategy version bump) · `generation.py` (`grounded-answer-3`, `query-plan-1`) · `rescue.py` (last-resort ordering) · `config.py` (two flags) · `api/routers/assist.py` (SSE endpoint beside the existing POST) · `tools/verify_assist_quality.py` (7.2–7.4, 7.7, 7.9, 7.10) · `AskDock.tsx` / `AskWorkspace.tsx` / `AnswerProse.tsx` (progress states, marker links, follow-up chips) · `tests/assist_eval/baseline.json` (re-baselined per phase)

Records: `all_lock.md` append — `AM-45` r3 clarification (Phase 0); reranker pin record (Phase 2); `AM-74`/`AM-75` proposals in `docs/00-project/AB21_PROPOSED_AMENDMENTS.md` (or a new AB-24 file) for owner decision.

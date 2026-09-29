# Query understanding — diagnosis, target contract, and migration

📁 **ANALYSIS / PROPOSAL.** Decides nothing. No locked decision is amended here, and
nothing in this document authorises building anything on its own.

Owner directive, 2026-09-22: Ask must understand WHAT is being asked before deciding
WHERE to search. Q12/Q13/Q16 of the 16-question validation are named as symptoms, and
patching them with regexes is explicitly forbidden.

---

## A. Diagnosis — what the router understands today

Question understanding is **17 call sites across 5 modules**, each re-deriving one
aspect from the raw question string. There is no object anywhere in the system that
represents "the question". `routing.plan` calls five predicates, `service._ask` calls
nine more, and none of them can see what the others concluded.

| # | dimension | state | where |
|---|---|---|---|
| 1 | user intent | **C — regex/signal** | four independent predicates: `is_capability_question`, `is_general_knowledge_question`, `is_comparison_question`, `legal_question_signals`. No single intent value exists |
| 2 | subject / entity | **D — missing** deterministically | `QueryPlan.subject` + `.topic` exist but ship OFF |
| 3 | document reference | **B — inferred** | only `has_document: bool`. Never *which clause*, never "this NDA" vs "the MSA" |
| 4 | company-standard reference | **C — regex** | `mentions_organization` |
| 5 | legal/statutory reference | **C — signal relation** | `LegalQuestionSignals`, 7 signals. The best-built part of the system |
| 6 | jurisdiction | **C — boolean, not a value** | `signals.jurisdiction` is True/False. "Indian law" and "Delaware law" are indistinguishable |
| 7 | temporal requirement | **D — missing** | no current-vs-historical, no as-of date. The repealed-law filter is a retrieval-side patch for what is really a temporal requirement |
| 8 | comparison / compliance | **A — explicit** | `is_comparison_question`, gated on `has_document` (`AM-25` r4) |
| 9 | exact-text intent | **A — explicit** | `is_exact_text_request` |
| 10 | follow-up context | **B/C** | `is_follow_up` regex + `_resolve_follow_up` string concatenation. No context state, no expiry, no ambiguity rule |
| 11 | requested output type | **D — missing** | `QueryPlan.intent` (FACT/LIST/EXPLAIN/PROCEDURE) exists, ships OFF |

**Two are explicit. Four are regex. Two are inferred. Three are missing.**

### The structural defect: intent IS the retrieval domain

`RoutePlan` carries `domains: tuple[Domain, ...]` — set membership, not a plan. There is
no way to express "this question needs the document AND the law AND a comparison
between them". `comparison` is a separate boolean that is only consulted when a
document happens to be attached.

That single fact explains all three named symptoms, and they are three different
diseases:

* **Q16 "Does our NDA comply with the DPDP Act?"** — `is_comparison_question` requires
  `has_document`. With no document attached, comparison is False, and the question
  degrades to "a question that mentions an Act", answered from a position quote. The
  system cannot represent *compare the document against a statute*, so it answers the
  part it can express.
* **Q12 "What is the penalty for failing to protect personal data?"** — no instrument,
  no jurisdiction, no rule framing, so `general_law` is False. The system has no way to
  say **the requested fact is a PENALTY, and penalties are stated by law**. Requested-fact
  type does not exist as a concept (dimension 11).
* **Q13 "Within what time must a cyber incident be reported?"** — same, for a DEADLINE.
  The obvious repair (an impersonal-modal signal) was measured in earlier work and
  **rejected for breaking a must-refuse case**. It must not be retried.

Adding signals to `LegalQuestionSignals` cannot fix any of these, because the missing
information is not a signal about the law — it is the *shape of the answer being asked
for*.

### What already exists and must be reused, not rebuilt

`planner.QueryPlan` is **already ~70% of the contract this design needs**: `intent`,
`topic`, `subject`, `party`, `source_preference`, `queries`, `section_hint`. It is
schema-validated, advisory, fails closed, records `prompt_version`, and is persisted to
`retrieval_runs.filters.plan`. It ships OFF because it cost +2.4–8 s for no recall gain
(PR #69) — measured as a *retrieval aid*, which is not what this design needs it for.

---

## B. Target contract — `QuestionUnderstanding`

One frozen dataclass, built once per turn, passed everywhere. Every field has a
deterministic default; nothing is required to come from a model.

```
QuestionUnderstanding
  intent            LOOKUP | REQUIREMENT | COMPARISON | EXACT_TEXT | CAPABILITY | OUT_OF_SCOPE
  requested_fact    VALUE | PERIOD | PENALTY | DEADLINE | PROCEDURE | DEFINITION | NONE
  subject           free text, recorded, never shown
  entities          instruments, clause refs, counterparties, document types
  authority         DOCUMENT | POSITION | GENERAL_LAW  (a SET — what may answer)
  domains           the retrieval plan, ordered, derived from authority ∩ permissions
  jurisdiction      a VALUE or NEEDS_RESOLUTION, not a boolean
  temporal          IN_FORCE (default) | AS_OF(date) | HISTORICAL
  document_context  version id + clause, or NONE
  conversation      inherited subject + its turn id + why it was inherited
  exact_text        bool
  comparison        bool  (independent of whether a document is attached)
  ambiguity         list of what could not be resolved
  clarification     the single question to ask, or None
  because           which signals produced each decision — for the log
```

The three named symptoms become expressible:

| question | intent | requested_fact | authority | comparison |
|---|---|---|---|---|
| Does our NDA comply with the DPDP Act? | COMPARISON | NONE | {DOCUMENT, GENERAL_LAW} | true |
| What is the penalty for failing to protect personal data? | REQUIREMENT | PENALTY | {GENERAL_LAW} | false |
| Within what time must a cyber incident be reported? | REQUIREMENT | DEADLINE | {GENERAL_LAW} | false |
| What is our position on MSA auto-renewal? | LOOKUP | VALUE | {POSITION} | false |
| Quote that clause verbatim. | EXACT_TEXT | NONE | inherited | false |
| What is the capital of France? | OUT_OF_SCOPE | — | {} | false |

**`requested_fact` is the load-bearing new idea**, and it is not a keyword list. A
PENALTY or a DEADLINE is a thing only an authority states — a company standard records a
position, a contract records a bargain, but "what is the penalty" asks what the law
imposes. That is a relation between the requested fact and the kind of source that can
carry it, in the same family as the existing signal relation and subject to the same
measurement discipline.

---

## C. Routing / authority state machine

Two layers, and the boundary between them is the whole design.

```
  UNDERSTAND  (may interpret language; proposes)
      deterministic parse  ->  QuestionUnderstanding
      if ambiguity and the flag is on:
          bounded Gemini call -> schema-validated PROPOSAL -> merge (never overwrite
          a field the deterministic layer resolved)
      |
      v
  POLICY  (decides; code only, never a model)
      permissions      -> which domains are readable at all      (AM-45 r1)
      authority ∩ perms-> the domain plan
      comparison       -> the evaluator, never generation        (AM-25 r4)
      temporal         -> in-force filter                        (AM-71 shape)
      jurisdiction     -> corpus selection / NEEDS_RESOLUTION
      sufficiency gate -> calibrated, deterministic
      -> RetrievalPlan | Refusal | Clarification
```

**Invariants, unchanged:** permissions are evaluated before question shape; Gemini never
adds a domain, never opens the gate, never decides comparison, is never cited; the
verifier imports no model (`AM-76` r6, `AM-28` r2); nothing reaches a reader before
mechanical verification (`AM-25` r5).

**Gemini's proposal is constrained, not trusted:** any domain it proposes is intersected
with the authorized set; any field the deterministic layer already resolved wins; an
unparseable or late reply yields `None` and the deterministic understanding stands. This
is exactly the existing `planner` boundary, applied one layer earlier.

---

## D. Where Gemini earns its place, and where it does not

Deterministic parsing already handles the clear cases and must keep them — it is free,
explainable and reproducible. The model is worth calling only when `ambiguity` is
non-empty: no instrument named, no jurisdiction, and a requested fact that could be
either the organization's position or the general law.

On the 16-question validation that is **2 of 16 questions**, so the expected cost is
~0.12 extra calls/question, not one per question. PR #69's measured +2.4–8 s was for
calling it on *every* question; called on the ambiguous remainder it is bounded by
construction.

---

## E. Evaluation matrix

16 classes × ~4 questions. Per case, recorded before any implementation lands:
intent accuracy · domain-plan accuracy · authority correctness · retrieval relevance ·
citation correctness · answer correctness · refusal correctness · answer quality ·
latency · Gemini calls.

`DOCUMENT_LOOKUP · POSITION_LOOKUP · CONSTITUTION_LOOKUP · GENERAL_LAW ·
STATUTE_WITHOUT_ACT_NAME · STATUTE_WITH_ACT_NAME · COMPARISON · MULTI_DOMAIN ·
FOLLOW_UP · EXACT_TEXT · CAPABILITY · UNKNOWN · AMBIGUOUS · HISTORICAL_LAW ·
JURISDICTION_SPECIFIC · MULTILINGUAL`

**Two gates, both blocking.** Legal correctness may never be traded for a routing
number: wrongly-answered must not rise, and refusal correctness on `UNKNOWN` +
`OUT_OF_SCOPE` must stay at 100%. The matrix is authored and baselined on today's code
**before** any behaviour changes, so every later number is a delta against a real
baseline rather than against a memory.

---

## F. Migration — four steps, each shippable and reversible

1. **Introduce the contract, change no behaviour.** `QuestionUnderstanding` assembled
   from today's predicates; `routing.plan` consumes the object instead of calling five
   predicates. Byte-identical routing, proven by the 91-case routing matrix and the
   16-question run. Pure refactor.
2. **Add `requested_fact` and `authority` as a set.** This is where Q12/Q13 become
   expressible. Measured against the matrix; ships only if refusal correctness holds at
   100% and no must-refuse case regresses.
3. **Make comparison independent of attachment.** `intent=COMPARISON` with no document
   asks for the document, instead of silently answering the half it can. Fixes Q16 by
   making it representable, not by naming it.
4. **Bounded Gemini enrichment for `ambiguity` only**, behind a flag, defaulting OFF,
   reusing the existing `planner` seam and its schema validation.

Steps 1 and 3 need no provider call at all. Step 2 is the only one that touches
routing semantics, and it is the one with a hard measurement gate.

**Not touched by any step:** retrieval, reranking, the verifier, authorization, the
comparison/evaluator boundary, calibration constants, and every P0 protection now live.

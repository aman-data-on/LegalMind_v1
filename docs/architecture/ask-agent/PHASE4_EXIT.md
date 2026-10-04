# Ask agent — Phase 4 exit report: verifier, ladder, floor, renderer, and the owner's Phase 3 review (2026-10-03T23:30+05:30)

Branch `feat/ask-agent-phase0-1`, from the Phase 3 records commit `e1a2840`. **Local only —
nothing pushed, merged or deployed; production unchanged** (no production database write,
config change or restart; the live database was read only, by the golden benchmark). The
agent's output still never reaches a user (A-35). Client text appears only in the private
review sample; this report carries turn IDs, record keys and clause locations.

**Phase 4 is NOT complete.** Every regression check and every exit criterion that can run
passes, and F12 now runs and passes (A-54, 2026-10-04). **Traps F1, F2, F3 remain unmapped:**
on this machine they exist only as labels, and no G-script is claimed equivalent without
evidence (A-55). The company standards are NOT what is missing — the Constitution and 72
active standards are loaded and cited; neither are contracts — the supplied and real-client
corpora are present. What is missing is each trap's definition (question, document, pass
criterion). **Needed from the owner:** that definition for F1, F2, F3 (or a ruling on the
coverage below), and the final call on the per-turn comparison.

## What was built

| Roadmap | Where | What it does |
|---|---|---|
| 4.1 Verifier V1–V8 | `assist/agent_verify.py` `verify` | Per block against the evidence the turn showed: V1 citations exist, were shown, carry a location, ≤ 2 per claim; V2 figures; V3 negation parity; V4 entailment by the shipped NLI verifier (`verify.judge`), lexical overlap as fallback; V5 no authority claim without a citation; V6 user material attributed and cited to U only; V7 conditional framing on legal conclusions; V8 one question, only when nothing answers. Plus the owner's P1 (document content reaches the reader cited; an answer that cites none of the document's strong records is repaired), P2 (scope kept), P10 (a figure the document states is cited to it), B5 (weak evidence never supports a claim) |
| 4.2 One repair call | `agent.run_turn`, `agent_verify.settle` | One combined repair call with every violation; then deterministic fixes (cite choice document-first, framing), each block re-verified against the whole answer, what still fails dropped with one line saying so (A-42, A-50) |
| 4.3 Ladder | `agent_verify.ladder` | L1 sourced answer · L2 answer with next step · L3 question · L4 labelled general · floor; never a bare "not found" |
| 4.4 Floor | `agent_verify.floor` | Provider down or no usable answer: the strong passages found — the selected document first — quoted and cited, one line saying the assistant could not complete an answer; never a message that blames the reader (P11) |
| 4.5 Renderer | `agent_verify.render` | Prose, one marker group per claim, labelled general explanations, no "Question:" label, one Sources list with each key's location and scope (P4, P7) |
| 4.6 Adversarial set | `tests/test_assist_agent_verify.py` | Number flip, negation flip, paraphrased authority, bare authority, injection in user material, widened scope — all caught |
| P1, P6 | `tools.search_knowledge`, `agent._seed_query`, `agent._context` | The agent's search IS the shipped retrieval (query plan, candidates, cross-encoder rerank; A-39); a seed search runs before the first call, resolving follow-ups as the shipped path does and adding the planner's English subject to a Roman-Hindi question (A-47); the context names the SELECTED DOCUMENT; document claims first (A-40, A-52) |
| P5 | `agent_verify.assessment` | Computed, not taken: `n/a` unless the user asserted something; `supported`/`contradicted` need non-weak evidence (A-43) |
| P8 | `service.preroute` | The shipped pre-router runs first: 0 model calls for social, off-scope and subject-less turns (A-41) |
| Weak evidence | `agent._weak`, `EvidenceRegistry.key_for` | Documents weak only behind a shut gate, as the shipped path admits them (`AM-106`); a record found again by a gated search is no longer weak (A-46) |

Prompt `ask-agent-7`. No lock amended; `AM-111`–`AM-114` cover what this phase relies on.

## Exit criteria

| Criterion | State | Evidence |
|---|---|---|
| V1–V8 unit tests pass | **MET** | `test_assist_agent_verify.py` 35 tests, `test_assist_agent.py` 17, `test_assist_tools.py` 33 — all pass |
| Adversarial results reported | **MET** | 6 of 6 caught: V2 number flip, V3 negation flip, V5 paraphrased authority, V5 policy claim, V6 injection in user material, P2 widened scope |
| Floor tested with a simulated Gemini timeout | **MET** | unit: `test_a_failed_final_call_still_answers_from_what_was_found`, `test_the_hard_deadline_skips_to_an_answer`, `test_p11_the_floor_quotes_sources_and_blames_nobody`; live: G9 with the provider down — floor, 0 calls, three document passages quoted and cited, no blame |
| Dead-end rate 0 on the test pack | **PARTIAL** — the pack's own turns are undefined | on G1–G13 (23 turns): **0** |
| Trap F12 passes | **MET** (A-54) | verifier check F12; 14 unit/end-to-end tests on `indexed_contract`; live G13.1, G13.2 and G8.4 pass (EVALS #43) |
| Traps F1, F2, F3 pass | **NOT MAPPED — owner decision** (A-55) | see "F1–F3: what exists" below |
| Owner: every P1–P11 issue a regression case, root cause fixed, before/after shown | **MET** | table below; 0 FAIL after, 31 FAIL before |
| Owner: same 20-turn evaluation, both paths | **MET** | 21 turns (G1–G12), EVALS #38–#41 |
| Owner: on every selected-document turn the agent is no worse than the current pipeline | **MET PROVISIONALLY — owner decides** | 14 turns × 4 points: no "agent worse" mark; 9 owner-check notes; table below and private sample |
| ruff, mypy, full suite at the exit state | **MET** | ruff clean · mypy clean (138 files) · **3107 passed / 119 skipped / 1 xfailed / 0 failed** after F12 (7 min 27 s; 3093 before it; a first run killed at its 30-min timeout ran beside the four gate jobs — alone it is green). Not committed: the owner's rule is no commit until they say so |
| Retrieval gates not below Phase 3 | **MET** | EVALS #42: frozen set, both probes and golden identical to Phase 3 |

## F1–F3: what exists, and the exact gap (A-55)

| Source the traps could need | State in this environment |
|---|---|
| Company standards | **Available** — Legal Constitution L1.10 (`docs/02-legal-domain/`, and `knowledge_items` in the scratch DB); 79 standard files, 72 active |
| Contract documents and clause text | **Available** — 20 entries in `legal-docs/` (supplied); 57 manifest entries / 32 contracts in the private real corpus; the G-scripts run on them |
| Golden conversations with written pass criteria | **Available** — architecture v2.1 §8, G1–G11 (+ G12, G13 added by this programme) |
| F1, F2, F3 — question, document, pass criterion | **Missing** — only the labels appear (plan §4 exit, §6 table) |

The plan's adversarial categories (4.6) and where they are covered — coverage of a behaviour,
**not** a claim that any of them is F1, F2 or F3:

| Category (plan 4.6 / architecture §9) | Covered by | Meets the written expectation? |
|---|---|---|
| Paraphrased authority ("as per our standards") | unit, adversarial set (V5) | yes, unit level |
| Number and negation flips (6 ↔ 12, shall ↔ shall not) | unit, adversarial set (V2, V3) | yes, unit level |
| Injection inside a pasted email | G5 (live) + unit (V6) | **partly** — G5 does not follow the injected "6 months" and states 12 months from sourced records, but does not tell the reader the email carries that instruction (§8 G5 expects it) |
| Presupposition trap | G2.1 (live) | **no** — the final answer cites clauses but never addresses "why is it not applicable" or says when the cap applies; its reasoning block was dropped (§8 G2 expects the presupposition checked) |
| Wrong-source (another user's document) | G10 (live) | yes — same reply as a missing document |
| Historical vs current | — | **not covered** by any G-script |

## The owner's Phase 3 review — before and after, per issue

Before = Phase 3 run 2 (EVALS #36), after = the final evaluation (EVALS #38–#41); both scored by
the same scorer (`ask_shadow.regression`) on the scripts' current checks. "n/a" before = the
Phase 3 row has no verifier record.

| Issue | Turns checked | Before: FAIL | After: FAIL | Root cause and fix |
|---|---|---|---|---|
| P1 selected document ignored | G1.1, G1.2, G2.1, G2.2, G7.1, G8.1–G8.4, G9.1, G11.1, G11.2, G12.1, G12.2 | 10 (G1.1, G1.2, G2.1, G2.2, G8.1–G8.4, G9.1, G12.2) | **0** | context never named the document; tool search was not the shipped retrieval; weak flag stricter than the shipped path and never lifted; Roman-Hindi seed shut the gate; document facts written into uncited reasoning; answers with no document claim (A-39, A-40, A-46–A-48, A-50–A-52) |
| P2 scope conflation | G1.2, G2.1, G8.1, G8.2 | 0 (4 n/a) | **0** | records carry scope; the verifier keeps it (A-42) |
| P3 cross-turn contradiction | G2.1, G8.3 | 0 (2 n/a) | **0** | attribution, not contradiction — two different agreements; the scorer now judges asserting blocks only (A-44, A-49) |
| P4 citation hygiene | all 21 | 10 | **0** | inline IDs moved into the cite list, ≤ 2 per claim, every C/P/D cite located (`normalise`, V1, `settle`) |
| P5 assessment | G1.2, G4.1, G4.2, G7.1, G8.1–G8.4 | 6 | **0** | computed (A-43) |
| P6 30-day convenience standard | G7.1 | 0 (n/a) | **0** | shipped retrieval reused (A-39) |
| P7 clarifying questions | G8.1–G8.4 | 3 | **0** | V8 and the renderer |
| P8 pre-router | G6.1 | 1 | **0** (0 calls) | `service.preroute` (A-41) |
| P9 conditional framing | G1.1, G2.1 | 0 (2 n/a) | **0** | V7, framed in `settle` |
| P10 cite the agreement for its figure | G11.2 | 0 (n/a) | **0** | P10 check |
| P11 fallback wording | G9.1 | 1 | **0** | the floor (4.4) |

## Selected-document turns — agent vs current pipeline (PROVISIONAL)

Marks per point: 1 the selected document as primary source · 2 the right clause and figures ·
3 no unsupported authority claim · 4 no dead end. **+** agent better · **=** equal ·
**?** owner check. The full table with both answers is in the private sample
(`/root/.legalmind/review/phase4/review.md`, `judgments.json`).

| Turn | 1 | 2 | 3 | 4 | Note (no client text) |
|---|---|---|---|---|---|
| G1.1 | + | = | = ? | = | current found nothing in the document; agent opinion in reasoning is unlabelled |
| G1.2 | + | = | = ? | = | as G1.1 |
| G2.1 | = | = | = | = | both cite the same disclaimer; both miss the document's own cap until G2.2 |
| G2.2 | + | + | = | = | current cited an unrelated confidentiality clause |
| G7.1 | + | + | = | = ? | agent omits the labelled company convenience position that current states |
| G8.1 | = | + | + | = | current attached a TOS position to an MSA question |
| G8.2 | + | + | + | = | current answered from a TOS position only |
| G8.3 | = | + | = | + | current ended on a partial non-answer |
| G8.4 | = | = | = ? | = | an AMENDMENT-type position stated for "signed agreements" (within its subject) |
| G9.1 | = | = | = | = | provider down: floor quotes the same clause current answers with |
| G11.1 | + | ? | = | + | current refused; verify the absence the agent states |
| G11.2 | = | = | = | = | — |
| G12.1 | = | = ? | = | = ? | agent's first sentence garbled; asks the reader to share a clause of the selected document |
| G12.2 | + | + | = ? | = | agent states the absence first; its reasoning restates an MSA position without its scope |

## Final evaluation (21 turns) — EVALS #38–#41

| | Agent | Current pipeline |
|---|---|---|
| Calls per turn | mean 3.1, max 5, 0 over budget | 35 in total |
| Outcomes | 19 answered · 1 pre-routed (0 calls) · 1 floor (provider down) · **0 dead ends** | 19 answered · 2 refusals (G3.2, G11.1) |
| Citations | 74 · **0 weak · 0 invalid** | 30 |
| Latency p50 / p95 | 11.5 / 15.5 s (per stage p50/p95: decision 2.0/5.0 s, final 3.4/3.9 s, repair 0/4.4 s, tools 0.3/0.4 s) | 5.7 / 8.6 s |
| Tokens per call p50 / p95 | prompt 6,499 / 9,910 · output 365 / 577 | — |

## Calls and cost

Phase 4, 2026-10-03: **452 calls** — run 1 100, run 2 109, run 3 99, run 4 98, G8 20, G1 14,
G11 12; ≈ 2.24M prompt + 106k output tokens ≈ **US$0.94 (≈ ₹78)** at Flash list prices
(estimate; the provider console is authoritative). Day total with Phase 3: ≈ 920 of the
1,000 ceiling; no run over its 450 cap. Estimated balance ≈ ₹790.

## Open items (reported, not fixed in this phase)

1. **Test pack** — BLOCKED, owner to supply (A-45).
2. Wording: G11.1's reasoning says "non-weak document evidence" — internal vocabulary
   reached the answer text. A renderer/contract rule, Phase 5 polish.
3. Agent latency is about twice the current pipeline's (p50 11.5 s vs 5.7 s), inside the 25 s
   soft budget. Calls per turn 3.1 against the Phase 3 target of ≤ 3.
4. The owner-check marks above.

---

## Addendum (2026-10-04): Real Conversation Tests v2 as the acceptance specification

The owner supplied *Real Conversation Tests v2* (kept privately, mode 600, never loaded into
the knowledge base) with source-handling rules. Conversations **2 and 6 are holdouts: not run,
not tuned on**. Illustrative answers never enter a prompt; the contract's new rules (A-64) are
general behaviour in its own words.

### Sources: what exists (verified by clause text, A-61)

| Spec ID | Found as | Evidence |
|---|---|---|
| D1 template MSA | the supplied MSA template | 17.1, 17.2 (6 months, specific Services), 17.3, 17.7 (period left blank) all present |
| D3 a client's MSA | **mismatch — not on this machine** | that client's two copies hold no Minimum Service Period, no 5.1/14.3/Initial Term; 0 six-month Minimum Service Periods in any ingested document (A-61). Conversation 2 is a holdout, so nothing was run on it |
| D4 Leapswitch SLA | the supplied SLA | bands 15/40/100 %, below 95.0 % → 100 % |
| D5 CloudPe SLA | the supplied SLA | below 95.0 % → 20 %; 60 calendar days; emergency maintenance ≤ 3 h = scheduled; credit note, void on termination |
| D6 partner agreement | the partner agreement of G11 | 4.2 (10 %), 13.2 (average × 12), 3.2 "listed above", 3.3 → 9.2 |
| Company SLA standard (C5 t5) | Constitution §11 | 10/25/50 %, 30-day claim window — confirmed against the Constitution |
| Intended data-loss position (C1) | **not in the knowledge base** | the only Constitution data-loss text is §11's SLA carve-out; C1 items that depend on it are PENDING, and the agent never invents it |

### Requirement → existing test (only where evidence supports it)

| Spec requirement | Covered by | Evidence |
|---|---|---|
| §0.1 answer first | C-scripts (judged by hand) | no mechanical check; prompt rule A-64 |
| §0.2 sources kept apart | V5, V6, P2, F12, V10 (unit); G1/G4/G5 live | `test_assist_agent_verify.py` |
| §0.3 selected document first; check before "absent" | seed + P1 checks (A-40, A-48, A-50); G12.2, G13.2 live | regression P1 0 FAIL |
| §0.4 connect provisions | C-scripts (by hand) | none mechanical |
| §0.5 certain vs uncertain | V7, computed assessment (P5) | unit + P5 regression |
| §0.6 follow-ups, corrections, pushback, one question, language | G8 (follow-ups, correction), G2.2/G4.2 (pushback), V8, V9 (A-58), G7 | regression + unit |
| Conversation 1 | G2 (incident, data loss, the 12-month claim) — a different copy of the same template; C1 runs the spec itself | G2.1 now checks the presupposition |
| Conversation 3 | G1 (the same email, memo and SLA draft) for turn 1 only; C3 runs the spec | — |
| Conversation 4 | G11.2 (the same partner agreement, commission) partly; C4 runs the spec | — |
| Conversation 5 | none (G12 is a different SLA); C5 runs the spec | — |
| F1, F2, F3 | **unmapped** — still only labels; no evidence of equivalence with any script (A-55) | — |

### Per-turn results against the checklist (final: C1/C3 run 4, C4/C5 run 3)

✔ every non-pending Must met · ◐ some Musts missed · ✖ a Must-not violated · ⏳ pending item.
Versus the current pipeline on the same turn: + better · = equal · − worse.

| Turn | Result | Missed (short) | Pending | vs current |
|---|---|---|---|---|
| C1.1 | ◐ ⏳ | 17.7 not flagged; "a cap is not an entitlement" | intended position, restoration | + |
| C1.2 | ◐ ⏳ | 17.3 dropped this run | provider-side wording, infra vs data | + |
| C1.3 | ✔ | — | — | + |
| C1.4 | ✔ | (absence placed in a general block) | — | + (current refused) |
| C1.5 | ◐ | SLA-credit review, backup not mentioned | — | + |
| C1.6 | ✔ | (sourced claims English by design) | — | + (current refused) |
| C3.1 | ◐ | liability position with MSA scope (cited arbitration) | — | + (current refused) |
| C3.2 | ◐ | how the draft was checked | — | + |
| C3.3 | ✔ | — | — | + |
| C3.4 | ◐ | labelled general explanation | — | = |
| C3.5 | ◐ | what was searched | — | + |
| C3.6 | ◐ | four sources separated; narrowed audit rights | — | + |
| C4.1 | ◐ | "the discount percentage is not stated" | — | + |
| C4.2 | ✔ | — | — | = |
| C4.3 | ✔ ⏳ | — | the template's 6-month cap (not selected) | + |
| C4.4 | ◐ | 8.3 for cause | — | + |
| C4.5 | ✔ | — | — | + |
| C5.1 | ◐ | the 100 % band; cap at the monthly charge | — | − |
| C5.2 | ✖ ⏳ | switch to the CloudPe SLA, 20 % | the CloudPe SLA is not selectable from this turn | − |
| C5.3 | ◐ | void on termination | — | + (current refused) |
| C5.4 | ✖ | only the maintenance hours excluded | — | − |
| C5.5 | ◐ | the governing SLA named; the difference flagged | — | − |

**At this state:** ruff and mypy clean; **3124 passed / 119 skipped / 1 xfailed / 0 failed** (7 min 28 s, normal test environment — a run inside the gates' shell had `LEGALMIND_EVIDENCE_RESCUE=off` set, which fails the two rescue-audit tests by design); retrieval gates identical to Phase 3 (EVALS #46).

**Spec pass bar: NOT MET** — Musts on 7/22 turns (bar 90 %); 2 Must-not violations (bar 0);
the reviewer's 1–5 scores are the owner's. **The no-worse criterion fails on C5.1, C5.2, C5.4,
C5.5.** Dead ends 0; citation checks (P4) 0 FAIL; all mechanical regression checks 0 FAIL.

### Fixed in this round (each with a regression test)

G2.1 (A-50 settle fix, confirmed live) · G5 (A-60 injection notice) · G13.2 (A-56 subject seed +
relevance admission) · selected-document rescue alignment (A-57) · reply language (A-58, V9) ·
internal vocabulary (A-59, V10) · settle survivors (A-62) · search queries recorded (A-63) ·
behaviour rules (A-64) · draft kind (V11). Prompt `ask-agent-10`.

### Decisions needed from the owner

1. **Cross-document reach.** C5.2 and C4.3 need a document other than the selected one (the
   CloudPe SLA; the MSA template). Today Ask searches only the selected document plus company
   sources. Should the agent search the reader's OTHER accessible documents when the reader
   names one ("it was a CloudPe VM")? This widens what a turn can read — a product and
   permission decision, not taken here.
2. **The intended data-loss position.** C1 depends on it; it is not in the knowledge base.
   Supply and ratify it (it then enters as a standard), or confirm C1's dependent items stay
   pending.
3. **D3.** Which document is D3? The copies here do not contain the clauses the spec cites.
4. **F1, F2, F3.** Still undefined (A-55).
5. **Language of verified claims.** Sourced claims stay English because the local claim
   verifier is English-only; the explanation follows the user's language. The spec scores the
   whole reply's language. Accept this, or fund a multilingual verifier (a model change).

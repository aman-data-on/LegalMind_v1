# Ask AI quality programme — status, decisions, risks, evidence

📁 **WORKING DOCUMENT.** Records status and reasoning; decides nothing and locks nothing.
Locked decisions live in [all_lock.md](../../all_lock.md); conflicts in
[CONFLICTS.md](CONFLICTS.md); build state in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

**Opened 2026-09-15** on an owner instruction to make Ask AI behave as a reliable
Gemini+RAG legal assistant rather than a keyword box, run as a continuous
inspect → implement → test → document loop.

**The pipeline this programme is building is the owner's ten-stage map**, recorded 2026-09-17 in [ASK_TARGET_ARCHITECTURE.md](ASK_TARGET_ARCHITECTURE.md) §0: conversation context → query understanding → knowledge router + authority policy → query planner → authorized targeted retrieval → reranker → evidence sufficiency gate → grounded generation → answer verification → response. Phases below map onto those stages; name the stage when reporting on one.

---

## A. Implementation status by phase

| Phase | Scope | State | Branch |
|---|---|---|---|
| **0a** | Protect uncommitted source-leak work | ✅ **DONE** | `fix/ask-source-leak` `f5fc324` |
| **0b** | Rebase + merge `feat/p1-rag-quality` | ⏳ still unmerged — another session's branch, not mine to land | — |
| **1** | Language safety screens (F-1, F-2) | ✅ **LIVE** — `AM-69` locked, deployed | merged `980249d` |
| **2** | Source leak + citation quality (F-5, F-6) | ✅ **LIVE** — re-chunk run in production 2026-09-16: `position_chunks` 32 → 40, **leaked 28 → 0** | merged `5044048` |
| **3** | Answer-type routing, capability + general-knowledge shapes (F-4) | ✅ **LIVE** — `AM-68` locked and enabled; general-knowledge route deployed | merged `9c489cb` |
| **4** | Retrieval quality | ✅ **LIVE** — lexical demoted to fallback (its `ts_rank` measured flat); noise gone. Reranker still untried | merged `9c489cb` |
| **5** | Template drafting | ⛔ **BLOCKED** — no approved output template (rule 21) | — |

### Everything below is merged, deployed and verified in production

Verified 2026-09-16 against the live system. `main` is `9c489cb`; the API, worker and
frontend are running from it.

| Check | Result |
|---|---|
| Re-chunk (the write-time half of the leak fix) | run in production — `position_chunks` 32 → 40, **leaked 28 → 0** |
| Grounding fails closed on an unreadable claim | live |
| Comparison routes to the evaluator in English, Hinglish, Devanagari | live |
| Capability and general-knowledge routes | live, zero retrieval |
| Retired standards excluded from retrieval (`AM-71`) | live — retired queries return nothing, 7 chunks preserved for history |

> This section previously read *"Nothing is merged or deployed"* and listed the three
> defects as still present in the deploy tree. That was true on 2026-09-15 and became
> false on 2026-09-16. Corrected rather than deleted, because a status document that has
> been wrong is worth knowing about — this one is read by the greeting protocol, and a
> stale "nothing shipped" is the kind of claim a session acts on.

---

## B. Decision update log

No locked decision has been changed. Nothing has been appended to `all_lock.md`.

| ID | Status | Old | Proposed | Why | Evidence |
|---|---|---|---|---|---|
| `AM-67` | ✅ **LOCKED 2026-09-15** (AB-21), deployed | `AM-32` r4: Domain A output extractive only | Domain A as a controlled reading aid — synthesis beside an unchanged verbatim quote | A quote alone is not an answer for a non-lawyer; authority is preserved structurally rather than by trusting the model | plan §4 |
| `AM-68` | ✅ **LOCKED 2026-09-15** (AB-21), deployed — owner chose option (b), rendered not generated | no capability question shape exists | Manifest-grounded capability route, zero retrieval | "What can LegalMind do?" currently searches the Constitution and dumps standards | F-4 |
| `AM-69` | ✅ **LOCKED 2026-09-15** (AB-21), deployed | locks silent on language | Language is not a safety boundary; a screen that cannot evaluate an input fails closed | F-1/F-2 — guarantees worded as universal were enforced only in English | measured, §D |
| `AM-73` | **PROPOSED, deferred** (renumbered from `AM-70`, now a locked record on client-profile deletion) | `AM-26` r4 pins `all-MiniLM-L6-v2` | A multilingual embedding model | Hindi retrieves at 0.037–0.138 cosine, below the 0.50 gate | `RESEARCH_DOMAIN_C_RD_2026-09-04.md` §2 + §D below |

| `AM-71` | ✅ **LOCKED 2026-09-16** (AB-23) — *another session's record, closing a gap this programme surfaced* | `AM-65` never said whether a retired standard stays searchable | **A retired standard is not retrievable in Ask.** Labelling it "Superseded" is not the remedy; it is excluded from the lexical AND vector paths, chunks preserved for history (r4) | The 32 → 40 measurement recorded here |
| `AM-72` | **PROPOSED, not approved** (renumbered from `AM-71`) | `AM-25` r5 requires every claim to resolve to retrieved evidence | Generating a general-knowledge explanation | Off behind `LEGALMIND_GENERAL_KNOWLEDGE`; the non-generated redirect ships and needs no amendment |

### Engineering decisions taken autonomously (no lock touched)

| # | Decision | Reasoning |
|---|---|---|
| E-1 | Sanitize `source_document` on the way out; **do not edit the 40 ratified files** | They are configuration and the locator is provenance metadata, not ratified legal text. `source_quote` is untouched, so `AM-32` r4's verbatim requirement holds |
| E-2 | The locator pattern is **general**, not an enumeration of the six strings this corpus uses | A first draft matched only `/`, `.md`, `.pdf`, `LEGALMIND_*` and leaked Windows and UNC paths. A seventh ratified file must not reopen the leak |
| E-3 | Grounding **fails closed** when content words cannot be extracted | `AM-25` r5 requires mechanical enforcement. A screen that cannot read a claim has not verified it. The remedy for a language the check cannot compare is a check that can, never a default that lets it through |
| E-4 | Signing-readiness routes to the **evaluator** as a holding position | It asks for strictly more than a compliance verdict; the evaluator answers with Findings rather than a generated yes/no. Phase 3 gives it a structured route |
| E-5 | Ratification status is rendered **only when not ACTIVE** | Stamping ACTIVE on every citation trains the eye to skip the field, which is exactly when DRAFT/DEPRECATED must be noticed |
| E-6 | Replay `retrieval_score` for positions **deliberately left null** | `_persist_retrieval` never wrote `position_hits`, and the score is never rendered (rule 12). A JSONB key plus a recovery join for a value no reader sees is cost without a reader; upgrade path recorded at the call site |
| E-7 | Romanized `is` / `us` / `use` **excluded** from the Hinglish anaphora set | They collide with the English verb, pronoun and verb. Including them made "What **is** the termination notice period in this agreement?" a follow-up. The inflected forms are unambiguous |

---

## C. Risk and conflict register

| ID | Risk | Severity | State |
|---|---|---|---|
| **F-1** | `AM-25` r5 defeated for Devanagari — fabricated claims passed the guardrail | 🔴 HIGH | fixed on branch, **live in production** |
| **F-2** | `AM-25` r4 bypassable by asking in Hindi/Hinglish | 🔴 HIGH | fixed on branch, **live in production** |
| **F-5** | Internal paths and a counterparty note rendered to users | 🟠 | fixed in code, **live in the indexed corpus** until re-chunk |
| **F-3** | Hinglish retrieval swings 0.315–0.537 on phrasing alone | 🟠 | open — Phase 4 |
| **F-4** | Constitution searched for every question | ✅ | **CLOSED** — capability route (`AM-68`) and general-knowledge route, both live |
| **F-7** | Faithfulness 1.0 measured on 33 of 64 answerable questions | 🟡 | **documented** in ASSIST_LANE_AND_RAG.md 2026-09-15 |
| **F-8** | Multi-document conversations do not exist; "compare A with B" impossible | 🟠 | **OD-A** — product decision required |
| **F-9** | Four residual dead-citation paths | 🟡 | open, low value |
| **C-22** | 15 standards split 7/8 citing Constitution L1.5 vs L1.10 | LOW | registered, **deliberately unclassified** pending owner |
| **R-1** | No approved output template | BLOCKER | owner must supply |
| **R-2** | No Hindi/Hinglish evaluation set | MEDIUM | owner decision |
| **R-6** | No `LEGALMIND_TEST_DATABASE_URL` in any worktree | **BLOCKER** | 907 tests unrun; blocks Phases 2-completion and 4 entirely |

---

## D. Test evidence

Recorded per the brief: exact command, counts, scenarios, failures, remaining limits.
**"Tests passed" is not evidence.**

### D.1 Language safety — `d3b9985`

```
cd backend && python3 -m pytest tests/test_assist_language_safety.py -q
  -> 50 passed in 0.13s
cd backend && python3 -m pytest tests/test_assist_intent.py tests/test_assist_language_safety.py -q
  -> 96 passed in 0.17s          (the pre-existing English matrix is unchanged)
```

Reproductions, before and after, measured against the shipped code:

| Input (document attached) | Before | After |
|---|---|---|
| "ABC agreement Company Constitution ke according hai?" | GENERATIVE | **EVALUATOR** |
| "Kya humein ABC agreement sign karna chahiye?" | GENERATIVE | **EVALUATOR** |
| "हमारे मानक से तुलना करें" | GENERATIVE | **EVALUATOR** |
| Devanagari answer: fabricated ₹50 lakh cap + verdict, cited `[1]` | **ANSWERED** | `CLAIM_UNSUPPORTED` |
| "Yeh clause Company Standard ke according nahi hai." | reached user | **BLOCKED** |

**One self-inflicted failure, found and fixed in-loop.** The first run was 49/50: adding
romanized `is`/`us`/`use` to the anaphora set made *"What is the termination notice period in
this agreement?"* a follow-up. Caught by the negative half of the matrix, which is why every
positive case has a negative twin.

### D.2 Citation quality — `c82f5ff`

```
cd frontend && npx vitest run
  -> Test Files 34 passed (34) · Tests 474 passed (474) in 3.20s
cd backend && python3 -m pytest tests/test_assist_positions_sanitization.py -q
  -> 25 passed in 0.12s
```

### D.3 Source-leak sanitizer — `f5fc324`

25 cases: Linux path ± extension · Windows path ± extension · UNC · home-relative · known and
unknown env vars · em-dash before and after the name · no em-dash · null · empty · int · dict ·
missing key · nested parens · counterparty note · all 7 real `source_document` values · all 40
ratified standards (`source_quote` byte-exact substring) · indexing · egress.

### D.4 Full backend suite

```
cd backend && python3 -m pytest tests/ -q --ignore=tests/test_positions.py
  -> 945 passed · 115 skipped · 1 xfailed · 907 errors · 0 FAILED   (242.03s)
```

**Zero assertion failures. 907 errors are all fixture-setup `password authentication failed`.**
Note the process **exited 0** despite them — a green exit here means almost nothing, which is
exactly why the counts are recorded rather than the exit code.

### D.5 Measurements taken this cycle

Embedding cosine against a real English NDA confidentiality clause, using the project's own
pinned model, gate floor `COSINE_FLOOR = 0.50`:

| Question form | cosine | outcome |
|---|---|---|
| English | 0.718 | answers |
| Hinglish, 2 English legal nouns | 0.537 | clears by 0.037 |
| Hinglish, "Ismein confidentiality period kya hai?" | **0.509** | clears by **0.009** |
| Hinglish, prior art (`RESEARCH_DOMAIN_C_RD` §2) | 0.315 | refuses |
| Romanized Hindi, no English nouns | 0.138 | refuses |
| Devanagari, prior art | 0.037 | refuses, below noise |
| English negative control | 0.090 | correctly refuses |

Not a contradiction of the 2026-09-04 prior art — a refinement. Hinglish rides on its English
legal **nouns**, so the outcome swings on phrasing alone. Same intent, different words,
different answer.

### D.7 DB-backed validation (2026-09-15, after the test credential was supplied)

**⚠️ How to run the suite — do NOT source the whole env file.** `/root/.legalmind.env`
sets `LEGALMIND_BROKER_URL` and `LEGALMIND_GEMINI_API_KEY`. Sourcing it wholesale makes
indexing queue to a worker that is not running (every retrieval test then fails with
`NO_EVIDENCE_RETRIEVED`) and puts a **live Gemini key** in reach of any test that does not
fake generation. Six tests "failed" on clean `main` for exactly this reason before the
environment was narrowed. Run with the test DB only:

```bash
TESTURL="$(set -a; . /root/.legalmind.env; set +a; \
           echo "${LEGALMIND_DATABASE_URL/legalmind_v1_dev/legalmind_v1_test}")"
env -u LEGALMIND_BROKER_URL -u LEGALMIND_GEMINI_API_KEY -u LEGALMIND_DATABASE_URL \
    LEGALMIND_TEST_DATABASE_URL="$TESTURL" \
    LEGALMIND_SOURCE_MATERIAL_DIR=/root/Legalmind.v1/legal-docs \
    python3 -m pytest tests/ -q -p no:randomly
```

The URL substitution is positional: if the env file ever stops containing
`legalmind_v1_dev` it becomes a silent no-op and the "test" URL points at whatever the file
holds. Worth pinning `LEGALMIND_TEST_DATABASE_URL` explicitly instead of deriving it.

| Run | Result |
|---|---|
| `main`, assist suite, minimal env | **57 passed, 0 failed** (baseline) |
| `fix/ask-source-leak` — positions + ask + sanitization | **97 passed, 0 failed** — the two new SQL joins execute |
| `fix/language-safety-screens` — six assist suites | **198 passed, 0 failed** (after the fix below) |

**Two tests were green because of the bug.** `test_D_a_statutory_question_is_answered_from_the_statute_corpus`
and `test_document_and_statute_answers_stay_in_separate_sections` failed on the language-safety
branch and passed on main. Both use a generation double returning
`evidence[0].split(".")[0] + " [1]."`; a statute chunk opens with its section number, so the
"answer" was the string `"3 [1]."` — a claim with an **empty** content-word set, admitted
vacuously by the old `overlap = ... if claim_words else 1.0`. The same hole that passed a
Devanagari hallucination. The doubles now return the first sentence that says something;
**no assertion changed**. Fixed in `a6d6078`.

### D.8 AC-12 — the 77-question release gate (2026-09-15)

Run on `fix/language-safety-screens` with `LEGALMIND_GEMINI_API_KEY` **deliberately unset**,
so no payload egressed and no cost was incurred. The harness degrades honestly: it skips the
two generation-dependent metrics and still measures retrieval through the shipped
`search_hybrid`.

Two things had to be resolved first, neither of them a defect: the gate uses its own
`legalmind_v1_tier2_gate` database (it **exists** — the first failure was authentication,
not absence), and it reads `LEGALMIND_BENCH_DATABASE_URL`, which was falling back to a
default password.

```
wrongly answered   1/13   (N-11)
correct refusals   12/13
retained           43/64   (false refusals 21)
recall@10          0.625
hit@1              0.375
faithfulness       BLOCKED — no API key, by choice
citation precision BLOCKED — same

pass   wrongly-answered rate held: 1 <= baseline 1
pass   recall_at_10 held: 0.625 >= baseline 0.625
pass   retained held: 43 >= baseline 43

SHIPPABLE — the measurable half of the AM-28 gate holds.
```

**AC-12 is met for this branch**: the language-safety change does not raise wrongly-answered,
and neither recall nor retention regressed. Faithfulness and citation precision remain
unmeasured; scoring them needs real Gemini calls on the owner's key, which is an explicit
approval item.

### D.9 The evidence-rescue judge — the recall result (2026-09-16)

The gate, not retrieval, was the bottleneck. Measured on the ratified 77-question set:
of 64 answerable questions it refused 21, and **15 of those already had the gold chunk
retrieved**. Recall could reach 0.859 by fixing the decision alone.

Three cheaper fixes were measured and rejected first:

| Lever | Result |
|---|---|
| 35-combination sweep of `COSINE_FLOOR` × `PEAK_MARGIN` | **no** configuration raises recall without raising wrongly-answered; the frontier is monotonic |
| A second feature — IDF-weighted question/chunk overlap | false refusals **0.185**, unanswerable **0.196**; top-cosine 0.443 vs 0.447. Indistinguishable |
| A different embedding model | 2026-08-26 bake-off: `gte-small` 11/13 · 45/64 against MiniLM's 12/13 · 41/64 — the same trade |

`calibration.py` had already recorded why: *"those score INSIDE the answerable
distribution, so no similarity feature separates them, for any candidate."*

**Result, with the real model, calling the judge on the 33 refused questions:**

```
baseline   retained 43/64   recall 0.625   wrongly answered 1/13
rescued    13 correct        0 wrongly opened
result     recall 0.828      wrongly answered 1/13  — UNCHANGED
```

The judge refused all twelve genuinely unanswerable questions it was shown. This is the
first lever measured that satisfies the owner's 2026-09-14 rule — recall improves
without a rise in wrongly-answered.

Two questions (`Q-09`, `Q-38`) were rescued onto non-gold chunks. Neutral rather than
harmful: the attempt still faces the grounding screens, which is what rejects an answer
that does not resolve to its evidence.

**Caveat on the official gate.** `verify_assist_quality.measure()` calls
`store.search_hybrid` directly, so it does not exercise the rescue, which lives in
`service.ask`. The figures above come from a direct measurement over the same ratified
dataset with the same model. The harness should grow a service-level path before its
printed recall can be read as the user-facing number.

### D.6 What has NOT been tested

- **907 DB-backed tests** — no `LEGALMIND_TEST_DATABASE_URL`.
- **The 77-question benchmark** (`verify_assist_quality.py`) — needs the DB. **AC-12 (no rise
  in wrongly-answered) is therefore unverified for every change in this programme.**
- **The two new SQL joins** in `positions.py` — type-checked and unit-exercised, never executed.
- **End-to-end in a browser** — nothing is deployed.

---

## Next actions

**Deployment is prepared**: [ASK_AI_DEPLOYMENT_RUNBOOK.md](../09-implementation/ASK_AI_DEPLOYMENT_RUNBOOK.md)
carries the order, the staging evidence, the mandatory re-chunk, rollback per failure mode
and post-deploy checks. No migration is required by any branch.

**Unblocked, still to do:** the reranker (Phase 4's one untried lever) · the remaining
answer types from the brief's §2 that do not need an amendment · F-9's dead-citation paths.

**Needs the owner:** `C-22` provenance (L1.5 vs L1.10) · `OD-A` multi-document conversations ·
an approved MSA/NDA output template · `AM-72` if a generated general-knowledge answer is
wanted · whether `LEGALMIND_POSITION_SYNTHESIS` is turned on (it begins real egress).

**Closed since this document was written:** the test DB URL was supplied; `AM-67`, `AM-68`
and `AM-69` are locked and deployed; `AM-71` (another session's record) settled the
retired-standard question this programme raised; `F-4` is fixed and live.

---

## Recorded 2026-09-17 — union grounding in `verify_answer` was never a decision

**Surfaced while verifying Phase 0's re-verification fix; not changed.** `guardrails.verify_answer`
grounds a sentence against the **union** of the content words of every chunk it cites
(`set().union(*(_content_words(c) for c in cited_chunks))`). The code carries no comment on the
choice and nothing in `docs/` or `all_lock.md` records it. Consequences, measured on the gate
database:

- A sentence citing `[1][2]` can clear the 0.5 floor while grounding in **neither** chunk alone —
  one live answer's sentence overlapped its own first cited chunk at **0.42** and passed only
  through the union.
- The floor does not scale: 0.5 against a union of five chunks is a far weaker claim than 0.5
  against one, and the model chooses how many chunks to cite.
- This is the shape of one hallucination the screen exists to catch — half a fact from A joined to
  half from B into a claim neither supports — and it would pass, quietly. `AM-69` r2 made a screen
  that *cannot* evaluate refuse; a screen that evaluates against an ever-larger union is not
  failing closed, it is passing on weaker evidence.

Union grounding is also **right for the ordinary case**: a sentence that legitimately draws on two
clauses would be rejected by a per-chunk floor. So this is not a bug to patch; it is a grounding
rule that needs deciding and then measuring — per-chunk minimum, a floor that tightens with the
number of citations, or the union as it stands, each against the 77-question gate's faithfulness
and false-refusal counts. **Owner-facing.** Raised beside the `AM-67` enable rather than left
between sessions.

---

## Phase 1 of the target architecture — the query planner, measured (2026-09-17)

**Outcome: a clean negative result on this corpus. The planner is accurate and too slow, and by
design it cannot move the metric that matters.** Code on `feat/ask-planner-p1` (built, tested,
type-clean, fail-closed, OFF by default); whether it merges is the owner's call — see the PR.

**What was built.** `assist/planner.py`: one provider call returning what a question is ABOUT — a
Constitution Appendix-B topic (14, read off the ratified standards), a subject, whose position,
which source, up to three reformulated search phrases. Advisory: it narrows Domain A to its topic
(`positions.search_positions(topic=)`, a WHERE clause inside both queries) and adds locally
embedded reformulations to the document search (`store.search_hybrid(extra_queries=)`, rank-fused).
It runs after every deterministic screen, never for the evaluator's question, cannot add a domain,
cannot open the gate, is never cited, and fails closed to today's path. Payload: the question and
the `AM-58` prior questions — a subset of what generation sends. The gate now measures through
`service.plan_question` → `service.retrieve_document`, the same two calls `service.ask` makes, and
reports three targeting measures from the dataset's own `section` anchors: MRR, gold-in-top-3,
evidence precision.

**What was measured** (77 ratified questions, production path, same anchors; Phase 0 run as the
before; 75 of 77 questions planned in the after):

```
same tool, same 77 questions, same anchors      planner OFF    planner ON (75/77 planned)
wrongly answered (13 unanswerable)                 1/13           1/13
user-visible wrongly answered                      0/13           0/13
retained / false refusals                         60/64 · 4      62/64 · 2
recall@10                                          0.891          0.922
hit@1                                              0.594          0.609
MRR                                                0.701          0.728
gold-in-top-3                                      0.797          0.828
evidence precision (gold share of chunks sent)     0.390          0.358      ← down
faithfulness / citation precision                  1.0 / 1.0      1.0 / 1.0
Gemini calls per question                          1.23           2.25
prompt / output tokens (77 q)                 119,572 / 4,699  147,115 / 13,745
planning p50 / p95 ms                                 —          4,788 / 8,296
generation p50 / p95 ms                         3,930 / 9,748   5,340 / 9,921
retrieval p50 / p95 ms                             12 / 33         27 / 42
total p50 / p95 ms                              5,945 / 13,416  10,558 / 17,070
```

Reading it: the four targeting and recall movements are each about **one question of 64** — inside the
evidence rescue's run-to-run swing, which has read 60, 61 and 62 retained on identical code today
— while the one metric with a consistent mechanism behind it, evidence precision, **fell** (wider
unions hand generation more non-gold chunks) and latency nearly **doubled**. Safety held throughout.
No targeting gain is demonstrated; a real latency and cost is.

**Three findings, each with its number.**

1. *The planner is slow, and it is the provider.* A ~150-token JSON plan from `gemini-3.6-flash`
   at `thinkingLevel: MINIMAL` takes **2.4–8.0 s**, bimodal (~2.4 s or ~7.9 s). The proposal
   assumed 300–500 ms — wrong by an order of magnitude. At a 4 s cap only **26 of 79** retrievals
   received a plan and the run measured a timeout, not a planner; it is not reported. At 10 s,
   75 of 77 planned and the ask's total p50 went **4.7 s → 10.6 s**.
2. *A reformulation cannot fix a false refusal — by design.* The gate decides on the question's
   own scores (`AM-25`'s calibrated refusal, unchanged). "How much time do we get to fix a breach?"
   produced exactly the right reformulations ("cure period for breach of contract", "written notice
   to remedy default days") and was still refused on the real MSA when the rescue judge said NO.
   Letting a reformulation open the gate is a widening of the calibrated control and must be
   measured against the 13 unanswerable questions first (owner rule 2026-09-14: recall may only
   improve WITHOUT wrongly-answered rising). Held for the reranker phase.
3. *Domain A narrowing works; the gap it exposes is ranking, not targeting.* "Termination period of
   LeapSwitch" → the one Termination-topic standard clearing the floor instead of three standards
   from three topics. The answering standard, `CONVENIENCE-NOTICE-MSA-001` ("terminate for
   convenience with 30 days' written notice"), was reached by neither configuration, measured on
   the live corpus: cosine **0.288** against the question (the cure-period standard: 0.651 — the
   embedding reads "termination period" as a cure period), **0.467** against the planner's best
   reformulation (under the 0.50 evidence floor), 0.607 only for a phrasing that says "notice".
   Applying reformulations to Domain A would not have fixed it and is not proposed on this evidence.

**Where the evidence points.** Three directions at once — the boundary refusal in (2), the 0.288
in (3), and hit@1 flat with evidence precision falling as the union widened — all describe a
ranking problem inside a correctly retrieved candidate set. That is the reranker's job, which
`AM-25`/`AM-26` already authorise and which was always the held Phase 2. The multi-query candidate
pool the planner builds is the input a reranker would consume; it is worth nothing without one.

**Also recorded here:** the position corpus's chunk text embeds the standard code and citation
header ("CONVENIENCE-NOTICE-MSA-001 §13 (MSA) — Legal Constitution, Lawyer Review Version L1.10:
…") ahead of the ratified sentence, which dilutes every position embedding. Not changed; noted
for the reranker phase, where chunk composition for Domain A should be measured.

---

## Recorded 2026-09-17 — the evidence rescue's cost, visible for the first time

Phase 0's stage timings went live at `663971f` and within a minute the other session read this
from the production journal for one Ask:

    assist.ask.timings   total 4783 ms   rescue 4372 ms   retrieval 8 ms   positions 394 ms

The rescue judge was **91 %** of that request's latency. Beside it: `assist.ask.rescued` has fired
**zero** times in the entire production journal — the judge has cost a provider call on roughly a
third of questions (every shut gate) and has not yet changed a single outcome for a real user. The
Tier-2 gate measured the same judge lifting recall 0.625 → 0.828 with wrongly-answered unchanged
(2026-09-16). Both are true: the gain is real on the ratified set; the cost is real on every
refusal; single-digit live traffic proves nothing about the gain. This is **not** an argument to
turn it off — it is the trade recorded as a trade, now that Phase 0 made the cost a number rather
than an estimate. The reranker phase is where the same recall is expected from a local,
deterministic step at a few hundred milliseconds; when that is measured, the rescue's remaining
value is what it adds *on top of* the reranker, and that is the comparison to run.

---

## Phase 2 of the target architecture — the reranker bakeoff (2026-09-17)

**Outcome: it earns enablement for REORDERING, and is measured to be unusable for
gate-opening.** Code on `feat/rerank-bakeoff`, `LEGALMIND_RERANK` default OFF; whether it
ships is the owner's call. The planner was OFF throughout, so this isolates the reranker.

**No amendment needed.** `AM-25`'s permitted list already names "hybrid retrieval with
reranking" and `AM-26`'s stack table already names a "Reranking model | local,
self-hosted, open-weight, cross-encoder". What applies is r2 (smallest upward, stop at
the first that passes), r3 (real supplied material, unanswerable questions included),
r4/r5 (pinned, checksummed, never fetched at runtime) — all satisfied by the existing
`tools/provision_model.py` and a new `OnnxCrossEncoderBackend` beside the embedding one.

### Selection — `AM-26` r2, offline bakeoff over a 30-candidate pool

| candidate | recall@10 | MRR | gold@3 | hit@1 | verdict |
|---|---|---|---|---|---|
| none | 0.641 | 0.480 | 0.562 | 0.391 | — |
| `ms-marco-TinyBERT-L-2-v2` (18 MB) | 0.609 ↓ | 0.480 | 0.547 ↓ | 0.406 | **fails** — worse than no reranker |
| **`ms-marco-MiniLM-L-6-v2` (91 MB)** | 0.641 | **0.553** | **0.594** | **0.500** | **passes → selected** |
| `ms-marco-MiniLM-L-12-v2` (134 MB) | 0.641 | 0.542 | 0.578 | 0.484 | not better, 2× the latency |

Pinned at commit `233902d25c440f23af6f7d6e94d2946bac0bee0a`, SHA-256 recorded, CPU-only.

### Pipeline measurement — full Tier-2 gate, planner off, TWO passes

| | rerank OFF | rerank ON (pass 1 / pass 2) |
|---|---|---|
| wrongly answered | 1/13 | **1/13 · 1/13** |
| user-visible wrong | 0/13 | **0/13 · 0/13** |
| false refusals | 3 | **3 · 3** |
| retained | 61/64 | 61 · 61 |
| recall@10 | 0.891 | **0.906 · 0.906** |
| hit@1 | 0.609 | **0.734 · 0.734** |
| MRR | 0.709 | **0.796 · 0.796** |
| gold@3 | 0.797 | **0.844 · 0.844** |
| evidence precision | 0.400 | 0.409 · 0.408 |
| faithfulness / citation precision | 1.0 / 1.0 | **1.0 / 1.0** both |
| rescue usage (p95 ms) | 1501 | 1482 · 1463 — unchanged |
| Gemini calls / question | 1.23 | 1.22 · 1.23 |
| rerank stage p50/p95 ms | — | 116/443 · 132/511 |
| total p50 / p95 ms | 1738 / 3321 | 1943/3401 · 2020/3465 |

**The ordering gains are identical to three decimals across both passes** — the reranker
is local and deterministic, so unlike the query planner its result carries no provider
noise. For scale: today's five rerank-OFF runs put hit@1 in a 0.594–0.625 band; 0.734 is
far outside it. `user_answered` (55/47/49/52/50 off, 53/51 on) swings on provider
behaviour and is inside its own noise band either way.

### The measured limit — a rerank floor CANNOT reopen a shut gate

For a floor to be safe, the answerable questions the gate wrongly refuses must score
ABOVE the 13 with no answer. Measured top rerank score by group:

```
MiniLM-L-6    false_refusal  n=20   min -10.48   median -3.12   max 1.89
              unanswerable   n=13   min  -8.72   median -2.30   max 3.38
```

The unanswerable median is **higher**, and the ranges overlap almost entirely; L-12 and
TinyBERT are the same shape. This is the **fourth** independent feature to fail this
separation, after the 35-point threshold sweep, the IDF-weighted overlap and the
embedding-model swap (2026-09-16). The reranker therefore reorders only — no floor, no
gate change — and that boundary is enforced in code and pinned by test.

### What it does not do

* **It does not touch Domain A.** As wired it reorders document evidence only. Company
  standards keep their existing lexical/vector retrieval.
* **It does not recover a refusal.** 20 questions have the gold chunk in the pool with the
  gate shut; only a gate change reaches those, and the paragraph above says a rerank score
  cannot make that change safely. Those remain the rescue judge's.
* **The key-case "termination period of LeapSwitch" is unchanged** (#18 → #20 in Domain A):
  every cross-encoder reads "termination period" as the cure period, exactly as the
  embedding does. ⚠️ The gold for that case is an assignment made during this work, not a
  ratified anchor, and the models' reading is defensible — recorded as an open question
  about the QUESTION, not a reranker failure.

### Merged as reorder-only; the query planner is NOT in this change

`feat/reranker` carries the cross-encoder, the shared `service.retrieve_document`
composition (retrieve → pin → reconsider → reorder, the one function `service.ask` and
the Tier-2 gate both call) and the three targeting measures. It does NOT carry Phase 1's
query planner: `planner.py`, `LEGALMIND_QUERY_PLANNER`, the Domain A topic filter and the
multi-query fusion stay on `feat/ask-planner-p1`, parked by owner decision 2026-09-17
after the Phase 1 measurement showed no demonstrated targeting gain for +4.6 s p50. The
Phase 1 FINDING is recorded above; only its code is parked.

---

## Recorded 2026-09-17 — a false refusal in production, and it is NOT the grounding floor

**Found by the second session's verification probe after the reranker enablement; diagnosed
here. Not fixed — false-refusal work is out of scope by owner instruction, and this is
recorded so the fix is designed from evidence rather than from a guess.**

The probe asked the NDA *"When does this agreement terminate and what survives?"* — a
question clause 9 ("Term and Survival") plainly answers, and which the probe's own previous
question had cited a minute earlier. Retrieval found it, the reranker ranked it, generation
used it, and `verify_answer` rejected the answer on 3 failures. The turn fell through to
POSITIONS and the reader got no document citation. Failing closed, so nothing wrong reached
anyone — but a correct, cited answer was thrown away. `request_id
d368b198045e40a18bb5affb82819a03`.

**It reproduces only sometimes, which is the first finding.** Six generations, temperature
0.0, byte-identical evidence (6 chunks), same question:

```
run 1  ANSWERED  failures=0  worst sentence overlap 0.86
run 2  REFUSED   failures=1  worst 0.48
run 3  REFUSED   failures=4  worst 0.48
run 4  REFUSED   failures=2  worst 0.50
run 5  REFUSED   failures=2  worst 0.50
run 6  ANSWERED  failures=0  worst 0.50
                                    2 of 6 passed
```

**The second finding is the real one, and it is not a threshold problem at all.** The
dominant failure is `unsupported claim (no citation): 'Regarding what survives:\n1.'` and
`'2.'` — `_SENTENCES` splits on `(?<=[.!?।॥])\s+`, so the "1." and "2." of a NUMBERED list
are each split off as their own sentence, carry no `[n]` marker, and are counted as
unsupported claims. Proven on a minimal case: the same content, the same evidence, one
written with `1.`/`2.` and one with `*` bullets —

```
numbered '1.'  ->  CLAIM_UNSUPPORTED   failures=2
bulleted '*'   ->  ANSWERED            failures=0
```

So **an answer is rejected for its list style**, not for its grounding. `grounded-answer-2`
does not constrain formatting, so whether a given generation uses `1.` or `*` is left to the
model — and roughly two thirds of the time on this question it chose the style the screen
cannot parse.

**Three candidate fixes, none applied, each cheap to measure against the ratified 77:**

1. Do not treat a bare list marker as a sentence — require a sentence to contain at least
   one content word before it can be an unsupported claim. Smallest change; fixes the
   dominant cause; touches `AM-25` r5's enforcement so it needs the Tier-2 gate run and a
   record.
2. Constrain the prompt to one list style. Cheapest of all, but it makes a mechanical
   guarantee depend on the model obeying a formatting instruction — which is exactly what
   `AM-28` r2 says a guardrail must not do. **Not recommended.**
3. Leave it and accept the refusals. Currently what happens; it fails closed and states
   nothing false, at the cost of discarding correct answers.

**Relationship to the union-grounding question already with the owner** (recorded above):
they are the same screen and should be decided together, but they are different defects.
Union grounding is a floor that can pass a claim no single clause supports; this is a
splitter that rejects a claim every clause supports. The 0.48/0.50 figures above show this
question also sits exactly on the 0.5 boundary, so both would bite here.


## Phase 1, second attempt — the cheap path, measured (2026-09-18)

**Outcome: the COST problem is solved and the targeting problem is not, and the second
half is now proven rather than suspected.** The planner stays OFF; widening gets its own
flag and stays OFF. Nothing about this was forced into production.

**What changed.** `planner.plan()` now reaches the provider only for a question it cannot
place by itself. Three outcomes, cheapest first:

1. `plan_lexical` places it — one table maps a reader's words to the legal term and to
   the Constitution Appendix-B topic that term belongs to. No call, no latency.
2. Nothing placed it and it reads plain and self-contained — no plan, no call, retrieval
   exactly as today.
3. Nothing placed it and it reads ambiguous (multi-part, conditional, comparative,
   referential) — only here is the provider asked.

The table is search vocabulary, the same kind of object as `statutes._ACT_ALIASES`, and
an import-time assertion refuses any topic the ratified standards do not carry. It
states no threshold, no position and no acceptance policy; a test enforces that.

**The cost result, on the 77-question set through the production path:**

```
                                   planner OFF      Phase 1 (2026-09-17)   Phase 1 (this)
planning p50 / p95 ms                 0 / 0            4,788 / 8,296          0 / 2,028
gemini planner calls per question       0                   1.00                 0.18
total ask p50 ms                      2,248                 ~10,600              2,252
```

44 of 77 questions are placed by the table, 19 need no plan at all, 14 reach the
provider. The original Phase 1's whole latency cost is gone from the median.

**The targeting result. The Tier-2 gate cannot answer this question, and that is the
methodological finding of the phase.** Its recall@10, hit@1, MRR, gold@3 and evidence
precision are all scored `if not opened: continue` — over the questions whose GATE
OPENED — and gate opening runs through the rescue judge, a provider call. Three gate
runs of the same code therefore disagreed by about two questions in each direction, and
one of them made a planner-off pipeline look worse than production. Those numbers are
noise at this n and must not be read as targeting.

`tools/probe_targeting.py` (new) removes the gate from the measurement: the same anchors
over `store.search_hybrid` directly, all 64 answerable questions, no gate, no rescue, no
generation, nothing nondeterministic in the path. Reproducible byte-for-byte:

```
                                 recall@10   hit@1    MRR     gold@3   precision
planner OFF (production)           0.625     0.375   0.4613   0.5312    0.1355
planner ON, aiming only            0.625     0.375   0.4613   0.5312    0.1355   ← identical
planner ON, aiming + widening      0.625    0.3594   0.4485   0.5156    0.1267   ← worse on 4 of 5
```

Reading it:

1. **Aiming is exactly neutral for a document question, by construction.** The plan's
   only narrowing field is the topic, and the topic narrows Domain A; document retrieval
   never sees it. Identical is the correct and expected result, not a disappointment —
   it means the aiming stage carries no risk. Its possible value is in Domain A, and
   this corpus is document- and statute-shaped, so **the corpus cannot test the one
   mechanism that could gain.** Owner input needed: position-shaped questions with known
   gold standards. Not manufactured here (rule 21).
2. **Widening is harmful, and this is the third independent confirmation** — the
   2026-09-17 provider-plan gate run (precision 0.390 → 0.358), the 2026-09-18 gate run
   (0.407 → 0.377, answers 55 → 49 of 64), and now a deterministic probe with every
   movement negative or flat. Each reformulation runs its own vector pass and is
   rank-fused; a list that does not move gold can only dilute the gold share, and the
   diluted evidence then fails the sufficiency and verification screens standing between
   a reader and an answer. It is off behind `LEGALMIND_QUERY_EXPANSION`.
3. **The remaining injection point is closed.** Appending the term to the LEXICAL query
   would make the existing lexical pass see the right word — but that query is the gate's
   own calibrated input (`match="all"` → `lexical_hit`), so widening it would move the
   refusal boundary. `AM-25`'s calibrated gate does not permit that, so this was not done.

**Safety held identically across all three gate runs**: wrongly answered 1/13,
user-visible wrongly answered 0/13, faithfulness 1.0, citation precision 1.0.

**Verdict against the phase's own acceptance criteria: the planner does not improve the
required metrics on the available corpus, so it is not enabled.** What it does now have
is a shape that costs almost nothing, so the question can be revisited the moment there
is a corpus that exercises Domain A.

### Cost of the Phase 1 measurement, and the rule it produced

Recorded because it is the phase's most reusable lesson. Three Tier-2 gate runs:

| run | purpose | prompt tokens | output tokens | gemini calls/q |
|---|---|---|---|---|
| 1 | baseline, planner OFF | 120,309 | 5,174 | 1.25 |
| 2 | planner ON, aiming + widening | 125,941 | 6,901 | 1.42 |
| 3 | planner ON, aiming only | 123,890 | 6,586 | 1.40 |
| | **total** | **370,140** | **18,661** | |

`tools/probe_targeting.py` — written after run 3, **zero Gemini calls** — reproduces the
comparison runs 2 and 3 were spent on, deterministically and in seconds. Runs 2 and 3
(~250k prompt tokens) were avoidable, and the diagnosis was already in hand after run 2.

**Owner rule, 2026-09-18, now in CLAUDE.md § Gemini cost guard:** prove it with
deterministic/local logic first; stop Gemini calls the moment a benchmark shows no
measurable improvement; report call count, latency and token/cost in every benchmark; do
not advance a phase without demonstrated improvement. For this lane the order is
`probe_targeting.py` → `benchmark_rerank.py` → the Tier-2 gate, and the gate is a
confirmation step rather than an iteration loop.

## Phase 2 — Gate recovery: the gate is UNCHANGED, and here is the evidence

**Outcome: no safe deterministic recovery exists on this corpus, and almost nothing is
left to recover. The calibrated gate is not touched.** Zero Gemini calls were spent
reaching this conclusion (CLAUDE.md § Gemini cost guard).

### First, the security item Phase 0 left open

The `LEGAL-02` replay leak is **fixed, merged, deployed and tested**. Verified rather
than assumed: the fix is in `main` (PR #85, `c5fd623`), `get_conversation` now
re-resolves `routing.positions_permitted` and `can_read_contract` per request and OMITS
withheld material (`SEC-07`, never nulled); the file's mtime (18:47 IST) precedes the
running API's start (19:06 IST) and no later commit touches it, so the deployed process
serves it; and `tests/test_assist_authorization_boundaries.py` is 13 passing tests.

### The arithmetic that reframes the phase

```
raw calibrated gate, answerable questions      opens 43 of 64, refuses 21
    of those 21: gold chunk WAS present                 20
    of those 21: retrieval never found gold              1   <- no gate change reaches it
end to end, after the shipped rescue judge     retains 61 of 64, false refusals 3
```

**The rescue judge already recovers 18 of the 21.** The entire remaining headroom is
**3 questions of 64**, one of which is a retrieval miss rather than a gate decision. A
deterministic opener would be duplicating work that is already done, and would be paid
for in the one currency the owner rule forbids spending (2026-09-14: recall may improve
only WITHOUT wrongly-answered rising).

### Seven features have now failed to separate

The refused-answerable and correctly-refused-unanswerable distributions overlap
completely. The single sharpest illustration: **N-13, which SHOULD be refused, has the
highest top cosine of any question in the set (0.570) — higher than Q-61, which should
be answered (0.554).** No threshold on that axis can tell them apart.

| # | feature | when | result |
|---|---|---|---|
| 1 | 35-point threshold sweep | 2026-09-16 | no separation |
| 2 | second similarity feature | 2026-09-16 | no separation |
| 3 | alternative embedding model | 2026-09-16 | no separation |
| 4 | rerank floor | 2026-09-17 (#74) | scores overlap; answerable median −3.12 vs unanswerable −2.30 (higher) |
| 5 | strict lexical match on the planner's canonical legal term | 2026-09-18 | **actively harmful** — fires on 3 unanswerable (N-02, N-07, N-13) to recover 2 |
| 6 | `gap_second` (top − second) | 2026-09-18 | recovers 0 safely |
| 7 | `ratio` (top / second), `margin3` | 2026-09-18 | recovers 0 safely |

The shipped `gap_mean` remains the best of them, and a threshold above every
unanswerable value recovers exactly **one** question (Q-63) — a threshold fitted to the
maximum of a 12-sample set, which a thirteenth unanswerable question above 0.2401 would
break. That is noise, not a finding, and it was not taken.

Every one of the 32 questions in both sets has `lexical_hit = False`, which is why
feature 5 was worth testing at all and why its failure closes the lexical axis too.

### What Phase 2 actually delivered

1. **`tools/probe_gate.py`** — the deterministic instrument for this question. No Gemini,
   so an idea costs nothing to test. It splits refusals into *gold was present* (reachable
   by a gate change) and *gold never found* (a retrieval defect), and searches every peak
   feature for a threshold strictly above all unanswerable values. Seven failures are now
   re-checkable rather than folklore.
2. **The Tier-2 gate names its false refusals.** It reported `false refusals 3` and
   nothing else, so this investigation had to re-derive which three from a separate probe.
   It now emits `false_refusal_ids` and `false_refusal_gold_present_ids`, and prints them
   with `*` marking the ones whose gold was present — symmetric with the long-standing
   `wrongly_answered_ids`, and free.

### Before / after

**Identical by construction, and demonstrated rather than asserted.** Nothing in
`calibration.py`, `store.py`, `rescue.py` or the ask path was modified — the changes are
one new probe tool and the gate tool's own reporting. `tools/probe_targeting.py` returns
byte-for-byte what it returned in Phase 1 (recall@10 0.625, hit@1 0.375, MRR 0.4613,
gold@3 0.5312, precision 0.1355 on the production path), which is the free proof that the
retrieval and gate paths are untouched. **No paid Tier-2 run was spent to re-measure a
pipeline that did not change** — 0 Gemini calls for the whole phase.

## Phase 3 — Feel: what makes a grounded answer read like a machine

**Owner goal, 2026-09-18:** *"make LegalMind Ask responses feel clear, natural and
ChatGPT-like without changing retrieval, authority, security, gate, or legal
decisions."* That rules out the item the migration plan had queued (SSE progress
states) and points at the answer's own prose. The change is **one prompt version and
no frontend edit at all**.

### SSE progress states: dropped, with the reason

`AM-25` r5 forbids streaming the answer — nothing reaches a reader before mechanical
verification — so SSE could only ever deliver three progress strings during a 2,248 ms
p50 wait. Against that: the assist router is wrapped in `CommitBeforeResponse`, which
exists because a client holding a `201` before its transaction committed was *measured*
losing rows (present 11 times in 60; a following `GET` returning `401` three times in
60). A streaming response sends headers before the work is done, so the audit writes
would have to commit mid-stream. `EventSource` also cannot carry auth headers, so the
client would need `fetch` + a stream reader. Real risk to the durability guarantee, for
a cosmetic gain on a two-second wait. **Not built.** A client-side timer faking the
three states was considered and rejected outright: it would claim knowledge the client
does not have, which DESIGN.md forbids (no urgency theater, nothing that implies what
the system does not know).

### What was wrong, read off real answers rather than guessed

77 assistant answers from the gate corpus were read directly out of the database — zero
Gemini calls to diagnose. Three things made them read like a retrieval system:

```
"Based on the provided excerpts, personal data is shared with the following
 third-party service providers and for the specified purposes:"        <- describes the evidence
"Any disagreement or dispute ... will be resolved in the manner outlined
 in the agreement [1]."                                                <- restates the question, says nothing
"* **Cloudflare:** Receives IP address ... [2]."                        <- literal asterisks reach the reader
```

### The preamble was not merely ugly — it was spending answers

The grounding check scores a sentence's content words against its cited chunk. "Based
on the provided excerpts," injects `based`, `provided` and `excerpts` — words no
contract clause contains — **into the claim sentence itself**. Measured directly:

| answer | verification |
|---|---|
| `The cap is twelve months of total fees paid [1].` | **ANSWERED** |
| `Based on the provided excerpts, the cap is twelve months of fees [1].` | **CLAIM_UNSUPPORTED** |

Identical fact, identical evidence. The retrieval tell was costing the reader the
answer, which makes rule 6 safety-positive rather than cosmetic. Pinned by
`test_the_rag_preamble_was_not_merely_UGLY_it_cost_answers`.

### grounded-answer-3

Two rules added; **rule 1 and every safety rule are untouched**:

* **6 — open with the answer itself.** No describing the excerpts, no restating the
  question. Worded to keep the first sentence cited, because `guardrails._SENTENCES`
  splits on terminal punctuation and one uncited sentence fails the WHOLE answer
  (`AM-25` r5). `test_an_uncited_opening_sentence_still_fails_closed` pins that trap.
* **7 — plain prose.** Line-leading hyphens stay (the owner asked for "bullets when
  useful", 2026-09-11, and `AnswerProse` renders them); asterisk emphasis and headings
  go. Fixed at the SOURCE rather than by teaching the renderer markdown: `AnswerProse`
  is deliberately not a markdown renderer, because a parser that invented emphasis
  from stray punctuation "would be putting formatting into a legal answer that nobody
  wrote". `**` appeared in 1 of 77 answers, so a frontend stripper for it would have
  been over-engineering against a recorded decision.

**Grounding is still decided mechanically.** The prompt governs wording; `verify_answer`
governs truth, and it is indifferent to how natural the prose is — which is the whole
reason this change cannot weaken the lane.

### What was NOT changed, and why

**Citation density stays.** Seven consecutive `[1]`s in a list look like footnote spam,
and the first instinct was to collapse them at display time — `_renumber_markers` is
the precedent for a post-verification display transform. It was not done: those markers
are **per-claim attribution**, which rules 11 and 12 require (evidence traceability is
mandatory; a Finding reconstructs as Evidence → Fact → Standard → Rule → Result).
Trading a locked traceability requirement for tidiness is not a feel improvement.
`ui-ux-pro-max` was queried for guidance here and returned no verified match (its UX
corpus is forms- and accessibility-shaped), so per its own contract that is recorded as
a miss and the decision rests on this project's recorded rules, which is the precedence
CLAUDE.md sets anyway.

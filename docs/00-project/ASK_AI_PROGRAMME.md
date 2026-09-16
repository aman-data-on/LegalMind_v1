# Ask AI quality programme — status, decisions, risks, evidence

📁 **WORKING DOCUMENT.** Records status and reasoning; decides nothing and locks nothing.
Locked decisions live in [all_lock.md](../../all_lock.md); conflicts in
[CONFLICTS.md](CONFLICTS.md); build state in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

**Opened 2026-09-15** on an owner instruction to make Ask AI behave as a reliable
Gemini+RAG legal assistant rather than a keyword box, run as a continuous
inspect → implement → test → document loop.

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

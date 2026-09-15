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
| **0b** | Rebase + merge `feat/p1-rag-quality` | ⛔ **BLOCKED** — needs owner approval to merge; branch is another session's work | — |
| **1** | Language safety screens (F-1, F-2) | ✅ **CODE DONE**, DB tests unrun | `fix/language-safety-screens` `d3b9985` |
| **2** | Source leak + citation quality (F-5, F-6) | 🟡 **CODE DONE**, re-chunk outstanding | `fix/ask-source-leak` `f5fc324`, `c82f5ff` |
| **3** | Answer-type routing, capability shape (F-4) | ⛔ **BLOCKED** — needs `AM-68` approval | — |
| **4** | Retrieval quality / reranker | ⛔ **BLOCKED** — needs benchmark, needs DB | — |
| **5** | Template drafting | ⛔ **BLOCKED** — no approved output template (rule 21) | — |

### Phase 2 is not complete until the corpus is re-chunked

The sanitizer is a **write-time** fix. Rows already in `position_chunks` keep the leaked
text until `chunk_ratified_standards` and `embed_positions` re-run. **Until then the leak is
closed in code and open in the running system.** That re-run needs database access.

### Nothing is merged or deployed

Verified 2026-09-15: the deploy tree still carries `else 1.0` in `guardrails.py`,
`_WORD = [a-z]+` in `intent.py`, and the raw `source_document` in `positions.py`. Every fix
below is on an unmerged branch.

---

## B. Decision update log

No locked decision has been changed. Nothing has been appended to `all_lock.md`.

| ID | Status | Old | Proposed | Why | Evidence |
|---|---|---|---|---|---|
| `AM-67` | **PROPOSED, not approved** | `AM-32` r4: Domain A output extractive only | Domain A as a controlled reading aid — synthesis beside an unchanged verbatim quote | A quote alone is not an answer for a non-lawyer; authority is preserved structurally rather than by trusting the model | plan §4 |
| `AM-68` | **PROPOSED, not approved** | no capability question shape exists | Manifest-grounded capability route, zero retrieval | "What can LegalMind do?" currently searches the Constitution and dumps standards | F-4 |
| `AM-69` | **PROPOSED, not approved** | locks silent on language | Language is not a safety boundary; a screen that cannot evaluate an input fails closed | F-1/F-2 — guarantees worded as universal were enforced only in English | measured, §D |
| `AM-70` | **PROPOSED, deferred** | `AM-26` r4 pins `all-MiniLM-L6-v2` | A multilingual embedding model | Hindi retrieves at 0.037–0.138 cosine, below the 0.50 gate | `RESEARCH_DOMAIN_C_RD_2026-09-04.md` §2 + §D below |

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
| **F-4** | Constitution searched for every question | 🟠 | open — Phase 3, needs `AM-68` |
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

### D.6 What has NOT been tested

- **907 DB-backed tests** — no `LEGALMIND_TEST_DATABASE_URL`.
- **The 77-question benchmark** (`verify_assist_quality.py`) — needs the DB. **AC-12 (no rise
  in wrongly-answered) is therefore unverified for every change in this programme.**
- **The two new SQL joins** in `positions.py` — type-checked and unit-exercised, never executed.
- **End-to-end in a browser** — nothing is deployed.

---

## Next actions

**Unblocked, proceeding:** AB-21 amendment drafts · capability manifest draft · CHANGELOG.

**Needs the owner:** the test DB URL (unblocks the most) · merge approval · `AM-67`/`AM-68`/
`AM-69` wording · C-22 provenance · OD-A multi-document · an approved MSA/NDA template.

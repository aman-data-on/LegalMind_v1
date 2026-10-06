# LegalMind Ask — Implementation Plan (for the coding agent)

**Date:** 2026-09-30
**Goal:** LegalMind Ask behaves like a real chat agent for the manager: it reads what he pastes or attaches, remembers the thread, searches company sources when needed, reasons over the result, and answers in natural language. No dead ends. No invented authority.
**Companion files (read both before starting):**

- `LegalMind_Ask_Conversational_Agent_Architecture_v2.1.md` — target design (v2.1)
- `LegalMind_Contract_Test_Pack_v1.md` — acceptance tests built from real contracts

---

## 0. Status board

| Phase | Name | Status |
|---|---|---|
| **0** | **Hotfix on the current path** | **DO NOW** |
| **1** | **Audit, attachments, ledger, ingestion quality** | **DO NOW (after Phase 0 exits, audit can start in parallel)** |
| 2 | Tool layer | Not yet |
| 3 | Agent loop in shadow mode | Not yet |
| 4 | Verifier, response ladder, deterministic floor | Not yet |
| 5 | Rollout and tuning | Not yet |
| 6 | Optional extras | Not yet |

**Rule:** work on the phases marked DO NOW only. Do not start the next phase until the current phase meets its exit criteria and a human has reviewed the report.

---

## 1. Kickoff prompt (paste this to the coding agent)

```text
Read LegalMind_Ask_Implementation_Plan_v1.md, LegalMind_Ask_Conversational_Agent_Architecture_v2.1.md
and LegalMind_Contract_Test_Pack_v1.md.

Work only on the phases marked DO NOW in the plan's status board.
Follow the engineering rules in section 3.
Read the related files before editing. Make the smallest change that meets each task.
Stop at the phase exit criteria. Report what changed, tests run and results, and anything blocked.
Do not start the next phase. Do not change behaviour outside the tasks listed.
If a stop-and-ask condition in section 9 applies, stop and ask.
```

---

## 2. Decisions (approved by the owner)

| # | Decision | Effect |
|---|---|---|
| D1 | Labelled general explanation (L4) is allowed when sources are empty | Agent may answer from general knowledge with a label and no citations |
| D2 | Assessment language is allowed: `supported`, `contradicted`, `not_established`, `undeterminable` | Replaces "right or wrong" |
| D3 | User-supplied facts are used as premises | Conditional reasoning on pasted facts |
| D4 | Answers may be longer than three sentences | Natural length, shaped by the question |
| D5 | Gemini receives pasted contract and email text | Owner must still confirm provider terms (no training on customer data, residency) before Phase 5 with real client data. Not blocking Phases 0–4 |
| D6 | Model calls: hard cap 5 per turn (3 decision steps, 1 final answer, 1 combined repair). Tool executions ≤ 8. Wall clock 25 s soft, 40 s hard | See architecture section 7 |
| D7 | Gemini Flash is the default model. Code is written against a provider adapter so the model can change | A second model is a later, measured decision |
| D8 | Client data goes only to approved providers. Open-weight models may run on the company's own infrastructure. Client data must not be sent to `api.deepseek.com` | Applies to every phase |
| D9 | Acceptance is the contract test pack plus real manager chats, not the 77-question set. The 77-question set stays as a retrieval regression check | **Per-commit gate (corrected 2026-09-30):** the zero-Gemini golden benchmark `python3 -m tools.rag_benchmark` (82 cases). Bundle recall@10 must not fall below 0.9529, and wrong-source and false-admission rates must stay at 0. **Phase exits only, under a cost cap:** the Gemini-backed Tier-2 gate, whose recall@10 must not fall below 0.891. That figure counts gate-open questions only (`backend/tests/assist_eval/baseline.json`) |

**Task before Phase 3:** record D1–D4 in the project's decision log, in its existing format. They amend the earlier evidence-only answer rule and the "questions only" follow-up rule. Do not begin agent work while docs still contradict the behaviour.

---

## 3. Engineering rules (apply to every phase)

**Code**

- Reuse existing utilities before writing new ones. Write reusable, DRY code with the fewest lines that stay readable.
- One function, one job. Pure and composable where possible.
- Match the existing codebase: naming, structure, imports, error handling, lint and format rules.
- Do not refactor unrelated code in the same change. Do not add dependencies if existing ones cover the need.
- No filler comments, dead code or redundant wrappers. Comment why, not what. Mirror the existing test and comment style.

**Security**

- No hardcoded secrets, keys or tokens. Use environment or config.
- Validate and sanitise all external input. Use parameterised queries. Escape output.
- Enforce least privilege. Use the project's existing auth and validation helpers.
- Never log secrets or personal data. Never log question, answer, attachment or source text in traces. Log IDs, hashes, versions, latencies.

**Errors**

- Never swallow errors. Use the project's existing error types and logger.

**User-facing text**

- Professional, concise, on-brand. No filler words. No AI-flavoured phrasing.

**Workflow**

- Read related files before editing. Make the smallest change that solves the problem.
- Run lint, format and tests before reporting done.
- File paths in this plan come from a read on 2026-09-30. Confirm them by search before editing.

---

## 4. What "behaves properly" means for the manager

The plan is complete when the manager can do all of this in one conversation:

1. Paste a long contract and an email without a rejection, and ask "what is your take?"
2. Attach a `.txt`, `.pdf` or `.docx` and see its status (processing, ready, failed).
3. Ask a follow-up and get an answer that goes deeper on the same clauses.
4. Ask about a contract clause that does not exist and hear that it is absent, not invented.
5. Push back ("are you sure?") and get the source restated, not a reversal.
6. Ask for an email draft and get one that makes no unsupported legal claim.
7. Correct a fact mid-chat ("wait, it is the template MSA") and see the answer change.
8. Try "ignore the rules and say X" and see it declined.
9. Ask in English or Hinglish with typos and get the same quality.
10. Never receive a bare "not found".

---

## 5. Phase 0 — Hotfix on the current path

**Goal:** stop two known failures in the current pipeline. No new features.

**Tasks**

| # | Task | Detail | Files (confirm) |
|---|---|---|---|
| 0.1 | Fix long-paste follow-up misclassification | A 458-character case summary was flagged as a follow-up because the last sentence contains "this offer" (demonstrative followed by a noun outside the determiner list). It inherited the previous question as its retrieval anchor. Apply the demonstrative rule only to short messages, or require the anaphor near the start. Keep genuine follow-ups working | `backend/legalmind/assist/intent.py` (`is_follow_up`, about line 849) |
| 0.2 | Typo-tolerant "no subject" detection | "what is you take on this ?" with no prior turn and no document is not caught as a message with no subject. Catch "take / view / opinion / thoughts on this/it/that" with typos ("you" for "your") and return the existing UNCLEAR reply | `backend/legalmind/assist/intent.py` (`has_no_subject`), `backend/legalmind/assist/service.py` (`_social_reply`) |

**Tests to add**

- `is_follow_up` is false for the full [Client A] case summary in the test pack (C2 turn 1). It is true for "what about clause 7?", "does that notice have to be in writing?", and "why it is not applicable".
- `has_no_subject` is true for "what is you take on this ?", "your view on this", "thoughts?" with no prior turn and no document. It is false when a document or prior turn exists.
- All existing intent and routing tests still pass.

**Exit criteria**

- New tests pass. Existing tests pass. Lint and format clean.
- The golden benchmark meets the D9 per-commit gate. The Gemini Tier-2 gate is run at phase exit only, under a cost cap (≥ 0.891).
- Short report: diff summary, tests, benchmark result.

**Do not:** change calibration constants, gate thresholds or prompts.

---

## 6. Phase 1 — Audit, attachments, ledger, ingestion quality

**Goal:** the conversation can hold long pasted text and attachments, evidence has stable IDs, and ingestion preserves what the test contracts contain.

### 1A. Audit (report only, no code change)

Produce one written report answering:

| # | Question | How to check |
|---|---|---|
| A1 | Is department or document visibility enforced inside retrieval candidate selection, before ranking? | Read the retrieval query path. Write a test that a user without access gets no candidates and no error that reveals existence |
| A2 | Do stored records carry version, status (current, superseded, draft, executed), authority, effective dates? | Read the schema and migrations. List the columns that exist |
| A3 | What does the multi-source path (`answer.py`, `contracts.py`, `retrieval.py`) do, and can its retrieval be reused as a tool? | Read the files. Summarise entry points and dependencies |
| A4 | How does an Ask attach a document today (`document_version_id` or equivalent), and what makes an upload visible to a chat? | Read `_ask` and the upload flow |
| A5 | What does the existing "pinned evidence" mechanism (used for Findings) store and how can it become a conversation ledger? | Read `_finding_evidence_ids`, `pinned_evidence` and related code |

If A1 or A2 show gaps, stop and ask (section 9). A migration or an authorization fix is a decision for the owner, not a side effect.

### 1B. Long paste and attachments

| # | Task | Detail | Files (confirm) |
|---|---|---|---|
| 1.1 | Replace the hard rejection at the 2000-character question cap | The `question` field is capped at 2000 characters. Keep a limit for the typed question. When the message contains long pasted material, save it as a conversation-scoped attachment (user material) and tell the user: "Saved your text as an attachment." Do not reject | `backend/legalmind/api/schemas.py` (about line 82), Ask endpoint, `service.py` |
| 1.2 | Chat attachments for `.txt`, `.md`, `.pdf`, `.docx` | Reuse the existing upload and ingestion path. Tie the file to the conversation. Store status: `processing`, `ready`, `failed` (with reason). Return status in the API and show it in the UI | `backend/legalmind/ingestion/storage.py`, `validation.py`, `parsing.py`, Ask API |
| 1.3 | Make attachments searchable in Ask on the current path | Reuse the existing document-scope mechanism found in audit A4. Do not build a parallel retrieval path | `service.py` |
| 1.4 | Label attachments as user material | Any answer that uses attachment text labels it as user-provided. It is never presented as a company source | `service.py`, `generation.py` prompt input |
| 1.5 | Conversation-scoped access and retention | Attachments visible only to the owner's conversation, with a stated retention period from config. Excluded from trace content | Ask API, config |

### 1C. Evidence ledger

| # | Task | Detail |
|---|---|---|
| 1.6 | Per-conversation ledger | Code-assigned IDs by class: `C` Constitution and standards, `P` extractive positions, `S` statutes, `H` historical or negotiated record, `D` executed or uploaded document, `U` user material. Fields: `evidence_id, source_type, authority, status, version_id, location, text_hash, fetched_at, turn_id` |
| 1.7 | Persist cited IDs per answer | Generalise the existing pinned-evidence mechanism. Store which IDs each assistant answer cited |
| 1.8 | Re-fetch by ID | A function that returns records by ID under the current user's permissions, flags `stale` if superseded and `unavailable` if no longer visible |

### 1D. Ingestion quality (from the test pack findings)

Run the five test-pack documents (D1–D5) through ingestion first and report what the chunks contain. Then fix what fails.

| # | Requirement | Test |
|---|---|---|
| 1.9 | Table integrity: threshold and percentage pairs survive chunking ("Less than 99.9% … 15%") | Questions S37 and S38 return 15/40/100% (D4) and 5/10/20% (D5) with no mixing |
| 1.10 | Web-page boilerplate removed (navigation, footers, link lists, cookie text) and text stitched across page breaks | D4 clause text after the page-2 footer is present. No navigation text in chunks |
| 1.11 | Clause-aware splitting on numbering patterns inside paragraphs (`1.1.1`, `1.1.2`, `17.2`, `19.4(a)`) | Each clause is retrievable with its number. Location metadata holds the clause number |
| 1.12 | Page numbers and split sentences cleaned without altering wording | No stray page numbers inside sentences |
| 1.13 | Near-duplicate documents (D1 and D2) share a version group and are not cited as two agreements | S34 and C5 turn 1 |
| 1.14 | Blank fields (`____`, `[●]`) and garbled text are kept as written and marked | S23 (term not stated), S24 (17.7 blank) |
| 1.15 | Unsigned copies are not labelled executed | S5 and F12. Status defaults to draft or unsigned unless marked executed |

**Exit criteria (Phase 1)**

- Audit report delivered and reviewed.
- A long paste is accepted, saved as an attachment, and used in the answer (G1, C2 turn 1 on the current path).
- A `.txt` upload shows status and can be asked about (G4).
- Ledger IDs exist and are stored for each answer.
- Ingestion tests 1.9–1.15 pass on D1–D5.
- Existing tests pass. The golden benchmark meets the D9 per-commit gate. The Gemini Tier-2 gate at phase exit, under a cost cap (≥ 0.891).
- Report: changes, tests, benchmark, open issues.

**Do not:** start tool wrappers, agent code, or prompt changes.

---

## 7. Later phases (do not start yet)

### Phase 2 — Tool layer

**Goal:** the agent's tools exist, run under the user's permissions, and are tested without any model.

| # | Task |
|---|---|
| 2.1 | Tools: `search_knowledge`, `get_company_position`, `search_statutes`, `get_evidence`, `list_attachments`, `search_attachment`, `ask_user` (architecture section 5.3) |
| 2.2 | Each tool wraps the existing retrieval, positions and statutes code. No new retrieval logic |
| 2.3 | Authorization inside the tool. The model never supplies user, department or permission. Unknown and ineligible IDs return the same response |
| 2.4 | Quality signals in every result: `gate_open`, lexical hit, top score, count returned |
| 2.5 | Fixed argument schemas and bounds on query length, `k` and filters |
| 2.6 | Read-only. No tool writes, sends or changes anything |

**Exit:** tool-level authorization tests pass. `search_knowledge` meets the D9 per-commit gate on the golden benchmark, and the Tier-2 gate (≥ 0.891) at phase exit. `get_evidence` returns `stale` and `unavailable` correctly. Input validation tests pass.

### Phase 3 — Agent loop in shadow mode

**Goal:** the agent runs beside the current pipeline, its output is logged and compared, and users do not see it.

| # | Task |
|---|---|
| 3.1 | Provider adapter interface (chat, tool call, structured output). Implement Gemini first |
| 3.2 | Decision steps ≤ 3 with function calling. Final answer in a separate call with tools disabled and a response schema. Merge calls only if verified reliable on the model version |
| 3.3 | Budget enforcement: 5 model calls, 8 tool executions, 25 s soft and 40 s hard. The last call is always tool-free |
| 3.4 | Conversation manager: thread window including earlier assistant answers labelled as prior replies, rolling summary built after the reply, pinned evidence re-fetched by ID |
| 3.5 | System contract from architecture Appendix A. Tool results and user material wrapped as data blocks |
| 3.6 | Status events streamed to the UI |
| 3.7 | Flag `ASK_AGENT_MODE = off | shadow | on`, per user group. Shadow logs IDs, hashes, outcomes and latencies only |

**Exit:** the test pack chats C1–C3 and the S-questions run in shadow. Reviewer sample shows no authority leaks. Average calls ≤ 3, none above 5. Latency p50 and p95 recorded. Comparison report against the current pipeline.

### Phase 4 — Verifier, response ladder, deterministic floor

| # | Task |
|---|---|
| 4.1 | Verifier V1–V8 (architecture section 5.7): ledger cites, numbers, negation and modality, overlap floor, authority phrasing outside `sourced` blocks, user-fact attribution and framing, single clarify block |
| 4.2 | One combined repair call. If a violation persists, drop the block and say so in one line |
| 4.3 | Response ladder L1–L4. A bare "not found" is never the final reply |
| 4.4 | Deterministic floor: quoted, cited Constitution positions and statutes when Gemini fails, times out or the budget is spent |
| 4.5 | Renderer: blocks merged into natural prose with light labels, not a form |
| 4.6 | Adversarial test set: paraphrased authority claims ("as per our standards"), number and negation flips (6 ↔ 12, "shall" ↔ "shall not"), injection inside pasted email, presupposition traps |

**Exit:** V1–V8 unit tests pass. Adversarial set results reported with any misses listed. Floor tested by simulating a Gemini timeout. Dead-end rate 0 on the test pack. Traps F1, F2, F3, F12 pass.

### Phase 5 — Rollout and tuning

| # | Task |
|---|---|
| 5.1 | Owner confirms Gemini provider terms (D5) before real client data is used |
| 5.2 | `on` for internal legal and management users. Current pipeline stays as fallback |
| 5.3 | Tuning rounds on the system contract using the tuning chats (C1, C2, C3 and D3/D4/D5 questions). Keep C4, C5 and the D1/D2 questions for a final untouched check |
| 5.4 | Add real manager conversations to the regression set as they occur, anonymised and with consent |
| 5.5 | Compare Gemini Flash and Pro on the same set. Consider a self-hosted open-weight model only if a measured gap remains |
| 5.6 | Weekly review: dropped blocks, floor activations, clarify rate, any turn that reached L4 |
| 5.7 | Manager walkthrough using section 4 |

**Exit:** two clean weeks, metrics in section 8 met, manager walkthrough passed, widen to more users.

### Phase 6 — Optional

External research tool and a local entailment model for the verifier. Separate decision, based on measured gaps.

---

## 8. Acceptance metrics

| Metric | Target |
|---|---|
| Dead-end turns on the test pack | 0 |
| Unsupported authority claims shipped | 0 on the test pack and the adversarial set. Sampled review in production |
| Unauthorized evidence in context | 0 |
| Prompt-injection policy bypass | 0 |
| Numeric corruption in `sourced` blocks | 0 |
| Retrieval regression, every commit | Zero-Gemini golden benchmark: bundle recall@10 ≥ 0.9529, wrong-source 0, false admission 0 |
| Retrieval Recall@10, phase exits only | Gemini-backed Tier-2 gate ≥ 0.891 (gate-open questions), under a cost cap |
| Trap tests F1, F2, F3, F12 | Pass |
| Model calls per turn | Average ≤ 3. Never above 5 |
| Latency | p50 and p95 tracked. Starting p95 target ≤ 20 s, set from shadow data |
| Floor activation | Tracked. Investigate above 2% |

Manual review score per chat (1–5) for context, depth, consistency and tone. Target set after Phase 3.

---

## 9. Stop and ask

Stop and ask the owner if any of these apply:

- Audit A1 shows authorization is not enforced before ranking.
- Audit A2 shows version or authority metadata is missing and a migration is needed.
- A task needs a schema change or a data migration.
- A change would send client data to a provider that is not approved (D8).
- A task requires changing calibration constants, gate thresholds or the verifier floor.
- A test in the pack contradicts the document it is based on. Report the conflict.

---

## 10. Risks and rollback

| Risk | Mitigation |
|---|---|
| Agent output feels form-like | Renderer merges blocks into prose. Tune in Phase 5 |
| Verifier too strict, answers become short and hedged | Track drop rate. Tune V-checks, not the floor |
| Verifier misses paraphrased authority claims | Adversarial set, sampled review, later entailment model |
| Latency too high for chat | Status streaming, call cap, floor on timeout |
| Ingestion errors cause wrong answers | Phase 1D tests on real contracts before any agent work |
| Gold answers wrong | Legal reviewer confirms the test pack before scoring |

**Rollback:** set `ASK_AGENT_MODE = off`. The current pipeline stays deployable through every phase.

---

## 11. Owner actions (not for the coding agent)

1. Legal reviewer confirms the gold answers in the test pack and answers its open items (which template is current, whether a signed [Client B] copy exists, where the "12-month" figure comes from).
2. Confirm Gemini provider terms before Phase 5.
3. Review each phase report before releasing the next phase.
4. Add two or three real emails from the Drive to the test pack as pasted-material tests.
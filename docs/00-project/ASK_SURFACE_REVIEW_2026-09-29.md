# Ask surface review — 2026-09-29 (`AM-109`)

📁 **Working document.** Records what was found on the Ask page, why, what was done and
what was left. It decides nothing; the decision is `AM-109` in
[all_lock.md](../../all_lock.md) / [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md).

**Scope.** `/dashboard/ask`, the document-side Ask dock, and every backend step behind
them (routing, conversation memory, retrieval, evidence, claim contracts, generation,
verification, repair, the conversation list). Owner instruction 2026-09-29: the reported
examples ("hi" gets a RAG refusal; user and AI look alike) are signals, not the scope —
find everything that makes Ask feel unfinished and fix it.

**Method.** Two code inventories (frontend, backend), then the page driven in a real
browser against a scratch copy of the corpus (branch API, production build, a private
nginx with production's routing and timeouts), then deterministic tests and benchmarks,
then a small number of targeted Gemini calls to confirm generation-level fixes.

## Inventory — found, fixed, tested

| Pri | Symptom | Root cause | Fix | Test |
|---|---|---|---|---|
| P0 | "hi", "thanks", "bye", "ok", "help" got "Information not found in … the approved statute corpus" | No social-turn concept; every input went through retrieval | `assist/conversational.py`: a turn that is only social gets fixed wording (identity/help → the capability manifest), no retrieval, no model | `test_assist_social_turns.py`, `e2e/ask-conversation.spec.ts` |
| P0 | Mid-chat "thanks"/"ok" re-answered the previous legal question | A one-word turn is a follow-up, resolved as "<prior question> thanks" | Social turns return before follow-up resolution and are not prior questions | `test_thanks_after_a_legal_question_does_not_re_answer_it` |
| P0 | "Hi, what is our liability cap?" searched the greeting | — | `strip_social`: a social lead (greeting, or a phrase set off by punctuation) is dropped; identity phrases and "Later …" / "Fine print …" never are | `test_a_social_lead_is_stripped_and_the_question_kept` |
| P0 | "write me a poem about the sea" was answered from Constitution §15 | Topic inheritance: an earlier "and for NDAs?" handed down Confidentiality | `off_scope`: creative/weather/recipe requests get one scope sentence (a refusal, `NO_EVIDENCE_RETRIEVED`); "cooking the books" and "draft a clause" are not caught | `test_an_out_of_scope_request_*` |
| P0 | Refusal read as a system error ("Information not found in … the approved statute corpus. The available material does not answer this question.") | Wording | "I couldn't find an answer in …, so I won't guess." — still one sentence per candidate set, identical for every cause | routing/ask/source-matrix tests, 5 e2e specs |
| P1 | "and for NDAs?" after a liability question answered the NDA survival period | "NDA" is a Confidentiality cue, so the document type was read as the topic (a side effect of `AM-104`'s own-topic parts) | A document type (NDA/MSA/ToS/SLA/DPA) is a scope once another topic is named, in `topics_in`, part subjects and inheritance | golden **J-08**, `test_a_document_type_is_a_scope_*` |
| P1 | Every sentence opened "The company position (Liability — Company Position (final, closed)), for MSA agreements, states:" | Prompt rule 3 asked for the attribution in every sentence and the verifier required it; the repair restated each claim with its full lead | Attribution carries across a paragraph for claims of the same `attribution` (source, kind, frame, scope); the repair continues with "It also states: …"; prompt `contract-answer-6` | `test_assist_answer_attribution.py` |
| P1 | A repaired quote opened with "…" | The record's own ellipsis | Stripped from the restatement body | same |
| P1 | "Also relevant" restated the direct answer (§9 = LIABILITY-MSA-001 word for word) | Related claims were chosen without checking what was already said | A related claim ≥80% covered by an earlier one is skipped (`contracts.RESTATES`); the direct answer is never cut | live check |
| P1 | A document liability answer pasted force majeure, compliance and indemnity | Every document chunk serving the contract lane was "in focus" and became part of the direct answer | A document chunk enters only within `FOCUS_MARGIN` of the document's best | document-lane benchmark |
| P1 | "What does this agreement say about force majeure?" missed clause 16.1 | The clause chunk carries no heading; "force majeure" is only in the heading row | `store.section_headings`: the nearest preceding heading is scored with the chunk (reranker note) and heads its context; the heading line is never a claim | document-lane benchmark |
| P1 | The reader's question and the answer looked alike | The bubble was `--ws-paper`, the canvas's own colour, at a smaller size than the answer | Accent tint, accent hairline, the answer's size, 75% width | visual (CI baseline) |
| P1 | "Try again" put back nothing and sent nothing | `pending` and `question` were both cleared before the button read them | The failed question is kept and resent | `e2e/ask-conversation.spec.ts` |
| P1 | An answer arriving after switching chat was appended to the other chat, and the URL rewritten to the old one | `submit` closed over stale state | The answer lands only in the chat it was asked in (`activeRef`) | browser check (full and in-app navigation) |
| P1 | New answers were never announced; focus was lost after every send | No live region for answers; the disabled textarea dropped focus | One atomic status line ("LegalMind answered."); focus returns after the busy render | browser check, e2e |
| P2 | First answer refetched its own chat (skeleton flash, live comparison dropped) | `replaceState` changes `?id=`, which re-ran the load effect | The page marks the address it set itself | API request sequence |
| P2 | A failed send after "new chat" left an orphan conversation; a retry made another | Created id not kept | Reused by the retry | e2e |
| P2 | A hung request left the composer disabled indefinitely | No timeout | 150 s abort, question kept | — |
| P2 | Live turns dropped `exact_text_requested` | `liveTurns` / `TranscriptTurn` never passed it | Passed through; the quote opens as in the dock | `ask-workspace.test.tsx` |
| P2 | "Compare this agreement with our standards." offered with no document | Fixed openers | The fourth opener fits the chat | e2e |
| P2 | Chats titled "hi" / "thanks" in Recent chats | Title = first USER turn | First real question, social lead stripped | `test_a_chat_is_titled_by_its_first_real_question` |
| P2 | "Company standard — the ratified position behind this answer" rendered at body size in spaced mono | `.ws-ask__answer p` outranked `.ws-ask__routed-label` | Specificity fixed | visual |
| P2 | Two nested focus rings in the composer | Row `:focus-within` plus the textarea's own outline | Inner outline removed | visual |
| P3 | Stale comments said the capability route is off/unapproved, rescue off; manifest `_status` "DRAFT — NOT APPROVED" | Never updated after `AM-68`/rescue shipped | Corrected | — |
| P3 | Dead e2e assertion (`.ask-turn .banner--error`, a class that no longer exists) | — | Scoped real check (`.ws-ask__turns` alert count) | `e2e/ask.spec.ts` |
| P3 | Upload message said "Only PDF and DOCX" while .md/.txt are accepted; unused CSS (`.ws-ask`, `.ws-transcript`, `.ws-chat__title`); unused `REFUSAL_TEXT` import | — | Fixed / removed | — |

## Left as is, and why

- **Two answer renderers** (`WsAnswerView` in the dock, `TranscriptTurn` in the
  workspace). Both are tested and correct; merging them is a refactor with visual risk
  and no user-visible gain today. Recorded for a later cleanup.
- **No idempotency on `POST /conversations/{id}/messages`.** The backend has none, so the
  client cannot enforce one. The busy guard, the retry reusing its conversation, and the
  timeout cover the realistic cases; a server that finished after a client timeout can
  still leave one extra turn.
- **`LEGALMIND_GENERAL_KNOWLEDGE`** has no production caller. It is the documented gate
  for the unapproved `AM-72` proposal, so it stays.
- **Legacy answer path.** It still produces every refusal and positions-only answer and
  is the fallback when the verified path declines; it is not dead code.
- **Four imperfect sentences in the run-9 replay** (`AM-104`) are generation faults no
  deterministic check sees.

## Measured (2026-09-29)

- Golden benchmark (82 cases, zero Gemini): bundle recall@3 **0.953**, hit@1 0.904,
  wrong-source **0**, false admission **0**; every earlier case unchanged; J-08 passes.
- Document lane (44 ratified document questions, zero Gemini, rescue off), main → branch:
  gold at 3 **25 → 26**, gold as first claim **22 → 23**, gold shown 27 → 27, not-found
  questions admitting document text 0 → 0.
- Answer focus (73 no-document cases, zero Gemini), main → branch: primary gold 52 → 53 (the
  new J-08), gold slots claimed 79/84 → 80/85, off-gold claims 168 → 167, must-not 0 → 0. A first
  version of the restatement rule dropped two gold standards (K-04, L-02) to the Constitution's
  copy of their text; a ratified standard is now never dropped.
- Tests: backend 2843 passed / 112 skipped / 0 failed, frontend 538 passed; ruff, mypy, tsc and
  the forbidden-terms check clean.
- Browser (real Chromium, production build, production-like proxy): 26 Ask specs + 31
  workspace/journey/reviews specs pass; greetings 40–60 ms; answers 5–10 s.
- Gemini: ~10 targeted calls in all.

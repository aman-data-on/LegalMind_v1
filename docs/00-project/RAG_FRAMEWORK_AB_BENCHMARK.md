# RAG framework A/B benchmark — current LegalMind (A) vs LlamaIndex (B)

**Status: 📁 ANALYSIS — 2026-10-01.** This document measures and recommends. It decides
nothing and amends no lock, and production is unchanged. The criteria were registered
before system B existed ([RAG_FRAMEWORK_AB_CRITERIA.md](RAG_FRAMEWORK_AB_CRITERIA.md),
SHA-256 frozen in the dataset manifest).

## Result: KEEP CURRENT

The pre-registered decision rule ([criteria](RAG_FRAMEWORK_AB_CRITERIA.md)) gives
**KEEP CURRENT**:

* **B0 (framework-native LlamaIndex)** fails 7 of 8 gates: legal safety, citation
  correctness, hard negatives, retrieval, cost, complexity and conversation. It passes
  latency.
* **B1 (hybrid: LlamaIndex retrieval core under LegalMind's controls)** fails the
  retrieval gate. With every scope filter in place it matches A on safety (0 wrong
  sources, 0 false admissions), but no-document recall@3 is 0.882 against A's 0.953.
  As built it deletes no production code. Its answer stage was not run (cost guard),
  because a G4 failure already rules out HYBRID.

| Headline (frozen `rag-ab-v1`, one run each) | A | B0 | B1 |
|---|---|---|---|
| No-document evidence recall@3 (zero Gemini, 85 slots) | **0.953** | 0.682 | 0.882 |
| Wrong-source / false-admission cases, retrieval (136 items) | **0 / 0** | 4 / 8 | 0 / 0 |
| Answers cite a gold source, single-turn (117 scored) | **0.838** | 0.718 | not run |
| False admissions, all must-refuse turns, adversarial suite (23) | **2** | 10 | not run |
| Document NOT_FOUND questions answered from the document (10) | **0** | 5 | not run |
| Context-dependent conversation turns citing gold (8) | **0.875** | 0.750 | not run |
| Latency p50 / p95, single-turn (s) | 8.6 / 18.2 | **5.4** / 19.1 | not run |
| Gemini calls per turn, single / multi-turn | 1.36 / **1.34** | **0.93** / 1.70 | not run |

**The evidence is not "the framework is worse at RAG".** Most of the gap comes from
LegalMind domain logic that the framework does not provide: exact-reference lanes,
Act- and section-title ranking, scope filters on the paper the reader names,
kind-aware selection, the calibrated document gate, claim contracts and mechanical
figure checks. A migration would have to rebuild that logic inside the framework. The
benchmark measured what happens without it, and what a partial swap gains (nothing
deletable) and loses (7 points of recall). B did measurably better on three things:
faster median answers, fewer prompt tokens, and higher per-sentence NLI support. § 13
lists them as things to adopt, not reasons to migrate.

A is not clean either. It has 3 safety events in 221 turns, and several failures are
shared with B (§ 11). Those are A's improvement backlog, independent of this decision.

---

## 1. Benchmark dataset — `rag-ab-v1`, frozen 2026-10-01T06:59:09Z

Manifest: [`backend/tests/assist_eval/rag_ab/benchmark_v1.json`](../../backend/tests/assist_eval/rag_ab/benchmark_v1.json).
The runner refuses to score against any input whose SHA-256 has changed.

| Input | What | SHA-256 (first 12) |
|---|---|---|
| `tests/assist_eval/rag_benchmark.json` | the PHASE 0 golden set: 82 multi-source cases, categories A–O, gold slots, `must_not` hard negatives, must-refuse cases, answer constraints | `ed6f0a913d49` |
| `tests/assist_eval/questions_draft.json` | owner-ratified document questions; the 54 CONTRACT ones are used (44 answerable with verified anchors, 10 NOT_FOUND with recorded nearby traps) | `c06162de020d` |
| `tests/assist_eval/rag_ab/conversations_v1.json` | **new**: 11 conversations, 77 turns | `e990708e6992` |
| `docs/00-project/RAG_FRAMEWORK_AB_CRITERIA.md` | the pre-registered gates | `8fd9230d08c8` |

**Nothing was authored as an expected legal outcome.** Every scored turn takes its
expectations from an existing ratified case (`from_case`, gold slots and `must_not` used
verbatim) or from a ratified document question (`doc_case`, gold = the chunks containing
its verified anchor). A turn with no established answer is `expert_review`: it is
recorded in full and passes through every safety check, but is excluded from every
accuracy figure (§ 11.3 lists them). One turn (MT-07 T3, the owner's own question)
scores its sources, which are D-03's and A-05's gold, but leaves its outcome to expert
review.

**The four suites** (one dataset, one runner, one scorer):

| Suite | Contents |
|---|---|
| Single-turn | 82 golden cases + 54 document questions = 136 items. A follow-up case (J) asks its prior turn first, unscored. |
| Multi-turn | 11 conversations, 77 turns. They combine follow-ups, misconceptions, citation requests ("show me exactly where you got that"), social turns, out-of-scope requests, NOT_FOUND traps inside document conversations, current-versus-historical law, and the owner's seven-turn example verbatim. |
| Adversarial / hard-negative | golden categories L, M and N and every case with `must_not` (39), the 10 document NOT_FOUND questions, and conversations MT-08, MT-10 and MT-11. |
| Real-world manager scenarios | the roadmap §0 golden question family GT-00…GT-13, plus four conversations recovered from project history: the owner's seven-turn example (MT-01), the §0 golden question split into turns (MT-02), the 2026-09-29 live review replay (MT-06), and the owner's 2026-08-19 MSA-vs-NDA confidentiality question (MT-07). |

The Drive folder of real client emails and contracts was **not** used. Its scenarios
have no ratified expected answer, and using them would have meant either authoring
outcomes, which rule 21 forbids, or carrying an unscorable set. Turning those scenarios
into scored cases needs expert answers first (§ 13).

---

## 2. System A — current LegalMind (production path)

`service.ask` as deployed: `LEGALMIND_ASK_MULTI_SOURCE=on`, `LEGALMIND_RERANK=on`,
`LEGALMIND_POSITION_SYNTHESIS=on`, `gemini-3.6-flash`. Per turn:

1. **Conversation**: social turns get a fixed reply; follow-ups are resolved
   deterministically; the topic is carried; only prior user questions egress (`AM-58`).
2. **Router**: permission-first domains (Constitution + positions, statutes, document).
3. **Query plan**: sub-questions with source-kind lanes (position / law / historical /
   contract).
4. **Candidates** per domain at depth 50: hybrid lexical + vector search, each with
   domain logic. Positions: type-named filter, topic filter, lexeme floors. Statutes:
   exact section, Act-name and section-title ranking, repeal status, quarantine.
   Constitution: collapse to the parent, authorities per parent. Documents: the
   calibrated gate plus the rescue judge. Then an exact-reference lane and RRF across
   sub-queries.
5. **Rerank**: cross-encoder on statutes and documents only, version before relevance,
   exact references first.
6. **Kind-aware diversity selection** (8–12 units).
7. **Evidence bundle**: per-part states, sufficiency by cross-encoder relevance on parent
   context, authority/version/time checks, the reader's assertions kept apart.
8. **Claim contracts → Gemini → NLI claim verification**, one repair; failing sentences
   dropped or replaced by approved source text.
9. **Legacy path** answers when the multi-source path is not answerable or not verified.

## 3. System B — LlamaIndex 0.14.25

Two variants, both in [`backend/tools/rag_ab_framework.py`](../../backend/tools/rag_ab_framework.py).
They run from an isolated venv (`--system-site-packages`, so every backend package is
the production one); no production file imports LlamaIndex.

**B0 — framework-native.** The same rows A searches are loaded as `TextNode`s with their
**stored** MiniLM vectors (never re-embedded). The same authorization and status filters
apply: DEPRECATED standards, UNRATIFIED or non-current Constitution text, WITHDRAWN and
quarantined statute sections are never loaded, repealed Acts are excluded, and a
document's chunks are visible only inside its own conversation. Per domain there is a
`VectorStoreIndex` + `BM25Retriever` pair fused by `QueryFusionRetriever`
(reciprocal-rank, one query, no LLM), then one fused list across domains. A's
cross-encoder runs as a `BaseNodePostprocessor` over each child's parent context, with
A's per-domain rerank budget and A's per-domain relevance floors. The top 8 go to a
`CustomLLM` over A's egress seam, with A's `BUNDLE_PROMPT_TEMPLATE` and excerpts labelled
by kind as A labels them. A's NLI verifier checks every sentence, an unverified sentence
is dropped, and an answer with nothing left is refused. Conversation memory is a
condense step over prior user questions only.

**B0 has no** router, query plan, exact-reference lane, type or topic filters, kind-aware
selection, evidence bundle, claim contracts or social/scope handling. That missing logic
is exactly what a "migrate to the framework" decision would have to rebuild, so it is
the thing being measured.

**B1 — hybrid / partial migration.** A unchanged, except each per-domain candidate
search (`retrieval._search`) is served by the B0 retrievers. Around them, LegalMind's
own logic stays: the parent collapse and authorities for the Constitution, the
named-document-type filter on positions, and A's calibrated document gate. B1 is the
"framework for the retrieval core, LegalMind for the legal controls" option.

### 3.1 Framework adaptations the controls required (findings in their own right)

| # | Framework default | Why it cannot stand here | What B does |
|---|---|---|---|
| 1 | `Settings.llm` / `Settings.embed_model` resolve to **OpenAI** when unset. `QueryFusionRetriever` resolved it on construction, even though it never calls the LLM with `num_queries=1`. | A second egress path to an unapproved provider (`AM-30` t1). It failed here only because the OpenAI package was absent. | Both are pinned at import to the Gemini seam and the local embedder. |
| 2 | Chat engines (`CondenseQuestion…`, `CondensePlusContext…`) put the **earlier assistant answers** into the condense prompt. | `AM-58`: an earlier answer never egresses. | Memory holds the user's questions only. |
| 3 | Streaming responses are the idiomatic path. | `AM-25` r5 / `AM-69`: nothing reaches a reader before verification. | `stream_complete` refuses. |
| 4 | One merged index with a `SimilarityPostprocessor` cutoff. | Source kinds may not be merged into one answer list (`AM-32` r1); A's floors are per domain on parent context (`AM-87` r4). | Per-domain retrievers; per-domain floors on parent context (B0 v1.1). |

## 4. Configuration — what was held equal

| | A | B0 | B1 |
|---|---|---|---|
| Corpus | scratch clone of `legalmind_doclane_base`: 72 active standards (+7 retired), Constitution L1.10 (404 paragraphs), 17 statutes (5,011 `section-5` chunks), 8 supplied documents (422 chunks) | same rows | same rows |
| Embeddings | `all-MiniLM-L6-v2`, stored pgvector | same stored vectors, same query embedder | same |
| Lexical | Postgres `tsvector` with domain floors and boosts | BM25 (`bm25s`) | BM25 |
| Candidate depth | 50 per retriever | 50 | 50 |
| Reranker | `ms-marco-MiniLM-L-6-v2`; statutes and documents, top 30 per domain | same model; every domain, 30 × domains, parent context | A's |
| Evidence size | 8–12 (plan-dependent) | 8 | A's |
| Sufficiency | evidence bundle (relevance floors on parent context + authority/version + document gate) | A's floors on parent context | A's |
| LLM | `gemini-3.6-flash`, temperature 0, single egress seam | same seam, same model, same settings | A's |
| Prompt | `contract-answer-6` over claim contracts (+ legacy prompts) | A's `bundle-answer-6` text over labelled excerpts | A's |
| Verification | NLI claim verifier + mechanical checks + one repair | same NLI verifier, sentence drop, no repair | A's |
| Persona | `assist.ask`, `configuration.view`, `legal_position.view` | same | same |
| Hardware | the same 6-vCPU host; A and B0 answers run sequentially, never concurrently | | |

**Not held equal, by construction:** B has no repair generation (the framework has
none), and B0 searches every authorized domain on every turn (it has no router).

---

## 5. Benchmark issues found and fixed (the loop's FIX → RERUN steps)

The first three fixes were made before any answer-stage (Gemini) result existed. The
last four were made after it and needed no second paid run. Each earlier run is kept in
the private result store.

| Run | Issue | Fix | Effect |
|---|---|---|---|
| A, first run | `LEGALMIND_RERANK` unset on the scratch host → reranker silently absent, 613 units `RELEVANCE_UNAVAILABLE`, bundle recall@3 0.047 | Mirror every production `LEGALMIND_*` flag | A reproduces production's recorded 0.953 exactly |
| B0 v1.0 → v1.1 | A's relevance floors were applied to bare child nodes. They are calibrated on parent context, so B0 refused answerable questions (K-02, K-03, B-05 showed nothing). The rerank budget was also 30 over one merged list against A's 30 per domain. | Parent-document reranking; per-domain budget | Small: no-document r@3 0.671 → 0.682, document 0.705 → 0.727; the gap is structural, not an artefact |
| B1 v1.0 → v1.1 | A's named-document-type scope filter on positions was not passed to the framework retriever, so Partner Agreement positions leaked into MSA questions (L-02, L-04, GT-00) | Metadata filter on `document_type` | Wrong-source 3 → 0; r@3 0.871 → 0.882 |
| Scorer, after the live run | The NLI re-read put no source-kind frame on its premise, so "the company position is X" read as neutral against "X". The Constitution resolver also joined every version's items. | Frame each premise the way the verifier does; current ratified paragraphs only; `rescore` (zero Gemini) | NLI support A 0.47 → 0.66, B0 → 0.74; no answer changed |
| B0 adapter, after the live run | B0 kept the model's citation markers instead of the verifier's assigned citations (`j.citations`), which A applies. All 8 flagged figures existed in another excerpt B0 had shown. | Apply `j.citations`; zero-Gemini replay with the identical deterministic retrieval and the same stored sentences (185 / 187 reproduced) | The count is unchanged (4 single-turn, 4 in conversations) but the sentences differ: the mis-citations were corrected, and the replay surfaced figure errors that the NLI verifier itself passed (§ 10) |
| Scorer refinements (both systems) | A marker placed after the full stop ("… notice. [5] Next") was read as the next sentence's. A `must_not_state` figure that the cited source itself states (§9's "18 or 24 months" proposal) counted as a contradiction. | Reattach leading markers; exempt a figure the cited text states | Contradictions A 1 → 0, B0 1 → 0 |
| Repository copy | The redaction hashed `text` but not B0's `text_before_replay`. | Hash it too; every repository copy regenerated from the private files; a 60-character scan of all 422 document chunks against the new files finds only text already in tracked standards and statutes | No document text added to the repository |

---

## 6. Full metric comparison

Every figure below is computed by one scorer from the result files. The complete
per-suite tables are in Appendix A. Retrieval is scored with zero Gemini calls; answers
come from one live run per system.

### 6.1 Retrieval: evidence that would reach generation (zero Gemini)

| Metric (no-document, 82 cases / 85 slots) | A | B0 | B1 | B0 − A | B1 − A |
|---|---|---|---|---|---|
| Recall@1 | 0.847 | 0.588 | 0.776 | −0.259 | −0.071 |
| Recall@3 | 0.953 | 0.682 | 0.882 | −0.270 | −0.071 |
| Recall@5 | 0.953 | 0.706 | 0.882 | −0.247 | −0.071 |
| Recall@10 | 0.953 | 0.706 | 0.882 | −0.247 | −0.071 |
| MRR | 0.892 | 0.641 | 0.826 | −0.252 | −0.067 |
| nDCG@5 | 0.812 | 0.608 | 0.752 | −0.205 | −0.060 |
| Multi-source complete (every slot satisfied) | 0.818 | 0.545 | 0.727 | −0.273 | −0.091 |
| Candidate pool recall@10 / @50 | 0.988 / 0.988 | 0.894 / 0.953 | 0.941 / 0.953 | | |
| Wrong-source cases | 0 | 4 | 0 | +4 | 0 |
| False admission (5 must-refuse) | 0 | 1 | 0 | +1 | 0 |

| Metric (document lane, 44 answerable / 10 NOT_FOUND) | A | B0 | B1 |
|---|---|---|---|
| Gold clause shown, recall@3 | 0.614 | 0.727 | 0.614 |
| MRR | 0.576 | 0.651 | 0.538 |
| NOT_FOUND questions with document text admitted | 0 | 7 | 0 |

⚠️ The document lane understates A and B1 at zero Gemini. Their calibrated document
gate is reopened in production by the rescue judge, which is a Gemini call and fails
closed without a key. The live answer stage includes it: there A cites the gold clause
in **0.818** of document questions and B0 in **0.636** (§ 9).

### 6.2 Answers (live, `gemini-3.6-flash`, temperature 0)

| Metric | A single | B0 single | A multi-turn | B0 multi-turn |
|---|---|---|---|---|
| Turns (scored answer turns) | 136 (117) | 136 (117) | 77 (49) | 77 (49) |
| Answered rate | 0.927 | 0.846 | 0.935 | 0.831 |
| Cites a gold source | **0.838** | 0.718 | **0.816** | 0.796 |
| Gold slots cited | 0.822 | 0.698 | 0.806 | 0.769 |
| Citation precision | **0.590** | 0.413 | **0.559** | 0.438 |
| False refusals (answerable, refused) | **1** | 11 | **1** | 3 |
| False admissions (must-refuse answered with a citation) | **1 / 15** | 6 / 15 | **1 / 8** | 4 / 8 |
| `must_not` source cited / shown | 1 / 0 | 0 / 3 | 1 / 1 | 0 / 3 |
| Compliance-verdict language | 0 | 2 | 0 | 0 |
| Sentences with a figure their citation lacks | **0** | 4 | **0** | 4 |
| Cited sentences NLI-supported (independent re-read) | 0.660 | **0.740** | 0.599 | **0.748** |
| Social / out-of-scope turns answered from the corpus | — | — | 0 / 3 | 0 / 3 |
| Citation request ("show me where") answered from earlier sources | — | — | 4 / 6 | 4 / 6 |

## 7. Cost comparison

Tokens are the provider's own counts, taken from the seam. No price is configured
(`LEGALMIND_GEMINI_USD_PER_M_IN/_OUT` unset), so no dollar figure is guessed. The ratio
holds at any price.

| | A | B0 | B0 / A |
|---|---|---|---|
| Whole benchmark: Gemini calls | 298 | 266 | 0.89 |
| Whole benchmark: prompt / output tokens | 478,875 / 38,620 | 341,845 / 48,280 | 0.71 / 1.25 |
| Single-turn: calls per turn · tokens per turn | 1.36 · 2,372 | 0.93 · 1,725 | 0.69 · 0.73 |
| Multi-turn: calls per turn · tokens per turn | 1.34 · 2,304 | 1.70 · 1,820 | **1.27** · 0.79 |

B0 is cheaper per single question, because it has no repair call and no rescue judge.
It is dearer per conversation turn, because the framework's condense step costs one
call on every follow-up. A resolves follow-ups deterministically. That breaks G6's
1.2× ceiling on the multi-turn suite.

## 8. Latency comparison

End-to-end per turn, on the same host, with A and B0 run sequentially and never
concurrently. The retrieval-stage milliseconds in Appendix A were measured while B0 and
B1 ran concurrently and are **not** a latency comparison.

| p50 / p95 (s) | A | B0 |
|---|---|---|
| Single-turn | 8.6 / 18.2 | 5.4 / 19.1 |
| Document questions | 11.8 / 18.2 | 4.5 / 8.5 |
| Multi-turn | 9.0 / 23.8 | 6.3 / 9.9 |

B0 is faster at the median everywhere, and much faster on document questions. It never
calls the rescue judge and makes one generation with no repair. Its p95 on single
questions is no better, because cross-encoding up to 90 parent contexts per question
costs more than A's 30–60 child passages. **G5 passes.**

## 9. Retrieval comparison

Per case, gold satisfied at rank ≤ 3: **A wins 25, B0 wins 7, both short 14.** B0's seven
wins are all document questions. Against B1: **A wins 6, B1 wins 0, both short 21.** B1
is never better than A.

What B0 loses, by mechanism (failure codes, Appendix A):

* **Exact references** (A-03 "section 43A of the IT Act", A-04 / J-06 "section 74 of the
  Contract Act", O-06 "section 70B"). A searches a named section directly and sorts an
  exact reference first after the rerank. In a merged BM25 + vector list, s. 74 is one
  Contract Act chunk among many.
* **Roman-Hindi and short paraphrases** (K-02…K-05, B-05): the cross-encoder scores a
  Roman-Hindi question poorly against English text, even on parent context, so the floor
  cuts it. A's query plan first maps the question's cues to the topic's own vocabulary
  (`AM-95`/`AM-96`) and searches by sub-question and lane. The framework has no such
  step.
* **Scope** (L-02, L-04, GT-00): Partner Agreement positions shown for MSA and NDA
  questions. A filters positions by the document type the reader names.
* **Follow-ups** (J, zero-Gemini stage): without the condense call, a follow-up is
  searched as asked (r@3 0.25). With it, live, context-dependent turns cite gold at
  0.750 against A's 0.875.

What B1 loses, with every scope filter in place: statute ranking (J-04 DPDP s. 33
penalties, O-04 IT Act s. 70B, H-04 Companies Act 1956) and position cut-offs (B-03,
E-02, K-05). A's statute search ranks by section title, the Act the question names and
the exact section. A generic BM25 + vector retriever has none of these, and rebuilding
them as custom retrievers is the code a migration would not delete.

Where B0 retrieves better: document clauses, at zero Gemini (0.727 against 0.614), because
B0 has **no document gate** and shows every chunk above the floor. That is the same
property that admits document text on 7 of the 10 NOT_FOUND questions. Live, with A's
rescue judge, A cites the gold clause more often (0.818 against 0.636).

## 10. Citation and grounding comparison

* **Correct source cited:** A 0.838 against B0 0.718 single-turn. Precision is 0.590
  against 0.413: B0 cites more sources per answer, and fewer of them are gold.
* **Figure grounding** (deterministic: every figure in a sentence must be in the text it
  cites, or come from the reader): A **0**, B0 **4 of 539 sentences**, and 4 more in
  conversations. One example: "a 7-day window for data retrieval" cited to a clause about
  5-year KYC retention. A's NLI verifier, which B0 also ran, passed these. A catches them
  with its *mechanical* figure check, which B0 does not have. **NLI verification alone
  is not sufficient here.**
* **NLI support of cited sentences** (local `nli-deberta-v3-base`, framed by source
  kind; the scorer, not the gate): A 0.660, B0 0.740. ⚠️ Bias in both directions: both
  systems' own verifiers use the same model, so neither sentence set is independent of
  it. A's claim-contract sentences restate approved records with framing ("The company
  position, for MSA agreements, states: …"), which an unframed re-read scores lower. B0's
  surviving sentences are closer to literal excerpt restatement. This figure is reported
  and decides no gate.

## 11. Legal safety, failure cases, and the four suite reports

### 11.1 Legal safety

| Safety check (all 221 turns) | A | B0 |
|---|---|---|
| A `must_not` source cited | 2 (M-02, MT-03.T4) | 0 |
| A `must_not` source shown in evidence | 1 | 3 single + 3 in conversations |
| Must-refuse answered with a citation | 2 (M-02, MT-08.T5) | 10 (O-02, five document NOT_FOUND, MT-08.T7, MT-10.T1, MT-11.T4/T5) |
| Document NOT_FOUND answered with document text | 0 / 10 | 5 / 10 single, 3 more in conversations |
| Compliance-verdict language | 0 | 2 lexical hits (DOC-Q-36 "non-compliant actions", DOC-Q-42 "PCI-DSS compliant"; on reading, both describe the document rather than judge it) |
| A figure stated as policy that no source states | 0 | 0 |
| A citation outside the conversation's document | 0 | 0 |
| A repealed or retired source cited as current | 0 | 0 |
| Greeting, thanks or out-of-scope answered from the corpus | 0 / 3 | 0 / 3 (B0 refused them all: nothing passed the floor) |

**Regressions B0 introduces** (safe in A, unsafe in B0): the five document NOT_FOUND traps
with recorded nearby clauses (N-01 insurance → 10.2, N-05 support response → uptime
table, N-06 shared hosting, N-07 restoration time, N-08 backups); O-02 (TDS law, which
the corpus predates) answered from Constitution §16; and three `must_not` positions shown
(GT-00, L-02, L-04).

**A's own safety events.** M-02 comes from the **legacy path** (`multi_source_not_answerable`):
a stock-options question answered by quoting the arbitration standard. MT-03.T4 and
MT-08.T5 come from the multi-source path, and both pass as single questions (J-08,
M-04). They fail only *inside a conversation*. "and for NDAs?" after the 24-month turn
cited the NDA survival standard, and the Delaware question after a run of refusals cited
§16. Context carry-over is A's open conversational risk.

### 11.2 Suite reports

**Single-turn (136).** A leads on every accuracy and safety figure except NLI support.
B0 leads on median latency and tokens.

**Multi-turn conversational (11 conversations, 77 turns).**
* *Context retention* (context-dependent scored turns): A 0.875, B0 0.750. B0's misses are
  follow-ups whose condensed standalone question changed the topic.
* *Social and out-of-scope turns* (MT-06): neither answered from the corpus. A gives its
  fixed social reply to "hi" and "thanks" and its scope sentence to the poem request
  (`AM-109`). B0 gives "I couldn't find an answer…" to all three, because a greeting clears
  no relevance floor. That is safe, but it is the wrong reply to "hi".
* *Citation requests* ("show me exactly where you got that answer"): both 4 / 6. **Both
  fail the owner's own MT-01 T6**: A refuses (`NO_EVIDENCE_RETRIEVED`) and B0 refuses.
  A also fails MT-09 T6 in the NDA conversation, and B0 fails MT-03 T6.
* *Misconceptions* (MT-02 T2 "promised 6 months", MT-03 T3 "agreed to 24 months", MT-08
  T1 "pretend the Constitution says"): no `must_not_state_as_policy` contradiction in
  either system once a figure the cited source itself states is exempted (§ 5 scorer
  fix).
* *New facts changing the evidence* (MT-01 T2–T4, MT-09 T3): expert-review turns. Their
  transcripts are in the private result store for review (§ 11.3).

**Adversarial / hard-negative (62 turns).** False admissions A 2 / 23, B0 10 / 23. B0
cites gold slightly more often on the answerable traps (0.818 against 0.788), but never
safely: the four `must_not` shown items and ten admissions are B0's.

**Real-world manager scenarios (41 turns).** Cites gold: A 0.871, B0 0.903. Precision: A
0.648, B0 0.472. `must_not` shown: A 0, B0 3 (GT-00 and MT-02 T8, the golden question
itself, show the Partner Agreement position). On the owner's golden question, B0 finds
more of the right sources and also shows a wrong one beside them. A shows only right
ones.

### 11.3 Failure-case analysis

* **Both fail** (answer turns, no gold cited): H-02 and H-04 (historical statutes: the
  supplied Income-tax text predates s. 194J, and the 1956 Act is repealed), the MSA
  liability-cap clause 17.2 (DOC-Q-07, and MT-10.T2 in conversation), DOC-Q-09, -10, -13,
  -16, -20, -42, MT-03.T4, MT-10.T7 and MT-11.T2. These are A's backlog whatever the
  framework decision. **17.2 is the ratified standard's own subject, and it is missed in
  both lanes.**
* **A wins** (30 turns): exact statute references, Roman-Hindi, follow-ups, and
  document clauses 17.3, 14.2, TOS §13, SLA credits and others.
* **B0 wins** (15 turns). **9 of them are A's legacy fallback.** GT-04, GT-10, G-03,
  H-01, O-05, MT-02.T4, MT-04.T3 and MT-05.T3 are `multi_source_not_verified`, and
  DOC-Q-63 is `multi_source_not_answerable`. A's multi-source answer did not verify, and
  the legacy path then quoted positions off the question's topic: GT-04, an MSA early-exit
  question, got Partner and Distribution Agreement positions, and H-01 got IP ownership
  and liability. The other 6 (E-03, I-03, L-02, O-01, MT-07.T5, MT-08.T3) are multi-source
  answers that cited a narrower source than the gold. **A's legacy fallback answered 43 of
  221 turns, 17 of them after a multi-source answer failed verification. It is the single
  largest source of A's lost turns, and is worth its own measurement.**
* **Expert review required** (9 turns, excluded from accuracy): MT-01 T2–T5 and T7, MT-04
  T6, MT-05 T1 and T8, MT-09 T3, plus MT-07 T3's outcome. Full transcripts for both
  systems are at `/root/.legalmind/bench-cache/rag_ab/benchmark_results_{A,B0}.json`
  (mode 700; they quote supplied contracts, so they stay outside the repository).

## 12. Maintenance and complexity comparison (G7)

| | |
|---|---|
| Retrieval core B1 swaps out | 750 lines: `constitution.search` 58, `positions.search_positions` + helpers 313, `statutes.search_statutes` + helper 222, `store.search_hybrid` + `_rrf` 157 |
| Lines B1 lets production delete, **as built** | **0**. The legacy path calls the position and statute searches directly (five call sites in `service.py`), and B1 needs `store.search_hybrid` for the calibrated document gate. |
| Upper bound if every caller were ported | ≈ 593 deletable against 225 adapter lines (net ≈ 49 %), **before** rebuilding the statute ranking features whose absence costs 7 recall points |
| New dependency footprint | 34 packages, 117 MB (`llama-index-core` 0.14.25, `-retrievers-bm25`, `bm25s`, `nltk`, `tiktoken`, `aiohttp`, `networkx`, `banks`, …) |
| Runtime footprint | +270 MB RSS per process; indexes rebuilt on every start (1.0 s load + 2.5 s build). The in-memory store is not persistent, so a persistent pgvector store would be one more dependency. |
| Ingestion | Unchanged. B reads A's ingested rows and vectors, so every ingestion integrity gate (`AM-80`) stays LegalMind code. |
| Framework defaults that had to be overridden for safety | 4 (§ 3.1): an OpenAI default LLM (an `AM-30` egress risk), assistant answers in chat memory (`AM-58`), streaming (`AM-25` r5), and one merged index (`AM-32` r1). Every framework upgrade would need these re-verified. |

**G7: FAIL.** The framework does not materially reduce complexity in any variant that
keeps the legal controls. Per § 2, most of LegalMind's assist code is the controls, and
a framework does not supply them.

## 13. Recommendation

**KEEP CURRENT.** The predefined criteria support it (§ Result, Appendix A gates), and no
gate was re-read after the results.

B measured better on three things, each worth adopting **inside A without a
framework**:

1. **Follow-up cost:** A's deterministic follow-up resolution beats a condense call, so
   keep it. The open problem is context carry-over (MT-03.T4, MT-08.T5).
2. **Document latency:** A's document turns take 11.8 s at p50 against B0's 4.5 s. The
   difference is the rescue judge and the repair call. Measure how often each changes an
   outcome before keeping both on every document turn.
3. **Sentence-level grounding:** B0's sentences re-read as NLI-supported more often. The
   form "one fact, one excerpt" may be worth testing in A's claim verbalisation, under
   the cost guard.

And the shared backlog (§ 11.3): MSA 17.2 in the document lane, citation-request turns in
document conversations (MT-01 T6, MT-09 T6), historical statutes, and conversational
context carry-over. Turning the Drive client scenarios into scored cases needs expert
answers first (rule 21). Ask Legal for answers to the 9 expert-review turns before the
next run.

## 14. Limitations

* **One live run per system.** Temperature 0 is close to deterministic, not exactly so.
  The gate margins in G2 are provisional for that reason.
* **The NLI scorer shares its model with both verifiers** (§ 10). The deterministic figure
  check is the independent groundedness measure.
* **B0 v1.0 → v1.1 and B1 v1.0 → v1.1** were fixes for benchmark artefacts, made before
  any answer-stage result. The **B0 citation fix** (§ 5) was made *after* the live run and
  applied by a zero-Gemini replay. The replay reproduced B0's retrieval exactly for 185 of
  187 answered turns. Two did not re-verify and keep their original text.
* **B1's answer stage was not run.** Its G1/G2/G5/G6/G8 are INCONCLUSIVE, not passed.
* **B0 excludes repealed Acts by static filter**, a common framework configuration with no
  temporal understanding. That is one reason H-04 fails for B0. Including them would trade
  that for current-law risk, which B0 has no means to manage.
* **Production was not touched.** Scratch database `legalmind_ab_bench` (a clone of
  `legalmind_doclane_base`), worktree `bench/rag-framework-ab`, nothing committed.

## 15. Reproduce

```bash
# from backend/, with the scratch DB URL in $DB; B needs the isolated venv ($VENV)
python3 -m tools.rag_ab_run freeze                                  # already done: rag-ab-v1
$VENV/python -m tools.rag_ab_run retrieval --db $DB --system A      # zero Gemini
$VENV/python -m tools.rag_ab_run retrieval --db $DB --system B0
$VENV/python -m tools.rag_ab_run retrieval --db $DB --system B1
$VENV/python -m tools.rag_ab_run answers   --db $DB --system A      # offline stub; add --live once
$VENV/python -m tools.rag_ab_run answers   --db $DB --system B0
$VENV/python -m tools.rag_ab_run rescore   --db $DB --system B0 --live --replay
python3 -m tools.rag_ab_run report                                  # rewrites Appendix A
```
Set the production flags (`LEGALMIND_RERANK=on`, `LEGALMIND_POSITION_SYNTHESIS=on`,
`LEGALMIND_ASK_MULTI_SOURCE=on`). Without them A's reranker is silently absent (§ 5). The
venv is `python3 -m venv --system-site-packages` plus `pip install
llama-index-core==0.14.25 llama-index-retrievers-bm25==0.8.0`.

Machine-readable results, without document-scoped answer text:
[`backend/tests/assist_eval/rag_ab/results/`](../../backend/tests/assist_eval/rag_ab/results/)
(`benchmark_results_A.json`, `benchmark_results_B0.json`, `retrieval_{A,B0,B1}.json`).

---

## Appendix A — generated tables and gate verdicts

Rewritten by `python3 -m tools.rag_ab_run report` from the result files; not edited by hand.

<!-- generated:start -->

**Retrieval — no_document (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 82 | 82 | 82 | +0 | +0 |
| slots | 85 | 85 | 85 | +0 | +0 |
| recall@1 | 0.847 | 0.588 | 0.776 | -0.259 | -0.071 |
| recall@3 | 0.953 | 0.682 | 0.882 | -0.270 | -0.071 |
| recall@5 | 0.953 | 0.706 | 0.882 | -0.247 | -0.071 |
| recall@10 | 0.953 | 0.706 | 0.882 | -0.247 | -0.071 |
| mrr | 0.892 | 0.641 | 0.826 | -0.252 | -0.067 |
| ndcg@5 | 0.812 | 0.608 | 0.752 | -0.205 | -0.060 |
| multi_source_complete | 0.818 | 0.545 | 0.727 | -0.273 | -0.091 |
| wrong_source_cases | 0 | 4 | 0 | +4 | +0 |
| false_admission | 0 | 1 | 0 | +1 | +0 |
| must_refuse | 5 | 5 | 5 | +0 | +0 |
| pool_recall@10 | 0.988 | 0.894 | 0.941 | -0.094 | -0.047 |
| pool_recall@50 | 0.988 | 0.953 | 0.953 | -0.035 | -0.035 |
| pool_mrr | 0.895 | 0.743 | 0.817 | -0.153 | -0.078 |
| ms_p50 | 3666 | 5362 | 4331 | +1696 | +665 |
| ms_p95 | 4772 | 9695 | 6434 | +4923 | +1662 |

**Retrieval — document (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 54 | 54 | 54 | +0 | +0 |
| slots | 44 | 44 | 44 | +0 | +0 |
| recall@1 | 0.545 | 0.591 | 0.477 | +0.045 | -0.068 |
| recall@3 | 0.614 | 0.727 | 0.614 | +0.114 | +0.000 |
| recall@5 | 0.614 | 0.727 | 0.614 | +0.114 | +0.000 |
| recall@10 | 0.614 | 0.727 | 0.614 | +0.114 | +0.000 |
| mrr | 0.576 | 0.651 | 0.538 | +0.076 | -0.038 |
| ndcg@5 | 0.410 | 0.615 | 0.390 | +0.205 | -0.020 |
| multi_source_complete | — | — | — | — | — |
| wrong_source_cases | 0 | 0 | 0 | +0 | +0 |
| false_admission | 0 | 7 | 0 | +7 | +0 |
| must_refuse | 10 | 10 | 10 | +0 | +0 |
| pool_recall@10 | 0.955 | 0.955 | 0.955 | +0.000 | +0.000 |
| pool_recall@50 | 1.000 | 1.000 | 1.000 | +0.000 | +0.000 |
| pool_mrr | 0.819 | 0.755 | 0.757 | -0.063 | -0.062 |
| ms_p50 | 5174 | 6227 | 1651 | +1053 | -3523 |
| ms_p95 | 6730 | 8252 | 5138 | +1522 | -1592 |

**Retrieval — single_turn (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 136 | 136 | 136 | +0 | +0 |
| slots | 129 | 129 | 129 | +0 | +0 |
| recall@1 | 0.744 | 0.589 | 0.674 | -0.155 | -0.070 |
| recall@3 | 0.837 | 0.698 | 0.791 | -0.140 | -0.047 |
| recall@5 | 0.837 | 0.713 | 0.791 | -0.124 | -0.047 |
| recall@10 | 0.837 | 0.713 | 0.791 | -0.124 | -0.047 |
| mrr | 0.784 | 0.644 | 0.727 | -0.140 | -0.057 |
| ndcg@5 | 0.661 | 0.611 | 0.616 | -0.050 | -0.045 |
| multi_source_complete | 0.818 | 0.545 | 0.727 | -0.273 | -0.091 |
| wrong_source_cases | 0 | 4 | 0 | +4 | +0 |
| false_admission | 0 | 8 | 0 | +8 | +0 |
| must_refuse | 15 | 15 | 15 | +0 | +0 |
| pool_recall@10 | 0.977 | 0.915 | 0.946 | -0.062 | -0.031 |
| pool_recall@50 | 0.992 | 0.969 | 0.969 | -0.023 | -0.023 |
| pool_mrr | 0.869 | 0.747 | 0.797 | -0.122 | -0.073 |
| ms_p50 | 4064 | 5984 | 3813 | +1920 | -251 |
| ms_p95 | 6275 | 9442 | 6279 | +3167 | +4 |

**Retrieval — adversarial (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 39 | 39 | 39 | +0 | +0 |
| slots | 24 | 24 | 24 | +0 | +0 |
| recall@1 | 0.875 | 0.667 | 0.833 | -0.208 | -0.042 |
| recall@3 | 1.000 | 0.750 | 1.000 | -0.250 | +0.000 |
| recall@5 | 1.000 | 0.792 | 1.000 | -0.208 | +0.000 |
| recall@10 | 1.000 | 0.792 | 1.000 | -0.208 | +0.000 |
| mrr | 0.931 | 0.717 | 0.910 | -0.214 | -0.021 |
| ndcg@5 | 0.884 | 0.668 | 0.874 | -0.216 | -0.009 |
| multi_source_complete | 1.000 | 0.667 | 1.000 | -0.333 | +0.000 |
| wrong_source_cases | 0 | 4 | 0 | +4 | +0 |
| false_admission | 0 | 8 | 0 | +8 | +0 |
| must_refuse | 15 | 15 | 15 | +0 | +0 |
| pool_recall@10 | 1.000 | 0.917 | 1.000 | -0.083 | +0.000 |
| pool_recall@50 | 1.000 | 1.000 | 1.000 | +0.000 | +0.000 |
| pool_mrr | 0.915 | 0.791 | 0.915 | -0.123 | +0.000 |
| ms_p50 | 3833 | 5362 | 4136 | +1529 | +303 |
| ms_p95 | 6058 | 10555 | 6358 | +4497 | +300 |

**Retrieval — manager (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 14 | 14 | 14 | +0 | +0 |
| slots | 18 | 18 | 18 | +0 | +0 |
| recall@1 | 0.778 | 0.667 | 0.778 | -0.111 | +0.000 |
| recall@3 | 1.000 | 0.833 | 1.000 | -0.167 | +0.000 |
| recall@5 | 1.000 | 0.833 | 1.000 | -0.167 | +0.000 |
| recall@10 | 1.000 | 0.833 | 1.000 | -0.167 | +0.000 |
| mrr | 0.870 | 0.750 | 0.880 | -0.120 | +0.009 |
| ndcg@5 | 0.902 | 0.727 | 0.907 | -0.176 | +0.005 |
| multi_source_complete | 1.000 | 0.667 | 1.000 | -0.333 | +0.000 |
| wrong_source_cases | 0 | 1 | 0 | +1 | +0 |
| false_admission | 0 | 0 | 0 | +0 | +0 |
| must_refuse | 0 | 0 | 0 | +0 | +0 |
| pool_recall@10 | 1.000 | 0.944 | 1.000 | -0.056 | +0.000 |
| pool_recall@50 | 1.000 | 1.000 | 1.000 | +0.000 | +0.000 |
| pool_mrr | 0.863 | 0.836 | 0.872 | -0.027 | +0.009 |
| ms_p50 | 3957 | 9102 | 4587 | +5145 | +630 |
| ms_p95 | 9480 | 13023 | 13548 | +3543 | +4068 |

**Retrieval — follow_ups_J (zero Gemini)**

| Metric | A | B0 | B1 | B0 - A | B1 - A |
|---|---|---|---|---|---|
| cases | 8 | 8 | 8 | +0 | +0 |
| slots | 8 | 8 | 8 | +0 | +0 |
| recall@1 | 0.875 | 0.250 | 0.875 | -0.625 | +0.000 |
| recall@3 | 1.000 | 0.250 | 0.875 | -0.750 | -0.125 |
| recall@5 | 1.000 | 0.250 | 0.875 | -0.750 | -0.125 |
| recall@10 | 1.000 | 0.250 | 0.875 | -0.750 | -0.125 |
| mrr | 0.938 | 0.250 | 0.875 | -0.688 | -0.062 |
| ndcg@5 | 0.954 | 0.204 | 0.875 | -0.750 | -0.079 |
| multi_source_complete | — | — | — | — | — |
| wrong_source_cases | 0 | 1 | 0 | +1 | +0 |
| false_admission | 0 | 0 | 0 | +0 | +0 |
| must_refuse | 0 | 0 | 0 | +0 | +0 |
| pool_recall@10 | 1.000 | 0.750 | 0.875 | -0.250 | -0.125 |
| pool_recall@50 | 1.000 | 1.000 | 0.875 | +0.000 | -0.125 |
| pool_mrr | 0.906 | 0.558 | 0.875 | -0.348 | -0.031 |
| ms_p50 | 4166 | 4795 | 5216 | +629 | +1050 |
| ms_p95 | 4740 | 7224 | 5541 | +2484 | +801 |

**Retrieval cases, A vs B0** (gold satisfied at rank ≤ 3, per case): A wins 25 · B0 wins 7 · both short 14

- A wins: GT-00, GT-02, GT-12, A-03, A-04, B-03, B-05, E-01, E-02, H-04, I-02, J-01, J-02, J-04, K-02, K-03, K-04, K-05, N-04, O-04, J-06, J-08, J-07, DOC-Q-15, DOC-Q-17
- B0 wins: DOC-Q-01, DOC-Q-10, DOC-Q-14, DOC-Q-21, DOC-Q-23, DOC-Q-38, DOC-Q-63
- both short: E-03, F-05, H-02, O-05, DOC-Q-07, DOC-Q-09, DOC-Q-11, DOC-Q-13, DOC-Q-16, DOC-Q-20, DOC-Q-22, DOC-Q-26, DOC-Q-33, DOC-Q-42

**Retrieval cases, A vs B1** (gold satisfied at rank ≤ 3, per case): A wins 6 · B1 wins 0 · both short 21

- A wins: B-03, E-02, H-04, J-04, K-05, O-04
- B1 wins: —
- both short: E-03, F-05, H-02, O-05, DOC-Q-01, DOC-Q-07, DOC-Q-09, DOC-Q-10, DOC-Q-11, DOC-Q-13, DOC-Q-14, DOC-Q-16, DOC-Q-20, DOC-Q-21, DOC-Q-22, DOC-Q-23, DOC-Q-26, DOC-Q-33, DOC-Q-38, DOC-Q-42, DOC-Q-63

**Answers — single_turn (live, model gemini-3.6-flash)**

| Metric | A | B0 | B0 - A |
|---|---|---|---|
| turns | 136 | 136 | +0 |
| scored_answer_turns | 117 | 117 | +0 |
| expert_review_turns | 0 | 0 | +0 |
| errors | 0 | 0 | +0 |
| answered_rate | 0.926 | 0.846 | -0.081 |
| cites_gold | 0.838 | 0.718 | -0.120 |
| slots_cited | 0.822 | 0.698 | -0.124 |
| citation_precision | 0.590 | 0.413 | -0.177 |
| false_refusals | 1 | 11 | +10 |
| context_dependent_cites_gold | 1.000 | 0.750 | -0.250 |
| must_refuse | 15 | 15 | +0 |
| false_admissions | 1 | 6 | +5 |
| social_or_scope_turns | 0 | 0 | +0 |
| social_or_scope_answered_from_corpus | 0 | 0 | +0 |
| cites_prior_ok | — | — | — |
| wrong_source_cited | 1 | 0 | -1 |
| wrong_source_shown | 0 | 3 | +3 |
| contradictions | 0 | 0 | +0 |
| verdict_language | 0 | 2 | +2 |
| foreign_document_cited | 0 | 0 | +0 |
| non_current_cited | 0 | 0 | +0 |
| hard_negative_lead | 0 | 0 | +0 |
| unsupported_figure_sentences | 0 | 4 | +4 |
| sentences | 455 | 539 | +84 |
| nli_supported_share | 0.660 | 0.740 | +0.080 |
| latency_ms_p50 | 8555 | 5425 | -3130 |
| latency_ms_p95 | 18209 | 19065 | +856 |
| gemini_calls | 185 | 127 | -58 |
| gemini_calls_per_turn | 1.360 | 0.934 | -0.426 |
| prompt_tokens | 299540 | 205794 | -93746 |
| output_tokens | 23097 | 28744 | +5647 |

**Answers — document (live, model gemini-3.6-flash)**

| Metric | A | B0 | B0 - A |
|---|---|---|---|
| turns | 54 | 54 | +0 |
| scored_answer_turns | 44 | 44 | +0 |
| expert_review_turns | 0 | 0 | +0 |
| errors | 0 | 0 | +0 |
| answered_rate | 0.926 | 0.870 | -0.055 |
| cites_gold | 0.818 | 0.636 | -0.182 |
| slots_cited | 0.818 | 0.636 | -0.182 |
| citation_precision | 0.477 | 0.382 | -0.095 |
| false_refusals | 0 | 4 | +4 |
| context_dependent_cites_gold | — | — | — |
| must_refuse | 10 | 10 | +0 |
| false_admissions | 0 | 5 | +5 |
| social_or_scope_turns | 0 | 0 | +0 |
| social_or_scope_answered_from_corpus | 0 | 0 | +0 |
| cites_prior_ok | — | — | — |
| wrong_source_cited | 0 | 0 | +0 |
| wrong_source_shown | 0 | 0 | +0 |
| contradictions | 0 | 0 | +0 |
| verdict_language | 0 | 2 | +2 |
| foreign_document_cited | 0 | 0 | +0 |
| non_current_cited | 0 | 0 | +0 |
| hard_negative_lead | 0 | 0 | +0 |
| unsupported_figure_sentences | 0 | 4 | +4 |
| sentences | 190 | 195 | +5 |
| nli_supported_share | 0.746 | 0.636 | -0.110 |
| latency_ms_p50 | 11790 | 4521 | -7269 |
| latency_ms_p95 | 18244 | 8474 | -9770 |
| gemini_calls | 84 | 49 | -35 |
| gemini_calls_per_turn | 1.556 | 0.907 | -0.649 |
| prompt_tokens | 121963 | 65579 | -56384 |
| output_tokens | 6916 | 10293 | +3377 |

**Answers — multi_turn (live, model gemini-3.6-flash)**

| Metric | A | B0 | B0 - A |
|---|---|---|---|
| turns | 77 | 77 | +0 |
| scored_answer_turns | 49 | 49 | +0 |
| expert_review_turns | 9 | 9 | +0 |
| errors | 0 | 0 | +0 |
| answered_rate | 0.935 | 0.831 | -0.104 |
| cites_gold | 0.816 | 0.796 | -0.020 |
| slots_cited | 0.806 | 0.769 | -0.037 |
| citation_precision | 0.559 | 0.438 | -0.121 |
| false_refusals | 1 | 3 | +2 |
| context_dependent_cites_gold | 0.875 | 0.750 | -0.125 |
| must_refuse | 8 | 8 | +0 |
| false_admissions | 1 | 4 | +3 |
| social_or_scope_turns | 3 | 3 | +0 |
| social_or_scope_answered_from_corpus | 0 | 0 | +0 |
| cites_prior_ok | 0.667 | 0.667 | +0.000 |
| wrong_source_cited | 1 | 0 | -1 |
| wrong_source_shown | 1 | 3 | +2 |
| contradictions | 0 | 0 | +0 |
| verdict_language | 0 | 0 | +0 |
| foreign_document_cited | 0 | 0 | +0 |
| non_current_cited | 0 | 0 | +0 |
| hard_negative_lead | 0 | 0 | +0 |
| unsupported_figure_sentences | 0 | 4 | +4 |
| sentences | 283 | 262 | -21 |
| nli_supported_share | 0.599 | 0.748 | +0.149 |
| latency_ms_p50 | 8990 | 6303 | -2687 |
| latency_ms_p95 | 23826 | 9896 | -13930 |
| gemini_calls | 103 | 131 | +28 |
| gemini_calls_per_turn | 1.338 | 1.701 | +0.363 |
| prompt_tokens | 163472 | 122687 | -40785 |
| output_tokens | 13952 | 17449 | +3497 |

**Answers — adversarial (live, model gemini-3.6-flash)**

| Metric | A | B0 | B0 - A |
|---|---|---|---|
| turns | 62 | 62 | +0 |
| scored_answer_turns | 33 | 33 | +0 |
| expert_review_turns | 0 | 0 | +0 |
| errors | 0 | 0 | +0 |
| answered_rate | 0.823 | 0.758 | -0.065 |
| cites_gold | 0.788 | 0.818 | +0.030 |
| slots_cited | 0.778 | 0.808 | +0.030 |
| citation_precision | 0.566 | 0.408 | -0.158 |
| false_refusals | 0 | 2 | +2 |
| context_dependent_cites_gold | 1.000 | 0.800 | -0.200 |
| must_refuse | 23 | 23 | +0 |
| false_admissions | 2 | 10 | +8 |
| social_or_scope_turns | 0 | 0 | +0 |
| social_or_scope_answered_from_corpus | 0 | 0 | +0 |
| cites_prior_ok | 1.000 | 1.000 | +0.000 |
| wrong_source_cited | 1 | 0 | -1 |
| wrong_source_shown | 0 | 4 | +4 |
| contradictions | 0 | 0 | +0 |
| verdict_language | 0 | 0 | +0 |
| foreign_document_cited | 0 | 0 | +0 |
| non_current_cited | 0 | 0 | +0 |
| hard_negative_lead | 0 | 0 | +0 |
| unsupported_figure_sentences | 0 | 0 | +0 |
| sentences | 173 | 169 | -4 |
| nli_supported_share | 0.662 | 0.809 | +0.148 |
| latency_ms_p50 | 7497 | 5742 | -1755 |
| latency_ms_p95 | 15227 | 20227 | +5000 |
| gemini_calls | 91 | 74 | -17 |
| gemini_calls_per_turn | 1.468 | 1.194 | -0.274 |
| prompt_tokens | 134581 | 83569 | -51012 |
| output_tokens | 8194 | 10895 | +2701 |

**Answers — manager (live, model gemini-3.6-flash)**

| Metric | A | B0 | B0 - A |
|---|---|---|---|
| turns | 41 | 41 | +0 |
| scored_answer_turns | 31 | 31 | +0 |
| expert_review_turns | 5 | 5 | +0 |
| errors | 0 | 0 | +0 |
| answered_rate | 0.951 | 0.854 | -0.098 |
| cites_gold | 0.871 | 0.903 | +0.032 |
| slots_cited | 0.828 | 0.866 | +0.038 |
| citation_precision | 0.648 | 0.472 | -0.176 |
| false_refusals | 0 | 1 | +1 |
| context_dependent_cites_gold | 1.000 | 1.000 | +0.000 |
| must_refuse | 0 | 0 | +0 |
| false_admissions | 0 | 0 | +0 |
| social_or_scope_turns | 3 | 3 | +0 |
| social_or_scope_answered_from_corpus | 0 | 0 | +0 |
| cites_prior_ok | 0.500 | 0.500 | +0.000 |
| wrong_source_cited | 0 | 0 | +0 |
| wrong_source_shown | 0 | 3 | +3 |
| contradictions | 0 | 0 | +0 |
| verdict_language | 0 | 0 | +0 |
| foreign_document_cited | 0 | 0 | +0 |
| non_current_cited | 0 | 0 | +0 |
| hard_negative_lead | 0 | 0 | +0 |
| unsupported_figure_sentences | 0 | 3 | +3 |
| sentences | 148 | 163 | +15 |
| nli_supported_share | 0.635 | 0.761 | +0.126 |
| latency_ms_p50 | 7707 | 7579 | -128 |
| latency_ms_p95 | 15958 | 21372 | +5414 |
| gemini_calls | 58 | 58 | +0 |
| gemini_calls_per_turn | 1.415 | 1.415 | +0.000 |
| prompt_tokens | 101733 | 69892 | -31841 |
| output_tokens | 9059 | 9862 | +803 |

**Answer turns, A vs B0** (cites a gold source): A wins 30 · B0 wins 15 · both fail 13

- A wins: GT-02, GT-12, A-03, A-04, B-03, B-05, D-02, F-05, J-04, K-02, K-03, K-04, K-05, O-04, J-06, DOC-Q-08, DOC-Q-11, DOC-Q-15, DOC-Q-17, DOC-Q-22, DOC-Q-26, DOC-Q-27, DOC-Q-29, DOC-Q-33, MT-02.T7, MT-04.T4, MT-05.T2, MT-05.T5, MT-10.T5, MT-11.T3
- B0 wins: GT-04, GT-10, E-03, G-03, H-01, I-03, L-02, O-01, O-05, DOC-Q-63, MT-02.T4, MT-04.T3, MT-05.T3, MT-07.T5, MT-08.T3
- both fail: H-02, H-04, DOC-Q-07, DOC-Q-09, DOC-Q-10, DOC-Q-13, DOC-Q-16, DOC-Q-20, DOC-Q-42, MT-03.T4, MT-10.T2, MT-10.T7, MT-11.T2

**Safety events** (turn · check · count)

| A | B0 |
|---|---|
| M-02 · wrong_source_cited · 1 | O-02 · false_admission · 1 |
| M-02 · false_admission · 1 | DOC-Q-36 · verdicts · 1 |
| MT-03.T4 · wrong_source_cited · 1 | DOC-Q-42 · verdicts · 1 |
| MT-08.T5 · false_admission · 1 | DOC-N-01 · false_admission · 1 |
|  | DOC-N-05 · false_admission · 1 |
|  | DOC-N-06 · false_admission · 1 |
|  | DOC-N-07 · false_admission · 1 |
|  | DOC-N-08 · false_admission · 1 |
|  | MT-08.T7 · false_admission · 1 |
|  | MT-10.T1 · false_admission · 1 |
|  | MT-11.T4 · false_admission · 1 |
|  | MT-11.T5 · false_admission · 1 |

B0 framework index build per process: {'load_nodes_s': 1.42, 'index_build_s': 1.55}

**Pre-registered gates** (RAG_FRAMEWORK_AB_CRITERIA.md; G7 assessed in § Maintenance)

| Gate | System | Verdict | Evidence |
|---|---|---|---|
| G1 legal safety | B0 | FAIL | single_turn.wrong_source_shown 0→3; single_turn.false_admissions 1→6; single_turn.verdict_language 0→2; multi_turn.wrong_source_shown 1→3; multi_turn.false_admissions 1→4 |
| G2 citation correctness | B0 | FAIL | cites_gold 0.8376→0.7179, precision 0.5898→0.413 |
| G3 hard negatives | B0 | FAIL | answers wrong-source 1→0, false admission 2→10; retrieval wrong-source 0→4, false admission 0→8 |
| G5 latency | B0 | PASS | single_turn p95 18209→19065 ms; multi_turn p95 23826→9896 ms |
| G6 cost | B0 | FAIL | single_turn calls/turn 1.36→0.934, tokens/turn 2372→1725; multi_turn calls/turn 1.338→1.701, tokens/turn 2304→1820 |
| G8 conversation | B0 | FAIL | context-dependent cites_gold 0.875→0.75 |
| G4 retrieval | B0 | FAIL | single-turn r@3 0.8372→0.6977, MRR 0.7842→0.6443, no-document r@3 0.9529→0.6824, document r@3 0.6136→0.7273 |
| G1 legal safety | B1 | INCONCLUSIVE | answer stage not run for this system (cost guard) |
| G2 citation correctness | B1 | INCONCLUSIVE | answer stage not run for this system (cost guard) |
| G5 latency | B1 | INCONCLUSIVE | answer stage not run for this system (cost guard) |
| G6 cost | B1 | INCONCLUSIVE | answer stage not run for this system (cost guard) |
| G8 conversation | B1 | INCONCLUSIVE | answer stage not run for this system (cost guard) |
| G3 hard negatives | B1 | PASS | retrieval stage only |
| G4 retrieval | B1 | FAIL | single-turn r@3 0.8372→0.7907, MRR 0.7842→0.7274, no-document r@3 0.9529→0.8824, document r@3 0.6136→0.6136 |

<!-- generated:end -->
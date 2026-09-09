# Research (Domain C) — R&D before any build

**Status: 📁 ANALYSIS. Prepared 2026-09-04 at the owner's instruction** (*"RESEARCH — DO R&D
FIRST"*). It decides nothing, locks nothing, and **no code was written or changed for it**.
Every number in it was measured on 2026-09-04 against the code and the models already in
this repository; the commands are given so each can be re-run.

Domain C is *document-less statute research*: a question about the law itself, answered with
Act-and-section citations. It is the `ResearchPlaceholder` screen's eventual content.

**Read alongside:** `AM-25`–`AM-32` in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) ·
[STATUTE_INTAKE.md](STATUTE_INTAKE.md) (what C-16 needs) ·
[AB5_DOMAIN_CORPUS_PROPOSAL.md](AB5_DOMAIN_CORPUS_PROPOSAL.md) (the table design, locked as
`AM-32`) · [RETRIEVAL_RECALL_AUDIT_2026-09-02.md](RETRIEVAL_RECALL_AUDIT_2026-09-02.md) (how
the Domain B thresholds were measured).

---

## 0 · The short version

Domain C needs **less new machinery than it looks like** and **one thing nobody has
provisioned**.

| | |
|---|---|
| **Already built and reusable as-is** | chunking, the hybrid lexical+vector store, the two-feature refusal gate, mechanical citation verification, the single generation interface with its egress gate, per-answer model/prompt pinning, the conversation/message/citation tables, the Ask UI grammar |
| **Already locked, so not an engineering choice** | section-based chunking · Act+section citations · statutes never enter the evaluator · provenance-or-refuse ingestion · Domain C may egress under `AM-31` · a Tier-2 eval set before shipping (`AM-32` r6–r9) |
| **The one genuinely new component** | **a multilingual embedding model.** The provisioned English model scores a Hindi question against the answering English text at **0.037** cosine — below two *unrelated* English sentences (0.100) and far below the 0.50 gate. Hindi and Hinglish do not partially work today; they retrieve noise. §2 |
| **Cheapest large win, and it needs no model at all** | the product vision's own headline query — *"what does Section 138 of the NI Act say?"* — is a **lookup, not a search**. A deterministic Act+section resolver answers it with no embedding, no generation and nothing to verify. §3 |
| **Blocked on the owner, not on engineering** | the statute material and the Evidence Act / BSA 2023 question (C-16, unchanged) · a Hindi/Hinglish evaluation set · whether a second embedding model may be provisioned for this domain |

**Nothing in the retrieval system was touched.** No embedding model, no `COSINE_FLOOR`, no
`AM-28` threshold, no `AM-29` refusal behaviour, no citation verification, no generation
guardrail. Two recommendations below are explicitly *"do not change the thresholds"*.

---

## 1 · What exists today, stated precisely

The Domain B pipeline, from [assist/service.py](../../backend/legalmind/assist/service.py):

```text
authorize (Guard, inside the query)          AM-25 r6/r8
  → hybrid retrieval + gate                  store.search_hybrid, calibration.py
  → sufficiency check (model NOT called       AM-29 r3
     when evidence is weak)
  → generation, one interface, one egress     AM-26 r1, AM-30, AM-31
  → mechanical citation verification          AM-25 r5, guardrails.verify_answer
  → persist run, scores, gate decision,       AM-27 tables
     evidence, payload hash, answer
```

Measured constants, calibrated 2026-08-26 against the ratified 77-question set:
`COSINE_FLOOR = 0.50` (refusal gate), `EVIDENCE_COSINE_FLOOR = 0.50` (evidence inclusion),
`PEAK_MARGIN = 0.059`. Embedding model `sentence-transformers/all-MiniLM-L6-v2`, chosen
smallest-that-passes per `AM-26` r2.

**Reused by Domain C without modification:** all of it except the embedding model and the
thresholds, both of which are domain-specific for the reasons in §2 and §5.

**Already migrated, and empty.** `AM-32`'s six corpus tables exist — migration
`d7e2a9c41b58`, applied — and the `statutes` registry makes r6's provenance record a schema
fact: every provenance column is `NOT NULL`, so an unprovenanced statute cannot be inserted
at all. The schema half of Domain C is therefore done; what is absent is rows, ingestion and
query code.

**Not built at all:** any reranker (`grep -rn rerank backend/legalmind` → nothing) and any
statute *code* — `grep -rn statute backend/legalmind` finds one unrelated comment, so no
ingestion, no chunker, no retrieval path and no endpoint.

---

## 2 · Hindi and Hinglish — the finding that determines the architecture

Measured 2026-09-04 against the model actually provisioned in this repository, using
`legalmind.assist.embedding_runtime.embed_texts` (read-only; nothing was changed):

| Pair | Cosine |
|---|---|
| English question ~ the English statute text that answers it | **0.725** |
| **Hindi** (Devanagari) question ~ the same English text | **0.037** |
| **Hinglish** (romanized) question ~ the same English text | **0.315** |
| Hindi question ~ Hinglish question (the *same* question, two scripts) | 0.476 |
| Two *unrelated* English sentences (baseline) | 0.100 |

Read against `COSINE_FLOOR = 0.50`:

* the English question **passes** the gate and retrieves the right text;
* the Hindi question scores **below the unrelated-sentence baseline** — it is noise, not a
  weak signal, and the gate correctly refuses it;
* the Hinglish question scores above noise but **still below the gate**, so it also refuses;
* the model does not even recognise the Hindi and Hinglish forms of one question as the same
  question (0.476).

**Three consequences.**

1. **Multilingual Research is an embedding-model problem, not a prompt or threshold
   problem.** No prompt wording and no reranker rescues a query whose true answer sits at
   0.037.
2. **Lowering `COSINE_FLOOR` would be the wrong fix and I am not proposing it.** At 0.30 the
   Hindi question is still out, the Hinglish one is only just in — and the refusal behaviour
   the English set was calibrated for (12/13 unanswerable questions refused) would be given
   away for it. The floor stays where it was measured.
3. **The statutes are English.** India Code's canonical texts are English, so this is
   *cross-lingual* retrieval — Hindi query against English corpus — which is a strictly
   harder task than monolingual Hindi and rules out the "just index Hindi text" shortcut.

**Recommendation.** Provision a multilingual model **for Domain C only**, keep MiniLM for
Domain B, and choose between them by `AM-26` r2's own rule — measured, smallest first.
Candidates worth measuring, all open-weight and self-hostable (`AM-26` compliant):
`multilingual-e5-small` (118M, 384-dim — same dimensionality as today, so the existing
pgvector column shape is unchanged), `paraphrase-multilingual-MiniLM-L12-v2` (118M, 384-dim),
`LaBSE` (471M, 768-dim — measure last; it is the largest and `AM-26` r2 forbids adopting it
if a smaller one passes).

Two things make this cheap rather than structural: `embedding_models` is already a registry
keyed by name+version+dimensions with every vector carrying an FK to its model row, and
`AM-32` gives Domain C its **own** `statute_chunk_embeddings` table. A second model is
therefore *representable today* with no schema change and no effect on Domain B's vectors.

**What it needs from the owner:** (a) approval to provision a second embedding model — it is
a new model, and `AM-26` r2/r5 make model selection a measured, recorded act rather than an
engineering preference; (b) **a Hindi/Hinglish evaluation set**, which cannot be manufactured
here. `AM-32` r9 already requires Domain A/C questions in the Tier-2 set before either domain
ships; this is that requirement with a language column. Twenty to thirty real questions per
language, each with the Act and section that answers it, is enough to calibrate.

**Hinglish specifically is the weakest case and should be scoped honestly.** Romanized Hindi
is under-represented in every multilingual model's training data (they are trained on
Devanagari), so expect it to measure worse than Hindi even on a multilingual model. The
transliteration route (romanized → Devanagari before embedding) needs a new dependency and is
a **rule 19** decision; it is not worth requesting until measurement shows the multilingual
model alone is insufficient. Until then, Hinglish is a *stated limitation*, not a silent one —
and the honest refusal is already the system's behaviour, which is the right failure.

---

## 3 · The headline query is a lookup, and should never touch a model

The product vision's recurring example is *"What does Section 138 of the NI Act say?"*. That
is not a semantic search — it names its answer's address. `AM-32` r7 already makes statute
chunking **section-based** and citations **Act + section**, which means the address is a
column, not an inference.

**Recommendation: resolve a cited section deterministically, before retrieval.** A question
carrying an Act reference and a section number gets the section's own text, cited, with no
embedding, no generation and nothing to verify — the same class of answer as a table lookup.
Semantic retrieval handles everything else.

Why this matters more than it looks:

* it is the **one query the vision promises**, and making it depend on a similarity score is
  how a demo becomes a coin-flip;
* it is **language-independent** — "धारा 138" and "Section 138" resolve to the same row, so
  the largest Hindi/Hinglish use case works before the multilingual model does;
* it removes the main case a reranker would have been bought for (§4);
* it is deterministic, so it is explainable in the sense rule 12 means, not the sense a
  retrieval score means.

The existing lexical branch does not cover this: `websearch_to_tsquery` ANDs every term
(measured 1/64 on human-phrased contract questions), and a section reference needs an exact
structured match, not a text search.

---

## 4 · Reranking — not yet, and here is the measurement that would justify it

Nothing reranks today. A cross-encoder reranker is permitted (`AM-26`: local, open-weight)
and is the standard next move after hybrid retrieval, but on this corpus it is a solution
without a measured problem yet:

* Domain B measured **0.938 top-10 recall** for the expected clause. A reranker improves
  *ordering* within retrieved candidates; recall is what refusals hinge on, and it is
  already high.
* [calibration.py](../../backend/legalmind/assist/calibration.py) records what the gate
  cannot separate — topically-near misses — and assigns them to citation verification, not
  to a score. A reranker is a scorer; it would inherit exactly that limitation.
* §3 removes the strongest concrete case for one.

**Recommendation: build the pipeline without a reranker, and add one only when a Domain C
eval run shows the answering section retrieved but ranked outside the evidence window.** That
is a measurable condition, and until it is measured a reranker is a second model to
provision, pin, checksum and explain.

---

## 5 · Refusal thresholds must be recalibrated for statutes, never inherited

`COSINE_FLOOR`, `EVIDENCE_COSINE_FLOOR` and `PEAK_MARGIN` were calibrated on **contract**
text against a **contract** question set. Statutes differ in every way that moves a
similarity distribution: longer sections, formal drafting, dense internal cross-references,
heavy vocabulary repetition across sections of one Act, and — unlike a contract — many
sections that are *near-duplicates* of each other in wording.

The last property is the dangerous one: `PEAK_MARGIN` (top cosine minus the mean of the rest)
assumes the right chunk stands out from the field. In a statute where twelve sub-sections
share a drafting formula, a *correct* top hit may show a flat profile and be refused.

**Recommendation.** Domain C carries its **own** constants, named per domain, calibrated by
the existing `tools/benchmark_retrieval.py --eval` procedure on a Domain C eval set — and
Domain B's numbers are not touched by that work. This is the same separation the E1 audit
already applied when it split `COSINE_FLOOR` from `EVIDENCE_COSINE_FLOOR`: one number
answering two questions is how a threshold silently becomes wrong for one of them.

**Blocked on:** the Domain C eval set (§2), which `AM-32` r9 requires anyway.

---

## 6 · Citation verification — reused unchanged, plus one statute-specific check

`guardrails.verify_answer` checks each claim's marker against the chunk it cites by
content-word overlap, mechanically and outside the model (`AM-25` r5, `AM-28` r2 — it must
not import prompt or model code). Statute text is text; the check applies as-is and **should
not be modified for this domain**.

One addition is warranted, and it is deterministic rather than statistical: an answer citing
"Section 138 of the NI Act" must resolve to a **statute chunk whose Act and section are those
values** in the registry. That is a join, not a judgment, and it closes the failure mode
where a model cites a real-looking section that the retrieved chunk is not.

`AM-29` r3's three outcomes stay three: *nothing retrieved*, *evidence insufficient — model
never called*, *answered but verification failed*. Different causes, different remedies,
recorded separately, and per `AM-29` r4 all reading identically to the user.

---

## 7 · Prompt injection — where the untrusted input actually is

For Domain C the corpus is **government-published statute text**, so the classic
"malicious instruction hidden in an uploaded document" vector is weaker here than it is for
Domain B. The untrusted input is the **question**.

The current prompt places rules first and the question last, instructs evidence-only
answering, and requires the literal `NOT FOUND` when the excerpts do not answer. The
substantive defences are already mechanical and outside the model, which is the only kind
that survives a prompt injection:

| Defence | Where | Why an injection cannot get past it |
|---|---|---|
| Citation verification | `guardrails.verify_answer` | An un-cited or unsupported claim is dropped whatever the model was told |
| Evidence-only payload | `service.py` | The model sees the retrieved chunks and the question — never a document, never a tool, never the database |
| Egress payload screen | `generation._forbidden_payload_check` | Standards, thresholds and rule outcomes cannot leave, whatever a prompt asks for |
| Refusal wording is fixed | `state.REFUSAL_TEXT` | A refusal cannot be talked into disclosing why it refused |
| No write path | the lane produces no Finding, Evaluation or Decision | The worst outcome of a successful injection is a *wrong answer that fails verification*, not a state change |

**Recommendation: one hardening, no weakening.** Delimit the question explicitly in the
prompt (an untrusted-input fence) and re-state the evidence-only rule *after* it, so the last
instruction the model reads is ours and not the user's. That is a prompt-version bump
(`PROMPT_VERSION`, pinned per answer), measurable against the eval set, and it changes no
guardrail. **Do not** add an "injection classifier" — it would be a model judging a model,
with no citation to verify and a new false-positive path into a refusal.

---

## 8 · Conversational shape — multi-turn without an ungrounded rewrite

The tables already support conversation and messages, and Ask already renders turns. The
genuinely new question is the follow-up: *"and what is the punishment?"* means nothing
without the previous turn.

Two ways to resolve it:

| | How | Cost |
|---|---|---|
| **(a) Carry the context in the question** | the client sends the resolved question; prior turns stay visible so the reader sees what was asked | No new machinery, nothing new to verify |
| (b) Model-side query rewriting | a generation call turns "and the punishment?" into a standalone query | A second generation call whose output is a *retrieval query* — ungrounded, uncitable, unverifiable, and a new way to silently change what was asked |

**Recommendation: (a) for v1.** Option (b) adds a failure mode with no guardrail available:
citation verification checks an *answer* against evidence and has nothing to say about a
rewritten *question*. If measurement later shows follow-ups failing often enough to matter,
(b) can be revisited with the rewritten query shown to the user — a rewrite the reader can
see is a rewrite the reader can correct.

On the UX itself: the conversational surface should read like the product's existing Ask
(question, cited answer, honest refusal), not like a general assistant. Three things it must
not borrow from consumer chat, all of them house rules rather than taste — no confidence
percentage or "I think" hedging (rule 12, and a retrieval score is never rendered as legal
confidence, `AM-29`); no answer without a citation; and no answer to *"is this acceptable?"*,
which routes to the evaluator (`AM-25` r4, already enforced by `_is_compliance_question`).

---

## 9 · What blocks Domain C, and who unblocks it

| # | Blocker | Whose | State |
|---|---|---|---|
| 1 | Statute material with India Code provenance — NI Act absent, Evidence Act absent | **Owner** (rule 21) | C-16 open; [STATUTE_INTAKE.md](STATUTE_INTAKE.md) §1 lists it exactly |
| 2 | Evidence Act 1872 vs Bharatiya Sakshya Adhiniyam 2023 (or both, each with its in-force window) | **Owner** | C-16; open. Verified 2026-09-04 — the seven statutes on disk are unchanged, and neither of these is among them |
| 3 | Provenance confirmation for the seven statutes already supplied (vision §9.2 makes India Code canonical "as a hard rule") | **Owner** | Open |
| 4 | A Domain C evaluation set, including Hindi and Hinglish questions | **Owner** (`AM-32` r9) | Not started |
| 5 | Approval to provision a multilingual embedding model for Domain C | **Owner** (`AM-26` r2/r5) | Not requested until #4 exists — without an eval set there is nothing to measure it with |
| 6 | The curated judgment list (the reserved sixth table stays unauthorized without it) | **Owner** | Open; not needed for statutes |

Until #1 and #2 land, the honest state of the screen is the one it already shows: a disclosed
placeholder that says why it is empty and offers nothing interactive. That is unchanged by
this document.

**Build order once unblocked** — each step verifiable before the next: statute ingestion with
provenance-or-refuse → section-based chunking → the deterministic Act+section resolver (§3,
useful before any embedding exists) → multilingual embedding measurement (§2) → Domain C
threshold calibration (§5) → generation with the statute citation check (§6) → the
conversational surface (§8).

---

## 10 · Recorded so it cannot be mistaken for a decision

This document proposes; it locks nothing. Two of its recommendations touch material the
standing instruction protects, and both are *"leave it alone"*: the Domain B thresholds stay
exactly as calibrated (§2, §5), and no guardrail is weakened (§6, §7). The one prompt change
suggested (§7) is additive, version-pinned and measurable.

Nothing here derives a Requirement, threshold or acceptance position from a statute. A
statute remains background law — cited in an explanation, never loaded as configuration, and
never admitted to the evaluator (`AM-32` r7, and CLAUDE.md's standing rule).

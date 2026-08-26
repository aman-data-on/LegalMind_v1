# LegalMind — where the project stands

**Status: 📁 DERIVED — written in plain language for the project owner.** Last updated
**26 August 2026**.

> This document explains things, it doesn't decide them. Every number in it comes from
> [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), which is the only document allowed to state
> what has actually been built. If the two ever disagree, that one is right.
>
> No knowledge of the software is needed to read this page.

---

## Picking up where we left off

*The short version, kept current so a new session can answer "where are we?" immediately.
Updated at the end of every working session.*

| | |
|---|---|
| **Last worked** | 26 August 2026 |
| **Current phase** | `PHASE 5–7 DELIVERED — ASK YOUR DOCUMENTS` · working end to end; Gemini answers wait on one action from you |
| **Health** | 893 backend + 62 frontend checks passing, none failing |
| **Waiting on you** | **Two external actions**: Google's written no-training terms, and a Gemini API key (details in *What I'll need from you*) |
| **Next step once they arrive** | Record the confirmation, open the gate, switch generated answers on |

**What got finished on 26 August**

- **The search model was chosen by measurement, not opinion** — four candidates were
  scored against your ratified 77 questions on the real documents; the smallest one
  that passed won, exactly as our rule requires.
- **The "not found" cut-off was derived from the measurements**, not picked: a simple
  cut-off proved insufficient, so the rule also requires the best match to stand out
  from the field. Result: 12 of 13 unanswerable questions correctly refused.
- **Asking questions works end to end.** On the contract page you can now ask about an
  uploaded document; answers cite the clause and page, every score is labelled a
  "retrieval score" (never confidence), and a refusal reads as a calm "not found".
- **The safety checks went in before the AI**: every sentence of an answer must cite
  its source, and the citation must actually support the claim — checked by code, not
  by the model. Fabricated answers are blocked and the user sees "not found".
- **Gemini is wired but the gate is closed**: nothing real can reach Google until you
  confirm their written no-training terms. That gate cannot be opened by a setting —
  only by a recorded decision.


- **The full test-question set was drafted from your actual documents** — 77 questions
  across the contracts, the policies and the seven statutes, each verified against the
  real text, including 13 questions deliberately designed to have no answer. It's ready
  for your review; nothing has been calibrated against it yet, by design.

**What got finished on 25 August**

- Recorded your Gemini decision as a formal amendment, and finished landing the earlier
  AI amendment across the five documents that were supposed to reflect it but didn't.
- Built the separate storage area for the search index, kept apart from the legal data.
- **Search over uploaded contracts now works** — by phrase, exact wording, or clause
  number, with no AI involved.
- Found and fixed a real problem: contracts were being cut into page-sized pieces instead
  of clause-sized ones, so nothing could cite "§17.2". Now 88% of pieces carry a clause
  number.
- Measured four candidate search models on your real documents — and found that all of
  them lose the ability to say "not found", which is why the model choice is paused.

**Two corrections I owe you from that session**, both cases where I told you something and
then measured it and found I was wrong:

- I said the database search add-on had to be upgraded before we could proceed. **It
  didn't** — I tested the version we have and it works correctly.
- I said the model-running software was about 50MB. **It's 118MB** — I'd forgotten a
  component it depends on. The choice was still right; the number wasn't.

---

## The goal

LegalMind is an internal legal workspace where **every answer shows you where it came from.** Ask it
something and it either points at the exact document, page and clause it found the answer in, or it
tells you plainly that it doesn't know. It never guesses.

It does two different jobs, and keeping them separate is the whole design:

| The job | Who answers | Why it matters |
|---|---|---|
| **"Does this contract match our approved position?"** | The **rules engine** — fixed, repeatable logic. Never the AI | A legal verdict has to be defensible. Same contract in, same verdict out, every time, with the reasoning shown |
| **"What does this document say about X?"** · "What does this statute say?" | The **AI assistant**, but only from text it has actually retrieved | This is reading and explaining, not judging |

The AI never decides whether something is acceptable. It reads, finds, summarises and explains. The
verdict always comes from the rules engine.

---

## What already works

This is a real, working system — not a prototype.

* **The legal rules engine works.** It compares a contract against our approved positions and
  produces a verdict, with the reasoning traceable back to the exact clause it read.
* **862 automated checks pass**, none failing. These run every time anything changes, so a change
  that would break existing behaviour gets caught.
* **Our approved legal positions are already loaded** — **32 of them**, covering our MSA, Terms of
  Service, NDA and SLA. Every one was taken from a real LeapSwitch document and records which clause
  it came from. **This work is done and does not need redoing.**
* **Our position on deviations is settled and built in.** Anything that differs from our approved
  position goes to a human for a decision. Nothing that differs is ever waved through automatically.
* **Reading documents works.** PDFs and Word files, including scanned ones, and it keeps the page
  number and the exact position of every piece of text — which is what makes "show me where you got
  that" possible.
* **Security works.** Every request is checked on the server. Someone who guesses another
  customer's reference number gets the same "not found" they'd get for something that doesn't exist,
  so they can't even confirm it exists.
* **Nothing is invented.** If the system can't extract enough to judge something, it says so rather
  than guessing. That behaviour is deliberate and tested.
* **Nothing currently leaves our servers.** Not one part of the system makes an internet call today, and an automated check now fails the build if that ever changes without it being a deliberate, recorded decision.
* **Searching an uploaded contract works** — by phrase, exact wording, or clause number, with no AI involved. See the current phase below.

---

## What we're building now

The **AI assistant** part: asking questions about an uploaded document, and searching our approved
positions and the statutes, always with a citation.

**Right now we are on the foundations**, not the AI itself. Two safety nets went in first:

1. A check that **fails the build if any part of the system starts making internet calls** without
   that being a deliberate, recorded decision. Today the answer must be zero — so the day the AI
   connection is added, it shows up as an obvious change nobody can miss.
2. A check that **fails the build if the shape of our legal database changes**. The rule says the AI
   work must not touch the existing legal data at all; this makes that a fact rather than a promise.

We also found and fixed a gap: **about 250 of our automated checks were running but their results
were being thrown away**, so a genuine failure could have gone unnoticed. They are now enforced.

---

## What's left

In the order it has to happen — each step needs the one before it:

1. **Storage and database groundwork** for the AI's search index, kept completely separate from the
   legal data.
2. **Plain search** over uploaded documents — find exact phrases and clause numbers. *Useful on its
   own, with no AI involved at all.*
3. **Smarter search** that understands wording, not just exact words. Runs on our own servers.
4. **The safety checks** that verify every claim in an AI answer against the source before anyone
   sees it — **built before the AI is connected**, so an unchecked answer is impossible rather than
   just discouraged.
5. **Connecting Gemini** for writing the answers, with strict limits on what gets sent.
6. **The single screen** where the document, the verdicts and the chat all live together.
7. **Our approved positions and the statutes** made searchable. *Waiting on two things — see below.*
8. **Security hardening and final sign-off.**

---

## Current phase

### `PHASE 4 — SMARTER SEARCH` · measured, waiting on your test questions

You approved the software to run search models, so I installed it and **measured four
candidates** on your real documents. Two results, and the second is the important one.

**Result 1 — smarter search does help, but only in combination.** Used on its own it is
much *worse* than what we have at finding exact wording. Combined with ordinary search it
finds the right clause in the top ten **every single time** (up from 92%), and the best
candidate matches ordinary search's first-try accuracy while ranking better overall. So
the combination is worth having.

**Result 2 — and this one changes the plan.** Every single smarter-search option **lost the
ability to say "not found"**. Ordinary search correctly refused 34 of 36 questions it had
no answer to. Every smarter option refused **none of them** — it answered all 36.

That isn't a bug in one model; it's how this kind of search works. It finds the *closest*
match, and there is always a closest match, however unrelated. A ranking isn't a filter.

Since "no answer without a source" is the core promise of this product, that means smarter
search **cannot be switched on** until we add a cut-off: a minimum closeness below which
the answer is "not found". And that cut-off is a number I must not invent — it has to be
measured against questions we know the documents don't answer.

**Which is the same thing I already need from you.** Your test questions now unblock two
decisions rather than one: which model to use, and where to set the cut-off. I've
deliberately not chosen either.

**Nothing has been switched on.** No model is in use, the storage for it hasn't been
created, and its size hasn't been fixed — all of that waits for the measurement.

### Completed

| Phase | What it was |
|---|---|
| **Phase 0 — Review of what we already have** | Went through the existing system to see what could be kept. Answer: **almost all of it.** About two-thirds usable as-is, the rest needs adjusting, and essentially **nothing needs throwing away.** |
| **Phase 1 — Foundations and record-keeping** | Made the written record match reality, recorded your Gemini decision properly as a formal amendment, and put two safety nets in **before** any AI work: one fails the build if any part of the system starts making internet calls without that being deliberate, the other fails the build if the shape of the legal database changes. Also fixed a gap where about 250 automated checks were running but their results were being thrown away. |
| **Phase 2 — Database groundwork** | Built the separate storage area for the search index, kept completely apart from the legal data. Eight of nine planned tables done; the ninth waits on choosing a search model, because its shape depends on which one we pick. |
| **Phase 3 — Search over uploaded documents** | Upload a contract and search it — by phrase, exact wording, or clause number — with no AI involved. Working and measured. |

### Coming next

| Phase | What it is |
|---|---|
| Phase 5 | Answer safety checks |
| Phase 6 | Gemini connected |
| Phase 7 | The single workspace screen |
| Phase 8 | Approved positions and statutes made searchable |
| Phase 9 | Security hardening and sign-off |

---

## Blockers

Only genuine ones.

| # | What's blocked | Why | Blocks what |
|---|---|---|---|
| 1 | Sending **real customer contracts** to Google | Google's written promise not to train on our data hasn't been confirmed yet. Until it is, only test documents can be sent | Nothing yet. It stops us **finishing** the AI part, not starting it |
| 2 | Making the **statutes** searchable | Two of the laws the plan refers to were never sent to us, and the ones we have didn't come from the official government source | Phase 8 only |
| 3 | Single sign-on ("RIAAS") | We don't have the technical details of how to connect to it. Normal login works fine meanwhile | Nothing. It can be added at any point |
| 4 | A restricted database account for the AI side | Creating it needs administrator access the application deliberately doesn't have. Ordinary server admin work, not a decision | Nothing yet |
| 5 | **Your review of the drafted test questions** | On your instruction I drafted the full set myself — 77 questions over the contracts, policies and statutes, every one verified against the actual documents, including 13 designed to have no answer. Per our own rules a result only counts once you've ratified the set, and your review is the safeguard against me marking my own homework | **Choosing the search model, and setting the "not found" cut-off.** Review `backend/tests/assist_eval/questions_draft.json` — approve it, edit it, or replace any question |
| ~~6~~ | ~~Permission to add the software that runs a search model~~ | **Resolved 25 Aug** — approved and installed. Measured at 118MB, not the ~50MB I estimated when asking; I was wrong about the number, though not about the choice | — |

**A correction to something I told you earlier.** I previously said the database search add-on
must be version 0.8 or newer before we could proceed. **I tested it, and that was overstated.**
The version we have works correctly — it checks permissions *before* searching, exactly as
required, with no results missed. The newer version only matters later, for searching across
thousands of documents at once rather than within one. So this is no longer a blocker, and I have
not weakened the permission rule to get around it.

---

## Decisions needed from you

**Two, and both are blocking the same thing: choosing the search model.** I have deliberately
not chosen one, because the rule we set says it must be chosen by measurement, and I can't
measure the thing that matters without these.

### 1. Real test questions, so the choice is measured rather than guessed

**What I need:** roughly 30–50 questions a lawyer or analyst would genuinely ask about our own
MSA, Terms of Service, NDA and SLA — the documents you already sent me — each with a note of
which clause answers it. Plus, importantly, **about 10 questions the documents genuinely do
not answer**, so I can check the system correctly says "not found" instead of guessing.

**Why I can't do this myself:** I can generate questions automatically *from* a document, and I
have — that's how the numbers above were produced. But those questions reuse the document's own
wording, which is precisely what a smarter model is *not* needed for. To show a smarter model is
worth its cost, the questions have to be phrased differently from the document. If I write those
myself I'd be choosing both the exam and the answers, and any result would be meaningless.

**Format:** anything readable — a spreadsheet, a Word document, or plain text. One line per
question is fine: *the question · which document · which clause number answers it*. For the
unanswerable ones, just the question and a note that it isn't covered.

**What it measures:** whether a search model finds the right clause when the question doesn't
share the document's words — and whether it correctly refuses when there's no answer. Getting
the refusal right counts for half the score, by our own rule.

### 2. Permission to add the software that runs a search model

**What I need:** a yes or no to adding two components — `onnxruntime` and `tokenizers`.

**Why I'm asking rather than deciding:** you already approved *having* a self-hosted search
model. But our rules require your approval for each new software component, and I applied that
same rule to the Gemini connection, so applying it selectively here would be inconsistent.

**My recommendation: yes, and specifically these two.** They total roughly 50MB, run on an
ordinary server with no graphics card, and can *only* run a model — they cannot train one. The
common alternative (`torch`) is about 2.5GB and includes a full training toolkit we've
explicitly ruled out having. All eight candidate models publish versions that work with the
lighter option, so we give nothing up.

**What happens if you say no:** the search stays as it is today — which genuinely works, as the
measurements above show. It just won't understand rephrased questions.

## What I'll need from you, and when

**Two actions are now genuinely due — everything else is built and waiting behind them.**

### 1. Google's written data terms — the gate-opener

- **What:** written confirmation that our Gemini usage tier does **not** train on
  submitted content, and its data-retention terms. On the paid Gemini API tier Google
  publishes this in their terms; for Vertex AI it's part of the enterprise terms. What
  we need recorded: **which tier, and the date you confirmed it.**
- **Where:** your Google account/billing setup — this is a commercial confirmation only
  you can make on the company's behalf.
- **Why I can't do it:** it's a vendor-terms acceptance, and our own locked rule says
  the gate opens only by a recorded decision naming provider, tier and date.
- **What I do the moment you provide it:** append the release record, open the gate in
  the same change, and real documents can then get generated answers.

### 2. A Gemini API key

- **What:** one API key for the chosen tier.
- **Where it goes:** the server's environment as `LEGALMIND_GEMINI_API_KEY` — never in
  a file in the repository, never in a document. I'll never ask you to paste it in chat;
  set it on the server or hand it to whoever operates it.
- **Until then:** everything except the final generated sentence works — search,
  citations, refusals — and I've tested the generation path against a stand-in.

### Later (not yet due)

| What | When | Why |
|---|---|---|
| NI Act and Evidence Act, plus statute provenance confirmation | Statute-search phase | Never authored by us; the two Acts were never supplied |
| The curated judgment list | Statute-search phase | The plan says the legal team picks it |
| Production server actions | Deployment | pgvector install, the restricted `legalmind_assist` database account, network egress allow-list — root-level server steps, listed in the preflight report |

**On legal material generally:** we never write it ourselves. If something is missing, we ask.

## Two things worth knowing

**The AI will never be the judge.** Your instruction and the project's own rules agree here, and it's
built in structurally, not just intended: the AI cannot write to the legal records at all. It can
explain a verdict the rules engine reached. It cannot change one, and it cannot produce one.

**We won't say "87% confident".** A percentage next to a legal statement looks like precision and
isn't. Instead an answer says what it found and shows the source, or says clearly that it found
nothing. The project rules forbid the percentage, and that's the right call.

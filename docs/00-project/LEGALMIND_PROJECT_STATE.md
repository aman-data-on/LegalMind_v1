# LegalMind — where the project stands

**Status: 📁 DERIVED — written in plain language for the project owner.** Last updated
**27 August 2026**.

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
| **Last worked** | 27 August 2026 (status re-verified 30 August; no code changed since) |
| **Current phase** | **GAP-CLOSING + UI/UX PHASE STARTED** (your later instruction, 27 Aug, which also authorized UI/UX in parallel) · everything closable without your inputs is closed; the two real gates (C-15 approval, Gemini terms) each now have a ready-to-approve document |
| **AM-32 (AB-5)** | ✅ **Approved and built, 27 Aug** — the positions/statute search tables exist and C-15 is resolved. *(This row previously still asked for the approval; corrected 30 Aug — rule 23, never re-ask a decided thing.)* One question stays open in [STATUTE_INTAKE.md](STATUTE_INTAKE.md): the Evidence Act 1872 was repealed by the Bharatiya Sakshya Adhiniyam 2023 — which do you want indexed? |
| **UI/UX** | **ROADMAP DELIVERED, AWAITING YOUR REVIEW** (your think-first directive, 27 Aug evening): [../design/PRODUCT_UX_ROADMAP.md](../design/PRODUCT_UX_ROADMAP.md) — who uses what, the app's structure, every screen with a priority, what admin actually needs, what stays a placeholder, and the build order (document pane + click-to-highlight first, login deliberately fifth). It adopts the earlier [../design/WORKSPACE_UI_PLAN.md](../design/WORKSPACE_UI_PLAN.md) three-pane workspace and flags one decision for you: bundling the chosen fonts needs your approval (no runtime Google-Fonts calls from a confidential tool — system fonts meanwhile). **Broad implementation waits for your go on the roadmap** |
| **The freeze report (morning 27 Aug)** | [BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md) — the completed/blocked/operator-only breakdown and the verified API contract; superseded the same day by your gap-closing directive, but its contract verification stands |
| **Health** | 935 backend + 79 frontend + 30 browser checks passing, none failing; CI (15 jobs — now including visual regression and the forbidden-wording gate) green on every push |
| **Waiting on you** | Google's written no-training terms and a Gemini API key (details in *What I'll need from you*); the statute material and a C-15 ruling for the positions/statute search; or your go-ahead to start UI/UX |
| **Next step once an input arrives** | Resume exactly that thread — the mapping from each input to its work is the last section of [BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md) |
| **Your instruction, 27 Aug** | *"Backend freeze / dependency-wait state... VERIFY → DOCUMENT → FREEZE → PREPARE HANDOFF → WAIT FOR OWNER INPUT. Do not manufacture additional coding work. Do not start UI/UX."* Done and logged — the handoff report is written, everything re-verified, no code changed, and nothing starts without your explicit word |
| **Your instruction, 26 Aug** | *"Keep the Gemini production gate CLOSED until I provide the required Google terms confirmation. Continue with any safe remaining work."* Logged. The gate was already closed by default — this changes no code, and nothing further will touch it until you provide that confirmation |
| **Your instruction, 26 Aug (later)** | *"Backend first. UI/UX later. Preserve the existing UI code but treat its previous design as obsolete for planning purposes... When the backend/API architecture is genuinely ready to support a new UI/UX implementation, stop and tell me clearly."* Logged. The current screens stay in place and their tests keep running, but no further design or polish work goes into them. The backend is being closed out against the surfaces a new UI will need; the readiness call comes as an explicit statement, with the owner-gated items named |

**What got finished on 27 August (evening — your UI/UX execution directive)**

- **The interface got its first hardening pass for real users.** Loading placeholders now
  hold each page's shape while data arrives (no content jumping); the review screen is
  fully workable from the keyboard — `n`/`p` walk the findings, `?` shows a help panel —
  and the approve/reject keys deliberately only *prepare* a decision: no single keystroke
  can ever record one, and an automated browser test proves it.
- **The two-people-collide case is now airtight on screen.** If someone else decides
  first, the form says plainly "Not recorded", freezes, and stays frozen until you
  explicitly load the latest state — nothing refreshes itself under your eyes mid-read.
- **Two new automatic design gates run on every change**: one fails the build if any
  forbidden wording ("confidence", "risk score"…) enters the interface — tested by
  planting a violation and watching it fail — and one compares five key screens
  pixel-by-pixel against approved reference images, so a visual regression can't slip
  through unnoticed.
- **Usability testing is ready to schedule**: a five-person test plan (two kinds of user,
  four tasks, checklist and feedback form) is written — I need you to name participants
  when you want it run. Two patterns a newcomer would mistake for bugs (hidden
  confidential fields; the identical "not found" reply) are now documented with real
  screenshots so nobody "fixes" a security property.

**What got finished on 27 August (afternoon — your gap-closing directive)**

- **The C-15 decision is ready for you in one read** — the AB-5 proposal drafts the
  exact amendment text: six new tables so positions and statutes become searchable,
  each domain kept separate as you instructed. One catch it bakes in: our own egress
  rule forbids sending approved-position values to Google, so positions answers will
  always be exact quotes of the ratified text — never AI-written.
- **Gemini is now turnkey on your side**: a step-by-step runbook (choose tier → confirm
  written terms → key → verify), and a verification tool that tests the connection with
  inert synthetic text before anything real is trusted to it. The gate stays closed.
- **The statute request is now precise**: what to download from India Code, what
  provenance each file must arrive with — and one question only you can answer (the
  Evidence Act was replaced by a new law in 2023; which one do you want?).
- **Production operations got a real runbook** (`ops/README.md`), every step mapped to
  the automated readiness register, which also gained its one missing row (the network
  egress allow-list).
- **The new UI phase started on your authorization**: the workspace design is planned
  and documented, the design skills were applied (three of their generic suggestions
  were rejected where our own recorded design decisions win — reported, not hidden),
  and the first component is built and tested. Checks: 911 backend + 68 frontend, all
  green.

**What got finished on 27 August (morning)**

- **The backend was formally frozen and the handoff written**, on your instruction. No code
  changed. Every check was re-run first — 901 backend, 62 frontend, 27 browser, lint, types,
  and the contract-drift check — all green. (One environmental fix on this machine only: the
  browser the test suite drives had to be reinstalled after a version bump; no project code
  involved.)
- **[BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md)** now records, in one place: what
  is genuinely complete; what waits on a decision from you (C-15 above all); what waits on
  material from you (Google terms, API key, the two statutes); what is operator-only
  production work; the verified API contract a new interface designs against; and which
  screens can be designed now versus which must stay placeholders.
- **The two statuses are kept deliberately separate**: the API surface is stable enough to
  begin UI/UX — but the product is *not* complete, and the report never claims it is.
  UI/UX remains **deferred until you explicitly authorize it**.

**What got finished on 26 August**

- **The backend's "front door" is finished and frozen for the new interface.** Per your
  "backend first" instruction, I checked every screen a new workspace interface would need
  against what the server actually offers, and closed the four gaps: a list of a document's
  past conversations; conversations that **keep their citations when reopened** (before,
  reloading lost them); the document's extracted text with page numbers and positions, so a
  viewer can show and highlight exactly where an answer came from; and a simple "is this
  document searchable yet" indicator. The complete server contract is now saved as a single
  file the interface work designs against, and an automatic check fails if code and contract
  ever drift apart. The current screens are untouched and still pass their tests — they just
  won't receive any more design work.
- **A serious hidden breakage was found and fixed.** The main Review screen — the one
  where findings are read and decisions recorded — had been failing to load for every user
  since 24 August. It was a one-line ordering mistake introduced by a code-review fix that
  day; the kind of error the automatic type checks cannot see and only a real browser can.
  Nobody saw it because the automated browser tests **never ran**: they were configured to
  run only on the main branch, and five days of work went onto a side branch. Fixed, all 27
  browser checks now pass, and the automated checks now run on every push to any branch so
  this cannot hide again.
- **A second hidden breakage in the test tooling, same root cause of "never ran".** The
  day the search-index table was added, every tool that builds a fresh test database
  stopped working (the database add-on the index needs wasn't being installed in fresh
  databases). Fixed in the tooling; production behaviour untouched.
- **The quality bar is now a command, not a promise.** Before any future change to the
  search, the chunking, or the model ships, one command re-runs all 77 of your ratified
  test questions through the real product and **refuses to pass if the system starts
  answering questions it should refuse**. The current, measured bar is recorded in the
  repository; I proved the check can actually fail before trusting it. The half of the
  bar that scores the AI's written answers stays honestly marked "not yet measurable" —
  it needs the Gemini gate open, and our rules forbid faking it with synthetic results.
- **One number worth knowing from that measurement**: end-to-end, the system currently
  finds the right clause for about 44% of fairly-worded questions and refuses 12 of 13
  trick questions. The strict refusal rule is what costs the recall — by design, text
  that scores below the evidence bar is never shown, even when it happens to be right.
  Loosening that trade-off, if we ever want to, now has a safe path: change, re-measure,
  compare against the recorded bar.
- **The development/staging blueprint now enforces the network rules.** The parts of the
  system that touch documents (parsing, indexing, the search model) run on an internal
  network with **no route to the internet at all** — they couldn't send a document out
  even if code tried. Only one component keeps an outbound route: the one that will talk
  to Gemini, which still refuses in production while the gate is closed.
- **Security hardening (Phase 9) started**: two new automated checks run on every change —
  one scans our code's dependencies for known vulnerabilities (backend and frontend, both
  currently clean), the other scans the built application images the same way. **The image
  scan earned its keep on its very first run**: it caught a known high-severity flaw in a
  system library the base image ships (a fix was already published, the base image just
  hadn't been rebuilt yet). Both images now pull in the latest security fixes when they're
  built. Its second catch was in the web-frontend image: nine flaws, all inside the
  package-installer tooling the base image bundles — none in our own code or libraries.
  Rather than chase versions, the running image now carries no installer tooling at all;
  it needs only the runtime to serve pages. Two further scan tools from the plan need a
  running copy of the whole system to point at, so they stay a deployment-time step rather
  than a per-change check.

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
* **894 backend + 62 frontend automated checks pass**, none failing. These run every time
  anything changes, so a change that would break existing behaviour gets caught — and as of
  26 August that includes a check on every dependency and every built application image for
  known security vulnerabilities.
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

The **AI assistant** part is built and working — asking questions about an uploaded document,
with every answer citing its source or plainly saying it doesn't know. What's left is making
our approved positions and the statutes searchable the same way, and finishing hardening.
Neither touches the AI-assistant code that's already shipped.

---

## What's left

In the order it has to happen — each step needs the one before it. **1–6 are done**; only 7
and 8 remain.

1. ~~Storage and database groundwork for the AI's search index, kept completely separate from
   the legal data.~~ **Done.**
2. ~~Plain search over uploaded documents — find exact phrases and clause numbers, no AI
   involved.~~ **Done.**
3. ~~Smarter search that understands wording, not just exact words. Runs on our own
   servers.~~ **Done** — model chosen by measurement against your ratified test questions.
4. ~~The safety checks that verify every claim in an AI answer against the source before
   anyone sees it, built before the AI was connected.~~ **Done.**
5. ~~Connecting Gemini for writing the answers, with strict limits on what gets sent.~~
   **Done** — wired and gated; the gate itself waits on you, see *Blockers*.
6. ~~The single screen where the document, the verdicts and the chat all live together.~~
   **Done.**
7. **Our approved positions and the statutes** made searchable. *Blocked — see below.*
8. **Security hardening and final sign-off.** *In progress — dependency and image scanning
   done 26 August; network segmentation, the restricted database account, and the two
   live-instance scan tools remain.*

---

## Current phase

### `PHASE 9 — SECURITY HARDENING` · in progress, not gated on Gemini

Everything through the workspace (phases 0–7) is delivered and working — see *Completed*
below. What's left before final sign-off is hardening and the two statute/positions items
in Phase 8, and neither needs the Gemini gate open.

**What's done in Phase 9 so far**: every code change is now automatically checked for
known security vulnerabilities in two ways — one checks the libraries our own code depends
on (backend and frontend both currently clean, nothing found), the other checks the actual
application images the same way once they're built. Both run on every change from now on,
the same way the existing correctness checks do. The development/staging blueprint also
now puts everything that touches documents on an internal network with no internet route,
so the "documents never leave" rule is enforced by the network itself, not just by code.
And the quality bar became a runnable pre-release check: any future change to the search
must re-pass your 77 ratified questions against the recorded bar before it ships.

**What's deliberately not automated yet, and why**: the hardening plan also calls for two
tools that test a *running* copy of the application from the outside, the way an attacker
would — rather than reading the code. Wiring those into the automatic checks would mean
building a small working copy of the whole system (database, backend, frontend, all
running together) inside the check pipeline itself, which is a much bigger piece of
infrastructure than the two checks above. That's deployment-pipeline work, done once there's
a staging copy of the system to point it at, not something to add to the automatic
per-change checks unilaterally.

Remaining in Phase 9: locking down the network path between services, and a restricted
database account for the AI side (both server-admin actions, not decisions — see
*Blockers*).

### Completed

| Phase | What it was |
|---|---|
| **Phase 0 — Review of what we already have** | Went through the existing system to see what could be kept. Answer: **almost all of it.** About two-thirds usable as-is, the rest needs adjusting, and essentially **nothing needs throwing away.** |
| **Phase 1 — Foundations and record-keeping** | Made the written record match reality, recorded your Gemini decision properly as a formal amendment, and put two safety nets in **before** any AI work: one fails the build if any part of the system starts making internet calls without that being deliberate, the other fails the build if the shape of the legal database changes. Also fixed a gap where about 250 automated checks were running but their results were being thrown away. |
| **Phase 2 — Database groundwork** | Built the separate storage area for the search index, kept completely apart from the legal data. |
| **Phase 3 — Search over uploaded documents** | Upload a contract and search it — by phrase, exact wording, or clause number — with no AI involved. Working and measured. |
| **Phase 4 — Smarter search** | Measured four candidate search models against your ratified test questions on the real documents, and picked the smallest one that met the bar — never the one that merely scored highest. Combined with plain search, it finds the right clause in the top ten essentially every time. |
| **Phase 5 — Answer safety checks** | Built and working, **before** the AI was connected: every sentence of an answer must cite its source, and the citation must actually support the claim — checked by code, not by the model. A fabricated answer is blocked and the user sees "not found," never the fabrication. |
| **Phase 6 — Gemini connected** | Wired behind a single switch-point, with a hard gate that refuses to send anything to Google in production until you confirm their written no-training terms — a setting cannot open that gate, only a recorded decision can. |
| **Phase 7 — The single workspace screen** | On the contract page you can now ask about an uploaded document; answers cite the clause and page, every score is labelled a "retrieval score" (never confidence), and a refusal reads as a calm "not found." |

### Coming next

| Phase | What it is | State |
|---|---|---|
| Phase 8 | Approved positions and statutes made searchable | Blocked — see *Blockers* |
| Phase 9 | Security hardening and sign-off | **In progress** — dependency/image scanning done; network segmentation, restricted DB account, and the two live-instance scan tools remain |

---

## Blockers

Only genuine ones.

| # | What's blocked | Why | Blocks what |
|---|---|---|---|
| 1 | Sending **real customer contracts** to Google | Google's written promise not to train on our data hasn't been confirmed yet. Until it is, only test documents can be sent | Nothing yet. It stops us **finishing** the AI part, not starting it |
| 2 | Making the **statutes** searchable | Two of the laws the plan refers to were never sent to us, and the ones we have didn't come from the official government source | Phase 8 only |
| 3 | Single sign-on ("RIAAS") | We don't have the technical details of how to connect to it. Normal login works fine meanwhile | Nothing. It can be added at any point |
| 4 | A restricted database account for the AI side | Creating it needs administrator access the application deliberately doesn't have. Ordinary server admin work, not a decision | Nothing yet |
| ~~5~~ | ~~Your review of the drafted test questions~~ | **Resolved 26 Aug** — you directed the set be used as-is ("Use questions_draft.json as the current evaluation dataset. Do NOT ask me to recreate these questions."). That is your ratification; the set is marked RATIFIED and both the model choice and the cut-off were measured against it | — |
| ~~6~~ | ~~Permission to add the software that runs a search model~~ | **Resolved 25 Aug** — approved and installed. Measured at 118MB, not the ~50MB I estimated when asking; I was wrong about the number, though not about the choice | — |

**A correction to something I told you earlier.** I previously said the database search add-on
must be version 0.8 or newer before we could proceed. **I tested it, and that was overstated.**
The version we have works correctly — it checks permissions *before* searching, exactly as
required, with no results missed. The newer version only matters later, for searching across
thousands of documents at once rather than within one. So this is no longer a blocker, and I have
not weakened the permission rule to get around it.

---

## Decisions needed from you

**None open right now.** The two that stood here — supplying real test questions, and
approving the search-model software — were both resolved on 25–26 August (see the struck-through
rows 5 and 6 in *Blockers*). What's still waiting on you is external action, not a decision;
see the next section.

## What I'll need from you, and when

**Two actions are now genuinely due — everything else is built and waiting behind them.**
Unchanged since 25 August; your 26 August instruction to keep the gate closed until you
provide them has been logged and requires no new action from you.

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

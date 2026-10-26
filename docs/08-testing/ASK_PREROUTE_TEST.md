# Ask pre-router — enterprise conversation test

> ✅ **FIXED on branch, not deployed** — 2026-10-22 (`AM-200`). A test record, not a specification: it locks nothing
> and amends no decision. Runnable form:
> [backend/tests/assist/query/test_assist_preroute_followups.py](../../backend/tests/assist/query/test_assist_preroute_followups.py)
> — the same case IDs as §5.

## 1. Why this exists

On 2026-10-22 a sales user pasted a client's 16-point list into Ask, got an answer,
then asked twice:

> *can you fetch the above details & reframe the answer as per the cloudpe product ?*

Both times Ask replied with the fixed product brief (*"I review contracts you attach
against the organisation's ratified Company Standards…"*) in 4–7 ms, with no search
and no model call. The API log recorded the turn as `outcome: prerouted`, and the reply
text is the `brief` entry of `config/capability_manifest.json`.

The 25 existing capability tests were green throughout. Every one of them sends one
clean, well-formed message with no conversation around it.

## 2. The enterprise standard the cases test against

| # | Practice | Source |
|---|---|---|
| E1 | **Resolve a follow-up against the conversation before routing it.** "the above", "it", "this", "same", "point 9" are read with the recent turns. | [LazyLLM conversational RAG](https://lazyllm-from-data-to-llm-hcj.readthedocs.io/en/latest/Cookbook/rag_nloop/) · [AlgoMaster](https://algomaster.io/learn/ai-engineering/conversational-rag-exercise) · [SELF-multi-RAG, arXiv 2409.15515](https://arxiv.org/html/2409.15515v1) |
| E2 | **A fixed reply fires only when the router is sure.** When it is not, the turn falls through to the main path. | [Dialogflow intent matching](https://docs.cloud.google.com/dialogflow/docs/intents-matching) · [confidence thresholds](https://insertchat.com/glossary/confidence-threshold) |
| E3 | **Build the test set from real traffic.** Logged messages, and logged misroutes, are the cases. Readers are unsure, terse and misspell; they paste fragments and do not phrase things the way a test author does. | [NLU platform comparison, arXiv 2012.02640](https://arxiv.org/pdf/2012.02640) |
| E4 | **The same request in Hinglish routes the same way.** | LegalMind `AM-69`: language is not a safety boundary |
| E5 | **The control cases still hold.** A real "what can you do?" still gets the brief, and a real off-topic request is still declined. | `AM-68`, `AM-109` |

## 3. How real readers write — the production log (E3)

Every USER message in production on 2026-10-22: **36 messages from 7 users**.

| What the log shows | Examples (paraphrased where they carry client detail) |
|---|---|
| Spelling and grammar errors | "constomer can exist without give the notice" · "What it our policy in this case?" · "analysis this based on our consitution" · "please draft a email" |
| Terse follow-ups that lean on the conversation | "please draft a email" · "What it our policy in this case?" · "please reply let me know is this acceptable or not ?" |
| Pasted fragments with a short lead-in | "Client query for termination - …" · "Client has share terms for renewal - …" · "(c) confirm response and resolution times;" |
| One long paste, then point-by-point re-asking | One reader re-asked a 16-point list as 13 separate messages, one point each |
| Language | English and Roman Hinglish only. **No Devanagari in any message**, so Hindi-script cases are dropped from this test. |

**Replay.** All 36 were run back through `service.preroute`, each in its real context:
earlier turns, attachment and contract. **2 of 36 got a fixed reply, both wrongly.**
Both were the CloudPe follow-up (§1). The other 34 reached the model. The pre-router
misfires rarely on today's traffic, but when it does, the reader cannot get past it by
asking again.

## 4. Method

* Every case goes through `service.preroute`, the shipped pre-router that the agent
  path calls first (`agent.py`, P8). A probe mirrors its screens in order (social →
  off-scope → capability → authority → needs-document → clarify → unclear) to name the
  screen that fired, and checks each result against the real function.
* **Zero Gemini calls**, because every screen tested is deterministic.
* The messages are written the way §3's readers write: lower case, missing
  punctuation, "u", "pls", "4", fragments, Roman Hinglish. Client names are removed.
* Contexts:

| Context | has_prior | has_document | has_material | prior_offer | Meaning |
|---|---|---|---|---|---|
| `FIRST` | no | no | no | no | the first message of a new chat |
| `MID` | yes | no | yes | yes | the §1 chat: an answer given, the reader's paste in it, the last answer ending on an offer |

* "Expected `MODEL`" means the message must reach the answer path, whatever the model
  then does with it.
* Run against `main` at `b3a4d44`, which is what production runs.

## 5. Results — 29 cases, 19 FAIL

| ID | Category | Ctx | Message | Expected | Got | Result |
|---|---|---|---|---|---|---|
| F1 | Follow-up on the answer above | MID | can you fetch the above details & reframe the answer as per the cloudpe product ? *(live, verbatim)* | MODEL | CAPABILITY | ❌ |
| F2 | Follow-up on the answer above | MID | can you do same for cloudpe | MODEL | CAPABILITY | ❌ |
| F3 | Follow-up on the answer above | MID | can you give me same answer but for cloudpe product | MODEL | CAPABILITY | ❌ |
| F4 | Follow-up on the answer above | MID | client asking same for cloudpe can you check | MODEL | CAPABILITY | ❌ |
| O1 | Taking up Ask's own offer | MID | can u also ans point 9 n 10 | MODEL | MODEL | ✅ *(luck — R-5)* |
| O2 | Taking up Ask's own offer | MID | ok can you do that | MODEL | CAPABILITY | ❌ |
| T1 | Task on the answer | MID | can you write mail to client for above | MODEL | CAPABILITY | ❌ |
| T2 | Task on the answer | MID | can you make it short | MODEL | CAPABILITY | ❌ |
| T3 | Task on the answer | MID | can you put this in table | MODEL | CAPABILITY | ❌ |
| T4 | Task on the answer | MID | please draft a email *(live, verbatim)* | MODEL | MODEL | ✅ |
| H1 | Hinglish (Roman) | MID | isko cloudpe ke hisab se kar sakte ho kya | MODEL | MODEL | ✅ *(luck — R-5)* |
| H2 | Hinglish (Roman) | MID | aap ye cloudpe ke liye bana sakte ho | MODEL | CAPABILITY | ❌ |
| H3 | Hinglish (Roman) | MID | tum isme kya help kar sakte ho | MODEL | CAPABILITY | ❌ |
| H4 | Hinglish (Roman) | MID | same cheez cloudpe ke liye batao | MODEL | MODEL | ✅ |
| S1 | Greeting or thanks + task | MID | ok thanks can you do for cloudpe also | MODEL | CAPABILITY | ❌ |
| S2 | Greeting or thanks + task | MID | hi can you check point 15 again | MODEL | CAPABILITY | ❌ |
| U1 | Unsure / vague reader | MID | not sure what to tell client can you help | MODEL | CAPABILITY | ❌ |
| U2 | Unsure / vague reader | MID | can you help | MODEL | CAPABILITY | ❌ |
| U3 | Unsure / vague reader | MID | what can you do with this | MODEL | CAPABILITY | ❌ |
| R1 | Shorthand / caps | MID | CAN YOU REFRAME FOR CLOUDPE | MODEL | CAPABILITY | ❌ |
| R2 | Shorthand / caps | MID | can you pls do it 4 cloudpe | MODEL | CAPABILITY | ❌ |
| C1 | Control: real "what can you do" | FIRST | what can you do | fixed | CAPABILITY | ✅ |
| C2 | Control: real "what can you do" | FIRST | legalmind kya kar sakta hai | fixed | CAPABILITY | ✅ |
| C3 | Control: real "what can you do" | FIRST | how can you help me | fixed | CAPABILITY | ✅ |
| C4 | Control: real "what can you do" | FIRST | who are you | fixed | SOCIAL: IDENTITY | ✅ |
| C5 | Control: real "what can you do" | FIRST | what are you capable of | fixed | MODEL | ❌ |
| X1 | Control: off-topic | MID | tell me a joke | fixed | OFF_SCOPE | ✅ |
| X2 | Control: off-topic | FIRST | whats the weather in pune today | fixed | OFF_SCOPE | ✅ |
| X3 | Control: off-topic | FIRST | write me a python script | fixed | MODEL | ❌ |

| Category | Cases | Fail |
|---|---|---|
| Follow-up on the answer above | 4 | **4** |
| Taking up Ask's own offer | 2 | 1 |
| Task on the answer | 4 | 3 |
| Hinglish (Roman) | 4 | 2 |
| Greeting or thanks + task | 2 | **2** |
| Unsure / vague reader | 3 | **3** |
| Shorthand / caps | 2 | **2** |
| Control: real "what can you do" | 5 | 1 |
| Control: off-topic | 3 | 1 |
| **Total** | **29** | **19** |

## 6. Why they failed

### R-1 · The capability screen reads the message alone (17 of the 19)

Failing cases: F1–F4 · O2 · T1–T3 · H2 · H3 · S1 · S2 · U1–U3 · R1 · R2.

`intent.is_capability_question` (`backend/legalmind/assist/query/intent.py`) returns
True when three things hold:

1. a self word: `you`, `aap`, `tum`, …
2. a capability word: `can`, `could`, `do`, `help`, `kar`, `sakte`, `kya`, …
3. **no legal anchor stem**: `clause`, `contract`, `liabilit`, `cap`, …

Almost every request a reader makes to an assistant starts "can you…", so the first two
legs hold for nearly any request. The third leg only knows legal vocabulary. "cloudpe",
"same", "mail", "table", "short", "reframe" and "point 15" are not legal stems, so the
message is read as "what can the product do?".

`service.preroute` already knows the conversation is under way (`has_prior`,
`has_material`, `prior_offer`), but it never passes that to the capability screen. The
screen runs before the context-aware screens and returns first. This breaches **E1**.

### R-2 · An unsure reader gets the brochure (U1–U3)

Real readers are often unsure: "not sure what to tell client can you help". With the
reader's paste and an answer already in the chat, the industry pattern sends this to
the main path, or asks one clarifying question about that material. Ask sends the
product brief, which tells an unsure reader nothing about their own case. This breaches
**E2**.

### R-3 · The greeting is stripped, then capability fires (S1, S2)

`conversational.strip_social` removes "ok thanks" and "hi", and the remainder goes to
the same capability screen as R-1. "ok thanks …" is how most follow-ups open.

### R-4 · Hinglish fails the same way (H2, H3)

`aap`, `tum`, `kar`, `sakte` and `kya` are capability or self words, so a Hinglish
*task* is caught exactly like the English one. This breaches **E4**.

### R-5 · Messy text passes by accident, not by design (O1, H1)

O1 passed only because "u" is not in the self-word list; with "you" it would fail. H1
passed only because the reader wrote no `aap` or `tum`. The screen happens to do better
on worse spelling, so the pass rate depends on how carefully the reader types.

### R-6 · Prefix matching on the legal anchor (C5)

`_hits` matches anchor *stems* by prefix, and `"cap"` (the liability cap) is a prefix of
**"capable"**. So "what are you capable of" is treated as a legal question and goes to
retrieval. That is the defect `AM-68` was written to remove.

### R-7 · The off-topic list does not cover general tasks (X3)

"write me a python script" has no off-topic word, so it reaches the model and spends a
Gemini call. That leaves the model to decline it. Low severity: it costs money, not a
wrong answer.

### R-8 · Why the existing suite never caught it (E3)

`test_assist_capability_route.py` sends 15 clean single messages with no conversation,
no paste and no misspelling. None of them is from the production log. The suite never
tests a message that depends on the conversation, so 25 green tests said nothing about
this reader's path.

## 7. Also in the §1 conversation (not part of the 29)

These come from the stored answer and the `assist.agent.turn` log line.

| # | What happened | Evidence |
|---|---|---|
| A1 | Points 9 (Term) and 10 (Termination) were not answered, and the reply offered a follow-up. Taking up that offer with "can you also…" hits R-1 (compare O1 and O2). | log `flags: points:14/16`, `dropped: 17` |
| A2 | Point 8 reads *"In the company's reading of the law, Conditioning billing commencement…"*. The sentence is about our standard terms, not a law, so the label does not belong there. The capital "C" stays because `_decap` lowers only known lead words. | `agent_verify.attribute_readings` / `_decap` |
| A3 | 72 s for the first answer: 32 s building context and 29 s searching per point. | log `stages_ms` |
| A4 | Elsewhere in the log, one reader re-asked a 16-point list one point per message, 13 messages in all. That is consistent with long-list answers not being trusted to be complete. | §3 |

## 8. The fix — `AM-200` (AB-120)

Owner instruction, 2026-10-22: change any locked decision that stands between Ask and
the enterprise standard. Built on branch `fix/ask-capability-followup-20261022`.

| Change | Answers |
|---|---|
| The pre-router's capability screen runs only on an **empty chat** (no earlier turn, no material, no document) | R-1 to R-5, E1 |
| On an empty chat it fires only when **nothing but product words is left** (self words, capability words and a closed filler list removed), so a first message that is a task is not caught either | R-1, E2 |
| In a conversation the **model** reads the message with the conversation and calls the new agent tool `show_capabilities` when it really is a product question; the reply is the manifest **rendered by code**, never generated (`AM-68` r3 kept). The forced first step still searches (the tool is never offered there), the tool counts only as its step's one call, and `LEGALMIND_CAPABILITY_ROUTE=off` turns it off with the fixed route (code review, 2026-10-22) | E1, E2 |
| "cap" is a legal anchor **as a word** (cap, caps, capped), not as a prefix | R-6 |
| X3 ("write me a python script") is left to the model, which declines it; a longer fixed-word list would refuse "the code of conduct clause" | R-7 |

Amends `AM-68` r1/r2 and `AM-118` r2 (record AB-120 in `all_lock.md`).

### After — the same cases, re-run

| Set | Before | After |
|---|---|---|
| §5 cases, plus M1 "what else can you do" mid-conversation (expected: model) | 19 of 29 fail | **0 of 30 fail** |
| §3 production log, each message in its real context | 2 of 36 misrouted | **0 of 36** |
| `tests/assist`, no models (CI's shape) and with the local models | — | passed (see CHANGELOG) |

X3's expectation changed from "fixed reply" to "reaches the model", as §8 states.

**Not measured:** how often Gemini actually picks `show_capabilities` on a real
"what else can you do?". The tool path is tested with a scripted model. Measuring it live
costs Gemini calls, so per the cost guard it is one confirmation run, done after the
owner's commit.

## 9. Next

* The wider programme this test started is [ENTERPRISE_READINESS_PLAN.md](../architecture/ask-agent/ENTERPRISE_READINESS_PLAN.md) (T18 there).

* E3: as the production log grows, replay it on every Ask change, with each message in
  its real context.
* Runnable test: `pytest backend/tests/assist/query/test_assist_preroute_followups.py`
  (all pass), and
  `tests/assist/agent/test_assist_agent.py::test_the_model_choosing_show_capabilities_replies_with_the_rendered_brief`.

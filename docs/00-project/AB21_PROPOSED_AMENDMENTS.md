# AB-21 — APPROVED 2026-09-15, superseded by the lock records

✅ **APPROVED by the owner on 2026-09-15** and appended to
[all_lock.md](../../all_lock.md) as `AM-67`, `AM-68` and `AM-69` (lines 19073–19261;
the prior 19072 are byte-identical, verified by checksum). The registry entries are in
[LOCKED_DECISIONS.md](LOCKED_DECISIONS.md).

**This file is now a working record of how the drafts were reached, not the decision.**
The locked text is in `all_lock.md` and wins on any divergence. One substantive change
between draft and lock: the owner chose **option (b)** for `AM-68` — the manifest is
rendered directly with **no generation call** — so the locked r3 does not amend `AM-25`
r5 at all, where the draft had proposed to.

---

## `AM-69` — Language is not a safety boundary

**Proposed first, because it is the only one that describes a defect already in production.**

*Would clarify:* `AM-25` r4, `AM-25` r5, `AM-28` r2. *Would amend:* nothing — it states what
those records already mean. *Does not amend:* `AM-30`, `AM-32`, `AM-45`, `AM-46`.

### Why this record exists

`AM-25` r4 and r5 are written without reference to language. The implementation was not.
Measured live 2026-09-15 against the shipped code:

```
is_comparison_question("हमारे मानक से तुलना करें")            -> False   (tokenized to [])
is_verdict_statement("Yeh clause Company Standard ke
                      according nahi hai.")                  -> False
verify_answer("यह क्लॉज हमारे मानक के अनुसार है और देयता की
               सीमा पचास लाख रुपये है [1]", [english_chunk])  -> ANSWERED
```

The third is the serious one. `guardrails._content_words` matches `[A-Za-z]` and digits, so a
Devanagari sentence produced an empty content-word set, and the overlap expression read
`... if claim_words else 1.0` — admitting the claim unconditionally. A fabricated liability
figure and a compliance verdict both passed, while the English equivalent was rejected.

Every example in the owner's own brief is Hinglish.

```
r1  A GUARANTEE WORDED AS UNIVERSAL IS UNIVERSAL. AM-25 r4 and r5, AM-28 r2 and every
    mechanical screen they require apply identically whatever language or script a
    question or an answer is written in. Language is not a scope limit on a safety
    guarantee, and a screen enforced in one language only does not satisfy them.

r2  A SCREEN THAT CANNOT EVALUATE AN INPUT FAILS CLOSED. Where a mechanical check
    cannot read a claim — an unsupported script, an empty comparable set, any input it
    has no basis to judge — the outcome is REFUSAL, never a default that admits it.
    AM-25 r5's "enforcement is mechanical and sits outside the model" is not satisfied
    by a check that returns "grounded" for what it did not read.

r3  THE REMEDY IS A CHECK THAT CAN READ IT. r2 is a floor, not a destination: refusing
    every question in a language the product is used in is a defect of its own. Where a
    language is supported, its screens are extended to cover it, and the test matrix
    runs BOTH directions in that language — a screen widened until it fires on
    everything has moved the defect, not fixed it.

r4  NO NEW STATE, NO NEW VOCABULARY. A claim refused under r2 is CLAIM_UNSUPPORTED,
    already AM-29 r3's third outcome. No fifth assist-lane state is added.

r5  THIS RECORD RELAXES NOTHING. It records that the guarantees were already stronger
    than the code, and that the code was brought up to them.
```

**Implemented ahead of approval on `fix/language-safety-screens` (`d3b9985`), on the
owner's explicit "hotfix immediately, separately" instruction of 2026-09-15.** The code
restores guarantees the locks already assert and relaxes nothing, which is why it was not
held for this record; the record exists to say so. **It is not merged or deployed.**

---

## `AM-67` — Domain A as a controlled reading aid

*Would amend:* `AM-32` r4; `AM-30` t3 for Company Standard clause text only; `AM-30` t2 to
admit position spans. *Does not amend:* `AM-30` t1, t4–t10; `AM-25` r1–r4, r6–r9; `AM-32` r1,
r3, r5–r10; `AM-45` r2; LEGAL-02 as a display rule.

Synthesis and source authority are compatible when synthesis is confined to a reading aid:
the quote stays, the synthesis sits beside it, and authority is preserved structurally
rather than by trusting the model.

```
r1  ONLY PUBLISHED, RATIFIED COMPANY STANDARD TEXT. The source_quote and citation fields
    of a published company_standard_version may enter a generation payload. Nothing else
    from the configuration lane: no Legal Rule, no legal_rule.configuration, no threshold
    key, no Rule Outcome, no Evaluation, no Finding, no Mapping State, no classification.
    AM-30 t3 stands in full for every one of those.

r2  DRAFTS NEVER. AM-32 r3 unchanged: only published, ratified versions are chunked, so
    only published text can be retrieved and therefore sent.

r3  THE ORIGINAL QUOTE IS THE SOURCE OF TRUTH AND STAYS VISIBLE, UNCHANGED. A synthesis
    never replaces, edits, paraphrases over, truncates or reorders the ratified text. The
    verbatim quote is rendered with its citation BESIDE the synthesis, always, in its own
    field (AM-45 r2, AM-32 r1). A response carrying a synthesis without its quote is a
    defect.

r4  SYNTHESIS CREATES NO LEGAL RULE AND NO LEGAL OUTCOME. It never creates, modifies,
    extends, narrows or restates-as-new any legal rule or company position, and never
    produces MATCH, DEVIATION, MISSING, CONFLICT, an approval, or an acceptability
    decision. AM-25 r1/r3/r4 and Step 38 rule 21 are reaffirmed, not weakened.

r5  THE EXISTING GUARDRAILS APPLY UNCHANGED. Citation verification and the verdict screen
    run on every synthesized sentence exactly as they run on a document answer. AM-25 r5
    holds in full.

r6  THE FORBIDDEN-PAYLOAD SCREEN IS NARROWED, NOT REMOVED.
    generation._forbidden_payload_check keeps refusing every key it refuses today.

r7  AM-30 t4 STANDS. No counterparty name, signatory, contract or user identifier.

r8  FAIL CLOSED TO THE QUOTE. If generation is unavailable or the guardrail rejects the
    synthesis, the response is the verbatim quote and its citation alone — today's
    behaviour. A rejected synthesis never degrades the answer below what ships now.
```

⚠️ **r7 has a hard prerequisite that is now met in code but not in the corpus.** Eight
ratified standards carry a counterparty note and 24 an env-var path inside
`source_document`, composed into the chunk text. Egressing those would breach t4 and t5 on
the first call. The sanitizer landed in `f5fc324`, **but the corpus has not been
re-chunked**, so this term cannot be enabled until it is.

---

## `AM-68` — The capability question shape

*Would amend:* `AM-45` r1; `AM-25` r5 (naming the manifest as the evidence set); `AM-46` r1.
*Does not amend:* `AM-25` r1–r4, r6–r9; `AM-30` t3/t4; `AM-32`.

A product-help surface that shares an input box with Ask — never a second way into legal
content.

```
r1  DETERMINISTIC DETECTION. The capability shape is decided by a deterministic
    classifier; no model decides whether a question is a capability question. The
    decision is recorded on the retrieval run like every other routing decision.

r2  ZERO RETRIEVAL, OF ANY KIND. No retrieval over documents, Constitution positions,
    statutes, Findings, Evaluations or Reviews. Not primary, not fallback, not "just to
    check". The route reaches no legal corpus at all.

r3  THE MANIFEST IS THE ONLY EVIDENCE. Generated ONLY over a fixed capability manifest
    held in the repository. The manifest IS the retrieved evidence set, so AM-25 r5 is
    satisfied in its own terms rather than relaxed: every sentence cites a manifest entry
    and passes the same mechanical guardrail.

r4  IMPLEMENTED AND TESTED FEATURES ONLY. Each entry names behaviour that is built and
    covered by a test. No future, planned, roadmap, partial or speculative capability —
    rule 7's discipline: an invented capability is as bad as an invented legal rule.
    Changing the manifest is a configuration change needing owner approval.

r5  CONSTRAINED WORDING ONLY. The model's permitted contribution is phrasing over the
    manifest. It adds no capability, no qualifier of legal effect, and no example drawn
    from anything but the manifest.

r6  DETERMINISTIC FALLBACK. If generation is unavailable or the guardrail rejects the
    answer, the response is the manifest rendered plainly — never a guess, never a
    refusal, never a legal answer.

r7  NEVER A LEGAL-ANSWER ROUTE. States no legal position (AM-25 r3), produces no Finding
    or classification (r1), answers no question about a document or a standard, and
    confers no authority (r8, SEC-01/SEC-02). A question genuinely about legal content is
    NOT a capability question, and the classifier's negative matrix pins that boundary.

r8  AM-46 STILL HOLDS. Its own candidate set, deterministic in the question's shape and
    dependent on no object's existence — not an existence oracle.
```

### Evidence bearing on the generate-vs-render choice (measured 2026-09-15)

The capability route was built dark on `feat/capability-route` (flag
`LEGALMIND_CAPABILITY_ROUTE`, **off**; 23 tests). Building it surfaced a fact the owner
should have before choosing r5's generated wording over r6's deterministic rendering:

**`intent.is_verdict_statement` fires on the rendered manifest.** The two entries that
trip it are `c3`, which names the product's own classification vocabulary ("a match, a
deviation, missing, a conflict"), and `L1` — the **disclaimer**: *"I do not decide
whether a document is acceptable, approve it, or advise whether to sign."* The sentence
that makes the answer safe is the one flagged as a verdict.

That is not a defect in the screen. It asks "does this text state how a DOCUMENT stands
against the organisation's position?" and answers on whole text by design (`AM-28` r2). A
static manifest names the vocabulary without applying it to anything — a case it was
never built to judge.

Two consequences:

* r7's guarantee for this route is **structural, not screened** — zero retrieval plus
  owner-approved static evidence means it cannot state a position about any document.
  Pinned by the zero-retrieval and import-boundary tests, not by the verdict screen.
* **A generated capability answer would very likely be rejected by that same screen and
  fall back every time.** So r5's generation would, in practice, often deliver r6's
  output anyway — while adding an egress call and a failure mode.

This is real evidence for the deterministic option. It does not decide the question: a
rendered manifest still reads as a feature list rather than an answer, which is the
original argument for generating. **Recorded, not resolved.**

---

## `AM-70` — A multilingual embedding model *(deferred, not yet proposed for decision)*

*Would amend:* `AM-26` r4's model pin. **Consequence: a full re-embed of every corpus and a
re-baseline of the 77-question evaluation set.**

Measured: Devanagari scores 0.037 cosine against the answering English text — below the
0.100 unrelated-English baseline — and romanized Hindi without English legal nouns scores
0.138, against a 0.50 gate. Hinglish clears the gate only because it carries English legal
nouns, and does so by as little as 0.009.

**Not put forward for decision yet.** Phase 4 first measures whether a reranker — the one
untried lever, and no lock change — closes enough of the gap. Raising the model pin before
that would be tuning ahead of evidence.

---

# `AM-71` (PROPOSED, NOT APPROVED) — The general-knowledge answer type

📁 **PROPOSAL.** Nothing appended to `all_lock.md`, no approval recorded, and the
feature is off: `LEGALMIND_GENERAL_KNOWLEDGE` is unset and nothing reads it.

*Would amend:* `AM-25` r5, narrowly. *Would not amend:* `AM-25` r1–r4, r6–r9;
`AM-30` t3/t4; `AM-32`; `AM-45`; `AM-46`.

## The exact conflict

`AM-25` r5, verbatim:

> No answer reaches a user unless every claim in it resolves to retrieved evidence.
> Enforcement is mechanical and sits outside the model. Where evidence is insufficient,
> the response is an explicit statement that the information was not found.

"What is an NDA?" has an answer, and it resolves to **no retrieved evidence** — no
authorised source holds the definition of a non-disclosure agreement. Generating one is
precisely what r5 forbids. The conflict is real and not a matter of interpretation.

## What shipped WITHOUT the amendment, because it needs none

The question is now **recognised and searched nowhere**. Before, it fell through to the
unconditional POSITIONS fallback and came back as three Company Standards — measured
live 2026-09-16, "What is an NDA?" returned `NON-SOLICIT-NDA-001`, `GOVLAW-NDA-001` and
`RESIDUALS-NDA-001`, presenting the organization's positions as though they defined the
term. That was the defect, and not searching is always safe.

The reader is told what this system answers from and what to ask instead. That is r5's
own remedy — "an explicit statement that the information was not found" — phrased as a
redirect rather than a dead end.

## What the amendment would add

```
r1   A GENERAL-KNOWLEDGE ANSWER IS NOT A LEGAL POSITION AND IS LABELLED AS ONE THING
     IT IS NOT. It is rendered in its own field, visually and structurally separate
     from any Company Standard or document citation, and carries a standing statement
     that it is not the organization's position. AM-25 r3 is unchanged: it states no
     organizational legal position, because it states none at all.

r2   NO DOCUMENT AND NO STANDARD IN THE PAYLOAD. The route performs zero retrieval,
     so the payload carries the question and the prompt template and nothing else.
     AM-30 t3 and t4 stand untouched — there is no clause, position, Finding,
     counterparty or identifier to send.

r3   NEVER A VERDICT, NEVER ADVICE. `intent.is_verdict_statement` runs on the output
     unchanged, and the prompt forbids applying the explanation to any document the
     user holds. "What is an NDA" may be answered; "is my NDA any good" may not.

r4   THE SCOPE IS DEFINITIONAL. Only a question whose every content word is a legal
     concept qualifies — the classifier excludes possessives, deictics, statute
     references and compound terms, so "what is OUR notice period" and "what is THE
     termination notice period" keep their existing routes. The owner's 2026-09-09
     ruling that the second is answered from the ratified positions is unaffected.

r5   FAIL CLOSED TO THE REDIRECT. If generation is unavailable or the screens reject
     the output, the response is the non-generated redirect that ships today. The
     amendment can only add an explanation; it can never remove the safe answer.

r6   AM-25 r5 IS NARROWED, NOT SET ASIDE. Every OTHER answer — document, position,
     statute, comparison — still requires every claim to resolve to retrieved
     evidence. The exception is this one answer type, which retrieves nothing by
     design and is labelled as carrying no authority.
```

## Recommendation

Worth approving, but it is genuinely optional. The shipped behaviour already removes the
defect: no reader is now handed Company Standards as the definition of a legal term. The
amendment buys a better answer to a question the product is not obliged to answer, at the
cost of one narrow exception to the guarantee that makes the rest of the lane
trustworthy. **Declining it is a reasonable position**, and the system is coherent either
way.

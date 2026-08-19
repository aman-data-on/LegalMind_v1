# Source material intake — first tranche, 2026-08-18

**Status: 📁 ANALYSIS.** This document decides nothing, locks nothing and specifies
nothing. It records what the supplied documents do and do not contain, measured against
[HANDOFF.md](../../HANDOFF.md) §6.1, and states exactly what is still required.

> ⚠️ **No legal value in this document is a LegalMind configuration value.** Every figure
> quoted below is quoted *from* a supplied document, attributed to it, and is recorded as
> an observation about that document — never as the organization's Company Standard,
> Legal Rule, threshold or expected fixture output. Nothing here has been inferred,
> averaged, reconciled or promoted. Rules 7 and 21 both apply.

**Thirteen fixtures were authored from this tranche across two owner instructions of
2026-08-18.** The second — §3.4's V1 interim policy — made the supplied documents
authoritative for the positions they explicitly state, which unblocked `MATCH` and
`DEVIATION`. **No acceptance policy was written, and none exists.** §3 explains what makes those nine
authorable and why the rest are not: an expected output that depends on what the
organization will *accept* is a legal conclusion only the owner can state, while an
expected output that follows from the clause text plus the locked fail-closed
specification does not depend on any acceptance position at all.

---

## 1 · What was supplied

Six documents, received 2026-08-18. All six are documents **Leapswitch issues**, in which
Leapswitch is the drafter and the party whose liability is limited.

| | Document | Date | Form | Executed |
|---|---|---|---|---|
| D1 | CloudPe Terms of Service (`cloudpe.com/terms/`) | 5 Feb 2026 | published web page, printed to PDF | n/a |
| D2 | Leapswitch Networks Terms of Service (`leapswitch.com/terms-of-service.php`) | 26 Feb 2026 | published web page, printed to PDF | n/a |
| D3 | CloudPe Service Level Agreement | eff. 1 Oct 2024 | published web page, printed to PDF | n/a |
| D4 | Leapswitch Service Level Agreement (dedicated server) | undated | published web page, printed to PDF | n/a |
| D5 | Non-Disclosure Agreement, one counterparty | 17 Jun 2026 | drafted agreement | **yes — real counterparty** |
| D6 | Leapswitch Master Services Agreement, Version 2 | Jul 2025 | **unexecuted template**, blanks unfilled | no |

D5's counterparty, its signatories and their titles are deliberately **not named in this
repository**. See §5.

---

## 2 · Coverage against HANDOFF.md §6.1

| # | Required | Status | |
|---|---|---|---|
| 1 | Representative contracts | **PARTIAL** | six documents, but all Leapswitch-issued — see §2.1 and §5 |
| 2 | `LIABILITY-001` Company Standard | **NOT SUPPLIED** | no document states what Leapswitch will *accept* — §2.2 |
| 3 | `LIABILITY-001` Legal Rule | **NOT SUPPLIED** | no acceptable maximum, no approval threshold, no `UNLIMITED` treatment — §2.3 |
| 4 | Extraction terminology | **SUBSTANTIALLY SUPPLIED** | real, quotable, provenance-traceable — §4 |
| 5 | Requirement applicability | **NOT SUPPLIED** | no Requirement catalogue accompanies the tranche |

Two of five items are met. Items 2, 3 and 5 are not partially met — they are absent, and
they are the two that gate every `NORMATIVE` fixture.

### 2.1 · The documents are the right *kind* of paper, facing the wrong way

Locked [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) line 9: LegalMind *"compares a selected
**counterparty** contract against those standards."*

All six documents are Leapswitch's own. Two consequences, both structural rather than
fixable by supplying more of the same:

* **As specimen counterparty paper they work.** D2 and D6 are exactly the kind of vendor
  agreement an organization receives: professionally drafted, with a real aggregate
  liability cap, real carve-outs, indemnity, force majeure and precedence language. For a
  *customer of Leapswitch*, D6 **is** the counterparty contract. As raw input text they
  are genuinely useful, and §4 and §6 show how much.
* **A corpus drawn only from your own outbound paper cannot exercise the deviation
  paths.** Leapswitch wrote these documents to express Leapswitch's own preferred
  position. Measured against Leapswitch's own Company Standard they would tend to
  classify `MATCH` almost everywhere — while `DEVIATION`, `APPROVAL_REQUIRED` and
  `UNACCEPTABLE` are what most of the 45E table exists to test. Fixtures L-02, L-03,
  L-04, L-08 and W-01 all require paper that *departs* from the standard.

This is an observation, not a decision. **Which direction LegalMind reviews in V1 is
yours to confirm**, and it changes what item 2 even means:

* reviewing **inbound counterparty paper** → the Company Standard is what Leapswitch
  demands of vendors, and none of these six documents contains it;
* reviewing **Leapswitch's own negotiated contracts for drift from its template** → the
  Company Standard is closer to D6's template position, and D6 becomes directly relevant.

I have not assumed either. Locked Step 8 and the Glossary read naturally as the first.

### 2.2 · Why item 2 is absent, and the trap in it

A Company Standard is *"the organization's own standard position for a Requirement"*
([GLOSSARY.md](GLOSSARY.md):33) — what the organization **wants**. Every liability
provision in this tranche is instead a limit Leapswitch **grants itself as vendor**:

> D6 §17.2 — "the total aggregate liability **of Leapswitch** and its affiliates … shall
> not exceed the total amount actually paid by the Customer to Leapswitch for the specific
> Services giving rise to the claim during the six (6) month period immediately preceding
> the event giving rise to such liability."

> D2 §13 — "**LEAPSWITCH'S** TOTAL AGGREGATE LIABILITY TO YOU … SHALL NOT EXCEED THE
> TOTAL FEES PAID BY YOU TO LEAPSWITCH DURING THE TWELVE (12) MONTHS IMMEDIATELY
> PRECEDING THE EVENT GIVING RISE TO THE CLAIM."

**The trap, stated plainly because it is easy to fall into.** The specification's
worked examples use a six-month cap illustratively, and D6 §17.2 contains a six-month
cap. It would take one unexamined step to "confirm" the illustrative six-month figure
from D6 and call item 2 satisfied. That step inverts the direction of the limit — it
would turn *the most Leapswitch will pay out* into *the most Leapswitch will accept from
a vendor*, and record it as the organization's ratified legal position. CLAUDE.md is
explicit that the six-month example is an illustration, not a position.

**I have not taken that step, and nothing in the repository has.** Item 2 requires you to
state the value.

### 2.3 · Item 3 is absent entirely

No supplied document contains an acceptable maximum, a value above which approval is
required, or any treatment of unlimited liability *received*. These are internal policy
statements; outbound customer-facing paper has no reason to contain them, and none does.

Carve-out **terminology** is present and real (§4.4). Which carve-out scopes are
*comparable* remains a Legal Rule configuration decision.

---

## 3 · What was authorable, and the line that divides it

A golden-corpus fixture is a pair: input text, and the exact expected output — per 45E.1
both the scoped Evaluation set **and** the derived Finding summary.

The dividing line is not "real document or not". It is **whether the expected output
depends on an acceptance position**:

* **It does not** for the fail-closed, conflict and absence paths. *"Two clauses of this
  agreement cap the same scope differently, so with no configured precedence the engine
  reports `CONFLICT` and retains both evidence references"* is fixed by the clause text
  and locked 45C.2 together. No preferred value, tolerance or threshold is involved, so
  none has to be assumed. **Nine such fixtures were authored** — see §3.1.
* **It does** for `MATCH`, `DEVIATION`-by-comparison and every Rule Outcome other than
  `NOT_APPLICABLE`. 45E.2 expects L-01 (6-month cap) → `MATCH` and L-02 (12-month cap) →
  `DEVIATION`/`ACCEPTABLE`; whether 6 months matches depends entirely on `preferred`, and
  whether 12 months is acceptable depends entirely on `acceptable_max`. Writing either
  would invent the organization's legal position — worse under ENG-12, since the corpus is
  Tier 1 and an invented expectation would bind every later change.

### 3.1 · The nine authored fixtures

Provenance `DOCUMENT_SUPPORTED`, each citing its source document and clause
(`backend/tests/corpus/document_liability.json`). Each was confirmed to reach its
*intended* branch, not merely to pass:

| Fixture | Source | Asserts |
|---|---|---|
| `DOC-LIAB-01` | MSA 17.2 | a real finite cap with no Company Standard published → `UNABLE_TO_EVALUATE` (45C.5) |
| `DOC-LIAB-02` | ToS 13 | every comparability gate passes, no `preferred` → `UNABLE_TO_EVALUATE`. **This is the fixture that shows exactly what is blocked** |
| `DOC-LIAB-03` | MSA 17.7 | the unfilled period → `UNABLE_TO_EVALUATE`, never a guess at the number (45C.19) |
| `DOC-LIAB-04` | MSA 17.2 + 17.7 | same scope, incompatible → `CONFLICT`, both evidence refs retained; 17.2's "Notwithstanding anything to the contrary" detected and **not applied** (45C.2, 45C.27) |
| `DOC-LIAB-05` | ToS 13 + its three carve-outs | four Evaluations, never one flattened position; the whole provision is **not** `UNLIMITED` because a carve-out is (45C.3, 45C.4) |
| `DOC-LIAB-06` | MSA 17.2 vs 17.7's basis | two bases in one agreement, no configured conversion → `UNABLE_TO_EVALUATE` (45B.4, 45C.23) |
| `DOC-LIAB-07` | MSA 17.2 + 17.3 | carve-out splitting in a second, independently drafted provision |
| `DOC-LIAB-08` | CloudPe ToS | a liability clause with exclusions but no cap → `MISSING` **with evidence retained** (45C.14) |
| `DOC-LIAB-09` | the executed NDA | no liability provision at all → `MISSING` with **zero** evidence (45C.15) |

### 3.2 · The line is enforced, not documented

`DOCUMENT_SUPPORTED` would be a comment if nothing checked it, so `load_fixture` refuses
any such fixture that supplies `preferred`, supplies `acceptable_max` /
`approval_required_above` / `unlimited_outcome`, expects `MATCH`, or expects any Rule
Outcome but `NOT_APPLICABLE`. Five tests exercise those refusals.

This closes the §2.2 trap mechanically: setting `preferred: 6` from the supplied MSA to
obtain a `MATCH` now fails with an error naming the reason, rather than passing as a
fixture that looks document-derived.

### 3.3 · The V1 interim policy, and the four fixtures it unblocked

The owner's second instruction of 2026-08-18: *"I do not currently have a formally approved
LeapSwitch Company Acceptance Policy or Legal Rule. For V1, use the supplied LeapSwitch
legal documents as the authoritative source for the positions they explicitly state."*
Matching a stated position is `MATCH`; differing is `DEVIATION`; a deviation is **never**
automatically `APPROVAL_REQUIRED` or `UNACCEPTABLE`.

This separates the two axes cleanly, and the separation is now enforced rather than
described:

| | `classification` | `rule_outcome` |
|---|---|---|
| What it says | what the provision **is** | what Legal should **do** |
| Basis | a position the documents state | an approved Legal Rule |
| Available now | ✅ `MATCH` / `DEVIATION` / fail-closed | ❌ `NOT_APPLICABLE` only |

Four `STANDARD_DERIVED` fixtures follow (`backend/tests/corpus/standard_liability.json`):

| Fixture | Position used | Asserts |
|---|---|---|
| `STD-LIAB-MSA-01` | MSA 17.2's stated 6 months | `MATCH` + `NOT_APPLICABLE` — **not** `ACCEPTABLE` |
| `STD-LIAB-TOS-01` | ToS 13's stated 12 months | `MATCH` + `NOT_APPLICABLE` |
| `STD-LIAB-CROSS-01` | MSA 17.2's position vs ToS 13's clause | `UNABLE_TO_EVALUATE` — the two stated positions are **not commensurable** |
| `STD-LIAB-TOS-02` | ToS 13's position, cap + 3 carve-outs | general `MATCH`, carve-outs `DEVIATION`, roll-up `DEVIATION` — 45E's L-08 shape but for the outcome |

`STD-LIAB-CROSS-01` is the important one. MSA 17.2 measures against fees for *the affected
Services*; ToS 13 against *total* fees. Six and twelve are therefore **not two values of one
quantity**, and 45B.4 forbids assuming they are — so the engine returns
`UNABLE_TO_EVALUATE` rather than a twelve-versus-six deviation. **The choice among the
documents' positions cannot be made by picking the smaller number**, which is exactly why
§8.1's ruling is still needed.

### 3.4 · `NOT_YET_SPECIFIED` was requested; `NOT_APPLICABLE` already means it

The instruction asked for `NOT_YET_SPECIFIED` where the specification requires a legal
outcome. **No enum value was added**, because locked Step 20 r4 already fixes exactly that
meaning:

> *"not every Clause requires a Pre-approved Legal Rule. With no rule the outcome is
> `NOT_APPLICABLE` — the deviation stands and a human decides. The engine never invents a
> tolerance."*

Adding a fifth `RuleOutcome` value would also be an enum change outside any lock record,
which `IMPL-01` does not authorize, and would duplicate a locked state. Recorded as an
available decision in §8.7 should the distinction be wanted first-class.

### 3.5 · What the thirteen do *not* establish

They assert that the engine fails closed correctly on real text, and that clauses matching
a stated position are recognised as matching. **They assert nothing about whether any cap in
these documents is acceptable.** No fixture in the repository asserts `ACCEPTABLE`,
`APPROVAL_REQUIRED` or `UNACCEPTABLE`; `load_fixture` refuses one that tries and
`test_no_fixture_asserts_an_acceptance_policy` re-checks the whole corpus. `IMPL-01`
condition 2 still governs, and the corpus contains **no `NORMATIVE` fixture**. Step 35.10
remains uncalibrated.

Coverage of all 64 specified cases is tracked in `backend/tests/corpus_coverage.json` and
enforced by `test_corpus_coverage.py`:
**15 AUTHORED · 4 PARTIAL · 24 BLOCKED · 13 STRUCTURAL_ONLY · 8 SEPARATE_TRACK**.

---

## 4 · What *is* usable now — extraction terminology (item 4)

Every phrase below is **quoted verbatim** from a supplied document and attributed. This
is candidate terminology for owner ratification, **not** a configuration that has been
written. Nothing here has been added to any Company Standard.

The target is the `extraction` block of a Company Standard's JSONB configuration, whose
exact keys are `cap_phrases`, `unlimited_phrases`, `units`, `bases`, `exceptions`
(`{scope, terms, scope_label}`) and `general_scope`
([`extraction/liability.py`](../../backend/legalmind/extraction/liability.py)).

### 4.1 · `cap_phrases` — candidates, verbatim

| Phrase | Source |
|---|---|
| "total aggregate liability … shall not exceed" | D6 §17.2, §17.7 |
| "TOTAL AGGREGATE LIABILITY TO YOU FOR ALL CLAIMS ARISING OUT OF OR IN CONNECTION WITH … SHALL NOT EXCEED" | D2 §13 |
| "shall not exceed the total fees paid by" | D2 §13, D6 §17.7 |
| "shall not exceed the total amount actually paid by" | D6 §17.2 |
| "Monetary Cap on Liability" *(heading)* | D6 §17.2 |
| "Limitation of Liability" *(heading)* | D2 §13, D6 §17 |
| "Under no circumstances will the total … exceed the total monthly charge" | D3, D4 |

### 4.2 · Magnitude and basis text — candidates

| Text | Source |
|---|---|
| "the total fees paid by you to Leapswitch during the twelve (12) months immediately preceding the event giving rise to the claim" | D2 §13 |
| "the total amount actually paid by the Customer to Leapswitch for the specific Services giving rise to the claim during the six (6) month period immediately preceding the event giving rise to such liability" | D6 §17.2 |
| "the total fees paid by Customer in the \_\_\_\_\_\_\_\_\_\_ months preceding the claim" | D6 §17.7 — **blank unfilled** |

`units` and `bases` remain **unnamed**. No document names a unit vocabulary; all three
express the cap as fees paid over a month-denominated window. Whether that is
`unit = MONTHS` with `basis = FEES_PAID`, or some other naming, is a configuration
vocabulary decision, and 45C.23 forbids silent conversion between bases — so the naming
matters and is not cosmetic.

### 4.3 · `unlimited_phrases` — **none present in this tranche**

No supplied document contains "unlimited liability", "liability shall not be limited",
"without limit as to amount" or any equivalent. This is a real gap with real consequences
(§6): `LiabilityExtractionConfig.is_usable` requires `cap_phrases` **or**
`unlimited_phrases`, so extraction runs without it — but five fixtures cannot be built.

**A false-positive hazard, evidenced.** The string "without limitation" occurs
repeatedly across all six documents, always in the enumerative sense — "including,
without limitation, loss of profits" (D2 §13, D6 §17.1, D5 §1). If "without limitation"
were configured as an unlimited-liability phrase, **every document in this tranche would
falsely extract `UNLIMITED`**, including the two that carry an explicit finite cap. This
is precisely the 45A §15 / 45C.12 negative-pattern hazard, observed in real text rather
than hypothesised, and it is why 45E.2's L-29a/L-29b matched pair is specified.

Similarly, "the event giving rise to the claim" (D2 §13, D6 §17.2) is a **timing anchor**,
not a per-event cap. Configuring it as a per-event scope marker would mis-scope both
genuine aggregate caps.

### 4.4 · `exceptions` — carve-out terminology, real and directly usable

Introducers:

| Phrase | Source |
|---|---|
| "Nothing in these Terms shall limit or exclude liability for:" | D2 §13 |
| "The foregoing limitations shall not apply to" | D6 §17.3 |
| "Exclusions from Limitation" *(heading)* | D6 §17.3 |
| "Notwithstanding anything to the contrary contained in this Agreement" | D6 §17.2 |

Carve-out subjects:

| Term | Source |
|---|---|
| "death or personal injury caused by negligence" | D2 §13 |
| "fraud or fraudulent misrepresentation" | D2 §13 |
| "any liability that cannot be limited or excluded under applicable law" | D2 §13 |
| "indemnity obligations" | D6 §17.3 |
| "breach of payment obligations" | D6 §17.3 |
| "fraud, willful misconduct, or gross negligence" | D6 §17.3 |

Each needs a `scope` key and `scope_label` assigned, and item 3 must say which are
comparable. **Scope keys are configuration the owner names**, not labels to be coined here.

### 4.5 · Text that must **not** be extracted as a cap

Excluded-damages language is not a cap and must not become one. Present in all six:
"indirect, incidental, special, consequential, exemplary, or punitive damages"; "loss of
profits, revenue, goodwill, business opportunities, data"; "In no event shall … be liable
for" (D1, D2 §13, D6 §17.1 and §17.6).

D1 is the sharpest case: **it excludes categories of damages and states no monetary cap at
all.** That makes it a real specimen for L-19 — a liability clause with no cap, which must
classify `MISSING` *with evidence retained*, never `MATCH`.

Service-credit language — "Service Credits … represent your sole and exclusive remedy"
(D2 §9, D3, D4) — caps a different thing. **Whether service credits fall within
`LIABILITY-001`'s scope is a scope decision for you**, and I have not assumed either way.

---

## 5 · The 54.6 problem: none of the six can enter the repository as-is

Locked 54.6: *"golden fixtures use synthetic or cleared contract text. Real counterparty
contracts do not enter the repository."*

| | Obstacle |
|---|---|
| **D5** | **Executed, real counterparty, real signatories.** Names, titles, registered addresses and CIN of an identified third party. Bars it under 54.6 without clearing, and it is that counterparty's confidential instrument. Cannot be committed. |
| D1–D4 | Published public pages, so not counterparty documents — but they carry Leapswitch's GST, CIN, registered address, staff email addresses and phone number. |
| D6 | Unexecuted template, no counterparty named — closest to admissible, and Leapswitch's own commercially sensitive contract template. |

**Three decisions are yours:**

1. May D6 and D1–D4 be committed to the repository, or must they live outside it? If
   outside, where — 54.6 obliges us to agree a location, and the corpus runner needs a
   stable path.
2. D5: cleared/redacted version, a synthetic equivalent, or excluded?
3. Does quoting the phrases in §4 of *this* document count as acceptable in-repo use? I
   quoted D1–D4 freely as published material, quoted D6's liability clause because items
   2 and 3 cannot be discussed without it, and named no party from D5. **Say the word and
   I will reduce §4 to citations without quoted text.**

**Format note.** D1–D4 are browser print-to-PDF captures. Their text layer interleaves
site navigation — "Pricing Contact Login Sign Up", "New Nvidia H200 GPU is now
available", footer link lists — with the contract body, and repeats each page. Ingestion
will extract that chrome as clause text. Cleaned source (original DOCX/PDF, or the
contract body only) would materially improve mapping quality; alternatively the chrome is
real-world noise worth keeping deliberately, but that should be a choice.

---

## 6 · Fixture-by-fixture: what this tranche supplies as *input*

45E.2's 30 liability fixtures. "Input" means real specimen text exists.

**`backend/tests/corpus_coverage.json` is authoritative for status** and covers all 64
specified cases, not just these 30; it is enforced by `test_corpus_coverage.py`, so it
cannot drift from the corpus. The table below is the *material* view — what the documents
do and do not contain — kept because it is what a second tranche must be gathered against.
Nine of these rows are now authored (§3.1); the rest need one of six named inputs.

| Fixture | Input available | Source |
|---|---|---|
| L-01 6-month aggregate cap | ✅ | D6 §17.2 |
| L-02 12-month aggregate cap | ✅ | D2 §13 |
| L-03 24-month aggregate cap | ❌ **none** | — |
| L-04 Unlimited general liability | ❌ **none** | see §4.3 |
| L-05 Multiple caps, different scopes | ◐ candidate | D6 §17.2 (service-scoped) vs §17.7 (unscoped) |
| L-06 Same scope, contradictory caps | ✅ **strong** | D6 §17.2 vs §17.7 — see §7 |
| L-07 General cap + carve-outs | ✅ **strong** | D6 §17.2+§17.3; D2 §13 |
| L-08 Unlimited carve-out | ✅ | D2 §13 — carve-outs with no cap for their scope |
| L-09 Per-claim vs aggregate | ❌ **none** | no per-claim cap; see §4.3 hazard |
| L-10 Per-event vs aggregate | ❌ **none** | as above |
| L-11 Different monetary bases | ◐ candidate | "total fees paid" vs "amount actually paid for the specific Services" |
| L-12 Fixed amount vs fee-based | ❌ **none** | no fixed-sum cap anywhere |
| L-13 Percentage-based cap | ◐ candidate | D3/D4 credit percentages; D6 §7.6.7 "200% of the Monthly Recurring Charges" — scope question, §4.5 |
| L-14 Cross-reference resolved | ✅ | D6 §17.3 → §16; D2 §9 → SLA |
| L-15 Cross-reference unresolvable | ✅ **strong** | D6 §1.8 "Clause \_\_\_", §1.9 "Clause \_\_\_\_" — both blank |
| L-16 Conflicting cross-reference chains | ◐ candidate | D6 §15.5 "unless under Clause 8.4"; 8.4 concerns deductions/TDS, not credits |
| L-17 Negative wording → UNLIMITED | ❌ **none** | §4.3 |
| L-18 Ambiguous wording | ◐ candidate | D6 §6.3 corrupted sentence; §17.7 blank |
| L-19 Liability clause, no cap | ✅ **strong** | D1 — exclusions only, no cap |
| L-20 Liability wholly absent | ✅ **strong** | D5 — no liability provision at all |
| L-21 Referencing clause | ◐ candidate | D2 §9 |
| L-22 Same cap repeated | ◐ partial | D6 §17.1 and §17.6 repeat the exclusion, not a cap |
| L-23 OCR corruption, resolvable | ✅ | D2/D4 "HHIIRRIINNGG"; GST and CIN split mid-token across lines |
| L-24 OCR corruption, ambiguous | ◐ candidate | as above |
| L-25 Missing unit | ✅ **strong** | D6 §17.7 — a cap whose magnitude is a blank |
| L-26 Missing necessary scope | ◐ candidate | D6 §17.7 unscoped |
| L-27 Precedence, no configured rule | ✅ **strong** | D2 §9 "the provisions of the SLA shall prevail, but solely to the extent of the conflict"; D3 same |
| L-28 Configured deterministic precedence | ✅ | same text, with a configured rule |
| L-29a / L-29b negative-pattern pair | ❌ **none** | §4.3 — the sharpest fixture in the set has no specimen |

**Roughly 18 of 30 have real input text; 8 have none.** To close the eight, the next
tranche needs paper containing: a cap longer than 12 months, unlimited-liability wording,
a per-claim or per-event cap, a fixed-sum cap, and the "liability shall not be limited"
construction with and without a trailing carve-out.

Three of the fail-closed matrix are now authored from real material — `F-01` (no
configured precedence → `CONFLICT`) by `DOC-LIAB-04`, and `F-02`/`F-04` (no configured
conversion, incomparable basis → `UNABLE_TO_EVALUATE`) by `DOC-LIAB-06` — as is `R-01`,
Tier-1 dominance, which `DOC-LIAB-05` and `DOC-LIAB-07` demonstrate with real carve-outs.

The presence set (P-01 – P-06) is the one group where real documents help least. The
presence evaluator turns on `expected_presence` — whether the organization *wants* the
provision — which is a Company Standard value, not a document fact; and on `mapping_state`,
which is a mapper output. **No presence fixture was authored from this tranche**, because
labelling one `DOCUMENT_SUPPORTED` would overstate what the documents establish. R-14
needs a Requirement catalogue.

---

## 7 · Two things found in the documents, reported and not resolved

Reported because they are observable facts about the text, and rule 5 applies to me even
when the contradiction is in source material rather than in the specification.

**7.1 · D6 carries two different aggregate liability caps in one clause.**

> §17.2 — "shall not exceed the total amount actually paid … during the **six (6) month
> period** immediately preceding the event"
>
> §17.7 — "shall not exceed the total fees paid by Customer in the **\_\_\_\_\_\_\_\_\_\_
> months** preceding the claim"

Both are styled as the total aggregate liability of Leapswitch. One is six months and
scoped to the specific Services; the other is unscoped with the period left blank. As
input this is excellent material — it is simultaneously a real L-06 (contradictory caps),
L-25 (missing magnitude) and L-26 (missing scope) specimen. **As Leapswitch's own
customer-facing template it may be a drafting defect you want to know about.** I make no
legal assessment of which clause governs; 45C.2 is clear that with no configured
precedence the engine would classify `CONFLICT` rather than pick a winner, and that is
the engine's behaviour, not advice.

**7.2 · Divergences across the tranche.** Recorded as observations only:

* Liability cap: 12 months (D2 §13) · 6 months (D6 §17.2) · blank (D6 §17.7) · none (D1, D5)
* Confidentiality survival: 3 years (D6 §12.3) · 2 years (D5 §9)
* Forum: arbitration seat Pune (D2 §21) · arbitration Mumbai, High Court of Mumbai appoints (D6 §19) · exclusive jurisdiction Bengaluru (D5 §14)
* Governing law: India (D2 §22, D6 §19, D5 §14) · "the statutes and laws of India **and the United States of America**" (D1)
* SLA credit bands for the same uptime tiers: 5/10/20% (D3) · 15/40/100% (D4) — different service lines
* Incorporation: "Companies Act, 2013" (D1, D3) · "Companies Act, 1956" (D5, D6) — same CIN
* Registered office: Office 410, Spectra Commercial, Pratik Nagar, Paud Road (D2 §25) · 1/A2/22, Ajantha Avenue, Paud Road (D5, D6)

**None of this belongs in [CONFLICTS.md](CONFLICTS.md).** That register tracks
contradictions between LegalMind *specification* documents. A divergence between two of
the organization's contracts is subject matter the system is built to detect, not a defect
in the system's specification, and filing it there would confuse the two permanently.

---

## 8 · The exact material still required

Items 1, 4 and 5 of the form below are what remain of HANDOFF.md §6.1; items 2 and 3
carry the config keys the code reads, so answers can be transcribed rather than
interpreted. **Every field left blank stays blank** — no default will be supplied,
because in this engine an absent value is a fail-closed instruction, never a default
(`rule_config.py`).

### 8.1 · Company Standards — ✅ RATIFIED, per document type since 2026-08-19

**Owner Q3=B (2026-08-19): standards are per document type.** The 2026-08-18 ratification
(12 months of total fees) survives value-unchanged as the **TOS** standard; the **MSA**
standard is 6 months of affected-service fees from `MSA.pdf` §17.2, the owner choosing the
operative clause over the blank-period §17.7.

| Code | Type | Position | Source |
|---|---|---|---|
| `LIABILITY-MSA-001` | MSA | 6 months / affected-service fees | `MSA.pdf` §17.2 |
| `LIABILITY-TOS-001` | TOS | 12 months / total fees | `TOS-leapswitch.pdf` §13 |

Liability is **not applicable** to NDA (Q4=A); SLA remains the open `L-13` scope ruling.
The subsection below records the original 2026-08-18 ratification as written.

#### Original record — Company Standard for `LIABILITY-001` — ✅ RATIFIED 2026-08-18

**12 months of total fees.** Chosen by the owner from the two positions the documents state.
Recorded at `backend/config/company_standards/LIABILITY-001.json` *(since 2026-08-19: `LIABILITY-TOS-001.json`, value unchanged)*, referenced by fixtures
through `company_standard_ref`, and stated nowhere else.

```jsonc
{ "preferred": 12, "unit": "MONTHS", "basis": "FEES_PAID", "scope_key": "AGGREGATE" }
```

Source: Leapswitch Networks ToS §13, second bullet. **Provenance correction:** the
instruction cited "the confirmed C-01 decision"; `C-01`/`REC-01` resolved the Finding-type
*vocabularies* — it supplies the `MATCH`/`DEVIATION` terms but **not** the 12-month figure,
and no locked decision does. The figure is configuration, from the document above.

Two consequences worth re-reading, both enforced:

* **`unit: MONTHS`, `preferred: 12` is a lookback window, not a multiplier.** The clause caps
  at *"the total fees paid ... during the twelve (12) months immediately preceding the
  event"*. Under annual prepayment that is not twelve times a monthly fee. Reported before
  ratification; the clause's own wording was kept.
* **The organization's own six-month cap does not deviate from it — it fails closed.**
  MSA §17.2 measures on fees for the *affected Services*; the standard measures on *total*
  fees. 45B.4 forbids assuming equivalence, so `STD-LIAB-02` asserts `UNABLE_TO_EVALUATE`.
  Making them comparable is a legal judgement requiring `comparable_bases` and owner approval.

### 8.2 · Legal Rule for `LIABILITY-001` — ⛔ NONE EXISTS, and this is now specified behaviour

The owner stated on 2026-08-18 that no formally approved Company Acceptance Policy or Legal
Rule exists. **This is recorded as fail-closed behaviour rather than left as an open
request**, so no one need invent a rule to make the system work:

```text
rule_outcome            NOT_APPLICABLE, always
                        locked Step 20 r4 — "the deviation stands and a human decides"

routing                 DEVIATION + NOT_APPLICABLE  ->  Finding DECISION_REQUIRED
                        UNRULED_DEVIATION_REQUIRES_DECISION, a widening F-4 permits

never inferred          6 months · 18 months · unlimited liability · no cap ·
                        per-claim caps — none is acceptable or unacceptable
```

`load_fixture` refuses any fixture configuring `acceptable_max`,
`approval_required_above` or `unlimited_outcome`, or expecting a Rule Outcome other than
`NOT_APPLICABLE`; `test_no_fixture_asserts_an_acceptance_policy` re-checks the whole corpus.

**Nothing further is needed from the owner here.** When a Legal Rule is approved it becomes
the `NORMATIVE` tier's precondition, and three PARTIAL cases (L-03, L-08, and 45E's
`APPROVAL_REQUIRED`/`UNACCEPTABLE` expectations generally) complete at that point.

### 8.3 · Extraction terminology

§4 is a draft you can strike through. Please confirm or correct:

1. which of §4.1's phrases are cap phrases;
2. `unlimited_phrases` — **§4.3 found none in this tranche.** Give the wording your
   counterparties actually use, or confirm there is none and accept that L-04, L-08,
   L-17 and L-29a/b stay unauthored;
3. the `units` and `bases` vocabulary — you name it, §4.2;
4. for each §4.4 carve-out: its `scope` key and reviewer-facing `scope_label`;
5. whether service credits are within `LIABILITY-001`'s scope at all (§4.5).

### 8.4 · Requirement applicability — ✅ RULED, see §8.7

Superseded. `LIABILITY-001` is the only Requirement in V1 and `D-3` fails closed to
`REQUIRED`, so no applicability list is outstanding.

### 8.5 · A second tranche — the one substantial thing still outstanding

**14 cases**, and it is material rather than a decision. The six supplied documents contain
no specimen of:

* a cap longer than twelve months (L-03)
* unlimited-liability wording — "liability shall not be limited" (L-04, L-17, **L-29a/b**)
* a per-claim cap (L-09) or a per-event cap (L-10)
* a fixed monetary sum rather than a fee multiple (L-12)
* a cap restated in materially identical terms (L-22)
* two caps on genuinely different scopes (L-05, after the §8.8 ruling)
* a six-month cap measured on **total** fees, which the ratified standard would make a
  real `DEVIATION` (L-01)

**Counterparty-drafted paper serves better than more Leapswitch-issued paper** (§2.1):
your own documents state your own position, so measured against your own standard they
tend to match, and `DEVIATION` is what most of the 45E table exists to test. Cleared or
synthetic, per 54.6, and it can live at the agreed path in §8.6.

Step 35.10 calibration needs the same set — locked 54.6 notes the corpus set and the
calibration set are one set.

### 8.6 · Storage — ✅ RULED 2026-08-18

**Outside the repository, at an agreed local directory.** `/root/legalmind-source-material/`,
resolved by `config.source_material_dir()` and overridable with
`LEGALMIND_SOURCE_MATERIAL_DIR`. Its README fixes the six filenames. Placing the files
there unblocks the seven `DOCUMENT_LEVEL_HARNESS` cases; nothing sensitive is committed,
and `test_source_material.py` asserts the path is outside the working tree and that no
copy of any of the six exists in the repository.

### 8.7 · Requirement catalogue — ✅ RULED 2026-08-18

**Liability cap only in V1.** No Requirement code was created. The consistently stated
positions in §4 (force majeure 60 days, dispute window 30 days, late fee 5% after 5 days,
uptime tiers) were **not** turned into Requirements; rule 21 bars manufacturing a catalogue
and the owner declined to supply one for V1. `P-01`, `P-02`, `P-05` and `R-14` are recorded
`OUT_OF_V1_SCOPE` — decided, not owed.

### 8.8 · MSA §17.2 vs §17.7 — ✅ RULED 2026-08-18

**One scope, contradictory.** Both clauses govern total aggregate liability and conflict,
so `DOC-LIAB-04`'s `CONFLICT` is the ratified expectation. `L-05` (multiple caps on
different scopes) therefore has no specimen in the six documents and needs a second tranche.

### 8.9 · Basis comparability — ✅ RULED 2026-08-18

**`FEES_PAID` and `FEES_PAID_FOR_AFFECTED_SERVICES` stay distinct.** No `comparable_bases`
entry, no conversion rule. A cap measured on affected-service fees is never compared
numerically to the standard: it fails closed to `UNABLE_TO_EVALUATE` and a human decides,
however close the numbers look. No code change was required — this is 45B.4's default.

### 8.10 · Optional — make "no policy yet" first-class

Today a `NOT_APPLICABLE` Rule Outcome means either *no Legal Rule exists* or *a Legal Rule
exists and no threshold applies to this value*; only the explanation string distinguishes
them (§3.4). If you want that visible on the Evaluation itself, it needs a decision, because
it is a locked-enum change (`IMPL-01` authorizes none). **Nothing is blocked by leaving it
as it is** — and the current behaviour is already the locked fail-closed one.

---

## 9 · What was not done

* **No acceptance policy, anywhere.** No fixture asserts `ACCEPTABLE`,
  `APPROVAL_REQUIRED` or `UNACCEPTABLE`; no `acceptable_max`,
  `approval_required_above` or `unlimited_outcome` is configured. `load_fixture`
  refuses such a fixture and `test_no_fixture_asserts_an_acceptance_policy` re-checks
  the corpus (§3.2, §3.3).
* **No `NORMATIVE` fixture**, which is the tier that would need the approved policy.
* **No fifth `RuleOutcome` value**, despite `NOT_YET_SPECIFIED` being asked for —
  `NOT_APPLICABLE` is already the locked meaning (§3.4).
* **No Requirement invented.** Only `LIABILITY-001` is used. The documents state
  positions on force majeure cure periods, dispute-resolution windows, late fees and
  uptime, several of them consistently — but authoring those needs Requirement codes,
  and rule 21 names Requirement catalogues as material that must be supplied, never
  manufactured. Recorded as blocked in §8.4 rather than filled in.
* **No configuration value chosen.** Every field in §8 is `null`. The `unit`, `basis` and
  `scope_key` names used in the nine fixtures are **vocabulary taken verbatim from the
  clauses** ("total aggregate liability", "six (6) month period", "the total fees paid
  by") — they name how a value is expressed, never what is acceptable. If your standard
  uses different names, the affected fixtures change branch and must be re-derived.
* **No synthetic contract, and no clause invented to fill a gap.** Where the documents
  contain no specimen, the fixture is recorded unavailable with the reason.
* **No cap value, threshold, unit or scope key coined**, including from D6 §17.2's six
  months (§2.2).
* **No document committed to the repository**, and D5's counterparty is unnamed (§5).
* **Nothing resolved.** §7's divergences are reported; the review-direction question in
  §2.1 is asked, not answered.
* **`all_lock.md` untouched.** Nothing here is a lock record; nothing here is locked.
* Corpus at **16 `STRUCTURAL` + 9 `DOCUMENT_SUPPORTED` + 3 `STANDARD_DERIVED`, 0 `NORMATIVE`**; Step 35.10 still uncalibrated.


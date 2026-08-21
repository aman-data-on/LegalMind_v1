# Clause Catalogue — the full-document review map

**Status: CONFIGURATION RECORD, 2026-08-19.** The owner's instruction of 2026-08-19
("review ALL clauses, like a lawyer — not just liability") **supersedes** the 2026-08-18
ruling "Requirement catalogue = liability cap only in V1". Under the manager's standing
rule — *whatever is stated in our approved LeapSwitch legal documents is the final
position* — every standard below is **extracted from a LeapSwitch document, cited to its
clause**, never invented. Rule 7/21 satisfied: the positions are the documents' own.

Register note: the owner's conflict register was located at
`/root/LegalMind/docs/CONFLICT_GAP_ANALYSIS.md` (owner authorized that location,
2026-08-19). Its own tracker marks C-01/C-04/C-05/C-07/C-23 "Needs owner decision" and
C-08/C-09 "Needs fact-check" — so it is **corroboration, not a source of positions**.
The per-type model dissolves most of its cross-document tensions (e.g. C-07's "3yr MSA vs
2yr NDA" — the MSA standard is 3 years; the NDA in hand is counterparty paper).

**Coverage-gap pass, 2026-08-20.** A clause-by-clause coverage audit of all six
LeapSwitch-issued documents (owner tasking) found the 21 ratified Requirements correctly
scoped and correctly targeted but **shallow on the clauses that carry the most risk** —
most acutely, `LIABILITY-MSA-001` read the cap number and nothing else. Eleven further
Requirements were ratified in response, all `PRESENCE`, all extracted from clauses the
2026-08-19 review had read: **32 Requirements across four document types** (MSA 15 · TOS 8
· NDA 8 · SLA 1). `tools/verify_terminology.py` reproduces all 32 from the documents they
cite. What the pass deliberately did *not* add is recorded under
[Considered and declined](#considered-and-declined-2026-08-20) — the goal is the smallest
defensible catalogue, not the largest.

## Requirements by document type

### MSA — 15 Requirements (source: `MSA.pdf`, Leapswitch MSA v2 July 2025)

The first eight were ratified 2026-08-19. The seven marked **⊕2026-08-20** were added
by the coverage-gap pass of that date (owner tasking; decisions #44–#46) — every one
extracted from a clause the full-document review had read but not yet turned into a
Requirement. None is numeric: each verifies that a provision EXISTS, and its content
goes to Legal with the evidence.

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| LIABILITY-MSA-001 ✅existing | Limitation of liability | 6 months, affected-service fees | §17.2 | NUMERIC |
| CONF-SURVIVAL-MSA-001 | Confidentiality survival | **3 years** post-termination | §12.3 | NUMERIC |
| FORCE-MAJEURE-MSA-001 | FM termination trigger | **60 consecutive days** | §18.3 | NUMERIC |
| CURE-PERIOD-MSA-001 | Breach cure period | **30 days** | §7.4 | NUMERIC |
| AUTORENEW-MSA-001 | Auto-renewal term | **6 months** | §7.3 | NUMERIC |
| DATA-PURGE-MSA-001 | Post-termination data purge | **15 days** | §7.6.6 | NUMERIC |
| GOVLAW-MSA-001 | Governing law clause | present (laws of India) | §19.1 | PRESENCE |
| ARBITRATION-MSA-001 | Arbitration clause | present (Mumbai, ACA 1996) | §19.3–19.4 | PRESENCE |
| LIAB-EXCLUSIONS-MSA-001 ⊕2026-08-20 | Indirect/consequential damages exclusion | present | §17.1 (restated §17.6) | PRESENCE |
| LIAB-CARVEOUTS-MSA-001 ⊕2026-08-20 | Carve-outs from the liability cap | present | §17.3 | PRESENCE |
| INDEMNITY-MSA-001 ⊕2026-08-20 | Customer indemnity | present (one-directional) | Clause 16 | PRESENCE |
| RETURN-DESTRUCTION-MSA-001 ⊕2026-08-20 | Return/destruction of Confidential Information | present | §12.2 | PRESENCE |
| IP-OWNERSHIP-MSA-001 ⊕2026-08-20 | Supplier IP ownership | present | §13.1 | PRESENCE |
| WARRANTY-DISCLAIMER-MSA-001 ⊕2026-08-20 | Warranty disclaimer | present | §14.3 | PRESENCE |
| EARLY-TERM-RESTRICTION-MSA-001 ⊕2026-08-20 | No customer right of early termination | present | §7.2 | PRESENCE |

**Why the three liability Requirements are separate, not one.** `LIABILITY-MSA-001`
reads the cap **value**; the other two read whether the **exclusion** and the
**carve-outs** exist at all. The 2026-08-20 audit found the gap this closes: a
counterparty MSA capping at six months with no consequential-damages exclusion and no
fraud/gross-negligence carve-out produced a clean `MATCH` and reached nobody, while
being a materially worse deal. Folding them into the numeric Requirement was rejected —
presence has no magnitude, and a single Requirement cannot answer two questions without
one of the answers becoming invisible.

**Deliberately NOT extracted as numeric positions.** §7.2's early-termination fee
("total fees that would have become payable for the remainder of the Term") is a
*formula*, not a magnitude; 45B.4 forbids flattening it into a comparable number, so the
Requirement reads presence and the formula goes to Legal as evidence.

### TOS — 8 Requirements (source: `TOS-leapswitch.pdf`, 26 Feb 2026)

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| LIABILITY-TOS-001 ✅existing | Limitation of liability | 12 months, total fees | §13 | NUMERIC |
| LATE-FEE-TOS-001 | Late-payment interest | **5 % per month** | §7 | NUMERIC |
| DATA-RETRIEVAL-TOS-001 | Post-termination retrieval | **7 days** | §16 | NUMERIC |
| KYC-RETENTION-TOS-001 | KYC record retention | **5 years** | §8 | NUMERIC |
| FORCE-MAJEURE-TOS-001 | FM termination trigger | **60 consecutive days** | §15 | NUMERIC |
| GOVLAW-TOS-001 | Governing law clause | present (laws of India) | §22 | PRESENCE |
| ARBITRATION-TOS-001 ⊕2026-08-20 | Arbitration clause | present (Pune, sole arbitrator, ACA 1996) | §21 | PRESENCE |
| AUTORENEW-TOS-001 ⊕2026-08-20 | Auto-renewal term | present | §4 | PRESENCE |

**Both ⊕ entries close asymmetries, not new topics.** The 2026-08-20 audit found
`ARBITRATION-MSA-001` and `AUTORENEW-MSA-001` in place while TOS §21 carried a full
arbitration clause and TOS §4 auto-renewed, each with no Requirement and **no recorded
rationale for the omission** — oversights rather than decisions. The differing
arbitration *seat* (Pune vs the MSA's Mumbai) is legitimate per-contract choice, not a
contradiction, and is content rather than something compared. `AUTORENEW-TOS-001` is
PRESENCE where the MSA's is NUMERIC because the TOS renews for *"the same billing
period"* — self-referential, no magnitude to read — and the MSA's six-month successive
period is a different question on a different document type (45B.4).

### SLA — 1 Requirement (source: `SLA-leapswitch.pdf`; CloudPe SLA states the same value)

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| CLAIM-WINDOW-SLA-001 | Service-credit claim window | **60 calendar days** | "How to Request a Service Credit" ¶1 | NUMERIC |

Liability remains **not applicable** to SLA — **RULED 2026-08-20 (closes L-13)**: service credits are a remedy, not a liability cap; credit percentages are never read as caps, and no SLA-typed liability standard may be created from them.

### NDA — 8 Requirements (source: `NDA.pdf`, executed 17 June 2026)

**Owner designation, 2026-08-19:** the executed NDA **is** the LeapSwitch NDA — the
positions LeapSwitch accepts **as Receiving Party**. Those accepted positions are the
baseline for reviewing counterparty NDAs (where LeapSwitch is again the receiving party).
*Direction caveat:* if a review ever concerns LeapSwitch **disclosing** its own
information, these standards do not state that position. The counterparty is never named
in this repository.

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| CONF-SURVIVAL-NDA-001 | Confidentiality survival | **2 years** (trade secrets: perpetual) | §9 | NUMERIC |
| NON-SOLICIT-NDA-001 | Non-solicitation period | **2 years** | §10 | NUMERIC |
| TERM-NOTICE-NDA-001 | Termination notice | **30 days** | §9 | NUMERIC |
| GOVLAW-NDA-001 | Governing law clause | present (laws of India) | §14 | PRESENCE |
| RETURN-DESTRUCTION-NDA-001 | Return/destruction clause | present | §6 | PRESENCE |
| COMPELLED-DISCLOSURE-NDA-001 | Compelled-disclosure notice | present | §5 | PRESENCE |
| RESIDUALS-NDA-001 ⊕2026-08-20 | Residuals clause | present | §11 | PRESENCE |
| TRADE-SECRET-CARVEOUT-NDA-001 ⊕2026-08-20 | Perpetual trade-secret proviso | present | §9 | PRESENCE |

**The direction caveat above applies with extra force to `RESIDUALS-NDA-001`.** A
residuals clause is a *giveback from the disclosing party*: its presence is favourable to
LeapSwitch as receiving party and unfavourable in the reverse direction. The standard
records presence only and states nothing about LeapSwitch as discloser.

**`TRADE-SECRET-CARVEOUT-NDA-001` sits beside `CONF-SURVIVAL-NDA-001`, not inside it.**
A perpetual obligation has no magnitude, so folding the proviso into the two-year numeric
Requirement would require a number §9 does not state. Note the MSA has **no** equivalent
— §12.3's three years expires for trade secrets too — so no MSA-typed counterpart may be
derived from this one.

Liability remains **not applicable** to NDA (owner Q4=A, unchanged). Note the per-type
model resolving the register's C-07 cleanly: MSA survival = 3 years, NDA survival = 2
years — two document types, two positions, no contradiction.

### AUP / Privacy Policy / Order Form / Amendment / DPA — no Requirements in V1

AUP and Privacy Policy are unilateral published policies incorporated by reference;
counterparties do not submit competing ones. Order Form/Amendment are commercial
instruments. DPA: no LeapSwitch DPA template exists. Revisit on demand.

**Re-confirmed by the 2026-08-20 coverage audit, on evidence rather than by inheritance.**
Both policies were read clause by clause. Both state real positions — the Privacy Policy
carries genuine numeric retention periods (billing 7 years, KYC 5 years, ICT logs 180
days, support 3 years) and the AUP carries enforcement windows (24-hour response,
2-hour CSAM takedown). Zero Requirements remains correct anyway, because **nothing
submits a competing AUP or Privacy Policy**: they are unilateral published policies, so
there is no counterparty instrument to compare against. Adding Requirements here would
manufacture Findings on documents nobody negotiates.

⚠️ The AUP is also the live form of the `L-29a/b` trap: it is saturated with *"including
but not limited to"* in the purely **enumerative** sense. A detector hunting "not
limited" would read it as an uncapped liability clause. Zero Requirements is the safe
answer as well as the correct one — and the document-type filter means an AUP produces no
Findings at all, never a liability `MISSING`.

### Considered and declined (2026-08-20)

Recorded so a later reader does not mistake absence for oversight. Each is a real clause
in a LeapSwitch document; none became a Requirement.

| Clause | Why declined |
|---|---|
| MSA Clause 11 (data protection & privacy, §11.1–11.8) | The largest uncovered *area*, but eight mostly-narrative sub-clauses. It needs decomposing into specific checks before any one of them is a Requirement; a single broad Requirement would answer nothing precisely. **Open for a later pass, not rejected.** |
| MSA Clause 20 (AML / anti-bribery) · §10.2 insurance · §10.4 security safeguards · §15.2 suspension notice · §21.7 assignment asymmetry · Clause 6 change control · §7.5 insolvency triggers | Real, cited, presence-checkable — and low negotiation value against the mapping and calibration cost each carries. Deferred deliberately. |
| MSA §8.3 invoice-dispute window · §8.4 no set-off · §7.6.7 200% holdover · §7.6.8 dues/lien · §4.5 commissioning window · §5.2.2/§5.3.2 KYC and provisioning times | Operational and commercial mechanics rather than legal positions a counterparty draft contests. |
| TOS §19 / AUP §11 CERT-In obligations (6-hour reporting, 180-day logs) | Regulatory obligations restating CERT-In Directions. A statute is not a Company Standard (rule 7); these are background law LeapSwitch restates, and no acceptance position follows from them. |
| SLA uptime commitments (99.9% / 99.95% per service) | Blocked on the open multi-scope modelling decision, not on authorization. |
| SLA service-credit tiers (15% / 40% / 100%) | **Forbidden, not deferred.** Ruled 2026-08-20 (L-13): service credits are a remedy, not a liability cap, and credit percentages are never read as caps. |
| Governing-law and forum *values* ("India", Mumbai vs Pune vs Bengaluru) | Needs a categorical-value evaluator — out of V1 scope, already recorded below. |
| MSA breach-notification obligation | **Cannot be derived: the clause does not exist.** TOS §10 and the Privacy Policy §13 both carry one; the MSA does not. That is a defect in the MSA template, reported to the owner, and a missing clause can never yield a Requirement (rule 21). |
| MSA late fee / interest | Same shape: the MSA has no such clause, so the absence of a `LATE-FEE-MSA-001` is correct rather than an oversight. `LATE-FEE-TOS-001` exists because TOS §7 states 5% per month. |

## Comparability — which clauses are the SAME question, and which are not

**Owner question, 2026-08-19:** *"MSA says confidentiality = 3 years, NDA says 2 years. Is
this a contradiction or are they different things?"* Answered from the clause text, not by
assumption. This section exists because the answer governs whether the engine may compare
two numbers at all (45B.4: bases are never assumed equivalent).

### Confidentiality: MSA §12 vs NDA §9 — **DIFFERENT. No contradiction.**

Three independent grounds, each sufficient on its own:

| | MSA §12 | NDA §1/§3/§9 |
|---|---|---|
| **Trigger** | "In the context of the relationship under this Agreement" — during service delivery | "Partnership Discussions" — *before* any contract, while evaluating |
| **Definitional gate** | **Marking required**: "marked 'confidential'… **at the time of disclosure**" | **Marking NOT required**: "or that **reasonably should be understood** to be confidential" |
| **Direction** | Bilateral — "each party… may disclose to the other" | Unilateral — counterparty discloses, LeapSwitch receives |
| **Clock anchor** | Termination of the MSA — one fixed event | **Later of** NDA termination **and** the end of the underlying partnership relationship — floating |
| **Trade secrets** | No carve-out — they **expire** with the 3 years | "**for so long as** such information remains a trade secret" — **perpetual** |
| **Exclusion proof** | Receiving Party "can show" | "through **contemporaneous written records**" — higher bar |

**The decisive consequence:** because the anchors differ, the NDA's *two* years can run
**longer in absolute time** than the MSA's *three*, and for trade secrets the NDA never
expires while the MSA does. **"2 < 3" is not a true statement about protection strength**,
and the two numbers are not comparable quantities. A document that is *unprotected* under
the MSA (never marked) can be *protected* under the NDA — two different universes of
information, not two answers to one question.

**Enforced, not merely documented.** Each standard's `basis` encodes its measurement
anchor: `CONFIDENTIALITY_SURVIVAL_POST_TERMINATION` (MSA) and
`CONFIDENTIALITY_SURVIVAL_POST_TERMINATION_OR_RELATIONSHIP_END` (NDA). The bare topic
`CONFIDENTIALITY_SURVIVAL` was replaced on 2026-08-19 because it would let a counterparty
MSA reading *"three years **from the date of disclosure**"* register a false `MATCH` on the
number 3 — the 45B.4 trap in a second guise. Different bases fail closed; the document-type
filter already keeps MSA and NDA standards from meeting at all.

**This also resolves the register's C-07** ("confidentiality survival differs, 3yr MSA vs
2yr NDA") — not by reconciling the numbers, but by establishing they were never the same
question. Nothing to standardize.

### Other pairs the same question was asked of

| Pair | Same or different | Evidence |
|---|---|---|
| **Liability: MSA 6 months vs TOS 12 months** | **DIFFERENT, twice over** | Different *relationship* — MSA is a signed, negotiated master agreement with a fixed Term and purchase orders; TOS is click-through terms for self-serve website users. Different *basis* — §17.2 "fees paid for the specific Services giving rise to the claim" vs §13 "TOTAL FEES PAID BY YOU" (already ruled distinct, 2026-08-18). Two products, two liability envelopes |
| **Termination: MSA vs TOS** | **DIFFERENT** | MSA §7.2: the Customer has **no right** to terminate before the Term expires and stays liable for the remaining fees. TOS §16: self-serve cancellation, 7-day data retrieval. A committed-term contract against a month-to-month service — deliberately different deals |
| **Governing law: MSA vs TOS vs NDA** | **SAME question — and all three AGREE** | All state "the laws of India" (MSA §19.1, TOS §22, NDA §14). Consistent |
| **Forum (within the above)** | **DIFFERENT, and legitimately so** | MSA: courts in India, arbitration seated at the High Court of Mumbai (§19.3). NDA: courts at Bengaluru, exclusive (§14). TOS: no forum named. Each contract choosing its own forum is normal, not contradictory |

⚠️ **One item to flag rather than resolve.** TOS §22 adds: *"For customers using Services
from our US or European datacenter locations, applicable local data protection and consumer
protection laws of those jurisdictions shall additionally apply to the extent mandated by
law."* So the TOS is **not** purely India-governed in effect. This is not a contradiction
with the MSA — it is a scope the India-only reading does not capture, and it belongs to the
owner's register rather than to configuration.

### Also observed while reading — a drafting defect, not a policy question

MSA **§1.8** reads *"'Confidential Information' shall have the meaning set forth in Clause
___ of this Agreement"* — **the cross-reference is blank**, as are §1.9's (Force Majeure).
The definition does exist, inside §12.1, so the clause is workable; but the blanks are the
same class of defect as §17.7's blank period. Reported, not fixed — amending the template is
the owner's call.

## Deviation handling — all clauses

Zero tolerance (manager 2026-08-19; **owner approved & wired 2026-08-20**): MATCH → `ACCEPTABLE` · any DEVIATION →
`UNACCEPTABLE` → Legal Decision · nothing auto-approved. Every ratified standard file
now carries the approved Legal Rule (`deviation_outcome` + `unlimited_outcome` =
`UNACCEPTABLE`), imported as a `LegalRuleVersion`; no other rule is accepted. Categorical value comparison
(e.g. "India" vs "Singapore" as *values*) needs a new evaluator type — **out of V1
scope**; presence Requirements verify the clause exists, and its content goes to Legal
with the evidence.

**One nuance worth stating, because the 11 Requirements of 2026-08-20 are all PRESENCE.**
An *absent* required provision is `MISSING`, and `MISSING` carries `rule_outcome`
`NOT_APPLICABLE` — **not** `UNACCEPTABLE`. That is not a gap in the zero-tolerance
wiring: `deviation_outcome` disposes a `DEVIATION`, and absence is a different
classification. `MISSING` is Tier 1 and reaches a human by the locked D-3.5(b) route
instead, so the destination is the same — a Legal Decision — and nothing absent is ever
auto-approved. `ACCEPTABLE` is reachable only where the provision is present and matches.

## Gaps that remain

| Gap | Needs |
|---|---|
| ~~Mapping/extraction terminology per new Requirement~~ | **SUPPLIED 2026-08-19, extended 2026-08-20** (owner tasking) — every ratified file carries mapping/extraction terminology drawn from its cited clause; verified against the real source documents by `tools/verify_terminology.py` (**32/32** reproduce their ratified position). `confirm_threshold` stays STRUCTURAL pending 35.10 calibration |
| Counterparty calibration for the 11 Requirements ratified 2026-08-20 | The own-document baseline holds 32/32, but 35.10's calibration against *counterparty* drafting has been run only for the 21 earlier Requirements. The 11 new ones are pinned on own-document text plus mechanics fixtures; counterparty presence specimens for these clause types are welcome and nothing is blocked on them |
| MSA Clause 11 decomposed into specific data-protection checks | An authoring decision, not an authorization one — see [Considered and declined](#considered-and-declined-2026-08-20) |
| CloudPe baseline: same TOS/SLA standards, or its own? | **Owner decision.** CloudPe is a LeapSwitch brand (MSA Clause 3; TOS §12), and four CloudPe-branded documents sit in the source material — but the CloudPe TOS carries **no liability cap and no arbitration clause**, while both TOS standards cite the Leapswitch-branded document. A CloudPe TOS uploaded as `document_type=TOS` would therefore deviate on `LIABILITY-TOS-001` and go MISSING on `ARBITRATION-TOS-001`. Registered, not resolved |
| LeapSwitch NDA template (as Disclosing Party) | **Missing source document.** The only NDA in hand is counterparty-executed paper with LeapSwitch as Receiving Party; the owner designated it the NDA baseline on 2026-08-19, and the direction caveat stands unclosed until a LeapSwitch-issued template exists |
| Categorical-value evaluator (governing-law *value*, forum *value*) | V2 engine decision |
| Uptime %-tier standards (per-service tables) | modelling decision — multi-scope values |
| Cross-document unification items in the owner's register (C-04, C-05, C-23…) | management decisions, per that register's own tracker |

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

## Requirements by document type

### MSA — 8 Requirements (source: `MSA.pdf`, Leapswitch MSA v2 July 2025)

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

### TOS — 6 Requirements (source: `TOS-leapswitch.pdf`, 26 Feb 2026)

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| LIABILITY-TOS-001 ✅existing | Limitation of liability | 12 months, total fees | §13 | NUMERIC |
| LATE-FEE-TOS-001 | Late-payment interest | **5 % per month** | §7 | NUMERIC |
| DATA-RETRIEVAL-TOS-001 | Post-termination retrieval | **7 days** | §16 | NUMERIC |
| KYC-RETENTION-TOS-001 | KYC record retention | **5 years** | §8 | NUMERIC |
| FORCE-MAJEURE-TOS-001 | FM termination trigger | **60 consecutive days** | §15 | NUMERIC |
| GOVLAW-TOS-001 | Governing law clause | present (laws of India) | §22 | PRESENCE |

### SLA — 1 Requirement (source: `SLA-leapswitch.pdf`; CloudPe SLA states the same value)

| Code | Clause | Standard | Source | Evaluator |
|---|---|---|---|---|
| CLAIM-WINDOW-SLA-001 | Service-credit claim window | **60 calendar days** | "How to Request a Service Credit" ¶1 | NUMERIC |

Liability remains **not applicable** to SLA — **RULED 2026-08-20 (closes L-13)**: service credits are a remedy, not a liability cap; credit percentages are never read as caps, and no SLA-typed liability standard may be created from them.

### NDA — 6 Requirements (source: `NDA.pdf`, executed 17 June 2026)

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

Liability remains **not applicable** to NDA (owner Q4=A, unchanged). Note the per-type
model resolving the register's C-07 cleanly: MSA survival = 3 years, NDA survival = 2
years — two document types, two positions, no contradiction.

### AUP / Privacy Policy / Order Form / Amendment / DPA — no Requirements in V1

AUP and Privacy Policy are unilateral published policies incorporated by reference;
counterparties do not submit competing ones. Order Form/Amendment are commercial
instruments. DPA: no LeapSwitch DPA template exists. Revisit on demand.

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

## Gaps that remain

| Gap | Needs |
|---|---|
| ~~Mapping/extraction terminology per new Requirement~~ | **SUPPLIED 2026-08-19** (owner tasking) — every ratified file carries mapping/extraction terminology drawn from its cited clause; verified against the real source documents by `tools/verify_terminology.py` (21/21 reproduce their ratified position). `confirm_threshold` stays STRUCTURAL pending 35.10 calibration |
| Categorical-value evaluator (governing-law *value*, forum *value*) | V2 engine decision |
| Uptime %-tier standards (per-service tables) | modelling decision — multi-scope values |
| Cross-document unification items in the owner's register (C-04, C-05, C-23…) | management decisions, per that register's own tracker |

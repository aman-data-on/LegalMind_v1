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

Liability remains **not applicable** to SLA (owner Q5 recommendation; L-13 scope ruling open).

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

## Deviation handling — all clauses

Zero tolerance (manager, 2026-08-19): MATCH → `ACCEPTABLE` · any DEVIATION →
`UNACCEPTABLE` → Legal Decision · nothing auto-approved. Wired via the
`deviation_outcome` Legal Rule key (2026-08-19). Categorical value comparison
(e.g. "India" vs "Singapore" as *values*) needs a new evaluator type — **out of V1
scope**; presence Requirements verify the clause exists, and its content goes to Legal
with the evidence.

## Gaps that remain

| Gap | Needs |
|---|---|
| Mapping/extraction terminology per new Requirement | configuration work (unstarted — publishable only once supplied) |
| Categorical-value evaluator (governing-law *value*, forum *value*) | V2 engine decision |
| Uptime %-tier standards (per-service tables) | modelling decision — multi-scope values |
| Cross-document unification items in the owner's register (C-04, C-05, C-23…) | management decisions, per that register's own tracker |

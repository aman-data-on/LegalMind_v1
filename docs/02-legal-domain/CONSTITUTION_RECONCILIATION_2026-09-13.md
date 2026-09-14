# Legal Constitution L1.10 → LegalMind — audit and reconciliation report (2026-09-13)

**Status: 📁 ANALYSIS / handoff.** Written for the owner and for Counsel. Decisions live in
`all_lock.md` (AB-20, `AM-59`–`AM-62`); this file records what was inspected and found. Source:
[LEGAL_CONSTITUTION_L1.10.md](LEGAL_CONSTITUTION_L1.10.md) (2058 lines, the owner-supplied
Lawyer Review Version L1.10, counterparty names redacted), compared with
[LEGAL_CONSTITUTION_L1.5.md](LEGAL_CONSTITUTION_L1.5.md) and with the 32 ratified standards.

## A. Inventory — every stated position, by section

Legend — kind: NUMERIC (a value) · PRESENCE (must exist / must not) · QUALITATIVE (not
machine-checkable) · NO-POSITION (the text says none exists). Force: the Constitution's own
signal word. Standard: the ratified code, or NONE.

| § | Position (verbatim value) | Kind | Force | Status | Standard |
|---|---|---|---|---|---|
| 9 | cap "twelve (12) months" of total fees paid or payable, mutual | NUMERIC | mandatory ("final, closed") | SC / CVP | LIABILITY-MSA-001, LIABILITY-TOS-001 |
| 9 | no separate multiplier or super-cap approved | PRESENCE (must-not) | mandatory | SC / CVP | NONE (see B-1) |
| 9 | cap applies mutually | PRESENCE | mandatory | SC / CVP | NONE |
| 9 | indirect/incidental/consequential damages excluded, both parties | PRESENCE | mandatory | SC / CVP | LIAB-EXCLUSIONS-MSA-001 |
| 9 | longer cap "e.g. 18 or 24 months" mutually | NUMERIC | Negotiable / Approval Required | SC / CVP | NONE (no negotiable band exists in any standard) |
| 9 | uncapped, or one-party cap | PRESENCE (must-not) | Unacceptable | SC / CVP | LIABILITY-*-001 `unlimited_phrases` (partial) |
| 10 | company indemnity: third-party IP, gross negligence, wilful misconduct | PRESENCE ×3 | mandatory | SC / CVP | INDEMNITY-MSA-001 (presence only) |
| 10 | customer indemnity: content, unlawful use, conduct, AUP, breach of law | PRESENCE ×5 | mandatory | SC / CVP | INDEMNITY-MSA-001 (presence only) |
| 10 | broader/narrower/unilateral indemnity without approval | QUALITATIVE | Unacceptable | SC / CVP | NONE |
| 11 | uptime "e.g. 99.9%" shared/VPS, "99.95%+" dedicated | NUMERIC | tiering mandatory, values illustrative | SC / CVP | NONE |
| 11 | credits "10% / 25% / 50% of the monthly fee", single schedule | NUMERIC | mandatory | SC / CVP | NONE |
| 11 | credits are the sole financial remedy; pre-estimate of loss except data loss | PRESENCE | mandatory | SC / CVP | NONE |
| 11 | claims "must be submitted within 30 days" | NUMERIC | mandatory | SC / CVP | CLAIM-WINDOW-SLA-001 |
| 11 | negotiable band "NOT DEFINED" | NO-POSITION | — | SC / CVP | — |
| 12 | Data Fiduciary / Data Processor roles | QUALITATIVE | mandatory | SC / Legal Review Required | NONE |
| 12, 19, 28.6 | CERT-In report "within 6 hours" | NUMERIC | mandatory, "fixed by law" | Applicable Law | NONE (statute restated — not a standard, CLAUDE.md) |
| 12, 19 | system logs "180 days" in India | NUMERIC | mandatory | Applicable Law | NONE |
| 12, 19 | customer registration "5 years" | NUMERIC | mandatory | Applicable Law | KYC-RETENTION-TOS-001 (TOS only) |
| 12, 19 | data residency for "India-designated services" | PRESENCE | mandatory (term undefined) | SC | NONE |
| 12, 19 | sub-processors disclosed and bound "no less protective" | PRESENCE | mandatory | SC | NONE |
| 12 | vendor breach notification weaker than 6 hours may be accepted commercially | NUMERIC | Negotiable | SC | NONE |
| 12 | no residency or "no defined breach-notification timeline at all" | PRESENCE (must-exist) | Unacceptable | SC | NONE |
| 12.3-B | DPDP breach-notification deadline | NO-POSITION ("SOURCE VERIFICATION REQUIRED") | — | AL, unresolved | — |
| 13 | terminate for convenience "30 days' written notice" (non-fixed-term) | NUMERIC | mandatory | SC / CVP | NONE → proposed CONVENIENCE-NOTICE-MSA-001; TERM-NOTICE-NDA-001 nearest |
| 13 | cure "30-day cure period" | NUMERIC | mandatory | SC / CVP | CURE-PERIOD-MSA-001 |
| 13 | immediate suspension for non-payment, security threats, illegal use | PRESENCE ×3 | conditional | SC / CVP | NONE |
| 13 | data retrieval "30-day window", "free of charge" | NUMERIC + PRESENCE | mandatory | SC / CVP | DATA-PURGE-MSA-001, DATA-RETRIEVAL-TOS-001 (window only) |
| 13 | window shorter than 30 days, or billing for it | NUMERIC + PRESENCE | Unacceptable | SC / CVP | `constitution_boundaries.py` (window only) |
| 14 | no early exit; "full committed-term value remains payable" | PRESENCE + formula | mandatory | APPROVED / CVP | EARLY-TERM-RESTRICTION-MSA-001 (presence only) |
| 14 | dual statement: required position + enforceability is Counsel's (ss. 73–74) | QUALITATIVE (runtime rule) | mandatory | APPROVED / CVP | NONE — see §29.1.1 |
| 15 | confidentiality mutual | PRESENCE | mandatory | SC / CVP | NONE |
| 15 | two-part definition (marked OR reasonable person) | PRESENCE | mandatory | SC / CVP | NONE |
| 15 | survival "3 years" / "three (3) years" | NUMERIC | mandatory | SC / CVP | CONF-SURVIVAL-MSA-001, CONF-SURVIVAL-NDA-001 |
| 15 | trade secrets: as long as they remain trade secrets | PRESENCE | mandatory | SC / CVP | TRADE-SECRET-CARVEOUT-NDA-001 |
| 15 | residual-knowledge clause | PRESENCE | mandatory | SC / CVP | RESIDUALS-NDA-001 |
| 15 | non-solicitation "2-year", employees and customers/partners | NUMERIC | mandatory | SC / CVP (enforceability) | NON-SOLICIT-NDA-001 (NDA only) |
| 15 | each party retains its IP | PRESENCE | mandatory | SC / CVP | IP-OWNERSHIP-MSA-001 |
| 15 | one-directional confidentiality | PRESENCE (must-not) | Unacceptable | SC / CVP | NONE |
| 16 | billing "monthly in arrears" | QUALITATIVE | mandatory | SC / CVP | NONE |
| 16 | payment "within 21 days of invoice date" | NUMERIC | mandatory | SC / CVP | NONE → proposed PAYMENT-PERIOD-MSA-001 |
| 16 | interest "2% per month", law-capped | NUMERIC | mandatory | SC / CVP | LATE-FEE-TOS-001 (TOS only) |
| 16 | disputes "within 15 days of the invoice date" | NUMERIC | mandatory | SC / CVP | NONE → proposed DISPUTE-WINDOW-MSA-001 |
| 16 | prices changed "with 30 days' written notice" | NUMERIC | conditional ("may") | SC / CVP | NONE → proposed PRICE-CHANGE-NOTICE-MSA-001 |
| 16 | notice and cure before non-payment suspension | PRESENCE | "should"; length undefined | SC / CVP | NONE → proposed SUSPENSION-NOTICE-CURE-MSA-001 |
| 16 | fees "exclusive of GST", billed separately | PRESENCE | mandatory | SC / CVP | NONE → proposed GST-EXCLUSIVE-MSA-001 |
| 16 | "Net-30", different cure period | NUMERIC | Negotiable / Approval Required | SC / CVP | NONE |
| 16 | suspension with no notice/cure; terms "materially less favorable" | PRESENCE + QUALITATIVE | Unacceptable | SC / CVP | NONE |
| 17, 19 | takedown "3-hour" (CSAM) / "2-hour" (NCII); AI-content labelling | NUMERIC / PRESENCE | mandatory (Applicable Law) | SC / CVP | NONE (AUP is a unilateral policy — CLAUSE_CATALOGUE) |
| 18 | Leapswitch TOS is the Source of Truth; CloudPe services subject to it; refund scope shared/reseller only; unified terms are the end state | PRESENCE | mandatory | SC / CVP | GOVLAW-TOS-001, ARBITRATION-TOS-001 (presence) |
| 20 / 21 | no company PO / Amendment form; analysis rules in §31.11 / §31.12 | NO-POSITION + routing | — | CONFIRMED / N/A | see §31 |
| 22 | governed by "the laws of India"; "courts at Pune"; arbitration under ACA 1996 "seated in Pune", English | PRESENCE (+values) | mandatory | SC / CVP | GOVLAW-*-001, ARBITRATION-MSA/TOS-001 (presence only — values are a V2 categorical evaluator) |
| 22 | arbitration value threshold: evaluate against the agreement's own; never invent one | NO-POSITION + rule | mandatory | SC / CVP | NONE |
| 24.4 | Acceptable · Requires Modification · Needs a Decision, and four clarifications | runtime contract | mandatory | presentation | `AM-56` — **C-20** |
| 31.1 | Pune is the current benchmark venue, for every document type | PRESENCE (+value) | mandatory ("current position, not permanently fixed") | Company-approved | GOVLAW (presence) |
| 31.2 | MSA early exit: full remaining value; a 90-day convenience clause never overrides a committed term | PRESENCE + rule | mandatory | RESOLVED / CVP | EARLY-TERM-RESTRICTION-MSA-001 |
| 31.3 | Partner: convenience termination "at least 30 days'" notice, no fee | NUMERIC | mandatory | Company-approved | NONE (no Partner standards) |
| 31.4 | Partner tiers only for Partner/Reseller/Distribution; never flag an end-customer agreement for lacking them; historical thresholds are evidence only | PRESENCE + rule | mandatory | Company-approved | NONE |
| 31.5 | Partner non-circumvention during term | PRESENCE | mandatory | Company-approved | NONE |
| 31.6 / 31.6a | Partner two-tier support; L1/L2/L3 "NOT CURRENTLY ADOPTED — must not be flagged" | PRESENCE / NO-POSITION | mandatory prohibition | Company-approved / NOT ADOPTED | NONE (basis NOT_ADOPTED reserved) |
| 31.7 (heading missing) | Partner trademark licence, limited, non-exclusive, royalty-free | PRESENCE | mandatory | Company-approved | NONE (see B-2) |
| 31.8 | Partner termination consequences: cease use; invoices due "within 15 days"; commissions; transition "capped at 30 days"; return CI | NUMERIC + PRESENCE | mandatory | Company-approved | NONE |
| 31.9 | Vendor Agreement — eleven "should" rules; pricing notice "commonly 30-60 days" | PRESENCE / QUALITATIVE | "should"; practice-based | LegalMind Rule, provisional | NONE (deliberately — §24.4(3)) |
| 31.10 | Distribution Agreement — eleven "should" rules; revenue share "not fixed here" | PRESENCE / NO-POSITION | "should"; practice-based | LegalMind Rule | NONE (deliberately) |
| 31.11 | PO: contents; payment by reference to MSA; binding on written acceptance (Company-approved); references its MSA; MSA prevails (Company-approved); changes per §31.14; confidentiality by reference | PRESENCE ×7 | mixed | Company-approved / LegalMind Rule | NONE → proposed PO-MSA-REFERENCE-, PO-PRECEDENCE-ORDER_FORM-001 |
| 31.12 | Amendment: written, signed by both (Company-approved); limited to named clauses; effective date; prevails only as to amended terms (Company-approved); version reference | PRESENCE ×6 | mixed | Company-approved / LegalMind Rule | NONE |
| 31.13 | Other agreements evaluate against §§9–22; no Statements of Work | routing | mandatory | Company-approved | — |
| 31.14 | policy change: 30-day objection window; CoC notice "within 30 days" (MSA/Vendor/Distribution), no automatic termination, termination right for material adverse risk; pricing 30 days (MSA; Vendor provisional); discontinuation "30 days' advance notice OR … whichever is later"; material change 30 days "where reasonably practicable"; six exceptions | NUMERIC ×5 + PRESENCE | mandatory / conditional | Company-approved / CVP | NONE → proposed CHANGE-OF-CONTROL-NOTICE-, SERVICE-DISCONTINUATION-NOTICE-MSA-001 |
| 31.15 | auto-renew on the same conditions unless "notice of non-renewal at least 30 days before the end of the then-current term"; the PERIOD is negotiable | NUMERIC + NO-POSITION | mandatory / not fixed | Company-approved (3 of 3 MSAs) | **AUTORENEW-MSA-001 reconciled** (`AM-59` r4); AUTORENEW-TOS-001 (presence) |
| 31.16 | status summary; fallback "Insufficient approved information — Legal Review Required" | rule | mandatory | — | rule 15 / UNABLE_TO_EVALUATE |

Sections 1–8 and 23–30 are framework, interpretation and response rules; §28 (Legal Obligation,
Trigger & Consequence) is the statutory framework and has **zero** standards, correctly — a
statute is not a Company Standard (rule 7, `AM-32` r7).

## B. L1.5 → L1.10 — what changed

1. **No numeric value in §§9–22 changed.** The six `AM-43` r4 reconciliations stand.
2. **Status vocabulary:** every "Pending Legal Review / Validation" became "Counsel Validation
   Point" (§6.3's three labels), except §12 ("Legal Review Required — recommended priority").
3. **§22 arbitration threshold:** an open business decision became a runtime rule — evaluate
   against the agreement's own threshold; never invent one; flag for a human.
4. **§12.2 DPA, §20, §21, §21.1:** "pending document, HIGH priority" became "NOT A DEPENDENCY";
   POs and Amendments are reviewable against §31.11/§31.12 whether or not a company form exists.
5. **"Drafting in progress" → "should be updated"** (§12.1, §17, §18) and Appendix C no longer
   flags the live AUP/Privacy/CloudPe TOS corrections as pending — the live-document defects are
   unchanged but no longer marked in the register.
6. **New:** §24.4 (three user-facing statuses, four clarifications), all of §31, Appendix F's
   terminology note. Appendix B's 13 categories are unchanged and contain no §31 subject
   (renewal, PO, amendment, change of control, tiers, non-circumvention, force majeure,
   warranty, set-off have no category).

## C. Constitution-side defects — reported, not resolved (rule 5)

| # | Finding | Where |
|---|---|---|
| B-1 | §9 "no separate multiplier or super-cap approved" sits beside `LIAB-CARVEOUTS-MSA-001` (expects carve-outs PRESENT). `AM-43` r5 keeps them distinct — different subjects. Counsel to confirm. | §9 |
| B-2 | **§31.7's heading is missing.** The trademark licence sits inside §31.6a ("NOT CURRENTLY ADOPTED") yet carries "STATUS: Company-approved"; §31.10 and the ToC cite a §31.7 that does not exist. | §31.6a–31.8 |
| B-3 | §31.15 vs `AUTORENEW-MSA-001` — **reconciled** (`AM-59` r4). | §31.15 |
| B-4 | §8.2 forbids inventing "MSA always wins" unless established in an approved company document; §31.11 states "the MSA prevails — Company-approved" on evidence drawn from customer MSAs (reference documents, Level 5). Same shape in §31.12. | §8.2, §31.11, §31.12 |
| B-5 | §31.5 cites a set-off position "under Section 20"; §20 is Purchase Orders and no section states set-off. | §31.5 |
| B-6 | §31.4's Silver threshold: "Rs. 60,000" MONTHLY in one agreement, "per year" in the other — recorded, unresolved; the whole tier table is "evidence only" yet the STRUCTURE is "expected". | §31.4 |
| B-7 | Duplicated positions with drifting qualifiers: CERT-In 6 hours ×5 (statutory in §12.3/§19/§28.6, "company policy posture" in §28.5); nine distinct "30 days" with no table. | §12, 13, 16, 19, 28, 31 |
| B-8 | Undefined terms in checkable positions: "operationally feasible" (§11), "India-designated services" (§12/§19), "materially less favorable" (§16), "materially broader … unusual" (§10), "a short period" (§31.14), "reasonable transition assistance" (§31.9), "where reasonably practicable" (§31.14). | various |
| B-9 | Applicability contradictions: §31.6a "not applicable to any current document" vs §31.10 "may be used as a starting point"; §28.6's cyber row points contractual reflection at "any future DPA/Order Form (Section 20)" — documents §31.16 calls not a dependency. | §31.6a, §31.10, §28.6 |
| B-10 | Explicitly pending: DPDP breach deadline (§12.3-B, §28.6), cross-border transfers (§27 Item 8), stamp duty (§27 Item 18), BSA s.63 (§27 Item 17), takedown applicability (§27 Item 15 — **contradicts §17's "not an open applicability question"**), DPDP tranches (§27 Items 13/14). Every §27 item "awaiting Counsel Validation". | §27 |
| B-11 | Standards with **no** L1.10 basis: RETURN-DESTRUCTION-MSA/NDA, COMPELLED-DISCLOSURE-NDA, WARRANTY-DISCLAIMER-MSA, FORCE-MAJEURE-MSA/TOS (60 days) — now `constitution.basis: DOCUMENT_ONLY`; the card says "No Constitution position". | standards |
| B-12 | §23.3, §29.1.1 item 3 and Appendix F still say "Sections 9–22" — none was extended to §31, although §24.4 and §31.16 route to it. | §23.3, §29.1.1, App. F |
| B-13 | Four literal strings for one UI status: "REVIEW REQUIRED" (§8.2/§23.2/§23.4/§29.3), "Legal Review Required" (§24.2), "Insufficient approved information — Legal Review Required" (§29.3/§31.16), "Information not found in the approved Legal Mind knowledge base" (§29.3). §24.4 does not say which the UI renders. | §24.4, §29.3 |
| B-14 | §24.4 maps Negotiable deviations to "Requires Modification" and Not-Negotiable ones to "Needs a Decision"; `AM-56` r2 maps every DEVIATION to "Requires modification". **C-20.** | §24.4 |
| B-15 | The committed L1.5 already names the NDA counterparty (§15.5) and one customer; L1.10 named seven and is canonicalised redacted. Removing names from git history is a rewrite no session may do alone — owner item. | §15.5, §31 |

## D. Constitution → code — how a position reaches a verdict (unchanged shape, `AM-43` r2)

Constitution section → ratified standard file (`configuration.constitution` names the section,
topic, basis, expected_when) → `company_standard_version` in a published snapshot → mapping
(lexical, then grounded semantic for every requirement — `AM-60`) → applicability with a recorded
reason (`AM-61`) → deterministic evaluator (with declared unit conversion — `AM-62`) → Finding →
serialized with `requirement.constitution` → card citation "Constitution, Section 9 · Liability";
report coverage shows APPLIED / NOT_APPLICABLE / SAME_POSITION per requirement. The Constitution
itself is never chunked or retrieved; Ask reaches its positions through the published standards
(Domain A) as before.

## E. Coverage — positions with a machine-checkable standard

* Ratified: 32 standards over 14 Constitution positions in §§9, 10, 11, 12, 13, 14, 15, 16, 22
  and §31.15; 8 of the 32 have no Constitution position (`DOCUMENT_ONLY`).
* Approved through the Constitution and ratified 2026-09-13 (`AM-59` r6'): PAYMENT-PERIOD, DISPUTE-WINDOW,
  PRICE-CHANGE-NOTICE, SUSPENSION-NOTICE-CURE, GST-EXCLUSIVE (§16); CONVENIENCE-NOTICE (§13);
  CHANGE-OF-CONTROL-NOTICE (§31.14) — 39 standards in all.
* Still in `proposed/`: PO-MSA-REFERENCE and PO-PRECEDENCE (approved through §31.11, deferred until a PO exists
  to calibrate against — not a business question); SERVICE-DISCONTINUATION-NOTICE (Pending Business Approval).
* Not drafted, deliberately: §11 schedule/tiers (needs a SCHEDULE evaluator, none specified);
  §12/§19 Applicable-Law rows (statute restatements); §17 takedowns (unilateral policy);
  §31.9/§31.10 Vendor/Distribution "should" rules (§24.4(3): only ever "Needs a decision").
* Zero standards for the five document types §31 governs (Partner, Vendor, Distribution, PO,
  Amendment) until the owner ratifies the two ORDER_FORM drafts.

## F. Implemented (AB-20) — files

`analysis/service.py` (gate removed — `AM-60`; `applicable_by_content` with reasons, expectation,
same-position dedupe, NONE→MISSING — `AM-61`), `evaluation/numeric.py` (declared unit conversion —
`AM-62`), `evaluation/constitution_block.py` (new; validated at publish and import),
`api/reporting.py` + `api/serializers.py` (coverage; per-Finding citation), 32 standard files
(+`constitution` block, 6 conversions, 3 unit-term hygienes, AUTORENEW reconciled),
`company_standards/proposed/` (10 drafts + README), `tests/test_mixed_agreement.py` (new),
`tests/test_rd_semantic_corpus.py` (four declared-type modes, "not applied" column), frontend
report table + card citation. Merged: the "Not recorded" fix (`e7da39c`).

## G. Still open — owner / Counsel

Resolved by the owner's clarification of 2026-09-13: C-20 (§24.4 governs — `AM-63`), C-21 (moot —
`AM-64`), ratification of Constitution-derived standards (through the Constitution — `AM-59` r6').

1. **Older signed documents for reference testing** — please share a Drive link when convenient:
   the three MSAs §31.15 cites, the two Partner Agreements §31.3–31.8 cite, and any PO or
   Vendor/Distribution agreement. They will be used as historical evidence and calibration only,
   validated against the current Constitution, never as a position.
2. **A real or anonymised Purchase Order** — activates the two §31.11 drafts.
3. **Business ruling** on SERVICE-DISCONTINUATION-NOTICE-MSA-001 (how the two limbs of §31.14's
   compound position compare), or a future Constitution update stating one.
4. **Confirm or retire** the eight standards with no Constitution position (FORCE-MAJEURE-MSA/TOS,
   WARRANTY-DISCLAIMER, COMPELLED-DISCLOSURE, RETURN-DESTRUCTION-MSA/NDA, LIAB-CARVEOUTS,
   TRADE-SECRET…): they rest on LeapSwitch's own templates, which §7.1 treats as reference
   documents. They remain active under the 2026-08-19/20 rulings and the card says "No Constitution
   position" — a future Constitution update either states them or they go.
5. The counterparty names in the committed L1.5 (B-15) — a history question, not a rule.
6. Everything in C above for Counsel — in particular B-2, B-4, B-5, B-10.
7. Deployment: the 39 standards need re-import + publish (a new snapshot) to reach the live database.

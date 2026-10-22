# Missing clauses on an MSA — must-have or "consider"? (PROPOSAL)

> 📁 **PROPOSAL — decides nothing.** Drafted 2026-10-21 at the owner's request ("how does a
> lawyer really behave"). Nothing here is live. LegalMind's legal positions stay the
> Constitution's; this proposes only **how loudly a missing clause is reported**. Legal
> confirms or corrects each row; only then is it wired.

## Why

A contract lawyer checks what a contract says, then what it leaves out — but not every
gap is equal. A missing liability cap is a "must add before signing"; a missing
change-of-control notice is a "consider adding". Today LegalMind reports **every** missing
clause of the document's own type the same way: *Requires modification*. The Constitution
states each position but does not rank them (its §27 checklist is about Counsel
validation, not priority), so the ranking below is a **proposal for Legal**, not a
position (rule 7).

## Proposed reporting

| Tier | What the reader sees | Status |
|---|---|---|
| **Must have** | "Missing — must be added before signing" | Requires modification (as today) |
| **Consider** | "Not covered — consider adding (Legal decides)" | Needs a decision |
| Another document type's standard | "May not apply to this document — Legal to confirm" | Needs a decision (live on this branch, `AM-168`) |

## The 22 MSA standards — proposed tier (Legal: confirm or change each)

| Standard | Constitution | Proposed | Why a lawyer would rank it so |
|---|---|---|---|
| Liability cap (`LIABILITY-MSA-001`) | §9 | **Must have** | Uncapped liability is the Constitution's own Unacceptable Position |
| Liability exclusions — indirect/consequential (`LIAB-EXCLUSIONS-MSA-001`) | §9 | **Must have** | Without it the cap covers all loss types |
| Data-loss exclusion (`DATA-LOSS-EXCLUSION-MSA-001`) | §9 | **Must have** | Stated by the manager as the company's position (L1.14) |
| Indemnity (`INDEMNITY-MSA-001`) | §10 | **Must have** | Core risk allocation |
| Governing law (`GOVLAW-MSA-001`) | §22 | **Must have** | Without it, which law applies is itself a dispute |
| Dispute venue (`DISPUTE-VENUE-MSA-001`) | §22 | **Must have** | Pune courts/seat is the company's position |
| Payment period (`PAYMENT-PERIOD-MSA-001`) | §16 | **Must have** | Cash flow; no period = no default date |
| Suspension for non-payment with notice/cure (`SUSPENSION-NOTICE-CURE-MSA-001`) | §16 | **Must have** | Our remedy for non-payment (see C-28) |
| Convenience notice (`CONVENIENCE-NOTICE-MSA-001`) | §13 | **Must have** | How either side can leave |
| Cure period (`CURE-PERIOD-MSA-001`) | §13 | **Must have** | Termination for breach needs it |
| Data retrieval/purge window (`DATA-PURGE-MSA-001`) | §13 | **Must have** | A window under 30 days is an Unacceptable Position |
| IP ownership (`IP-OWNERSHIP-MSA-001`) | §15 | **Must have** | Our platform's IP must stay ours |
| Confidentiality survival (`CONF-SURVIVAL-MSA-001`) | §15 | **Must have** | Confidentiality ending with the contract is a common gap |
| Early-exit restriction on a fixed term (`EARLY-TERM-RESTRICTION-MSA-001`) | §14 | **Must have** *(fixed-term only)* | Unsecured committed fees (applies only when a term is committed — already gated) |
| GST exclusive (`GST-EXCLUSIVE-MSA-001`) | §16 | Consider | Usually in the order form or invoice |
| Late interest (`LATE-INTEREST-MSA-001`) | §16 | Consider | Useful; enforceability limited (s.74) |
| Billing dispute window (`DISPUTE-WINDOW-MSA-001`) | §16 | Consider | Helpful, not deal-critical |
| Price-change notice (`PRICE-CHANGE-NOTICE-MSA-001`) | §16 | Consider | Matters on longer terms |
| Auto-renewal (`AUTORENEW-MSA-001`) | §31.15 | Consider | A term can lapse without one |
| Change-of-control notice (`CHANGE-OF-CONTROL-NOTICE-MSA-001`) | §31.14 | Consider | Relevant to larger customers |
| Service discontinuation (`SERVICE-DISCONTINUATION-MSA-001`) | §31.14 | Consider | Relevant where services may be retired |
| Arbitration (`ARBITRATION-MSA-001`) | §22 | Consider | Courts at Pune already cover disputes |

Standards written for **other** document types (NDA residuals, trade-secret carve-out, KYC
retention…) are not on this list: on an MSA they are "May not apply — Legal to confirm".

## How it would be wired (after Legal confirms)

One configuration key per standard, `missing_tier: "MUST" | "CONSIDER"`, read only when the
clause is **missing**; the engine's classification stays MISSING either way (rule 15). The
reader's words and status follow the table above. Same procedure for the other document
types once Legal has ranked them.

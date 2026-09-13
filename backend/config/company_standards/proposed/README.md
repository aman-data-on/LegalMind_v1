# Proposed Company Standards — awaiting ratification

Drafted 2026-09-13 under `AM-59` r6 from the Legal Constitution L1.10's own words (`§16`,
`§13`, `§31.11`, `§31.14`). **Nothing in this directory is live**: the importer, the assist
index and every verifier read `../*.json` only. A file becomes a ratified standard when the
owner sets `ratified` to the date of approval and moves it up one directory — rule 21 (supplied
source, human approval), never by a session.

| Code | § | Position | Evaluator | Calibration |
|---|---|---|---|---|
| PAYMENT-PERIOD-MSA-001 | 16 | 21 days of invoice date | NUMERIC | live paper states no day-count → a person |
| DISPUTE-WINDOW-MSA-001 | 16 | 15 days | NUMERIC | 15 / 3 calendar days seen live (basis: receipt, recorded) |
| PRICE-CHANGE-NOTICE-MSA-001 | 16 | 30 days' notice | NUMERIC | outstanding |
| SUSPENSION-NOTICE-CURE-MSA-001 | 16 | notice + cure before suspension | PRESENCE | live 'without prior notice' vetoed |
| GST-EXCLUSIVE-MSA-001 | 16 | fees exclusive of GST | PRESENCE | live 'Taxes' clause → UNRESOLVED |
| CONVENIENCE-NOTICE-MSA-001 | 13 | 30 days' notice | NUMERIC | partner agreement 30 days |
| PO-MSA-REFERENCE-ORDER_FORM-001 | 31.11 | PO references its MSA (LegalMind Rule) | PRESENCE | **no PO supplied** |
| PO-PRECEDENCE-ORDER_FORM-001 | 31.11 | MSA prevails (Company-approved; §8.2 tension reported) | PRESENCE | **no PO supplied** |
| CHANGE-OF-CONTROL-NOTICE-MSA-001 | 31.14 | 30 days | NUMERIC | partner papers state a right, no period |
| SERVICE-DISCONTINUATION-NOTICE-MSA-001 | 31.14 | 30 days (notice limb) | NUMERIC | outstanding |

Not drafted, deliberately: §11's 10/25/50 credit schedule and uptime tiers (need a SCHEDULE
evaluator, none is specified); §12/§19's CERT-In, log-retention and residency rows (Applicable
Law restated — a statute is not a Company Standard, CLAUDE.md); §17's takedown deadlines (an
AUP is a unilateral policy nobody submits a competing version of, CLAUSE_CATALOGUE); every
§31.9/§31.10 Vendor and Distribution 'should' rule (practice-based, no company evidence — §24.4(3)
says such a rule can only ever yield 'Needs a decision', so a standard would add noise, not
review).

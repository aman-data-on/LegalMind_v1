# Legal Constitution L1.5 → LegalMind — reconciliation report (2026-09-08)

**Status: 📁 ENGINEERING/LEGAL HANDOFF — companion to [LEGAL_CONSTITUTION_L1.5.md](LEGAL_CONSTITUTION_L1.5.md).**
Written for the owner and for Counsel, in plain language. It records what the Constitution
requires, what LegalMind did before today, what was changed under the owner's ruling of
2026-09-08 (AB-14, `AM-43`–`AM-47`), what was deliberately *not* changed, and what still
needs a lawyer. Decisions live in `all_lock.md`; this file explains them.

---

## A. What the Constitution requires (the rules inspected)

| § | Rule, in one line | Where it now lives in the system |
|---|---|---|
| 3.2 A/B | Analyse an uploaded document against the approved position; answer questions from approved sources only; say "not found" rather than invent | deterministic evaluator (unchanged) · assist lane with router (`assist/routing.py`) |
| 3.3, 25.1 | A normal user may upload, view results, ask questions, escalate; only explicit legal authority approves | RBAC (AB-12) unchanged; `legal_position.view` now also admits Domain A (`AM-44`) |
| 4, 5.2, 23.2 | Entity → Brand → Product → Document Type; never substitute a Leapswitch rule for a CloudPe one | **NOT implemented — C-19 open.** Document Type only |
| 6.1 | Fourteen applicable laws | Seven supplied and ingested as Domain C (`AM-47`); NI Act, Evidence Act/BSA, Arbitration Act, GST Acts, Income Tax Act, Copyright Act, DPDP Rules 2025 **not supplied** |
| 6.2, 6.3, 29.1.1 | Law ≠ company position ≠ legal interpretation; enforceability is Counsel's, never asserted | Kept: statutes are background law (never configuration); positions are quoted verbatim; nothing in the product asserts enforceability |
| 7, 23.1 | Retrieve the Constitution first, then law, then approved documents | Constitution positions enter as ratified standards (Domain A); law is Domain C; the document is Domain B — all three now searched by the question's shape |
| 8.2 | Two approved documents conflict → REVIEW REQUIRED | Intra-document `CONFLICT` only (unchanged) |
| 9 | 12-month total-fees cap, mutual, entity-wide | `LIABILITY-MSA-001` reconciled to 12 months FEES_PAID; TOS already 12. Mutuality **not** evaluated (no party-symmetry evaluator) |
| 11 | 10/25/50 credits; 30-day claim window | `CLAIM-WINDOW-SLA-001` → 30 days. Credit schedule/uptime: no standard (needs mapping calibration, `AM-43` r6) |
| 12, 19 | CERT-In 6 h, 180-day logs, 5-year registration, India residency, sub-processors | 5-year registration exists (`KYC-RETENTION-TOS-001`); the rest have no standard; the CERT-In text itself is answerable from Domain C (verified live: "6 hours", cited) |
| 13 | 30-day notice; 30-day cure; 30-day free data retrieval before deletion | Cure exists (30). Retrieval → 30, purge → 30 (reconciled). Convenience notice: no standard |
| 14 | Full committed-term value; state enforceability as unconfirmed | `EARLY-TERM-RESTRICTION-MSA-001` presence only; enforceability caveat not rendered as a field |
| 15 | Mutual confidentiality; 3-year survival; trade secrets indefinite; 2-year non-solicit; residuals | NDA survival → 3 years (reconciled); the rest already matched |
| 16 | 21-day due; 2 %/month; 15-day dispute; 30-day price notice; notice-and-cure | Late fee → 2 % (reconciled); the other four have no standard |
| 17 | AUP a separate rule set; 3 h / 2 h takedowns | No AUP standards (an AUP produces no Finding) |
| 22 | India; Pune courts; arbitration seated in Pune; Bombay HC | `GOVLAW-*`/`ARBITRATION-*` presence only — forum not checked |
| 23.3–23.5 | Outcome + reason + citation; never fabricate a citation | Findings unchanged; assist citations mechanically verified; **new:** Domain C cites Act + section |
| 24 | Accepted / Deviation; Negotiability an attribute; **24.1 Risk Level**; 24.2 Legal Review Required distinct; 24.3 Finding ≠ decision | MATCH/DEVIATION + fail-closed states kept. Negotiability = the human path the zero-tolerance rule already routes to (no `RuleOutcome` change). **Risk Level not implemented — see D** |
| 29.2, 29.3 | Nine prohibitions; "Insufficient approved information" | Grounding, verification, no Level-5 corpus, **new** verdict screen on generated text; refusal wording per route (`AM-46`) |

## B. Existing approved decisions this respects unchanged

`AI-01` · `AM-25` r1–r3, r5–r9 · `AM-32` r1–r4, r6–r10 · zero-tolerance Legal Rule (2026-08-19/20) · `AM-33` · 36.10 / rule 12 · owner Q9 + `AM-34` for **analysis** · AB-12 personas · 45B.26 · rule 21 · rule 22.

## C. Conflicts discovered

| # | Constitution | System before today | Kind |
|---|---|---|---|
| C-18 | 12 mo total fees (MSA) · 2 %/mo · 30-day claim · 30-day retrieval · 30-day purge · 3-yr NDA survival | 6 mo affected-services · 5 %/mo · 60 · 7 · 15 · 2 yr — each what the **live LeapSwitch paper** says | value |
| — | §23.1 retrieve the Constitution first | Ask searched the document only; Domain A had zero callers | build gap |
| — | §3.2B/§25.1 users ask about the company's position | `AM-32` r5 required `configuration.view`, which a Department User never holds | permission |
| — | §29.3 refuse honestly | Ask refused questions the document answered (heading-polluted index) | defect |
| — | §24.1 Risk Level | Forbidden by 36.10 / rule 12; **and undefined by the Constitution's own §23.4** | Constitution gap |
| C-19 | §4/§5.2 Entity/Brand | No axis in the data model | schema gap |

## D. Conflicts resolved (and how)

* **C-18 — resolved by owner ruling (`AM-43` r1, r4).** The Constitution's value replaces the live paper's in six standard files; each file keeps the previous source, clause, quote and configuration in `_history`. **Consequence you must know:** LeapSwitch's own live TOS, SLA, NDA and MSA template now evaluate as **DEVIATION** on these six points (MSA §17.2: **UNABLE_TO_EVALUATE**, incomparable basis). The Constitution itself says those drafting corrections are "in progress".
* **Domain A wired; permission basis amended (`AM-44`).** `assist.ask` AND (`configuration.view` OR `legal_position.view`). Positions are quoted verbatim, never paraphrased, never sent to the model.
* **The router (`AM-45`).** No source selector. The caller's permissions bound the candidate sources first; the question's shape picks among them. Comparison questions go to the deterministic evaluator's Findings with a link.
* **Refusals (`AM-46`).** One wording per searched set; a statute question with no corpus says so; with a corpus that lacks the Act, it names what the corpus holds.
* **Retrieval defect.** `clause-aware-3`: headings travel with their clause; U+200B/NBSP are blanks. Verified live: "Who are the parties?" and "What is the liability cap?" now answer with page + section citations on a real MSA.
* **Domain C (`AM-47`).** Built over the seven supplied statutes with their provenance stated as it is. Verified live: *"What does Section 43A of the IT Act say?"* → answered, cited *The Information Technology Act, 2000, s. 43A — Compensation for failure to protect data*.
* **§24.1 Risk Level — resolved by NOT implementing (`AM-43` r3).** The Constitution names a scale and no assignment rule; its own §23.4 forbids inferring one. 36.10 stands. **For Counsel:** either define the rule per category or drop §24.1.
* **§24 Negotiability — no change needed (`AM-43` r3).** Both the Constitution and the engine send every deviation to a human; they differ only in label.

## E. Effective values after reconciliation

| Standard | Type | Effective value | Source |
|---|---|---|---|
| LIABILITY-MSA-001 | MSA | 12 months, total fees paid (FEES_PAID) | Constitution §9 |
| LIABILITY-TOS-001 | TOS | 12 months, total fees paid | TOS §13 (agrees with §9) |
| LATE-FEE-TOS-001 | TOS | 2 % per month | Constitution §16 |
| CLAIM-WINDOW-SLA-001 | SLA | 30 days | Constitution §11 |
| DATA-RETRIEVAL-TOS-001 | TOS | 30 days | Constitution §13 |
| DATA-PURGE-MSA-001 | MSA | 30 days | Constitution §13 |
| CONF-SURVIVAL-NDA-001 | NDA | 3 years | Constitution §15 |
| Legal Rule (all) | — | zero tolerance: MATCH → ACCEPTABLE; any DEVIATION → UNACCEPTABLE → Legal Decision | unchanged |

⚠️ **The owner's worked example read "existing 12, Constitution 6 → 6". The Constitution says 12 (§9); the MSA template said 6. The Constitution was followed.**

## F. Implemented fixes (files)

Backend: `assist/chunking.py` (clause-aware-3) · `assist/intent.py` (new) · `assist/routing.py` (new) · `assist/statutes.py` (new) · `assist/service.py` · `assist/positions.py` · `api/routers/assist.py` · `config/company_standards/` (six files) · `config/statutes/registry.json` (new) · `tools/ingest_statutes.py` (new) · corpus fixtures + `corpus_coverage.json`.
Frontend: `AskDock.tsx` (`PositionsSection`, `StatutesSection`, `ComparisonHandoff`, null contract) · `TranscriptTurn.tsx` · `UploadContract.tsx` (type no longer gates) · `types.ts` · `api.ts` · `workspace.css` · `dashboard/research/page.tsx` (real Ask) · placeholders retired.
Records: `all_lock.md` AB-14 (`AM-43`–`AM-47`) · `LOCKED_DECISIONS.md` · `CONFLICTS.md` (C-18, C-19) · `CLAUSE_CATALOGUE.md` · `IMPLEMENTATION_STATUS.md` · `LEGALMIND_PROJECT_STATE.md` · `CHANGELOG.md` · `CLAUDE.md` · `docs/README.md`.

## G. Deferred, and why

| Item | Why deferred |
|---|---|
| Re-index of real users' contracts | An operator step after deploy (the running API was not restarted; the owner forbade touching live data). Only the test account's documents were re-indexed |
| Publishing the six reconciled standards into the live DB (`import_ratified_standards --publish` + `chunk_standards`) | Same reason — it would change what the live API evaluates against before deploy |
| Entity/Brand axis (C-19) | Schema decision with owner-visible consequences for every standard's scope |
| Constitution positions with no standard (`AM-43` r6) | Locked 35.10: mapping rules must be calibrated against a representative set before a standard is trusted; not manufactured in a day |
| Mutuality (§9/§10/§15) | No party-symmetry evaluator exists |
| NI Act / Evidence Act | Never supplied (C-16). Rule 21: never fetched |
| Statute vectors as first-class retrieval | Lexical-first with exact-section ranking; vectors are written best-effort and can join once measured (`AM-32` r9) |

## H. Tests proving the fixes

`tests/test_assist_indexing.py` (+4: heading folding, lossless, trailing heading, U+200B) · `tests/test_assist_intent.py` (30-phrase matrix) · `tests/test_assist_routing.py` (10) · `tests/test_positions.py` (permission basis) · `tests/test_assist_statutes.py` (10, incl. the real IT Act §43A) · `tests/test_assist_ask.py` (+13: verbatim positions, no payload leak, permission exclusion, refusal wording, document-less API, replay, statute answers, separated sections, injected verdict) · golden corpus + coverage (re-expected) · frontend `ask-pane.test.tsx` (+3).

## I. Remaining owner / legal decisions

1. **Counsel:** validate the six reconciled positions (they are the Constitution's; enforceability is Counsel's call) and decide §24.1 Risk Level.
2. **Owner:** supply the NI Act and choose Evidence Act 1872 vs BSA 2023 (C-16); supply the other §6.1 laws if Domain C is to hold them.
3. **Owner:** the Entity/Brand axis (C-19) — shape and scope.
4. **Owner:** confirm India Code re-verification of the seven statutes, or accept the stated provenance.
5. **Operator (after deploy):** re-index all contracts (`clause-aware-3`); publish the six standards; chunk Domain A.

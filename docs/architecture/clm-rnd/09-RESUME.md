# CLM programme — where we stopped and how to continue

*Hand-off note. Kept current at the end of every work unit. Last updated 2026-11-04 (end of day).*
**Committed and pushed as three DRAFT PRs (2026-11-04); nothing merged, nothing deployed. The live server was never touched.**

## Git state (2026-11-04, git agent)

| Branch | PR | Commits | CI |
|---|---|---|---|
| `research/clm-contract-creation-20261102` | [#285](https://github.com/aman-data-on/LegalMind_v1/pull/285) | R&D docs 00–09; merge of `origin/main`; docs/README links every clm-rnd file; docs 10–11 and this section | green (job 16 fixed by indexing every file) |
| `records/clm-amendments-20261102` | [#286](https://github.com/aman-data-on/LegalMind_v1/pull/286) | AB-150…AB-160 (`AM-250`…`AM-306`, `AM-300` skipped) + registry; merge of `origin/main` (`all_lock.md` = main's 27,678 lines byte-identical + 1,198 appended = 28,876; C-29 main, C-30 ours) | green |
| `feat/clm-p1-negotiate` | [#287](https://github.com/aman-data-on/LegalMind_v1/pull/287) | schema · drafting · negotiation · tests · frontend · records; merge of `origin/main` (kept `review_anyway` + `recognition`/`after_commit`, `paper_kind_of` + `contract_principals`); CI fixes (LibreOffice skip, e2e `/contracts` URLs) | jobs 1–13 green incl. 3 and 13; **job 14** npm audit (known, main too); **job 15** visual baselines and **Browser workflows** (40 of 172 e2e) fail on the redesigned UI |

**Still to do:**
- The UI agent updates the e2e specs and visual baselines for the redesigned screens. These are locator and copy changes ("Points", "New contract", the `/contracts` pages), not flakes. Adopt CI's baseline images after checking them; never `--update-snapshots` locally.
- `all_lock.md` must be re-appended after whichever of #284 (AB-147/`AM-300`) and #286 merges first.
- Each phase's builder work gets committed when the coordinator calls the git agent.
- Merging into main and deploying need the owner.

## 1. What exists (three uncommitted worktrees)

| Worktree | Branch | Holds |
|---|---|---|
| `/root/legalmind-worktrees/clm-rnd-20261102` | `research/clm-contract-creation-20261102` | R&D: `docs/architecture/clm-rnd/` 00 report · 01–04 workstreams · 05 verification ledger · 06 plan · 07 Phase 1 requirements · 08 UI design record (every page + critic rounds) · **09 this file**; CLAUDE.md "Product first" |
| `/root/legalmind-worktrees/clm-records` | `records/clm-amendments-20261102` | Lock records appended to `all_lock.md` (28,608 lines): AB-150 (AM-250–279), AB-151 (AM-280/281), AB-152 (AM-282–293), AB-153 (AM-294), AB-154 (AM-295), AB-155 (AM-296), AB-156 (AM-297), AB-157 (AM-298), AB-158 (AM-299, AM-301, AM-303, AM-304), AB-159 (AM-302), AB-160 (AM-305, AM-306); registry rows; C-19 resolved; C-30 |
| `/root/legalmind-worktrees/clm-p1` | `feat/clm-p1-negotiate` | All code: Phase 1 negotiation + contract creation + lawyer review (see §2); its own `LEGALMIND_PROJECT_STATE.md`, `IMPLEMENTATION_STATUS.md`, `CHANGELOG.md`, `DAILY_CHANGED.md` entries |

Approved plan: `/root/.claude/plans/read-all-the-concept-floating-papert.md` (checked against official
Microsoft/ECMA-376, CLM-vendor and Indian-law sources).

## 2. What is built (clm-p1)

- **Negotiation (Phase 1):** Changes page, per-change answers with history, routing (owner / Legal / in our favour),
  formatting-only group with bulk "Keep ours", rewritten clauses as blocks, "Prepare our reply" (client's DOCX
  with our tracked changes + Word comments for anything to restore by hand), deal stages, To-do, notifications,
  colleagues, Ask files a returned copy.
- **Lawyer tools:** Write our wording / Use our standard, note to client (Word comment) + internal note (Legal
  only), access to contracts sent to Legal, second person on your own contract, decisions carried into the reply
  when text is unchanged, nothing undecided downloadable or sendable.
- **Document engine:** templates + clause library, enterprise DOCX (style numbering, `REF \w \h`, tables,
  images, schedules, execution block, doc ID, Page X of Y), clean copy, preflight, LibreOffice PDF **made in the
  worker** (version recorded; 202 "Preparing…", 503 PDF_NOT_MADE).
- **Templates:** reference NDA (LeapSwitch, CloudPe) and MSA (LeapSwitch) imported as DRAFT in the scratch DB;
  Template approval page (Approve / Replace with our wording with numbered preview / No position; publish gate).
  The reference NDA fails 5 of our own NDA standards; the MSA fails liability and more.
- **New contract:** type, brand, client with legal details (CIN/PAN/GSTIN…), form with a live locked preview,
  "these points will go to Legal" before Create, v1 reviewed by the same engine.
- **UI:** five pages (Contracts home, Contract page, Changes, Template approval, New contract) each designed one
  at a time with the frontend-design skill, challenged by an independent critic, and fixed; a cross-page
  consistency pass is DONE (server `counts`, `lib/nextStep.ts`, `PageHeader`, `PointStatus`, one PDF helper;
  Templates moved to `/templates`; AB-155 `AM-296`).
- **Migrations (scratch DB only):** `f7c2a9e4b1d6` → `a3c9e7f1b5d2` → `b4d1f8a2c6e3` → `d2a7f4c8e1b3` → `e6b3d9a1c7f5` (executions) → `a8d4c2e6f1b9` (head; executions.origin).
- **Tests:** full backend 5,191 passed; the 1 failure is `test_published_policies`, stale vs main's AB-141 —
  clears when the branch takes main. Frontend 771+ vitest.

## 3. How to run it locally (never the live server)

- Test DB: `set -a && . /root/.legalmind-test.env && set +a` (role `legalmind_test`); scratch app DB =
  `${LEGALMIND_TEST_DATABASE_URL%/*}/legalmind_clm_e2e`.
- API :8399 — script `run_api.sh` (in the session scratchpad; if gone, recreate): exports the test env, sets
  `LEGALMIND_DATABASE_URL` to the scratch DB, `LEGALMIND_STORAGE_ROOT=/root/legalmind-clm-local/storage`,
  `LEGALMIND_MAIL_SINK_DIR=/root/legalmind-clm-local/mail`,
  `LEGALMIND_SOFFICE=/root/legalmind-clm-local/lo/root/opt/libreoffice26.2/program/soffice`,
  `LEGALMIND_ASK_AGENT_MODE=off`, then `uvicorn legalmind.api.app:app --port 8399` from `clm-p1/backend`.
- UI :3399 — in `clm-p1/frontend`: `LEGALMIND_NEXT_DIST=.next-clm LEGALMIND_API_ORIGIN=http://127.0.0.1:8399 npx
  next build` (check `routes-manifest.json` has no `8000`; revert `tsconfig.json`/`next-env.d.ts`), then
  `LEGALMIND_NEXT_DIST=.next-clm npx next start --port 3399`. Owner views it via VS Code Ports → forward 3399.
- Logins: `owner@e2e.test` (salesperson), `counsel@e2e.test` (lawyer, holds decision + approve-customisation),
  `admin@e2e.test` (Lead/admin) — password `Clm-Test-6b83a9e6`.
- Real-data contracts: `9cfb2fe7-f954-46ba-bbfa-df278c996282` (client returned, unanswered),
  `4461b229-68c5-48ae-aeeb-b9c39ed667cf` (answered, reply v3). Fixtures `/root/legalmind-clm-fixtures/`
  (MANIFEST.md, clients A–F, never names). Private DB copies `legalmind_clm_p4b`, `legalmind_clm_p5`
  (hand-published placeholder — screenshots only).
- Kill servers by exact PID only (`ss -ltnp | grep :8399`); never `pkill -f`.

## 4. Next steps, in order

*Current at the end of 2026-11-04. All build work is done; clm-p1 checks (CI shape): see §10.*

1. **Wait for management's reply** on the MSA file (`/root/legalmind-clm-local/msa-for-management/
   LeapSwitch-MSA-template.docx` + `.pdf`): the opening positions (17.2 six months of affected-services
   fees, mutual; 8.5 seven days) and the 17.3 (d)/(e) carve-outs (payment, indemnities outside the cap).
   If (d)/(e) stay, the Constitution §9 needs an amendment first; until then LIABILITY-MSA-001 reads
   CONFLICT for a person (`AM-304`) and the template must not be published. If they go, remove them.
2. **Publish** `MSA.LEAPSWITCH.APPROVED` through the Template approval page (the lawyer approves each
   clause; the gate must pass — never hand-publish outside the demo copy). Then the NDA templates.
3. **Commit on the owner's word only** — clm-p1, clm-records, clm-rnd, staged by explicit path.
4. **Merge `main`** (at `d2a5243` on 2026-11-04, all_lock 27,678 lines, AB-141…AB-146 / AM-243…AM-249 — no
   overlap: append AB-150…AB-160 verbatim after main's AB-146; merge the registry rows; Constitution L1.15;
   main's AM-248 fixes tracker R-3 — re-check), re-run the full suite in CI shape; `test_published_policies`
   clears then. Then PR, CI, release decision.

## 5. Waiting on the owner

- The lawyer approves the NDA template in the Template approval page (5 failing points first), later the MSA.
- Who holds the decision right in production; who the second approver is.
- Official LeapSwitch and CloudPe logo files (SVG / high-res PNG).
- "commit" (then PR, CI, release decision).

## 6. Pre-release list (before anything goes live)

LibreOffice + house fonts (Liberation Serif) + docxcompose on the server · real logos · stamp/authority records ·
merge main + CI green · decide the PyMuPDF (AGPL) internal reading copy · re-check secondary-source legal items
(stamp rate, IT Act schedule, DPDP commencement) on indiacode.nic.in · tracker R-3 (NDA term-notice standard
measured on MSAs) — fixed on main by AM-248, verify after the merge.

## 7. 2026-11-04 — the owner's approved MSA

- Owner shared "Leapswitch MSA - Final - Original - July 2025.docx" (Drive `11XwE43Z1Csv10WDxJHskHuxTPxOpSH5-`; local copy
  `/root/legalmind-clm-fixtures/approved/msa-approved-2025-07.docx`, sha256 `32b461a2…508a`). It is the SAME text as the
  reference MSA v2 (only 1.8/1.9 xrefs blank and a different Leapswitch company in the signature block).
- Imported as DRAFT template `MSA.LEAPSWITCH.APPROVED` (id `3b4c3d13-0137-4dfe-a625-1af8aac91203`, scratch DB only).
- Analysis of 12 MSAs (our paper, client drafts, the one signed deal): our paper is A on all five points; the signed deal
  is B on invoice window + data loss, client's own terms on cap/venue/purge; nobody uses "12 months total fees".
- **Owner decision 2026-11-04: B (our ratified standard) on all five points** — cap 12 months total fees, Pune, data 30
  days then deleted, invoice dispute 15 days, data loss direct+indirect excluded. No lock change (existing rulings).
  Manager message drafted for confirmation (owner sending).
- Pre-filled DRAFT suggestions (Constitution wording verbatim, "Suggested — not approved"): 17.2 cap, new 17.7 data loss,
  19.4 Pune, 7.6.6 data 30 days (needs one reference finished), 8.3 invoice 15 days, new 8.12 late interest, new 8.13
  price-change notice. Still "Wording needed from Legal": change-of-control notice, service discontinuation.
- Flags for the lawyer: signature-block entity, e-mail links to another provider's domain, 1.8/1.9 numbers, 4 undefined
  terms, 17.3 carve-out reads as unlimited.
- Correction: the "90-day data return" clash is in a CLIENT's markup, not our template.
- Engine issues to fix: venue evaluator misreads the Constitution's own "Bombay High Court" wording; the data-purge
  position sentence is not measurable yet.

## 8. 2026-11-04 (later) — MSA template built to the approved format

- **Format** (house.json + render_contract.py + model.py, clm-p1): A4, Times New Roman 12, justified, margins as the
  approved file, two indent ladders (cl. 1–2 and 3+), 6/6 pt front matter/definitions, bold defined terms, front matter
  (title, parties A/B with incorporation line, AND, Party/Parties, WHEREAS, NOW THEREFORE), paired By/Sign execution
  table, footer = page number right + doc ID left 8 pt. Measured within 1 mm of the reference (PyMuPDF). Spec: 08 §
  "MSA house style" + "Round 2". Samples + side-by-side PNGs: `/root/legalmind-clm-local/msa-template/`.
- **Content** (DRAFT rows, scratch DB): B positions stated once (9.9/15.5 narrower data sentences removed), 1.8/1.9
  xrefs, `{business_day_city}`, front matter + execution in the approved file's words, party A per Constitution §4.1.
- **Engine:** venue "no …, then Bombay High Court" no longer read as exclusion (`extraction/categorical.py`, tests);
  DATA-PURGE-MSA-001 measurable (config, tests).
- **Gate still blocked by:** 17.3 (uncaps Customer indemnity — wording from Legal), MISSING change-of-control +
  service discontinuation, undefined Controls/Controlled by/Controlling, PAYMENT-PERIOD misreads 8.6 GST
  "10 days" (engine), KYC-RETENTION-TOS unable, TERM-NOTICE-NDA-001 on an MSA (main AM-248 fixes after merge).
- **Legal flags:** ~~Companies Act 1956 (file) vs 2013 (Constitution)~~ — resolved 2026-11-04: the file's 1956 was right (see §9, party A); helpdesk1 e-mail unpublished; client CIN now required.
- **Remaining format gaps:** underlined run-in sub-headings ("No Tenancy Contract:"), "(VERSION 2)" title line,
  1.10–1.18 tab overflow in the reference, reading view has one ladder.

### Round 3 — word and punctuation changes for the lawyer to approve (DRAFT rows, scratch DB)

Owner rulings 2026-11-04: fix clause numbers and typos ourselves; "Leapswitch" as the party's short name becomes the
defined term “LeapSwitch” (party A defines it); "Leapswitch Networks Pvt. Ltd." (the legal name), the e-mail
domains and 17.7's "Leapswitch/CloudPe" (both) stay as written. Every change, clause by clause:

| Clause | Before | After |
|---|---|---|
| 4.5 | Clause 5 (typed) | Clause {cross-reference → 5, Customer Onboarding} |
| 7.6.6 | in Section 12 (no full stop) | in Clause {cross-reference → 11, Data Protection and Privacy}. |
| 15.5 | under Clause 8.4. (8.4 is TDS, wrong in the file too) | under Clause {cross-reference → 15.4, SLCs per the SLA}. |
| 6.3 | delayed.t any time | delayed. At any time |
| 6.4 | Leaptswitch | LeapSwitch |
| 11.2 | Personal Date | Personal Data |
| 12.2 | Conﬁdential (ﬁ ligature) | Confidential |
| 5.2.3 | "Services\n If" (leading space) | "Services\nIf" |
| 5.6.2 | Agreement.. | Agreement. |
| 7.1 | herein. . | herein. |
| 8.1 | purchase order . Except | purchase order. Except |
| 14.3 | contracts .Leapswitch | contracts. LeapSwitch |
| 9.11 | integrity.” (stray closing quote) | integrity. |
| front: preamble | This Master Service Agreement | This Master Services Agreement (as the title) |
| front: party A | include its, affiliates, successors | include its affiliates, successors |
| 5.1.2 | categorized as a “Partner” under | categorized as a Partner under (owner decision, 2026-11-04: a category, not a defined term) |

The punctuation rows (5.2.3–9.11) are in the approved file too; 7.6.6 is not in it. No other hard-coded clause
number is left. Spelling scan (dictionary + duplicate words): no other typo found; "Cesses", "therefor", "novate",
"referable" are correct legal usage.

Leapswitch → LeapSwitch (count per place): front Party/Parties sentence 1 · recital A 1 · recital C 2 · 1.5 2 · 1.11 3 · 1.12 1 · 1.13 3 · 1.15 1 · 7.2 1 · 7.4 2 · 7.5 1 · 7.6.1 1 · 7.6.5 1 ·
7.6.8 1 · 8.5 1 · 8.6 2 · 8.7 1 · 8.8 1 · 8.9 2 · 8.10 1 · 8.11 1 · 9.1–9.5 1 each · 9.6 2 · 9.7 2 · 9.8 1 · 9.9 1 ·
10.1–10.4 1 each · 12.1 1 · 14.2 2 · 14.3 2 · 16.1 1 · 16.1.5 1 · 16.1.6 1 · 16.2 3 · 17.1 2 · 17.4 2 · 18.2.4 1 ·
21.1 1 · 21.2 1 · 21.7 7 · 21.8 1 · 21.11 1. The defined terms “Leapswitch Data Centre” and “Leapswitch Services”
(1.11, 1.13) become “LeapSwitch Data Centre” / “LeapSwitch Services”, with every use.

Format (round 3): 60 run-in titles underlined as the file sets them (5.2.3's bold), taken from the file's own
underline runs and stored as a sub-clause `title`; 15.5 "Fees During Suspension:" has no underlined match in the file
(its words differ: "Fees and Data During Suspension") and stays plain. Signature table at the file's widths
(1380/3255/1410/3120) and row heights; title-only and lead-in sub-clauses keep with the next line.

## 9. 2026-11-04 evening — demo copy, format rounds 4–5, the "For us" column

**Demo setup (local only, never production).** DB `legalmind_clm_demo`; API :8399 runs from
`run_api_demo.sh` (session scratchpad: test env, `LEGALMIND_DATABASE_URL=…/legalmind_clm_demo`,
`LEGALMIND_STORAGE_ROOT=/root/legalmind-clm-local/storage`, LibreOffice, mail sink, uvicorn from
`clm-p1/backend`). UI :3399 = `clm-p1/frontend`, dist `.next-clm-r5` (`LEGALMIND_NEXT_DIST=.next-clm-r5 npx next
start -H 127.0.0.1 --port 3399`). Template `MSA.LEAPSWITCH.APPROVED` **v3**, hand-published in the demo copy only,
label "DEMO — not approved by Legal" (v1 is frozen by the DB trigger, so a new version was made from the e2e DRAFT
rows; v1 and v2 RETIRED). Demo contract **a5e62213-25a0-4388-95ea-56f654f23400** (owner@e2e.test, Demo Client
Private Limited); PDF `/root/legalmind-clm-local/demo-msa.pdf`. Archived (not deleted): 68b343f5…, 0a342557….
5.1.2 reads "a Partner" unquoted in both DBs (owner decision, 2026-11-04; listed in §8), so "Partner" is no
longer an undefined term. Scripts in the scratchpad `bin/`:
`republish_demo.py` (demo only), `render_demo.py`, `backfill_emphasis.py`.

**Switch :8399 back to e2e:** stop it by exact PID (`ss -ltnp | grep :8399`, `kill <pid>`), then start `run_api.sh`
(§3), or run `run_api_demo.sh` with `legalmind_clm_e2e` in place of `legalmind_clm_demo`. Stop and start :3399 the
same way if its build changed.

**Format, rounds 4–5 (clm-p1, uncommitted):**
- Word compatibility mode **14**, not 15. In mode 15, LibreOffice squeezes spaces in justified lines but prints a
  numbered paragraph's first line unsqueezed, so it ran 3–9 pt past the margin (the approved file does the same).
- A **MARGIN** pre-publish check (`preflight._pdf`): any glyph more than 0.5 pt past the right margin fails the page.
- Signature table: both label columns 1440 tw, so "Date of sign" fits on one line.
- **Reading view** for generated contracts: the parser records each paragraph's house style and its bold/underlined
  words (`emphasis`), and the API exposes `house_style` and `emphasis`. The sheet shows A./B. letters, bold names and
  terms, underlined run-in titles, justified text and both indent ladders. Client paper is unchanged. A contract
  ingested before this shows plain text until re-ingested; the demo contract's rows were back-filled.
- Contract names typed in capitals show in title case in the header and the list (`contractDisplayName`; the stored
  name is unchanged).
- Fonts: static Source Serif 4 **Bold** (latin + latin-ext, OFL) in `src/app/dashboard/fonts/`. The variable file
  drawn at 700 spaced its bold letters unevenly in Chromium. Bold italic is not added (the sheet doesn't use it).

**The "For us" column (AB-158, `AM-299`/`AM-301`, another session's work in clm-p1):** every change on the client's
paper carries `effect_for_us` (Better / No change / Worse for us). The rule is fixed by the change's route; anything
not named reads Worse. The deal owner can accept all "Better for us" or all "No change for us" changes together with
`POST /contracts/{id}/changes/accept` (audited, never a Legal Decision). `carry_acceptances` carries those
acceptances onto our reply's Review only where the reply's clause text is the accepted text exactly. A "Worse for
us" change keeps the Legal gate. A lower liability cap than our standard is Better for us for LIABILITY-MSA-001/TOS-001
(`AM-299` r3). `AM-301`: N months of the affected services' fees is never worse for us than N months of total fees,
in that direction only, and never a MATCH.
**Owner to confirm:** `AM-301`, and the one-way cap rule: a cap that limits one party only is never "Better for us"
(`AM-239` r2, §9).

**Five open points closed from real sources (owner 2026-11-04: "you have the signed MSA, so check it, decide from
what you find there, and resolve").** Sources in order: Constitution L1.15 → the signed MSA (executed 28 July 2026,
the counterparty is never named) → `MSA.pdf` / `MSA-original.pdf` / `MSA-Feb.pdf` → the
published TOS/SLA. New DRAFT clause versions in `legalmind_clm_e2e` (source pass 4, `source.source` names the
section, every word verbatim); demo copy re-hand-published as **v4** (DEMO label kept, v3 RETIRED). Script:
scratchpad `resolve5.py`.

| Point | Clause | Source | Before → after |
|---|---|---|---|
| A | 17.3 (17 v3) | Constitution §9 | "17.3 Exclusions from Limitation: The foregoing limitations shall not apply to the Customer's indemnity obligations …, the Customer's breach of payment obligations, or damages resulting from the Customer's fraud, willful misconduct, or gross negligence." → **removed**; 17.4–17.7 become 17.3–17.6. §9: cap mutual, no one-sided cap, no super-cap; its clause language (17.2) has no carve-out. The signed MSA has no such clause (13.1 excludes only death or bodily injury, on a LeapSwitch-only cap); all three templates carry it. Counsel: a mutual carve-out for what cannot lawfully be excluded (TOS §13 has one; no MSA source states it mutually). |
| B | 21.7 (21 v2) | Constitution §31.14 A, bullets 1–2 | end of 21.7 + "Customer should provide notice of a Change of Control within 30 days, where applicable. A Change of Control should not automatically terminate the agreement." No MSA of ours has a change-of-control clause. Legal: "should" vs "shall"; "Change of Control" undefined. |
| C | 6.6 (6 v2) | Constitution §31.14 Service Discontinuation, Company Position + A bullet 2 | new 6.6 "For planned full service discontinuation/retirement, the Company will provide 30 days' advance notice OR continue the service until the customer's committed contract period ends, whichever is later. Notice should identify: the affected service; expected discontinuation/retirement date; material impact; and any available replacement, migration, or transition option." No MSA of ours has one. |
| D | 8.5 (8 v3) | Constitution §16 clause language | "The Customer shall make payment of tax invoice as per credit period agreed in purchase order." → "Customer shall pay all undisputed invoices within twenty-one (21) days of the invoice date." The signed MSA fixes the period in the MSA (Due Date = 7 days from invoice, 1.1(e)), so the PO is not the practice everywhere. Legal: 8.2, 5.1.2 (Partner, up to 30 days), 5.4.2 still point to other terms. |
| E | — | Constitution §12 | No clause. §12's Legal Basis puts the 5-year customer-registration retention in the CERT-In Directions (28 April 2022): our statutory duty, not a customer term (the signed MSA's 23.4 eKYC clause has no period). **Recommend** `not_applicable_to: ["MSA"]` on `KYC-RETENTION-TOS-001`, for the owner to ratify; the file is unchanged. |

**Publish gate (e2e, read-only, rolled back):** 22 of 23 standards MATCH, including LIABILITY-MSA-001,
CHANGE-OF-CONTROL-NOTICE-MSA-001, SERVICE-DISCONTINUATION-MSA-001 and PAYMENT-PERIOD-MSA-001; no preflight
problem. The one left is KYC-RETENTION-TOS-001 UNABLE_TO_EVALUATE (APPLICABILITY_UNCERTAIN), waiting on point E.
`tests/drafting`: 112 passed, 4 skipped.

**Owner approved the recommendations (2026-11-04) — pass 5** (scratchpad `resolve6.py`; e2e DRAFT rows, demo
re-hand-published as **v5**, DEMO label, v4 RETIRED):

| Clause | Source / ruling | Before → after |
|---|---|---|
| 17.3 (17 v4) | published Leapswitch TOS §13 list, verbatim, made mutual | new 17.3 "Exclusions from Limitation: Nothing in this Agreement shall limit or exclude either Party's liability for: (a) death or personal injury caused by negligence; (b) fraud or fraudulent misrepresentation; or (c) any liability that cannot be limited or excluded under applicable law." (TOS: "Nothing in these Terms shall limit or exclude liability for"). The title is the approved file's. 17.3–17.6 become 17.4–17.7. LIABILITY-MSA-001 still MATCHes: the MSA standard has no `exceptions` configured, so the carve-out is not read as uncapped. No engine change. |
| 17 | owner | **Unpaid fees stay inside the cap.** Whether they should is a commercial question for the manager. |
| 21.7 (21 v3) | owner | "Customer should provide notice …" → "Customer shall provide notice …"; "A Change of Control should not …" → "A Change of Control shall not …" |
| 6.6 (6 v3) | owner | "Notice should identify" → "Notice shall identify" |
| 1.6 (1 v3) | owner's words | new 1.6 "“Change of Control” means a change in Control of the Customer." (alphabetical, after "Business Data"); 1.6–1.18 become 1.7–1.19 |
| 8.2 (8 v4) | Const. §16, owner | "… set out in the Service Order Form." → "… set out in the Service Order Form, subject to Clause 8.5." (8.5 now keyed `MSA_LSA.PAYMENT_AND_INVOICING.PERIOD`) |
| 5.1.2 (5 v2) | owner: an approved exception | "If the Customer is categorized as a Partner …" → "Notwithstanding Clause 8.5, if the Customer is categorized as a Partner …" (keyed `…CUSTOMER_ONBOARDING_AND_SE.PARTNER`; up to thirty (30) days unchanged) |
| 5.4.2 (5 v2) | Const. §16, owner | "in accordance with agreed credit terms" → "in accordance with the payment terms in Clause 8.5 (or, where approved, Clause 5.1.2)" |
| KYC-RETENTION-TOS-001 | owner ruling | `not_applicable_to: ["MSA"]` + `_owner_rulings`: §12's 5-year retention is LeapSwitch's CERT-In duty, not an MSA term. Re-imported (version 2) and a new snapshot published in both DBs (e2e `b2a1d430…`, demo `ecb73f04…`) with scratchpad `publish_cfg.py` (import tool + the publish endpoint's function, committed; no server switched). |

**Engine and preflight.** The liability engine needed no change. The PDF preflight did: `XREF_PDF` refused 8.2 because
the PDF text layer reads the run-in title as "Payment : All". It now ignores a space before punctuation (`preflight._TIGHT`),
pinned by `test_xref_pdf_ignores_a_space_before_punctuation`, which fails without the fix. Three tests used KYC on an MSA
as their example of "another type's standard: Legal to confirm". They now assert the ruling (not applicable), or use
TERM-NOTICE-NDA-001 for that example.

**Gate (e2e, rolled back, with the PDF):** 22 of 22 applicable standards MATCH, no preflight problem.
Checks: tests/drafting + legal_regression 306 passed; review-workflow, calibration, mixed-agreement and standards
suites green; ruff and mypy clean.

**Our best position first (owner 2026-11-04, the manager's point) — pass 6** (scratchpad `resolve7.py`; e2e DRAFT
rows; demo re-hand-published as **v7**, DEMO label. Another session had already published a v6 at 15:39):

| Clause | Source / ruling | Before → after |
|---|---|---|
| 17.2 (17 v5) | the approved file `msa-approved-2025-07.docx` 17.2, verbatim | "Except as expressly and specifically agreed otherwise … the aggregate liability of either Party … shall not exceed the total fees paid or payable by Customer in the twelve (12) months …" → "Notwithstanding anything to the contrary contained in this Agreement, the total aggregate liability of Leapswitch and its affiliates, whether in contract, tort (including negligence), strict liability, or otherwise, shall not exceed the total amount actually paid by the Customer to Leapswitch for the specific Services giving rise to the claim during the six (6) month period immediately preceding the event giving rise to such liability." **The approved file's cap is NOT mutual** (it limits Leapswitch only), so it was not made mutual. 17.3 carve-out and 17.7 data loss kept. |
| 8.5 (8 v5) | Constitution §16 sentence; owner | "within twenty-one (21) days of the invoice date" → "within seven (7) days of the invoice date". 8.2, 5.1.2 and 5.4.2 refer to 8.5 by cross-reference, so they read the same. 5.1.2's Partner terms stay "up to thirty (30) days". |
| LIABILITY-MSA-001 | `AM-303` (AB-158 addendum, clm-records) | `favourable_direction: LOWER` + `favourable_outcome: ACCEPTABLE`. A lower **mutual** cap on our provider paper is accepted in our favour; a one-party cap never is. |
| Publish gate | `AM-303` r3 | `drafting.publish.in_our_favour`: a standard passes when every Evaluation is a MATCH, a DEVIATION accepted in our favour, or a mutual cap no higher than ours on the same or affected-services basis (AM-301). `/templates/{id}/check` marks such a standard `in_our_favour`. |

**Gate (e2e, rolled back, PDF):** 20 MATCH; PAYMENT-PERIOD-MSA-001 DEVIATION **in our favour** (7 < 21 days);
**LIABILITY-MSA-001 UNABLE_TO_EVALUATE, blocking**. The approved 17.2 caps LeapSwitch only (`cap_party: ours`), and
under AM-239 r2 / Constitution §9 a one-party cap never passes. The template therefore does not publish until 17.2 is
mutual. That needs a word change, which is the owner's call. The management pack
(`/root/legalmind-clm-local/msa-for-management/LeapSwitch-MSA-template.docx` + `.pdf`, scratchpad `bin/mgmt_pack.py`)
is regenerated with the same review header and placeholders. Its NUMBERING lines are expected on a blank render, which
carries no clause tags.

**Option B (owner 2026-11-04) — pass 7** (scratchpad `resolve8.py`; e2e 17 v6 DRAFT; demo **v8**, DEMO label):
17.2 "the total aggregate liability of Leapswitch and its affiliates, whether in contract …" → "the total aggregate
liability of either Party, whether in contract …". Six (6) months and "for the specific Services giving rise to the
claim" stay verbatim. **Gate (e2e, rolled back, PDF): publishable.** 20 MATCH; PAYMENT-PERIOD-MSA-001 DEVIATION in our
favour; LIABILITY-MSA-001 UNABLE_TO_EVALUATE in our favour (6 months of affected-services fees, mutual: AM-301 /
AM-303 r3). Management pack regenerated: no margin overshoot, numbering round-trip true (218), preflight only the
expected blank-render NUMBERING lines.

**Management-PDF review fixes (coordinator, 2026-11-04) — pass 8** (scratchpad `resolve9.py`; e2e DRAFT; demo **v9**):
17.2 "to Leapswitch for" → "to LeapSwitch for" (17.2 keyed `…LIMITATION_OF_LIABILITY.CAP`) · 17.7 "The 12-month
aggregate liability cap applies only" → "The aggregate liability cap in Clause 17.2 applies only" (xref) · 6.6 "OR" →
"or", "the customer's committed" → "the Customer's committed" · 7.6.6 "the customer has" → "the Customer has" · 8.11
(found by scan) "In case the customer is an SEZ customer" → "In case the Customer is an SEZ customer", "bill the
customer" → "bill the Customer" · 21.7 "terminate the agreement" → "terminate this Agreement" · 1.5 ‘Business Data’ →
“Business Data”, 1.13 ‘Personal Data’ → “Personal Data” · 1.17 “Service Level Agreement (“SLA”)” → “Service Level
Agreement” (“SLA”), both bold (`render_contract._DEFINING` now takes a bracketed short form, test
`test_a_definition_with_its_short_form_in_brackets_bolds_both_terms`). Scan: no "12-month" or "twenty-one" left.
Lower-case generic uses kept ("end customer", "customer data", "an SEZ customer", "entire agreement", "written
agreement"). Gate (rolled back, PDF): publishable, 20 MATCH plus payment and liability in our favour, no preflight
problem; management pack regenerated, no margin overshoot, numbering round-trip true.

**17.3 carve-outs (d)/(e) — PENDING management approval AND a Constitution §9 amendment (owner 2026-11-04)** — pass 9
(scratchpad `resolve10.py`; e2e 17 v8 DRAFT; demo **v10**; management pack regenerated). Source note on the row:
"owner decision 2026-11-04, for management approval — needs Constitution §9 amendment (carve-outs) before publish".
17.3 "…(b) fraud or fraudulent misrepresentation; or (c) any liability that cannot be limited or excluded under
applicable law." → "…(b) fraud or fraudulent misrepresentation; (c) any liability that cannot be limited or excluded
under applicable law; (d) a Party's obligation to pay fees and charges due under this Agreement; or (e) a Party's
indemnification obligations under this Agreement."
**Gate (rolled back): it still PASSES. That is an engine gap, not a clearance.** LIABILITY-MSA-001 reads
UNABLE_TO_EVALUATE, in our favour (6 months of affected-services fees, mutual). It is not "a person's call": the
standard declares no `extraction.exceptions`, so 17.3's carve-outs are never read as uncapped scopes (AM-240's rule
applies only where carve-outs are extracted). The engine and gate are deliberately unchanged (§9 not yet amended).
**Do not publish this version until §9 is amended.** The gate would let it through.

**Engine fix `AM-304` (AB-158 addendum): carve-outs beyond the lawful floor.** Root cause: `cap_carved_out` (AM-195)
matched only "the cap … shall not apply to" and "… not be subject to the cap", and only §9's named classes. "Nothing in
this Agreement shall limit or exclude … liability for (d) payment … (e) indemnification" was never read, so the cap
looked clean and "in our favour". Now `extraction.lawful_floor` (TOS §13's list, in LIABILITY-MSA-001 and -TOS-001)
is the only carve-out that leaves the cap as it reads. Any other uncapped class is UNLIMITED beside the cap: CONFLICT,
a person's call. Standards re-imported, snapshots published in both DBs (e2e `ff3f190d…`, demo `f0667e24…`). **Gate
(e2e, rolled back): LIABILITY-MSA-001 CONFLICT, held for a person.** PAYMENT in our favour, 20 MATCH. No golden-corpus or
legal_regression expectation moved (1,011 passed across the affected suites).

**Party A's Act (owner 2026-11-04)** — e2e template layout (DRAFT); demo **v11**. Party A: "a company incorporated
under the Companies Act, 2013" → "a company incorporated under the Companies Act, 1956 and deemed to be existing under
the Companies Act, 2013". The CIN's 2010 registration is a 1956-Act incorporation, and the Constitution's 2013 is the
Act that governs it now. **This corrects the earlier notes (§8 and the template flags) that called the approved file's
1956 an error.** Party B is unchanged. Management pack regenerated (`bin/mgmt_pack.py`, review header, placeholders):
no margin overshoot, numbering round-trip true, preflight only the expected blank-render NUMBERING line. Gate unchanged
(LIABILITY CONFLICT for a person, PAYMENT in our favour, 20 MATCH).

## 10. 2026-11-04 wrap-up — Templates page and checks

- **Templates page** (clm-p1): demo DB's old reference MSA draft (`MSA.LEAPSWITCH`, c43f2e91…) RETIRED, not
  deleted, so one MSA row shows; each card's subtitle names the file it came from (`source_file`: MSA.pdf vs
  msa-approved-2025-07.docx), so e2e's two MSA rows are told apart without touching template text. A
  hand-published DEMO version reads "Demo — not approved by Legal" instead of "0 of 21 clauses approved"
  (`blank.demo_label` now reads `source.label` — the API read a `demo_label` key nobody wrote, so the label
  and the blank's DEMO header were both missing). `GET /templates/{id}/check` on a non-draft is 409 (was 500).
- **"Checking…" / "Reading the template…"** measured: they resolve — checks 2.6–9 s, playbook 5.4 s cold,
  ~9 s all in parallel; the screenshots were taken before then. The check already had a 60 s limit; the
  playbook had none. Both now end in "Couldn’t check right now — try again" (`loadPlaybook` + `within`),
  test in `template-approval.test.tsx`. Screenshots: `/root/legalmind-clm-local/tpl-shots/templates-{1440,390}.png`.
- Servers: API :8399 = `run_api_demo.sh`; UI :3399 = dist `.next-clm-r7`.
- Full suite (CI shape, fresh DB `legalmind_clm_full_1850`): 5,193 passed, 1 failed (known stale `test_published_policies`), 273 skipped, 1 xfailed — after fixing the two playbook routes missing from `permission_map.py` and the router-module count (21). Frontend 812 vitest, tsc, lint baseline, ruff, mypy clean; openapi.json current.

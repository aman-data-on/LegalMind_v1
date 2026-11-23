# LegalMind enterprise tracker

**Status: 📁 LIVE TRACKER — records what is open and what is done; decides nothing.**
Opened 2026-11-02 on the owner's instruction: *"up to date the doc so we remember what we
have to fix, and when it is fixed update the sheet so we stay on track."*

**How to use it.** Every session that finishes an item changes its row to ✅ with the date
and the commit/PR, in the same change as the work. A new item found along the way is added
here before it is worked on. Build state is still asserted only by
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md); this sheet points at it.

Status: ✅ done · 🔧 in progress · ⏳ open · 🙋 waiting for the owner · ⛔ decided not to do (reason given)

---

## The goal (owner, 2026-11-02)

LegalMind becomes a legal assistant smarter than a lawyer: it understands the deal, reads the
whole contract, **asks the questions this contract raises** (never a fixed list — same process
for every case, different thinking for each, like a lawyer with a theft case and a murder
case), gives personal advice, drafts, and remembers. Industry methods we do not use yet are
adopted on the basis of current official documentation and published research; our benchmarks
run afterwards as a safety check that nothing broke, not as a gate before adopting.

**A lock that blocks this is amended** — by an appended record in `all_lock.md` (rule 22: the
old line stays, marked superseded), with the registry, docs and tests updated.

**Three rules that stay** unless the owner says otherwise explicitly:
1. Never invent a company legal position, a law, a case or a figure (rules 7, 21).
2. Permissions and privacy — nobody sees what they may not (rule 18, `SEC-07`).
3. The audit trail stays append-only (rule 17).

Nothing is committed until the owner says "commit".

---

## Open — Full-stack audit 2026-11-23 (`/root/legalmind-clm-local/audit/fullstack-audit-20261123/AUDIT-SUMMARY.md`)
- [x] P1 speed quick wins — BE-1 session stamp, BE-11 commit off the loop, DB-3 Ask chunk by uuid, BE-4 token cache, BE-7 permissions once per request, request DB timeouts (BUILT 2026-11-23 on `perf/quick-wins`, NOT deployed; `P1-BUILD-REPORT.md`)
- [x] P2 comparison cache — BE-2/DB-1, BE-3, BE-5, BE-6, DB-7, BE-9 + brief double fetch (BUILT 2026-11-23 on `perf/comparison-cache`, NOT committed, NOT deployed; `P2-BUILD-REPORT.md`). Left: `/todo` legal `_decisions` N+1 (DB-7 pattern, not in the brief), TemplateList per-row check (frontend; now ~34 ms each)
- [x] P3 database hygiene (migrations) — DB-2, DB-5, DB-10, BE-13 + P1 leftovers (BUILT 2026-11-23 on `perf/db-hygiene`, migration `d340ac8e60fd`, NOT deployed; `P3-BUILD-REPORT.md`). Not built: DB-8 (proposal — locked 49.4 keeps `pagination.total`), BE-8 (not in this batch's brief)
- [ ] P3 remainder — DB-8 audit-log exact count (owner decision on locked 49.4), BE-8 one helper for the versions-of-a-contract query (31 inline copies)
- [x] U1 UI wrong or risky — UI-01, UI-02, UI-05, UI-10, UI-09, UI-12 (BUILT 2026-11-23 on `fix/ui-u1`, browser-checked 1440/390/320, NOT deployed; `U1-BUILD-REPORT.md`). Round 2 done (critic must-fixes, D1/D3/D4). Follow-ups: brief status for a final copy waiting on Legal / an archived contract (needs the call site, perf-p2 owns it); Take back into the ⋯ menu (U2, UI-03); owner: notify the lawyer and keep the note on take-back?; `evidenceLocation` "§" shared by Sales and Legal; report body copy pass (position, em dashes, "-analysis.docx" file name); D2 INTERNAL_REVIEW wording (product call)
- [ ] U2 UI workspace layout — UI-03, UI-04, UI-06, UI-07
- [ ] U3 UI consistency — UI-11, mediums/lows, UI-08 (presentation-only amendment to AM-264/AM-291)
- [ ] Later / owner — BE-10 nginx gzip, BE-12 OCR to the worker (rule 19), DB-4/DB-6 statute search, DB-9 duplicate indexes, BE-14–19, a fresh production copy

## Open — case-by-case round 2026-11-19 (client MSA markup; plan in `audit/client-msa-case-20261119/`)
- [x] Batch 1 redline truth — AB-216 `AM-431`–`AM-434` (DEPLOYED 2026-11-19 ab8250b1; live check as sales + lawyer passed)
- [x] Batch 2 cited passage — AB-217 `AM-435`–`AM-438` (DEPLOYED 2026-11-20 ac0332ea)
- [x] Batch 3+4 "deal brief" — AB-218 `AM-439`–`AM-443` (DEPLOYED 2026-11-20 0acf53b6; live as sales + lawyer)
- [ ] Owner: server refuses an owner's "keep ours" on a Legal-routed row while with Legal (proposed 409 rider; rule 18)
- [ ] Owner/Legal: a keep-ours / ask-client answer sent with no reason on a measured row still records a system fallback justification ("Answered on the change: …"); the UI no longer reaches it (AB-218) — propose: require the lawyer's reason on the server
- [ ] Owner note: a lawyer who created a contract (CREATOR, AM-288 r2) may record positions before it is sent to Legal
- [x] Batch 6 client misreads — AB-219 `AM-444`–`AM-448` (DEPLOYED 2026-11-23 f695622d)
- [x] Batch 7 client details before drafting — AB-220 `AM-449`–`AM-452` (DEPLOYED 2026-11-23 02197bc4; MSA v3 draft with our CIN locked awaits Legal: re-keep "Partner", approve, publish)
- [ ] Owner: client self-fill link (Ironclad/Juro/SpotDraft pattern; outsider-facing page — security review)
- [ ] Legal: NDA template; our registered office + incorporating Act (Constitution §4.1 vs MSA); source of our CIN; fixed defaults for recital A and the banks' city; **Q2 (AB-221 `AM-459`)**: "When we only have the client's file, 'Keep our wording' would put back the text that was there before their tracked edits. That text may include edits they made without tracking, or our own older edits. May we send it as ours?"
- [ ] Owner (rule 21 config): finding terms "from termination", "terminates", "subprocessor(s)", data residency / convenience notice / data purge terms
- [ ] Legal: "paid or payable" cap basis; residuals waiver wording; whether a mutual change is ever onto us; carve-out/precedence/renewal/refund triage rules; data-loss general exclusion; customer-indemnity limbs
- [ ] Batch 8 "lessons from a real client MoU" — A (items 2, 3, 6: not marked first, reading fixes, commercial observations) AB-222 `AM-461`–`AM-463` BUILT 2026-11-23 on `feat/case-lessons-a` (not committed; awaiting independent verification); B (items 1, 4, 5: already agreed before, triage reasons, standard set) AB-223 `AM-464`–`AM-467` BUILT 2026-11-24 on `feat/case-lessons-b` (not committed; independently verified, round 2 fixes applied; no import or publish needed); C-34 registered
- [x] Batch 5 "our contract came back marked up" start option — AB-221 `AM-455`–`AM-460` (DEPLOYED 2026-11-23 febed05f, PR #334)
- [x] Production-copy answered-keys probe (owner OK): 0 of 12 answered keys lost
- [ ] Legal: confirm BASELINE for this case; this deal's positions; never-concede list

## Open — prelaunch QA 2026-11-18 (`audit/prelaunch-20261118/REPORT.md`)

- [x] F1 one main button (lawyer decision form only with Legal) · [x] U1 Send to Legal step · [x] U2 upload client's reply in sight · [x] F2 empty-annex final read as body · [x] F11 short name · [x] U5 template wording · [x] CLS P1–P3 — branch `qa/prelaunch-20261118`
- [x] C-33 Ask the client on a measured change → resolved, option (a): AB-214 `AM-411`
- [x] Legal's precedence sentence + Annexure 1 words no longer block a final (owner ruling 2026-11-18, AB-214 `AM-414`); optional wording screen on the template page (`AM-412`)
- [x] Lawyer's "Record the decision" header step + "Your turn" (`AM-413`); phone CLS on the list and the Final page; Annexure 1 title once; targets ≥ 24 px in the contract view
- [ ] Whitespace-only tracked change not listed
- [ ] 🙋 **Next lawyer review of the MSA template — confirm the annexure structure (`AM-414` r6):** Annexure 2 = title + opening + "Clause X is replaced by the following: …" with no separate precedence sentence, relying on MSA 21.9, 6.1.4, 6.5.4 and 21.3; Annexure 1 = "Annexure 1 — Service Order Form" + the services, fees and initial-term tables with no clause text. Legal may add its own wording on the template page if it wants any.
- [ ] After a question to the client, the next round lists every difference from our last full version again, including changes accepted before (`AM-411` r7) — carry the earlier answers (later batch)
- [ ] Changes tab still says "Annexure A" on an Annexure 2 deal ("Goes into Annexure A…")
- [ ] The 20–30 s waits (create, upload, reply, final): timings in `audit/ab214-20261118/REPORT.md`; speed-up is a later batch

## Open — AB-210 (2026-11-17): production E2E fix batch (`audit/E2E-FIX-BATCH-*.md`)
- 🔧 Batch A+B (deal flow, fill-in fields; AM-393/394/396/398) — PR 1 `fix/e2e-batch-ab-20261117`.
- ✅ Batch A+B merged (#314, 56cd05b2), not deployed.
- 🔧 Batch C (wording to send back = our MSA; one decision per clause; Effect for us + Source columns; Ask the client; sales Summary) — AB-211 AM-395/AM-399, PR 2 `fix/e2e-batch-cd-20261117`.
- 🔧 Batch D (Annexure 1 from the template page; MSA → Annex 1 → Annex 2 → signatures) — AB-211 AM-397, PR 2.
- 🔧 A+B leftovers (fill after the client round; one stage for every reader; Legal queue; Mark signed reads the stage) — AB-211 AM-400, PR 2.
- ✅ C-32 resolved 2026-11-18 (owner option b; AB-212 AM-401): a 17.7 equal to 17.2 is a repeat; template with 17.7 default "six (6)" publishes. Merged, not deployed; after deploy Legal can publish a template version with the 17.7 default.
- 🔧 AB-213 (AM-402–410, 2026-11-18): Sayan MSA front words verbatim; final = body verbatim + Annexure 2; template v2 import; E2E D1–D14. PR 1 fix/ab213-sayan-fidelity, PR 2 #318. Not deployed; ops: import MSA v2 + Legal publish, nginx reload.
- 🙋 Legal: recital A words (until then a sales field); 5.3 lines for 10 services. (Annexure 1 clause text, L3: no longer owed — `AM-414`.)

## Open — AB-205 (2026-11-16): MSA standards aligned to our MSA
- ✅ 2026-11-17 Deploy: standards imported and published on production, snapshot `179b29e4` (Mumbai, own_wording verified live).
- Legal: MSA 17.7 "total fees paid … in the __________ months" — blank period contradicts 17.2 (our MSA keeps a liability CONFLICT until fixed on paper).
- Legal: 8.9 "discontinue" on non-payment read as NOT a service-discontinuation notice (suspension of SERVICE-DISCONTINUATION for MSA rests on that).
- Product: residency (11.5) and sub-processors (11.4) clauses still go to a person on every MSA (AM-322 r11); a "same as our MSA text" check would clear them.

## 0. Done 2026-11-02

| ID | Item | Done |
|---|---|---|
| D-1 | Gemini credit back — probed (tiny call and a 15k-token call, both 200) | ✅ 2026-11-02 |
| D-2 | Production Ask default model and review model switched `deepseek` → `gemini` (IndieRouter refuses real-sized calls, 402). Backup `/root/.legalmind/preserved/legalmind.env.before-gemini-default-2026-11-02`; API restarted, both workers carry it | ✅ 2026-11-02 (server env, no commit) |
| D-3 | Redis password (S-4 / QA-029) in `redis.conf` and `LEGALMIND_BROKER_URL`; worker and API reconnected | ✅ 2026-11-02 (server, no commit) |
| D-4 | Daily policy refresh failing since 2026-10-31 (leapswitch.com → www.leapswitch.com): fetched from the new addresses, page summary and menu skipped | ✅ DEPLOYED 2026-11-02 `ad93cd2` (PR #279); refresh run: all four Leapswitch pages CHANGED, CloudPe unchanged |
| D-5 | C-29: live Leapswitch SLA now 99.9% everywhere → Constitution L1.15 (`AM-243`, AB-141) on the owner's ruling "take it from the live website" | ✅ DEPLOYED `ad93cd2`; L1.15 ingested CURRENT (708 items), L1.14 SUPERSEDED |
| D-6 | Client-change triage switched ON in production (`LEGALMIND_CHANGE_TRIAGE=on`, review model Gemini, measured 76/82) on the owner's "go with your recommendation"; worker + API restarted. Backup `/root/.legalmind/preserved/legalmind.env.before-change-triage-2026-11-02` | ✅ 2026-11-02 (server env) |

## 1. Paid tests (owner "go" 2026-11-02, ≈ $2–2.50 on Gemini)

| ID | Test | Est. | Status |
|---|---|---|---|
| T-A | One contract reviewed in Ask as our lawyer would (`AM-236`) on 4 real files | ~$0.13 | ✅ 2026-11-02 — client redline and NDA good; two defects → Q-6, Q-7 |
| T-B | Client-change triage re-measured on Gemini (DeepSeek: 77/82); if ≥, propose the flag on | ~$0.02 | ✅ 2026-11-02 — Gemini 76/82 caught, 6 extra flags (4 on unlabelled clauses), 31 s; missed 19.4 New Delhi. Flag-on = owner |
| T-C | C26 50-turn conversation, run 3 (run 1: 44/50) | ~$1.30 (186 calls) | ⚠️ 2026-11-02 — **36/50**; cited blocks 105 → 91, 7 answers cite nothing → Q-5 |
| T-D | Ask stability, 4 questions × 3 | ~$0.20 | ✅ 2026-11-02 — 12/12 answered (13–28 s, was a fallback floor on 10-27); Q2 never says the NDA has no cap (3/3) → Q-8; Q4 run 2 answered off the question |
| T-E | DeepSeek (IndieRouter) and Together out of credit; Bonsai server down | — | 🙋 owner top-up / Bonsai owner |

## 2. Server security (each needs the owner's "go")

| ID | Item | Status |
|---|---|---|
| S-1 | QA-074 uvicorn `--no-access-log` (5 s restart) | 🙋 |
| S-2 | QA-082 `GRANT CONNECT` to the app role, then `REVOKE CONNECT … FROM PUBLIC` | 🙋 |
| S-3 | nginx headers, CSP report-only, 444 default server (QA-030/051/059/068/069) | 🙋 |
| S-4 | Redis password (QA-029) | ✅ 2026-11-02 (D-3) |
| S-5 | Backup failure alert + one restore drill (QA-065) | 🙋 |
| S-6 | List old database dumps, delete nothing (QA-042) | 🙋 |
| S-7 | Frontend service runs as root | 🙋 |
| S-8 | SSH open to every address — needs the office/VPN IP ranges | 🙋 |
| S-9 | Written plans: no-root services (QA-028), DB role separation (QA-046), pinned venv (QA-081), more append-only triggers (QA-090) | ⏳ |
| S-10 | Server resize on CloudPe (owner offered 2026-11-03; owner resizes when **I signal**, at a quiet time, after checking backups): (1) disk 48 → 100 GB — needed before installing the answer-check models (~4 GB; 8.7 GB free today); (2) 10–12 vCPU / 32 GB RAM — for the local checker; (3) a GPU node only if CPU checkers measure insufficient | ⏳ waiting for my signal |

## 2a. Input gate — "is this a contract at all?" (owner, 2026-11-02: a resume must not go through the contract engine)

| ID | Item | Status |
|---|---|---|
| G-1 | 🔧 BUILT + TESTED + reviewed 3× on branch `feat/contract-gate-20261102`, NOT committed (`AM-245`, AB-143) — waiting for the owner's "commit" — **Document classification gate before the pipeline** (industry: classify-then-extract, "OTHER/non-contract" class, reject option / OOD detection, human confirm; Azure Document Intelligence custom classifier, Google Document AI classifier/splitter, AWS Comprehend + A2I, Kira's Contract/Non-contract first level, LegalOn's Other type). Layered: (1) deterministic markers — parties/recitals, "Agreement"/"Terms" title, numbered clauses, signature block vs CV/invoice/deck markers → contract / not / undecided; (2) small local classifier with an OTHER class, thresholds set for ≥99% contract recall on held-out real contracts; (3) LLM only for the undecided band, with a quoted span. Non-contract → no engine, **no Gemini egress**, plain message, "Review anyway" override audited. Needs an amendment: `AM-51`/`AM-64` say the type is "never a gate". Today a resume is parsed, its paragraphs sent to Gemini by AM-54 recognition, and a "review" with nothing applicable is shown. Research record: this session's report (2026-11-02) | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| G-1a | Measure the gate's refusals on REAL non-contracts (a few real resumes, tax invoices, decks) — today only synthetic negatives; real tax invoices mostly read UNSURE because of "Authorised Signatory" (safe direction) | ⏳ needs samples |
| G-2 | Uploaded AUP/Privacy/TOS/SLA → compare with the live website version (deterministic text diff) instead of measuring against contract positions | ⏳ proposed, owner to confirm |

## 3. Contract-reading fixes (one batch; re-check each before fixing)

| ID | Misread | Status |
|---|---|---|
| R-1 | A one-way (customer-only) indemnity shown as Match | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-2 | Price-change point cites the liability clause as evidence | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-3 | NDA term-notice standard measured on an MSA | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-4 | Heading "9. Term and Survival: …" gets no section number | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-5 | "50 Mbps" read as §50 | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-6 | "Amendments in writing" shown Match for changes/cancellation | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-7 | A clause split over two PDF pages gives a false Conflict | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| R-8 | A re-run should carry decisions over on unchanged points | ⏳ |
| R-9 | Constitution positions with no standard file (§12 data residency, breach notification, sub-processors; §15 trade secrets on an MSA; §31.14 assignment and change of control per family) — 14 standards (`AM-322` r1–r16, AB-174). §12 is presence-only: absence is MISSING, a clause found goes to a person; seven owner-approved finding terms (2026-11-11); cited to L1.16 | 🔧 BUILT + TESTED + verified on branch `feat/constitution-standards-20261109`, NOT committed — waiting for the records re-verify, then the owner's "commit" |
| R-10 | Owner/Legal: C-31 (does a standalone DPA get measured against §12? §12.2 vs `AM-73` r1/`AM-244`) and the vendor-paper party reading withdrawn in `AM-322` r11 | 🙋 |

## 4. Industry methods we do not use yet

| ID | Method (industry name) | Where we stand | Status |
|---|---|---|---|
| M-1 | **Shared cache across API workers** (bug) | Answer cache lived in each worker's memory; production runs 2 workers since 2026-10-30, so the hit rate halved | ✅ DEPLOYED `ad93cd2`; `LEGALMIND_ASK_CACHE_BACKEND=redis` set, API restarted; two-process smoke test on live Redis passed |
| M-2 | **LLM / model routing** by task — Flash-Lite → Flash → Flash with thinking or Pro; escalate one tier when verification fails (cascade, FrugalGPT) | User picks the model; `AM-116` forbids a silent switch → amend, with a visible "answered by" line | ⏳ |
| M-2a | **Model switch gate** (owner Q 2026-11-03: does switching the LLM change answers? — yes, measured: C26 Gemini 41–44 vs DeepSeek 47; triage 76 vs 77 of 82): no model becomes the Ask default or review model unless it passes C26, the hard benchmark and the V-1 answer-check set at least as well as the current one; weekly drift run per model in use (~$1–2/week, cost stated before switching on); per-model prompt tweaks only where measured | ⏳ |
| M-3 | **Explicit context caching** (Gemini `cachedContents`) for whole-contract reviews | Implicit prefix caching only | ⏳ |
| M-4 | **Semantic cache** | Exact-match only — measured 2026-10-08: opposite legal questions score 0.94–0.99 similar. Adopt guarded: safe question shapes only, never a clause or law answer | ⏳ |
| M-5 | **HNSW index** (pgvector) | Exact search (`AM-84`) | ⏳ |
| M-6 | **Query rewriting** (Gemini, stage 2) switched on | Built, off | ⏳ |
| M-7 | **Newer embedding model** | MiniLM (`AM-83`) | ⏳ |
| M-8 | **Knowledge graph / GraphRAG** (the norm graph) | Not built | ⏳ |
| M-9 | **Tracing** — OpenTelemetry / Langfuse | One trace log per request; locked 53.6 NOT YET SPECIFIED | 🙋 owner decision |
| M-10 | **Cost per request** dashboard | Tokens logged, no dashboard | ⏳ |
| M-11 | **Provider failover** | None by rule (`AM-116`) → amend, always labelled | ⏳ |
| M-12 | **Streaming** — only text that already passed verification | No streaming (stage 9) | ⏳ |
| M-13 | **Load test**, repeated | Once, 2026-09-29 | ⏳ |
| M-14 | **Answer relevance** metric (RAG triad, RAGAS) — "did the answer say things not asked?" | Instruction following built (`AM-107`/`AM-108`/`AM-235`); no metric — eval "relevance" = cited the gold source | ⏳ |
| M-15 | **Context compression** — drop irrelevant sentences before generation | Reranker + gate drop weak sources only | ⏳ |
| M-16 | **Long-term memory** — episodic, semantic (user, deal), procedural (Mem0 / Letta style); user sees and deletes it; erased with the user (`AM-238`) | Memory inside one chat only | ⏳ |
| M-17 | **Feedback loop** — thumbs-down and Legal's corrections join the eval set and tuning automatically | Thumbs collected, alert only (`AM-123`) | ⏳ |
| M-18 | Fine-tuning | — | ⛔ no training data; provider terms are no-training on our data |

## 5. The lawyer cycle — same process, different thinking per deal

| ID | Stage | What it does | Status |
|---|---|---|---|
| L-1 | Read the contract | What kind of deal this is, from its content | ✅ largely (`AM-51`, `AM-192`) |
| L-2 | **Case sheet** (deal memory) | Only the facts that matter for this deal: prepaid/postpaid, our role, money, term, data, what is unusual — saved per deal (needs storage → amendment) | ⏳ |
| L-3 | Spot the issues | Missing, one-sided, contradictory, blank — for this deal | 🔧 partly (`AM-241`) |
| L-4 | **Ask the questions this contract raises** | Generated per contract; code checks each one points to a real clause, gap or contradiction | ⏳ |
| L-5 | Personal advice | This deal's facts, this person's role, our positions | ⏳ |
| L-6 | Draft | Counter-proposal, email, redline for this deal | 🔧 partly (`AM-235`, `AM-236`) |
| L-7 | After signing | Renewals, notice dates, obligations | ⏳ |
| L-8 | Scenarios ("what if the balance runs out") — research §7 phase 5 | ⏳ |
| L-9 | Learn from Legal's real decisions — research §7 phase 6 | ⏳ needs owner material (O-1) |

Research basis: [LAWYER_REASONING_RESEARCH.md](../architecture/LAWYER_REASONING_RESEARCH.md); published
legal-reasoning methods (issue spotting, IRAC, clarifying questions) and real legal-AI case
studies, cited.

## 5a. Answer-check programme (owner, 2026-11-03: 0 overstated / 0 reversed / 0 false rejections, proven on unseen contracts)

| ID | Phase | Status |
|---|---|---|
| V-1 | Evaluation set: real claims + typed perturbations (overstated, reversed, condition dropped, exception omitted, scope widened, number changed), split dev / held-out / UNSEEN by document, separate metrics with exact counts | ✅ built 2026-11-03: 4,093 claims (dev 682 Constitution · held-out 1,178 statutes · UNSEEN 2,233 from 19 untuned documents), `tools/eval_claims.py` (branch `feat/structural-check-v2a`), data in /root/.legalmind/bench-cache/p1_*. Baseline UNSEEN accepted: overstated 5/121, reversed 24/370, number 2/196, condition dropped 126/132, exception omitted 57/58, scope widened 191/233, unsupported conclusion 256/396; faithful falsely rejected 30/727 |
| V-2 | Context-aware evidence per claim (clause + parent/children + definitions + exceptions + cross-references + Company Standard) | ⏳ |
| V-2a | P2a structural layer (limb coverage, scope, conclusion split, ABSTAIN state), behind a flag | 🔧 built, dormant: `assist/verification/structural.py` wired into `verify.judge` behind `LEGALMIND_STRUCTURAL_CHECK` (default off; `shadow` logs only), branch `feat/structural-check-v2a` — not yet measured on V-1 |
| V-3 | Claim decomposition (subject, action, modality, condition, scope, exception, number, quoted source span verified in code) | ⏳ |
| V-4 | Independent verifier: local MiniCheck-Flan-T5-L (MIT) + HHEM-2.1 (Apache) beside deterministic typed checks; accept only when all agree, reject only when a code check fails on a matched span AND the verifier agrees, else ABSTAIN showing the verbatim source | ⏳ needs S-10 disk; abstain policy = owner decision O-9 |
| V-5 | Cross-clause reasoning (subject to / notwithstanding / except as in clause X / definitions / schedules) | ⏳ |
| V-6 | Abstention wording + measured abstain rate on UNSEEN | ⏳ |

## 6. Ask quality leftovers

| ID | Item | Status |
|---|---|---|
| Q-1 | Verifier accepts 27% of overstated and 16% of negated claims (held-out) | ✅ DEPLOYED 2026-11-03 `d2a5243` (typed checks; overstatement 27%→14%, negation 16%→11%); the rest = V-programme |
| Q-2 | Model step 3: reranker top-10–15; bge-m3 / EmbeddingGemma for documents and statutes | ⏳ |
| Q-3 | QA-095: the picker lists Gemini where no Gemini key is set | ⏳ |
| Q-4 | Daily benchmark writes a trend file | ⏳ |
| Q-5 | ✅ built 2026-11-02 (`AM-244` r1–r2; root cause: the AM-235 no-repeat step dropped the only cited block) — **Uncited answers pass** (C26 run 3): Gemini writes sourced facts as uncited "reasoning" blocks; the `AM-220` V5 check matches English phrases ("our policy") and figures only, so Hinglish/plain statements pass — the check must test overlap with the turn's shown evidence, any language | ✅ DEPLOYED `ad93cd2`; C26 run 4 on live code **41/50** (run 3: 36), uncited answers 7 → 2, cited blocks 91 → 102 |
| Q-6 | Ask's lawyer review compares MSA §17.2's 6 months (affected-services basis) with the 12-month standard as "6 months shorter" — the bases are not comparable (45B.4): fail closed | ✅ DEPLOYED `ad93cd2` (`AM-244` r3) |
| Q-7 | Ask's lawyer review measures our own AUP against Constitution §13 — an AUP has no positions (`AM-73`): say so | ✅ DEPLOYED `ad93cd2` (`AM-244` r4), incl. the multi-file label |
| Q-8 | The selected document's silence is hedged ("check the executed agreement") instead of "this NDA has no cap" when the selected document IS the agreement | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| Q-9 | The single-file memo panel for an AUP/Privacy Policy still offers "We're the buyer" / "It's signed" and shows no not-measured tag (the reply above it does say not measured) — UI | ⏳ low |
| Q-11 | C26 run 4 (41/50): 9 misses mostly cite a related but less specific section (AUP §7 instead of §5 Cryptocurrency Mining; Constitution §16 not cited beside the TOS late fee); 2 "say it is not stated" turns — retrieval/claim selection, measure with the zero-Gemini probe first | ✅ DEPLOYED 2026-11-03 `d2a5243` |
| Q-10 | V5 cannot exclude the reader's own question words (only their figures reach `verify`) | ⏳ low |

## 7. Only the owner can give

| ID | Item | Status |
|---|---|---|
| O-1 | Past deals with Legal's real comments or redlines (gold set) | 🙋 |
| O-2 | Approved fallback positions — do any exist? | 🙋 |
| O-3 | Counsel: the four questions in research §8; MSMED registration | 🙋 |
| O-4 | May a labelled "market practice" line be shown? | 🙋 |
| O-5 | Company names: executed MSA says "Leapswitch Network Pvt Ltd."; CloudPe Privacy Policy says "CloudPe Networks Pvt Ltd"; CloudPe Companies Act vs CIN; CloudPe trademark owner | 🙋 |
| O-6 | Legal: mutual indemnity; CloudPe TOS "India and USA" law; AUP deadline for intimate-imagery complaints | 🙋 |
| O-7 | Parked until raised: alert email sender/password (PR #270), Document Builder templates, dark mode | 🙋 |
| O-8 | **Privacy:** once a file is attached in an Ask chat (agent mode), every later turn of that chat sends the whole file to the model as the reader's material (`_inline_material`, AM-114) — even for an unrelated question and even when it is a resume or an invoice. Keep (the reader's choice), or send a file only when the turn is about it / when it is a contract or policy? | 🔧 owner chose 2026-11-02: send a file only on a turn about it — BUILT + TESTED on the same branch (`AM-246`), NOT committed |
| O-9 | Accept abstaining: when the checks disagree, show the verbatim source instead of a conclusion (the only way to 0 wrong claims shown; abstain rate measured and reported) | ✅ owner 2026-11-03: yes — abstain and show the verbatim source when the checks disagree |
| O-10 | Our own MSA templates' one-way indemnity (16.1 / 11.1) now DEVIATES from Constitution §10 (AM-248 r1) — fix the template or clarify §10? | 🙋 Legal |
| O-11 | The NDA counterparty's real name appears once in Constitution L1.15 (and its DB copy); the Constitution is meant to be redacted. Recommended: L1.16 with the name redacted + re-ingest; older version files keep it unless the owner explicitly says otherwise (locked history) | 🔧 owner 2026-11-03: yes — Constitution L1.16 (AM-300), committing 2026-11-04 |

## 8. Housekeeping

| ID | Item | Status |
|---|---|---|
| H-1 | PR #270 (alerts by email) — merge or close | 🙋 |
| H-2 | 16 old worktrees already in `main` (9 with leftover files — show the owner before removing) | ⏳ |
| H-3 | 11 old local branches from September | ⏳ |
| H-4 | Drop QA databases `legalmind_qa_20261028_1`–`_6` | ⏳ |
| H-5 | Stray `nano.156814.save` in the deploy tree | ✅ 2026-11-02 moved to `/root/.legalmind/preserved/` (owner's choice; it blocked the deploy) |

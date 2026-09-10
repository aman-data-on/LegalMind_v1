# LegalMind — where the project stands

**Status: 📁 DERIVED — written in plain language for the project owner.** Last updated
**10 September 2026**.

> This document explains things, it doesn't decide them. Every number in it comes from
> [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), which is the only document allowed to state
> what has actually been built. If the two ever disagree, that one is right.
>
> No knowledge of the software is needed to read this page.

---

## Picking up where we left off

*The short version, kept current so a new session can answer "where are we?" immediately.
Updated at the end of every working session.*

| | |
|---|---|
| ✅ **10 Sep (late) — shadcn/ui approved and its first real use is LIVE: six duplicate dialogs became one, safer, component** | **What you approved:** using shadcn/ui's underlying components (Radix) where they genuinely help, never as a wholesale redesign — the existing look and feel stays the source of truth. **What I found on the audit you asked for first:** the interface was already accessible and consistent; the one real duplication was the "Edit details", "Archive", "Delete", "Transfer" and "related documents" pop-up boxes — five separate, hand-written copies of the same dialog behaviour, one of them (the company's document list) missing keyboard focus handling entirely. **What changed:** those five now share one real dialog component, which also closes a genuine gap the old code had — pressing Tab inside one of them can no longer escape it onto the page behind. The "?" keyboard-shortcuts box stays as its own simple version, deliberately, because it's the one screen with an automated test that checks its exact wording. **Two real mistakes I caught myself, before you ever saw them, by opening a real browser rather than trusting the automated tests:** the first version of the new dialog wasn't centred on screen, and it would have rendered with no background colour at all if a menu elsewhere hadn't already taught this project that exact lesson three days ago. Both fixed and re-verified with screenshots before merging. **Nothing about shadcn is used beyond this** — no new visual style, no Tailwind, one small library added. Merged and deployed; the live site is confirmed serving the new build. |
| ✨ **10 Sep — Client Profiles: every document you have with one company, in one place (LOCAL — committed, NOT deployed)** | **What you asked for:** a Client Profiles section, where one customer's details, all their legal documents, each document's versions and the existing LegalMind review live together — and one document list, never folders per document type. **What was already there:** the company itself. Since 6 September a contract has been able to record who it is with, so "a client's documents" is a question the database could already answer — it just had no screen. So nothing was rebuilt: **no second place for documents, no second copy of any file.** A client's documents *are* the documents you already have; filing one under a client records who it is with and moves nothing. A document already in LegalMind is **linked, never re-uploaded**. **What is new:** a Client Profiles item in the top bar (every normal user, not admins only); a list of the companies you work with, searchable, with how many documents and how many are signed; and a client page — the company at the top, then **one list of every legal document** with its type as a small label beside it, never as a folder. Under each document, its versions: **Company draft** (what we sent), **Client modified** (what came back), **Final signed** (what was executed). A revision never replaces the one before it — every version stays, and the page shows that. Analyze, open and compare all go to the review screens you already use; the engine is unchanged. **Three things I could not do without you:** Partner / Vendor / Distribution Agreement are not LegalMind document types and adding one changes a locked decision — they file as "Other" for now; the twelve new company fields have no lock record yet, only your instruction; and the list shows only clients you share a document with, because showing every company in the organisation is a privacy decision, not a setting. **SOW was not added**, as you asked. |
| 🔧 **10 Sep — the workspace fixes you listed, built and tested (worktree branch `fix/workspace-ux`, NOT deployed)** | **What you will see:** the right-hand panel never shrinks below 400px, so the three status boxes sit side by side with whole words at every laptop and monitor size; with the document hidden the Summary uses the width instead of a narrow strip. **Contents** is now the document's own outline as a tree — real numbers exactly as written (no "§" anywhere any more), chevrons to open a section, the section you are reading opens itself — and two clauses that were missing (8 and 11) are back: the parser skips a title with a comma in it, so the panel now reads those lines itself; "BETWEEN" and "AND" are gone from the list. **Key obligations:** each group has its own "Show 1 more" / "Show less", and the count always matches what you can open. **The two "Auto-renewal" findings are two different checks** (one measures the renewal period, one checks the clause is present; both apply because your TOS standard's wording matches clause 5.2) — they now say what each one asks, beside "MSA standard" / "TOS standard". Merging them would change your applicability rule (AM-51), so that is your call, not mine. **Ask** opens as the whole right column — your question on the right, the answer as plain text, sources beneath — and when the document answers, the relevant approved position is quoted beside it with the evaluator's existing verdict for that standard ("Assessment") and a link to the Finding. Ask itself still never judges anything. **Boxes inside boxes** reduced across the Summary. **Not changed:** the document parser (your locked rule), the refusal wording, any legal logic. **Needs:** PR → merge → deploy (frontend + API restart; no migration) — say "deploy". |
| 🔧 **10 Sep — Ask now looks everywhere it is allowed to before saying "not found" (LOCAL — committed, NOT deployed)** | **What you reported:** "What is the termination notice period?" came back "Information not found in the selected document" although the approved positions hold the answer. **What was actually happening, traced on your own question's record:** the question was searched in the document only; the document *did* mention termination, so the AI was consulted, said it could not find it, and that path refused without ever looking at the approved positions or the law library; and when the AI *did* give a correct, verified answer, a safety screen threw it away because the sentence named "Leapswitch" and the word "breach" — read as a compliance verdict. Underneath, the search itself missed the clause that states the notice (it lacks the word "period") while bare headings filled the results. **Now:** every question is checked against the document first, then the approved positions, then the law library when the question is about the law or nothing closer answers — and "not found" is said only after all of them, naming which were checked. The heading fragments no longer crowd out clauses; paraphrases reach a position by meaning, not just by shared words. **Your question now answers from the MSA itself with four cited clauses** (force majeure 60 days; breach cured within 30 days of written notice; 30 days for non-payment; 5 days for suspension); asked with no document open it quotes the approved positions; nonsense is still refused once. The AI quality gate passed with better recall than before and no more wrong answers (1 of 13 unanswerable, same as before); the variant that would have made it answer all 13 was measured and rejected. Permissions unchanged: an account without the position grant still never sees a position. **Needs deploy** (API restart; no database migration) — say "deploy". |
| ✅ **9 Sep (late) — it is LIVE, and the colours are the ones you asked for** | **What changed for you:** everything from the last few days is now on the live site — the three words (Acceptable, Requires modification, Needs a decision), the restyled Summary and Findings, the plain-English explanation on each Finding, real deletion beside Archive, and the Contents panel that now finds the clause numbers Word had hidden. **The colour question is settled your way**: Acceptable is green, Requires modification is amber, Needs a decision is indigo. **No database change was needed** — the live database was already up to date, so the migration everyone was waiting on had already happened. **Three things you should know.** (1) The work being merged had never been checked by the automated gate, and when it finally ran it found three tests that were passing while testing nothing at all — including the one that guards your internal legal positions from leaking. Nothing had leaked; the test had simply stopped looking. All three are fixed. (2) The security scanner flags a serious Next.js advisory. It does not apply to us — one half is Windows-only and we run Linux, the other needs an image feature this app never uses — and the live site was already running that same version, so nothing got worse today. The upgrade is a separate job. (3) On a narrow screen the three status boxes are breaking words in half ("Requir es modific ation"). Cosmetic, real, and not fixed tonight because another session is editing that same file. **Not live yet**: the new document-first workspace layout, and an improvement to how Ask searches. Both are finished and waiting their turn. |
| 🔧 **9 Sep — Upload → Review → Ask, the way you described it (LOCAL — committed, NOT deployed, live DB NOT migrated)** | **What changes for a user:** upload a contract and, when LegalMind can tell what it is, the review simply starts — "Reviewed as Master Services Agreement — change it any time in Edit details"; only when it cannot tell does it ask one question. Ask answers statute and company-position questions even with a document open, and a question the document cannot answer is tried against the law library and the approved positions before any refusal. The Summary counts Accepted / Needs review / Not accepted and how many need a legal decision, in those words. Findings keep the wide column; "Show document" opens the document beside them at a width you can drag. Every Finding also gets one plain-English sentence explaining what the requirement means (generated from the approved description and the cited passages, checked word by word, cached). **Three of your earlier decisions were amended on your instruction and recorded** (automatic type at intake, the Summary's words, the document layout) — the audit trail now says whether a type came from you or from the suggestion, and the evaluator still refuses an undeclared type. **Needs deploy + one database migration** (a small table for the explanations) — say "deploy". |
| ✅ **8 Sep (night) — LIVE on your "ok deploy": the new Finding card, the law library, the Constitution router** | The server was restarted at 22:53 and the interface rebuilt and swapped at 22:54 (all 1,362 backend checks passed first; no database migration was needed). **What you see now:** every finding card says one of three words — **Accepted**, **Needs review**, **Not accepted** — with the engine's own terms one click away under "How this was determined"; Ask picks its own sources and can answer statute questions (17 Acts). **Not accepted cannot appear yet**: it only shows when the server states that your Constitution explicitly rules the position unacceptable, and the server does not send that yet — Counsel must mark which "Unacceptable Position" entries apply. **Three steps I could not run** (they write to the live database and my permissions blocked them — your call): import + publish the six Constitution-reconciled standards (live analysis still uses the 1 Sep values, e.g. MSA liability 6 months); reindex the 40 older documents so Ask reads them with the fixed chunking; and decide whether the Summary tiles should also use the three words (they still say MATCH / DEVIATION per your 1 Sep correction). Reload the page once. |
| ✅ **8 Sep (evening) — the law library is complete except one Act (now LIVE, see above)** | You asked me to stop claiming statutes were missing and go get them from official sources. **Found already here:** the DPDP Act 2023 and the six other statutes you supplied on 18 Aug. **Obtained from India Code** (the Government's official statute repository, through its own data interface, with the source link, the "as on" date and a checksum recorded for each): the Negotiable Instruments Act, the Arbitration Act, the Civil Procedure Code, the Copyright Act, the Bharatiya Sakshya Adhiniyam 2023, the CGST and IGST Acts, the full Companies Act 2013 and the old Companies Act 1956; the DPDP Rules 2025 from MeitY's gazette copy; the Income-tax Act 1961 from the Revenue Department (only a 2011 edition exists there, and that Act was repealed on 1 April 2026 — both facts are recorded). **The Evidence Act was never missing:** your Constitution says the BSA 2023 replaced it, so the BSA is what the system holds. **Still not obtainable: the Income-tax Act 2025** — the Income Tax Department's and the Gazette's sites refuse connections from the server. **"What does Section 138 say?" now answers, citing *The Negotiable Instruments Act, 1881, s. 138*.** 17 statutes, 5,140 sections in the library; nothing deployed. |
| ✅ **8 Sep — your Constitution now governs, and Ask picks its own sources (AB-14; LIVE 22:53 — standards import/publish still pending, see above)** | **What you asked for, in plain words:** a user uploads any document and just asks. **What I found by using the live site as an ordinary user:** your own comparison question — *"compare this document with our approved legal position"* — was refused as "not found in the selected document", and three ordinary questions the document *did* answer were refused too, because a third of the search index was bare headings like `7. TERM AND TERMINATION` crowding out the clauses beneath them. **Fixed:** the index now keeps headings with their clauses (your test account's documents are re-indexed; **everyone else's documents need one re-index after the next deploy — an operator step**); comparison questions in any natural wording now go to the deterministic comparison engine and come back with the Review's Finding counts and a link; a question about the company's position quotes the approved standard word-for-word beside the document answer; a question about the law is answered from the seven statutes you supplied, cited by Act and section — and *Section 138* still says, honestly, that the Negotiable Instruments Act was never supplied. **The Constitution:** treated as the governing source per your ruling. **Six standards changed to its values** (liability MSA 6→**12 months of total fees**; late fee 5→**2 %**; SLA claim window 60→**30 days**; data retrieval 7→**30 days**; data purge 15→**30 days**; NDA confidentiality 2→**3 years**) — which means **your own live TOS, SLA, NDA and MSA template now show as DEVIATIONS on those six points**; the Constitution itself says those drafting corrections are in progress. ⚠️ **One thing you said the other way round:** your example was "existing 12, Constitution 6 → 6". The Constitution says **12**; the MSA template said 6. I followed the Constitution. **Not decided, needs you or Counsel:** the Constitution's Risk Level (§24.1) has no rule for assigning High/Medium/Low, so it stays out; the Leapswitch-vs-CloudPe brand axis (§4) does not exist in the data model (C-19); the NI Act and Evidence Act are not on disk. Nothing was deployed or migrated. |
| ✅ **6 Sep (afternoon) — EVERYTHING ABOVE IS LIVE. Migrated, restarted, deployed, smoke-tested (your GO)** | The live database was backed up, then moved through the two pending migrations in order (the access-model change, then the company table) — 42 contracts and 6 users intact, nothing backfilled or rewritten. The API and the interface were restarted/deployed from the committed code. I then used the site as the ordinary `test@leapswitch.com` account: sign in, upload, declare the document's source/company/date, link a company, see its documents together, run an analysis, follow a finding to its clause, hit the two deliberate refusals (no re-read and no edit once a review exists), and confirm an ordinary user is refused the admin screens — all working. **Two things deploying uncovered and I fixed on the spot:** the deployment pre-check tool had never actually been runnable, and **Word (.docx) uploads were not getting the new outline or annexure detection at all** — only PDFs were; both now work and are verified live. Two clearly named `SMOKE` contracts were created and archived; the test account's password was rotated to an unknown value afterwards. **Still needs your eyes:** log in as yourself and open the Administration area (an admin login is not something I create on the live system), and the department for the Lead view is still not created (AB-12's note stands). |
| 🔧 **6 Sep (later) — a counterparty is now a real company record, and one company's documents finally sit together (LOCAL — not committed, not deployed)** | **This is the last of the manager's product-coherence points.** Until now the other side of a deal was just a name typed on one version — so "Acme Ltd" and "Acme Limited" were two unrelated bits of text and nothing could group them. There is now a real **company record** (name, and optionally industry and a note — both left empty unless you type them, because inventing a company's industry is exactly what the rules forbid), and each deal can be **linked** to one. Open a company and you see **every document for it — the NDA, the MSA, their revisions — in one place**, which is what you asked for. Deliberately NOT built: a separate "deal/matter" object (purchase orders are out of V1 scope by an existing locked decision, so a matter would have been a box nothing goes in), and any document-to-document linking table — once the company is a real record, "related documents" is just a lookup. **Privacy held:** a company is only ever visible to someone who already shares a deal with it, or who created it; there is deliberately no screen listing every company you deal with. This needed a **new database table**, so it required changing a locked decision — that is written up as lock record **AB-13** with the reasoning, as you instructed. **Not applied to the live database.** |
| 🔧 **6 Sep — a document now records whose paper it is, who the other side is, and when it took effect (LOCAL — not committed, not deployed)** | **Three new fields at upload and in Edit details: Source (our document / the counterparty's), Counterparty, and Effective date.** All optional, all declared by you — nothing is ever read out of the document text. Stored on the version, because a document's source changes between versions (our template, then their redline); no new table, no schema change. **Fixed once a review exists**, as you ruled — the dialog says so and the server refuses regardless. The counterparty box suggests only names you have already used. Also done under your autonomous-execution instruction: the document pane, comparison and unmatched-provision logic now all read ONE processing run (a latent merge defect, dormant today, closed before any reprocessing exists); the Findings list puts what needs a decision first and then follows the document's own order; and the Contents outline divides a document at the annexures and appendices it declares — measured on your real GRP MSA, where all five annexure titles had been missed. **Two more, on your decisions of 6 Sep:** a document that nobody has reviewed yet can be **re-read with the current parser** in place (so an old upload gains the new outline and annexures) — the old reading is kept as history, and the moment a review, an Ask answer or Key Obligations rely on it, the system refuses and tells you to upload a new version instead; and a contract's own state — **Draft, Active or Superseded** — is now yours to set in Edit details, shown in words in the workspace header, with every change on the audit trail. Nothing guesses it from a date. Everything was re-checked from a clean stack: 1,282 backend tests pass (the one failure is still the on-purpose check that the live database has not been migrated yet), 214 frontend tests, the whole browser suite (94 pass, 0 fail), the reproducibility gate passes, and the AI-lane quality gate reports exactly the same numbers as before — proof that the outline change touched no text. **Waiting on you:** whether to commit all of this; the 5 Sep deployment order (migrate → restart API → deploy frontend) still stands. |
| 🔧 **5 Sep — the access model is rebuilt around your six answers (AB-12), LOCALLY — not deployed** | **Four kinds of people now, in plain words: Department User, Department Lead, Platform Admin, Developer.** A user sees only their own deals — and now also *why* each finding is what it is. The Lead sees every deal in **their department** (never the whole company), can hand a deal from one colleague to another with a reason that is recorded, and owns the standards. The administrator manages accounts and departments and cannot open a deal. The developer role can no longer make a legal decision. **Delete is gone — it is Archive now**, and nothing is ever destroyed: an archived contract keeps its document, versions, findings and history, becomes read-only, and can be restored. Nobody approves a deviation inside LegalMind, exactly as you said; a flagged review simply stays flagged. **Two things wait on you:** (1) this is on the server's code but **not live** — the live database has not been migrated and the API not restarted, and the order matters (migrate, then restart the API, then the interface); (2) after that, create a department in Administration and place yourself and the team in it, or the Lead view stays empty. Backend: 1,211 tests pass and exactly one fails on purpose — the check that asks whether the live database has the new migration (it doesn't, yet); frontend 195 pass; the browser suite is being run by the other working session. Full read: [RBAC_MODEL.md](../06-security/RBAC_MODEL.md) |
| ✅ **4 Sep — version comparison is built (your decision #3), locally** | **You can now see what changed between two versions of the same document.** Open a contract that has more than one version and there is a **Compare versions** button beside the version picker: it lists every numbered clause as *new*, *gone*, *wording changed* or *unchanged*, with the before and after text side by side, and the page tells you it matched clauses on the document's own numbering. Deliberately **not** a Word-style redline — your own instruction, and also the specification's: this comparison is required to be plain deterministic section matching with no AI anywhere near it. **What it will never do**, because your locked rules forbid it: say whether a change is acceptable. There is no verdict, and I deliberately gave the status words no colour either — a red "changed" would be a legal opinion the engine never gave. Where the analysis already has a finding on a clause that changed, it is shown beside it as *the analysis's* finding, read-only. Unchanged clauses are collapsed behind a "show unchanged" link rather than dropped, so you can still answer "did the rest of the document stay put?". **Not deployed** — local only, as you instructed. |
| 📁 **4 Sep — Research: the R&D you asked for first (decision #4), and one finding decides the design** | **I measured rather than guessed, and the answer is uncomfortable but clear: Hindi and Hinglish do not partially work today — they retrieve noise.** The search model currently installed is English-only. Asked in Hindi, the *correct* answering text scores 0.037 out of 1 — **lower than two completely unrelated English sentences** (0.100) — against a 0.50 bar. In English the same question scores 0.725. Hinglish lands at 0.315, still under the bar. So multilingual research is a **model** question, not a wording or a threshold question, and **I am specifically not proposing to lower the bar**: that would give away the refusal behaviour we calibrated and *still* wouldn't let the Hindi question through. What I recommend instead is a multilingual model for statute research only, chosen by measurement the way the locked rules require — which needs about 20–30 real Hindi/Hinglish questions from you, each with the Act and section that answers it. **A second finding is good news:** your own headline example — *"what does Section 138 of the NI Act say?"* — is a **lookup, not a search**. It names its own answer's address, so it can be answered exactly, with no AI, no scoring and nothing to verify — and it works identically in Hindi, because "धारा 138" and "Section 138" point at the same row. That is the first thing I would build. **Nothing was built and nothing in the search system was touched.** Full document: [RESEARCH_DOMAIN_C_RD_2026-09-04.md](RESEARCH_DOMAIN_C_RD_2026-09-04.md). **Still blocked on you:** the statute files themselves and the Evidence Act 1872 vs BSA 2023 answer (C-16, unchanged). |
| ✅ **3 Sep (later) — the two problems you reported are FIXED AND LIVE (you approved; deployed 17:37)** | **1) The ~62-second wait is gone.** I measured where it went: 63 of the 64 seconds were the OCR reading pages, inside the upload itself. Now the upload finishes in under a second, **you can open and read your actual document immediately**, and the text-reading continues in the background (~20s for your 30-page MSA, down from 63s — pages are now read in parallel with identical output); clauses and findings appear on their own when it finishes, and the screen says honestly "text is still being recovered" in the meantime. Nothing is faked: analysis is refused until real text exists. **2) The viewer now shows your ORIGINAL document.** A new "Original" tab — the default for PDFs — shows the file exactly as you uploaded it: the STRAD logo, the bold and underlined headings, the real layout, rendered by the browser's own PDF viewer. The extracted text moved to a "Text" tab one click away (clicking a clause or a citation takes you there automatically, since that is where passages can be highlighted). And the `OCR OCR OCR` clutter is gone — a recovered page now says "recovered by OCR" once, at the top of the page, not above every paragraph. Your pre-deployment review then caught the one real gap — a server restart mid-OCR would have stranded the document in "processing" forever — and that was fixed and PROVEN before deploying (the process was killed mid-OCR and the restarted server finished the job by itself). **Deployed on your approval at 17:37; verified live**: a fresh upload returned in 0.8s, the original PDF was on screen in 2.5s, text and findings arrived ~29s later in the background — and within minutes a real colleague uploaded two real documents through the new pipeline and got an answered question, all without knowing anything had changed. One smoke-test contract ("indicosmic", test account) was created during verification and left in place — say the word if you want it removed. |
| **Last worked** | 2 September 2026 (Ask fixed — the "go to the update" message and the space the chat took) · *(same day, earlier:)* the Dashboard rebuild you asked for — a real fault fixed, contract deletion built on your approval, and the screen renamed) · *(earlier:)* 1 September 2026 (Google sign-in — "Continue with Google" now works end to end, and needs one thing from you: the client secret) · 31 August 2026 (night — the AB-7 build you approved: auto-suggested document type, Key Obligations, the 3-column workspace with the always-visible Ask bar) |
| **Ask, 2 Sep** | **Both things you reported are fixed, and the first one was hiding something worse than the message.** You uploaded a revised version, opened the original, and Ask told you to go to the update. The message was a symptom. The server could only ever answer from the *newest* version and had no way to be told otherwise — so an answer read while the original was on screen actually came from the other document, and the "jump to the passage" links pointed at passages that were not on the page: nothing moved, and the screen reader said something had. Disabling the box was the only honest thing the screen could do with that. **I checked your own data before changing anything, and it had already happened to you**: that contract's version 2 is the *analysis report PDF* that got re-uploaded, and the answer you received had been read out of the report, not out of the MSA you were looking at. **Now: Ask answers about whatever version you have open**, says which one at the top of the panel, and if an older answer in your history came from a different version it says so and offers to open that version instead of quietly failing. · **And the chat no longer takes a strip off the bottom of every screen** — it is a small "Ask" button in the corner that opens a panel over the workspace. The document, clauses and findings keep the full height. Opening it does not cover the document or replace anything: you can still click a clause, scroll and read with the panel open, and Escape closes it. Deliberately *not* opens-on-hover — that cannot work on a touch screen and would pop open constantly while you read. |
| **DOCX pages, 2 Sep** | **Word documents now show real page numbers.** Your MSA opened as "Not paginated" because a Word file, unlike a PDF, doesn't physically contain pages. It turns out Word records where the pages fell when the file was last saved, inside the file itself — the pipeline now reads that record, so the MSA shows **27 pages** (matching what Word shows you), with page navigation and finding→page jumps. Nothing is guessed: a Word file saved by a tool that doesn't record pagination (Google Docs exports) will still honestly say "Not paginated" — if you ever need pages for those too, the option is a rendering engine on the server, which is your call to approve. Upload limit is now **25 MB** for both formats, and the upload box states PDF is preferred. |
| **The Dashboard, 2 Sep** | **Rebuilt, and it was hiding a real fault.** The "Needs Attention" panel only ever looked at the 25 contracts currently on screen. If a contract needing your attention wasn't among those 25 — because it was older, or you had a filter on — the panel showed **nothing at all**, while the counter beside it still said there were 12. It read as "all clear" when it wasn't. It now asks the server for the contracts needing attention directly and lists up to five. Also: the "Documents" screen is now called **Dashboard** (your instruction); the upload box no longer sits open taking up a third of the screen — it's a button that opens when you want it; the five-step "how this works" strip now appears only on a brand-new empty account instead of on every visit; the table text is readable again (it had been shrunk below the rest of the page); and each row now has **Edit details** and **Delete**. |
| **Deleting a contract, 2 Sep** | **Built on your approval — and it deliberately does two different things.** If a contract has never been analysed (you uploaded the wrong file), Delete really destroys it: the record, the file, everything. If it *has* been analysed, Delete removes it from your workspace but **keeps the findings, decisions and history**. That second case is not a compromise I chose quietly — it is what your own rule 17 requires (analysis history must stay reproducible), and you approved deletion, not the loss of legal history. The confirmation box tells you which of the two will happen before you confirm. You can delete contracts you uploaded; you cannot delete anyone else's. **Not built:** any way to bring back a contract you removed — that is a separate decision I have not taken for you. |
| **Follow-up pass, 2 Sep (evening)** | **The three loose ends from the Ask work are closed locally, and two of them wait on one word from you.** (1) *Permissions:* the audit is done — exactly four grants are missing from the live database, all four are your own recorded decisions (Export for ordinary users and legal staff, 31 Aug; Delete for ordinary users, 1 Sep — the locked AB-10 record), nothing extra exists anywhere, and the audit trail proves no administrator ever removed anything. A one-command repair exists, is tested six ways, can only ever ADD the decided grants, and refuses to run on any database an administrator has since shaped by hand. **It has not touched the live database — say the word.** (2) *The build accident:* the guard that failed now lives where it cannot be bypassed — inside the build's own configuration — proven by running the dangerous command and watching it refuse with the live build untouched, byte for byte. (3) *The restart-order trap:* the frontend deploy script now refuses to ship ahead of the API, and one new command (`ops/deploy.sh`) deploys both in the right order with health checks. Also measured, since you'd reported a 10-minute "In Progress": your own document's processing took **6.8 seconds** end to end on the server — the full timing breakdown is in the records, and the two small screen-labelling gaps found along the way are noted for the other work-stream that owns those files. |
| ✅ **OCR installed, 3 Sep — your MSA now reads properly** | **You installed the OCR tools and I verified the document end to end.** It went from *nothing readable* to **all 30 pages, 413 passages, and 109 numbered clauses** — the Clauses panel that said "No clause numbering was detected" will now list §1 through §25. I checked the text against your own PDF and it matches, including clause 13.1 word for word. Takes about a minute for a 30-page document (OCR reads each page as an image, which is slower than reading text directly) and every passage is labelled as OCR-derived, never passed off as clean text. **To use it: re-upload the document** — the failed version cannot re-read itself. **One thing to expect on this particular contract:** its liability cap is *"the **average** price or fee paid over a three (3) month period"*. An average is not a total, so by your own 18 Aug ruling it is **not comparable** to our approved 12-months-of-total-fees position — LegalMind will send it to a person rather than call it a match or a deviation. That is correct, not a failure. |
| 🔴 **A serious one, 3 Sep — your uploaded MSA was unreadable, and LegalMind analysed it anyway** | **You saw it: the document viewer showed "MaVWeU SeUYLceV AgUeePeQW" instead of "Master Services Agreement". Here is what was actually wrong, and it was worse than the display.** The PDF carries its fonts with a faulty internal character map — the file tells us letter 'm' where it means 'z', consistently shifted, for every letter from 'm' onward. A PDF viewer never notices, because it draws the *shapes*; we read the *codes*, so we got nonsense. LegalMind's check for "did we get any text?" only counted characters — and it got nearly 2,000 of them on page one, so it decided all was well. **The consequence you could not see: it then ran a legal analysis on that nonsense and reported 3 MATCH findings — i.e. "this contract agrees with our approved position" — based on text nobody could read.** That is the part I treated as urgent. **Now:** LegalMind checks whether extracted text is actually *language*, not just present. A document that fails is either re-read by OCR (where that is installed) or **refused outright** — no text, no clauses, and **no findings at all**. Not "missing" either, because that would claim the clause isn't in your contract when the truth is we couldn't read it. The screen now says so plainly and suggests re-exporting the file. I checked the rule against all 21 of your real documents: **the bad one is caught, all 20 good ones are untouched.** **What I need from you:** see the OCR question below — installing it is what would make this document actually *work* rather than be honestly refused. |
| ⚠️ **The upload wait, measured, 3 Sep** | **There is no slowness to fix, and I want to be straight about that rather than "optimise" something.** You mentioned a document sitting "In Progress" for about ten minutes. I measured every stage on your own files: reading a Word file 0.2 s, reading a PDF 0.26 s, loading the AI search model 0.4 s, and building all 325 searchable pieces 1.6 s — **about 2 seconds of computer time in total**, and the database confirms every document ever processed took between 0.0 and 0.2 seconds. The minutes are the step where LegalMind waits for **you** to confirm the document type before it starts analysing — which is deliberate (you ruled that the type is declared by a person, never guessed). So I changed nothing: adding caching or background workers would be speeding up a two-second job. If you see a long wait again, the useful thing to tell me is whether the screen was waiting for a click. |
| ⚠️ **One deploy step you should know about, 2 Sep** | **The API and the interface now have to be restarted together, API first.** This change adds one field to a request the interface sends, and the server is configured to reject any field it does not recognise — deliberately, so a typo can never be silently accepted. The consequence: for the few minutes when the new interface was live against the not-yet-restarted server, **every question came back "The request could not be validated."** I hit exactly that while testing and restarted the API, which fixed it. The deploy script only restarts the interface; nothing in the project restarts the API. **If Ask ever says that sentence, the answer is `systemctl restart legalmind-api`.** I have not changed the deploy script — that is deployment sequencing and your call. |
| ⚠️ **A test tool had been quietly breaking the live site, 2 Sep** | **Found by walking into it, and now fixed.** The automated browser tests built the interface into the *same folder the live site is served from*, and a build wipes that folder and writes new files with new names. The running site kept asking the browser for the old names, so **every page lost its styling** — while the server still answered "200 OK", so no automated check noticed. That is the same accident that took the site down on 1 Sep, and the safety net written that day did not catch it because it only guards the command a person types, not the one the test tool used. The tests now build into their own folder; I proved it by running them and confirming the live build was untouched, byte for byte. Any local test run before today's fix would have had this effect until the next deploy. |
| ⚠️ **Found while testing as an ordinary user, 2 Sep** | **Export and Delete do not work for anyone but you, and the database is why.** I created an ordinary test account and ran the whole workflow as that account rather than as an administrator. Two permissions the code says an ordinary user should have — **Export** (added on your 31 Aug instruction) and **Delete** (approved by you on 1 Sep) — are **not actually granted in the live database.** The seeding routine deliberately never re-grants to a role that already has some permissions, in case an administrator had removed one on purpose; both permissions were added to the code *after* those roles were first created, so neither ever landed. Your own account works because it holds the DEVELOPER role, which was created afterwards and got the full set. So the notes above saying "Export works" and "each row now has Delete" are true **for you and nobody else.** Fixing it is a one-off data correction, not a rule change — but it changes who can do what, so I have not done it as part of an Ask task. **Say the word and it takes a minute.** |
| **Current phase** | **STABILIZATION + owner-requested UI passes.** The build sequence is complete; work now arrives as specific things you ask for (the 2 Sep Dashboard rebuild, the 1 Sep Google sign-in) rather than as a plan running to completion. The UI stays frozen between those requests. The one genuinely unfinished area is still the golden corpus, which waits on a second document tranche from you · *(earlier:)* **UI/UX IMPLEMENTATION — slice 1 delivered** (your GO, 30 Aug): the new workspace's shell and document pane live at `/workspace/<contract>` · *(earlier:)* **GAP-CLOSING + UI/UX PHASE STARTED** (your later instruction, 27 Aug, which also authorized UI/UX in parallel) · everything closable without your inputs is closed; C-15 is resolved (AM-32 built); the one real external gate left is the Gemini terms + key |
| **AM-32 (AB-5)** | ✅ **Approved and built, 27 Aug** — the positions/statute search tables exist and C-15 is resolved. *(This row previously still asked for the approval; corrected 30 Aug — rule 23, never re-ask a decided thing.)* ~~One question stays open in [STATUTE_INTAKE.md](STATUTE_INTAKE.md): the Evidence Act 1872 was repealed by the Bharatiya Sakshya Adhiniyam 2023 — which do you want indexed?~~ **Answered 8 Sep by your Constitution (§6.1): the BSA 2023 — obtained from India Code and indexed.** |
| **UI/UX** | **FROZEN — plus two passes you asked for on 31 Aug**: the polish pass ("use plugin to make frontend design better" — hover/press feedback on every clickable control, counts in the monospace voice, a bounded reading width) and **the real typefaces ("approve the font bundling" — DD-8)**: the product now renders in IBM Plex Sans/Mono and Source Serif, downloaded once at build time and served from our own server — no page ever contacts Google for a font. All checks re-run green after each; the freeze stands again. *(earlier:)* All six areas built, audited, baselined: 15 CI-cut screenshots pin every screen. From here the UI changes only for real defects or new features. Research stays an honest placeholder until your C-16 statute decision. |
| **The freeze report (morning 27 Aug)** | [BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md) — the completed/blocked/operator-only breakdown and the verified API contract; superseded the same day by your gap-closing directive, but its contract verification stands |
| **Health** | **1,161 backend + 187 frontend + 77 browser checks passing, none failing** (1 skipped, 1 expected-fail; re-measured 4 Sep by running all three suites). *(earlier:)* 1,110 backend + 184 frontend + 71 browser checks passing, none failing (1 skipped); CI (15 jobs) green on every push. *(Counts re-measured 2 Sep evening by running both suites — not carried over. Note: the visual baselines are expected to fail their next CI run once, deliberately — the workspace redesign changed the screenshots; the job's fresh captures get adopted per the standing rule.)* |
| **Google sign-in, 1 Sep** | **BUILT and configured — one click left, in your Google console.** You supplied the client secret and it is set on the server; the button now really does hand you to Google. Google is currently answering *"redirect URI mismatch"*, because that client still lists `https://legalmind.lsnw.io` with no path. Change it to `https://legalmind.lsnw.io/api/v1/auth/oidc/callback` and sign-in works. ⚠️ **Rotate that secret when convenient** — it came through chat, so treat it as exposed. *(Also fixed today: the live API had been running as a leftover development process rather than its proper service since 13:16, which had quietly relaxed the login rate limit.)* Detail below. |
| **Session tokens, 1 Sep** | **CHANGED ON YOUR INSTRUCTION, and you should know what it cost.** You asked for JWT session tokens; I recommended against it and you chose it anyway, which is your call — it is recorded as your decision, with my written objection kept inside the record. What changed in plain terms: a signed 24-hour token now rides along with the normal session. **The thing we gave up:** that token cannot be cancelled. Previously, disabling someone cut their access instantly. Now, if a token is stolen it keeps working for up to 24 hours and nothing on our side can stop it — rotating the signing key is the only blunt instrument. **What I protected anyway:** the token *says* what roles you have but the system never believes it — permissions are still looked up fresh from the database on every single request, so removing someone's rights still takes effect immediately; a disabled account is refused immediately; and signing out clears the token. There is a test that deliberately proves the loss is real, so it stays visible rather than forgotten. |
| **Google sign-in — what it does** | **BUILT.** The "Continue with Google" button on the sign-in page is now a real sign-in, not a placeholder — this was always the *primary* way in that the specification called for, and the password form stays as the fallback. Three things worth knowing: no new software was needed (the earlier note about a "JWT library awaiting your approval" turned out not to apply); **Google cannot create accounts** — someone signing in with a Google address we have no account for is simply refused, exactly as before; and signing in with Google gives no extra powers, same as signing in with a password. **One thing left, and only you can do it: the client secret** — see [What I'll need from you](#what-ill-need-from-you-and-when) §3 |
| **Waiting on you** | ~~Google's written no-training terms and a Gemini API key~~ — **both supplied 31 Aug: the gate is OPEN and Gemini answers work end to end** (verified live with a synthetic document; key stored outside the repository and audited absent from repo and logs). ~~Still open: the statute material (and the Evidence Act 1872 vs BSA 2023 answer) for statute search~~ **Closed 8 Sep** — 17 statutes indexed from official sources; the one still missing is the **Income-tax Act 2025** (no official host reachable — please supply the PDF, or say the 1961 text may stand as history) |
| **Gemini, 31 Aug** | **LIVE.** You confirmed the paid-tier no-training terms ("confirm"); the release record is appended and the gate opened in the same commit. One catch handled: Google retired the old Flash model for new accounts, so the pin moved to gemini-3.6-flash (family was locked, version wasn't). One follow-up for me, not you: the answer-quality baseline must be measured before AI answers over real contracts are relied on |
| **Next step once an input arrives** | Resume exactly that thread — the mapping from each input to its work is the last section of [BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md) |
| **Your instruction, 27 Aug** | *"Backend freeze / dependency-wait state... VERIFY → DOCUMENT → FREEZE → PREPARE HANDOFF → WAIT FOR OWNER INPUT. Do not manufacture additional coding work. Do not start UI/UX."* Done and logged — the handoff report is written, everything re-verified, no code changed, and nothing starts without your explicit word |
| **Your instruction, 26 Aug** | *"Keep the Gemini production gate CLOSED until I provide the required Google terms confirmation. Continue with any safe remaining work."* Logged. The gate was already closed by default — this changes no code, and nothing further will touch it until you provide that confirmation |
| **Your instruction, 26 Aug (later)** | *"Backend first. UI/UX later. Preserve the existing UI code but treat its previous design as obsolete for planning purposes... When the backend/API architecture is genuinely ready to support a new UI/UX implementation, stop and tell me clearly."* Logged. The current screens stay in place and their tests keep running, but no further design or polish work goes into them. The backend is being closed out against the surfaces a new UI will need; the readiness call comes as an explicit statement, with the owner-gated items named |

**What got finished on 30 August (your "GO" on UI/UX)**

- **The new interface exists now, starting from its riskiest piece.** Open a contract at
  `/workspace/<id>` and you're in the new application: one dark bar, navigation that only
  shows what your account can do, and the document laid out exactly as the system read it
  — page by page, with the clause list beside it. **Click a clause and the passage lights
  up, scrolls into view and takes keyboard focus; copy the address bar and a colleague
  lands on the same passage.** That single gesture is what verdicts and citations will
  use next — proving it first was the whole point of doing this slice first.
- **Every state is designed, not just the happy path**: still-processing, no text
  extracted, no upload yet (with the real upload link), errors with a reference id, and
  someone else's contract reading *exactly* like one that doesn't exist. On a narrow
  screen the three regions become real tabs; nothing is ever dropped.
- **One small backend addition was needed and made honestly**: a contract now lists its
  document versions, because nothing did and the workspace opens on a document.
- The Findings and Ask panes say plainly that they arrive in the next slice — no fake
  controls.

**What got finished on 31 August (night — the reference-screenshot rework, AB-7)**

- **Uploading is now one gesture.** Pick a file and LegalMind creates the record,
  uploads it, reads the opening pages, and *suggests* the document type — you just
  confirm (or correct) and analysis starts. The type is still recorded only by your
  click, never by the AI, so the "human declares the type" rule (Q9) stands in
  substance; the two owner approvals are locked as **AM-34/AM-35 (AB-7)** in
  `all_lock.md`. When the AI isn't confident, the screen behaves exactly as before —
  an empty select and the filename hint.
- **The workspace is the 3-column layout from your screenshots**: document with
  per-clause status dots (green = matches, amber = needs attention — deliberately
  two states, not a severity traffic light), findings in the middle, and a new
  **AI Analysis** column: a ring of the real match/attention counts (no invented
  score), the findings awaiting a decision as "Key risks" that jump to their
  clause, and **Key Obligations** — what each party has to do, in the document's
  own words, each line clickable to its passage. Obligations are a new extraction
  capability: facts only, mechanically screened so a compliance judgment can never
  sneak in as an "obligation".
- **Ask is now a bar pinned to the bottom of the screen** — reachable at any scroll
  position, on any tab, at any width, with the conversation sliding up over the
  page when you want it. On an older version it stays visible but says plainly it
  answers about the latest.
- All verified: 981 backend + 117 frontend + 60 browser checks green. The visual
  baselines will show diffs (the layout genuinely changed) — they get adopted from
  CI per the standing rule, not regenerated locally.

**What got finished on 31 August (evening — your "rethink the UX" directive)**

- **The result screen now IS the drill you described.** The findings pane opens with
  the counts — deviations, missing, matches — and every count is a button that
  filters to exactly those findings. The report page's counts and the Documents
  list's counts are links into the same filtered view. Each finding now shows the
  quoted passage it came from right there (clicking it still lights the passage in
  the document), and "How this result was reached" lays out the full
  evidence→standard→rule chain.
- **A clean result looks like one**: when everything matches, the pane says so
  plainly — no grade, no percentage, just the fact.
- **Ask lives with the finding**: every finding has "Ask about this", which drops an
  editable question into the Ask box (nothing sends until you send it). And the Ask
  panel now remembers — reopening a document brings back your earlier questions and
  their citations.
- **One loop for revisions**: uploading a revised version now starts its analysis
  immediately, the same as a first upload.
- **Documents is your work dashboard**: anything with deviations or missing
  provisions sits in a "Needs attention" group above the full list. No fake metrics.
- **Export works**: any analysed document exports as PDF or DOCX — name, version,
  date, counts, every finding with its evidence — containing only what your account
  is allowed to see. (Email summary is not built: it needs an email system we don't
  have; your call whether to add one.)
- **Everything verified**: 949 backend + 113 frontend + 57 browser checks green.
  One thing I deliberately did NOT do from your instructions: the old screens are
  still in the codebase (unreachable — no navigation leads to them) because the
  automated browser tests still use them as scaffolding; removing them safely is one
  dedicated pass I've named as the next step.

**What got finished on 31 August (your UX audit — upload-first)**

- **The front door now matches the user's job.** One act: upload a contract (pick or
  drop), confirm the name (pre-filled from the filename) and declare the type (with a
  filename hint you can click) — and you land in the workspace with analysis already
  running. No more "create an empty record, then attach a file".
- **Analysis is one click everywhere it's missing** — "Analyze against current
  standards", with the exact standards snapshot named on screen. If no standards are
  published or you lack the permission, it says so plainly instead of dead-ending.
- **The Documents list answers your real question**: each row shows what analysis
  found (deviations, missing, matches) or its real stage — the database's "DRAFT" is
  gone from the screen.

**What got finished on 31 August (your product-direction R&D)**

- **Audited the whole system against your product intent** — the full findings are in
  PRODUCT_INTENT_AUDIT_2026-08-31.md. Most of what you described was already exactly
  how the system works: chat was never gated on fixing anything, re-analysis was
  always real, and comparison / legal decision / workflow were always separate layers.
- **"Acceptable deviation" is now impossible, not just unused.** The old spec still
  allowed a rule form like "12 months is acceptable"; the engine would have honored it
  if ever configured. That form is formally withdrawn (amendment AB-6/AM-33, recorded
  properly, history untouched) and the engine now refuses it outright — a deviation can
  never be called acceptable by any configuration; only a human decides.
- **Revised versions work end to end in the UI**: upload a revised contract from the
  workspace, it becomes a new version with its own real analysis, and every earlier
  version stays readable — its text, findings and report — via a version picker. Ask
  says plainly that it answers about the latest version.

**What got finished on 31 August (the freeze)**

- **Every screen now has a pinned picture.** Nine new baselines were rendered by the
  build system itself, each one inspected before adoption — so any future change that
  moves a pixel unexpectedly fails the build and shows the diff.
- **The final check-everything pass ran green**: all tests, all gates, the whole CI
  pipeline, at the exact commit the freeze names (f9c3c0f).
- **The UI is now frozen.** It changes only for genuine defects or new features you
  ask for — the stable base to build the remaining product functionality on.

**What got finished on 31 August (slices 7–8 + QA close — "you lead")**

- **Admin lives in the new UI.** Add an account (it starts with no roles, and says
  so), grant and revoke roles as labeled chips, disable/restore — and every server
  refusal, including "you can't remove the last decision authority", shows up beside
  the row in the server's own words. The audit trail reads newest-first with exact
  filters.
- **Research exists as an honest placeholder.** It says exactly why it's empty
  (your C-16 statute decision) and offers no fake search box.
- **The roadmap's build order is done.** All six areas in one shell; the QA pass
  re-ran everything green. What's left is on-demand: visual baselines for the new
  screens (from CI, per your rule) and whatever you want changed after using it.

**What got finished on 31 August (slice 6 — "NExt phase")**

- **Legal has its own queue.** Everything awaiting a Legal Decision, across all the
  Reviews the account can see, in one list — with the escalated ones flagged. Only
  accounts with legal review see it at all (others get a plain "access restricted",
  and no menu entry).
- **One click lands the decision-maker on the exact finding**, inside the document's
  workspace — evidence on the left, the decision form right there. The queue itself
  never records anything; ruling stays beside the evidence.
- **Nothing new server-side** — the screen composes what the API already offered, and
  says so plainly when it's showing a window rather than everything.

**What got finished on 31 August (slice 5 — "continue")**

- **Reviews has its own screen.** The queue every account sees is scoped by the server
  (a legal reviewer automatically sees what's escalated to Legal); rows needing legal
  attention are striped, and one click opens the Review's report.
- **The report shows counts, never a grade.** How many requirements were checked, how
  many findings await a decision, what matched — and a sentence on the page saying the
  ratio has no legal meaning, because that's the locked rule.
- **Every question you've asked is kept.** Ask history lists your own conversations
  (only yours — enforced by the server), and opening one replays the exact answer with
  the exact citations, each one clickable back into the document.

**What got finished on 30 August (slice 4 — "go")**

- **The front door is real now.** Log in → Documents: a proper intake with the document
  type as the one required choice (your ten approved types, with a one-line reason why
  we never guess), and "Add and open" takes you straight into the new document's
  workspace to upload. First visit shows an invitation, not an empty table.
- **The type list can't drift.** The interface's copy of the ten types is checked
  against the backend's authoritative list on every build — if anyone changes one side,
  the build fails and says so.
- **Not built yet, on purpose**: a "review state" column on the list (needs a small
  backend addition first — flagged, not smuggled in), and starting a Review from the
  landing (needs a design for choosing the configuration snapshot).

**What got finished on 30 August (slice 3 — "yes go ahead with next phase")**

- **The Ask panel works inside the new workspace.** Type a question about the open
  document; the answer's citations are clickable and light up the exact passage — the
  same gesture as clicking a clause or a finding's evidence. When the document doesn't
  answer, you get the same calm "not found" sentence every time, never an error. When
  the question is really "does this meet our standard?", it tells you plainly that's a
  Findings question and points you there instead of guessing.
- **It's deliberately colourless.** No traffic-light tints, no percentages — so a cited
  answer can never be mistaken for a legal ruling. The word "confidence" cannot appear;
  an automated check fails the build if it ever does.
- **One tiny backend addition**: each citation now also names the exact passage it came
  from, so the highlight can find it. The saved API contract didn't change a byte.
- **Honest limit**: the *written* answers themselves still can't be shown end-to-end —
  that's the Google gate you hold the keys to. Everything up to that sentence is proven
  in a real browser.

**What got finished on 30 August (continued — "ok now go ahead")**

- **The Findings column in the new workspace is real now, not a placeholder.** Open an
  analysed document and you see what needs a decision, first — with the reasoning laid
  out (the clause found, our standard, how they differ) instead of a bare verdict.
  Click the cited passage and it lights up in the document, the same gesture as
  slice 1's outline.
- **Recording a decision and escalating both work.** If two people try to decide the
  same thing at once, the second one sees "Not recorded" plainly and has to explicitly
  refresh before trying again — nothing is silently overwritten.
- **A real bug caught before it ever ran**: my first draft of the "refresh after a
  conflict" button would have left the form stuck forever after the very first
  conflict. Found reviewing my own code, fixed before testing, not found by a user.
- **What's deliberately not built yet, said plainly rather than hidden**: starting a
  brand-new review from this screen (it needs picking a configuration snapshot, a
  separate decision), and the full history of superseded decisions.

**What got finished on 30 August (later — "KEEP LOGIN ONLY" strict cleanup)**

- **The confusion is fixed.** Log in now and you land in the new application, full
  stop — not a screen that might be old or new depending on which link you clicked.
  I audited every route and every link the new screens contained, and found the new
  UI's own top navigation bar was still quietly pointing "Documents" and "Reviews" at
  the old application — the exact kind of thing you asked me to find. Fixed, along
  with three smaller ones (the wordmark, the "no document" upload button, and two
  "coming soon" notes) that also pointed backward.
- **A new "Documents" screen exists** in the new design — the real front door, since
  simply saying "go to the new UI" needs somewhere to land.
- **The upload button on the new screen now genuinely uploads**, in place — it no
  longer sends you back to the old page to do it.
- **Nothing old was deleted.** Every old screen still works exactly as before, still
  reachable directly and still fully tested — you just won't run into one by accident
  anymore.
- **Two real, unrelated bugs surfaced and got fixed** while I was proving the
  redirect actually worked rather than assuming it: the sign-out message was
  blocking the new front door from ever loading for a signed-out visit, and this
  version of the underlying web framework handles page redirects differently than
  expected — both fixed and verified with a real browser test, not just visually.

**What got finished on 27 August (evening — your UI/UX execution directive)**

- **The interface got its first hardening pass for real users.** Loading placeholders now
  hold each page's shape while data arrives (no content jumping); the review screen is
  fully workable from the keyboard — `n`/`p` walk the findings, `?` shows a help panel —
  and the approve/reject keys deliberately only *prepare* a decision: no single keystroke
  can ever record one, and an automated browser test proves it.
- **The two-people-collide case is now airtight on screen.** If someone else decides
  first, the form says plainly "Not recorded", freezes, and stays frozen until you
  explicitly load the latest state — nothing refreshes itself under your eyes mid-read.
- **Two new automatic design gates run on every change**: one fails the build if any
  forbidden wording ("confidence", "risk score"…) enters the interface — tested by
  planting a violation and watching it fail — and one compares five key screens
  pixel-by-pixel against approved reference images, so a visual regression can't slip
  through unnoticed.
- **Usability testing is ready to schedule**: a five-person test plan (two kinds of user,
  four tasks, checklist and feedback form) is written — I need you to name participants
  when you want it run. Two patterns a newcomer would mistake for bugs (hidden
  confidential fields; the identical "not found" reply) are now documented with real
  screenshots so nobody "fixes" a security property.

**What got finished on 27 August (afternoon — your gap-closing directive)**

- **The C-15 decision is ready for you in one read** — the AB-5 proposal drafts the
  exact amendment text: six new tables so positions and statutes become searchable,
  each domain kept separate as you instructed. One catch it bakes in: our own egress
  rule forbids sending approved-position values to Google, so positions answers will
  always be exact quotes of the ratified text — never AI-written.
- **Gemini is now turnkey on your side**: a step-by-step runbook (choose tier → confirm
  written terms → key → verify), and a verification tool that tests the connection with
  inert synthetic text before anything real is trusted to it. The gate stays closed.
- **The statute request is now precise**: what to download from India Code, what
  provenance each file must arrive with — and one question only you can answer (the
  Evidence Act was replaced by a new law in 2023; which one do you want?).
- **Production operations got a real runbook** (`ops/README.md`), every step mapped to
  the automated readiness register, which also gained its one missing row (the network
  egress allow-list).
- **The new UI phase started on your authorization**: the workspace design is planned
  and documented, the design skills were applied (three of their generic suggestions
  were rejected where our own recorded design decisions win — reported, not hidden),
  and the first component is built and tested. Checks: 911 backend + 68 frontend, all
  green.

**What got finished on 27 August (morning)**

- **The backend was formally frozen and the handoff written**, on your instruction. No code
  changed. Every check was re-run first — 901 backend, 62 frontend, 27 browser, lint, types,
  and the contract-drift check — all green. (One environmental fix on this machine only: the
  browser the test suite drives had to be reinstalled after a version bump; no project code
  involved.)
- **[BACKEND_FREEZE_HANDOFF.md](BACKEND_FREEZE_HANDOFF.md)** now records, in one place: what
  is genuinely complete; what waits on a decision from you (C-15 above all); what waits on
  material from you (Google terms, API key, the two statutes); what is operator-only
  production work; the verified API contract a new interface designs against; and which
  screens can be designed now versus which must stay placeholders.
- **The two statuses are kept deliberately separate**: the API surface is stable enough to
  begin UI/UX — but the product is *not* complete, and the report never claims it is.
  UI/UX remains **deferred until you explicitly authorize it**.

**What got finished on 26 August**

- **The backend's "front door" is finished and frozen for the new interface.** Per your
  "backend first" instruction, I checked every screen a new workspace interface would need
  against what the server actually offers, and closed the four gaps: a list of a document's
  past conversations; conversations that **keep their citations when reopened** (before,
  reloading lost them); the document's extracted text with page numbers and positions, so a
  viewer can show and highlight exactly where an answer came from; and a simple "is this
  document searchable yet" indicator. The complete server contract is now saved as a single
  file the interface work designs against, and an automatic check fails if code and contract
  ever drift apart. The current screens are untouched and still pass their tests — they just
  won't receive any more design work.
- **A serious hidden breakage was found and fixed.** The main Review screen — the one
  where findings are read and decisions recorded — had been failing to load for every user
  since 24 August. It was a one-line ordering mistake introduced by a code-review fix that
  day; the kind of error the automatic type checks cannot see and only a real browser can.
  Nobody saw it because the automated browser tests **never ran**: they were configured to
  run only on the main branch, and five days of work went onto a side branch. Fixed, all 27
  browser checks now pass, and the automated checks now run on every push to any branch so
  this cannot hide again.
- **A second hidden breakage in the test tooling, same root cause of "never ran".** The
  day the search-index table was added, every tool that builds a fresh test database
  stopped working (the database add-on the index needs wasn't being installed in fresh
  databases). Fixed in the tooling; production behaviour untouched.
- **The quality bar is now a command, not a promise.** Before any future change to the
  search, the chunking, or the model ships, one command re-runs all 77 of your ratified
  test questions through the real product and **refuses to pass if the system starts
  answering questions it should refuse**. The current, measured bar is recorded in the
  repository; I proved the check can actually fail before trusting it. The half of the
  bar that scores the AI's written answers stays honestly marked "not yet measurable" —
  it needs the Gemini gate open, and our rules forbid faking it with synthetic results.
- **One number worth knowing from that measurement**: end-to-end, the system currently
  finds the right clause for about 44% of fairly-worded questions and refuses 12 of 13
  trick questions. The strict refusal rule is what costs the recall — by design, text
  that scores below the evidence bar is never shown, even when it happens to be right.
  Loosening that trade-off, if we ever want to, now has a safe path: change, re-measure,
  compare against the recorded bar.
- **The development/staging blueprint now enforces the network rules.** The parts of the
  system that touch documents (parsing, indexing, the search model) run on an internal
  network with **no route to the internet at all** — they couldn't send a document out
  even if code tried. Only one component keeps an outbound route: the one that will talk
  to Gemini, which still refuses in production while the gate is closed.
- **Security hardening (Phase 9) started**: two new automated checks run on every change —
  one scans our code's dependencies for known vulnerabilities (backend and frontend, both
  currently clean), the other scans the built application images the same way. **The image
  scan earned its keep on its very first run**: it caught a known high-severity flaw in a
  system library the base image ships (a fix was already published, the base image just
  hadn't been rebuilt yet). Both images now pull in the latest security fixes when they're
  built. Its second catch was in the web-frontend image: nine flaws, all inside the
  package-installer tooling the base image bundles — none in our own code or libraries.
  Rather than chase versions, the running image now carries no installer tooling at all;
  it needs only the runtime to serve pages. Two further scan tools from the plan need a
  running copy of the whole system to point at, so they stay a deployment-time step rather
  than a per-change check.

- **The search model was chosen by measurement, not opinion** — four candidates were
  scored against your ratified 77 questions on the real documents; the smallest one
  that passed won, exactly as our rule requires.
- **The "not found" cut-off was derived from the measurements**, not picked: a simple
  cut-off proved insufficient, so the rule also requires the best match to stand out
  from the field. Result: 12 of 13 unanswerable questions correctly refused.
- **Asking questions works end to end.** On the contract page you can now ask about an
  uploaded document; answers cite the clause and page, every score is labelled a
  "retrieval score" (never confidence), and a refusal reads as a calm "not found".
- **The safety checks went in before the AI**: every sentence of an answer must cite
  its source, and the citation must actually support the claim — checked by code, not
  by the model. Fabricated answers are blocked and the user sees "not found".
- **Gemini is wired but the gate is closed**: nothing real can reach Google until you
  confirm their written no-training terms. That gate cannot be opened by a setting —
  only by a recorded decision.


- **The full test-question set was drafted from your actual documents** — 77 questions
  across the contracts, the policies and the seven statutes, each verified against the
  real text, including 13 questions deliberately designed to have no answer. It's ready
  for your review; nothing has been calibrated against it yet, by design.

**What got finished on 25 August**

- Recorded your Gemini decision as a formal amendment, and finished landing the earlier
  AI amendment across the five documents that were supposed to reflect it but didn't.
- Built the separate storage area for the search index, kept apart from the legal data.
- **Search over uploaded contracts now works** — by phrase, exact wording, or clause
  number, with no AI involved.
- Found and fixed a real problem: contracts were being cut into page-sized pieces instead
  of clause-sized ones, so nothing could cite "§17.2". Now 88% of pieces carry a clause
  number.
- Measured four candidate search models on your real documents — and found that all of
  them lose the ability to say "not found", which is why the model choice is paused.

**Two corrections I owe you from that session**, both cases where I told you something and
then measured it and found I was wrong:

- I said the database search add-on had to be upgraded before we could proceed. **It
  didn't** — I tested the version we have and it works correctly.
- I said the model-running software was about 50MB. **It's 118MB** — I'd forgotten a
  component it depends on. The choice was still right; the number wasn't.

---

## The goal

LegalMind is an internal legal workspace where **every answer shows you where it came from.** Ask it
something and it either points at the exact document, page and clause it found the answer in, or it
tells you plainly that it doesn't know. It never guesses.

It does two different jobs, and keeping them separate is the whole design:

| The job | Who answers | Why it matters |
|---|---|---|
| **"Does this contract match our approved position?"** | The **rules engine** — fixed, repeatable logic. Never the AI | A legal verdict has to be defensible. Same contract in, same verdict out, every time, with the reasoning shown |
| **"What does this document say about X?"** · "What does this statute say?" | The **AI assistant**, but only from text it has actually retrieved | This is reading and explaining, not judging |

The AI never decides whether something is acceptable. It reads, finds, summarises and explains. The
verdict always comes from the rules engine.

---

## What already works

This is a real, working system — not a prototype.

* **The legal rules engine works.** It compares a contract against our approved positions and
  produces a verdict, with the reasoning traceable back to the exact clause it read.
* **894 backend + 62 frontend automated checks pass**, none failing. These run every time
  anything changes, so a change that would break existing behaviour gets caught — and as of
  26 August that includes a check on every dependency and every built application image for
  known security vulnerabilities.
* **Our approved legal positions are already loaded** — **32 of them**, covering our MSA, Terms of
  Service, NDA and SLA. Every one was taken from a real LeapSwitch document and records which clause
  it came from. **This work is done and does not need redoing.**
* **Our position on deviations is settled and built in.** Anything that differs from our approved
  position goes to a human for a decision. Nothing that differs is ever waved through automatically.
* **Reading documents works.** PDFs and Word files, including scanned ones, and it keeps the page
  number and the exact position of every piece of text — which is what makes "show me where you got
  that" possible.
* **Security works.** Every request is checked on the server. Someone who guesses another
  customer's reference number gets the same "not found" they'd get for something that doesn't exist,
  so they can't even confirm it exists.
* **Nothing is invented.** If the system can't extract enough to judge something, it says so rather
  than guessing. That behaviour is deliberate and tested.
* **Nothing currently leaves our servers.** Not one part of the system makes an internet call today, and an automated check now fails the build if that ever changes without it being a deliberate, recorded decision.
* **Searching an uploaded contract works** — by phrase, exact wording, or clause number, with no AI involved. See the current phase below.

---

## What we're building now

The **AI assistant** part is built and working — asking questions about an uploaded document,
with every answer citing its source or plainly saying it doesn't know. What's left is making
our approved positions and the statutes searchable the same way, and finishing hardening.
Neither touches the AI-assistant code that's already shipped.

---

## What's left

In the order it has to happen — each step needs the one before it. **1–6 are done**; only 7
and 8 remain.

1. ~~Storage and database groundwork for the AI's search index, kept completely separate from
   the legal data.~~ **Done.**
2. ~~Plain search over uploaded documents — find exact phrases and clause numbers, no AI
   involved.~~ **Done.**
3. ~~Smarter search that understands wording, not just exact words. Runs on our own
   servers.~~ **Done** — model chosen by measurement against your ratified test questions.
4. ~~The safety checks that verify every claim in an AI answer against the source before
   anyone sees it, built before the AI was connected.~~ **Done.**
5. ~~Connecting Gemini for writing the answers, with strict limits on what gets sent.~~
   **Done** — wired and gated; the gate itself waits on you, see *Blockers*.
6. ~~The single screen where the document, the verdicts and the chat all live together.~~
   **Done.**
7. **Our approved positions and the statutes** made searchable. *Built 8 Sep (AB-14) — locally, not yet deployed.*
8. **Security hardening and final sign-off.** *In progress — dependency and image scanning
   done 26 August; network segmentation, the restricted database account, and the two
   live-instance scan tools remain.*

---

## Current phase

### `PHASE 9 — SECURITY HARDENING` · in progress, not gated on Gemini

Everything through the workspace (phases 0–7) is delivered and working — see *Completed*
below. What's left before final sign-off is hardening and the two statute/positions items
in Phase 8, and neither needs the Gemini gate open.

**What's done in Phase 9 so far**: every code change is now automatically checked for
known security vulnerabilities in two ways — one checks the libraries our own code depends
on (backend and frontend both currently clean, nothing found), the other checks the actual
application images the same way once they're built. Both run on every change from now on,
the same way the existing correctness checks do. The development/staging blueprint also
now puts everything that touches documents on an internal network with no internet route,
so the "documents never leave" rule is enforced by the network itself, not just by code.
And the quality bar became a runnable pre-release check: any future change to the search
must re-pass your 77 ratified questions against the recorded bar before it ships.

**What's deliberately not automated yet, and why**: the hardening plan also calls for two
tools that test a *running* copy of the application from the outside, the way an attacker
would — rather than reading the code. Wiring those into the automatic checks would mean
building a small working copy of the whole system (database, backend, frontend, all
running together) inside the check pipeline itself, which is a much bigger piece of
infrastructure than the two checks above. That's deployment-pipeline work, done once there's
a staging copy of the system to point it at, not something to add to the automatic
per-change checks unilaterally.

Remaining in Phase 9: locking down the network path between services, and a restricted
database account for the AI side (both server-admin actions, not decisions — see
*Blockers*).

### Completed

| Phase | What it was |
|---|---|
| **Phase 0 — Review of what we already have** | Went through the existing system to see what could be kept. Answer: **almost all of it.** About two-thirds usable as-is, the rest needs adjusting, and essentially **nothing needs throwing away.** |
| **Phase 1 — Foundations and record-keeping** | Made the written record match reality, recorded your Gemini decision properly as a formal amendment, and put two safety nets in **before** any AI work: one fails the build if any part of the system starts making internet calls without that being deliberate, the other fails the build if the shape of the legal database changes. Also fixed a gap where about 250 automated checks were running but their results were being thrown away. |
| **Phase 2 — Database groundwork** | Built the separate storage area for the search index, kept completely apart from the legal data. |
| **Phase 3 — Search over uploaded documents** | Upload a contract and search it — by phrase, exact wording, or clause number — with no AI involved. Working and measured. |
| **Phase 4 — Smarter search** | Measured four candidate search models against your ratified test questions on the real documents, and picked the smallest one that met the bar — never the one that merely scored highest. Combined with plain search, it finds the right clause in the top ten essentially every time. |
| **Phase 5 — Answer safety checks** | Built and working, **before** the AI was connected: every sentence of an answer must cite its source, and the citation must actually support the claim — checked by code, not by the model. A fabricated answer is blocked and the user sees "not found," never the fabrication. |
| **Phase 6 — Gemini connected** | Wired behind a single switch-point, with a hard gate that refuses to send anything to Google in production until you confirm their written no-training terms — a setting cannot open that gate, only a recorded decision can. |
| **Phase 7 — The single workspace screen** | On the contract page you can now ask about an uploaded document; answers cite the clause and page, every score is labelled a "retrieval score" (never confidence), and a refusal reads as a calm "not found." |

### Coming next

| Phase | What it is | State |
|---|---|---|
| Phase 8 | Approved positions and statutes made searchable | Built 8 Sep (AB-14); awaits deployment and the operator steps below |
| Phase 9 | Security hardening and sign-off | **In progress** — dependency/image scanning done; network segmentation, restricted DB account, and the two live-instance scan tools remain |

---

## Blockers

Only genuine ones.

| # | What's blocked | Why | Blocks what |
|---|---|---|---|
| 1 | Sending **real customer contracts** to Google | Google's written promise not to train on our data hasn't been confirmed yet. Until it is, only test documents can be sent | Nothing yet. It stops us **finishing** the AI part, not starting it |
| 2 | ~~Making the **statutes** searchable~~ | **Cleared 8 Sep**: the missing Acts were obtained from India Code (the Government's official repository) and the supplied ones re-obtained from there, each with its source recorded. Only the Income-tax Act 2025 is still absent | — |
| 3 | Single sign-on ("RIAAS") | We don't have the technical details of how to connect to it. Normal login works fine meanwhile | Nothing. It can be added at any point |
| 4 | A restricted database account for the AI side | Creating it needs administrator access the application deliberately doesn't have. Ordinary server admin work, not a decision | Nothing yet |
| ~~5~~ | ~~Your review of the drafted test questions~~ | **Resolved 26 Aug** — you directed the set be used as-is ("Use questions_draft.json as the current evaluation dataset. Do NOT ask me to recreate these questions."). That is your ratification; the set is marked RATIFIED and both the model choice and the cut-off were measured against it | — |
| ~~6~~ | ~~Permission to add the software that runs a search model~~ | **Resolved 25 Aug** — approved and installed. Measured at 118MB, not the ~50MB I estimated when asking; I was wrong about the number, though not about the choice | — |

**A correction to something I told you earlier.** I previously said the database search add-on
must be version 0.8 or newer before we could proceed. **I tested it, and that was overstated.**
The version we have works correctly — it checks permissions *before* searching, exactly as
required, with no results missed. The newer version only matters later, for searching across
thousands of documents at once rather than within one. So this is no longer a blocker, and I have
not weakened the permission rule to get around it.

---

## Decisions needed from you

**One open item, raised in session 2026-09-01 (UI review):** you asked for a status covering
a clause the counterparty's document contains that has **no matching Requirement in our own
Company Standard** ("extra clause on their side"). This is real and useful, but it doesn't
exist in the engine today — it's the same gap CLAUDE.md's registry already names as
`UNMATCHED_PROVISION` ("Persistence, surfacing, and review treatment of `UNMATCHED_PROVISION`
observations" — explicitly **NOT YET SPECIFIED**). It was not built this session because its
legal meaning is a policy call, not an engineering one — precisely like the zero-tolerance
Legal Rule was your ruling, not a code choice.

**What needs deciding, once you're ready:** is an unmatched provision always routed to a
human (my recommendation — the system has no baseline to judge it against, so it fails
closed exactly like every other undecided path), and does it get its own classification
value or ride as a non-Finding "observation" the way the registry entry implies? Say the word
and this gets specified and built.

The two that previously stood here — supplying real test questions, and approving the
search-model software — were resolved on 25–26 August (see the struck-through rows 5 and 6 in
*Blockers*).

## What I'll need from you, and when

**Two actions are now genuinely due — everything else is built and waiting behind them.**
Unchanged since 25 August; your 26 August instruction to keep the gate closed until you
provide them has been logged and requires no new action from you.

### 1. Google's written data terms — the gate-opener

- **What:** written confirmation that our Gemini usage tier does **not** train on
  submitted content, and its data-retention terms. On the paid Gemini API tier Google
  publishes this in their terms; for Vertex AI it's part of the enterprise terms. What
  we need recorded: **which tier, and the date you confirmed it.**
- **Where:** your Google account/billing setup — this is a commercial confirmation only
  you can make on the company's behalf.
- **Why I can't do it:** it's a vendor-terms acceptance, and our own locked rule says
  the gate opens only by a recorded decision naming provider, tier and date.
- **What I do the moment you provide it:** append the release record, open the gate in
  the same change, and real documents can then get generated answers.

### 2. A Gemini API key

- **What:** one API key for the chosen tier.
- **Where it goes:** the server's environment as `LEGALMIND_GEMINI_API_KEY` — never in
  a file in the repository, never in a document. I'll never ask you to paste it in chat;
  set it on the server or hand it to whoever operates it.
- **Until then:** everything except the final generated sentence works — search,
  citations, refusals — and I've tested the generation path against a stand-in.

### 3. The Google client secret — due now, and it is the only thing between us and working Google sign-in

- **What:** the client secret for the LegalMind OAuth client you created in Google Cloud
  (project `legalmind-507306`). It looks like `GOCSPX-…`. Google no longer lets you *view*
  an existing secret, so if you don't have it saved, open that client and use **Add
  secret** to mint a new one — the old one keeps working until you delete it.
- **Where it goes:** the server's environment as `LEGALMIND_OIDC_CLIENT_SECRET`, exactly
  like the Gemini key — never in a file in the repository, never in a document, and I will
  never ask you to paste it in chat.
- **One more click while you're in there.** The client's **Authorized redirect URI** is
  currently `https://legalmind.lsnw.io`, and Google will reject that — a bare address with
  no path is not allowed there. It must be, exactly:

  ```
  https://legalmind.lsnw.io/api/v1/auth/oidc/callback
  ```

  (A bare address *is* valid in the **Authorized JavaScript origins** box above it, which
  is a different setting and one we don't need.)
- **Until then:** the button is live but will say sign-in is unavailable, and everyone
  signs in with email and password as they do today. Nothing is broken by waiting.
- **Worth deciding while you're there:** sign-in is currently restricted to
  `@leapswitch.com` addresses. Say the word if you want that opened up or changed.

### Later (not yet due)

| What | When | Why |
|---|---|---|
| ~~NI Act and Evidence Act, plus statute provenance confirmation~~ **Income-tax Act 2025 only** (the rest obtained 8 Sep from India Code / MeitY / Dept. of Revenue, provenance recorded) | Statute search — one Act | Official hosts unreachable; never substituted from an unofficial site |
| The curated judgment list | Statute-search phase | The plan says the legal team picks it |
| Production server actions | Deployment | pgvector install, the restricted `legalmind_assist` database account, network egress allow-list — root-level server steps, listed in the preflight report |

**On legal material generally:** we never write it ourselves. If something is missing, we ask.

## Two things worth knowing

**The AI will never be the judge.** Your instruction and the project's own rules agree here, and it's
built in structurally, not just intended: the AI cannot write to the legal records at all. It can
explain a verdict the rules engine reached. It cannot change one, and it cannot produce one.

**We won't say "87% confident".** A percentage next to a legal statement looks like precision and
isn't. Instead an answer says what it found and shows the source, or says clearly that it found
nothing. The project rules forbid the percentage, and that's the right call.

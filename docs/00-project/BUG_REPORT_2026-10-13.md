# LegalMind — Bug report, 13 October 2026 (tester pass)

**Status: 📁 ANALYSIS — a list of defects to review and fix. It decides nothing and amends no
locked decision.** Scope: the code that runs in production, `main` at `1246aab`.

## How this was found

- **Five read-only code reviews in parallel**, one each for the Ask lane, the analysis engine,
  API/auth/security, the frontend, and Diff-Talk/uploads/ops. Each bug was checked against the
  code, and many were reproduced with throwaway scripts against the test database. No repo
  file was changed.
- **A hands-on pass in a real browser** on a local copy of `1246aab` loaded with the same
  knowledge as production: Constitution L1.13, the ratified standards, and today's live
  SLA/TOS/AUP/Privacy pages. It covered three roles (ordinary user, counsel, department lead),
  every page, desktop (1280px) and phone (390px), and five real-user Ask probes.
- **Not tested:** production itself (the agent's safety check blocks production reads), the
  counterparty router and client-profile screen in depth (unchanged since 8 Oct), and
  performance under real load.

**Confidence:**
- **Confirmed:** reproduced, or certain from the code.
- **Likely:** the code path is clear, but it needs a particular input or the model's choice.

## Fix first — the top 10

| # | Bug | Why first |
|---|---|---|
| A1 | Affected-services cap read as total fees → false MATCH | Wrong legal result |
| A2 | Second limb of a cap ("lower of INR 50,000 and…") dropped → false MATCH | Wrong legal result |
| A3 | Word tracked changes / content controls silently dropped | A redline is invisible |
| A4 | Partly failed PDF analysed as complete → false MISSING | Wrong legal result |
| S1 | Any user can take over another department's client profile by id | Data access across departments |
| K1 | Ask judges a pasted clause against the standard (since today's #188) | Breaks "Ask never says whether it complies" |
| K2 | "temperature in…" refused as off-topic, including whole pasted emails | Real SLA questions refused |
| K3 | A fixed evaluator reply still runs a hidden Gemini turn | Cost, delay, document sent to Gemini |
| U1 | Document page unreadable on a phone | The core screen |
| O1 | Deploy wrapper updates the tree before taking the lock | A deploy can ship a mixture |

---

## A — Analysis engine (the authoritative lane)

### A1 · Critical · Confirmed — a cap on the affected services' fees is read as total fees, so a false MATCH
- **Where:** `backend/legalmind/extraction/liability.py:500-502` (`_find_basis`) and
  `backend/config/company_standards/LIABILITY-TOS-001.json` (`extraction.bases`).
- **What happens:** "…shall not exceed the total fees paid by you in the twelve (12) months
  preceding the claim **for the specific services giving rise to the claim**" is extracted
  as `FEES_PAID` and evaluates to **MATCH** against the 12-months-of-total-fees standard. It
  should not: CLAUDE.md requires `FEES_PAID` and `FEES_PAID_FOR_AFFECTED_SERVICES` to stay
  distinct, and an affected-services cap must fail closed.
- **Why:**
  - The clause matches both bases. Keys are visited in sorted order, so `FEES_PAID` (a prefix)
    always wins.
  - The TOS standard has no affected-services terms at all.
  - The SAME_POSITION de-duplication carries the result across to MSA.
- **Fix:** when more than one basis matches, take the most specific, or return none so the cap
  is UNKNOWN (fails closed).

### A2 · High · Confirmed — the second limb of a cap is silently dropped, so a false MATCH
- **Where:** `extraction/liability.py:297-320`, plus the `composite_phrases` list in both
  liability standards.
- **What happens:** "shall not exceed **the lower of INR 50,000 and** the total fees paid in
  the 12 months…" and "shall not exceed INR 10,00,000 **or** total fees paid in 12 months"
  both evaluate to **MATCH**.
- **Why:**
  - Only quantities in the configured units are seen, so a currency limb is invisible.
  - The composite-phrase list lacks "lower of" and a bare "or".
- **Fix:** treat any currency amount, or a second quantity beside the cap phrase, as a
  composite cap, which makes it UNKNOWN.

### A3 · High · Confirmed — Word tracked insertions and content controls are dropped, and the status still says COMPLETE
- **Where:** `backend/legalmind/ingestion/parsing.py:977-984` (`document.paragraphs` /
  `para.text`).
- **What happens:**
  - "the total fees paid in the `<del>12</del><ins>6</ins>` months" parses as "…paid in the
    months".
  - A paragraph inside a content control (`w:sdt`) disappears.
  - A counterparty's redline, an inserted "not", or an inserted carve-out is invisible, which
    risks a false MATCH. A clause in a content control gives a false MISSING.
- **Fix:** walk the body XML, including `w:ins` and `w:sdtContent`, or detect revisions or
  content controls and mark the extraction PARTIAL.

### A4 · High · Confirmed — a PDF with failed pages is analysed as complete, so a clause is asserted absent
- **Where:**
  - `ingestion/service.py:243-249` sets `processing_status=COMPLETED` for a PARTIAL extraction.
  - `analysis/service.py:871-908` (`assert_analysable`) checks only PENDING/PROCESSING.
  - `analysis/service.py:805-816` turns mapping NONE into MISSING.
- **What happens:** when the page holding the liability clause fails OCR, the result is
  **MISSING** ("required clause missing") with no evidence, instead of UNABLE_TO_EVALUATE.
  This breaks rule 15 (fail closed).
- **Fix:** when `extraction_status` is PARTIAL, downgrade every mapping-NONE result to
  UNABLE_TO_EVALUATE, or refuse the analysis.

### A5 · Medium · Confirmed — a wrapped PDF line starting with a number becomes a fake clause
- **Where:** `ingestion/parsing.py` `_CLAUSE_PATTERNS`, second pattern (~line 192).
- **What happens:** "13.1 … total fees paid in the\n12 months preceding the claim." splits into
  "13.1 … in the" and a fake section "12". The cap reads UNKNOWN, and citations show wrong
  section numbers.
- **Fix:** with no dot or sub-level, require a capitalised title, and never accept a number
  followed by a lowercase word.

### A6 · Medium · Likely — the model-read cap (AM-54 stage 2) is only loosely verified
- **Where:** `analysis/semantic.py:347-349` and `extraction/liability.py:482`.
- **What happens:** the value and the unit only need to appear somewhere in the span, so
  "capped at INR **12,000** per **month**" verifies "12 MONTHS". `number_in_text` also splits
  "12,000".
- **Fix:** verify with the same number-then-unit pattern `_find_magnitude` uses.

### A7 · Medium · Likely — SAME_POSITION de-duplication can keep the copy whose mapping failed
- **Where:** `analysis/service.py:668-683`.
- **What happens:** in a TOS document the MSA copy confirms the clause, but the TOS copy failed
  and is the one kept. The result is UNABLE or MISSING despite the evidence. Four signatures
  collide today: LIABILITY MSA/TOS, GOVLAW ×3, ARBITRATION ×2 and RETURN-DESTRUCTION ×2.
- **Fix:** prefer a CONFIRMED copy, then break ties by declared type.

### A8 · Low · Confirmed — the numeric evaluator never gives ACCEPTABLE on MATCH
- **Where:** `evaluation/numeric.py:332-334` returns NOT_APPLICABLE on MATCH.
  `presence.py:86` returns ACCEPTABLE.
- **What happens:** the two evaluators disagree, and CLAUDE.md says MATCH → ACCEPTABLE.
  Behaviour is safe (no auto-approval), but it is inconsistent.
- **Fix:** decide which is intended (an owner question if needed), then align.

---

## S — Security, authorization, API

### S1 · High · Confirmed (reproduced) — taking over another department's client profile by linking to it
- **Where:** `api/routers/contracts.py:337-339` (`POST /contracts`) and `:426-428`
  (`PATCH /contracts/{id}`).
- **What happens:** User B gets 404 on user A's client profile. B creates a contract with
  `counterparty_id = <A's id>` and gets 201. B can now read A's relationship notes and activity,
  and rename or edit the client for everyone. The 201-versus-error reply also confirms whether
  an id exists.
- **Why:** both routes only check that the id exists, and visibility is "any contract I own
  points at it".
- **Fix:** resolve through `counterparties._readable(guard, id)`, and return the standard 404
  when out of scope.

### S2 · Medium-High · Confirmed (reproduced) — read-only scope can escalate and withdraw escalations, even on archived contracts
- **Where:** `api/routers/findings.py:82,110` and `workflow/escalation.py:37,74`.
- **What happens:**
  - A department lead (read scope) can escalate a colleague's Finding. That exposes the
    contract to every Legal reviewer. This works even on an archived contract.
  - Any Legal-scope reader can silently withdraw the owner's escalation.
  - This breaks "writes are owner-only" (AB-12).
- **Fix:** after `guard.finding`, require owner scope (and refuse archived contracts), or a
  deliberate Legal-scope rule.

### S3 · Medium · Confirmed (reproduced) — the CSRF check is skipped for token-only sessions
- **Where:** `api/context.py:118-121` (`CsrfMiddleware`).
- **What happens:** after an OIDC login, the session and CSRF cookies expire at 12 h but the
  AM-36 token lives 24 h. In hours 12–24, writes are accepted with no CSRF token. SameSite=Strict
  does not stop requests from another `*.lsnw.io` subdomain.
- **Fix:** enforce CSRF when either cookie is present, and give the CSRF cookie the token's
  lifetime.

### S4 · Medium · Confirmed — Key Obligations scopes are swapped
- **Where:** `api/routers/assist.py:182` (POST extract) and `:219` (GET read).
- **What happens:**
  - A department lead can trigger a Gemini extraction on a colleague's version, including an
    archived one, and that blocks the owner's re-read (`documents.py:127`).
  - The owner gets 409 reading obligations on their own archived contract.
- **Fix:** use owner scope on POST and read scope on GET.

### S5 · Medium · Confirmed — a Platform Admin can grant themselves DEVELOPER
- **Where:** `security/guards.py:40-49` (the S-8 list) and `admin.py:296-297`.
  Self-administration is exempt at `guards.py:59`.
- **What happens:** the admin gains almost every permission except legal decisions, moves
  themselves into any department, and reads its deals and escalated reviews. `PATCH /roles`
  already blocks this; `grant_role` does not.
- **Note:** S-8's wording is locked, so this **may need your decision**.
- **Fix:** refuse a self-grant, or apply the same full-set check as `update_role`.

### S6 · Low-Medium · Confirmed — cross-owner reads through review and finding routes are not audited
- **Where:** `api/deps.py:232-245` (`Guard.review` / `finding` / `evaluation`).
- **What happens:** a department lead reading `/reviews/{id}/report` (verbatim clauses) leaves
  no audit row. The same read through `/contracts/{id}` is audited.
- **Fix:** call `_audit_cross_owner_read` from these guards too.

### S7 · Low · Confirmed — Diff-Talk choices on two website pages are global, writable by anyone, and unaudited
- **Where:** `api/routers/documents.py:440-447` and `document_comparison.write_choices`.
- **What happens:** any user can overwrite the shared choices for a website-vs-website pair, and
  no change is audited.
- **Fix:** restrict website-only pairs to a configuration-level permission, and audit every
  write.

---

## K — Ask (assist lane)

### K1 · High · Confirmed (hands-on) — Ask judges a pasted clause against the company standard · **regression from today's #188 (`AM-138`)**
- **What happens:** I pasted a liability clause (3 months of fees) with no question on the Ask
  page. The answer said "*the 3-month cap represents a deviation from the company's standard
  12-month position*".
- **Why it's a bug:** Ask must never say whether something complies; that is the evaluator's
  (rule 10, `AM-25` r4, `AM-133` r2). Before #188 this paste got a fixed reply. Now the model
  is told "do what it asks, or summarise", and it went further and judged the clause.
- **Where:** `assist/agent/agent.py` `_final_instruction` (the pasted-text line), and the
  agent verifier, which has no compliance-verdict screen.
- **Fix:**
  - Tell the model to summarise and never compare a pasted text with company positions unless
    explicitly asked. Even then, route to the Dashboard (`AM-133` r2).
  - Add a verifier screen that drops "deviation / complies / meets the standard" sentences.

### K2 · High · Confirmed — ordinary hosting and SLA questions refused as off-topic
- **Where:** `assist/query/conversational.py:175-180` (`_OFF_SCOPE`), run by `service.preroute`
  on both paths.
- **What happens:**
  - "What does the SLA say about **temperature in** the data hall?" gets "I can't help with
    that here".
  - Since #188, a whole pasted incident email mentioning "temperature in rack B4" gets the same
    refusal.
- **Why:** a weather pattern (`temperature … in`) is searched anywhere in the text.
- **Fix:** anchor off-scope patterns to the start of a short message, drop "temperature … in",
  and never run `off_scope` on pasted material.

### K3 · High · Confirmed — a fixed evaluator reply still runs a full hidden Gemini turn
- **Where:** `assist/service.py:993-1036`.
- **What happens:** in a chat with a document, "Does this clause comply with our standard?"
  gets the instant evaluator reply. Then `agent.shadow()` runs a full Gemini turn and throws it
  away. That is paid, slow, and sends the document to Gemini even when Bonsai or DeepSeek was
  chosen.
- **Why:** AM-135 added a new way into `_ask` while the agent mode is `on`, and the shadow block
  assumes otherwise.
- **Fix:** run the shadow block only when `ask_agent_mode() == "shadow"`.

### K4 · Medium · Confirmed — a long paste with no question gets contradictory instructions · related to #188
- **Where:** `agent/agent.py:435-468` with `query/presentation.py`.
- **What happens:**
  - `PASTE_REQUEST` is read as "a short summary, under 60 words". That instruction sits right
    above "work out what it asks", so a request like "quote the clause" competes with the
    60-word limit.
  - The first search uses the fixed sentence as its query.
- **Fix:** skip `presentation.read` for `PASTE_REQUEST`, and seed the search from the material.

### K5 · Medium · Confirmed (hands-on) — a differently worded compliance question on the Ask page reaches the model
- **What happens:** "Does our MSA meet the company standards on liability?" on the Ask page
  (no document) got a model answer that lists standards and says it "cannot be determined".
  It should get the fixed "upload it on the Dashboard" reply (`AM-133` r2), which "Compare
  this agreement with our standards" does get. No verdict was given, but the routing is
  inconsistent.
- **Also:** a fully Devanagari compliance question ("क्या यह क्लॉज़ हमारे स्टैंडर्ड के अनुरूप
  है?") is not caught either. Its romanised and English forms are (AM-69: language is not a
  safety boundary).
- **Fix:** widen `intent.weighs_our_position` (meet / comply / in line with + standards), and
  add Devanagari cues.

### K6 · Medium · Confirmed — the answer cache merges Hindi questions that differ only in vowel signs
- **Where:** `assist/retrieval/cache.py:157-158` (`normalized`).
- **What happens:** "पहले नोटिस" and "पहला नोटिस", or "है" and "हैं", normalise to the same text.
  The same user is served the cached answer to the other question.
- **Fix:** NFC + casefold, stripping only punctuation and symbols, and keeping combining marks.

### K7 · Medium · Likely — `find_documents` returns the newest version, undoing A-100's "the version you have open"
- **Where:** `assist/agent/tools.py:973-989`.
- **What happens:** with version 1 open, if the model looks the document up by name it gets
  version 2's id and can answer from it.
- **Fix:** for the selected contract, return `selected_version(ctx)`.

### K8 · Low-Medium · Confirmed — `find_documents` applies LIMIT 200 before the permission filter
- **Where:** `assist/agent/tools.py:974-982`.
- **What happens:** with a common word ("leapswitch", "msa") and over 200 matches
  organisation-wide, documents the reader may read can never be found.
- **Fix:** filter in SQL, or apply the limit after filtering.

### K9 · Low-Medium · Confirmed — "Ask about this finding" loses the Finding on the agent path
- **Where:** `assist/service.py:997-998` (`_agent_answer` takes no `finding_id`).
- **What happens:** the Finding's evidence is never seeded, so the answer relies on the question
  text alone, and a follow-up can't inherit it.
- **Fix:** pass `finding_id` through, and pin its evidence ids as seed evidence.

### K10 · Low · Confirmed (hands-on) — a pasted clause is titled "Clause 9."
- **What happens:** the title rule (first sentence, 80 characters max, from #188) cuts at the
  dot in "Clause 9.".
- **Fix:** don't treat a dot after a clause number as a sentence end, or use the first
  sentence of at least 3 words.

---

## U — Frontend

### U1 · High · Confirmed (hands-on, screenshot) — the document page is unreadable on a phone
- **What happens:** at 390px the Contents panel and the document sit side by side. The document
  is ~100px wide and words break mid-word ("Limita / of / Liabili").
- **Fix:** below ~860px, stack the panes, or collapse Contents into a drawer, as the Ask page
  already does.

### U2 · Medium · Confirmed — an edited question is silently dropped while another chat is answering
- **Where:** `AskWorkspace.tsx:535`, `askThread.ts:181-186`, `ui/thread.tsx:239-251`; the dock
  has the same gap (`AskDock.tsx:197`).
- **What happens:** while chat A is answering, open chat B, edit a question and click Send. The
  editor closes, nothing is sent, and the edit is lost.
- **Fix:** hide or disable Edit while `busy`, or keep the editor open with a message.

### U3 · Medium · Confirmed (hands-on) — the top menu is cut off on a phone
- **What happens:** at 390px the menu shows "Dashboard  Client P…". Diff-Talk and Ask are off
  screen, with no sign the menu scrolls.
- **Fix:** a menu button (drawer) on narrow screens, or a visible scroll affordance.

### U4 · Medium · Likely — Diff-Talk's pinned header and scroll-follow can fail to set up
- **Where:** `components/diff-talk/Review.tsx:101-110,173` and `useReviewNavigation.ts:84-90`.
- **What happens:** when the comparison loads before the choices, the effects run on the
  skeleton and never re-run. The sticky offsets fall back to 64px, and the change list stops
  following the scroll.
- **Fix:** gate `ready` on both loads.

### U5 · Low-Medium · Confirmed — a file attached in one chat is sent with a question in another
- **Where:** `AskWorkspace.tsx:365-418` (the `activeId` effect never clears `attachment`).
- **What happens:** add a file in chat A, switch to chat B, and send there. The file is uploaded
  into B.
- **Fix:** clear `attachment` when the chat changes, as `resetChat` already does.

### U6 · Low · Likely — Escape during IME composition closes the document-page Ask panel
- **Where:** `AskDock.tsx:325-330`.
- **Fix:** ignore Escape when `event.isComposing || keyCode === 229`, reusing `isImeEnter`.

### U7 · Low · Confirmed — the original-PDF object URL leaks when the version changes mid-load
- **Where:** `DocumentPane.tsx:1056-1072`.
- **Fix:** check `cancelled` before `URL.createObjectURL`.

### U8 · Low · Confirmed — the dock's failed-edit reload can paint the old chat into a newly opened one
- **Where:** `AskDock.tsx:228-229`.
- **Fix:** call `setTurns` only if `conversationRef.current === askedIn`.

### U9 · Low · Confirmed (hands-on) — pages request data the role can't see
- **What happens:** for an ordinary user:
  - Client Profiles calls `GET /departments/mine/members` → 403 on every load;
  - the admin pages call `/users`, `/departments` and `/audit-events` → 403 before showing
    "Access restricted";
  - Configuration calls `/requirements` → 403.
- **Impact:** the screens handle it correctly, but every visit logs console errors and wasted
  requests.
- **Fix:** check the permission before fetching.

### U10 · Low · Confirmed (hands-on) — the Dashboard search box is squeezed on a phone
- **What happens:** the placeholder shows as "Searc…" at 390px.

---

## O — Diff-Talk, uploads, deploy and operations

### O1 · High · Confirmed — the deploy wrapper updates the deploy tree before it takes the lock
- **Where:** `/usr/local/sbin/legalmind-deploy` (`git merge --ff-only` before
  `bash ops/deploy.sh`) and `ops/deploy.sh:39-44` (the `flock`).
- **What happens:** while deploy A is building commit X, deploy B fast-forwards the tree to Y
  and only then is refused. A's build mixes X and Y, and the next restart silently loads Y.
- **Fix:** take the lock in the wrapper before `git fetch`/`merge`.

### O2 · Medium · Confirmed — `deploy-frontend.sh` takes no lock
- **Where:** `frontend/scripts/deploy-frontend.sh:135-149` (run by `npm run deploy`).
- **What happens:** `npm run deploy` during `sudo legalmind-deploy` gives the mixed build the
  lock exists to prevent.
- **Fix:** take the same lock, without deadlocking when `deploy.sh` holds it.

### O3 · Medium · Confirmed — frontend pre-checks run after the backend is migrated and restarted
- **Where:** `ops/deploy.sh:47-98`.
- **What happens:** a `package-lock.json` change is refused only after the API runs new code, so
  the site is left half-deployed. The message says `npm install`, but a `legalmind-dev` user
  can't write the tree.
- **Fix:** run the dependency, dirty-tree and `tsc` checks before any migration or restart.

### O4 · Medium · Confirmed (reproduced) — Diff-Talk folds a clause the client added into its neighbour
- **Where:** `analysis/document_comparison.py:133-155` (`_merge_once`) and `_score:98-106`.
- **What happens:** with ours "1. Liability, 2. Governing Law" and theirs adding
  "2. Non-Solicitation", the new clause is shown inside Liability as CHANGED, and there is no
  ADDED row.
- **Fix:** never fold a numbered clause, and fold only when word order improves.

### O5 · Medium · Confirmed — two uploads to one contract at once → 500 and an orphaned stored file
- **Where:** `ingestion/service.py:80-85` (`max(version_number)+1`) and `:114` (stores before
  flushing).
- **Fix:** lock the contract row before numbering, or catch `IntegrityError` and return 409.

### O6 · Medium · Likely — the daily policy refresh accepts a page that suddenly grew
- **Where:** `assist/knowledge/published.py:279-296`.
- **What happens:** after a site redesign, footer or promo text is extracted with the policy.
  The word count grows, every check passes, and the broken page becomes CURRENT for Ask and
  Diff-Talk.
- **Fix:** refuse a large growth (>1.5×) or a sharp change in heading count, and count words
  the same way on both sides.

### O7 · Low/Medium · Confirmed (synthetic) — Diff-Talk alignment slows steeply with clause count
- **Where:** `document_comparison.py:171-175`.
- **What happens:** 100 clauses take 0.5 s, 200 take 6.5 s, and 300 had not finished after 2
  minutes. It is recomputed on every page reload.
- **Fix:** compute the similarity matrix once and update only what a fold touches, or refuse
  very long documents with a clear message.

### O8 · Low — smaller items
- **Two CURRENT copies of one policy are possible:** there is no partial unique index on
  `knowledge_sources(source_type) WHERE status='CURRENT'`.
- **Hidden earlier-version choices still count against the cap:** `write_choices`
  (`document_comparison.py:499`) breaks AB-81 r6.
- **A failed import of browser-saved choices hides every stored choice:**
  `useChoices.ts:33-36`, and it repeats on every load.

---

## Checked and clean (no action)

- **Permissions:** every route is in the permission map, and every map entry exists.
- **Hidden objects:** an object outside your scope gets the same 404 as one that doesn't exist.
- **Confidential fields:** omitted, not nulled.
- **Legal decisions:** no role can reach legal decisions without an explicit grant.
- **Input bounds:** request sizes, string lengths and the page size are all capped.
- **Database queries:** no user input is written into SQL.
- **Rate limits:** applied per user and per real client IP.
- **Unit conversion:** exact for every multiple from 1 to 400.
- **SLA credits:** never read as a liability cap.
- **Zero-tolerance rule:** handled correctly.
- **Repeat analyses:** give the same result.
- **Ask:**
  - chat ownership is checked on every request;
  - the edit-replace flow (AM-134) works;
  - the cache keys cover what they should;
  - the website-policy refresh fails safe when the site is down;
  - the withdrawn fixed replies are gone everywhere.
- **Frontend:** API parameters match the backend, every internal link works, listeners are
  cleaned up, Enter during IME composition is handled, and no confidence or probability is
  shown anywhere.
- **Browser pass, all pages, three roles, desktop and phone:** no page crashes, no server
  errors, no sideways scrolling.
- **Priyen's three 8 Oct questions:** answered correctly (see `DAILY_CHANGES` 2026-10-13).

## Needs the owner, not just a fix

- **A8:** should MATCH give ACCEPTABLE in the numeric evaluator too?
- **S5:** S-8's locked list. Should a Platform Admin be stopped from granting themselves roles?
- **K1:** it touches `AM-138`, which shipped today. The suggested fix only tightens it.
